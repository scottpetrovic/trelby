# centered action elements.

import trelby.undo as undo
from trelby.screenplay.constants import (
    ACTION,
)


class CenteringMixin:
    # return how many characters (possibly a fraction of one) line i is
    # indented by in addition to its type's indent: for a line of a
    # centered action, what centers it within the action width, otherwise
    # 0.
    def getCenterOffset(self, i):
        if not self.isCentered(i):
            return 0

        width = self.cfg.getType(ACTION).width
        cols = len(self.lines[i].text) * self.cfg.getCharWidth()

        return max(0, width - cols) / 2.0

    # return True if line i has the centered flag set where it means
    # something, i.e. on the first line of an action element.
    def hasCenteredFlag(self, i):
        ln = self.lines[i]

        return ln.centered and (ln.lt == ACTION) and self.isFirstLineOfElem(i)

    # return True if line i is in a centered action element
    def isCentered(self, i):
        if self.lines[i].lt != ACTION:
            return False

        return self.hasCenteredFlag(self.getElemFirstIndexFromLine(i))

    # return the first lines of the action elements in the selection, or
    # with nothing selected, of the element at the cursor if it's one
    def getActionsForCentering(self):
        marked = self.getMarkedLines()
        first, last = marked if marked else (self.line, self.line)

        ret = []
        i = self.getElemFirstIndexFromLine(first)

        while i <= last:
            if self.lines[i].lt == ACTION:
                ret.append(i)

            i = self.getElemLastIndexFromLine(i) + 1

        return ret

    # return None if centering can't be toggled at the cursor (no action
    # element there or in the selection), otherwise whether all of those
    # actions are centered
    def getCenteredState(self):
        starts = self.getActionsForCentering()

        if not starts:
            return None

        return all(self.lines[i].centered for i in starts)

    # center the action element at the cursor, or the ones in the
    # selection, or if they all are already, stop centering them. returns
    # False if there's no action element there.
    def toggleCentered(self):
        starts = self.getActionsForCentering()

        if not starts:
            return False

        center = not self.getCenteredState()

        u = undo.AnyDifference(self)

        for i in starts:
            self.lines[i].centered = center

        self.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)

        return True
