import copy

import tests.u as u
import trelby.screenplay.beatboard as beatboard

# test the beat board (screenplay/beatboard.py): its cards, saving and
# loading them as part of a script, and replacing the board as an
# undoable edit


def beat(text="", x=0, y=0):
    return beatboard.Beat(text, x, y)


# an editor on test.trelby with a board of one card
def boardEditor():
    ed = u.loadEditor()

    board = beatboard.BeatBoard()
    board.beats.append(beat("The chase", 20, 40))
    assert ed.setBeatBoard(board)

    return ed


def test_saveLoad():
    b = beat("Title\nline \\ two\r\nend", 15, 300)
    b.color = "ffb3b3"
    b.extra["Future"] = "value"

    board = beatboard.BeatBoard()
    board.beats = [b, beat()]

    s = board.save()
    board2 = beatboard.BeatBoard()
    board2.load(s)

    assert len(board2.beats) == 2
    b2 = board2.beats[0]
    assert (b2.text, b2.x, b2.y, b2.color) == (b.text, 15, 300, "ffb3b3")
    assert b2.extra == {"Future": "value"}
    assert board2.save() == s


def test_invalidValues():
    board = beatboard.BeatBoard()
    board.load("Beats:1\nBeat/1/X:-5\nBeat/1/Y:abc\nBeat/1/Color:red\ngarbage\n")

    b = board.beats[0]
    assert (b.x, b.y, b.color) == (0, 0, None)


def test_title():
    assert beat("\n  First \nsecond").getTitle() == "First"
    assert beat(" \n ").getTitle() == ""


def test_scriptRoundTrip():
    ed = boardEditor()

    data = ed.sp.save().decode("UTF-8")
    lines = data.splitlines()

    # the section comes before the script and looks like unknown lines to
    # older versions, which skip them
    start = lines.index("#Begin-Beat-Board ")
    end = lines.index("#End-Beat-Board ")
    assert start < end < lines.index("#Start-Script ")

    for s in lines[start + 1 : end]:
        assert not s.startswith("#")

    sp2 = u.loadString(data)
    assert sp2.beatBoard.beats[0].text == "The chase"
    assert (sp2.beatBoard.beats[0].x, sp2.beatBoard.beats[0].y) == (20, 40)
    assert sp2.save().decode("UTF-8") == data


def test_emptyNoSection():
    sp = u.load()

    assert "Beat-Board" not in sp.save().decode("UTF-8")


def test_noChange():
    ed = boardEditor()

    assert not ed.setBeatBoard(copy.deepcopy(ed.sp.beatBoard))


def test_undoRedo():
    ed = boardEditor()
    lines = [str(ln) for ln in ed.sp.lines]

    ed.cmd("undo")
    assert not ed.sp.beatBoard.beats
    assert [str(ln) for ln in ed.sp.lines] == lines

    ed.cmd("redo")
    assert ed.sp.beatBoard.beats[0].text == "The chase"
    ed._validate()


def test_deepcopy():
    ed = boardEditor()

    sp2 = copy.deepcopy(ed.sp)
    sp2.beatBoard.beats[0].text = "changed"

    assert ed.sp.beatBoard.beats[0].text == "The chase"


def test_image():
    b = beat("A face", 10, 10)
    b.image = b"\x89PNG\r\n\x1a\n\x00\xff picture bytes"

    board = beatboard.BeatBoard()
    board.beats = [b, beat("No picture")]

    s = board.save()
    board2 = beatboard.BeatBoard()
    board2.load(s)

    assert board2.beats[0].image == b.image
    assert board2.beats[1].image is None
    assert board2.save() == s

    # one that isn't base64 is dropped
    board2.load("Beats:1\nBeat/1/Image:not base64!\n")
    assert board2.beats[0].image is None
    assert not board2.beats[0].extra


def test_imageScriptRoundTrip():
    ed = u.loadEditor()

    board = beatboard.BeatBoard()
    board.beats.append(beat("", 0, 0))
    board.beats[0].image = bytes(range(256)) * 400
    assert ed.setBeatBoard(board)

    data = ed.sp.save().decode("UTF-8")
    sp2 = u.loadString(data)
    assert sp2.beatBoard.beats[0].image == board.beats[0].image
    assert sp2.save().decode("UTF-8") == data

    # the undo step keeps the picture too
    board2 = copy.deepcopy(board)
    board2.beats[0].image = None
    assert ed.setBeatBoard(board2)
    ed.cmd("undo")
    assert ed.sp.beatBoard.beats[0].image == board.beats[0].image
