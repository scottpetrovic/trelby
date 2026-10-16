# Adobe Story files.
#
# astx files are xml files. The textlines can be found under
# AdobeStory/document/stream/section/scene/paragraph which contain one or
# more textRun/break elements, to be joined. The paragraph attribute
# "element" gives us the element style.

import trelby.screenplay as screenplay
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
    "Dialog": screenplay.DIALOGUE,
    "Parenthetical": screenplay.PAREN,
    "SceneHeading": screenplay.SCENE,
    "Shot": screenplay.SHOT,
    "Transition": screenplay.TRANSITION,
}


def parse(data, options=None):
    checkNotEmpty(data)
    root = parseXML(data)
    lines = []

    for para in root.xpath("/AdobeStory/document/stream/section/scene/paragraph"):
        lt = ELEM_MAP.get(para.get("element"), screenplay.ACTION)

        items = []
        s = ""

        for text in para:
            if text.tag == "textRun" and text.text:
                s += text.text
            elif text.tag == "break":
                items.append(s.rstrip())
                s = ""

        items.append(s.rstrip())

        addElem(lines, lt, items)

    checkLines(lines, _("File has no content."))

    return ImportResult(lines)
