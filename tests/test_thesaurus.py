from unittest import mock

import tests.u as u
import trelby.screenplay as scr
import trelby.thesaurus as thesaurus
import trelby.translations as translations
import trelby.ui.trelbyctrl as trelbyctrl
from trelby.screenplay.line import Line

_ = translations.trelby_translations_load()

DATA = """\
# a comment
S\ta\tfeeling or showing anger\tangry|mad|furious|irate
S\tv\tuse one's feet to advance\twalk|stroll|amble|go on foot|wander
S\tv\tmove fast by using one's feet\trun|sprint|dash|jog
S\tn\ta score in baseball\trun|tally
S\tn\tthe act of walking\twalk|stroll|walking
S\tn\ta domestic canine\tdog|hound|pooch
W\tangry\t0
W\tdog\t5
W\twalk\t1 4
W\trun\t2 3
X\tran\trun
"""


def makeThesaurus():
    return thesaurus.Thesaurus(DATA)


def words(senses):
    return [(s.word, s.pos, s.words) for s in senses]


def testLookup():
    th = makeThesaurus()

    # the word itself is left out
    assert words(th.lookup("angry")) == [("angry", "a", ["mad", "furious", "irate"])]
    assert th.lookup("angry")[0].definition == "feeling or showing anger"

    assert words(th.lookup("walk")) == [
        ("walk", "v", ["stroll", "amble", "go on foot", "wander"]),
        ("walk", "n", ["stroll", "walking"]),
    ]

    assert th.lookup("xyzzy") == []
    assert th.lookup("") == []


def testLookupKeepsCase():
    th = makeThesaurus()

    assert th.lookup("Angry")[0].words == ["Mad", "Furious", "Irate"]
    assert th.lookup("ANGRY")[0].words == ["MAD", "FURIOUS", "IRATE"]
    assert th.lookup("WALK")[0].words[2] == "GO ON FOOT"


def testHeadwords():
    th = makeThesaurus()

    # regular endings, irregular forms, and possessives
    assert th.headwords("walked") == ["walk"]
    assert th.headwords("Walking") == ["walk"]
    assert th.headwords("walks") == ["walk"]
    assert th.headwords("ran") == ["run"]
    assert th.headwords("runs") == ["run"]
    assert th.headwords("walk's") == ["walk"]
    assert th.headwords("s") == []

    assert words(th.lookup("Ran"))[0] == ("run", "v", ["Sprint", "Dash", "Jog"])


# the real file has the common words and forms
def testFile():
    with open(thesaurus.FILENAME, encoding="utf-8") as f:
        th = thesaurus.Thesaurus(f.read())

    assert "furious" in th.lookup("angry")[0].words
    assert th.headwords("walked") == ["walk"]
    assert th.headwords("went") == ["go"]
    assert "say" in th.headwords("said")


# the right-click menu's synonyms, on a MyCtrl made without a window
class MenuEvent:
    def __init__(self, id):
        self.id = id

    def GetId(self):
        return self.id


def makeCtrl(text):
    sp = u.new()
    sp.lines = [Line(scr.LB_LAST, scr.ACTION, text)]

    ctrl = trelbyctrl.MyCtrl.__new__(trelbyctrl.MyCtrl)
    ctrl.sp = sp
    ctrl.ed = scr.Editor(sp)
    ctrl.gd = mock.Mock()
    ctrl.synonymIds = list(range(101, 137))
    ctrl.clearAutoComp = lambda: None
    ctrl.makeLineVisible = lambda line: None
    ctrl.updateScreen = lambda: None

    return ctrl


def testSynonymsMenu():
    ctrl = makeCtrl("She walked home, the dog's angry.")

    with mock.patch.object(thesaurus, "gThesaurus", makeThesaurus()):
        assert ctrl.synonymsMenu(0, 0) is None
        assert ctrl.synonymsMenu(None, None) is None

        # a word already listed for an earlier sense isn't repeated
        items = ctrl.synonymsMenu(0, 6)
        assert items == [
            (None, "walk (verb): use one's feet to advance"),
            (101, "stroll"),
            (102, "amble"),
            (103, "go on foot"),
            (104, "wander"),
            (None, "walk (noun): the act of walking"),
            (105, "walking"),
        ]

        ctrl.OnSynonymMenu(MenuEvent(102))
        assert ctrl.sp.lines[0].text == "She amble home, the dog's angry."
        assert ctrl.sp.isModified()

        ctrl.ed.cmd("undo")
        assert ctrl.sp.lines[0].text == "She walked home, the dog's angry."

        # a possessive keeps its "'s"
        ctrl.synonymsMenu(0, 22)
        ctrl.OnSynonymMenu(MenuEvent(102))
        assert ctrl.sp.lines[0].text == "She walked home, the pooch's angry."


def testSynonymsMenuLimits():
    senses = "".join("S\tn\tsense %d\tword|a%d|b%d\n" % (i, i, i) for i in range(10))
    th = thesaurus.Thesaurus(senses + "W\tword\t" + " ".join(map(str, range(10))))
    ctrl = makeCtrl("word")

    with mock.patch.object(thesaurus, "gThesaurus", th):
        items = ctrl.synonymsMenu(0, 0)

    headers = [label for id, label in items if id is None]
    assert len(headers) == trelbyctrl.SYNONYM_SENSES

    long = "x" * 100
    th = thesaurus.Thesaurus("S\tn\t%s\tword|other\nW\tword\t0" % long)

    with mock.patch.object(thesaurus, "gThesaurus", th):
        header = ctrl.synonymsMenu(0, 0)[0][1]

    assert header.endswith("x…")
    assert len(header) == len("word (noun): ") + trelbyctrl.SYNONYM_DEFINITION_LENGTH
