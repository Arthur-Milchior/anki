from anki.utils import intTime
from aqt import mw
from .debug import debug
from .consts import *
# Associate to [column name][deck id name] some value corresponding to
# the number of card of this deck in this column
values = dict()


def computeValues():
    debug("Compute values")
    cutoff = intTime() + mw.col.conf['collapseTime']
    today = mw.col.sched.today
    tomorrow = today+1
    yesterdayLimit = (mw.col.sched.dayCutoff-86400)*1000
    debug(f"Yesterday limit is {yesterdayLimit}")
    queriesCardCount = ([(f"flag {i}", f"(flags & 7) == {i}" ,"","") for i in range(5)]+
    [
        ("due tomorrow", f"queue in ({QUEUE_REV},{QUEUE_DAY_LRN}) and due = {tomorrow}" ,"",""),
        ("learning now from today", f"queue = {QUEUE_LRN} and due <= {cutoff}" ,"",""),
        ("learning today from past", f"queue = {QUEUE_DAY_LRN} and due <= {today}" ,"",""),
        ("learning later today", f"queue = {QUEUE_LRN} and due > {cutoff}" ,"",""),
        ("learning future", f"queue = {QUEUE_DAY_LRN} and due > {today}" ,"",""),
        ("learning today repetition from today", f"queue = {QUEUE_LRN}", f"left/1000",""),
        ("learning today repetition from past",f"queue = {QUEUE_DAY_LRN}" , f"left/1000",""),
        ("learning repetition from today", f"queue = {QUEUE_LRN}", f"mod%1000",""),
        ("learning repetition from past",f"queue = {QUEUE_DAY_LRN}", f"mod%1000",""),
        ("review due", f"queue = {QUEUE_REV} and due <= {today}" ,"",""),
        ("reviewed today", f"queue = {QUEUE_REV} and due>0 and due-ivl = {today}" ,"",""),
        ("repeated today", f"revlog.id>{yesterdayLimit}" ,"","revlog inner join cards on revlog.cid = cards.id"),
        ("repeated", "" ,"",f"revlog inner join cards on revlog.cid = cards.id"),
        ("unseen", f"queue = {QUEUE_NEW_CRAM}","",""),
        ("buried", f"queue = {QUEUE_USER_BURIED}  or queue = {QUEUE_SCHED_BURIED}","",""),
        ("suspended", f"queue = {QUEUE_SUSPENDED}","",""),
        ("cards","","",""),
        ("undue", f"queue = {QUEUE_REV} and due >  {today}","",""),
        ("mature", f"queue = {QUEUE_REV} and ivl >= 21" ,"",""),
        ("young", f"queue = {QUEUE_REV} and 0<ivl and ivl <21" ,"",""),
    ])
    for name, condition, addend, table in queriesCardCount:
        if addend:
            element = f" sum({addend})"
        else:
            element = f" count(*)"
        if condition:
            condition = f" where {condition}"
        if not table:
            table = "cards"
        query = f"select did, {element} from {table} {condition} group by did"
        results = mw.col.db.all(query)
        debug("""For {name}: query "{query}".""")
        values[name] = dict()
        for did, value in results:
            debug(f"In deck {did} there are {value} cards of kind {name}")
            values[name][did] = value

times = dict()
def computeTime():
    times.clear()
    for did, time in mw.col.db.all(f"select did,min(case when queue = {QUEUE_LRN} then due else null end) from cards group by did"):
        times[did]=time
