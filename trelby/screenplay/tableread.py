# the table read: what is read aloud, and in which voice (no wx). the
# speaking itself is trelby/speech.py's, and the GUI that drives it
# ui/tablereader.py.
#
#  - utterances(sp, opts) splits the whole script into Utterances, one per
#    element read: scene headings, action, transitions, shots and act
#    breaks by the narrator, dialogue by its speaker, as
#    speeches.iterSpeeches finds them (so who speaks where agrees with the
#    reports). character names aren't read, the voice says who it is, and
#    neither are parentheticals, unless the ReadOptions say so; they're
#    read by the narrator then. dialogue with no speaker is the narrator's.
#    indexAt(utts, line) is where reading from a line starts.
#  - assignVoices gives the narrator and each character a VoiceChoice (a
#    voice and a rate), from the voices there are: each character a
#    different one where possible, matching the character's gender where
#    it's known and voices of both genders exist (see guessGender), then
#    the same voices again at other rates. the same script and voices
#    always get the same cast. choices passed in as overrides (e.g. ones
#    stored with the script, later) win.

import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional

import trelby.config as config
import trelby.screenplay.speeches as speeches
from trelby.screenplay.constants import (
    ACTBREAK,
    ACTION,
    CHARACTER,
    DIALOGUE,
    PAREN,
    SCENE,
    SHOT,
    TRANSITION,
)


@dataclass
class ReadOptions:
    # read the parentheticals, in the narrator's voice
    parentheticals: bool = False

    # read each speaker's name before their speech, in the narrator's voice
    characterNames: bool = False

    # read scene headings, action, transitions, shots and act breaks. off,
    # only the dialogue is read.
    narration: bool = True


@dataclass
class Utterance:
    # the lines of the element read
    start: int
    end: int

    # what's said
    text: str

    # the speaker's name (as in speeches.Speech), or None for the narrator
    speaker: Optional[str]

    # the element's type
    lt: int


# the element types the narrator reads (if ReadOptions.narration)
NARRATED = (SCENE, ACTION, TRANSITION, SHOT, ACTBREAK)


def utterances(sp, opts: Optional[ReadOptions] = None) -> List[Utterance]:
    opts = opts or ReadOptions()
    ls = sp.lines

    # first line of each dialogue element -> its speaker
    speakers = {}

    for s in speeches.iterSpeeches(sp):
        for i in s.dialogue:
            speakers[i] = s.name

    ret = []
    i = 0

    while i < len(ls):
        start = i
        end = sp.getElemLastIndexFromLine(i)
        lt = ls[start].lt
        i = end + 1

        speaker = None

        if lt == DIALOGUE:
            speaker = speakers.get(start)
        elif lt == PAREN:
            if not opts.parentheticals:
                continue
        elif lt == CHARACTER:
            if not opts.characterNames:
                continue
        elif (lt not in NARRATED) or not opts.narration:
            continue

        text = spokenText(lt, elemText(sp, start, end))

        if text:
            ret.append(Utterance(start, end, text, speaker, lt))

    return ret


# the text of the element from line start to end, its lines joined as they
# are in its paragraphs
def elemText(sp, start, end):
    ls = sp.lines
    s = ""

    for i in range(start, end + 1):
        s += ls[i].text

        if i != end:
            s += config.lb2str(ls[i].lb)

    return s


# scene heading prefixes and what to say for them
SCENE_PREFIXES = [
    (r"(int\.?\s*/\s*ext|ext\.?\s*/\s*int|i\s*/\s*e)\.?", "Interior, exterior."),
    (r"int\.?", "Interior."),
    (r"ext\.?", "Exterior."),
    (r"est\.?", "Establishing."),
]


# text of an element of type lt, made better for speaking: scene headings
# with INT. / EXT. spelled out, and the headings, transitions, shots and
# act breaks, all capitals by convention, lower cased so that no engine
# spells their words out letter by letter. "" if there's nothing to say.
def spokenText(lt, text):
    s = " ".join(text.split())

    if lt in (SCENE, TRANSITION, SHOT, ACTBREAK):
        s = s.lower()

        if lt == SCENE:
            for pattern, said in SCENE_PREFIXES:
                m = re.match(pattern + r"(\s+|$)", s)

                if m:
                    s = said + " " + s[m.end() :]
                    break

            # "house - night" reads better with a pause than a "minus"
            s = re.sub(r"\s+-+\s+", ", ", s)

        s = s.strip()

        if s.endswith(":"):
            s = s[:-1] + "."

        s = s[:1].upper() + s[1:]

    # a dash between words is a pause too
    s = re.sub(r"\s*--+\s*", ", ", s)

    s = s.strip()

    if not re.search(r"\w", s):
        return ""

    return s


# the index in utts of the first utterance at or after line, or None if
# there's none
def indexAt(utts: List[Utterance], line: int) -> Optional[int]:
    for i, u in enumerate(utts):
        if u.end >= line:
            return i

    return None


# the characters in sp, the ones with the most speeches first, then in the
# order they first speak
def characters(sp) -> List[str]:
    counts = Counter()
    first = {}

    for s in speeches.iterSpeeches(sp):
        counts[s.name] += 1
        first.setdefault(s.name, s.charLine)

    return sorted(counts, key=lambda name: (-counts[name], first[name]))


@dataclass(frozen=True)
class VoiceChoice:
    # speech.Voice.id
    voiceId: str

    # words per minute
    rate: int


# the speaker name for the narrator in a Cast's overrides
NARRATOR = ""


@dataclass
class Cast:
    narrator: VoiceChoice

    # speaker name -> VoiceChoice
    characters: Dict[str, VoiceChoice]

    # the VoiceChoice for speaker (None for the narrator), the narrator's
    # for a character not in the cast
    def voiceFor(self, speaker: Optional[str]) -> VoiceChoice:
        if speaker is None:
            return self.narrator

        return self.characters.get(speaker, self.narrator)


# the factors the voices' rates are multiplied by, for each round of
# giving out the voices
RATE_FACTORS = [1.0, 1.2, 0.85, 1.4, 0.75]


# voices: speech.Voices (anything with .id, .language and .gender), the
# narrator's (the system default) first. names: the characters, the most
# important first (see characters()). genders: name -> "male" / "female"
# for the characters whose gender is known. baseRate: the voices' normal
# rate. overrides: name (NARRATOR for the narrator) -> VoiceChoice.
def assignVoices(
    voices,
    names: List[str],
    genders: Optional[Dict[str, str]] = None,
    baseRate: int = 175,
    overrides: Optional[Dict[str, VoiceChoice]] = None,
) -> Cast:
    genders = genders or {}
    overrides = overrides or {}

    if not voices:
        # the engine's default voice, at different rates
        voices = [_NoVoice()]

    # only the voices that speak the narrator's language, if it's known
    lang = (voices[0].language or "").split("-")[0].lower()

    if lang:
        same = [
            v for v in voices if (v.language or "").split("-")[0].lower() == lang
        ]
        voices = same or voices

    def rate(k):
        return int(round(baseRate * RATE_FACTORS[k % len(RATE_FACTORS)]))

    narrator = overrides.get(NARRATOR) or VoiceChoice(voices[0].id, rate(0))

    # (voice index, rate round) -> how many have it. the narrator's counts
    # double, so that it's the last one shared.
    used = Counter()
    used[(0, 0)] = 2

    cast = {}

    for name in names:
        if name in overrides:
            cast[name] = overrides[name]
            continue

        gender = genders.get(name)
        pool = [i for i, v in enumerate(voices) if gender and (v.gender == gender)]
        pool = pool or list(range(len(voices)))

        # the least used of the pool's voices, in the earliest round, the
        # voices in each round starting after the narrator's
        slots = [
            (k, i)
            for k in range(len(RATE_FACTORS))
            for i in sorted(pool, key=lambda i: (i == 0, i))
        ]
        k, i = min(slots, key=lambda s: (used[(s[1], s[0])], s[0]))

        used[(i, k)] += 1
        cast[name] = VoiceChoice(voices[i].id, rate(k))

    return Cast(narrator, cast)


# a stand-in for when an engine has no voices to choose from: its default
# voice
class _NoVoice:
    id = None
    language = ""
    gender = None


# words in a character's name that say their gender
GENDER_WORDS = {
    "male": (
        "mr mister sir lord king prince duke father dad daddy papa pa son "
        "brother uncle grandpa grandfather nephew husband boyfriend man men "
        "boy guy gentleman monk priest waiter actor policeman fireman "
        "businessman salesman"
    ).split(),
    "female": (
        "mrs ms miss madam madame lady queen princess duchess mother mom "
        "mommy mum mummy mama ma daughter sister aunt grandma grandmother "
        "niece wife girlfriend woman women girl gal nun waitress actress "
        "policewoman businesswoman saleswoman"
    ).split(),
}


# {name: (male count, female count)} from the name database
# (trelby/names.txt, whose "M name" / "F name" lines are names of each
# gender, of many nationalities)
def parseNameGenders(s) -> Dict[str, tuple]:
    counts = {}

    for line in s.splitlines():
        if line[:1] in ("M", "F"):
            name = line[1:].strip().upper()

            if name:
                m, f = counts.get(name, (0, 0))
                counts[name] = (m + 1, f) if line[0] == "M" else (m, f + 1)

    return counts


# the gender of the character called name: from a word in it like "MRS."
# or "WAITRESS", else from its first name in nameGenders (see
# parseNameGenders) if that's mostly used for one gender. None if it can't
# be told.
def guessGender(name, nameGenders=None) -> Optional[str]:
    words = [w for w in re.split(r"[^\w']+", name.lower()) if w]

    for w in words:
        for gender, gw in GENDER_WORDS.items():
            if w in gw:
                return gender

        # "fisherman", "chairwoman"
        if w.endswith(("woman", "women")):
            return "female"
        elif w.endswith(("man", "men")) and (len(w) > 4):
            return "male"

    # the first word that's a name, skipping e.g. a "DR."
    for w in words:
        m, f = (nameGenders or {}).get(w.upper(), (0, 0))

        if m or f:
            if m > 2 * f:
                return "male"
            elif f > 2 * m:
                return "female"

            return None

    return None
