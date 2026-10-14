import random

import tests.u as u
import trelby.characterprofiles as characterprofiles
import trelby.namearray as namearray
import trelby.screenplay as screenplay
import trelby.translations as translations

_ = translations.trelby_translations_load()

# test characterprofiles.CharacterProfiles and its saving/loading as part
# of a script


def test_escape():
    for s in [
        "",
        "plain",
        "two\nlines",
        "back\\slash",
        "\\n is not a newline",
        "\\u0041 is not an A",
        "tab\there",
        "crlf\r\nand line separator",
        "unicode: äöü 日本語",
    ]:
        esc = characterprofiles.escapeText(s)

        assert esc.splitlines() == ([esc] if esc else [])
        assert characterprofiles.unescapeText(esc) == s


def test_normalizeName():
    n = characterprofiles.normalizeName

    assert n("bob") == "BOB"
    assert n("Bob (V.O.)") == "BOB"
    assert n("  mary   jane (cont'd)") == "MARY JANE"


def makeProfiles():
    profs = characterprofiles.CharacterProfiles()

    p = characterprofiles.CharacterProfile("JOHN")
    p.role = "Protagonist"
    p.age = "42"
    p.background = "Grew up in Ohio.\n\nMoved to \\ New York."
    p.notes = "Line one\nLine two: with a colon"
    p.photos = [b"\x89PNG fake data \x00\xff", b"\xff\xd8 more fake data"]
    profs.profiles.append(p)

    p = characterprofiles.CharacterProfile("MARY")
    p.gender = "Female"
    profs.profiles.append(p)

    return profs


def checkSame(a, b):
    assert len(a.profiles) == len(b.profiles)

    for pa, pb in zip(a.profiles, b.profiles):
        for attr, _key in characterprofiles.TEXT_FIELDS:
            assert getattr(pa, attr) == getattr(pb, attr)

        assert pa.photos == pb.photos
        assert pa.extra == pb.extra


def test_saveLoad():
    profs = makeProfiles()

    profs2 = characterprofiles.CharacterProfiles()
    profs2.load(profs.save())

    checkSame(profs, profs2)


def test_get():
    profs = makeProfiles()

    assert profs.get("john").age == "42"
    assert profs.get("JOHN (O.S.)").age == "42"
    assert profs.get("nobody") is None


def test_unknownKeysKept():
    profs = characterprofiles.CharacterProfiles()
    profs.load("Profiles:1\nProfile/1/Name:BOB\nProfile/1/Height:6 ft\n")

    assert profs.profiles[0].extra == {"Height": "6 ft"}
    assert "Profile/1/Height:6 ft\n" in profs.save()


def test_badData():
    profs = characterprofiles.CharacterProfiles()
    profs.load(
        "Profiles:3\n"
        "Profile/1/Name:BOB\n"
        "Profile/1/Photos:2\n"
        "Profile/1/Photo/1:not base64!!\n"
        "Profile/1/Photo/2:aGVsbG8=\n"
        "Profile/2/Age:12\n"
        "garbage\n"
    )

    # profile 2 has no name, profile 3 doesn't exist
    assert len(profs.profiles) == 1
    assert profs.profiles[0].photos == [b"hello"]


def test_scriptRoundTrip():
    u.init()

    sp = u.load()
    sp.characterProfiles = makeProfiles()

    data = sp.save().decode("UTF-8")
    lines = data.splitlines()

    # the section must come before the script and its lines must look like
    # unknown, non-config lines to older versions, which then skip them
    start = lines.index("#Begin-Character-Profiles ")
    end = lines.index("#End-Character-Profiles ")
    assert start < end < lines.index("#Start-Script ")

    for line in lines[start + 1 : end]:
        assert len(line) >= 2
        assert not line.startswith("#")

    sp2 = u.loadString(data)
    checkSame(sp.characterProfiles, sp2.characterProfiles)

    # saving again gives the same file
    assert sp2.save().decode("UTF-8") == data


def test_noProfilesNoSection():
    sp = u.load()

    assert "Character-Profiles" not in sp.save().decode("UTF-8")
    assert sp.characterProfiles.profiles == []


def test_deepcopy():
    import copy

    sp = u.load()
    sp.characterProfiles = makeProfiles()

    sp2 = copy.deepcopy(sp)
    sp2.characterProfiles.profiles[0].age = "1"

    assert sp.characterProfiles.profiles[0].age == "42"


def test_randomNames():
    arr = namearray.NameArray()
    arr.append("Anna", "English", "F")
    arr.append("Bob", "English", "M")
    arr.append("Anna", "German", "F")
    arr.append("Hans", "German", "M")
    arr.append("Greta", "German", "F")

    rng = random.Random(1)
    german = {arr.typeId["German"]}

    assert sorted(arr.randomNames(10, german, None, rng)) == ["Anna", "Greta", "Hans"]
    assert sorted(arr.randomNames(10, german, 0, rng)) == ["Anna", "Greta"]
    assert sorted(arr.randomNames(10, None, 1, rng)) == ["Bob", "Hans"]

    # "Anna" is listed twice but only returned once
    assert sorted(arr.randomNames(10, None, 0, rng)) == ["Anna", "Greta"]

    assert len(arr.randomNames(2, None, None, rng)) == 2


def loadRenameScript():
    return u.loadString(
        "\n".join(
            [
                "#Version 3",
                "#Start-Script ",
                ".\\INT. BOB'S HOUSE - DAY",
                "..Bob and Mary Jane enter. MARY sits. Bobby waves.",
                "._BOB",
                ".:Hi, Mary.",
                "._MARY JANE (V.O.)",
                ".:Bob's here.",
                "._mary",
                ".:Hello.",
            ]
        )
    )


def texts(sp):
    return [ln.text for ln in sp.lines]


def test_rename():
    sp = loadRenameScript()

    assert sp.renameCharacters(
        {"BOB": "ROBERT", "MARY JANE": "MARY-ANNE O'NEIL"}
    ) == (2, 4)

    t = " ".join(texts(sp))

    assert "INT. ROBERT'S HOUSE - DAY" in t
    assert "Robert and Mary-Anne O'Neil enter. MARY sits. Bobby waves." in t
    assert "MARY-ANNE O'NEIL (V.O.)" in t
    assert "Robert's here." in t
    assert "Hi, Mary." in t
    assert sp.isModified()

    names = sorted(sp.getCharacterNames())
    assert names == ["mary", "mary-anne o'neil (v.o.)", "robert"]


def test_renameKeepsOtherNames():
    sp = loadRenameScript()

    # "Mary" in "Mary Jane" is part of another character's name
    assert sp.renameCharacters({"MARY": "SUE"}) == (1, 2)

    t = " ".join(texts(sp))

    assert "Bob and Mary Jane enter. SUE sits." in t
    assert "Hi, Sue." in t
    assert "MARY JANE (V.O.)" in t


def test_renameSwap():
    sp = loadRenameScript()

    assert sp.renameCharacters({"BOB": "MARY", "MARY": "BOB"}) == (2, 5)
    assert sorted(sp.getCharacterNames()) == ["bob", "mary", "mary jane (v.o.)"]
    assert texts(sp)[1] == "Mary and Mary Jane enter. BOB sits. Bobby waves."
    assert texts(sp)[2] == "MARY"
    assert texts(sp)[3] == "Hi, Bob."
    assert texts(sp)[6] == "BOB"


def test_renameNothing():
    sp = loadRenameScript()

    assert sp.renameCharacters({"NOBODY": "SOMEBODY"}) == (0, 0)
    assert sp.renameCharacters({"BOB": "BOB"}) == (0, 0)
    assert not sp.canUndo()


def test_renameUndo():
    sp = loadRenameScript()
    before = texts(sp)

    sp.renameCharacters({"BOB": "ROBERT"})
    assert texts(sp) != before

    sp.undoCmd(None)
    assert texts(sp) == before

    sp.redoCmd(None)
    assert "ROBERT" in texts(sp)


def test_renameRewraps():
    sp = loadRenameScript()

    sp.renameCharacters({"BOB": "BARTHOLOMEW-MAXIMILIAN " * 3})

    # the action line got too long and was wrapped
    width = sp.cfg.getType(screenplay.ACTION).width
    assert all(len(ln.text) <= width for ln in sp.lines)
