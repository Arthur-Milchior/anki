from anki.collection import _Collection
from aqt.browser import ChangeModel

oldAccept = ChangeModel.accept

def modSchema(self, check):
    pass

def accept(self):
    oldModSchema = _Collection.modSchema
    _Collection.modSchema = modSchema
    oldAccept(self)
    _Collection.modSchema = oldModSchema

ChangeModel.accept = accept
