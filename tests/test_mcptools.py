import os
import shutil

import pytest

import tests.u as u
import trelby.mcptools as m

# tests for the operations behind the MCP server


SMALL = [
    "#Version 3",
    "#Start-Script ",
    "./Fade in:",
    "#Scene-Color ffb3b3",
    ".\\int. kitchen - day",
    "..Mary cooks.",
    "._MARY",
    ".:Dinner's ready, John!",
    ".\\ext. garden - night",
    "..John waits for Mary.",
    ".@Act two",
    ".\\int. car - day",
    "._JOHN (V.O.)",
    ".:Drive.",
]


@pytest.fixture
def small(tmp_path):
    path = str(tmp_path / "small.trelby")

    with open(path, "w", encoding="UTF-8") as f:
        f.write("\n".join(SMALL) + "\n")

    return path


@pytest.fixture
def sample(tmp_path):
    path = str(tmp_path / "test.trelby")
    shutil.copy(u.fixtureFilePath("test.trelby"), path)

    return path


def rev(path):
    return m.listScenes(path)["revision"]


def headings(res):
    return [s["heading"] for s in res["scenes"]]


def elems(path, index):
    return m.readScenes(path, index)["scenes"][0]["elements"]


def testListScenes(small):
    scenes = m.listScenes(small)["scenes"]

    assert [s["index"] for s in scenes] == [0, 1, 2, 3, 4]
    assert scenes[0]["type"] == "opening"
    assert scenes[1]["heading"] == "INT. KITCHEN - DAY"
    assert scenes[1]["scene_number"] == 1
    assert scenes[1]["color"] == "#ffb3b3"
    assert scenes[1]["summary"] == "Mary cooks."
    assert scenes[3]["type"] == "act break"
    assert "scene_number" not in scenes[3]
    assert scenes[4]["scene_number"] == 3


def testNoOpening(sample):
    scenes = m.listScenes(sample)["scenes"]

    assert scenes[0]["index"] == 1
    assert len(scenes) == 13


def testReadScenes(small):
    res = m.readScenes(small, 0, 1)

    assert res["scenes"][0]["elements"] == [{"type": "transition", "text": "Fade in:"}]
    assert res["scenes"][1]["elements"] == [
        {"type": "scene", "text": "int. kitchen - day", "color": "#ffb3b3"},
        {"type": "action", "text": "Mary cooks."},
        {"type": "character", "text": "MARY"},
        {"type": "dialogue", "text": "Dinner's ready, John!"},
    ]

    with pytest.raises(m.ToolError):
        m.readScenes(small, 5)

    with pytest.raises(m.ToolError):
        m.readScenes(small, 2, 1)


def testReadJoinsWrappedLines(sample):
    action = elems(sample, 1)[1]

    assert action["type"] == "action"
    assert action["text"].startswith("A blizzard rages. Snow is everywhere")
    assert action["text"].endswith("this kind of weather.")
    assert "\n" not in action["text"]


def testInfo(sample):
    info = m.getInfo(sample)

    assert info["title_page"][0] == "THE KOALA INCIDENT"
    assert info["scenes"] == 13
    assert info["pages"] == 4
    assert info["words"] > 0
    assert info["characters"] > 0


def testListCharacters(small):
    chars = m.listCharacters(small)["characters"]

    assert [c["name"] for c in chars] == ["JOHN", "MARY"]
    assert chars[0]["scenes"] == [4]
    assert chars[1]["speeches"] == 1


def testSearch(small):
    matches = m.search(small, "mary")["matches"]

    assert [(x["index"], x["type"]) for x in matches] == [
        (1, "action"),
        (1, "character"),
        (2, "action"),
    ]
    assert len(m.search(small, "mary", True)["matches"]) == 0

    with pytest.raises(m.ToolError):
        m.search(small, "")


def testPaths(small, tmp_path):
    with pytest.raises(m.ToolError, match="absolute"):
        m.listScenes("small.trelby")

    with pytest.raises(m.ToolError, match="not found"):
        m.listScenes(str(tmp_path / "missing.trelby"))

    with pytest.raises(m.ToolError, match="Not a .trelby"):
        m.listScenes(str(tmp_path / "small.txt"))


def testStaleRevision(small):
    old = rev(small)
    m.deleteScene(small, old, 2)

    with open(small, "rb") as f:
        before = f.read()

    with pytest.raises(m.ToolError, match="changed"):
        m.deleteScene(small, old, 1)

    with open(small, "rb") as f:
        assert f.read() == before


def testReplaceScene(small):
    res = m.replaceScene(
        small,
        rev(small),
        2,
        [
            {"type": "scene", "text": "EXT. GARDEN - DAWN"},
            {"type": "action", "text": "John is gone.\nOnly his hat remains."},
        ],
    )

    assert headings(res)[2] == "EXT. GARDEN - DAWN"
    assert res["revision"] == rev(small)
    assert elems(small, 2)[1]["text"] == "John is gone.\nOnly his hat remains."
    assert os.path.exists(small + ".bak")


def testReplaceKeepsColor(small):
    m.replaceScene(small, rev(small), 1, [{"type": "scene", "text": "INT. HALL"}])
    assert elems(small, 1)[0]["color"] == "#ffb3b3"

    m.replaceScene(
        small, rev(small), 1, [{"type": "scene", "text": "INT. HALL", "color": None}]
    )
    assert "color" not in elems(small, 1)[0]


def testReplaceNeedsHeading(small):
    with pytest.raises(m.ToolError, match="first element"):
        m.replaceScene(small, rev(small), 1, [{"type": "action", "text": "x"}])

    # but the opening can be anything
    m.replaceScene(small, rev(small), 0, [{"type": "action", "text": "Dark."}])
    assert elems(small, 0) == [{"type": "action", "text": "Dark."}]


def testBadElements(small):
    r = rev(small)

    for bad in (
        [],
        [{"text": "no type"}],
        [{"type": "bogus", "text": "x"}],
        [{"type": "scene", "text": "x", "color": "red"}],
        [{"type": "scene", "text": "x"}, {"type": "action", "text": "x", "color": "#ff0000"}],
        [{"type": "scene", "text": "x"}, {"type": "dialogue", "text": "x", "dual": True}],
    ):
        with pytest.raises(m.ToolError):
            m.replaceScene(small, r, 1, bad)

    assert rev(small) == r


def testTypeNames():
    assert m.typeFromName("Act_Break") == m.ACTBREAK
    assert m.typeFromName("paren") == m.typeFromName("parenthetical")


def testInsertScenes(small):
    new = [
        {"type": "scene", "text": "INT. CAVE - NIGHT"},
        {"type": "action", "text": "Drip."},
        {"type": "scene", "text": "EXT. CAVE - NIGHT"},
    ]

    res = m.insertScenes(small, rev(small), 2, new)
    assert headings(res)[1:5] == [
        "INT. KITCHEN - DAY",
        "INT. CAVE - NIGHT",
        "EXT. CAVE - NIGHT",
        "EXT. GARDEN - NIGHT",
    ]

    res = m.insertScenes(
        small, rev(small), len(res["scenes"]), [{"type": "scene", "text": "THE END"}]
    )
    assert headings(res)[-1] == "THE END"

    with pytest.raises(m.ToolError, match="out of range"):
        m.insertScenes(small, rev(small), 0, new)


def testDeleteScene(small):
    res = m.deleteScene(small, rev(small), 1)

    assert headings(res)[1] == "EXT. GARDEN - NIGHT"

    res = m.deleteScene(small, rev(small), 0)
    assert res["scenes"][0]["index"] == 1

    with pytest.raises(m.ToolError, match="nothing before"):
        m.deleteScene(small, rev(small), 0)


def testMoveScene(small):
    res = m.moveScene(small, rev(small), 1, 4)

    assert headings(res)[1:] == [
        "EXT. GARDEN - NIGHT",
        "ACT TWO",
        "INT. CAR - DAY",
        "INT. KITCHEN - DAY",
    ]
    assert res["scenes"][4]["color"] == "#ffb3b3"

    for bad in ((1, 1), (0, 2), (1, 5)):
        with pytest.raises(m.ToolError):
            m.moveScene(small, rev(small), *bad)


def testRenameCharacter(small):
    res = m.renameCharacter(small, rev(small), "john", "Jack")

    assert res["cues_renamed"] == 1
    assert res["mentions_renamed"] == 2
    assert elems(small, 4)[1]["text"] == "JACK (V.O.)"
    assert elems(small, 2)[1]["text"] == "Jack waits for Mary."

    with pytest.raises(m.ToolError, match="not found"):
        m.renameCharacter(small, rev(small), "Nobody", "Somebody")


def testExport(small, tmp_path):
    text = m.export(small, "text")["content"]
    assert "KITCHEN" in text

    assert "<FinalDraft" in m.export(small, "fdx")["content"]

    with pytest.raises(m.ToolError, match="output path"):
        m.export(small, "pdf")

    with pytest.raises(m.ToolError, match="Unknown format"):
        m.export(small, "docx")

    with pytest.raises(m.ToolError):
        m.export(small, "text", str(tmp_path / "other.trelby"))

    out = str(tmp_path / "small.pdf")
    m.export(small, "pdf", out)

    with open(out, "rb") as f:
        assert f.read(4) == b"%PDF"


def testCreateScript(tmp_path):
    path = str(tmp_path / "new.trelby")

    res = m.createScript(
        path,
        [
            {"type": "transition", "text": "FADE IN:"},
            {"type": "scene", "text": "EXT. BEACH - DAY"},
            {"type": "action", "text": "Waves."},
        ],
    )

    assert headings(res) == ["(material before the first scene)", "EXT. BEACH - DAY"]
    assert elems(path, 1)[1] == {"type": "action", "text": "Waves."}
    assert not os.path.exists(path + ".bak")

    with pytest.raises(m.ToolError, match="already exists"):
        m.createScript(path, [{"type": "scene", "text": "x"}])
