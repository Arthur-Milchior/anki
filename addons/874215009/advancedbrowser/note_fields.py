# -*- coding: utf-8 -*-
# See github page to report issues or to contribute:
# https://github.com/hssm/advanced-browser

from aqt import *
from aqt.main import AnkiQt
from anki.hooks import addHook, wrap
from .config import getEachFieldInSingleList

class NoteFields:
    
    def onAdvBrowserLoad(self, advBrowser):
        # Dictionary of field names indexed by "type" name. Used to
        # figure out if the requested column is a note field.
        # {type -> name}
        self.fieldTypes = {}

        # Dictionary of dictionaries to get position for field in model.
        # We build this dictionary once to avoid needlessly finding the
        # field order for every single row when sorting. It's
        # significantly faster that way.
        # {mid -> {fldName -> pos}}
        self.modelFieldPos = {}

        # Dictionary of columns. A column can exist in multiple places, because
        # different note types may have the same field name.
        # {fld['name'] -> CustomColumn}}
        self.customColumns = {}

        self.advBrowser = advBrowser
        self.buildMappings()



    def onBuildContextMenu(self, contextMenu):
        # Models might have changed so rebuild our mappings.
        # E.g., a field or note type could have been deleted.
        self.buildMappings()
        
        # Create a new sub-menu for our columns
        fldGroup = contextMenu.newSubMenu(" - Fields -")
        if getEachFieldInSingleList():
            # And an option for each fields
            for model in mw.col.models.models.values():
                for fld in model['flds']:
                    fldGroup.addItem(self.customColumns[fld['name']])
        else:
            # And a sub-menu for each note type
            for model in mw.col.models.models.values():
                modelGroup = fldGroup.newSubMenu(model['name'])
                for fld in model['flds']:
                    modelGroup.addItem(self.customColumns[fld['name']])


    def buildMappings(self):
        for model in mw.col.models.all():
            # For some reason, some mids return as unicode, so convert to int
            mid = int(model['id'])
            # And some platforms get a signed 32-bit integer from SQlite, so
            # we will also provide an index to that as a workaround.
            mid32 = (mid + 2**31) % 2**32 - 2**31
            self.modelFieldPos[mid] = {}
            self.modelFieldPos[mid32] = {}
            # For each field in this model, store the ordinal of the
            # field with the field name as the key.
            for field in model['flds']:
                name = field['name']
                ord = field['ord']
                type = "_field_"+name  # prefix to avoid potential clashes
                self.modelFieldPos[mid][name] = ord
                self.modelFieldPos[mid32][name] = ord
                if type not in self.fieldTypes:  # avoid dupes
                    self.fieldTypes[type] = name

        # Convenience method to create lambdas without scope clobbering
        def getOnSort(f):
            return lambda: f

        def fldOnData(c, n, t):
            field = self.fieldTypes[t]
            if field in c.note().keys():
                return anki.utils.htmlToTextLine(c.note()[field])

        for type, name in self.fieldTypes.items():
            if name not in self.customColumns:
                srt = ("(select valueForField(mid, flds, '%s') "
                       "from notes where id = c.nid)" % name)

                cc = self.advBrowser.newCustomColumn(
                    type=type,
                    name=name,
                    onData=fldOnData,
                    onSort=getOnSort(srt)
                )
                self.customColumns[name] = cc
        self.advBrowser.setupColumns()

    def valueForField(self, mid, flds, fldName):
        """Function called from SQLite to get the value of a field,
        given a field name and the model id for the note.
        
        mid is the model id. The model contains the definition of a note,
        including the names of all fields.
        
        flds contains the text of all fields, delimited by the character
        "x1f". We split this and index into it according to a precomputed
        index for the model (mid) and field name (fldName).
        
        fldName is the name of the field we are after."""
    
        try:
            index = self.modelFieldPos.get(mid).get(fldName, None)
            if index is not None:
                fieldsList = flds.split("\x1f", index+1)
                return anki.utils.stripHTMLMedia(fieldsList[index])
        except Exception as ex:
            pass
            # print("Failed to get value for field.")
            # print("Mid: " + str(mid or 'None'))
            # print("flds: " + str(flds or 'None'))
            # print("fldName: " + str(fldName or 'None'))
            # print("_modelFieldPos: " + str(self.modelFieldPos))
            # print("Error was: ", ex)

    def myLoadCollection(self, _self):
        # Create a new SQL function that we can use in our queries.
        mw.col.db._db.create_function("valueForField", 3, self.valueForField)
        return True

nf = NoteFields()
addHook("advBrowserLoaded", nf.onAdvBrowserLoad)
addHook("advBrowserBuildContext", nf.onBuildContextMenu)
AnkiQt.loadCollection = wrap(AnkiQt.loadCollection, nf.myLoadCollection)
