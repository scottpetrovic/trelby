import tests.u as u
import trelby.translations as translations
import trelby.writingsession as writingsession
from trelby.writinglog import WritingLog

_ = translations.trelby_translations_load()

# recording writing sessions as a script is edited (writingsession.py), on
# a real Editor, with a clock the tests move on


class Clock:
    def __init__(self):
        self.t = 1_800_000_000.0

    def __call__(self):
        return self.t

    def wait(self, seconds):
        self.t += seconds


INFO = lambda: ("/s/Pilot.trelby", "Pilot")  # noqa: E731


def setup(ed=None):
    ed = ed or u.loadEditor()
    log = WritingLog()
    clock = Clock()
    tracker = writingsession.Tracker(log, clock)
    tracker.update(ed.sp, INFO)

    return ed, log, clock, tracker


def type(ed, tracker, text):
    for ch in text:
        ed.cmd("addChar", char=ch)

    ed.sp.paginate()
    tracker.update(ed.sp, INFO)


def testOpeningIsNotWriting():
    ed, log, clock, tracker = setup()

    assert ed.sp.getWordCount() > 0
    assert log.sessions == []

    # nor is looking at it again without changing anything
    clock.wait(10)
    tracker.update(ed.sp, INFO)
    assert log.sessions == []


def testTypingMakesASession():
    ed, log, clock, tracker = setup()
    before = ed.sp.getWordCount()

    type(ed, tracker, "one two ")
    clock.wait(20)
    type(ed, tracker, "three four five ")

    assert len(log.sessions) == 1

    s = log.sessions[0]
    assert s.words == ed.sp.getWordCount() - before == 5
    assert (s.path, s.title) == INFO()
    assert s.active == 20
    assert s.end - s.start == 20
    assert log.dirty


# a gap longer than IDLE isn't writing time, and one longer than
# SESSION_GAP starts a new session, measured from where the last ended
def testGaps():
    ed, log, clock, tracker = setup()

    type(ed, tracker, "a ")
    clock.wait(writingsession.IDLE + 1)
    type(ed, tracker, "b ")

    assert len(log.sessions) == 1
    assert log.sessions[0].active == 0
    assert log.sessions[0].words == 2

    clock.wait(writingsession.SESSION_GAP + 1)
    type(ed, tracker, "c d e ")

    assert len(log.sessions) == 2
    assert [s.words for s in log.sessions] == [2, 3]


# tick ends a session that's gone quiet, and the next edit starts a new one
def testTick():
    ed, log, clock, tracker = setup()

    type(ed, tracker, "a ")
    clock.wait(60)
    tracker.tick()
    assert tracker.session is not None

    clock.wait(writingsession.SESSION_GAP)
    tracker.tick()
    assert tracker.session is None

    type(ed, tracker, "b ")
    assert [s.words for s in log.sessions] == [1, 1]


# deleting takes words off the session
def testDeleting():
    ed, log, clock, tracker = setup()

    ed.cmd("moveEnd")
    type(ed, tracker, " extra words here")

    for i in range(len(" here")):
        ed.cmd("deleteBackward")

    ed.sp.paginate()
    tracker.update(ed.sp, INFO)

    assert log.sessions[0].words == 2


# a new script in the tab ends the session, and doesn't count as writing
def testNewScript():
    ed, log, clock, tracker = setup()
    type(ed, tracker, "a b ")

    other = u.loadEditor()
    tracker.update(other.sp, INFO)
    assert tracker.session is None

    type(other, tracker, "c ")
    assert [s.words for s in log.sessions] == [2, 1]


# what something else wrote isn't the writer's, but what they write after
# it is
def testExclude():
    ed, log, clock, tracker = setup()
    type(ed, tracker, "a b ")

    for ch in "lots of words from the assistant ":
        ed.cmd("addChar", char=ch)

    ed.sp.markChanged()
    ed.sp.paginate()
    tracker.exclude(ed.sp)
    tracker.update(ed.sp, INFO)

    assert log.sessions[0].words == 2

    type(ed, tracker, "c ")
    assert log.sessions[0].words == 3


def testPages():
    ed, log, clock, tracker = setup(u.newEditor())
    before = ed.sp.getPageLength()

    type(ed, tracker, "word " * 400)

    s = log.sessions[0]
    assert s.words == 400
    assert s.pages == ed.sp.getPageLength() - before > 0.4
