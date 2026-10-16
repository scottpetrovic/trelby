# finding text in a script, and the Editor's replace commands, for Edit /
# Find & Replace (finddlg) and the spell checker (spellcheckdlg).
#
# each paragraph is searched as one string, its lines' texts joined by
# what their line breaks stand for (config.lb2str: " " for LB_SPACE, ""
# for LB_NONE), so text that wraps from one line to the next is found.
# offsets into that string are the ones rewrapPara uses.

import dataclasses

import trelby.config as config
import trelby.textutil as textutil
import trelby.undo as undo
from trelby.screenplay.constants import LB_NONE


@dataclasses.dataclass(frozen=True)
class FindOptions:
    text: str = ""
    matchCase: bool = False
    wholeWord: bool = False

    # search towards the start of the script
    up: bool = False

    # the element types (line types) to search in, or None for all
    elementTypes: frozenset = None


# a match of FindOptions.text: length characters from line, col, counted
# in the paragraph's text, so it can run on into the paragraph's next
# lines (see advance)
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


# the position n characters on from line, col, counted in the paragraph's
# text, as (line, col). it stops at the end of the paragraph. one past a
# match is advance(sp, m.line, m.col, m.length), and its last character
# is at advance(sp, m.line, m.col, m.length - 1).
def advance(sp, line, col, n):
    p = _Para(sp, line)

    return p.pos(p.offset(line, col) + n)


# a paragraph's text as one string, and the mapping between offsets into
# it and (line, col) positions
class _Para:
    def __init__(self, sp, line):
        self.lines = sp.lines
        self.first = sp.getParaFirstIndexFromLine(line)
        self.last = sp.getParaLastIndexFromLine(line)

        # the offset of each line's text
        self.starts = []

        parts = []
        offset = 0

        for i in range(self.first, self.last + 1):
            self.starts.append(offset)
            offset += self._len(i)

            parts.append(self.lines[i].text)
            if i != self.last:
                parts.append(config.lb2str(self.lines[i].lb))

        self.text = "".join(parts)

    # the length of line i's text plus its line break
    def _len(self, i):
        ln = self.lines[i]

        return len(ln.text) + len(config.lb2str(ln.lb))

    # the offset of line, col. columns past the end of the line count up
    # to the start of the next line.
    def offset(self, line, col):
        return self.starts[line - self.first] + min(col, self._len(line))

    # the position of an offset, as rewrapPara puts the cursor: one at an
    # LB_SPACE break (on the implied space) stays at the end of that line,
    # while one at an LB_NONE break goes to the start of the next line
    def pos(self, offset):
        for i in range(self.first, self.last):
            if offset < self._len(i):
                return (i, min(offset, len(self.lines[i].text)))

            offset -= self._len(i)

        return (self.last, min(offset, len(self.lines[self.last].text)))


# return the first match from line, col on, or going up, the last one
# that ends at or before it, as a Match, or None. doesn't wrap around.
def findNext(sp, line, col, opts):
    value = opts.text
    if not value:
        return None

    if not opts.matchCase:
        value = textutil.upper(value)

    ls = sp.lines

    if not (0 <= line < len(ls)):
        return None

    p = _Para(sp, line)
    offset = p.offset(line, col)

    while True:
        # all of a paragraph's lines are of the same type
        if (opts.elementTypes is None) or (ls[p.first].lt in opts.elementTypes):
            text = p.text
            if not opts.matchCase:
                text = textutil.upper(text)

            res = _findInText(text, value, offset, opts)
            if res != -1:
                return Match(*p.pos(res), len(value))

        if opts.up:
            if p.first == 0:
                return None

            p = _Para(sp, p.first - 1)
            offset = len(p.text)
        else:
            if p.last == (len(ls) - 1):
                return None

            p = _Para(sp, p.last + 1)
            offset = 0


# the offset of the first match in text starting at or after offset, or
# going up, the last one ending at or before it, or -1
def _findInText(text, value, offset, opts):
    n = len(value)

    if opts.up:
        res = text.rfind(value, 0, offset)
    else:
        res = text.find(value, offset)

    while (res != -1) and opts.wholeWord and not _isWholeWord(text, res, n):
        if opts.up:
            res = text.rfind(value, 0, res + n - 1)
        else:
            res = text.find(value, res + 1)

    return res


# the neighboring characters are sliced rather than indexed, so that past
# the ends of the paragraph they're "", which isWordBoundary counts as a
# boundary
def _isWholeWord(text, offset, n):
    return textutil.isWordBoundary(
        text[offset - 1 : offset]
    ) and textutil.isWordBoundary(text[offset + n : offset + n + 1])


class SearchEditMixin:
    # replace length characters from line, col with text, as one undo
    # step (or none, if saveUndo is False), and rewrap the paragraph. the
    # characters are counted in the paragraph's text, as in a Match, so
    # they can run on into its next lines. the cursor is left just past
    # the new text, or at its start if cursorAtStart is True, wherever the
    # rewrapping puts it.
    def replaceRange(
        self, line, col, length, text, cursorAtStart=False, saveUndo=True
    ):
        sp = self.sp
        ls = sp.lines
        text = textutil.toInputStr(text)

        if saveUndo:
            u = undo.SinglePara(self, undo.CMD_MISC, line)

        endLine, endCol = advance(sp, line, col, length)

        if endLine == line:
            ls[line].replaceText(col, endCol - col, text)
        else:
            # the new text goes on the first line, and what's left of the
            # last one follows it, with the lines in between emptied. the
            # line breaks from the first line to the last become LB_NONE,
            # so that the spaces they stood for, which were replaced too,
            # don't come back when rewrapPara joins the lines.
            first = ls[line]
            first.replaceText(col, len(first.text) - col, text)

            for i in range(line + 1, endLine):
                ls[i].deleteText(0, len(ls[i].text))

            ls[endLine].deleteText(0, endCol)

            for i in range(line, endLine):
                ls[i].lb = LB_NONE

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
