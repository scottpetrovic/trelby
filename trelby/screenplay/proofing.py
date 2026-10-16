# the script checker (Script -> Check script): finds common formatting
# mistakes.

import trelby.util as util
from trelby.screenplay.constants import (
    CHARACTER,
    DIALOGUE,
    LB_LAST,
    NOTE,
    PAREN,
)


# find next error in screenplay, starting at given line. returns
# (line, msg) tuple, where line is -1 if no error was found and the
# line number otherwise where the error is, and msg is a description
# of the error
def findError(sp, line):
    ls = sp.lines
    cfg = sp.cfg

    # type of previous line, or None when a new element starts
    prevType = None

    msg = None
    while 1:
        if line >= len(ls):
            break

        ln = ls[line]
        tcfg = cfg.getType(ln.lt)

        isFirst = sp.isFirstLineOfElem(line)
        isLast = sp.isLastLineOfElem(line)
        isOnly = isFirst and isLast

        prev = sp.getTypeOfPrevElem(line)
        next = sp.getTypeOfNextElem(line)

        # notes are allowed to contain empty lines, because a) they do
        # not appear in the final product b) they're basically
        # free-format text anyway, and people may want to format them
        # however they want

        if (len(ln.text) == 0) and (ln.lt != NOTE):
            msg = _("Empty line.")
            break

        if (len(ln.text.strip("  ")) == 0) and (ln.lt != NOTE):
            msg = _("Empty line (contains only spaces).")
            break

        if (ln.lt == PAREN) and isOnly and (ln.text == "()"):
            msg = _("Empty parenthetical.")
            break

        if ln.text != util.toInputStr(ln.text):
            msg = _("Line contains invalid characters (BUG).")
            break

        if len(ln.text.rstrip(" ")) > (tcfg.width // cfg.getCharWidth()):
            msg = _("Line is too long (BUG).")
            break

        if ln.lt == CHARACTER:
            if isLast and next and next not in (PAREN, DIALOGUE):
                msg = _("Element type '{}' can not follow type '{}'.").format(
                    cfg.getType(next).ti.name, tcfg.ti.name
                )
                break

        if ln.lt == PAREN:
            if isFirst and prev and prev not in (CHARACTER, DIALOGUE):
                msg = _("Element type '{}' can not follow type '{}'.").format(
                    tcfg.ti.name, cfg.getType(prev).ti.name
                )
                break

        if ln.lt == DIALOGUE:
            if isFirst and prev and prev not in (CHARACTER, PAREN):
                msg = _("Element type '{}' can not follow type '{}'.").format(
                    tcfg.ti.name, cfg.getType(prev).ti.name
                )
                break

        if prevType:
            if ln.lt != prevType:
                msg = _("Element contains lines with different line types (BUG).")
                break

        if ln.lb == LB_LAST:
            prevType = None
        else:
            prevType = ln.lt

        line += 1

    if not msg:
        line = -1

    return (line, msg)
