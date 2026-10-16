import copy

import tests.u as u
import trelby.screenplay.beatboard as beatboard

# test the beat board (screenplay/beatboard.py): its cards, saving and
# loading them, and the scene ids that link them to scenes, which must stay
# on their scene through editing


def beat(text="", x=0, y=0, sceneId=None):
    b = beatboard.Beat(text, x, y)
    b.sceneId = sceneId

    return b


# an editor on test.trelby, with a board of one card linked to the scene
# that's item 'idx' of the outline. returns (ed, the scene's first line).
def linkedEditor(idx=2):
    ed = u.loadEditor()
    line = ed.sp.getOutlineStarts()[idx]

    board = beatboard.BeatBoard()
    board.beats.append(beat("The chase", 20, 20, "1"))
    assert ed.setBeatBoard(board, {line: "1"})

    return ed, line


def test_saveLoad():
    b = beat("Title\nline \\ two\r\nend", 15, 300, "7")
    b.color = "ffb3b3"
    b.extra["Future"] = "value"

    board = beatboard.BeatBoard()
    board.beats = [b, beat()]

    s = board.save()
    board2 = beatboard.BeatBoard()
    board2.load(s)

    assert len(board2.beats) == 2
    b2 = board2.beats[0]
    assert (b2.text, b2.x, b2.y, b2.color, b2.sceneId) == (
        b.text,
        15,
        300,
        "ffb3b3",
        "7",
    )
    assert b2.extra == {"Future": "value"}
    assert board2.save() == s
    assert board2.beats[1].sceneId is None


def test_invalidValues():
    board = beatboard.BeatBoard()
    board.load(
        "Beats:1\nBeat/1/X:-5\nBeat/1/Y:abc\nBeat/1/Color:red\n"
        "Beat/1/Scene:0\ngarbage\n"
    )

    b = board.beats[0]
    assert (b.x, b.y, b.color, b.sceneId) == (0, 0, None, None)


def test_title():
    assert beat("\n  First \nsecond").getTitle() == "First"
    assert beat(" \n ").getTitle() == ""


def test_findFreeSpot():
    G, W, H = beatboard.GAP, beatboard.CARD_WIDTH, beatboard.CARD_HEIGHT

    board = beatboard.BeatBoard()
    assert beatboard.findFreeSpot(board) == (G, G)

    board.beats.append(beat("", G, G))
    assert beatboard.findFreeSpot(board) == (2 * G + W, G)

    # a card between spots blocks all four around it
    board.beats = [beat("", G + W // 2, G + H // 2)]
    assert beatboard.findFreeSpot(board, columns=2) == (G, 3 * G + 2 * H)


def test_newSceneId():
    assert beatboard.newSceneId(set()) == "1"
    assert beatboard.newSceneId({"3", "12"}) == "13"


def test_link():
    ed, line = linkedEditor()
    sp = ed.sp

    assert sp.getSceneId(line) == "1"
    assert sp.findSceneId("1") == line
    assert sp.findSceneId("2") == -1
    ed._validate()


def test_scriptRoundTrip():
    ed, line = linkedEditor()

    data = ed.sp.save().decode("UTF-8")
    lines = data.splitlines()

    # the section comes before the script and looks like unknown lines to
    # older versions, which skip them
    start = lines.index("#Begin-Beat-Board ")
    end = lines.index("#End-Beat-Board ")
    assert start < end < lines.index("#Start-Script ")

    for s in lines[start + 1 : end]:
        assert not s.startswith("#")

    assert data.count("#Scene-Id ") == 1

    sp2 = u.loadString(data)
    assert sp2.beatBoard.beats[0].text == "The chase"
    assert sp2.findSceneId("1") == line
    assert sp2.save().decode("UTF-8") == data


def test_emptyNoSection():
    sp = u.load()
    data = sp.save().decode("UTF-8")

    assert "Beat-Board" not in data
    assert "Scene-Id" not in data


def test_unusedIdsNotSaved():
    ed, line = linkedEditor()

    board = copy.deepcopy(ed.sp.beatBoard)
    board.beats[0].sceneId = None
    assert ed.setBeatBoard(board)

    # the id is still on the line, but nothing links to it
    assert ed.sp.getSceneId(line) == "1"
    assert "Scene-Id" not in ed.sp.save().decode("UTF-8")


def test_noChange():
    ed, line = linkedEditor()

    assert not ed.setBeatBoard(copy.deepcopy(ed.sp.beatBoard), {line: "1"})


def test_undoRedo():
    ed, line = linkedEditor()

    ed.cmd("undo")
    assert not ed.sp.beatBoard.beats
    assert ed.sp.getSceneId(line) is None

    ed.cmd("redo")
    assert ed.sp.beatBoard.beats[0].text == "The chase"
    assert ed.sp.findSceneId("1") == line
    ed._validate()


def test_moveScene():
    ed, line = linkedEditor()
    heading = ed.sp.getElemText(line)

    assert ed.moveSceneTo(line, 0)

    newLine = ed.sp.findSceneId("1")
    assert newLine == ed.sp.getOutlineStarts()[0]
    assert ed.sp.getElemText(newLine) == heading


def test_typingInHeading():
    ed, line = linkedEditor()

    ed.line, ed.column = line, 0

    for ch in "VERY LONG ADDITION TO THE SCENE HEADING SO THAT IT WRAPS - ":
        ed.cmd("addChar", char=ch)

    assert ed.sp.findSceneId("1") == line
    ed._validate()


def selectScene(ed, line):
    end = ed.sp.getOutlineStarts()
    end = end[end.index(line) + 1] - 1

    ed.setMark(line, 0)
    ed.line, ed.column = end, len(ed.sp.lines[end].text)


def test_cutPaste():
    ed, line = linkedEditor()
    heading = ed.sp.getElemText(line)

    selectScene(ed, line)
    cd = ed.getSelectedAsCD(True)
    assert ed.sp.findSceneId("1") == -1

    # paste it in front of the first scene
    ed.line, ed.column = ed.sp.getOutlineStarts()[0], 0
    ed.paste(cd.lines)

    newLine = ed.sp.findSceneId("1")
    assert newLine != -1
    assert ed.sp.getElemText(newLine) == heading
    ed._validate()


def test_copyPasteNoDuplicate():
    ed, line = linkedEditor()

    selectScene(ed, line)
    cd = ed.getSelectedAsCD(False)
    ed.clearMark()

    ed.line, ed.column = ed.sp.getOutlineStarts()[0], 0
    ed.paste(cd.lines)

    assert sum(1 for ln in ed.sp.lines if ln.sceneId == "1") == 1


def test_deletedScene():
    ed, line = linkedEditor()

    selectScene(ed, line)
    ed.getSelectedAsCD(True)

    # the card stays, linked to a scene that isn't there
    assert ed.sp.beatBoard.beats[0].sceneId == "1"
    assert ed.sp.findSceneId("1") == -1


def test_deepcopy():
    ed, line = linkedEditor()

    sp2 = copy.deepcopy(ed.sp)
    sp2.beatBoard.beats[0].text = "changed"

    assert ed.sp.beatBoard.beats[0].text == "The chase"
    assert sp2.findSceneId("1") == line
