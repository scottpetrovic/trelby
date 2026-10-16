import tests.u as u
import trelby.screenplay.speeches as speeches
import trelby.translations as translations

_ = translations.trelby_translations_load()

# the speeches in tests/fixtures/reports/edge.trelby, which has the cases
# the reports treat differently


def texts(sp, lines):
    return [sp.lines[i].text for i in lines]


def testSpeeches():
    sp = u.load("reports/edge.trelby")
    ls = sp.lines
    got = list(speeches.iterSpeeches(sp))

    assert [s.name for s in got] == [
        "NARRATOR",
        "BOB",
        None,  # after an action line
        "",  # an empty character element
        "ANN",  # only a parenthetical
        None,  # after a scene heading
        None,  # after an act break
        "BOB",
        "SMITH",  # the last line of a two-line name
        "ANN",  # upper cased
    ]

    bob = got[1]
    assert texts(sp, bob.parens) == ["(quietly)"]
    assert texts(sp, bob.dialogue) == ["Hello there.", "And again."]
    assert (bob.start, bob.end) == (bob.parens[0], bob.dialogue[-1])
    assert ls[bob.charLine].text == "BOB"
    assert speeches.sceneName(sp, bob.scene) == "INT. ROOM - DAY"

    assert got[0].scene is None
    assert got[2].charLine is None
    assert got[4].dialogue == []

    # act breaks don't end a scene
    assert speeches.sceneName(sp, got[7].scene) == "INT. HALL - NIGHT"

    assert ls[got[8].charLine].text == "DR. JOHN"


def testEmpty():
    sp = u.new()

    assert list(speeches.iterSpeeches(sp)) == []
