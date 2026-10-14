import random

import tests.u as u
import trelby.characterprofiles as characterprofiles
import trelby.namearray as namearray

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
