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
S\tv\tperceive with attention\tlook|stare|glance|peer|take a look
S\ta\tlosing one's temper\tangry|mad|furious|hot under the collar
W\tangry\t0
W\tdog\t5
W\tlook\t6
W\tmad\t7
W\twalk\t1 4
W\trun\t2 3
X\tangrier\ta\tangry\ter
X\tangriest\ta\tangry\test
X\tbetter\ta\tgood\ter
X\tchildren\tn\tchild\ts
X\tgone\tv\tgo\ted
X\thas\tv\thave\ts
X\thit\tv\thit\ted
X\tis\tv\tbe\ts
X\tjogged\tv\tjog\ted
X\tmadder\ta\tmad\ter
X\tmaddest\ta\tmad\test
X\tmen\tn\tman\ts
X\tran\tv\trun\ted
X\tsaw\tv\tsee\ted
X\tseen\tv\tsee\ted
X\ttaken\tv\ttake\ted
X\ttook\tv\ttake\ted
X\twent\tv\tgo\ted
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

    assert words(th.lookup("Ran"))[0] == ("run", "v", ["Sprinted", "Dashed", "Jogged"])

    # which form word is of each headword, and as which parts of speech
    assert th.headForms("walks") == [("walk", "s", "nv")]
    assert th.headForms("walked") == [("walk", "ed", "v")]
    assert th.headForms("ran") == [("run", "ed", "v")]
    assert th.headForms("madder") == [("mad", "er", "a")]
    assert th.headForms("dog's") == [("dog", None, "")]


def testRegularForm():
    def forms(word, pos, endings):
        return [thesaurus.regularForm(word, pos, e) for e in endings]

    verb = ["s", "ed", "ing"]
    assert forms("stare", "v", verb) == ["stares", "stared", "staring"]
    assert forms("peer", "v", verb) == ["peers", "peered", "peering"]
    assert forms("carry", "v", verb) == ["carries", "carried", "carrying"]
    assert forms("play", "v", verb) == ["plays", "played", "playing"]
    assert forms("push", "v", verb) == ["pushes", "pushed", "pushing"]
    assert forms("watch", "v", verb) == ["watches", "watched", "watching"]
    assert forms("fix", "v", verb) == ["fixes", "fixed", "fixing"]
    assert forms("buzz", "v", verb) == ["buzzes", "buzzed", "buzzing"]
    assert forms("echo", "v", verb) == ["echoes", "echoed", "echoing"]
    assert forms("go", "v", ["s", "ing"]) == ["goes", "going"]
    assert forms("tie", "v", verb) == ["ties", "tied", "tying"]
    assert forms("agree", "v", verb) == ["agrees", "agreed", "agreeing"]
    assert forms("dye", "v", ["ing"]) == ["dyeing"]
    assert forms("be", "v", ["ing"]) == ["being"]

    assert forms("hound", "n", ["s"]) == ["hounds"]
    assert forms("box", "n", ["s"]) == ["boxes"]
    assert forms("puppy", "n", ["s"]) == ["puppies"]
    assert forms("boy", "n", ["s"]) == ["boys"]
    assert forms("photo", "n", ["s"]) == ["photos"]
    assert forms("glass", "n", ["s"]) == ["glasses"]
    assert forms("bus", "n", ["s"]) == ["buses"]
    # already plural
    assert forms("trousers", "n", ["s"]) == ["trousers"]

    adj = ["er", "est"]
    assert forms("fast", "a", adj) == ["faster", "fastest"]
    assert forms("large", "a", adj) == ["larger", "largest"]
    assert forms("free", "a", adj) == ["freer", "freest"]
    assert forms("angry", "a", adj) == ["angrier", "angriest"]
    assert forms("grey", "a", adj) == ["greyer", "greyest"]
    assert forms("furious", "a", adj) == ["more furious", "most furious"]
    assert forms("irate", "a", adj) == ["more irate", "most irate"]
    assert forms("quickly", "r", adj) == ["more quickly", "most quickly"]

    assert forms("catch-22", "n", ["s"]) == ["catch-22"]


def testInflect():
    th = makeThesaurus()

    # irregular forms that are safe to use
    assert th.inflect("jog", "v", "ed") == "jogged"
    assert th.inflect("have", "v", "s") == "has"
    assert th.inflect("be", "v", "s") == "is"
    assert th.inflect("child", "n", "s") == "children"
    assert th.inflect("mad", "a", "er") == "madder"
    assert th.inflect("good", "a", "er") == "better"

    # a past tense that could be the participle ("has ran"), or that has
    # two forms
    assert th.inflect("run", "v", "ed") == "run"
    assert th.inflect("see", "v", "ed") == "see"
    assert th.inflect("go", "v", "ed") == "go"
    assert th.inflect("run", "v", "s") == "runs"
    assert th.inflect("see", "v", "ing") == "seeing"

    # the past tense is the word itself
    assert th.inflect("hit", "v", "ed") == "hit"

    # phrases
    assert th.inflect("take a look", "v", "s") == "takes a look"
    assert th.inflect("take a look", "v", "ed") == "take a look"
    assert th.inflect("go on foot", "v", "ing") == "going on foot"
    assert th.inflect("domestic dog", "n", "s") == "domestic dogs"
    assert th.inflect("man of war", "n", "s") == "man of war"
    assert th.inflect("mother-in-law", "n", "s") == "mother-in-law"
    assert th.inflect("hot under the collar", "a", "er") == "hot under the collar"

    # "-man"
    assert th.inflect("man", "n", "s") == "men"
    assert th.inflect("woman", "n", "s") == "women"
    assert th.inflect("walkman", "n", "s") == "walkmen"
    assert th.inflect("human", "n", "s") == "human"

    # proper nouns
    assert th.inflect("Canis familiaris", "n", "s") == "Canis familiaris"


def testLookupInflects():
    th = makeThesaurus()

    assert words(th.lookup("looks")) == [
        ("look", "v", ["stares", "glances", "peers", "takes a look"]),
    ]
    looked = th.lookup("Looked")[0].words
    assert looked == ["Stared", "Glanced", "Peered", "Take a look"]
    assert th.lookup("looking")[0].words == [
        "staring",
        "glancing",
        "peering",
        "taking a look",
    ]

    # the verbs are inflected, the nouns aren't
    assert words(th.lookup("walked")) == [
        ("walk", "v", ["strolled", "ambled", "go on foot", "wandered"]),
        ("walk", "n", ["stroll", "walking"]),
    ]
    assert words(th.lookup("walks")) == [
        ("walk", "v", ["strolls", "ambles", "goes on foot", "wanders"]),
        ("walk", "n", ["strolls", "walkings"]),
    ]

    assert words(th.lookup("dogs")) == [("dog", "n", ["hounds", "pooches"])]
    assert words(th.lookup("angrier")) == [
        ("angry", "a", ["madder", "more furious", "more irate"]),
    ]
    assert words(th.lookup("madder")) == [
        ("mad", "a", ["angrier", "more furious", "hot under the collar"]),
    ]
    assert th.lookup("angriest")[0].words == ["maddest", "most furious", "most irate"]


# the real file has the common words and forms
def testFile():
    with open(thesaurus.FILENAME, encoding="utf-8") as f:
        th = thesaurus.Thesaurus(f.read())

    assert "furious" in th.lookup("angry")[0].words
    assert th.headwords("walked") == ["walk"]
    assert th.headwords("went") == ["go"]
    assert "say" in th.headwords("said")

    assert th.lookup("looks")[0].words[:3] == ["stares", "glances", "peers"]
    assert "strolled" in th.lookup("sauntered")[2].words
    assert th.inflect("stop", "v", "ed") == "stopped"
    assert th.inflect("see", "v", "ed") == "see"
    assert th.inflect("be", "v", "s") == "is"
    assert th.inflect("cut", "v", "ed") == "cut"
    assert th.inflect("knife", "n", "s") == "knives"
    assert th.inflect("big", "a", "est") == "biggest"


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

        # the headers have the headword, the verbs are in the past tense
        items = ctrl.synonymsMenu(0, 6)
        assert items == [
            (None, "walk (verb): use one's feet to advance"),
            (101, "strolled"),
            (102, "ambled"),
            (103, "go on foot"),
            (104, "wandered"),
            (None, "walk (noun): the act of walking"),
            (105, "stroll"),
            (106, "walking"),
        ]

        ctrl.OnSynonymMenu(MenuEvent(102))
        assert ctrl.sp.lines[0].text == "She ambled home, the dog's angry."
        assert ctrl.sp.isModified()

        ctrl.ed.cmd("undo")
        assert ctrl.sp.lines[0].text == "She walked home, the dog's angry."

        # a possessive keeps its "'s"
        ctrl.synonymsMenu(0, 22)
        ctrl.OnSynonymMenu(MenuEvent(102))
        assert ctrl.sp.lines[0].text == "She walked home, the pooch's angry."

        # a word already listed for an earlier sense isn't repeated
        items = makeCtrl("walk").synonymsMenu(0, 0)
        assert items[-2:] == [
            (None, "walk (noun): the act of walking"),
            (105, "walking"),
        ]


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
