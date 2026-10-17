# helpers shared by the exporters.

import trelby.textfmt as textfmt
import trelby.textutil as textutil
from trelby.screenplay.constants import (
    LB_FORCED,
    LB_LAST,
    LB_SPACE,
)


# return the notes (see screenplay/notes.py) on the element starting at
# line 'first'
def getElemNotes(sp, first):
    last = sp.getElemLastIndexFromLine(first)

    return sum((sp.lines[i].notes for i in range(first, last + 1)), ())


# Return screenplay as list of tuples of the form (elType, elText,
# firstLine, fmt), where firstLine is the index of the element's first
# line and fmt is the format string for elText (see textfmt), or None.
# forced linebreaks are represented as \n characters.
def getElementsAsList(sp):
    ls = sp.lines
    eleList = []
    curLine = ""
    firstLine = 0

    # (text, fmt) of the element's lines and the separators between
    # them, for its format string
    parts = []
    seps = []

    for i, line in enumerate(ls):
        lineType = line.lt
        lineText = line.text

        if sp.cfg.getType(line.lt).export.isCaps:
            lineText = textutil.upper(lineText)

        curLine += lineText
        parts.append((lineText, line.fmt))

        if line.lb == LB_LAST:
            fmt = textfmt.join(parts, seps)
            eleList.append((lineType, curLine, firstLine, fmt))
            curLine = ""
            firstLine = i + 1
            parts = []
            seps = []
        elif line.lb == LB_SPACE:
            curLine += " "
            seps.append(" ")
        elif line.lb == LB_FORCED:
            curLine += "\n"
            seps.append("\n")
        else:
            seps.append("")

    return eleList
