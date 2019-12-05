import json

from aqt import mw

from .cards import toTup
from .consts import *
from .notes import isNew, isNotNew


def sortCids(cids, params, start=None, step=1):
    """Re-order all new cards whose id belong to cids
      The order of the cards is given in parameters. Sorting is done
    according to first parameter. In case of equality according to
    second parameter. And so on. A paramater is either a string `"rule"`,
    or a pair `("rule", False)`. If it is a string, the sort is as follows:
    * "seen first": show siblings of cards which have already been seen.
    * "new first": show notes whose no card have been seen first
    * "ord": sort cards according to their position in the note
    * "note creation": sort according to the date of creation of the note
    * "mod": sort according to the last time the note was modified
    * "card creation": sort according to the date of creation of the card.
    * "random": sort randomly in case of ambiguity in the previous cases.
      Note that there are no equality in the two last cases; the
    order is complete, so it's useless to add more parameters
    after "card creation" or after "random".
      If the parameter is a pair, it means this order is reversed.
      cids -- iterable card ids.
    params -- list of parameters, or JSON encoding of it
    start -- first due value. Default is nextID.
    step -- number of elements to put between two successive due values
    """
    if isinstance(params, str):
        params = json.loads(params)
    if start is None:
        start = mw.col.nextID("pos")
    cards = []
    for cid in cids:
        card = mw.col.getCard(cid) 
        if card.type == CARD_NEW:
            cards.append(card)
    cards.sort(key=lambda card: toTup(card, params))
    for card in cards:
        card.due = start
        card.flush()
        start += step
    return cards

def sortDid(did, params, start=None, step=1):
    cids = mw.col.decks.cids(did, True)
    return sortCids(cids, params, start, step)
