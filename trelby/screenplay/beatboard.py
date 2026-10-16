# the beat board: index cards ("beats") laid out freely on a canvas, for
# planning a story before or while writing it. a card is just text in a
# place on the board, and it can be linked to a scene in the script.
#
# the link is loose on purpose. linking gives the scene's heading line a
# scene id (Line.sceneId, see Screenplay.getSceneId), and the card keeps
# that id. the id moves with the heading when the scene is edited, moved
# or cut and pasted, and the card finds its scene again by it
# (Screenplay.findSceneId). when the scene is deleted, the card stays on
# the board, shown as linked to a missing scene, and unlinking it is
# always one click. ids that no card refers to any more aren't saved.

import re

import trelby.screenplay.characterprofiles as characterprofiles
import trelby.mypickle as mypickle
import trelby.undo as undo
import trelby.util as util
from trelby.screenplay.datatypes import isValidColor

# size of a card on the board, in the board's units (unscaled pixels)
CARD_WIDTH = 200
CARD_HEIGHT = 120

# space between cards that are laid out automatically
GAP = 20

# the board's coordinates are kept within this, so that a damaged file
# can't put a card somewhere unreachable
MAX_COORD = 100000


# return True if s is a valid scene id: a positive number
def isValidSceneId(s):
    return re.fullmatch("[1-9][0-9]{0,8}", s) is not None


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

        # the id of the scene the card is linked to (see the top of the
        # module), or None if it's not linked
        self.sceneId = None

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

    def save(self, prefix):
        s = "%s/X:%d\n%s/Y:%d\n" % (prefix, self.x, prefix, self.y)

        if self.text:
            s += "%s/Text:%s\n" % (prefix, characterprofiles.escapeText(self.text))

        if self.color:
            s += "%s/Color:%s\n" % (prefix, self.color)

        if self.sceneId:
            s += "%s/Scene:%s\n" % (prefix, self.sceneId)

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

        sceneId = vals.pop(prefix + "/Scene", "")
        self.sceneId = sceneId if isValidSceneId(sceneId) else None

        start = prefix + "/"

        for name in [n for n in vals if n.startswith(start)]:
            self.extra[name[len(start) :]] = vals.pop(name)


# all the cards of a single screenplay, in drawing order: a card is drawn
# on top of the ones before it
class BeatBoard:
    def __init__(self):
        # list of Beat objects
        self.beats = []

    # whether there's anything worth saving
    def hasInfo(self):
        return bool(self.beats)

    # the ids of the scenes the cards are linked to
    def getSceneIds(self):
        return {b.sceneId for b in self.beats if b.sceneId}

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


# return a scene id that's not in 'used', a collection of scene ids
def newSceneId(used):
    return str(max([int(s) for s in used], default=0) + 1)


# return the ids of all the lines in sp that have one, including those
# left on lines that aren't scene headings any more, which would come
# back if the line was made one again
def usedSceneIds(sp):
    return {ln.sceneId for ln in sp.lines if ln.sceneId}


# return (x, y), a place for a new card on 'board' that overlaps no other
# card: the first free one in a grid of 'columns' cards per row, going
# left to right and then down.
def findFreeSpot(board, columns=5):
    stepX = CARD_WIDTH + GAP
    stepY = CARD_HEIGHT + GAP

    def isFree(x, y):
        return not any(
            (abs(b.x - x) < stepX) and (abs(b.y - y) < stepY) for b in board.beats
        )

    # a card overlaps at most four spots of the grid, so one of these is
    # always free
    i = 0

    while True:
        x = GAP + (i % columns) * stepX
        y = GAP + (i // columns) * stepY

        if isFree(x, y):
            return (x, y)

        i += 1


# the Editor's side: replacing the board as one undoable edit
class BeatBoardEditMixin:
    # replace the script's beat board with 'board', and give the scenes in
    # 'newIds' ({line: id}, line being the first line of a scene heading
    # or act break) the ids the board's new links use. both are one undo
    # step. returns False if nothing would change.
    def setBeatBoard(self, board, newIds=None):
        newIds = {
            i: sid
            for i, sid in (newIds or {}).items()
            if self.sp.getSceneId(i) != sid
        }

        if (board.save() == self.sp.beatBoard.save()) and not newIds:
            return False

        u = undo.BeatBoard(self)

        for i, sid in newIds.items():
            self.sp.lines[i].sceneId = sid

        self.sp.beatBoard = board
        self.sp.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)

        return True
