from .consts import CARD_NEW


# Methods to sort new card
######################################################
def isNew(note):
    return not isNotNew(note)
def isNotNew(note):
    return note.col.db.scalar(f"select 1 from cards where nid = ? and type <> {CARD_NEW} limit 1", note.id)
