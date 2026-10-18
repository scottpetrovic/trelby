import os.path
import re

import wx

import tests.u as u
import trelby.dialogs.charmapdlg as charmapdlg
import trelby.config as config
import trelby.pdf.fontinfo as fontinfo
import trelby.keys as keys
import trelby.pdf.writer as pdf
import trelby.pdf.pml as pml
import trelby.screenplay as screenplay
import trelby.screenplay.export as export
import trelby.screenplay.render as render
import trelby.spellcheck as spellcheck
import trelby.textutil as textutil
import trelby.screenplay.titles as titles
import trelby.translations as translations
import trelby.util as util
from trelby.screenplay.line import Line
from trelby.ui.textedit import TextEdit

_ = translations.trelby_translations_load()

# characters above U+00FF: Polish, Czech, the euro sign, Cyrillic and
# Greek. see also test_keyinput.py for typing them.

TEXT = "łŁčČžŽ€ПётрΩμέγα"


def testValidInputChars():
    for ch in TEXT + "äÅ ~\xa0" + "—«»™№ĳǆ":
        assert textutil.isValidInputChar(ord(ch)), ch

    # control characters, DEL, the C1 range, soft hyphen, zero-width and
    # bidi format characters, line/paragraph separators, surrogates,
    # private use and unassigned code points
    for kc in (
        [0, 9, 10, 13, 31, 0x7F, 0x80, 0x85, 0x9F, 0xAD]
        + [0x200B, 0x200E, 0x202E, 0x2028, 0x2029, 0xFEFF]
        + [0xD800, 0xDFFF, 0xE000, 0xFFFF, 0x110000]
    ):
        assert not textutil.isValidInputChar(kc), hex(kc)


def testLatin1RangeUnchanged():
    # the old check allowed 32-255 minus 0x7F-0x9F and 0xAD
    for kc in range(256):
        old = (32 <= kc <= 255) and not (0x7F <= kc < 0xA0) and (kc != 0xAD)
        assert textutil.isValidInputChar(kc) == old, kc


def testRemoveInvalidChars():
    assert textutil.removeInvalidChars("a\x85ł\xadb\n€\u200b\u2028") == "ałb\n€"
    assert textutil.removeInvalidChars("a\nb\tc", keep="\t") == "ab\tc"


def testCleanInputComposes():
    # "c" + combining caron -> "č", so it takes up one column
    assert textutil.cleanInput("c\u030capek") == "čapek"


def testUpperLower():
    assert textutil.upper("łódź čapek пётр ωμέγα ǆ") == "ŁÓDŹ ČAPEK ПЁТР ΩΜΈΓΑ Ǆ"
    assert textutil.lower("ŁÓDŹ ČAPEK ПЁТР ΩΜΈΓΑ") == "łódź čapek пётр ωμέγα"


def testUpperLowerKeepLength():
    # these have case mappings longer than one character; the script's
    # layout counts characters, so they're left as they are
    assert textutil.upper("straße") == "STRAßE"
    assert textutil.upper("ŉ ﬁx") == "ŉ ﬁX"
    assert textutil.lower("İSTANBUL") == "İstanbul"
    assert textutil.capitalize("ßa") == "ßa"


def testKeysAboveLatin1AreSpecialKeys():
    # key codes above 255 are wx.WXK_ constants, even when the same number
    # is a letter as a code point (WXK_LEFT = 314 = "ĺ")
    assert keys.Key(ord("a")).isValidInputChar()
    assert keys.Key(ord("ä")).isValidInputChar()
    assert not keys.Key(wx.WXK_LEFT).isValidInputChar()
    assert not keys.Key(wx.WXK_F1).isValidInputChar()
    assert keys.Key(wx.WXK_LEFT, ctrl=True).toStr() == "CTRL+Left"
    assert keys.Key(wx.WXK_INSERT).toStr() == "Insert"
    assert keys.Key(ord("ä"), alt=True).toStr() == "ALT+Ä"

    # "ÿ" uppercases to "Ÿ" (U+0178), which would clash with a WXK constant
    assert keys.Key(ord("ÿ"), alt=True).kc == ord("ÿ")


def testKeyBindingsSurviveLoad():
    u.init()
    cfg = config.ConfigGlobal()
    saved = {cmd.name: cmd.keys for cmd in cfg.commands}

    cfg2 = config.ConfigGlobal()
    cfg2.load(cfg.save())

    for cmd in cfg2.commands:
        if saved[cmd.name] != [0]:
            assert cmd.keys == saved[cmd.name], cmd.name

    moveLeft = [cmd for cmd in cfg2.commands if cmd.name == "MoveLeft"][0]
    assert keys.Key(wx.WXK_LEFT).toInt() in moveLeft.keys


def testSaveLoadRoundTrip():
    ed = u.loadEditor("unicode.trelby")
    texts = [ln.text for ln in ed.sp.lines]

    assert texts[0] == "Int. Łódź — mieszkanie Čapka"
    assert texts[2] == "Пётр"
    assert "Ωμέγα" in texts[3]
    assert "€" in texts[1]

    ed2 = u.loadStringEditor(ed.save().decode("UTF-8"))
    assert [ln.text for ln in ed2.sp.lines] == texts
    assert [ln.lt for ln in ed2.sp.lines] == [ln.lt for ln in ed.sp.lines]

    ed2.line = 0
    ed2.column = len(ed2.sp.lines[0].text)
    ed2.cmd("addChar", char="ł")
    ed3 = u.loadStringEditor(ed2.save().decode("UTF-8"))
    assert ed3.sp.lines[0].text.endswith("Čapkał")


def testUppercaseHeadingsAndNames():
    ed = u.loadEditor("unicode.trelby")
    ed.sp.paginate()

    text = export.generateText(ed.sp, False)
    assert "INT. ŁÓDŹ — MIESZKANIE ČAPKA" in text
    assert "ПЁТР" in text
    assert "EWA ŻAK" in text

    # dialogue isn't uppercased, and "ß" stays as it is
    assert "Ωμέγα" in text
    assert "Straße" in text

    assert ed.sp.getExportText(0) == "INT. ŁÓDŹ — MIESZKANIE ČAPKA"
    assert "INT. ŁÓDŹ — MIESZKANIE ČAPKA" in ed.sp.getSceneNames()
    assert "пётр" in ed.sp.getCharacterNames()


def testTypeIntoSceneHeading():
    ed = u.newEditor()
    ed.sp.lines[0].lt = screenplay.SCENE

    # the first letter of a sentence is capitalized as you type
    for ch in "ext. łąka żółta":
        ed.cmd("addChar", char=ch)

    assert ed.sp.lines[0].text == "Ext. Łąka żółta"
    assert ed.sp.getExportText(0) == "EXT. ŁĄKA ŻÓŁTA"


def testAddCharRejectsInvalid():
    ed = u.newEditor()

    for ch in "a\x85\xad\u200b\u2028b":
        ed.cmd("addChar", char=ch)

    assert ed.sp.lines[0].text == "Ab"


def testPasteTextEdit():
    te = TextEdit([""])
    te.insert("łódź\x85\xad €\r\nc\u030capek Пётр")

    assert te.lines == ["łódź €", "čapek Пётр"]


def testSpellCheckerPrefix():
    assert textutil.getWordPrefix("ab") == "ab"
    assert textutil.getWordPrefix("AB") == "ab"
    assert textutil.getWordPrefix("äb") == "zb"
    assert textutil.getWordPrefix("łó") == "zz"
    assert textutil.getWordPrefix("Пё") == "zz"

    d = spellcheck.Dict()
    d.add("Łódź")
    d.add("Пётр")
    assert d.isKnown("łódź")
    assert d.isKnown("пётр")


def testSpellCheckerFindsWords():
    ed = u.loadEditor("unicode.trelby")
    sc = spellcheck.SpellChecker(ed.sp, spellcheck.Dict())

    # character names are known words
    assert sc.isKnown("Пётр")

    words = []
    while sc.findNext():
        words.append(sc.word)
        sc.col += len(sc.word)

    assert "Łódź" in words
    assert "Ωμέγα" in words
    assert "gęślą" in words


def testCharMapBlocks():
    latin1 = charmapdlg.blockChars([(0x20, 0xFF)])
    assert len(latin1) == 190
    assert "\xad" not in latin1

    punct = charmapdlg.blockChars([(0x2010, 0x205E), (0x20A0, 0x20C0)])
    assert "€" in punct
    assert "—" in punct
    assert "\u2028" not in punct
    assert "\u202e" not in punct

    for name, ranges in charmapdlg.getBlocks():
        assert charmapdlg.blockChars(ranges)


def testPDFUnsupportedChars():
    ed = u.loadEditor("unicode.trelby")
    ed.sp.paginate()
    doc = render.generatePML(ed.sp)

    chars = pdf.unsupportedChars(doc)
    # character names and scene headings are uppercased
    for ch in "ПЁТРαγ":
        assert ch in chars, ch

    # Courier Prime has WinAnsi, Latin Extended-A and a few Greek letters
    for ch in "€óäß«»—žłŁČΩμ":
        assert ch not in chars, ch

    # renders without errors anyway
    assert pdf.generate(doc)[:8] == b"%PDF-1.5"


def testPDFCustomFont():
    ed = u.loadEditor("unicode.trelby")
    ed.sp.paginate()

    for pfi in ed.sp.cfg.getPDFFontIds():
        pf = ed.sp.cfg.getPDFFont(pfi)
        pf.pdfName = "Jost"
        pf.filename = u.fixtureFilePath("custom-font/Jost-400-Book.ttf")

    doc = render.generatePML(ed.sp)
    chars = pdf.unsupportedChars(doc)

    # checked against the font's own characters: Jost has Cyrillic but no
    # Greek
    for ch in "ПЁТРłŁČ":
        assert ch not in chars, ch

    for ch in "αγ":
        assert ch in chars, ch

    assert pdf.generate(doc)[:8] == b"%PDF-1.5"


def testPDFFormattedRuns():
    doc = pml.Document(210, 297)
    pg = pml.Page(doc)
    doc.add(pg)

    # "П" is bold, and only the bold font (Jost) has it
    pg.add(pml.TextOp("aП", 10, 10, 12, fmt="\x00\x01"))
    doc.addFont(
        pml.COURIER | pml.BOLD,
        pml.PDFFontInfo("Jost", u.fixtureFilePath("custom-font/Jost-400-Book.ttf")),
    )
    assert pdf.unsupportedChars(doc) == ""

    pg.add(pml.TextOp("ПЁ", 10, 20, 12))
    assert pdf.unsupportedChars(doc) == "ЁП"


def testPDFUsesBundledFont():
    ed = u.loadEditor("unicode.trelby")
    ed.sp.paginate()
    data = export.generatePDF(ed.sp)

    # Courier text is in Courier Prime, embedded, not the standard Courier
    assert b"CourierPrime-Regular" in data
    assert not re.search(rb"/BaseFont\s*/Courier\b", data)

    # a script's own fonts replace it
    for pfi in ed.sp.cfg.getPDFFontIds():
        pf = ed.sp.cfg.getPDFFont(pfi)
        pf.pdfName = "Jost"
        pf.filename = u.fixtureFilePath("custom-font/Jost-400-Book.ttf")

    assert b"CourierPrime" not in export.generatePDF(ed.sp)


def testBundledFontsExist():
    for name, fileName in fontinfo.BUNDLED_FONTS.values():
        assert os.path.isfile(fontinfo.bundledFontPath(fileName)), fileName


def testTextWidth():
    # Courier is fixed width; Helvetica/Times have widths for Latin-1 only
    # in the table, and ask reportlab for the rest
    assert fontinfo.getMetrics(pml.COURIER).getTextWidth("łП", 10) == 12.0

    for style in (pml.HELVETICA, pml.TIMES_ROMAN | pml.BOLD):
        m = fontinfo.getMetrics(style)
        assert m.getTextWidth("ł€Пω", 10) > 0
        assert m.getTextWidth("a", 10) == m.getTextWidth("a", 10)

    assert util.getTextWidth("Łódź", pml.HELVETICA, 12) > 0


def testTitlePageInHelvetica():
    ed = u.loadEditor("unicode.trelby")
    ed.sp.titles.pages = [
        [titles.TitleString(["Łódź — Пётр"], y=100.0, font=pml.HELVETICA)]
    ]
    ed.sp.paginate()

    assert export.generatePDF(ed.sp)[:8] == b"%PDF-1.5"


def testEscapeRTF():
    assert textutil.escapeRTF("a{b}\\") == r"a\{b\}\\"
    assert textutil.escapeRTF("äł€") == r"\u228?\u322?\u8364?"

    # characters above U+FFFF are UTF-16 surrogate pairs, signed
    assert textutil.escapeRTF("\U0001f600") == r"\u-10179?\u-8704?"


def testExportRTF():
    ed = u.loadEditor("unicode.trelby")
    ed.sp.paginate()

    rtf = export.generateRTF(ed.sp)
    assert rtf.isascii()
    assert r"\u321?" in rtf  # Ł
