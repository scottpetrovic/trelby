# notes on the script's text: the writer's reminders, or the notes from a
# producer or a reader, shown in the notes sidebar rather than in the
# script. they're never printed.
#
# a note is attached to a paragraph, and kept in Line.notes on its first
# line, so it stays with that text as the script is edited: rewrapPara
# gathers the notes of a paragraph's lines onto its new first line (joining
# two paragraphs keeps both's notes), and the notes of a paragraph go away
# only when all of its text is deleted. undo, cut and paste, and the file
# keep them with the lines (see undo.lines2storage, fileformat).
#
# scripts used to have a note element type (NOTE) instead. note elements
# in old files and in imported ones become notes on the element before
# them (absorbNoteElements).

from dataclasses import dataclass, replace

import trelby.config as config
import trelby.screenplay.pagelock as pagelock
import trelby.undo as undo
from trelby.screenplay.constants import (
    ACTION,
    LB_FORCED,
    LB_LAST,
    NOTE,
)
from trelby.screenplay.line import Line


# one note. it's an immutable value, so lines and undo objects can share
# them; a changed note is a new one (see Note.replace).
@dataclass(frozen=True)
class Note:
    # the note's text, which can have several lines
    text: str

    # whether the note has been dealt with. resolved notes are shown
    # dimmed in the sidebar.
    resolved: bool = False

    def replace(self, **changes):
        return replace(self, **changes)


# return the text of the element starting at lines[i] with its line
# breaks turned back into what was typed, and the index of its last line
def _elemText(lines, i):
    s = ""

    while True:
        s += lines[i].text

        if lines[i].lb == LB_LAST:
            return s, i

        s += config.lb2str(lines[i].lb)
        i += 1


# return page lock labels a and b (either can be None) as one
def combineLocks(a, b):
    if a and b:
        return pagelock.combine(a, b)

    return a or b


# turn the note elements in 'lines', a list of Lines (wrapped or not),
# into notes on the element before each (on its first paragraph), or the
# one after for notes before anything else. lines is changed in place.
# page locks on removed lines move to the next line kept. if cursor
# (anything with line / column) is given, it's kept on the same text, or
# put at the start of the line after a removed note. returns True if
# anything was changed.
def absorbNoteElements(lines, cursor=None):
    if not any(ln.lt == NOTE for ln in lines):
        return False

    out = []

    # index in out of the first line of the last element added, or None
    lastElem = None

    # notes found before the first non-note line
    pending = ()

    # page lock of removed lines, to put on the next line kept
    label = None

    # the cursor's line in out, once it's been passed
    cursorLine = None

    i = 0

    while i < len(lines):
        ln = lines[i]

        if ln.lt == NOTE:
            text, last = _elemText(lines, i)
            text = text.strip()

            for k in range(i, last + 1):
                label = combineLocks(label, lines[k].pageLock)

            if (cursor is not None) and (i <= cursor.line <= last):
                cursorLine = len(out)
                cursor.column = 0

            if text:
                note = Note(text)

                if lastElem is None:
                    pending += (note,)
                else:
                    out[lastElem].notes += (note,)

            i = last + 1

            continue

        if label:
            ln.pageLock = combineLocks(label, ln.pageLock)
            label = None

        if (cursor is not None) and (i == cursor.line):
            cursorLine = len(out)

        if not out or (out[-1].lb == LB_LAST):
            lastElem = len(out)

        out.append(ln)
        i += 1

    if not out:
        out.append(Line(LB_LAST, ACTION))

    if pending:
        out[0].notes = pending + out[0].notes

    # a page lock left over from notes at the end is dropped, like
    # removeElementTypes does
    lines[:] = out

    if cursor is not None:
        if cursorLine is None or cursorLine >= len(out):
            cursorLine = len(out) - 1
            cursor.column = 0

        cursor.line = cursorLine
        cursor.column = min(cursor.column, len(out[cursorLine].text))

    return True


# the Screenplay's side: finding notes
class NotesMixin:
    # return the notes of the paragraph containing line i
    def getParaNotes(self, i):
        first = self.getParaFirstIndexFromLine(i)
        last = self.getParaLastIndexFromLine(i)

        ret = ()

        for k in range(first, last + 1):
            ret += self.lines[k].notes

        return ret

    # return a list of (line, index, Note) of every note in the script, in
    # the order they're in. line is the line the note is on, the first
    # line of its paragraph, and index its index in that line's notes.
    def getAllNotes(self):
        return [
            (i, k, note)
            for i, ln in enumerate(self.lines)
            for k, note in enumerate(ln.notes)
        ]

    def hasNotes(self):
        return any(ln.notes for ln in self.lines)

    # lines del1 - del2 are about to be deleted. the notes on them whose
    # paragraph goes on after del2 (its text isn't all deleted) are moved
    # to line del2 + 1, which stays in that paragraph.
    def moveNotesForward(self, del1, del2):
        ls = self.lines

        if del2 + 1 >= len(ls):
            return

        moved = ()

        for i in range(del1, del2 + 1):
            if ls[i].notes and not any(
                ls[k].lb in (LB_LAST, LB_FORCED) for k in range(i, del2 + 1)
            ):
                moved += ls[i].notes

        if moved:
            ls[del2 + 1].notes = moved + ls[del2 + 1].notes


# the Editor's side: adding, changing and deleting notes, each as one undo
# step. the cursor stays where it is. 'line' is any line of the paragraph,
# and 'index' the note's index among the paragraph's notes (as returned by
# getParaNotes).
class NotesEditMixin:
    # gather the paragraph's notes onto its first line, which they should
    # already be on, and return the index of that line
    def _noteParaStart(self, line):
        ls = self.sp.lines
        first = self.sp.getParaFirstIndexFromLine(line)
        notes = self.sp.getParaNotes(line)

        for k in range(first, self.sp.getParaLastIndexFromLine(line) + 1):
            ls[k].notes = ()

        ls[first].notes = notes

        return first

    def _setParaNotes(self, line, notes):
        u = undo.SinglePara(self, undo.CMD_MISC, line)

        first = self._noteParaStart(line)
        self.sp.lines[first].notes = tuple(notes)
        self.sp.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)

    # add a note with the given text to the paragraph containing line.
    # returns the note's index among the paragraph's notes.
    def addNote(self, line, text):
        notes = self.sp.getParaNotes(line) + (Note(text),)
        self._setParaNotes(line, notes)

        return len(notes) - 1

    # replace a note with 'note'. returns False if that wouldn't change
    # anything.
    def setNote(self, line, index, note):
        notes = list(self.sp.getParaNotes(line))

        if notes[index] == note:
            return False

        notes[index] = note
        self._setParaNotes(line, notes)

        return True

    def deleteNote(self, line, index):
        notes = list(self.sp.getParaNotes(line))
        del notes[index]
        self._setParaNotes(line, notes)
