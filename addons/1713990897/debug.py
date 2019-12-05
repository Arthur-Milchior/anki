import re
from inspect import stack

mayDebug = False

indentation = 0
def debug(text, indentToAdd=0, level =1):
    global indentation
    glob = stack()[level].frame.f_globals
    loc = stack()[level].frame.f_locals
    text = eval(f"""f"{text}" """,glob,loc)
    indentToPrint = indentation
    t = " "*indentToPrint
    if indentToAdd>0:
        t+= "{<"
    space = " "
    newline = "\n"
    t+= re.sub(newline,newline+space,text)
    print (t)
    indentation +=indentToAdd
    if indentToAdd<0:
        indentToPrint +=indentToAdd
        print((" "*indentToPrint)+">}")

def debugFun(fun, debug=debug):
    if not mayDebug:
        return fun
    def aux_debugFun(*args, **kwargs):
        nonlocal debug
        t = f"{fun.__qualname__}("
        first = False
        def comma(text):
            nonlocal first, t
            if not first:
                first = True
            else:
                t+=", "
            t+=text
        for arg in args:
            comma(f"«{arg}»")
        for kw in kwargs:
            comma(f"«{kw}={kwargs[kw]}»")
        t+=")"
        debug("{t}",1)
        ret = fun(*args, **kwargs)
        debug("returns {ret}",-1)
        return ret
    aux_debugFun.__name__ = f"debug_{fun.__name__}"
    aux_debugFun.__qualname__ = f"debug_{fun.__qualname__}"
    return aux_debugFun
