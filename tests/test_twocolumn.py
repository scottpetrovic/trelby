import zipfile
from io import BytesIO

import wx

import tests.u as u
import trelby.config as config
import trelby.importers.fdx as fdxImporter
import trelby.importers.fountain as fountainImporter
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
from trelby.screenplay.export.common import getElementsAsList
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

    # the column headings at the top of every page, the first one too,
    # where they start in the PDF
    for name in ("word/header1.xml", "word/header2.xml"):
        with zipfile.ZipFile(BytesIO(export.generateDocx(sp))) as z:
            hdr = z.read(name).decode("utf-8")

        assert hdr.index("VIDEO") < hdr.index("<w:tab/>") < hdr.index("AUDIO")
        assert '<w:tab w:val="left" w:pos="%d"/>' % (32 * 12 * sp.cfg.fontSize) in hdr

    assert "<w:titlePg/>" in doc

    # a screenplay has none
    with zipfile.ZipFile(BytesIO(export.generateDocx(avScript(key="screenplay")))) as z:
        assert "VIDEO" not in "".join(
            z.read(n).decode("utf-8") for n in z.namelist() if "header" in n
        )


# Up and Down go up and down the cursor's column, past the other one
def testUpDown():
    ed = scr.Editor(avScript())
    sp = ed.sp

    wide = lineOf(sp, "WIDE SHOT")
    music = lineOf(sp, "MUSIC")
    skyLast = music - 1
    traffic = lineOf(sp, "Traffic")
    narrationLast = traffic - 1
    late = lineOf(sp, "Some of them")
    interview = lineOf(sp, "2. INTERVIEW")

    def move(cmd, line, column=0):
        ed.line, ed.column = line, column
        ed.cmd(cmd)

        return ed.line

    # from the bottom of the video to the next row's video, not the audio
    # beside it
    assert move("moveDown", skyLast) == traffic
    assert move("moveUp", traffic) == skyLast
    assert move("moveDown", wide) == wide + 1

    # and the audio's
    assert move("moveDown", narrationLast) == late
    assert move("moveUp", late) == narrationLast
    assert move("moveUp", music) == 0

    # past the shorter column
    assert move("moveDown", traffic) == interview

    # into a row, the column under the cursor
    assert move("moveDown", 0) == wide
    assert sp.getColumnAt(0, 0) == LEFT
    sp.lines[0].text = "X" * 40
    assert sp.getColumnAt(0, 35) == RIGHT
    assert move("moveDown", 0, 35) == music
    assert move("moveUp", interview, 0) == traffic
    assert move("moveUp", interview, 35) == late

    # nothing below the end
    assert move("moveDown", len(sp.lines) - 1) == len(sp.lines) - 1

    assert sp.getRowAround(0) is None
    assert sp.getRowAround(wide) == (wide, music, narrationLast)
    assert sp.getRowAround(late) == (traffic, late, late)
    assert sp.getRowAround(interview + 1) is None

    # a script with one column goes line by line
    ed = scr.Editor(avScript(key="screenplay"))
    sp = ed.sp
    assert move("moveDown", lineOf(sp, "MUSIC") - 1) == lineOf(sp, "MUSIC")


# Sound elements complete to sound cues, not a screenplay's transitions
def testSoundCompletions():
    sp = u.new()
    scriptformats.get("av").applyTo(sp)
    items = sp.autoCompletion.getType(scr.TRANSITION).items

    assert items == scriptformats.AV_SOUNDS
    assert "CUT TO:" not in items

    # changing the format back brings the transitions back
    ed = scr.Editor(sp)
    ed.applyCfg(config.Config())
    assert "CUT TO:" in sp.autoCompletion.getType(scr.TRANSITION).items

    # but a list the user has changed is kept
    sp.autoCompletion.getType(scr.TRANSITION).items = ["WHOOSH"]
    cfg = config.Config()
    scriptformats.get("av").apply(cfg)
    ed.applyCfg(cfg)
    assert sp.autoCompletion.getType(scr.TRANSITION).items == ["WHOOSH"]

    # and an audio drama's Music elements, music cues
    sp = u.new()
    scriptformats.get("audiodrama").applyTo(sp)
    assert sp.autoCompletion.getType(scr.TRANSITION).items == (
        scriptformats.AUDIO_DRAMA_MUSIC
    )


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


# the script's elements as (type, text)
def elements(sp):
    return [(typ, txt) for typ, txt, first, fmt in getElementsAsList(sp)]


# a script made from an import's result, as MyCtrl.importFile does
def imported(result):
    sp = u.new()

    if result.format:
        scriptformats.get(result.format).applyTo(sp)

    sp.lines = result.lines
    sp.reformatAll()
    sp.paginate()

    return sp


# Fountain has no columns, so the elements go in order, with the format
# on the title page for Trelby to lay them out in columns again
def testFountainRoundTrip():
    sp = avScript()
    text = export.generateFountain(sp)

    assert "\nFormat: av\n" in "\n" + text

    # the narration with no speaker, after an empty forced character line
    assert "\n\n@\nSome of them are late." in text
    assert "\n\n@\nAudio alone." in text

    result = fountainImporter.parse(text)
    assert result.format == "av"
    sp2 = imported(result)

    assert scriptformats.ofConfig(sp2.cfg).key == "av"
    assert "FORMAT" not in str(
        [ts.items for page in result.titlePages for ts in page]
    ).upper()

    # Fountain has no shots: they come back as video (action), in the
    # same column
    want = [
        (scr.ACTION if typ == scr.SHOT else typ, txt) for typ, txt in elements(sp)
    ]
    assert elements(sp2) == want
    assert len(sp2.getRowLines(0, len(sp2.lines) - 1)) == len(
        sp.getRowLines(0, len(sp.lines) - 1)
    )

    # a screenplay says nothing
    sp = avScript(key="screenplay")
    text = export.generateFountain(sp)
    assert "Format:" not in text
    assert fountainImporter.parse(text).format is None

    # "@" forces a character name
    lines = fountainImporter.parse("Hi.\n\n@McCLANE\nYippee.\n").lines
    assert [(ln.lt, ln.text) for ln in lines] == [
        (scr.ACTION, "Hi."),
        (scr.CHARACTER, "McCLANE"),
        (scr.DIALOGUE, "Yippee."),
    ]

    # an unknown format is a title
    result = fountainImporter.parse("Format: widescreen\n\nHello.\n")
    assert result.format is None
    assert "Format: widescreen" in str(
        [ts.items for page in result.titlePages for ts in page]
    )


def testFdxRoundTrip():
    sp = avScript()
    data = export.generateFDX(sp).decode("utf-8")

    assert '<TrelbyScriptFormat Key="av"/>' in data

    result = fdxImporter.parse(data)
    assert result.format == "av"
    sp2 = imported(result)

    assert elements(sp2) == elements(sp)
    assert sp2.getRowLines(0, len(sp2.lines) - 1) == sp.getRowLines(
        0, len(sp.lines) - 1
    )

    sp = avScript(key="screenplay")
    data = export.generateFDX(sp).decode("utf-8")
    assert "TrelbyScriptFormat" not in data
    assert fdxImporter.parse(data).format is None
