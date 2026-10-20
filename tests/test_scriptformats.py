import tests.u as u
import trelby.config as config
import trelby.screenplay as scr
import trelby.screenplay.scriptformats as scriptformats
import trelby.translations as translations
from trelby.screenplay.line import Line

_ = translations.trelby_translations_load()
u.init()


def applied(key):
    cfg = config.Config()
    scriptformats.get(key).apply(cfg)

    return cfg


def testFormats():
    keys = [f.key for f in scriptformats.FORMATS]

    assert len(keys) == len(set(keys))
    assert keys[0] == scriptformats.SCREENPLAY

    for f in scriptformats.FORMATS:
        assert f.name() and f.untitled() and f.description()

        cfg = applied(f.key)
        assert cfg.scriptFormat == f.key

        # a format can't hide the types every script has
        for lt in (scr.SCENE, scr.ACTION, scr.CHARACTER, scr.DIALOGUE):
            assert lt in scriptformats.usedTypes(cfg)


# the screenplay format is the default config
def testScreenplayIsTheDefault():
    assert applied(scriptformats.SCREENPLAY).save() == config.Config().save()


# a format starts from the defaults, so nothing is left over from the last
# one, and the settings that aren't the format's are kept
def testApplyResetsTheLastFormat():
    cfg = config.Config()
    cfg.marginLeft = 30.0
    cfg.strMore = "(MORE MORE)"

    scriptformats.get("sitcom").apply(cfg)
    assert cfg.pbSceneNewPage
    assert cfg.getType(scr.DIALOGUE).intraSpacing == 10

    scriptformats.get("stageplay").apply(cfg)
    assert not cfg.pbSceneNewPage
    assert cfg.getType(scr.DIALOGUE).intraSpacing == 0
    assert cfg.getType(scr.ACTION).export.isItalic

    scriptformats.get(scriptformats.SCREENPLAY).apply(cfg)
    assert not cfg.getType(scr.ACTION).export.isItalic
    assert cfg.marginLeft == 30.0
    assert cfg.strMore == "(MORE MORE)"


def testFormatIsSaved():
    cfg = config.Config()
    cfg.load(applied("comic").save())

    assert cfg.scriptFormat == "comic"
    assert cfg.getType(scr.SHOT).export.isBold
    assert scriptformats.typeLabel(cfg, scr.SHOT) == "Panel"

    # and the format survives a script's save and load
    sp = u.new()
    sp.cfg = applied("comic")
    assert u.loadString(sp.save().decode("utf-8")).cfg.scriptFormat == "comic"


def testLabels():
    cfg = applied("stageplay")

    assert scriptformats.typeLabel(cfg, scr.ACTION) == "Stage direction"
    assert (
        scriptformats.typeLabel(cfg, scr.ACTION, withUsual=True)
        == "Stage direction (Action)"
    )
    assert scriptformats.typeLabel(cfg, scr.DIALOGUE, withUsual=True) == "Dialogue"
    assert scr.SHOT not in scriptformats.usedTypes(cfg)

    cfg = config.Config()
    assert scriptformats.typeLabel(cfg, scr.ACTION) == "Action"
    assert scriptformats.usedTypes(cfg) == list(scriptformats.TYPE_ORDER)


# a format from a newer version is taken as a screenplay
def testUnknownFormat():
    cfg = config.Config()
    cfg.scriptFormat = "opera"

    assert scriptformats.ofConfig(cfg).key == scriptformats.SCREENPLAY
    assert scriptformats.typeLabel(cfg, scr.SHOT) == "Shot"


def script(key, elems):
    sp = u.new()
    sp.cfg = applied(key)
    sp.lines = [Line(scr.LB_LAST, lt, text) for lt, text in elems]
    sp.reformatAll()
    sp.paginate()

    return sp


SITCOM = [
    (scr.TRANSITION, "FADE IN:"),
    (scr.SCENE, "INT. KITCHEN - DAY"),
    (scr.ACTION, "BOB ENTERS."),
    (scr.SCENE, "INT. HALL - DAY"),
    (scr.ACTION, "BOB EXITS."),
    (scr.ACTBREAK, "ACT TWO"),
    (scr.SCENE, "INT. KITCHEN - NIGHT"),
    (scr.ACTION, "BOB RETURNS."),
    (scr.SCENE, "INT. GARAGE - NIGHT"),
    (scr.SCENE, "INT. YARD - NIGHT"),
]


def firstLines(sp):
    return [sp.lines[sp.pages[p - 1] + 1].text for p in range(1, len(sp.pages))]


# every scene but the first starts a new page, except right after an act
# heading, which starts the page itself, or another scene heading
def testScenesStartPages():
    sp = script("sitcom", SITCOM)

    assert firstLines(sp) == [
        "FADE IN:",
        "INT. HALL - DAY",
        "ACT TWO",
        "INT. GARAGE - NIGHT",
    ]

    sp.cfg.pbSceneNewPage = False
    sp.paginate()

    assert firstLines(sp) == ["FADE IN:", "ACT TWO"]
