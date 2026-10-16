# the scene outline (the outline panel's data), scene colors, and moving
# whole scenes around.

import trelby.undo as undo
import trelby.util as util
from trelby.screenplay.constants import (
    ACTBREAK,
    ACTION,
    NOTE,
    SCENE,
)
from trelby.screenplay.datatypes import OutlineItem


class OutlineMixin:
    # return the first line of every scene heading and act break element,
    # in script order.
    def getOutlineStarts(self):
        ls = self.lines

        return [
            i
            for i in range(len(ls))
            if (ls[i].lt in (SCENE, ACTBREAK)) and self.isFirstLineOfElem(i)
        ]

    # return the outline color of the scene heading or act break element
    # starting at line i, or None if it has none or line i isn't the first
    # line of such an element.
    def getSceneColor(self, i):
        ln = self.lines[i]

        if ln.color and (ln.lt in (SCENE, ACTBREAK)) and self.isFirstLineOfElem(i):
            return ln.color

        return None

    # return the script's outline as a list of OutlineItems, one for each
    # scene and act break, in script order. anything before the first
    # scene / act break is not included. page numbers are only accurate
    # if pagination is up to date.
    def getOutline(self):
        ls = self.lines
        starts = self.getOutlineStarts()
        ret = []
        sceneNrs = dict(self.getSceneLabels())

        for idx, start in enumerate(starts):
            if idx + 1 < len(starts):
                end = starts[idx + 1] - 1
            else:
                end = len(ls) - 1

            lt = ls[start].lt
            heading = self.getElemText(start)

            if self.cfg.getType(lt).screen.isCaps:
                heading = util.upper(heading)

            sceneNr = sceneNrs.get(start, "")

            note = None
            action = None

            i = start + 1

            while i <= end:
                if self.isFirstLineOfElem(i):
                    if (ls[i].lt == NOTE) and (note is None):
                        note = self.getElemText(i)
                        break
                    elif (ls[i].lt == ACTION) and (action is None):
                        action = self.getElemText(i)

                i += 1

            summary = note if note is not None else (action or "")

            ret.append(
                OutlineItem(
                    lt,
                    sceneNr,
                    start,
                    end,
                    heading,
                    summary,
                    self.line2pageLabel(start),
                    self.getSceneColor(start),
                )
            )

        return ret

    # return the index in starts (as returned by getOutlineStarts) of the
    # scene / act break containing the given line, or -1 if the line is
    # before the first one.
    def getOutlineIndex(self, starts, line):
        idx = -1

        for i, start in enumerate(starts):
            if start <= line:
                idx = i
            else:
                break

        return idx


# the Editor's side: scene colors and moving scenes, as undoable edits
class OutlineEditMixin:
    # set the outline color of the scene (or act break) containing the
    # given line to color ("rrggbb"), or remove it if color is None.
    # returns False if the line isn't in a scene or the scene already has
    # that color.
    def setSceneColor(self, line, color):
        starts = self.sp.getOutlineStarts()
        idx = self.sp.getOutlineIndex(starts, line)

        if idx == -1:
            return False

        start = starts[idx]

        if color is not None:
            color = color.lower()

        if self.sp.getSceneColor(start) == color:
            return False

        u = undo.SinglePara(self, undo.CMD_MISC, start)

        self.sp.lines[start].color = color
        self.sp.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)

        return True

    # move the scene (or act break) containing the given line one step up
    # (direction = -1) or down (direction = 1) in the script, swapping it
    # with its neighbor. see moveSceneTo.
    def moveScene(self, line, direction):
        idx = self.sp.getOutlineIndex(self.sp.getOutlineStarts(), line)

        if idx == -1:
            return False

        return self.moveSceneTo(line, idx + direction)

    # move the scene (or act break) containing the given line so that it
    # becomes item number newIndex (0-based) in the outline, shifting the
    # ones in between by one. material before the first scene / act break
    # is never moved, and nothing can be moved above it. on success, the
    # cursor is placed at the start of the moved scene and True is
    # returned.
    def moveSceneTo(self, line, newIndex):
        starts = self.sp.getOutlineStarts()
        idx = self.sp.getOutlineIndex(starts, line)

        if (idx == -1) or (newIndex == idx):
            return False

        if (newIndex < 0) or (newIndex >= len(starts)):
            return False

        self.clearAutoComp()

        bounds = starts + [len(self.sp.lines)]
        blocks = [self.sp.lines[bounds[i] : bounds[i + 1]] for i in range(len(starts))]

        u = undo.AnyDifference(self)

        # moving a scene is like cutting and pasting it: the pages it was
        # locked to stay where they were, starting from whatever followed
        # the scene.
        if idx + 1 < len(blocks):
            self.sp.movePageLocksForward(starts[idx], bounds[idx + 1] - 1)
        else:
            for ln in blocks[idx]:
                ln.pageLock = None

        blocks.insert(newIndex, blocks.pop(idx))

        newLines = []

        for i, block in enumerate(blocks):
            if i == newIndex:
                self.line = starts[0] + len(newLines)

            newLines.extend(block)

        self.sp.lines[starts[0] :] = newLines
        self.column = 0

        self.clearMark()
        self.sp.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)

        return True
