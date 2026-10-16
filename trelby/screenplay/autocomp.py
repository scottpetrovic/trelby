# the auto-completion list shown while typing scene headings, character
# names and transitions. the candidates come from trelby/autocompletion.py.

import trelby.autocompletion as autocompletion
import trelby.undo as undo
import trelby.util as util
from trelby.screenplay.constants import (
    CHARACTER,
    SCENE,
)


class AutoCompletionMixin:
    # if auto-completion is active, clear it and return True. otherwise
    # return False.
    def clearAutoComp(self):
        if not self.acItems:
            return False

        self.acItems = None

        return True

    def fillAutoComp(self):
        ls = self.sp.lines

        lt = ls[self.line].lt
        t = self.sp.autoCompletion.getType(lt)

        # completing replaces the line's text, which would mangle an
        # element that has wrapped onto more than one line
        if not (t and t.enabled and self.sp.isOnlyLineOfElem(self.line)):
            self.acItems = None

            return

        text = ls[self.line].text
        self.acItems = self.getMatchingText(text, lt)
        self.acSel = 0

        # if what was typed isn't itself a match, offer it as the first
        # row, so a new name that's the start of an existing one (BOB vs
        # BOBBY) is one Up away. the best match stays selected, so Enter
        # still completes. not after a space, where a word or a part of a
        # scene heading (like "INT. ") has just been finished.
        typed = util.upper(text)
        if (
            self.acItems
            and typed.strip()
            and not typed[-1].isspace()
            and (typed not in self.acItems)
        ):
            self.acItems.insert(0, typed)
            self.acSel = 1

    # page up (dir == -1) or page down (dir == 1) was pressed and we're in
    # auto-comp mode, handle it.
    def pageScrollAutoComp(self, dir):
        if len(self.acItems) > self.acMax:

            if dir < 0:
                self.acSel -= self.acMax

                if self.acSel < 0:
                    self.acSel = len(self.acItems) - 1

            else:
                self.acSel = (self.acSel + self.acMax) % len(self.acItems)

    # if the cursor is in a new, empty character element, show the
    # auto-completion list right away, so the next speaker can be picked
    # without typing anything.
    def offerAutoComp(self, cs):
        ln = self.sp.lines[self.line]

        if (
            (ln.lt == CHARACTER)
            and not ln.text
            and self.sp.isOnlyLineOfElem(self.line)
        ):
            cs.doAutoComp = cs.AC_REDO

    # if the selected auto-completion item is only the start of a scene
    # heading, like "INT. " or "INT. KITCHEN - ".
    def isAutoCompPartial(self):
        return (
            bool(self.acItems)
            and (self.sp.lines[self.line].lt == SCENE)
            and autocompletion.isPartial(self.acItems[self.acSel])
        )

    # put the selected auto-completion item in the current line. if it's
    # only the start of a scene heading, show the list for the next part.
    def acceptAutoComp(self, cs):
        partial = self.isAutoCompPartial()

        u = undo.SinglePara(self, undo.CMD_MISC, self.line)

        self.sp.lines[self.line].setText(self.acItems[self.acSel])
        self.column = len(self.sp.lines[self.line].text)
        self.rewrapPara()
        self.sp.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)

        if partial:
            cs.doAutoComp = cs.AC_REDO

    # get a list of strings (single-line text elements for now) that start
    # with 'text' (not case sensitive) and are of of type 'type', in the
    # order to show them (see AutoCompletion.getMatches), but with an
    # exact match first. also mixes in the type's default items from
    # config. ignores current line.
    def getMatchingText(self, text, lt):
        text = util.upper(text)
        ls = self.sp.lines
        uses = []

        for i in range(len(ls)):
            if (ls[i].lt == lt) and (i != self.line) and self.sp.isOnlyLineOfElem(i):
                upstr = util.upper(ls[i].text).rstrip()

                if upstr:
                    uses.append((i, upstr))

        mlist = self.sp.autoCompletion.getMatches(text, lt, uses, self.line)

        if text in mlist:
            mlist.remove(text)
            mlist.insert(0, text)

        return mlist
