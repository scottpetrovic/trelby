# the scene outline (the outline panel's data), scene colors and
# synopses, and adding
# and moving whole scenes around.

import trelby.textutil as textutil
import trelby.undo as undo
from trelby.screenplay.constants import (
    ACTBREAK,
    ACTION,
    LB_LAST,
    SCENE,
)
from trelby.screenplay.datatypes import OutlineItem
from trelby.screenplay.line import Line

# how much of a scene's action its outline summary has, in characters,
# at least
SUMMARY_LENGTH = 200


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

    # return the synopsis of the scene heading element starting at line i,
    # or None if it has none or line i isn't the first line of a scene
    # heading
    def getSynopsis(self, i):
        ln = self.lines[i]

        if ln.synopsis and (ln.lt == SCENE) and self.isFirstLineOfElem(i):
            return ln.synopsis

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
                heading = textutil.upper(heading)

            sceneNr = sceneNrs.get(start, "")

            summary = self.getSceneSummary(start, end)

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
                    self.getSynopsis(start),
                )
            )

        return ret

    # return the start of the action in lines start - end, a scene, as one
    # string: its action paragraphs joined until there's at least
    # SUMMARY_LENGTH characters, which is more than the outline shows.
    # notes aren't used, they have their own sidebar.
    def getSceneSummary(self, start, end):
        ls = self.lines
        parts = []
        length = 0

        for i in range(start, end + 1):
            if length >= SUMMARY_LENGTH:
                break

            if (ls[i].lt == ACTION) and self.isFirstLineOfElem(i):
                text = " ".join(self.getElemText(i).split())

                if text:
                    parts.append(text)
                    length += len(text) + 1

        return " ".join(parts)

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

    # set the synopsis of the scene whose heading starts at the given line
    # to text, or remove it if text is empty or None. returns False if the
    # line doesn't start a scene heading or the synopsis is unchanged.
    def setSynopsis(self, line, text):
        sp = self.sp

        if not ((sp.lines[line].lt == SCENE) and sp.isFirstLineOfElem(line)):
            return False

        text = textutil.fixNL(text or "").strip() or None

        if sp.getSynopsis(line) == text:
            return False

        u = undo.SinglePara(self, undo.CMD_MISC, line)

        sp.lines[line].synopsis = text
        sp.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)

        return True

    # insert the given Lines, which must start with a scene heading or act
    # break, after the scene (or act break) containing the given line, or
    # before the first one if the line is before it. a script with no text
    # or notes is replaced instead. the cursor is placed at the start of
    # the first new line.
    def insertScenes(self, line, lines):
        sp = self.sp
        self.clearAutoComp()
        self.clearMark()

        if sp.isEmpty() and not sp.getAllNotes():
            at, end = 0, len(sp.lines)

            # adding an empty scene to a script that's just one
            if (len(lines) == end) and not any(
                a != b for a, b in zip(lines, sp.lines)
            ):
                self.gotoPos(0, 0)

                return
        else:
            starts = sp.getOutlineStarts()
            idx = sp.getOutlineIndex(starts, line)

            if idx + 1 < len(starts):
                at = starts[idx + 1]
            else:
                at = len(sp.lines)

            end = at

        u = undo.AnyDifference(self)

        sp.lines[at:end] = lines
        self.line = at
        self.column = 0

        # each new line is a paragraph of its own
        sp.reformatRange(at, at + len(lines) - 1, self)
        sp.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)

    # insert an empty scene heading, see insertScenes
    def addScene(self, line):
        self.insertScenes(line, [Line(LB_LAST, SCENE)])

    # move the scene (or act break) containing the given line one step up
    # (direction = -1) or down (direction = 1) in the script, swapping it
    # with its neighbor. see moveSceneTo.
    def moveScene(self, line, direction):
        idx = self.sp.getOutlineIndex(self.sp.getOutlineStarts(), line)

        if idx == -1:
            return False

        return self.moveSceneTo(line, idx + direction)

    # move the scene (or act break) containing the given line, and the
    # count - 1 items after it (a folded act in the outline), so that it
    # becomes item number newIndex (0-based) in the outline, shifting the
    # ones in between. material before the first scene / act break is
    # never moved, and nothing can be moved above it. on success, the
    # cursor is placed at the start of the moved scene and True is
    # returned.
    def moveSceneTo(self, line, newIndex, count=1):
        starts = self.sp.getOutlineStarts()
        idx = self.sp.getOutlineIndex(starts, line)

        if (idx == -1) or (newIndex == idx) or (count < 1):
            return False

        if (newIndex < 0) or (newIndex + count > len(starts)):
            return False

        if idx + count > len(starts):
            return False

        self.clearAutoComp()

        bounds = starts + [len(self.sp.lines)]
        blocks = [self.sp.lines[bounds[i] : bounds[i + 1]] for i in range(len(starts))]

        u = undo.AnyDifference(self)

        # moving a scene is like cutting and pasting it: the pages it was
        # locked to stay where they were, starting from whatever followed
        # the scene.
        end = idx + count

        if end < len(blocks):
            self.sp.movePageLocksForward(starts[idx], bounds[end] - 1)
        else:
            for block in blocks[idx:]:
                for ln in block:
                    ln.pageLock = None

        moved = [ln for block in blocks[idx:end] for ln in block]
        del blocks[idx:end]
        blocks.insert(newIndex, moved)

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
