import tests.u as u
import trelby.translations as translations

_ = translations.trelby_translations_load()

# tests for scene colors in the outline view


def loadLines(lines):
    return u.loadStringEditor("\n".join(["#Version 3", "#Start-Script "] + lines))


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


def colors(ed):
    return [it.color for it in ed.sp.getOutline()]


def saved(ed):
    return ed.save().decode("UTF-8")


def testLoad():
    ed = loadSmall()

    # stored lower-case
    assert colors(ed) == ["ffb3b3", None, "c5f0b8", None]


def testSaveRoundTrip():
    ed = loadSmall()
    s = saved(ed)

    assert "#Scene-Color ffb3b3\n.\\int. kitchen - day\n" in s
    assert "#Scene-Color c5f0b8\n.@Act two\n" in s
    assert s.count("#Scene-Color") == 2

    assert colors(u.loadStringEditor(s)) == colors(ed)


def testInvalidIgnored():
    ed = loadLines(
        [
            "#Scene-Color nothex",
            ".\\int. kitchen - day",
            # not on a scene heading
            "#Scene-Color ffb3b3",
            "..Mary cooks.",
        ]
    )

    assert colors(ed) == [None]
    assert "#Scene-Color" not in saved(ed)


def testSetSceneColor():
    ed = loadSmall()

    # any line inside the scene works
    assert ed.setSceneColor(4, "B8D4FF")
    assert colors(ed) == ["ffb3b3", "b8d4ff", "c5f0b8", None]
    assert ed.sp.isModified()

    assert ed.setSceneColor(1, None)
    assert colors(ed) == [None, "b8d4ff", "c5f0b8", None]


def testSetSceneColorNoChange():
    ed = loadSmall()

    assert not ed.setSceneColor(1, "ffb3b3")
    # before the first scene
    assert not ed.setSceneColor(0, "ffb3b3")
    assert not ed.undoHistory.canUndo()


def testSetSceneColorUndoRedo():
    ed = loadSmall()

    ed.setSceneColor(3, "b8d4ff")
    ed.cmd("undo")
    assert colors(ed) == ["ffb3b3", None, "c5f0b8", None]

    ed.cmd("redo")
    assert colors(ed) == ["ffb3b3", "b8d4ff", "c5f0b8", None]


def testColorMovesWithScene():
    ed = loadSmall()

    assert ed.moveSceneTo(1, 3)
    assert colors(ed) == [None, "c5f0b8", None, "ffb3b3"]

    ed.cmd("undo")
    assert colors(ed) == ["ffb3b3", None, "c5f0b8", None]


def testColorSurvivesEditingHeading():
    ed = loadSmall()

    ed.gotoPos(1, len(ed.sp.lines[1].text))
    ed.cmdChars(" and a very long description of the place" * 3)

    assert len(ed.sp.getOutline()[0].heading) > 60
    assert colors(ed)[0] == "ffb3b3"
    ed._validate()


def testColorIgnoredWhenNotSceneHeading():
    ed = loadSmall()

    # turn the colored scene heading into an action
    ed.gotoPos(1, 0)
    ed.convertTypeTo(ed.sp.lines[2].lt, True)

    assert "#Scene-Color ffb3b3" not in saved(ed)


def testCopyPasteKeepsColor():
    ed = loadSmall()

    # copy the colored scene heading and paste it as a new element at the
    # end of the script
    ed.gotoPos(1, 0)
    ed.cmd("setMark")
    ed.gotoPos(1, len(ed.sp.lines[1].text))
    cd = ed.getSelectedAsCD(False)

    ed.clearMark()
    ed.gotoPos(len(ed.sp.lines) - 1, len(ed.sp.lines[-1].text))
    ed.splitElement(ed.sp.lines[1].lt)
    ed.paste(cd.lines)

    assert colors(ed) == ["ffb3b3", None, "c5f0b8", None, "ffb3b3"]
