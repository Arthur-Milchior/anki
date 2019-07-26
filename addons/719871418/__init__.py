from anki.collection import _Collection
from aqt.browser import ChangeModel
from aqt.fields import FieldDialog

def modSchema(self, check):
    self.setMod()


for (class_, methodName) in [
        (ChangeModel, "accept"),
        (FieldDialog, "reject"),
        (FieldDialog, "onRename"),
        (FieldDialog, "onDelete"),
        (FieldDialog, "onAdd"),
        (FieldDialog, "onPosition"),
]:
    method = getattr(class_, methodName)
    def aux(method):
        #two methods, to fix method to this precise value
        def aux_(self):
            oldModSchema = _Collection.modSchema
            _Collection.modSchema = modSchema
            method(self)
            _Collection.modSchema = oldModSchema
        return aux_
    setattr(class_, methodName, aux(method))
