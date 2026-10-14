import base64
import re

import trelby.mypickle as mypickle
import trelby.util as util

# profile fields stored as text, in the order they're shown and saved:
# (attribute name, name in the file)
TEXT_FIELDS = [
    ("name", "Name"),
    ("role", "Role"),
    ("age", "Age"),
    ("gender", "Gender"),
    ("occupation", "Occupation"),
    ("appearance", "Appearance"),
    ("personality", "Personality"),
    ("background", "Background"),
    ("goals", "Goals"),
    ("notes", "Notes"),
]

# characters that str.splitlines() splits on (the script loader uses it),
# so they must never appear unescaped in a saved value
_LINE_BREAKS = "\n\r\x0b\x0c\x1c\x1d\x1e\x85  "


# escape a possibly multi-line text value so that it fits on one line:
# \ becomes \\, a newline becomes \n, and other line breaks and control
# characters become \uXXXX.
def escapeText(s):
    ret = []

    for ch in s:
        if ch == "\\":
            ret.append("\\\\")
        elif ch == "\n":
            ret.append("\\n")
        elif (ch in _LINE_BREAKS) or (ord(ch) < 32):
            ret.append("\\u%04x" % ord(ch))
        else:
            ret.append(ch)

    return "".join(ret)


def _unescapeRepl(mo):
    s = mo.group(1)

    if s == "n":
        return "\n"
    elif s == "\\":
        return "\\"
    else:
        return chr(int(s[1:], 16))


# reverse of escapeText. invalid escapes are kept as-is.
def unescapeText(s):
    return re.sub(r"\\(n|\\|u[0-9a-fA-F]{4})", _unescapeRepl, s)


# strip a character extension like "(V.O.)" or "(CONT'D)" from a name
# and upper-case it, so that all the ways a character's name appears in
# the script map to the same profile.
def normalizeName(name):
    name = util.upper(name)

    idx = name.find("(")
    if idx != -1:
        name = name[:idx]

    return " ".join(name.split())


# reference information about one character
class CharacterProfile:
    def __init__(self, name=""):
        for attr, _key in TEXT_FIELDS:
            setattr(self, attr, "")

        self.name = name

        # photos, as the raw bytes of PNG or JPEG files
        self.photos = []

        # values found in the file that this version doesn't know about,
        # kept so that saving doesn't lose them. key = name in the file
        # (without the "Profile/N/" prefix), value = the saved string.
        self.extra = {}

    # whether the profile holds anything besides the name
    def hasInfo(self):
        for attr, _key in TEXT_FIELDS:
            if (attr != "name") and getattr(self, attr).strip():
                return True

        return bool(self.photos) or bool(self.extra)

    def save(self, prefix):
        s = ""

        for attr, key in TEXT_FIELDS:
            val = getattr(self, attr)

            if val:
                s += "%s/%s:%s\n" % (prefix, key, escapeText(val))

        if self.photos:
            s += "%s/Photos:%d\n" % (prefix, len(self.photos))

            for i, data in enumerate(self.photos):
                s += "%s/Photo/%d:%s\n" % (
                    prefix,
                    i + 1,
                    base64.b64encode(data).decode("ascii"),
                )

        for key in sorted(self.extra):
            s += "%s/%s:%s\n" % (prefix, key, self.extra[key])

        return s

    # load from 'vals', a dictionary as returned by mypickle.Vars.makeVals.
    # the values used are deleted from 'vals'.
    def load(self, vals, prefix):
        for attr, key in TEXT_FIELDS:
            name = "%s/%s" % (prefix, key)

            if name in vals:
                setattr(self, attr, unescapeText(vals.pop(name)))

        count = util.str2int(vals.pop(prefix + "/Photos", "0"), 0, 0, 1000)

        for i in range(1, count + 1):
            data = vals.pop("%s/Photo/%d" % (prefix, i), None)

            if data:
                try:
                    self.photos.append(base64.b64decode(data, validate=True))
                except ValueError:
                    pass

        start = prefix + "/"

        for name in [n for n in vals if n.startswith(start)]:
            self.extra[name[len(start) :]] = vals.pop(name)


# all the character profiles of a single screenplay
class CharacterProfiles:
    def __init__(self):
        # list of CharacterProfile objects
        self.profiles = []

    # load from string 's'. does not throw any exceptions and silently
    # ignores any errors.
    def load(self, s):
        vals = mypickle.Vars.makeVals(s)

        count = util.str2int(vals.pop("Profiles", "0"), 0, 0, 100000)

        self.profiles = []

        for i in range(1, count + 1):
            prof = CharacterProfile()
            prof.load(vals, "Profile/%d" % i)

            if prof.name:
                self.profiles.append(prof)

    # save to a string and return that.
    def save(self):
        s = "Profiles:%d\n" % len(self.profiles)

        for i, prof in enumerate(self.profiles):
            s += prof.save("Profile/%d" % (i + 1))

        return s

    # return the profile for the given character name, or None. the name
    # is compared ignoring case and any extension like "(V.O.)".
    def get(self, name):
        name = normalizeName(name)

        for prof in self.profiles:
            if normalizeName(prof.name) == name:
                return prof

        return None

    def sort(self):
        self.profiles.sort(key=lambda p: normalizeName(p.name))
