# -*- coding: utf-8 -*-
# Copyright: Arthur Milchior arthur@milchior.fr
# encoding: utf8
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
# Feel free to contribute to this code on https://github.com/Arthur-Milchior/anki-Multiple-Windows
# Add-on number 354407385 https://ankiweb.net/shared/info/354407385
from inspect import stack

import aqt
import sip
from anki.hooks import remHook
from aqt import DialogManager, mw
from aqt.editcurrent import EditCurrent


def debug(t):
    #print(t)
    pass

def shouldBeMultiple(name):
    """Whether window name may have multiple copy.

    Ensure that ["multiple"] exsits in the configuration file. The default value being True.
    """
    debug(f"Calling shouldBeMultiple({name})")
    userOption = mw.addonManager.getConfig(__name__)
    if "multiple" not in userOption:
        userOption["multiple"]={"default": True}
        debug(f"""Adding "multiple" to userOption""")
        mw.addonManager.writeConfig(__name__,userOption)
    multipleOption = userOption["multiple"]
    debug(f"""multipleOption is {multipleOption}""")
    if name in multipleOption:
        debug(f"""{name} in multipleOption, its value is {multipleOption[name]}""")
        return multipleOption[name]
    elif "default" in multipleOption:
        debug(f"""Not {name} but "default" in multipleOption, its value is {multipleOption["default"]}""")
        return multipleOption["default"]
    else:
        debug(f"""Not {name} nor "default" in multipleOption. Returning True""")
        return  True


class DialogManagerMultiple(DialogManager):
    """Associating to a window name a pair (as a list...)

    The element associated to WindowName Is composed of:
    First element is the class to use to create the window WindowName.
    Second element is always None
    """
    # We inherits from aqt.DialogManager. Thus, if something is added to
    # its _dialogs, we have access to it.

    # Every method are redefined, they use the parent's method when it makes sens.

    def __init__(self,oldDialog=None):
        if oldDialog is not None:
            DialogManagerMultiple._dialogs= oldDialog._dialogs
        super().__init__()

    _openDialogs = list()
    def open(self,name,*args):
        """Open a new window, with name and args.

        Or reopen the window name, if it should be single in the
        config, and is already opened.
        """
        debug(f"Calling open({name},*args)")
        function = self.openMany if shouldBeMultiple(name) else super().open
        return function(name,*args)


    def openMany(self, name, *args):
        """Open a new window whose kind is name.

        keyword arguments:
        args -- values passed to the opener.
        name -- the name of the window to open
        """
        debug(f"Calling openMany({name},{args})")
        (creator, _) = self._dialogs[name]
        instance = creator(*args)
        self._openDialogs.append(instance)
        return instance

    def markClosedMultiple(self):
        debug(f"markClosedMultiple({self})")
        caller = stack()[2].frame.f_locals['self']
        if caller in self._openDialogs:
            debug(f"caller found")
            self._openDialogs.remove(caller)
        else:
            debug(f"caller not found")

    def markClosed(self, name):
        """Remove the window of windowName from the set of windows. """
        # If it is a window of kind single, then call super
        # Otherwise, use inspect to figure out which is the caller
        debug(f"Calling markClosed({name})")
        if shouldBeMultiple(name):
            self.markClosedMultiple()
        else:
            super().markClosed(name)

    def allClosed(self):
        """
        Whether all windows (except the main window) are marked as
        closed.
        """
        debug(f"Calling allClosed()")
        return self._openDialogs==[] and super().allClosed()


    def closeAll(self, onsuccess):
        """Close all windows (except the main one). Call onsuccess when it's done.

        Return True if some window needed closing.
        None otherwise

        Keyword arguments:
        onsuccess -- the function to call when the last window is closed.
        """
        debug(f"Calling closeAll({onsuccess})")
        def callback():
            """Call onsuccess if all window (except main) are closed."""
            print(f"Calling callback")
            if self.allClosed():
                onsuccess()
            else:
                # still waiting for others to close
                pass
        if self.allClosed():
            onsuccess()
            return

        for instance in self._openDialogs:
            if not sip.isdeleted(instance):#It should be useless. I prefer to keep it to avoid erros
                if getattr(instance, "silentlyClose", False):
                    instance.close()
                    callback()
                else:
                    instance.closeWithCallback(callback)

        return super().closeAll(onsuccess)


aqt.DialogManager = DialogManagerMultiple
aqt.dialogs= DialogManagerMultiple(oldDialog=aqt.dialogs)
debug("Changing dialog manager")

def onReset(self):
        # lazy approach for now: throw away edits
        try:
            n = self.editor.note
            n.load()
        except:
            # card's been deleted
            remHook("reset", self.onReset)
            self.editor.setNote(None)
            self.mw.reset()
            aqt.dialogs.markClosed("EditCurrent")
            self.close()
            return
        self.editor.setNote(n)

EditCurrent.onReset=onReset
