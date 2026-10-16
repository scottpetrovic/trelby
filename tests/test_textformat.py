from unittest import mock

import tests.u as u
import trelby.myimport as myimport
import trelby.mypager as mypager
import trelby.pml as pml
import trelby.screenplay as scr
import trelby.screenplay.export as export
import trelby.screenplay.render as render
import trelby.textfmt as textfmt
import trelby.translations as translations
from trelby.line import Line

_ = translations.trelby_translations_load()

# tests for bold / italic / underlined text and centered elements

B = textfmt.BOLD
I = textfmt.ITALIC
U = textfmt.UNDERLINED


def loadLines(lines):
    ed = u.loadStringEditor("\n".join(["#Version 3", "#Start-Script "] + lines))
    ed.sp.paginate()

    return ed


# a scene heading and an action with "door" in bold
def loadBold():
    return loadLines(
        [
            ".\\INT. HALL - NIGHT",
            "#Format 4-8:b",
            "..The door opens slowly.",
        ]
    )


# select columns c1 - c2 (inclusive) of line 'line'
def select(ed, line, c1, c2):
    ed.setMark(line, c1)
    ed.line = line
    ed.column = c2


# return the text of the characters of 'ed's lines with the given style
# bits, joined by "|" between runs
def styled(ed, bits):
    ret = []

    for ln in ed.sp.lines:
        for a, b, style in textfmt.runs(ln.fmt, len(ln.text)):
            if (style & bits) == bits:
                ret.append(ln.text[a:b])

    return "|".join(ret)


# --- textfmt


def testRuns():
    assert textfmt.runs(None, 0) == []
    assert textfmt.runs(None, 3) == [(0, 3, 0)]
    assert textfmt.runs("0110", 4) == [(0, 1, 0), (1, 3, 1), (3, 4, 0)]

    # too short / too long format strings are fitted to the text
    assert textfmt.runs("01", 3) == [(0, 1, 0), (1, 2, 1), (2, 3, 0)]
    assert textfmt.runs("0111", 2) == [(0, 1, 0), (1, 2, 1)]


def testEncodeDecode():
    fmt = "0011005577"

    assert textfmt.encode(fmt) == "2-4:b,6-8:bu,8-10:biu"
    assert textfmt.decode(textfmt.encode(fmt), len(fmt)) == fmt
    assert textfmt.encode(None) == ""

    # invalid items are ignored, and ones past the end clipped
    assert textfmt.decode("0-2:b,junk,3-9:i", 5) == "11022"
    assert textfmt.decode("junk", 5) is None


def testJoin():
    # the space between two underlined words is underlined, but not one
    # between an underlined and a plain one
    assert textfmt.join([("ab", "44"), ("cd", "44")], [" "]) == "44444"
    assert textfmt.join([("ab", "44"), ("cd", None)], [" "]) == "44000"
    assert textfmt.join([("ab", None), ("cd", None)], [" "]) is None
    assert textfmt.join([("ab", "11"), ("cd", None)], [""]) == "1100"


def testMarkup():
    for text, fmt, markup in (
        ("plain", None, "plain"),
        ("a bold word", "00111100000", "a **bold** word"),
        ("an italic one", "0002222220000", "an *italic* one"),
        ("both", "3333", "***both***"),
        ("under", "44444", "_under_"),
        ("all", "777", "_***all***_"),
    ):
        assert textfmt.toMarkup(text, fmt) == markup
        assert textfmt.fromMarkup(markup) == (text, textfmt.compact(fmt))

    # spaces at the edges of a run go outside the markers
    assert textfmt.toMarkup("x bold y", "00111110") == "x **bold** y"


def testMarkupLiterals():
    # unmatched markers and ones followed by a space are text
    assert textfmt.fromMarkup("5 * 3") == ("5 * 3", None)
    assert textfmt.fromMarkup("a * b * c") == ("a * b * c", None)
    assert textfmt.fromMarkup("snake_case") == ("snake_case", None)

    # escapes
    assert textfmt.fromMarkup(r"\*not\*") == ("*not*", None)

    # characters that would be read as markup are escaped
    assert textfmt.toMarkup("*not*", None) == r"\*not\*"
    assert textfmt.toMarkup("a_b_c", None) == r"a\_b\_c"
    assert textfmt.fromMarkup(textfmt.toMarkup("a_b_c", None)) == ("a_b_c", None)
    assert textfmt.toMarkup("5 * 3", None) == "5 * 3"


# --- storage


def testLoadSave():
    ed = loadBold()

    assert ed.sp.lines[1].fmt == "0000111100000000000000"
    assert styled(ed, B) == "door"

    s = ed.save().decode("UTF-8")
    assert "#Format 4-8:b\n..The door opens slowly.\n" in s
    assert s.count("#Format") == 1

    assert styled(u.loadStringEditor(s), B) == "door"
    ed._validate()


def testUnknownInOldVersions():
    # a format line is a config line older versions skip
    ed = loadLines(["#Format 0-3:b", "..THE END"])

    assert ed.sp.lines[0].fmt == "111" + "0" * 4


def testLineEquality():
    assert Line(text="ab") == Line(text="ab", fmt="00")
    assert Line(text="ab") != Line(text="ab", fmt="10")


# --- editing


def testToggleSelection():
    ed = loadBold()
    select(ed, 1, 9, 13)

    ed.toggleFormat(I)
    assert styled(ed, I) == "opens"
    assert styled(ed, B) == "door"

    # all of it already italic: turns it off
    ed.toggleFormat(I)
    assert styled(ed, I) == ""

    # partly bold: makes all of it bold
    select(ed, 1, 6, 13)
    ed.toggleFormat(B)
    assert styled(ed, B) == "door opens"

    ed._validate()


def testToggleUndo():
    ed = loadBold()
    select(ed, 1, 9, 13)
    ed.toggleFormat(U)
    assert styled(ed, U) == "opens"

    ed.cmd("undo")
    assert styled(ed, U) == ""
    assert styled(ed, B) == "door"

    ed.cmd("redo")
    assert styled(ed, U) == "opens"


def testTypingStyle():
    ed = loadBold()
    ed.line = 1
    ed.column = 22

    # typing goes on in the style of the text before the cursor, which is
    # plain here
    ed.cmdChars(" Then")
    assert styled(ed, B) == "door"

    # toggled with nothing selected, for the text typed next
    ed.toggleFormat(B)
    ed.cmdChars(" BANG")
    assert styled(ed, B) == "door| BANG"

    ed.toggleFormat(B)
    ed.cmdChars("!")
    assert styled(ed, B) == "door| BANG"

    # in the middle of a bold word
    ed.column = 6
    ed.cmdChars("x")
    assert styled(ed, B) == "doxor| BANG"

    ed._validate()


def testTypingStyleResetsOnMove():
    ed = loadBold()
    ed.line = 1
    ed.column = 22

    ed.toggleFormat(B)
    ed.cmd("moveLeft")
    ed.cmd("moveRight")
    ed.cmdChars("z")

    assert styled(ed, B) == "door"


def testWrap():
    # formatting moves along with the text when it wraps onto other lines
    ed = loadBold()
    ed.line = 1
    ed.column = 0
    ed.cmdChars("Without a sound, after a long and anxious wait, ")

    assert len(ed.sp.lines) > 2
    assert styled(ed, B) == "door"
    ed._validate()

    # and when it's joined back
    for i in range(48):
        ed.cmd("deleteBackward")

    assert ed.sp.lines[1].text == "The door opens slowly."
    assert styled(ed, B) == "door"
    ed._validate()


def testUnderlinedWrapSpace():
    # a space between underlined words stays underlined across a wrap
    words = "word " * 15
    ed = loadLines(["..x"])
    ed.line = 0
    ed.column = 1
    ed.toggleFormat(U)
    ed.cmdChars(words.strip())

    assert len(ed.sp.lines) == 2
    assert styled(ed, U) == ed.sp.lines[0].text[1:] + "|" + ed.sp.lines[1].text
    ed._validate()


def testSplitAndJoin():
    ed = loadBold()
    ed.line = 1
    ed.column = 6
    ed.cmd("insertForcedLineBreak")

    assert ed.sp.lines[1].text == "The do"
    assert ed.sp.lines[2].text == "or opens slowly."
    assert styled(ed, B) == "do|or"
    ed._validate()

    ed.cmd("deleteBackward")
    assert styled(ed, B) == "door"
    ed._validate()


def testDelete():
    ed = loadBold()
    ed.line = 1
    ed.column = 4
    ed.cmd("deleteForward")

    assert styled(ed, B) == "oor"
    ed._validate()


def testCutPaste():
    ed = loadBold()
    select(ed, 1, 0, 8)
    cd = ed.getSelectedAsCD(True)

    assert cd.lines[0].text == "The door "
    assert ed.sp.lines[1].text == "opens slowly."
    assert styled(ed, B) == ""
    ed._validate()

    ed.line = 1
    ed.column = 6
    ed.paste(cd.lines)

    assert ed.sp.lines[1].text == "opens The door slowly."
    assert styled(ed, B) == "door"
    ed._validate()


def testFindReplace():
    ed = loadBold()
    ed.sp.lines[1].replaceText(4, 4, "gate")
    assert styled(ed, B) == "gate"

    ed.sp.lines[1].replaceText(4, 4, "portcullis")
    assert styled(ed, B) == "portcullis"
    assert ed.sp.lines[1].text == "The portcullis opens slowly."


def testRenameCharacter():
    ed = loadLines(
        [
            ".\\INT. HALL - NIGHT",
            "#Format 0-4:b",
            "..Mary waits for Mary.",
            "._MARY",
            ".:Hello.",
        ]
    )

    ed.renameCharacters({"MARY": "JOSEPHINE"})

    assert ed.sp.lines[1].text == "Josephine waits for Josephine."
    assert styled(ed, B) == "Josephine"
    ed._validate()


# --- output


def testPML():
    ed = loadBold()
    pg = render.generatePMLPage(ed.sp, mypager.Pager(ed.sp.cfg), 1, True, True)
    ops = [op for op in pg.ops if isinstance(op, pml.TextOp) and op.line == 1]

    assert ops[0].fmt == ed.sp.lines[1].fmt

    # and the PDF draws it
    assert export.generatePDF(ed.sp).startswith(b"%PDF")


def testFDX():
    ed = loadBold()
    s = export.generateFDX(ed.sp).decode("UTF-8")

    assert '<Text Style="Bold">door</Text>' in s
    assert "<Text>The </Text>" in s


def testFDXImport(tmp_path):
    path = tmp_path / "bold.fdx"
    path.write_bytes(export.generateFDX(loadBold().sp))

    lines = myimport.importFDX(str(path), mock.Mock())

    assert lines[1].text == "The door opens slowly."
    assert lines[1].fmt == "0000111100000000000000"


def testFountain():
    ed = loadBold()
    s = export.generateFountain(ed.sp)

    assert "The **door** opens slowly." in s


def importFountain(tmp_path, text, convert=True):
    path = tmp_path / "script.fountain"
    path.write_text(text, encoding="UTF-8")

    dlg = mock.Mock()
    dlg.ShowModal.return_value = myimport.wx.ID_OK

    def checkBoxDlg(parent, title, items, descr, rememberLast):
        items[2].selected = convert

        return dlg

    with mock.patch.object(myimport.checkboxdlg, "CheckBoxDlg", checkBoxDlg):
        return myimport.importFountain(str(path), mock.Mock(), [])[0]


def testFountainImport(tmp_path):
    lines = importFountain(tmp_path, "INT. HALL - NIGHT\n\nThe **door** _opens_.\n")

    assert lines[1].text == "The door opens."
    assert lines[1].fmt == "000011110444440"


def testFountainImportNoConvert(tmp_path):
    lines = importFountain(tmp_path, "INT. HALL - NIGHT\n\nThe **door**.\n", False)

    assert lines[1].text == "The **door**."
    assert lines[1].fmt is None


def testRTF():
    s = export.generateRTF(loadBold().sp)

    assert r"The {\b door} opens slowly." in s


def testHtml():
    s = export.generateHtml(loadBold().sp)

    assert 'The <span style="font-weight:bold">door</span> opens slowly.' in s


# --- centered


def loadCentered():
    return loadLines(
        [
            ".\\INT. HALL - NIGHT",
            "..The door opens.",
            "#Centered ",
            "|.THE END",
            "..for now",
            "..Credits roll.",
        ]
    )


# return the texts of the lines of centered actions
def centeredTexts(ed):
    return [ln.text for i, ln in enumerate(ed.sp.lines) if ed.sp.isCentered(i)]


def testCenteredOffset():
    ed = loadCentered()
    width = ed.sp.cfg.getType(scr.ACTION).width

    assert ed.sp.lines[2].lt == scr.ACTION
    assert centeredTexts(ed) == ["THE END", "for now"]
    assert ed.sp.getCenterOffset(1) == 0
    assert ed.sp.getCenterOffset(2) == (width - 7) / 2.0
    assert ed.sp.getCenterOffset(3) == (width - 7) / 2.0
    assert ed.sp.getCenterOffset(4) == 0

    pg = render.generatePMLPage(ed.sp, mypager.Pager(ed.sp.cfg), 1, True, True)
    x = {op.line: op.x for op in pg.ops if isinstance(op, pml.TextOp)}

    assert x[2] > x[1]
    assert x[4] == x[1]
    ed._validate()


def testCenteredSaveLoad():
    ed = loadCentered()
    s = ed.save().decode("UTF-8")

    assert "#Centered \n|.THE END\n..for now\n..Credits" in s
    assert s.count("#Centered") == 1
    assert centeredTexts(u.loadStringEditor(s)) == ["THE END", "for now"]


def testOldCenteredType():
    # an early development version had a separate centered element type
    ed = loadLines(["..x", "|^THE END", ".^for now"])

    assert [ln.lt for ln in ed.sp.lines] == [scr.ACTION] * 3
    assert centeredTexts(ed) == ["THE END", "for now"]
    assert ed.sp.hasCenteredFlag(1)
    assert not ed.sp.lines[2].centered


def testToggleCentered():
    ed = loadCentered()

    # on an action
    ed.line = 1
    assert ed.getCenteredState() is False
    assert ed.toggleCentered()
    assert centeredTexts(ed) == ["The door opens.", "THE END", "for now"]

    # not on a scene heading
    ed.line = 0
    assert ed.getCenteredState() is None
    assert not ed.toggleCentered()

    # a selection over centered and uncentered actions centers them all,
    # and then stops centering them all
    select(ed, 2, 0, 0)
    ed.line = 4
    assert ed.getCenteredState() is False
    ed.toggleCentered()
    assert len(centeredTexts(ed)) == 4

    assert ed.getCenteredState() is True
    ed.toggleCentered()
    assert centeredTexts(ed) == ["The door opens."]

    ed.cmd("undo")
    assert len(centeredTexts(ed)) == 4

    ed.clearMark()
    ed._validate()


def testCenteredStaysWithElement():
    ed = loadCentered()

    # turning it into something else and back keeps it centered
    ed.line = 2
    ed.convertTypeTo(scr.TRANSITION, True)
    assert centeredTexts(ed) == []

    ed.convertTypeTo(scr.ACTION, True)
    assert centeredTexts(ed) == ["THE END", "for now"]

    # a new element after it isn't centered
    ed.line = 3
    ed.column = len(ed.sp.lines[3].text)
    ed.cmd("splitElement")
    ed.cmdChars("Fade")
    assert centeredTexts(ed) == ["THE END", "for now"]

    ed._validate()


def testCenteredCopyPaste():
    ed = loadCentered()
    select(ed, 2, 0, 6)
    ed.line = 3
    ed.column = 6
    cd = ed.getSelectedAsCD(False)
    ed.clearMark()

    assert cd.lines[0].centered

    ed.line = len(ed.sp.lines) - 1
    ed.column = len(ed.sp.lines[ed.line].text)
    ed.cmd("splitElement")
    ed.paste(cd.lines)

    assert centeredTexts(ed) == ["THE END", "for now"] * 2
    ed._validate()


def testCenteredText():
    ed = loadCentered()
    width = ed.sp.cfg.getType(scr.ACTION).width
    lines = export.generateText(ed.sp, False).split("\n")

    assert " " * int((width - 7) / 2.0) + "THE END" in lines
    assert "Credits roll." in lines


def testCenteredRTF():
    s = export.generateRTF(loadCentered().sp)

    assert "\\qc THE END\\line for now}" in s
    assert "\\qc The door" not in s


def testCenteredFountain(tmp_path):
    s = export.generateFountain(loadCentered().sp)

    assert "\n>THE END<\n>for now<\n\nCredits roll." in s

    # without the empty line between them
    lines = importFountain(tmp_path, s.replace("<\n\nCredits", "<\nCredits"))
    texts = [ln.text for ln in lines]
    i = texts.index("THE END")

    assert lines[i].lt == scr.ACTION
    assert lines[i].centered and (lines[i].lb == scr.LB_FORCED)
    assert not lines[i + 1].centered and (lines[i + 1].lb == scr.LB_LAST)

    # the uncentered action right after it is an element of its own
    assert lines[i + 2].text == "Credits roll."
    assert not lines[i + 2].centered


def testCenteredFDX(tmp_path):
    s = export.generateFDX(loadCentered().sp)

    assert s.count(b'<Paragraph Type="Action" Alignment="Center">') == 1

    path = tmp_path / "centered.fdx"
    path.write_bytes(s)
    lines = myimport.importFDX(str(path), mock.Mock())

    texts = [ln.text for ln in lines]
    i = texts.index("THE END")

    assert lines[i].centered
    assert not any(ln.centered for j, ln in enumerate(lines) if j != i)


def testFormatState():
    # bold and underline together on part of a speech
    ed = loadLines(
        [
            ".\\INT. HALL - NIGHT",
            "._MARY",
            "#Format 2-6:bu,7-12:b",
            ".:I said never again.",
        ]
    )

    ed.line = 2
    ed.column = 4
    assert ed.getFormatState() == B | U

    ed.column = 0
    assert ed.getFormatState() == 0

    # what all of the selection has
    select(ed, 2, 2, 5)
    assert ed.getFormatState() == B | U

    select(ed, 2, 2, 11)
    assert ed.getFormatState() == 0

    select(ed, 2, 7, 11)
    assert ed.getFormatState() == B

    # toggling with nothing selected shows up at once
    ed.clearMark()
    ed.line = 2
    ed.column = 0
    ed.toggleFormat(I)
    assert ed.getFormatState() == I
