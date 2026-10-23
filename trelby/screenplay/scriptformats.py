# script formats: the kinds of script a new one can be made as (File >
# New from template) or an open one switched to (Script > Change format),
# e.g. a stage play or a multi-camera sitcom.
#
# a format doesn't add element types. it lays out the eight there are
# (indents, widths, spacing, capitals...) and the page breaks its own way,
# and can give them names of its own, e.g. an action is a "Stage
# direction" in a stage play, and hide the ones it doesn't use from the
# toolbar and the right-click menu. the script's config remembers which
# format it is (Config.scriptFormat), for the names; everything else is
# ordinary script settings, which the user can change afterwards like any
# others. the file still stores the elements under their own names, so a
# script in another format opens in older versions too, just with the
# usual names.
#
# a two-column format (AV) puts some element types in a left column and
# others in a right one (ScriptFormat.columns): their indents and widths
# keep them in their columns, and the page layout (see twocolumn) puts
# each run of right-column elements beside the run of left-column ones
# before it. the script is still one list of elements.
#
# the texts are made when asked for, as the formats are defined before
# the translations are loaded.

import trelby.config as config
from trelby.screenplay.constants import (
    ACTBREAK,
    ACTION,
    CHARACTER,
    DIALOGUE,
    PAREN,
    SCENE,
    SHOT,
    TRANSITION,
)

# the key of the default format, which Config.scriptFormat starts as
SCREENPLAY = "screenplay"

# the order element types are listed in (the toolbar's)
TYPE_ORDER = (SCENE, ACTION, CHARACTER, PAREN, DIALOGUE, TRANSITION, SHOT, ACTBREAK)

# the script settings a format sets. apply resets these to their defaults
# before the format's own changes, so that switching formats doesn't keep
# the last one's; the rest (paper, margins, fonts, strings...) is left as
# it is.
FORMAT_VARS = ("pbActNewPage", "pbSceneNewPage", "sceneContinueds")

# the columns of a two-column format; element types in neither go across
# the page
LEFT = 1
RIGHT = 2


# what Enter and Tab make or switch an element to (see config.TypeGlobal),
# for a format that has its own instead of the global settings
class TypeFlow:
    def __init__(self, newTypeEnter, newTypeTab, nextTypeTab, prevTypeTab):
        self.newTypeEnter = newTypeEnter
        self.newTypeTab = newTypeTab
        self.nextTypeTab = nextTypeTab
        self.prevTypeTab = prevTypeTab


class ScriptFormat:
    def __init__(
        self,
        key,
        name,
        untitled,
        description,
        setup,
        labels=None,
        hidden=(),
        columns=None,
        headings=None,
        flow=None,
    ):
        # id, saved in the script, e.g. "stageplay"
        self.key = key

        # functions returning the name shown in the menus, the name of a
        # new script that hasn't been saved yet ("Untitled Stage Play"),
        # and a sentence saying what it's for
        self._name = name
        self._untitled = untitled
        self._description = description

        # function(cfg) making the format's changes to a default config
        self.setup = setup

        # {line type: function returning its name in this format}, for the
        # ones that differ from the usual names
        self.labels = labels or {}

        # line types the format doesn't use
        self.hidden = frozenset(hidden)

        # for a two-column format, {line type: LEFT or RIGHT}, else None
        self.columns = columns

        # for a two-column format, functions returning the titles printed
        # above its columns on every page, (left, right)
        self.headings = headings

        # {line type: TypeFlow} for the types whose Enter and Tab differ
        # from the global settings in this format
        self.flow = flow or {}

    def name(self):
        return self._name()

    def untitled(self):
        return self._untitled()

    def description(self):
        return self._description()

    # lay out cfg's elements and page breaks for this format
    def apply(self, cfg):
        default = config.Config()

        for lt, t in default.types.items():
            cfg.types[lt] = t

        for name in FORMAT_VARS:
            setattr(cfg, name, getattr(default, name))

        self.setup(cfg)
        cfg.scriptFormat = self.key
        cfg.recalc()


# set the layout of element type lt in cfg. caps, bold and underlined
# apply to the screen and the PDF alike, italic too.
def setType(
    cfg,
    lt,
    indent=None,
    width=None,
    before=None,
    intra=None,
    caps=None,
    bold=None,
    italic=None,
    underlined=None,
):
    t = cfg.getType(lt)

    for name, value in (
        ("indent", indent),
        ("width", width),
        ("beforeSpacing", before),
        ("intraSpacing", intra),
    ):
        if value is not None:
            setattr(t, name, value)

    for name, value in (
        ("isCaps", caps),
        ("isBold", bold),
        ("isItalic", italic),
        ("isUnderlined", underlined),
    ):
        if value is not None:
            setattr(t.screen, name, value)
            setattr(t.export, name, value)


def setupScreenplay(cfg):
    pass


# multi-camera sitcom: everything but the dialogue in capitals, the
# dialogue double-spaced, scene headings underlined and each scene (and
# act) on a new page
def setupSitcom(cfg):
    setType(cfg, SCENE, caps=True, bold=False, underlined=True)
    setType(cfg, ACTION, caps=True)
    setType(cfg, CHARACTER, indent=25, width=35)
    setType(cfg, DIALOGUE, indent=10, width=35, intra=10)
    setType(cfg, PAREN, indent=16, width=25)
    setType(cfg, TRANSITION, underlined=True)
    setType(cfg, ACTBREAK, indent=20, width=20)

    cfg.pbActNewPage = True
    cfg.pbSceneNewPage = True


# stage play: the dialogue across the page under the speaker's name, which
# is near the middle, and the stage directions indented and in italics
def setupStagePlay(cfg):
    setType(cfg, SCENE, indent=20, width=40, caps=True, bold=False, underlined=True)
    setType(cfg, ACTION, indent=20, width=40, italic=True)
    setType(cfg, CHARACTER, indent=27, width=33)
    setType(cfg, DIALOGUE, indent=0, width=60)
    setType(cfg, PAREN, indent=15, width=35, italic=True)
    setType(cfg, TRANSITION, indent=40, width=20)
    setType(cfg, ACTBREAK, indent=22, width=16, bold=True)

    cfg.pbActNewPage = True


# audio drama: a screenplay's speeches, with sound effects and music cues
# in capitals and underlined, indented from the descriptions
def setupAudioDrama(cfg):
    setType(cfg, ACTION, indent=0, width=60)
    setType(cfg, SHOT, indent=10, width=50, caps=True, underlined=True)
    setType(cfg, TRANSITION, indent=10, width=50, caps=True, underlined=True)


# comic book full script: a heading for each page, then each panel's
# number and description, followed by what's said in it. captions and
# sound effects are written as speeches (CAPTION, SFX).
def setupComic(cfg):
    setType(cfg, SCENE, before=20, caps=True, bold=True, underlined=True)
    setType(cfg, SHOT, before=10, caps=True, bold=True)
    setType(cfg, ACTION, indent=0, width=60)
    setType(cfg, CHARACTER, indent=10, width=50)
    setType(cfg, DIALOGUE, indent=10, width=45)
    setType(cfg, PAREN, indent=13, width=30)
    setType(cfg, ACTBREAK, indent=20, width=20, bold=True)

    cfg.pbActNewPage = True


# AV (audio-visual) two-column script, for documentaries, commercials,
# corporate and educational videos: what's seen on the left, what's heard
# on the right, side by side. scene headings (and act breaks) go across
# the page. Audio is the dialogue type, so it can follow a speaker or
# stand on its own as narration.
def setupAV(cfg):
    setType(cfg, ACTION, indent=0, width=28)
    setType(cfg, SHOT, indent=0, width=28)
    setType(cfg, CHARACTER, indent=32, width=28)
    setType(cfg, DIALOGUE, indent=32, width=28)
    setType(cfg, PAREN, indent=33, width=26)
    setType(cfg, TRANSITION, indent=32, width=28)
    setType(cfg, ACTBREAK, indent=20, width=20)

    cfg.sceneContinueds = False


AV_COLUMNS = {
    ACTION: LEFT,
    SHOT: LEFT,
    CHARACTER: RIGHT,
    PAREN: RIGHT,
    DIALOGUE: RIGHT,
    TRANSITION: RIGHT,
}

# Enter goes from a video element to the audio beside it and from audio to
# the next row's video, and Tab goes round each column's types
AV_FLOW = {
    ACTION: TypeFlow(DIALOGUE, CHARACTER, DIALOGUE, SHOT),
    SHOT: TypeFlow(ACTION, DIALOGUE, ACTION, SCENE),
    DIALOGUE: TypeFlow(ACTION, TRANSITION, TRANSITION, ACTION),
    TRANSITION: TypeFlow(ACTION, DIALOGUE, CHARACTER, DIALOGUE),
    CHARACTER: TypeFlow(DIALOGUE, PAREN, DIALOGUE, ACTION),
}


FORMATS = [
    ScriptFormat(
        SCREENPLAY,
        lambda: _("Screenplay"),
        lambda: _("Untitled Screenplay"),
        lambda: _("A feature film or single-camera TV script."),
        setupScreenplay,
    ),
    ScriptFormat(
        "sitcom",
        lambda: _("Multi-camera sitcom"),
        lambda: _("Untitled Sitcom"),
        lambda: _(
            "A multi-camera TV comedy: action in capitals, dialogue"
            " double-spaced, and each scene on a new page."
        ),
        setupSitcom,
    ),
    ScriptFormat(
        "stageplay",
        lambda: _("Stage play"),
        lambda: _("Untitled Stage Play"),
        lambda: _(
            "A play for the theater: dialogue across the page, and stage"
            " directions indented and in italics."
        ),
        setupStagePlay,
        labels={
            ACTION: lambda: _("Stage direction"),
            ACTBREAK: lambda: _("Act"),
        },
        hidden=(SHOT,),
    ),
    ScriptFormat(
        "audiodrama",
        lambda: _("Audio drama"),
        lambda: _("Untitled Audio Drama"),
        lambda: _(
            "A radio play or podcast drama, with sound effects and music"
            " cues of their own."
        ),
        setupAudioDrama,
        labels={
            ACTION: lambda: _("Description"),
            SHOT: lambda: _("Sound"),
            TRANSITION: lambda: _("Music"),
        },
    ),
    ScriptFormat(
        "comic",
        lambda: _("Comic"),
        lambda: _("Untitled Comic"),
        lambda: _(
            "A comic book script: each page's panels, with what's seen and"
            " said in each one."
        ),
        setupComic,
        labels={
            SCENE: lambda: _("Page"),
            SHOT: lambda: _("Panel"),
            ACTION: lambda: _("Description"),
            DIALOGUE: lambda: _("Balloon"),
            ACTBREAK: lambda: _("Chapter"),
        },
        hidden=(TRANSITION,),
    ),
    ScriptFormat(
        "av",
        lambda: _("AV two-column"),
        lambda: _("Untitled AV Script"),
        lambda: _(
            "A documentary, commercial or corporate video: what's seen on"
            " the left, what's heard beside it on the right."
        ),
        setupAV,
        labels={
            ACTION: lambda: _("Video"),
            CHARACTER: lambda: _("Speaker"),
            DIALOGUE: lambda: _("Audio"),
            TRANSITION: lambda: _("Sound"),
        },
        hidden=(ACTBREAK,),
        columns=AV_COLUMNS,
        headings=(lambda: _("VIDEO"), lambda: _("AUDIO")),
        flow=AV_FLOW,
    ),
]

_byKey = {f.key: f for f in FORMATS}


# the format with the given key, or the screenplay format for an unknown
# one (e.g. from a newer version)
def get(key):
    return _byKey.get(key, _byKey[SCREENPLAY])


# the format of the script with config cfg
def ofConfig(cfg):
    return get(cfg.scriptFormat)


# the name of element type lt in the script with config cfg. with
# withUsual, a name that isn't the usual one is followed by that, e.g.
# "Stage direction (Action)".
def typeLabel(cfg, lt, withUsual=False):
    usual = _(config.lt2ti(lt).name)
    label = ofConfig(cfg).labels.get(lt)

    if not label:
        return usual

    label = label()

    if withUsual and (label != usual):
        return "%s (%s)" % (label, usual)

    return label


# the element types the script with config cfg uses, in TYPE_ORDER
def usedTypes(cfg):
    hidden = ofConfig(cfg).hidden

    return [lt for lt in TYPE_ORDER if lt not in hidden]


# what Enter and Tab do in an element of type lt in the script with config
# cfg: the format's own TypeFlow if it has one, else the global settings'
# config.TypeGlobal from cfgGl
def typeFlow(cfgGl, cfg, lt):
    return ofConfig(cfg).flow.get(lt) or cfgGl.getType(lt)


# the script with config cfg's columns, {line type: LEFT or RIGHT}, or
# None if its format has one column
def columns(cfg):
    return ofConfig(cfg).columns
