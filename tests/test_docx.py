import io
import zipfile

from lxml import etree

import tests.u as u
import trelby.screenplay as scr
import trelby.screenplay.export as export
import trelby.screenplay.export.docx as docx
import trelby.screenplay.titles as titles
import trelby.translations as translations

_ = translations.trelby_translations_load()

# the DOCX export (screenplay/export/docx.py)

W = "{%s}" % docx.W_NS
NS = {"w": docx.W_NS}


def loadLines(lines, settings=()):
    ed = u.loadStringEditor(
        "\n".join(["#Version 3"] + list(settings) + ["#Start-Script "] + lines)
    )
    ed.sp.paginate()

    return ed.sp


# return the export's parts as {name: parsed xml}
def parts(sp):
    z = zipfile.ZipFile(io.BytesIO(export.generateDocx(sp)))

    return {name: etree.fromstring(z.read(name)) for name in z.namelist()}


def body(sp):
    return parts(sp)["word/document.xml"].find(W + "body")


# the text of a paragraph, with line breaks as \n, tabs as \t and fields
# as {NAME}
def text(p):
    s = ""

    # whether we're in a field's result, which Word replaces
    inResult = False

    for r in p.iter(W + "r"):
        for el in r:
            if el.tag == W + "fldChar":
                inResult = el.get(W + "fldCharType") == "separate"
            elif el.tag == W + "instrText":
                s += "{%s}" % el.text.strip()
            elif inResult:
                pass
            elif el.tag == W + "t":
                s += el.text or ""
            elif el.tag == W + "br":
                s += "\n"
            elif el.tag == W + "tab":
                s += "\t"

    return s


def style(p):
    ps = p.find("w:pPr/w:pStyle", NS)

    return ps.get(W + "val") if ps is not None else None


# the script's paragraphs, as (style, text)
def paragraphs(sp):
    return [
        (style(p), text(p))
        for p in body(sp).iter(W + "p")
        if style(p) is not None
    ]


def testPackageIsComplete():
    sp = u.load()
    sp.paginate()

    data = export.generateDocx(sp)
    z = zipfile.ZipFile(io.BytesIO(data))
    names = set(z.namelist())

    types = etree.fromstring(z.read("[Content_Types].xml"))
    overrides = {
        el.get("PartName").lstrip("/")
        for el in types
        if el.tag.endswith("Override")
    }

    # every xml part but the relationships has a content type, and every
    # relationship's target exists
    assert overrides == {
        n for n in names if not (n.endswith(".rels") or n.startswith("["))
    }

    rels = etree.fromstring(z.read("word/_rels/document.xml.rels"))

    for rel in rels:
        assert "word/" + rel.get("Target") in names

    for name in names:
        etree.fromstring(z.read(name))


def testElementsAreStyledParagraphs():
    sp = loadLines(
        [
            ".\\int. hall - night",
            "..The door opens.",
            "._jane",
            ".((quietly)",
            ".:Hello there.",
            "./CUT TO:",
        ]
    )

    # scene headings and characters are in capitals, as in the PDF
    assert paragraphs(sp) == [
        ("Scene", "INT. HALL - NIGHT"),
        ("Action", "The door opens."),
        ("Character", "JANE"),
        ("Parenthetical", "(quietly)"),
        ("Dialogue", "Hello there."),
        ("Transition", "CUT TO:"),
    ]


def testStylesFollowConfig():
    sp = loadLines(["..The door opens."])
    styles = parts(sp)["word/styles.xml"]
    cfg = sp.cfg
    cw = cfg.fontSize * 12

    for ti in [scr.ACTION, scr.DIALOGUE, scr.CHARACTER]:
        t = cfg.getType(ti)
        name = docx._styleId(ti)
        el = styles.find("w:style[@w:styleId='%s']" % name, NS)
        ind = el.find("w:pPr/w:ind", NS)
        spacing = el.find("w:pPr/w:spacing", NS)

        assert int(ind.get(W + "left")) == t.indent * cw
        assert int(spacing.get(W + "before")) == t.beforeSpacing * cfg.fontSize * 2

        # the text area is wide enough for the element's width, with less
        # than a character to spare
        textW = round(
            docx.util.mm2twips(cfg.paperWidth - cfg.marginLeft - cfg.marginRight)
        )
        width = textW - t.indent * cw - int(ind.get(W + "right"))
        assert t.width * cw < width < (t.width + 1) * cw

    sect = body(sp).find("w:sectPr", NS)
    pgSz = sect.find("w:pgSz", NS)

    assert int(pgSz.get(W + "w")) == round(docx.util.mm2twips(cfg.paperWidth))
    assert int(pgSz.get(W + "h")) == round(docx.util.mm2twips(cfg.paperHeight))


def testFormattingAndLineBreaks():
    sp = loadLines(
        [
            ".\\INT. HALL - NIGHT",
            "#Format 4-8:b",
            "..The door opens slowly.",
            "#Centered ",
            "|.THE END",
            "..for now",
        ]
    )
    b = body(sp)

    bold = [
        r.find("w:t", NS).text
        for r in b.iter(W + "r")
        if r.find("w:rPr/w:b", NS) is not None
    ]
    assert bold == ["door"]

    centered = [
        text(p) for p in b.iter(W + "p") if p.find("w:pPr/w:jc", NS) is not None
    ]
    assert centered == ["THE END\nfor now"]


def testTitlePagesAreFramesInTheirOwnSection():
    sp = loadLines(["..The door opens."])
    sp.titles.pages = [
        [
            titles.TitleString(["MY TITLE"], y=80.0, size=24, isBold=True),
            titles.TitleString(["Agent", "Phone"], x=200.0, y=240.0, isCentered=False),
        ]
    ]
    sp.titles.pages[0][1].isRightJustified = True
    b = body(sp)

    frames = [
        (text(p), p.find("w:pPr/w:framePr", NS))
        for p in b.iter(W + "p")
        if p.find("w:pPr/w:framePr", NS) is not None
    ]
    assert [t for t, f in frames] == ["MY TITLE", "Agent", "Phone"]
    assert frames[0][1].get(W + "xAlign") == "center"

    # the right-justified string's frame ends at its x
    f = frames[1][1]
    assert int(f.get(W + "x")) + int(f.get(W + "w")) == round(
        docx.util.mm2twips(200.0)
    )

    # the title pages end in a section break, and the script's section
    # numbers its pages from 1
    sects = list(b.iter(W + "sectPr"))
    assert len(sects) == 2
    assert sects[1].find("w:pgNumType", NS).get(W + "start") == "1"


def testHeadersAndFooter():
    sp = loadLines(["..The door opens."])
    sp.headers.addDefaults()
    sp.footer.left = "${TITLE}"
    sp.footer.right = "${PAGE} / ${PAGES}"
    sp.footer.showOnFirstPage = False
    sp.titles.pages = [[titles.TitleString(["MY TITLE"], kind=titles.TITLE)]]

    ps = parts(sp)
    sect = list(ps["word/document.xml"].iter(W + "sectPr"))[-1]
    refs = {
        (el.tag.split("}")[1], el.get(W + "type"))
        for el in sect
        if el.tag.endswith("Reference")
    }

    # nothing on the script's first page: no header there, and the footer
    # isn't on the first page either
    assert refs == {("headerReference", "default"), ("footerReference", "default")}
    assert sect.find("w:titlePg", NS) is not None

    hdr = text(ps["word/header1.xml"].find("w:p", NS))
    ftr = text(ps["word/footer1.xml"].find("w:p", NS))

    # the default header, with its empty line after it
    assert hdr == "\t\t{PAGE}."
    assert len(ps["word/header1.xml"].findall("w:p", NS)) == 2
    assert ftr == "MY TITLE\t\t{PAGE} / {SECTIONPAGES}"

    sp.footer.showOnFirstPage = True
    sect = list(body(sp).iter(W + "sectPr"))[-1]
    assert sect.find("w:footerReference[@w:type='first']", NS) is not None


def testDualDialogueIsATable():
    sp = loadLines(
        [
            ".\\INT. GARAGE - DAY",
            "._BRICK",
            ".:Go away.",
            "#Dual-Dialogue ",
            "._STEEL",
            ".:No.",
            "..They glare.",
        ]
    )
    b = body(sp)
    tables = b.findall("w:tbl", NS)

    assert len(tables) == 1

    cells = [
        [(style(p), text(p)) for p in tc.iter(W + "p")]
        for tc in tables[0].iter(W + "tc")
    ]
    assert cells == [
        [("Character", "BRICK"), ("Dialogue", "Go away.")],
        [("Character", "STEEL"), ("Dialogue", "No.")],
    ]
    assert ("Action", "They glare.") in paragraphs(sp)


def testPageStarts():
    sp = loadLines(
        [
            ".\\INT. HALL - NIGHT",
            "..The door opens.",
            ".@ACT TWO",
            ".\\INT. KITCHEN - DAY",
        ]
    )
    assert sp.cfg.pbActNewPage

    breaks = [
        text(p)
        for p in body(sp).iter(W + "p")
        if p.find("w:pPr/w:pageBreakBefore", NS) is not None
    ]
    assert breaks == ["ACT TWO"]


def testControlCharactersAreDropped():
    sp = loadLines(["..The door opens & <closes>."])
    sp.lines[0].text = "The \x01door\x0b opens & <closes>."

    assert ("Action", "The door opens & <closes>.") in paragraphs(sp)
