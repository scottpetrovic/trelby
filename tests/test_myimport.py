import os

import tests.u as u
import trelby.importers as importers
import trelby.screenplay as screenplay
import trelby.screenplay.export as export
import trelby.translations as translations
from trelby.screenplay.line import Line

_ = translations.trelby_translations_load()


def testImportCeltx() -> None:
    u.init()
    location = os.path.dirname(__file__)
    pathToTestScriptCeltx = os.path.join(location, "fixtures/test.celtx")

    with open(pathToTestScriptCeltx, "rb") as f:
        importedLines = importers.celtx.parse(f.read()).lines

    # in order to compare the screenplays, we need to reformat it with the same configuration as the loaded one
    importedScreenplay = u.new()
    importedScreenplay.lines = importedLines
    importedScreenplay.reformatAll()

    expectedScreenplay = u.load()

    for line, expectedLine in zip(importedScreenplay.lines, expectedScreenplay.lines):
        assert line == expectedLine


def testImportTextFile() -> None:
    u.init()
    location = os.path.dirname(__file__)
    pathToTestScriptTxt = os.path.join(location, "fixtures/test.txt")

    # with the guessed line types
    with open(pathToTestScriptTxt, encoding="UTF-8") as f:
        lines = importers.text.parse(f.read()).lines

    expectedScreenplay = u.load()
    for line, expectedLine in zip(lines, expectedScreenplay.lines):
        assert TextImportMatcher(line) == TextImportMatcher(expectedLine)


# return the dual dialogue blocks in imported lines, as lists of the
# character names in them
def importedDuals(lines):
    sp = u.new()
    sp.lines = lines
    sp.reformatAll()

    blocks = {
        sp.getDualBlock(i)
        for i, ln in enumerate(sp.lines)
        if ln.lt == screenplay.CHARACTER and sp.getDualBlock(i)
    }

    return sorted(
        [sp.lines[first].text, sp.lines[right].text] for first, right, last in blocks
    )


def dualScript():
    import tests.test_dualdialogue as dd

    return dd.makeScript()


def testImportFDXDualDialogue(tmp_path) -> None:
    path = tmp_path / "dual.fdx"
    path.write_bytes(export.generateFDX(dualScript().sp))

    lines = importers.fdx.parse(path.read_text(encoding="UTF-8")).lines

    assert importedDuals(lines) == [["BRICK", "STEEL"]]


def testImportFountainDualDialogue(tmp_path) -> None:
    path = tmp_path / "dual.fountain"
    path.write_text(export.generateFountain(dualScript().sp), encoding="UTF-8")

    lines = importers.fountain.parse(path.read_text(encoding="UTF-8")).lines

    assert importedDuals(lines) == [["BRICK", "STEEL"]]
    assert "^" not in "".join(ln.text for ln in lines)


class TextImportMatcher:
    line: Line

    def __init__(self, line: Line):
        self.line = line

    def __eq__(self, other):
        """
        The text import has some known limitations:
            - depending on the export config, some lines are all caps, so it can't reliably preserve case
            - it can't reliably detect linebreak types
            - sometimes, it can't distinguish ACTION from SCENE types
        That's why this implementation is not so hard on it, and only compares the text case-insensitively, doesn't
        compare linebreak types at all and only compares the line type if it's not ACTION or SCENE
        """
        if not isinstance(other, TextImportMatcher):
            return NotImplemented
        if self.line.text.lower() != other.line.text.lower():
            return False
        if (
            self.line.lt != screenplay.ACTION
            and self.line.lt != screenplay.SCENE
            and self.line.lt != other.line.lt
        ):
            return False
        return True

    def __repr__(self) -> str:
        return self.line.__str__()
