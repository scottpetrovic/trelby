# a script's undo history: a doubly linked list of undo objects (see
# trelby/undo.py), oldest first, trimmed from the front once its estimated
# memory use gets too big.
#
# undo objects refer to absolute line numbers, so they're only valid if
# every change to sp.lines since the oldest one has been recorded here, in
# order. anything that changes the lines without recording it (like
# Screenplay.reformatAll) must clear the history first.


class UndoHistory:
    # history is trimmed when its estimated size reaches this, in bytes
    MAX_MEMORY = 5000000

    def __init__(self):
        self.clear()

    def clear(self):
        # first/last undo objects (undo.Base)
        self.first = None
        self.last = None

        # value of this, depending on the user's last action:
        #  undo: the undo object that was used
        #  redo: the next undo object from the one that was used
        #  anything else: None
        self.current = None

        # estimated amount of memory used by undo objects, in bytes
        self.memoryUsed = 0

    def isEmpty(self):
        return self.first is None

    # return True if we can undo
    def canUndo(self):
        return bool(
            # undo history exists
            self.last
            # and we either:
            and (
                # are not in the middle of undo/redo
                not self.current
                or
                # or are, but can still undo more
                self.current.prev
            )
        )

    # return True if we can redo
    def canRedo(self):
        return bool(self.current)

    def add(self, u):
        if self.current:
            # new edit action while navigating undo history; throw away
            # any undo history after current point

            if self.current.prev:
                # not at beginning of undo history; cut off the rest
                self.current.prev.next = None
                self.last = self.current.prev
            else:
                # beginning of undo history; throw everything away
                self.first = None
                self.last = None

            self.current = None

            # we threw away an unknown number of undo items, so we must go
            # through all of the remaining ones and recalculate how much
            # memory is used
            self.memoryUsed = 0

            tmp = self.first

            while tmp:
                self.memoryUsed += tmp.memoryUsed()
                tmp = tmp.next

        if not self.last:
            # no undo history at all yet
            self.first = u
            self.last = u
        else:
            self.last.next = u
            u.prev = self.last
            self.last = u

        self.memoryUsed += u.memoryUsed()

        # trim undo history until the estimated memory usage is small
        # enough
        while (self.first is not self.last) and (self.memoryUsed >= self.MAX_MEMORY):

            tmp = self.first
            tmp.next.prev = None
            self.first = tmp.next

            # it shouldn't be technically necessary to reset this, but it
            # might make the GC's job easier, and helps detecting bugs if
            # somebody somehow tries to access this later on
            tmp.next = None

            self.memoryUsed -= tmp.memoryUsed()

        self.current = None

    # return the last undo object if a new action can be merged into it
    # instead of getting its own: we're not in the middle of undo / redo,
    # it's of one of the given undo.CMD_* types, and it ended at pos (a
    # Mark), i.e. the user hasn't moved the cursor since. otherwise None.
    # used to make a run of typed or deleted characters one undo step.
    def mergeTarget(self, types, pos):
        u = self.last

        if (
            not self.current
            and u
            and (u.getType() in types)
            and (u.endPos == pos)
        ):
            return u

        return None

    # u, the last undo object, has had another action merged into it: take
    # sp's current state as its end state
    def addMerged(self, u, sp):
        assert u is self.last

        memoryUsedBefore = u.memoryUsed()
        u.setAfter(sp)
        memoryUsedAfter = u.memoryUsed()

        self.memoryUsed += memoryUsedAfter - memoryUsedBefore

    # undo the last action (or the one before the last one undone) on sp.
    # returns False if there was nothing to undo.
    def undo(self, sp):
        if not self.canUndo():
            return False

        # the action to undo
        if self.current:
            u = self.current.prev
        else:
            u = self.last

        u.undo(sp)
        self.current = u

        return True

    # redo the last action undone on sp. returns False if there was
    # nothing to redo.
    def redo(self, sp):
        if not self.canRedo():
            return False

        self.current.redo(sp)
        self.current = self.current.next

        return True
