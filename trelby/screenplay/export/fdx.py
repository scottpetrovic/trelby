# Final Draft XML (.fdx) export.

from lxml import etree

import trelby.config as config
import trelby.screenplay.revisions as revisions
import trelby.textfmt as textfmt
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

# the page colors of the revisions in Final Draft's form (16 bits per
# channel), in revisions.COLORS' order: White, Blue, Pink, Yellow, Green,
# Goldenrod, Buff, Salmon, Cherry. the paper colors, lighter than the
# highlights.
PAGE_COLORS = [
    "#FFFFFFFFFFFF",
    "#C6C6EDEDFEFE",
    "#FEFECDCDDADA",
    "#FEFEFAFAB4B4",
    "#CDCDF2F2CDCD",
    "#F3F3D6D69292",
    "#F5F5E8E8BFBF",
    "#FDFDCECEC0C0",
    "#F1F1A9A9BABA",
]


# return the revision marks of the element starting at line 'first', for
# its text as getElementsAsList joins it, or None if it has none
def elemRevs(sp, first):
    ls = sp.lines
    last = sp.getElemLastIndexFromLine(first)

    if not any(ls[i].revs for i in range(first, last + 1)):
        return None

    return revisions.join(
        [(ls[i].text, ls[i].revs) for i in range(first, last + 1)],
        [config.lb2str(ls[i].lb) for i in range(first, last)],
    )


# return the (start, end, style, level) runs of text n characters long
# with the format string fmt and revision marks revs, each run having the
# same formatting and revision throughout. empty for n == 0.
def runs(fmt, revs, n):
    fmt = textfmt.fit(fmt, n)
    revs = textfmt.fit(revs, n)
    ret = []
    start = 0

    for i in range(1, n + 1):
        if (i == n) or (fmt[i] != fmt[start]) or (revs[i] != revs[start]):
            ret.append((start, i, ord(fmt[start]) - 48, ord(revs[start]) - 48))
            start = i

    return ret


# add the script's revision sets (Final Draft's Revisions element), one
# for each revision up to the current one or the latest one used, to fd
def addRevisions(sp, fd):
    rv = sp.revisions
    used = max((revisions.lineLevel(ln) for ln in sp.lines), default=0)
    count = max(rv.level, used)

    if not count:
        return

    elem = etree.SubElement(fd, "Revisions")
    elem.set("ActiveSet", str(max(rv.level, 1)))
    elem.set("RevisionMode", "Yes" if rv.active else "No")

    for level in range(1, count + 1):
        r = etree.SubElement(elem, "Revision")
        r.set("ID", str(level))
        r.set("Name", rv.label(level))
        r.set("Mark", rv.markChar)
        r.set("Color", "#000000000000")
        r.set("PageColor", PAGE_COLORS[level % len(PAGE_COLORS)])
        r.set("FullRevision", "No")
        r.set("Style", "")


# Generate a Final Draft XML file and return as string.
def generateFDX(sp):
    eleList = getElementsAsList(sp)
    fd = etree.Element("FinalDraft")
    fd.set("DocumentType", "Script")
    fd.set("Template", "No")
    fd.set("Version", "1")
    content = etree.SubElement(fd, "Content")

    xmlMap = {
        ACTION: "Action",
        CHARACTER: "Character",
        DIALOGUE: "Dialogue",
        PAREN: "Parenthetical",
        SCENE: "Scene Heading",
        SHOT: "Shot",
        TRANSITION: "Transition",
        ACTBREAK: "New Act",
    }

    # where to add paragraphs: 'content', or the DualDialogue element
    # of the dual dialogue we're in, which ends at line dualEnd
    parent = content
    dualEnd = -1

    # the last ScriptNote's ID
    noteId = 0

    # scene numbers, when they're locked or printed
    if sp.hasSceneLocks() or sp.cfg.pdfShowSceneNumbers:
        sceneNrs = dict(sp.getSceneLabels())
    else:
        sceneNrs = {}

    for typ, txt, first, fmt in eleList:
        if typ == CHARACTER:
            block = sp.getDualBlock(first)

            if block and (block[0] == first):
                general = etree.SubElement(content, "Paragraph")
                general.set("Type", "General")
                parent = etree.SubElement(general, "DualDialogue")
                dualEnd = block[2]

        para = etree.SubElement(parent, "Paragraph")
        para.set("Type", xmlMap[typ])

        if (typ == ACTION) and sp.hasCenteredFlag(first):
            para.set("Alignment", "Center")

        if first in sceneNrs:
            para.set("Number", sceneNrs[first])

        # a scene's synopsis is its SceneProperties' Summary, a paragraph
        # per line
        synopsis = sp.getSynopsis(first) if typ == SCENE else None

        if synopsis:
            props = etree.SubElement(para, "SceneProperties")
            summary = etree.SubElement(props, "Summary")

            for ln in synopsis.split("\n"):
                summaryPara = etree.SubElement(summary, "Paragraph")
                etree.SubElement(summaryPara, "Text").text = ln

        # a Text element for each run of text with different formatting or
        # revision
        for a, b, style, level in runs(fmt, elemRevs(sp, first), len(txt)) or [
            (0, 0, 0, 0)
        ]:
            paratxt = etree.SubElement(para, "Text")
            paratxt.text = str(txt[a:b])

            if level:
                paratxt.set("RevisionID", str(level))

            flags = [
                name
                for bit, name in (
                    (textfmt.BOLD, "Bold"),
                    (textfmt.ITALIC, "Italic"),
                    (textfmt.UNDERLINED, "Underline"),
                )
                if style & bit
            ]

            if flags:
                paratxt.set("Style", "+".join(flags))

        # the element's notes, as script notes in its paragraph
        for note in getElemNotes(sp, first):
            noteId += 1
            scriptnote = etree.SubElement(para, "ScriptNote")
            scriptnote.set("ID", str(noteId))
            notePara = etree.SubElement(scriptnote, "Paragraph")
            etree.SubElement(notePara, "Text").text = note.text

        if sp.getElemLastIndexFromLine(first) >= dualEnd:
            parent = content

    addRevisions(sp, fd)

    # FD does not recognize "New Act" by default. It needs an
    # ElementSettings element added.
    eleSet = etree.SubElement(fd, "ElementSettings")
    eleSet.set("Type", xmlMap[ACTBREAK])
    eleSetFont = etree.SubElement(eleSet, "FontSpec")
    eleSetFont.set("Style", "Underline+AllCaps")
    eleSetPara = etree.SubElement(eleSet, "ParagraphSpec")
    eleSetPara.set("Alignment", "Center")

    return etree.tostring(
        fd, xml_declaration=True, encoding="UTF-8", pretty_print=True
    )
