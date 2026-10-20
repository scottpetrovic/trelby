# running a writing sprint (see sprint.py) in the app: Tools / Writing
# sprint, F7, the status bar's goal field, or the Home screen start and
# stop one, and Shift+F7 pauses it. while it runs, the status bar counts
# down in place of today's writing, and when its time is up (or its word
# target is reached) it plays a sound, if that's on, and says how it went.
# every sprint, finished or stopped, goes in the writing log.

import time

import wx

import trelby.misc as misc
import trelby.sprint as sprint
import trelby.ui.gutil as gutil


# the sound a sprint ends with
def chime():
    if misc.isWindows:
        try:
            import winsound

            winsound.MessageBeep(winsound.MB_ICONASTERISK)

            return
        except (ImportError, RuntimeError):
            pass

    wx.Bell()


def minutesText(seconds):
    if seconds < 60:
        if int(seconds) == 1:
            return _("1 second")

        return _("%d seconds") % int(seconds)

    minutes = int(round(seconds / 60))

    if minutes == 1:
        return _("1 minute")

    return _("%d minutes") % minutes


def wordsText(words):
    if words == 1:
        return _("1 word")

    return _("%s words") % "{:,}".format(words)


# what the summary says about the Sprint sp, ending at time now. completed
# is whether it ran its course.
def summaryText(sp, now, completed):
    elapsed = sp.elapsed(now)
    words = wordsText(sp.words)
    pace = _("%.1f words a minute") % sp.pace(now)

    if not completed:
        return _("Sprint stopped after {}: {} ({}).").format(
            minutesText(elapsed), words, pace
        )

    if sp.reachedTarget():
        return _("You reached your target of {} in {} ({}).").format(
            wordsText(sp.target), minutesText(elapsed), pace
        )

    return _("Time's up! You wrote {} in {} ({}).").format(
        words, minutesText(elapsed), pace
    )


# frame is the main window, told about every change with
# frame.sprintChanged(), and the parent of the summary. gd is the
# GlobalData, for the settings and the writing log. clock gives the time
# (seconds since the epoch).
class SprintTimer:
    def __init__(self, frame, gd, clock=time.time):
        self.frame = frame
        self.gd = gd
        self.clock = clock

        # the sprint.Sprint going on, or None
        self.sprint = None

        self.timer = wx.Timer()
        self.timer.Bind(wx.EVT_TIMER, self.OnTimer)

    def isActive(self):
        return self.sprint is not None

    def isPaused(self):
        return self.isActive() and self.sprint.isPaused()

    # start a sprint, with the lengths in the settings
    def start(self):
        cfgGl = self.gd.cfgGl
        self.sprint = sprint.Sprint(
            cfgGl.sprintMinutes,
            cfgGl.sprintWords,
            self.clock(),
            self.gd.writingLog.totalWords,
        )
        self.timer.Start(1000)
        self.frame.sprintChanged()

    # start a sprint, or stop the one going on
    def toggle(self):
        if self.isActive():
            self.finish(False)
        else:
            self.start()

    def togglePause(self):
        if not self.isActive():
            return

        if self.sprint.isPaused():
            self.sprint.resume(self.clock())
        else:
            self.sprint.pause(self.clock())

        self.frame.sprintChanged()

    def OnTimer(self, event=None):
        if not self.isActive():
            return

        self.sprint.update(self.gd.writingLog.totalWords)

        if self.sprint.isOver(self.clock()):
            self.finish(True)
        else:
            self.frame.sprintChanged()

    # end the sprint, put it in the writing log, and say how it went.
    # completed is whether it ran its course. without 'summary', for
    # closing the app, nothing is said.
    def finish(self, completed, summary=True):
        sp = self.sprint
        now = self.clock()

        self.timer.Stop()
        sp.update(self.gd.writingLog.totalWords)
        self.sprint = None

        self.gd.writingLog.addSprint(sp.record(now, completed))
        self.gd.saveWritingLog()
        self.frame.sprintChanged()

        if not summary:
            return

        if completed and self.gd.cfgGl.sprintSound:
            chime()

        self.showSummary(summaryText(sp, now, completed))

    def showSummary(self, text):
        gutil.messageBox(text, _("Writing sprint"), parent=self.frame)

    # stop the sprint, if one's going on, without saying anything, as the
    # app closes
    def close(self):
        if self.isActive():
            self.finish(False, summary=False)

    # the sprint's state for the status bar: the time left and the words
    # written, out of its target if it has one
    def statusText(self):
        sp = self.sprint
        left = sprint.clockText(sp.remaining(self.clock()))

        if sp.target:
            words = _("{} / {} words").format(
                "{:,}".format(sp.words), "{:,}".format(sp.target)
            )
        else:
            words = wordsText(sp.words)

        if sp.isPaused():
            return _("Sprint paused {}  ·  {}").format(left, words)

        return _("Sprint {}  ·  {}").format(left, words)
