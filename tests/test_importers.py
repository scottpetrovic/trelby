# the script importers, on the sample files in tests/fixtures/import: the
# lines, line types and title pages each one makes, and the errors it
# reports. tests/importrun.py runs them with the options dialogs answered.

import sys
import zipfile

import pytest

import tests.importrun as importrun
import tests.pdffixture as pdffixture
import tests.u as u
import trelby.formats as formats
import trelby.importers as importers
import trelby.pdf.pml as pml
import trelby.screenplay as screenplay
import trelby.screenplay.export as export
import trelby.screenplay.titles as titles
from tests.importrun import Failed, dumpLines, dumpTitles

SCENE_ACTION = importers.text.SCENE_ACTION
IGNORE = importers.text.IGNORE


def sample(ext):
    return u.fixtureFilePath("import/sample." + ext)


def run(key, path, **options):
    return importrun.run(key, path, **options)


def defaultTitlePages():
    t = titles.Titles()
    t.addDefaults()

    return t.pages


def testAstx():
    lines, titlePages = run("astx", sample("astx"))

    assert titlePages is None
    assert dumpLines(lines) == [
        "LAST SCENE 'INT. KITCHEN - DAY'",
        "FORCED ACTION 'Steam rises from a pot.'",
        "LAST ACTION 'A second line.'",
        "LAST CHARACTER 'ANNA'",
        "LAST PAREN '(quietly)'",
        "LAST DIALOGUE \"It's ready.\"",
        "LAST SHOT 'CLOSE ON THE POT'",
        "LAST TRANSITION 'CUT TO:'",
        "LAST SCENE 'EXT. GARDEN - NIGHT'",
        "LAST ACTION 'Caf\xe9 lights.'",
        "LAST ACTION ''",
        "FORCED ACTION ''",
        "FORCED ACTION ''",
        "LAST ACTION 'Two breaks.'",
    ]


def testFadein():
    lines, titlePages = run("fadein", sample("fadein"))

    assert titlePages is None
    assert dumpLines(lines) == [
        "LAST SCENE 'INT. BARN - NIGHT'",
        "FORCED NOTE 'A bold note'",
        "LAST NOTE 'on two lines'",
        "LAST NOTE 'The storm arrives.'",
        "FORCED ACTION 'Rain hammers the roof.'",
        "LAST ACTION 'Thunder.'",
        "LAST CHARACTER 'TOM'",
        "FORCED PAREN '(whispering'",
        "LAST PAREN 'softly)'",
        "LAST DIALOGUE 'Hello there.'",
        "LAST PAREN '(already wrapped)'",
        "LAST DIALOGUE 'Underlined'",
        "LAST NOTE 'Note without text'",
        "LAST TRANSITION 'FADE OUT.'",
        "LAST ACTION 'No style means action.'",
        "LAST ACTION 'Unknown style.'",
        "LAST ACTION ''",
        "LAST SHOT 'WIDE ON THE BARN'",
    ]


def testCeltx():
    lines, titlePages = run("celtx", sample("celtx"))

    assert titlePages is None
    assert dumpLines(lines) == [
        "LAST ACTBREAK 'ACT ONE'",
        "LAST SCENE 'INT. SHIP - DAY'",
        "LAST ACTION 'Waves crash against the hull.'",
        "LAST CHARACTER 'MAYA'",
        "LAST PAREN '(shouting)'",
        # each text node is a line of its own
        "FORCED DIALOGUE 'Hold'",
        "FORCED DIALOGUE 'on'",
        "LAST DIALOGUE '!'",
        "LAST SHOT 'CLOSE ON THE ROPE'",
        "LAST TRANSITION 'CUT TO:'",
        "LAST ACTION 'Unknown class.'",
        "FORCED ACTION 'Caf\xe9 au lait.'",
        "LAST ACTION 'Second line.'",
    ]


def testFDX():
    lines, titlePages = run("fdx", sample("fdx"))

    assert titlePages is None
    assert dumpLines(lines) == [
        "LAST SCENE 'INT. OFFICE - DAY'",
        "LAST ACTION 'The door opens slowly.' fmt=0000111100000006666660",
        "FORCED ACTION 'First line'",
        "FORCED ACTION 'second line'",
        "LAST ACTION 'third line'",
        "FORCED NOTE 'Note one'",
        "LAST NOTE 'Note two'",
        "LAST ACTION 'Has a note.'",
        "LAST NOTE 'Only a note'",
        "LAST ACTION ''",
        "LAST CHARACTER 'JOE'",
        "LAST PAREN '(beat)'",
        "LAST DIALOGUE 'Hello.'",
        "LAST CHARACTER 'AMY'",
        "LAST DIALOGUE 'Left.'",
        "LAST CHARACTER 'BEN' dual",
        "LAST DIALOGUE 'Right.'",
        "LAST SHOT 'ANGLE ON JOE'",
        "LAST ACTION 'Unknown type.'",
        "LAST TRANSITION 'CUT TO:'",
        "LAST ACTION 'THE END' centered",
        "LAST CHARACTER 'NOT CENTERED'",
    ]


TEXT_GUESSED = [
    "LAST SCENE 'INT. KITCHEN - DAY'",
    "SPACE ACTION 'Steam rises from a pot. It bubbles'",
    "LAST ACTION 'and spits.'",
    "LAST CHARACTER 'ANNA'",
    "LAST PAREN '(quietly)'",
    "SPACE DIALOGUE \"It's ready, she says, and\"",
    "LAST DIALOGUE 'it really is.'",
    "LAST CHARACTER 'BEN'",
    "LAST DIALOGUE 'What?'",
    "LAST CHARACTER 'ANNA'",
    "SPACE PAREN '(smiling and'",
    "LAST PAREN 'hopping along)'",
    "LAST DIALOGUE 'Nothing.'",
    "LAST TRANSITION 'CUT TO:'",
    "LAST SCENE 'EXT. GARDEN - NIGHT'",
    "SPACE ACTION 'Quiet.'",
    "LAST ACTION '12.'",
]


# with the guessed line types accepted
def testText():
    lines, titlePages = run("text", sample("txt"))

    assert titlePages is None
    assert dumpLines(lines) == TEXT_GUESSED


# with some line types changed in the dialog: the page number ignored, and
# scene headings taken as action
def testTextChangedTypes():
    lines, titlePages = run(
        "text", sample("txt"), lineTypes={60: IGNORE, 0: screenplay.ACTION}
    )

    assert dumpLines(lines) == [
        "LAST ACTION 'INT. KITCHEN - DAY'",
        "SPACE ACTION 'Steam rises from a pot. It bubbles'",
        "LAST ACTION 'and spits.'",
    ] + TEXT_GUESSED[3:14] + [
        "LAST ACTION 'EXT. GARDEN - NIGHT'",
        "LAST ACTION 'Quiet.'",
    ]


def testTextCancel():
    assert run("text", sample("txt"), cancel=True) is None


# sample.pdf (made by tests/pdffixture.py) with the guessed line types:
# the scene numbers, page numbers, CONTINUED, (MORE) and the repeated name
# are gone, the dialogue split by the page break is joined up, the
# right-aligned transitions are one indent level, and the dual dialogue's
# columns come one after the other
PDF_GUESSED = [
    "LAST ACTION 'FADE IN:'",
    "LAST SCENE 'INT. KITCHEN - DAY'",
    "SPACE ACTION 'Anna stirs a pot. Steam rises and fills the small'",
    "LAST ACTION 'room.'",
    "LAST CHARACTER 'ANNA'",
    "LAST PAREN '(quietly)'",
    "SPACE DIALOGUE \"It's almost ready. Just a few\"",
    "LAST DIALOGUE 'more minutes.'",
    "LAST CHARACTER 'BEN (V.O.)'",
    "LAST DIALOGUE \"Good. I'm starving.\"",
    "LAST ACTION 'He sits down.'",
    "LAST TRANSITION 'CUT TO:'",
    "LAST SCENE 'EXT. GARDEN - NIGHT'",
    "LAST ACTION 'Crickets.'",
    "LAST CHARACTER 'ANNA'",
    "SPACE DIALOGUE 'Did you hear that? Something is out'",
    "SPACE DIALOGUE 'there in the dark, waiting for us'",
    "LAST DIALOGUE 'to make a mistake.'",
    "LAST CHARACTER 'BEN'",
    "SPACE DIALOGUE \"Nothing's there.\"",
    "LAST DIALOGUE 'Go to sleep.'",
    "LAST CHARACTER 'ANNA'",
    "LAST DIALOGUE \"Something's there.\"",
    "LAST ACTION 'They look at each other.'",
    "LAST TRANSITION 'DISSOLVE TO:'",
    "LAST SCENE 'INT. KITCHEN - LATER'",
    "LAST ACTION 'The pot is empty.'",
    "LAST TRANSITION 'FADE OUT.'",
]

PDF_TITLES = [
    [
        (["THE TEST SCRIPT"], 0.0, 98.7, True, "title"),
        (["Written by", "", "Some Writer"], 0.0, 114.96, True, "byline"),
        (["Some Writer", "writer@example.com"], 38.1, 233.5, False, "contact"),
    ]
]


def testPdf():
    lines, titlePages = run("pdf", sample("pdf"), titlePages=defaultTitlePages())

    assert dumpLines(lines) == PDF_GUESSED
    assert dumpTitles(titlePages) == PDF_TITLES

    title = titlePages[0][0]
    assert (title.size, title.isBold, title.font) == (24, True, pml.HELVETICA)


# the transitions ignored and the dialogue taken as action in the dialog
def testPdfChangedTypes():
    lines, titlePages = run(
        "pdf", sample("pdf"), lineTypes={63: IGNORE, 25: screenplay.ACTION}
    )

    assert dumpLines(lines)[:8] == PDF_GUESSED[:6] + [
        "SPACE ACTION \"It's almost ready. Just a few\"",
        "LAST ACTION 'more minutes.'",
    ]
    assert "LAST TRANSITION 'CUT TO:'" not in dumpLines(lines)


def testPdfCancel():
    assert run("pdf", sample("pdf"), cancel=True) is None


# a PDF of the sample script, made by Trelby's own export, imports as the
# script it was made from: the same elements, in capitals where the export
# makes them so, with the same title page. the one difference is that
# lines in capitals on their own, at the scene heading indent, are taken
# as scene headings ("MAP OF THE ATLANTIC OCEAN" is one in the sample,
# "LATER" isn't).
def testPdfRoundTrip(tmp_path):
    with open("trelby/sample.trelby", encoding="UTF-8") as f:
        sp = u.loadString(f.read())

    sp.paginate()
    path = tmp_path / "sample.pdf"
    path.write_bytes(export.generatePDF(sp))

    lines, titlePages = run("pdf", path)

    def elems(lines):
        ret = []
        texts = []

        for ln in lines:
            texts.append(ln.text)

            if ln.lb == screenplay.LB_LAST:
                ret.append((ln.lt, " ".join(texts).upper()))
                texts = []

        return ret

    orig = elems(sp.lines)
    imported = elems(lines)

    assert len(imported) == len(orig)

    diffs = [(a, b) for a, b in zip(orig, imported) if a != b]

    assert diffs == [
        ((screenplay.ACTION, text), (screenplay.SCENE, text))
        for text in ["LATER", "LATER", "2 MINUTES LATER"]
    ]

    # x doesn't matter for centered strings, and the kinds are guessed
    def dumpTitle(ts):
        return (
            ts.items,
            None if ts.isCentered else round(ts.x, 2),
            round(ts.y, 2),
            ts.getAlignment(),
            ts.size,
            ts.getStyle(),
        )

    assert [[dumpTitle(ts) for ts in page] for page in titlePages] == [
        [dumpTitle(ts) for ts in page] for page in sp.titles.pages
    ]
    assert [ts.kind for ts in titlePages[0]] == [
        "title",
        "byline",
        "copyright",
        "contact",
    ]


# headers repeated on most pages are taken out, wherever they are
def testPdfRepeatedHeader(tmp_path):
    path = str(tmp_path / "header.pdf")
    w = pdffixture.Writer(path)

    words = ["One", "Two", "Three", "Four"]

    for n, word in enumerate(words):
        if n:
            w.page(n + 1)

        w.line(15, "Blue draft 10/%d/26" % (n + 1))
        w.blank()
        w.line(15, "INT. ROOM %s - DAY" % word.upper())
        w.blank()
        w.line(15, "Action on page %s." % word)
        w.blank()
        w.line(15, "Page %s goes on." % word)

    w.save()

    lines, titlePages = run("pdf", path)

    assert titlePages is None
    assert dumpLines(lines) == [
        s
        for word in words
        for s in [
            "LAST SCENE 'INT. ROOM %s - DAY'" % word.upper(),
            "LAST ACTION 'Action on page %s.'" % word,
            "LAST ACTION 'Page %s goes on.'" % word,
        ]
    ]


# a PDF with only page furniture in it
def testPdfOnlyFurniture(tmp_path):
    path = str(tmp_path / "numbers.pdf")
    w = pdffixture.Writer(path)
    w.page(2)
    w.save()

    with pytest.raises(Failed) as e:
        run("pdf", path)

    assert e.value.message == "The file contains no importable lines"


def testPdfNoText(tmp_path):
    path = str(tmp_path / "empty.pdf")
    pdffixture.Writer(path).save()

    with pytest.raises(Failed) as e:
        run("pdf", path)

    assert e.value.message.startswith("The PDF file contains no text.")


def testPdfWithoutPypdf(monkeypatch):
    # a None in sys.modules makes importing it fail
    monkeypatch.setitem(sys.modules, "pypdf", None)
    importers.pdf._convertPDF.cache_clear()

    with pytest.raises(Failed) as e:
        run("pdf", sample("pdf"))

    assert "pypdf" in e.value.message


FOUNTAIN_SCRIPT = [
    "LAST SCENE 'INT. KITCHEN - DAY'",
    "LAST ACTION 'Steam rises from a pot.  It bubbles.'"
    " fmt=000000000000000000011100000044444440",
    "LAST CHARACTER 'ANNA'",
    "LAST PAREN '(quietly)'",
    "FORCED DIALOGUE \"It's ready.\"",
    "FORCED DIALOGUE '  '",
    "LAST DIALOGUE 'Really ready.'",
    "LAST CHARACTER 'BEN' dual",
    "LAST DIALOGUE 'What?'",
    "LAST TRANSITION 'CUT TO:'",
    "LAST SCENE 'FLASHBACK'",
    "LAST NOTE 'Remember the pot.'",
    "LAST ACTION 'SMASH CUT' centered",
    "FORCED ACTION 'THE END' centered",
    "LAST ACTION 'REALLY'",
    "LAST ACTION '==='",
    "LAST TRANSITION 'FADE OUT.'",
    "LAST ACTION ''",
    "LAST ACTION 'Last line.'",
]

FOUNTAIN_SECTIONS = [
    "LAST NOTE 'Act One'",
    "LAST NOTE 'The kitchen wakes up.'",
]

FOUNTAIN_TITLE_LINES = [
    "FORCED ACTION 'Title: The Pot' fmt=00000001111111",
    "FORCED ACTION 'Credit: Written by'",
    "FORCED ACTION 'Author: Anna Smith'",
    "FORCED ACTION 'Source: Based on a true story'",
    "FORCED ACTION 'Draft date: 1 May 2026'",
    "FORCED ACTION 'Contact:'",
    "FORCED ACTION '    Anna Smith'",
    "FORCED ACTION '    555-1234'",
    "LAST ACTION 'Not a keyword line'",
]

# the default title page with the sample's titles: Title, Author and
# Contact replace the default strings, the others are added
FOUNTAIN_TITLES = [
    [
        (["The Pot"], 0.0, 105.0, True, "title"),
        (["by", "", "Anna Smith"], 0.0, 120.46, True, "byline"),
        (["Anna Smith", "555-1234"], 15.0, 248.46, False, "contact"),
        (["Credit: Written by"], 0.0, 150.0, True, None),
        (["Source: Based on a true story"], 0.0, 155.0, True, None),
        (["Draft date: 1 May 2026"], 0.0, 220.0, False, None),
    ]
]


# the default options: titles go to the title page, and a line in the
# title block that isn't one goes into the script
def testFountain():
    lines, titlePages = run(
        "fountain", sample("fountain"), titlePages=defaultTitlePages()
    )

    assert dumpLines(lines) == (
        ["LAST ACTION 'Not a keyword line'"] + FOUNTAIN_SECTIONS + FOUNTAIN_SCRIPT
    )
    assert dumpTitles(titlePages) == FOUNTAIN_TITLES


def testFountainTitlesToBoth():
    lines, titlePages = run(
        "fountain",
        sample("fountain"),
        titlePages=defaultTitlePages(),
        titlesAsAction=True,
    )

    assert dumpLines(lines) == (
        FOUNTAIN_TITLE_LINES + FOUNTAIN_SECTIONS + FOUNTAIN_SCRIPT
    )
    assert dumpTitles(titlePages) == FOUNTAIN_TITLES


def testFountainTitlesAsActionOnly():
    lines, titlePages = run(
        "fountain",
        sample("fountain"),
        titlePages=defaultTitlePages(),
        titlePage=False,
        titlesAsAction=True,
    )

    assert dumpLines(lines) == (
        FOUNTAIN_TITLE_LINES + FOUNTAIN_SECTIONS + FOUNTAIN_SCRIPT
    )
    assert dumpTitles(titlePages) == dumpTitles(defaultTitlePages())


def testFountainTitlesDropped():
    lines, titlePages = run(
        "fountain",
        sample("fountain"),
        titlePages=defaultTitlePages(),
        titlePage=False,
    )

    assert dumpLines(lines) == FOUNTAIN_SECTIONS + FOUNTAIN_SCRIPT
    assert dumpTitles(titlePages) == dumpTitles(defaultTitlePages())


def testFountainNoMarkupNoSections():
    lines, titlePages = run(
        "fountain",
        sample("fountain"),
        titlePages=defaultTitlePages(),
        markup=False,
        sectionsAsNotes=False,
    )

    assert dumpLines(lines) == [
        "LAST ACTION 'Not a keyword line'",
        FOUNTAIN_SCRIPT[0],
        "LAST ACTION 'Steam rises from a **pot**.  It _bubbles_.'",
    ] + FOUNTAIN_SCRIPT[2:]
    assert dumpTitles(titlePages) == FOUNTAIN_TITLES


def testFountainCancel():
    assert (
        run(
            "fountain",
            sample("fountain"),
            titlePages=defaultTitlePages(),
            cancel=True,
        )
        is None
    )


def writeZip(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)


@pytest.mark.parametrize(
    "key, contents, message",
    [
        ("astx", "", "File is empty."),
        ("astx", "<AdobeStory><x></AdobeStory>", "Error parsing file: "),
        ("astx", "<AdobeStory/>", "File has no content."),
        ("fdx", "", "File is empty."),
        ("fdx", "<FinalDraft>", "Error parsing file: "),
        (
            "fdx",
            "<FinalDraft><Content/></FinalDraft>",
            "The file contains no importable lines",
        ),
        ("fountain", "", "File is empty."),
        ("pdf", "", "File is empty."),
        ("pdf", "not a PDF file", "Error reading PDF file: "),
        ("text", "", "File is empty."),
        ("text", "  \n\t\n", "File contains only empty lines."),
        ("fadein", "not a zip", "File is not a valid .fadein file."),
        ("fadein", {"other.xml": "<a/>"}, "File is not a valid .fadein file."),
        ("fadein", {"document.xml": ""}, "File is empty."),
        ("fadein", {"document.xml": "<document>"}, "Error parsing file: "),
        (
            "fadein",
            {"document.xml": "<document><paragraphs/></document>"},
            "The file contains no importable lines",
        ),
        ("celtx", "not a zip", "File is not a valid Celtx script file."),
        ("celtx", {"project.rdf": "x"}, "Unable to find script in this Celtx file."),
        ("celtx", {"script-a.html": ""}, "Script seems to be empty."),
        (
            "celtx",
            {"script-a.html": "<html><body></body></html>"},
            "The file contains no importable lines",
        ),
    ],
)
def testErrors(tmp_path, key, contents, message):
    path = tmp_path / ("script." + key)

    if isinstance(contents, dict):
        writeZip(path, contents)
    else:
        path.write_text(contents, encoding="UTF-8")

    with pytest.raises(Failed) as e:
        run(key, path, titlePages=defaultTitlePages())

    assert e.value.message.startswith(message)

    if message.endswith(": "):
        assert len(e.value.message) > len(message)


def testMissingFile(tmp_path):
    with pytest.raises(Failed) as e:
        run("text", tmp_path / "missing.txt")

    assert e.value.message.startswith("Error loading file '")


# the importers without the GUI: parse with the default options gives the
# same as importing with the dialogs' defaults
@pytest.mark.parametrize(
    "key, ext", [(f.key, f.extensions[0]) for f in formats.IMPORT_FORMATS]
)
def testParse(key, ext):
    importer = formats.find(formats.IMPORT_FORMATS, key).importer
    lines, titlePages = run(key, sample(ext), titlePages=defaultTitlePages())

    if importer.BINARY:
        data = readBytes(sample(ext))
    else:
        data = readText(sample(ext))

    result = importer.parse(data)

    assert dumpLines(result.lines) == dumpLines(lines)
    assert dumpTitles(result.titlePages) == dumpTitles(titlePages)


def readBytes(path):
    with open(path, "rb") as f:
        return f.read()


# as fileio.loadFile reads it
def readText(path):
    with open(path, encoding="UTF-8") as f:
        return f.read()


@pytest.mark.parametrize("key", [f.key for f in formats.IMPORT_FORMATS])
def testParseEmpty(key):
    importer = formats.find(formats.IMPORT_FORMATS, key).importer

    with pytest.raises(importers.ImportFailed) as e:
        importer.parse(b"" if importer.BINARY else "")

    assert e.value.message


def testTextGuessIndents():
    indents = importers.text.guessIndents(readText(sample("txt")))

    assert {ind.indent: ind.lt for ind in indents} == {
        0: SCENE_ACTION,
        10: screenplay.DIALOGUE,
        15: screenplay.PAREN,
        16: screenplay.PAREN,
        20: screenplay.CHARACTER,
        40: screenplay.TRANSITION,
        60: screenplay.ACTION,
    }
    assert [ind.lines for ind in indents if ind.indent == 40] == [["CUT TO:"]]


def testTextOptions():
    options = importers.text.Options(lineTypes={60: IGNORE, 0: screenplay.ACTION})
    result = importers.text.parse(readText(sample("txt")), options)

    assert dumpLines(result.lines) == dumpLines(
        run("text", sample("txt"), lineTypes={60: IGNORE, 0: screenplay.ACTION})[0]
    )
    assert result.titlePages is None


# an XML declaration used to make lxml refuse the str
def testAstxXmlDeclaration():
    data = readText(sample("astx"))
    result = importers.astx.parse('<?xml version="1.0" encoding="UTF-8"?>\n' + data)

    assert dumpLines(result.lines) == dumpLines(importers.astx.parse(data).lines)


# the imported titles go on a copy of the script's title pages: the
# script's are only replaced once the import has succeeded
def testFountainKeepsScriptTitlePages():
    pages = defaultTitlePages()

    run("fountain", sample("fountain"), titlePages=pages)
    assert dumpTitles(pages) == dumpTitles(defaultTitlePages())

    run("fountain", sample("fountain"), titlePages=pages, cancel=True)
    assert dumpTitles(pages) == dumpTitles(defaultTitlePages())


# Title, Author and Contact go to the strings of their kind, wherever they
# are on the page
def testFountainTitlesByKind():
    page = list(reversed(defaultTitlePages()[0]))
    note = titles.TitleString(["A note"], 15.0, 50.0, False, kind=titles.TEXT)
    page.insert(1, note)

    result = importers.fountain.parse(
        readText(sample("fountain")), importers.fountain.Options(titlePages=[page])
    )

    assert dumpTitles(result.titlePages)[0][:4] == [
        (["Anna Smith", "555-1234"], 15.0, 248.46, False, "contact"),
        (["A note"], 15.0, 50.0, False, "text"),
        (["by", "", "Anna Smith"], 0.0, 120.46, True, "byline"),
        (["The Pot"], 0.0, 105.0, True, "title"),
    ]


# strings saved before kinds existed get their kind guessed
def testFountainTitlesGuessedKinds():
    pages = defaultTitlePages()

    for ts in pages[0]:
        ts.kind = None

    result = importers.fountain.parse(
        readText(sample("fountain")), importers.fountain.Options(titlePages=pages)
    )

    assert dumpTitles(result.titlePages) == FOUNTAIN_TITLES


# a missing kind is added, placed for the paper size
def testFountainTitlesMissingKind():
    pages = defaultTitlePages()
    del pages[0][2]

    result = importers.fountain.parse(
        "Title: The Pot\nContact: Anna\n\nHello.\n",
        importers.fountain.Options(titlePages=pages, paperSize=(215.9, 279.4)),
    )

    contact = titles.makeString(titles.CONTACT, 215.9, 279.4)

    assert dumpTitles(result.titlePages) == [
        [
            (["The Pot"], 0.0, 105.0, True, "title"),
            (["by", "", "My Name Here"], 0.0, 120.46, True, "byline"),
            (["Anna"], contact.x, round(contact.y, 2), False, "contact"),
        ]
    ]


# without title pages given, the titles go on the default one; a script
# with none gets a page for them
def testFountainTitlePagesDefault():
    data = readText(sample("fountain"))

    result = importers.fountain.parse(data)
    assert dumpTitles(result.titlePages) == FOUNTAIN_TITLES

    result = importers.fountain.parse(data, importers.fountain.Options(titlePages=[]))
    assert dumpTitles(result.titlePages)[0][0] == (
        ["The Pot"],
        0.0,
        105.0,
        True,
        "title",
    )
