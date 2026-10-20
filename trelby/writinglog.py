# the writing log: every writing session in every script, kept in one file
# in the config directory (writinglog.json, see globaldata), so that the
# Home screen can show how much was written each day, and in what, across
# all scripts. writingsession.py records the sessions.
#
# a session is a stretch of editing one script, with no gap longer than
# writingsession.SESSION_GAP between edits: when it started and ended, the
# script's path (None while it has never been saved) and its name, the
# words and pages it added (net: deleting text takes them off again, so
# either can be negative), and how long was spent writing, which leaves out
# gaps between edits longer than writingsession.IDLE.
#
# a session belongs to the day it started on, in local time. a day's words
# and pages are the sum of its sessions', and never shown as less than 0.
#
# it also keeps the writing sprints (see sprint.py): when each started and
# ended, how long it was set for and its word target, the words written in
# it, and whether it ran its course (or reached its target) rather than
# being stopped.
#
# the file is JSON: {"version": 1, "sessions": [{...}, ...], "sprints":
# [{...}, ...]}, each in the order they started.

import datetime
import json
import os
import time
import uuid

VERSION = 1


class Session:
    def __init__(
        self,
        start,
        end=None,
        path=None,
        title="",
        words=0,
        pages=0.0,
        active=0.0,
        id=None,
    ):
        # a unique id, so that a session can be stored while it's still
        # going on and replaced as it goes on (see WritingLog.put)
        self.id = id or uuid.uuid4().hex

        # seconds since the epoch
        self.start = start
        self.end = start if end is None else end

        self.path = path
        self.title = title
        self.words = words
        self.pages = pages

        # seconds spent writing
        self.active = active

    # the key of the script the session was in: its path, or for a script
    # never saved, its name
    def scriptKey(self):
        return ("path", self.path) if self.path else ("title", self.title)

    def day(self):
        return localDay(self.start)

    def toDict(self):
        d = {
            "id": self.id,
            "start": round(self.start, 1),
            "end": round(self.end, 1),
            "title": self.title,
            "words": self.words,
            "pages": round(self.pages, 2),
            "active": round(self.active),
        }

        if self.path:
            d["path"] = self.path

        return d

    # the Session in the dict d, as toDict makes. raises ValueError,
    # TypeError or KeyError if it's not a valid one.
    @staticmethod
    def fromDict(d):
        def num(key, default=None):
            v = d.get(key, default)

            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError("%s is not a number" % key)

            return v

        def text(key):
            v = d.get(key)

            if (v is not None) and not isinstance(v, str):
                raise ValueError("%s is not a string" % key)

            return v

        return Session(
            num("start"),
            num("end", d["start"]),
            text("path") or None,
            text("title") or "",
            int(num("words", 0)),
            float(num("pages", 0.0)),
            float(num("active", 0.0)),
            text("id"),
        )


class SprintRecord:
    def __init__(self, start, end, minutes, target, words, completed, id=None):
        self.id = id or uuid.uuid4().hex
        self.start = start
        self.end = end
        self.minutes = minutes
        self.target = target
        self.words = words
        self.completed = completed

    def day(self):
        return localDay(self.start)

    def toDict(self):
        return {
            "id": self.id,
            "start": round(self.start, 1),
            "end": round(self.end, 1),
            "minutes": self.minutes,
            "target": self.target,
            "words": self.words,
            "completed": self.completed,
        }

    # raises ValueError, TypeError, KeyError or AttributeError if d isn't
    # one
    @staticmethod
    def fromDict(d):
        for key in ("start", "end", "minutes", "target", "words"):
            v = d[key]

            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError("%s is not a number" % key)

        if not isinstance(d["completed"], bool):
            raise ValueError("completed is not a bool")

        id = d.get("id")

        if (id is not None) and not isinstance(id, str):
            raise ValueError("id is not a string")

        return SprintRecord(
            d["start"],
            d["end"],
            int(d["minutes"]),
            int(d["target"]),
            int(d["words"]),
            d["completed"],
            id,
        )


# the name shown for a script file: its file name without the .trelby
def scriptName(path):
    name = os.path.basename(path)
    base, ext = os.path.splitext(name)

    return base if ext.lower() == ".trelby" else name


# the local date of the time t (seconds since the epoch)
def localDay(t):
    return datetime.date.fromtimestamp(t)


# the time (seconds since the epoch) local day 'day' starts at
def dayStart(day):
    return time.mktime((day.year, day.month, day.day, 0, 0, 0, 0, 0, -1))


# what was written in one script on one day, or in all of them (see
# WritingLog.dayTotal)
class Total:
    def __init__(self, day, title="", path=None):
        self.day = day
        self.title = title
        self.path = path
        self.words = 0
        self.pages = 0.0
        self.active = 0.0

        # when the last session in it ended
        self.last = 0

    def add(self, s):
        self.words += s.words
        self.pages += s.pages
        self.active += s.active
        self.last = max(self.last, s.end)

    # the words and pages, not less than 0
    def shownWords(self):
        return max(0, self.words)

    def shownPages(self):
        return max(0.0, self.pages)


class WritingLog:
    def __init__(self):
        # Sessions, in the order they started
        self.sessions = []

        # {id: index into sessions}
        self.index = {}

        # SprintRecords, in the order they started
        self.sprints = []

        # the words of all the sessions together, and {id: the words each
        # one had when it was last put}, to keep it up to date as sessions
        # are replaced. a sprint's words are how much this went up during
        # it.
        self.totalWords = 0
        self.counted = {}

        # whether it has changed since it was last saved
        self.dirty = False

    # the log in the string s, a writinglog.json file's contents. raises
    # ValueError if it's not one.
    @staticmethod
    def load(s):
        try:
            data = json.loads(s)
        except json.JSONDecodeError as e:
            raise ValueError("not JSON: %s" % e)

        if not isinstance(data, dict) or not isinstance(data.get("sessions"), list):
            raise ValueError("no sessions")

        version = data.get("version", VERSION)

        if not isinstance(version, int) or (version > VERSION):
            raise ValueError("written by a newer version of Trelby")

        byId = {}

        for d in data["sessions"]:
            try:
                s = Session.fromDict(d)
            except (ValueError, TypeError, KeyError, AttributeError):
                # one bad session doesn't lose the others
                continue

            byId[s.id] = s

        log = WritingLog()
        log.sessions = sorted(byId.values(), key=lambda s: s.start)
        log.reindex()
        log.counted = {s.id: s.words for s in log.sessions}
        log.totalWords = sum(log.counted.values())

        sprints = data.get("sprints", [])

        if isinstance(sprints, list):
            for d in sprints:
                try:
                    log.sprints.append(SprintRecord.fromDict(d))
                except (ValueError, TypeError, KeyError, AttributeError):
                    continue

        log.sprints.sort(key=lambda sp: sp.start)

        return log

    def save(self):
        return json.dumps(
            {
                "version": VERSION,
                "sessions": [s.toDict() for s in self.sessions],
                "sprints": [sp.toDict() for sp in self.sprints],
            },
            ensure_ascii=False,
            indent=0,
        )

    def reindex(self):
        self.index = {s.id: i for i, s in enumerate(self.sessions)}

    # add session s, or if one with its id is already in the log, replace
    # it
    def put(self, s):
        i = self.index.get(s.id)

        if i is None:
            # sessions mostly arrive in order; one that started earlier
            # than the last one goes in its place
            self.sessions.append(s)

            if (len(self.sessions) > 1) and (self.sessions[-2].start > s.start):
                self.sessions.sort(key=lambda x: x.start)
                self.reindex()
            else:
                self.index[s.id] = len(self.sessions) - 1
        else:
            self.sessions[i] = s

        self.totalWords += s.words - self.counted.get(s.id, 0)
        self.counted[s.id] = s.words
        self.dirty = True

    def addSprint(self, rec):
        self.sprints.append(rec)
        self.sprints.sort(key=lambda sp: sp.start)
        self.dirty = True

    # the sprints that started on local day 'day'
    def sprintsOn(self, day):
        return [sp for sp in self.sprints if sp.day() == day]

    # the sessions that started on local day 'day', newest last
    def sessionsOn(self, day):
        start = dayStart(day)
        end = dayStart(day + datetime.timedelta(days=1))
        ret = []

        # the recent ones are at the end, which is what's mostly asked for
        for s in reversed(self.sessions):
            if s.start < start:
                break

            if s.start < end:
                ret.append(s)

        ret.reverse()

        return ret

    # what was written on local day 'day', in all scripts
    def dayTotal(self, day):
        t = Total(day)

        for s in self.sessionsOn(day):
            t.add(s)

        return t

    # what was written in the week of day 'today', from its Monday up to
    # and including it. its words and pages are the days' shown ones, so a
    # day that took words away doesn't take them off another.
    def weekTotal(self, today):
        t = Total(today)

        for i in range(today.weekday() + 1):
            day = self.dayTotal(today - datetime.timedelta(days=i))
            t.words += day.shownWords()
            t.pages += day.shownPages()
            t.active += day.active

        return t

    # the day totals of the n days up to and including 'today', oldest
    # first
    def days(self, today, n):
        return [self.dayTotal(today - datetime.timedelta(days=i)) for i in range(n)][
            ::-1
        ]

    # how many days in a row, up to today, something was written on. today
    # counts once it has some words, but having none yet doesn't break the
    # run that ended yesterday.
    def streak(self, today):
        days = 0
        day = today

        if self.dayTotal(day).words <= 0:
            day -= datetime.timedelta(days=1)

        while self.dayTotal(day).words > 0:
            days += 1
            day -= datetime.timedelta(days=1)

        return days


# the log in the file at path, or a new one if there's no file. if the
# file can't be read, it's renamed to <path>.bad, so that the next save
# doesn't overwrite it, and a new log is returned. returns (log, error),
# error being why the file couldn't be read, or None.
def loadFile(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            s = f.read()
    except FileNotFoundError:
        return (WritingLog(), None)
    except (OSError, UnicodeDecodeError) as e:
        return (WritingLog(), str(e))

    try:
        return (WritingLog.load(s), None)
    except ValueError as e:
        try:
            os.replace(path, path + ".bad")
        except OSError:
            pass

        return (WritingLog(), str(e))
