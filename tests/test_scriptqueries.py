import tests.u as u
import trelby.screenplay as scr
import trelby.translations as translations
import trelby.util as util

_ = translations.trelby_translations_load()

# the queries the editor's menus and dialogs use: which character to show
# first in the character profiles, the element type in the right-click
# menu, whether to warn about exporting an empty script, and which menu
# items are enabled


def loadEditor():
    return u.loadStringEditor(
        "\n".join(
            [
                "#Version 3",
                "#Start-Script ",
                ".\\INT. KITCHEN - DAY",
                "..Bob opens the fridge.",
                "._Bob",
                ".((sadly)",
                ".:Empty, as always. Nothing to eat in this house, nothing at all.",
                "..He sits.",
                ".%Note",
            ]
        )
    )


def testLoadedTypes():
    ed = loadEditor()

    # the dialogue is wrapped onto two lines
    assert [ln.lt for ln in ed.sp.lines] == [
        scr.SCENE,
        scr.ACTION,
        scr.CHARACTER,
        scr.PAREN,
        scr.DIALOGUE,
        scr.DIALOGUE,
        scr.ACTION,
    ]

    # the note element is a note on the action before it
    assert [n.text for n in ed.sp.lines[6].notes] == ["Note"]


def testGetCharacterAt():
    sp = loadEditor().sp

    assert [sp.getCharacterAt(i) for i in range(len(sp.lines))] == [
        None,
        None,
        "Bob",
        "Bob",
        "Bob",
        "Bob",
        None,
    ]


def testGetCharacterAtFirstLine():
    ed = u.newEditor()
    ed.sp.lines[0].lt = scr.DIALOGUE

    assert ed.sp.getCharacterAt(0) is None

    ed.sp.lines[0].lt = scr.CHARACTER
    ed.sp.lines[0].text = "Ann"
    assert ed.sp.getCharacterAt(0) == "Ann"


def testGetSelectionType():
    ed = loadEditor()

    ed.line = 4
    assert ed.getSelectionType() == scr.DIALOGUE

    # both lines of the speech
    ed.setMark(5, 0)
    assert ed.getSelectionType() == scr.DIALOGUE

    ed.setMark(3, 0)
    assert ed.getSelectionType() is None

    ed.clearMark()
    ed.line = 0
    assert ed.getSelectionType() == scr.SCENE


def testIsEmpty():
    ed = u.newEditor()
    assert ed.sp.isEmpty()

    ed.sp.lines[0].text = "  "
    assert ed.sp.isEmpty()

    ed.sp.lines[0].text = " a"
    assert not ed.sp.isEmpty()


def testHasScenes():
    assert loadEditor().sp.hasScenes()

    ed = u.newEditor()
    ed.sp.lines[0].lt = scr.ACTION
    assert not ed.sp.hasScenes()


# unlocking scene numbers also removes locks that aren't valid (here, one
# on an action line), so the menu item is enabled for them
def testHasAnySceneLock():
    sp = loadEditor().sp
    assert not sp.hasAnySceneLock()

    sp.lines[1].sceneLock = "5"
    assert sp.hasAnySceneLock()
    assert not sp.hasSceneLocks()

    sp.lines[0].sceneLock = "5"
    assert sp.hasSceneLocks()


def testUniqueName():
    assert util.uniqueName("a", []) == "a"
    assert util.uniqueName("a", ["b"]) == "a"
    assert util.uniqueName("a", ["a"]) == "a-2"
    assert util.uniqueName("a", ["a", "a-2", "a-3"]) == "a-4"
    assert util.uniqueName("a", ["a-2"]) == "a"
