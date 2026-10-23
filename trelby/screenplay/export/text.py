# plain text export.

import trelby.util as util
from trelby.screenplay.constants import (
    DIALOGUE,
)


# return a dual dialogue or a two-column script's row (see
# getSideBySideLines) as a list of (lineType, text) rows of plain text,
# indented with spaces, with the columns side by side. lineType is that of
# the row's left column if it has a line there, otherwise the right
# column's, and DIALOGUE for empty rows.
def getColumnTextRows(sp, first, right, last):
    twoColumn = sp.isTwoColumn()

    def column(start, end, col):
        rows = []

        for i in range(start, end + 1):
            if i != start:
                rows.extend([(None, "")] * (sp.getSpacingBefore(i) // 10))

            text = sp.getExportText(i)

            if text and sp.needsExtraParenIndent(i):
                text = " " + text

            if twoColumn:
                indent = sp.cfg.getType(sp.lines[i].lt).indent
            else:
                indent = sp.cfg.getDualIndentWidth(sp.lines[i].lt, col)[0]
            rows.append((sp.lines[i].lt, " " * indent + text))

        return rows

    leftRows = column(first, right - 1, 1)
    rightRows = column(right, last, 2)
    ret = []

    for k in range(max(len(leftRows), len(rightRows))):
        lt1, text1 = leftRows[k] if k < len(leftRows) else (None, "")
        lt2, text2 = rightRows[k] if k < len(rightRows) else (None, "")

        if text2.strip():
            indent = len(text2) - len(text2.lstrip())
            text1 = text1.ljust(indent) + text2.lstrip()

        ret.append((lt1 or lt2 or DIALOGUE, text1))

    return ret


# generate formatted text and return it as a string. if 'dopages' is
# True, marks pagination in the output.
def generateText(sp, doPages):
    ls = sp.lines

    output = util.String()

    for p in range(1, len(sp.pages)):
        start, end = sp.page2lines(p)
        dualLines = sp.getSideBySideLines(start, end)

        if doPages and (p != 1):
            s = "%s %s. " % ("-" * 30, sp.pageLabels[p])
            s += "-" * (60 - len(s))
            output += "\n%s\n\n" % s

        for i in range(start, end + 1):
            line = ls[i]
            tcfg = sp.cfg.getType(line.lt)
            dual = dualLines.get(i)

            # dual dialogues and rows are output whole at their first line
            if dual and (i != dual[1]):
                continue

            text = sp.getExportText(i)

            if (i != 0) and (not doPages or (i != start)):
                output += (sp.getSpacingBefore(i) // 10) * "\n"

            if dual:
                for lt, s in getColumnTextRows(sp, *dual[1:]):
                    output += s + "\n"

                continue

            if text and sp.needsExtraParenIndent(i):
                text = " " + text

            text = " " * int(sp.getCenterOffset(i)) + text

            output += " " * tcfg.indent + text + "\n"

    return str(output)
