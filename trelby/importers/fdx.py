# Final Draft (FDX) files.

import trelby.screenplay as screenplay
import trelby.textfmt as textfmt
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


def parse(data, options=None):
    checkNotEmpty(data)

    # https://github.com/trelby/trelby/issues/61
    data = data.replace(" ", "\n")

    root = parseXML(data)
    lines = []

    for para in root.xpath("Content//Paragraph"):
        addedNote = False
        et = para.get("Type")

        # Check for script notes
        s = ""
        for notes in para.xpath("ScriptNote/Paragraph/Text"):
            if notes.text:
                s += notes.text

            # FD has AdornmentStyle set to "0" on notes with newline.
            if notes.get("AdornmentStyle") == "0":
                s += "\n"

        if s:
            addElem(lines, screenplay.NOTE, s.split("\n"))
            addedNote = True

        # "General" has embedded Dual Dialogue paragraphs inside it;
        # nothing to do for the General element itself.
        #
        # If no type is defined (like inside scriptnote), skip.
        if (et == "General") or (et is None):
            continue

        s = ""
        fmt = ""
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

        # don't remove paragraphs with no text, unless that paragraph
        # contained a scriptnote
        if s or not addedNote:
            lt = ELEM_MAP.get(et, screenplay.ACTION)
            firstLine = len(lines)
            addElem(lines, lt, s.split("\n"), textfmt.compact(fmt))

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

    checkLines(lines)

    return ImportResult(lines)
