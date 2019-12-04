from anki.consts import *
from anki.lang import _


class Column:
    def topRow(self):
        pass

    def deckRow(self, deck):
        pass

class DeckName(Column):
    def topRow(self):
        return f"""
    <th align=left>{_("Deck")}
    </th>"""

    def deckRow(self, deck):
        try :
            collapse = (f"""
      <a class=collapse href=# onclick='return pycmd(\"collapse:{deck.getId()}\")'>
        {"+" if deck['collapsed'] else "-"}
      </a>""" if (not deck.isLeaf()) else """
      <span class=collapse></span>""")
        except KeyError:
            print(f"missing 'collapsed' in {deck}")
            raise
        return f"""

    <td class=decktd>{"&nbsp;"*6*deck.depth()}{collapse}
       <a class="deck {"filtered" if deck.isDyn() else ""}" href=# onclick="return pycmd('open:{deck.getId()}')">{deck.getBaseName()}
       </a>
    </td>"""

class Number:
    def __init__(self, name, key, color):
        self.name = name
        self.key = key
        self.color = color

    @staticmethod
    def nonzeroColour(cnt, colour):
        if not cnt:
            colour = "#e0e0e0"
        if cnt >= 1000:
            cnt = "1000+"
        return f"""
      <font color='{colour}'>
         {cnt}
      </font>"""

    def topRow(self):
        return f"""
    <th class=count>{_(self.name)}
    </th>"""

    def deckRow(self, deck):
        return f"""
    <td align=right>{self.nonzeroColour(deck.getCount(self.key), self.color)}
    </td>"""

class Gear(Column):
    def topRow(self):
        return """
    <th class=optscol>
    </th>"""

    def deckRow(self, deck):
        return f"""
    <td align=center class=opts>
      <a onclick='return pycmd(\"opts:{deck.getId()}\");'>
        <img src='/_anki/imgs/gears.svg' class=gears>
      </a>
    </td>"""
