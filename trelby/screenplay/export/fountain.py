# Fountain export.

import re

import trelby.textfmt as textfmt
import trelby.textutil as textutil
from trelby.screenplay.constants import (
    ACTBREAK,
    ACTION,
    CHARACTER,
    DIALOGUE,
    PAREN,
    SCENE,
    SHOT,
    TRANSITION,
)
from trelby.screenplay.export.common import getElemNotes, getElementsAsList


# generate Fountain and return it as a string.
def generateFountain(sp):
    eleList = getElementsAsList(sp)
    flines = []
    TWOSPACE = "  "
    sceneStartsList = ("INT", "EXT", "EST", "INT./EXT", "INT/EXT", "I/E", "I./E")

    # does s look like a fountain scene line:
    def looksLikeScene(s):
        s = s.upper()
        looksGood = False
        for t in sceneStartsList:
            if s.startswith(t):
                looksGood = True
                break
        return looksGood

    # Generate Title Page
    def generateTitleString(keyword, titleLine, startAt, linePrefix, lineSuffix):
        if (len(titleLine) - startAt) > 1:
            # multi-line
            flines.append(keyword)
            for part in titleLine:
                if startAt > 0:
                    startAt -= 1
                    continue
                flines.append("    " + linePrefix + part + lineSuffix)
        elif len(titleLine) == 1 and keyword == titleLine[0]:
            flines.append(keyword)
        else:
            flines.append(keyword + " " + titleLine[startAt])

    # fountain's title page is "Key: value" pairs, while Trelby's title
    # strings are free text, so the keys are guessed: the first bold
    # centered string is the title, "by" introduces the author, a
    # string that starts with something like "Draft date:" is used as
    # its own key, and anything else becomes a contact.
    titleNeeded = True
    kwPattern = re.compile(r"^([A-Za-z][^:]+:)")
    for page in sp.titles.pages:
        # index of a title string already used as an author
        skipIndex = -1
        for i, titleLine in enumerate(page):
            if i == skipIndex:
                continue
            if titleNeeded and titleLine.isBold and titleLine.isCentered:
                generateTitleString("Title:", titleLine.items, 0, "_**", "**_")
                titleNeeded = False
            elif titleLine.items[0].strip().lower() == "by":
                # the author is either in this title string after "by"
                # (usually with a blank line in between), or, if "by"
                # is alone, in the next one.
                author = titleLine.items[1:]
                while author and not author[0].strip():
                    author = author[1:]
                if not author and (i + 1) < len(page):
                    author = page[i + 1].items
                    skipIndex = i + 1
                if author:
                    generateTitleString("Author:", author, 0, "", "")
            elif kwPattern.match(titleLine.items[0]):
                generateTitleString(titleLine.items[0], titleLine.items, 0, "", "")
            else:
                generateTitleString("Contact:", titleLine.items, 0, "", "")

    # notes of the elements written since the last place a blank line
    # could go (see flushNotes)
    notes = []

    # add the pending notes as [[notes]], each a paragraph of its own. a
    # note can't be in the middle of a speech, as the blank line before it
    # would end the speech, so the notes of a speech's elements wait until
    # the next element starting with a blank line. they're imported as
    # notes on the element before them.
    def flushNotes():
        for note in notes:
            if flines and flines[-1] != "":
                flines.append("")

            flines.append("[[" + " ".join(note.text.split()) + "]]")

        notes.clear()

    for typ, txt, first, fmt in eleList:
        if typ not in (DIALOGUE, PAREN):
            flushNotes()

        # formatting as markup, a line at a time, since it can't span
        # lines
        pos = 0
        lns = []

        for ln in txt.split("\n"):
            lns.append(textfmt.toMarkup(ln, fmt and fmt[pos : pos + len(ln)]))
            pos += len(ln) + 1

        txt = "\n".join(lns)

        # ensure last element of flines is empty for some types.
        if typ in (
            SCENE,
            ACTION,
            CHARACTER,
            TRANSITION,
            SHOT,
            ACTBREAK,
                ):
            if flines and flines[-1] != "":
                flines.append("")

        # special handling of some elements.
        if typ == SCENE:
            # if the line would not be recognized as Scene by fountain,
            # append a "." so it is forced as a scene line.
            if not looksLikeScene(txt):
                txt = "." + txt

        elif (typ == ACTION) and sp.hasCenteredFlag(first):
            txt = "\n".join(">" + ln + "<" for ln in lns)

        elif typ == ACTION:
            tmp = []
            for ln in lns:
                if ln and (ln.isupper() or looksLikeScene(txt)):
                    tmp.append(ln + TWOSPACE)
                else:
                    tmp.append(ln)
            txt = "\n".join(tmp)

        elif typ == TRANSITION:
            if not txt.endswith("TO:"):
                txt = "> " + txt

        elif typ == DIALOGUE:
            tmp = []
            for ln in lns:
                if not ln:
                    tmp.append(TWOSPACE)
                else:
                    tmp.append(ln)
            txt = "\n".join(tmp)

        elif typ == ACTBREAK:
            txt = "\n".join(">" + ln + "<" for ln in lns)

        elif typ == SHOT:
            txt += TWOSPACE

        elif typ == CHARACTER:
            if sp.getDualBlockFromRight(first):
                txt += " ^"

        flines.append(txt)
        notes.extend(getElemNotes(sp, first))

    flushNotes()

    return textutil.toUTF8("\n".join(flines))
