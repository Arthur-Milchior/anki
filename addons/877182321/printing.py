def cap(n):
    """The number. Either n, or capped according to cap value"""
    capValue = getUserOption("cap value",0)
    if capValue == 0:
        if n == 0:
            return "0"
        else:
            return "+"
        if n >= capValue and capValue >0:
            return str(c) + "+"
        return str(n)


def conditionString(cond,string = None, parenthesis = False):
    """If the condition cond holds: return the string if it's not None, else the cond.
    If its not empty, add parenthesis around them
    """
    if not cond:
        return ""
    if string is not None:
        ret = str(string)
    else:
        ret = str(cond)
    if parenthesis:
        ret = f"(+{ret})"
    return ret

def nowLater(first, second = None):
    """A representation for the pair"""
    first = conditionString(first)
    second = conditionString(second, parenthesis = True)
    return first+second
