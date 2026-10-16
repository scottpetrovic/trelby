import wx

import tests.u as u
import trelby.charmapdlg as charmapdlg
import trelby.config as config
import trelby.fontinfo as fontinfo
import trelby.pdf as pdf
import trelby.pml as pml
import trelby.screenplay as screenplay
import trelby.screenplay.export as export
import trelby.screenplay.render as render
import trelby.spellcheck as spellcheck
import trelby.titles as titles
import trelby.translations as translations
import trelby.util as util
from trelby.line import Line
from trelby.textedit import TextEdit

_ = translations.trelby_translations_load()

# characters above U+00FF: Polish, Czech, the euro sign, Cyrillic and
# Greek. see also test_keyinput.py for typing them.

TEXT = "łŁčČžŽ€ПётрΩμέγα"


def testValidInputChars():
    for ch in TEXT + "äÅ ~\xa0" + "—«»™№ĳǆ":
        assert util.isValidInputChar(ord(ch)), ch

    # control characters, DEL, the C1 range, soft hyphen, zero-width and
    # bidi format characters, line/paragraph separators, surrogates,
    # private use and unassigned code points
    for kc in (
        [0, 9, 10, 13, 31, 0x7F, 0x80, 0x85, 0x9F, 0xAD]
        + [0x200B, 0x200E, 0x202E, 0x2028, 0x2029, 0xFEFF]
        + [0xD800, 0xDFFF, 0xE000, 0xFFFF, 0x110000]
    ):
        assert not util.isValidInputChar(kc), hex(kc)


def testLatin1RangeUnchanged():
    # the old check allowed 32-255 minus 0x7F-0x9F and 0xAD
    for kc in range(256):
        old = (32 <= kc <= 255) and not (0x7F <= kc < 0xA0) and (kc != 0xAD)
        assert util.isValidInputChar(kc) == old, kc


def testRemoveInvalidChars():
    assert util.removeInvalidChars("a\x85ł\xadb\n€\u200b\u2028") == "ałb\n€"
    assert util.removeInvalidChars("a\nb\tc", keep="\t") == "ab\tc"


def testCleanInputComposes():
    # "c" + combining caron -> "č", so it takes up one column
    assert util.cleanInput("c\u030capek") == "čapek"


def testUpperLower():
    assert util.upper("łódź čapek пётр ωμέγα ǆ") == "ŁÓDŹ ČAPEK ПЁТР ΩΜΈΓΑ Ǆ"
    assert util.lower("ŁÓDŹ ČAPEK ПЁТР ΩΜΈΓΑ") == "łódź čapek пётр ωμέγα"


def testUpperLowerKeepLength():
    # these have case mappings longer than one character; the script's
    # layout counts characters, so they're left as they are
    assert util.upper("straße") == "STRAßE"
    assert util.upper("ŉ ﬁx") == "ŉ ﬁX"
    assert util.lower("İSTANBUL") == "İstanbul"
    assert util.capitalize("ßa") == "ßa"


def testKeysAboveLatin1AreSpecialKeys():
    # key codes above 255 are wx.WXK_ constants, even when the same number
    # is a letter as a code point (WXK_LEFT = 314 = "ĺ")
    assert util.Key(ord("a")).isValidInputChar()
    assert util.Key(ord("ä")).isValidInputChar()
    assert not util.Key(wx.WXK_LEFT).isValidInputChar()
    assert not util.Key(wx.WXK_F1).isValidInputChar()
    assert util.Key(wx.WXK_LEFT, ctrl=True).toStr() == "CTRL+Left"
    assert util.Key(wx.WXK_INSERT).toStr() == "Insert"
    assert util.Key(ord("ä"), alt=True).toStr() == "ALT+Ä"

    # "ÿ" uppercases to "Ÿ" (U+0178), which would clash with a WXK constant
    assert util.Key(ord("ÿ"), alt=True).kc == ord("ÿ")


def testKeyBindingsSurviveLoad():
    u.init()
    cfg = config.ConfigGlobal()
    keys = {cmd.name: cmd.keys for cmd in cfg.commands}

    cfg2 = config.ConfigGlobal()
    cfg2.load(cfg.save())

    for cmd in cfg2.commands:
        if keys[cmd.name] != [0]:
            assert cmd.keys == keys[cmd.name], cmd.name

    moveLeft = [cmd for cmd in cfg2.commands if cmd.name == "MoveLeft"][0]
    assert util.Key(wx.WXK_LEFT).toInt() in moveLeft.keys


def testSaveLoadRoundTrip():
    sp = u.load("unicode.trelby")
    texts = [ln.text for ln in sp.lines]

    assert texts[0] == "Int. Łódź — mieszkanie Čapka"
    assert texts[2] == "Пётр"
    assert "Ωμέγα" in texts[3]
    assert "€" in texts[1]

    sp2 = u.loadString(sp.save().decode("UTF-8"))
    assert [ln.text for ln in sp2.lines] == texts
    assert [ln.lt for ln in sp2.lines] == [ln.lt for ln in sp.lines]

    sp2.line = 0
    sp2.column = len(sp2.lines[0].text)
    sp2.cmd("addChar", char="ł")
    sp3 = u.loadString(sp2.save().decode("UTF-8"))
    assert sp3.lines[0].text.endswith("Čapkał")


def testUppercaseHeadingsAndNames():
    sp = u.load("unicode.trelby")
    sp.paginate()

    text = export.generateText(sp, False)
    assert "INT. ŁÓDŹ — MIESZKANIE ČAPKA" in text
    assert "ПЁТР" in text
    assert "EWA ŻAK" in text

    # dialogue isn't uppercased, and "ß" stays as it is
    assert "Ωμέγα" in text
    assert "Straße" in text

    assert sp.getExportText(0) == "INT. ŁÓDŹ — MIESZKANIE ČAPKA"
    assert "INT. ŁÓDŹ — MIESZKANIE ČAPKA" in sp.getSceneNames()
    assert "пётр" in sp.getCharacterNames()


def testTypeIntoSceneHeading():
    sp = u.new()
    sp.lines[0].lt = screenplay.SCENE

    # the first letter of a sentence is capitalized as you type
    for ch in "ext. łąka żółta":
        sp.cmd("addChar", char=ch)

    assert sp.lines[0].text == "Ext. Łąka żółta"
    assert sp.getExportText(0) == "EXT. ŁĄKA ŻÓŁTA"


def testAddCharRejectsInvalid():
    sp = u.new()

    for ch in "a\x85\xad\u200b\u2028b":
        sp.cmd("addChar", char=ch)

    assert sp.lines[0].text == "Ab"


def testPasteTextEdit():
    ed = TextEdit([""])
    ed.insert("łódź\x85\xad €\r\nc\u030capek Пётр")

    assert ed.lines == ["łódź €", "čapek Пётр"]


def testSpellCheckerPrefix():
    assert util.getWordPrefix("ab") == "ab"
    assert util.getWordPrefix("AB") == "ab"
    assert util.getWordPrefix("äb") == "zb"
    assert util.getWordPrefix("łó") == "zz"
    assert util.getWordPrefix("Пё") == "zz"

    d = spellcheck.Dict()
    d.add("Łódź")
    d.add("Пётр")
    assert d.isKnown("łódź")
    assert d.isKnown("пётр")


def testSpellCheckerFindsWords():
    sp = u.load("unicode.trelby")
    sc = spellcheck.SpellChecker(sp, spellcheck.Dict())

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
    sp = u.load("unicode.trelby")
    sp.paginate()
    doc = render.generatePML(sp)

    chars = pdf.unsupportedChars(doc)
    # character names and scene headings are uppercased
    for ch in "łŁČПЁТРΩμ":
        assert ch in chars, ch

    # WinAnsi has these
    for ch in "€óäß«»—ž":
        assert ch not in chars, ch

    # renders without errors anyway
    assert pdf.generate(doc)[:8] == b"%PDF-1.5"


def testPDFCustomFont():
    sp = u.load("unicode.trelby")
    sp.paginate()

    for pfi in sp.cfg.getPDFFontIds():
        pf = sp.cfg.getPDFFont(pfi)
        pf.pdfName = "Jost"
        pf.filename = u.fixtureFilePath("custom-font/Jost-400-Book.ttf")

    doc = render.generatePML(sp)

    assert pdf.unsupportedChars(doc) == ""
    assert pdf.generate(doc)[:8] == b"%PDF-1.5"


def testPDFFormattedRuns():
    doc = pml.Document(210, 297)
    pg = pml.Page(doc)
    doc.add(pg)

    # "ł" is bold, and only the bold font is a custom one
    pg.add(pml.TextOp("ał", 10, 10, 12, fmt="\x00\x01"))
    doc.addFont(pml.COURIER | pml.BOLD, pml.PDFFontInfo("Jost", "x.ttf"))
    assert pdf.unsupportedChars(doc) == ""

    pg.add(pml.TextOp("łč", 10, 20, 12))
    assert pdf.unsupportedChars(doc) == "čł"


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
    sp = u.load("unicode.trelby")
    sp.titles.pages = [
        [titles.TitleString(["Łódź — Пётр"], y=100.0, font=pml.HELVETICA)]
    ]
    sp.paginate()

    assert export.generatePDF(sp)[:8] == b"%PDF-1.5"


def testEscapeRTF():
    assert util.escapeRTF("a{b}\\") == r"a\{b\}\\"
    assert util.escapeRTF("äł€") == r"\u228?\u322?\u8364?"

    # characters above U+FFFF are UTF-16 surrogate pairs, signed
    assert util.escapeRTF("\U0001f600") == r"\u-10179?\u-8704?"


def testExportRTF():
    sp = u.load("unicode.trelby")
    sp.paginate()

    rtf = export.generateRTF(sp)
    assert rtf.isascii()
    assert r"\u321?" in rtf  # Ł
