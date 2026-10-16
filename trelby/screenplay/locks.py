# locked pages and scene numbers, which keep their labels (e.g. "15A") as
# the script changes. the label arithmetic is in trelby/pagelock.py.

import trelby.pagelock as pagelock
import trelby.undo as undo
from trelby.screenplay.constants import (
    SCENE,
)


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

    def unlockScenes(self):
        if not self.sp.hasAnySceneLock():
            return

        u = undo.FullCopy(self)

        for ln in self.sp.lines:
            ln.sceneLock = None

        self.sp.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)
