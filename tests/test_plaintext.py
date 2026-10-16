import os

import tests.u as u
import trelby.screenplay as screenplay
import trelby.screenplay.plaintext as plaintext
import trelby.translations as translations
from trelby.screenplay.line import Line

_ = translations.trelby_translations_load()

# copying to and pasting from the system clipboard (Edit / Copy (system),
# Paste (system))


def lines():
    return [
        Line(screenplay.LB_LAST, screenplay.SCENE, "Int. Kitchen - day"),
        Line(screenplay.LB_SPACE, screenplay.ACTION, "Bob opens the"),
        Line(screenplay.LB_LAST, screenplay.ACTION, "fridge."),
        Line(screenplay.LB_LAST, screenplay.CHARACTER, "Bob"),
        Line(screenplay.LB_LAST, screenplay.DIALOGUE, "Empty."),
    ]


def testLinesToText():
    sp = u.new()
    s = plaintext.linesToText(lines(), sp.cfgGl, False)

    # scene headings and character names are exported in capitals
    assert s.split(os.linesep) == [
        "INT. KITCHEN - DAY",
        "Bob opens the fridge.",
        "BOB",
        "Empty.",
        "",
    ]


def testLinesToFormattedText():
    sp = u.new()
    s = plaintext.linesToText(lines(), sp.cfgGl, True)
    rows = [r.strip() for r in s.split("\n") if r.strip()]

    # laid out line by line, as on the page
    assert rows == [
        "INT. KITCHEN - DAY",
        "Bob opens the",
        "fridge.",
        "BOB",
        "Empty.",
    ]


def testTextToLines():
    ls = plaintext.textToLines("Łódź\x85\xad €\r\nčapek​ Пётр\tΩ\r\n\r\n")

    assert [ln.text for ln in ls] == ["Łódź €", "čapek Пётр|Ω"]
    assert all(ln.lt == screenplay.ACTION for ln in ls)
    assert all(ln.lb == screenplay.LB_LAST for ln in ls)


# empty lines are dropped, so there may be nothing left to paste
def testTextToLinesEmpty():
    assert plaintext.textToLines("") == []
    assert plaintext.textToLines("\r\n\n​") == []
