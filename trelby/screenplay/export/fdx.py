# Final Draft XML (.fdx) export.

import uuid

from lxml import etree

import trelby.config as config
import trelby.screenplay.breakdown as breakdown
import trelby.screenplay.revisions as revisions
import trelby.screenplay.scriptformats as scriptformats
import trelby.textfmt as textfmt
from trelby.screenplay.constants import (
    ACTBREAK,
    ACTION,
    CHARACTER,
    DIALOGUE,
    LB_FORCED,
    LB_LAST,
    LB_SPACE,
    PAREN,
    SCENE,
    SHOT,
    TRANSITION,
)
from trelby.screenplay.export.common import getElemNotes, getElementsAsList

# the element recording a script's format (see scriptformats), which
# isn't Final Draft's: the importer reads it back
FORMAT_ELEMENT = "TrelbyScriptFormat"

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


# return the (start, end, style, level, tag) runs of text n characters
# long with the format string fmt, revision marks revs and tags (a Tag
# number per character, 0 for none, or None for no tags), each run having
# the same formatting, revision and tag throughout. empty for n == 0.
def runs(fmt, revs, n, tags=None):
    fmt = textfmt.fit(fmt, n)
    revs = textfmt.fit(revs, n)
    tags = tags or [0] * n
    ret = []
    start = 0

    for i in range(1, n + 1):
        if (
            (i == n)
            or (fmt[i] != fmt[start])
            or (revs[i] != revs[start])
            or (tags[i] != tags[start])
        ):
            ret.append(
                (start, i, ord(fmt[start]) - 48, ord(revs[start]) - 48, tags[start])
            )
            start = i

    return ret


# the breakdown tags (see screenplay/breakdown.py) as Final Draft's
# TagData: each element is a TagDefinition in its category, and each
# stretch of text tagged with the same elements a numbered Tag listing
# them (DefId), which the text runs refer to (TagNumber).
class FdxTags:
    def __init__(self):
        # element key -> (TagDefinition Id, Number, category key, name)
        self.defs = {}

        # the Tags, as tuples of element keys: Tag n is self.tags[n - 1]
        self.tags = []

    # return the Tag number of each character of the element's text txt
    # (as getElementsAsList gives it), which starts at line 'first', 0 for
    # none, adding the Tags and TagDefinitions it needs; or None if
    # nothing in it is tagged
    def elemTags(self, sp, txt, first):
        ls = sp.lines
        last = sp.getElemLastIndexFromLine(first)

        if not any(ls[i].tags for i in range(first, last + 1)):
            return None

        # the element keys tagged at each character
        keys = [()] * len(txt)

        # the element's paragraphs, which forced line breaks end, by their
        # first line and their place in txt
        pos = 0
        paraFirst = first
        paraStart = 0

        for i in range(first, last + 1):
            pos += len(ls[i].text)

            if ls[i].lb in (LB_FORCED, LB_LAST):
                self.markPara(sp, txt, keys, paraFirst, paraStart, pos)
                pos += 1
                paraFirst = i + 1
                paraStart = pos
            elif ls[i].lb == LB_SPACE:
                pos += 1

        ret = [0] * len(txt)

        for i, k in enumerate(keys):
            if k:
                if (i == 0) or (keys[i - 1] != k):
                    self.tags.append(k)

                ret[i] = len(self.tags)

        return ret

    # mark the characters of the paragraph txt[start:end], whose first
    # line is 'first', in keys with the elements tagged there. a tag whose
    # text isn't in it (one with no text, which is on a scene heading, or
    # whose text has been edited away) marks all of it, so that Final
    # Draft still has it in the scene. an empty paragraph's tags are lost.
    def markPara(self, sp, txt, keys, first, start, end):
        tags = sp.getParaTags(first)

        if not tags or (start == end):
            return

        found = set()

        for a, b, tag in breakdown.findSpans(txt[start:end], tags):
            found.add(tag)
            self.mark(keys, tag, start + a, start + b)

        for tag in tags:
            if tag not in found:
                self.mark(keys, tag, start, end)

    def mark(self, keys, tag, start, end):
        cat = breakdown.category(tag.category).key
        key = breakdown.elementKey(cat, tag.name)

        if key not in self.defs:
            # the same Id for the same element every time, so that
            # exporting again gives the same file
            defId = uuid.uuid5(uuid.NAMESPACE_URL, "trelby:tag:%s:%s" % key)
            self.defs[key] = (
                str(defId),
                len(self.defs) + 1,
                cat,
                breakdown.cleanName(tag.name),
            )

        for i in range(start, end):
            if key not in keys[i]:
                keys[i] += (key,)

    # add the TagData element to fd, if anything is tagged. it lists all
    # of Final Draft's standard categories, as Final Draft does, the ones
    # Trelby has in Trelby's colors.
    def addTo(self, fd):
        if not self.defs:
            return

        data = etree.SubElement(fd, "TagData")
        cats = etree.SubElement(data, "TagCategories")
        catIds = {}

        for name, catId, nr, key in breakdown.FDX_CATEGORIES:
            elem = etree.SubElement(cats, "TagCategory")

            if key:
                catIds[key] = catId
                color = fdxColor(breakdown.category(key).color)
            else:
                color = "#94AA11150000"

            elem.set("Color", color)
            elem.set("Id", catId)
            elem.set("Name", name)
            elem.set("Number", str(nr))
            elem.set("Style", "Bold")

        defs = etree.SubElement(data, "TagDefinitions")

        for defId, nr, cat, name in self.defs.values():
            elem = etree.SubElement(defs, "TagDefinition")
            elem.set("CatId", catIds[cat])
            elem.set("Id", defId)
            elem.set("Label", name)
            elem.set("Number", str(nr))

        tags = etree.SubElement(data, "Tags")

        for nr, keys in enumerate(self.tags, 1):
            elem = etree.SubElement(tags, "Tag")
            elem.set("Number", str(nr))

            for key in keys:
                etree.SubElement(elem, "DefId").text = self.defs[key][0]


# the other takes of elements (see screenplay/alternates.py) as Final
# Draft's alternates: an element's paragraph lists its takes by number
# (Alts / AltId), and the AltCollection after the content has their text
# (Alt, a paragraph with no Type). Current is the shown take's place
# among them all, which is first here (a guess from Final Draft's own
# files: its Current goes up to the number of AltIds).
class FdxAlts:
    def __init__(self):
        # the takes, Alt n being self.takes[n - 1]
        self.takes = []

    # list the takes in 'alternates' in the paragraph para, if there are
    # any
    def addElem(self, para, alternates):
        if not alternates:
            return

        alts = etree.SubElement(para, "Alts")
        alts.set("Current", "0")

        for take in alternates:
            self.takes.append(take)
            etree.SubElement(alts, "AltId").text = str(len(self.takes))

    # add the AltCollection element to fd, if any element has takes
    def addTo(self, fd):
        if not self.takes:
            return

        coll = etree.SubElement(fd, "AltCollection")

        for nr, take in enumerate(self.takes, 1):
            alt = etree.SubElement(coll, "Alt")
            alt.set("Id", str(nr))
            para = etree.SubElement(alt, "Paragraph")

            for a, b, style, level, tagNr in runs(take.fmt, None, len(take.text)):
                addText(para, take.text[a:b], style)


# add a Text element with text s in the textfmt style 'style' to para, and
# return it
def addText(para, s, style):
    elem = etree.SubElement(para, "Text")
    elem.text = s

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
        elem.set("Style", "+".join(flags))

    return elem


# a color "rrggbb" in Final Draft's form, 16 bits per channel
def fdxColor(color):
    return "#" + "".join(color[i : i + 2].upper() * 2 for i in range(0, 6, 2))


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

    tagData = FdxTags()
    altData = FdxAlts()

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

        # a Text element for each run of text with different formatting,
        # revision or tags
        elemRuns = runs(
            fmt, elemRevs(sp, first), len(txt), tagData.elemTags(sp, txt, first)
        )

        for a, b, style, level, tagNr in elemRuns or [(0, 0, 0, 0, 0)]:
            paratxt = addText(para, str(txt[a:b]), style)

            if level:
                paratxt.set("RevisionID", str(level))

            if tagNr:
                paratxt.set("TagNumber", str(tagNr))

        # the element's other takes, after its text as in Final Draft's
        # files
        altData.addElem(para, sp.getAlternates(first))

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

    altData.addTo(fd)
    tagData.addTo(fd)

    # the script's format, for importing it back into Trelby (Final Draft
    # has no two-column layout, so an AV script is its elements in order)
    fmtKey = sp.cfg.scriptFormat

    if fmtKey != scriptformats.SCREENPLAY:
        etree.SubElement(fd, FORMAT_ELEMENT).set("Key", fmtKey)

    return etree.tostring(
        fd, xml_declaration=True, encoding="UTF-8", pretty_print=True
    )
