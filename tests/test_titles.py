import tests.u as u
import trelby.pml as pml
import trelby.titles as titles
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
    assert ts.isCentered and ts.isBold and (ts.font == pml.HELVETICA)

    ts = titles.makeString(titles.DRAFT, 215.9, 279.4)
    assert ts.getAlignment() == util.ALIGN_RIGHT
    assert ts.x == 215.9 - titles.EDGE_X


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
