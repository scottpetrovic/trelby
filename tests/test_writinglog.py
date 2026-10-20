import datetime
import json
import os
import time

import pytest

import trelby.writinglog as writinglog
from trelby.writinglog import Session, WritingLog

# the writing log (writinglog.py): the sessions in every script, saved as
# JSON, and the day totals, streak and recent activity worked out from them

TODAY = datetime.date(2026, 10, 20)


# seconds since the epoch at hour h on the day 'days' days before TODAY
def at(days, h=10, m=0):
    d = TODAY - datetime.timedelta(days=days)

    return time.mktime((d.year, d.month, d.day, h, m, 0, 0, 0, -1))


def session(days, words, path="/s/Pilot.trelby", title="Pilot", h=10, active=600):
    start = at(days, h)

    return Session(start, start + active, path, title, words, words / 250, active)


def makeLog(*sessions):
    log = WritingLog()

    for s in sessions:
        log.put(s)

    return log


def testScriptName():
    assert writinglog.scriptName(os.path.join("a", "Pilot.trelby")) == "Pilot"
    assert writinglog.scriptName(os.path.join("a", "Pilot.TRELBY")) == "Pilot"
    assert writinglog.scriptName("notes.txt") == "notes.txt"


def testSaveAndLoad():
    a = session(1, 500)
    b = session(0, -40, path=None, title="Untitled Screenplay")
    log = makeLog(a, b)

    assert log.dirty

    loaded = WritingLog.load(log.save())

    assert not loaded.dirty
    assert [s.toDict() for s in loaded.sessions] == [a.toDict(), b.toDict()]
    assert loaded.sessions[1].path is None

    # the path isn't saved for a script that has none
    assert "path" not in json.loads(log.save())["sessions"][1]


@pytest.mark.parametrize(
    "s",
    [
        "",
        "not json",
        "[]",
        '{"sessions": 3}',
        '{"version": 99, "sessions": []}',
        '{"version": "1", "sessions": []}',
    ],
)
def testLoadRefusesWhatIsNotALog(s):
    with pytest.raises(ValueError):
        WritingLog.load(s)


# a bad session is left out, keeping the others
def testLoadSkipsBadSessions():
    good = session(0, 100).toDict()
    s = json.dumps(
        {
            "version": 1,
            "sessions": [
                good,
                {"start": "yesterday"},
                {"words": 3},
                {"start": 5, "words": True},
                {"start": 5, "title": 7},
                "session",
            ],
        }
    )

    log = WritingLog.load(s)

    assert [x.toDict() for x in log.sessions] == [good]


# the sessions are kept in the order they started, and putting one with an
# id that's there replaces it
def testPut():
    a = session(0, 100, h=14)
    b = session(0, 50, h=9)
    log = makeLog(a, b)

    assert log.sessions == [b, a]

    c = Session(a.start, a.end, a.path, a.title, 300, 1.0, 900, id=a.id)
    log.put(c)

    assert log.sessions == [b, c]
    assert log.dayTotal(TODAY).words == 350


def testDayTotal():
    log = makeLog(
        session(1, 700),
        session(0, 300, h=9),
        session(0, 200, path="/s/Other.trelby", title="Other", h=11),
        session(0, -100, h=15),
    )

    t = log.dayTotal(TODAY)

    assert (t.words, t.active) == (400, 1800)
    assert t.pages == pytest.approx(1.6)

    # a day's words are never shown as less than 0
    log.put(session(2, -300))
    assert log.dayTotal(TODAY - datetime.timedelta(days=2)).shownWords() == 0
    assert log.dayTotal(TODAY - datetime.timedelta(days=2)).shownPages() == 0

    # a session belongs to the day it started on, even one going past
    # midnight
    log.put(Session(at(3, 23, 50), at(2, 0, 30), None, "Late", 120))
    assert log.dayTotal(TODAY - datetime.timedelta(days=3)).words == 120


def testDays():
    log = makeLog(session(0, 10), session(2, 20))

    days = log.days(TODAY, 4)

    assert [d.day for d in days] == [TODAY - datetime.timedelta(days=i) for i in (3, 2, 1, 0)]
    assert [d.words for d in days] == [0, 20, 0, 10]


def testStreak():
    assert makeLog().streak(TODAY) == 0

    # today with nothing yet doesn't break the run up to yesterday
    log = makeLog(session(1, 100), session(2, 100), session(4, 100))
    assert log.streak(TODAY) == 2

    log.put(session(0, 50))
    assert log.streak(TODAY) == 3

    # a day whose words came to nothing doesn't count
    log = makeLog(session(0, 100), session(1, 100), session(1, -100, h=12))
    assert log.streak(TODAY) == 1


# the recent activity is per day and script, newest first, a script being
# its path, or for one never saved, its name
def testRecentActivity():
    log = makeLog(
        session(2, 100),
        session(1, 300, path="/s/Other.trelby", title="Other"),
        session(0, 200, h=9),
        session(0, 50, path=None, title="Untitled Screenplay", h=10),
        session(0, 25, h=11),
        # renamed: the latest name is shown
        session(0, 5, title="Pilot v2", h=12),
    )

    act = log.recentActivity(10)

    assert [(a.day, a.title, a.path, a.words) for a in act] == [
        (TODAY, "Pilot v2", "/s/Pilot.trelby", 230),
        (TODAY, "Untitled Screenplay", None, 50),
        (TODAY - datetime.timedelta(days=1), "Other", "/s/Other.trelby", 300),
        (TODAY - datetime.timedelta(days=2), "Pilot", "/s/Pilot.trelby", 100),
    ]

    # cut short, a day's script still gets all its sessions
    act = log.recentActivity(1)

    assert [(a.title, a.words) for a in act] == [("Pilot v2", 230)]


def testLoadFile(tmp_path):
    path = str(tmp_path / "writinglog.json")

    log, err = writinglog.loadFile(path)
    assert (log.sessions, err) == ([], None)

    with open(path, "w", encoding="utf-8") as f:
        f.write(makeLog(session(0, 10)).save())

    log, err = writinglog.loadFile(path)
    assert ([s.words for s in log.sessions], err) == ([10], None)

    # one that can't be read is kept aside, and a new log started
    with open(path, "w", encoding="utf-8") as f:
        f.write("{broken")

    log, err = writinglog.loadFile(path)
    assert (log.sessions, bool(err)) == ([], True)
    assert not os.path.exists(path)

    with open(path + ".bad", encoding="utf-8") as f:
        assert f.read() == "{broken"
