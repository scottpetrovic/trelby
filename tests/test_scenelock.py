import copy

import tests.u as u
import trelby.mcptools as m
import trelby.pagelock as pagelock
import trelby.screenplay as scr
import trelby.screenplay.render as render
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

    ed = u.loadStringEditor("\n".join(lines))
    ed.sp.paginate()

    return ed


def makeLocked(**kwargs):
    ed = makeScript(**kwargs)
    ed.lockScenes()

    return ed


# return {heading: scene number} for all scenes
def numbers(ed):
    return {ed.sp.lines[i].text: label for i, label in ed.sp.getSceneLabels()}


# return scene numbers in script order
def labels(ed):
    return [label for i, label in ed.sp.getSceneLabels()]


# return lines making up a new scene with the given heading
def newScene(heading):
    return [
        Line(scr.LB_LAST, scr.SCENE, heading),
        Line(scr.LB_LAST, scr.ACTION, "Something happens."),
    ]


# select the whole scene with the given (0-based) index
def selectScene(ed, idx):
    starts = ed.sp.getSceneStarts()
    end = (starts[idx + 1] if idx + 1 < len(starts) else len(ed.sp.lines)) - 1

    ed.setMark(starts[idx], 0)
    ed.gotoPos(end, len(ed.sp.lines[end].text))


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
    ed = makeScript()

    assert labels(ed) == ["1", "2", "3", "4", "5"]
    assert not ed.sp.hasSceneLocks()
    assert ed.sp.getSceneNumber(-1) == ""
    assert ed.sp.getSceneNumber(ed.sp.getSceneStarts()[2] + 1) == "3"


def testLock():
    ed = makeLocked()

    assert ed.sp.hasSceneLocks()
    assert labels(ed) == ["1", "2", "3", "4", "5"]
    assert [ed.sp.lines[i].sceneLock for i in ed.sp.getSceneStarts()] == labels(ed)


def testAddedSceneGetsAScene():
    ed = makeLocked()

    ed.gotoPos(ed.sp.getSceneStarts()[2], 0)
    ed.paste(newScene("INT. NEW ROOM - DAY") + newScene("INT. NEWER ROOM - DAY"))
    ed._validate()

    assert numbers(ed) == {
        "INT. ROOM 1 - DAY": "1",
        "INT. ROOM 2 - DAY": "2",
        "INT. NEW ROOM - DAY": "2A",
        "INT. NEWER ROOM - DAY": "2B",
        "INT. ROOM 3 - DAY": "3",
        "INT. ROOM 4 - DAY": "4",
        "INT. ROOM 5 - DAY": "5",
    }


def testAddedSceneAtStart():
    ed = makeLocked()

    ed.gotoPos(0, 0)
    ed.paste(newScene("INT. PROLOGUE - DAY"))
    ed._validate()

    assert labels(ed) == ["A1", "1", "2", "3", "4", "5"]


def testAddedSceneAtEnd():
    ed = makeLocked()

    ed.gotoPos(len(ed.sp.lines) - 1, len(ed.sp.lines[-1].text))
    ed.cmd("splitElement")
    ed.convertTypeTo(scr.SCENE, True)
    for ch in "INT. EPILOGUE":
        ed.cmd("addChar", char=ch)
    ed._validate()

    assert labels(ed) == ["1", "2", "3", "4", "5", "5A"]


def testDeleteSceneLeavesGap():
    ed = makeLocked()

    selectScene(ed, 2)
    ed.getSelectedAsCD(True)
    ed._validate()

    assert labels(ed) == ["1", "2", "4", "5"]


def testCutPasteKeepsNumber():
    ed = makeLocked()

    selectScene(ed, 1)
    cd = ed.getSelectedAsCD(True)
    assert labels(ed) == ["1", "3", "4", "5"]

    ed.gotoPos(ed.sp.getSceneStarts()[3], 0)
    ed.paste(cd.lines)
    ed._validate()

    assert numbers(ed)["INT. ROOM 2 - DAY"] == "2"
    assert labels(ed) == ["1", "3", "4", "2", "5"]

    # pasting it again makes a new scene
    ed.gotoPos(ed.sp.getSceneStarts()[1], 0)
    ed.paste(cd.lines)
    ed._validate()

    assert labels(ed) == ["1", "1A", "3", "4", "2", "5"]


def testCopyPasteMakesNewScene():
    ed = makeLocked()

    selectScene(ed, 1)
    cd = ed.getSelectedAsCD(False)
    assert cd.lines[0].sceneLock == "2"

    ed.gotoPos(ed.sp.getSceneStarts()[3], 0)
    ed.paste(cd.lines)
    ed._validate()

    assert labels(ed) == ["1", "2", "3", "3A", "4", "5"]
    assert numbers(ed)["INT. ROOM 4 - DAY"] == "4"


def testMoveSceneKeepsNumber():
    ed = makeLocked()
    starts = ed.sp.getOutlineStarts()

    ed.moveSceneTo(starts[4], 1)
    ed._validate()

    assert labels(ed) == ["1", "5", "2", "3", "4"]

    # a scene added after the moved one is numbered after scene 1
    ed.gotoPos(ed.sp.getSceneStarts()[2], 0)
    ed.paste(newScene("INT. NEW ROOM - DAY"))

    assert labels(ed) == ["1", "5", "1A", "2", "3", "4"]


def testTypingKeepsNumber():
    ed = makeLocked()
    start = ed.sp.getSceneStarts()[2]

    # make the heading long enough to wrap onto more lines
    ed.gotoPos(start, len(ed.sp.lines[start].text))
    for ch in " AND A VERY LONG HEADING THAT GOES ON AND ON AND ON AND ON":
        ed.cmd("addChar", char=ch)
    ed.gotoPos(start, 0)
    ed.cmd("addChar", char="X")
    ed._validate()

    assert ed.sp.getElemLastIndexFromLine(start) > start
    assert labels(ed) == ["1", "2", "3", "4", "5"]


def testConvertToActionAndBack():
    ed = makeLocked()
    start = ed.sp.getSceneStarts()[2]

    ed.gotoPos(start, 0)
    ed.convertTypeTo(scr.ACTION, True)
    assert labels(ed) == ["1", "2", "4", "5"]

    ed.convertTypeTo(scr.SCENE, True)
    assert labels(ed) == ["1", "2", "3", "4", "5"]


def testJoinWithPrevElementLosesNumber():
    ed = makeLocked()

    ed.gotoPos(ed.sp.getSceneStarts()[2], 0)
    ed.cmd("deleteBackward")
    ed._validate()

    assert labels(ed) == ["1", "2", "4", "5"]


def testUndoRedo():
    ed = makeScript()
    ed.lockScenes()

    ed.cmd("undo")
    assert not ed.sp.hasSceneLocks()

    ed.cmd("redo")
    assert ed.sp.hasSceneLocks()

    selectScene(ed, 2)
    ed.getSelectedAsCD(True)
    assert labels(ed) == ["1", "2", "4", "5"]

    ed.cmd("undo")
    assert labels(ed) == ["1", "2", "3", "4", "5"]
    assert all(ed.sp.getSceneLock(i) for i in ed.sp.getSceneStarts())


def testUnlock():
    ed = makeLocked()

    selectScene(ed, 2)
    ed.getSelectedAsCD(True)
    ed.unlockScenes()

    assert not ed.sp.hasSceneLocks()
    assert labels(ed) == ["1", "2", "3", "4"]

    ed.cmd("undo")
    assert labels(ed) == ["1", "2", "4", "5"]


def testRelockLocksAScenes():
    ed = makeLocked()

    ed.gotoPos(ed.sp.getSceneStarts()[2], 0)
    ed.paste(newScene("INT. NEW ROOM - DAY"))
    ed.lockScenes()

    assert ed.sp.getSceneLock(ed.sp.getSceneStarts()[2]) == "2A"

    # now that 2A is locked, a scene added before it has no letter left,
    # like with page locks
    ed.gotoPos(ed.sp.getSceneStarts()[2], 0)
    ed.paste(newScene("INT. NEWER ROOM - DAY"))

    assert labels(ed) == ["1", "2", "2.1", "2A", "3", "4", "5"]


def testLockWhenLockedDoesNothing():
    ed = makeLocked()
    ed.cmd("undo")
    ed.cmd("redo")

    ed.lockScenes()
    ed.cmd("undo")

    # the second lock added no undo step, so this undid the first one
    assert not ed.sp.hasSceneLocks()


def testSaveLoad():
    ed = makeLocked()
    ed.gotoPos(ed.sp.getSceneStarts()[2], 0)
    ed.paste(newScene("INT. NEW ROOM - DAY"))

    data = ed.save().decode("UTF-8")
    assert data.count("#Scene-Lock ") == 5
    assert "#Scene-Lock 3\n.\\INT. ROOM 3 - DAY" in data

    ed2 = u.loadStringEditor(data)
    assert labels(ed2) == labels(ed) == ["1", "2", "2A", "3", "4", "5"]


def testLoadIgnoresInvalidLocks():
    ed = u.loadStringEditor(
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
    assert labels(ed) == ["A7", "7", "7A"]

    data = ed.save().decode("UTF-8")
    assert "2-3" not in data
    assert "#Scene-Lock 4" not in data


def testDeepcopyKeepsLocks():
    ed = makeLocked()
    ed2 = copy.deepcopy(ed)

    assert labels(ed2) == labels(ed)
    assert ed2.sp.hasSceneLocks()


def testOutlineAndLocations():
    ed = makeLocked()
    ed.gotoPos(ed.sp.getSceneStarts()[1], 0)
    ed.paste(newScene("INT. NEW ROOM - DAY"))

    expected = ["1", "1A", "2", "3", "4", "5"]

    assert [it.sceneNr for it in ed.sp.getOutline()] == expected
    assert [nr for nr, line in ed.sp.getSceneLocations()] == expected
    assert ed.sp.getSceneNumber(ed.sp.getSceneStarts()[1] + 1) == "1A"


def testPDFShowsNumbers():
    ed = makeLocked()
    ed.gotoPos(ed.sp.getSceneStarts()[1], 0)
    ed.paste(newScene("INT. NEW ROOM - DAY"))
    ed.sp.cfg.pdfShowSceneNumbers = True
    ed.sp.paginate()

    texts = [
        op.text for pg in render.generatePML(ed.sp).pages for op in pg.ops if hasattr(op, "text")
    ]

    # each number is printed on both sides of its heading
    assert texts.count("1A") == 2
    assert texts.count("5") == 2


def testMCPListAndReplace(tmp_path):
    path = str(tmp_path / "locked.trelby")
    ed = makeLocked()
    ed.gotoPos(ed.sp.getSceneStarts()[1], 0)
    ed.paste(newScene("INT. NEW ROOM - DAY"))

    with open(path, "wb") as f:
        f.write(ed.save())

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
