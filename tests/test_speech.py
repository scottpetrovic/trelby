import sys
import threading
import types

import pytest

import trelby.speech as speech
import trelby.translations as translations
from trelby.speech import Voice

_ = translations.trelby_translations_load()

TIMEOUT = 10


# collects onDone's calls, and waits for them
class Done:
    def __init__(self):
        self.calls = []
        self.cond = threading.Condition()

    def __call__(self, completed, error):
        with self.cond:
            self.calls.append((completed, error))
            self.cond.notify_all()

    def wait(self, n=1):
        with self.cond:
            assert self.cond.wait_for(lambda: len(self.calls) >= n, TIMEOUT)

        return self.calls[n - 1]


# a ThreadedBackend whose utterances last until finish() or stop()
class FakeBackend(speech.ThreadedBackend):
    def __init__(self):
        super().__init__()
        self.spoken = []
        self.started = threading.Event()
        self.end = threading.Event()
        self.fail = None

    def finish(self):
        self.end.set()

    def _run(self, job):
        self.spoken.append((job.text, job.voiceId, job.rate))
        self.end.clear()
        self.started.set()

        if self.fail:
            raise RuntimeError(self.fail)

        self.end.wait(TIMEOUT)

        return not job.cancelled

    def _interrupt(self):
        self.end.set()


@pytest.fixture
def fake():
    b = FakeBackend()
    yield b
    b.close()


def testSpeakToTheEnd(fake):
    done = Done()

    fake.speak("Hello.", "v1", 150, done)
    assert fake.started.wait(TIMEOUT)
    fake.finish()

    assert done.wait() == (True, None)
    assert fake.spoken == [("Hello.", "v1", 150)]


def testStop(fake):
    done = Done()

    fake.speak("Hello.", "v1", 150, done)
    assert fake.started.wait(TIMEOUT)
    fake.stop()

    assert done.wait() == (False, None)

    # stopping when nothing's spoken does nothing
    fake.stop()
    assert len(done.calls) == 1


# speaking stops the utterance being spoken, which is reported as not
# completed
def testSpeakStopsTheCurrentOne(fake):
    first = Done()
    second = Done()

    fake.speak("One.", "v1", 150, first)
    assert fake.started.wait(TIMEOUT)
    fake.started.clear()

    fake.speak("Two.", "v2", 160, second)

    assert first.wait() == (False, None)
    assert fake.started.wait(TIMEOUT)
    fake.finish()

    assert second.wait() == (True, None)
    assert [s[0] for s in fake.spoken] == ["One.", "Two."]


# a stop before the worker gets to an utterance means it's never spoken
def testStopBeforeStarting():
    gate = threading.Event()

    class SlowStart(FakeBackend):
        def _threadInit(self):
            gate.wait(TIMEOUT)

    b = SlowStart()
    done = Done()

    b.speak("Never.", None, 150, done)
    b.stop()

    assert done.wait() == (False, None)

    gate.set()
    b.close()

    assert b.spoken == []


def testError(fake):
    done = Done()
    fake.fail = "no such voice"

    fake.speak("Hello.", "v1", 150, done)

    assert done.wait() == (False, "no such voice")

    # and the next one works
    fake.fail = None
    fake.started.clear()
    fake.speak("Again.", "v1", 150, done)
    assert fake.started.wait(TIMEOUT)
    fake.finish()

    assert done.wait(2) == (True, None)


def testClose(fake):
    done = Done()

    fake.speak("Hello.", "v1", 150, done)
    assert fake.started.wait(TIMEOUT)
    thread = fake._thread
    fake.close()

    assert done.wait() == (False, None)
    assert not thread.is_alive()


# a stand-in for the pyttsx3 module: its Engine "speaks" on runAndWait,
# reporting the events pyttsx3 does
class FakeEngine:
    voices = [
        types.SimpleNamespace(
            id="zira", name="Zira", languages=["en-US"], gender="Female"
        ),
        types.SimpleNamespace(
            id="david", name="David", languages=["en_US"], gender="Male"
        ),
        types.SimpleNamespace(id="x", name=None, languages=[b"\x05en"], gender=None),
    ]

    spoken = []
    stopNext = False

    def __init__(self):
        self.props = {"voice": "david"}
        self.cbs = {}
        self.queue = []

    def getProperty(self, name):
        return self.voices if name == "voices" else self.props[name]

    def setProperty(self, name, value):
        self.props[name] = value

    def connect(self, topic, cb):
        self.cbs.setdefault(topic, []).append(cb)

    def say(self, text):
        self.queue.append(text)

    def notify(self, topic, **kwargs):
        for cb in self.cbs.get(topic, []):
            cb(**kwargs)

    def stop(self):
        self.stopped = True

    def runAndWait(self):
        self.stopped = False

        for text in self.queue:
            self.notify("started-word", name=None, location=0, length=1)

            if FakeEngine.stopNext:
                self.stop()

            FakeEngine.spoken.append(
                (text, self.props["voice"], self.props["rate"], self.stopped)
            )
            self.notify("finished-utterance", name=None, completed=not self.stopped)

        self.queue = []


@pytest.fixture
def pyttsx3(monkeypatch):
    monkeypatch.setattr(speech, "_comInit", lambda: None)
    FakeEngine.spoken = []
    FakeEngine.stopNext = False

    return types.SimpleNamespace(Engine=FakeEngine)


def testPyttsx3Voices(pyttsx3):
    b = speech.Pyttsx3Backend(pyttsx3)

    # the default voice first
    assert b.voices() == [
        Voice("david", "David", "en-US", "male"),
        Voice("zira", "Zira", "en-US", "female"),
        Voice("x", "x", "en", None),
    ]


def testPyttsx3Speak(pyttsx3):
    b = speech.Pyttsx3Backend(pyttsx3)
    done = Done()

    b.speak("Hello.", "zira", 180, done)
    assert done.wait() == (True, None)

    b.speak("Bye.", "david", 140, done)
    assert done.wait(2) == (True, None)

    assert FakeEngine.spoken == [
        ("Hello.", "zira", 180, False),
        ("Bye.", "david", 140, False),
    ]

    b.close()


# a stop() just as the engine starts, too early for it to do anything,
# is acted on once it has started
def testPyttsx3StopAtStart(pyttsx3):
    b = speech.Pyttsx3Backend(pyttsx3)
    done = Done()
    FakeEngine.stopNext = True

    b.speak("Hello.", None, 180, done)

    assert done.wait() == (False, None)
    b.close()


# a CommandBackend running Python, which reads the text and exits with
# the code given as the voice, or sleeps for "sleep"
class PythonBackend(speech.CommandBackend):
    def __init__(self):
        super().__init__(sys.executable)

    def args(self, voiceId, rate):
        code = (
            "import sys, time\n"
            "text = sys.stdin.read()\n"
            "if text == 'sleep': time.sleep(30)\n"
            "if text == 'fail': sys.stderr.write('bad voice'); sys.exit(3)\n"
        )

        return ["-c", code]


def testCommandBackend():
    b = PythonBackend()
    done = Done()

    b.speak("hello", None, 150, done)
    assert done.wait() == (True, None)

    b.speak("fail", None, 150, done)
    assert done.wait(2) == (False, "bad voice")

    b.speak("sleep", None, 150, done)

    # wait for the process to start, then stop it
    for i in range(200):
        if b._proc:
            break

        threading.Event().wait(0.05)

    b.stop()
    assert done.wait(3) == (False, None)

    b.close()


SAY_VOICES = """Albert              en_US    # Hello! My name is Albert.
Amelie              fr_CA    # Bonjour! Je m’appelle Amelie.
Bad News            en_US    # Hello! My name is Bad News.
Eddy (English (UK)) en_GB    # Hello! My name is Eddy.
Samantha            en_US    # Hello! My name is Samantha.
"""


def testParseSayVoices():
    assert speech.parseSayVoices(SAY_VOICES) == [
        Voice("Albert", "Albert", "en-US", "male"),
        Voice("Amelie", "Amelie", "fr-CA", "female"),
        Voice("Bad News", "Bad News", "en-US", None),
        Voice("Eddy (English (UK))", "Eddy (English (UK))", "en-GB", "male"),
        Voice("Samantha", "Samantha", "en-US", "female"),
    ]

    # an English voice first
    assert speech.parseSayVoices(SAY_VOICES.split("\n", 1)[1])[0].id == "Bad News"

    assert speech.SayBackend().args("Samantha", 200) == ["-v", "Samantha", "-r", "200"]


ESPEAK_VOICES = """Pty Language       Age/Gender VoiceName          File                 Other Languages
 5  af              --/M      Afrikaans          gmw/af
 2  en-gb           --/M      English_(Great_Britain) gmw/en           (en 2)
 5  en-us           --/F      English_(America)  gmw/en-US            (en 3)
 5  fi              --/M      Finnish            urj/fi
"""


def testParseEspeakVoices():
    voices = speech.parseEspeakVoices(ESPEAK_VOICES, "en_US")

    assert voices[0] == Voice("en-us", "English (America)", "en-US", "female")

    # the variants of the best match
    assert voices[1] == Voice("en-us+f2", "English (America) f2", "en-US", "female")
    assert voices[2].gender == "male"

    n = len(speech.ESPEAK_VARIANTS)

    assert [v.id for v in voices[n + 1 :]] == ["en-gb", "af", "fi"]

    # no language: English first
    assert speech.parseEspeakVoices(ESPEAK_VOICES)[0].id == "en-gb"
    assert speech.parseEspeakVoices("") == []

    assert speech.EspeakBackend("espeak-ng").args("en-us", 170) == [
        "-v",
        "en-us",
        "-s",
        "170",
        "--stdin",
    ]


@pytest.mark.parametrize(
    "s, lang",
    [
        ("en_US", "en-US"),
        ("EN-gb", "en-GB"),
        (b"\x05en-us", "en-US"),
        ("", ""),
        (None, ""),
        ("zh-yue", "zh-YUE"),
    ],
)
def testNormalizeLanguage(s, lang):
    assert speech.normalizeLanguage(s) == lang


def testNormalizeGender():
    assert speech.normalizeGender("Male") == "male"
    assert speech.normalizeGender("F") == "female"
    assert speech.normalizeGender("neutral") is None
    assert speech.normalizeGender(None) is None


def testSystemBackendWithoutPyttsx3(monkeypatch):
    def noModule(name):
        raise ImportError(name)

    monkeypatch.setattr(speech.importlib, "import_module", noModule)
    monkeypatch.setattr(speech.sys, "platform", "win32")

    backend, reason = speech.systemBackend()

    assert backend is None
    assert "pip install trelby[speech]" in reason

    monkeypatch.setattr(speech.sys, "platform", "linux")
    monkeypatch.setattr(speech.shutil, "which", lambda name: None)

    backend, reason = speech.systemBackend()

    assert backend is None
    assert "espeak-ng" in reason

    monkeypatch.setattr(
        speech.shutil, "which", lambda name: "/usr/bin/" + name if name == "espeak" else None
    )
    backend, reason = speech.systemBackend()

    assert isinstance(backend, speech.EspeakBackend)
    assert backend.command == "/usr/bin/espeak"

    monkeypatch.setattr(speech.sys, "platform", "darwin")
    monkeypatch.setattr(speech.shutil, "which", lambda name: "/usr/bin/say")

    assert isinstance(speech.systemBackend()[0], speech.SayBackend)
