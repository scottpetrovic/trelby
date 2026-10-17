import pytest

import tests.u as u
import trelby.screenplay as screenplay
import trelby.screenplay.speeches as speeches
import trelby.screenplay.tableread as tableread
import trelby.translations as translations
from trelby.screenplay.tableread import ReadOptions, VoiceChoice

_ = translations.trelby_translations_load()

SCRIPT = "\n".join(
    [
        "#Version 3",
        "#Start-Script ",
        "./FADE IN:",
        ".\\INT. KITCHEN - NIGHT",
        ">.Bob makes coffee -- badly. The machine hisses and spits all over",
        "..the counter.",
        "._BOB",
        ".((to himself)",
        ".:Not again.",
        "..He drinks it.",
        "._ANN (V.O.)",
        ">:Bob? Are you up? It's three in the",
        ".:morning.",
        "._BOB",
        ".:Coming.",
        "..He goes.",
        ".:Nobody said this.",
        ".:   ",
        "./CUT TO:",
        ".@END OF ACT ONE",
    ]
)


def load():
    return u.loadString(SCRIPT)


def summary(utts):
    return [(u.start, u.end, u.speaker, u.text) for u in utts]


def testUtterances():
    sp = load()

    assert summary(tableread.utterances(sp)) == [
        (0, 0, None, "Fade in."),
        (1, 1, None, "Interior. kitchen, night"),
        # the element's lines joined
        (
            2,
            3,
            None,
            "Bob makes coffee, badly. The machine hisses and spits all over"
            " the counter.",
        ),
        # no character name or parenthetical
        (6, 6, "BOB", "Not again."),
        (7, 7, None, "He drinks it."),
        # without the "(V.O.)"
        (9, 10, "ANN", "Bob? Are you up? It's three in the morning."),
        (12, 12, "BOB", "Coming."),
        (13, 13, None, "He goes."),
        # dialogue with no speaker is the narrator's, and the empty one
        # after it isn't read
        (14, 14, None, "Nobody said this."),
        (16, 16, None, "Cut to."),
        (17, 17, None, "End of act one"),
    ]


def testOptions():
    sp = load()

    utts = tableread.utterances(
        sp, ReadOptions(parentheticals=True, characterNames=True)
    )
    got = summary(utts)

    assert got[3:6] == [
        (4, 4, None, "BOB"),
        (5, 5, None, "(to himself)"),
        (6, 6, "BOB", "Not again."),
    ]
    assert (8, 8, None, "ANN (V.O.)") in got

    utts = tableread.utterances(sp, ReadOptions(narration=False))

    assert [u.start for u in utts] == [6, 9, 12, 14]


# the speakers are the speeches' (see speeches.py), so the reports and the
# table read agree on who speaks
def testSpeakersAgreeWithSpeeches():
    sp = u.load("reports/edge.trelby")
    utts = tableread.utterances(sp)
    lines = {}

    for s in speeches.iterSpeeches(sp):
        for i in s.dialogue:
            lines[i] = s.name

    for ut in utts:
        if ut.lt == screenplay.DIALOGUE:
            assert ut.speaker == lines.get(ut.start)

    assert {ut.speaker for ut in utts} - {None} == {
        "NARRATOR",
        "BOB",
        "DR. JOHN SMITH",
        "ANN",
    }


@pytest.mark.parametrize(
    "lt, text, said",
    [
        (screenplay.SCENE, "INT. HOUSE - DAY", "Interior. house, day"),
        (screenplay.SCENE, "ext. road -- night", "Exterior. road, night"),
        (screenplay.SCENE, "INT./EXT. CAR - DAY", "Interior, exterior. car, day"),
        (screenplay.SCENE, "I/E CAR", "Interior, exterior. car"),
        (screenplay.SCENE, "INTERVIEW ROOM", "Interview room"),
        (screenplay.SCENE, "EXT.", "Exterior."),
        (screenplay.TRANSITION, "DISSOLVE TO:", "Dissolve to."),
        (screenplay.ACTION, "She waits.  And  waits.", "She waits. And waits."),
        (screenplay.DIALOGUE, "Well--I mean...", "Well, I mean..."),
        (screenplay.ACTION, "  ...  ", ""),
        (screenplay.TRANSITION, "--", ""),
    ],
)
def testSpokenText(lt, text, said):
    assert tableread.spokenText(lt, text) == said


def testIndexAt():
    sp = load()
    utts = tableread.utterances(sp)

    assert tableread.indexAt(utts, 0) == 0

    # in the middle of an element: that element
    assert utts[tableread.indexAt(utts, 3)].start == 2

    # a character name or parenthetical: the dialogue after it
    assert utts[tableread.indexAt(utts, 4)].text == "Not again."
    assert utts[tableread.indexAt(utts, 5)].text == "Not again."

    assert tableread.indexAt(utts, len(sp.lines) - 1) == len(utts) - 1
    assert tableread.indexAt(utts, len(sp.lines)) is None
    assert tableread.indexAt([], 0) is None


def testSampleText():
    utts = tableread.utterances(load())

    # sentences up to minLen
    assert tableread.sampleText(utts, "ANN") == (
        "Bob? Are you up? It's three in the morning."
    )
    assert tableread.sampleText(utts, "ANN", minLen=4) == "Bob?"
    # a short utterance is all there is
    assert tableread.sampleText(utts, None) == "Fade in."
    assert tableread.sampleText(utts, "BOB", maxLen=8) == "Not..."
    assert tableread.sampleText(utts, "NOBODY") is None


def testCharacters():
    # BOB speaks twice, ANN once
    assert tableread.characters(load()) == ["BOB", "ANN"]

    # equal counts: in the order they first speak
    sp = u.loadString(
        "#Version 3\n#Start-Script \n._ZED\n.:One.\n._AMY\n.:Two.\n"
    )

    assert tableread.characters(sp) == ["ZED", "AMY"]


class Voice:
    def __init__(self, id, gender=None, language="en-US"):
        self.id = id
        self.gender = gender
        self.language = language


DAVID = Voice("david", "male")
ZIRA = Voice("zira", "female")


def testAssignVoicesByGender():
    names = ["JASON", "SARAH", "KEVIN", "KID", "MOM"]
    genders = {"JASON": "male", "SARAH": "female", "KEVIN": "male", "MOM": "female"}

    cast = tableread.assignVoices([DAVID, ZIRA], names, genders, 160)

    assert cast.narrator == VoiceChoice("david", 160)
    assert cast.characters == {
        # the narrator's voice, but faster
        "JASON": VoiceChoice("david", 192),
        "SARAH": VoiceChoice("zira", 160),
        "KEVIN": VoiceChoice("david", 136),
        # unknown: the next free one, the narrator's voice last
        "KID": VoiceChoice("zira", 192),
        "MOM": VoiceChoice("zira", 136),
    }

    assert cast.voiceFor(None) == cast.narrator
    assert cast.voiceFor("SARAH") == VoiceChoice("zira", 160)
    assert cast.voiceFor("NOT IN THE CAST") == cast.narrator


def testAssignVoicesIsDeterministic():
    names = ["C%d" % i for i in range(30)]
    voices = [DAVID, ZIRA, Voice("mark", "male")]

    a = tableread.assignVoices(voices, names)
    b = tableread.assignVoices(voices, names)

    assert a == b


def testAssignVoicesSpreadsOut():
    voices = [DAVID, ZIRA, Voice("mark", "male")]
    names = ["C%d" % i for i in range(len(voices) * len(tableread.RATE_FACTORS))]

    cast = tableread.assignVoices(voices, names, baseRate=100)
    choices = list(cast.characters.values())

    # the first ones each get a voice of their own, none the narrator's
    assert [c.voiceId for c in choices[:2]] == ["zira", "mark"]
    assert cast.narrator not in choices[:14]

    # every voice and rate is used once before any is used twice, and the
    # narrator's is shared last
    assert len(set(choices[:14])) == 14

    cast = tableread.assignVoices(voices, names * 2, baseRate=100)
    choices = list(cast.characters.values())

    assert choices[14] == choices[0]
    assert cast.narrator not in choices[:28]


def testAssignVoicesLanguage():
    voices = [DAVID, Voice("hans", "male", "de-DE"), ZIRA]

    cast = tableread.assignVoices(voices, ["A", "B", "C"])

    assert "hans" not in {c.voiceId for c in cast.characters.values()}

    # none of the narrator's language: all are used
    cast = tableread.assignVoices([Voice("x", language=""), Voice("y", language="fr")], ["A"])

    assert cast.characters["A"].voiceId == "y"


def testAssignVoicesNoVoices():
    cast = tableread.assignVoices([], ["A", "B"], baseRate=100)

    assert cast.narrator == VoiceChoice(None, 100)
    assert cast.characters == {"A": VoiceChoice(None, 120), "B": VoiceChoice(None, 85)}


def testAssignVoicesOverrides():
    overrides = {
        tableread.NARRATOR: VoiceChoice("zira", 150),
        "BOB": VoiceChoice("zira", 170),
    }

    cast = tableread.assignVoices([DAVID, ZIRA], ["BOB", "ANN"], baseRate=160, overrides=overrides)

    assert cast.narrator == VoiceChoice("zira", 150)
    assert cast.characters["BOB"] == VoiceChoice("zira", 170)

    # the voice no one has been given
    assert cast.characters["ANN"] == VoiceChoice("david", 160)

    # a choice of a voice that isn't there takes no slot
    cast = tableread.assignVoices(
        [DAVID, ZIRA],
        ["BOB", "ANN"],
        baseRate=160,
        overrides={"BOB": VoiceChoice("gone", 160)},
    )

    assert cast.characters["ANN"] == VoiceChoice("zira", 160)


# the voices chosen by hand are saved with the script
def testVoiceSettings():
    sp = load()

    assert not sp.readAloud.hasInfo()
    assert "Read-Aloud" not in sp.save().decode("utf-8")

    zira = r"HKEY\Voices\Zira"
    sp.readAloud.choices = {
        tableread.NARRATOR: VoiceChoice(zira, 150),
        "ANN (V.O.)": VoiceChoice(None, 200),
    }

    sp2 = u.loadString(sp.save().decode("utf-8").lstrip("﻿"))

    assert sp2.readAloud == sp.readAloud
    assert sp2.readAloud.usableChoices([DAVID, Voice(zira)]) == {
        tableread.NARRATOR: VoiceChoice(zira, 150)
    }

    # damaged entries are left out
    vs = tableread.VoiceSettings()
    vs.load(
        "Voices:3\nVoice/1/Name:A\nVoice/1/Rate:x\nVoice/2/Rate:100\n"
        "Voice/3/Name:C\nVoice/3/Id:v\nVoice/3/Rate:120\n"
    )

    assert vs.choices == {"C": VoiceChoice("v", 120)}


NAMES = """# comment
NEnglish
MJohn
MJohn
FMary
FJordan
NAmerican
MJordan
FMary
"""


def testGuessGender():
    ng = tableread.parseNameGenders(NAMES)

    assert ng == {"JOHN": (2, 0), "MARY": (0, 2), "JORDAN": (1, 1)}

    assert tableread.guessGender("JOHN", ng) == "male"
    assert tableread.guessGender("MARY (V.O.)", ng) == "female"
    assert tableread.guessGender("DR. JOHN SMITH", ng) == "male"
    assert tableread.guessGender("JORDAN", ng) is None
    assert tableread.guessGender("MRS. JORDAN", ng) == "female"
    assert tableread.guessGender("OLD MAN", ng) == "male"
    assert tableread.guessGender("FISHERMAN #2", ng) == "male"
    assert tableread.guessGender("CHAIRWOMAN", ng) == "female"
    assert tableread.guessGender("WAITRESS", ng) == "female"
    assert tableread.guessGender("ROBOT", ng) is None
    assert tableread.guessGender("JOHN") is None
