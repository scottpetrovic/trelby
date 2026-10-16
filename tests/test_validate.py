import tests.u as u
import trelby.screenplay as scr
import trelby.translations as translations

_ = translations.trelby_translations_load()

# tests that Screenplay._validate() finds all errors it's supposed to


# helper function that asserts if ed._validate() does not assert
def v(ed):
    try:
        ed._validate()
    except AssertionError:
        return

    assert 0


def testEmpty():
    ed = u.newEditor()
    ed._validate()
    ed.sp.lines = []
    v(ed)


def testCursorPos():
    ed = u.newEditor()

    ed._validate()

    ed.line = -1
    v(ed)

    ed.line = 5
    v(ed)

    ed.line = 0

    ed.column = -1
    v(ed)

    ed.column = 5
    v(ed)

    ed.column = 0

    ed._validate()


def testInvalidChars():
    ed = u.newEditor()
    ed._validate()
    ed.sp.lines[0].text = chr(9)
    v(ed)


def testTooLongLine():
    ed = u.newEditor()
    ed._validate()
    ed.sp.lines[0].text = "a" * 100
    v(ed)


def testElemChangesType():
    ed = u.loadEditor()
    ed._validate()
    ed.sp.lines[1].lt = scr.SCENE
    v(ed)
