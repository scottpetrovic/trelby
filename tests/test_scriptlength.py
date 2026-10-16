import tests.u as u
import trelby.screenplay as scr
from trelby.screenplay.line import Line

# tests for the status bar's script length figures: Screenplay.getWordCount
# and Screenplay.getPageLength


def loadSmall():
    return u.loadString(
        "\n".join(
            [
                "#Version 3",
                # the trailing space is required by the file format
                "#Start-Script ",
                ".\\int. kitchen - day",
                "..Mary cooks -- badly.",
                "._MARY",
                ".:Hello there.",
            ]
        )
    )


def testWordCount():
    sp = loadSmall()

    assert sp.getWordCount() == 11


def testWordCountEmpty():
    sp = u.new()

    assert sp.getWordCount() == 0


def testWordCountAcrossLines():
    sp = loadSmall()

    # split the action line in two. a space break keeps two words, a
    # break without a space joins them into one.
    ln = sp.lines[1]
    sp.lines.insert(2, Line(scr.LB_LAST, scr.ACTION, "badly."))
    ln.text = "Mary cooks --"
    ln.lb = scr.LB_SPACE
    assert sp.getWordCount() == 11

    ln.text = "Mary cooks --bad"
    sp.lines[2].text = "ly."
    ln.lb = scr.LB_NONE
    assert sp.getWordCount() == 10


def testWordCountSample():
    sp = u.load()

    words = sum(len(ln.text.split()) for ln in sp.lines)
    assert 0 < sp.getWordCount() <= words


def testPageLengthShort():
    sp = loadSmall()
    sp.paginate()

    length = sp.getPageLength()
    assert 0.0 < length < 1.0


def testPageLengthMatchesPages():
    sp = u.load()
    sp.paginate()

    pageCnt = len(sp.pages) - 1
    length = sp.getPageLength()

    assert pageCnt > 1
    assert (pageCnt - 1) < length <= pageCnt


def testPageLengthStalePagination():
    sp = u.load()
    sp.paginate()

    # pagination isn't redone on every edit, so pages can point past the
    # end of the script
    del sp.lines[len(sp.lines) // 2 :]

    assert sp.getPageLength() >= 0.0
