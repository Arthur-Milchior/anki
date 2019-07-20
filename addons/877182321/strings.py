from .config import getUserOption
from anki.stats import *
from anki.lang import _


# Associate to each column its title
defaultHeader = {**{
    "learning card":_("Learning")+"<br/>"+_("(card)"),
    "learning later":_("Learning")+"<br/>"+_("later")+" ("+_("review")+")" ,
    "learning now":_("Learning")+"<br/>"+_("now") ,
    "learning today":_("Learning")+"<br/>"+_("now")+"<br/>"+_("and later"),
    "learning all":_("Learning")+"<br/>"+_("now")+"<br/>("+_("later today")+"<br/>("+_("other day")+"))",
    "review due":_("Due")+"<br/>"+_("all") ,
    "due tomorrow":_("Due")+"<br/>"+_("tomorrow") ,
    "review today":_("Due")+"<br/>"+_("today") ,
    "review":_("Due")+"<br/>"+_("today")+" ("+_("all")+")",
    "unseen":_("Unseen")+"<br/>"+_("all")  ,
    "unseen later":_("Unseen")+"<br/>"+_("later")  ,
    "review later":_("review")+"<br/>"+_("later")  ,
    "reviewed today":_("reviewed")+"<br/>"+_("today")  ,
    "reviewed today/repeated today":_("reviewed")+"/"+"<br/>"+_("repeated")+"<br/>"+_("today")  ,
    "repeated today":_("repeated")+"<br/>"+_("today")  ,
    "repeated":_("repeated"),
    "new":_("New")+"<br/>"+_("today") ,
    "unseen new":_("New")+"<br/>"+"("+_("Unseen")+")",
    "buried":_("Buried"),
    "buried/suspended":_("Buried")+"/<br/>"+_("Suspended"),
    "suspended":_("Suspended"),
    "cards":_("Total"),
    "notes/cards":_("Total")+"/<br/>"+_("Card/Note"),
    "notes":_("Total")+"<br/>"+_("Note"),
    "new today":_("New")+"<br/>"+_("Today"),
    "today":_("Today"),
    "undue":_("Undue"),
    "mature":_("Mature"),
    "mature/young":_("Mature")+"/<br/>"+_("Young"),
    "young": _("Young"),
    "marked":_("Marked"),
    "leech":_("Leech"),
    "bar":_("Progress"),
    "flags":_("Flags"),
    "all flags":_("Flags")
},**{f"flag {i}": _("Flag")+" {i}" for i in range(5)}}

def getHeader(conf):
    """The header for the configuration in argument"""
    if "header" not in conf:
        return None
    header = conf["header"]
    if header is None:
        return defaultHeader[conf["name"]]
    return header

# Associate to each column its overlay
defaultOverlay = {**{
    "learning card":_("Cards in learning")+"<br/>"+_("""(either new cards you see again,""")+"<br/>"+_("or cards which you have forgotten recently.")+"<br/>"+_("""Assuming those cards didn't graduate)"""),
    "learning later":_("Review which will happen later.")+"<br/>"+_("Either because a review happened recently,")+"<br/>"+_("or because the card have many review left."),
    "learning now":_("Cards in learning which are due now.")+"<br/>"+_("If there are no such cards,")+"<br/>"+_("the time in minutes")+"<br/>"+_("or seconds until another learning card is due"),
    "learning today":_("Cards in learning which are due now and then later."),
    "learning all":_("Cards in learning which are due now")+"<br/>"+_("(and in parenthesis, the number of reviews")+"<br/>"+_("which are due later)"),
    "review due":_("Review cards which are due today")+"<br/>"+_("(not counting the one in learning)"),
    "due tomorrow":_("Review cards which are due tomorrow")+"<br/>"+_("(note: new cards and lapsed card seen today may increase this number.)"),
    "review today":_("Review cards you will see today"),
    "review":_("Review cards cards you will see today")+"<br/>"+_("(and the ones you will not see today)"),
    "unseen":_("Cards that have never been answered"),
    "unseen later":_("Cards that have never been answered<br/>and you won't see today"),
    "review later":_("Cards that you must review,<br/>but can't review now"),
    "reviewed today":_("Number of time<br/>you did review a card from this deck."),
    "reviewed today/repeated today":_("Number of cards and of review<br/>from this deck today."),
    "repeated today":_("Number of time you saw a question<br/> from this deck today."),
    "repeated":_("Number of time<br/>you saw a question from this deck."),
    "new":_("Unseen")+ _("cards")+ _("you will see today")+"<br/>"+_("(what anki calls ")+_("new cards"),
    "unseen new":_("Unseen cards you will see today")+"<br/>"+_("(and those you will not see today)"),
    "buried":_("number of buried cards,")+"<br/>"+_("(cards you decided not to see today)"),
    "buried/suspended":_("number of buried cards,")+"<br/>"+_("(cards you decided not to see today)")+_("number of suspended cards,")+"<br/>"+_("(cards you will never see")+"<br/>"+_("unless you unsuspend them in the browser)"),
    "suspended":_("number of suspended cards,")+"<br/>"+_("(cards you will never see")+"<br/>"+_("unless you unsuspend them in the browser)"),
    "cards":_("Number of cards in the deck"),
    "notes/cards":_("Number of cards/note in the deck"),
    "notes":_("Number of cards/note in the deck"),
    "today":_("Number of review you will see today")+"<br/>"+_("(new, review and learning)"),
    "undue":_("Number of cards reviewed, not yet due"),
    "mature/young":_("Number of cards reviewed,")+"<br/>"+_("with interval at least 3 weeks/")+"<br/>"+_("less than 3 weeks"),
    "mature":_("Number of cards reviewed,")+"<br/>"+_("with interval at least 3 weeks"),
    "young": _("Number of cards reviewed,")+"<br/>"+_("with interval less than 3 weeks"),
    "marked":_("Number of marked note"),
    "leech":_("Number of note with a leech card"),
    "new today":_("Number of new cards you'll see today"),
    "bar":None, #It provides its own overlays,
    "flags":_("Number of cards for each flag"),
    "all flags":_("Number of cards for each flag")
},**{f"flag {i}": _(f"Number of cards with flag {i}") for i in range(5)}}

def getOverlay(conf):
    """The overlay for the configuration in argument"""
    overlay =  conf.get("overlay")
    if overlay is None:
        name = conf["name"]
        return defaultOverlay[name]
    return overlay

def getColor(conf):
    if "color" in conf and conf.get('color') is not None:
        return conf.get('color')
    name = conf.get('name',"")
    for word, color in [
            ("learning",colRelearn),
            ("unseen",colUnseen),
            ("new",colLearn),
            ("suspend",colSusp),
            ("young",colYoung),
            ("mature",colMature),
            ("buried",colSusp),
            ("repeated",colCum)
    ]:
        if word in name:
            return color
    return getUserOption("default column color","grey")
