# recording writing sessions (see writinglog.py) as a script is edited.
# each open script has a Tracker, which MyCtrl tells about the script after
# every change it shows (update), and about a new script in its tab
# (watch). the frame's timer ends sessions that have gone quiet (tick).
#
# an edit is anything that marks the script changed (sp.changeCount). the
# first one starts a session, measured from the words and pages the script
# had when the last session ended, or when it was opened, made or
# imported, so neither opening a script nor importing one counts as
# writing. edits made for the writer by something else, like an AI
# assistant over MCP, are left out (exclude).

import time

import trelby.writinglog as writinglog

# a gap between edits longer than this many seconds isn't counted as time
# spent writing
IDLE = 3 * 60

# and one longer than this ends the session, the next edit starting a new
# one
SESSION_GAP = 30 * 60


# the script's (words, pages)
def counts(sp):
    return (sp.getWordCount(), sp.getPageLength())


class Tracker:
    # log is the writinglog.WritingLog the sessions go in, and clock what
    # gives the time (seconds since the epoch)
    def __init__(self, log, clock=time.time):
        self.log = log
        self.clock = clock

        # the Screenplay watched, its sp.changeCount when last looked at,
        # and its (words, pages) then
        self.sp = None
        self.lastChange = None
        self.lastCounts = (0, 0.0)

        # the (words, pages) the current session is measured from
        self.base = (0, 0.0)

        # the writinglog.Session going on, or None, and the time of its
        # last edit
        self.session = None
        self.lastEdit = 0

    # start watching sp, a new script in the tab, ending the session in the
    # one before
    def watch(self, sp):
        self.end()

        self.sp = sp
        self.lastChange = sp.changeCount
        self.lastCounts = counts(sp)
        self.base = self.lastCounts

    # the script sp may have changed: record it in the session, starting
    # one if there's none. info() returns (path, title): the script's file
    # (None if it has none) and its name, asked only when it has changed.
    def update(self, sp, info):
        if sp is not self.sp:
            self.watch(sp)

            return

        if sp.changeCount == self.lastChange:
            return

        now = self.clock()
        self.lastChange = sp.changeCount

        if self.session and (now - self.lastEdit > SESSION_GAP):
            self.end()

        if self.session:
            gap = now - self.lastEdit

            if gap <= IDLE:
                self.session.active += gap
        else:
            self.session = writinglog.Session(now)

        self.lastCounts = counts(sp)
        self.lastEdit = now

        s = self.session
        s.end = now
        s.path, s.title = info()
        s.words = self.lastCounts[0] - self.base[0]
        s.pages = self.lastCounts[1] - self.base[1]

        self.log.put(s)

    # the changes to sp since it was last looked at weren't written by the
    # writer: leave them out of the session
    def exclude(self, sp):
        if sp is not self.sp:
            self.watch(sp)

            return

        now = counts(sp)
        self.base = tuple(b + n - c for b, n, c in zip(self.base, now, self.lastCounts))
        self.lastCounts = now
        self.lastChange = sp.changeCount

    # end the session if it's gone quiet. called now and then.
    def tick(self):
        if self.session and (self.clock() - self.lastEdit > SESSION_GAP):
            self.end()

    # end the session, if one's going on. the next starts from where it
    # left off.
    def end(self):
        if self.session:
            self.session = None
            self.base = self.lastCounts
