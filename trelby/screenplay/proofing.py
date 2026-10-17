# the formatting checker (Tools -> Check formatting errors, and the check
# before export / compare): finds common formatting mistakes.

from dataclasses import dataclass

import trelby.textutil as textutil
from trelby.screenplay.constants import (
    CHARACTER,
    DIALOGUE,
    LB_LAST,
    PAREN,
)


# a formatting error: the line it's on and a description of it
@dataclass
class FormattingError:
    line: int
    msg: str


# return a list of the formatting errors in the screenplay, in script order,
# at most one per line (the first problem found on it)
def findErrors(sp):
    errors = []

    # type of previous line, or None when a new element starts
    prevType = None

    for line, ln in enumerate(sp.lines):
        msg = _lineError(sp, line, prevType)

        if msg:
            errors.append(FormattingError(line, msg))

        if ln.lb == LB_LAST:
            prevType = None
        else:
            prevType = ln.lt

    return errors


# the description of the first problem with the given line, or None.
# 'prevType' is the type of the line before it in the same element, or None
# if it starts an element.
def _lineError(sp, line, prevType):
    cfg = sp.cfg
    ln = sp.lines[line]
    tcfg = cfg.getType(ln.lt)

    isFirst = sp.isFirstLineOfElem(line)
    isLast = sp.isLastLineOfElem(line)
    isOnly = isFirst and isLast

    prev = sp.getTypeOfPrevElem(line)
    next = sp.getTypeOfNextElem(line)

    if len(ln.text) == 0:
        return _("Empty line.")

    if len(ln.text.strip("  ")) == 0:
        return _("Empty line (contains only spaces).")

    if (ln.lt == PAREN) and isOnly and (ln.text == "()"):
        return _("Empty parenthetical.")

    if ln.text != textutil.toInputStr(ln.text):
        return _("Line contains invalid characters (BUG).")

    if len(ln.text.rstrip(" ")) > (tcfg.width // cfg.getCharWidth()):
        return _("Line is too long (BUG).")

    if ln.lt == CHARACTER:
        if isLast and next and next not in (PAREN, DIALOGUE):
            return _("Element type '{}' can not follow type '{}'.").format(
                cfg.getType(next).ti.name, tcfg.ti.name
            )

    if ln.lt == PAREN:
        if isFirst and prev and prev not in (CHARACTER, DIALOGUE):
            return _("Element type '{}' can not follow type '{}'.").format(
                tcfg.ti.name, cfg.getType(prev).ti.name
            )

    if ln.lt == DIALOGUE:
        if isFirst and prev and prev not in (CHARACTER, PAREN):
            return _("Element type '{}' can not follow type '{}'.").format(
                tcfg.ti.name, cfg.getType(prev).ti.name
            )

    if prevType and (ln.lt != prevType):
        return _("Element contains lines with different line types (BUG).")

    return None
