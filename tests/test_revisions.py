import tests.u as u
import trelby.mcpserver.tools as m
import trelby.screenplay as scr
import trelby.screenplay.render as render
import trelby.screenplay.revisions as revisions
import trelby.translations as translations
import trelby.undo as undo
from trelby.screenplay.line import Line

_ = translations.trelby_translations_load()

# tests for revision marks (screenplay/revisions.py) and omitted scenes


# return an Editor on a script with 'scenes' scenes, each a heading and
# an action element long enough to wrap
def makeScript(scenes=3):
    lines = ["#Version 3", "#Start-Script "]

    for s in range(scenes):
        lines.append(".\\INT. ROOM %d - DAY" % (s + 1))
        lines.append(
            "..Scene %d starts here and the action goes on for long enough "
            "to wrap onto a second line and then a third line of text." % (s + 1)
        )

    ed = u.loadStringEditor("\n".join(lines))
    ed.sp.paginate()

    return ed


# the same, in revision mode with the given revision
def makeRevising(level=1, **kwargs):
    ed = makeScript(**kwargs)
    ed.sp.revisions.level = level
    ed.sp.revisions.active = True

    return ed


# return the text of the paragraph starting at line i, and its marks
def para(ed, i):
    p = revisions._Para(ed.sp.lines, i)

    return p.text, p.revs


# return the words of the paragraph at line i marked with 'level'
def markedWords(ed, i, level=1):
    text, revs = para(ed, i)
    c = revisions.levelChar(level)

    return "".join(t if r == c else " " for t, r in zip(text, revs)).split()


# return the indexes of the lines with marks
def markedLines(ed):
    return [i for i, ln in enumerate(ed.sp.lines) if ln.revs]


def testLevelNames():
    assert revisions.levelName(0) == "White"
    assert revisions.levelName(1) == "Blue"
    assert revisions.levelName(2) == "Pink"
    assert revisions.levelName(3) == "Yellow"
    assert revisions.levelName(8) == "Cherry"
    assert revisions.levelName(9) == "Double White"
    assert revisions.levelName(10) == "Double Blue"
    assert revisions.levelName(18) == "Triple White"
    assert revisions.levelName(revisions.MAX_LEVEL) == "Triple Cherry"


def testLabel():
    rv = revisions.Revisions()
    rv.dates[2] = "10/17/26"

    assert rv.label(0) == ""
    assert rv.label(1) == "Blue Rev."
    assert rv.label(2) == "Pink Rev. 10/17/26"


def testEncodeDecode():
    revs = "0011100002"

    assert revisions.encode(revs) == "2-5:1,9-10:2"
    assert revisions.decode("2-5:1,9-10:2", 10) == revs
    assert revisions.decode("2-5:1,bad,3-4:99,8-20:3", 10) == "0011100033"
    assert revisions.decode("", 5) is None
    assert revisions.encode(None) == ""


def testNoMarksOutsideRevisionMode():
    ed = makeScript()
    ed.gotoPos(1, 0)
    ed.cmdChars("New ")

    assert not ed.sp.hasRevisionMarks()


def testTypingMarksTheWord():
    ed = makeRevising()
    ed.gotoPos(1, len("Scene 1 starts"))
    ed.cmdChars(" right")
    ed._validate()

    assert markedWords(ed, 1) == ["right"]

    # the other lines of the paragraph aren't marked, though the text on
    # them has moved
    assert markedLines(ed) == [1]


def testChangedWordIsMarked():
    ed = makeRevising()
    ed.gotoPos(1, len("Scene 1 st"))
    ed.cmdChars("x")

    assert markedWords(ed, 1) == ["stxarts"]


def testMarksMoveWithRewrapping():
    ed = makeRevising()

    # mark a word at the end of the first line, then push it onto the
    # next one
    end = len(ed.sp.lines[1].text)
    ed.gotoPos(1, end)
    ed.cmdChars(" zzz")
    ed.gotoPos(1, 0)
    ed.cmdChars("More words at the start. ")
    ed._validate()

    assert markedWords(ed, 1) == ["More", "words", "at", "the", "start.", "zzz"]


def testMarksKeptOutsideRevisionMode():
    ed = makeRevising()
    ed.gotoPos(1, 0)
    ed.cmdChars("Blue ")

    ed.sp.revisions.active = False
    ed.gotoPos(1, len("Blue Scene 1"))
    ed.cmdChars(" plain")
    ed._validate()

    assert markedWords(ed, 1) == ["Blue"]


def testNewRevisionLevel():
    ed = makeRevising()
    ed.gotoPos(1, 0)
    ed.cmdChars("Blue ")

    ed.sp.revisions.level = 2
    ed.gotoPos(1, len("Blue "))
    ed.cmdChars("Pink ")

    assert markedWords(ed, 1, 1) == ["Blue"]
    assert markedWords(ed, 1, 2) == ["Pink"]
    assert revisions.lineLevel(ed.sp.lines[1]) == 2


def testDeletionMarksNeighbor():
    ed = makeRevising()
    ed.gotoPos(1, len("Scene 1"))

    for i in range(len(" starts")):
        ed.cmd("deleteForward")

    text, revs = para(ed, 1)
    assert text.startswith("Scene 1 here")
    assert ed.sp.lines[1].revs
    assert markedLines(ed) == [1]


def testDeletedParagraphMarksNeighbor():
    ed = makeRevising()
    start = ed.sp.getSceneStarts()[1]
    last = ed.sp.getElemLastIndexFromLine(start + 1)

    ed.setMark(start + 1, 0)
    ed.gotoPos(last, len(ed.sp.lines[last].text))
    ed.getSelectedAsCD(True)
    ed._validate()

    assert markedLines(ed)


def testTypeChangeMarksParagraph():
    ed = makeRevising()
    ed.gotoPos(1, 0)
    ed.convertTypeTo(scr.CHARACTER, True)

    last = ed.sp.getElemLastIndexFromLine(1)
    assert all(
        ln.revs == "1" * len(ln.text) for ln in ed.sp.lines[1 : last + 1]
    )


def testUndoRedo():
    ed = makeRevising()
    ed.gotoPos(1, 0)
    ed.cmdChars("New ")
    assert markedLines(ed) == [1]

    ed.cmd("undo")
    assert not ed.sp.hasRevisionMarks()

    ed.cmd("redo")
    assert markedWords(ed, 1) == ["New"]


def testPasteIsMarked():
    ed = makeRevising()
    ed.gotoPos(ed.sp.getSceneStarts()[1], 0)
    ed.paste(
        [
            Line(scr.LB_LAST, scr.SCENE, "INT. NEW ROOM - DAY"),
            Line(scr.LB_LAST, scr.ACTION, "Something happens."),
        ]
    )
    ed._validate()

    start = ed.sp.getSceneStarts()[1]
    assert markedWords(ed, start) == ["INT.", "NEW", "ROOM", "-", "DAY"]
    assert markedWords(ed, start + 1) == ["Something", "happens."]
    assert markedLines(ed) == [start, start + 1]


def testMovingSceneKeepsMarks():
    ed = makeRevising()
    ed.gotoPos(1, 0)
    ed.cmdChars("Blue ")
    ed.sp.revisions.active = False

    ed.moveSceneTo(1, 2)
    ed._validate()

    start = ed.sp.getSceneStarts()[2]
    assert markedWords(ed, start + 1) == ["Blue"]


def testClearMarks():
    ed = makeRevising()
    ed.gotoPos(1, 0)
    ed.cmdChars("New ")

    ed.clearRevisionMarks()
    assert not ed.sp.hasRevisionMarks()

    ed.cmd("undo")
    assert markedWords(ed, 1) == ["New"]


def testCarryOnWholeScript():
    ed = makeRevising()
    ed.gotoPos(1, 0)
    ed.cmdChars("New ")

    # a FullCopy edit elsewhere keeps the marks
    ed.lockPages()
    assert markedWords(ed, 1) == ["New"]


def testSaveLoad():
    ed = makeRevising(level=3)
    ed.sp.revisions.dates = {1: "10/1/26", 3: "10/17/26"}
    ed.sp.revisions.markChar = "+"
    ed.sp.revisions.currentOnly = True
    ed.gotoPos(1, 0)
    ed.cmdChars("New ")

    s = ed.sp.save().decode("utf-8")
    assert "#Begin-Revisions" in s
    assert "#Revised 0-4:3" in s

    sp = u.loadString(s)
    assert sp.revisions == ed.sp.revisions
    assert [ln.revs for ln in sp.lines] == [ln.revs for ln in ed.sp.lines]


def testPlainScriptSavesNoRevisions():
    s = makeScript().sp.save().decode("utf-8")

    assert "Revisions" not in s
    assert "#Revised" not in s


def testUndoStorageKeepsMarks():
    lines = [Line(scr.LB_LAST, scr.ACTION, "abc", revs="010")]

    assert undo.storage2lines(undo.lines2storage(lines))[0].revs == "010"


def testMCPRevisionCoversMarks():
    ed = makeScript()
    before = m.linesRevision(ed.sp)
    ed.sp.lines[1].revs = "1"

    assert m.linesRevision(ed.sp) != before


# return the text ops of page pageNr of the script's PDF layout
def pageTexts(sp, pageNr, revisedOnly=False):
    doc = render.generatePML(sp, revisedOnly)

    return [op for op in doc.pages[pageNr - 1].ops if hasattr(op, "text")]


# return a script of about three pages, with the middle one revised
def makeThreePages():
    ed = makeRevising(scenes=30)
    ed.sp.revisions.active = False
    ed.sp.paginate()
    assert len(ed.sp.pages) - 1 >= 3

    first, last = ed.sp.page2lines(2)
    i = first

    while ed.sp.lines[i].lt != scr.ACTION:
        i += 1

    ed.sp.revisions.active = True
    ed.gotoPos(i, 0)
    ed.cmdChars("Changed ")
    ed.sp.revisions.dates[1] = "10/17/26"
    ed.sp.paginate()

    return ed


def testPDFRevisionMarks():
    ed = makeThreePages()
    sp = ed.sp

    texts = pageTexts(sp, 2)
    marks = [op for op in texts if op.text == "*"]

    chX = render.util.getTextWidth(" ", render.pml.COURIER, sp.cfg.fontSize)

    # one mark, in the right margin
    assert len(marks) == 1
    assert marks[0].x == revisions.markX(sp.cfg, chX)
    assert marks[0].x > sp.cfg.paperWidth - sp.cfg.marginRight

    assert not [op for op in pageTexts(sp, 1) if op.text == "*"]


def testPDFHeaderShowsRevision():
    ed = makeThreePages()
    sp = ed.sp

    assert "Blue Rev. 10/17/26" in [op.text for op in pageTexts(sp, 2)]
    assert "Blue Rev. 10/17/26" not in [op.text for op in pageTexts(sp, 1)]

    sp.revisions.showInHeader = False
    assert "Blue Rev. 10/17/26" not in [op.text for op in pageTexts(sp, 2)]

    # a header with ${REVISION} shows it instead
    sp.revisions.showInHeader = True
    sp.headers.addDefaults()
    sp.headers.hdrs[0].text = "${REVISION}  ${PAGE}."
    texts = [op.text for op in pageTexts(sp, 2)]
    assert "Blue Rev. 10/17/26  2." in texts
    assert "Blue Rev. 10/17/26" not in texts


def testRevisedPagesOnly():
    ed = makeThreePages()
    sp = ed.sp

    assert sp.getRevisedPages() == [2]

    doc = render.generatePML(sp, True)
    assert len(doc.pages) == 1
    assert "Changed" in " ".join(
        op.text for op in doc.pages[0].ops if hasattr(op, "text")
    )

    # pages revised in an older revision don't count
    sp.revisions.level = 2
    assert sp.getRevisedPages() == []
    assert sp.getPageRevision(2) == 1


def testCurrentOnlyMarks():
    ed = makeRevising()
    ed.gotoPos(1, 0)
    ed.cmdChars("Blue ")
    ed.sp.revisions.level = 2
    ed.sp.revisions.currentOnly = True

    assert not ed.sp.revisions.isMarked(ed.sp.lines[1])

    ed.gotoPos(1, 0)
    ed.cmdChars("Pink ")
    assert ed.sp.revisions.isMarked(ed.sp.lines[1])


# omitted scenes


def makeLocked(**kwargs):
    ed = makeScript(**kwargs)
    ed.lockScenes()

    return ed


def labels(ed):
    return [(label, ed.sp.lines[i].text) for i, label in ed.sp.getSceneLabels()]


def testOmitScene():
    ed = makeLocked()
    ed.gotoPos(ed.sp.getSceneStarts()[1] + 1, 3)
    ed.omitScene()
    ed._validate()

    assert labels(ed) == [
        ("1", "INT. ROOM 1 - DAY"),
        ("2", "OMITTED"),
        ("3", "INT. ROOM 3 - DAY"),
    ]

    start = ed.sp.getSceneStarts()[1]
    assert ed.sp.getSceneIndexesFromLine(start) == (start, start)
    assert ed.line == start

    # omitting it again does nothing
    ed.omitScene()
    assert ed.undoHistory.last.prev is not None

    ed.cmd("undo")
    assert labels(ed)[1] == ("2", "INT. ROOM 2 - DAY")


def testOmitSceneUnlocked():
    ed = makeScript()
    ed.gotoPos(ed.sp.getSceneStarts()[1], 0)
    ed.omitScene()

    assert labels(ed)[1] == ("2", "OMITTED")


def testOmitSceneIsRevised():
    ed = makeLocked()
    ed.sp.revisions.level = 1
    ed.sp.revisions.active = True
    ed.gotoPos(ed.sp.getSceneStarts()[1], 0)
    ed.omitScene()

    assert ed.sp.lines[ed.sp.getSceneStarts()[1]].revs == "1" * len("OMITTED")


def testDeletingOmittedSceneRemovesIt():
    ed = makeLocked()
    start = ed.sp.getSceneStarts()[1]
    ed.gotoPos(start, 0)
    ed.omitScene()

    ed.setMark(start, 0)
    ed.gotoPos(start, len("OMITTED"))
    ed.getSelectedAsCD(True)
    ed._validate()

    # the selection left the heading empty, and deleting it doesn't put
    # another omitted scene back
    assert [label for label, text in labels(ed) if text == "OMITTED"] == []


def testCutOmitsAtSceneEnd():
    ed = makeLocked()
    starts = ed.sp.getSceneStarts()

    # select from the middle of scene 1 to the middle of scene 2: scene
    # 2's heading goes, and its omitted scene comes before scene 3
    ed.setMark(starts[0] + 1, 5)
    ed.gotoPos(starts[1] + 1, 5)
    ed.getSelectedAsCD(True)
    ed._validate()

    assert labels(ed) == [
        ("1", "INT. ROOM 1 - DAY"),
        ("2", "OMITTED"),
        ("3", "INT. ROOM 3 - DAY"),
    ]


def testCutLastScene():
    ed = makeLocked()
    start = ed.sp.getSceneStarts()[2]
    last = len(ed.sp.lines) - 1

    ed.setMark(start, 0)
    ed.gotoPos(last, len(ed.sp.lines[last].text))
    ed.getSelectedAsCD(True)
    ed._validate()

    assert labels(ed)[-1] == ("3", "OMITTED")


def testMCPDeleteSceneOmits(tmp_path):
    path = str(tmp_path / "locked.trelby")
    ed = makeLocked()

    with open(path, "wb") as f:
        f.write(ed.sp.save())

    doc = m.FileDoc(path)
    rev = m.listScenes(doc)["revision"]
    m.deleteScene(doc, rev, 2)

    sp = u.loadString(open(path, encoding="utf-8").read())
    assert [(label, sp.lines[i].text) for i, label in sp.getSceneLabels()][1] == (
        "2",
        "OMITTED",
    )


def testPDFPrintsOmitted():
    ed = makeLocked()
    ed.gotoPos(ed.sp.getSceneStarts()[1], 0)
    ed.omitScene()
    ed.sp.cfg.pdfShowSceneNumbers = True
    ed.sp.paginate()

    texts = [op.text for op in pageTexts(ed.sp, 1)]

    assert "OMITTED" in texts
    assert texts.count("2") == 2


# the settings dialog, built for real but not shown


def testRevisionsDlg():
    import wx

    import trelby.dialogs.revisionsdlg as revisionsdlg
    import trelby.ui.gutil as gutil

    app = wx.App(False)
    gutil.init()

    try:
        rv = revisions.Revisions()
        rv.dates = {1: "9/1/26"}
        dlg = revisionsdlg.RevisionsDlg(None, rv, ["2", "5A"])

        # a new script starts at Blue, with its date
        assert dlg.getLevel() == 1
        assert dlg.dateEntry.GetValue() == "9/1/26"

        # Pink gets today's date
        dlg.levelCombo.SetSelection(1)
        dlg.OnLevel(None)
        assert dlg.dateEntry.GetValue() == revisionsdlg.today()

        # looking at Yellow doesn't keep a date for it
        dlg.levelCombo.SetSelection(2)
        dlg.OnLevel(None)
        dlg.levelCombo.SetSelection(1)
        dlg.OnLevel(None)

        dlg.activeCb.SetValue(True)
        dlg.markEntry.SetValue("#")

        dlg.EndModal = lambda code: None
        dlg.OnOK(None)
        dlg.Destroy()

        assert rv.level == 2
        assert rv.active
        assert rv.markChar == "#"
        assert rv.dates == {1: "9/1/26", 2: revisionsdlg.today()}
    finally:
        app.Destroy()


# Final Draft (FDX) export and import


def fdxRoot(sp):
    from lxml import etree

    import trelby.screenplay.export as export

    return etree.XML(export.generateFDX(sp))


def testFDXExport():
    ed = makeRevising()
    ed.lockScenes()
    ed.sp.revisions.dates[1] = "10/17/26"
    ed.gotoPos(1, len("Scene 1 starts"))
    ed.cmdChars(" right")
    ed.gotoPos(ed.sp.getSceneStarts()[1], 0)
    ed.omitScene()

    root = fdxRoot(ed.sp)
    paras = root.xpath("Content/Paragraph")

    # revised text is its own Text element, with the revision's ID
    texts = paras[1].xpath("Text")
    assert "".join(t.text for t in texts).startswith("Scene 1 starts right here")
    assert [t.text.strip() for t in texts if t.get("RevisionID") == "1"] == [
        "right"
    ]
    assert all(t.get("RevisionID") in (None, "1") for t in texts)

    # locked scene numbers go on the headings, the omitted scene's too
    headings = root.xpath("Content/Paragraph[@Type='Scene Heading']")
    assert [(h.get("Number"), h.xpath("string(Text)")) for h in headings] == [
        ("1", "INT. ROOM 1 - DAY"),
        ("2", "OMITTED"),
        ("3", "INT. ROOM 3 - DAY"),
    ]

    sets = root.xpath("Revisions")
    assert len(sets) == 1
    assert sets[0].get("ActiveSet") == "1"
    assert sets[0].get("RevisionMode") == "Yes"

    rev = sets[0].xpath("Revision")
    assert len(rev) == 1
    assert rev[0].get("ID") == "1"
    assert rev[0].get("Name") == "Blue Rev. 10/17/26"
    assert rev[0].get("Mark") == "*"
    assert len(rev[0].get("PageColor")) == len("#RRRRGGGGBBBB")


def testFDXExportPlainScript():
    sp = makeScript().sp
    root = fdxRoot(sp)

    assert not root.xpath("Revisions")
    assert not root.xpath("//Text[@RevisionID]")

    # scene numbers only when they're printed (or locked)
    assert not root.xpath("//Paragraph[@Number]")

    sp.cfg.pdfShowSceneNumbers = True
    assert [
        p.get("Number") for p in fdxRoot(sp).xpath("//Paragraph[@Number]")
    ] == ["1", "2", "3"]


# every revision up to the latest one used gets a revision set
def testFDXExportOlderRevisions():
    ed = makeRevising(level=3)
    ed.gotoPos(1, 0)
    ed.cmdChars("Yellow ")
    ed.sp.revisions.level = 1
    ed.sp.revisions.active = False

    sets = fdxRoot(ed.sp).xpath("Revisions")[0]
    assert [r.get("ID") for r in sets.xpath("Revision")] == ["1", "2", "3"]
    assert sets.get("ActiveSet") == "1"
    assert sets.get("RevisionMode") == "No"


def testFDXRoundTrip():
    import trelby.importers.fdx as fdximport
    import trelby.screenplay.export as export

    ed = makeRevising(level=2)
    ed.sp.revisions.markChar = "#"
    ed.gotoPos(1, 0)
    ed.cmdChars("Pink ")

    result = fdximport.parse(export.generateFDX(ed.sp).decode("UTF-8"))

    assert result.revisions.level == 2
    assert result.revisions.active
    assert result.revisions.markChar == "#"

    sp = u.new()
    sp.lines = result.lines
    sp.revisions = result.revisions
    sp.reformatAll()
    ed2 = scr.Editor(sp)
    ed2._validate()

    assert markedWords(ed2, 1, 2) == ["Pink"]
    assert [ln.text for ln in sp.lines] == [ln.text for ln in ed.sp.lines]
    assert [ln.revs for ln in sp.lines] == [ln.revs for ln in ed.sp.lines]


# a file as Final Draft writes it, with revision sets of its own
def testFDXImportFinalDraftRevisions():
    import trelby.importers.fdx as fdximport

    s = """<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<FinalDraft DocumentType="Script" Template="No" Version="5">
  <Content>
    <Paragraph Number="1" Type="Scene Heading">
      <Text>INT. HOUSE - DAY</Text>
    </Paragraph>
    <Paragraph Type="Action">
      <Text>She opens the </Text>
      <Text RevisionID="2" Style="Bold">red</Text>
      <Text> door.</Text>
    </Paragraph>
  </Content>
  <Revisions ActiveSet="2" Location="7.75" RevisionMode="No" RevisionsShown="Active" ShowAllMarks="No" ShowAllSets="No">
    <Revision Color="#000000000000" FullRevision="No" ID="1" Mark="*" Name="First Revision" PageColor="#C6C6EDEDFEFE" Style=""/>
    <Revision Color="#000000000000" FullRevision="No" ID="2" Mark="+" Name="Second Revision" PageColor="#FEFECDCDDADA" Style=""/>
  </Revisions>
</FinalDraft>
"""
    result = fdximport.parse(s)
    ln = result.lines[1]

    assert ln.text == "She opens the red door."
    assert ln.revs == "0" * 14 + "222" + "0" * 6
    assert ln.fmt == "0" * 14 + "111" + "0" * 6

    rv = result.revisions
    assert (rv.level, rv.active, rv.markChar) == (2, False, "+")


def testFDXImportWithoutRevisions():
    import trelby.importers.fdx as fdximport

    result = fdximport.parse(
        "<FinalDraft><Content><Paragraph Type='Action'><Text>Hi.</Text>"
        "</Paragraph></Content></FinalDraft>"
    )

    assert result.revisions is None
    assert result.lines[0].revs is None
