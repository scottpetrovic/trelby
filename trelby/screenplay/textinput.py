# commands that type or delete text: adding characters (with automatic
# capitalization and type changes), deleting, line breaks, and tab.

import trelby.textfmt as textfmt
import trelby.undo as undo
import trelby.util as util
from trelby.screenplay.constants import (
    CHARACTER,
    DIALOGUE,
    LB_LAST,
    LB_NONE,
    LB_SPACE,
    PAREN,
    SCENE,
)


class TextInputMixin:
    def deleteBackwardCmd(self, cs):
        u = None
        mergeUndo = False
        wrapCnt = 0

        # only merge with the previous item in undo history if:
        #   -we are not in middle of undo/redo
        #   -previous item is "delete backward"
        #   -cursor is exactly where it was left off by the previous item
        last = self.undoHistory.mergeTarget(
            (undo.CMD_DEL_BACKWARD,), self.cursorAsMark()
        )

        if last:
            u = last
            mergeUndo = True

        if self.column != 0:
            if not mergeUndo:
                u = undo.ManyElems(self, undo.CMD_DEL_BACKWARD, self.line, 1, 1)

            self.deleteChar(self.line, self.column - 1)
            self.sp.markChanged()
            cs.doAutoComp = cs.AC_REDO
        else:
            if self.line != 0:
                ln = self.sp.lines[self.line - 1]

                # delete at start of the line of the first line of the
                # element means "join up with previous element", so is a
                # 2->1 change. otherwise we just delete a character from
                # current element so no element count change. joining
                # elements can make speeches part of a dual dialogue or
                # take them out of one, so the speeches around are
                # rewrapped too, and included in the undo.
                if ln.lb == LB_LAST:
                    wrapFirst, wrapLast = self.sp.getSpeechRangeAround(
                        self.line - 1, self.line
                    )
                    wrapCnt = self.sp.elemsDistance(wrapFirst, wrapLast) + 1

                    u = undo.ManyElems(
                        self, undo.CMD_MISC, wrapFirst, wrapCnt, wrapCnt - 1
                    )
                    mergeUndo = False
                else:
                    if not mergeUndo:
                        u = undo.ManyElems(self, undo.CMD_DEL_BACKWARD, self.line, 1, 1)

                # joinLines removes the break, which for LB_SPACE deletes
                # its implied space. an LB_NONE break has no character of
                # its own, so the last one before it is deleted instead.
                if ln.lb == LB_NONE:
                    self.deleteChar(self.line - 1, len(ln.text) - 1, False)

                self.joinLines(self.line - 1)

                self.sp.markChanged()

        self.rewrapElem()

        if wrapCnt:
            self.rewrapElems(wrapFirst, wrapCnt - 1)

        if u:
            if mergeUndo:
                self.undoHistory.addMerged(u, self)
            else:
                u.setAfter(self)
                self.undoHistory.add(u)

    def deleteForwardCmd(self, cs):
        u = None
        mergeUndo = False
        wrapCnt = 0

        # only merge with the previous item in undo history if:
        #   -we are not in middle of undo/redo
        #   -previous item is "delete forward"
        #   -cursor is exactly where it was left off by the previous item
        last = self.undoHistory.mergeTarget(
            (undo.CMD_DEL_FORWARD,), self.cursorAsMark()
        )

        if last:
            u = last
            mergeUndo = True

        if self.column != len(self.sp.lines[self.line].text):
            if not mergeUndo:
                u = undo.ManyElems(self, undo.CMD_DEL_FORWARD, self.line, 1, 1)

            self.deleteChar(self.line, self.column)
            self.sp.markChanged()
            cs.doAutoComp = cs.AC_REDO
        else:
            if self.line != (len(self.sp.lines) - 1):
                ln = self.sp.lines[self.line]

                # delete at end of the line of the last line of the
                # element means "join up with next element", so is a 2->1
                # change. otherwise we just delete a character from
                # current element so no element count change. as in
                # deleteBackwardCmd, the speeches around are rewrapped.
                if ln.lb == LB_LAST:
                    wrapFirst, wrapLast = self.sp.getSpeechRangeAround(
                        self.line, self.line + 1
                    )
                    wrapCnt = self.sp.elemsDistance(wrapFirst, wrapLast) + 1

                    u = undo.ManyElems(
                        self, undo.CMD_MISC, wrapFirst, wrapCnt, wrapCnt - 1
                    )
                    mergeUndo = False
                else:
                    if not mergeUndo:
                        u = undo.ManyElems(self, undo.CMD_DEL_FORWARD, self.line, 1, 1)

                # as in deleteBackwardCmd, an LB_NONE break has no
                # character of its own, so the one after it is deleted
                if ln.lb == LB_NONE:
                    self.deleteChar(self.line + 1, 0, False)

                self.joinLines(self.line)

                self.sp.markChanged()

        self.rewrapElem()

        if wrapCnt:
            self.rewrapElems(wrapFirst, wrapCnt - 1)

        if u:
            if mergeUndo:
                self.undoHistory.addMerged(u, self)
            else:
                u.setAfter(self)
                self.undoHistory.add(u)

    def insertForcedLineBreakCmd(self, cs):
        u = undo.ManyElems(self, undo.CMD_MISC, self.line, 1, 1)

        self.splitLine()

        self.rewrapPara()
        self.rewrapPrevPara()

        u.setAfter(self)
        self.undoHistory.add(u)

    def splitElementCmd(self, cs):
        if self.isAutoCompPartial():
            self.acceptAutoComp(cs)

            return

        # with a selection, splitElement only clears it
        hadMark = bool(self.mark)

        tcfg = self.sp.cfgGl.getType(self.sp.lines[self.line].lt)
        self.splitElement(tcfg.newTypeEnter)

        if not hadMark:
            self.offerAutoComp(cs)

    # either creates a new element or converts the current one to
    # nextTypeTab, depending on circumstances.
    def tabCmd(self, cs):
        if self.mark:
            self.clearMark()

            return

        if self.isAutoCompPartial():
            self.acceptAutoComp(cs)

            return

        tcfg = self.sp.cfgGl.getType(self.sp.lines[self.line].lt)

        if self.tabMakesNew():
            self.splitElement(tcfg.newTypeTab)
        else:
            self.convertTypeTo(tcfg.nextTypeTab, True)

        self.offerAutoComp(cs)

    # switch current element to prevTypeTab.
    def toPrevTypeTabCmd(self, cs):
        if self.mark:
            self.clearMark()

            return

        tcfg = self.sp.cfgGl.getType(self.sp.lines[self.line].lt)
        self.convertTypeTo(tcfg.prevTypeTab, True)
        self.offerAutoComp(cs)

    # returns True if pressing TAB at current position would make a new
    # element, False if it would just change element's type.
    def tabMakesNew(self):
        l = self.sp.lines[self.line]

        if self.isAtEndOfParen():
            return True

        if (l.lb != LB_LAST) or (self.column != len(l.text)):
            return False

        if (len(l.text) == 0) and self.sp.isOnlyLineOfElem(self.line):
            return False

        return True

    # add character cs.char if it's a valid one.
    def addCharCmd(self, cs):
        char = cs.char

        if len(char) != 1:
            return

        kc = ord(char)

        if not util.isValidInputChar(kc):
            return

        isSpace = char == " "

        # only merge with the previous item in undo history if:
        #   -we are not in middle of undo/redo
        #   -previous item is "add character"
        #   -cursor is exactly where it was left off by the previous item
        #
        # in addition, to get word-level undo, not element-level undo, we
        # want to merge all spaces with the word preceding them, but stop
        # merging when a new word begins. this is implemented by the
        # following algorith:
        #
        # last undo   char       merge
        # --------    -------    -----
        # non-space   non-space  Y
        # non-space   space      Y      <- change type of last undo to space
        # space       space      Y
        # space       non-space  N

        if isSpace:
            mergeTypes = (undo.CMD_ADD_CHAR, undo.CMD_ADD_CHAR_SPACE)
        else:
            mergeTypes = (undo.CMD_ADD_CHAR,)

        last = self.undoHistory.mergeTarget(mergeTypes, self.cursorAsMark())

        if last:
            u = last
            mergeUndo = True

            if isSpace:
                u.cmdType = undo.CMD_ADD_CHAR_SPACE
        else:
            mergeUndo = False

            if isSpace:
                u = undo.SinglePara(self, undo.CMD_ADD_CHAR_SPACE, self.line)
            else:
                u = undo.SinglePara(self, undo.CMD_ADD_CHAR, self.line)

        if self.capitalizeNeeded():
            char = util.upper(char)

        ls = self.sp.lines
        s = ls[self.line].text

        # a lone "i" becomes "I" when the character typed after it isn't
        # alphanumeric, and neither is the one before it (or the "i"
        # starts the line, and doesn't continue a word broken there with
        # LB_NONE).
        if self.sp.cfgGl.capitalizeI and (self.column > 0):
            s = ls[self.line].text

            if s[self.column - 1] == "i":
                if not util.isAlnum(char):
                    doIt = False

                    if self.column > 1:
                        if not util.isAlnum(s[self.column - 2]):
                            doIt = True
                    else:
                        if (self.line == 0) or (ls[self.line - 1].lb != LB_NONE):
                            doIt = True

                    if doIt:
                        s = util.replace(s, "I", self.column - 1, 1)

        style, isSet = self.getTypingStyle()
        ln = ls[self.line]
        fmt = ln.getFmt() if (ln.fmt or style) else None

        s = s[: self.column] + char + s[self.column :]

        if fmt is None:
            ln.text = s
        else:
            ln.setText(
                s, fmt[: self.column] + textfmt.char(style) + fmt[self.column :]
            )

        self.column += 1

        # typing "INT." or "EXT." as all of a one-line element makes it a
        # scene heading, and typing "(" into an empty character or
        # dialogue element makes it a parenthetical, with the ")" added
        # after the cursor.
        tmp = s.upper()
        if (tmp == "EXT.") or (tmp == "INT."):
            if self.sp.isOnlyLineOfElem(self.line):
                ls[self.line].lt = SCENE
        elif (
            (tmp == "(")
            and ls[self.line].lt in (DIALOGUE, CHARACTER)
            and self.sp.isOnlyLineOfElem(self.line)
        ):
            ls[self.line].lt = PAREN
            ls[self.line].setText("()")

        self.rewrapPara()
        self.sp.markChanged()

        # keep typing in the style that was set
        if isSet:
            self.typingStyle = (self.line, self.column, style)

        cs.doAutoComp = cs.AC_REDO

        if mergeUndo:
            self.undoHistory.addMerged(u, self)
        else:
            u.setAfter(self)
            self.undoHistory.add(u)

    # returns true if a character, inserted at current position, would
    # need to be capitalized as a start of a sentence.
    def capitalizeNeeded(self):
        if not self.sp.cfgGl.capitalize:
            return False

        ls = self.sp.lines
        line = self.line
        column = self.column

        text = ls[line].text
        if (column < len(text)) and (text[column] != " "):
            return False

        # go backwards at most 4 characters, looking for "!?.", and
        # breaking on anything other than space or ".

        cnt = 1
        while 1:
            column -= 1

            char = None

            if column < 0:
                line -= 1

                if line < 0:
                    return True

                lb = ls[line].lb

                if lb == LB_LAST:
                    return True

                elif lb == LB_SPACE:
                    char = " "
                    column = len(ls[line].text)

                else:
                    text = ls[line].text
                    column = len(text) - 1

                    if column < 0:
                        return True
            else:
                text = ls[line].text

            if not char:
                char = text[column]

            if cnt == 1:
                # must be preceded by a space
                if char != " ":
                    return False
            else:
                if char in (".", "?", "!"):
                    return True
                elif char not in (" ", '"'):
                    return False

            cnt += 1

            if cnt > 4:
                break

        return False
