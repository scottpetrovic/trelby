# queries about the script's structure: which lines make up a paragraph,
# an element, a speech or a scene, what's before and after them, and
# simple statistics (word counts, scene and character names).

import trelby.config as config
import trelby.textutil as textutil
from trelby.screenplay.constants import (
    ACTBREAK,
    CHARACTER,
    DIALOGUE,
    LB_FORCED,
    LB_LAST,
    LB_NONE,
    PAREN,
    SCENE,
)


class StructureMixin:
    # return True if the line is a parenthetical and not the first line of
    # that element (such lines need an extra space of indenting).
    def needsExtraParenIndent(self, line):
        return (self.lines[line].lt == PAREN) and not self.isFirstLineOfElem(line)

    # return the empty space above line i, in tenths of a line (the unit of
    # all vertical spacing here, see paginateRange): its type's
    # beforeSpacing if it starts an element, otherwise its intraSpacing.
    # the text-based exports round it down to whole lines.
    def getSpacingBefore(self, i):
        if i == 0:
            return 0

        tcfg = self.cfg.types[self.lines[i].lt]

        if self.lines[i - 1].lb == LB_LAST:
            return tcfg.beforeSpacing
        else:
            return tcfg.intraSpacing

    def isFirstLineOfElem(self, line):
        return (line == 0) or (self.lines[line - 1].lb == LB_LAST)

    def isLastLineOfElem(self, line):
        return self.lines[line].lb == LB_LAST

    def isOnlyLineOfElem(self, line):
        # this is just "isLastLineOfElem(line) and isFirstLineOfElem(line)"
        # inlined here, since it's 130% faster this way.
        return (self.lines[line].lb == LB_LAST) and (
            (line == 0) or (self.lines[line - 1].lb == LB_LAST)
        )

    # get first index of paragraph
    def getParaFirstIndexFromLine(self, line):
        ls = self.lines

        while 1:
            tmp = line - 1

            if tmp < 0:
                break

            if ls[tmp].lb in (LB_LAST, LB_FORCED):
                break

            line -= 1

        return line

    # get last index of paragraph
    def getParaLastIndexFromLine(self, line):
        ls = self.lines

        while 1:
            if ls[line].lb in (LB_LAST, LB_FORCED):
                break

            if (line + 1) >= len(ls):
                break

            line += 1

        return line

    def getElemFirstIndexFromLine(self, line):
        ls = self.lines

        while 1:
            tmp = line - 1

            if tmp < 0:
                break

            if ls[tmp].lb == LB_LAST:
                break

            line -= 1

        return line

    def getElemLastIndexFromLine(self, line):
        ls = self.lines

        while 1:
            if ls[line].lb == LB_LAST:
                break

            if (line + 1) >= len(ls):
                break

            line += 1

        return line

    def getElemIndexesFromLine(self, line):
        return (
            self.getElemFirstIndexFromLine(line),
            self.getElemLastIndexFromLine(line),
        )

    # for scene CONTINUEDs, an act break ends a scene the same way a new
    # scene heading does.
    def isFirstLineOfScene(self, line):
        if line == 0:
            return True

        ls = self.lines
        lt = ls[line].lt

        if lt not in (SCENE, ACTBREAK):
            return False

        l = ls[line - 1]

        return (l.lt != lt) or (l.lb == LB_LAST)

    def isLastLineOfScene(self, line):
        ls = self.lines

        if ls[line].lb != LB_LAST:
            return False

        if line == (len(ls) - 1):
            return True

        return ls[line + 1].lt in (SCENE, ACTBREAK)

    # is the given line the first line of an act heading, i.e. an act break
    # that's the last one in a run of act breaks, followed by the act
    # itself. in "END OF ACT ONE", "ACT TWO", "INT. HOUSE", it's "ACT TWO";
    # "END OF ACT ONE" isn't one, and neither is an act break that ends
    # the script.
    def isActStart(self, line):
        ls = self.lines

        if (ls[line].lt != ACTBREAK) or not self.isFirstLineOfElem(line):
            return False

        nextLt = self.getTypeOfNextElem(line)

        return (nextLt is not None) and (nextLt != ACTBREAK)

    def getTypeOfPrevElem(self, line):
        line = self.getElemFirstIndexFromLine(line)
        line -= 1

        if line < 0:
            return None

        return self.lines[line].lt

    def getTypeOfNextElem(self, line):
        line = self.getElemLastIndexFromLine(line)
        line += 1

        if line >= len(self.lines):
            return None

        return self.lines[line].lt

    def getSceneIndexesFromLine(self, line):
        top, bottom = self.getElemIndexesFromLine(line)
        ls = self.lines

        while 1:
            if ls[top].lt in (SCENE, ACTBREAK):
                break

            tmp = top - 1
            if tmp < 0:
                break

            top = self.getElemIndexesFromLine(tmp)[0]

        while 1:
            tmp = bottom + 1
            if tmp >= len(ls):
                break

            if ls[tmp].lt in (SCENE, ACTBREAK):
                break

            bottom = self.getElemIndexesFromLine(tmp)[1]

        return (top, bottom)

    # return the number (e.g. "12" or "12A") of the scene the given line
    # is in, i.e. that of the last scene heading at or before it, or ""
    # if there is none (e.g. line is -1).
    def getSceneNumber(self, line):
        ret = ""

        for start, label in self.getSceneLabels():
            if start > line:
                break

            ret = label

        return ret

    # return how many elements one must advance to get from element
    # containing line1 to element containing line2. line1 must be <=
    # line2, and either line can be anywhere in their respective elements.
    # returns 0 if they're in the same element, 1 if they're in
    # consecutive elements, etc.
    def elemsDistance(self, line1, line2):
        ls = self.lines

        count = 0
        line = line1

        while line < line2:
            if ls[line].lb == LB_LAST:
                count += 1

            line += 1

        return count

    # returns true if 'line', which must be the last line on a page, needs
    # (MORE) after it and the next page needs a "SOMEBODY (cont'd)".
    def needsMore(self, line):
        ls = self.lines

        return (
            ls[line].lt in (DIALOGUE, PAREN)
            and (line != (len(ls) - 1))
            and ls[line + 1].lt in (DIALOGUE, PAREN)
        )

    # starting at line, go backwards until a line with type of CHARACTER
    # and lb of LAST is found, and return that line's text, possibly
    # upper-cased if CHARACTER's config for export says so.
    def getPrevSpeaker(self, line):
        ls = self.lines

        while 1:
            if line < 0:
                return "UNKNOWN"

            ln = ls[line]

            if (ln.lt == CHARACTER) and (ln.lb == LB_LAST):
                s = ln.text

                if self.cfg.getType(CHARACTER).export.isCaps:
                    s = textutil.upper(s)

                return s

            line -= 1

    # return total number of characters in script
    def getCharCount(self):
        return sum([len(ln.text) for ln in self.lines])

    # return total number of words in script
    def getWordCount(self):
        # a line broken without a space (LB_NONE) continues the same word
        # on the next line
        parts = []

        for ln in self.lines:
            parts.append(ln.text)

            if ln.lb != LB_NONE:
                parts.append(" ")

        return len("".join(parts).split())

    # return the full text of the element starting at the given line, with
    # line breaks converted to spaces.
    def getElemText(self, line):
        ls = self.lines
        s = ""

        while 1:
            ln = ls[line]
            s += ln.text

            if ln.lb == LB_LAST:
                break

            s += config.lb2str(ln.lb).replace("\n", " ")
            line += 1

        return s

    # return a dictionary of all scene names (single-line text elements
    # only, upper-cased, values = None).
    def getSceneNames(self):
        names = {}

        for ln in self.lines:
            if (ln.lt == SCENE) and (ln.lb == LB_LAST):
                names[textutil.upper(ln.text)] = None

        return names

    # return a dictionary of all character names (single-line text
    # elements only, lower-cased, values = None).
    def getCharacterNames(self):
        names = {}

        ul = textutil.lower

        for ln in self.lines:
            if (ln.lt == CHARACTER) and (ln.lb == LB_LAST):
                names[ul(ln.text)] = None

        return names

    # return a list of all scene locations in a [(sceneNumber, startLine),
    # ...] format. if script does not start with a scene line, that scene
    # is not included in this list. note that the sceneNumber in the
    # returned list is a string, e.g. "12" or "12A".
    def getSceneLocations(self):
        return [(label, i) for i, label in self.getSceneLabels()]

    # get next word, starting at (line, col). line must be valid, but col
    # can point after the line's length, in which case the search starts
    # at (line + 1, 0). returns (word, line, col), where word is None if
    # at end of script, and (line, col) point to the start of the word.
    # note that this only handles words that are on a single line.
    def getWord(self, line, col):
        ls = self.lines

        while 1:
            if (line < 0) or (line >= len(ls)):
                return (None, 0, 0)

            s = ls[line].text

            if col >= len(s):
                line += 1
                col = 0

                continue

            ch = s[col : col + 1]

            if not textutil.isWordBoundary(ch):
                word = ch
                startCol = col
                col += 1

                while col < len(s):
                    ch = s[col : col + 1]

                    if textutil.isWordBoundary(ch):
                        break

                    word += ch
                    col += 1

                return (word, line, startCol)

            else:
                col += 1

    # set line types from 'line' to the end of the element to 'lt'.
    def setLineTypes(self, line, lt):
        ls = self.lines

        while 1:
            ln = ls[line]

            ln.lt = lt
            if ln.lb == LB_LAST:
                break

            line += 1

    # give every line of the elements in the given range of lines
    # (inclusive) the type of its element's first line. 'line1' must be
    # the first line of an element.
    def fixElemLineTypes(self, line1, line2):
        ls = self.lines
        lt = None

        for i in range(line1, line2 + 1):
            if lt is None:
                lt = ls[i].lt
            else:
                ls[i].lt = lt

            if ls[i].lb == LB_LAST:
                lt = None
