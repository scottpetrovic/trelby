import tests.u as u
import trelby.dialoguechart as dialoguechart
import trelby.screenplay as screenplay
import trelby.translations as translations

_ = translations.trelby_translations_load()


def chars(chart):
    return {ci.name: (ci.firstPage, ci.lastPage, ci.lineCnt) for ci in chart.cinfo}


def testData():
    sp = u.load("reports/edge.trelby")
    chart = dialoguechart.DialogueChart(sp, 1)

    # every dialogue line is counted: lines with no character right
    # before them (skipping parentheticals) are spoken by "UNKNOWN", and
    # a two-line name is its last line
    assert chars(chart) == {
        "": (0, 0, 1),
        "ANN": (1, 1, 1),
        "BOB": (0, 1, 3),
        "NARRATOR": (0, 0, 1),
        "SMITH": (1, 1, 1),
        "UNKNOWN": (0, 1, 3),
    }

    assert len(chart.pages) == 2
    assert chart.pages[1].speakers == {"ANN": 1, "BOB": 1, "SMITH": 1, "UNKNOWN": 1}
    assert chart.pages[1].getLineCount(screenplay.DIALOGUE) == 4

    assert chars(dialoguechart.DialogueChart(sp, 3)).keys() == {"BOB", "UNKNOWN"}


def testNoDialogue():
    sp = u.loadString("#Version 3\n#Start-Script \n..Just action.")
    chart = dialoguechart.DialogueChart(sp, 1)

    assert chart.cinfo == []
