import pytest

import tests.u as u
import trelby.importers.fdx as fdximport
import trelby.importers.fountain as fountainimport
import trelby.mcpserver.tools as mcptools
import trelby.screenplay as scr
import trelby.screenplay.export as export
import trelby.translations as translations
from trelby.screenplay.notes import Note

_ = translations.trelby_translations_load()

# notes on paragraphs (screenplay/notes.py): editing them, keeping them
# with their text through edits, the file format, the old note elements,
# and the exports and MCP tools

SCRIPT = [
    "#Version 3",
    "#Start-Script ",
    ".\\INT. KITCHEN - DAY",
    "#Note Remember the salt.",
    "..Mary cooks a long dinner for everyone she knows, stirring and tasting"
    " and stirring again until the whole house smells of it.",
    "#Note-Resolved Done.",
    "..John waits.",
    "._MARY",
    ".:Dinner's ready!",
]


def load():
    return u.loadStringEditor("\n".join(SCRIPT))


def lineOf(ed, text):
    return next(i for i, ln in enumerate(ed.sp.lines) if ln.text == text)


# (line, text, resolved) of every note
def allNotes(ed):
    return [(i, n.text, n.resolved) for i, k, n in ed.sp.getAllNotes()]


def testLoad():
    ed = load()
    john = lineOf(ed, "John waits.")

    assert allNotes(ed) == [(1, "Remember the salt.", False), (john, "Done.", True)]

    # the action is wrapped onto more than one line
    assert ed.sp.lines[1].lb == scr.LB_SPACE
    ed._validate()


def testSaveRoundTrip():
    ed = load()
    ed.sp.lines[1].notes = (Note("Two\nlines \\ and a backslash"), Note("x", True))

    s = ed.sp.save().decode("utf-8-sig")

    assert "#Note Two\\nlines \\\\ and a backslash\n" in s
    assert "#Note-Resolved x\n" in s

    sp = u.loadString(s)
    assert sp.lines[1].notes == ed.sp.lines[1].notes


def testAddSetDeleteUndo():
    ed = load()
    ed.line, ed.column = 2, 3

    # any line of the paragraph will do; the note goes on its first line
    assert ed.addNote(2, "Add pepper.") == 1
    assert [n.text for n in ed.sp.lines[1].notes] == [
        "Remember the salt.",
        "Add pepper.",
    ]
    assert not ed.sp.lines[2].notes

    assert ed.setNote(2, 1, Note("Add pepper.", True))
    assert not ed.setNote(2, 1, Note("Add pepper.", True))

    ed.deleteNote(1, 0)
    assert ed.sp.lines[1].notes == (Note("Add pepper.", True),)

    # the cursor stays put
    assert (ed.line, ed.column) == (2, 3)

    ed.cmd("undo")
    assert ed.sp.lines[1].notes == (
        Note("Remember the salt."),
        Note("Add pepper.", True),
    )

    ed.cmd("undo")
    ed.cmd("undo")
    assert ed.sp.lines[1].notes == (Note("Remember the salt."),)

    ed.cmd("redo")
    ed.cmd("redo")
    ed.cmd("redo")
    assert ed.sp.lines[1].notes == (Note("Add pepper.", True),)
    ed._validate()


def testTypingKeepsNoteOnFirstLine():
    ed = load()
    ed.line, ed.column = 1, 0

    for ch in "Slowly and with great care, ":
        ed.cmd("addChar", char=ch)

    assert ed.sp.lines[1].text.startswith("Slowly")
    assert allNotes(ed)[0] == (1, "Remember the salt.", False)

    ed._validate()


def testJoiningKeepsBothNotes():
    ed = load()
    ed.line, ed.column = lineOf(ed, "John waits."), 0

    ed.cmd("deleteBackward")

    assert [n.text for n in ed.sp.getParaNotes(1)] == ["Remember the salt.", "Done."]
    assert [i for i, t, r in allNotes(ed)] == [1, 1]
    ed._validate()


def testSplittingLeavesNoteOnFirstPart():
    ed = load()
    ed.line, ed.column = 1, 10

    ed.cmd("splitElement")

    assert ed.sp.lines[1].notes == (Note("Remember the salt."),)
    assert not ed.sp.lines[ed.line].notes
    ed._validate()


# a new paragraph made before one with notes, by splitting it at its start
# or pasting there, pushes its text down, and the notes go with it
@pytest.mark.parametrize("command", ["splitElement", "insertForcedLineBreak"])
def testSplittingAtStartMovesNoteWithText(command):
    ed = load()
    ed.line, ed.column = 1, 0

    ed.cmd(command)

    assert ed.sp.lines[2].text.startswith("Mary cooks")
    assert not ed.sp.lines[1].notes
    assert ed.sp.lines[2].notes == (Note("Remember the salt."),)
    ed._validate()

    ed.cmd("undo")
    assert ed.sp.lines[1].notes == (Note("Remember the salt."),)
    ed._validate()


def testPastingAtStartMovesNoteWithText():
    ed = load()
    john = lineOf(ed, "John waits.")

    ed.selectElementAt(john)
    cd = ed.getSelectedAsCD(False)
    ed.clearMark()

    # two paragraphs, the first with its own note
    lines = cd.lines + [ln.copy() for ln in cd.lines]
    lines[0].lb = scr.LB_LAST
    lines[1].notes = ()

    ed.line, ed.column = 1, 0
    ed.paste(lines)

    mary = next(i for i, ln in enumerate(ed.sp.lines) if ln.text.startswith("Mary"))
    assert mary == 3
    assert ed.sp.lines[1].text == "John waits."
    assert ed.sp.lines[1].notes == (Note("Done.", True),)
    assert ed.sp.lines[mary].notes == (Note("Remember the salt."),)
    ed._validate()


def testCutAndPasteMoveNotes():
    ed = load()

    ed.selectElementAt(1)
    cd = ed.getSelectedAsCD(True)

    assert "Remember the salt." not in [t for i, t, r in allNotes(ed)]
    assert cd.lines[0].notes == (Note("Remember the salt."),)

    # pasted at the end of the dialogue, the action joins its paragraph,
    # notes and all
    last = len(ed.sp.lines) - 1
    ed.line, ed.column = last, len(ed.sp.lines[last].text)
    ed.paste(cd.lines)

    dlg = ed.sp.getParaFirstIndexFromLine(len(ed.sp.lines) - 1)
    assert ed.sp.lines[dlg].lt == scr.DIALOGUE
    assert Note("Remember the salt.") in ed.sp.lines[dlg].notes

    ed.cmd("undo")
    ed.cmd("undo")
    assert ed.sp.lines[1].notes == (Note("Remember the salt."),)
    ed._validate()


def testDeletingPartOfParagraphKeepsNote():
    ed = load()

    # all of the paragraph's first line, and some of the next
    ed.setMark(2, 2)
    ed.line, ed.column = 1, 0
    ed.getSelectedAsCD(True)

    assert ed.sp.lines[1].notes == (Note("Remember the salt."),)
    ed._validate()


def testDeepcopyKeepsNotes():
    import copy

    ed = load()
    sp = copy.deepcopy(ed.sp)

    assert sp.getAllNotes() == ed.sp.getAllNotes()


OLD_SCRIPT = [
    "#Version 3",
    "#Start-Script ",
    ".%Opening note.",
    ".\\INT. HALL",
    "..Ann enters.",
    "|%First line",
    ".%second line",
    ".%",
    "._ANN",
    ".:Hi.",
]


def testOldNoteElementsBecomeNotes():
    sp = u.loadString("\n".join(OLD_SCRIPT))

    # a note before everything goes on the first element, the others on
    # the one before them; empty ones are dropped
    assert [ln.text for ln in sp.lines] == ["INT. HALL", "Ann enters.", "ANN", "Hi."]
    assert sp.lines[0].notes == (Note("Opening note."),)
    assert sp.lines[1].notes == (Note("First line\nsecond line"),)

    s = sp.save().decode("utf-8-sig")
    assert "%" not in s
    assert "#Note First line\\nsecond line\n" in s


def testOutlineSummaryIsFirstUnresolvedNote():
    ed = load()

    assert ed.sp.getOutline()[0].summary == "Remember the salt."

    ed.setNote(1, 0, Note("Remember the salt.", True))
    assert ed.sp.getOutline()[0].summary.startswith("Mary cooks")


def text(data):
    return data.decode("utf-8") if isinstance(data, bytes) else data


def importedNotes(result):
    return [(ln.text, n.text) for ln in result.lines for n in ln.notes]


def withSpeechNote():
    ed = load()
    ed.addNote(lineOf(ed, "Dinner's ready!"), "Too loud?")
    ed.sp.paginate()

    return ed.sp


def testFountainExportAndImport():
    sp = withSpeechNote()
    s = text(export.generateFountain(sp))

    assert "[[Remember the salt.]]" in s

    # the note on the dialogue waits until after the speech
    assert s.rstrip().endswith("Dinner's ready!\n\n[[Too loud?]]")

    notes = importedNotes(fountainimport.parse(s))
    assert [n for t, n in notes] == ["Remember the salt.", "Done.", "Too loud?"]
    assert notes[0][0].startswith("Mary cooks")


def testFDXExportAndImport():
    sp = withSpeechNote()
    s = text(export.generateFDX(sp))

    assert importedNotes(fdximport.parse(s)) == [
        (
            "Mary cooks a long dinner for everyone she knows, stirring and"
            " tasting and stirring again until the whole house smells of it.",
            "Remember the salt.",
        ),
        ("John waits.", "Done."),
        ("Dinner's ready!", "Too loud?"),
    ]


def testHtmlExport():
    sp = withSpeechNote()

    assert "Remember the salt." in export.generateHtml(sp, True)
    assert "Remember the salt." not in export.generateHtml(sp, False)


def testMCPReadAndWrite():
    doc = mcptools.LiveDoc(load())
    rev = mcptools.listScenes(doc)["revision"]
    elems = mcptools.readScenes(doc, 1)["scenes"][0]["elements"]

    assert elems[1]["notes"] == [{"text": "Remember the salt.", "resolved": False}]
    assert elems[2]["notes"] == [{"text": "Done.", "resolved": True}]
    assert "notes" not in elems[0]
    assert mcptools.getInfo(doc)["notes"] == 2

    elems[3]["notes"] = ["Louder.", {"text": "Fine.", "resolved": True}]
    res = mcptools.replaceScene(doc, rev, 1, elems)

    assert res["revision"] != rev
    assert mcptools.readScenes(doc, 1)["scenes"][0]["elements"][3]["notes"] == [
        {"text": "Louder.", "resolved": False},
        {"text": "Fine.", "resolved": True},
    ]

    # undoable, like the other MCP edits
    doc.ed.cmd("undo")
    assert mcptools.getInfo(doc)["notes"] == 2


def testMCPRefusesNoteType():
    doc = mcptools.LiveDoc(load())
    rev = mcptools.listScenes(doc)["revision"]

    with pytest.raises(mcptools.ToolError, match="notes"):
        mcptools.insertScenes(
            doc,
            rev,
            1,
            [{"type": "scene", "text": "INT. X"}, {"type": "note", "text": "Hi"}],
        )
