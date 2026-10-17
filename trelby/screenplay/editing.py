# edit operations used by the commands and dialogs: changing element
# types, joining and splitting lines and elements, and whole-script edits
# (removing element types, renaming characters).

import re

import trelby.screenplay.characterprofiles as characterprofiles
import trelby.screenplay.pagelock as pagelock
import trelby.textfmt as textfmt
import trelby.textutil as textutil
import trelby.undo as undo
from trelby.screenplay.line import Line
from trelby.screenplay.constants import (
    CHARACTER,
    LB_FORCED,
    LB_LAST,
    PAREN,
    SCENE,
)


class EditingMixin:
    # convert element(s) to given type
    #  - if multiple elements are selected, all are changed
    #  - if not, the change is applied to element under cursor.
    def convertTypeTo(self, lt, saveUndo):
        ls = self.sp.lines
        selection = self.getMarkedLines()

        if selection:
            startSection, endSection = selection
            selectedElems = self.sp.elemsDistance(startSection, endSection) + 1
        else:
            startSection, endSection = self.getElemIndexes()
            selectedElems = 1

        currentLine = startSection

        if saveUndo:
            # the speeches around the changed elements may move into or
            # out of a dual dialogue, so they're rewrapped too, and
            # included in the undo
            wrapFirst, wrapLast = self.sp.getSpeechRangeAround(
                startSection, endSection
            )
            wrapCnt = self.sp.elemsDistance(wrapFirst, wrapLast) + 1

            u = undo.ManyElems(self, undo.CMD_MISC, wrapFirst, wrapCnt, wrapCnt)

        while currentLine <= endSection:
            first, last = self.sp.getElemIndexesFromLine(currentLine)

            # if changing away from PAREN containing only "()", remove it
            if (first == last) and (ls[first].lt == PAREN) and (ls[first].text == "()"):
                ls[first].setText("")

                if first == self.line:
                    self.column = 0

            for i in range(first, last + 1):
                ls[i].lt = lt

            # if changing empty element to PAREN, add "()"
            if (
                (first == last)
                and (ls[first].lt == PAREN)
                and (len(ls[first].text) == 0)
            ):
                ls[first].setText("()")

                if first == self.line:
                    self.column = 1

            currentLine = last + 1

        if selection:
            self.clearMark()

            # this is moderately complex because we need to deal with
            # forced linebreaks; reformatRange wants paragraph indexes but
            # we are converting elements, so we must find the indexes of
            # the a) first paragraph of the first selected element and b)
            # last paragraph of the last selected element

            self.reformatRange(
                self.sp.getElemFirstIndexFromLine(startSection),
                self.sp.getParaFirstIndexFromLine(
                    self.sp.getElemLastIndexFromLine(endSection)
                ),
            )
        else:
            self.rewrapElem(first)

        self.sp.markChanged()

        if saveUndo:
            self.rewrapElems(wrapFirst, wrapCnt)

            u.setAfter(self)
            self.undoHistory.add(u)

    # join lines 'line' and 'line + 1' and position cursor at the join
    # position.
    def joinLines(self, line):
        ls = self.sp.lines
        ln = ls[line]

        pos = len(ln.text)
        ln.appendLine(ls[line + 1])
        ln.lb = ls[line + 1].lb

        # rewrapPara moves them to the paragraph's first line
        ln.notes += ls[line + 1].notes

        # the joined line's page lock now points into the middle of this
        # line. rewrapPara uses pageLockCol to put it back on the right
        # line.
        label = ls[line + 1].pageLock

        if label:
            if ln.pageLock:
                ln.pageLock = pagelock.combine(ln.pageLock, label)
            else:
                ln.pageLock = label
                ln.pageLockCol = pos

        # if line + 1 started another element, the two are one now (this
        # line took over its line break above), so the rest of that
        # element gets this line's type
        self.sp.setLineTypes(line + 1, ln.lt)
        del ls[line + 1]

        self.line = line
        self.column = pos

    # split current line at current column position.
    def splitLine(self):
        ln = self.sp.lines[self.line]

        s = ln.text
        preStr = s[: self.column]
        postStr = s[self.column :]
        newLine = Line(ln.lb, ln.lt, postStr, fmt=ln.sliceFmt(self.column))
        ln.setText(preStr, ln.sliceFmt(0, self.column))
        ln.lb = LB_FORCED
        self.sp.lines.insert(self.line + 1, newLine)

        self.line += 1
        self.column = 0
        self.sp.markChanged()

    # split element at current position. newType is type to give to the
    # new element.
    def splitElement(self, newType):
        ls = self.sp.lines

        if self.mark:
            self.clearMark()

            return

        # splitting a speech can make it, or the speeches around it, part
        # of a dual dialogue or take them out of one, so they're rewrapped
        # too, and included in the undo
        wrapFirst, wrapLast = self.sp.getSpeechRangeAround(self.line, self.line)
        wrapCnt = self.sp.elemsDistance(wrapFirst, wrapLast) + 1

        u = undo.ManyElems(self, undo.CMD_MISC, wrapFirst, wrapCnt, wrapCnt + 1)

        # with the auto-completion list showing, the selected item is
        # accepted first. at the end of a parenthetical, the cursor steps
        # over the ")" so that it stays in the parenthetical.
        if not self.acItems:
            if self.isAtEndOfParen():
                self.column += 1
        else:
            ls[self.line].setText(self.acItems[self.acSel])
            self.column = len(ls[self.line].text)

        # splitLine makes a forced line break; making it LB_LAST instead
        # turns the text after the cursor into a new element, which is
        # where the cursor is for convertTypeTo
        self.splitLine()
        ls[self.line - 1].lb = LB_LAST

        self.convertTypeTo(newType, False)

        self.rewrapPara()
        self.rewrapPrevPara()
        self.rewrapElems(wrapFirst, wrapCnt + 1)
        self.sp.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)

    # delete character at given position and optionally position
    # cursor there.
    def deleteChar(self, line, column, posCursor=True):
        self.sp.lines[line].deleteText(column, column + 1)

        if posCursor:
            self.column = column
            self.line = line

    # remove all lines whose element types are in tdict as keys.
    def removeElementTypes(self, tdict, saveUndo):
        self.clearAutoComp()

        if saveUndo:
            u = undo.FullCopy(self)

        lsNew = []
        lsOld = self.sp.lines
        sl = self.line

        # how many lines were removed from above the current line
        # (inclusive)
        cnt = 0

        # page lock of removed lines, to be moved to the next line kept
        label = None

        for i in range(len(lsOld)):
            l = lsOld[i]

            if l.lt not in tdict:
                if label:
                    if l.pageLock:
                        l.pageLock = pagelock.combine(label, l.pageLock)
                    else:
                        l.pageLock = label

                    label = None

                lsNew.append(l)
            else:
                if l.pageLock:
                    if label:
                        label = pagelock.combine(label, l.pageLock)
                    else:
                        label = l.pageLock

                if i <= sl:
                    cnt += 1

        self.line -= cnt

        if len(lsNew) == 0:
            lsNew.append(Line(LB_LAST, SCENE))

        self.sp.lines = lsNew

        self.validatePos()
        self.clearMark()
        self.sp.markChanged()

        if saveUndo:
            u.setAfter(self)
            self.undoHistory.add(u)

    # rename characters. 'renames' is a dictionary mapping old names to
    # new ones, both normalized with characterprofiles.normalizeName.
    # character cues are renamed keeping any extension like "(V.O.)", and
    # the names are also replaced where they're mentioned in other
    # elements, matching the case they were written in. all renames are
    # done in one pass, so names can be swapped. if renameProfiles is
    # True, the characters' profiles are renamed too, in the same undo
    # step. returns a (cues, mentions) tuple of how many of each were
    # renamed.
    def renameCharacters(self, renames, renameProfiles=False):
        normalize = characterprofiles.normalizeName

        renames = {k: v for k, v in renames.items() if k and v and (k != v)}
        if not renames:
            return (0, 0)

        # (old name, new name) of the profiles to rename
        profileRenames = []

        if renameProfiles:
            for old, new in renames.items():
                prof = self.sp.characterProfiles.get(old)

                if prof:
                    profileRenames.append((prof.name, new))

        # the names of the other characters are matched too, but left as
        # they are, so that renaming MARY doesn't touch "Mary" in mentions
        # of MARY JANE. longest names first, so that "MARY JANE" wins over
        # "MARY".
        names = {normalize(n): None for n in self.sp.getCharacterNames()}
        names.update(renames)
        names.pop("", None)

        pattern = re.compile(
            "|".join(
                r"(?<!\w)%s(?!\w)" % r"\s+".join(re.escape(w) for w in name.split())
                for name in sorted(names, key=len, reverse=True)
            ),
            re.IGNORECASE,
        )

        # how many mentions the current line had renamed
        lineMentions = 0

        def replaceMention(mo):
            nonlocal lineMentions

            found = mo.group(0)
            new = names[normalize(found)]

            if not new:
                return found

            lineMentions += 1

            if found.isupper():
                return new
            elif found.islower():
                return textutil.lower(new)
            else:
                # capitalize each word, e.g. "MARY-ANNE O'NEIL" ->
                # "Mary-Anne O'Neil"
                return re.sub(
                    r"[^\W\d_]+",
                    lambda m: textutil.upper(m.group(0)[:1]) + textutil.lower(m.group(0)[1:]),
                    new,
                )

        cues = 0
        mentions = 0

        # (line, new text, new format string) for every changed line
        changes = []

        for i, ln in enumerate(self.sp.lines):
            if ln.lt == CHARACTER:
                new = renames.get(normalize(ln.text)) if ln.lb == LB_LAST else None

                if new:
                    idx = ln.text.find("(")
                    ext = (" " + ln.text[idx:].strip()) if idx != -1 else ""

                    # the name gets the style of its first letter, and the
                    # extension keeps its own
                    fmt = None

                    if ln.fmt:
                        fmt = textfmt.char(textfmt.styleAt(ln.fmt, 0)) * len(new)

                        if ext:
                            fmt += "0" + textfmt.fit(ln.sliceFmt(idx), len(ext) - 1)

                    changes.append((i, new + ext, fmt))
                    cues += 1

            else:
                lineMentions = 0
                text, fmt = textfmt.sub(pattern, replaceMention, ln.text, ln.fmt)

                if lineMentions:
                    changes.append((i, text, fmt))
                    mentions += lineMentions

        if not changes and not profileRenames:
            return (cues, mentions)

        self.clearAutoComp()

        u = undo.RenameCharacters(self, profileRenames)

        undo.renameProfiles(self.sp, profileRenames)

        for i, text, fmt in changes:
            self.sp.lines[i].setText(text, fmt)

        # rewrap changed paragraphs from the bottom up, so that the line
        # numbers of the ones still to do stay valid
        paras = {self.sp.getParaFirstIndexFromLine(i) for i, _text, _fmt in changes}

        for line in sorted(paras, reverse=True):
            self.rewrapPara(line)

        acType = self.sp.autoCompletion.getType(CHARACTER)
        acType.items = list(
            dict.fromkeys(renames.get(normalize(it), it) for it in acType.items)
        )

        self.validatePos()
        self.clearMark()
        self.sp.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)

        return (cues, mentions)
