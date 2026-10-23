import zipfile
from io import BytesIO

import wx

import tests.u as u
import trelby.config as config
import trelby.pdf.mypager as mypager
import trelby.pdf.pml as pml
import trelby.screenplay as scr
import trelby.screenplay.export as export
import trelby.screenplay.render as render
import trelby.screenplay.scriptformats as scriptformats
import trelby.translations as translations
import trelby.ui.configgui as configgui
import trelby.ui.scriptpainter as scriptpainter
import trelby.ui.viewmode as viewmode
import trelby.util as util
from trelby.screenplay.line import Line
from trelby.screenplay.twocolumn import FULL, LEFT, RIGHT, RowLayout

_ = translations.trelby_translations_load()
u.init()

# two-column (AV) scripts: the format, the rows' layout (twocolumn), and
# what pagination, the exports and the editor make of them

SKY = "Aerial view of the city at dawn, mist rolling over the river."
NARRATION = (
    "Every morning, three million people wake up in this city and every"
    " one of them has somewhere to be."
)

ELEMS = [
    (scr.SCENE, "1. OPENING"),
    (scr.SHOT, "WIDE SHOT"),
    (scr.ACTION, SKY),
    (scr.TRANSITION, "MUSIC: SOFT PIANO"),
    (scr.CHARACTER, "NARRATOR (V.O.)"),
    (scr.DIALOGUE, NARRATION),
    (scr.ACTION, "Traffic on the bridge."),
    (scr.DIALOGUE, "Some of them are late."),
    (scr.SCENE, "2. INTERVIEW"),
    (scr.DIALOGUE, "Audio alone."),
    (scr.ACTION, "Video alone."),
]


def avScript(elems=ELEMS, key="av"):
    sp = u.new()
    scriptformats.get(key).apply(sp.cfg)
    sp.lines = [Line(scr.LB_LAST, lt, text) for lt, text in elems]
    sp.reformatAll()
    sp.paginate()

    return sp


# the first line of each element with the given text
def lineOf(sp, text):
    for i, ln in enumerate(sp.lines):
        if sp.isFirstLineOfElem(i) and ln.text.startswith(text):
            return i

    raise KeyError(text)


# page pageNr's text, as {line: (x, y)} in characters / lines from the
# top left margin, and the texts that aren't script lines as [(text, x, y)]
def pageLayout(sp, pageNr, pager=None):
    pg = render.generatePMLPage(
        sp, pager or mypager.Pager(sp.cfg), pageNr, True, True
    )
    chX = util.getTextWidth(" ", pml.COURIER, sp.cfg.fontSize)
    chY = util.getTextHeight(sp.cfg.fontSize)
    lines = {}
    others = []

    for op in pg.ops:
        if not isinstance(op, pml.TextOp):
            continue

        x = round((op.x - sp.cfg.marginLeft) / chX)
        y = round((op.y - sp.cfg.marginTop) / chY)

        if op.line == -1:
            others.append((op.text, x, y))
        else:
            lines[op.line] = (x, y)

    return lines, others


def testRowLayout():
    layout = RowLayout(5)

    # a full-width element, then a row: the right run starts where the
    # left one does, without its spacing
    assert layout.place(FULL, 10) == 5
    assert layout.place(LEFT, 10) == 25
    assert layout.place(LEFT, 0) == 35
    assert not layout.inRightRun()
    assert layout.place(RIGHT, 10) == 25
    assert layout.inRightRun()
    assert layout.bottom() == 45

    # the right run is the longer one
    for top in (35, 45, 55):
        assert layout.place(RIGHT, 0) == top

    assert layout.bottom() == 65

    # what follows goes below it, with its own spacing
    assert layout.place(FULL, 10) == 75
    assert not layout.inRightRun()

    # a right run with no left run before it takes its place
    assert layout.place(RIGHT, 10) == 95
    assert layout.place(LEFT, 10) == 115

    # and so does a left run after the right one
    layout = RowLayout()
    layout.place(LEFT, 0)
    layout.place(RIGHT, 0)
    layout.place(RIGHT, 0)
    assert layout.place(LEFT, 10) == 30


def testFormat():
    sp = avScript()
    cfg = sp.cfg

    assert sp.isTwoColumn()
    assert scriptformats.typeLabel(cfg, scr.ACTION) == "Video"
    assert scriptformats.typeLabel(cfg, scr.DIALOGUE) == "Audio"
    assert scr.ACTBREAK not in scriptformats.usedTypes(cfg)

    cols = sp.getColumns()
    assert cols[scr.ACTION] == cols[scr.SHOT] == LEFT
    assert cols[scr.DIALOGUE] == cols[scr.CHARACTER] == RIGHT
    assert cols[scr.SCENE] == FULL

    # every column's types fit in it, and the columns don't overlap
    (x1, x2), (x3, x4) = sp.getColumnBounds()
    assert x1 < x2 < x3 < x4 <= cfg.getType(scr.SCENE).width

    # a screenplay has one column
    sp = avScript(key=scriptformats.SCREENPLAY)
    assert not sp.isTwoColumn()
    assert sp.getColumns() is None
    assert sp.getRowLines(0, len(sp.lines) - 1) == {}
    assert sp.getColumnHeadings() == []


# and survives saving and loading
def testFormatIsSaved():
    sp = avScript()
    sp2 = u.loadString(sp.save().decode("utf-8"))

    assert sp2.isTwoColumn()
    assert sp2.getRowLines(0, len(sp2.lines) - 1) == sp.getRowLines(
        0, len(sp.lines) - 1
    )


def testRowLines():
    sp = avScript()
    end = len(sp.lines) - 1
    rows = sp.getRowLines(0, end)

    shot = lineOf(sp, "WIDE SHOT")
    music = lineOf(sp, "MUSIC")
    traffic = lineOf(sp, "Traffic")
    late = lineOf(sp, "Some of them")
    first = (shot, music, traffic - 1)

    assert rows[shot] == (LEFT,) + first
    assert rows[music] == (RIGHT,) + first
    assert rows[traffic - 1] == (RIGHT,) + first
    assert rows[late] == (RIGHT, traffic, late, late)

    # scene headings and the rows with one column aren't in any
    for text in ("1. OPENING", "2. INTERVIEW", "Audio alone", "Video alone"):
        assert lineOf(sp, text) not in rows

    # a row is cut at the range's ends
    rows = sp.getRowLines(shot + 1, music)
    assert rows[shot + 1] == (LEFT, shot + 1, music, music)
    assert sp.getRowLines(music, end).get(music) is None


# the right column starts beside the left one, and what follows goes below
# the longer of them
def testRender():
    sp = avScript()
    lines, others = pageLayout(sp, 1)
    (x1, x2), (x3, x4) = sp.getColumnBounds()

    # the column headings come first, above each column
    assert ("VIDEO", x1, 0) in others
    assert ("AUDIO", x3, 0) in others

    scene = lineOf(sp, "1. OPENING")
    shot = lineOf(sp, "WIDE SHOT")
    music = lineOf(sp, "MUSIC")
    narration = lineOf(sp, "Every morning")
    traffic = lineOf(sp, "Traffic")
    late = lineOf(sp, "Some of them")
    interview = lineOf(sp, "2. INTERVIEW")
    audio = lineOf(sp, "Audio alone")
    video = lineOf(sp, "Video alone")

    assert lines[scene] == (0, 2)
    assert lines[shot] == (x1, 4)
    assert lines[music] == (x3, 4)

    # the narration is the longer column
    lastNarration = traffic - 1
    assert lines[lastNarration][1] > lines[traffic - 2][1]
    assert lines[traffic] == (x1, lines[lastNarration][1] + 2)
    assert lines[late] == (x3, lines[traffic][1])
    assert lines[interview][1] == lines[late][1] + 2

    # one column alone takes its place, at its column's indent
    assert lines[audio] == (x3, lines[interview][1] + 1)
    assert lines[video] == (x1, lines[audio][1] + 2)

    # the page's length counts the rows' height, not every line
    assert sp.getPageLength() == (lines[video][1] + 1) / sp.cfg.linesOnPage

    assert narration in lines


# a page's script lines fit on it
def checkPagesFit(sp):
    room = sp.cfg.linesOnPage

    for p in range(1, len(sp.pages)):
        lines, others = pageLayout(sp, p)
        bottom = max(y for x, y in list(lines.values()))

        assert bottom < room, "page %d" % p

        # every page has the headings, above its script lines
        y = headingsY(others)
        assert y + 2 <= min(y for x, y in lines.values())


# the line the column headings are on
def headingsY(others):
    ys = [y for t, x, y in others if t in ("VIDEO", "AUDIO")]

    assert len(ys) == 2 and ys[0] == ys[1]

    return ys[0]


def rowElems(n, videoWords=8, audioWords=30):
    elems = [(scr.SCENE, "1. SEGMENT")]

    for k in range(n):
        elems.append((scr.ACTION, " ".join(["video%d" % k] * videoWords)))
        elems.append((scr.DIALOGUE, " ".join(["audio%d" % k] * audioWords)))

    return elems


# rows are kept on a page, so each page starts with a row's video
def testRowsAreNotSplit():
    sp = avScript(rowElems(30))

    assert len(sp.pages) > 3

    for p in range(2, len(sp.pages)):
        first = sp.pages[p - 1] + 1
        assert sp.lines[first].lt == scr.ACTION
        assert sp.isFirstLineOfElem(first)

    checkPagesFit(sp)


# a row too long for a page is split, its audio going on at the top of the
# next page
def testLongRowIsSplit():
    sp = avScript(rowElems(1, audioWords=500) + rowElems(1)[1:])

    assert len(sp.pages) > 2

    start = sp.pages[1] + 1
    assert sp.lines[start].lt == scr.DIALOGUE
    assert not sp.isFirstLineOfElem(start)

    lines, others = pageLayout(sp, 2)
    (x1, x2), (x3, x4) = sp.getColumnBounds()

    # right below the headings, in its column
    assert lines[start] == (x3, headingsY(others) + 2)

    # narration has no speaker to continue
    assert not [t for t, x, y in others if ("MORE" in t) or ("cont'd" in t)]

    checkPagesFit(sp)

    # a speaker's speech is continued in the audio column
    elems = rowElems(1, audioWords=500)
    elems.insert(2, (scr.CHARACTER, "NARRATOR"))
    sp = avScript(elems)

    start = sp.pages[1] + 1
    assert sp.needsMore(start - 1)

    for p, text in ((1, "(MORE)"), (2, "NARRATOR (cont'd)")):
        assert [x for t, x, y in pageLayout(sp, p)[1] if t == text] == [x3]

    checkPagesFit(sp)


# a two-column script has no dual dialogue: its speeches are in a column
def testNoDualDialogue():
    ed = u.newEditor()
    scriptformats.get("av").apply(ed.sp.cfg)
    ed.sp.lines = [
        Line(scr.LB_LAST, lt, t)
        for lt, t in [
            (scr.CHARACTER, "BOB"),
            (scr.DIALOGUE, "Hi."),
            (scr.CHARACTER, "AMY"),
            (scr.DIALOGUE, "Hello."),
        ]
    ]
    ed.sp.lines[2].dual = True
    ed.line = 3

    assert ed.sp.getDualLines(0, 3) == {}
    assert ed.getDualToggle() is None


# Enter goes from the video to the audio beside it, and from the audio to
# the next row's video
def testEnterAndTab():
    ed = u.newEditor()
    scriptformats.get("av").apply(ed.sp.cfg)
    ed.sp.lines = [Line(scr.LB_LAST, scr.ACTION, "Sunrise.")]
    ed.line, ed.column = 0, len("Sunrise.")

    assert ed.typeFlow().newTypeEnter == scr.DIALOGUE

    ed.cmd("splitElement")
    assert ed.sp.lines[ed.line].lt == scr.DIALOGUE

    ed.cmd("addChar", char="x")
    ed.cmd("splitElement")
    assert ed.sp.lines[ed.line].lt == scr.ACTION

    # Tab on an empty video element switches it to audio
    ed.cmd("tab")
    assert ed.sp.lines[ed.line].lt == scr.DIALOGUE

    # other formats use the global settings
    ed.sp.cfg = config.Config()
    assert ed.typeFlow() is ed.sp.cfgGl.getType(scr.DIALOGUE)


def testTextExport():
    sp = avScript()
    text = export.generateText(sp, False).split("\n")
    (x1, x2), (x3, x4) = sp.getColumnBounds()

    # the row's columns side by side
    row = [s for s in text if s.startswith("WIDE SHOT")][0]
    assert row[x3:] == "MUSIC: SOFT PIANO"

    row = [s for s in text if s.startswith("Traffic on the bridge.")][0]
    assert row[x3:] == "Some of them are late."

    assert " " * x3 + "Audio alone." in text


def testHtmlExport():
    sp = avScript()
    html = export.generateHtml(sp, False)

    assert "Traffic on the bridge." + " " * 10 in html
    assert "Some of them are late." in html


def testDocxExport():
    sp = avScript()

    with zipfile.ZipFile(BytesIO(export.generateDocx(sp))) as z:
        doc = z.read("word/document.xml").decode("utf-8")

    # a table per row
    assert doc.count("<w:tbl>") == 2
    assert doc.index("WIDE SHOT") < doc.index("MUSIC") < doc.index("</w:tbl>")
    assert doc.index("Audio alone") > doc.rindex("</w:tbl>")


def screen(sp, vm):
    ed = scr.Editor(sp)
    cfgGui = configgui.ConfigGui(sp.cfgGl, 100)
    vp = scriptpainter.Viewport.make(
        sp, ed, cfgGui, vm, wx.Size(900, 3000), lambda n: n
    )

    return {t.line: (t.x, t.y) for t in vm.getScreen(vp, False)[0]}


# the screen shows the rows side by side in every view
def testViews(app):
    sp = avScript()
    shot = lineOf(sp, "WIDE SHOT")
    music = lineOf(sp, "MUSIC")
    traffic = lineOf(sp, "Traffic")
    late = lineOf(sp, "Some of them")

    for vm in (
        viewmode.ViewModeDraft(),
        viewmode.ViewModeLayout(),
        viewmode.ViewModeSideBySide(),
    ):
        texts = screen(sp, vm)

        assert texts[music][1] == texts[shot][1]
        assert texts[music][0] > texts[shot][0]
        assert texts[late][1] == texts[traffic][1]
        assert texts[traffic][1] > texts[traffic - 1][1]
