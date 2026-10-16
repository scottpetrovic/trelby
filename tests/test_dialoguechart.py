import tests.u as u
import trelby.dialoguechart as dialoguechart
import trelby.pml as pml
import trelby.screenplay as screenplay
import trelby.translations as translations

_ = translations.trelby_translations_load()


def chars(cinfo):
    return {ci.name: (ci.firstPage, ci.lastPage, ci.lineCnt) for ci in cinfo}


def testData():
    sp = u.load("reports/edge.trelby")
    chart = dialoguechart.DialogueChart(sp)

    # the speakers are those of screenplay.speeches: dialogue with no
    # character before it isn't counted
    assert chars(chart.cinfo) == {
        "ANN": (1, 1, 1),
        "BOB": (0, 1, 4),
        "DR. JOHN SMITH": (1, 1, 1),
        "NARRATOR": (0, 0, 1),
    }

    assert [pi.label for pi in chart.pages] == ["1", "2"]
    assert chart.pages[1].speakers == {"ANN": 1, "BOB": 2, "DR. JOHN SMITH": 1}

    # the page content bars count every dialogue line
    assert chart.pages[1].getLineCount(screenplay.DIALOGUE) == 5

    assert chars(chart.getChars(3)).keys() == {"BOB"}


def testSorts():
    sp = u.load("reports/edge.trelby")
    chart = dialoguechart.DialogueChart(sp)

    def names(sort):
        return [ci.name for ci in chart.getChars(sort=sort)]

    # first page, then last page descending, then lines descending
    assert names("first") == ["BOB", "NARRATOR", "ANN", "DR. JOHN SMITH"]
    assert names("last") == ["NARRATOR", "ANN", "BOB", "DR. JOHN SMITH"]
    assert names("count") == ["BOB", "NARRATOR", "ANN", "DR. JOHN SMITH"]
    assert names("name") == ["ANN", "BOB", "DR. JOHN SMITH", "NARRATOR"]


def testDoc():
    sp = u.load("reports/edge.trelby")
    chart = dialoguechart.DialogueChart(sp)
    sorts = [name for name, label, key in dialoguechart.SORTS]

    doc = dialoguechart.generateDoc(chart, sp.cfg, sorts)

    # landscape, with a page for each sort order, titled by it
    assert (doc.w, doc.h) == (sp.cfg.paperHeight, sp.cfg.paperWidth)
    assert [pg.ops[0].text for pg in doc.pages] == [
        label() for name, label, key in dialoguechart.SORTS
    ]

    # a row for each character, and their names in the sort order
    texts = [op.text for op in doc.pages[3].ops if isinstance(op, pml.TextOp)]
    assert texts[-4:] == ["ANN", "BOB", "DR. JOHN SMITH", "NARRATOR"]

    # nothing to show
    assert dialoguechart.generateDoc(chart, sp.cfg, sorts, 10) is None


def testNoDialogue():
    sp = u.loadString("#Version 3\n#Start-Script \n..Just action.")
    chart = dialoguechart.DialogueChart(sp)

    assert chart.cinfo == []
    assert dialoguechart.generateDoc(chart, sp.cfg, ["first"]) is None
