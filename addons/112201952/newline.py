# -*- coding: utf-8 -*-
# Copyright: Arthur Milchior <arthur@milchior.fr>
# Based on anki code by Damien Elmes <anki@ichi2.net>
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
# Source in https://github.com/Arthur-Milchior/anki-json-new-line
# Addon number 11201952
import json
import re
import sys

from aqt.addons import AddonManager, ConfigEditor

from .debug import debug, debugFun

debug("json")
oldLoads=json.loads
def newLoads(t,*args,**kwargs):
    debug(f"newLoads «{t}»")
    t_=correctJson(t)
    debug(f"t_ is {t_}")
    res = oldLoads(t_,*args,**kwargs)
    debug("res is {res}")
    # if res is None:
    #     print(f"«{t}» led to None")
    #print(f"From «{t}» to «{res}»")
    return res

json.loads=newLoads


@debugFun
def correctJson(text):
    """Text, with new lines replaced by \n when inside quotes"""
    if not isinstance(text,str):
        return text
    def correctQuotedString(match):
        string = match[0]
        debug("Found string «{string}»")
        return string.replace("\n","\\n")
    res= re.sub(r'"(?:(?<=[^\\])(?:\\\\)*\\"|[^"])*"',correctQuotedString,text,re.M)
    if res is None:
        debug("«{text}» was sent to None")
    return res

def readableJson(text):
    """Text, where \n are replaced with new line. Unless it's preceded by a odd number of \."""
    l=[]
    numberOfSlashOdd=False
    numberOfQuoteOdd=False
    for char in text:
        if char == "n" and numberOfQuoteOdd and numberOfSlashOdd:
            l[-1]="\n"
            debug("replacing last slash by newline")
        else:
            l.append(char)
            if char=="\n":
                char="newline"
            debug(f"adding {char}")

        if char == "\"":
            if not numberOfSlashOdd:
                numberOfQuoteOdd = not numberOfQuoteOdd
                debug(f"numberOfQuoteOdd is now {numberOfQuoteOdd}")

        if char == "\\":
            numberOfSlashOdd = not numberOfSlashOdd
        else:
            numberOfSlashOdd = False
        debug(f"numberOfSlashOdd is now {numberOfSlashOdd}")
    return "".join(l)



def updateText(self, conf):
    self.form.editor.setPlainText(
        readableJson(json.dumps(conf,sort_keys=True,indent=4, separators=(',', ': '))))
ConfigEditor.updateText=updateText
