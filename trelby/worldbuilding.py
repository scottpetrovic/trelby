import trelby.characterprofiles as characterprofiles
import trelby.mypickle as mypickle


# free-form notes about the world a screenplay is set in
class WorldBuilding:
    def __init__(self):
        self.text = ""

        # values found in the file that this version doesn't know about,
        # kept so that saving doesn't lose them. key = name in the file,
        # value = the saved string.
        self.extra = {}

    # whether there's anything worth saving
    def hasInfo(self):
        return bool(self.text.strip()) or bool(self.extra)

    # load from string 's'. does not throw any exceptions and silently
    # ignores any errors.
    def load(self, s):
        vals = mypickle.Vars.makeVals(s)

        self.text = characterprofiles.unescapeText(vals.pop("Text", ""))
        self.extra = vals

    # save to a string and return that.
    def save(self):
        s = ""

        if self.text:
            s += "Text:%s\n" % characterprofiles.escapeText(self.text)

        for key in sorted(self.extra):
            s += "%s:%s\n" % (key, self.extra[key])

        return s
