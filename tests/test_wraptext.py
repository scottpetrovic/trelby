import tests.u as u
import trelby.util as util

# tests for util.wrapText, measuring text in columns: one per character,
# two for wide ones


def measure(s):
    return sum(2 if util.isWideChar(ch) else 1 for ch in s)


def wrap(text, width):
    return util.wrapText(text, width, measure)


def testFits():
    assert wrap("", 10) == ""
    assert wrap("one two", 10) == "one two"
    assert wrap("one two", 7) == "one two"


def testBreaksAtSpaces():
    assert wrap("one two three", 7) == "one two\nthree"
    assert wrap("one two three", 6) == "one\ntwo\nthree"

    # the spaces at a break are dropped
    assert wrap("one   two", 3) == "one\ntwo"


def testKeepsLineBreaks():
    assert wrap("one two\n\nthree four", 20) == "one two\n\nthree four"
    assert wrap("one two\nthree", 3) == "one\ntwo\nthree"


def testLongWord():
    # a word wider than the width gets a line of its own
    assert wrap("a abcdefgh b", 4) == "a\nabcdefgh\nb"
    assert wrap("abcdefgh", 4) == "abcdefgh"


def testWideChars():
    # each character is two columns wide, and lines can break between
    # any two of them
    assert wrap("拼写检查器", 6) == "拼写检\n查器"

    # between a wide character and a Latin one too
    assert wrap("用MCP服务器", 8) == "用MCP服\n务器"


def testWidePunctuation():
    # closing punctuation doesn't start a line: the character before it
    # moves down with it
    assert wrap("拼写，检查", 4) == "拼\n写，\n检查"

    # and if that's the only character, the line gets too wide
    assert wrap("拼，", 2) == "拼，"
    assert wrap("拼写检查。", 8) == "拼写检\n查。"
