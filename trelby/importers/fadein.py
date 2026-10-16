# Fade In files.
#
# a Fade In file is a zipped document.xml file, in open screenplay format:
# http://sourceforge.net/projects/openscrfmt/files/latest/download

import io
import re
import zipfile

import trelby.screenplay as screenplay
from trelby.importers.common import (
    ImportFailed,
    ImportResult,
    addElem,
    checkLines,
    checkNotEmpty,
    parseXML,
)

# whether parse takes bytes rather than str
BINARY = True

ELEM_MAP = {
    "Action": screenplay.ACTION,
    "Character": screenplay.CHARACTER,
    "Dialogue": screenplay.DIALOGUE,
    "Parenthetical": screenplay.PAREN,
    "Scene Heading": screenplay.SCENE,
    "Shot": screenplay.SHOT,
    "Transition": screenplay.TRANSITION,
}

# the html formatting in the texts, removed by sanitizeStr
RE_REMOVE = [r"<font[^>]*>", r"<size[^>]*>", r"<bgcolor[^>]*>"]
REMOVE = [
    "<b>",
    "</b>",
    "<i>",
    "</i>",
    "<u>",
    "</u>",
    "</font>",
    "</size>",
    "</bgcolor>",
]


# removes html formatting from s, and returns list of lines.
# if s is None, return a list with single empty string.
def sanitizeStr(s):
    if s:
        for r in RE_REMOVE:
            s = re.sub(r, "", s)
        for r in REMOVE:
            s = s.replace(r, "")

        if s:
            return s.split("<br>")

    return [""]


def parse(data, options=None):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as fadein_file:
            with fadein_file.open("document.xml") as fadein_document:
                data = fadein_document.read()
    except Exception:
        raise ImportFailed(_("File is not a valid .fadein file."))

    checkNotEmpty(data)
    root = parseXML(data)
    lines = []

    for para in root.xpath("paragraphs/para"):
        # check for notes/synopsis, import as Note.
        if para.get("note"):
            addElem(lines, screenplay.NOTE, sanitizeStr(para.get("note")))

        if para.get("synopsis"):
            addElem(lines, screenplay.NOTE, sanitizeStr(para.get("synopsis")))

        # look for the <style> and <text> tags. Bail if no <text> found.
        styl = para.xpath("style")
        txt = para.xpath("text")

        if not txt:
            continue

        if styl:
            lt = ELEM_MAP.get(styl[0].get("basestylename"), screenplay.ACTION)
        else:
            lt = screenplay.ACTION

        items = sanitizeStr(txt[0].text)

        if (lt == screenplay.PAREN) and items and (items[0][0] != "("):
            items[0] = "(" + items[0]
            items[-1] = items[-1] + ")"

        addElem(lines, lt, items)

    checkLines(lines)

    return ImportResult(lines)
