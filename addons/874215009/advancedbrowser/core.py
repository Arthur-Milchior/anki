# -*- coding: utf-8 -*-
# See github page to report issues or to contribute:
# https://github.com/hssm/advanced-browser

import time
from operator import  itemgetter

from aqt import *
from aqt.browser import DataModel, Browser, StatusDelegate
from anki.hooks import runHook, addHook
from anki.cards import Card
from .contextmenu import ContextMenu
from .column import Column, CustomColumn

CONF_KEY = 'advbrowse_activeCols'

class AdvancedDataModel(DataModel):
    
    def __init__(self, browser):
        """Load our copy of the active columns and suppress the built-in one.

        This function runs after custom columns have been registered, so our
        list of custom types has already been populated."""
        super(AdvancedDataModel, self).__init__(browser)

        # Keep a reference to this function; we need the original later
        self._columnData = DataModel.columnData

        # Model->flds cache, similar to self.cardObjs
        self.modelFldObjs = {}

        # Keep a copy of the original active columns to restore on closing.
        self.origActiveCols = list(self.activeCols)

        configuredCols = mw.col.conf.get(CONF_KEY, None)
        if configuredCols:
            # We've used this add-on before and have a configured list of columns.
            # Adjust activeCols to reflect it.

            # Make sure the columns we are loading are still valid. If not, we
            # just ignore them. This guards against the event that a column is
            # removed or renamed.
            #
            # The list of valid columns are the built-in ones + our custom ones.
            valids = set([c[0] for c in browser.columns] + list(browser.customTypes.keys()))

            self.activeCols = [col for col in configuredCols if col in valids]

            # Also make sure the sortType is valid
            if mw.col.conf['sortType'] not in valids:
                mw.col.conf['sortType'] = 'noteFld'
                # If there is no sorted column, we add the 'Sort Field' column
                # and sort on that. This method is one way to guarantee that we
                # always start with at least one valid column.
                if 'noteFld' not in self.activeCols:
                    self.activeCols.append('noteFld')

    def getFld(self, index):
        """"
        Field cache, similar to getCard().
        This method only exists to make fetching field settings efficient in
        order to determine if it is RTL.
        """
        model = self.getCard(index).note().model()
        id = model['id']
        fldName = self.activeCols[index.column()]
        if fldName.startswith("_field_"):
            fldName = fldName[7:]
        else:
            # This custom column is not a field column
            return None
        if id not in self.modelFldObjs:
            self.modelFldObjs[id] = {}
        if fldName not in self.modelFldObjs[id]:
            flds = [f for f in model['flds'] if f['name'] == fldName]
            if len(flds) == 0:
                # This model does not have a field with that name
                self.modelFldObjs[id][fldName] = None
            else:
                self.modelFldObjs[id][fldName] = flds[0]
        return self.modelFldObjs[id][fldName]

    def data(self, index, role):
        if role == Qt.TextAlignmentRole:
            col = self.activeCols[index.column()]
            if col in self.browser.customTypes:
                # If this is one of our columns, use custom alignment rules
                align = Qt.AlignVCenter | Qt.AlignLeft
                return align
        return super(AdvancedDataModel, self).data(index, role)

    def columnData(self, index):
        # Try to handle built-in Anki column
        returned = self._columnData(self, index)
        if returned:
            return returned
        
        # If Anki can't handle it, it must be one of ours.
        col = index.column()
        type = self.columnType(col)
        c = self.getCard(index)
        n = c.note()

        if type in self.browser.customTypes:
            return self.browser.customTypes[type].onData(c, n, type)

    def search(self, txt):
        """We swap out the col.findCards function with our custom myFindCards,
        call the original search(), then put it back to its original version.

        if the configuration uniqueNote holds, cards are filtered to keep only one card by note.
        """
        self.beginReset()
        orig = self.col.findCards
        self.col.findCards = self.myFindCards
        super(AdvancedDataModel, self).search(txt)
        if mw.col.conf.get("advbrowse_uniqueNote", False):
            nids = set()
            filtered_card = []
            for cid in self.cards:
                card = Card(mw.col, cid)
                nid = card.nid
                if nid not in nids:
                    filtered_card.append(cid)
                    nids.add(nid)
            self.cards = filtered_card
        self.col.findCards = orig
        self.endReset()


    def myFindCards(self, query, order):
        """This function takes over the call chain of
        Collection.findCards -> Finder.findCards but only handles custom
        columns maintained by the add-on. If we find that the column
        to be sorted is a built-in column, we defer to the original
        Finder.findCards.
        
        Our version differs in its approach by building a more
        efficiently sortable query for the cases where it makes sense
        to do so."""
        
        finder = anki.find.Finder(self.col)
        cTypes = self.browser.customTypes

        # If the column is not a custom one handled by this add-on, do it
        # internally.
        type = self.col.conf['sortType']
        if type not in cTypes:
            return finder.findCards(query, order=True)
        
        # We bypass _query() and _order and write our own combined version
        #
        # NOTE: the "order by x is null, x is '', x is X" pattern is to
        # ensure null values and empty strings are sorted after useful
        # values. The default is to place them first, which we don't want.
        
        tokens = finder._tokenize(query)
        preds, args = finder._where(tokens)
        if preds is None:
            return []
    
        if preds:
            preds = "(" + preds + ")"
        else:
            preds = "1"
        
        order = cTypes[type].onSort()
                
        t = time.time()
        drop = False
        
        if not order:
            #print("NO SORT PATH")
    
            if "n." not in preds:
                sql = "select c.id from cards c where "
            else:
                sql = "select c.id from cards c, notes n where c.nid=n.id and "
            sql += preds
        elif cTypes[type].cacheSortValue or "select" in order.lower():
            # Use a temporary table to store the results of the ORDER BY
            # clause for efficiency since we repeatedly access those values.
            #print("TEMP SORT TABLE PATH")
            try:
                if "n." not in preds:
                    tmpSql = ("create temp table tmp as select *, %s as srt "
                              "from cards c where %s" % (order, preds))
                else:
                    tmpSql = ("create temp table tmp as select *, %s as srt "
                              "from cards c, notes n where c.nid=n.id and %s"
                               % (order, preds))
                
                #print("Temp sort table sql: " + tmpSql)
                self.col.db.execute(tmpSql, *args)
                drop = True
                args = {} # We've consumed them, so empty this.
            except Exception as ex:
                #print("Failed to create temp sort table: ", ex)
                return []

            sql = ("""
select id, srt from tmp order by tmp.srt is null, tmp.srt is '',
case when tmp.srt glob '*[^0-9.]*' then tmp.srt else cast(tmp.srt AS real) end
collate nocase""")
            
        else:
            # This is used for the remaining basic columns like internal fields
            #print("NORMAL SORT PATH")
            
            if "n." not in preds and "n." not in order:
                sql = "select * from cards c where "
            else:
                sql = "select * from cards c, notes n where c.nid=n.id and "
        
            sql += preds
            sql += ("""
order by %s is null, %s is '',
case when (%s) glob '*[^0-9.]*' then (%s) else cast((%s) AS real) end
collate nocase """ %
                    (order, order, order, order, order))
    
        try:
            #print("sql :" + sql)
            res = self.col.db.list(sql, *args)
        except Exception as ex:
            #print("Error finding cards:", ex)
            return []
        finally:
            if drop:
                self.col.db.execute("drop table tmp")
    
        if self.col.conf['sortBackwards']:
            res.reverse()
            
        #print("Search took: %dms" % ((time.time() - t)*1000))
        return res

class AdvancedStatusDelegate(StatusDelegate):
    def paint(self, painter, option, index):
        fld = self.browser.model.getFld(index)
        if fld and fld['rtl']:
            option.direction = Qt.RightToLeft
        return super(AdvancedStatusDelegate, self).paint(painter, option, index)


class AdvancedBrowser(Browser):
    """Maintains state for the add-on."""
    
    def newBrowserInit(self, mw):
        """Init stub to allow us to construct a Browser without doing
        the setup until we need to."""
        QMainWindow.__init__(self, None, Qt.Window)
    
    def __init__(self, mw):
        # Override Browser __init_. We manually invoke the original after
        # we use our stub one. This is to work around the fact that super
        # needs to be called on Browser before its methods can be invoked,
        # which add-ons need to do in the hook.
        origInit = Browser.__init__
        Browser.__init__ = self.newBrowserInit
        super(AdvancedBrowser, self).__init__(mw)
        
        # A list of columns to exclude when building the final column list.
        self.columnsToRemove = []
        
        # CustomColumn objects maintained by this add-on.
        # {type -> CustomColumn}
        self.customTypes = {}
        
        # Let add-ons add or remove columns now.
        runHook("advBrowserLoaded", self)
        
        # Build the actual browser, which now has our state in it,
        # and restore constructor.
        origInit(self, mw)
        Browser.__init__ = origInit


        tn = QAction(('- Only show notes -'), self)
        tn.setShortcut(QKeySequence("Ctrl+Alt+N"))
        self.addAction(tn)
        tn.triggered.connect(self.toggleUniqueNote)


        # Remove excluded columns after the browser is built. Doing it here
        # is mostly a compromise in complexity. The alternative is to
        # rewrite the order of the original __init__ method, which is
        # cumbersome and error-prone.
        self.__removeColumns()

        # Workaround for double-saving (see closeEvent)
        self.saveEvent = False

    def newCustomColumn(self, type, name, onData, onSort=None,
                 cacheSortValue=False):
        """Add a CustomColumn to the browser. See CustomColumn for a
        detailed description of the parameters."""
        cc = CustomColumn(type, name, onData, onSort, cacheSortValue)
        self.customTypes[cc.type] = cc
        return cc
    
    def removeColumn(self, type):
        """Remove a column from the columns list so that it will not appear
        in the browser. Applies to built-in or custom columns."""
        self.columnsToRemove.append(type)

    def __removeColumns(self):
        for type in self.columnsToRemove:
            # Remove from ours
            if type in self.customTypes:
                self.customTypes.pop(type, None)
            
            # Built-in list is a list of tuples.
            self.removedBuiltIns = []
            for tup in list(self.columns):
                if tup[0] == type:
                    self.removedBuiltIns.append(tup)
                    self.columns.remove(tup)
            
            # Remove it from the active columns if it's there.
            if type in self.model.activeCols:
                self.toggleField(type)

    def setupTable(self):
        """Some customizations to the table view"""
        super(AdvancedBrowser, self).setupTable()
        self.form.tableView.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.form.tableView.setItemDelegate(AdvancedStatusDelegate(self, self.model))

    def setupColumns(self):
        """Build a list of candidate columns. We extend the internal
        self.columns list with our custom types."""
        super(AdvancedBrowser, self).setupColumns()
        for type in self.customTypes:
            self.columns.append((self.customTypes[type].type,
                                 self.customTypes[type].name))
        self.columns.sort(key=itemgetter(1))
    
    def onHeaderContext(self, pos):
        """Override the original onHeaderContext. We are responsible for
        building the entire menu, so we include the original columns as
        well."""
        
        gpos = self.form.tableView.mapToGlobal(pos)
        main = QMenu()
        contextMenu = ContextMenu()
        
        # We are also a client and we need to add the built-in columns first.
        for item in self.columns:
            type, name = item
            if type not in self.customTypes:
                contextMenu.addItem(Column(type, name))


        # Now let clients do theirs.
        runHook("advBrowserBuildContext", contextMenu)

        def addCheckableAction(menu, type, name):
            a = menu.addAction(name)
            a.setCheckable(True)
            a.setChecked(type in self.model.activeCols)
            a.toggled.connect(lambda b, t=type: self.toggleField(t))
    
        # For some reason, sub menus aren't added if we don't keep a
        # reference to them until exec, so keep them in this list.
        tmp = []
        # Recursively add each item/group.
        def addToSubgroup(menu, items):
            for item in items:
                # TODO: this isn't great :(
                if isinstance(item, ContextMenu):
                    sub = QMenu(item.name)
                    tmp.append(sub)
                    menu.addMenu(sub)
                    addToSubgroup(sub, item.items())
                else:
                    addCheckableAction(menu, item.type, item.name)
        # Start adding from the top
        addToSubgroup(main, contextMenu.items())

        # Add unique note toggle
        a = main.addAction("- Only show notes -")
        a.setCheckable(True)
        # This shortcut has no effect since it's attached to the context menu
        # which needs to be open, but the visual indicator is still useful.
        # The real shortcut is in init.
        a.setShortcut(QKeySequence("Ctrl+Alt+N"))
        a.setChecked(mw.col.conf.get("advbrowse_uniqueNote", False))
        a.toggled.connect(self.toggleUniqueNote)

        main.exec_(gpos)

    def closeEvent(self, evt):
        """Preserve our column state in a collection preference."""
        
        # After we save our columns, we restore activeCols to the original
        # copy that Anki maintains and allow it to resume its own save
        # routine unhindered by our unsupported columns.
        # When the add-on resumes on next startup, we replace activecols
        # again with our own version.
        # NOTE: we use a flag to check if we have performed this action before
        # as a workaround to this function being called twice and overriding
        # the custom columns with the original columns.

        if not self.saveEvent:
            # Save ours
            mw.col.conf[CONF_KEY] = self.model.activeCols
            # Restore old
            self.model.activeCols = self.model.origActiveCols
            # Restore built-in columns we removed
            self.columns.extend(self.removedBuiltIns or [])
            # Only save once
            self.saveEvent = True

        # Let Anki do its stuff now
        super(AdvancedBrowser, self).closeEvent(evt)

    def toggleUniqueNote(self):
        self.model.beginReset()
        mw.col.conf["advbrowse_uniqueNote"] =  not  mw.col.conf.get("advbrowse_uniqueNote", False)
        self.onSearchActivated()
        self.model.endReset()


# Override DataModel with our subclass
aqt.browser.DataModel = AdvancedDataModel

# Make Anki load AdvancedBrowser instead of the original Browser
aqt.dialogs._dialogs['Browser'] = [AdvancedBrowser, None]


