import os
import shutil

import pytest

import tests.u as u
import trelby.mcptools as m

D = m.FileDoc

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
    return m.listScenes(D(path))["revision"]


def headings(res):
    return [s["heading"] for s in res["scenes"]]


def elems(path, index):
    return m.readScenes(D(path), index)["scenes"][0]["elements"]


def testListScenes(small):
    scenes = m.listScenes(D(small))["scenes"]

    assert [s["index"] for s in scenes] == [0, 1, 2, 3, 4]
    assert scenes[0]["type"] == "opening"
    assert scenes[1]["heading"] == "INT. KITCHEN - DAY"
    assert scenes[1]["scene_number"] == "1"
    assert scenes[1]["color"] == "#ffb3b3"
    assert scenes[1]["summary"] == "Mary cooks."
    assert scenes[3]["type"] == "act break"
    assert "scene_number" not in scenes[3]
    assert scenes[4]["scene_number"] == "3"


def testNoOpening(sample):
    scenes = m.listScenes(D(sample))["scenes"]

    assert scenes[0]["index"] == 1
    assert len(scenes) == 13


def testReadScenes(small):
    res = m.readScenes(D(small), 0, 1)

    assert res["scenes"][0]["elements"] == [{"type": "transition", "text": "Fade in:"}]
    assert res["scenes"][1]["elements"] == [
        {"type": "scene", "text": "int. kitchen - day", "color": "#ffb3b3"},
        {"type": "action", "text": "Mary cooks."},
        {"type": "character", "text": "MARY"},
        {"type": "dialogue", "text": "Dinner's ready, John!"},
    ]

    with pytest.raises(m.ToolError):
        m.readScenes(D(small), 5)

    with pytest.raises(m.ToolError):
        m.readScenes(D(small), 2, 1)


def testReadJoinsWrappedLines(sample):
    action = elems(sample, 1)[1]

    assert action["type"] == "action"
    assert action["text"].startswith("A blizzard rages. Snow is everywhere")
    assert action["text"].endswith("this kind of weather.")
    assert "\n" not in action["text"]


def testInfo(sample):
    info = m.getInfo(D(sample))

    assert info["title_page"][0] == "THE KOALA INCIDENT"
    assert info["scenes"] == 13
    assert info["pages"] == 4
    assert info["words"] > 0
    assert info["characters"] > 0
    assert not info["has_world_building"]


def testListCharacters(small):
    chars = m.listCharacters(D(small))["characters"]

    assert [c["name"] for c in chars] == ["JOHN", "MARY"]
    assert chars[0]["scenes"] == [4]
    assert chars[1]["speeches"] == 1


def testSearch(small):
    matches = m.search(D(small), "mary")["matches"]

    assert [(x["index"], x["type"]) for x in matches] == [
        (1, "action"),
        (1, "character"),
        (2, "action"),
    ]
    assert len(m.search(D(small), "mary", True)["matches"]) == 0

    with pytest.raises(m.ToolError):
        m.search(D(small), "")


def testPaths(small, tmp_path):
    with pytest.raises(m.ToolError, match="absolute"):
        m.listScenes(D("small.trelby"))

    with pytest.raises(m.ToolError, match="not found"):
        m.listScenes(D(str(tmp_path / "missing.trelby")))

    with pytest.raises(m.ToolError, match="Not a .trelby"):
        m.listScenes(D(str(tmp_path / "small.txt")))


def testStaleRevision(small):
    old = rev(small)
    m.deleteScene(D(small), old, 2)

    with open(small, "rb") as f:
        before = f.read()

    with pytest.raises(m.ToolError, match="changed"):
        m.deleteScene(D(small), old, 1)

    with open(small, "rb") as f:
        assert f.read() == before


def testReplaceScene(small):
    res = m.replaceScene(
        D(small),
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
    m.replaceScene(D(small), rev(small), 1, [{"type": "scene", "text": "INT. HALL"}])
    assert elems(small, 1)[0]["color"] == "#ffb3b3"

    m.replaceScene(
        D(small),
        rev(small),
        1,
        [{"type": "scene", "text": "INT. HALL", "color": None}],
    )
    assert "color" not in elems(small, 1)[0]


def testReplaceNeedsHeading(small):
    with pytest.raises(m.ToolError, match="first element"):
        m.replaceScene(D(small), rev(small), 1, [{"type": "action", "text": "x"}])

    # but the opening can be anything
    m.replaceScene(D(small), rev(small), 0, [{"type": "action", "text": "Dark."}])
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
        [{"type": "scene", "text": "x"}, {"type": "shot", "text": "x", "centered": True}],
    ):
        with pytest.raises(m.ToolError):
            m.replaceScene(D(small), r, 1, bad)

    assert rev(small) == r


def testCentered(small):
    m.replaceScene(
        D(small),
        rev(small),
        1,
        [
            {"type": "scene", "text": "int. kitchen - day"},
            {"type": "action", "text": "THE END\nfor now", "centered": True},
            {"type": "action", "text": "Credits roll."},
        ],
    )

    assert elems(small, 1)[1:] == [
        {"type": "action", "text": "THE END\nfor now", "centered": True},
        {"type": "action", "text": "Credits roll."},
    ]


def testTypeNames():
    assert m.typeFromName("Act_Break") == m.ACTBREAK
    assert m.typeFromName("paren") == m.typeFromName("parenthetical")


def testInsertScenes(small):
    new = [
        {"type": "scene", "text": "INT. CAVE - NIGHT"},
        {"type": "action", "text": "Drip."},
        {"type": "scene", "text": "EXT. CAVE - NIGHT"},
    ]

    res = m.insertScenes(D(small), rev(small), 2, new)
    assert headings(res)[1:5] == [
        "INT. KITCHEN - DAY",
        "INT. CAVE - NIGHT",
        "EXT. CAVE - NIGHT",
        "EXT. GARDEN - NIGHT",
    ]

    res = m.insertScenes(
        D(small),
        rev(small),
        len(res["scenes"]),
        [{"type": "scene", "text": "THE END"}],
    )
    assert headings(res)[-1] == "THE END"

    with pytest.raises(m.ToolError, match="out of range"):
        m.insertScenes(D(small), rev(small), 0, new)


def testDeleteScene(small):
    res = m.deleteScene(D(small), rev(small), 1)

    assert headings(res)[1] == "EXT. GARDEN - NIGHT"

    res = m.deleteScene(D(small), rev(small), 0)
    assert res["scenes"][0]["index"] == 1

    with pytest.raises(m.ToolError, match="nothing before"):
        m.deleteScene(D(small), rev(small), 0)


def testMoveScene(small):
    res = m.moveScene(D(small), rev(small), 1, 4)

    assert headings(res)[1:] == [
        "EXT. GARDEN - NIGHT",
        "ACT TWO",
        "INT. CAR - DAY",
        "INT. KITCHEN - DAY",
    ]
    assert res["scenes"][4]["color"] == "#ffb3b3"

    for bad in ((1, 1), (0, 2), (1, 5)):
        with pytest.raises(m.ToolError):
            m.moveScene(D(small), rev(small), *bad)


def testRenameCharacter(small):
    res = m.renameCharacter(D(small), rev(small), "john", "Jack")

    assert res["cues_renamed"] == 1
    assert res["mentions_renamed"] == 2
    assert elems(small, 4)[1]["text"] == "JACK (V.O.)"
    assert elems(small, 2)[1]["text"] == "Jack waits for Mary."

    with pytest.raises(m.ToolError, match="not found"):
        m.renameCharacter(D(small), rev(small), "Nobody", "Somebody")


def testWorldBuilding(small):
    res = m.getWorldBuilding(D(small))
    assert res["text"] == ""
    assert res["revision"] == rev(small)

    text = "The town floods every spring.\r\nMagic costs memories."
    res = m.setWorldBuilding(D(small), rev(small), text)
    assert res["revision"] == rev(small)
    assert os.path.exists(small + ".bak")

    assert m.getWorldBuilding(D(small))["text"] == (
        "The town floods every spring.\nMagic costs memories."
    )
    assert m.getInfo(D(small))["has_world_building"]

    # the scenes are untouched
    assert elems(small, 1)[2]["text"] == "MARY"

    # the old revision is stale now
    with pytest.raises(m.ToolError, match="changed"):
        m.setWorldBuilding(D(small), res["revision"][::-1], "x")

    with pytest.raises(m.ToolError, match="string"):
        m.setWorldBuilding(D(small), rev(small), None)

    # setting the same text again changes nothing
    os.remove(small + ".bak")
    r = rev(small)
    assert m.setWorldBuilding(D(small), r, m.getWorldBuilding(D(small))["text"])[
        "revision"
    ] == r
    assert not os.path.exists(small + ".bak")


def testCharacterProfiles(small):
    assert m.getCharacterProfiles(D(small))["profiles"] == []
    assert m.getInfo(D(small))["character_profiles"] == 0

    res = m.setCharacterProfile(D(small), rev(small), "mary (o.s.)", "A cook.\r\nKind.")
    assert res["created"]
    assert res["profile"] == {
        "name": "MARY",
        "notes": "A cook.\nKind.",
        "photos": 0,
        "in_script": True,
    }
    assert res["revision"] == rev(small)

    res = m.setCharacterProfile(D(small), rev(small), "Alice", "Never seen.")
    assert res["created"]
    assert not res["profile"]["in_script"]

    res = m.setCharacterProfile(D(small), rev(small), "Mary", "A chef.")
    assert not res["created"]

    profs = m.getCharacterProfiles(D(small))["profiles"]
    assert [(p["name"], p["notes"]) for p in profs] == [
        ("ALICE", "Never seen."),
        ("MARY", "A chef."),
    ]
    assert m.getCharacterProfiles(D(small), "mary")["profiles"][0]["notes"] == (
        "A chef."
    )
    assert m.listCharacters(D(small))["characters"][1]["has_profile"]
    assert m.getInfo(D(small))["character_profiles"] == 2

    with pytest.raises(m.ToolError, match="no profile"):
        m.getCharacterProfiles(D(small), "John")

    with pytest.raises(m.ToolError, match="empty"):
        m.setCharacterProfile(D(small), rev(small), " (V.O.)", "x")

    with pytest.raises(m.ToolError, match="changed"):
        m.setCharacterProfile(D(small), res["revision"][::-1], "Mary", "x")

    res = m.deleteCharacterProfile(D(small), rev(small), "alice")
    assert res["deleted"] == "ALICE"
    assert [p["name"] for p in m.getCharacterProfiles(D(small))["profiles"]] == [
        "MARY"
    ]

    with pytest.raises(m.ToolError, match="no profile"):
        m.deleteCharacterProfile(D(small), rev(small), "alice")

    # the scenes are untouched
    assert elems(small, 1)[2]["text"] == "MARY"


def testCharacterProfileKeepsPhotos(small):
    m.setCharacterProfile(D(small), rev(small), "Mary", "A cook.")

    with open(small, encoding="UTF-8") as f:
        s = f.read()

    with open(small, "w", encoding="UTF-8") as f:
        f.write(
            s.replace(
                "Profile/1/Notes",
                "Profile/1/Photos:1\nProfile/1/Photo/1:AAAA\nProfile/1/Notes",
            )
        )

    m.setCharacterProfile(D(small), rev(small), "Mary", "A chef.")
    prof = m.getCharacterProfiles(D(small))["profiles"][0]

    assert prof["notes"] == "A chef."
    assert prof["photos"] == 1


def testExport(small, tmp_path):
    text = m.export(D(small), "text")["content"]
    assert "KITCHEN" in text

    assert "<FinalDraft" in m.export(D(small), "fdx")["content"]

    with pytest.raises(m.ToolError, match="output path"):
        m.export(D(small), "pdf")

    with pytest.raises(m.ToolError, match="Unknown format"):
        m.export(D(small), "docx")

    with pytest.raises(m.ToolError):
        m.export(D(small), "text", str(tmp_path / "other.trelby"))

    out = str(tmp_path / "small.pdf")
    m.export(D(small), "pdf", out)

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


# scripts open in the app are edited in memory, with undo


LONG = "A sentence long enough to need wrapping over several lines. " * 4


def live():
    sp = u.loadString("\n".join(SMALL))
    sp.markChanged(False)

    return m.LiveDoc(sp)


def testLiveReplace():
    d = live()
    sp = d.sp

    res = m.replaceScene(
        d,
        m.listScenes(d)["revision"],
        2,
        [
            {"type": "scene", "text": "EXT. GARDEN - DAWN"},
            {"type": "action", "text": LONG + "\nLast line."},
            {"type": "character", "text": "JOHN"},
            {"type": "dialogue", "text": LONG},
        ],
    )
    sp._validate()

    assert headings(res)[2] == "EXT. GARDEN - DAWN"
    assert res["revision"] == m.listScenes(d)["revision"]
    assert m.readScenes(d, 2)["scenes"][0]["elements"][1]["text"] == (
        LONG.strip() + "\nLast line."
    )

    # the cursor is put at the start of the change
    assert m.getInfo(d)["cursor_scene"] == 2
    assert m.getInfo(d)["modified"]

    sp.cmd("undo")
    sp._validate()
    assert headings(m.listScenes(d))[2] == "EXT. GARDEN - NIGHT"

    sp.cmd("redo")
    sp._validate()
    assert headings(m.listScenes(d))[2] == "EXT. GARDEN - DAWN"


def testLiveOwnUndo():
    d = live()
    sp = d.sp

    m.moveScene(d, m.listScenes(d)["revision"], 1, 4)
    m.renameCharacter(d, m.listScenes(d)["revision"], "John", "Jack")
    sp._validate()

    assert headings(m.listScenes(d))[4] == "INT. KITCHEN - DAY"
    assert m.search(d, "john")["matches"] == []

    # each edit is one undo step
    sp.cmd("undo")
    assert len(m.search(d, "john")["matches"]) == 3
    assert headings(m.listScenes(d))[4] == "INT. KITCHEN - DAY"

    sp.cmd("undo")
    sp._validate()
    assert headings(m.listScenes(d))[1] == "INT. KITCHEN - DAY"


def testLiveDeleteAndInsert():
    d = live()
    sp = d.sp

    m.deleteScene(d, m.listScenes(d)["revision"], 1)
    sp._validate()

    res = m.insertScenes(
        d,
        m.listScenes(d)["revision"],
        len(m.listScenes(d)["scenes"]),
        [{"type": "scene", "text": "INT. END"}, {"type": "action", "text": LONG}],
    )
    sp._validate()
    assert headings(res)[-1] == "INT. END"

    # everything can be deleted, leaving an empty script
    for _ in range(len(res["scenes"]) - 1):
        m.deleteScene(d, m.listScenes(d)["revision"], 1)

    m.deleteScene(d, m.listScenes(d)["revision"], 0)
    sp._validate()
    assert len(sp.lines) == 1


def testLiveStale():
    d = live()
    old = m.listScenes(d)["revision"]

    # typing changes the revision, but moving the cursor doesn't
    d.sp.line = 3
    assert m.listScenes(d)["revision"] == old

    d.sp.cmd("addChar", char="x")
    assert m.listScenes(d)["revision"] != old

    with pytest.raises(m.ToolError, match="changed"):
        m.deleteScene(d, old, 1)


def testLiveFailedEditChangesNothing():
    d = live()
    r = m.listScenes(d)["revision"]

    class Readonly(m.LiveDoc):
        def checkWritable(self):
            raise m.ToolError("busy")

    with pytest.raises(m.ToolError, match="busy"):
        m.deleteScene(Readonly(d.sp), r, 1)

    with pytest.raises(m.ToolError):
        m.replaceScene(d, r, 1, [{"type": "action", "text": "x"}])

    assert m.listScenes(d)["revision"] == r
    assert not d.sp.canUndo()


def testLiveWorldBuilding():
    d = live()
    sp = d.sp
    old = m.listScenes(d)["revision"]

    res = m.setWorldBuilding(d, old, "Two moons.")
    assert sp.worldBuilding.text == "Two moons."
    assert sp.isModified()

    # the revision covers the notes, so scene edits based on the old one
    # are refused
    assert res["revision"] == m.listScenes(d)["revision"] != old

    with pytest.raises(m.ToolError, match="changed"):
        m.deleteScene(d, old, 1)

    m.setWorldBuilding(d, res["revision"], "Three moons.")

    # each change is one undo step
    sp.cmd("undo")
    assert m.getWorldBuilding(d)["text"] == "Two moons."

    sp.cmd("undo")
    assert m.getWorldBuilding(d)["text"] == ""
    assert m.listScenes(d)["revision"] == old
    assert not sp.canUndo()

    sp.cmd("redo")
    assert m.getWorldBuilding(d)["text"] == "Two moons."
    sp._validate()


def testLiveWorldBuildingNotWritable():
    d = live()

    class Readonly(m.LiveDoc):
        def checkWritable(self):
            raise m.ToolError("busy")

    with pytest.raises(m.ToolError, match="busy"):
        m.setWorldBuilding(Readonly(d.sp), m.listScenes(d)["revision"], "x")

    assert d.sp.worldBuilding.text == ""
    assert not d.sp.canUndo()


def testLiveCharacterProfiles():
    d = live()
    sp = d.sp
    old = m.listScenes(d)["revision"]

    res = m.setCharacterProfile(d, old, "Mary", "A cook.")
    assert sp.characterProfiles.get("MARY").notes == "A cook."
    assert sp.isModified()

    # the revision covers the profiles
    assert res["revision"] == m.listScenes(d)["revision"] != old

    with pytest.raises(m.ToolError, match="changed"):
        m.deleteScene(d, old, 1)

    res = m.setCharacterProfile(d, res["revision"], "Mary", "A chef.")
    m.deleteCharacterProfile(d, res["revision"], "Mary")
    assert sp.characterProfiles.profiles == []

    # each change is one undo step
    sp.cmd("undo")
    assert sp.characterProfiles.get("MARY").notes == "A chef."

    sp.cmd("undo")
    assert sp.characterProfiles.get("MARY").notes == "A cook."

    sp.cmd("undo")
    assert sp.characterProfiles.profiles == []
    assert m.listScenes(d)["revision"] == old
    assert not sp.canUndo()

    sp.cmd("redo")
    assert sp.characterProfiles.get("MARY").notes == "A cook."

    # undo history isn't shared with the live profiles
    sp.characterProfiles.get("MARY").notes = "changed"
    sp.cmd("undo")
    sp.cmd("redo")
    assert sp.characterProfiles.get("MARY").notes == "A cook."
    sp._validate()


def testLiveFailedProfileEditChangesNothing():
    d = live()
    r = m.listScenes(d)["revision"]

    with pytest.raises(m.ToolError, match="no profile"):
        m.deleteCharacterProfile(d, r, "Mary")

    assert m.listScenes(d)["revision"] == r
    assert not d.sp.canUndo()


def testLiveRenameUndoesProfile():
    d = live()
    sp = d.sp

    m.setCharacterProfile(d, m.listScenes(d)["revision"], "John", "Waits.")
    m.setCharacterProfile(d, m.listScenes(d)["revision"], "Alice", "Unseen.")

    m.renameCharacter(d, m.listScenes(d)["revision"], "John", "Jack")
    assert sp.characterProfiles.get("JACK").notes == "Waits."

    # a profile of a character that isn't in the script can be renamed too
    m.renameCharacter(d, m.listScenes(d)["revision"], "Alice", "Ann")
    assert sp.characterProfiles.get("ANN").notes == "Unseen."

    # undoing a rename renames the profile back, in the same step as the
    # script
    sp.cmd("undo")
    assert sp.characterProfiles.get("ALICE").notes == "Unseen."
    assert not sp.characterProfiles.get("ANN")

    sp.cmd("undo")
    assert sp.characterProfiles.get("JOHN").notes == "Waits."
    assert not sp.characterProfiles.get("JACK")
    assert len(m.search(d, "john")["matches"]) == 3

    sp.cmd("redo")
    assert sp.characterProfiles.get("JACK").notes == "Waits."
    assert m.search(d, "john")["matches"] == []
    sp._validate()
