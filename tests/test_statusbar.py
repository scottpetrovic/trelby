import trelby.statusbar as statusbar
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
