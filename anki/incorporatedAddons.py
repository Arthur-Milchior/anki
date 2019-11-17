
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
    Addon("CTRL+F5 to Refresh the Browser", 1347728560, 1564463100, "056a2cf4b0096c42e077876578778b1cfe3cc90c", "https://github.com/Arthur-Milchior/anki-addons-misc/tree/refreshBrowser/src/browser_refresh"),
    Addon("F5 to Refresh the Browser", 832679841, gitRepo="https://github.com/glutanimate/anki-addons-misc/tree/master/src/browser_refresh"),
    Addon("«Check database» Explain errors and what is done to fix it", 1135180054, gitHash = "371c360e5611ad3eec5dcef400d969e7b1572141", gitRepo = "https://github.com/Arthur-Milchior/anki-database-check-explained"), #mod unkwon because it's not directly used by the author anymore
}

incorporatedAddonsDict = {**{addon.name: addon for addon in incorporatedAddonsSet if addon.name},
                          **{addon.id: addon for addon in incorporatedAddonsSet if addon.id}}
