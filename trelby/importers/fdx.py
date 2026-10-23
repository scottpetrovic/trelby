# Final Draft (FDX) files.

import trelby.screenplay as screenplay
import trelby.screenplay.breakdown as breakdown
import trelby.screenplay.revisions as revisions
import trelby.textfmt as textfmt
import trelby.textutil as textutil
import trelby.util as util
from trelby.importers.common import (
    ImportResult,
    addElem,
    addSynopsis,
    checkLines,
    checkNotEmpty,
    parseXML,
)

# whether parse takes bytes rather than str
BINARY = False

ELEM_MAP = {
    "Action": screenplay.ACTION,
    "Character": screenplay.CHARACTER,
    "Dialogue": screenplay.DIALOGUE,
    "Parenthetical": screenplay.PAREN,
    "Scene Heading": screenplay.SCENE,
    "Shot": screenplay.SHOT,
    "Transition": screenplay.TRANSITION,
}

# the FDX text styles, and the textfmt style bit each one sets
STYLES = (
    ("Bold", textfmt.BOLD),
    ("Italic", textfmt.ITALIC),
    ("Underline", textfmt.UNDERLINED),
)


# add a note element with the text s to lines, if s isn't empty
def addNote(lines, s):
    if s:
        addElem(lines, screenplay.NOTE, s.split("\n"))


def parse(data, options=None):
    checkNotEmpty(data)

    # https://github.com/trelby/trelby/issues/61
    data = data.replace(" ", "\n")

    root = parseXML(data)
    lines = []
    tagData = parseTagData(root)

    for para in root.xpath("Content//Paragraph"):
        et = para.get("Type")

        # Check for script notes
        note = ""
        for notes in para.xpath("ScriptNote/Paragraph/Text"):
            if notes.text:
                note += notes.text

            # FD has AdornmentStyle set to "0" on notes with newline.
            if notes.get("AdornmentStyle") == "0":
                note += "\n"

        addedNote = bool(note)

        # "General" has embedded Dual Dialogue paragraphs inside it;
        # nothing to do for the General element itself.
        #
        # If no type is defined (like inside scriptnote), skip.
        if (et == "General") or (et is None):
            addNote(lines, note)

            continue

        s = ""
        fmt = ""
        revs = ""

        # the tag number of each character of s
        tagNrs = []

        for text in para.xpath("Text"):
            # text.text is None for paragraphs with no text
            if text.text:
                s += text.text
                tagNrs += [text.get("TagNumber") or "0"] * len(text.text)

                styles = (text.get("Style") or "").split("+")
                style = 0

                for name, bit in STYLES:
                    if name in styles:
                        style |= bit

                fmt += textfmt.char(style) * len(text.text)
                revs += revisions.levelChar(revisionLevel(text)) * len(text.text)

        # don't remove paragraphs with no text, unless that paragraph
        # contained a scriptnote
        if s or not addedNote:
            lt = ELEM_MAP.get(et, screenplay.ACTION)
            firstLine = len(lines)
            addElem(
                lines,
                lt,
                s.split("\n"),
                textfmt.compact(fmt),
                textfmt.compact(revs),
            )

            if (lt == screenplay.ACTION) and (para.get("Alignment") == "Center"):
                lines[firstLine].centered = True

            addTags(lines, firstLine, lt, s, tagNrs, tagData)

            # a scene's synopsis is its SceneProperties' Summary, a
            # paragraph per line. (FD's own paragraphs in it have no Type,
            # so the loop skips them.)
            if lt == screenplay.SCENE:
                addSynopsis(lines, sceneSummary(para))

            # in a DualDialogue, the second character's speech is the
            # right-hand column
            parent = para.getparent()

            if (
                (lt == screenplay.CHARACTER)
                and (parent.tag == "DualDialogue")
                and (parent.xpath("Paragraph[@Type='Character']")[0] is not para)
            ):
                lines[firstLine].dual = True

        # after the paragraph it's in, so that it becomes a note on that
        # paragraph (see ImportResult)
        addNote(lines, note)

    checkLines(lines)

    return ImportResult(lines, revisions=parseRevisions(root))


# return the script's breakdown elements from its TagData (Final Draft's
# tagger) as a dict of Tag number -> [(category key, name)], a tagged
# text run naming its Tag by number (TagNumber), which lists the elements
# tagged there (DefId: a TagDefinition's Id, which has the element's name,
# Label, and its category's Id, CatId). Final Draft's categories are
# matched to Trelby's by name (breakdown.categoryFromFdx).
def parseTagData(root):
    cats = {}

    for c in root.xpath("TagData/TagCategories/TagCategory"):
        cats[c.get("Id")] = breakdown.categoryFromFdx(c.get("Name") or "")

    defs = {}

    for d in root.xpath("TagData/TagDefinitions/TagDefinition"):
        defs[d.get("Id")] = (
            cats.get(d.get("CatId"), breakdown.UNKNOWN),
            breakdown.cleanName(textutil.cleanInput(d.get("Label") or "")),
        )

    ret = {}

    for t in root.xpath("TagData/Tags/Tag"):
        elems = [defs.get((d.text or "").strip()) for d in t.xpath("DefId")]
        elems = [e for e in elems if e]

        if elems:
            ret.setdefault(t.get("Number"), []).extend(elems)

    return ret


# put the tags of an element of type lt, whose text s was added to lines
# from line 'first' on (a line per paragraph, s's lines), on its
# paragraphs. tagNrs is the Tag number of each character of s, and tagData
# what parseTagData returned. each stretch of text tagged with an element
# becomes a tag with that text, except a whole scene heading, which is how
# Trelby exports tags with no text (an element the scene needs that its
# text doesn't mention). an element with no name is named by its text.
def addTags(lines, first, lt, s, tagNrs, tagData):
    if not tagData:
        return

    start = 0

    for i, para in enumerate(s.split("\n")):
        end = start + len(para)
        nrs = tagNrs[start:end]
        tags = []

        # element -> start of the stretches of text tagged with it that
        # go on to character k
        going = {}

        for k in range(len(para) + 1):
            elems = tagData.get(nrs[k], []) if k < len(para) else []

            for elem in list(going):
                if elem not in elems:
                    addTag(tags, lt, para, elem, going.pop(elem), k)

            for elem in elems:
                going.setdefault(elem, k)

        if tags and (first + i < len(lines)):
            lines[first + i].tags = tuple(tags)

        start = end + 1


# add a tag for the element elem tagged at para[a:b] to tags, unless it's
# already in them
def addTag(tags, lt, para, elem, a, b):
    category, name = elem
    text = textutil.cleanInput(para[a:b]).strip()

    if not text:
        return

    if (lt == screenplay.SCENE) and (text == para.strip()):
        text = ""

    tag = breakdown.Tag(category, name or text, text)

    if not tag.name:
        return

    for t in tags:
        if (t.key == tag.key) and (textutil.lower(t.text) == textutil.lower(text)):
            return

    tags.append(tag)


# return the text of a scene heading paragraph's summary, "" if it has
# none
def sceneSummary(para):
    ret = []

    for p in para.xpath("SceneProperties/Summary/Paragraph"):
        ret.append("".join(t.text or "" for t in p.xpath("Text")))

    return "\n".join(ret)


# return the revision a Text element is marked with: its RevisionID, a
# revision set's ID, which is taken as the revision's level (1 for Blue,
# ...). 0 if it has none or it's invalid.
def revisionLevel(text):
    return util.str2int(text.get("RevisionID", "0"), 0, 0, revisions.MAX_LEVEL)


# return the script's revision settings from its Revisions element, or
# None if it has none: the active revision set, revision mode and the
# active set's revision mark. the sets' names and colors are Final
# Draft's own, so they're not kept.
def parseRevisions(root):
    elems = root.xpath("Revisions")

    if not elems:
        return None

    elem = elems[0]
    rv = revisions.Revisions()
    rv.level = util.str2int(elem.get("ActiveSet", "0"), 0, 0, revisions.MAX_LEVEL)
    rv.active = bool(rv.level) and (elem.get("RevisionMode") == "Yes")

    for r in elem.xpath("Revision"):
        if r.get("ID") == str(rv.level):
            rv.markChar = (r.get("Mark") or "").strip()[:1] or rv.markChar

    return rv
