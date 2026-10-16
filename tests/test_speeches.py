import pytest

import tests.u as u
import trelby.reports.characterreport as characterreport
import trelby.reports.dialoguechart as dialoguechart
import trelby.mcpserver.tools as mcptools
import trelby.reports.scenereport as scenereport
import trelby.screenplay as screenplay
import trelby.screenplay.speeches as speeches
import trelby.reports.scriptreport as scriptreport
import trelby.translations as translations

_ = translations.trelby_translations_load()

# the speeches in tests/fixtures/reports/edge.trelby, which has the cases
# the reports used to count differently


def texts(sp, lines):
    return [sp.lines[i].text for i in lines]


def testSpeeches():
    sp = u.load("reports/edge.trelby")
    ls = sp.lines
    got = list(speeches.iterSpeeches(sp))

    # left out: dialogue after an action line, after an empty character
    # name, after a scene heading and after an act break, and a speech
    # that's only a parenthetical
    assert [s.name for s in got] == [
        "NARRATOR",
        "BOB",
        "BOB",
        "DR. JOHN SMITH",  # a two-line name
        "ANN",  # upper cased
        "BOB",  # without the "(CONT'D)"
    ]

    bob = got[1]
    assert texts(sp, bob.parens) == ["(quietly)"]
    assert texts(sp, bob.dialogue) == ["Hello there.", "And again."]
    assert (bob.start, bob.end) == (bob.parens[0], bob.dialogue[-1])
    assert ls[bob.charLine].text == "BOB"
    assert speeches.sceneName(sp, bob.scene) == "INT. ROOM - DAY"

    assert got[0].scene is None
    assert ls[got[3].charLine].text == "DR. JOHN"

    # a scene starting at an act break has no name
    assert ls[got[2].scene].text == "ACT TWO"
    assert speeches.sceneName(sp, got[2].scene) == "(NO SCENE NAME)"
    assert speeches.sceneName(sp, None) == "(NO SCENE NAME)"


def testSceneName():
    sp = u.loadString("#Version 3\n#Start-Script \n.\\ \n..Action.")

    assert speeches.sceneName(sp, 0) == "(EMPTY SCENE NAME)"


def testEmpty():
    sp = u.new()

    assert list(speeches.iterSpeeches(sp)) == []


# the reports, the dialogue chart and the MCP tools count the same
# characters, speeches and lines
@pytest.mark.parametrize("name", ["test.trelby", "reports/edge.trelby"])
def testAllAgree(name):
    sp = u.load(name)
    ed = screenplay.Editor(sp)

    cr = characterreport.CharacterReport(sp)
    lines = {ci.name: ci.lineCnt for ci in cr.cinfo}
    speechCnt = {ci.name: ci.speechCnt for ci in cr.cinfo}

    chart = dialoguechart.DialogueChart(sp)
    assert {ci.name: ci.lineCnt for ci in chart.cinfo} == lines

    sceneLines = {}
    for si in scenereport.SceneReport(sp).scenes:
        for n, cnt in si.chars.items():
            sceneLines[n] = sceneLines.get(n, 0) + cnt
    assert sceneLines == lines

    assert scriptreport.ScriptReport(sp).speakers == lines.keys()

    doc = mcptools.LiveDoc(ed)
    assert mcptools.getInfo(doc)["characters"] == len(lines)

    mcpChars = mcptools.listCharacters(doc)["characters"]
    assert {c["name"]: c["speeches"] for c in mcpChars} == speechCnt
