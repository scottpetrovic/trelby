# a writing sprint: writing against the clock for a set number of minutes,
# in any scripts, optionally until a word target is reached first. the
# words written in it are how much the writing log's total went up since
# it started (writinglog.WritingLog.totalWords), so they come from the same
# sessions as everything else (see writingsession.py). it can be paused,
# the time paused not counting. ui/sprinttimer.py runs one; when it's over,
# record() is what goes in the writing log.

import trelby.writinglog as writinglog


class Sprint:
    # minutes long, ending early at 'target' words unless that's 0,
    # starting at time 'now' (seconds since the epoch) when the log's total
    # was 'totalWords'
    def __init__(self, minutes, target, now, totalWords):
        self.minutes = minutes
        self.target = target
        self.start = now
        self.startWords = totalWords

        # the words written in it, as of the last update
        self.words = 0

        # when it was paused, if it is, and how long it's been paused for
        # before that
        self.pausedAt = None
        self.pausedFor = 0.0

    def isPaused(self):
        return self.pausedAt is not None

    def pause(self, now):
        if not self.isPaused():
            self.pausedAt = now

    def resume(self, now):
        if self.isPaused():
            self.pausedFor += now - self.pausedAt
            self.pausedAt = None

    # the seconds it's been running, leaving out the time paused
    def elapsed(self, now):
        end = self.pausedAt if self.isPaused() else now

        return max(0.0, end - self.start - self.pausedFor)

    def remaining(self, now):
        return max(0.0, self.minutes * 60 - self.elapsed(now))

    # the log's total is now totalWords. the words written while paused
    # count too: it's the writing that matters, not the clock.
    def update(self, totalWords):
        self.words = totalWords - self.startWords

    def reachedTarget(self):
        return bool(self.target) and (self.words >= self.target)

    # whether it's over: its time is up or its target reached
    def isOver(self, now):
        return (self.remaining(now) <= 0) or self.reachedTarget()

    # words per minute of the time it ran
    def pace(self, now):
        minutes = self.elapsed(now) / 60

        return (self.words / minutes) if minutes >= 1 / 60 else 0.0

    # the writinglog.SprintRecord of it ending at time now. completed is
    # whether it ran its course, rather than being stopped.
    def record(self, now, completed):
        return writinglog.SprintRecord(
            self.start, now, self.minutes, self.target, self.words, completed
        )


# "18:42", the minutes and seconds left, rounded up so that it shows 0:00
# only once the time's up
def clockText(seconds):
    s = int(seconds + 0.999)

    return "%d:%02d" % divmod(s, 60)
