import copy

import pytest

import tests.u as u
import trelby.mcpserver.tools as mcptools
import trelby.screenplay as scr
import trelby.screenplay.fileformat as fileformat
import trelby.translations as translations
from trelby.screenplay.alternates import Take, cleanText

_ = translations.trelby_translations_load()

# alternates (screenplay/alternates.py): the other takes of an element,
# switching between them, keeping them with their element through edits,
# the file format and the MCP tools

SCRIPT = [
    "#Version 3",
    "#Start-Script ",
    ".\\INT. KITCHEN - DAY",
    "..Mary cooks.",
    "._MARY",
    "#Alternate |Dinner.",
    "#Alternate 0-4:b|Food's on the table, come and get it before it all"
    " goes cold!",
    ".:Dinner's ready!",
    "._JOHN",
    ".:Coming.",
]

LONG = "Food's on the table, come and get it before it all goes cold!"


def load():
    return u.loadStringEditor("\n".join(SCRIPT))


def lineOf(ed, text):
    return next(i for i, ln in enumerate(ed.sp.lines) if ln.text.startswith(text))


def texts(takes):
    return [t.text for t in takes]


def shown(ed, line):
    return ed.sp.getShownTake(line).text


def testLoad():
    ed = load()
    dlg = lineOf(ed, "Dinner's")

    assert texts(ed.sp.lines[dlg].alternates) == ["Dinner.", LONG]
    assert ed.sp.lines[dlg].alternates[1].fmt == "1111" + "0" * (len(LONG) - 4)
    assert ed.sp.hasAlternates()
    ed._validate()


def testSaveRoundTrip():
    ed = load()
    dlg = lineOf(ed, "Dinner's")
    ed.sp.lines[dlg].alternates += (Take("Two\nparas | a bar \\ backslash"),)

    s = ed.sp.save().decode("utf-8-sig")

    assert "#Alternate |Dinner.\n" in s
    assert "#Alternate 0-4:b|Food's" in s
    assert "#Alternate |Two\\nparas | a bar \\\\ backslash\n" in s

    sp = u.loadString(s)
    assert sp.lines[dlg].alternates == ed.sp.lines[dlg].alternates


@pytest.mark.parametrize("value", ["", "|", "|   ", "no bar", "|\\n\\n"])
def testBadAlternateLinesAreIgnored(value):
    assert fileformat.parseTake(value) is None


def testCleanText():
    assert cleanText("  a\tb \n\n c \n\n") == "a b\n\nc"


def testShownTakeJoinsParagraphs():
    ed = u.loadStringEditor(
        "\n".join(
            [
                "#Version 3",
                "#Start-Script ",
                "._MARY",
                "#Format 0-2:i",
                "|:First paragraph,",
                ".:second.",
            ]
        )
    )

    take = ed.sp.getShownTake(1)
    assert take.text == "First paragraph,\nsecond."
    assert take.fmt.startswith("220")


def testAddAlternate():
    ed = load()
    dlg = lineOf(ed, "Dinner's")
    ed.line, ed.column = dlg, 3

    # the shown text is kept as a take, and stays shown
    assert ed.addAlternate(dlg) == 2
    assert texts(ed.sp.getAlternates(dlg)) == ["Dinner.", LONG, "Dinner's ready!"]
    assert shown(ed, dlg) == "Dinner's ready!"
    assert (ed.line, ed.column) == (dlg, 3)

    # but not twice
    assert ed.addAlternate(dlg) is None

    ed.cmd("undo")
    assert texts(ed.sp.getAlternates(dlg)) == ["Dinner.", LONG]

    ed.cmd("redo")
    assert len(ed.sp.getAlternates(dlg)) == 3
    ed._validate()


def testSwitchRotatesTakes():
    ed = load()
    dlg = lineOf(ed, "Dinner's")
    john = lineOf(ed, "JOHN")
    ed.line, ed.column = john, 2

    assert ed.switchAlternate(dlg, 1)

    # the long take is wrapped onto two lines, so John moves down, the
    # cursor with him
    assert shown(ed, dlg) == LONG
    assert ed.sp.lines[dlg].lb == scr.LB_SPACE
    assert ed.sp.lines[dlg].fmt.startswith("1111")
    assert texts(ed.sp.getAlternates(dlg)) == ["Dinner's ready!", "Dinner."]
    assert (ed.line, ed.column) == (john + 1, 2)
    assert ed.sp.lines[ed.line].text == "JOHN"
    ed._validate()

    ed.cmd("undo")
    assert shown(ed, dlg) == "Dinner's ready!"
    assert texts(ed.sp.getAlternates(dlg)) == ["Dinner.", LONG]
    assert (ed.line, ed.column) == (john, 2)
    ed._validate()

    ed.cmd("redo")
    assert shown(ed, dlg) == LONG
    ed._validate()


def testCycleGoesThroughAllTakes():
    ed = load()
    dlg = lineOf(ed, "Dinner's")
    ed.line, ed.column = dlg, 5

    seen = []

    for i in range(3):
        assert ed.cycleAlternate(dlg)
        seen.append(shown(ed, dlg))

        # the cursor was in the element, so it goes to its start
        assert (ed.line, ed.column) == (dlg, 0)

    assert seen == ["Dinner.", LONG, "Dinner's ready!"]
    assert texts(ed.sp.getAlternates(dlg)) == ["Dinner.", LONG]

    ed.cycleAlternate(dlg, -1)
    assert shown(ed, dlg) == LONG

    assert not ed.cycleAlternate(lineOf(ed, "JOHN"))
    ed._validate()


def testSetAndDeleteAlternate():
    ed = load()
    dlg = lineOf(ed, "Dinner's")

    assert ed.setAlternate(dlg, 0, Take("Supper."))
    assert not ed.setAlternate(dlg, 0, Take("Supper."))
    assert not ed.setAlternate(dlg, 0, Take(""))
    assert texts(ed.sp.getAlternates(dlg)) == ["Supper.", LONG]

    ed.deleteAlternate(dlg, 1)
    assert texts(ed.sp.getAlternates(dlg)) == ["Supper."]

    ed.cmd("undo")
    ed.cmd("undo")
    assert texts(ed.sp.getAlternates(dlg)) == ["Dinner.", LONG]
    ed._validate()


def testKeepAlternate():
    ed = load()
    dlg = lineOf(ed, "Dinner's")

    assert ed.keepAlternate(dlg, 0)
    assert shown(ed, dlg) == "Dinner."
    assert not ed.sp.hasAlternates()

    ed.cmd("undo")
    assert ed.keepAlternate(dlg)
    assert shown(ed, dlg) == "Dinner's ready!"
    assert not ed.sp.hasAlternates()
    ed._validate()


def testSetTakesWithParagraphs():
    ed = load()
    dlg = lineOf(ed, "Dinner's")

    assert ed.setTakes(dlg, Take("One.\nTwo."), [Take("Dinner's ready!")])

    assert ed.sp.lines[dlg].text == "One."
    assert ed.sp.lines[dlg].lb == scr.LB_FORCED
    assert ed.sp.lines[dlg + 1].text == "Two."
    assert ed.sp.lines[dlg + 1].lt == scr.DIALOGUE
    assert ed.sp.lines[dlg].alternates == (Take("Dinner's ready!"),)
    assert not ed.setTakes(dlg + 1, Take("One.\nTwo."), [Take("Dinner's ready!")])

    # and back, one paragraph again
    assert ed.switchAlternate(dlg + 1, 0)
    assert ed.sp.lines[dlg].text == "Dinner's ready!"
    assert ed.sp.lines[dlg].lb == scr.LB_LAST
    assert texts(ed.sp.getAlternates(dlg)) == ["One.\nTwo."]
    ed._validate()


def testSwitchKeepsNotesTagsAndDual():
    ed = load()
    dlg = lineOf(ed, "Dinner's")
    ed.addNote(dlg, "Too short?")
    ed.sp.lines[dlg - 1].dual = True

    ed.switchAlternate(dlg, 1)

    assert [n.text for n in ed.sp.lines[dlg].notes] == ["Too short?"]
    assert ed.sp.lines[dlg - 1].dual
    ed._validate()


def testSwitchKeepsPageLock():
    ed = load()
    dlg = lineOf(ed, "Dinner's")
    ed.sp.lines[dlg].pageLock = "2"

    ed.switchAlternate(dlg, 1)

    assert ed.sp.lines[dlg].pageLock == "2"
    assert not ed.sp.lines[dlg + 1].pageLock


def testTypingKeepsTakesOnFirstLine():
    ed = load()
    dlg = lineOf(ed, "Dinner's")
    ed.switchAlternate(dlg, 1)
    ed.line, ed.column = dlg, 0

    for ch in "Hey, everyone, ":
        ed.cmd("addChar", char=ch)

    assert len(ed.sp.lines[dlg].alternates) == 2
    assert not any(ln.alternates for ln in ed.sp.lines[dlg + 1 :])
    ed._validate()


def testJoiningKeepsBothsTakes():
    ed = load()
    john = lineOf(ed, "JOHN")
    ed.addAlternate(john, Take("JOHNNY"))
    ed.addAlternate(john + 1, Take("On my way."))

    # joining John's dialogue onto his name
    ed.line, ed.column = john + 1, 0
    ed.cmd("deleteBackward")

    assert ed.sp.lines[john].text == "JOHNComing."
    assert texts(ed.sp.getAlternates(john)) == ["JOHNNY", "On my way."]
    ed._validate()


def testSplittingLeavesTakesOnFirstPart():
    ed = load()
    dlg = lineOf(ed, "Dinner's")
    ed.line, ed.column = dlg, 9

    ed.cmd("splitElement")

    assert len(ed.sp.lines[dlg].alternates) == 2
    assert not ed.sp.getAlternates(ed.line)
    ed._validate()


@pytest.mark.parametrize("command", ["splitElement", "insertForcedLineBreak"])
def testSplittingAtStartMovesTakesWithText(command):
    ed = load()
    dlg = lineOf(ed, "Dinner's")
    ed.line, ed.column = dlg, 0

    ed.cmd(command)

    assert ed.sp.lines[dlg + 1].text == "Dinner's ready!"
    assert not ed.sp.lines[dlg].alternates
    assert len(ed.sp.lines[dlg + 1].alternates) == 2

    # with a forced line break, the takes are still the element's, and an
    # edit puts them back on its first line
    if command == "insertForcedLineBreak":
        assert len(ed.sp.getAlternates(dlg)) == 2
        ed.addAlternate(dlg)
        assert len(ed.sp.lines[dlg].alternates) == 3
        assert not ed.sp.lines[dlg + 1].alternates

    ed._validate()


def testTypeChangeKeepsTakes():
    ed = load()
    dlg = lineOf(ed, "Dinner's")
    ed.line, ed.column = dlg, 0

    ed.convertTypeTo(scr.ACTION, True)

    assert ed.sp.lines[dlg].lt == scr.ACTION
    assert len(ed.sp.lines[dlg].alternates) == 2
    ed._validate()


def testCutAndPasteMoveTakes():
    ed = load()
    dlg = lineOf(ed, "Dinner's")

    ed.selectElementAt(dlg)
    cd = ed.getSelectedAsCD(True)

    assert not ed.sp.hasAlternates()
    assert len(cd.lines[0].alternates) == 2

    ed.line, ed.column = 1, 0
    ed.paste(cd.lines)

    assert len(ed.sp.getAlternates(1)) == 2

    ed.cmd("undo")
    ed.cmd("undo")
    assert len(ed.sp.lines[dlg].alternates) == 2
    ed._validate()


def testDeletingPartOfElementKeepsTakes():
    ed = load()
    dlg = lineOf(ed, "Dinner's")
    ed.switchAlternate(dlg, 1)

    # all of the dialogue's first line, and some of the next
    ed.setMark(dlg + 1, 2)
    ed.line, ed.column = dlg, 0
    ed.getSelectedAsCD(True)

    assert len(ed.sp.lines[dlg].alternates) == 2
    ed._validate()


def testDeletingWholeElementDropsTakes():
    ed = load()
    dlg = lineOf(ed, "Dinner's")

    ed.setMark(dlg, len(ed.sp.lines[dlg].text) - 1)
    ed.line, ed.column = dlg, 0
    ed.getSelectedAsCD(True)

    assert not ed.sp.hasAlternates()
    ed._validate()


def testRevisionModeMarksSwitchedText():
    ed = load()
    dlg = lineOf(ed, "Dinner's")
    ed.sp.revisions.toggleActive()

    ed.switchAlternate(dlg, 0)

    assert ed.sp.lines[dlg].revs.strip("0")
    assert not ed.sp.lines[0].revs


def testDeepcopyKeepsTakes():
    ed = load()
    sp = copy.deepcopy(ed.sp)

    assert [ln.alternates for ln in sp.lines] == [ln.alternates for ln in ed.sp.lines]


def testRevisionNoticesTakes():
    ed = load()
    rev = mcptools.linesRevision(ed.sp)

    ed.deleteAlternate(lineOf(ed, "Dinner's"), 0)

    assert mcptools.linesRevision(ed.sp) != rev


# the MCP tools: elements' alternates


@pytest.fixture
def scriptFile(tmp_path):
    path = str(tmp_path / "kitchen.trelby")

    with open(path, "w", encoding="UTF-8") as f:
        f.write("\n".join(SCRIPT) + "\n")

    return path


def testMcpReadAndReplaceKeepTakes(scriptFile):
    doc = mcptools.FileDoc(scriptFile)
    res = mcptools.readScenes(doc, 1)
    elements = res["scenes"][0]["elements"]

    assert elements[3]["alternates"] == ["Dinner.", LONG]
    assert "alternates" not in elements[4]

    elements[5]["alternates"] = ["On my way.", "  ", "Two\nparagraphs."]

    mcptools.replaceScene(doc, res["revision"], 1, elements)

    sp = mcptools.FileDoc(scriptFile).read()[0]
    assert texts(sp.getAlternates(3)) == ["Dinner.", LONG]
    assert texts(sp.getAlternates(5)) == ["On my way.", "Two\nparagraphs."]


def testMcpBadTakes(scriptFile):
    doc = mcptools.FileDoc(scriptFile)
    rev = mcptools.listScenes(doc)["revision"]

    with pytest.raises(mcptools.ToolError) as e:
        mcptools.replaceScene(
            doc, rev, 1, [{"type": "scene", "text": "INT. A", "alternates": [5]}]
        )

    assert "alternates" in str(e.value)


# Final Draft's alternates: Alts in the paragraph, AltCollection after
# the content


def testFdxExport():
    from lxml import etree

    import trelby.screenplay.export as export

    ed = load()
    root = etree.fromstring(export.generateFDX(ed.sp))

    para = root.xpath("Content/Paragraph[Alts]")
    assert len(para) == 1
    assert para[0].xpath("Text")[0].text == "Dinner's ready!"

    alts = para[0].xpath("Alts")[0]
    assert alts.get("Current") == "0"
    assert [a.text for a in alts.xpath("AltId")] == ["1", "2"]

    coll = root.xpath("AltCollection/Alt")
    assert [a.get("Id") for a in coll] == ["1", "2"]
    assert coll[0].xpath("Paragraph/Text")[0].text == "Dinner."

    # the formatting is kept
    texts1 = coll[1].xpath("Paragraph/Text")
    assert [(t.text, t.get("Style")) for t in texts1] == [
        ("Food", "Bold"),
        (LONG[4:], None),
    ]


def testFdxExportWithoutAlternates():
    import trelby.screenplay.export as export

    ed = load()
    ed.keepAlternate(lineOf(ed, "Dinner's"))

    assert b"Alt" not in export.generateFDX(ed.sp)


def testFdxRoundTrip():
    import trelby.importers.fdx as fdximport
    import trelby.screenplay.export as export

    ed = load()
    lines = fdximport.parse(export.generateFDX(ed.sp).decode("UTF-8")).lines

    got = [(ln.text, ln.alternates) for ln in lines if ln.alternates]
    assert got == [("Dinner's ready!", ed.sp.getAlternates(lineOf(ed, "Dinner's")))]


def testFdxImportFinalDraftAlternates():
    import pathlib

    import trelby.importers.fdx as fdximport

    path = pathlib.Path("tests/fixtures/import/alternates.fdx")
    lines = fdximport.parse(path.read_text(encoding="UTF-8")).lines

    got = [(ln.text, texts(ln.alternates)) for ln in lines if ln.alternates]

    # Current is the shown take's place among them all: the ones after it
    # come first in Trelby, then the ones before it
    assert got == [
        ("Keep the light burning.", ["Light it.", "Don't let it go out."]),
        ("Always.", ["Every night.", "Yes.", "I will."]),
    ]

    assert lines[2].alternates[0].fmt == "111110000"
