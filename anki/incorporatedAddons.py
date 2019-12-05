
## Add-ons incorporated in this fork.

class Addon:
    def __init__(self, name = None, id = None, mod = None, gitHash = None, gitRepo = None):
        self.name = name
        self.id = id
        self.mod = mod
        self.gitHash = gitHash
        self.gitRepo = gitRepo

    def __hash__(self):
        return self.id or hash(self.name)

""" Set of characteristic of Add-ons incorporated here"""
incorporatedAddonsSet = {
    Addon("3 add-ons merged quicker anki explain deletion explain database check", 777545149, 1560838078, "https://github.com/Arthur-Milchior/anki-big-addon", "9138f06acf75df3eeb79a9b3cabdcfb0c6d964b9"),
    Addon("Add a tag to notes with missing media", 2027876532, 1560318502, "26c4f6158ce2b8811b8ac600ed8a0204f5934d0b", "Arthur-Milchior/anki-tag-missing-medias"),
    Addon("Advanced Browser", 874215009, 1552544150, "3f3f2c2855c4ad811a40705c565233acced1c1de", "https://github.com/hssm/advanced-browser"),
    Addon("Allows empty first field during adding and import", 46741504, 1553438887, "7224199", "https://github.com/Arthur-Milchior/anki-empty-first-field"),
    Addon("Batch Editing", 291119185, 1560116344, "https://github.com/glutanimate/batch-editing", "41149dbec543b019a9eb01d06d2a3c5d13b8d830"),
    Addon("CTRL+F5 to Refresh the Browser", 1347728560, 1564463100, "056a2cf4b0096c42e077876578778b1cfe3cc90c", "https://github.com/Arthur-Milchior/anki-addons-misc/tree/refreshBrowser/src/browser_refresh"),
    Addon("Change cards decks prefix", 1262882834, 1550534152, "f9843693dafb4aeb2248de5faf44cf5b5fdc69ec", "https://github.com/Arthur-Milchior/anki-deck-prefix-edit"),
    Addon("Compile latex during addedition and warn in case of error", 769835008, 1542763850, "afd052471c7e9406e7a8dbe3b08c09cb3ed20e77", "https://github.com/Arthur-Milchior/anki-compile-latex-early/"),
    Addon("Copy notes", 1566928056, 1563556640, "b9ad0a66f36db8a7b74c7da3cf967690623cd50c", "https://github.com/Arthur-Milchior/anki-copy-note"),
    Addon("Delete empty NEW cards", 1402327111, 1550534154, "6c45b4117e5d6cc4802ed4382d8b5d05ee80ac81", "https://github.com/Arthur-Milchior/anki-empty-new-cards"),
    Addon("Directly review, without going through overview page", 1024346707, gitHash="0a0d0365deb022c54197f90c3f1100e9fc259ec0", gitRepo="https://github.com/Arthur-Milchior/anki-direct-to-review"),
    Addon("Empty cards returns more usable informations", 25425599, 1560126141, "299a0a7b3092923f5932da0bf8ec90e16db269af", "https://github.com/Arthur-Milchior/anki-clearer-empty-card"),
    Addon("Export cards selected in the Browser", 1983204951, 1560768960, "f8990da153af2745078e7b3c33854d01cb9fa304", "https://github.com/Arthur-Milchior/anki-export-from-browser"),
    Addon("F5 to Refresh the Browser", 832679841, gitRepo="https://github.com/glutanimate/anki-addons-misc/tree/master/src/browser_refresh"),
    Addon("Frozen Fields", 516643804, 1561600792, "191bbb759b3a9554e88fa36ba20b83fe68187f2d", "https://github.com/glutanimate/frozen-fields"),
    Addon("If a note has no more card warns instead of deleting it", 2018640062, 1560126140, "4a854242d06a05b2ca801a0afc29760682004782", "https://github.com/Arthur-Milchior/anki-keep-empty-note"),
    Addon("Keep files (git, svn...) in add-on folders", 225953877, 1574388077, "d6f81fa47021f37100c77fc92470491526e7982a", "https://github.com/Arthur-Milchior/anki-keep-files-in-addon-Folder"),
    Addon("Keep model of add cards", 424778276, 1553438887, "64bdf3c7d8e252d6f69f0a423d2db3c23ce6bc04", "https://github.com/Arthur-Milchior/anki-keep-model-in-add-cards"),
    Addon("Multi-column note editor debugged", 2064123047, 1550534156, "70f92cd5f62bd4feda5422701bd01acb41ed48ce", "https://github.com/Arthur-Milchior/anki-Multi-column-edit-window"),
    Addon("Multi-column note editor", 3491767031, 1560844854, "ad7a4014f184a1ec5d5d5c43a3fc4bab8bb8f6df", "https://github.com/hssm/anki-addons/tree/master/multi_column_editor"),
    Addon("Newline in strings in add-ons configurations", 112201952, 1560116341, "c02ac9bbbc68212da3d2bccb65ad5599f9f5af97", "https://github.com/Arthur-Milchior/anki-json-new-line"),
    Addon("Open Added Today from Reviewer", 861864770, 1561610680, gitRepo = "https://github.com/glutanimate/anki-addons-misc"), #repo contains many add-ons. Thus hash seems useless. 47a218b21314f4ed7dd62397945c18fdfdfdff71
    Addon("Opening the same window multiple time", 354407385, 1545364194, "c832579f6ac7b327e16e6dfebcc513c1e89a693f", "https://github.com/Arthur-Milchior/anki-Multiple-Windows"),
    Addon("Postpone cards review", 1152543397, 1560126139, "27103fd69c19e0576c5df6e28b5687a8a3e3d905", "https://github.com/Arthur-Milchior/Anki-postpone-reviews"),
    Addon("Preview any cloze", 915063177, gitHash="53becee3577c308dc169304d9ff30bf54ce34018", gitRepo="https://github.com/Arthur-Milchior/anki-any-cloze-in-preview"),
    Addon("Reviewer to Browser choosing what to display", 1555020859, 1565286616, "2e8ef9c8fa2648925807be43991432ae9211ba68", "https://github.com/Arthur-Milchior/anki-browser-from-reviewer"),
    Addon("Update add-ons when Anki starts", 1847544206, 1568266364, "4ca633266986da6ba6886d4706909ddbd18c10d4", "https://github.com/Arthur-Milchior/anki-auto-update-addons"),
    Addon("\"Close and lose current input ?\" for sticky fields", 1284221829, 1574383623, "8eb22c84dea7dfdf5e3f501db1c0d9b273de9f3e", "https://github.com/Arthur-Milchior/anki-Close-and-lose-current-input-for-sticky-fields"),
    Addon("«Check database» Explain errors and what is done to fix it", 1135180054, gitHash = "371c360e5611ad3eec5dcef400d969e7b1572141", gitRepo = "https://github.com/Arthur-Milchior/anki-database-check-explained"), #mod unkwon because it's not directly used by the author anymore
}

incorporatedAddonsDict = {**{addon.name: addon for addon in incorporatedAddonsSet if addon.name},
                          **{addon.id: addon for addon in incorporatedAddonsSet if addon.id}}
