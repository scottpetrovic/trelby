# dual dialogue: two speeches printed side by side. a speech is made the
# right-hand column by setting the dual flag on its character line.

import trelby.undo as undo
from trelby.screenplay.constants import (
    CHARACTER,
    DIALOGUE,
    PAREN,
)


class DualDialogueMixin:
    # return True if line i has the dual flag set where it means
    # something, i.e. on the first line of a character element.
    def hasDualFlag(self, i):
        ln = self.lines[i]

        return ln.dual and (ln.lt == CHARACTER) and self.isFirstLineOfElem(i)

    # if 'line' is in a character's speech (a character element and the
    # parenthetical and dialogue elements following it), return the
    # (first, last) lines of the speech, otherwise None.
    def getSpeechIndexes(self, line):
        ls = self.lines
        speechTypes = (PAREN, DIALOGUE)

        i = line
        while (i >= 0) and (ls[i].lt in speechTypes):
            i -= 1

        if (i < 0) or (ls[i].lt != CHARACTER):
            return None

        first, last = self.getElemIndexesFromLine(i)

        while ((last + 1) < len(ls)) and (ls[last + 1].lt in speechTypes):
            last += 1

        return (first, last)

    # if line r starts the speech printed as the right-hand column of a
    # dual dialogue, return the dual dialogue's lines as (first line of
    # left speech, r, last line of right speech), otherwise None. the
    # left speech is the one right before r, and it can't itself be the
    # right-hand column of another dual dialogue. two-column scripts have
    # none, as their speeches are already in a column.
    def getDualBlockFromRight(self, r):
        if (
            (r == 0)
            or self.isTwoColumn()
            or not self.hasDualFlag(r)
            or (self.lines[r - 1].lt not in (PAREN, DIALOGUE))
        ):
            return None

        left = self.getSpeechIndexes(r - 1)

        if not left or self.hasDualFlag(left[0]):
            return None

        return (left[0], r, self.getSpeechIndexes(r)[1])

    # return the dual dialogue 'line' is part of, in the format of
    # getDualBlockFromRight, or None.
    def getDualBlock(self, line):
        speech = self.getSpeechIndexes(line)

        if not speech:
            return None

        block = self.getDualBlockFromRight(speech[0])

        if not block and ((speech[1] + 1) < len(self.lines)):
            block = self.getDualBlockFromRight(speech[1] + 1)

        return block

    # return which column of a dual dialogue 'line' is in: 1 = left, 2 =
    # right, or 0 if it's not in one.
    def getDualColumn(self, line):
        block = self.getDualBlock(line)

        if not block:
            return 0

        return 1 if line < block[1] else 2

    # return the dual dialogues lying entirely within lines start - end
    # (inclusive) that can be printed as such, as a {line: (column, first,
    # right, last)} dict containing all of their lines (see
    # getDualBlockFromRight). a dual dialogue can't be printed if some of
    # its lines are too long for its columns, which happens when
    # something has made it one without its speeches being rewrapped.
    def getDualLines(self, start, end):
        ls = self.lines
        cfg = self.cfg
        ret = {}

        for r in range(start + 1, end + 1):
            if not ls[r].dual:
                continue

            block = self.getDualBlockFromRight(r)

            if not block or (block[0] < start) or (block[2] > end):
                continue

            first, right, last = block
            fits = True

            for i in range(first, last + 1):
                col = 1 if i < right else 2
                width = cfg.getDualIndentWidth(ls[i].lt, col)[1]

                if len(ls[i].text.rstrip(" ")) > width:
                    fits = False

                    break

            if fits:
                for i in range(first, last + 1):
                    ret[i] = (1 if i < right else 2, first, right, last)

        return ret


# the Editor's side: toggling dual dialogue at the cursor
class DualDialogueEditMixin:
    # return what toggleDualDialogue would do, as (block, makeDual), where
    # block is the dual dialogue in the format of getDualBlockFromRight and
    # makeDual is False if it would be made normal again, or None if
    # toggling isn't possible at the cursor.
    def getDualToggle(self):
        ls = self.sp.lines

        speech = self.sp.getSpeechIndexes(self.line)

        if not speech:
            return None

        block = self.sp.getDualBlock(self.line)

        if block:
            return (block, False)

        for r in (speech[0], speech[1] + 1):
            if (r >= len(ls)) or (ls[r].lt != CHARACTER):
                continue

            # don't take over a speech from another dual dialogue
            if (r != speech[0]) and self.sp.getDualBlock(r):
                continue

            # see whether setting the flag on r would make it the right
            # column of a dual dialogue, without changing anything
            old = ls[r].dual
            ls[r].dual = True
            block = self.sp.getDualBlockFromRight(r)
            ls[r].dual = old

            if block:
                return (block, True)

        return None

    # if the cursor is in a dual dialogue, make its speeches normal again.
    # otherwise make the speech the cursor is in a dual dialogue with the
    # speech right before it, or failing that, the one right after it.
    # returns False if that wasn't possible.
    def toggleDualDialogue(self):
        ls = self.sp.lines

        toggle = self.getDualToggle()

        if not toggle:
            return False

        block, makeDual = toggle
        first, right, last = block
        elemCnt = self.sp.elemsDistance(first, last) + 1

        u = undo.ManyElems(self, undo.CMD_MISC, first, elemCnt, elemCnt)

        ls[right].dual = makeDual

        # rewrap both speeches to their new widths
        self.rewrapElems(first, elemCnt)

        self.clearAutoComp()
        self.sp.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)

        return True
