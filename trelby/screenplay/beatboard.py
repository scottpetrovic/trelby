# the beat board: index cards ("beats") laid out freely on a canvas, for
# planning a story before or while writing it. a card is just text in a
# place on the board, with a color, maybe a picture, and a size if it has
# been resized. the board is kept apart from the script's scenes and
# outline.
#
# cards can also be put in acts: named frames on the board, each holding
# its cards in order, laid out left to right and top to bottom inside it
# (Act.layout), which can be folded to just their title. the board's acts
# are its own, not the script's act breaks.

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

# an act's frame, in the same units: the height of its title bar, the
# space between its edges and its cards, and between its cards
ACT_TITLE_HEIGHT = 40
ACT_PAD = 16
ACT_GAP = 16

# where an act's cards start, below its title bar
ACT_TOP = ACT_TITLE_HEIGHT + ACT_PAD

# the width of a new act's frame, which fits ACT_COLUMNS cards side by
# side, and the narrowest it can be made
ACT_COLUMNS = 4
ACT_WIDTH = ACT_COLUMNS * CARD_WIDTH + (ACT_COLUMNS - 1) * ACT_GAP + 2 * ACT_PAD
MIN_ACT_WIDTH = MIN_CARD_WIDTH + 2 * ACT_PAD


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


# an act on the board: a frame with a title, holding cards in order
class Act:
    def __init__(self, title="", x=0, y=0):
        self.title = title

        # position of the frame's top left corner on the board, and its
        # width
        self.x = x
        self.y = y
        self.width = ACT_WIDTH

        # the frame's color ("rrggbb"), or None for the default
        self.color = None

        # whether it's folded to just its title bar, hiding its cards
        self.folded = False

        # its cards, in order: Beat objects that are also in the board's
        # list. a card is in one act at most.
        self.beats = []

        # the frame's height, worked out by layout (not saved)
        self.height = ACT_TITLE_HEIGHT

        # values found in the file that this version doesn't know about
        # (see Beat.extra)
        self.extra = {}

    def setWidth(self, w):
        self.width = util.clamp(w, MIN_ACT_WIDTH, MAX_CARD_SIZE)

    # put the act's cards in place inside its frame, in order, left to
    # right in rows that wrap at the frame's width, and work out its
    # height. sizeOf(beat) is a card's (width, height).
    def layout(self, sizeOf):
        if self.folded:
            self.height = ACT_TITLE_HEIGHT

            return

        inner = self.width - 2 * ACT_PAD
        x = y = rowHeight = 0

        for beat in self.beats:
            w, h = sizeOf(beat)

            if (x > 0) and (x + w > inner):
                x = 0
                y += rowHeight + ACT_GAP
                rowHeight = 0

            beat.x = min(self.x + ACT_PAD + x, MAX_COORD)
            beat.y = min(self.y + ACT_TOP + y, MAX_COORD)

            x += w + ACT_GAP
            rowHeight = max(rowHeight, h)

        # an empty act has room for a card, to drop one in
        content = (y + rowHeight) if self.beats else CARD_HEIGHT

        self.height = ACT_TOP + content + ACT_PAD

    # where a card dropped at (x, y) on the board would go among the
    # act's cards, leaving out the ones in 'skip': an index in the list of
    # the others. the cards must be laid out (see layout).
    def insertIndex(self, x, y, sizeOf, skip=()):
        skip = {id(b) for b in skip}
        beats = [b for b in self.beats if id(b) not in skip]

        # the bottom of each row of cards, by its top
        bottoms = {}

        for b in beats:
            bottoms[b.y] = max(bottoms.get(b.y, b.y), b.y + sizeOf(b)[1])

        for i, b in enumerate(beats):
            if y < b.y:
                return i

            if (y < bottoms[b.y] + ACT_GAP) and (x < b.x + sizeOf(b)[0] // 2):
                return i

        return len(beats)

    def save(self, prefix, numbers):
        s = "%s/Title:%s\n%s/X:%d\n%s/Y:%d\n%s/Width:%d\n" % (
            prefix,
            characterprofiles.escapeText(self.title),
            prefix,
            self.x,
            prefix,
            self.y,
            prefix,
            self.width,
        )

        if self.color:
            s += "%s/Color:%s\n" % (prefix, self.color)

        if self.folded:
            s += "%s/Folded:1\n" % prefix

        if self.beats:
            s += "%s/Cards:%s\n" % (
                prefix,
                ",".join(str(numbers[id(b)]) for b in self.beats),
            )

        for key in sorted(self.extra):
            s += "%s/%s:%s\n" % (prefix, key, self.extra[key])

        return s

    # load from 'vals' (see Beat.load). its cards are taken from 'beats',
    # the board's, leaving out the ones in the set 'taken' (ids of cards
    # already in an act), which those it takes are added to.
    def load(self, vals, prefix, beats, taken):
        self.title = characterprofiles.unescapeText(vals.pop(prefix + "/Title", ""))
        self.x = util.str2int(vals.pop(prefix + "/X", "0"), 0, 0, MAX_COORD)
        self.y = util.str2int(vals.pop(prefix + "/Y", "0"), 0, 0, MAX_COORD)
        self.setWidth(util.str2int(vals.pop(prefix + "/Width", ""), ACT_WIDTH))

        color = vals.pop(prefix + "/Color", "")
        self.color = color.lower() if isValidColor(color) else None

        self.folded = vals.pop(prefix + "/Folded", "0") == "1"

        self.beats = []

        for s in vals.pop(prefix + "/Cards", "").split(","):
            n = util.str2int(s.strip(), 0)

            if (1 <= n <= len(beats)) and (id(beats[n - 1]) not in taken):
                taken.add(id(beats[n - 1]))
                self.beats.append(beats[n - 1])

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
# on top of the ones before it, and the acts
class BeatBoard:
    def __init__(self):
        # list of Beat objects
        self.beats = []

        # list of Act objects, in drawing order (under the cards)
        self.acts = []

    # whether there's anything worth saving
    def hasInfo(self):
        return bool(self.beats or self.acts)

    # the act beat is in, or None
    def actOf(self, beat):
        for act in self.acts:
            if any(b is beat for b in act.beats):
                return act

        return None

    # the cards that are shown: all but those in folded acts
    def shownBeats(self):
        hidden = {id(b) for act in self.acts if act.folded for b in act.beats}

        return [b for b in self.beats if id(b) not in hidden]

    # take the cards in the list 'beats' off the board, and out of their
    # acts
    def remove(self, beats):
        ids = {id(b) for b in beats}
        self.beats = [b for b in self.beats if id(b) not in ids]
        self.takeOut(beats)

    # take the cards in the list 'beats' out of their acts, leaving them
    # on the board where they are
    def takeOut(self, beats):
        ids = {id(b) for b in beats}

        for act in self.acts:
            act.beats = [b for b in act.beats if id(b) not in ids]

    # lay out every act's cards (see Act.layout)
    def layout(self, sizeOf):
        for act in self.acts:
            act.layout(sizeOf)

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

        count = util.str2int(vals.pop("Acts", "0"), 0, 0, 100000)

        self.acts = []
        taken = set()

        for i in range(1, count + 1):
            act = Act()
            act.load(vals, "Act/%d" % i, self.beats, taken)
            self.acts.append(act)

    # save to a string and return that.
    def save(self):
        s = "Beats:%d\n" % len(self.beats)
        numbers = {}

        for i, beat in enumerate(self.beats):
            s += beat.save("Beat/%d" % (i + 1))
            numbers[id(beat)] = i + 1

        if self.acts:
            s += "Acts:%d\n" % len(self.acts)

            for i, act in enumerate(self.acts):
                s += act.save("Act/%d" % (i + 1), numbers)

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
