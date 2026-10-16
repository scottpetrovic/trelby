# the native .trelby file format: save turns a Screenplay into the file's
# bytes, load parses them back. the format is described in
# trelby/fileformat.txt.

import re
from typing import Tuple

import trelby.config as config
import trelby.error as error
import trelby.screenplay.headers as headers
import trelby.screenplay.pagelock as pagelock
import trelby.textfmt as textfmt
import trelby.textutil as textutil
import trelby.screenplay.titles as titles
import trelby.util as util
from trelby.screenplay.line import Line
from trelby.screenplay.constants import (
    ACTION,
    LB_LAST,
    LB_SPACE,
)
from trelby.screenplay.datatypes import Mark, isValidColor


# save script to a utf-8 encoded string and return that
def save(sp) -> bytes:
    output = ""

    output += "\ufeff"
    output += "#Version 3\n"

    output += "#Begin-Auto-Completion \n"
    output += sp.autoCompletion.save()
    output += "#End-Auto-Completion \n"

    output += "#Begin-Config \n"
    output += sp.cfg.save()
    output += "#End-Config \n"

    output += "#Begin-Locations \n"
    output += sp.locations.save()
    output += "#End-Locations \n"

    output += "#Begin-Spell-Checker-Dict \n"
    output += sp.scDict.save()
    output += "#End-Spell-Checker-Dict \n"

    # only written when there are profiles, so that scripts without
    # any stay readable by older versions without a warning
    if sp.characterProfiles.profiles:
        output += "#Begin-Character-Profiles \n"
        output += sp.characterProfiles.save()
        output += "#End-Character-Profiles \n"

    # likewise only written when there's something in it
    if sp.worldBuilding.hasInfo():
        output += "#Begin-World-Building \n"
        output += sp.worldBuilding.save()
        output += "#End-World-Building \n"

    if sp.beatBoard.hasInfo():
        output += "#Begin-Beat-Board \n"
        output += sp.beatBoard.save()
        output += "#End-Beat-Board \n"

    pgs = sp.titles.pages
    for pg in range(len(pgs)):
        if pg != 0:
            output += "#Title-Page \n"

        for i in range(len(pgs[pg])):
            output += "#Title-String %s\n" % str(pgs[pg][i])

    for h in sp.headers.hdrs:
        output += "#Header-String %s\n" % str(h)

    output += "#Header-Empty-Lines %d\n" % sp.headers.emptyLinesAfter

    output += "#Start-Script \n"

    # a line's attributes are written as config lines just before it,
    # and load attaches them to the next script line it reads. they're
    # only written where they mean something (e.g. hasDualFlag rather
    # than ln.dual), which drops flags left on other lines by editing.
    for i, ln in enumerate(sp.lines):
        if ln.pageLock:
            output += "#Page-Lock %s\n" % ln.pageLock

        if sp.hasDualFlag(i):
            output += "#Dual-Dialogue \n"

        color = sp.getSceneColor(i)

        if color:
            output += "#Scene-Color %s\n" % color

        sceneLock = sp.getSceneLock(i)

        if sceneLock:
            output += "#Scene-Lock %s\n" % sceneLock

        if sp.hasCenteredFlag(i):
            output += "#Centered \n"

        if ln.fmt:
            output += "#Format %s\n" % textfmt.encode(ln.getFmt())

        output += str(ln) + "\n"

    return output.encode("UTF-8")


# load script from string s and return a (Screenplay, msg) tuple,
# where msgs is string (possibly empty) of warnings about the loading
# process. fatal errors are indicated by raising a MiscError. note
# that this is a static function.
def load(s: str, cfgGl):
    # imported here, as model imports this module
    from trelby.screenplay.model import Screenplay

    lines = s.splitlines()

    sp = Screenplay(cfgGl)

    # remove default empty line
    sp.lines = []

    if len(lines) < 2:
        raise error.MiscError(
            _("File has too few lines to be a valid\nscreenplay file.")
        )

    key, version = parseConfigLine(lines[0])
    if not key or (key != "Version"):
        raise error.MiscError(
            _("File doesn't seem to be a proper\nscreenplay file.")
        )

    if version not in ("1", "2", "3"):
        raise error.MiscError(
            _("File uses fileformat version '{}',\nwhich is not supported by this version\nof the program.").format(
                version
            )
        )

    version = int(version)

    # current position at 'lines'
    index = 1

    # the optional #Begin-X / #End-X sections come right after the
    # version line, in the order save writes them. getConfigPart only
    # looks at the current position, so a missing section is simply
    # skipped, while one out of order ends up in the loop below as
    # unknown information.
    s, index = getConfigPart(lines, "Auto-Completion", index)
    if s:
        sp.autoCompletion.load(s)

    s, index = getConfigPart(lines, "Config", index)
    if s:
        sp.cfg.load(s)

    s, index = getConfigPart(lines, "Locations", index)
    if s:
        sp.locations.load(s)

    s, index = getConfigPart(lines, "Spell-Checker-Dict", index)
    if s:
        sp.scDict.load(s)

    s, index = getConfigPart(lines, "Character-Profiles", index)
    if s:
        sp.characterProfiles.load(s)

    s, index = getConfigPart(lines, "World-Building", index)
    if s:
        sp.worldBuilding.load(s)

    s, index = getConfigPart(lines, "Beat-Board", index)
    if s:
        sp.beatBoard.load(s)

    # used to keep track that element type only changes after a
    # LB_LAST line.
    prevType = None

    # did we encounter unknown lb types
    unknownLb = False

    # did we encounter unknown element types
    unknownTypes = False

    # did we encounter unknown config lines
    unknownConfigs = False

    # have we seen the Start-Script line. defaults to True in old
    # files which didn't have it.
    startSeen = version < 3

    # page lock to set on the next script line, or None
    pageLock = None

    # whether to set the dual flag on the next script line
    dual = False

    # color to set on the next script line, or None
    color = None

    # scene lock to set on the next script line, or None
    sceneLock = None

    # formatting (as saved by textfmt.encode) to set on the next script
    # line, or None
    fmt = None

    # whether to set the centered flag on the next script line
    centered = False

    for i in range(index, len(lines)):
        s = lines[i]

        if len(s) < 2:
            raise error.MiscError(_("Line {} is too short.").format(i + 1))

        if s[0] == "#":
            key, val = parseConfigLine(s)
            if not key:
                raise error.MiscError(
                    _("Line {} has invalid syntax for\nconfig line.").format(i + 1)
                )

            if key == "Title-Page":
                sp.titles.pages.append([])

            elif key == "Title-String":
                if len(sp.titles.pages) == 0:
                    sp.titles.pages.append([])

                tmp = titles.TitleString([])
                tmp.load(val)
                sp.titles.pages[-1].append(tmp)

            elif key == "Header-String":
                tmp = headers.HeaderString()
                tmp.load(val)
                sp.headers.hdrs.append(tmp)

            elif key == "Header-Empty-Lines":
                sp.headers.emptyLinesAfter = util.str2int(val, 1, 0, 5)

            elif key == "Start-Script":
                startSeen = True

            elif (key == "Page-Lock") and startSeen and pagelock.isValid(val):
                pageLock = val

            elif (key == "Dual-Dialogue") and startSeen:
                dual = True

            elif (key == "Scene-Color") and startSeen and isValidColor(val):
                color = val.lower()

            elif (
                (key == "Scene-Lock") and startSeen and pagelock.isValidScene(val)
            ):
                sceneLock = val

            elif (key == "Format") and startSeen:
                fmt = val

            elif (key == "Centered") and startSeen:
                centered = True

            else:
                unknownConfigs = True

        else:
            if not startSeen:
                unknownConfigs = True

                continue

            # a script line is <lb char><lt char><text>, as written by
            # Line.__str__ (see config's char tables)
            lb = config.char2lb(s[0], False)
            lt = config.char2lt(s[1], False)
            text = textutil.toInputStr(textutil.fromUTF8(s[2:]))

            # an early development version had a separate centered
            # element type
            if s[1] == "^":
                lt = ACTION
                centered = centered or not prevType

            # convert unknown lb types into LB_SPACE
            if lb == None:
                lb = LB_SPACE
                unknownLb = True

            # convert unknown types into ACTION
            if lt == None:
                lt = ACTION
                unknownTypes = True

            if prevType and (lt != prevType):
                raise error.MiscError(
                    _("Line {} has invalid element type.").format(i + 1)
                )

            line = Line(lb, lt, text, pageLock, dual, color)
            line.centered = centered
            line.sceneLock = sceneLock

            if fmt:
                line.fmt = textfmt.decode(fmt, len(text))

            sp.lines.append(line)
            pageLock = None
            dual = False
            color = None
            sceneLock = None
            fmt = None
            centered = False

            if lb != LB_LAST:
                prevType = lt
            else:
                prevType = None

    if not startSeen:
        raise error.MiscError(_("Start-Script line not found."))

    if len(sp.lines) == 0:
        raise error.MiscError(_("File doesn't contain any screenplay lines."))

    if sp.lines[-1].lb != LB_LAST:
        raise error.MiscError(_("Last line doesn't end an element."))

    # the saved cursor position, which an Editor on the script starts at
    cursor = Mark(0, 0)

    if cfgGl.honorSavedPos:
        cursor.line, cursor.column = sp.clampPos(
            sp.cfg.cursorLine, sp.cfg.cursorColumn
        )

    # lines are stored already wrapped, but they're rewrapped with the
    # current rules anyway, which also converts old LB_SPACE2 breaks
    sp.reformatAll(cursor)
    sp.cfg.cursorLine, sp.cfg.cursorColumn = cursor.line, cursor.column
    sp.paginate()
    sp.titles.sort()
    sp.locations.refresh(sp.getSceneNames())

    msgs = []

    if unknownLb:
        msgs.append(_("Screenplay contained unknown linebreak types."))

    if unknownTypes:
        msgs.append(
            _(
                "Screenplay contained unknown element types. These have been converted to Action elements."
            )
        )

    if unknownConfigs:
        msgs.append(
            _(
                "Screenplay contained unknown information. This probably means that the file was created with a newer version of this program.\n\n  You'll lose that information if you save over the existing file."
            )
        )

    return (sp, "\n\n".join(msgs))


# lines is an array of strings. if lines[startIndex] == "Begin-$name
# ", this searches for a string of "End-$name ", takes all the strings
# between those two, joins the lines into a single string (lines
# separated by a "\n") and returns (string,
# line-index-after-the-end-line). returns ("", startIndex) if
# startIndex does not contain the start line or startIndex is too big
# for 'lines'. raises error.MiscError on errors.
def getConfigPart(lines, name, startIndex):
    if (startIndex >= len(lines)) or (lines[startIndex] != ("#Begin-%s " % name)):
        return ("", startIndex)

    try:
        endIndex = lines.index("#End-%s " % name, startIndex)
    except ValueError:
        raise error.MiscError("#End-{} ".format(name) + _("not found"))

    return ("\n".join(lines[startIndex + 1 : endIndex]), endIndex + 1)


# parse a line containing a config-value in the format detailed in
# fileformat.txt. line must have newline stripped from the end
# already. returns a (key, value) tuple. if line doesn't match the
# format, (None, None) is returned.
def parseConfigLine(s: str) -> Tuple[str, str]:
    pattern = re.compile("#([a-zA-Z0-9-]+) (.*)")
    m = pattern.search(s)
    if m:
        return (m.group(1), m.group(2))
    else:
        return (None, None)
