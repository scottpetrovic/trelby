import copy

import tests.u as u
import trelby.worldbuilding as worldbuilding

# test worldbuilding.WorldBuilding and its saving/loading as part of a
# script

TEXT = (
    "Physical Environment: a desert planet\n\n"
    "Rules and Systems: magic costs \\ blood\r\nno exceptions end"
)


def test_saveLoad():
    wb = worldbuilding.WorldBuilding()
    wb.text = TEXT

    s = wb.save()
    assert len(s.splitlines()) == 1

    wb2 = worldbuilding.WorldBuilding()
    wb2.load(s)
    assert wb2.text == TEXT
    assert wb2.save() == s


def test_unknownKept():
    wb = worldbuilding.WorldBuilding()
    wb.load("Text:hello\nFuture:value\ngarbage\n")

    assert wb.text == "hello"
    assert wb.extra == {"Future": "value"}
    assert wb.hasInfo()
    assert "Future:value\n" in wb.save()


def test_hasInfo():
    wb = worldbuilding.WorldBuilding()
    assert not wb.hasInfo()

    wb.text = "  \n "
    assert not wb.hasInfo()

    wb.text = "x"
    assert wb.hasInfo()


def test_scriptRoundTrip():
    u.init()

    sp = u.load()
    sp.worldBuilding.text = TEXT

    data = sp.save().decode("UTF-8")
    lines = data.splitlines()

    # the section must come before the script and its lines must look like
    # unknown, non-config lines to older versions, which then skip them
    start = lines.index("#Begin-World-Building ")
    end = lines.index("#End-World-Building ")
    assert start < end < lines.index("#Start-Script ")

    for line in lines[start + 1 : end]:
        assert len(line) >= 2
        assert not line.startswith("#")

    sp2 = u.loadString(data)
    assert sp2.worldBuilding.text == TEXT

    # saving again gives the same file
    assert sp2.save().decode("UTF-8") == data


def test_withCharacterProfiles():
    import trelby.characterprofiles as characterprofiles

    sp = u.load()
    sp.worldBuilding.text = TEXT
    sp.characterProfiles.profiles.append(characterprofiles.CharacterProfile("JOHN"))

    sp2 = u.loadString(sp.save().decode("UTF-8"))
    assert sp2.worldBuilding.text == TEXT
    assert sp2.characterProfiles.profiles[0].name == "JOHN"


def test_emptyNoSection():
    sp = u.load()

    assert "World-Building" not in sp.save().decode("UTF-8")
    assert sp.worldBuilding.text == ""


def test_deepcopy():
    sp = u.load()
    sp.worldBuilding.text = "original"

    sp2 = copy.deepcopy(sp)
    sp2.worldBuilding.text = "changed"

    assert sp.worldBuilding.text == "original"
