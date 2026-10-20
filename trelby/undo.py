import copy
import zlib

import trelby.screenplay.revisions as revisions
from trelby.screenplay.line import Line

# Which command uses which undo object:
#
# command                type
# -------                ------
#
# removeElementTypes     FullCopy
# addChar                SinglePara (possibly merged)
#   charmap
#   namesDlg
# spellCheck             SinglePara
# findAndReplace         SinglePara
# NewElement             ManyElems(1, 2)
# Tab:
#   (end of elem)        ManyElems(1, 2)
#   (middle of elem)     ManyElems(1, 1)
# TabPrev                ManyElems(1, 1)
# insertForcedLineBreak  ManyElems(1, 1)
# deleteForward:
#   (not end of elem)    ManyElems(1, 1) (possibly merged)
#   (end of elem)        ManyElems(2, 1)
# deleteBackward:
#   (not start of elem)  ManyElems(1, 1) (possibly merged)
#   (start of elem)      ManyElems(2, 1)
# convertTypeTo          ManyElems(N, N)
# cut                    AnyDifference
# paste                  AnyDifference
# (MCP) scene edits      AnyDifference (move: moveSceneTo's own)
# (MCP) world building   WorldBuildingText
# (MCP) char. profiles   CharacterProfiles
# beat board             BeatBoard
# addNote / setNote /    SinglePara
#   deleteNote
# renameCharacters       RenameCharacters (a FullCopy)


# extremely rough estimate for the base memory usage of a single undo
# object, WITHOUT counting the actual textual differences stored inside
# it. so this figure accounts for the Python object overhead, member
# variable overhead, memory allocation overhead, etc.
#
# this figure does not need to be very accurate.
BASE_MEMORY_USAGE = 1500

# possible command types. only used for possibly merging consecutive
# edits.
(CMD_ADD_CHAR, CMD_ADD_CHAR_SPACE, CMD_DEL_FORWARD, CMD_DEL_BACKWARD, CMD_MISC) = list(
    range(5)
)


# convert a list of Screenplay.Line objects into an unspecified, but
# compact, form of storage. storage2lines will convert this back to the
# original form.
#
# the return type is a tuple: (numberOfLines, ...). the number and type of
# elements after the first is of no concern to the caller.
#
# implementation notes:
#
#   tuple[1]: bool; True if tuple[2] is zlib-compressed
#
#   tuple[2]: string; the line objects converted to their string
#   representation and joined by the "\n" character
#
#   tuple[3]: dict of {index: pageLock} for the lines that have a page
#   lock, or None if none do
#
#   tuple[4]: tuple of indexes of the lines that have the dual flag set,
#   or None if none do
#
#   tuple[5]: dict of {index: color} for the lines that have a color, or
#   None if none do
#
#   tuple[6]: dict of {index: fmt} for the lines that have formatting, or
#   None if none do
#
#   tuple[7]: tuple of indexes of the lines that have the centered flag
#   set, or None if none do
#
#   tuple[8]: dict of {index: sceneLock} for the lines that have a scene
#   lock, or None if none do
#
#   tuple[9]: dict of {index: notes} for the lines that have notes, or
#   None if none do. the notes are immutable, so they're shared.
#
#   tuple[10]: dict of {index: revs} for the lines that have revision
#   marks, or None if none do
#
#   tuple[11]: dict of {index: synopsis} for the lines that have a
#   synopsis, or None if none do
#
def lines2storage(lines):
    if not lines:
        return (0,)

    locks = {i: ln.pageLock for i, ln in enumerate(lines) if ln.pageLock}
    duals = tuple(i for i, ln in enumerate(lines) if ln.dual) or None
    colors = {i: ln.color for i, ln in enumerate(lines) if ln.color} or None
    fmts = {i: ln.fmt for i, ln in enumerate(lines) if ln.fmt} or None
    centers = tuple(i for i, ln in enumerate(lines) if ln.centered) or None
    sceneLocks = {i: ln.sceneLock for i, ln in enumerate(lines) if ln.sceneLock}
    notes = {i: ln.notes for i, ln in enumerate(lines) if ln.notes} or None
    revs = {i: ln.revs for i, ln in enumerate(lines) if ln.revs} or None
    synopses = {i: ln.synopsis for i, ln in enumerate(lines) if ln.synopsis} or None

    # str(ln) only holds the line break, type and text, which is all
    # Line.fromStr can restore, so every other Line attribute travels in
    # the side tables above. a new Line attribute must be added there (as
    # well as to Line.copy, Line.__ne__ and mcptools.linesRevision), or
    # undo silently drops it.
    lines = [str(ln) for ln in lines]
    linesStr = "\n".join(lines)

    # instead of having an arbitrary cutoff figure ("compress if < X
    # bytes"), always compress, but only use the compressed version if
    # it's shorter than the non-compressed one.

    linesStrCompressed = zlib.compress(linesStr.encode(), 6)

    locks = locks or None

    if len(linesStrCompressed) < len(linesStr):
        data = (True, linesStrCompressed)
    else:
        data = (False, linesStr.encode())

    return (len(lines),) + data + (
        locks,
        duals,
        colors,
        fmts,
        centers,
        sceneLocks or None,
        notes,
        revs,
        synopses,
    )


# see lines2storage.
def storage2lines(storage):
    if storage[0] == 0:
        return []

    if storage[1]:
        linesStr = zlib.decompress(storage[2]).decode()
    else:
        linesStr = storage[2].decode()

    lines = [Line.fromStr(s) for s in linesStr.split("\n")]

    if storage[3]:
        for i, label in storage[3].items():
            lines[i].pageLock = label

    if storage[4]:
        for i in storage[4]:
            lines[i].dual = True

    if storage[5]:
        for i, color in storage[5].items():
            lines[i].color = color

    if storage[6]:
        for i, fmt in storage[6].items():
            lines[i].fmt = fmt

    if storage[7]:
        for i in storage[7]:
            lines[i].centered = True

    if storage[8]:
        for i, label in storage[8].items():
            lines[i].sceneLock = label

    if storage[9]:
        for i, notes in storage[9].items():
            lines[i].notes = notes

    if storage[10]:
        for i, revs in storage[10].items():
            lines[i].revs = revs

    if storage[11]:
        for i, synopsis in storage[11].items():
            lines[i].synopsis = synopsis

    return lines


# whether any of the lines in the given storage has revision marks
def hasRevs(storage):
    return (storage[0] != 0) and bool(storage[10])


# an edit replaced the lines 'before' (a list of Lines, or a storage
# tuple) with ed.sp.lines[start:end]: give those their revision marks (see
# revisions.carry), unless there are none to carry and revision mode is
# off
def carryRevisions(ed, before, start, end):
    level = ed.sp.revisions.markingLevel()

    if isinstance(before, tuple):
        if not level and not hasRevs(before):
            return

        before = storage2lines(before)

    elif not level and not any(ln.revs for ln in before):
        return

    revisions.carry(before, ed.sp.lines[start:end], level)


# how much memory is used by the given storage object
def memoryUsed(storage):
    # 16 is a rough estimate for the first two tuple members' memory usage

    if storage[0] == 0:
        return 16

    return 16 + len(storage[2])


# abstract base class for storing undo history. concrete subclasses
# implement undo/redo for specific actions taken on a screenplay.
class Base:
    def __init__(self, ed, cmdType):
        # cursor position before the action
        self.startPos = ed.cursorAsMark()

        # type of action; one of the CMD_ values
        self.cmdType = cmdType

        # prev/next undo objects in the history
        self.prev = None
        self.next = None

    # set cursor position after the action
    def setEndPos(self, ed):
        self.endPos = ed.cursorAsMark()

    def getType(self):
        return self.cmdType

    # rough estimate of how much memory is used by this undo object. can
    # be overridden by subclasses that need something different.
    def memoryUsed(self):
        return (
            BASE_MEMORY_USAGE
            + memoryUsed(self.linesBefore)
            + memoryUsed(self.linesAfter)
        )

    # default implementation for undo. can be overridden by subclasses
    # that need something different.
    #
    # subclasses using it set elemStartLine and linesBefore / linesAfter
    # (lines2storage tuples, whose [0] is the line count). undo replaces
    # the linesAfter[0] lines at elemStartLine with linesBefore, and redo
    # the other way around. these are absolute line indexes, so they're
    # only right if ed.sp.lines is exactly as this object left it: undo/redo
    # must go strictly through the history in order, and every change to
    # ed.sp.lines must be recorded with ed.undoHistory.add. anything that
    # changes lines without doing so (like reformatAll) must clear the
    # history first.
    def undo(self, ed):
        ed.line, ed.column = self.startPos.line, self.startPos.column

        ed.sp.lines[self.elemStartLine : self.elemStartLine + self.linesAfter[0]] = (
            storage2lines(self.linesBefore)
        )

    # default implementation for redo. can be overridden by subclasses
    # that need something different.
    def redo(self, ed):
        ed.line, ed.column = self.endPos.line, self.endPos.column

        ed.sp.lines[self.elemStartLine : self.elemStartLine + self.linesBefore[0]] = (
            storage2lines(self.linesAfter)
        )


# stores a full copy of the screenplay before/after the action. used by
# actions that modify the screenplay globally.
#
# we store the line data as compressed text, not as a list of Line
# objects, because it takes much less memory to do so. figures from a
# 32-bit machine (a 64-bit machine wastes even more space storing Line
# objects) from speedTest for a 120-page screenplay (Casablanca):
#
#   -Line objects:         1,737 KB, 0.113s
#   -text, not compressed:   267 KB, 0.076s
#   -text, zlib fastest(1):  127 KB, 0.090s
#   -text, zlib medium(6):   109 KB, 0.115s
#   -text, zlib best(9):     107 KB, 0.126s
#   -text, bz2 best(9):       88 KB, 0.147s
class FullCopy(Base):
    def __init__(self, ed):
        Base.__init__(self, ed, CMD_MISC)

        self.elemStartLine = 0
        self.linesBefore = lines2storage(ed.sp.lines)

    # called after editing action is over to snapshot the "after" state.
    # like every undo object, it first carries the revision marks over to
    # the changed lines (see carryRevisions), unless carry is False.
    def setAfter(self, ed, carry=True):
        if carry:
            carryRevisions(ed, self.linesBefore, 0, len(ed.sp.lines))

        self.linesAfter = lines2storage(ed.sp.lines)
        self.setEndPos(ed)


# renaming characters: a FullCopy of the lines, plus the character
# profiles that were renamed, as a list of (old name, new name). undo
# renames those profiles back.
class RenameCharacters(FullCopy):
    def __init__(self, ed, profileRenames):
        FullCopy.__init__(self, ed)

        self.profileRenames = profileRenames

    def undo(self, ed):
        FullCopy.undo(self, ed)
        renameProfiles(ed.sp, [(new, old) for old, new in self.profileRenames])

    def redo(self, ed):
        FullCopy.redo(self, ed)
        renameProfiles(ed.sp, self.profileRenames)


# rename character profiles, given a list of (old name, new name). all
# the profiles are looked up before any is renamed, so names can be
# swapped.
def renameProfiles(sp, renames):
    found = [(sp.characterProfiles.get(old), new) for old, new in renames]

    for prof, new in found:
        if prof:
            prof.name = new


# stores a single modified paragraph
class SinglePara(Base):
    # line is any line belonging to the modified paragraph. there is no
    # requirement for the cursor to be in this paragraph.
    def __init__(self, ed, cmdType, line):
        Base.__init__(self, ed, cmdType)

        self.elemStartLine = ed.sp.getParaFirstIndexFromLine(line)
        endLine = ed.sp.getParaLastIndexFromLine(line)

        self.linesBefore = lines2storage(ed.sp.lines[self.elemStartLine : endLine + 1])

    def setAfter(self, ed):
        # if all we did was modify a single paragraph, the index of its
        # starting line can not have changed, because that would mean one of
        # the paragraphs above us had changed as well, which is a logical
        # impossibility. so we can find the dimensions of the modified
        # paragraph by starting at the first line.

        endLine = ed.sp.getParaLastIndexFromLine(self.elemStartLine)

        carryRevisions(ed, self.linesBefore, self.elemStartLine, endLine + 1)
        self.linesAfter = lines2storage(ed.sp.lines[self.elemStartLine : endLine + 1])

        self.setEndPos(ed)


# stores N modified consecutive elements
class ManyElems(Base):
    # line is any line belonging to the first modified element. there is
    # no requirement for the cursor to be in this paragraph.
    # nrOfElemsStart is how many elements there are before the edit
    # operaton and nrOfElemsEnd is how many there are after. so an edit
    # operation splitting an element would pass in (1, 2) while an edit
    # operation combining two elements would pass in (2, 1).
    def __init__(self, ed, cmdType, line, nrOfElemsStart, nrOfElemsEnd):
        Base.__init__(self, ed, cmdType)

        self.nrOfElemsEnd = nrOfElemsEnd

        self.elemStartLine, endLine = ed.sp.getElemIndexesFromLine(line)

        # find last line of last element to include in linesBefore
        for i in range(nrOfElemsStart - 1):
            endLine = ed.sp.getElemLastIndexFromLine(endLine + 1)

        self.linesBefore = lines2storage(ed.sp.lines[self.elemStartLine : endLine + 1])

    def setAfter(self, ed):
        endLine = ed.sp.getElemLastIndexFromLine(self.elemStartLine)

        for i in range(self.nrOfElemsEnd - 1):
            endLine = ed.sp.getElemLastIndexFromLine(endLine + 1)

        carryRevisions(ed, self.linesBefore, self.elemStartLine, endLine + 1)
        self.linesAfter = lines2storage(ed.sp.lines[self.elemStartLine : endLine + 1])

        self.setEndPos(ed)


# stores a single block of changed lines by diffing before/after states of
# a screenplay
class AnyDifference(Base):
    def __init__(self, ed):
        Base.__init__(self, ed, CMD_MISC)

        # kept as Line copies (not storage) until setAfter, since the diff
        # compares them with Line.__ne__, i.e. all attributes and not just
        # the text. this is a full copy of the script for the duration of
        # the action.
        self.linesBefore = [ln.copy() for ln in ed.sp.lines]

    # [a:b] of the old lines was replaced by [x:y] of the new ones (a ==
    # x). only that block is stored, and undo / redo swap it back in, so
    # unlike the other classes these don't use elemStartLine.
    #
    # a locked scene that the edit deleted is left as an OMITTED scene
    # (see Screenplay.omitDeletedScenes). in revision mode the block gets
    # an unchanged line on each side, so that deleting whole lines can
    # mark the line next to them (see revisions.carry).
    def setAfter(self, ed):
        ed.sp.omitDeletedScenes(self.linesBefore, ed)

        before = self.linesBefore
        lines = ed.sp.lines
        a, b, x, y = mySequenceMatcher(before, lines)

        if ed.sp.revisions.markingLevel():
            if a > 0:
                a -= 1
                x -= 1

            if (b < len(before)) and (y < len(lines)):
                b += 1
                y += 1

        carryRevisions(ed, before[a:b], x, y)
        self.a, self.b, self.x, self.y = a, b, x, y

        self.removed = lines2storage(self.linesBefore[self.a : self.b])
        self.inserted = lines2storage(ed.sp.lines[self.x : self.y])

        self.setEndPos(ed)

        del self.linesBefore

    def memoryUsed(self):
        return BASE_MEMORY_USAGE + memoryUsed(self.removed) + memoryUsed(self.inserted)

    def undo(self, ed):
        ed.line, ed.column = self.startPos.line, self.startPos.column

        ed.sp.lines[self.x : self.y] = storage2lines(self.removed)

    def redo(self, ed):
        ed.line, ed.column = self.endPos.line, self.endPos.column

        ed.sp.lines[self.a : self.b] = storage2lines(self.inserted)


# a change to the text of the script's world building notes, which are
# not part of the lines. the cursor is left where it is.
class WorldBuildingText(Base):
    def __init__(self, ed):
        Base.__init__(self, ed, CMD_MISC)

        self.textBefore = ed.sp.worldBuilding.text

    def setAfter(self, ed):
        self.textAfter = ed.sp.worldBuilding.text
        self.setEndPos(ed)

    def memoryUsed(self):
        return BASE_MEMORY_USAGE + len(self.textBefore) + len(self.textAfter)

    def undo(self, ed):
        ed.sp.worldBuilding.text = self.textBefore

    def redo(self, ed):
        ed.sp.worldBuilding.text = self.textAfter


# a change to the script's character profiles, which are not part of the
# lines. the cursor is left where it is.
class CharacterProfiles(Base):
    def __init__(self, ed):
        Base.__init__(self, ed, CMD_MISC)

        # photos are immutable bytes, so these copies share them
        self.before = copy.deepcopy(ed.sp.characterProfiles)

    def setAfter(self, ed):
        self.after = copy.deepcopy(ed.sp.characterProfiles)
        self.setEndPos(ed)

    def memoryUsed(self):
        return BASE_MEMORY_USAGE + sum(
            len(p.name) + len(p.notes)
            for p in self.before.profiles + self.after.profiles
        )

    def undo(self, ed):
        ed.sp.characterProfiles = copy.deepcopy(self.before)

    def redo(self, ed):
        ed.sp.characterProfiles = copy.deepcopy(self.after)


# a change to the script's beat board, which is not part of the lines.
# the cursor is left where it is.
class BeatBoard(Base):
    def __init__(self, ed):
        Base.__init__(self, ed, CMD_MISC)

        self.before = copy.deepcopy(ed.sp.beatBoard)

    def setAfter(self, ed):
        self.after = copy.deepcopy(ed.sp.beatBoard)
        self.setEndPos(ed)

    def memoryUsed(self):
        return (
            BASE_MEMORY_USAGE + len(self.before.save()) + len(self.after.save())
        )

    def undo(self, ed):
        ed.sp.beatBoard = copy.deepcopy(self.before)

    def redo(self, ed):
        ed.sp.beatBoard = copy.deepcopy(self.after)


# Our own implementation of difflib.SequenceMatcher, since the actual one
# is too slow for our custom needs.
#
# l1, l2 = lists to diff. List elements must have __ne__ defined.
#
# Return a, b, x, y such that l1[a:b] could be replaced with l2[x:y] to
# convert l1 into l2.
#
# it only strips the longest common prefix and then the longest common
# suffix, so it finds a single changed block (a == x always): two
# separate changes far apart yield one block spanning both. the suffix
# scan is capped at the end of the prefix, so the block in the shorter
# list never ends before it starts (d >= a below). the work is done on
# (bigger, smaller), and the final swap maps the ends back to (l1, l2).
def mySequenceMatcher(l1, l2):
    len1 = len(l1)
    len2 = len(l2)

    if len1 >= len2:
        bigger = l1
        smaller = l2
        bigLen = len1
        smallLen = len2
        l1Big = True
    else:
        bigger = l2
        smaller = l1
        bigLen = len2
        smallLen = len1
        l1Big = False

    i = 0
    a = b = 0

    m1found = False

    while a < smallLen:
        if not m1found and (bigger[a] != smaller[a]):
            b = a
            m1found = True
            break

        a += 1

    if not m1found:
        a = b = smallLen

    num = smallLen - a + 1
    i = 1
    c = bigLen
    d = smallLen

    while (i <= num) and (i <= smallLen):
        c = bigLen - i + 1
        d = smallLen - i + 1

        if bigger[-i] != smaller[-i]:
            break

        i += 1

    if not l1Big:
        a, c, b, d = a, d, b, c

    return a, c, b, d
