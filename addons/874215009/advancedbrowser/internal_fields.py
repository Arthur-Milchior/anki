# -*- coding: utf-8 -*-
# See github page to report issues or to contribute:
# https://github.com/hssm/advanced-browser



class InternalFields:

    def __init__(self):
        self.noteColumns = []
        self.cardColumns = []

    def onBuildContextMenu(self, contextMenu):
        nGroup = contextMenu.newSubMenu("- Note (internal) -")
        cGroup = contextMenu.newSubMenu("- Card (internal) -")

        for cc in self.noteColumns:
            nGroup.addItem(cc)
        for cc in self.cardColumns:
            cGroup.addItem(cc)

    def onAdvBrowserLoad(self, advBrowser):
        """Called when the Advanced Browser add-on has finished
        loading. Create and add all custom columns owned by this
        add-on here.

        """

        # Clear existing state
        self.noteColumns = []
        self.cardColumns = []

        cc = advBrowser.newCustomColumn(
            type="nid",
            name="Note ID",
            onData=lambda c, n, t: n.id,
            onSort=lambda: "n.id"
        )
        self.noteColumns.append(cc)

        cc = advBrowser.newCustomColumn(
            type="nguid",
            name="Note Guid",
            onData=lambda c, n, t: n.guid,
            onSort=lambda: "n.guid"
        )
        self.noteColumns.append(cc)

        cc = advBrowser.newCustomColumn(
            type="nmid",
            name="Model ID",
            onData=lambda c, n, t: n.mid,
            onSort=lambda: "n.mid"
        )
        self.noteColumns.append(cc)

        cc = advBrowser.newCustomColumn(
            type="nusn",
            name="Note USN",
            onData=lambda c, n, t: n.usn,
            onSort=lambda: "n.usn"
        )
        self.noteColumns.append(cc)

        cc = advBrowser.newCustomColumn(
            type="nfields",
            name="Note Fields",
            onData=lambda c, n, t: u"\u25A0".join(n.fields),
            onSort=lambda: "n.flds"
        )
        self.noteColumns.append(cc)

        cc = advBrowser.newCustomColumn(
            type="nflags",
            name="Note Flags",
            onData=lambda c, n, t: n.flags,
            onSort=lambda: "n.flags"
        )
        self.noteColumns.append(cc)

        cc = advBrowser.newCustomColumn(
            type="ndata",
            name="Note Data",
            onData=lambda c, n, t: n.data,
            onSort=lambda: "n.data"
        )
        self.noteColumns.append(cc)

        cc = advBrowser.newCustomColumn(
            type="cid",
            name="Card ID",
            onData=lambda c, n, t: c.id,
            onSort=lambda: "c.id"
        )
        self.cardColumns.append(cc)

        cc = advBrowser.newCustomColumn(
            type="cdid",
            name="Deck ID",
            onData=lambda c, n, t: c.did,
            onSort=lambda: "c.did"
        )
        self.cardColumns.append(cc)

        cc = advBrowser.newCustomColumn(
            type="codid",
            name="Original Deck ID",
            onData=lambda c, n, t: c.odid,
            onSort=lambda: "c.odid"
        )
        self.cardColumns.append(cc)

        cc = advBrowser.newCustomColumn(
            type="cord",
            name="Card Ordinal",
            onData=lambda c, n, t: c.ord,
            onSort=lambda: "c.ord"
        )
        self.cardColumns.append(cc)

        cc = advBrowser.newCustomColumn(
            type="cusn",
            name="Card USN",
            onData=lambda c, n, t: c.usn,
            onSort=lambda: "c.usn"
        )
        self.cardColumns.append(cc)

        cc = advBrowser.newCustomColumn(
            type="ctype",
            name="Card Type",
            onData=lambda c, n, t: c.type,
            onSort=lambda: "c.type"
        )
        self.cardColumns.append(cc)

        cc = advBrowser.newCustomColumn(
            type="cqueue",
            name="Card Queue",
            onData=lambda c, n, t: c.queue,
            onSort=lambda: "c.queue"
        )
        self.cardColumns.append(cc)

        cc = advBrowser.newCustomColumn(
            type="cleft",
            name="Card Left",
            onData=lambda c, n, t: c.left,
            onSort=lambda: "c.left"
        )
        self.cardColumns.append(cc)

        cc = advBrowser.newCustomColumn(
            type="codue",
            name="Card Original Due",  # I think?
            onData=lambda c, n, t: c.odue,
            onSort=lambda: "c.odue"
        )
        self.cardColumns.append(cc)

        cc = advBrowser.newCustomColumn(
            type="cflags",
            name="Card Flags",
            onData=lambda c, n, t: c.flags,
            onSort=lambda: "c.flags"
        )
        self.cardColumns.append(cc)


iff = InternalFields()
