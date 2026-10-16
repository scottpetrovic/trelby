import copy

import tests.u as u
import trelby.mcptools as m
import trelby.pagelock as pagelock
import trelby.screenplay as scr
import trelby.translations as translations
from trelby.line import Line

_ = translations.trelby_translations_load()

# tests for scene locking: pagelock.sceneLabels and the Screenplay
# functions using it


# return a script with 'scenes' scenes, each with a heading and two
# action elements
def makeScript(scenes=5):
    lines = ["#Version 3", "#Start-Script "]

    for s in range(scenes):
        lines.append(".\\INT. ROOM %d - DAY" % (s + 1))
        lines.append("..Scene %d, first action." % (s + 1))
        lines.append("..Scene %d, second action." % (s + 1))

    sp = u.loadString("\n".join(lines))
    sp.paginate()

    return sp


def makeLocked(**kwargs):
    sp = makeScript(**kwargs)
    sp.lockScenes()

    return sp


# return {heading: scene number} for all scenes
def numbers(sp):
    return {sp.lines[i].text: label for i, label in sp.getSceneLabels()}


# return scene numbers in script order
def labels(sp):
    return [label for i, label in sp.getSceneLabels()]


# return lines making up a new scene with the given heading
def newScene(heading):
    return [
        Line(scr.LB_LAST, scr.SCENE, heading),
        Line(scr.LB_LAST, scr.ACTION, "Something happens."),
    ]


# select the whole scene with the given (0-based) index
def selectScene(sp, idx):
    starts = sp.getSceneStarts()
    end = (starts[idx + 1] if idx + 1 < len(starts) else len(sp.lines)) - 1

    sp.setMark(starts[idx], 0)
    sp.gotoPos(end, len(sp.lines[end].text))


def testSceneLabelsUnlocked():
    assert pagelock.sceneLabels(3, {}) == ["1", "2", "3"]
    assert pagelock.sceneLabels(0, {}) == []


def testSceneLabelsAdded():
    assert pagelock.sceneLabels(5, {0: "1", 1: "2", 4: "3"}) == [
        "1",
        "2",
        "2A",
        "2B",
        "3",
    ]
    assert pagelock.sceneLabels(3, {0: "1", 1: "2"}) == ["1", "2", "2A"]
    assert pagelock.sceneLabels(3, {2: "1"}) == ["A1", "B1", "1"]
    assert pagelock.sceneLabels(2, {1: "5"}) == ["A5", "5"]


def testSceneLabelsBetweenAScenes():
    assert pagelock.sceneLabels(3, {0: "2", 1: "2A", 2: "2B"}) == ["2", "2A", "2B"]
    assert pagelock.sceneLabels(3, {0: "2A", 2: "2B"}) == ["2A", "2AA", "2B"]
    assert pagelock.sceneLabels(2, {1: "A1"}) == ["0A", "A1"]

    # every label must be valid and in order
    for result in (
        pagelock.sceneLabels(4, {0: "2A", 3: "2B"}),
        pagelock.sceneLabels(3, {2: "A1"}),
        pagelock.sceneLabels(3, {0: "3", 2: "3A"}),
    ):
        keys = [pagelock.labelRange(label)[0] for label in result]
        assert all(pagelock.isValidScene(label) for label in result)
        assert keys == sorted(keys)


def testSceneLabelsSkipMovedScenes():
    # scene 6 was moved between 2 and 3, and a scene was added after it:
    # the new one is numbered after 2, the last scene in order.
    result = pagelock.sceneLabels(6, {0: "1", 1: "2", 2: "6", 4: "3", 5: "4"})
    assert result == ["1", "2", "6", "2A", "3", "4"]

    # labels a moved scene has aren't reused
    result = pagelock.sceneLabels(4, {0: "1", 1: "1A", 3: "2"})
    assert result == ["1", "1A", "1B", "2"]
    result = pagelock.sceneLabels(4, {0: "1", 1: "1B", 2: "0"})
    assert result[3] not in ("1", "1B", "0")


def testSceneLabelValidity():
    assert pagelock.isValidScene("12")
    assert pagelock.isValidScene("12A")
    assert pagelock.isValidScene("A1")
    assert not pagelock.isValidScene("12-13")
    assert not pagelock.isValidScene("")
    assert not pagelock.isValidScene("X")


def testUnlockedNumbering():
    sp = makeScript()

    assert labels(sp) == ["1", "2", "3", "4", "5"]
    assert not sp.hasSceneLocks()
    assert sp.getSceneNumber(-1) == ""
    assert sp.getSceneNumber(sp.getSceneStarts()[2] + 1) == "3"


def testLock():
    sp = makeLocked()

    assert sp.hasSceneLocks()
    assert labels(sp) == ["1", "2", "3", "4", "5"]
    assert [sp.lines[i].sceneLock for i in sp.getSceneStarts()] == labels(sp)


def testAddedSceneGetsAScene():
    sp = makeLocked()

    sp.gotoPos(sp.getSceneStarts()[2], 0)
    sp.paste(newScene("INT. NEW ROOM - DAY") + newScene("INT. NEWER ROOM - DAY"))
    sp._validate()

    assert numbers(sp) == {
        "INT. ROOM 1 - DAY": "1",
        "INT. ROOM 2 - DAY": "2",
        "INT. NEW ROOM - DAY": "2A",
        "INT. NEWER ROOM - DAY": "2B",
        "INT. ROOM 3 - DAY": "3",
        "INT. ROOM 4 - DAY": "4",
        "INT. ROOM 5 - DAY": "5",
    }


def testAddedSceneAtStart():
    sp = makeLocked()

    sp.gotoPos(0, 0)
    sp.paste(newScene("INT. PROLOGUE - DAY"))
    sp._validate()

    assert labels(sp) == ["A1", "1", "2", "3", "4", "5"]


def testAddedSceneAtEnd():
    sp = makeLocked()

    sp.gotoPos(len(sp.lines) - 1, len(sp.lines[-1].text))
    sp.cmd("splitElement")
    sp.convertTypeTo(scr.SCENE, True)
    for ch in "INT. EPILOGUE":
        sp.cmd("addChar", char=ch)
    sp._validate()

    assert labels(sp) == ["1", "2", "3", "4", "5", "5A"]


def testDeleteSceneLeavesGap():
    sp = makeLocked()

    selectScene(sp, 2)
    sp.getSelectedAsCD(True)
    sp._validate()

    assert labels(sp) == ["1", "2", "4", "5"]


def testCutPasteKeepsNumber():
    sp = makeLocked()

    selectScene(sp, 1)
    cd = sp.getSelectedAsCD(True)
    assert labels(sp) == ["1", "3", "4", "5"]

    sp.gotoPos(sp.getSceneStarts()[3], 0)
    sp.paste(cd.lines)
    sp._validate()

    assert numbers(sp)["INT. ROOM 2 - DAY"] == "2"
    assert labels(sp) == ["1", "3", "4", "2", "5"]

    # pasting it again makes a new scene
    sp.gotoPos(sp.getSceneStarts()[1], 0)
    sp.paste(cd.lines)
    sp._validate()

    assert labels(sp) == ["1", "1A", "3", "4", "2", "5"]


def testCopyPasteMakesNewScene():
    sp = makeLocked()

    selectScene(sp, 1)
    cd = sp.getSelectedAsCD(False)
    assert cd.lines[0].sceneLock == "2"

    sp.gotoPos(sp.getSceneStarts()[3], 0)
    sp.paste(cd.lines)
    sp._validate()

    assert labels(sp) == ["1", "2", "3", "3A", "4", "5"]
    assert numbers(sp)["INT. ROOM 4 - DAY"] == "4"


def testMoveSceneKeepsNumber():
    sp = makeLocked()
    starts = sp.getOutlineStarts()

    sp.moveSceneTo(starts[4], 1)
    sp._validate()

    assert labels(sp) == ["1", "5", "2", "3", "4"]

    # a scene added after the moved one is numbered after scene 1
    sp.gotoPos(sp.getSceneStarts()[2], 0)
    sp.paste(newScene("INT. NEW ROOM - DAY"))

    assert labels(sp) == ["1", "5", "1A", "2", "3", "4"]


def testTypingKeepsNumber():
    sp = makeLocked()
    start = sp.getSceneStarts()[2]

    # make the heading long enough to wrap onto more lines
    sp.gotoPos(start, len(sp.lines[start].text))
    for ch in " AND A VERY LONG HEADING THAT GOES ON AND ON AND ON AND ON":
        sp.cmd("addChar", char=ch)
    sp.gotoPos(start, 0)
    sp.cmd("addChar", char="X")
    sp._validate()

    assert sp.getElemLastIndexFromLine(start) > start
    assert labels(sp) == ["1", "2", "3", "4", "5"]


def testConvertToActionAndBack():
    sp = makeLocked()
    start = sp.getSceneStarts()[2]

    sp.gotoPos(start, 0)
    sp.convertTypeTo(scr.ACTION, True)
    assert labels(sp) == ["1", "2", "4", "5"]

    sp.convertTypeTo(scr.SCENE, True)
    assert labels(sp) == ["1", "2", "3", "4", "5"]


def testJoinWithPrevElementLosesNumber():
    sp = makeLocked()

    sp.gotoPos(sp.getSceneStarts()[2], 0)
    sp.cmd("deleteBackward")
    sp._validate()

    assert labels(sp) == ["1", "2", "4", "5"]


def testUndoRedo():
    sp = makeScript()
    sp.lockScenes()

    sp.cmd("undo")
    assert not sp.hasSceneLocks()

    sp.cmd("redo")
    assert sp.hasSceneLocks()

    selectScene(sp, 2)
    sp.getSelectedAsCD(True)
    assert labels(sp) == ["1", "2", "4", "5"]

    sp.cmd("undo")
    assert labels(sp) == ["1", "2", "3", "4", "5"]
    assert all(sp.getSceneLock(i) for i in sp.getSceneStarts())


def testUnlock():
    sp = makeLocked()

    selectScene(sp, 2)
    sp.getSelectedAsCD(True)
    sp.unlockScenes()

    assert not sp.hasSceneLocks()
    assert labels(sp) == ["1", "2", "3", "4"]

    sp.cmd("undo")
    assert labels(sp) == ["1", "2", "4", "5"]


def testRelockLocksAScenes():
    sp = makeLocked()

    sp.gotoPos(sp.getSceneStarts()[2], 0)
    sp.paste(newScene("INT. NEW ROOM - DAY"))
    sp.lockScenes()

    assert sp.getSceneLock(sp.getSceneStarts()[2]) == "2A"

    # now that 2A is locked, a scene added before it has no letter left,
    # like with page locks
    sp.gotoPos(sp.getSceneStarts()[2], 0)
    sp.paste(newScene("INT. NEWER ROOM - DAY"))

    assert labels(sp) == ["1", "2", "2.1", "2A", "3", "4", "5"]


def testLockWhenLockedDoesNothing():
    sp = makeLocked()
    sp.cmd("undo")
    sp.cmd("redo")

    sp.lockScenes()
    sp.cmd("undo")

    # the second lock added no undo step, so this undid the first one
    assert not sp.hasSceneLocks()


def testSaveLoad():
    sp = makeLocked()
    sp.gotoPos(sp.getSceneStarts()[2], 0)
    sp.paste(newScene("INT. NEW ROOM - DAY"))

    data = sp.save().decode("UTF-8")
    assert data.count("#Scene-Lock ") == 5
    assert "#Scene-Lock 3\n.\\INT. ROOM 3 - DAY" in data

    sp2 = u.loadString(data)
    assert labels(sp2) == labels(sp) == ["1", "2", "2A", "3", "4", "5"]


def testLoadIgnoresInvalidLocks():
    sp = u.loadString(
        "\n".join(
            [
                "#Version 3",
                "#Start-Script ",
                "#Scene-Lock 2-3",
                ".\\INT. A",
                "#Scene-Lock 4",
                "..Not a scene heading.",
                "#Scene-Lock 7",
                ".\\INT. B",
                "#Scene-Lock 7",
                ".\\INT. C",
            ]
        )
    )

    # the first lock isn't valid, the second isn't on a scene heading,
    # and the last one is a duplicate
    assert labels(sp) == ["A7", "7", "7A"]

    data = sp.save().decode("UTF-8")
    assert "2-3" not in data
    assert "#Scene-Lock 4" not in data


def testDeepcopyKeepsLocks():
    sp = makeLocked()
    sp2 = copy.deepcopy(sp)

    assert labels(sp2) == labels(sp)
    assert sp2.hasSceneLocks()


def testOutlineAndLocations():
    sp = makeLocked()
    sp.gotoPos(sp.getSceneStarts()[1], 0)
    sp.paste(newScene("INT. NEW ROOM - DAY"))

    expected = ["1", "1A", "2", "3", "4", "5"]

    assert [it.sceneNr for it in sp.getOutline()] == expected
    assert [nr for nr, line in sp.getSceneLocations()] == expected
    assert sp.getSceneNumber(sp.getSceneStarts()[1] + 1) == "1A"


def testPDFShowsNumbers():
    sp = makeLocked()
    sp.gotoPos(sp.getSceneStarts()[1], 0)
    sp.paste(newScene("INT. NEW ROOM - DAY"))
    sp.cfg.pdfShowSceneNumbers = True
    sp.paginate()

    texts = [
        op.text for pg in sp.generatePML().pages for op in pg.ops if hasattr(op, "text")
    ]

    # each number is printed on both sides of its heading
    assert texts.count("1A") == 2
    assert texts.count("5") == 2


def testMCPListAndReplace(tmp_path):
    path = str(tmp_path / "locked.trelby")
    sp = makeLocked()
    sp.gotoPos(sp.getSceneStarts()[1], 0)
    sp.paste(newScene("INT. NEW ROOM - DAY"))

    with open(path, "wb") as f:
        f.write(sp.save())

    res = m.listScenes(m.FileDoc(path))
    assert [s["scene_number"] for s in res["scenes"]] == [
        "1",
        "1A",
        "2",
        "3",
        "4",
        "5",
    ]

    # a replaced scene keeps its number
    res = m.replaceScene(
        m.FileDoc(path),
        res["revision"],
        4,
        [{"type": "scene", "text": "EXT. ROOF - NIGHT"}],
    )
    assert res["scenes"][3]["heading"] == "EXT. ROOF - NIGHT"
    assert res["scenes"][3]["scene_number"] == "3"
