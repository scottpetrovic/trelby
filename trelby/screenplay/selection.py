# the selection (between the mark and the cursor), and copying and pasting
# it through ClipData.

import sys

import trelby.config as config
import trelby.textfmt as textfmt
import trelby.textutil as textutil
import trelby.undo as undo
import trelby.util as util
from trelby.line import Line
from trelby.screenplay.constants import (
    LB_FORCED,
    LB_LAST,
    LB_NONE,
    SCENE,
)
from trelby.screenplay.datatypes import ClipData, Mark


class SelectionMixin:
    # returns pair (start, end) of marked lines, inclusive. if mark is
    # after the end of the script (text has been deleted since setting
    # it), returns a valid pair (by truncating selection to current
    # end). returns None if no lines marked.
    def getMarkedLines(self):
        if not self.mark:
            return None

        mark = min(len(self.sp.lines) - 1, self.mark.line)

        if self.line < mark:
            return (self.line, mark)
        else:
            return (mark, self.line)

    # return the type of the selected lines, or of the cursor's line if
    # nothing is selected, or None if they're of more than one type
    def getSelectionType(self):
        first, last = self.getMarkedLines() or (self.line, self.line)
        types = {self.sp.lines[i].lt for i in range(first, last + 1)}

        return types.pop() if len(types) == 1 else None

    # returns pair (start, end) (inclusive) of marked columns for the
    # given line (line must be inside the marked lines). 'marked' is the
    # value returned from getMarkedLines. if marked column is invalid
    # (text has been deleted since setting the mark), returns a valid pair
    # by truncating selection as needed. returns None on errors.
    def getMarkedColumns(self, line, marked):
        if not self.mark:
            return None

        # line is not marked at all
        if (line < marked[0]) or (line > marked[1]):
            return None

        ls = self.sp.lines

        # last valid offset for given line's text
        lvo = max(0, len(ls[line].text) - 1)

        # only one line marked
        if (line == marked[0]) and (marked[0] == marked[1]):
            c1 = min(self.mark.column, self.column)
            c2 = max(self.mark.column, self.column)

        # line is between end lines, so totally marked
        elif (line > marked[0]) and (line < marked[1]):
            c1 = 0
            c2 = lvo

        # line is first line marked
        elif line == marked[0]:

            if line == self.line:
                c1 = self.column

            else:
                c1 = self.mark.column

            c2 = lvo

        # line is last line marked
        elif line == marked[1]:

            if line == self.line:
                c2 = self.column

            else:
                c2 = self.mark.column

            c1 = 0

        # should't happen
        else:
            return None

        c1 = util.clamp(c1, 0, lvo)
        c2 = util.clamp(c2, 0, lvo)

        return (c1, c2)

    # checks if a line is marked. 'marked' is the value returned from
    # getMarkedLines.
    def isLineMarked(self, line, marked):
        return (line >= marked[0]) and (line <= marked[1])

    # get selected text as a ClipData object, optionally deleting it from
    # the script. if nothing is selected, returns None.
    def getSelectedAsCD(self, doDelete):
        marked = self.getMarkedLines()

        if not marked:
            return None

        ls = self.sp.lines

        cd = ClipData()

        for i in range(marked[0], marked[1] + 1):
            c1, c2 = self.getMarkedColumns(i, marked)

            ln = ls[i]

            cd.lines.append(
                Line(
                    ln.lb,
                    ln.lt,
                    ln.text[c1 : c2 + 1],
                    dual=self.sp.hasDualFlag(i) and (c1 == 0),
                    color=self.sp.getSceneColor(i) if (c1 == 0) else None,
                    centered=self.sp.hasCenteredFlag(i) and (c1 == 0),
                    fmt=ln.sliceFmt(c1, c2 + 1),
                    sceneLock=self.sp.getSceneLock(i) if (c1 == 0) else None,
                )
            )

        # the selection can end mid-element, but paste needs every
        # paragraph in the clip to end with LB_FORCED or LB_LAST
        cd.lines[-1].lb = LB_LAST

        if not doDelete:
            return cd

        u = undo.AnyDifference(self)

        # range of lines, inclusive, that we need to totally delete
        del1 = sys.maxsize
        del2 = -1

        # delete selected text from the lines
        for i in range(marked[0], marked[1] + 1):
            c1, c2 = self.getMarkedColumns(i, marked)

            ln = ls[i]
            ln.deleteText(c1, c2 + 1)

            if i == marked[0]:
                endCol = c1

            # if we removed all text, mark this line to be deleted
            if len(ln.text) == 0:
                del1 = min(del1, i)
                del2 = max(del2, i)

        # adjust linebreaks
        if marked[0] == marked[1]:

            # user has selected text from a single line only

            ln = ls[marked[0]]

            # if it is a single-line element, we never need to modify
            # its linebreak
            if not self.sp.isOnlyLineOfElem(marked[0]):
                # if we're totally deleting the line and it's the last
                # line of a multi-line element, mark the preceding
                # line as the new last line of the element.

                if not ln.text and self.sp.isLastLineOfElem(marked[0]):
                    ls[marked[0] - 1].lb = LB_LAST

        else:

            # now find the line whose linebreak we need to adjust. if
            # the starting line is not completely removed, it is that,
            # otherwise it is the preceding line, unless we delete the
            # first line of the element, in which case there's nothing
            # to adjust.
            if ls[marked[0]].text:
                ln = ls[marked[0]]
            else:
                if not self.sp.isFirstLineOfElem(marked[0]):
                    ln = ls[marked[0] - 1]
                else:
                    ln = None

            if ln:
                # if the selection ends by removing completely the
                # last line of an element, we need to mark the
                # element's new end, otherwise we must set it to
                # LB_NONE so that the new element is reformatted
                # properly.
                if self.sp.isLastLineOfElem(marked[1]) and not ls[marked[1]].text:
                    ln.lb = LB_LAST
                else:
                    ln.lb = LB_NONE

        # if we're joining two elements we have to change the line
        # types for the latter element (starting from the last marked
        # line, because everything before that will get deleted
        # anyway) to that of the first element.
        self.sp.setLineTypes(marked[1], ls[marked[0]].lt)

        if del2 != -1:
            self.sp.movePageLocksForward(del1, del2)

        del ls[del1 : del2 + 1]

        self.clearMark()

        if len(ls) == 0:
            ls.append(Line(LB_LAST, SCENE))

        self.line = min(marked[0], len(ls) - 1)
        self.column = min(endCol, len(ls[self.line].text))

        self.rewrapElem()
        self.rewrapSpeechesAround(self.line, self.line)
        self.sp.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)

        return cd

    # paste data into script. clines is a list of Line objects.
    def paste(self, clines):
        if len(clines) == 0:
            return

        u = undo.AnyDifference(self)

        # a pasted scene keeps its locked number (so cutting and pasting a
        # scene moves it with its number), unless the script already has
        # a scene with that number (e.g. it was copied, not cut)
        usedLocks = set(self.sp.getSceneLocks().values())

        inLines = []
        i = 0

        # wrap all paragraphs into single lines
        while 1:
            if i >= len(clines):
                break

            ln = clines[i]

            newLine = Line(
                LB_LAST, ln.lt, dual=ln.dual, color=ln.color, centered=ln.centered
            )

            if ln.sceneLock and (ln.sceneLock not in usedLocks):
                newLine.sceneLock = ln.sceneLock
                usedLocks.add(ln.sceneLock)

            # (text, fmt) of the lines in this paragraph, and the
            # separators between them
            parts = []
            seps = []

            while 1:
                ln = clines[i]
                i += 1

                newLine.text += ln.text
                parts.append((ln.text, ln.fmt))

                if ln.lb in (LB_LAST, LB_FORCED):
                    break

                newLine.text += config.lb2str(ln.lb)
                seps.append(config.lb2str(ln.lb))

            newLine.fmt = textfmt.join(parts, seps)

            newLine.lb = ln.lb
            inLines.append(newLine)

        # shouldn't happen, but...
        if len(inLines) == 0:
            return

        ls = self.sp.lines

        # where we need to start wrapping
        wrap1 = self.sp.getParaFirstIndexFromLine(self.line)

        ln = ls[self.line]

        atEnd = self.column == len(ln.text)

        # pasting several lines at the start of a scene heading puts them
        # before it, so its locked number has to move with its text
        movedLock = None

        if (self.column == 0) and (len(inLines) != 1) and not atEnd:
            movedLock = ln.sceneLock
            ln.sceneLock = inLines[0].sceneLock

        if (len(ln.text) == 0) and self.sp.isOnlyLineOfElem(self.line):
            ln.lt = inLines[0].lt
            ln.dual = inLines[0].dual
            ln.color = inLines[0].color
            ln.centered = inLines[0].centered
            ln.sceneLock = inLines[0].sceneLock or ln.sceneLock

        if ln.fmt or inLines[0].fmt:
            fmt = ln.getFmt()
            ln.setText(
                ln.text[: self.column] + inLines[0].text + ln.text[self.column :],
                fmt[: self.column] + inLines[0].getFmt() + fmt[self.column :],
            )
        else:
            ln.text = ln.text[: self.column] + inLines[0].text + ln.text[self.column :]

        self.column += len(inLines[0].text)

        if len(inLines) != 1:

            if not atEnd:
                self.splitLine()
                ls[self.line].sceneLock = movedLock
                ls[self.line - 1].lb = inLines[0].lb
                ls[self.line : self.line] = inLines[1:]
                self.line += len(inLines) - 2

            else:
                origLb = ln.lb
                ln.lb = inLines[0].lb

                # don't join the pasted text to the element after this
                # one
                if origLb == LB_LAST:
                    inLines[-1].lb = LB_LAST

                ls[self.line + 1 : self.line + 1] = inLines[1:]
                self.line += len(inLines) - 1

            self.column = len(ls[self.line].text)

            # the pasted lines can now be part of the element they were
            # pasted into, or the text after the cursor part of a pasted
            # element, so give every element around the paste the type
            # of its first line.
            self.sp.fixElemLineTypes(
                self.sp.getElemFirstIndexFromLine(wrap1),
                self.sp.getElemLastIndexFromLine(min(self.line + 1, len(ls) - 1)),
            )

        # FIXME: copy/paste, when copying elements containing forced
        # linebreaks, converts them to end of element? this seems like a
        # bug...

        # the line after the paste can now start a paragraph, so it's
        # reformatted too
        wrap2 = min(self.line + 1, len(ls) - 1)

        self.reformatRange(wrap1, self.sp.getParaFirstIndexFromLine(wrap2))
        self.rewrapSpeechesAround(wrap1, min(self.line + 1, len(ls) - 1))

        u.setAfter(self)
        self.undoHistory.add(u)

        self.clearMark()
        self.clearAutoComp()
        self.sp.markChanged()

    # set mark at given position
    def setMark(self, line, column):
        self.mark = Mark(line, column)

    # clear mark
    def clearMark(self):
        self.mark = None

    # if doIt is True and mark is not yet set, set it at current position.
    def maybeMark(self, doIt):
        if doIt and not self.mark:
            self.setMark(self.line, self.column)

    # select the word at (line, col), as on a double click. clicking on
    # whitespace or punctuation selects the run of it instead. selections
    # are inclusive, so the cursor ends up on the word's last character.
    def selectWordAt(self, line, col):
        self.clearAutoComp()

        s = self.sp.lines[line].text

        if not s:
            self.clearMark()
            self.gotoPos(line, 0)

            return

        col = util.clamp(col, 0, len(s) - 1)

        def charClass(ch):
            if not textutil.isWordBoundary(ch):
                return 0
            elif ch.isspace():
                return 1
            else:
                return 2

        cls = charClass(s[col])
        start = col
        end = col

        while (start > 0) and (charClass(s[start - 1]) == cls):
            start -= 1

        while (end < (len(s) - 1)) and (charClass(s[end + 1]) == cls):
            end += 1

        self.setMark(line, start)
        self.line = line
        self.column = end

    # select the whole element containing line, as on a triple click.
    def selectElementAt(self, line):
        self.clearAutoComp()

        first, last = self.sp.getElemIndexesFromLine(line)

        self.setMark(first, 0)
        self.line = last
        self.column = len(self.sp.lines[last].text)
