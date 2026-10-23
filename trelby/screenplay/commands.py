# the command layer the editor calls, by name, through cmd(): cursor
# movement, selection, element type changes and undo / redo. the commands
# that type or delete text are in textinput.

from trelby.screenplay.constants import (
    ACTBREAK,
    ACTION,
    CHARACTER,
    DIALOGUE,
    PAREN,
    SCENE,
    SHOT,
    TRANSITION,
)
from trelby.screenplay.datatypes import CommandState


class CommandsMixin:
    # this must be called after each command (all functions named fooCmd
    # are commands)
    def cmdPost(self, cs):
        # TODO: is this needed?
        self.column = min(self.column, len(self.sp.lines[self.line].text))

        # a typing style only lasts while the cursor stays where it was set
        ts = self.typingStyle

        if ts and ((ts[0] != self.line) or (ts[1] != self.column)):
            self.typingStyle = None

        if cs.doAutoComp == cs.AC_DEL:
            self.clearAutoComp()
        elif cs.doAutoComp == cs.AC_REDO:
            self.fillAutoComp()

    # helper function for calling commands. name is the name of the
    # command, e.g. "moveLeft".
    def cmd(self, name, char=None, count=1):
        for i in range(count):
            cs = CommandState()

            if char:
                cs.char = char

            getattr(self, name + "Cmd")(cs)
            self.cmdPost(cs)

    # call addCharCmd for each character in s. ONLY MEANT TO BE USED IN
    # TEST CODE.
    def cmdChars(self, s):
        for char in s:
            self.cmd("addChar", char=char)

    def moveLeftCmd(self, cs):
        self.maybeMark(cs.mark)

        if self.column > 0:
            self.column -= 1
        else:
            if self.line > 0:
                self.line -= 1
                self.column = len(self.sp.lines[self.line].text)

    def moveRightCmd(self, cs):
        self.maybeMark(cs.mark)

        if self.column != len(self.sp.lines[self.line].text):
            self.column += 1
        else:
            if self.line < (len(self.sp.lines) - 1):
                self.line += 1
                self.column = 0

    def moveUpCmd(self, cs):
        if not self.acItems:
            self.maybeMark(cs.mark)

            # (in a two-column script, up the cursor's column)
            line = self.sp.getLineAbove(self.line, self.column)

            if line is not None:
                self.line = line

        else:
            self.acSel -= 1

            if self.acSel < 0:
                self.acSel = len(self.acItems) - 1

            cs.doAutoComp = cs.AC_KEEP

    def moveDownCmd(self, cs):
        if not self.acItems:
            self.maybeMark(cs.mark)

            line = self.sp.getLineBelow(self.line, self.column)

            if line is not None:
                self.line = line

        else:
            self.acSel = (self.acSel + 1) % len(self.acItems)

            cs.doAutoComp = cs.AC_KEEP

    def moveNextWordCmd(self, cs):
        if not self.acItems:
            self.maybeMark(cs.mark)

            l = self.line
            i = self.column
            t = self.sp.lines[l].text
            firstReadFlag = False
            while True:
                if t == "":  # empty line
                    if l + 1 < len(self.sp.lines):
                        self.line += 1
                    return

                # the cursor can sit after the last character, at column
                # len(t), so test with >= rather than ==
                if i + 1 >= len(t):  # end of line
                    if firstReadFlag == False:  # event started at the end of the line
                        if l + 1 == len(self.sp.lines):
                            return
                        l += 1
                        i = 0
                        t = self.sp.lines[l].text

                    self.column = i
                    self.line = l
                    return

                if (
                    t[i + 1].isspace() and firstReadFlag
                ):  # shifting the cursor to the end of the word
                    self.column = i
                    return
                else:
                    i += 1
                if firstReadFlag == False:
                    firstReadFlag = True

    def movePrevWordCmd(self, cs):
        # returns a reverse list of indexes of words in string s.
        def getWordIndex(s):
            l = []
            if s and not s[0].isspace():
                l.append(0)
            for i in range(1, len(s)):
                if s[i - 1].isspace() and i == len(s):
                    l.append(i)
                if not s[i].isspace() and s[i - 1].isspace():
                    l.append(i)

            l.reverse()
            return l

        if not self.acItems:
            self.maybeMark(cs.mark)

            l = self.line
            i = self.column

            words = getWordIndex(self.sp.lines[l].text)
            while True:
                for word in words:
                    if word < i:
                        self.column = word
                        self.line = l
                        return
                l = l - 1
                if l == -1:
                    self.line = 0
                    self.column = 0
                    return
                words = getWordIndex(self.sp.lines[l].text)
                if words:
                    i = words[0] + 1

    def moveLineEndCmd(self, cs):
        if self.acItems:
            self.acceptAutoComp(cs)
        else:
            self.maybeMark(cs.mark)
            self.column = len(self.sp.lines[self.line].text)

    def moveLineStartCmd(self, cs):
        self.maybeMark(cs.mark)

        self.column = 0

    def moveStartCmd(self, cs):
        self.maybeMark(cs.mark)

        self.line = 0
        self.setTopLine(0)
        self.column = 0

    def moveEndCmd(self, cs):
        self.maybeMark(cs.mark)

        self.line = len(self.sp.lines) - 1
        self.column = len(self.sp.lines[self.line].text)

    def moveSceneUpCmd(self, cs):
        self.maybeMark(cs.mark)

        tmpUp = self.getSceneIndexes()[0]

        if self.line != tmpUp:
            self.line = tmpUp
        else:
            tmpUp -= 1
            if tmpUp >= 0:
                self.line = self.sp.getSceneIndexesFromLine(tmpUp)[0]

        self.column = 0

    def moveSceneDownCmd(self, cs):
        self.maybeMark(cs.mark)

        tmpBottom = self.getSceneIndexes()[1]
        self.line = min(len(self.sp.lines) - 1, tmpBottom + 1)
        self.column = 0

    # aborts stuff, like selection, auto-completion, etc
    def abortCmd(self, cs):
        self.clearMark()

    # select all text of current scene
    def selectSceneCmd(self, cs):
        l1, l2 = self.getSceneIndexes()

        self.setMark(l1, 0)

        self.line = l2
        self.column = len(self.sp.lines[l2].text)

    # select all text of the screenplay. sets mark at beginning and moves
    # cursor to the end.
    def selectAllCmd(self, cs):
        self.setMark(0, 0)

        self.line = len(self.sp.lines) - 1
        self.column = len(self.sp.lines[self.line].text)

    def setMarkCmd(self, cs):
        self.setMark(self.line, self.column)

    def toSceneCmd(self, cs):
        self.convertTypeTo(SCENE, True)

    def toActionCmd(self, cs):
        self.convertTypeTo(ACTION, True)

    def toCharacterCmd(self, cs):
        hadMark = bool(self.mark)
        self.convertTypeTo(CHARACTER, True)

        if not hadMark:
            self.offerAutoComp(cs)

    def toDialogueCmd(self, cs):
        self.convertTypeTo(DIALOGUE, True)

    def toParenCmd(self, cs):
        self.convertTypeTo(PAREN, True)

    def toTransitionCmd(self, cs):
        self.convertTypeTo(TRANSITION, True)

    def toShotCmd(self, cs):
        self.convertTypeTo(SHOT, True)

    def toActBreakCmd(self, cs):
        self.convertTypeTo(ACTBREAK, True)

    def undoCmd(self, cs):
        if self.undoHistory.undo(self):
            self.clearMark()
            self.sp.markChanged()

    def redoCmd(self, cs):
        if self.undoHistory.redo(self):
            self.clearMark()
            self.sp.markChanged()
