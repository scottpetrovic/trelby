# operations behind the MCP server (see mcpserver.py). they work on a
# document, which is either a .trelby file on disk (FileDoc, here) or a
# script open in the app (AppDoc, in mcpapp.py), and don't depend on the
# MCP SDK or the GUI.
#
# the script is divided into parts: part 0 is whatever comes before the
# first scene heading / act break (often empty), and part n (1-based) is
# the n:th scene or act break, i.e. item n in the outline.
#
# every read returns the document's revision (a hash of its contents),
# and every write must be given the revision it was based on. if the
# script has changed in between, the write is refused, so that edits are
# never made using part numbers that have since shifted.

import hashlib
import os
import re

import trelby.characterprofiles as characterprofiles
import trelby.config as config
import trelby.error as error
import trelby.misc as misc
import trelby.screenplay as screenplay
import trelby.translations as translations
import trelby.undo as undo
import trelby.util as util
from trelby.line import Line
from trelby.screenplay import (
    ACTBREAK,
    ACTION,
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


# an error caused by the request (bad arguments, changed script, ...),
# whose message is meant to be shown to the client.
class ToolError(Exception):
    pass


_cfgGl = None


# initialize what's needed to load scripts without the app. not needed
# (or wanted) when running inside the app.
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


# there are two kinds of revision: a FileDoc's is the hash of the file's
# bytes, so any change to the file (e.g. saving it in the app) is caught,
# and a LiveDoc's is linesRevision's hash of the script in memory. they
# differ even for the same script, so a revision from the file server
# can't be used with the app's, or the other way around. 16 hex digits
# are plenty, since a revision is only compared with the current one.
def revisionOf(data):
    return hashlib.sha256(data).hexdigest()[:16]


# revision of a script in memory: covers everything the tools can see or
# change in the script's text, world building notes and character
# profiles, but not e.g. the cursor position.
#
# the lines are hashed as wrapped, so a rewrap alone (e.g. after a
# formatting setting changes) also changes the revision. each Line
# attribute must be listed here, or changing only it won't be noticed
# (see undo.lines2storage). the title page isn't covered: tools only
# report it, never change it.
def linesRevision(sp):
    s = "\n".join(
        "%s|%s|%s|%s|%s|%s|%s"
        % (
            ln,
            ln.pageLock or "",
            int(ln.dual),
            ln.color or "",
            ln.fmt or "",
            int(ln.centered),
            ln.sceneLock or "",
        )
        for ln in sp.lines
    )

    if sp.worldBuilding.text:
        s += "\0" + sp.worldBuilding.text

    for prof in sp.characterProfiles.profiles:
        s += "\0%s\0%s\0%d" % (prof.name, prof.notes, len(prof.photos))

    return revisionOf(s.encode("UTF-8"))


def staleError(revision, current):
    return ToolError(
        "The script has changed since revision '%s' was read (it is now "
        "'%s'). Read it again before making changes." % (revision, current)
    )


def checkPath(path, mustExist=True):
    if not path or not os.path.isabs(path):
        raise ToolError("Path must be absolute: '%s'." % path)

    path = os.path.normpath(path)

    if not path.lower().endswith(".trelby"):
        raise ToolError("Not a .trelby file: '%s'." % path)

    if mustExist and not os.path.isfile(path):
        raise ToolError("File not found: '%s'." % path)

    return path


# a .trelby file on disk. every operation loads it, and every write saves
# it back, keeping the old file as path + ".bak".
#
# documents have these methods:
#
#  read(): return (Screenplay, revision). the Screenplay must not be
#   modified.
#
#  write(revision, edit, ownUndo): check the revision, call edit(sp) to
#   modify the script, store the result and return (Screenplay, new
#   revision). edit returns the (first, last) range of lines it inserted
#   or joined, which need to be rewrapped, or None. ownUndo is True if
#   edit uses a Screenplay method that records its own undo information.
#   if edit raises ToolError, it must not have modified anything.
#
#  describe(sp): return a dict of information about the document.
class FileDoc:
    def __init__(self, path):
        self.path = checkPath(path)

    def read(self):
        init()

        try:
            with open(self.path, "rb") as f:
                data = f.read()
        except OSError as e:
            raise ToolError("Can't read '%s': %s." % (self.path, e.strerror or e))

        try:
            sp = screenplay.Screenplay.load(data.decode("UTF-8"), _cfgGl)[0]
        except (UnicodeDecodeError, error.TrelbyError) as e:
            raise ToolError("Can't load '%s': %s" % (self.path, e))

        return (sp, revisionOf(data))

    def write(self, revision, edit, ownUndo=False):
        sp, current = self.read()

        if revision != current:
            raise staleError(revision, current)

        # the changed-lines range edit returns and ownUndo don't matter
        # here: save() rewraps the whole script and throws away the undo
        # history anyway
        edit(sp)

        return (sp, save(sp, self.path))

    def describe(self, sp):
        return {"path": self.path}


# reformat and save the script. returns the new revision.
def save(sp, path, backup=True):
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


# a script in memory that has undo history, like one open in the app.
# edits are recorded for undo and rewrapped in place, and the cursor is
# moved to the start of the change. mcpapp.AppDoc adds updating the
# screen.
class LiveDoc:
    def __init__(self, sp):
        self.sp = sp

    def read(self):
        return (self.sp, linesRevision(self.sp))

    def describe(self, sp):
        return {
            "modified": sp.isModified(),
            "cursor_scene": partOfLine(sp, sp.line),
        }

    # raise ToolError if the script can't be edited right now
    def checkWritable(self):
        pass

    # called after the script has been changed
    def changed(self):
        pass

    def write(self, revision, edit, ownUndo=False):
        self.checkWritable()

        sp = self.sp
        current = linesRevision(sp)

        if revision != current:
            raise staleError(revision, current)

        sp.clearAutoComp()
        sp.clearMark()

        # the undo step spans both the edit and the rewrapping it causes,
        # so undoing it restores the old lines exactly. an edit with
        # ownUndo records its own step, which must not be wrapped in a
        # second one, and returns None, leaving any rewrapping to the
        # Screenplay method it uses.
        u = None if ownUndo else undo.AnyDifference(sp)

        changedLines = edit(sp)

        if changedLines:
            sp.rewrapSpeechesAround(*changedLines)
            sp.line = min(changedLines[0], len(sp.lines) - 1)
            sp.column = 0

        sp.validatePos()

        if u:
            u.setAfter(sp)
            sp.addUndo(u)

        sp.markChanged()
        sp.paginate()

        self.changed()

        return (sp, linesRevision(sp))


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


# return the index of the part containing the given line.
def partOfLine(sp, line):
    for idx, (first, last) in enumerate(getParts(sp)):
        if first <= line <= last:
            return idx

    return 0


# return the elements on lines first - last as a list of dicts.
#
# sp.lines are wrapped lines, and an element runs up to the next LB_LAST
# line, so first must be the start of an element. lb2str turns each line
# break back into what the user typed: the space(s) a word wrap replaced
# (" ", "  " or ""), or "\n" for a forced break. text formatting
# (Line.fmt) and scene locks are not returned, and buildLines doesn't take
# them, so replacing a scene drops its bold / italic / underline.
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

        if sp.hasCenteredFlag(start):
            elem["centered"] = True

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


# convert a list of element dicts ({"type", "text", optional "color",
# "dual" and "centered"}) to unwrapped lines. if needHeading is True, the first element
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

        centered = bool(elem.get("centered"))
        if centered and (lt != ACTION):
            raise ToolError("Only action elements can be centered.")

        parts = util.fixNL(text).replace("\t", " ").split("\n")

        # one Line per forced-break segment, not yet word wrapped (the
        # document's write does that). the element's flags only go on its
        # first line, the only one where Line gives them a meaning.
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
                    centered=centered and isFirst,
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
            d["scene_number"] = item.sceneNr

        if item.summary:
            d["summary"] = item.summary

        if item.color:
            d["color"] = "#" + item.color

        ret.append(d)

    return ret


def getInfo(doc):
    sp, rev = doc.read()

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

    ret = doc.describe(sp)
    ret.update(
        {
            "revision": rev,
            "title_page": titles,
            "pages": len(sp.pages) - 1,
            "page_length": round(sp.getPageLength(), 2),
            "words": sp.getWordCount(),
            "scenes": sum(1 for item in outline if item.lt == SCENE),
            "act_breaks": sum(1 for item in outline if item.lt == ACTBREAK),
            "characters": len(characters),
            "character_profiles": len(sp.characterProfiles.profiles),
            "has_world_building": bool(sp.worldBuilding.text.strip()),
        }
    )

    return ret


def listScenes(doc):
    sp, rev = doc.read()

    return {"revision": rev, "scenes": getOutline(sp)}


def readScenes(doc, first, last=None):
    sp, rev = doc.read()

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


def listCharacters(doc):
    sp, rev = doc.read()

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


def search(doc, query, caseSensitive=False):
    if not query:
        raise ToolError("Search text can't be empty.")

    sp, rev = doc.read()

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
def export(doc, fmt, outputPath=None):
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

    sp, rev = doc.read()

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


# do a write and return the new revision and outline.
def write(doc, revision, edit, ownUndo=False):
    sp, rev = doc.write(revision, edit, ownUndo)

    return {"revision": rev, "scenes": getOutline(sp)}


# replace part 'index' with the given elements. a scene / act break being
# replaced keeps its color unless the new heading says otherwise, and a
# scene replaced by a scene keeps its locked number.
def replaceScene(doc, revision, index, elements):
    def edit(sp):
        first, last = getPart(sp, index)
        lines = buildLines(elements, index > 0)

        if (index > 0) and ("color" not in elements[0]):
            lines[0].color = sp.getSceneColor(first)

        if index > 0:
            lines[0].sceneLock = sp.getSceneLock(first)

        # like cut + paste: page locks on the replaced lines move to the
        # line after them
        if last >= first:
            sp.movePageLocksForward(first, last)

        sp.lines[first : last + 1] = lines

        return (first, first + len(lines) - 1)

    return write(doc, revision, edit)


# insert elements before part 'position' (1 - number of parts, or one
# more to append at the end).
def insertScenes(doc, revision, position, elements):
    def edit(sp):
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

        return (at, at + len(lines) - 1)

    return write(doc, revision, edit)


def deleteScene(doc, revision, index):
    def edit(sp):
        first, last = getPart(sp, index)

        if last < first:
            raise ToolError("There is nothing before the first scene to delete.")

        sp.movePageLocksForward(first, last)
        del sp.lines[first : last + 1]

        if not sp.lines:
            sp.lines = [Line(LB_LAST, SCENE)]

        # the elements around the gap may need rewrapping, e.g. if they
        # end up in a dual dialogue
        first = min(first, len(sp.lines) - 1)

        return (max(first - 1, 0), first)

    return write(doc, revision, edit)


def moveScene(doc, revision, index, newIndex):
    def edit(sp):
        first = getPart(sp, index, False)[0]
        getPart(sp, newIndex, False)

        if index == newIndex:
            raise ToolError("The scene is already at index %d." % index)

        # part n is outline item n - 1: moveSceneTo counts from 0, without
        # the opening part
        if not sp.moveSceneTo(first, newIndex - 1):
            raise ToolError("Moving scene %d to %d failed." % (index, newIndex))

        return None

    return write(doc, revision, edit, True)


# rename a character in cues and in mentions in other text, like renaming
# a character profile in the app does. also renames the profile.
def renameCharacter(doc, revision, oldName, newName):
    old = characterprofiles.normalizeName(oldName)
    new = characterprofiles.normalizeName(newName)

    if not old or not new:
        raise ToolError("Character names can't be empty.")

    if old == new:
        raise ToolError("The new name is the same as the old one.")

    counts = {}

    def edit(sp):
        names = {characterprofiles.normalizeName(n) for n in sp.getCharacterNames()}
        prof = sp.characterProfiles.get(old)

        if (old not in names) and not prof:
            raise ToolError("Character '%s' was not found." % old)

        counts["cues"], counts["mentions"] = sp.renameCharacters({old: new}, True)

        return None

    ret = write(doc, revision, edit, True)
    ret.update({"cues_renamed": counts["cues"], "mentions_renamed": counts["mentions"]})

    return ret


def getWorldBuilding(doc):
    sp, rev = doc.read()

    return {"revision": rev, "text": sp.worldBuilding.text}


# replace the script's world building notes with the given text, like
# editing them in Tools > World building does.
def setWorldBuilding(doc, revision, text):
    if not isinstance(text, str):
        raise ToolError("The text must be a string.")

    text = util.fixNL(text)

    sp, current = doc.read()

    if revision != current:
        raise staleError(revision, current)

    # nothing to save, or to undo
    if text == sp.worldBuilding.text:
        return {"revision": current, "length": len(text)}

    def edit(sp):
        u = undo.WorldBuildingText(sp)
        sp.worldBuilding.text = text
        u.setAfter(sp)
        sp.addUndo(u)

        return None

    sp, rev = doc.write(revision, edit, True)

    return {"revision": rev, "length": len(sp.worldBuilding.text)}


def profileDict(prof, scriptNames):
    name = characterprofiles.normalizeName(prof.name)

    return {
        "name": name,
        "notes": prof.notes,
        "photos": len(prof.photos),
        "in_script": name in scriptNames,
    }


def scriptNamesOf(sp):
    return {characterprofiles.normalizeName(n) for n in sp.getCharacterNames()}


# return the character profiles, or only the one for 'name'.
def getCharacterProfiles(doc, name=None):
    sp, rev = doc.read()
    names = scriptNamesOf(sp)

    if name is None:
        profs = sp.characterProfiles.profiles
    else:
        prof = sp.characterProfiles.get(name)

        if not prof:
            raise ToolError(
                "There is no profile for '%s'."
                % characterprofiles.normalizeName(name)
            )

        profs = [prof]

    return {"revision": rev, "profiles": [profileDict(p, names) for p in profs]}


# do a write that changes the character profiles, as one undo step.
# edit(sp) changes sp.characterProfiles and returns the result to
# include.
def writeProfiles(doc, revision, edit):
    ret = {}

    def wrapper(sp):
        u = undo.CharacterProfiles(sp)
        ret.update(edit(sp))
        u.setAfter(sp)
        sp.addUndo(u)

        return None

    ret["revision"] = doc.write(revision, wrapper, True)[1]

    return ret


# create a profile for 'name' or replace its notes. photos are kept.
def setCharacterProfile(doc, revision, name, notes):
    name = characterprofiles.normalizeName(name)

    if not name:
        raise ToolError("Character names can't be empty.")

    if not isinstance(notes, str):
        raise ToolError("The notes must be a string.")

    notes = util.fixNL(notes)

    def edit(sp):
        profiles = sp.characterProfiles
        prof = profiles.get(name)
        created = prof is None

        if created:
            prof = characterprofiles.CharacterProfile(name)
            profiles.profiles.append(prof)
            profiles.sort()

        prof.notes = notes

        return {"created": created, "profile": profileDict(prof, scriptNamesOf(sp))}

    return writeProfiles(doc, revision, edit)


# delete the profile for 'name', including its photos. the character
# itself stays in the script.
def deleteCharacterProfile(doc, revision, name):
    name = characterprofiles.normalizeName(name)

    def edit(sp):
        prof = sp.characterProfiles.get(name)

        if not prof:
            raise ToolError("There is no profile for '%s'." % name)

        sp.characterProfiles.profiles.remove(prof)

        return {"deleted": name}

    return writeProfiles(doc, revision, edit)


# create a new .trelby file containing the given elements.
def createScript(path, elements):
    init()
    path = checkPath(path, False)

    if os.path.exists(path):
        raise ToolError("'%s' already exists." % path)

    if not os.path.isdir(os.path.dirname(path)):
        raise ToolError("Directory '%s' doesn't exist." % os.path.dirname(path))

    sp = screenplay.Screenplay(_cfgGl)
    sp.lines = buildLines(elements, False)

    rev = save(sp, path, False)

    return {"revision": rev, "scenes": getOutline(sp)}


# the operations on documents, by MCP tool name. each takes a document and
# a dict of the tool's other arguments.
OPS = {
    "get_script_info": lambda d, a: getInfo(d),
    "list_scenes": lambda d, a: listScenes(d),
    "read_scenes": lambda d, a: readScenes(d, a["first"], a.get("last")),
    "list_characters": lambda d, a: listCharacters(d),
    "search_script": lambda d, a: search(
        d, a["query"], a.get("case_sensitive", False)
    ),
    "export_script": lambda d, a: export(d, a["format"], a.get("output_path")),
    "replace_scene": lambda d, a: replaceScene(
        d, a["revision"], a["index"], a["elements"]
    ),
    "insert_scenes": lambda d, a: insertScenes(
        d, a["revision"], a["position"], a["elements"]
    ),
    "delete_scene": lambda d, a: deleteScene(d, a["revision"], a["index"]),
    "move_scene": lambda d, a: moveScene(
        d, a["revision"], a["index"], a["new_index"]
    ),
    "rename_character": lambda d, a: renameCharacter(
        d, a["revision"], a["old_name"], a["new_name"]
    ),
    "get_world_building": lambda d, a: getWorldBuilding(d),
    "set_world_building": lambda d, a: setWorldBuilding(d, a["revision"], a["text"]),
    "get_character_profiles": lambda d, a: getCharacterProfiles(d, a.get("name")),
    "set_character_profile": lambda d, a: setCharacterProfile(
        d, a["revision"], a["name"], a["notes"]
    ),
    "delete_character_profile": lambda d, a: deleteCharacterProfile(
        d, a["revision"], a["name"]
    ),
}
