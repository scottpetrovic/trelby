import pytest
import wx

import tests.test_tableread as test_tableread
import trelby.screenplay as screenplay
import trelby.translations as translations
import trelby.ui.tablereader as tablereader
from trelby.speech import Voice

_ = translations.trelby_translations_load()

# the table read's GUI side (ui/tablereader.py), on a stand-in for MyCtrl
# and a backend that finishes utterances when told to


class FakeBackend:
    defaultRate = 100

    def __init__(self):
        # (text, voiceId, rate, onDone) of each speak()
        self.spoken = []
        self.stops = 0

    def voices(self):
        return [Voice("david", "David", "en-US", "male"), Voice("zira", "Zira", "en-US", "female")]

    def speak(self, text, voiceId, rate, onDone):
        self.spoken.append((text, voiceId, rate, onDone))

    def stop(self):
        self.stops += 1

    def close(self):
        pass

    # the last utterance has been spoken to the end
    def finish(self, completed=True, error=None):
        self.spoken[-1][3](completed, error)


class Ctrl:
    def __init__(self, reader):
        self.ed = test_tableread.u.loadStringEditor(test_tableread.SCRIPT)
        self.sp = self.ed.sp
        self.reader = reader
        self.readingLines = None
        self.visible = []

    def clearAutoComp(self):
        pass

    def makeLineVisible(self, line):
        self.visible.append(line)

    def updateScreen(self):
        self.reader.checkScript(self)

    def Refresh(self, erase):
        pass


@pytest.fixture
def setup(monkeypatch):
    messages = []

    monkeypatch.setattr(wx, "CallAfter", lambda f, *args: f(*args))
    monkeypatch.setattr(wx, "MessageBox", lambda msg, *args: messages.append(msg))

    reader = tablereader.TableReader(None)
    backend = FakeBackend()
    reader.backend = backend
    reader.triedBackend = True
    reader.nameGenders = {"BOB": (1, 0), "ANN": (0, 1)}

    ctrl = Ctrl(reader)

    return reader, backend, ctrl, messages


def said(backend):
    return [(text, voice, rate) for text, voice, rate, onDone in backend.spoken]


def testReadFromCursor(setup):
    reader, backend, ctrl, messages = setup

    # on the character name: its speech
    ctrl.ed.gotoPos(4, 3)
    reader.toggle(ctrl)

    assert reader.isReading()
    assert said(backend) == [("Not again.", "david", 120)]
    assert ctrl.readingLines == (6, 6)
    assert (ctrl.ed.line, ctrl.ed.column) == (6, 0)
    assert 6 in ctrl.visible

    backend.finish()

    assert said(backend)[1] == ("He drinks it.", "david", 100)
    assert ctrl.readingLines == (7, 7)

    backend.finish()

    assert said(backend)[2] == (
        "Bob? Are you up? It's three in the morning.",
        "zira",
        100,
    )
    assert ctrl.readingLines == (9, 10)


def testReadsToTheEnd(setup):
    reader, backend, ctrl, messages = setup

    ctrl.ed.gotoPos(16, 0)
    reader.toggle(ctrl)
    backend.finish()

    assert said(backend)[-1][0] == "End of act one"

    backend.finish()

    assert not reader.isActive()
    assert ctrl.readingLines is None
    assert len(backend.spoken) == 2


def testPauseResume(setup):
    reader, backend, ctrl, messages = setup

    reader.toggle(ctrl)
    reader.toggle(ctrl)

    assert reader.state == tablereader.PAUSED
    assert backend.stops == 1

    # the stopped utterance's end doesn't move on
    backend.finish(False)

    assert len(backend.spoken) == 1
    assert ctrl.readingLines == (0, 0)

    # resuming reads it again
    reader.toggle(ctrl)

    assert reader.isReading()
    assert said(backend) == [("Fade in.", "david", 100)] * 2


def testSkip(setup):
    reader, backend, ctrl, messages = setup

    reader.toggle(ctrl)
    reader.skip(1)
    reader.skip(1)
    reader.skip(-1)

    assert [s[0] for s in said(backend)] == [
        "Fade in.",
        "Interior. kitchen, night",
        "Bob makes coffee, badly. The machine hisses and spits all over"
        " the counter.",
        "Interior. kitchen, night",
    ]

    # an earlier utterance's end is ignored
    backend.spoken[0][3](True, None)

    assert len(backend.spoken) == 4

    # can't go before the start
    reader.skip(-1)
    reader.skip(-1)

    assert said(backend)[-1][0] == "Fade in."

    # paused: only shows where it is
    reader.pause()
    reader.skip(1)

    assert len(backend.spoken) == 5
    assert ctrl.readingLines == (1, 1)

    reader.pause()

    assert said(backend)[-1][0] == "Interior. kitchen, night"


def testEditStops(setup):
    reader, backend, ctrl, messages = setup

    reader.toggle(ctrl)
    stops = backend.stops

    # moving the cursor doesn't stop it
    ctrl.ed.gotoPos(2, 3)
    ctrl.updateScreen()

    assert reader.isReading()

    cs = screenplay.CommandState()
    cs.char = "x"
    ctrl.ed.addCharCmd(cs)
    ctrl.updateScreen()

    assert not reader.isActive()
    assert backend.stops == stops + 1
    assert ctrl.readingLines is None

    # nor does the utterance's end start the next one
    backend.finish(False)

    assert len(backend.spoken) == 1


def testStopAndError(setup):
    reader, backend, ctrl, messages = setup

    reader.toggle(ctrl)
    reader.stop()

    assert not reader.isActive()
    assert ctrl.readingLines is None

    # skipping does nothing when stopped
    reader.skip(1)

    assert len(backend.spoken) == 1

    reader.toggle(ctrl)
    backend.finish(False, "the voice is gone")

    assert not reader.isActive()
    assert "the voice is gone" in messages[-1]


def testNothingToRead(setup):
    reader, backend, ctrl, messages = setup

    ctrl.sp.lines = ctrl.sp.lines[:2]
    ctrl.sp.lines[-1].lt = screenplay.CHARACTER
    ctrl.ed.gotoPos(1, 0)
    reader.toggle(ctrl)

    assert not reader.isActive()
    assert backend.spoken == []
    assert messages


def testNoBackend(setup):
    reader, backend, ctrl, messages = setup

    reader.backend = None
    reader.noBackendReason = "Install it."
    reader.toggle(ctrl)

    assert not reader.isActive()
    assert "Install it." in messages[-1]
