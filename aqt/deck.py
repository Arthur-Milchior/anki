import anki.deck


class Deck(anki.deck.Deck):
    ## Deck Browser
    @staticmethod
    def _option():
        """html cell, to show gear opening options"""
        return f"""
      <td align=center class=opts>
        <a onclick='return pycmd("opts:{self.getId()}");'>
          <img src='/_anki/imgs/gears.svg' class=gears>
        </a>
      </td>"""
