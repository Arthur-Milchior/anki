from .notes import isNew, isNotNew

nidToRand = dict()
def toTup(card, params):
    """A tuple to sort the card. See bothSched.sortCids to get more
    informations."""
    l = []
    for param in params:
        if isinstance(param, tuple):
            param, reverse = param
        else:
            reverse = False
        if param == "new first":
            val = (isNotNew(card.note()))#false occurs first in list
        elif param == "seen first":
            val = (isNew(card.note()))#false occurs first in list
        elif param in {"ord", "card position"}:
            val = (card.ord)
        elif param == "note creation":
            val = (card.nid)
        elif param == "card creation":
            val = (card.id)
        elif param == "mod":
            val = (card.note().mod)
        elif param == "note random":
            if card.nid not in nidToRand:
                nidToRand[card.nid] = random()
            val = nidToRand[card.nid]
        elif param == "card random":
            val = (random())
        if reverse:
            val = -val
        l.append(val)
    return tuple(l)
