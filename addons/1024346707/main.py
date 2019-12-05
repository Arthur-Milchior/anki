from aqt import mw
from aqt.main import AnkiQt


def realOverview(self):
    self.col.reset()
    self.moveToState("overview")

def onOverview(self):
    self.onReview()

def onReview(self):
    self.col.startTimebox()
    self.moveToState("review")
    
AnkiQt.onOverview = onOverview
AnkiQt.realOverview = realOverview
AnkiQt.onReview = onReview

# def onStudyKey(self):
#     print(f"self.onReview is {self.onReview}")
#     self.onReview()

# AnkiQt.onStudyKey = onStudyKey


# def onStudyDeck(self):
#     from aqt.studydeck import StudyDeck
#     ret = StudyDeck(
#         self, dyn=True, current=self.col.decks.current()['name'])
#     if ret.name:
#         self.col.decks.select(self.col.decks.id(ret.name))
#         self.onReview()
# AnkiQt.onStudyDeck = onStudyDeck

#mw.setupKeys() #called again in order to set "s" to the new onStudyKey
