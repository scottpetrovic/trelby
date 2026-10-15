from unittest import mock

import tests.u as u
import trelby.myimport as myimport
import trelby.mypager as mypager
import trelby.pml as pml
import trelby.screenplay as scr
import trelby.textfmt as textfmt
import trelby.translations as translations
from trelby.line import Line

_ = translations.trelby_translations_load()

# tests for bold / italic / underlined text and centered elements

B = textfmt.BOLD
I = textfmt.ITALIC
U = textfmt.UNDERLINED


def loadLines(lines):
    sp = u.loadString("\n".join(["#Version 3", "#Start-Script "] + lines))
    sp.paginate()

    return sp


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
def select(sp, line, c1, c2):
    sp.setMark(line, c1)
    sp.line = line
    sp.column = c2


# return the text of the characters of 'sp's lines with the given style
# bits, joined by "|" between runs
def styled(sp, bits):
    ret = []

    for ln in sp.lines:
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
    sp = loadBold()

    assert sp.lines[1].fmt == "0000111100000000000000"
    assert styled(sp, B) == "door"

    s = sp.save().decode("UTF-8")
    assert "#Format 4-8:b\n..The door opens slowly.\n" in s
    assert s.count("#Format") == 1

    assert styled(u.loadString(s), B) == "door"
    sp._validate()


def testUnknownInOldVersions():
    # a format line is a config line older versions skip, and a centered
    # line one they turn into action
    sp = loadLines(["#Format 0-3:b", ".^THE END"])

    assert sp.lines[0].lt == scr.CENTERED
    assert sp.lines[0].fmt == "111" + "0" * 4


def testLineEquality():
    assert Line(text="ab") == Line(text="ab", fmt="00")
    assert Line(text="ab") != Line(text="ab", fmt="10")


# --- editing


def testToggleSelection():
    sp = loadBold()
    select(sp, 1, 9, 13)

    sp.toggleFormat(I)
    assert styled(sp, I) == "opens"
    assert styled(sp, B) == "door"

    # all of it already italic: turns it off
    sp.toggleFormat(I)
    assert styled(sp, I) == ""

    # partly bold: makes all of it bold
    select(sp, 1, 6, 13)
    sp.toggleFormat(B)
    assert styled(sp, B) == "door opens"

    sp._validate()


def testToggleUndo():
    sp = loadBold()
    select(sp, 1, 9, 13)
    sp.toggleFormat(U)
    assert styled(sp, U) == "opens"

    sp.cmd("undo")
    assert styled(sp, U) == ""
    assert styled(sp, B) == "door"

    sp.cmd("redo")
    assert styled(sp, U) == "opens"


def testTypingStyle():
    sp = loadBold()
    sp.line = 1
    sp.column = 22

    # typing goes on in the style of the text before the cursor, which is
    # plain here
    sp.cmdChars(" Then")
    assert styled(sp, B) == "door"

    # toggled with nothing selected, for the text typed next
    sp.toggleFormat(B)
    sp.cmdChars(" BANG")
    assert styled(sp, B) == "door| BANG"

    sp.toggleFormat(B)
    sp.cmdChars("!")
    assert styled(sp, B) == "door| BANG"

    # in the middle of a bold word
    sp.column = 6
    sp.cmdChars("x")
    assert styled(sp, B) == "doxor| BANG"

    sp._validate()


def testTypingStyleResetsOnMove():
    sp = loadBold()
    sp.line = 1
    sp.column = 22

    sp.toggleFormat(B)
    sp.cmd("moveLeft")
    sp.cmd("moveRight")
    sp.cmdChars("z")

    assert styled(sp, B) == "door"


def testWrap():
    # formatting moves along with the text when it wraps onto other lines
    sp = loadBold()
    sp.line = 1
    sp.column = 0
    sp.cmdChars("Without a sound, after a long and anxious wait, ")

    assert len(sp.lines) > 2
    assert styled(sp, B) == "door"
    sp._validate()

    # and when it's joined back
    for i in range(48):
        sp.cmd("deleteBackward")

    assert sp.lines[1].text == "The door opens slowly."
    assert styled(sp, B) == "door"
    sp._validate()


def testUnderlinedWrapSpace():
    # a space between underlined words stays underlined across a wrap
    words = "word " * 15
    sp = loadLines(["..x"])
    sp.line = 0
    sp.column = 1
    sp.toggleFormat(U)
    sp.cmdChars(words.strip())

    assert len(sp.lines) == 2
    assert styled(sp, U) == sp.lines[0].text[1:] + "|" + sp.lines[1].text
    sp._validate()


def testSplitAndJoin():
    sp = loadBold()
    sp.line = 1
    sp.column = 6
    sp.cmd("insertForcedLineBreak")

    assert sp.lines[1].text == "The do"
    assert sp.lines[2].text == "or opens slowly."
    assert styled(sp, B) == "do|or"
    sp._validate()

    sp.cmd("deleteBackward")
    assert styled(sp, B) == "door"
    sp._validate()


def testDelete():
    sp = loadBold()
    sp.line = 1
    sp.column = 4
    sp.cmd("deleteForward")

    assert styled(sp, B) == "oor"
    sp._validate()


def testCutPaste():
    sp = loadBold()
    select(sp, 1, 0, 8)
    cd = sp.getSelectedAsCD(True)

    assert cd.lines[0].text == "The door "
    assert sp.lines[1].text == "opens slowly."
    assert styled(sp, B) == ""
    sp._validate()

    sp.line = 1
    sp.column = 6
    sp.paste(cd.lines)

    assert sp.lines[1].text == "opens The door slowly."
    assert styled(sp, B) == "door"
    sp._validate()


def testFindReplace():
    sp = loadBold()
    sp.lines[1].replaceText(4, 4, "gate")
    assert styled(sp, B) == "gate"

    sp.lines[1].replaceText(4, 4, "portcullis")
    assert styled(sp, B) == "portcullis"
    assert sp.lines[1].text == "The portcullis opens slowly."


def testRenameCharacter():
    sp = loadLines(
        [
            ".\\INT. HALL - NIGHT",
            "#Format 0-4:b",
            "..Mary waits for Mary.",
            "._MARY",
            ".:Hello.",
        ]
    )

    sp.renameCharacters({"MARY": "JOSEPHINE"})

    assert sp.lines[1].text == "Josephine waits for Josephine."
    assert styled(sp, B) == "Josephine"
    sp._validate()


# --- output


def testPML():
    sp = loadBold()
    pg = sp.generatePMLPage(mypager.Pager(sp.cfg), 1, True, True)
    ops = [op for op in pg.ops if isinstance(op, pml.TextOp) and op.line == 1]

    assert ops[0].fmt == sp.lines[1].fmt

    # and the PDF draws it
    assert sp.generatePDF().startswith(b"%PDF")


def testFDX():
    sp = loadBold()
    s = sp.generateFDX().decode("UTF-8")

    assert '<Text Style="Bold">door</Text>' in s
    assert "<Text>The </Text>" in s


def testFDXImport(tmp_path):
    path = tmp_path / "bold.fdx"
    path.write_bytes(loadBold().generateFDX())

    lines = myimport.importFDX(str(path), mock.Mock())

    assert lines[1].text == "The door opens slowly."
    assert lines[1].fmt == "0000111100000000000000"


def testFountain():
    sp = loadBold()
    s = sp.generateFountain()

    assert "The **door** opens slowly." in s


def importFountain(tmp_path, text, convert=True):
    path = tmp_path / "script.fountain"
    path.write_text(text, encoding="UTF-8")

    dlg = mock.Mock()
    dlg.ShowModal.return_value = myimport.wx.ID_OK

    def checkBoxDlg(parent, title, items, descr, rememberLast):
        items[2].selected = convert

        return dlg

    with mock.patch.object(myimport.misc, "CheckBoxDlg", checkBoxDlg):
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
    s = loadBold().generateRTF()

    assert r"The {\b door} opens slowly." in s


def testHtml():
    s = loadBold().generateHtml()

    assert 'The <span style="font-weight:bold">door</span> opens slowly.' in s


# --- centered


def loadCentered():
    return loadLines(
        [
            ".\\INT. HALL - NIGHT",
            "..The door opens.",
            "|^THE END",
            ".^for now",
        ]
    )


def testCenteredOffset():
    sp = loadCentered()
    width = sp.cfg.getType(scr.CENTERED).width

    assert sp.lines[2].lt == scr.CENTERED
    assert sp.getCenterOffset(1) == 0
    assert sp.getCenterOffset(2) == (width - 7) / 2.0
    assert sp.getCenterOffset(3) == (width - 7) / 2.0

    pg = sp.generatePMLPage(mypager.Pager(sp.cfg), 1, True, True)
    x = {op.line: op.x for op in pg.ops if isinstance(op, pml.TextOp)}

    assert x[2] > x[1]
    sp._validate()


def testCenteredSaveLoad():
    sp = loadCentered()
    s = sp.save().decode("UTF-8")

    assert "|^THE END\n.^for now\n" in s
    assert u.loadString(s).lines[2].lt == scr.CENTERED


def testCenteredText():
    sp = loadCentered()
    width = sp.cfg.getType(scr.CENTERED).width
    lines = sp.generateText(False).split("\n")

    assert " " * int((width - 7) / 2.0) + "THE END" in lines


def testCenteredFountain(tmp_path):
    s = loadCentered().generateFountain()

    assert "\n>THE END<\n>for now<" in s

    lines = importFountain(tmp_path, s)
    centered = [ln for ln in lines if ln.lt == scr.CENTERED]

    assert [ln.text for ln in centered] == ["THE END", "for now"]
    assert centered[0].lb == scr.LB_FORCED
    assert centered[1].lb == scr.LB_LAST


def testCenteredFDX(tmp_path):
    s = loadCentered().generateFDX()

    assert b'<Paragraph Type="Action" Alignment="Center">' in s

    path = tmp_path / "centered.fdx"
    path.write_bytes(s)
    lines = myimport.importFDX(str(path), mock.Mock())

    assert [ln.text for ln in lines if ln.lt == scr.CENTERED] == [
        "THE END",
        "for now",
    ]


def testChangeToCentered():
    sp = loadCentered()
    sp.line = 1
    sp.cmd("toCentered")

    assert sp.lines[1].lt == scr.CENTERED
    sp._validate()
