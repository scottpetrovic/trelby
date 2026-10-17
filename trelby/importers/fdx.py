# Final Draft (FDX) files.

import trelby.screenplay as screenplay
import trelby.screenplay.revisions as revisions
import trelby.textfmt as textfmt
import trelby.util as util
from trelby.importers.common import (
    ImportResult,
    addElem,
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
        for text in para.xpath("Text"):
            # text.text is None for paragraphs with no text
            if text.text:
                s += text.text

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
