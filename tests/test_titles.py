import tests.u as u
import trelby.pdf.pml as pml
import trelby.screenplay.titles as titles
import trelby.translations as translations
import trelby.util as util

translations.trelby_translations_load()
u.init()


def testKindRoundTrip():
    ts = titles.TitleString(["A, B", "C"], 1.5, 20.0, kind=titles.CONTACT)
    s = str(ts)
    assert ",Courier,contact," in s

    ts2 = titles.TitleString([])
    ts2.load(s)
    assert ts2.kind == titles.CONTACT
    assert ts2.items == ["A, B", "C"]


def testLoadOldFormat():
    ts = titles.TitleString([])
    ts.load("0.000000,80.000000,32,cb,Times,,THE KOALA INCIDENT")
    assert ts.kind is None
    assert ts.items == ["THE KOALA INCIDENT"]
    assert ts.isBold and ts.isCentered

    # unknown kinds (e.g. from a newer version) are treated as unknown
    ts.load("0.000000,80.000000,32,cb,Times,whatever,X")
    assert ts.kind is None

    # strings without a kind are saved like before
    assert ",Times,,X" in str(ts)


def testMakeString():
    for kind in titles.KINDS:
        ts = titles.makeString(kind, 215.9, 279.4)
        assert ts.kind == kind
        assert ts.items
        assert 0 <= ts.y < 279.4

    ts = titles.makeString(titles.TITLE, 215.9, 279.4)
    assert ts.isCentered and ts.isBold and (ts.font == pml.COURIER)

    ts = titles.makeString(titles.DRAFT, 215.9, 279.4)
    assert ts.getAlignment() == util.ALIGN_RIGHT
    assert ts.x == 215.9 - titles.EDGE_X


# changing the alignment with the paper width moves x so the string stays
# on the page; without it, x is left alone
def testSetAlignmentKeepsOnPage():
    w = 215.9

    ts = titles.TitleString(["Contact"], 20.0, 200.0, isCentered=False)
    ts.setAlignment(util.ALIGN_RIGHT, w)
    assert ts.isRightJustified and (ts.x == w - 20.0)

    ts.setAlignment(util.ALIGN_LEFT, w)
    assert (ts.getAlignment() == util.ALIGN_LEFT) and (ts.x == 20.0)

    ts.setAlignment(util.ALIGN_CENTER, w)
    assert ts.isCentered and (ts.x == 20.0)

    ts.setAlignment(util.ALIGN_RIGHT, w)
    assert ts.x == w - titles.EDGE_X

    ts.setAlignment(util.ALIGN_CENTER, w)
    ts.setAlignment(util.ALIGN_LEFT, w)
    assert ts.x == titles.EDGE_X

    # same alignment again: x stays where the user put it
    ts.x = 50.0
    ts.setAlignment(util.ALIGN_LEFT, w)
    assert ts.x == 50.0

    ts.setAlignment(util.ALIGN_RIGHT)
    assert ts.isRightJustified and (ts.x == 50.0)


def testGuessKinds():
    sp = u.load()
    t = sp.titles
    t.guessKinds()

    kinds = [(ts.items[0], ts.kind) for ts in t.pages[0]]
    assert kinds == [
        ("THE KOALA INCIDENT", titles.TITLE),
        ("by", titles.BYLINE),
        ("Anonymous Person", titles.AUTHOR),
        ("Sample script for Trelby.", titles.TEXT),
        ("All rights reserved.", titles.COPYRIGHT),
    ]

    # kinds already set aren't changed
    t.pages[0][3].kind = titles.DRAFT
    t.guessKinds()
    assert t.pages[0][3].kind == titles.DRAFT


def testDefaults():
    t = titles.Titles()
    t.addDefaults()
    assert [ts.kind for ts in t.pages[0]] == [
        titles.TITLE,
        titles.BYLINE,
        titles.CONTACT,
    ]


def _page(*specs):
    return [titles.TitleString([text], x, y) for text, x, y in specs]


def testSort():
    t = titles.Titles()
    t.pages = [
        _page(
            ("contact", 15.0, 248.0),
            ("draft", 120.0, 248.0),
            ("title", 0.0, 105.0),
            ("copyright", 15.0, 260.0),
            ("byline", 0.0, 120.0),
            ("left", 15.0, 105.0),
        ),
        _page(("b", 0.0, 50.0), ("a", 0.0, 10.0)),
    ]
    t.sort()

    assert [ts.items[0] for ts in t.pages[0]] == [
        "title",
        "left",
        "byline",
        "contact",
        "draft",
        "copyright",
    ]
    assert [ts.items[0] for ts in t.pages[1]] == ["a", "b"]


def testSortIsStable():
    t = titles.Titles()
    t.pages = [_page(("first", 0.0, 100.0), ("second", 0.0, 100.0))]
    t.sort()

    assert [ts.items[0] for ts in t.pages[0]] == ["first", "second"]


# loading a script sorts its title strings, so they're saved in y,x order
# whatever order the file had them in.
def testSavedOrder():
    sp = u.new()
    sp.titles.pages = [
        _page(
            ("CONTACT", 15.0, 248.0),
            ("TITLE", 0.0, 105.0),
            ("DRAFT", 120.0, 248.0),
            ("BY", 0.0, 120.0),
        )
    ]

    sp2 = u.loadString(sp.save().decode("utf-8"))
    out = sp2.save().decode("utf-8")
    saved = [
        line.rsplit(",", 1)[1]
        for line in out.splitlines()
        if line.startswith("#Title-String ")
    ]

    assert saved == ["TITLE", "BY", "CONTACT", "DRAFT"]
