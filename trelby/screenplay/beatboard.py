# the beat board: index cards ("beats") laid out freely on a canvas, for
# planning a story before or while writing it. a card is just text in a
# place on the board, with a color, maybe a picture, and a size if it has
# been resized. the board is kept apart from the script's scenes and
# outline.

import base64
import binascii

import trelby.screenplay.characterprofiles as characterprofiles
import trelby.mypickle as mypickle
import trelby.undo as undo
import trelby.util as util
from trelby.screenplay.datatypes import isValidColor

# size of a card on the board, in the board's units (unscaled pixels)
CARD_WIDTH = 260
CARD_HEIGHT = 156

# the sizes a card can be resized to, in the same units
MIN_CARD_WIDTH = 80
MIN_CARD_HEIGHT = 50
MAX_CARD_SIZE = 4000

# space kept between a card and the edge of the window when scrolling to
# it
GAP = 20

# the board's coordinates are kept within this, so that a damaged file
# can't put a card somewhere unreachable
MAX_COORD = 100000

# the longest side a card's picture is kept at, in pixels, and the
# biggest picture file kept as it is (see ui/beatboardview.imageData), so
# that pictures don't make scripts huge
MAX_IMAGE_SIDE = 1024
MAX_IMAGE_BYTES = 1024 * 1024

# the color new cards get: the outline's Yellow (ui/outline.getSceneColors)
DEFAULT_COLOR = "fff2a8"


# one index card on the board
class Beat:
    def __init__(self, text="", x=0, y=0):
        # the card's text. its first line is shown as the card's title.
        self.text = text

        # position of the card's top left corner on the board
        self.x = x
        self.y = y

        # the card's color ("rrggbb"), or None for the default
        self.color = None

        # the card's size, if it has been resized, otherwise None for both,
        # when it's the default size for its contents (see
        # ui/beatboardview.BeatBoardView.cardSize)
        self.width = None
        self.height = None

        # the card's picture, the contents of a PNG or JPEG file (bytes),
        # or None. saved in the file, so the script doesn't depend on
        # where the picture came from.
        self.image = None

        # values found in the file that this version doesn't know about,
        # kept so that saving doesn't lose them. key = name in the file
        # (without the "Beat/N/" prefix), value = the saved string.
        self.extra = {}

    # the card's title: the first non-empty line of its text
    def getTitle(self):
        for s in self.text.splitlines():
            if s.strip():
                return s.strip()

        return ""

    # resize the card to w x h, or back to its default size if w is None
    def setSize(self, w, h=None):
        if w is None:
            self.width = self.height = None
        else:
            self.width = util.clamp(w, MIN_CARD_WIDTH, MAX_CARD_SIZE)
            self.height = util.clamp(h, MIN_CARD_HEIGHT, MAX_CARD_SIZE)

    def save(self, prefix):
        s = "%s/X:%d\n%s/Y:%d\n" % (prefix, self.x, prefix, self.y)

        if self.text:
            s += "%s/Text:%s\n" % (prefix, characterprofiles.escapeText(self.text))

        if self.color:
            s += "%s/Color:%s\n" % (prefix, self.color)

        if self.width:
            s += "%s/Width:%d\n%s/Height:%d\n" % (
                prefix,
                self.width,
                prefix,
                self.height,
            )

        if self.image:
            data = base64.b64encode(self.image).decode("ascii")
            s += "%s/Image:%s\n" % (prefix, data)

        for key in sorted(self.extra):
            s += "%s/%s:%s\n" % (prefix, key, self.extra[key])

        return s

    # load from 'vals', a dictionary as returned by mypickle.Vars.makeVals.
    # the values used are deleted from 'vals'.
    def load(self, vals, prefix):
        self.text = characterprofiles.unescapeText(vals.pop(prefix + "/Text", ""))
        self.x = util.str2int(vals.pop(prefix + "/X", "0"), 0, 0, MAX_COORD)
        self.y = util.str2int(vals.pop(prefix + "/Y", "0"), 0, 0, MAX_COORD)

        color = vals.pop(prefix + "/Color", "")
        self.color = color.lower() if isValidColor(color) else None

        self.width = self.height = None
        w = vals.pop(prefix + "/Width", "")
        h = vals.pop(prefix + "/Height", "")

        if w and h:
            self.setSize(
                util.str2int(w, CARD_WIDTH),
                util.str2int(h, CARD_HEIGHT),
            )

        self.image = decodeImage(vals.pop(prefix + "/Image", ""))

        start = prefix + "/"

        for name in [n for n in vals if n.startswith(start)]:
            self.extra[name[len(start) :]] = vals.pop(name)


# the picture saved as 's' (base64), or None if there's none or it isn't
# valid base64
def decodeImage(s):
    try:
        return base64.b64decode(s, validate=True) or None
    except (binascii.Error, ValueError):
        return None


# all the cards of a single screenplay, in drawing order: a card is drawn
# on top of the ones before it
class BeatBoard:
    def __init__(self):
        # list of Beat objects
        self.beats = []

    # whether there's anything worth saving
    def hasInfo(self):
        return bool(self.beats)

    # load from string 's'. does not throw any exceptions and silently
    # ignores any errors.
    def load(self, s):
        vals = mypickle.Vars.makeVals(s)

        count = util.str2int(vals.pop("Beats", "0"), 0, 0, 100000)

        self.beats = []

        for i in range(1, count + 1):
            beat = Beat()
            beat.load(vals, "Beat/%d" % i)
            self.beats.append(beat)

    # save to a string and return that.
    def save(self):
        s = "Beats:%d\n" % len(self.beats)

        for i, beat in enumerate(self.beats):
            s += beat.save("Beat/%d" % (i + 1))

        return s


# the Editor's side: replacing the board as one undoable edit
class BeatBoardEditMixin:
    # replace the script's beat board with 'board', as one undo step.
    # returns False if that wouldn't change anything.
    def setBeatBoard(self, board):
        if board.save() == self.sp.beatBoard.save():
            return False

        u = undo.BeatBoard(self)

        self.sp.beatBoard = board
        self.sp.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)

        return True
