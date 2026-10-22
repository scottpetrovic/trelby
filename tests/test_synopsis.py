import io
import zipfile
from types import SimpleNamespace

import pytest
import wx

import tests.u as u
import trelby.importers.fadein as fadeinimport
import trelby.importers.fdx as fdximport
import trelby.importers.fountain as fountainimport
import trelby.mcpserver.tools as mcptools
import trelby.reports.scenereport as scenereport
import trelby.screenplay as scr
import trelby.screenplay.export as export
import trelby.translations as translations

_ = translations.trelby_translations_load()

import trelby.dialogs.synopsisdlg as synopsisdlg  # noqa: E402
import trelby.ui.outline as outline  # noqa: E402
import trelby.ui.scriptactions as scriptactions  # noqa: E402

# scene synopses (Line.synopsis on a scene heading's first line): editing
# them, keeping them with their heading through edits, the file format,
# the imports and exports, the MCP tools, the scene report and the outline

SCRIPT = [
    "#Version 3",
    "#Start-Script ",
    "./Fade in:",
    "#Synopsis Mary makes dinner,\\nand John waits.",
    ".\\INT. KITCHEN - DAY",
    "..Mary cooks.",
    "..John waits.",
    ".@Act one",
    ".\\EXT. GARDEN - NIGHT",
    "..They talk.",
]


def load():
    return u.loadStringEditor("\n".join(SCRIPT))


def lineOf(ed, text):
    return next(i for i, ln in enumerate(ed.sp.lines) if ln.text == text)


# (heading, synopsis) of every scene and act break
def synopses(sp):
    return [(it.heading, it.synopsis) for it in sp.getOutline()]


def testLoadAndSave():
    ed = load()

    assert synopses(ed.sp) == [
        ("INT. KITCHEN - DAY", "Mary makes dinner,\nand John waits."),
        ("ACT ONE", None),
        ("EXT. GARDEN - NIGHT", None),
    ]

    s = ed.sp.save().decode("utf-8-sig")
    assert "#Synopsis Mary makes dinner,\\nand John waits.\n.\\INT. KITCHEN" in s

    assert synopses(u.loadString(s)) == synopses(ed.sp)
    ed._validate()


# only a scene heading's first line has one
def testOnlyOnSceneHeadings():
    ed = load()
    garden = lineOf(ed, "EXT. GARDEN - NIGHT")
    act = lineOf(ed, "Act one")

    assert not ed.setSynopsis(act, "No.")
    assert not ed.setSynopsis(garden + 1, "No.")
    assert not ed.sp.lines[act].synopsis

    # one left on a line that's no longer a scene heading isn't saved
    ed.sp.lines[act].synopsis = "Stray."
    assert "Stray" not in ed.sp.save().decode("utf-8-sig")


def testSetAndUndo():
    ed = load()
    garden = lineOf(ed, "EXT. GARDEN - NIGHT")
    ed.line, ed.column = garden + 1, 3

    assert ed.setSynopsis(garden, "  They talk\r\nabout it.  ")
    assert ed.sp.getSynopsis(garden) == "They talk\nabout it."
    assert not ed.setSynopsis(garden, "They talk\nabout it.")

    # the cursor stays put
    assert (ed.line, ed.column) == (garden + 1, 3)

    # empty text removes it
    assert ed.setSynopsis(garden, " ")
    assert ed.sp.getSynopsis(garden) is None

    ed.cmd("undo")
    assert ed.sp.getSynopsis(garden) == "They talk\nabout it."

    ed.cmd("undo")
    assert ed.sp.getSynopsis(garden) is None

    ed.cmd("redo")
    assert ed.sp.getSynopsis(garden) == "They talk\nabout it."
    ed._validate()


def testTypingInHeadingKeepsIt():
    ed = load()
    kitchen = lineOf(ed, "INT. KITCHEN - DAY")
    ed.line, ed.column = kitchen, 0

    for ch in "INT./EXT. A VERY LONG HEADING THAT WRAPS ONTO A SECOND LINE ":
        ed.cmd("addChar", char=ch)

    assert ed.sp.lines[kitchen].lb != scr.LB_LAST
    assert ed.sp.getSynopsis(kitchen) == "Mary makes dinner,\nand John waits."
    ed._validate()


def testCutAndPasteMoveIt():
    ed = load()
    kitchen = lineOf(ed, "INT. KITCHEN - DAY")

    ed.selectElementAt(kitchen)
    cd = ed.getSelectedAsCD(True)
    assert cd.lines[0].synopsis == "Mary makes dinner,\nand John waits."

    last = len(ed.sp.lines) - 1
    ed.line, ed.column = last, len(ed.sp.lines[last].text)
    ed.cmd("splitElement")
    ed.paste(cd.lines)

    assert synopses(ed.sp)[-1] == (
        "INT. KITCHEN - DAY",
        "Mary makes dinner,\nand John waits.",
    )
    ed._validate()


# pasting paragraphs at the start of a heading pushes it down, and its
# synopsis goes with it
def testPastingBeforeHeadingMovesIt():
    ed = load()
    kitchen = lineOf(ed, "INT. KITCHEN - DAY")

    ed.selectElementAt(lineOf(ed, "They talk."))
    cd = ed.getSelectedAsCD(False)
    ed.clearMark()

    lines = cd.lines + [ln.copy() for ln in cd.lines]
    lines[0].lb = scr.LB_LAST

    ed.line, ed.column = kitchen, 0
    ed.paste(lines)

    heading = lineOf(ed, "INT. KITCHEN - DAY")
    assert heading == kitchen + 2
    assert ed.sp.getSynopsis(heading) == "Mary makes dinner,\nand John waits."
    assert [i for i, ln in enumerate(ed.sp.lines) if ln.synopsis] == [heading]
    ed._validate()


def text(data):
    return data.decode("utf-8") if isinstance(data, bytes) else data


def importedSynopses(result):
    return [(ln.text, ln.synopsis) for ln in result.lines if ln.synopsis]


EXPECTED = [("INT. KITCHEN - DAY", "Mary makes dinner,\nand John waits.")]


def testFountainExportAndImport():
    ed = load()
    s = text(export.generateFountain(ed.sp))

    assert "INT. KITCHEN - DAY\n\n= Mary makes dinner,\n= and John waits.\n\n" in s

    result = fountainimport.parse(s)
    assert importedSynopses(result) == EXPECTED

    # no blank line is left behind in its place
    kitchen = [ln.text for ln in result.lines].index("INT. KITCHEN - DAY")
    assert result.lines[kitchen + 1].text == "Mary cooks."


# a synopsis that isn't right after a scene heading is a note, or dropped
def testFountainOtherSynopses():
    s = "INT. HALL\n\nAnn enters.\n\n= Later on.\n\n# Act\n\n= Act synopsis.\n"

    result = fountainimport.parse(s)
    assert importedSynopses(result) == []
    assert [n.text for ln in result.lines for n in ln.notes] == [
        "Later on.",
        "Act",
        "Act synopsis.",
    ]

    result = fountainimport.parse(
        s.replace("INT. HALL\n", "INT. HALL\n= Scene.\n"),
        fountainimport.Options(sectionsAsNotes=False),
    )
    assert importedSynopses(result) == [("INT. HALL", "Scene.")]
    assert not any(ln.notes for ln in result.lines)


def testFDXExportAndImport():
    ed = load()
    s = text(export.generateFDX(ed.sp))

    assert "<Summary>" in s

    result = fdximport.parse(s)
    assert importedSynopses(result) == EXPECTED
    assert "Mary makes dinner," not in [ln.text for ln in result.lines]


def fadein(paras):
    xml = (
        '<?xml version="1.0"?><document><paragraphs>%s</paragraphs></document>'
        % "".join(paras)
    )
    data = io.BytesIO()

    with zipfile.ZipFile(data, "w") as z:
        z.writestr("document.xml", xml)

    return data.getvalue()


def testFadeInImport():
    result = fadeinimport.parse(
        fadein(
            [
                '<para synopsis="Ann arrives."><style basestylename="Scene'
                ' Heading"/><text>INT. HALL</text></para>',
                '<para synopsis="Not a scene."><style basestylename="Action"/>'
                "<text>Ann enters.</text></para>",
            ]
        )
    )

    assert importedSynopses(result) == [("INT. HALL", "Ann arrives.")]
    assert [n.text for ln in result.lines for n in ln.notes] == ["Not a scene."]


def testMCPReadAndWrite():
    doc = mcptools.LiveDoc(load())
    res = mcptools.listScenes(doc)
    rev = res["revision"]

    assert res["scenes"][1]["synopsis"] == "Mary makes dinner,\nand John waits."
    assert "synopsis" not in res["scenes"][3]

    elems = mcptools.readScenes(doc, 1)["scenes"][0]["elements"]
    assert elems[0]["synopsis"] == "Mary makes dinner,\nand John waits."

    # left out, it's kept
    del elems[0]["synopsis"]
    elems[1]["text"] = "Mary bakes."
    rev = mcptools.replaceScene(doc, rev, 1, elems)["revision"]
    assert doc.ed.sp.getOutline()[0].synopsis == "Mary makes dinner,\nand John waits."

    # null removes it
    elems[0]["synopsis"] = None
    rev = mcptools.replaceScene(doc, rev, 1, elems)["revision"]
    assert doc.ed.sp.getOutline()[0].synopsis is None

    res = mcptools.replaceScene(
        doc,
        rev,
        3,
        [
            {"type": "scene", "text": "EXT. GARDEN - NIGHT", "synopsis": "Talk."},
            {"type": "action", "text": "They talk."},
        ],
    )
    assert res["scenes"][3]["synopsis"] == "Talk."

    with pytest.raises(mcptools.ToolError, match="synopsis"):
        mcptools.insertScenes(
            doc,
            res["revision"],
            1,
            [{"type": "act break", "text": "ACT TWO", "synopsis": "No."}],
        )

    # undoable, like the other MCP edits
    doc.ed.cmd("undo")
    assert doc.ed.sp.getOutline()[2].synopsis is None


def testSceneReport():
    ed = load()
    ed.sp.paginate()
    report = scenereport.SceneReport(ed.sp)

    assert "Mary makes dinner, and John waits." in report.generateHtml()

    report.opts["synopses"] = False
    assert "Mary makes dinner" not in report.generateHtml()


class FakeCtrl:
    def __init__(self, ed):
        self.ed = ed

    @property
    def sp(self):
        return self.ed.sp

    def gotoLine(self, line):
        self.ed.gotoPos(line, 0)

    def setSynopsis(self, line, text):
        self.ed.setSynopsis(line, text)

    def SetFocus(self):
        pass


@pytest.fixture
def panel(app):
    ed = load()
    frame = wx.Frame(None, size=wx.Size(300, 700))
    p = outline.OutlinePanel(frame, SimpleNamespace(ctrl=FakeCtrl(ed)))
    frame.Show()
    p.refresh()

    yield p

    frame.Destroy()


# the dialog, answered with the given text (None: cancelled)
@pytest.fixture
def answer(monkeypatch):
    shown = []

    def use(text):
        def showModal(dlg):
            shown.append(dlg.textCtrl.GetValue())

            if text is None:
                return wx.ID_CANCEL

            dlg.text = text

            return wx.ID_OK

        monkeypatch.setattr(synopsisdlg.SynopsisDlg, "ShowModal", showModal)

        return shown

    return use


def testOutlineShowsSynopsisOrAction(panel):
    lc = panel.list

    assert lc.getSummaryLines(0) == ["Mary makes dinner, and John waits."]
    assert lc.getSummaryLines(2) == ["They talk."]

    lc.Refresh()
    lc.Update()


def testEditFromOutline(panel, answer):
    shown = answer("Ann and John talk.")

    # act breaks have none
    assert not panel.isSceneRow(1)
    panel.editSynopsis(1)
    assert shown == []

    panel.editSynopsis(2)
    assert shown == [""]
    assert panel.list.items[2].synopsis == "Ann and John talk."
    assert panel.list.getSummaryLines(2) == ["Ann and John talk."]

    answer(None)
    panel.editSynopsis(0)
    assert panel.list.items[0].synopsis == "Mary makes dinner,\nand John waits."


# Edit > Edit scene synopsis works on the scene selected in the outline,
# only while it's shown
def testMenuCommand(panel, answer):
    answer("Changed.")
    shownOutline = [True]
    frame = SimpleNamespace(
        panel=SimpleNamespace(outline=panel),
        gd=SimpleNamespace(outlineShown=lambda: shownOutline[0]),
    )
    ctrl = panel.getCtrl()

    ctrl.gotoLine(lineOf(ctrl.ed, "They talk."))
    panel.selectCurrent()
    assert scriptactions.canEditSynopsis(frame, ctrl)

    shownOutline[0] = False
    assert not scriptactions.canEditSynopsis(frame, ctrl)
    scriptactions.editSynopsis(frame, ctrl)
    assert panel.list.items[2].synopsis is None

    shownOutline[0] = True
    scriptactions.editSynopsis(frame, ctrl)
    assert panel.list.items[2].synopsis == "Changed."

    ctrl.gotoLine(lineOf(ctrl.ed, "Act one"))
    panel.selectCurrent()
    assert not scriptactions.canEditSynopsis(frame, ctrl)
