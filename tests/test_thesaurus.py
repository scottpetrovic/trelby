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
S\tn\ta young person\tchild|kid|youngster|offspring|small fry
S\ta\tacting quickly\tfast|quick|hurrying|rapid|male
S\tv\tperceive by sight\tsee|watch|catch sight|travel
S\tv\tchange location\ttravel|go|move
S\tv\tdeal a blow to\thit|strike|punch
W\tangry\t0
W\tchild\t8
W\tdog\t5
W\tfast\t9
W\thit\t12
W\tlook\t6
W\tmad\t7
W\tsee\t10
W\ttravel\t11
W\twalk\t1 4
W\trun\t2 3
X\tangrier\ta\tangry\ter
X\tangriest\ta\tangry\test
X\tbetter\ta\tgood\ter
X\tchildren\tn\tchild\ts
X\tcaught\tv\tcatch\ted
X\tcaught\tv\tcatch\ten
X\tfries\tn\tfry\ts
X\twent\tv\tgo\ted
X\tgone\tv\tgo\ten
X\thas\tv\thave\ts
X\thit\tv\thit\ted
X\thit\tv\thit\ten
X\thurrying\ta\thurrying\ter
X\thurrying\ta\thurrying\test
X\tis\tv\tbe\ts
X\tjogged\tv\tjog\ted
X\tjogged\tv\tjog\ten
X\tmadder\ta\tmad\ter
X\tmaddest\ta\tmad\test
X\tmale\ta\tmale\ter
X\tmale\ta\tmale\test
X\tmen\tn\tman\ts
X\toffspring\tn\toffspring\ts
X\tran\tv\trun\ted
X\trun\tv\trun\ten
X\tsaw\tv\tsee\ted
X\tseen\tv\tsee\ten
X\tstruck\tv\tstrike\ted
X\tstruck\tv\tstrike\ten
X\ttook\tv\ttake\ted
X\ttaken\tv\ttake\ten
X\ttraveled\tv\ttravel\ted
X\ttravelled\tv\ttravel\ted
X\ttraveled\tv\ttravel\ten
X\ttravelled\tv\ttravel\ten
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
    assert th.headForms("seen") == [("see", "en", "v")]
    assert th.headForms("madder") == [("mad", "er", "a")]
    assert th.headForms("dog's") == [("dog", None, "")]

    # a British spelling is still found
    assert th.headForms("travelled") == [("travel", "ed", "v")]


# the text before a past tense form can make it a past participle
def testParticiples():
    th = makeThesaurus()

    assert th.headForms("walked", "She ") == [("walk", "ed", "v")]
    assert th.headForms("walked", "She has ") == [("walk", "en", "v")]
    assert th.headForms("walked", "She hasn't ") == [("walk", "en", "v")]
    assert th.headForms("walked", "She'd ") == [("walk", "en", "v")]
    assert th.headForms("walked", "Had she never really ") == [("walk", "en", "v")]
    assert th.headForms("walked", "When it was dark, she ") == [("walk", "ed", "v")]
    assert th.headForms("walked", "It was, she ") == [("walk", "ed", "v")]
    assert th.headForms("hit", "He was ") == [("hit", "en", "v")]
    assert th.headForms("hit", "He ") == [("hit", None, "")]
    assert th.lookup("hit", "was ")[0].words == ["struck", "punched"]

    # "ran" is only a past tense, "seen" only a participle
    assert th.headForms("ran", "He has ") == [("run", "ed", "v")]
    assert th.headForms("seen", "He ") == [("see", "en", "v")]

    # "run" is the participle too, but "I'd run" is "I would run"
    assert th.headForms("run", "He has ") == [("run", "en", "v")]
    assert th.headForms("run", "He's ") == [("run", "en", "v")]
    assert th.headForms("run", "I'd ") == [("run", None, "")]
    assert th.headForms("run", "I ") == [("run", None, "")]

    assert th.lookup("walked", "She ")[0].words == [
        "strolled",
        "ambled",
        "went on foot",
        "wandered",
    ]
    assert th.lookup("walked", "She has ")[0].words == [
        "strolled",
        "ambled",
        "gone on foot",
        "wandered",
    ]
    assert th.lookup("ran")[0].words == ["sprinted", "dashed", "jogged"]
    assert th.lookup("run", "has ")[0].words == ["sprinted", "dashed", "jogged"]
    assert th.lookup("seen")[0].words == ["watched", "caught sight", "traveled"]
    assert th.lookup("saw")[0].words == ["watched", "caught sight", "traveled"]


def testAuxiliaryBefore():
    aux = thesaurus.auxiliaryBefore

    assert aux("") is None
    assert aux("He has ") == "has"
    assert aux("HE HAD ") == "had"
    assert aux("They haven't ") == "have"
    assert aux("I'd ") == "'d"
    assert aux("I\u2019ve ") == "'ve"
    assert aux("It was quickly ") == "was"
    assert aux("Has he ") == "has"
    assert aux("The dog's ") == "'s"
    assert aux("He has, ") is None
    assert aux("He has. She ") is None
    assert aux("He has the ") is None
    assert aux("He won't ") is None


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
    assert forms("friendly", "a", adj) == ["friendlier", "friendliest"]

    assert forms("stroll", "v", ["en"]) == ["strolled"]

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

    # the past tense and the participle
    assert th.inflect("run", "v", "ed") == "ran"
    assert th.inflect("run", "v", "en") == "run"
    assert th.inflect("see", "v", "ed") == "saw"
    assert th.inflect("see", "v", "en") == "seen"
    assert th.inflect("go", "v", "ed") == "went"
    assert th.inflect("go", "v", "en") == "gone"
    assert th.inflect("stroll", "v", "en") == "strolled"
    assert th.inflect("run", "v", "s") == "runs"
    assert th.inflect("see", "v", "ing") == "seeing"

    # the past tense is the word itself
    assert th.inflect("hit", "v", "ed") == "hit"
    assert th.inflect("hit", "v", "en") == "hit"

    # the first form is used: the US spelling
    assert th.inflect("travel", "v", "ed") == "traveled"

    # forms that aren't used: uncountable nouns, adjectives that have no
    # comparative
    assert th.inflect("offspring", "n", "s") == "offspring"
    assert th.inflect("hurrying", "a", "er") == "hurrying"
    assert th.inflect("male", "a", "est") == "male"

    # phrases
    assert th.inflect("take a look", "v", "s") == "takes a look"
    assert th.inflect("take a look", "v", "ed") == "took a look"
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

    # "-child"
    assert th.inflect("grandchild", "n", "s") == "grandchildren"

    # proper nouns
    assert th.inflect("Canis familiaris", "n", "s") == "Canis familiaris"


def testLookupInflects():
    th = makeThesaurus()

    assert words(th.lookup("looks")) == [
        ("look", "v", ["stares", "glances", "peers", "takes a look"]),
    ]
    looked = th.lookup("Looked")[0].words
    assert looked == ["Stared", "Glanced", "Peered", "Took a look"]
    assert th.lookup("looking")[0].words == [
        "staring",
        "glancing",
        "peering",
        "taking a look",
    ]

    # the noun senses can't be "walked", and are left out
    assert words(th.lookup("walked")) == [
        ("walk", "v", ["strolled", "ambled", "went on foot", "wandered"]),
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

    # the X lines with the word itself
    assert words(th.lookup("faster")) == [
        ("fast", "a", ["quicker", "hurrying", "more rapid", "male"]),
    ]
    assert words(th.lookup("children")) == [
        ("child", "n", ["kids", "youngsters", "offspring", "small fries"]),
    ]


# the real file has the common words and forms
def testFile():
    with open(thesaurus.FILENAME, encoding="utf-8") as f:
        th = thesaurus.Thesaurus(f.read())

    assert "furious" in th.lookup("angry")[0].words
    assert th.headwords("walked") == ["walk"]
    assert th.headwords("went") == ["go"]
    assert "say" in th.headwords("said")

    assert th.lookup("looks")[0].words[:3] == ["stares", "glances", "peers"]
    assert "strolled" in th.lookup("sauntered")[0].words
    assert th.inflect("stop", "v", "ed") == "stopped"
    assert th.inflect("be", "v", "s") == "is"
    assert th.inflect("cut", "v", "ed") == "cut"
    assert th.inflect("knife", "n", "s") == "knives"
    assert th.inflect("big", "a", "est") == "biggest"

    # past tenses and participles
    def verb(word):
        return [th.inflect(word, "v", e) for e in ("ed", "en")]

    assert verb("see") == ["saw", "seen"]
    assert verb("run") == ["ran", "run"]
    assert verb("come") == ["came", "come"]
    assert verb("take") == ["took", "taken"]
    assert verb("go") == ["went", "gone"]
    assert verb("swim") == ["swam", "swum"]
    assert verb("get") == ["got", "gotten"]
    assert verb("bear") == ["bore", "borne"]
    assert verb("beat") == ["beat", "beaten"]
    assert verb("bid") == ["bid", "bid"]
    assert verb("hit") == ["hit", "hit"]
    assert verb("buy") == ["bought", "bought"]
    assert verb("prove") == ["proved", "proven"]
    assert verb("dive") == ["dove", "dived"]
    assert verb("be") == ["was", "been"]
    assert verb("slide") == ["slid", "slid"]
    assert verb("lie") == ["lay", "lain"]

    # US spellings, and regular forms for old or British ones
    assert verb("travel") == ["traveled", "traveled"]
    assert th.inflect("cancel", "v", "ing") == "canceling"
    assert th.inflect("program", "v", "s") == "programs"
    assert th.inflect("dream", "v", "ed") == "dreamed"
    assert th.inflect("work", "v", "ed") == "worked"
    assert th.inflect("melt", "v", "en") == "melted"
    assert th.inflect("compel", "v", "ed") == "compelled"
    assert "travel" in th.headwords("travelled")

    # uncountable nouns
    assert th.inflect("offspring", "n", "s") == "offspring"
    assert th.inflect("progeny", "n", "s") == "progeny"
    assert th.inflect("child's play", "n", "s") == "child's play"
    assert th.inflect("happiness", "n", "s") == "happiness"
    assert th.inflect("walking", "n", "s") == "walking"
    assert th.inflect("advice", "n", "s") == "advice"
    assert th.inflect("sheep", "n", "s") == "sheep"
    assert th.inflect("hound", "n", "s") == "hounds"
    assert th.inflect("langur", "n", "s") == "langurs"
    assert th.inflect("schoolchild", "n", "s") == "schoolchildren"

    # adjectives and adverbs with no comparative, or a "more" one the
    # rules don't make
    assert th.inflect("hurrying", "a", "er") == "hurrying"
    assert th.inflect("presto", "a", "er") == "presto"
    assert th.inflect("male", "a", "er") == "male"
    assert th.inflect("now", "r", "er") == "now"
    assert th.inflect("boyish", "a", "er") == "more boyish"
    assert th.inflect("furious", "a", "est") == "most furious"
    assert th.inflect("friendly", "a", "er") == "friendlier"
    assert th.inflect("fast", "r", "er") == "faster"

    # "walked" isn't a noun
    assert {s.pos for s in th.lookup("walked")} == {"v"}
    assert th.lookup("walked")[0].words[0] == "went"
    assert th.lookup("walked", "has ")[0].words[0] == "gone"


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
            (103, "went on foot"),
            (104, "wandered"),
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


# the right-click menu looks at the paragraph's text before the word
def testSynonymsMenuParticiple():
    ctrl = makeCtrl("")
    ctrl.sp.lines = [
        Line(scr.LB_SPACE, scr.ACTION, "She has"),
        Line(scr.LB_LAST, scr.ACTION, "walked home."),
    ]

    with mock.patch.object(thesaurus, "gThesaurus", makeThesaurus()):
        items = ctrl.synonymsMenu(1, 0)

    assert items[3] == (103, "gone on foot")


# the generator's rules, on WordNet's forms
def testGenerator():
    import tools.make_thesaurus as gen

    pasts = {"saw", "seen"}
    assert gen.verbEndings("saw", "see", pasts) == ["ed"]
    assert gen.verbEndings("seen", "see", pasts) == ["en"]
    assert gen.verbEndings("sang", "sing", {"sang", "sung"}) == ["ed"]
    assert gen.verbEndings("sung", "sing", {"sang", "sung"}) == ["en"]
    assert gen.verbEndings("tore", "tear", {"tore", "torn"}) == ["ed"]
    assert gen.verbEndings("torn", "tear", {"tore", "torn"}) == ["en"]
    assert gen.verbEndings("bought", "buy", {"bought"}) == ["ed", "en"]
    assert gen.verbEndings("fled", "flee", {"fled"}) == ["ed", "en"]
    assert gen.verbEndings("hit", "hit", {"hit"}) == ["ed", "en"]
    assert gen.verbEndings("proven", "prove", {"proven"}) == ["en"]
    assert gen.verbEndings("ran", "run", {"ran"}) == ["ed"]
    assert gen.verbEndings("overcame", "overcome", {"overcame"}) == ["ed"]
    assert gen.verbEndings("took pains", "take pains", {"took", "taken"}) == ["ed"]

    assert gen.isVariant("travelled", "travel", "traveled")
    assert gen.isVariant("programmes", "program", "programs")
    assert gen.isVariant("dreamt", "dream", "dreamed")
    assert not gen.isVariant("bent", "bend", "bended")

    spelling = {"furious", "furiously", "male", "firstly", "worldly", "quickly"}
    kinds = {"worldly": {"a"}}
    assert gen.isGradable("furious", "a", spelling, kinds)
    assert not gen.isGradable("male", "a", spelling, kinds)
    assert not gen.isGradable("first", "a", spelling, kinds)
    assert not gen.isGradable("world", "a", spelling, kinds)
    assert gen.isGradable("quickly", "r", spelling, kinds)
    assert not gen.isGradable("presto", "r", spelling, kinds)

    th = makeThesaurus()
    words = {
        ("furious", "a"),
        ("female", "a"),
        ("advice", "n"),
        ("dog", "n"),
        ("langur", "n"),
        ("apt", "a"),
    }
    spelling = {"furious", "furiously", "female", "advice", "advices", "dog", "dogs"}
    spelling |= {"langur", "apt", "aptly"}
    kinds = {"langur": {"n", 5}, "advice": {"n", 9}}
    assert gen.unusedForms(th, words, spelling, kinds) == [
        ("more apt", "a", "apt", "er"),
        ("most apt", "a", "apt", "est"),
        ("female", "a", "female", "er"),
        ("female", "a", "female", "est"),
    ]
