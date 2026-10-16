# inline text formatting (bold / italic / underline): toggling it on the
# selection, and the style new text is typed in.

import trelby.textfmt as textfmt
import trelby.undo as undo
from trelby.screenplay.constants import (
    LB_NONE,
    LB_SPACE,
)


class FormattingMixin:
    # return (style, isSet) for text typed at the cursor: the style set
    # with toggleFormat at this cursor position (isSet = True), or else
    # that of the character before the cursor in the same paragraph.
    def getTypingStyle(self):
        ts = self.typingStyle

        if ts and (ts[0] == self.line) and (ts[1] == self.column):
            return (ts[2], True)

        ls = self.sp.lines
        ln = ls[self.line]

        if self.column > 0:
            return (textfmt.styleAt(ln.fmt, self.column - 1), False)

        if (self.line > 0) and (ls[self.line - 1].lb in (LB_SPACE, LB_NONE)):
            prev = ls[self.line - 1]

            return (textfmt.styleAt(prev.fmt, len(prev.text) - 1), False)

        return (0, False)

    # return the formatting bits (textfmt.BOLD etc.) that are on for the
    # selected text, i.e. that all of it has, or with nothing selected,
    # that text typed at the cursor would get
    def getFormatState(self):
        marked = self.getMarkedLines()

        if not marked:
            return self.getTypingStyle()[0]

        style = textfmt.ALL
        empty = True

        # format string characters are "0" - "7": the style bits plus
        # ord("0") (see textfmt.char), hence the "- 48" here and in
        # toggleFormat
        for i in range(marked[0], marked[1] + 1):
            c1, c2 = self.getMarkedColumns(i, marked)

            for c in self.sp.lines[i].getFmt()[c1 : c2 + 1]:
                style &= ord(c) - 48
                empty = False

        return 0 if empty else style

    # toggle a formatting bit (textfmt.BOLD etc.) on the selected text:
    # set it if any of it doesn't have it, otherwise clear it. with
    # nothing selected, toggles it for text typed at the cursor. the
    # selection stays as it is.
    def toggleFormat(self, bit):
        marked = self.getMarkedLines()

        if not marked:
            style = self.getTypingStyle()[0] ^ bit
            self.typingStyle = (self.line, self.column, style)

            return

        ls = self.sp.lines

        # whether all the selected text has the bit already
        allSet = bool(self.getFormatState() & bit)

        u = undo.AnyDifference(self)

        for i in range(marked[0], marked[1] + 1):
            c1, c2 = self.getMarkedColumns(i, marked)
            ln = ls[i]
            fmt = ln.getFmt()
            part = "".join(
                textfmt.char(
                    ((ord(c) - 48) & ~bit) if allSet else ((ord(c) - 48) | bit)
                )
                for c in fmt[c1 : c2 + 1]
            )
            ln.fmt = textfmt.compact(fmt[:c1] + part + fmt[c2 + 1 :])

        self.sp.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)
