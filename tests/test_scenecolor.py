import tests.u as u
import trelby.translations as translations

_ = translations.trelby_translations_load()

# tests for scene colors in the outline view


def loadLines(lines):
    return u.loadString("\n".join(["#Version 3", "#Start-Script "] + lines))


def loadSmall():
    return loadLines(
        [
            "./Fade in:",
            "#Scene-Color FFB3B3",
            ".\\int. kitchen - day",
            "..Mary cooks.",
            ".\\ext. garden - night",
            "..John waits.",
            "#Scene-Color c5f0b8",
            ".@Act two",
            ".\\int. car - day",
        ]
    )


def colors(sp):
    return [it.color for it in sp.getOutline()]


def saved(sp):
    return sp.save().decode("UTF-8")


def testLoad():
    sp = loadSmall()

    # stored lower-case
    assert colors(sp) == ["ffb3b3", None, "c5f0b8", None]


def testSaveRoundTrip():
    sp = loadSmall()
    s = saved(sp)

    assert "#Scene-Color ffb3b3\n.\\int. kitchen - day\n" in s
    assert "#Scene-Color c5f0b8\n.@Act two\n" in s
    assert s.count("#Scene-Color") == 2

    assert colors(u.loadString(s)) == colors(sp)


def testInvalidIgnored():
    sp = loadLines(
        [
            "#Scene-Color nothex",
            ".\\int. kitchen - day",
            # not on a scene heading
            "#Scene-Color ffb3b3",
            "..Mary cooks.",
        ]
    )

    assert colors(sp) == [None]
    assert "#Scene-Color" not in saved(sp)


def testSetSceneColor():
    sp = loadSmall()

    # any line inside the scene works
    assert sp.setSceneColor(4, "B8D4FF")
    assert colors(sp) == ["ffb3b3", "b8d4ff", "c5f0b8", None]
    assert sp.isModified()

    assert sp.setSceneColor(1, None)
    assert colors(sp) == [None, "b8d4ff", "c5f0b8", None]


def testSetSceneColorNoChange():
    sp = loadSmall()

    assert not sp.setSceneColor(1, "ffb3b3")
    # before the first scene
    assert not sp.setSceneColor(0, "ffb3b3")
    assert not sp.canUndo()


def testSetSceneColorUndoRedo():
    sp = loadSmall()

    sp.setSceneColor(3, "b8d4ff")
    sp.cmd("undo")
    assert colors(sp) == ["ffb3b3", None, "c5f0b8", None]

    sp.cmd("redo")
    assert colors(sp) == ["ffb3b3", "b8d4ff", "c5f0b8", None]


def testColorMovesWithScene():
    sp = loadSmall()

    assert sp.moveSceneTo(1, 3)
    assert colors(sp) == [None, "c5f0b8", None, "ffb3b3"]

    sp.cmd("undo")
    assert colors(sp) == ["ffb3b3", None, "c5f0b8", None]


def testColorSurvivesEditingHeading():
    sp = loadSmall()

    sp.gotoPos(1, len(sp.lines[1].text))
    sp.cmdChars(" and a very long description of the place" * 3)

    assert len(sp.getOutline()[0].heading) > 60
    assert colors(sp)[0] == "ffb3b3"
    sp._validate()


def testColorIgnoredWhenNotSceneHeading():
    sp = loadSmall()

    # turn the colored scene heading into an action
    sp.gotoPos(1, 0)
    sp.convertTypeTo(sp.lines[2].lt, True)

    assert "#Scene-Color ffb3b3" not in saved(sp)


def testCopyPasteKeepsColor():
    sp = loadSmall()

    # copy the colored scene heading and paste it as a new element at the
    # end of the script
    sp.gotoPos(1, 0)
    sp.cmd("setMark")
    sp.gotoPos(1, len(sp.lines[1].text))
    cd = sp.getSelectedAsCD(False)

    sp.clearMark()
    sp.gotoPos(len(sp.lines) - 1, len(sp.lines[-1].text))
    sp.splitElement(sp.lines[1].lt)
    sp.paste(cd.lines)

    assert colors(sp) == ["ffb3b3", None, "c5f0b8", None, "ffb3b3"]
