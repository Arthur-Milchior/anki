from anki.sync import Syncer

oldGetModels = Syncer.getModels
def getModels(self):
    self.col.models.removeLS()
    oldGetModels(self)
Syncer.getModels = oldGetModels
