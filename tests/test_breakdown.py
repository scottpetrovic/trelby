import pytest

import tests.u as u
import trelby.screenplay as scr
import trelby.screenplay.breakdown as breakdown
import trelby.translations as translations
from trelby.screenplay.breakdown import Tag

_ = translations.trelby_translations_load()

# the production breakdown (screenplay/breakdown.py): tags on paragraphs,
# keeping them with their text through edits, the file format, and the
# breakdown worked out from them

SCRIPT = [
    "#Version 3",
    "#Start-Script ",
    ".\\INT. GARAGE - NIGHT",
    "#Tag props|Revolver|his gun",
    "..Mary watches John clean his gun on the hood of the red sports car,"
    " slowly, piece by piece, until the gun shines under the lamp.",
    "..John looks up.",
    "._JOHN",
    ".:Get in.",
    "._MARY",
    ".:No.",
    ".\\EXT. HIGHWAY - DAY",
    "#Tag vehicles|Sports car|sports car",
    "..The sports car speeds past.",
]


def load():
    return u.loadStringEditor("\n".join(SCRIPT))


def lineOf(ed, start):
    return next(i for i, ln in enumerate(ed.sp.lines) if ln.text.startswith(start))


# (line, category, name, text) of every tag
def allTags(ed):
    return [(i, t.category, t.name, t.text) for i, k, t in ed.sp.getAllTags()]


def testLoad():
    ed = load()
    car = lineOf(ed, "The sports car")

    assert allTags(ed) == [
        (1, "props", "Revolver", "his gun"),
        (car, "vehicles", "Sports car", "sports car"),
    ]
    assert ed.sp.lines[1].lb == scr.LB_SPACE
    ed._validate()


def testSaveRoundTrip():
    ed = load()
    ed.sp.lines[1].tags = (
        Tag("props", "A | B", "back\\slash"),
        Tag("newcategory", "Thing"),
    )

    s = ed.sp.save().decode("utf-8-sig")

    assert "#Tag props|A \\u007c B|back\\\\slash\n" in s
    assert "#Tag newcategory|Thing|\n" in s

    sp = u.loadString(s)
    assert sp.lines[1].tags == ed.sp.lines[1].tags


@pytest.mark.parametrize(
    "value",
    ["props|Gun", "Props|Gun|", "props||gun", "props|Gun|a|b"],
)
def testBadTagLinesAreIgnored(value):
    sp = u.loadString(
        "\n".join(["#Version 3", "#Start-Script ", "#Tag " + value, "..Gun."])
    )

    assert not sp.hasTags()


def testAddRemoveUndo():
    ed = load()
    ed.line, ed.column = 2, 3

    # any line of the paragraph will do; the tag goes on its first line
    assert ed.addTag(2, "vehicles", "  Sports   car ", "red sports car")
    assert ed.sp.lines[1].tags[1] == Tag("vehicles", "Sports car", "red sports car")
    assert not ed.sp.lines[2].tags

    # the same tag again isn't added, nor one without a name
    assert not ed.addTag(1, "vehicles", "sports CAR", "Red Sports Car")
    assert not ed.addTag(1, "props", " ", "x")

    ed.removeTag(2, 0)
    assert [t.name for t in ed.sp.lines[1].tags] == ["Sports car"]

    # the cursor stays put
    assert (ed.line, ed.column) == (2, 3)

    ed.cmd("undo")
    assert [t.name for t in ed.sp.lines[1].tags] == ["Revolver", "Sports car"]

    ed.cmd("undo")
    assert [t.name for t in ed.sp.lines[1].tags] == ["Revolver"]

    ed.cmd("redo")
    ed.cmd("redo")
    assert [t.name for t in ed.sp.lines[1].tags] == ["Sports car"]
    ed._validate()


def testSpans():
    ed = load()
    sp = ed.sp
    sp.lines[1].tags += (Tag("props", "Gun", "gun"),)

    # the paragraph's text, across its lines
    text = ""
    i = 1

    while True:
        spans = sp.getLineTagSpans(i)
        found = [(sp.lines[i].text[a:b], t.name) for a, b, t in spans]
        text += str(found)

        if sp.lines[i].lb == scr.LB_LAST:
            break

        i += 1

    # whole words only, ignoring case, wherever they are in the paragraph
    assert text.count("('his gun', 'Revolver')") == 1
    assert text.count("('gun', 'Gun')") == 2
    assert "shines" not in text

    first = sp.getLineTagSpans(1)[0]
    assert sp.getTagsAt(1, first[0]) == [(1, 0, sp.lines[1].tags[0])]
    assert sp.getTagsAt(1, 0) == []


def testTagSpanningTwoLines():
    sp = load().sp
    first = sp.lines[1]

    # tag the last word of the first line and the first of the second
    words = first.text.split()
    text = words[-1] + " " + sp.lines[2].text.split()[0]
    first.tags = (Tag("props", "X", text),)

    a, b, tag = sp.getLineTagSpans(1)[-1]
    assert b == len(first.text)
    assert sp.getLineTagSpans(2)[0][0] == 0


def testTypingKeepsTagOnFirstLine():
    ed = load()
    ed.line, ed.column = 1, 0

    for ch in "Slowly and with great care, ":
        ed.cmd("addChar", char=ch)

    assert allTags(ed)[0] == (1, "props", "Revolver", "his gun")
    ed._validate()


def testJoiningKeepsBothTags():
    ed = load()
    ed.sp.lines[lineOf(ed, "John looks")].tags = (Tag("cast", "John", "John"),)
    ed.line, ed.column = lineOf(ed, "John looks"), 0

    ed.cmd("deleteBackward")

    assert [t.name for t in ed.sp.getParaTags(1)] == ["Revolver", "John"]
    ed._validate()


@pytest.mark.parametrize("command", ["splitElement", "insertForcedLineBreak"])
def testSplittingAtStartMovesTagWithText(command):
    ed = load()
    ed.line, ed.column = 1, 0

    ed.cmd(command)

    assert not ed.sp.lines[1].tags
    assert [t.name for t in ed.sp.lines[2].tags] == ["Revolver"]
    ed._validate()

    ed.cmd("undo")
    assert [t.name for t in ed.sp.lines[1].tags] == ["Revolver"]


def testCutAndPasteMoveTags():
    ed = load()

    ed.selectElementAt(1)
    cd = ed.getSelectedAsCD(True)

    assert "Revolver" not in [n for i, c, n, t in allTags(ed)]
    assert [t.name for t in cd.lines[0].tags] == ["Revolver"]

    last = len(ed.sp.lines) - 1
    ed.line, ed.column = last, len(ed.sp.lines[last].text)
    ed.paste(cd.lines)

    para = ed.sp.getParaFirstIndexFromLine(len(ed.sp.lines) - 1)
    assert "Revolver" in [t.name for t in ed.sp.lines[para].tags]

    ed.cmd("undo")
    ed.cmd("undo")
    assert [t.name for t in ed.sp.lines[1].tags] == ["Revolver"]
    ed._validate()


def testDeletingPartOfParagraphKeepsTag():
    ed = load()

    ed.setMark(2, 2)
    ed.line, ed.column = 1, 0
    ed.getSelectedAsCD(True)

    assert [t.name for t in ed.sp.lines[1].tags] == ["Revolver"]
    ed._validate()


def testBreakdown():
    ed = load()
    sp = ed.sp
    sp.paginate()

    scenes = sp.getBreakdown()
    assert len(scenes) == 2

    garage, highway = scenes
    assert (garage.intExt, garage.place, garage.time) == ("INT.", "GARAGE", "NIGHT")
    assert garage.number == "1"
    assert garage.page == "1"
    assert garage.eighths >= 1
    assert garage.elements == {"cast": ["JOHN", "MARY"], "props": ["Revolver"]}
    assert highway.elements == {"vehicles": ["Sports car"]}

    assert sp.getBreakdown(castSpeakers=False)[0].elements == {"props": ["Revolver"]}


def testElementList():
    ed = load()
    sp = ed.sp
    garage = 0
    highway = lineOf(ed, "EXT. HIGHWAY")

    # a tagged cast member who also speaks is one element, and so are
    # names differing only in case
    ed.addTag(1, "cast", "mary", "Mary")
    ed.addTag(1, "vehicles", "SPORTS CAR", "sports car")

    elems = [(e.category, e.name, e.scenes, e.tagged) for e in sp.getElementList()]

    assert elems == [
        ("cast", "JOHN", [garage], False),
        ("cast", "MARY", [garage], True),
        ("vehicles", "SPORTS CAR", [garage, highway], True),
        ("props", "Revolver", [garage], True),
    ]


def testSceneElementsAndActBreaks():
    ed = u.loadStringEditor(
        "\n".join(
            [
                "#Version 3",
                "#Start-Script ",
                ".@ACT ONE",
                "..Rain falls.",
                ".\\INT. HALL",
                "..Ann waits.",
            ]
        )
    )
    sp = ed.sp

    # the part after the act break, before the first heading, is a scene
    # of its own once something is tagged in it; the act break isn't part
    # of it
    assert sp.getBreakdownScenes() == [(2, 3)]

    assert ed.addSceneElement(1, "sfx", "Rain machine")
    assert sp.getBreakdownScenes() == [(1, 1), (2, 3)]
    assert sp.lines[1].tags == (Tag("sfx", "Rain machine"),)
    assert not ed.addSceneElement(1, "sfx", "rain MACHINE")

    assert ed.addSceneElement(3, "props", "Umbrella")
    assert sp.lines[2].tags == (Tag("props", "Umbrella"),)

    scenes = sp.getBreakdown()
    assert scenes[0].heading == ""
    assert scenes[0].elements == {"sfx": ["Rain machine"]}


def testRenameAndRemoveElement():
    ed = load()
    highway = lineOf(ed, "EXT. HIGHWAY")
    ed.addTag(1, "vehicles", "sports car", "sports car")

    assert ed.renameElement("vehicles", "SPORTS CAR", "vehicles", "Ferrari")
    assert [t.name for i, k, t in ed.sp.getAllTags()] == [
        "Revolver",
        "Ferrari",
        "Ferrari",
    ]
    assert not ed.renameElement("vehicles", "Nothing", "props", "X")

    # from one scene, then the whole script
    assert ed.removeElement("vehicles", "ferrari", highway)
    assert [t.name for i, k, t in ed.sp.getAllTags()] == ["Revolver", "Ferrari"]

    assert ed.removeElement("vehicles", "Ferrari")
    assert [t.name for i, k, t in ed.sp.getAllTags()] == ["Revolver"]

    ed.cmd("undo")
    ed.cmd("undo")
    ed.cmd("undo")
    assert [t.name for i, k, t in ed.sp.getAllTags()] == [
        "Revolver",
        "sports car",
        "Sports car",
    ]
    ed._validate()


def testMoveCategory():
    ed = load()

    assert ed.renameElement("props", "Revolver", "sfx", "Revolver")
    assert ed.sp.lines[1].tags == (Tag("sfx", "Revolver", "his gun"),)


@pytest.mark.parametrize(
    "heading, parts",
    [
        ("INT. MOTEL ROOM - NIGHT", ("INT.", "MOTEL ROOM", "NIGHT")),
        ("ext garden - later", ("EXT.", "garden", "LATER")),
        ("INT./EXT. CAR - DAY", ("INT./EXT.", "CAR", "DAY")),
        ("I/E. CAR - DAY", ("I/E.", "CAR", "DAY")),
        ("SPACE STATION", ("", "SPACE STATION", "")),
        ("INT. A - B - DAY", ("INT.", "A - B", "DAY")),
        ("INTERIOR", ("", "INTERIOR", "")),
    ],
)
def testSplitHeading(heading, parts):
    assert breakdown.splitHeading(heading) == parts


def testEighthsText():
    assert [breakdown.eighthsText(n) for n in (1, 5, 8, 11, 16)] == [
        "1/8",
        "5/8",
        "1",
        "1 3/8",
        "2",
    ]


def testCategories():
    keys = [c.key for c in breakdown.CATEGORIES]

    assert len(set(keys)) == len(keys)
    assert breakdown.category("unknown").key == "misc"

    for c in breakdown.CATEGORIES:
        assert len(c.color) == 6
        assert c.label()


def testDeepcopyKeepsTags():
    import copy

    ed = load()
    sp = copy.deepcopy(ed.sp)

    assert sp.getAllTags() == ed.sp.getAllTags()


# the MCP tools: elements' tags, and get_breakdown


@pytest.fixture
def scriptFile(tmp_path):
    path = str(tmp_path / "garage.trelby")

    with open(path, "w", encoding="UTF-8") as f:
        f.write("\n".join(SCRIPT) + "\n")

    return path


def testMcpReadAndReplaceKeepTags(scriptFile):
    import trelby.mcpserver.tools as m

    doc = m.FileDoc(scriptFile)
    res = m.readScenes(doc, 1)
    action = res["scenes"][0]["elements"][1]

    assert action["tags"] == [
        {"category": "props", "name": "Revolver", "text": "his gun"}
    ]

    elements = res["scenes"][0]["elements"]
    elements[2]["tags"] = [{"category": "cast", "name": "John", "text": "John"}]

    m.replaceScene(doc, res["revision"], 1, elements)

    sp = m.FileDoc(scriptFile).read()[0]
    assert [(t.category, t.name) for i, k, t in sp.getAllTags()] == [
        ("props", "Revolver"),
        ("cast", "John"),
        ("vehicles", "Sports car"),
    ]


@pytest.mark.parametrize(
    "tag, error",
    [
        ({"category": "food", "name": "Cake"}, "Unknown breakdown category"),
        ({"category": "props", "name": " "}, "without a name"),
        ({"category": "props", "name": 5}, "isn't"),
    ],
)
def testMcpBadTags(scriptFile, tag, error):
    import trelby.mcpserver.tools as m

    doc = m.FileDoc(scriptFile)
    rev = m.listScenes(doc)["revision"]

    with pytest.raises(m.ToolError) as e:
        m.replaceScene(
            doc, rev, 1, [{"type": "scene", "text": "INT. A", "tags": [tag]}]
        )

    assert error in str(e.value)


def testMcpGetBreakdown(scriptFile):
    import trelby.mcpserver.tools as m

    res = m.getBreakdown(m.FileDoc(scriptFile))

    assert res["categories"]["props"] == "Props"
    assert [
        (s["index"], s["scene_number"], s["int_ext"], s["time"], s["elements"])
        for s in res["scenes"]
    ] == [
        (1, "1", "INT.", "NIGHT", {"cast": ["JOHN", "MARY"], "props": ["Revolver"]}),
        (2, "2", "EXT.", "DAY", {"vehicles": ["Sports car"]}),
    ]
    assert res["elements"][2] == {
        "category": "vehicles",
        "name": "Sports car",
        "scenes": [2],
        "tagged": True,
    }

    res = m.getBreakdown(m.FileDoc(scriptFile), castSpeakers=False)
    assert "cast" not in res["scenes"][0]["elements"]


def testSelectedTagText():
    ed = load()

    assert ed.getSelectedTagText() is None

    # across the paragraph's line break
    ln = ed.sp.lines[1].text
    ed.setMark(1, len(ln) - 3)
    ed.line, ed.column = 2, 4
    first, text = ed.getSelectedTagText()

    assert first == 1
    assert text == ln[-3:] + " " + ed.sp.lines[2].text[:5]

    # into the next paragraph
    ed.line = lineOf(ed, "John looks")
    assert ed.getSelectedTagText() is None


def testCsvExport():
    import csv
    import io

    import trelby.formats as formats

    ed = load()
    ed.sp.paginate()
    fmt = formats.find(formats.EXPORT_FORMATS, "breakdown")

    s = fmt.generate(ed.sp)
    assert s.startswith("﻿")

    rows = list(csv.reader(io.StringIO(s[1:])))
    header = rows[0]

    assert header[:8] == [
        "Scene",
        "Heading",
        "Int/Ext",
        "Location",
        "Time",
        "Page",
        "Pages",
        "Eighths",
    ]
    assert len(header) == 8 + len(breakdown.CATEGORIES)
    assert len(rows) == 3

    garage = dict(zip(header, rows[1]))
    assert garage["Scene"] == "1"
    assert garage["Location"] == "GARAGE"
    assert garage["Cast"] == "JOHN; MARY"
    assert garage["Props"] == "Revolver"

    s = fmt.generate(ed.sp, castSpeakers=False)
    garage = dict(zip(header, list(csv.reader(io.StringIO(s[1:])))[1]))
    assert garage["Cast"] == ""


def testReport():
    import trelby.reports.breakdownreport as breakdownreport

    ed = load()
    ed.sp.paginate()
    report = breakdownreport.BreakdownReport(ed.sp)

    html = report.generateHtml()
    assert "Props: Revolver" in html.replace("&nbsp;", " ")
    assert "ELEMENTS" in html

    report.opts["elements"] = False
    assert "ELEMENTS" not in report.generateHtml()

    assert report.generate().startswith(b"%PDF")


# Final Draft (FDX): the tags as its tagger's TagData, and back

FDX_PROPS = "05c556eb-6bc1-4a3a-b09f-f8b5ba1b6afa"
FDX_CAST = "01fc9642-84ff-4366-b37c-a3068dee57e8"


def fdxTagged():
    ed = load()
    ed.addSceneElement(0, "sfx", "Rain machine")
    ed.addSceneElement(0, "cast", "Stunt double")
    car = lineOf(ed, "The sports car")
    ed.addTag(car, "props", "Car keys", "car")
    ed.addTag(lineOf(ed, "JOHN"), "cast", "John", "John")
    ed.sp.paginate()

    return ed


def fdxRoot(sp):
    from lxml import etree

    import trelby.screenplay.export as export

    return etree.fromstring(export.generateFDX(sp))


def testFdxExportTags():
    ed = fdxTagged()
    root = fdxRoot(ed.sp)

    # every Final Draft category, with its own Id, the ones Trelby has in
    # Trelby's colors
    cats = root.xpath("TagData/TagCategories/TagCategory")
    assert [c.get("Name") for c in cats] == [
        c[0] for c in breakdown.FDX_CATEGORIES
    ]
    props = root.xpath("TagData/TagCategories/TagCategory[@Name='Props']")[0]
    assert props.get("Id") == FDX_PROPS
    assert props.get("Color") == "#8E8E2424AAAA"

    defs = {
        d.get("Label"): d for d in root.xpath("TagData/TagDefinitions/TagDefinition")
    }
    assert list(defs) == [
        "Rain machine",
        "Stunt double",
        "Revolver",
        "John",
        "Sports car",
        "Car keys",
    ]
    assert defs["Revolver"].get("CatId") == FDX_PROPS
    assert defs["John"].get("CatId") == FDX_CAST

    # Tag number -> labels of the elements it names
    tags = {
        t.get("Number"): [
            [k for k, d in defs.items() if d.get("Id") == i.text][0]
            for i in t.xpath("DefId")
        ]
        for t in root.xpath("TagData/Tags/Tag")
    }

    # text run -> the elements tagged on it
    runs = [
        (t.text, tags[t.get("TagNumber")])
        for t in root.xpath("Content//Text[@TagNumber]")
    ]
    assert runs == [
        # the scene's elements that its text doesn't mention are on its
        # heading
        ("INT. GARAGE - NIGHT", ["Rain machine", "Stunt double"]),
        ("his gun", ["Revolver"]),
        ("JOHN", ["John"]),
        # overlapping tags: a Tag naming both
        ("sports ", ["Sports car"]),
        ("car", ["Sports car", "Car keys"]),
    ]

    # the same Ids every time
    assert fdxRoot(ed.sp).xpath("TagData/TagDefinitions/TagDefinition/@Id") == [
        d.get("Id") for d in defs.values()
    ]


def testFdxExportWithoutTags():
    ed = u.loadStringEditor("\n".join(SCRIPT[:3]))
    ed.sp.lines[0].tags = ()
    ed.sp.paginate()

    root = fdxRoot(ed.sp)
    assert not root.xpath("TagData")
    assert not root.xpath("//Text[@TagNumber]")


# the tags of each imported line that has some, as (text, set of tags)
def importedTags(lines):
    return [(ln.text, set(ln.tags)) for ln in lines if ln.tags]


def testFdxRoundTrip():
    import trelby.importers.fdx as fdximport
    import trelby.screenplay.export as export

    ed = fdxTagged()
    lines = fdximport.parse(export.generateFDX(ed.sp).decode("UTF-8")).lines

    # the export writes character names etc. in capitals, which the tags'
    # texts match all the same
    def same(tags):
        return {(t.key, t.text.lower()) for t in tags}

    want = [same(ln.tags) for ln in ed.sp.lines if ln.tags]
    got = importedTags(lines)

    assert want == [same(tags) for _s, tags in got]
    assert got[0][0] == "INT. GARAGE - NIGHT"
    assert Tag("sfx", "Rain machine") in got[0][1]


def testFdxImportFinalDraftTags():
    import pathlib

    import trelby.importers.fdx as fdximport

    path = pathlib.Path("tests/fixtures/import/tagged.fdx")
    lines = fdximport.parse(path.read_text(encoding="UTF-8")).lines

    assert importedTags(lines) == [
        ("INT. BOATHOUSE - NIGHT", {Tag("setdressing", "Boathouse", "BOATHOUSE")}),
        (
            "Mara lifts the old lantern and the shotgun. A heron watches.",
            {
                Tag("cast", "MARA", "Mara"),
                # a tag over two text runs (in different styles)
                Tag("props", "Lantern", "old lantern"),
                # a Tag naming two elements, one in a category Trelby hasn't
                # got
                Tag("misc", "Shotgun", "shotgun"),
                Tag("props", "Shotgun shells", "shotgun"),
                Tag("animals", "Heron", "heron"),
            },
        ),
        ("MARA", {Tag("cast", "MARA", "MARA")}),
        ("Where's the lantern?", {Tag("props", "Lantern", "lantern")}),
        # a whole heading tagged is an element of the scene, with no text
        ("EXT. DOCK - DAY", {Tag("misc", "Lake dock")}),
        # an element with no name is named by its text; an unknown DefId is
        # ignored
        ("Fog rolls in.", {Tag("sfx", "Fog", "Fog")}),
    ]


@pytest.mark.parametrize(
    "name, key",
    [
        ("Cast Members", "cast"),
        ("Background Actors", "extras"),
        ("Makeup/Hair", "makeup"),
        ("Makeup / hair", "makeup"),
        ("Special Effects", "sfx"),
        ("special effects", "sfx"),
        ("Mechanical Effects", "sfx"),
        ("Set Dressing", "setdressing"),
        ("setdressing", "setdressing"),
        ("Greenery", "setdressing"),
        ("Special Equipment", "equipment"),
        ("Visual Effects", "vfx"),
        ("Miscellaneous", "misc"),
        ("Weapons", "misc"),
        ("Location", "misc"),
        ("", "misc"),
    ],
)
def testCategoryFromFdx(name, key):
    assert breakdown.categoryFromFdx(name) == key


def testFdxCategoriesCoverTrelbys():
    keys = [c[3] for c in breakdown.FDX_CATEGORIES if c[3]]

    assert sorted(keys) == sorted(c.key for c in breakdown.CATEGORIES)
