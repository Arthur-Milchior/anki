# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import datetime
import json
import time

from anki.consts import *
from anki.lang import _, ngettext
from anki.utils import fmtTimeSpan, ids2str

# Card stats
##########################################################################

class CardStats:

    def __init__(self, col, card):
        self.col = col
        self.card = card

    def report(self):
        card = self.card
        # pylint: disable=unnecessary-lambda
        fmt = lambda x, **kwargs: fmtTimeSpan(x, short=True, **kwargs)
        self.txt = "<table width=100%>"
        self.addLine(_("Added"), self.date(card.id/1000))
        first = self.col.db.scalar(
            "select min(id) from revlog where cid = ?", card.id)
        last = self.col.db.scalar(
            "select max(id) from revlog where cid = ?", card.id)
        if first:
            self.addLine(_("First Review"), self.date(first/1000))
            self.addLine(_("Latest Review"), self.date(last/1000))
        if card.type in (CARD_LRN, CARD_DUE):
            if card.odid or card.queue < 0:
                next = None
            else:
                if card.queue in (QUEUE_REV, QUEUE_DAY_LRN):
                    next = time.time()+((card.due - self.col.sched.today)*86400)
                else:
                    next = card.due
                next = self.date(next)
            if next:
                self.addLine(_("Due"), next)
            if card.queue == QUEUE_REV:
                self.addLine(_("Interval"), fmt(card.ivl * 86400))
            self.addLine(_("Ease"), "%d%%" % (card.factor/10.0))
            self.addLine(_("Reviews"), "%d" % card.reps)
            self.addLine(_("Lapses"), "%d" % card.lapses)
            (cnt, total) = self.col.db.first(
                "select count(), sum(time)/1000 from revlog where cid = :id",
                id=card.id)
            if cnt:
                self.addLine(_("Average Time"), self.time(total / float(cnt)))
                self.addLine(_("Total Time"), self.time(total))
        elif card.queue == QUEUE_NEW_CRAM:
            self.addLine(_("Position"), card.due)
        self.addLine(_("Card Type"), card.template()['name'])
        self.addLine(_("Note Type"), card.model()['name'])
        self.addLine(_("Deck"), self.col.decks.name(card.did))
        self.addLine(_("Note ID"), card.nid)
        self.addLine(_("Card ID"), card.id)
        self.txt += "</table>"
        return self.txt

    def addLine(self, k, v):
        self.txt += self.makeLine(k, v)

    def makeLine(self, k, v):
        txt = "<tr><td align=left style='padding-right: 3px;'>"
        txt += "<b>%s</b></td><td>%s</td></tr>" % (k, v)
        return txt

    def date(self, tm):
        return time.strftime("%Y-%m-%d", time.localtime(tm))

    def time(self, tm):
        str = ""
        if tm >= 60:
            str = fmtTimeSpan((tm/60)*60, short=True, point=-1, unit=1)
        if tm%60 != 0 or not str:
            str += fmtTimeSpan(tm%60, point=2 if not str else -1, short=True)
        return str

# Collection stats
##########################################################################

class CollectionStats:

    def __init__(self, col):
        self.col = col
        self._stats = None
        self.type = 0
        self.width = 600
        self.height = 200
        self.wholeCollection = False

    # assumes jquery & plot are available in document
    def report(self, type=0):
        # 0=days, 1=weeks, 2=months
        self.type = type
        from .statsbg import bg
        txt = self.css % bg
        txt += self._section(self.todayStats())
        txt += self._section(self.dueGraph())
        txt += self.repsGraphs()
        txt += self._section(self.introductionGraph())
        txt += self._section(self.ivlGraph())
        txt += self._section(self.hourGraph())
        txt += self._section(self.easeGraph())
        txt += self._section(self.cardGraph())
        txt += self._section(self.footer())
        return "<center>%s</center>" % txt

    def _section(self, txt):
        return "<div class=section>%s</div>" % txt

    css = """
<style>
h1 { margin-bottom: 0; margin-top: 1em; }
.pielabel { text-align:center; padding:0px; color:white; }
body {background-image: url(data:image/png;base64,%s); }
@media print {
    .section { page-break-inside: avoid; padding-top: 5mm; }
}
</style>
"""

    # Today stats
    ######################################################################

    def todayStats(self):
        html = self._title(_("Today"))
        # studied today
        lim = self._revlogLimit()
        if lim:
            lim = " and " + lim
        cards, thetime, failed, lrn, rev, relrn, filt = self.col.db.first(f"""
select count(), sum(time)/1000,
sum(case when ease = 1 then 1 else 0 end), /* failed */
sum(case when type = {CARD_NEW} then 1 else 0 end), /* learning */
sum(case when type = {CARD_LRN} then 1 else 0 end), /* review */
sum(case when type = {CARD_DUE} then 1 else 0 end), /* relearn */
sum(case when type = {CARD_FILTERED} then 1 else 0 end) /* filter */
from revlog where id > ? """+lim, (self.col.sched.dayCutoff-86400)*1000)
        cards = cards or 0
        thetime = thetime or 0
        failed = failed or 0
        lrn = lrn or 0
        rev = rev or 0
        relrn = relrn or 0
        filt = filt or 0
        # studied
        def bold(s):
            return "<b>"+str(s)+"</b>"
        msgp1 = ngettext("<!--studied-->%d card", "<!--studied-->%d cards", cards) % cards
        if cards:
            html += _("Studied %(a)s %(howManyTime)s today (%(secs).1fs/card)") % dict(
                a=bold(msgp1), howManyTime=bold(fmtTimeSpan(thetime, unit=1, inTime=True)),
                secs=thetime/cards
            )
            # again/pass count
            html += "<br>" + _("Again count: %s") % bold(failed)
            if cards:
                html += " " + _("(%s correct)") % bold(
                    "%0.1f%%" %((1-failed/float(cards))*100))
            # type breakdown
            html += "<br>"
            html += (_("Learn: %(a)s, Review: %(nbRev)s, Relearn: %(relrn)s, Filtered: %(filt)s")
                  % dict(a=bold(lrn), nbRev=bold(rev), relrn=bold(relrn), filt=bold(filt)))
            # mature today
            mcnt, msum = self.col.db.first("""
    select count(), sum(case when ease = 1 then 0 else 1 end) from revlog
    where lastIvl >= 21 and id > ?"""+lim, (self.col.sched.dayCutoff-86400)*1000)
            html += "<br>"
            if mcnt:
                html += _("Correct answers on mature cards: %(a)d/%(mcnt)d (%(percent).1f%%)") % dict(
                    a=msum, mcnt=mcnt, percent=(msum / float(mcnt) * 100))
            else:
                html += _("No mature cards were studied today.")
        else:
            html += _("No cards have been studied today.")
        return html

    # Due and cumulative due
    ######################################################################

    def get_start_end_chunk(self, by='review'):
        start = 0
        if self.type == CARD_NEW:
            end, chunk = 31, 1
        elif self.type == CARD_LRN:
            end, chunk = 52, 7
        elif self.type == CARD_DUE:
            end = None
            if self._deckAge(by) <= 100:
                chunk = 1
            elif self._deckAge(by) <= 700:
                chunk = 7
            else:
                chunk = 31
        return start, end, chunk

    def dueGraph(self):
        start, end, chunk = self.get_start_end_chunk()
        due = self._due(start, end, chunk)
        yng = []
        mtr = []
        tot = 0
        totd = []
        for day in due:
            yng.append((day[0], day[1]))
            mtr.append((day[0], day[2]))
            tot += day[1]+day[2]
            totd.append((day[0], tot))
        data = [
            dict(data=mtr, color=colMature, label=_("Mature")),
            dict(data=yng, color=colYoung, label=_("Young")),
        ]
        if len(totd) > 1:
            data.append(
                dict(data=totd, color=colCum, label=_("Cumulative"), yaxis=2,
                     bars={'show': False}, lines=dict(show=True), stack=False))
        txt = self._title(
            _("Forecast"),
            _("The number of reviews due in the future."))
        xaxis = dict(tickDecimals=0, min=-0.5)
        if end is not None:
            xaxis['max'] = end-0.5
        txt += self._graph(
            id="due", data=data, xunit=chunk, ylabel2=_("Cumulative Cards"),
            conf=dict(
                xaxis=xaxis, yaxes=[
                    dict(min=0), dict(min=0, tickDecimals=0, position="right")]
            ),
        )
        txt += self._dueInfo(tot, len(totd)*chunk)
        return txt

    def _dueInfo(self, tot, num):
        tableLines = []
        self._line(tableLines, _("Total"), ngettext("%d review", "%d reviews", tot) % tot)
        self._line(tableLines, _("Average"), self._avgDay(
            tot, num, _("reviews")))
        tomorrow = self.col.db.scalar(f"""
select count() from cards where did in %s and queue in ({QUEUE_REV}, {QUEUE_DAY_LRN})
and due = ?""" % self._limit(), self.col.sched.today+1)
        tomorrow = ngettext("%d card", "%d cards", tomorrow) % tomorrow
        self._line(tableLines, _("Due tomorrow"), tomorrow)
        return self._lineTbl(tableLines)

    def _due(self, start=None, end=None, chunk=1):
        lim = ""
        if start is not None:
            lim += " and due-:today >= %d" % start
        if end is not None:
            lim += " and day < %d" % end
        return self.col.db.all(f"""
select (due-:today)/:chunk as day,
sum(case when ivl < 21 then 1 else 0 end), -- yng
sum(case when ivl >= 21 then 1 else 0 end) -- mtr
from cards
where did in %s and queue in ({QUEUE_REV}, {QUEUE_DAY_LRN})
%s
group by day order by day""" % (self._limit(), lim),
                            today=self.col.sched.today,
                            chunk=chunk)

    # Added, reps and time spent
    ######################################################################

    def introductionGraph(self):
        start, days, chunk = self.get_start_end_chunk()
        data = self._added(days, chunk)
        if not data:
            return ""
        conf = dict(
            xaxis=dict(tickDecimals=0, max=0.5),
            yaxes=[dict(min=0), dict(position="right", min=0)])
        if days is not None:
            # pylint: disable=invalid-unary-operand-type
            conf['xaxis']['min'] = -days+0.5
        def plot(id, data, ylabel, ylabel2):
            return self._graph(
                id, data=data, conf=conf, xunit=chunk, ylabel=ylabel, ylabel2=ylabel2)
        # graph
        repdata, repsum = self._splitRepData(data, ((1, colLearn, ""),))
        txt = self._title(
            _("Added"), _("The number of new cards you have added."))
        txt += plot("intro", repdata, ylabel=_("Cards"), ylabel2=_("Cumulative Cards"))
        # total and per day average
        tot = sum([tableLines[1] for tableLines in data])
        period = self._periodDays()
        if not period:
            # base off date of earliest added card
            period = self._deckAge('add')
        tableLines = []
        self._line(tableLines, _("Total"), ngettext("%d card", "%d cards", tot) % tot)
        self._line(tableLines, _("Average"), self._avgDay(tot, period, _("cards")))
        txt += self._lineTbl(tableLines)

        return txt

    def repsGraphs(self):
        start, days, chunk = self.get_start_end_chunk()
        data = self._done(days, chunk)
        if not data:
            return ""
        conf = dict(
            xaxis=dict(tickDecimals=0, max=0.5),
            yaxes=[dict(min=0), dict(position="right", min=0)])
        if days is not None:
            # pylint: disable=invalid-unary-operand-type
            conf['xaxis']['min'] = -days+0.5
        def plot(id, data, ylabel, ylabel2):
            return self._graph(
                id, data=data, conf=conf, xunit=chunk, ylabel=ylabel, ylabel2=ylabel2)
        # reps
        (repdata, repsum) = self._splitRepData(data, (
            (3, colMature, _("Mature")),
            (2, colYoung, _("Young")),
            (4, colRelearn, _("Relearn")),
            (1, colLearn, _("Learn")),
            (5, colCram, _("Cram"))))
        txt1 = self._title(
            _("Review Count"), _("The number of questions you have answered."))
        txt1 += plot("reps", repdata, ylabel=_("Answers"), ylabel2=_(
            "Cumulative Answers"))
        (daysStud, fstDay) = self._daysStudied()
        rep, tot = self._ansInfo(repsum, daysStud, fstDay, _("reviews"))
        txt1 += rep
        # time
        (timdata, timsum) = self._splitRepData(data, (
            (8, colMature, _("Mature")),
            (7, colYoung, _("Young")),
            (9, colRelearn, _("Relearn")),
            (6, colLearn, _("Learn")),
            (10, colCram, _("Cram"))))
        if self.type == CARD_NEW:
            kindOfTime = _("Minutes")
            convHours = False
        else:
            kindOfTime = _("Hours")
            convHours = True
        txt2 = self._title(_("Review Time"), _("The time taken to answer the questions."))
        txt2 += plot("time", timdata, ylabel=kindOfTime, ylabel2=_("Cumulative %s") % kindOfTime)
        rep, tot2 = self._ansInfo(
            timsum, daysStud, fstDay, _("minutes"), convHours, total=tot)
        txt2 += rep
        return self._section(txt1) + self._section(txt2)

    def _ansInfo(self, totd, studied, first, unit, convHours=False, total=None):
        if not totd:
            return
        tot = totd[-1][1]
        period = self._periodDays()
        if not period:
            # base off earliest repetition date
            period = self._deckAge('review')
        tableLines = []
        self._line(tableLines, _("Days studied"),
                   _("<b>%(pct)d%%</b> (%(x)s of %(y)s)") % dict(
                       x=studied, y=period, pct=studied/float(period)*100),
                   bold=False)
        if convHours:
            tunit = _("hours")
        else:
            tunit = unit
        #T: unit: can be hours, minutes, reviews... tot: the number of unit.
        self._line(tableLines, _("Total"), _("%(tot)s %(unit)s") % dict(
            unit=tunit, tot=int(tot)))
        if convHours:
            # convert to minutes
            tot *= 60
        self._line(tableLines, _("Average for days studied"), self._avgDay(
            tot, studied, unit))
        if studied != period:
            # don't display if you did study every day
            self._line(tableLines, _("If you studied every day"), self._avgDay(
                tot, period, unit))
        if total and tot:
            perMin = total / float(tot)
            perMin = round(perMin, 1)
            # don't round down to zero
            if perMin < 0.1:
                text = _("less than 0.1 cards/minute")
            else:
                text = _("%.01f cards/minute") % perMin
            self._line(
                tableLines, _("Average answer time"),
                _("%(a)0.1fs (%(text)s)") % dict(a=(tot*60)/total, text=text))
        return self._lineTbl(tableLines), int(tot)

    def _splitRepData(self, data, spec):
        sep = {}
        totcnt = {}
        totd = {}
        alltot = []
        allcnt = 0
        for (index, col, lab) in spec:
            totcnt[index] = 0
            totd[index] = []
        for row in data:
            for (index, col, lab) in spec:
                if index not in sep:
                    sep[index] = []
                sep[index].append((row[0], row[index]))
                totcnt[index] += row[index]
                allcnt += row[index]
                totd[index].append((row[0], totcnt[index]))
            alltot.append((row[0], allcnt))
        ret = []
        for (index, col, lab) in spec:
            if len(totd[index]) and totcnt[index]:
                # bars
                ret.append(dict(data=sep[index], color=col, label=lab))
                # lines
                ret.append(dict(
                    data=totd[index], color=col, label=None, yaxis=2,
                bars={'show': False}, lines=dict(show=True), stack=-index))
        return (ret, alltot)

    def _added(self, num=7, chunk=1):
        lims = []
        if num is not None:
            lims.append("id > %d" % (
                (self.col.sched.dayCutoff-(num*chunk*86400))*1000))
        lims.append("did in %s" % self._limit())
        if lims:
            lim = "where " + " and ".join(lims)
        else:
            lim = ""
        if self.type == CARD_NEW:
            tf = 60.0 # minutes
        else:
            tf = 3600.0 # hours
        return self.col.db.all("""
select
(cast((id/1000.0 - :cut) / 86400.0 as int))/:chunk as day,
count(id)
from cards %s
group by day order by day""" % lim, cut=self.col.sched.dayCutoff,tf=tf, chunk=chunk)

    def _done(self, num=7, chunk=1):
        lims = []
        if num is not None:
            lims.append("id > %d" % (
                (self.col.sched.dayCutoff-(num*chunk*86400))*1000))
        lim = self._revlogLimit()
        if lim:
            lims.append(lim)
        if lims:
            lim = "where " + " and ".join(lims)
        else:
            lim = ""
        if self.type == CARD_NEW:
            tf = 60.0 # minutes
        else:
            tf = 3600.0 # hours
        return self.col.db.all(f"""
select
(cast((id/1000.0 - :cut) / 86400.0 as int))/:chunk as day,
sum(case when type = {CARD_NEW} then 1 else 0 end), -- lrn count
sum(case when type = {CARD_LRN} and lastIvl < 21 then 1 else 0 end), -- yng count
sum(case when type = {CARD_LRN} and lastIvl >= 21 then 1 else 0 end), -- mtr count
sum(case when type = {CARD_DUE} then 1 else 0 end), -- lapse count
sum(case when type = {CARD_FILTERED} then 1 else 0 end), -- cram count
sum(case when type = {CARD_FILTERED} then time/1000.0 else 0 end)/:tf, -- lrn time
-- yng + mtr time
sum(case when type = {CARD_LRN} and lastIvl < 21 then time/1000.0 else 0 end)/:tf,
sum(case when type = {CARD_LRN} and lastIvl >= 21 then time/1000.0 else 0 end)/:tf,
sum(case when type = {CARD_DUE} then time/1000.0 else 0 end)/:tf, -- lapse time
sum(case when type = {CARD_FILTERED} then time/1000.0 else 0 end)/:tf -- cram time
from revlog %s
group by day order by day""" % lim,
                            cut=self.col.sched.dayCutoff,
                            tf=tf,
                            chunk=chunk)

    def _daysStudied(self):
        lims = []
        num = self._periodDays()
        if num:
            lims.append(
                "id > %d" %
                ((self.col.sched.dayCutoff-(num*86400))*1000))
        rlim = self._revlogLimit()
        if rlim:
            lims.append(rlim)
        if lims:
            lim = "where " + " and ".join(lims)
        else:
            lim = ""
        return self.col.db.first("""
select count(), abs(min(day)) from (select
(cast((id/1000 - :cut) / 86400.0 as int)+1) as day
from revlog %s
group by day order by day)""" % lim,
                                   cut=self.col.sched.dayCutoff)

    # Intervals
    ######################################################################

    def ivlGraph(self):
        (ivls, all, avg, max_), chunk = self._ivls()
        tot = 0
        totd = []
        if not ivls or not all:
            return ""
        for (grp, cnt) in ivls:
            tot += cnt
            totd.append((grp, tot/float(all)*100))
        if self.type == CARD_NEW:
            ivlmax = 31
        elif self.type == CARD_LRN:
            ivlmax = 52
        else:
            ivlmax = max(5, ivls[-1][0])
        txt = self._title(_("Intervals"),
                          _("Delays until reviews are shown again."))
        txt += self._graph(id="ivl", ylabel2=_("Percentage"), xunit=chunk, data=[
            dict(data=ivls, color=colIvl),
            dict(data=totd, color=colCum, yaxis=2,
             bars={'show': False}, lines=dict(show=True), stack=False)
            ], conf=dict(
                xaxis=dict(min=-0.5, max=ivlmax+0.5),
                yaxes=[dict(), dict(position="right", max=105)]))
        tableLines = []
        self._line(tableLines, _("Average interval"), fmtTimeSpan(avg*86400))
        self._line(tableLines, _("Longest interval"), fmtTimeSpan(max_*86400))
        return txt + self._lineTbl(tableLines)

    def _ivls(self):
        start, end, chunk = self.get_start_end_chunk()
        lim = "and grp <= %d" % end if end else ""
        data = [self.col.db.all(f"""
select ivl / :chunk as grp, count() from cards
where did in %s and queue = {QUEUE_REV} %s
group by grp
order by grp""" % (self._limit(), lim), chunk=chunk)]
        return data + list(self.col.db.first(f"""
select count(), avg(ivl), max(ivl) from cards where did in %s and queue = {QUEUE_REV}""" %
                                         self._limit())), chunk

    # Eases
    ######################################################################

    def easeGraph(self):
        # 3 + 4 + 4 + spaces on sides and middle = 15
        # yng starts at 1+3+1 = 5
        # mtr starts at 5+4+1 = 10
        dic = {'lrn':[], 'yng':[], 'mtr':[]}
        types = ("lrn", "yng", "mtr")
        eases = self._eases()
        for (type, ease, cnt) in eases:
            if type == CARD_LRN:
                ease += 5
            elif type == CARD_DUE:
                ease += 10
            index = types[type]
            dic[index].append((ease, cnt))
        ticks = [[1,1],[2,2],[3,3], # [4,4]
                 [6,1],[7,2],[8,3],[9,4],
                 [11, 1],[12,2],[13,3],[14,4]]
        if self.col.schedVer() != 1:
            ticks.insert(3, [4,4])
        txt = self._title(_("Answer Buttons"),
                          _("The number of times you have pressed each button."))
        txt += self._graph(id="ease", data=[
            dict(data=dic['lrn'], color=colLearn, label=_("Learning")),
            dict(data=dic['yng'], color=colYoung, label=_("Young")),
            dict(data=dic['mtr'], color=colMature, label=_("Mature")),
            ], type="bars", conf=dict(
                xaxis=dict(ticks=ticks, min=0, max=15)),
            ylabel=_("Answers"))
        txt += self._easeInfo(eases)
        return txt

    def _easeInfo(self, eases):
        types = {0: [0, 0], 1: [0, 0], 2: [0,0]}
        for (type, ease, cnt) in eases:
            if ease == 1:
                types[type][0] += cnt
            else:
                types[type][1] += cnt
        tableLines = []
        for type in range(3):
            (bad, good) = types[type]
            tot = bad + good
            try:
                pct = good / float(tot) * 100
            except:
                pct = 0
            tableLines.append(_(
                "Correct: <b>%(pct)0.2f%%</b><br>(%(good)d of %(tot)d)") % dict(
                pct=pct, good=good, tot=tot))
        return ("""
<center><table width=%dpx><tr><td width=50></td><td align=center>""" % self.width +
                "</td><td align=center>".join(tableLines) +
                "</td></tr></table></center>")

    def _eases(self):
        lims = []
        lim = self._revlogLimit()
        if lim:
            lims.append(lim)
        days = self._periodDays()
        if days is not None:
            lims.append("id > %d" % (
                (self.col.sched.dayCutoff-(days*86400))*1000))
        if lims:
            lim = "where " + " and ".join(lims)
        else:
            lim = ""
        if self.col.schedVer() == 1:
            ease4repl = "3"
        else:
            ease4repl = "ease"
        return self.col.db.all(f"""
select (case
when type in ({CARD_NEW},{CARD_DUE}) then 0
when lastIvl < 21 then 1
else 2 end) as thetype,
(case when type in ({CARD_NEW},{CARD_DUE}) and ease = 4 then %s else ease end), count() from revlog %s
group by thetype, ease
order by thetype, ease""" % (ease4repl, lim))

    # Hourly retention
    ######################################################################

    def hourGraph(self):
        data = self._hourRet()
        if not data:
            return ""
        shifted = []
        counts = []
        mcount = 0
        trend = []
        peak = 0
        for datum in data:
            hour = (datum[0] - 4) % 24
            pct = datum[1]
            if pct > peak:
                peak = pct
            shifted.append((hour, pct))
            counts.append((hour, datum[2]))
            if datum[2] > mcount:
                mcount = datum[2]
        shifted.sort()
        counts.sort()
        if len(counts) < 4:
            return ""
        for d in shifted:
            hour = d[0]
            pct = d[1]
            if not trend:
                trend.append((hour, pct))
            else:
                prev = trend[-1][1]
                diff = pct-prev
                diff /= 3.0
                diff = round(diff, 1)
                trend.append((hour, prev+diff))
        txt = self._title(_("Hourly Breakdown"),
                          _("Review success rate for each hour of the day."))
        txt += self._graph(id="hour", data=[
            dict(data=shifted, color=colCum, label=_("% Correct")),
            dict(data=counts, color=colHour, label=_("Answers"), yaxis=2,
             bars=dict(barWidth=0.2), stack=False)
        ], conf=dict(
            xaxis=dict(ticks=[[0, _("4AM")], [6, _("10AM")],
                           [12, _("4PM")], [18, _("10PM")], [23, _("3AM")]]),
            yaxes=[dict(max=peak), dict(position="right", max=mcount)]),
        ylabel=_("% Correct"), ylabel2=_("Reviews"))
        txt += _("Hours with less than 30 reviews are not shown.")
        return txt

    def _hourRet(self):
        lim = self._revlogLimit()
        if lim:
            lim = " and " + lim
        if self.col.schedVer() == 1:
            sd = datetime.datetime.fromtimestamp(self.col.crt)
            rolloverHour = sd.hour
        else:
            rolloverHour = self.col.conf.get("rollover", 4)
        pd = self._periodDays()
        if pd:
            lim += " and id > %d" % ((self.col.sched.dayCutoff-(86400*pd))*1000)
        return self.col.db.all(f"""
select
23 - ((cast((:cut - id/1000) / 3600.0 as int)) %% 24) as hour,
sum(case when ease = 1 then 0 else 1 end) /
cast(count() as float) * 100,
count()
from revlog where type in ({REVLOG_LRN},{REVLOG_REV},{REVLOG_RELRN}) %s
group by hour having count() > 30 order by hour""" % lim,
                            cut=self.col.sched.dayCutoff-(rolloverHour*3600))

    # Cards
    ######################################################################

    def cardGraph(self):
        # graph data
        div = self._cards()
        nameColor = []
        for index, (kindOfCard, col) in enumerate((
            (_("Mature"), colMature),
            (_("Young+Learn"), colYoung),
            (_("Unseen"), colUnseen),
            (_("Suspended+Buried"), colSusp))):
            nameColor.append(dict(data=div[index], label="%s: %s" % (kindOfCard, div[index]), color=col))
        # text data
        tableLines = []
        (countCard, countNote) = self.col.db.first("""
select count(id), count(distinct nid) from cards
where did in %s """ % self._limit())
        self._line(tableLines, _("Total cards"), countCard)
        self._line(tableLines, _("Total notes"), countNote)
        (low, avg, high) = self._factors()
        if low:
            self._line(tableLines, _("Lowest ease"), "%d%%" % low)
            self._line(tableLines, _("Average ease"), "%d%%" % avg)
            self._line(tableLines, _("Highest ease"), "%d%%" % high)
        info = "<table width=100%>" + "".join(tableLines) + "</table><p>"
        info += _('''\
A card's <i>ease</i> is the size of the next interval \
when you answer "good" on a review.''')
        txt = self._title(_("Card Types"),
                          _("The division of cards in your deck(s)."))
        txt += "<table width=%d><tr><td>%s</td><td>%s</td></table>" % (
            self.width,
            self._graph(id="cards", data=nameColor, type="pie"),
            info)
        return txt

    def _line(self, tableLines, a, value, bold=True):
        #T: Symbols separating first and second column in a statistics table. Eg in "Total:    3 reviews".
        colon = _(":")
        if bold:
            tableLines.append(("<tr><td width=200 align=right>%s%s</td><td><b>%s</b></td></tr>") % (a,colon,value))
        else:
            tableLines.append(("<tr><td width=200 align=right>%s%s</td><td>%s</td></tr>") % (a,colon,value))

    def _lineTbl(self, tableLines):
        return "<table width=400>" + "".join(tableLines) + "</table>"

    def _factors(self):
        return self.col.db.first(f"""
select
min(factor) / 10.0,
avg(factor) / 10.0,
max(factor) / 10.0
from cards where did in %s and queue = {QUEUE_REV}""" % self._limit())

    def _cards(self):
        return self.col.db.first(f"""
select
sum(case when queue={QUEUE_REV} and ivl >= 21 then 1 else 0 end), -- mtr
sum(case when queue in ({QUEUE_LRN},{QUEUE_DAY_LRN}) or (queue={QUEUE_REV} and ivl < 21) then 1 else 0 end), -- yng/lrn
sum(case when queue={QUEUE_NEW_CRAM} then 1 else 0 end), -- new
sum(case when queue<0 then 1 else 0 end) -- susp
from cards where did in %s""" % self._limit())

    # Footer
    ######################################################################

    def footer(self):
        html = "<br><br><font size=1>"
        html += _("Generated on %s") % time.asctime(time.localtime(time.time()))
        html += "<br>"
        if self.wholeCollection:
            deck = _("whole collection")
        else:
            deck = self.col.decks.current()['name']
        html += _("Scope: %s") % deck
        html += "<br>"
        html += _("Period: %s") % [
            _("1 month"),
            _("1 year"),
            _("deck life")
            ][self.type]
        return html

    # Tools
    ######################################################################

    def _graph(self, id, data, conf=None,
               type="bars", xunit=1, ylabel=_("Cards"), ylabel2=""):
        if conf is None:
            conf = {}
        # display settings
        if type == "pie":
            conf['legend'] = {'container': "#%sLegend" % id, 'noColumns':2}
        else:
            conf['legend'] = {'container': "#%sLegend" % id, 'noColumns':10}
        conf['series'] = dict(stack=True)
        if not 'yaxis' in conf:
            conf['yaxis'] = {}
        conf['yaxis']['labelWidth'] = 40
        if 'xaxis' not in conf:
            conf['xaxis'] = {}
        if xunit is None:
            conf['timeTicks'] = False
        else:
            #T: abbreviation of day
            day = _("d")
            #T: abbreviation of week
            w = _("w")
            #T: abbreviation of month
            mo = _("mo")
            conf['timeTicks'] = {1: day, 7: w, 31: mo}[xunit]
        # types
        width = self.width
        height = self.height
        if type == "bars":
            conf['series']['bars'] = dict(
                show=True, barWidth=0.8, align="center", fill=0.7, lineWidth=0)
        elif type == "barsLine":
            print("deprecated - use 'bars' instead")
            conf['series']['bars'] = dict(
                show=True, barWidth=0.8, align="center", fill=0.7, lineWidth=3)
        elif type == "fill":
            conf['series']['lines'] = dict(show=True, fill=True)
        elif type == "pie":
            width /= 2.3
            height *= 1.5
            ylabel = ""
            conf['series']['pie'] = dict(
                show=True,
                radius=1,
                stroke=dict(color="#fff", width=5),
                label=dict(
                    show=True,
                    radius=0.8,
                    threshold=0.01,
                    background=dict(
                        opacity=0.5,
                        color="#000"
                    )))
        return (
"""
<table cellpadding=0 cellspacing=10>
<tr>

<td><div style="width: 150px; text-align: center; position:absolute;
 -webkit-transform: rotate(-90deg) translateY(-85px);
font-weight: bold;
">%(ylab)s</div></td>

<td>
<center><div id=%(id)sLegend></div></center>
<div id="%(id)s" style="width:%(w)spx; height:%(height)spx;"></div>
</td>

<td><div style="width: 150px; text-align: center; position:absolute;
 -webkit-transform: rotate(90deg) translateY(65px);
font-weight: bold;
">%(ylab2)s</div></td>

</tr></table>
<script>
$(function () {
    var conf = %(conf)s;
    if (conf.timeTicks) {
        conf.xaxis.tickFormatter = function (val, axis) {
            return val.toFixed(0)+conf.timeTicks;
        }
    }
    conf.yaxis.minTickSize = 1;
    // prevent ticks from having decimals (use whole numbers instead)
    conf.yaxis.tickDecimals = 0;
    conf.yaxis.tickFormatter = function (val, axis) {
            // Just in case we get ticks with decimals, render to one decimal position.  If it's
            // a whole number then render without any decimal (i.e. without the trailing .0).
            return val === Math.round(val) ? val.toFixed(0) : val.toFixed(1);
    }
    if (conf.series.pie) {
        conf.series.pie.label.formatter = function(label, series){
            return '<div class=pielabel>'+Math.round(series.percent)+'%%</div>';
        };
    }
    $.plot($("#%(id)s"), %(data)s, conf);
});
</script>""" % dict(
    id=id, w=width, height=height,
    ylab=ylabel, ylab2=ylabel2,
    data=json.dumps(data), conf=json.dumps(conf)))

    def _limit(self):
        if self.wholeCollection:
            return ids2str([deck['id'] for deck in self.col.decks.all()])
        return self.col.sched._deckLimit()

    def _revlogLimit(self):
        if self.wholeCollection:
            return ""
        return ("cid in (select id from cards where did in %s)" %
                ids2str(self.col.decks.active()))

    def _title(self, title, subtitle=""):
        return '<h1>%s</h1>%s' % (title, subtitle)

    def _deckAge(self, by):
        lim = self._revlogLimit()
        if lim:
            lim = " where " + lim
        if by == 'review':
            time = self.col.db.scalar("select id from revlog %s order by id limit 1" % lim)
        elif by == 'add':
            lim = "where did in %s" % ids2str(self.col.decks.active())
            time = self.col.db.scalar("select id from cards %s order by id limit 1" % lim)
        if not time:
            period = 1
        else:
            period = max(
                1, int(1+((self.col.sched.dayCutoff - (time/1000)) / 86400)))
        return period

    def _periodDays(self):
        start, end, chunk = self.get_start_end_chunk()
        if end is None:
            return None
        return end * chunk

    def _avgDay(self, tot, num, unit):
        vals = []
        try:
            vals.append(_("%(a)0.1f %(unit)s/day") % dict(a=tot/float(num), unit=unit))
            return ", ".join(vals)
        except ZeroDivisionError:
            return ""
