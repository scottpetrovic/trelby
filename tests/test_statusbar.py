import trelby.ui.statusbar as statusbar
import trelby.translations as translations

_ = translations.trelby_translations_load()

# the texts in the main window's status bar


def testFormatWordCount():
    assert statusbar.formatWordCount(0) == "0 words"
    assert statusbar.formatWordCount(1) == "1 word"
    assert statusbar.formatWordCount(1234567) == "1,234,567 words"


def testFormatRuntime():
    assert statusbar.formatRuntime(0) == "Runtime: ~0 min"
    assert statusbar.formatRuntime(59) == "Runtime: ~59 min"
    assert statusbar.formatRuntime(60) == "Runtime: ~1 h 0 min"
    assert statusbar.formatRuntime(135) == "Runtime: ~2 h 15 min"


def testFormatToday():
    assert statusbar.formatToday(0, 0, 0, False) == "0 words today"
    assert statusbar.formatToday(1, 0, 0, False) == "1 word today"
    assert statusbar.formatToday(1234, 0, 0, False) == "1,234 words today"
    assert statusbar.formatToday(412, 0, 1000, False) == "412 / 1,000 words today"

    assert statusbar.formatToday(0, 1.0, 0, True) == "1 page today"
    assert statusbar.formatToday(0, 1.54, 0, True) == "1.5 pages today"
    assert statusbar.formatToday(0, 0.0, 3, True) == "0 / 3 pages today"
