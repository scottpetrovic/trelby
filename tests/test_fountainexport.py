import tests.u as u
import trelby.screenplay.export as export
import trelby.screenplay.titles as titles
import trelby.translations as translations

_ = translations.trelby_translations_load()


def titleLines(s):
    # the title page is everything before the first blank line
    return s.split("\n\n")[0].split("\n")


def scriptWithTitles(*strings):
    sp = u.new()
    page = [titles.TitleString(["MY SCRIPT"], y=80.0, isBold=True)]
    for i, items in enumerate(strings):
        page.append(titles.TitleString(items, y=100.0 + i * 10))
    sp.titles.pages = [page]

    return sp


# the fixture has "by" and the author as separate title strings
def testLoneByTakesAuthorFromNextString():
    lines = titleLines(export.generateFountain(u.load()))

    assert lines[0] == "Title: THE KOALA INCIDENT"
    assert lines[1] == "Author: Anonymous Person"
    assert "Contact: Anonymous Person" not in lines
    assert "Contact: Sample script for Trelby." in lines
    assert "Contact: All rights reserved." in lines


# Trelby's default title page: "by", blank line, author in one string
def testByAndAuthorInOneString():
    sp = u.new()
    sp.titles.addDefaults()
    lines = titleLines(export.generateFountain(sp))

    assert lines[0] == "Title: UNTITLED SCREENPLAY"
    assert lines[1] == "Author: My Name Here"
    assert "Contact: My Name Here" not in lines


def testByAndAuthorWithoutBlankLine():
    lines = titleLines(export.generateFountain(scriptWithTitles(["by", "Jane Doe"])))

    assert lines[1] == "Author: Jane Doe"


def testMultipleAuthors():
    sp = scriptWithTitles(["by", "", "Jane Doe", "John Doe"])
    lines = titleLines(export.generateFountain(sp))

    assert lines[1:4] == ["Author:", "    Jane Doe", "    John Doe"]


def testLoneByAsLastString():
    lines = titleLines(export.generateFountain(scriptWithTitles(["by"])))

    assert lines == ["Title: MY SCRIPT"]


# keys must start with a letter; "[A-za-z]" used to accept "[", "_" etc.
def testKeyMustStartWithLetter():
    sp = scriptWithTitles(["Draft: 2"], ["[Revised]: today"])
    lines = titleLines(export.generateFountain(sp))

    assert "Draft: 2" in lines
    assert "Contact: [Revised]: today" in lines
