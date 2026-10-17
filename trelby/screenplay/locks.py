# locked pages and scene numbers, which keep their labels (e.g. "15A") as
# the script changes. the label arithmetic is in trelby/pagelock.py.
#
# once the scene numbers are locked, a scene that's cut is left as an
# omitted scene: a scene heading reading OMITTED, keeping the scene's
# number, as shooting scripts do. Editor.omitScene does it by hand, and
# deleting a locked scene's heading with a selection (or over MCP) does it
# by itself (omitDeletedScenes, called by undo.AnyDifference). pasting
# the scene back takes its number back from the omitted scene, which goes
# away.

import trelby.screenplay.pagelock as pagelock
import trelby.undo as undo
from trelby.screenplay.constants import (
    ACTBREAK,
    LB_LAST,
    SCENE,
)
from trelby.screenplay.line import Line

# the text of an omitted scene's heading
OMITTED = "OMITTED"


# return the labels of the locked scene headings in lines, a run of lines
# (e.g. ones from before an edit), that aren't omitted scenes
def _sceneLockLabels(lines):
    ret = set()

    for i, ln in enumerate(lines):
        if (
            ln.sceneLock
            and (ln.lt == SCENE)
            and ((i == 0) or (lines[i - 1].lb == LB_LAST))
            and not _isOmittedText(lines, i)
        ):
            ret.add(ln.sceneLock)

    return ret


# whether the element starting at lines[i] reads OMITTED
def _isOmittedText(lines, i):
    return (lines[i].lb == LB_LAST) and (lines[i].text.strip().upper() == OMITTED)


class LocksMixin:
    # return a list of (line, label) tuples for the lines that start a
    # locked page, in script order, skipping any that are out of order.
    def getPageLocks(self):
        locks = [
            (i, ln.pageLock)
            for i, ln in enumerate(self.lines)
            if ln.pageLock and pagelock.isValid(ln.pageLock)
        ]

        return pagelock.orderedLocks(locks)

    def hasPageLocks(self):
        return any(ln.pageLock for ln in self.lines)

    # add a page lock to the given line. if it already has one, the two
    # pages are combined (e.g. "16-17").
    def addPageLock(self, line, label):
        ln = self.lines[line]

        if ln.pageLock:
            ln.pageLock = pagelock.combine(label, ln.pageLock)
        else:
            ln.pageLock = label

    # lines first - last (inclusive) are about to be deleted or moved
    # elsewhere, so move their page locks to the line after them. if there
    # is no line after them, the locks are removed.
    def movePageLocksForward(self, first, last):
        ls = self.lines
        label = None

        for i in range(first, last + 1):
            if ls[i].pageLock:
                if label:
                    label = pagelock.combine(label, ls[i].pageLock)
                else:
                    label = ls[i].pageLock

                ls[i].pageLock = None

        if label and (last + 1) < len(ls):
            self.addPageLock(last + 1, label)

    # return the first line of every scene heading element, in script
    # order.
    def getSceneStarts(self):
        ls = self.lines

        return [
            i
            for i in range(len(ls))
            if (ls[i].lt == SCENE) and self.isFirstLineOfElem(i)
        ]

    # return the locked number of the scene heading element starting at
    # line i, or None if it has none or line i isn't the first line of
    # such an element.
    def getSceneLock(self, i):
        ln = self.lines[i]

        if ln.sceneLock and (ln.lt == SCENE) and self.isFirstLineOfElem(i):
            return ln.sceneLock

        return None

    # return {line: label} for the scene headings that have a locked
    # number. if several have the same one (which editing can't cause),
    # only the first one keeps it.
    def getSceneLocks(self):
        ret = {}
        used = set()

        for i in self.getSceneStarts():
            label = self.lines[i].sceneLock

            if label and pagelock.isValidScene(label) and (label not in used):
                ret[i] = label
                used.add(label)

        return ret

    def hasSceneLocks(self):
        return bool(self.getSceneLocks())

    # return True if any line has a locked scene number, even one that
    # isn't used (see getSceneLocks). unlocking removes these too.
    def hasAnySceneLock(self):
        return any(ln.sceneLock for ln in self.lines)

    # return a list of (line, number) tuples for all scene headings, in
    # script order. see pagelock.sceneLabels for how scenes are numbered
    # once their numbers are locked.
    def getSceneLabels(self):
        starts = self.getSceneStarts()
        locks = self.getSceneLocks()

        labels = pagelock.sceneLabels(
            len(starts),
            {n: locks[i] for n, i in enumerate(starts) if i in locks},
        )

        return list(zip(starts, labels))

    # whether line i is the first line of an omitted scene's heading
    def isOmittedScene(self, i):
        return (
            (self.lines[i].lt == SCENE)
            and self.isFirstLineOfElem(i)
            and _isOmittedText(self.lines, i)
        )

    # return {label: line} for the omitted scenes that have a locked
    # number
    def getOmittedLocks(self):
        return {
            label: i
            for i, label in self.getSceneLocks().items()
            if self.isOmittedScene(i)
        }

    # an edit has replaced the lines oldLines (all of them, as Line
    # copies) with the current ones: if it deleted the heading of a scene
    # with a locked number, add an omitted scene with that number where
    # the scene was, before the next scene heading after the edited lines.
    # cursor (anything with line / column) is kept on the same text. used
    # by undo.AnyDifference, so that it covers every edit that can delete
    # whole scenes.
    def omitDeletedScenes(self, oldLines, cursor=None):
        if not any(ln.sceneLock for ln in oldLines):
            return

        lost = _sceneLockLabels(oldLines) - set(self.getSceneLocks().values())

        if not lost:
            return

        ls = self.lines
        a, b, x, y = undo.mySequenceMatcher(oldLines, ls)

        at = y
        while (at < len(ls)) and not (
            (ls[at].lt in (SCENE, ACTBREAK)) and self.isFirstLineOfElem(at)
        ):
            at = self.getElemLastIndexFromLine(at) + 1

        lost = sorted(lost, key=lambda label: pagelock.labelRange(label)[0])

        ls[at:at] = [Line(LB_LAST, SCENE, OMITTED, sceneLock=label) for label in lost]

        if (cursor is not None) and (cursor.line >= at):
            cursor.line += len(lost)


# the Editor's side: locking and unlocking, as undoable edits
class LocksEditMixin:
    # lock every page to start where it starts now, with its current
    # label, so later edits create A-pages / leave gaps instead of moving
    # text to other pages. if pages are already locked, any A-pages
    # become locked as well.
    def lockPages(self):
        u = undo.FullCopy(self)

        self.sp.paginate()

        for ln in self.sp.lines:
            ln.pageLock = None

        for p in range(1, len(self.sp.pages)):
            self.sp.lines[self.sp.pages[p - 1] + 1].pageLock = self.sp.pageLabels[p]

        self.sp.paginate()
        self.sp.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)

    def unlockPages(self):
        if not self.sp.hasPageLocks():
            return

        u = undo.FullCopy(self)

        for ln in self.sp.lines:
            ln.pageLock = None

        self.sp.paginate()
        self.sp.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)

    # lock the numbers of all scenes, so that adding scenes creates
    # A-scenes (12A, 12B, ...) and deleting them leaves gaps instead of
    # renumbering the scenes after them. if scenes are already locked,
    # any A-scenes become locked as well.
    def lockScenes(self):
        labels = self.sp.getSceneLabels()

        if all(self.sp.getSceneLock(i) == label for i, label in labels):
            return

        u = undo.FullCopy(self)

        for ln in self.sp.lines:
            ln.sceneLock = None

        for i, label in labels:
            self.sp.lines[i].sceneLock = label

        self.sp.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)

    # replace the scene the cursor is in with an omitted scene: a scene
    # heading reading OMITTED, keeping the scene's number and color. does
    # nothing before the first scene, in an act break, or in a scene
    # that's already omitted.
    def omitScene(self):
        sp = self.sp
        first, last = sp.getSceneIndexesFromLine(self.line)

        if (sp.lines[first].lt != SCENE) or (
            sp.isOmittedScene(first) and (first == last)
        ):
            return

        self.clearAutoComp()
        self.clearMark()

        u = undo.AnyDifference(self)

        heading = Line(
            LB_LAST,
            SCENE,
            OMITTED,
            pageLock=sp.lines[first].pageLock,
            color=sp.getSceneColor(first),
            sceneLock=sp.getSceneLock(first),
        )

        if last > first:
            sp.movePageLocksForward(first + 1, last)

        sp.lines[first : last + 1] = [heading]

        self.line = first
        self.column = 0
        sp.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)

    # delete the omitted scenes whose numbers are in labels, a scene
    # pasted back having taken them. an omitted scene's number is never
    # used by another scene's heading reading OMITTED, as paste keeps a
    # number only for one that doesn't. part of an edit, not one itself.
    def removeOmittedScenes(self, labels):
        sp = self.sp

        for i in reversed(sp.getSceneStarts()):
            if (sp.lines[i].sceneLock in labels) and sp.isOmittedScene(i):
                last = sp.getElemLastIndexFromLine(i)

                if len(sp.lines) == last - i + 1:
                    continue

                sp.movePageLocksForward(i, last)
                del sp.lines[i : last + 1]

                if self.line > last:
                    self.line -= last - i + 1
                elif self.line >= i:
                    self.line = min(i, len(sp.lines) - 1)
                    self.column = 0

    def unlockScenes(self):
        if not self.sp.hasAnySceneLock():
            return

        u = undo.FullCopy(self)

        for ln in self.sp.lines:
            ln.sceneLock = None

        self.sp.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)
