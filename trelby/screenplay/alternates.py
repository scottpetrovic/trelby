# alternates: other versions ("takes") of an element's text, like Fade
# In's and Final Draft's alternate dialogue. the writer keeps several
# wordings of a line of dialogue (or any other element) and switches
# which one is in the script; the others are kept out of sight.
#
# the shown take is the element's normal text, so pagination, the
# exports, the reports and spell checking need to know nothing about
# alternates. the other takes are kept in Line.alternates (a tuple of
# Take) on the element's first line, and carried with its text like the
# notes are (see notes.py): rewrapPara gathers a paragraph's onto its
# first line, joining keeps both's, cut and paste, undo and the file keep
# them with the lines, and they go away only when all of the element's
# text is deleted. so in the middle of editing they can end up on a later
# paragraph of their element (e.g. after joining two elements, or
# splitting at an element's start); getAlternates gathers them from the
# whole element, and every edit below puts them back on its first line.
#
# what happens to them in edits that change the element:
#
#   - type changes keep them: alternates aren't only for dialogue.
#   - splitting an element (Enter) leaves them on its first part, unless
#     it's split at its very start, when they go with the text.
#   - joining two elements keeps both's, the first one's first.
#
# a take is the element's whole text, with "\n" between its paragraphs
# (forced line breaks), and its formatting.

from dataclasses import dataclass

import trelby.config as config
import trelby.screenplay.pagelock as pagelock
import trelby.textfmt as textfmt
import trelby.textutil as textutil
import trelby.undo as undo
from trelby.screenplay.constants import LB_FORCED, LB_LAST
from trelby.screenplay.line import Line


# one version of an element's text. it's an immutable value, so lines and
# undo objects can share them.
@dataclass(frozen=True)
class Take:
    # the text, "\n" separating its paragraphs
    text: str

    # its format string (see textfmt), exactly as long as text, "\n"s
    # included, or None if it has no formatting
    fmt: str = None

    # the take's text on one line, shortened to at most n characters, for
    # menus and lists
    def preview(self, n=60):
        s = self.text.replace("\n", " / ")

        if len(s) > n:
            s = s[: n - 3].rstrip() + "..."

        return s


# text typed or pasted as a take, tidied up like an element's text: tabs
# become spaces, each paragraph is stripped, and empty paragraphs at
# either end dropped
def cleanText(text):
    parts = [
        textutil.toInputStr(p.replace("\t", " ")).strip()
        for p in textutil.fixNL(text).split("\n")
    ]

    while parts and not parts[0]:
        parts.pop(0)

    while parts and not parts[-1]:
        parts.pop()

    return "\n".join(parts)


# a Take of text, keeping the formatting of 'old' (a Take or None) if the
# text didn't change
def makeTake(text, old=None):
    text = cleanText(text)

    if old and (old.text == text):
        return old

    return Take(text)


# the Screenplay's side: finding alternates
class AlternatesMixin:
    # return the other takes of the element containing line i
    def getAlternates(self, i):
        first, last = self.getElemIndexesFromLine(i)

        return sum((self.lines[k].alternates for k in range(first, last + 1)), ())

    # return the shown take of the element containing line i: its text,
    # its paragraphs separated by "\n", and its formatting
    def getShownTake(self, i):
        first, last = self.getElemIndexesFromLine(i)
        ls = self.lines

        text = ""
        parts = []
        seps = []

        for k in range(first, last + 1):
            text += ls[k].text
            parts.append((ls[k].text, ls[k].fmt))

            if k != last:
                sep = "\n" if ls[k].lb == LB_FORCED else config.lb2str(ls[k].lb)
                text += sep
                seps.append(sep)

        return Take(text, textfmt.join(parts, seps))

    def hasAlternates(self):
        return any(ln.alternates for ln in self.lines)

    # lines del1 - del2 are about to be deleted. the takes on them whose
    # element goes on after del2 (its text isn't all deleted) are moved to
    # line del2 + 1, which stays in that element. (see
    # NotesMixin.moveNotesForward, which does the same per paragraph)
    def moveAlternatesForward(self, del1, del2):
        ls = self.lines

        if del2 + 1 >= len(ls):
            return

        moved = ()

        for i in range(del1, del2 + 1):
            if ls[i].alternates and not any(
                ls[k].lb == LB_LAST for k in range(i, del2 + 1)
            ):
                moved += ls[i].alternates

        if moved:
            ls[del2 + 1].alternates = moved + ls[del2 + 1].alternates


# the paragraphs of the element lines[first:last + 1], as lists of their
# lines' indexes
def _paragraphs(lines, first, last):
    ret = [[]]

    for k in range(first, last + 1):
        ret[-1].append(k)

        if (lines[k].lb == LB_FORCED) and (k != last):
            ret.append([])

    return ret


# the Editor's side: each edit is one undo step. 'line' is any line of
# the element, and 'index' a take's index among its other takes (as
# returned by getAlternates).
class AlternatesEditMixin:
    # replace the element at lines first - last with 'take', unwrapped
    # (the caller rewraps it). the first line's attributes stay, the notes
    # and tags of each paragraph go on the same paragraph of the new text
    # (or its last one), and so do the page locks, at the same offset or
    # the paragraph's end. returns the index of the element's last line.
    def _putTake(self, first, last, take):
        ls = self.sp.lines
        old = ls[first]
        paras = _paragraphs(ls, first, last)

        texts = take.text.split("\n")
        fmt = textfmt.fit(take.fmt, len(take.text)) if take.fmt else None

        new = []
        pos = 0

        for text in texts:
            ln = Line(LB_FORCED, old.lt)
            ln.setText(text, fmt[pos : pos + len(text)] if fmt else None)
            pos += len(text) + 1
            new.append(ln)

        new[-1].lb = LB_LAST

        new[0].dual = old.dual
        new[0].color = old.color
        new[0].centered = old.centered
        new[0].sceneLock = old.sceneLock
        new[0].synopsis = old.synopsis

        for n, para in enumerate(paras):
            target = new[min(n, len(new) - 1)]
            offset = 0

            for k in para:
                target.notes += ls[k].notes
                target.tags += ls[k].tags

                label = ls[k].pageLock

                if label:
                    col = offset + getattr(ls[k], "pageLockCol", 0)

                    if target.pageLock:
                        target.pageLock = pagelock.combine(target.pageLock, label)
                    else:
                        target.pageLock = label
                        target.pageLockCol = min(col, len(target.text))

                offset += len(ls[k].text) + len(config.lb2str(ls[k].lb))

        ls[first : last + 1] = new

        return first + len(new) - 1

    # the one edit everything below is made of: show 'shown' (a Take) in
    # the element containing line, if it isn't already shown, and keep
    # 'others' (Takes) as its other takes. the cursor, if it's in the
    # element and its text changes, goes to the element's start; below
    # it, it stays on the same text. returns False if nothing changed.
    def setTakes(self, line, shown, others):
        sp = self.sp
        ls = sp.lines
        others = tuple(t for t in others if t.text)
        first, last = sp.getElemIndexesFromLine(line)

        current = sp.getShownTake(line)
        changeText = (shown.text != current.text) or (
            textfmt.compact(shown.fmt) != current.fmt
        )

        if not changeText and (others == sp.getAlternates(line)):
            return False

        u = undo.ManyElems(self, undo.CMD_MISC, first, 1, 1)

        for k in range(first, last + 1):
            ls[k].alternates = ()

        if changeText:
            cursorIn = first <= self.line <= last
            below = self.line > last
            oldCount = last - first + 1

            last = self._putTake(first, last, shown)

            # rewrap each paragraph, from the last, so that the indexes of
            # the ones before don't move
            starts = [first] + [
                k + 1 for k in range(first, last) if ls[k].lb == LB_FORCED
            ]

            for k in reversed(starts):
                sp.rewrapPara(k)

            newLast = sp.getElemLastIndexFromLine(first)

            if cursorIn:
                self.line = first
                self.column = 0
            elif below:
                self.line += newLast - first + 1 - oldCount

            self.clearMark()

        ls[first].alternates = others
        sp.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)

        return True

    # keep the shown text of the element containing line as one of its
    # other takes too (the writer then changes the shown one), or 'take'
    # if given. returns the new take's index, or None if the element has
    # no text or already has that take.
    def addAlternate(self, line, take=None):
        take = take or self.sp.getShownTake(line)
        alts = self.sp.getAlternates(line)

        if not take.text or any(t.text == take.text for t in alts):
            return None

        self.setTakes(line, self.sp.getShownTake(line), alts + (take,))

        return len(alts)

    # replace a take with 'take'. returns False if that wouldn't change
    # anything (or would empty it).
    def setAlternate(self, line, index, take):
        alts = list(self.sp.getAlternates(line))

        if (alts[index] == take) or not take.text:
            return False

        alts[index] = take

        return self.setTakes(line, self.sp.getShownTake(line), alts)

    def deleteAlternate(self, line, index):
        alts = list(self.sp.getAlternates(line))
        del alts[index]
        self.setTakes(line, self.sp.getShownTake(line), alts)

    # show the take at 'index' in place of the shown text. the takes are
    # kept in a ring, the shown one first: switching rotates it so that
    # take 'index' comes first and the order stays the same, so switching
    # to take 0 again and again goes through all of them and back.
    def switchAlternate(self, line, index):
        ring = (self.sp.getShownTake(line),) + self.sp.getAlternates(line)
        k = index + 1
        ring = ring[k:] + ring[:k]

        return self.setTakes(line, ring[0], ring[1:])

    # show the next take of the element containing line (or the previous
    # one, if step is -1). returns False if it has no other takes.
    def cycleAlternate(self, line, step=1):
        alts = self.sp.getAlternates(line)

        if not alts:
            return False

        return self.switchAlternate(line, 0 if step > 0 else len(alts) - 1)

    # show the take at 'index' (or keep the shown one, if index is None)
    # and drop all the others
    def keepAlternate(self, line, index=None):
        if index is None:
            shown = self.sp.getShownTake(line)
        else:
            shown = self.sp.getAlternates(line)[index]

        return self.setTakes(line, shown, ())
