from types import SimpleNamespace

import pytest
import wx

import tests.test_tablereader as test_tablereader
import trelby.translations as translations
import trelby.ui.gutil as gutil
import trelby.ui.tablereader as tablereader

_ = translations.trelby_translations_load()

import trelby.ui.readaloudview as readaloudview  # noqa: E402
from trelby.screenplay.tableread import NARRATOR, VoiceChoice  # noqa: E402
from trelby.speech import Voice  # noqa: E402

# the side panel's Read aloud tab (ui/readaloudview.py), on a stand-in for
# the MyPanel and the main frame, with a real TableReader on a fake backend
# (see test_tablereader)


@pytest.fixture(scope="module")
def app():
    a = wx.App(False)
    gutil.init()
    yield a
    a.Destroy()


class Ctrl(test_tablereader.Ctrl):
    def SetFocus(self):
        pass


@pytest.fixture
def setup(app, monkeypatch):
    messages = []

    monkeypatch.setattr(wx, "CallAfter", lambda f, *args: f(*args))
    monkeypatch.setattr(wx, "MessageBox", lambda msg, *args: messages.append(msg))

    frame = wx.Frame(None, size=wx.Size(300, 400))
    mainFrame = SimpleNamespace(readerChanged=lambda: panel.updateState())

    reader = tablereader.TableReader(mainFrame)
    backend = test_tablereader.FakeBackend()
    reader.backend = backend
    reader.triedBackend = True
    reader.nameGenders = {"BOB": (1, 0), "ANN": (0, 1)}
    mainFrame.reader = reader

    ctrl = Ctrl(reader)
    scriptPanel = SimpleNamespace(ctrl=ctrl, gd=SimpleNamespace(mainFrame=mainFrame))

    panel = readaloudview.ReadAloudPanel(frame, scriptPanel)
    frame.Layout()
    panel.refresh()

    yield SimpleNamespace(
        panel=panel, reader=reader, backend=backend, ctrl=ctrl, messages=messages
    )

    frame.Destroy()


# each row as (name, voice shown, speed shown)
def rows(panel):
    return [
        (r.name, r.voice.GetStringSelection(), r.speed.GetStringSelection())
        for r in panel.rows
    ]


def said(backend):
    return test_tablereader.said(backend)


# the narrator and the characters, with the voices they'd be read in
def testCast(setup):
    p = setup.panel

    assert rows(p) == [
        (NARRATOR, "David", "100%"),
        ("BOB", "David", "120%"),
        ("ANN", "Zira", "100%"),
    ]
    assert p.rows[0].label.GetLabel() == "Narrator"
    assert not p.resetBtn.IsEnabled()

    # nothing's being read
    assert not p.stopBtn.IsEnabled()
    assert p.status.GetLabel() == ""


# a voice chosen is kept in the script, and the others are given out
# around it; reset goes back to the automatic ones
def testChooseVoice(setup):
    p, sp = setup.panel, setup.ctrl.sp
    bob = p.rows[1]

    bob.voice.SetSelection(1)
    bob.speed.SetSelection(readaloudview.SPEEDS.index(1.0))
    p.OnChoice(bob)

    assert sp.readAloud.choices == {"BOB": VoiceChoice("zira", 100)}
    assert sp.hasChanged
    assert p.resetBtn.IsEnabled()

    # ANN doesn't share Bob's voice
    assert rows(p)[1:] == [("BOB", "Zira", "100%"), ("ANN", "Zira", "120%")]

    p.OnReset(None)

    assert sp.readAloud.choices == {}
    assert rows(p)[1] == ("BOB", "David", "120%")


# the play button reads from the cursor and pauses, and the speaker being
# read is highlighted
def testPlay(setup):
    p, reader, backend, ctrl = setup.panel, setup.reader, setup.backend, setup.ctrl

    ctrl.ed.gotoPos(4, 0)
    p.OnPlay(None)

    assert reader.isReading()
    assert p.status.GetLabel() == "Reading"
    assert p.playBtn.GetToolTipText() == "Pause"
    assert p.stopBtn.IsEnabled()
    assert p.currentRow is p.rows[1]

    backend.finish()

    # "He drinks it."
    assert p.currentRow is p.rows[0]

    p.OnPlay(None)

    assert reader.state == tablereader.PAUSED
    assert p.status.GetLabel() == "Paused"
    assert p.playBtn.GetToolTipText() == "Resume"

    p.OnNext(None)

    assert p.currentRow is p.rows[2]

    p.OnStop(None)

    assert not reader.isActive()
    assert p.currentRow is None
    assert not p.nextBtn.IsEnabled()


# a voice changed while reading is used from the next element on
def testRecast(setup):
    p, backend, ctrl = setup.panel, setup.backend, setup.ctrl

    ctrl.ed.gotoPos(4, 0)
    p.OnPlay(None)

    ann = p.rows[2]
    ann.voice.SetSelection(0)
    p.OnChoice(ann)

    assert setup.reader.isReading()

    backend.finish()
    backend.finish()

    assert said(backend)[-1] == (
        "Bob? Are you up? It's three in the morning.",
        "david",
        100,
    )


# the speaker button says the start of the speaker's first line
# in the voice shown, stopping any reading
def testSample(setup):
    p, reader, backend = setup.panel, setup.reader, setup.backend

    p.OnPlay(None)
    p.playSample(p.rows[2])

    assert not reader.isActive()
    assert said(backend)[-1] == (
        "Bob? Are you up? It's three in the morning.",
        "zira",
        100,
    )
    assert reader.previewing

    stops = backend.stops
    p.OnStop(None)

    assert backend.stops == stops + 1
    assert not reader.previewing

    p.playSample(p.rows[0])

    assert said(backend)[-1] == ("Fade in.", "david", 100)

    backend.finish()

    assert not reader.previewing


def testNoBackend(setup):
    p, reader = setup.panel, setup.reader

    reader.backend = None
    reader.noBackendReason = "Install it."
    p.refresh()

    assert p.message.IsShown()
    assert "Install it." in p.message.GetLabel()
    assert not p.holder.IsShown()
    assert not p.playBtn.IsShown()


def testVoiceLabels():
    voices = [
        Voice("1", "Microsoft David Desktop - English (United States)"),
        Voice("2", "Microsoft Zira Desktop - English (United States)"),
        Voice("3", "Microsoft Zira Desktop - English (United Kingdom)"),
        Voice("4", "", "en"),
    ]

    assert readaloudview.voiceLabels(voices) == [
        "David",
        "Microsoft Zira Desktop - English (United States)",
        "Microsoft Zira Desktop - English (United Kingdom)",
        "4",
    ]
