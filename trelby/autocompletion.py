import re

import trelby.mypickle as mypickle
import trelby.screenplay as screenplay
import trelby.util as util
from trelby.autocompletiontype import AutoCompletionType as Type

# scene heading prefixes, offered in this order until the script uses
# some of them
SCENE_PREFIXES = ["INT.", "EXT.", "INT./EXT.", "EST.", "I/E."]

# times of day offered after a scene heading's location, in this order
# until the script uses some of them
SCENE_TIMES = [
    "DAY",
    "NIGHT",
    "CONTINUOUS",
    "LATER",
    "MOMENTS LATER",
    "MORNING",
    "AFTERNOON",
    "EVENING",
    "DAWN",
    "DUSK",
    "SAME",
]

# extensions offered after a character's name and "("
CHARACTER_EXTENSIONS = ["(V.O.)", "(O.S.)", "(O.C.)", "(CONT'D)"]

# a scene heading's prefix, then whitespace, then the rest
sceneRe = re.compile(
    r"(INT\./EXT\.|EXT\./INT\.|INT/EXT\.?|I/E\.?|INT\.|EXT\.|EST\.)\s+(.*)$"
)


# split upper-cased scene heading s into (prefix, location, time), where
# time is None if there's no " - " after the location yet. returns None if
# s doesn't start with a known prefix.
def parseScene(s):
    m = sceneRe.match(s)

    if not m:
        return None

    loc, sep, time = m.group(2).partition(" - ")

    return (m.group(1), loc.strip(), time.strip() if sep else None)


# true if auto-completion item s is only the start of a scene heading
# (a prefix, or a prefix and a location), which is completed further
# instead of ending the element.
def isPartial(s):
    return s.endswith(" ")


# order values by their last use above line 'cur', most recent first,
# then by how often they're used, then by their order in 'defaults', then
# alphabetically. 'uses' is a list of (line, value). returns the ordered
# list, and a dict of value -> the last line above 'cur' it's used on.
def rank(uses, cur, defaults=()):
    counts = {}
    lastAbove = {}

    for i, v in uses:
        counts[v] = counts.get(v, 0) + 1

        if i < cur:
            lastAbove[v] = i

    for v in defaults:
        counts.setdefault(v, 0)

    defIdx = {v: n for n, v in enumerate(defaults)}

    order = sorted(
        counts,
        key=lambda v: (
            -lastAbove.get(v, -1),
            -counts[v],
            defIdx.get(v, len(defIdx)),
            v,
        ),
    )

    return order, lastAbove


# scene heading completions for 'text', a part at a time: the prefix, then
# the location, then the time of day. returns None if 'text' isn't a
# heading of that form, for the caller to match whole headings instead.
def sceneMatches(text, uses, cur):
    parsed = [(i, parseScene(s)) for i, s in uses]
    parsed = [(i, h) for i, h in parsed if h]

    p = parseScene(text)

    if not p:
        prefixes = rank([(i, h[0]) for i, h in parsed], cur, SCENE_PREFIXES)[0]
        mlist = [s + " " for s in prefixes if (s + " ").startswith(text)]

        if not mlist:
            return None

        # headings not of the usual form can still be completed whole
        others = [s for _, s in uses if not parseScene(s)]
        mlist += [s for s in rank(uses, cur)[0] if s in others and s.startswith(text)]

        return mlist

    prefix, loc, time = p

    if time is None:
        locs = rank([(i, h[1]) for i, h in parsed if h[1]], cur)[0]

        return ["%s %s - " % (prefix, s) for s in locs if s.startswith(loc)]

    times = rank([(i, h[2]) for i, h in parsed if h[2]], cur, SCENE_TIMES)[0]

    return ["%s %s - %s" % (prefix, loc, s) for s in times if s.startswith(time)]


# character extension completions for 'text', once it has a name and
# "(". returns None if it doesn't.
def extensionMatches(text, uses, cur):
    idx = text.find("(")
    name = text[:idx].strip()

    if (idx == -1) or not name:
        return None

    exts = [(i, s[s.find("(") :]) for i, s in uses if "(" in s]
    exts = rank(exts, cur, CHARACTER_EXTENSIONS)[0]

    return ["%s %s" % (name, s) for s in exts if s.startswith(text[idx:])]


# manages auto completion information for a single script.
class AutoCompletion:
    def __init__(self):
        # type configs, key = line type, value = Type
        self.types = {}

        # element types
        t = Type(screenplay.SCENE)
        self.types[t.ti.lt] = t

        t = Type(screenplay.CHARACTER)
        self.types[t.ti.lt] = t

        t = Type(screenplay.TRANSITION)
        t.items = [
            "BACK TO:",
            "CROSSFADE:",
            "CUT TO:",
            "DISSOLVE TO:",
            "FADE IN:",
            "FADE OUT",
            "FADE TO BLACK",
            "FLASHBACK TO:",
            "JUMP CUT TO:",
            "MATCH CUT TO:",
            "SLOW FADE TO BLACK",
            "SMASH CUT TO:",
            "TIME CUT:",
        ]
        self.types[t.ti.lt] = t

        t = Type(screenplay.SHOT)
        self.types[t.ti.lt] = t

        self.refresh()

    # load config from string 's'. does not throw any exceptions, silently
    # ignores any errors, and always leaves config in an ok state.
    def load(self, s):
        vals = mypickle.Vars.makeVals(s)

        for t in self.types.values():
            t.load(vals, "AutoCompletion/")

        self.refresh()

    # save config into a string and return that.
    def save(self):
        s = ""

        for t in self.types.values():
            s += t.save("AutoCompletion/")

        return s

    # fix up invalid values and uppercase everything.
    def refresh(self):
        for t in self.types.values():
            tmp = []

            for v in t.items:
                v = util.upper(util.toInputStr(v)).strip()

                if len(v) > 0:
                    tmp.append(v)

            t.items = tmp

    # get type's Type, or None if it doesn't exist.
    def getType(self, lt):
        return self.types.get(lt)

    # get the completions for upper-cased 'text' in an element of type lt,
    # in the order to show them. 'uses' is a list of (line, text) for the
    # other single-line elements of that type, and 'cur' is the current
    # line. the type's configured items are included too.
    def getMatches(self, text, lt, uses, cur):
        items = self.getType(lt).items

        mlist = None
        allUses = uses + [(float("inf"), s) for s in items]

        if lt == screenplay.SCENE:
            mlist = sceneMatches(text, allUses, cur)
        elif lt == screenplay.CHARACTER:
            mlist = extensionMatches(text, allUses, cur)

        if mlist is not None:
            return mlist

        order, lastAbove = rank(uses, cur, items)

        # in dialogue the next speaker is more often the one before the
        # last one than the last one again
        if (
            (lt == screenplay.CHARACTER)
            and (len(order) > 1)
            and (order[1] in lastAbove)
        ):
            order[0], order[1] = order[1], order[0]

        return [s for s in order if s.startswith(text)]
