# operations on .trelby files for the MCP server (see mcpserver.py).
# everything here loads a script from disk, works on the Screenplay and
# writes it back, without any GUI, so that this module doesn't depend on
# the MCP SDK and could also be used by a server running inside the app.
#
# the script is divided into parts: part 0 is whatever comes before the
# first scene heading / act break (often empty), and part n (1-based) is
# the n:th scene or act break, i.e. item n in the outline.
#
# every read returns the file's revision (a hash of its contents), and
# every write must be given the revision it was based on. if the file has
# changed in between, the write is refused, so that edits are never made
# using part numbers that have since shifted.

import hashlib
import os
import re

import trelby.characterprofiles as characterprofiles
import trelby.config as config
import trelby.error as error
import trelby.misc as misc
import trelby.screenplay as screenplay
import trelby.translations as translations
import trelby.util as util
from trelby.line import Line
from trelby.screenplay import (
    ACTBREAK,
    CHARACTER,
    LB_FORCED,
    LB_LAST,
    SCENE,
)

# export formats, mapped to whether they're binary
EXPORT_FORMATS = {
    "pdf": True,
    "fountain": False,
    "text": False,
    "html": False,
    "fdx": False,
    "rtf": False,
}

# maximum number of matches returned by search
MAX_MATCHES = 200


# an error caused by the request (bad arguments, changed file, ...),
# whose message is meant to be shown to the client.
class ToolError(Exception):
    pass


_cfgGl = None


def init():
    global _cfgGl

    if _cfgGl is None:
        translations.trelby_translations_load()
        misc.init(False)
        util.init(False)

        _cfgGl = config.ConfigGlobal()


# element type name ("action", "act break", ...) for each line type
def typeName(lt):
    return config.lt2ti(lt).name.lower()


# return the line type for the given element type name, accepting a few
# variations like "Act_Break" and "paren".
def typeFromName(name):
    key = re.sub(r"[\s_-]", "", str(name).lower())

    if key == "paren":
        key = "parenthetical"

    for ti in config.getTIs():
        if ti.name.lower().replace(" ", "") == key:
            return ti.lt

    raise ToolError(
        "Unknown element type '%s'. Valid types: %s."
        % (name, ", ".join(typeName(ti.lt) for ti in config.getTIs()))
    )


def revisionOf(data):
    return hashlib.sha256(data).hexdigest()[:16]


def checkPath(path, mustExist=True):
    if not path or not os.path.isabs(path):
        raise ToolError("Path must be absolute: '%s'." % path)

    path = os.path.normpath(path)

    if not path.lower().endswith(".trelby"):
        raise ToolError("Not a .trelby file: '%s'." % path)

    if mustExist and not os.path.isfile(path):
        raise ToolError("File not found: '%s'." % path)

    return path


# load the script at path. returns (Screenplay, revision).
def load(path):
    init()
    path = checkPath(path)

    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        raise ToolError("Can't read '%s': %s." % (path, e.strerror or e))

    try:
        sp = screenplay.Screenplay.load(data.decode("UTF-8"), _cfgGl)[0]
    except (UnicodeDecodeError, error.TrelbyError) as e:
        raise ToolError("Can't load '%s': %s" % (path, e))

    return (sp, revisionOf(data))


# load the script at path for modification, checking that it is still at
# the given revision.
def loadForWrite(path, revision):
    sp, current = load(path)

    if revision != current:
        raise ToolError(
            "The script has changed since revision '%s' was read (it is now "
            "'%s'). Read it again before making changes." % (revision, current)
        )

    return sp


# reformat and save the script, keeping the old file as path + ".bak".
# returns the new revision.
def save(sp, path, backup=True):
    if not sp.lines:
        sp.lines = [Line(LB_LAST, SCENE)]

    # some edits (moveSceneTo, renameCharacters) add undo history, which
    # reformatAll refuses to run with. nobody can undo here anyway.
    sp.firstUndo = sp.lastUndo = sp.currentUndo = None
    sp.undoMemoryUsed = 0

    sp.reformatAll()
    sp.paginate()
    sp.validatePos()

    data = sp.save()

    try:
        util.atomicWrite(path, data, backup)
    except OSError as e:
        raise ToolError("Can't write '%s': %s." % (path, e.strerror or e))

    return revisionOf(data)


# return a list of (first, last) line ranges for the script's parts. part
# 0 is (0, -1) if there's nothing before the first scene.
def getParts(sp):
    starts = sp.getOutlineStarts()
    bounds = starts + [len(sp.lines)]

    ret = [(0, bounds[0] - 1)]

    for i in range(len(starts)):
        ret.append((bounds[i], bounds[i + 1] - 1))

    return ret


def getPart(sp, index, allowOpening=True):
    parts = getParts(sp)
    first = 0 if allowOpening else 1

    if not isinstance(index, int) or not (first <= index < len(parts)):
        raise ToolError(
            "Scene index %s is out of range; valid indexes are %d - %d."
            % (index, first, len(parts) - 1)
        )

    return parts[index]


# return the elements on lines first - last as a list of dicts.
def getElements(sp, first, last):
    ls = sp.lines
    ret = []

    i = first
    while i <= last:
        start = i
        text = ""

        while 1:
            text += ls[i].text

            if ls[i].lb == LB_LAST:
                break

            text += config.lb2str(ls[i].lb)
            i += 1

        ln = ls[start]
        elem = {"type": typeName(ln.lt), "text": text}

        if ln.lt in (SCENE, ACTBREAK) and sp.getSceneColor(start):
            elem["color"] = "#" + ln.color

        if ln.lt == CHARACTER and ln.dual:
            elem["dual"] = True

        ret.append(elem)
        i += 1

    return ret


def parseColor(color):
    if color is None:
        return None

    s = str(color).lstrip("#").lower()

    if not re.fullmatch(r"[0-9a-f]{6}", s):
        raise ToolError("Invalid color '%s'; use the form '#rrggbb'." % color)

    return s


# convert a list of element dicts ({"type", "text", optional "color" and
# "dual"}) to unwrapped lines. if needHeading is True, the first element
# must be a scene heading or act break.
def buildLines(elements, needHeading):
    if not isinstance(elements, list) or not elements:
        raise ToolError("At least one element is needed.")

    ret = []

    for n, elem in enumerate(elements, 1):
        if not isinstance(elem, dict) or ("type" not in elem):
            raise ToolError("Element %d has no type." % n)

        lt = typeFromName(elem["type"])
        text = elem.get("text", "")

        if not isinstance(text, str):
            raise ToolError("Element %d's text is not a string." % n)

        if (n == 1) and needHeading and (lt not in (SCENE, ACTBREAK)):
            raise ToolError(
                "The first element must be a scene heading or act break, so "
                "that it doesn't become part of the previous scene."
            )

        color = None
        if elem.get("color") is not None:
            if lt not in (SCENE, ACTBREAK):
                raise ToolError("Only scenes and act breaks can have a color.")

            color = parseColor(elem["color"])

        dual = bool(elem.get("dual"))
        if dual and (lt != CHARACTER):
            raise ToolError("Only character elements can be marked dual.")

        parts = util.fixNL(text).replace("\t", " ").split("\n")

        for i, part in enumerate(parts):
            isFirst = i == 0
            lb = LB_LAST if (i == len(parts) - 1) else LB_FORCED

            ret.append(
                Line(
                    lb,
                    lt,
                    part.strip(),
                    dual=dual and isFirst,
                    color=color if isFirst else None,
                )
            )

    return ret


# summary of the script's outline, as returned after every change.
def getOutline(sp):
    ret = []
    parts = getParts(sp)

    if parts[0][1] >= 0:
        ret.append(
            {
                "index": 0,
                "type": "opening",
                "heading": "(material before the first scene)",
                "lines": parts[0][1] + 1,
            }
        )

    for i, item in enumerate(sp.getOutline(), 1):
        d = {
            "index": i,
            "type": typeName(item.lt),
            "heading": item.heading,
            "page": item.page,
        }

        if item.sceneNr:
            d["scene_number"] = int(item.sceneNr)

        if item.summary:
            d["summary"] = item.summary

        if item.color:
            d["color"] = "#" + item.color

        ret.append(d)

    return ret


def getInfo(path):
    sp, rev = load(path)

    titles = []
    for page in sp.titles.pages:
        for ts in page:
            titles.append("\n".join(ts.items))

    outline = sp.getOutline()
    characters = {
        characterprofiles.normalizeName(e["text"])
        for first, last in getParts(sp)
        for e in getElements(sp, first, last)
        if e["type"] == typeName(CHARACTER)
    }
    characters.discard("")

    return {
        "path": os.path.normpath(path),
        "revision": rev,
        "title_page": titles,
        "pages": len(sp.pages) - 1,
        "page_length": round(sp.getPageLength(), 2),
        "words": sp.getWordCount(),
        "scenes": sum(1 for item in outline if item.lt == SCENE),
        "act_breaks": sum(1 for item in outline if item.lt == ACTBREAK),
        "characters": len(characters),
    }


def listScenes(path):
    sp, rev = load(path)

    return {"revision": rev, "scenes": getOutline(sp)}


def readScenes(path, first, last=None):
    sp, rev = load(path)

    if last is None:
        last = first

    getPart(sp, first)
    getPart(sp, last)

    if last < first:
        raise ToolError("Last index (%d) is before the first (%d)." % (last, first))

    parts = getParts(sp)
    scenes = []

    for idx in range(first, last + 1):
        start, end = parts[idx]
        scenes.append({"index": idx, "elements": getElements(sp, start, end)})

    return {"revision": rev, "scenes": scenes}


def listCharacters(path):
    sp, rev = load(path)

    chars = {}
    charType = typeName(CHARACTER)

    for idx, (first, last) in enumerate(getParts(sp)):
        for e in getElements(sp, first, last):
            if e["type"] != charType:
                continue

            name = characterprofiles.normalizeName(e["text"])
            if not name:
                continue

            c = chars.setdefault(
                name, {"name": name, "speeches": 0, "scenes": [], "has_profile": False}
            )
            c["speeches"] += 1

            if idx not in c["scenes"]:
                c["scenes"].append(idx)

    for c in chars.values():
        c["has_profile"] = sp.characterProfiles.get(c["name"]) is not None

    ret = sorted(chars.values(), key=lambda c: (-c["speeches"], c["name"]))

    return {"revision": rev, "characters": ret}


def search(path, query, caseSensitive=False):
    if not query:
        raise ToolError("Search text can't be empty.")

    sp, rev = load(path)

    if not caseSensitive:
        query = query.lower()

    matches = []
    truncated = False

    for idx, (first, last) in enumerate(getParts(sp)):
        for e in getElements(sp, first, last):
            text = e["text"] if caseSensitive else e["text"].lower()

            if query in text:
                if len(matches) == MAX_MATCHES:
                    truncated = True
                    break

                matches.append({"index": idx, "type": e["type"], "text": e["text"]})

    return {"revision": rev, "matches": matches, "truncated": truncated}


# export the script. if outputPath is given, the result is written there,
# otherwise it is returned (not possible for PDF).
def export(path, fmt, outputPath=None):
    fmt = str(fmt).lower()

    if fmt not in EXPORT_FORMATS:
        raise ToolError(
            "Unknown format '%s'. Valid formats: %s."
            % (fmt, ", ".join(EXPORT_FORMATS))
        )

    if EXPORT_FORMATS[fmt] and not outputPath:
        raise ToolError("Exporting to %s needs an output path." % fmt)

    if outputPath is not None:
        if not os.path.isabs(outputPath):
            raise ToolError("Output path must be absolute: '%s'." % outputPath)

        outputPath = os.path.normpath(outputPath)

        if outputPath.lower().endswith(".trelby"):
            raise ToolError("Exporting over a .trelby file is not allowed.")

    sp, rev = load(path)

    try:
        if fmt == "pdf":
            data = sp.generatePDF()
        elif fmt == "fountain":
            data = sp.generateFountain()
        elif fmt == "text":
            data = sp.generateText(False)
        elif fmt == "html":
            data = sp.generateHtml()
        elif fmt == "fdx":
            data = sp.generateFDX()
        else:
            data = sp.generateRTF()
    except Exception as e:
        raise ToolError("Exporting to %s failed: %s: %s" % (fmt, type(e).__name__, e))

    if outputPath is None:
        if isinstance(data, bytes):
            data = data.decode("UTF-8")

        return {"revision": rev, "format": fmt, "content": data}

    try:
        util.atomicWrite(outputPath, data)
    except OSError as e:
        raise ToolError("Can't write '%s': %s." % (outputPath, e.strerror or e))

    return {"revision": rev, "format": fmt, "output_path": outputPath}


def afterWrite(sp, path, backup=True):
    rev = save(sp, path, backup)

    return {"revision": rev, "scenes": getOutline(sp)}


# replace part 'index' with the given elements. a scene / act break being
# replaced keeps its color unless the new heading says otherwise.
def replaceScene(path, revision, index, elements):
    sp = loadForWrite(path, revision)
    first, last = getPart(sp, index)

    lines = buildLines(elements, index > 0)

    if (index > 0) and ("color" not in elements[0]):
        lines[0].color = sp.getSceneColor(first)

    # like cut + paste: page locks on the replaced lines move to the line
    # after them
    if last >= first:
        sp.movePageLocksForward(first, last)

    sp.lines[first : last + 1] = lines

    return afterWrite(sp, path)


# insert elements before part 'position' (1 - number of parts, or one
# more to append at the end).
def insertScenes(path, revision, position, elements):
    sp = loadForWrite(path, revision)
    parts = getParts(sp)

    if not isinstance(position, int) or not (1 <= position <= len(parts)):
        raise ToolError(
            "Position %s is out of range; valid positions are 1 - %d."
            % (position, len(parts))
        )

    lines = buildLines(elements, True)

    if position < len(parts):
        at = parts[position][0]
    else:
        at = len(sp.lines)

    sp.lines[at:at] = lines

    return afterWrite(sp, path)


def deleteScene(path, revision, index):
    sp = loadForWrite(path, revision)
    first, last = getPart(sp, index)

    if last < first:
        raise ToolError("There is nothing before the first scene to delete.")

    sp.movePageLocksForward(first, last)
    del sp.lines[first : last + 1]

    return afterWrite(sp, path)


def moveScene(path, revision, index, newIndex):
    sp = loadForWrite(path, revision)
    first = getPart(sp, index, False)[0]
    getPart(sp, newIndex, False)

    if index == newIndex:
        raise ToolError("The scene is already at index %d." % index)

    if not sp.moveSceneTo(first, newIndex - 1):
        raise ToolError("Moving scene %d to %d failed." % (index, newIndex))

    return afterWrite(sp, path)


# rename a character in cues and in mentions in other text, like renaming
# a character profile in the app does. also renames the profile.
def renameCharacter(path, revision, oldName, newName):
    sp = loadForWrite(path, revision)

    old = characterprofiles.normalizeName(oldName)
    new = characterprofiles.normalizeName(newName)

    if not old or not new:
        raise ToolError("Character names can't be empty.")

    if old == new:
        raise ToolError("The new name is the same as the old one.")

    prof = sp.characterProfiles.get(old)
    if prof:
        prof.name = new

    cues, mentions = sp.renameCharacters({old: new})

    if not (cues or mentions or prof):
        raise ToolError("Character '%s' was not found." % old)

    ret = afterWrite(sp, path)
    ret.update({"cues_renamed": cues, "mentions_renamed": mentions})

    return ret


# create a new script containing the given elements.
def createScript(path, elements):
    init()
    path = checkPath(path, False)

    if os.path.exists(path):
        raise ToolError("'%s' already exists." % path)

    if not os.path.isdir(os.path.dirname(path)):
        raise ToolError("Directory '%s' doesn't exist." % os.path.dirname(path))

    sp = screenplay.Screenplay(_cfgGl)
    sp.lines = buildLines(elements, False)

    return afterWrite(sp, path, False)
