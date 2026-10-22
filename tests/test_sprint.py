import pytest
import wx

import tests.u as u
import trelby.config as config
import trelby.sprint as sprint
import trelby.translations as translations
import trelby.writinglog as writinglog

_ = translations.trelby_translations_load()

import trelby.dialogs.configpages.goalspanel as goalspanel  # noqa: E402
import trelby.ui.sprinttimer as sprinttimer  # noqa: E402

# writing sprints: the model (sprint.py), the timer that runs one in the
# app (ui/sprinttimer.py), their records in the writing log, and the
# Settings dialog's Writing Goals page

T0 = 1_800_000_000.0


def testClockText():
    assert sprint.clockText(25 * 60) == "25:00"
    assert sprint.clockText(61.2) == "1:02"
    assert sprint.clockText(0.2) == "0:01"
    assert sprint.clockText(0) == "0:00"


def testTimeAndPausing():
    sp = sprint.Sprint(10, 0, T0, 1000)

    assert sp.remaining(T0) == 600
    assert sp.remaining(T0 + 60) == 540

    sp.pause(T0 + 60)
    assert sp.isPaused()

    # the clock stops while paused, and pausing again changes nothing
    sp.pause(T0 + 100)
    assert sp.remaining(T0 + 300) == 540

    sp.resume(T0 + 300)
    assert not sp.isPaused()
    assert sp.elapsed(T0 + 360) == 120
    assert not sp.isOver(T0 + 359 + 480)
    assert sp.isOver(T0 + 360 + 480)


def testWordsAndTarget():
    sp = sprint.Sprint(10, 50, T0, 1000)

    sp.update(1030)
    assert sp.words == 30
    assert not sp.reachedTarget()
    assert not sp.isOver(T0 + 60)
    assert sp.pace(T0 + 60) == 30

    sp.update(1050)
    assert sp.reachedTarget()
    assert sp.isOver(T0 + 60)

    rec = sp.record(T0 + 120, True)
    assert (rec.start, rec.end, rec.minutes, rec.target, rec.words, rec.completed) == (
        T0,
        T0 + 120,
        10,
        50,
        50,
        True,
    )

    # no target, no ending early
    sp = sprint.Sprint(10, 0, T0, 0)
    sp.update(100000)
    assert not sp.isOver(T0)


# the log's total follows the sessions as they're replaced, which is what
# a sprint counts from
def testLogTotalWords():
    log = writinglog.WritingLog()
    s = writinglog.Session(T0, words=10)
    log.put(s)
    assert log.totalWords == 10

    s.words = 25
    log.put(s)
    assert log.totalWords == 25

    log.put(writinglog.Session(T0 + 10, words=-5))
    assert log.totalWords == 20

    assert writinglog.WritingLog.load(log.save()).totalWords == 20


def testSprintRecordsSaved():
    log = writinglog.WritingLog()
    log.addSprint(writinglog.SprintRecord(T0 + 100, T0 + 700, 10, 0, 300, True))
    log.addSprint(writinglog.SprintRecord(T0, T0 + 60, 25, 500, 20, False))

    assert log.dirty
    assert [sp.words for sp in log.sprints] == [20, 300]

    loaded = writinglog.WritingLog.load(log.save())
    assert [sp.toDict() for sp in loaded.sprints] == [
        sp.toDict() for sp in log.sprints
    ]
    assert loaded.sprintsOn(writinglog.localDay(T0)) == loaded.sprints

    # bad ones are left out, and a log from before sprints has none
    s = log.save().replace('"completed": true', '"completed": "yes"')
    assert [sp.words for sp in writinglog.WritingLog.load(s).sprints] == [20]
    assert writinglog.WritingLog.load('{"sessions": []}').sprints == []


@pytest.fixture(scope="module")
def app(app):
    u.init()

    return app


class Clock:
    def __init__(self):
        self.t = T0

    def __call__(self):
        return self.t


class GD:
    def __init__(self):
        self.cfgGl = config.ConfigGlobal()
        self.cfgGl.sprintSound = False
        self.writingLog = writinglog.WritingLog()
        self.saved = 0

    def saveWritingLog(self):
        self.saved += 1


class Frame:
    def __init__(self):
        self.changes = 0

    def sprintChanged(self):
        self.changes += 1


@pytest.fixture
def timer(app):
    gd = GD()
    clock = Clock()
    t = sprinttimer.SprintTimer(Frame(), gd, clock)
    t.summaries = []
    t.showSummary = t.summaries.append

    yield t, gd, clock

    t.timer.Stop()


# the log's words written so far go up by n, as a session does while
# writing
def write(gd, n):
    s = writinglog.Session(T0, words=n)
    gd.writingLog.put(s)


def testTimerRunsItsCourse(timer):
    t, gd, clock = timer
    gd.cfgGl.sprintMinutes = 10
    write(gd, 500)

    t.start()
    assert t.isActive() and t.timer.IsRunning()
    assert t.statusText() == "Sprint 10:00  ·  0 words"

    write(gd, 120)
    clock.t += 61
    t.OnTimer()
    assert t.statusText() == "Sprint 8:59  ·  120 words"

    clock.t = T0 + 600
    t.OnTimer()

    assert not t.isActive() and not t.timer.IsRunning()
    assert t.summaries == [
        "Time's up! You wrote 120 words in 10 minutes (12.0 words a minute)."
    ]

    [rec] = gd.writingLog.sprints
    assert (rec.words, rec.completed, rec.minutes) == (120, True, 10)
    assert gd.saved == 1
    assert t.frame.changes >= 3


def testTimerTarget(timer):
    t, gd, clock = timer
    gd.cfgGl.sprintWords = 100

    t.start()
    assert t.statusText() == "Sprint 25:00  ·  0 / 100 words"

    clock.t += 300
    write(gd, 100)
    t.OnTimer()

    assert not t.isActive()
    assert t.summaries == [
        "You reached your target of 100 words in 5 minutes (20.0 words a minute)."
    ]


def testTimerPauseAndStop(timer):
    t, gd, clock = timer

    t.start()
    clock.t += 60
    t.togglePause()
    assert t.isPaused()
    assert t.statusText() == "Sprint paused 24:00  ·  0 words"

    clock.t += 600
    t.OnTimer()
    assert t.statusText().startswith("Sprint paused 24:00")

    t.togglePause()
    write(gd, 30)
    clock.t += 120
    t.toggle()

    assert not t.isActive()
    assert t.summaries == [
        "Sprint stopped after 3 minutes: 30 words (10.0 words a minute)."
    ]
    assert gd.writingLog.sprints[0].completed is False


# closing the app stops it without a word
def testTimerClose(timer):
    t, gd, clock = timer

    t.close()
    assert gd.writingLog.sprints == []

    t.start()
    t.close()

    assert not t.isActive()
    assert t.summaries == []
    assert len(gd.writingLog.sprints) == 1


def testGoalsPanel(app):
    frame = wx.Frame(None)
    cfg = config.ConfigGlobal()
    cfg.dailyGoal = 500
    cfg.sprintMinutes = 15

    panel = goalspanel.GoalsPanel(frame, -1, cfg)

    assert panel.dailyEntry.GetValue() == 500
    assert panel.unitChoice.GetSelection() == 0
    assert panel.minutesEntry.GetValue() == 15
    assert panel.soundCb.GetValue()

    panel.dailyEntry.SetValue(3)
    panel.unitChoice.SetSelection(1)
    panel.weeklyEntry.SetValue(15)
    panel.wordsEntry.SetValue(250)
    panel.soundCb.SetValue(False)
    panel.OnMisc()

    assert (cfg.dailyGoal, cfg.dailyGoalPages, cfg.weeklyGoal) == (3, True, 15)
    assert (cfg.sprintMinutes, cfg.sprintWords, cfg.sprintSound) == (15, 250, False)
    assert panel.weeklyUnit.GetLabel() == _("pages")

    # and they're saved
    loaded = config.ConfigGlobal()
    loaded.load(cfg.save())
    assert (loaded.dailyGoal, loaded.dailyGoalPages, loaded.weeklyGoal) == (3, True, 15)
    assert (loaded.sprintMinutes, loaded.sprintWords, loaded.sprintSound) == (
        15,
        250,
        False,
    )

    frame.Destroy()


def testMinutesText():
    assert sprinttimer.minutesText(1) == "1 second"
    assert sprinttimer.minutesText(6.7) == "6 seconds"
    assert sprinttimer.minutesText(60) == "1 minute"
    assert sprinttimer.minutesText(25 * 60 + 10) == "25 minutes"
