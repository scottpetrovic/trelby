# word wrapping: splitting each paragraph into lines that fit its
# element's width, and rewrapping paragraphs after they're edited.

import trelby.config as config
import trelby.textfmt as textfmt
import trelby.textutil as textutil
from trelby.screenplay.line import Line
from trelby.screenplay.constants import (
    CHARACTER,
    DIALOGUE,
    LB_FORCED,
    LB_LAST,
    LB_NONE,
    LB_SPACE,
    PAREN,
)


# the functions that rewrap paragraphs take an optional 'cursor', any
# object with line and column attributes (usually an Editor), which they
# keep on the same text as it moves.
class WrappingMixin:
    # rewrap the whole script. throws away the meaning of every line
    # number, so an Editor's undo history must be cleared first (see
    # Editor.reformatAll).
    def reformatAll(self, cursor=None):
        # sfdlksjf = util.TimerDev("reformatAll")

        line = 0

        while 1:
            line += self.rewrapPara(line, cursor)
            if line >= len(self.lines):
                break

    # reformat part of the screenplay. par1 is line number of paragraph to
    # start at, par2 the same for the ending one, inclusive.
    def reformatRange(self, par1, par2, cursor=None):
        ls = self.lines

        # rewrapping changes how many lines the paragraphs before par2
        # have, so its index can't tell us when to stop. the Line object
        # is tagged instead; rewrapPara replaces it with new Lines only
        # when rewrapping its own paragraph, after the tag has been seen.
        # par2 must be the first line of a paragraph, or the tag is never
        # found.
        #
        # add special tag to last paragraph we'll reformat
        ls[par2].reformatMarker = 0
        end = False

        line = par1
        while 1:
            if hasattr(ls[line], "reformatMarker"):
                del ls[line].reformatMarker
                end = True

            line += self.rewrapPara(line, cursor)
            if end:
                break

    # wraps a single line into however many lines are needed, according to
    # the given width (in columns), or the type's width if it's None.
    # doesn't modify the input line, returns a list of new lines.
    def wrapLine(self, line, width=None):
        ret = []

        if width is None:
            width = self.cfg.getType(line.lt).width

        isParen = line.lt == PAREN
        charWidth = self.cfg.getCharWidth()

        # text remaining to be wrapped, and its format string (or None)
        text = line.text
        fmt = line.getFmt() if line.fmt else None

        # add a line with text[a:b] and lb, and drop text[:c] from what's
        # left to be wrapped
        def add(lb, a, b, c):
            nonlocal text, fmt

            ret.append(Line(lb, line.lt, text[a:b], fmt=fmt and fmt[a:b]))
            text = text[c:]

            if fmt:
                fmt = fmt[c:]

        while 1:
            # reduce parenthetical width by 1 from second line onwards
            if isParen and ret:
                w = width - 1
            else:
                w = width

            # how many characters fit
            w = max(1, w // charWidth)

            if len(text) <= w:
                add(line.lb, 0, len(text), len(text))
                break
            else:
                i = text.rfind(" ", 0, w + 1)

                # Chinese and Japanese have no spaces between words, and
                # can be broken before or after any of their characters.
                # breaking right after a space would leave it at the end
                # of an LB_NONE line, so that's left to the space handling.
                if (charWidth == 2) and (i < w):
                    k = self.findWideBreak(text, i + 2, w)

                    if k is not None:
                        add(LB_NONE, 0, k, k)

                        continue

                if i == w:

                    # we allow space characters to go over the line
                    # length, for two reasons:
                    #
                    # 1) it is impossible to get the behavior right
                    # otherwise in situations where a line ends in two
                    # spaces and the user inserts a non-space character at
                    # the end of the line. the cursor must be positioned
                    # at the second space character for this to work
                    # right, and the only way to get that is to allow
                    # spaces to go over the normal line length.
                    #
                    # 2) doing this results in no harm, since space
                    # characters print as empty, so they don't overwrite
                    # anything.

                    i += 1
                    while text[i : i + 1] == " ":
                        i += 1

                    if i == len(text):
                        add(line.lb, 0, len(text), len(text))

                        break
                    else:
                        add(LB_SPACE, 0, i - 1, i)

                elif i >= 0:
                    add(LB_SPACE, 0, i, i + 1)

                else:
                    add(LB_NONE, 0, w, w)

        return ret

    # return the largest k in [lo, hi] such that text can be broken
    # between text[k - 1] and text[k] because one of them is a wide
    # character, or None if there's no such place.
    @staticmethod
    def findWideBreak(text, lo, hi):
        for k in range(hi, max(lo, 1) - 1, -1):
            if textutil.isWideChar(text[k - 1]) or textutil.isWideChar(text[k]):
                return k

        return None

    # rewrap paragraph starting at given line. returns the number of lines
    # in the wrapped paragraph.
    def rewrapPara(self, line1, cursor=None):
        ls = self.lines

        line2 = line1

        while ls[line2].lb not in (LB_LAST, LB_FORCED):
            line2 += 1

        # offsets into the paragraph count each line's text plus what its
        # line break stands for (config.lb2str: " " for LB_SPACE, "" for
        # LB_NONE, and one character at the paragraph's end, so that the
        # end of its last line is a valid position), i.e. they're
        # positions in the paragraph's text as one string (s below), which
        # stay valid however it gets rewrapped.
        if (cursor is not None) and (line1 <= cursor.line <= line2):
            # cursor is in this paragraph, save its offset from the
            # beginning of the paragraph
            cursorOffset = 0

            for i in range(line1, line2 + 1):
                if i == cursor.line:
                    cursorOffset += cursor.column

                    break
                else:
                    cursorOffset += len(ls[i].text) + len(config.lb2str(ls[i].lb))
        else:
            cursorOffset = -1

        # page locks in this paragraph, as (offset from the beginning of
        # the paragraph, label) tuples
        locks = []

        s = ""
        for i in range(line1, line2 + 1):
            if i != line1:
                s += config.lb2str(ls[i - 1].lb)

            if ls[i].pageLock:
                locks.append(
                    (len(s) + getattr(ls[i], "pageLockCol", 0), ls[i].pageLock)
                )

            s += ls[i].text

        fmt = textfmt.join(
            [(ls[i].text, ls[i].fmt) for i in range(line1, line2 + 1)],
            [config.lb2str(ls[i].lb) for i in range(line1, line2)],
        )

        tmp = Line(ls[line2].lb, ls[line1].lt, s, fmt=fmt)

        # speeches in a dual dialogue are wrapped to fit their column
        width = None
        if tmp.lt in (CHARACTER, PAREN, DIALOGUE):
            col = self.getDualColumn(line1)

            if col:
                width = self.cfg.getDualIndentWidth(tmp.lt, col)[1]

        wrappedLines = self.wrapLine(tmp, width)

        # the dual flag, color and scene lock stay on the first line of
        # the element
        firstOfElem = self.isFirstLineOfElem(line1)
        wrappedLines[0].dual = ls[line1].dual and firstOfElem
        wrappedLines[0].color = ls[line1].color if firstOfElem else None
        wrappedLines[0].centered = ls[line1].centered and firstOfElem
        wrappedLines[0].sceneLock = ls[line1].sceneLock if firstOfElem else None

        # the notes of all the paragraph's lines go on its first line (see
        # notes.py)
        wrappedLines[0].notes = sum((ls[i].notes for i in range(line1, line2 + 1)), ())

        ls[line1 : line2 + 1] = wrappedLines

        # put the page locks back on the lines that now contain the text
        # they were on
        if locks:
            for offset, label in locks:
                i = line1

                for ln in wrappedLines[:-1]:
                    offset -= len(ln.text) + len(config.lb2str(ln.lb))

                    if offset < 0:
                        break

                    i += 1

                self.addPageLock(i, label)

        # adjust cursor position. an offset at an LB_SPACE break (on the
        # implied space) stays at the end of that line, while one at an
        # LB_NONE break goes to the start of the next line.
        if cursorOffset != -1:
            for i in range(line1, line1 + len(wrappedLines)):
                ln = ls[i]
                llen = len(ln.text) + len(config.lb2str(ln.lb))

                if cursorOffset < llen:
                    cursor.line = i
                    cursor.column = min(cursorOffset, len(ln.text))
                    break
                else:
                    cursorOffset -= llen

        elif (cursor is not None) and (cursor.line >= line1):
            # cursor position is below current paragraph, modify its
            # linenumber appropriately
            cursor.line += len(wrappedLines) - (line2 - line1 + 1)

        return len(wrappedLines)

    # rewrap the elements of lines line1 - line2 and the elements next to
    # them, extended to whole speeches (see getSpeechRangeAround), so that
    # speeches that an edit there has made part of a dual dialogue, or
    # taken out of one, get their new widths. the undo object for the edit
    # must cover those lines too.
    def rewrapSpeechesAround(self, line1, line2, cursor=None):
        first, last = self.getSpeechRangeAround(line1, line2)
        self.rewrapElems(first, self.elemsDistance(first, last) + 1, cursor)

    # rewrap 'count' elements starting from the one starting at 'line'
    def rewrapElems(self, line, count, cursor=None):
        for i in range(count):
            self.rewrapElem(line, cursor)
            line = self.getElemLastIndexFromLine(line) + 1

    # return (first, last) lines of the elements containing lines line1 -
    # line2 and the elements before and after them, extended to whole
    # speeches and the dual dialogues they're in. a speech with the dual
    # flag right after that is included too, since an edit can make it
    # the right-hand column of a dual dialogue.
    def getSpeechRangeAround(self, line1, line2):
        ls = self.lines

        first = self.getElemFirstIndexFromLine(line1)
        if first > 0:
            first = self.getElemFirstIndexFromLine(first - 1)

        last = self.getElemLastIndexFromLine(line2)
        if (last + 1) < len(ls):
            last = self.getElemLastIndexFromLine(last + 1)

        speech = self.getSpeechIndexes(first)
        if speech:
            first = speech[0]

        speech = self.getSpeechIndexes(last)
        if speech:
            last = speech[1]

        block = self.getDualBlock(first)
        if block:
            first = block[0]

        block = self.getDualBlock(last)
        if block:
            last = block[2]

        if ((last + 1) < len(ls)) and self.hasDualFlag(last + 1):
            last = self.getSpeechIndexes(last + 1)[1]

        return (first, last)

    # rewrap element starting at given line.
    def rewrapElem(self, line, cursor=None):
        ls = self.lines

        while 1:
            line += self.rewrapPara(line, cursor)

            if ls[line - 1].lb == LB_LAST:
                break
