# finding text in a script, and the Editor's replace commands, for Edit /
# Find & Replace (finddlg) and the spell checker (spellcheckdlg).
#
# each line is searched on its own, so text that wraps from one line to
# the next isn't found.

import dataclasses

import trelby.textutil as textutil
import trelby.undo as undo


@dataclasses.dataclass(frozen=True)
class FindOptions:
    text: str = ""
    matchCase: bool = False
    wholeWord: bool = False

    # search towards the start of the script
    up: bool = False

    # the element types (line types) to search in, or None for all
    elementTypes: frozenset = None


# a match of FindOptions.text: length characters at line, col
@dataclasses.dataclass(frozen=True)
class Match:
    line: int
    col: int
    length: int


# where a search of the whole script starts: its start, or going up, its
# end
def startPos(sp, up):
    if up:
        line = len(sp.lines) - 1

        return (line, len(sp.lines[line].text))

    return (0, 0)


# return the first match from line, col on, or going up, the last one
# that ends at or before it, as a Match, or None. doesn't wrap around.
def findNext(sp, line, col, opts):
    value = opts.text
    if not value:
        return None

    if not opts.matchCase:
        value = textutil.upper(value)

    ls = sp.lines

    while 0 <= line < len(ls):
        ln = ls[line]

        if (opts.elementTypes is None) or (ln.lt in opts.elementTypes):
            text = ln.text
            if not opts.matchCase:
                text = textutil.upper(text)

            res = _findInLine(text, value, col, opts)
            if res != -1:
                return Match(line, res, len(value))

        if opts.up:
            line -= 1
            if line >= 0:
                col = len(ls[line].text)
        else:
            line += 1
            col = 0

    return None


# the column of the first match in text starting at or after col, or
# going up, the last one ending at or before it, or -1
def _findInLine(text, value, col, opts):
    n = len(value)

    if opts.up:
        res = text.rfind(value, 0, col)
    else:
        res = text.find(value, col)

    while (res != -1) and opts.wholeWord and not _isWholeWord(text, res, n):
        if opts.up:
            res = text.rfind(value, 0, res + n - 1)
        else:
            res = text.find(value, res + 1)

    return res


# the neighboring characters are sliced rather than indexed, so that past
# the ends of the line they're "", which isWordBoundary counts as a
# boundary
def _isWholeWord(text, col, n):
    return textutil.isWordBoundary(text[col - 1 : col]) and textutil.isWordBoundary(
        text[col + n : col + n + 1]
    )


class SearchEditMixin:
    # replace length characters at line, col with text, as one undo step
    # (or none, if saveUndo is False), and rewrap the paragraph. the
    # cursor is left just past the new text, or at its start if
    # cursorAtStart is True, wherever the rewrapping puts it.
    def replaceRange(
        self, line, col, length, text, cursorAtStart=False, saveUndo=True
    ):
        sp = self.sp
        text = textutil.toInputStr(text)

        if saveUndo:
            u = undo.SinglePara(self, undo.CMD_MISC, line)

        sp.lines[line].replaceText(col, length, text)

        # the line can be too long now, but rewrapPara keeps the cursor on
        # the same text
        self.gotoPos(line, col if cursorAtStart else col + len(text))
        self.rewrapPara(sp.getParaFirstIndexFromLine(line))

        self.clearMark()
        sp.markChanged()

        if saveUndo:
            u.setAfter(self)
            self.undoHistory.add(u)

    # replace a Match with text, leaving the cursor where the next search
    # in that direction should start: past the new text, or going up, at
    # its start, so that it isn't searched again
    def replaceAt(self, match, text, up=False):
        self.replaceRange(match.line, match.col, match.length, text, cursorAtStart=up)

    # replace every match in the script with text, as one undo step (the
    # direction, opts.up, doesn't matter). returns how many were
    # replaced. the cursor is left past the last one.
    def replaceAll(self, opts, text):
        opts = dataclasses.replace(opts, up=False)
        u = undo.AnyDifference(self)
        line, col = startPos(self.sp, False)
        count = 0

        while True:
            m = findNext(self.sp, line, col, opts)
            if not m:
                break

            # searching on from past the new text, so that it isn't
            # replaced again
            self.replaceRange(m.line, m.col, m.length, text, saveUndo=False)
            line, col = self.line, self.column
            count += 1

        if count:
            u.setAfter(self)
            self.undoHistory.add(u)

        return count
