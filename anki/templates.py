from anki.utils import DictAugmentedInModel


class Template(DictAugmentedInModel):
    """Templates are not necessarily in the model. If they are not, method add
    must be used to add them.  Only use them once the field is
    entirely configured (so that compilation of req is done correction
    for example)

    """
