# reading text aloud with the operating system's own text-to-speech voices
# (no wx). the table read (screenplay/tableread.py for what's read in which
# voice, ui/tablereader.py for the GUI) speaks through a Backend:
#
#  - voices() lists the voices, the system's default voice first.
#  - speak(text, voiceId, rate, onDone) starts speaking one utterance and
#    returns at once. onDone(completed, error) is called once, from any
#    thread, when it has finished (completed = True), been stopped
#    (False), or failed (False, and error is a message for the user).
#  - stop() stops the current utterance. speaking a new one stops the
#    current one first.
#  - close() stops and lets go of the engine.
#
# systemBackend() picks the platform's backend:
#
#  - Windows: SAPI 5, through pyttsx3 (an optional extra, pip install
#    trelby[speech]), with the voices Windows' Settings installs too
#    (ONECORE_VOICES).
#  - macOS: the "say" command.
#  - Linux and others: the espeak-ng (or espeak) command, or pyttsx3
#    (which uses the espeak library) if neither is installed.
#
# another engine (e.g. neural voices) only needs another Backend.

import importlib
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Callable, List, Optional


@dataclass(frozen=True)
class Voice:
    # what speak() takes as voiceId
    id: str

    # the name to show
    name: str

    # BCP 47 style language tag, e.g. "en-US", or "" if not known
    language: str = ""

    # "male", "female", or None if not known
    gender: Optional[str] = None


# lower-cased "male" / "female" from whatever an engine says, or None
def normalizeGender(s) -> Optional[str]:
    s = str(s or "").strip().lower()

    if s in ("male", "m"):
        return "male"
    elif s in ("female", "f"):
        return "female"

    return None


# "en_US", b"\x05en-us" (espeak's) etc. to "en-US", "" if there's nothing
def normalizeLanguage(s) -> str:
    if isinstance(s, bytes):
        s = s.decode("ascii", "ignore")

    s = re.sub(r"[^A-Za-z0-9_-]", "", str(s or "")).replace("_", "-")
    parts = s.split("-")

    if not parts[0]:
        return ""

    return "-".join([parts[0].lower()] + [p.upper() for p in parts[1:]])


class Backend:
    # shown to the user
    name = ""

    # the rate the voices normally speak at, in words per minute
    defaultRate = 175

    def voices(self) -> List[Voice]:
        raise NotImplementedError

    def speak(
        self,
        text: str,
        voiceId: Optional[str],
        rate: int,
        onDone: Callable[[bool, Optional[str]], None],
    ) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        self.stop()


# one utterance for a ThreadedBackend
class _Job:
    def __init__(self, text, voiceId, rate, onDone):
        self.text = text
        self.voiceId = voiceId
        self.rate = rate
        self.onDone = onDone

        # set by stop(), under the backend's lock
        self.cancelled = False


# a Backend whose engine speaks one utterance at a time, blocking until
# it's done: a worker thread runs _run(job) for each, and stop() calls
# _interrupt() to make it return early. both are called with self.lock
# held only where noted; subclasses take the lock to check job.cancelled
# and record what _interrupt needs, so that a stop() can't slip in
# between: _interrupt is called (under the lock) only for the job being
# run.
class ThreadedBackend(Backend):
    def __init__(self):
        self.lock = threading.Lock()
        self._jobs = queue.Queue()
        self._current = None
        self._thread = None

    def speak(self, text, voiceId, rate, onDone):
        self.stop()

        if (self._thread is None) or not self._thread.is_alive():
            self._thread = threading.Thread(
                target=self._work, name="trelby-speech", daemon=True
            )
            self._thread.start()

        self._jobs.put(_Job(text, voiceId, rate, onDone))

    def stop(self):
        dropped = []

        with self.lock:
            while True:
                try:
                    job = self._jobs.get_nowait()
                except queue.Empty:
                    break

                if job is not None:
                    job.cancelled = True
                    dropped.append(job)

            if self._current and not self._current.cancelled:
                self._current.cancelled = True
                self._interrupt()

        for job in dropped:
            job.onDone(False, None)

    def close(self):
        self.stop()

        if self._thread and self._thread.is_alive():
            self._jobs.put(None)
            self._thread.join(2.0)

        self._thread = None

    def _work(self):
        self._threadInit()

        while True:
            job = self._jobs.get()

            if job is None:
                break

            with self.lock:
                if job.cancelled:
                    continue

                self._current = job

            error = None
            completed = False

            try:
                completed = self._run(job)
            except Exception as e:
                error = str(e) or e.__class__.__name__

            with self.lock:
                self._current = None
                completed = completed and not job.cancelled

            job.onDone(completed, error)

    # called once in the worker thread before anything else
    def _threadInit(self):
        pass

    # speak job, returning whether it was spoken to the end
    def _run(self, job) -> bool:
        raise NotImplementedError

    # make the _run in progress return as soon as possible. called with
    # self.lock held.
    def _interrupt(self):
        raise NotImplementedError


# Windows needs COM set up in each thread that uses SAPI. wx has already
# done it in the GUI thread, which is fine.
def _comInit():
    if sys.platform == "win32":
        import pythoncom

        pythoncom.CoInitialize()


# the registry key of the voices installed by Windows' Settings (Time &
# language > Speech), which SAPI 5 doesn't list (it only lists the older
# desktop voices, under Speech\Voices) but can speak with when given one
ONECORE_VOICES = r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices"


# a voice's name without "Desktop", which Windows' desktop voices have and
# the same voices from Settings don't: "Microsoft David Desktop - English
# (United States)" and "Microsoft David - English (United States)"
def _sameVoiceName(name):
    return (name or "").replace(" Desktop", "").lower()


# SAPI 5 on Windows, or espeak / NSSpeechSynthesizer elsewhere, through
# pyttsx3. a new pyttsx3.Engine is made for each utterance (it takes a few
# milliseconds): pyttsx3 2.99's SAPI driver cuts every utterance after the
# first one short when an engine is reused with runAndWait.
class Pyttsx3Backend(ThreadedBackend):
    name = "pyttsx3"

    # pyttsx3's SAPI driver maps words per minute to SAPI's rates of -10 to
    # 10 so that 156 is SAPI's normal rate of 0
    defaultRate = 160 if sys.platform == "win32" else 175

    def __init__(self, module=None):
        super().__init__()
        self.pyttsx3 = module or importlib.import_module("pyttsx3")
        self._engine = None
        self._voices = None

    def _threadInit(self):
        _comInit()

    def voices(self):
        if self._voices is None:
            _comInit()
            engine = self.pyttsx3.Engine()
            default = engine.getProperty("voice")
            ret = []

            for v in engine.getProperty("voices"):
                voice = toVoice(v)

                if v.id == default:
                    ret.insert(0, voice)
                else:
                    ret.append(voice)

            # the voices from Settings that aren't the desktop ones again
            names = {_sameVoiceName(v.name) for v in ret}

            for v in self.extraVoices(engine):
                voice = toVoice(v)

                if _sameVoiceName(voice.name) not in names:
                    names.add(_sameVoiceName(voice.name))
                    ret.append(voice)

            self._voices = ret

        return self._voices

    # the voices SAPI 5 doesn't list (see ONECORE_VOICES), as pyttsx3
    # voices, or [] if they can't be found
    def extraVoices(self, engine):
        if sys.platform != "win32":
            return []

        try:
            import comtypes.client

            driver = engine.proxy._driver
            cat = comtypes.client.CreateObject("SAPI.SpObjectTokenCategory")
            cat.SetId(ONECORE_VOICES, False)

            tokens = list(cat.EnumerateTokens())
        except Exception:
            return []

        ret = []

        for t in tokens:
            try:
                ret.append(driver._toVoice(t))
            except Exception:
                # e.g. no language; skip it rather than lose the others
                pass

        return ret

    # whether voiceId is one of extraVoices', which pyttsx3 can't select
    def isExtraVoice(self, voiceId):
        return voiceId.lower().startswith(ONECORE_VOICES.lower() + "\\")

    # make engine speak in extra voice voiceId, behind pyttsx3's back
    def selectExtraVoice(self, engine, voiceId):
        import comtypes.client

        token = comtypes.client.CreateObject("SAPI.SpObjectToken")
        token.SetId(voiceId, "", False)
        engine.proxy._driver._tts.Voice = token

    def _run(self, job):
        engine = self.pyttsx3.Engine()

        if job.voiceId and self.isExtraVoice(job.voiceId):
            self.selectExtraVoice(engine, job.voiceId)
        elif job.voiceId:
            engine.setProperty("voice", job.voiceId)

        engine.setProperty("rate", job.rate)

        result = {}

        def onFinished(name=None, completed=True, **kwargs):
            result["completed"] = completed

        # a stop() between our check below and the driver actually
        # starting to speak finds nothing to stop, so look again once it
        # has started
        def onStarted(**kwargs):
            if job.cancelled:
                engine.stop()

        engine.connect("finished-utterance", onFinished)
        engine.connect("started-word", onStarted)

        with self.lock:
            if job.cancelled:
                return False

            self._engine = engine

        try:
            engine.say(job.text)
            engine.runAndWait()
        finally:
            with self.lock:
                self._engine = None

        return result.get("completed", False)

    def _interrupt(self):
        if self._engine:
            self._engine.stop()


# our Voice for pyttsx3 voice v
def toVoice(v):
    langs = getattr(v, "languages", None) or [""]

    return Voice(
        str(v.id),
        str(v.name or v.id),
        normalizeLanguage(langs[0]),
        normalizeGender(getattr(v, "gender", None)),
    )


# a backend that runs a command for each utterance, giving it the text on
# its standard input, and kills it to stop
class CommandBackend(ThreadedBackend):
    def __init__(self, command):
        super().__init__()
        self.command = command
        self._proc = None
        self._voices = None

    # the command line to speak with voiceId at rate (words per minute)
    def args(self, voiceId, rate) -> List[str]:
        raise NotImplementedError

    def voices(self):
        if self._voices is None:
            self._voices = self.listVoices()

        return self._voices

    def listVoices(self) -> List[Voice]:
        raise NotImplementedError

    def output(self, args) -> str:
        return subprocess.run(
            [self.command] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        ).stdout

    def _run(self, job):
        with self.lock:
            if job.cancelled:
                return False

            self._proc = subprocess.Popen(
                [self.command] + self.args(job.voiceId, job.rate),
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )

        try:
            err = self._proc.communicate(job.text.encode("utf-8"))[1]
            code = self._proc.returncode
        finally:
            with self.lock:
                self._proc = None

        if job.cancelled:
            return False

        if code != 0:
            raise RuntimeError(
                err.decode("utf-8", "replace").strip()
                or "%s exited with code %d" % (self.command, code)
            )

        return True

    def _interrupt(self):
        if self._proc and (self._proc.poll() is None):
            self._proc.kill()


# the genders of the voices macOS has had over the years, which "say -v ?"
# doesn't tell
MAC_VOICE_GENDERS = {
    "female": (
        "Agnes Alice Alva Amelie Anna Allison Ava Carmit Catherine Damayanti "
        "Ellen Fiona Ioana Joana Kanya Karen Kathy Kyoko Laura Lekha Luciana "
        "Mariska Martha Mei-Jia Melina Milena Moira Monica Nora Paulina "
        "Princess Samantha Sara Satu Sin-ji Susan Tessa Ting-Ting Veena "
        "Vicki Victoria Yelda Yuna Zosia Zuzana Flo Grandma Sandy Shelley"
    ).split(),
    "male": (
        "Aaron Albert Alex Arthur Bruce Daniel Diego Eddy Fred Jorge Juan "
        "Junior Lee Luca Maged Nicolas Oliver Ralph Reed Rishi Rocko Thomas "
        "Tom Xander Yannick Yuri Grandpa"
    ).split(),
}


# macOS's say
class SayBackend(CommandBackend):
    name = "say"
    defaultRate = 180

    def __init__(self, command="say"):
        super().__init__(command)

    def args(self, voiceId, rate):
        return (["-v", voiceId] if voiceId else []) + ["-r", str(rate)]

    def listVoices(self):
        return parseSayVoices(self.output(["-v", "?"]))


# "say -v ?" lists voices as "Name   en_US    # sample sentence", the name
# possibly with spaces or a "(Enhanced)" in it. the system voice isn't
# marked, so the first English one is put first, or failing that the
# first.
def parseSayVoices(s) -> List[Voice]:
    genders = {}

    for gender, names in MAC_VOICE_GENDERS.items():
        for name in names:
            genders[name] = gender

    ret = []

    for line in s.splitlines():
        m = re.match(r"^(.+?)\s+([a-zA-Z]{2,3}[_-][A-Za-z0-9_-]+)\s+#", line)

        if m:
            name = m.group(1).strip()
            ret.append(
                Voice(
                    name,
                    name,
                    normalizeLanguage(m.group(2)),
                    genders.get(name.split(" ")[0]),
                )
            )

    for i, v in enumerate(ret):
        if v.language.startswith("en"):
            ret.insert(0, ret.pop(i))
            break

    return ret


# espeak-ng's voice variants, which give the one voice per language that
# most languages have some variety: (suffix, gender)
ESPEAK_VARIANTS = [
    ("+f2", "female"),
    ("+m3", "male"),
    ("+f4", "female"),
    ("+m7", "male"),
    ("+f3", "female"),
    ("+m2", "male"),
]


# espeak-ng or espeak on Linux
class EspeakBackend(CommandBackend):
    name = "espeak"
    defaultRate = 175

    # language is the system's, like "en-US", for the voice to put first
    def __init__(self, command, language=""):
        super().__init__(command)
        self.language = language

    def args(self, voiceId, rate):
        return (["-v", voiceId] if voiceId else []) + ["-s", str(rate), "--stdin"]

    def listVoices(self):
        return parseEspeakVoices(self.output(["--voices"]), self.language)


# "espeak-ng --voices" lists voices as
#
#   Pty Language       Age/Gender VoiceName          File        Other Langs
#    5  en-us           --/M      English_(America)  gmw/en-US   (en 3)
#
# the voices for language (or, failing that, English) go first, the one
# that matches it best first of all, each followed by its variants
def parseEspeakVoices(s, language="") -> List[Voice]:
    voices = []

    for line in s.splitlines()[1:]:
        f = line.split()

        if len(f) < 4:
            continue

        lang = f[1]
        gender = normalizeGender(f[2].split("/")[-1])
        voices.append(Voice(lang, f[3].replace("_", " "), normalizeLanguage(lang), gender))

    language = normalizeLanguage(language)

    def score(v):
        if language and (v.language == language):
            return 0
        elif language and (v.language.split("-")[0] == language.split("-")[0]):
            return 1
        elif v.language.startswith("en"):
            return 2

        return 3

    voices.sort(key=score)

    if not voices:
        return voices

    first = score(voices[0])
    ret = []

    for v in voices:
        ret.append(v)

        if score(v) == first:
            for suffix, gender in ESPEAK_VARIANTS:
                ret.append(
                    Voice(v.id + suffix, "%s %s" % (v.name, suffix[1:]), v.language, gender)
                )

    return ret


# (Backend, None) for this platform, or (None, the reason there's none, for
# the user)
def systemBackend():
    if sys.platform == "darwin":
        if shutil.which("say"):
            return (SayBackend(), None)

        return (None, _("The \"say\" command was not found."))

    if sys.platform != "win32":
        command = shutil.which("espeak-ng") or shutil.which("espeak")

        if command:
            return (EspeakBackend(command, os.environ.get("LANG", "").split(".")[0]), None)

    try:
        return (Pyttsx3Backend(), None)
    except ImportError:
        if sys.platform == "win32":
            return (
                None,
                _(
                    "Reading aloud needs the pyttsx3 package. Install it with:\n\npip install trelby[speech]"
                ),
            )

        return (
            None,
            _(
                "Reading aloud needs espeak-ng. Install it with your package manager (e.g. apt install espeak-ng)."
            ),
        )
