# Celtx files.
#
# Celtx files are zipfiles, and the script content is within a file called
# "script-xxx.html", where xxx can be random.

import io
import zipfile

from lxml import etree

import trelby.screenplay as screenplay
from trelby.importers.common import (
    ImportFailed,
    ImportResult,
    addElem,
    checkLines,
    parseXML,
)

# whether parse takes bytes rather than str
BINARY = True

ELEM_MAP = {
    "action": screenplay.ACTION,
    "character": screenplay.CHARACTER,
    "dialog": screenplay.DIALOGUE,
    "parenthetical": screenplay.PAREN,
    "sceneheading": screenplay.SCENE,
    "shot": screenplay.SHOT,
    "transition": screenplay.TRANSITION,
    "act": screenplay.ACTBREAK,
}


def parse(data, options=None):
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except Exception:
        raise ImportFailed(_("File is not a valid Celtx script file."))

    with z:
        scripts = [s for s in z.namelist() if s.startswith("script")]

        if len(scripts) == 0:
            raise ImportFailed(_("Unable to find script in this Celtx file."))

        with z.open(scripts[0]) as f:
            content = f.read()

    if not content:
        raise ImportFailed(_("Script seems to be empty."))

    root = parseXML(content, etree.HTMLParser())
    lines = []

    for para in root.xpath("/html/body/p"):
        items = []
        for line in para.itertext():
            text = line.replace("\n", " ").strip()
            if text != "":
                items.append(text)

        lt = ELEM_MAP.get(para.get("class"), screenplay.ACTION)

        if items:
            addElem(lines, lt, items)

    checkLines(lines)

    return ImportResult(lines)
