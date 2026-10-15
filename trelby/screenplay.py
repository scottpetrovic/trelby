# -*- coding: utf-8 -*-
import wx

# linebreak types

LB_SPACE = 1

# we don't use this anymore, but we have to keep it in order to be able to
# load old scripts
LB_SPACE2 = 2

LB_NONE = 3
LB_FORCED = 4
LB_LAST = 5

# line types
SCENE = 1
ACTION = 2
CHARACTER = 3
DIALOGUE = 4
PAREN = 5
TRANSITION = 6
SHOT = 7
NOTE = 8
ACTBREAK = 9

import copy
import difflib
import re
import sys
import time
from typing import Tuple

from lxml import etree

import trelby.autocompletion as autocompletion
import trelby.characterprofiles as characterprofiles
import trelby.config as config
import trelby.error as error
import trelby.headers as headers
import trelby.locations as locations
import trelby.mypager as mypager
import trelby.pagelock as pagelock
import trelby.pdf as pdf
import trelby.pml as pml
import trelby.spellcheck as spellcheck
import trelby.titles as titles
import trelby.undo as undo
import trelby.util as util
import trelby.worldbuilding as worldbuilding
from trelby.line import Line


# screenplay
class Screenplay:
    def __init__(self, cfgGl):
        self.autoCompletion = autocompletion.AutoCompletion()
        self.headers = headers.Headers()
        self.locations = locations.Locations()
        self.titles = titles.Titles()
        self.scDict = spellcheck.Dict()
        self.characterProfiles = characterprofiles.CharacterProfiles()
        self.worldBuilding = worldbuilding.WorldBuilding()

        self.lines = [Line(LB_LAST, SCENE)]

        self.cfgGl = cfgGl
        self.cfg = config.Config()

        # cursor position: line and column
        self.line = 0
        self.column = 0

        # first line shown on screen. use getTopLine/setTopLine to access
        # this.
        self._topLine = 0

        # Mark object if selection active, or None.
        self.mark = None

        # pagination: pages[n] is the last line on page n (1-based) and
        # pages[0] is -1. pagesNoAdjust is the same, but without the
        # adjustments made to avoid things like dangling scene headings.
        # pageLabels[n] is the label printed on page n, which differs from
        # n once pages are locked (see paginate).
        self.pages = [-1, 0]
        self.pagesNoAdjust = [-1, 0]
        self.pageLabels = ["", "1"]

        # time when last paginated
        self.lastPaginated = 0.0

        # list of active auto-completion strings
        self.acItems = None

        # selected auto-completion item (only valid when acItems contains
        # something)
        self.acSel = -1

        # max nr of auto comp items displayed at once
        self.acMax = 10

        # True if script has had changes done to it after
        # load/save/creation.
        self.hasChanged = False

        # first/last undo objects (undo.Base)
        self.firstUndo = None
        self.lastUndo = None

        # value of this, depending on the user's last action:
        #  undo: the undo object that was used
        #  redo: the next undo object from the one that was used
        #  anything else: None
        self.currentUndo = None

        # estimated amount of memory used by undo objects, in bytes
        self.undoMemoryUsed = 0

    def isModified(self):
        if not self.hasChanged:
            return False

        # nothing of value is ever lost by not saving a completely empty
        # script, and it's annoying getting warnings about unsaved changes
        # on those, so don't do that

        return (len(self.lines) > 1) or bool(self.lines[0].text)

    def markChanged(self, state=True):
        self.hasChanged = state

    def cursorAsMark(self):
        return Mark(self.line, self.column)

    # return True if the line is a parenthetical and not the first line of
    # that element (such lines need an extra space of indenting).
    def needsExtraParenIndent(self, line):
        return (self.lines[line].lt == PAREN) and not self.isFirstLineOfElem(line)

    def getSpacingBefore(self, i):
        if i == 0:
            return 0

        tcfg = self.cfg.types[self.lines[i].lt]

        if self.lines[i - 1].lb == LB_LAST:
            return tcfg.beforeSpacing
        else:
            return tcfg.intraSpacing

    # we implement our own custom deepcopy because it's 8-10x faster than
    # the generic one (times reported by cmdSpeedTest using a 119-page
    # screenplay):
    #
    # ╭─────────────────────────────┬─────────┬────────╮
    # │                             │ Generic │ Custom │
    # ├─────────────────────────────┼─────────┼────────┤
    # │ Intel Core Duo T2050 1.6GHz │  0.173s │ 0.020s │
    # │ Intel i5-2400 3.1GHz        │  0.076s │ 0.007s │
    # ╰─────────────────────────────┴─────────┴────────╯
    def __deepcopy__(self, memo):
        sp = Screenplay(self.cfgGl)
        sp.cfg = copy.deepcopy(self.cfg)

        sp.autoCompletion = copy.deepcopy(self.autoCompletion)
        sp.headers = copy.deepcopy(self.headers)
        sp.locations = copy.deepcopy(self.locations)
        sp.titles = copy.deepcopy(self.titles)
        sp.scDict = copy.deepcopy(self.scDict)
        sp.characterProfiles = copy.deepcopy(self.characterProfiles)
        sp.worldBuilding = copy.deepcopy(self.worldBuilding)

        sp.lines = [ln.copy() for ln in self.lines]

        # "open PDF on current page" breaks on scripts we're removing
        # notes from before printing if we don't copy these
        sp.line = self.line
        sp.column = self.column

        return sp

    # save script to a utf-8 encoded string and return that
    def save(self) -> bytes:
        self.cfg.cursorLine = self.line
        self.cfg.cursorColumn = self.column

        output = ""

        output += "\ufeff"
        output += "#Version 3\n"

        output += "#Begin-Auto-Completion \n"
        output += self.autoCompletion.save()
        output += "#End-Auto-Completion \n"

        output += "#Begin-Config \n"
        output += self.cfg.save()
        output += "#End-Config \n"

        output += "#Begin-Locations \n"
        output += self.locations.save()
        output += "#End-Locations \n"

        output += "#Begin-Spell-Checker-Dict \n"
        output += self.scDict.save()
        output += "#End-Spell-Checker-Dict \n"

        # only written when there are profiles, so that scripts without
        # any stay readable by older versions without a warning
        if self.characterProfiles.profiles:
            output += "#Begin-Character-Profiles \n"
            output += self.characterProfiles.save()
            output += "#End-Character-Profiles \n"

        # likewise only written when there's something in it
        if self.worldBuilding.hasInfo():
            output += "#Begin-World-Building \n"
            output += self.worldBuilding.save()
            output += "#End-World-Building \n"

        pgs = self.titles.pages
        for pg in range(len(pgs)):
            if pg != 0:
                output += "#Title-Page \n"

            for i in range(len(pgs[pg])):
                output += "#Title-String %s\n" % str(pgs[pg][i])

        for h in self.headers.hdrs:
            output += "#Header-String %s\n" % str(h)

        output += "#Header-Empty-Lines %d\n" % self.headers.emptyLinesAfter

        output += "#Start-Script \n"

        for i, ln in enumerate(self.lines):
            if ln.pageLock:
                output += "#Page-Lock %s\n" % ln.pageLock

            if self.hasDualFlag(i):
                output += "#Dual-Dialogue \n"

            color = self.getSceneColor(i)

            if color:
                output += "#Scene-Color %s\n" % color

            output += str(ln) + "\n"

        return output.encode("UTF-8")

    # load script from string s and return a (Screenplay, msg) tuple,
    # where msgs is string (possibly empty) of warnings about the loading
    # process. fatal errors are indicated by raising a MiscError. note
    # that this is a static function.
    @staticmethod
    def load(s: str, cfgGl):
        lines = s.splitlines()

        sp = Screenplay(cfgGl)

        # remove default empty line
        sp.lines = []

        if len(lines) < 2:
            raise error.MiscError(
                _("File has too few lines to be a valid\nscreenplay file.")
            )

        key, version = Screenplay.parseConfigLine(lines[0])
        if not key or (key != "Version"):
            raise error.MiscError(
                _("File doesn't seem to be a proper\nscreenplay file.")
            )

        if version not in ("1", "2", "3"):
            raise error.MiscError(
                _(
                    "File uses fileformat version '{}',\nwhich is not supported by this version\nof the program.".format(
                        version
                    )
                )
            )

        version = int(version)

        # current position at 'lines'
        index = 1

        s, index = Screenplay.getConfigPart(lines, "Auto-Completion", index)
        if s:
            sp.autoCompletion.load(s)

        s, index = Screenplay.getConfigPart(lines, "Config", index)
        if s:
            sp.cfg.load(s)

        s, index = Screenplay.getConfigPart(lines, "Locations", index)
        if s:
            sp.locations.load(s)

        s, index = Screenplay.getConfigPart(lines, "Spell-Checker-Dict", index)
        if s:
            sp.scDict.load(s)

        s, index = Screenplay.getConfigPart(lines, "Character-Profiles", index)
        if s:
            sp.characterProfiles.load(s)

        s, index = Screenplay.getConfigPart(lines, "World-Building", index)
        if s:
            sp.worldBuilding.load(s)

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

        for i in range(index, len(lines)):
            s = lines[i]

            if len(s) < 2:
                raise error.MiscError(_("Line {} is too short.".format(i + 1)))

            if s[0] == "#":
                key, val = Screenplay.parseConfigLine(s)
                if not key:
                    raise error.MiscError(
                        _("Line {} has invalid syntax for\nconfig line.".format(i + 1))
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

                else:
                    unknownConfigs = True

            else:
                if not startSeen:
                    unknownConfigs = True

                    continue

                lb = config.char2lb(s[0], False)
                lt = config.char2lt(s[1], False)
                text = util.toInputStr(util.fromUTF8(s[2:]))

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
                        _("Line {} has invalid element type.".format(i + 1))
                    )

                line = Line(lb, lt, text, pageLock, dual, color)
                sp.lines.append(line)
                pageLock = None
                dual = False
                color = None

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

        if cfgGl.honorSavedPos:
            sp.line = sp.cfg.cursorLine
            sp.column = sp.cfg.cursorColumn
            sp.validatePos()

        sp.reformatAll()
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
    @staticmethod
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
    @staticmethod
    def parseConfigLine(s: str) -> Tuple[str, str]:
        pattern = re.compile("#([a-zA-Z0-9-]+) (.*)")
        m = pattern.search(s)
        if m:
            return (m.group(1), m.group(2))
        else:
            return (None, None)

    # apply new config.
    def applyCfg(self, cfg):
        self.firstUndo = None
        self.lastUndo = None
        self.currentUndo = None
        self.undoMemoryUsed = 0

        self.cfg = copy.deepcopy(cfg)
        self.cfg.recalc()
        self.reformatAll()
        self.paginate()

        self.markChanged()

    # return script config as a string.
    def saveCfg(self):
        return self.cfg.save()

    # return line i's text for export, upper-cased if its type's export
    # style says so
    def getExportText(self, i):
        line = self.lines[i]

        if self.cfg.getType(line.lt).export.isCaps:
            return util.upper(line.text)

        return line.text

    # return a dual dialogue (see getDualLines) as a list of (lineType,
    # text) rows of plain text, indented with spaces, with the columns side
    # by side. lineType is that of the row's left column if it has a line
    # there, otherwise the right column's, and DIALOGUE for empty rows.
    def getDualTextRows(self, first, right, last):
        def column(start, end, col):
            rows = []

            for i in range(start, end + 1):
                if i != start:
                    rows.extend([(None, "")] * (self.getSpacingBefore(i) // 10))

                text = self.getExportText(i)

                if text and self.needsExtraParenIndent(i):
                    text = " " + text

                indent = self.cfg.getDualIndentWidth(self.lines[i].lt, col)[0]
                rows.append((self.lines[i].lt, " " * indent + text))

            return rows

        leftRows = column(first, right - 1, 1)
        rightRows = column(right, last, 2)
        ret = []

        for k in range(max(len(leftRows), len(rightRows))):
            lt1, text1 = leftRows[k] if k < len(leftRows) else (None, "")
            lt2, text2 = rightRows[k] if k < len(rightRows) else (None, "")

            if text2.strip():
                indent = len(text2) - len(text2.lstrip())
                text1 = text1.ljust(indent) + text2.lstrip()

            ret.append((lt1 or lt2 or DIALOGUE, text1))

        return ret

    # generate formatted text and return it as a string. if 'dopages' is
    # True, marks pagination in the output.
    def generateText(self, doPages):
        ls = self.lines

        output = util.String()

        for p in range(1, len(self.pages)):
            start, end = self.page2lines(p)
            dualLines = self.getDualLines(start, end)

            if doPages and (p != 1):
                s = "%s %s. " % ("-" * 30, self.pageLabels[p])
                s += "-" * (60 - len(s))
                output += "\n%s\n\n" % s

            for i in range(start, end + 1):
                line = ls[i]
                tcfg = self.cfg.getType(line.lt)
                dual = dualLines.get(i)

                # dual dialogues are output whole at their first line
                if dual and (i != dual[1]):
                    continue

                text = self.getExportText(i)

                if (i != 0) and (not doPages or (i != start)):
                    output += (self.getSpacingBefore(i) // 10) * "\n"

                if dual:
                    for lt, s in self.getDualTextRows(*dual[1:]):
                        output += s + "\n"

                    continue

                if text and self.needsExtraParenIndent(i):
                    text = " " + text

                output += " " * tcfg.indent + text + "\n"

        return str(output)

    # generate HTML output and return it as a string, optionally including
    # notes.
    def generateHtml(self, includeNotes=True):
        ls = self.lines

        # We save space by shorter class names in html.
        htmlMap = {
            ACTION: "ac",
            CHARACTER: "ch",
            DIALOGUE: "di",
            PAREN: "pa",
            SCENE: "sc",
            SHOT: "sh",
            TRANSITION: "tr",
            NOTE: "nt",
            ACTBREAK: "ab",
        }

        # html header for files
        htmlHeader = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<title>Exported Screenplay</title>
<style type="text/css">
body {background: #ffffff; color: #000000; text-align: center;}
pre, p {font: 12px/14px Courier, "Courier New", monospace !important;}
pre {text-align: left !important; letter-spacing: 0 !important; margin-top: 0px !important; margin-bottom: 0px !important;}
p {text-align: center;}
.title, .footer {margin: 15px;}
.spcenter {margin: 0 auto; width: 500px;}
.sc, .ab {font-weight: bold !important;}
.nt {color: blue; font-style: italic !important;}
</style>
</head>
<body>
"""
        htmlFooter = """<p class = "footer">***<br>
Generated with <a href="http://www.trelby.org">Trelby</a>.</p>
</body>
</html>"""

        content = etree.Element("div")
        content.set("class", "spcenter")

        # title pages
        for page in self.titles.pages:
            for ts in page:
                for s in ts.items:
                    para = etree.SubElement(content, "p")
                    para.set("class", "title")
                    para.text = s

            para = etree.SubElement(content, "p")
            para.set("class", "title")
            para.text = "***"

        dualLines = self.getDualLines(0, len(ls) - 1)

        for i in range(len(ls)):
            line = ls[i]
            dual = dualLines.get(i)

            if not includeNotes and (line.lt == NOTE):
                continue

            # dual dialogues are output whole at their first line
            if dual and (i != dual[1]):
                continue

            tcfg = self.cfg.getType(line.lt)
            text = self.getExportText(i)

            if text and self.needsExtraParenIndent(i):
                text = " " + text

            text = " " * tcfg.indent + text

            # do we need space before this line?
            lineSpaces = self.getSpacingBefore(i) // 10

            for num in range(lineSpaces):
                para = etree.SubElement(content, "pre")
                para.set("class", htmlMap[line.lt])
                para.text = " "

            if dual:
                for lt, s in self.getDualTextRows(*dual[1:]):
                    para = etree.SubElement(content, "pre")
                    para.set("class", htmlMap[lt])
                    para.text = s or " "

                continue

            # and now the line text
            para = etree.SubElement(content, "pre")
            para.set("class", htmlMap[line.lt])
            para.text = str(text)

        bodyText = etree.tostring(content, encoding="UTF-8", pretty_print=True).decode()

        return htmlHeader + bodyText + htmlFooter

    # Return screenplay as list of tuples of the form (elType, elText,
    # firstLine), where firstLine is the index of the element's first line.
    # forced linebreaks are represented as \n characters.
    def getElementsAsList(self):
        ls = self.lines
        eleList = []
        curLine = ""
        firstLine = 0

        for i, line in enumerate(ls):
            lineType = line.lt
            lineText = line.text

            if self.cfg.getType(line.lt).export.isCaps:
                lineText = util.upper(lineText)

            curLine += lineText

            if line.lb == LB_LAST:
                eleList.append((lineType, curLine, firstLine))
                curLine = ""
                firstLine = i + 1
            elif line.lb == LB_SPACE:
                curLine += " "
            elif line.lb == LB_FORCED:
                curLine += "\n"

        return eleList

    # Generate a Final Draft XML file and return as string.
    def generateFDX(self):
        eleList = self.getElementsAsList()
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
            NOTE: "Action",
            ACTBREAK: "New Act",
        }

        # where to add paragraphs: 'content', or the DualDialogue element
        # of the dual dialogue we're in, which ends at line dualEnd
        parent = content
        dualEnd = -1

        for typ, txt, first in eleList:
            if typ == CHARACTER:
                block = self.getDualBlock(first)

                if block and (block[0] == first):
                    general = etree.SubElement(content, "Paragraph")
                    general.set("Type", "General")
                    parent = etree.SubElement(general, "DualDialogue")
                    dualEnd = block[2]

            if typ == NOTE:
                dummyPara = etree.SubElement(content, "Paragraph")
                dummyPara.set("Type", xmlMap[typ])
                scriptnote = etree.SubElement(dummyPara, "ScriptNote")
                scriptnote.set("ID", "1")
                para = etree.SubElement(scriptnote, "Paragraph")
            else:
                para = etree.SubElement(parent, "Paragraph")
                para.set("Type", xmlMap[typ])

            paratxt = etree.SubElement(para, "Text")
            paratxt.text = str(txt)

            if self.getElemLastIndexFromLine(first) >= dualEnd:
                parent = content

        # FD does not recognize "New Act" by default. It needs an
        # ElementSettings element added.
        eleSet = etree.SubElement(fd, "ElementSettings")
        eleSet.set("Type", xmlMap[ACTBREAK])
        eleSetFont = etree.SubElement(eleSet, "FontSpec")
        eleSetFont.set("Style", "Underline+AllCaps")
        eleSetPara = etree.SubElement(eleSet, "ParagraphSpec")
        eleSetPara.set("Alignment", "Center")

        return etree.tostring(
            fd, xml_declaration=True, encoding="UTF-8", pretty_print=True
        )

    # generate Fountain and return it as a string.
    def generateFountain(self):
        eleList = self.getElementsAsList()
        flines = []
        TWOSPACE = "  "
        sceneStartsList = ("INT", "EXT", "EST", "INT./EXT", "INT/EXT", "I/E", "I./E")

        # does s look like a fountain scene line:
        def looksLikeScene(s):
            s = s.upper()
            looksGood = False
            for t in sceneStartsList:
                if s.startswith(t):
                    looksGood = True
                    break
            return looksGood

        # Generate Title Page
        def generateTitleString(keyword, titleLine, startAt, linePrefix, lineSuffix):
            if (len(titleLine) - startAt) > 1:
                # multi-line
                flines.append(keyword)
                for part in titleLine:
                    if startAt > 0:
                        startAt -= 1
                        continue
                    flines.append("    " + linePrefix + part + lineSuffix)
            elif len(titleLine) == 1 and keyword == titleLine[0]:
                flines.append(keyword)
            else:
                flines.append(keyword + " " + titleLine[startAt])

        titleNeeded = True
        kwPattern = re.compile(r"^([A-za-z][^:]+:)")
        for page in self.titles.pages:
            # index of a title string already used as an author
            skipIndex = -1
            for i, titleLine in enumerate(page):
                if i == skipIndex:
                    continue
                if titleNeeded and titleLine.isBold and titleLine.isCentered:
                    generateTitleString("Title:", titleLine.items, 0, "_**", "**_")
                    titleNeeded = False
                elif titleLine.items[0].strip().lower() == "by":
                    # the author is either in this title string after "by"
                    # (usually with a blank line in between), or, if "by"
                    # is alone, in the next one.
                    author = titleLine.items[1:]
                    while author and not author[0].strip():
                        author = author[1:]
                    if not author and (i + 1) < len(page):
                        author = page[i + 1].items
                        skipIndex = i + 1
                    if author:
                        generateTitleString("Author:", author, 0, "", "")
                elif kwPattern.match(titleLine.items[0]):
                    generateTitleString(titleLine.items[0], titleLine.items, 0, "", "")
                else:
                    generateTitleString("Contact:", titleLine.items, 0, "", "")

        for typ, txt, first in eleList:
            lns = txt.split("\n")

            # ensure last element of flines is empty for some types.
            if typ in (SCENE, ACTION, CHARACTER, TRANSITION, SHOT, ACTBREAK, NOTE):
                if flines and flines[-1] != "":
                    flines.append("")

            # special handling of some elements.
            if typ == SCENE:
                # if the line would not be recognized as Scene by fountain,
                # append a "." so it is forced as a scene line.
                if not looksLikeScene(txt):
                    txt = "." + txt

            elif typ == ACTION:
                tmp = []
                for ln in lns:
                    if ln and (ln.isupper() or looksLikeScene(txt)):
                        tmp.append(ln + TWOSPACE)
                    else:
                        tmp.append(ln)
                txt = "\n".join(tmp)

            elif typ == TRANSITION:
                if not txt.endswith("TO:"):
                    txt = "> " + txt

            elif typ == DIALOGUE:
                tmp = []
                for ln in lns:
                    if not ln:
                        tmp.append(TWOSPACE)
                    else:
                        tmp.append(ln)
                txt = "\n".join(tmp)

            elif typ == NOTE:
                txt = "[[" + txt + "]]"

            elif typ == ACTBREAK:
                txt = ">" + txt + "<"

            elif typ == SHOT:
                txt += TWOSPACE

            elif typ == CHARACTER:
                if self.getDualBlockFromRight(first):
                    txt += " ^"

            flines.append(txt)

        return util.toUTF8("\n".join(flines))

    # generate RTF and return it as a string.
    def generateRTF(self):
        ls = self.lines
        s = util.String()

        s += r"{\rtf1\ansi\deff0{\fonttbl{\f0\fmodern Courier;}}" + "\n"

        s += "{\\stylesheet\n"

        mt = util.mm2twips
        fs = self.cfg.fontSize

        # since some of our units (beforeSpacing, indent, width) are
        # easier to handle if we assume normal font size, this is a scale
        # factor from actual font size to normal font size
        sf = fs / 12.0

        for ti in config.getTIs():
            t = self.cfg.getType(ti.lt)
            tt = t.export

            # font size is expressed as font size * 2 in RTF
            tmp = " \\fs%d" % (fs * 2)

            if tt.isCaps:
                tmp += r" \caps"

            if tt.isBold:
                tmp += r" \b"

            if tt.isItalic:
                tmp += r" \i"

            if tt.isUnderlined:
                tmp += r" \ul"

            # some hairy conversions going on here...
            tmp += r" \li%d\ri%d" % (
                sf * t.indent * 144,
                mt(self.cfg.paperWidth)
                - (
                    mt(self.cfg.marginLeft + self.cfg.marginRight)
                    + (t.indent + t.width) * 144 * sf
                ),
            )

            tmp += r" \sb%d" % (sf * t.beforeSpacing * 24)

            s += "{\\s%d%s %s}\n" % (ti.lt, tmp, ti.name)

        s += "}\n"

        s += r"\paperw%d\paperh%d\margt%d\margr%d\margb%d\margl%d" % (
            mt(self.cfg.paperWidth),
            mt(self.cfg.paperHeight),
            mt(self.cfg.marginTop),
            mt(self.cfg.marginRight),
            mt(self.cfg.marginBottom),
            mt(self.cfg.marginLeft),
        )
        s += "\n"

        s += self.titles.generateRTF()

        length = len(ls)
        i = 0

        magicslash = "TRELBY-MAGIC-SLASH"

        while i < length:
            lt = ls[i].lt
            text = ""

            while 1:
                ln = ls[i]
                i += 1

                lb = ln.lb
                text += ln.text

                if lb in (LB_SPACE, LB_NONE):
                    text += config.lb2str(lb)
                elif lb == LB_FORCED:
                    text += magicslash + "line "
                elif lb == LB_LAST:
                    break
                else:
                    raise error.MiscError(
                        _("Unknown line break style {} in generateRTF".format(lb))
                    )

            s += (
                (r"{\pard \s%d " % lt)
                + util.escapeRTF(text).replace(magicslash, "\\")
                + "}{\\par}\n"
            )

        s += "}"

        return str(s)

    # generate PDF and return it as a string. assumes paginate/reformat is
    # 100% correct for the screenplay.
    def generatePDF(self) -> bytes:
        return pdf.generate(self.generatePML())

    # Same as generatePDF, but returns a PML document.
    def generatePML(self) -> pml.Document:
        pager = mypager.Pager(self.cfg)
        self.titles.generatePages(pager.doc)

        pager.doc.showTOC = self.cfg.pdfShowTOC

        for i in range(1, len(self.pages)):
            pg = self.generatePMLPage(pager, i, True, True)

            if pg:
                pager.doc.add(pg)
            else:
                break

        for pfi in self.cfg.getPDFFontIds():
            pf = self.cfg.getPDFFont(pfi)

            if pf.pdfName and pf.filename != "":
                pager.doc.addFont(pf.style, pml.PDFFontInfo(pf.pdfName, pf.filename))

        return pager.doc

    # generate one page of PML data and return it.
    #
    # if forPDF is True, output is meant for PDF generation.
    #
    # if doExtra is False, omits headers and other stuff that is
    # automatically added, i.e. outputs only actual screenplay lines. also
    # text style/capitalization is not done 100% correctly. this should
    # only be True for callers that do not show the results in any way,
    # just calculate things based on text positions.
    #
    # can also return None, which means pagination is not up-to-date and
    # the given page number doesn't point to a valid page anymore, and the
    # caller should stop calling this since all pages have been generated
    # (assuming 1-to-n calling sequence).
    def generatePMLPage(self, pager, pageNr, forPDF, doExtra):
        # lsdjflksj = util.TimerDev("generatePMLPage")

        cfg = self.cfg
        ls = self.lines

        fs = cfg.fontSize
        chX = util.getTextWidth(" ", pml.COURIER, fs)
        chY = util.getTextHeight(fs)
        length = len(ls)

        start = self.pages[pageNr - 1] + 1

        if start >= length:
            # text has been deleted at end of script and pagination has
            # not been updated.
            return None

        # pagination may not be up-to-date, so any overflow text gets
        # dumped onto the last page which may thus be arbitrarily long.
        if pageNr == (len(self.pages) - 1):
            end = length - 1
        else:
            # another side-effect is that if text is deleted at the end,
            # self.pages can point to lines that no longer exist, so we
            # need to clamp it.
            end = util.clamp(self.pages[pageNr], maxVal=length - 1)

        pg = pml.Page(pager.doc)

        # what line we're on, counted from first line after top
        # margin, units = line / 10
        y = 0

        if pageNr != 1:
            if doExtra:
                self.headers.generatePML(pg, self.getPageLabel(pageNr), cfg)
            y += self.headers.getNrOfLines() * 10

            if cfg.sceneContinueds and not self.isFirstLineOfScene(start):
                if doExtra:
                    s = cfg.strContinuedPageStart
                    if pager.sceneContNr != 0:
                        s += " (%d)" % (pager.sceneContNr + 1)

                    pg.add(
                        pml.TextOp(
                            s,
                            cfg.marginLeft + pager.sceneIndent * chX,
                            cfg.marginTop + (y / 10.0) * chY,
                            fs,
                        )
                    )

                    pager.sceneContNr += 1

                    if cfg.pdfShowSceneNumbers:
                        self.addSceneNumbers(
                            pg,
                            "%d" % pager.scene,
                            cfg.getType(SCENE).width,
                            y,
                            chX,
                            chY,
                        )

                y += 20

            if self.needsMore(start - 1):
                if doExtra:
                    pg.add(
                        pml.TextOp(
                            self.getPrevSpeaker(start) + cfg.strDialogueContinued,
                            cfg.marginLeft + pager.charIndent * chX,
                            cfg.marginTop + (y / 10.0) * chY,
                            fs,
                        )
                    )

                y += 10

        # dual dialogues: the right-hand speech goes back up to where the
        # left one started, and what follows goes below the longer one
        dualLines = self.getDualLines(start, end)
        dualTop = dualLeftBottom = 0

        for i in range(start, end + 1):
            line = ls[i]
            tcfg = cfg.getType(line.lt)
            dual = dualLines.get(i)

            if dual and (i == dual[2]):
                dualLeftBottom = y
                y = dualTop
            elif i != start:
                y += self.getSpacingBefore(i)

            if dual and (i == dual[1]):
                dualTop = y

            if dual:
                indent = cfg.getDualIndentWidth(line.lt, dual[0])[0]
            else:
                indent = tcfg.indent

            typ = pml.NORMAL

            if doExtra:
                if forPDF:
                    tt = tcfg.export
                else:
                    tt = tcfg.screen

                if tt.isCaps:
                    text = util.upper(line.text)
                else:
                    text = line.text

                if tt.isBold:
                    typ |= pml.BOLD
                if tt.isItalic:
                    typ |= pml.ITALIC
                if tt.isUnderlined:
                    typ |= pml.UNDERLINED
            else:
                text = line.text

            extraIndent = 1 if self.needsExtraParenIndent(i) else 0

            to = pml.TextOp(
                text,
                cfg.marginLeft + (indent + extraIndent) * chX,
                cfg.marginTop + (y / 10.0) * chY,
                fs,
                typ,
                line=i,
            )

            pg.add(to)

            if forPDF and (tcfg.lt == NOTE) and cfg.pdfOutlineNotes:
                offset = chX / 2.0
                nx = cfg.marginLeft + tcfg.indent * chX
                ny = cfg.marginTop + (y / 10.0) * chY
                nw = tcfg.width * chX
                lw = 0.25

                pg.add(pml.genLine(nx - offset, ny, 0.0, chY, lw))
                pg.add(pml.genLine(nx + nw + offset, ny, 0.0, chY, lw))

                if self.isFirstLineOfElem(i):
                    pg.add(pml.QuarterCircleOp(nx, ny, offset, lw))
                    pg.add(pml.genLine(nx, ny - offset, nw, 0.0, lw))
                    pg.add(pml.QuarterCircleOp(nx + nw, ny, offset, lw, True))

                    pg.add(
                        pml.TextOp(
                            "Note",
                            (nx + nx + nw) / 2.0,
                            ny - offset,
                            6,
                            pml.ITALIC,
                            util.ALIGN_CENTER,
                            util.VALIGN_BOTTOM,
                        )
                    )

                if self.isLastLineOfElem(i):
                    pg.add(pml.QuarterCircleOp(nx, ny + chY, offset, lw, False, True))
                    pg.add(pml.genLine(nx, ny + chY + offset, nw, 0.0, lw))
                    pg.add(
                        pml.QuarterCircleOp(nx + nw, ny + chY, offset, lw, True, True)
                    )

            if doExtra and (tcfg.lt == SCENE) and self.isFirstLineOfElem(i):
                pager.sceneContNr = 0

                if cfg.pdfShowSceneNumbers:
                    pager.scene += 1
                    self.addSceneNumbers(
                        pg, "%d" % pager.scene, tcfg.width, y, chX, chY
                    )

                if cfg.pdfIncludeTOC:
                    if cfg.pdfShowSceneNumbers:
                        s = "%d %s" % (pager.scene, text)
                    else:
                        s = text

                    to.toc = pml.TOCItem(s, to)

            # the left column's line numbers are where the right one's
            # would go
            if doExtra and cfg.pdfShowLineNumbers and not (dual and (dual[0] == 2)):
                pg.add(
                    pml.TextOp(
                        "%02d" % (i - start + 1),
                        cfg.marginLeft - 3 * chX,
                        cfg.marginTop + (y / 10.0) * chY,
                        fs,
                    )
                )

            y += 10

            if dual and (i == dual[3]):
                y = max(y, dualLeftBottom)

        if self.needsMore(end):
            if doExtra:
                pg.add(
                    pml.TextOp(
                        cfg.strMore,
                        cfg.marginLeft + pager.charIndent * chX,
                        cfg.marginTop + (y / 10.0) * chY,
                        fs,
                    )
                )

            y += 10

        if cfg.sceneContinueds and not self.isLastLineOfScene(end):
            if doExtra:
                pg.add(
                    pml.TextOp(
                        cfg.strContinuedPageEnd,
                        cfg.marginLeft + cfg.sceneContinuedIndent * chX,
                        cfg.marginTop + (y / 10.0 + 1.0) * chY,
                        fs,
                    )
                )

            y += 10

        if forPDF and cfg.pdfShowMargins:
            lx = cfg.marginLeft
            rx = cfg.paperWidth - cfg.marginRight
            uy = cfg.marginTop
            dy = cfg.paperHeight - cfg.marginBottom

            pg.add(pml.LineOp([(lx, uy), (rx, uy), (rx, dy), (lx, dy)], 0, True))

        return pg

    def addSceneNumbers(self, pg, s, width, y, chX, chY):
        cfg = self.cfg

        pg.add(
            pml.TextOp(
                s,
                cfg.marginLeft - 6 * chX,
                cfg.marginTop + (y / 10.0) * chY,
                cfg.fontSize,
            )
        )
        pg.add(
            pml.TextOp(
                s,
                cfg.marginLeft + (width + 1) * chX,
                cfg.marginTop + (y / 10.0) * chY,
                cfg.fontSize,
            )
        )

    # get topLine, clamping it to the valid range in the process.
    def getTopLine(self):
        self._topLine = util.clamp(self._topLine, 0, len(self.lines) - 1)

        return self._topLine

    # set topLine, clamping it to the valid range.
    def setTopLine(self, line):
        self._topLine = util.clamp(line, 0, len(self.lines) - 1)

    def reformatAll(self):
        # doing a reformatAll while we have undo history will completely
        # break undo, so that can't be allowed.
        assert not self.firstUndo

        # sfdlksjf = util.TimerDev("reformatAll")

        line = 0

        while 1:
            line += self.rewrapPara(line)
            if line >= len(self.lines):
                break

    # reformat part of the screenplay. par1 is line number of paragraph to
    # start at, par2 the same for the ending one, inclusive.
    def reformatRange(self, par1, par2):
        ls = self.lines

        # add special tag to last paragraph we'll reformat
        ls[par2].reformatMarker = 0
        end = False

        line = par1
        while 1:
            if hasattr(ls[line], "reformatMarker"):
                del ls[line].reformatMarker
                end = True

            line += self.rewrapPara(line)
            if end:
                break

    # wraps a single line into however many lines are needed, according to
    # the given width, or the type's width if it's None. doesn't modify the
    # input line, returns a list of new lines.
    def wrapLine(self, line, width=None):
        ret = []

        if width is None:
            width = self.cfg.getType(line.lt).width

        isParen = line.lt == PAREN

        # text remaining to be wrapped
        text = line.text

        while 1:
            # reduce parenthetical width by 1 from second line onwards
            if isParen and ret:
                w = width - 1
            else:
                w = width

            if len(text) <= w:
                ret.append(Line(line.lb, line.lt, text))
                break
            else:
                i = text.rfind(" ", 0, w + 1)

                if i == w:

                    # we allow space characters to go over the line
                    # length, for two reasons:
                    #
                    # 1) it is impossible to get the behavior right
                    # otherwise in situations where a line ends in two
                    # spaces and the user inserts a non-space character at
                    # the end of the line. the cursor must be positioned
                    # at the second space character for this to work
                    # right, and the only way to get that is to allow
                    # spaces to go over the normal line length.
                    #
                    # 2) doing this results in no harm, since space
                    # characters print as empty, so they don't overwrite
                    # anything.

                    i += 1
                    while text[i : i + 1] == " ":
                        i += 1

                    if i == len(text):
                        ret.append(Line(line.lb, line.lt, text))

                        break
                    else:
                        ret.append(Line(LB_SPACE, line.lt, text[0 : i - 1]))
                        text = text[i:]

                elif i >= 0:
                    ret.append(Line(LB_SPACE, line.lt, text[0:i]))
                    text = text[i + 1 :]

                else:
                    ret.append(Line(LB_NONE, line.lt, text[0:w]))
                    text = text[w:]

        return ret

    # rewrap paragraph starting at given line. returns the number of lines
    # in the wrapped paragraph. if line1 is -1, rewraps paragraph
    # containing self.line. maintains cursor position correctness.
    def rewrapPara(self, line1=-1):
        ls = self.lines

        if line1 == -1:
            line1 = self.getParaFirstIndexFromLine(self.line)

        line2 = line1

        while ls[line2].lb not in (LB_LAST, LB_FORCED):
            line2 += 1

        if (self.line >= line1) and (self.line <= line2):
            # cursor is in this paragraph, save its offset from the
            # beginning of the paragraph
            cursorOffset = 0

            for i in range(line1, line2 + 1):
                if i == self.line:
                    cursorOffset += self.column

                    break
                else:
                    cursorOffset += len(ls[i].text) + len(config.lb2str(ls[i].lb))
        else:
            cursorOffset = -1

        # page locks in this paragraph, as (offset from the beginning of
        # the paragraph, label) tuples
        locks = []

        s = ""
        for i in range(line1, line2 + 1):
            if i != line1:
                s += config.lb2str(ls[i - 1].lb)

            if ls[i].pageLock:
                locks.append(
                    (len(s) + getattr(ls[i], "pageLockCol", 0), ls[i].pageLock)
                )

            s += ls[i].text

        tmp = Line(ls[line2].lb, ls[line1].lt, s)

        # speeches in a dual dialogue are wrapped to fit their column
        width = None
        if tmp.lt in (CHARACTER, PAREN, DIALOGUE):
            col = self.getDualColumn(line1)

            if col:
                width = self.cfg.getDualIndentWidth(tmp.lt, col)[1]

        wrappedLines = self.wrapLine(tmp, width)

        # the dual flag and color stay on the first line of the element
        firstOfElem = self.isFirstLineOfElem(line1)
        wrappedLines[0].dual = ls[line1].dual and firstOfElem
        wrappedLines[0].color = ls[line1].color if firstOfElem else None

        ls[line1 : line2 + 1] = wrappedLines

        # put the page locks back on the lines that now contain the text
        # they were on
        if locks:
            for offset, label in locks:
                i = line1

                for ln in wrappedLines[:-1]:
                    offset -= len(ln.text) + len(config.lb2str(ln.lb))

                    if offset < 0:
                        break

                    i += 1

                self.addPageLock(i, label)

        # adjust cursor position
        if cursorOffset != -1:
            for i in range(line1, line1 + len(wrappedLines)):
                ln = ls[i]
                llen = len(ln.text) + len(config.lb2str(ln.lb))

                if cursorOffset < llen:
                    self.line = i
                    self.column = min(cursorOffset, len(ln.text))
                    break
                else:
                    cursorOffset -= llen

        elif self.line >= line1:
            # cursor position is below current paragraph, modify its
            # linenumber appropriately
            self.line += len(wrappedLines) - (line2 - line1 + 1)

        return len(wrappedLines)

    # rewrap the elements of lines line1 - line2 and the elements next to
    # them, extended to whole speeches (see getSpeechRangeAround), so that
    # speeches that an edit there has made part of a dual dialogue, or
    # taken out of one, get their new widths. the undo object for the edit
    # must cover those lines too.
    def rewrapSpeechesAround(self, line1, line2):
        first, last = self.getSpeechRangeAround(line1, line2)
        self.rewrapElems(first, self.elemsDistance(first, last) + 1)

    # rewrap 'count' elements starting from the one starting at 'line'
    def rewrapElems(self, line, count):
        for i in range(count):
            self.rewrapElem(line)
            line = self.getElemLastIndexFromLine(line) + 1

    # return (first, last) lines of the elements containing lines line1 -
    # line2 and the elements before and after them, extended to whole
    # speeches and the dual dialogues they're in. a speech with the dual
    # flag right after that is included too, since an edit can make it
    # the right-hand column of a dual dialogue.
    def getSpeechRangeAround(self, line1, line2):
        ls = self.lines

        first = self.getElemFirstIndexFromLine(line1)
        if first > 0:
            first = self.getElemFirstIndexFromLine(first - 1)

        last = self.getElemLastIndexFromLine(line2)
        if (last + 1) < len(ls):
            last = self.getElemLastIndexFromLine(last + 1)

        speech = self.getSpeechIndexes(first)
        if speech:
            first = speech[0]

        speech = self.getSpeechIndexes(last)
        if speech:
            last = speech[1]

        block = self.getDualBlock(first)
        if block:
            first = block[0]

        block = self.getDualBlock(last)
        if block:
            last = block[2]

        if ((last + 1) < len(ls)) and self.hasDualFlag(last + 1):
            last = self.getSpeechIndexes(last + 1)[1]

        return (first, last)

    # rewraps paragraph previous to current one.
    def rewrapPrevPara(self):
        line = self.getParaFirstIndexFromLine(self.line)

        if line == 0:
            return

        line = self.getParaFirstIndexFromLine(line - 1)
        self.rewrapPara(line)

    # rewrap element starting at given line. if line is -1, rewraps
    # element containing self.line.
    def rewrapElem(self, line=-1):
        ls = self.lines

        if line == -1:
            line = self.getElemFirstIndex()

        while 1:
            line += self.rewrapPara(line)

            if ls[line - 1].lb == LB_LAST:
                break

    def isFirstLineOfElem(self, line):
        return (line == 0) or (self.lines[line - 1].lb == LB_LAST)

    def isLastLineOfElem(self, line):
        return self.lines[line].lb == LB_LAST

    def isOnlyLineOfElem(self, line):
        # this is just "isLastLineOfElem(line) and isFirstLineOfElem(line)"
        # inlined here, since it's 130% faster this way.
        return (self.lines[line].lb == LB_LAST) and (
            (line == 0) or (self.lines[line - 1].lb == LB_LAST)
        )

    # return True if line i has the dual flag set where it means
    # something, i.e. on the first line of a character element.
    def hasDualFlag(self, i):
        ln = self.lines[i]

        return ln.dual and (ln.lt == CHARACTER) and self.isFirstLineOfElem(i)

    # if 'line' is in a character's speech (a character element and the
    # parenthetical and dialogue elements following it), return the
    # (first, last) lines of the speech, otherwise None.
    def getSpeechIndexes(self, line):
        ls = self.lines
        speechTypes = (PAREN, DIALOGUE)

        i = line
        while (i >= 0) and (ls[i].lt in speechTypes):
            i -= 1

        if (i < 0) or (ls[i].lt != CHARACTER):
            return None

        first, last = self.getElemIndexesFromLine(i)

        while ((last + 1) < len(ls)) and (ls[last + 1].lt in speechTypes):
            last += 1

        return (first, last)

    # if line r starts the speech printed as the right-hand column of a
    # dual dialogue, return the dual dialogue's lines as (first line of
    # left speech, r, last line of right speech), otherwise None. the
    # left speech is the one right before r, and it can't itself be the
    # right-hand column of another dual dialogue.
    def getDualBlockFromRight(self, r):
        if (
            (r == 0)
            or not self.hasDualFlag(r)
            or (self.lines[r - 1].lt not in (PAREN, DIALOGUE))
        ):
            return None

        left = self.getSpeechIndexes(r - 1)

        if not left or self.hasDualFlag(left[0]):
            return None

        return (left[0], r, self.getSpeechIndexes(r)[1])

    # return the dual dialogue 'line' is part of, in the format of
    # getDualBlockFromRight, or None.
    def getDualBlock(self, line):
        speech = self.getSpeechIndexes(line)

        if not speech:
            return None

        block = self.getDualBlockFromRight(speech[0])

        if not block and ((speech[1] + 1) < len(self.lines)):
            block = self.getDualBlockFromRight(speech[1] + 1)

        return block

    # return which column of a dual dialogue 'line' is in: 1 = left, 2 =
    # right, or 0 if it's not in one.
    def getDualColumn(self, line):
        block = self.getDualBlock(line)

        if not block:
            return 0

        return 1 if line < block[1] else 2

    # return the dual dialogues lying entirely within lines start - end
    # (inclusive) that can be printed as such, as a {line: (column, first,
    # right, last)} dict containing all of their lines (see
    # getDualBlockFromRight). a dual dialogue can't be printed if some of
    # its lines are too long for its columns, which happens when
    # something has made it one without its speeches being rewrapped.
    def getDualLines(self, start, end):
        ls = self.lines
        cfg = self.cfg
        ret = {}

        for r in range(start + 1, end + 1):
            if not ls[r].dual:
                continue

            block = self.getDualBlockFromRight(r)

            if not block or (block[0] < start) or (block[2] > end):
                continue

            first, right, last = block
            fits = True

            for i in range(first, last + 1):
                col = 1 if i < right else 2
                width = cfg.getDualIndentWidth(ls[i].lt, col)[1]

                if len(ls[i].text.rstrip(" ")) > width:
                    fits = False

                    break

            if fits:
                for i in range(first, last + 1):
                    ret[i] = (1 if i < right else 2, first, right, last)

        return ret

    # get first index of paragraph
    def getParaFirstIndexFromLine(self, line):
        ls = self.lines

        while 1:
            tmp = line - 1

            if tmp < 0:
                break

            if ls[tmp].lb in (LB_LAST, LB_FORCED):
                break

            line -= 1

        return line

    # get last index of paragraph
    def getParaLastIndexFromLine(self, line):
        ls = self.lines

        while 1:
            if ls[line].lb in (LB_LAST, LB_FORCED):
                break

            if (line + 1) >= len(ls):
                break

            line += 1

        return line

    def getElemFirstIndex(self):
        return self.getElemFirstIndexFromLine(self.line)

    def getElemFirstIndexFromLine(self, line):
        ls = self.lines

        while 1:
            tmp = line - 1

            if tmp < 0:
                break

            if ls[tmp].lb == LB_LAST:
                break

            line -= 1

        return line

    def getElemLastIndex(self):
        return self.getElemLastIndexFromLine(self.line)

    def getElemLastIndexFromLine(self, line):
        ls = self.lines

        while 1:
            if ls[line].lb == LB_LAST:
                break

            if (line + 1) >= len(ls):
                break

            line += 1

        return line

    def getElemIndexes(self):
        return self.getElemIndexesFromLine(self.line)

    def getElemIndexesFromLine(self, line):
        return (
            self.getElemFirstIndexFromLine(line),
            self.getElemLastIndexFromLine(line),
        )

    def isFirstLineOfScene(self, line):
        if line == 0:
            return True

        ls = self.lines

        if ls[line].lt != SCENE:
            return False

        l = ls[line - 1]

        return (l.lt != SCENE) or (l.lb == LB_LAST)

    def isLastLineOfScene(self, line):
        ls = self.lines

        if ls[line].lb != LB_LAST:
            return False

        if line == (len(ls) - 1):
            return True

        return ls[line + 1].lt == SCENE

    def getTypeOfPrevElem(self, line):
        line = self.getElemFirstIndexFromLine(line)
        line -= 1

        if line < 0:
            return None

        return self.lines[line].lt

    def getTypeOfNextElem(self, line):
        line = self.getElemLastIndexFromLine(line)
        line += 1

        if line >= len(self.lines):
            return None

        return self.lines[line].lt

    def getSceneIndexes(self):
        return self.getSceneIndexesFromLine(self.line)

    def getSceneIndexesFromLine(self, line):
        top, bottom = self.getElemIndexesFromLine(line)
        ls = self.lines

        while 1:
            if ls[top].lt in (SCENE, ACTBREAK):
                break

            tmp = top - 1
            if tmp < 0:
                break

            top = self.getElemIndexesFromLine(tmp)[0]

        while 1:
            tmp = bottom + 1
            if tmp >= len(ls):
                break

            if ls[tmp].lt in (SCENE, ACTBREAK):
                break

            bottom = self.getElemIndexesFromLine(tmp)[1]

        return (top, bottom)

    # return scene number for the given line. if line is -1, return 0.
    def getSceneNumber(self, line):
        ls = self.lines
        sc = SCENE
        scene = 0

        for i in range(line + 1):
            if (ls[i].lt == sc) and self.isFirstLineOfElem(i):
                scene += 1

        return scene

    # return how many elements one must advance to get from element
    # containing line1 to element containing line2. line1 must be <=
    # line2, and either line can be anywhere in their respective elements.
    # returns 0 if they're in the same element, 1 if they're in
    # consecutive elements, etc.
    def elemsDistance(self, line1, line2):
        ls = self.lines

        count = 0
        line = line1

        while line < line2:
            if ls[line].lb == LB_LAST:
                count += 1

            line += 1

        return count

    # returns true if 'line', which must be the last line on a page, needs
    # (MORE) after it and the next page needs a "SOMEBODY (cont'd)".
    def needsMore(self, line):
        ls = self.lines

        return (
            ls[line].lt in (DIALOGUE, PAREN)
            and (line != (len(ls) - 1))
            and ls[line + 1].lt in (DIALOGUE, PAREN)
        )

    # starting at line, go backwards until a line with type of CHARACTER
    # and lb of LAST is found, and return that line's text, possibly
    # upper-cased if CHARACTER's config for export says so.
    def getPrevSpeaker(self, line):
        ls = self.lines

        while 1:
            if line < 0:
                return "UNKNOWN"

            ln = ls[line]

            if (ln.lt == CHARACTER) and (ln.lb == LB_LAST):
                s = ln.text

                if self.cfg.getType(CHARACTER).export.isCaps:
                    s = util.upper(s)

                return s

            line -= 1

    # return total number of characters in script
    def getCharCount(self):
        return sum([len(ln.text) for ln in self.lines])

    # return total number of words in script
    def getWordCount(self):
        # a line broken without a space (LB_NONE) continues the same word
        # on the next line
        parts = []

        for ln in self.lines:
            parts.append(ln.text)

            if ln.lb != LB_NONE:
                parts.append(" ")

        return len("".join(parts).split())

    # return the script's length in pages, with the last page counted as
    # the fraction of it that is filled. uses the last pagination, like
    # the page numbers do.
    def getPageLength(self):
        pageCnt = len(self.pages) - 1

        if pageCnt < 1:
            return 0.0

        ls = self.lines
        ct = self.cfg.types
        last = len(ls) - 1

        # self.pages can point to lines that no longer exist
        start = util.clamp(self.pages[-2] + 1, 0, last)

        # in tenths of a line, like paginate
        units = 10

        if pageCnt > 1:
            units += self.headers.getNrOfLines() * 10

        for i in range(start + 1, last + 1):
            units += 10

            if ls[i - 1].lb == LB_LAST:
                units += ct[ls[i].lt].beforeSpacing
            else:
                units += ct[ls[i].lt].intraSpacing

        return (pageCnt - 1) + min(1.0, units / (self.cfg.linesOnPage * 10))

    # paginate the script. if pages are locked (some lines have a
    # pageLock), each locked page starts at its line no matter what, which
    # splits the script into segments that are paginated independently: if
    # a segment no longer fits on its page, the rest goes onto A-pages
    # (15A, 15B, ...), and if it has gotten shorter, the page just ends
    # early.
    def paginate(self):
        # sfdlksjf = util.TimerDev("paginate")

        self.pages = [-1]
        self.pagesNoAdjust = [-1]
        self.pageLabels = [""]

        length = len(self.lines)
        locks = self.getPageLocks()

        self.initDualPagination()

        if not locks:
            self.paginateRange(0, length - 1)
            self.pageLabels.extend(str(p) for p in range(1, len(self.pages)))

        else:
            if locks[0][0] != 0:
                cnt = self.paginateRange(0, locks[0][0] - 1)
                self.pageLabels.extend(pagelock.labelsBefore(locks[0][1], cnt))

            for i, (line, label) in enumerate(locks):
                if i + 1 < len(locks):
                    end, nextLabel = locks[i + 1][0] - 1, locks[i + 1][1]
                else:
                    end, nextLabel = length - 1, None

                cnt = self.paginateRange(line, end)
                self.pageLabels.extend(pagelock.segmentLabels(label, nextLabel, cnt))

        self.lastPaginated = time.time()

    # set up what paginateRange needs to know about dual dialogues, for
    # paginate to call before it:
    #
    # dualBlockAt: {line: (first, right, last)} for each line of a dual
    # dialogue except its last one, i.e. the lines a page must not end on.
    #
    # dualCost: {line: (first, cost)} for each line of a right-hand
    # column. when the whole dual dialogue is on one page (it starts after
    # the previous page break), 'cost' is how much height the line adds,
    # in the same units as in paginateRange; together they add whatever
    # the right column is taller than the left one, if anything.
    def initDualPagination(self):
        self.dualBlockAt = {}
        self.dualCost = {}

        ls = self.lines
        ct = self.cfg.types

        def height(first, last):
            h = 10

            for i in range(first + 1, last + 1):
                h += 10

                if ls[i - 1].lb == LB_LAST:
                    h += ct[ls[i].lt].beforeSpacing
                else:
                    h += ct[ls[i].lt].intraSpacing

            return h

        blocks = {v[1:] for v in self.getDualLines(0, len(ls) - 1).values()}

        for first, right, last in blocks:
            for i in range(first, last):
                self.dualBlockAt[i] = (first, right, last)

            for i in range(right, last):
                self.dualCost[i] = (first, 0)

            extra = height(right, last) - height(first, right - 1)
            self.dualCost[last] = (first, max(0, extra))

    # paginate lines start - end (inclusive), appending to self.pages and
    # self.pagesNoAdjust as if 'start' was the first line of the script
    # and 'end' the last one, except that line 0 is the only one that
    # starts a page without headers. returns the number of pages added.
    def paginateRange(self, start, end):
        ls = self.lines
        cfg = self.cfg

        oldCnt = len(self.pages)
        length = end + 1
        lastBreak = start - 1

        # fast aliases for stuff
        lbl = LB_LAST
        ct = cfg.types
        hdrLines = self.headers.getNrOfLines()
        dualBlockAt = self.dualBlockAt
        dualCost = self.dualCost

        i = start
        while 1:
            lp = cfg.linesOnPage * 10

            if i != 0:
                lp -= hdrLines * 10

                # decrease by 2 if we have to put a "CONTINUED:" on top of
                # this page.
                if cfg.sceneContinueds and not self.isFirstLineOfScene(i):
                    lp -= 20

                # decrease by 1 if we have to put a "WHOEVER (cont'd)" on
                # top of this page.
                if self.needsMore(i - 1):
                    lp -= 10

            # just a safeguard
            lp = max(50, lp)

            pageLines = 0
            if i < length:
                pageLines = 10

                # advance i until it points to the last line to put on
                # this page (before adjustments)

                while i < (length - 1):

                    dual = dualCost.get(i + 1)

                    if dual and (dual[0] > lastBreak):
                        pageLines += dual[1]
                    else:
                        pageLines += 10
                        if ls[i].lb == lbl:
                            pageLines += ct[ls[i + 1].lt].beforeSpacing
                        else:
                            pageLines += ct[ls[i + 1].lt].intraSpacing

                    if pageLines > lp:
                        break

                    i += 1

            if i >= (length - 1):
                if pageLines != 0:
                    self.pages.append(length - 1)
                    self.pagesNoAdjust.append(length - 1)

                break

            self.pagesNoAdjust.append(i)

            # don't split a dual dialogue between pages. if it starts at
            # the top of the page and still doesn't fit, it's split
            # between its columns, or failing that, like a normal speech.
            block = dualBlockAt.get(i)

            if block:
                first, right, last = block

                if first > (lastBreak + 1):
                    i = first - 1
                elif i >= right:
                    i = right - 1

            line = ls[i]

            if line.lt == SCENE:
                i = self.removeDanglingElement(i, SCENE, lastBreak)

            elif line.lt == SHOT:
                i = self.removeDanglingElement(i, SHOT, lastBreak)
                i = self.removeDanglingElement(i, SCENE, lastBreak)

            elif line.lt == ACTION:
                if line.lb != LB_LAST:
                    first = self.getElemFirstIndexFromLine(i)

                    if first > (lastBreak + 1):
                        linesOnThisPage = i - first + 1
                        if linesOnThisPage < cfg.pbActionLines:
                            i = first - 1

                        i = self.removeDanglingElement(i, SCENE, lastBreak)

            elif line.lt == CHARACTER:
                i = self.removeDanglingElement(i, CHARACTER, lastBreak)
                i = self.removeDanglingElement(i, SCENE, lastBreak)

            elif line.lt in (DIALOGUE, PAREN):

                if line.lb != LB_LAST or self.getTypeOfNextElem(i) in (DIALOGUE, PAREN):

                    cutDialogue = False
                    cutParen = False
                    while 1:
                        oldI = i
                        line = ls[i]

                        if line.lt == PAREN:
                            i = self.removeDanglingElement(i, PAREN, lastBreak)
                            cutParen = True

                        elif line.lt == DIALOGUE:
                            if cutParen:
                                break

                            first = self.getElemFirstIndexFromLine(i)

                            if first > (lastBreak + 1):
                                linesOnThisPage = i - first + 1

                                # do we need to reserve one line for (MORE)
                                reserveLine = not (cutDialogue or cutParen)

                                val = cfg.pbDialogueLines
                                if reserveLine:
                                    val += 1

                                if linesOnThisPage < val:
                                    i = first - 1
                                    cutDialogue = True
                                else:
                                    if reserveLine:
                                        i -= 1
                                    break
                            else:
                                # leave space for (MORE)
                                i -= 1
                                break

                        elif line.lt == CHARACTER:
                            i = self.removeDanglingElement(i, CHARACTER, lastBreak)
                            i = self.removeDanglingElement(i, SCENE, lastBreak)

                            break

                        else:
                            break

                        if i == oldI:
                            break

            # make sure no matter how buggy the code above is, we always
            # advance at least one line per page
            i = max(i, lastBreak + 1)

            self.pages.append(i)
            lastBreak = i

            i += 1

        return len(self.pages) - oldCnt

    # return a list of (line, label) tuples for the lines that start a
    # locked page, in script order, skipping any that are out of order.
    def getPageLocks(self):
        locks = [
            (i, ln.pageLock)
            for i, ln in enumerate(self.lines)
            if ln.pageLock and pagelock.isValid(ln.pageLock)
        ]

        return pagelock.orderedLocks(locks)

    def hasPageLocks(self):
        return any(ln.pageLock for ln in self.lines)

    # lock every page to start where it starts now, with its current
    # label, so later edits create A-pages / leave gaps instead of moving
    # text to other pages. if pages are already locked, any A-pages
    # become locked as well.
    def lockPages(self):
        u = undo.FullCopy(self)

        self.paginate()

        for ln in self.lines:
            ln.pageLock = None

        for p in range(1, len(self.pages)):
            self.lines[self.pages[p - 1] + 1].pageLock = self.pageLabels[p]

        self.paginate()
        self.markChanged()

        u.setAfter(self)
        self.addUndo(u)

    def unlockPages(self):
        if not self.hasPageLocks():
            return

        u = undo.FullCopy(self)

        for ln in self.lines:
            ln.pageLock = None

        self.paginate()
        self.markChanged()

        u.setAfter(self)
        self.addUndo(u)

    # return what toggleDualDialogue would do, as (block, makeDual), where
    # block is the dual dialogue in the format of getDualBlockFromRight and
    # makeDual is False if it would be made normal again, or None if
    # toggling isn't possible at the cursor.
    def getDualToggle(self):
        ls = self.lines

        speech = self.getSpeechIndexes(self.line)

        if not speech:
            return None

        block = self.getDualBlock(self.line)

        if block:
            return (block, False)

        for r in (speech[0], speech[1] + 1):
            if (r >= len(ls)) or (ls[r].lt != CHARACTER):
                continue

            # don't take over a speech from another dual dialogue
            if (r != speech[0]) and self.getDualBlock(r):
                continue

            old = ls[r].dual
            ls[r].dual = True
            block = self.getDualBlockFromRight(r)
            ls[r].dual = old

            if block:
                return (block, True)

        return None

    # if the cursor is in a dual dialogue, make its speeches normal again.
    # otherwise make the speech the cursor is in a dual dialogue with the
    # speech right before it, or failing that, the one right after it.
    # returns False if that wasn't possible.
    def toggleDualDialogue(self):
        ls = self.lines

        toggle = self.getDualToggle()

        if not toggle:
            return False

        block, makeDual = toggle
        first, right, last = block
        elemCnt = self.elemsDistance(first, last) + 1

        u = undo.ManyElems(self, undo.CMD_MISC, first, elemCnt, elemCnt)

        ls[right].dual = makeDual

        # rewrap both speeches to their new widths
        self.rewrapElems(first, elemCnt)

        self.clearAutoComp()
        self.markChanged()

        u.setAfter(self)
        self.addUndo(u)

        return True

    # add a page lock to the given line. if it already has one, the two
    # pages are combined (e.g. "16-17").
    def addPageLock(self, line, label):
        ln = self.lines[line]

        if ln.pageLock:
            ln.pageLock = pagelock.combine(label, ln.pageLock)
        else:
            ln.pageLock = label

    # lines first - last (inclusive) are about to be deleted or moved
    # elsewhere, so move their page locks to the line after them. if there
    # is no line after them, the locks are removed.
    def movePageLocksForward(self, first, last):
        ls = self.lines
        label = None

        for i in range(first, last + 1):
            if ls[i].pageLock:
                if label:
                    label = pagelock.combine(label, ls[i].pageLock)
                else:
                    label = ls[i].pageLock

                ls[i].pageLock = None

        if label and (last + 1) < len(ls):
            self.addPageLock(last + 1, label)

    def removeDanglingElement(self, line, lt, lastBreak):
        ls = self.lines
        startLine = line

        while 1:
            if line < (lastBreak + 2):
                break

            ln = ls[line]

            if ln.lt != lt:
                break

            # only remove one element at most, to avoid generating
            # potentially thousands of pages in degenerate cases when
            # script only contains scenes or characters or something like
            # that.
            if (line != startLine) and (ln.lb == LB_LAST):
                break

            line -= 1

        return line

    # convert element(s) to given type
    #  - if multiple elements are selected, all are changed
    #  - if not, the change is applied to element under cursor.
    def convertTypeTo(self, lt, saveUndo):
        ls = self.lines
        selection = self.getMarkedLines()

        if selection:
            startSection, endSection = selection
            selectedElems = self.elemsDistance(startSection, endSection) + 1
        else:
            startSection, endSection = self.getElemIndexes()
            selectedElems = 1

        currentLine = startSection

        if saveUndo:
            # the speeches around the changed elements may move into or
            # out of a dual dialogue, so they're rewrapped too, and
            # included in the undo
            wrapFirst, wrapLast = self.getSpeechRangeAround(startSection, endSection)
            wrapCnt = self.elemsDistance(wrapFirst, wrapLast) + 1

            u = undo.ManyElems(self, undo.CMD_MISC, wrapFirst, wrapCnt, wrapCnt)

        while currentLine <= endSection:
            first, last = self.getElemIndexesFromLine(currentLine)

            # if changing away from PAREN containing only "()", remove it
            if (first == last) and (ls[first].lt == PAREN) and (ls[first].text == "()"):
                ls[first].text = ""

                if first == self.line:
                    self.column = 0

            for i in range(first, last + 1):
                ls[i].lt = lt

            # if changing empty element to PAREN, add "()"
            if (
                (first == last)
                and (ls[first].lt == PAREN)
                and (len(ls[first].text) == 0)
            ):
                ls[first].text = "()"

                if first == self.line:
                    self.column = 1

            currentLine = last + 1

        if selection:
            self.clearMark()

            # this is moderately complex because we need to deal with
            # forced linebreaks; reformatRange wants paragraph indexes but
            # we are converting elements, so we must find the indexes of
            # the a) first paragraph of the first selected element and b)
            # last paragraph of the last selected element

            self.reformatRange(
                self.getElemFirstIndexFromLine(startSection),
                self.getParaFirstIndexFromLine(
                    self.getElemLastIndexFromLine(endSection)
                ),
            )
        else:
            self.rewrapElem(first)

        self.markChanged()

        if saveUndo:
            self.rewrapElems(wrapFirst, wrapCnt)

            u.setAfter(self)
            self.addUndo(u)

    # join lines 'line' and 'line + 1' and position cursor at the join
    # position.
    def joinLines(self, line):
        ls = self.lines
        ln = ls[line]

        pos = len(ln.text)
        ln.text += ls[line + 1].text
        ln.lb = ls[line + 1].lb

        # the joined line's page lock now points into the middle of this
        # line. rewrapPara uses pageLockCol to put it back on the right
        # line.
        label = ls[line + 1].pageLock

        if label:
            if ln.pageLock:
                ln.pageLock = pagelock.combine(ln.pageLock, label)
            else:
                ln.pageLock = label
                ln.pageLockCol = pos

        self.setLineTypes(line + 1, ln.lt)
        del ls[line + 1]

        self.line = line
        self.column = pos

    # split current line at current column position.
    def splitLine(self):
        ln = self.lines[self.line]

        s = ln.text
        preStr = s[: self.column]
        postStr = s[self.column :]
        newLine = Line(ln.lb, ln.lt, postStr)
        ln.text = preStr
        ln.lb = LB_FORCED
        self.lines.insert(self.line + 1, newLine)

        self.line += 1
        self.column = 0
        self.markChanged()

    # split element at current position. newType is type to give to the
    # new element.
    def splitElement(self, newType):
        ls = self.lines

        if self.mark:
            self.clearMark()

            return

        # splitting a speech can make it, or the speeches around it, part
        # of a dual dialogue or take them out of one, so they're rewrapped
        # too, and included in the undo
        wrapFirst, wrapLast = self.getSpeechRangeAround(self.line, self.line)
        wrapCnt = self.elemsDistance(wrapFirst, wrapLast) + 1

        u = undo.ManyElems(self, undo.CMD_MISC, wrapFirst, wrapCnt, wrapCnt + 1)

        if not self.acItems:
            if self.isAtEndOfParen():
                self.column += 1
        else:
            ls[self.line].text = self.acItems[self.acSel]
            self.column = len(ls[self.line].text)

        self.splitLine()
        ls[self.line - 1].lb = LB_LAST

        self.convertTypeTo(newType, False)

        self.rewrapPara()
        self.rewrapPrevPara()
        self.rewrapElems(wrapFirst, wrapCnt + 1)
        self.markChanged()

        u.setAfter(self)
        self.addUndo(u)

    # delete character at given position and optionally position
    # cursor there.
    def deleteChar(self, line, column, posCursor=True):
        s = self.lines[line].text
        self.lines[line].text = s[:column] + s[column + 1 :]

        if posCursor:
            self.column = column
            self.line = line

    # set line types from 'line' to the end of the element to 'lt'.
    def setLineTypes(self, line, lt):
        ls = self.lines

        while 1:
            ln = ls[line]

            ln.lt = lt
            if ln.lb == LB_LAST:
                break

            line += 1

    def line2page(self, line):
        return self.line2pageReal(line, self.pages)

    def line2pageNoAdjust(self, line):
        return self.line2pageReal(line, self.pagesNoAdjust)

    def line2pageReal(self, line, p):
        lo = 1
        hi = len(p) - 1

        while lo != hi:
            mid = (lo + hi) // 2

            if line <= p[mid]:
                hi = mid
            else:
                lo = mid + 1

        return lo

    # return (startLine, endLine) for given page number (1-based). if
    # pageNr is out of bounds, it is clamped to the valid range. if
    # pagination is out of date and the lines no longer exist, they are
    # clamped to the valid range as well.
    def page2lines(self, pageNr):
        pageNr = util.clamp(pageNr, 1, len(self.pages) - 1)
        last = len(self.lines) - 1

        return (
            util.clamp(self.pages[pageNr - 1] + 1, 0, last),
            util.clamp(self.pages[pageNr], 0, last),
        )

    # return the label of the given page (1-based index into self.pages),
    # e.g. "16" or "15A". pageNr is clamped to the valid range.
    def getPageLabel(self, pageNr):
        return self.pageLabels[util.clamp(pageNr, 1, len(self.pageLabels) - 1)]

    # return the label of the page the given line is on
    def line2pageLabel(self, line):
        return self.getPageLabel(self.line2page(line))

    # return the page number (1-based index into self.pages) of the page
    # with the given label (case-insensitive), or -1 if there's none.
    def label2page(self, label):
        label = pagelock.normalize(label)

        for p in range(1, len(self.pageLabels)):
            if self.pageLabels[p] == label:
                return p

        return -1

    # return a list of all page labels, in order.
    def getPageNumbers(self):
        return self.pageLabels[1:]

    # return a list of all scene locations in a [(sceneNumber, startLine),
    # ...] format. if script does not start with a scene line, that scene
    # is not included in this list. note that the sceneNumber in the
    # returned list is a string, not a number.
    def getSceneLocations(self):
        ls = self.lines
        sc = SCENE
        scene = 0
        ret = []

        for i in range(len(ls)):
            if (ls[i].lt == sc) and self.isFirstLineOfElem(i):
                scene += 1
                ret.append((str(scene), i))

        return ret

    # return the first line of every scene heading and act break element,
    # in script order.
    def getOutlineStarts(self):
        ls = self.lines

        return [
            i
            for i in range(len(ls))
            if (ls[i].lt in (SCENE, ACTBREAK)) and self.isFirstLineOfElem(i)
        ]

    # return the outline color of the scene heading or act break element
    # starting at line i, or None if it has none or line i isn't the first
    # line of such an element.
    def getSceneColor(self, i):
        ln = self.lines[i]

        if ln.color and (ln.lt in (SCENE, ACTBREAK)) and self.isFirstLineOfElem(i):
            return ln.color

        return None

    # set the outline color of the scene (or act break) containing the
    # given line to color ("rrggbb"), or remove it if color is None.
    # returns False if the line isn't in a scene or the scene already has
    # that color.
    def setSceneColor(self, line, color):
        starts = self.getOutlineStarts()
        idx = self.getOutlineIndex(starts, line)

        if idx == -1:
            return False

        start = starts[idx]

        if color is not None:
            color = color.lower()

        if self.getSceneColor(start) == color:
            return False

        u = undo.SinglePara(self, undo.CMD_MISC, start)

        self.lines[start].color = color
        self.markChanged()

        u.setAfter(self)
        self.addUndo(u)

        return True

    # return the full text of the element starting at the given line, with
    # line breaks converted to spaces.
    def getElemText(self, line):
        ls = self.lines
        s = ""

        while 1:
            ln = ls[line]
            s += ln.text

            if ln.lb == LB_LAST:
                break

            s += config.lb2str(ln.lb).replace("\n", " ")
            line += 1

        return s

    # return the script's outline as a list of OutlineItems, one for each
    # scene and act break, in script order. anything before the first
    # scene / act break is not included. page numbers are only accurate
    # if pagination is up to date.
    def getOutline(self):
        ls = self.lines
        starts = self.getOutlineStarts()
        ret = []
        scene = 0

        for idx, start in enumerate(starts):
            if idx + 1 < len(starts):
                end = starts[idx + 1] - 1
            else:
                end = len(ls) - 1

            lt = ls[start].lt
            heading = self.getElemText(start)

            if self.cfg.getType(lt).screen.isCaps:
                heading = util.upper(heading)

            if lt == SCENE:
                scene += 1
                sceneNr = str(scene)
            else:
                sceneNr = ""

            note = None
            action = None

            i = start + 1

            while i <= end:
                if self.isFirstLineOfElem(i):
                    if (ls[i].lt == NOTE) and (note is None):
                        note = self.getElemText(i)
                        break
                    elif (ls[i].lt == ACTION) and (action is None):
                        action = self.getElemText(i)

                i += 1

            summary = note if note is not None else (action or "")

            ret.append(
                OutlineItem(
                    lt,
                    sceneNr,
                    start,
                    end,
                    heading,
                    summary,
                    self.line2pageLabel(start),
                    self.getSceneColor(start),
                )
            )

        return ret

    # return the index in starts (as returned by getOutlineStarts) of the
    # scene / act break containing the given line, or -1 if the line is
    # before the first one.
    def getOutlineIndex(self, starts, line):
        idx = -1

        for i, start in enumerate(starts):
            if start <= line:
                idx = i
            else:
                break

        return idx

    # move the scene (or act break) containing the given line one step up
    # (direction = -1) or down (direction = 1) in the script, swapping it
    # with its neighbor. see moveSceneTo.
    def moveScene(self, line, direction):
        idx = self.getOutlineIndex(self.getOutlineStarts(), line)

        if idx == -1:
            return False

        return self.moveSceneTo(line, idx + direction)

    # move the scene (or act break) containing the given line so that it
    # becomes item number newIndex (0-based) in the outline, shifting the
    # ones in between by one. material before the first scene / act break
    # is never moved, and nothing can be moved above it. on success, the
    # cursor is placed at the start of the moved scene and True is
    # returned.
    def moveSceneTo(self, line, newIndex):
        starts = self.getOutlineStarts()
        idx = self.getOutlineIndex(starts, line)

        if (idx == -1) or (newIndex == idx):
            return False

        if (newIndex < 0) or (newIndex >= len(starts)):
            return False

        self.clearAutoComp()

        bounds = starts + [len(self.lines)]
        blocks = [self.lines[bounds[i] : bounds[i + 1]] for i in range(len(starts))]

        u = undo.AnyDifference(self)

        # moving a scene is like cutting and pasting it: the pages it was
        # locked to stay where they were, starting from whatever followed
        # the scene.
        if idx + 1 < len(blocks):
            self.movePageLocksForward(starts[idx], bounds[idx + 1] - 1)
        else:
            for ln in blocks[idx]:
                ln.pageLock = None

        blocks.insert(newIndex, blocks.pop(idx))

        newLines = []

        for i, block in enumerate(blocks):
            if i == newIndex:
                self.line = starts[0] + len(newLines)

            newLines.extend(block)

        self.lines[starts[0] :] = newLines
        self.column = 0

        self.clearMark()
        self.markChanged()

        u.setAfter(self)
        self.addUndo(u)

        return True

    # return a dictionary of all scene names (single-line text elements
    # only, upper-cased, values = None).
    def getSceneNames(self):
        names = {}

        for ln in self.lines:
            if (ln.lt == SCENE) and (ln.lb == LB_LAST):
                names[util.upper(ln.text)] = None

        return names

    # return a dictionary of all character names (single-line text
    # elements only, lower-cased, values = None).
    def getCharacterNames(self):
        names = {}

        ul = util.lower

        for ln in self.lines:
            if (ln.lt == CHARACTER) and (ln.lb == LB_LAST):
                names[ul(ln.text)] = None

        return names

    # get next word, starting at (line, col). line must be valid, but col
    # can point after the line's length, in which case the search starts
    # at (line + 1, 0). returns (word, line, col), where word is None if
    # at end of script, and (line, col) point to the start of the word.
    # note that this only handles words that are on a single line.
    def getWord(self, line, col):
        ls = self.lines

        while 1:
            if (line < 0) or (line >= len(ls)):
                return (None, 0, 0)

            s = ls[line].text

            if col >= len(s):
                line += 1
                col = 0

                continue

            ch = s[col : col + 1]

            if not util.isWordBoundary(ch):
                word = ch
                startCol = col
                col += 1

                while col < len(s):
                    ch = s[col : col + 1]

                    if util.isWordBoundary(ch):
                        break

                    word += ch
                    col += 1

                return (word, line, startCol)

            else:
                col += 1

    # returns True if we're at second-to-last character of PAREN element,
    # and last character is ")"
    def isAtEndOfParen(self):
        ls = self.lines

        return (
            self.isLastLineOfElem(self.line)
            and (ls[self.line].lt == PAREN)
            and (ls[self.line].text[self.column :] == ")")
        )

    # returns True if pressing TAB at current position would make a new
    # element, False if it would just change element's type.
    def tabMakesNew(self):
        l = self.lines[self.line]

        if self.isAtEndOfParen():
            return True

        if (l.lb != LB_LAST) or (self.column != len(l.text)):
            return False

        if (len(l.text) == 0) and self.isOnlyLineOfElem(self.line):
            return False

        return True

    # if auto-completion is active, clear it and return True. otherwise
    # return False.
    def clearAutoComp(self):
        if not self.acItems:
            return False

        self.acItems = None

        return True

    def fillAutoComp(self):
        ls = self.lines

        lt = ls[self.line].lt
        t = self.autoCompletion.getType(lt)

        if t and t.enabled:
            self.acItems = self.getMatchingText(ls[self.line].text, lt)
            self.acSel = 0

    # page up (dir == -1) or page down (dir == 1) was pressed and we're in
    # auto-comp mode, handle it.
    def pageScrollAutoComp(self, dir):
        if len(self.acItems) > self.acMax:

            if dir < 0:
                self.acSel -= self.acMax

                if self.acSel < 0:
                    self.acSel = len(self.acItems) - 1

            else:
                self.acSel = (self.acSel + self.acMax) % len(self.acItems)

    # get a list of strings (single-line text elements for now) that start
    # with 'text' (not case sensitive) and are of of type 'type'. also
    # mixes in the type's default items from config. ignores current line.
    def getMatchingText(self, text, lt):
        text = util.upper(text)
        t = self.autoCompletion.getType(lt)
        ls = self.lines
        matches = {}
        last = None

        for i in range(len(ls)):
            if (ls[i].lt == lt) and (ls[i].lb == LB_LAST):
                upstr = util.upper(ls[i].text)

                if upstr.startswith(text) and i != self.line:
                    matches[upstr] = None
                    if i < self.line:
                        last = upstr

        for s in t.items:
            upstr = util.upper(s)

            if upstr.startswith(text):
                matches[upstr] = None

        if last:
            del matches[last]

        mlist = list(matches.keys())
        mlist.sort()

        if last:
            mlist.insert(0, last)

        return mlist

    # returns pair (start, end) of marked lines, inclusive. if mark is
    # after the end of the script (text has been deleted since setting
    # it), returns a valid pair (by truncating selection to current
    # end). returns None if no lines marked.
    def getMarkedLines(self):
        if not self.mark:
            return None

        mark = min(len(self.lines) - 1, self.mark.line)

        if self.line < mark:
            return (self.line, mark)
        else:
            return (mark, self.line)

    # returns pair (start, end) (inclusive) of marked columns for the
    # given line (line must be inside the marked lines). 'marked' is the
    # value returned from getMarkedLines. if marked column is invalid
    # (text has been deleted since setting the mark), returns a valid pair
    # by truncating selection as needed. returns None on errors.
    def getMarkedColumns(self, line, marked):
        if not self.mark:
            return None

        # line is not marked at all
        if (line < marked[0]) or (line > marked[1]):
            return None

        ls = self.lines

        # last valid offset for given line's text
        lvo = max(0, len(ls[line].text) - 1)

        # only one line marked
        if (line == marked[0]) and (marked[0] == marked[1]):
            c1 = min(self.mark.column, self.column)
            c2 = max(self.mark.column, self.column)

        # line is between end lines, so totally marked
        elif (line > marked[0]) and (line < marked[1]):
            c1 = 0
            c2 = lvo

        # line is first line marked
        elif line == marked[0]:

            if line == self.line:
                c1 = self.column

            else:
                c1 = self.mark.column

            c2 = lvo

        # line is last line marked
        elif line == marked[1]:

            if line == self.line:
                c2 = self.column

            else:
                c2 = self.mark.column

            c1 = 0

        # should't happen
        else:
            return None

        c1 = util.clamp(c1, 0, lvo)
        c2 = util.clamp(c2, 0, lvo)

        return (c1, c2)

    # checks if a line is marked. 'marked' is the value returned from
    # getMarkedLines.
    def isLineMarked(self, line, marked):
        return (line >= marked[0]) and (line <= marked[1])

    # get selected text as a ClipData object, optionally deleting it from
    # the script. if nothing is selected, returns None.
    def getSelectedAsCD(self, doDelete):
        marked = self.getMarkedLines()

        if not marked:
            return None

        ls = self.lines

        cd = ClipData()

        for i in range(marked[0], marked[1] + 1):
            c1, c2 = self.getMarkedColumns(i, marked)

            ln = ls[i]

            cd.lines.append(
                Line(
                    ln.lb,
                    ln.lt,
                    ln.text[c1 : c2 + 1],
                    dual=self.hasDualFlag(i) and (c1 == 0),
                    color=self.getSceneColor(i) if (c1 == 0) else None,
                )
            )

        cd.lines[-1].lb = LB_LAST

        if not doDelete:
            return cd

        u = undo.AnyDifference(self)

        # range of lines, inclusive, that we need to totally delete
        del1 = sys.maxsize
        del2 = -1

        # delete selected text from the lines
        for i in range(marked[0], marked[1] + 1):
            c1, c2 = self.getMarkedColumns(i, marked)

            ln = ls[i]
            ln.text = ln.text[0:c1] + ln.text[c2 + 1 :]

            if i == marked[0]:
                endCol = c1

            # if we removed all text, mark this line to be deleted
            if len(ln.text) == 0:
                del1 = min(del1, i)
                del2 = max(del2, i)

        # adjust linebreaks
        if marked[0] == marked[1]:

            # user has selected text from a single line only

            ln = ls[marked[0]]

            # if it is a single-line element, we never need to modify
            # its linebreak
            if not self.isOnlyLineOfElem(marked[0]):
                # if we're totally deleting the line and it's the last
                # line of a multi-line element, mark the preceding
                # line as the new last line of the element.

                if not ln.text and self.isLastLineOfElem(marked[0]):
                    ls[marked[0] - 1].lb = LB_LAST

        else:

            # now find the line whose linebreak we need to adjust. if
            # the starting line is not completely removed, it is that,
            # otherwise it is the preceding line, unless we delete the
            # first line of the element, in which case there's nothing
            # to adjust.
            if ls[marked[0]].text:
                ln = ls[marked[0]]
            else:
                if not self.isFirstLineOfElem(marked[0]):
                    ln = ls[marked[0] - 1]
                else:
                    ln = None

            if ln:
                # if the selection ends by removing completely the
                # last line of an element, we need to mark the
                # element's new end, otherwise we must set it to
                # LB_NONE so that the new element is reformatted
                # properly.
                if self.isLastLineOfElem(marked[1]) and not ls[marked[1]].text:
                    ln.lb = LB_LAST
                else:
                    ln.lb = LB_NONE

        # if we're joining two elements we have to change the line
        # types for the latter element (starting from the last marked
        # line, because everything before that will get deleted
        # anyway) to that of the first element.
        self.setLineTypes(marked[1], ls[marked[0]].lt)

        if del2 != -1:
            self.movePageLocksForward(del1, del2)

        del ls[del1 : del2 + 1]

        self.clearMark()

        if len(ls) == 0:
            ls.append(Line(LB_LAST, SCENE))

        self.line = min(marked[0], len(ls) - 1)
        self.column = min(endCol, len(ls[self.line].text))

        self.rewrapElem()
        self.rewrapSpeechesAround(self.line, self.line)
        self.markChanged()

        u.setAfter(self)
        self.addUndo(u)

        return cd

    # paste data into script. clines is a list of Line objects.
    def paste(self, clines):
        if len(clines) == 0:
            return

        u = undo.AnyDifference(self)

        inLines = []
        i = 0

        # wrap all paragraphs into single lines
        while 1:
            if i >= len(clines):
                break

            ln = clines[i]

            newLine = Line(LB_LAST, ln.lt, dual=ln.dual, color=ln.color)

            while 1:
                ln = clines[i]
                i += 1

                newLine.text += ln.text

                if ln.lb in (LB_LAST, LB_FORCED):
                    break

                newLine.text += config.lb2str(ln.lb)

            newLine.lb = ln.lb
            inLines.append(newLine)

        # shouldn't happen, but...
        if len(inLines) == 0:
            return

        ls = self.lines

        # where we need to start wrapping
        wrap1 = self.getParaFirstIndexFromLine(self.line)

        ln = ls[self.line]

        atEnd = self.column == len(ln.text)

        if (len(ln.text) == 0) and self.isOnlyLineOfElem(self.line):
            ln.lt = inLines[0].lt
            ln.dual = inLines[0].dual
            ln.color = inLines[0].color

        ln.text = ln.text[: self.column] + inLines[0].text + ln.text[self.column :]
        self.column += len(inLines[0].text)

        if len(inLines) != 1:

            if not atEnd:
                self.splitLine()
                ls[self.line - 1].lb = inLines[0].lb
                ls[self.line : self.line] = inLines[1:]
                self.line += len(inLines) - 2

                # FIXME: pasting a multi-paragraph ACTION where first line
                # has FORCED lb, in middle of a CHARACTER block, breaks
                # things

            else:
                ls[self.line + 1 : self.line + 1] = inLines[1:]
                self.line += len(inLines) - 1

                # FIXME: this doesn't modify .lb, and pasting a
                # multi-paragraph ACTION at end of line in CHARACTER block
                # where that line ends in forced linebreak breaks things.

            self.column = len(ls[self.line].text)

        # FIXME: copy/paste, when copying elements containing forced
        # linebreaks, converts them to end of element? this seems like a
        # bug...

        self.reformatRange(wrap1, self.getParaFirstIndexFromLine(self.line))
        self.rewrapSpeechesAround(wrap1, self.line)

        u.setAfter(self)
        self.addUndo(u)

        self.clearMark()
        self.clearAutoComp()
        self.markChanged()

    # returns true if a character, inserted at current position, would
    # need to be capitalized as a start of a sentence.
    def capitalizeNeeded(self):
        if not self.cfgGl.capitalize:
            return False

        ls = self.lines
        line = self.line
        column = self.column

        text = ls[line].text
        if (column < len(text)) and (text[column] != " "):
            return False

        # go backwards at most 4 characters, looking for "!?.", and
        # breaking on anything other than space or ".

        cnt = 1
        while 1:
            column -= 1

            char = None

            if column < 0:
                line -= 1

                if line < 0:
                    return True

                lb = ls[line].lb

                if lb == LB_LAST:
                    return True

                elif lb == LB_SPACE:
                    char = " "
                    column = len(ls[line].text)

                else:
                    text = ls[line].text
                    column = len(text) - 1

                    if column < 0:
                        return True
            else:
                text = ls[line].text

            if not char:
                char = text[column]

            if cnt == 1:
                # must be preceded by a space
                if char != " ":
                    return False
            else:
                if char in (".", "?", "!"):
                    return True
                elif char not in (" ", '"'):
                    return False

            cnt += 1

            if cnt > 4:
                break

        return False

    # find next error in screenplay, starting at given line. returns
    # (line, msg) tuple, where line is -1 if no error was found and the
    # line number otherwise where the error is, and msg is a description
    # of the error
    def findError(self, line):
        ls = self.lines
        cfg = self.cfg

        # type of previous line, or None when a new element starts
        prevType = None

        msg = None
        while 1:
            if line >= len(ls):
                break

            ln = ls[line]
            tcfg = cfg.getType(ln.lt)

            isFirst = self.isFirstLineOfElem(line)
            isLast = self.isLastLineOfElem(line)
            isOnly = isFirst and isLast

            prev = self.getTypeOfPrevElem(line)
            next = self.getTypeOfNextElem(line)

            # notes are allowed to contain empty lines, because a) they do
            # not appear in the final product b) they're basically
            # free-format text anyway, and people may want to format them
            # however they want

            if (len(ln.text) == 0) and (ln.lt != NOTE):
                msg = _("Empty line.")
                break

            if (len(ln.text.strip("  ")) == 0) and (ln.lt != NOTE):
                msg = _("Empty line (contains only spaces).")
                break

            if (ln.lt == PAREN) and isOnly and (ln.text == "()"):
                msg = _("Empty parenthetical.")
                break

            if ln.text != util.toInputStr(ln.text):
                msg = _("Line contains invalid characters (BUG).")
                break

            if len(ln.text.rstrip(" ")) > tcfg.width:
                msg = _("Line is too long (BUG).")
                break

            if ln.lt == CHARACTER:
                if isLast and next and next not in (PAREN, DIALOGUE):
                    msg = _(
                        "Element type '{}' can not follow type '{}'.".format(
                            cfg.getType(next).ti.name, tcfg.ti.name
                        )
                    )
                    break

            if ln.lt == PAREN:
                if isFirst and prev and prev not in (CHARACTER, DIALOGUE):
                    msg = _(
                        "Element type '{}' can not follow type '{}'.".format(
                            tcfg.ti.name, cfg.getType(prev).ti.name
                        )
                    )
                    break

            if ln.lt == DIALOGUE:
                if isFirst and prev and prev not in (CHARACTER, PAREN):
                    msg = _(
                        "Element type '{}' can not follow type '{}'.".format(
                            tcfg.ti.name, cfg.getType(prev).ti.name
                        )
                    )
                    break

            if prevType:
                if ln.lt != prevType:
                    msg = _("Element contains lines with different line types (BUG).")
                    break

            if ln.lb == LB_LAST:
                prevType = None
            else:
                prevType = ln.lt

            line += 1

        if not msg:
            line = -1

        return (line, msg)

    # compare this script to sp2 (Screenplay), return a PDF file (as a
    # string) of the differences, or None if the scripts are identical.
    def compareScripts(self, sp2) -> bytes:
        s1 = self.generateText(False).split("\n")
        s2 = sp2.generateText(False).split("\n")

        dltTmp = difflib.unified_diff(s1, s2, lineterm="")

        # get rid of stupid delta generator object that doesn't allow
        # subscription or anything else really. also expands hunk
        # separators into three lines.
        dlt = []
        i = 0
        for s in dltTmp:
            if i >= 3:
                if s[0] == "@":
                    dlt.extend(["1", "2", "3"])
                else:
                    dlt.append(s)

            i += 1

        if len(dlt) == 0:
            return None

        dltTmp = dlt

        # now, generate changed-lines for single-line diffs
        dlt = []
        for i in range(len(dltTmp)):
            s = dltTmp[i]

            dlt.append(s)

            # this checks that we've just added a sequence of lines whose
            # first characters are " -+", where " " means '"not -" or
            # missing line', and that we're either at end of list or next
            # line does not start with "+".

            if (
                (s[0] == "+")
                and (i != 0)
                and (dltTmp[i - 1][0] == "-")
                and ((i == 1) or (dltTmp[i - 2][0] != "-"))
                and ((i == (len(dltTmp) - 1)) or (dltTmp[i + 1][0] != "+"))
            ):

                # generate line with "^" character at every position that
                # the lines differ

                s1 = dltTmp[i - 1]
                s2 = dltTmp[i]

                minCnt = min(len(s1), len(s2))
                maxCnt = max(len(s1), len(s2))

                res = "^"

                for i in range(1, minCnt):
                    if s1[i] != s2[i]:
                        res += "^"
                    else:
                        res += " "

                res += "^" * (maxCnt - minCnt)

                dlt.append(res)

        tmp = [
            "  Color information:",
            "1",
            "-  Deleted lines",
            "+  Added lines",
            "^  Positions of single-line changes (marked with ^)",
            "1",
            "2",
            "2",
            "3",
        ]
        tmp.extend(dlt)
        dlt = tmp

        cfg = self.cfg
        chY = util.getTextHeight(cfg.fontSize)

        doc = pml.Document(cfg.paperWidth, cfg.paperHeight)

        # how many lines put on current page
        y = 0

        pg = pml.Page(doc)

        # we need to gather text ops for each page into a separate list
        # and add that list to the page only after all other ops are
        # added, otherwise the colored bars will be drawn partially over
        # some characters.
        textOps = []

        for s in dlt:

            if y >= cfg.linesOnPage:
                pg.ops.extend(textOps)
                doc.add(pg)

                pg = pml.Page(doc)

                textOps = []
                y = 0

            if s[0] == "1":
                pass

            elif s[0] == "3":
                pass

            elif s[0] == "2":
                pg.add(pml.PDFOp("0.75 g"))
                w = 50.0
                pg.add(
                    pml.RectOp(
                        doc.w / 2.0 - w / 2.0,
                        cfg.marginTop + y * chY + chY / 4,
                        w,
                        chY / 2.0,
                    )
                )
                pg.add(pml.PDFOp("0.0 g"))

            else:
                color = ""

                if s[0] == "-":
                    color = "1.0 0.667 0.667"
                elif s[0] == "+":
                    color = "0.667 1.0 0.667"
                elif s[0] == "^":
                    color = "1.0 1.0 0.467"

                if color:
                    pg.add(pml.PDFOp("%s rg" % color))
                    pg.add(
                        pml.RectOp(
                            cfg.marginLeft,
                            cfg.marginTop + y * chY,
                            doc.w - cfg.marginLeft - 5.0,
                            chY,
                        )
                    )
                    pg.add(pml.PDFOp("0.0 g"))

                textOps.append(
                    pml.TextOp(
                        s[1:], cfg.marginLeft, cfg.marginTop + y * chY, cfg.fontSize
                    )
                )

            y += 1

        pg.ops.extend(textOps)
        doc.add(pg)

        return pdf.generate(doc)

    # move to line,col, and if mark is True, set mark there
    def gotoPos(self, line, col, mark=False):
        self.clearAutoComp()

        self.line = line
        self.column = col

        if mark and not self.mark:
            self.setMark(line, col)

    # remove all lines whose element types are in tdict as keys.
    def removeElementTypes(self, tdict, saveUndo):
        self.clearAutoComp()

        if saveUndo:
            u = undo.FullCopy(self)

        lsNew = []
        lsOld = self.lines
        sl = self.line

        # how many lines were removed from above the current line
        # (inclusive)
        cnt = 0

        # page lock of removed lines, to be moved to the next line kept
        label = None

        for i in range(len(lsOld)):
            l = lsOld[i]

            if l.lt not in tdict:
                if label:
                    if l.pageLock:
                        l.pageLock = pagelock.combine(label, l.pageLock)
                    else:
                        l.pageLock = label

                    label = None

                lsNew.append(l)
            else:
                if l.pageLock:
                    if label:
                        label = pagelock.combine(label, l.pageLock)
                    else:
                        label = l.pageLock

                if i <= sl:
                    cnt += 1

        self.line -= cnt

        if len(lsNew) == 0:
            lsNew.append(Line(LB_LAST, SCENE))

        self.lines = lsNew

        self.validatePos()
        self.clearMark()
        self.markChanged()

        if saveUndo:
            u.setAfter(self)
            self.addUndo(u)

    # rename characters. 'renames' is a dictionary mapping old names to
    # new ones, both normalized with characterprofiles.normalizeName.
    # character cues are renamed keeping any extension like "(V.O.)", and
    # the names are also replaced where they're mentioned in other
    # elements, matching the case they were written in. all renames are
    # done in one pass, so names can be swapped. returns a (cues,
    # mentions) tuple of how many of each were renamed.
    def renameCharacters(self, renames):
        normalize = characterprofiles.normalizeName

        renames = {k: v for k, v in renames.items() if k and v and (k != v)}
        if not renames:
            return (0, 0)

        # the names of the other characters are matched too, but left as
        # they are, so that renaming MARY doesn't touch "Mary" in mentions
        # of MARY JANE. longest names first, so that "MARY JANE" wins over
        # "MARY".
        names = {normalize(n): None for n in self.getCharacterNames()}
        names.update(renames)
        names.pop("", None)

        pattern = re.compile(
            "|".join(
                r"(?<!\w)%s(?!\w)" % r"\s+".join(re.escape(w) for w in name.split())
                for name in sorted(names, key=len, reverse=True)
            ),
            re.IGNORECASE,
        )

        # how many mentions the current line had renamed
        lineMentions = 0

        def replaceMention(mo):
            nonlocal lineMentions

            found = mo.group(0)
            new = names[normalize(found)]

            if not new:
                return found

            lineMentions += 1

            if found.isupper():
                return new
            elif found.islower():
                return util.lower(new)
            else:
                # capitalize each word, e.g. "MARY-ANNE O'NEIL" ->
                # "Mary-Anne O'Neil"
                return re.sub(
                    r"[^\W\d_]+",
                    lambda m: util.upper(m.group(0)[:1]) + util.lower(m.group(0)[1:]),
                    new,
                )

        cues = 0
        mentions = 0

        # (line, new text) for every changed line
        changes = []

        for i, ln in enumerate(self.lines):
            if ln.lt == CHARACTER:
                new = renames.get(normalize(ln.text)) if ln.lb == LB_LAST else None

                if new:
                    idx = ln.text.find("(")
                    ext = (" " + ln.text[idx:].strip()) if idx != -1 else ""

                    changes.append((i, new + ext))
                    cues += 1

            else:
                lineMentions = 0
                text = pattern.sub(replaceMention, ln.text)

                if lineMentions:
                    changes.append((i, text))
                    mentions += lineMentions

        if not changes:
            return (cues, mentions)

        self.clearAutoComp()

        u = undo.FullCopy(self)

        for i, text in changes:
            self.lines[i].text = text

        # rewrap changed paragraphs from the bottom up, so that the line
        # numbers of the ones still to do stay valid
        paras = {self.getParaFirstIndexFromLine(i) for i, _text in changes}

        for line in sorted(paras, reverse=True):
            self.rewrapPara(line)

        acType = self.autoCompletion.getType(CHARACTER)
        acType.items = list(
            dict.fromkeys(renames.get(normalize(it), it) for it in acType.items)
        )

        self.validatePos()
        self.clearMark()
        self.markChanged()

        u.setAfter(self)
        self.addUndo(u)

        return (cues, mentions)

    # set mark at given position
    def setMark(self, line, column):
        self.mark = Mark(line, column)

    # clear mark
    def clearMark(self):
        self.mark = None

    # if doIt is True and mark is not yet set, set it at current position.
    def maybeMark(self, doIt):
        if doIt and not self.mark:
            self.setMark(self.line, self.column)

    # make sure current line and column are within the valid bounds.
    def validatePos(self):
        self.line = util.clamp(self.line, 0, len(self.lines) - 1)
        self.column = util.clamp(self.column, 0, len(self.lines[self.line].text))

    # this must be called after each command (all functions named fooCmd
    # are commands)
    def cmdPost(self, cs):
        # TODO: is this needed?
        self.column = min(self.column, len(self.lines[self.line].text))

        if cs.doAutoComp == cs.AC_DEL:
            self.clearAutoComp()
        elif cs.doAutoComp == cs.AC_REDO:
            self.fillAutoComp()

    # helper function for calling commands. name is the name of the
    # command, e.g. "moveLeft".
    def cmd(self, name, char=None, count=1):
        for i in range(count):
            cs = CommandState()

            if char:
                cs.char = char

            getattr(self, name + "Cmd")(cs)
            self.cmdPost(cs)

    # call addCharCmd for each character in s. ONLY MEANT TO BE USED IN
    # TEST CODE.
    def cmdChars(self, s):
        for char in s:
            self.cmd("addChar", char=char)

    def moveLeftCmd(self, cs):
        self.maybeMark(cs.mark)

        if self.column > 0:
            self.column -= 1
        else:
            if self.line > 0:
                self.line -= 1
                self.column = len(self.lines[self.line].text)

    def moveRightCmd(self, cs):
        self.maybeMark(cs.mark)

        if self.column != len(self.lines[self.line].text):
            self.column += 1
        else:
            if self.line < (len(self.lines) - 1):
                self.line += 1
                self.column = 0

    def moveUpCmd(self, cs):
        if not self.acItems:
            self.maybeMark(cs.mark)

            if self.line > 0:
                self.line -= 1

        else:
            self.acSel -= 1

            if self.acSel < 0:
                self.acSel = len(self.acItems) - 1

            cs.doAutoComp = cs.AC_KEEP

    def moveDownCmd(self, cs):
        if not self.acItems:
            self.maybeMark(cs.mark)

            if self.line < (len(self.lines) - 1):
                self.line += 1

        else:
            self.acSel = (self.acSel + 1) % len(self.acItems)

            cs.doAutoComp = cs.AC_KEEP

    def moveNextWordCmd(self, cs):
        if not self.acItems:
            l = self.line
            i = self.column
            t = self.lines[l].text
            firstReadFlag = False
            while True:
                if t == "":  # empty line
                    self.line += 1
                    return

                if i + 1 == len(self.lines[l].text):  # end of line
                    if firstReadFlag == False:  # event started at the end of the line
                        if l + 1 == len(self.lines):
                            return
                        l += 1
                        i = 0
                        t = self.lines[l].text

                    self.column = i
                    self.line = l
                    return

                if (
                    t[i + 1].isspace() and firstReadFlag
                ):  # shifting the cursor to the end of the word
                    self.column = i
                    return
                else:
                    i += 1
                if firstReadFlag == False:
                    firstReadFlag = True

    def movePrevWordCmd(self, cs):
        # returns a reverse list of indexes of words in string s.
        def getWordIndex(s):
            l = []
            if s and not s[0].isspace():
                l.append(0)
            for i in range(1, len(s)):
                if s[i - 1].isspace() and i == len(s):
                    l.append(i)
                if not s[i].isspace() and s[i - 1].isspace():
                    l.append(i)

            l.reverse()
            return l

        if not self.acItems:
            l = self.line
            i = self.column

            words = getWordIndex(self.lines[l].text)
            while True:
                for word in words:
                    if word < i:
                        self.column = word
                        self.line = l
                        return
                l = l - 1
                if l == -1:
                    self.line = 0
                    self.column = 0
                    return
                words = getWordIndex(self.lines[l].text)
                if words:
                    i = words[0] + 1

    def moveLineEndCmd(self, cs):
        if self.acItems:
            self.lines[self.line].text = self.acItems[self.acSel]
        else:
            self.maybeMark(cs.mark)

        self.column = len(self.lines[self.line].text)

    def moveLineStartCmd(self, cs):
        self.maybeMark(cs.mark)

        self.column = 0

    def moveStartCmd(self, cs):
        self.maybeMark(cs.mark)

        self.line = 0
        self.setTopLine(0)
        self.column = 0

    def moveEndCmd(self, cs):
        self.maybeMark(cs.mark)

        self.line = len(self.lines) - 1
        self.column = len(self.lines[self.line].text)

    def moveSceneUpCmd(self, cs):
        self.maybeMark(cs.mark)

        tmpUp = self.getSceneIndexes()[0]

        if self.line != tmpUp:
            self.line = tmpUp
        else:
            tmpUp -= 1
            if tmpUp >= 0:
                self.line = self.getSceneIndexesFromLine(tmpUp)[0]

        self.column = 0

    def moveSceneDownCmd(self, cs):
        self.maybeMark(cs.mark)

        tmpBottom = self.getSceneIndexes()[1]
        self.line = min(len(self.lines) - 1, tmpBottom + 1)
        self.column = 0

    def deleteBackwardCmd(self, cs):
        u = None
        mergeUndo = False
        wrapCnt = 0

        # only merge with the previous item in undo history if:
        #   -we are not in middle of undo/redo
        #   -previous item is "delete backward"
        #   -cursor is exactly where it was left off by the previous item
        if (
            not self.currentUndo
            and self.lastUndo
            and (self.lastUndo.getType() == undo.CMD_DEL_BACKWARD)
            and (self.lastUndo.endPos == self.cursorAsMark())
        ):
            u = self.lastUndo
            mergeUndo = True

        if self.column != 0:
            if not mergeUndo:
                u = undo.ManyElems(self, undo.CMD_DEL_BACKWARD, self.line, 1, 1)

            self.deleteChar(self.line, self.column - 1)
            self.markChanged()
            cs.doAutoComp = cs.AC_REDO
        else:
            if self.line != 0:
                ln = self.lines[self.line - 1]

                # delete at start of the line of the first line of the
                # element means "join up with previous element", so is a
                # 2->1 change. otherwise we just delete a character from
                # current element so no element count change. joining
                # elements can make speeches part of a dual dialogue or
                # take them out of one, so the speeches around are
                # rewrapped too, and included in the undo.
                if ln.lb == LB_LAST:
                    wrapFirst, wrapLast = self.getSpeechRangeAround(
                        self.line - 1, self.line
                    )
                    wrapCnt = self.elemsDistance(wrapFirst, wrapLast) + 1

                    u = undo.ManyElems(
                        self, undo.CMD_MISC, wrapFirst, wrapCnt, wrapCnt - 1
                    )
                    mergeUndo = False
                else:
                    if not mergeUndo:
                        u = undo.ManyElems(self, undo.CMD_DEL_BACKWARD, self.line, 1, 1)

                if ln.lb == LB_NONE:
                    self.deleteChar(self.line - 1, len(ln.text) - 1, False)

                self.joinLines(self.line - 1)

                self.markChanged()

        self.rewrapElem()

        if wrapCnt:
            self.rewrapElems(wrapFirst, wrapCnt - 1)

        if u:
            if mergeUndo:
                self.addMergedUndo(u)
            else:
                u.setAfter(self)
                self.addUndo(u)

    def deleteForwardCmd(self, cs):
        u = None
        mergeUndo = False
        wrapCnt = 0

        # only merge with the previous item in undo history if:
        #   -we are not in middle of undo/redo
        #   -previous item is "delete forward"
        #   -cursor is exactly where it was left off by the previous item
        if (
            not self.currentUndo
            and self.lastUndo
            and (self.lastUndo.getType() == undo.CMD_DEL_FORWARD)
            and (self.lastUndo.endPos == self.cursorAsMark())
        ):
            u = self.lastUndo
            mergeUndo = True

        if self.column != len(self.lines[self.line].text):
            if not mergeUndo:
                u = undo.ManyElems(self, undo.CMD_DEL_FORWARD, self.line, 1, 1)

            self.deleteChar(self.line, self.column)
            self.markChanged()
            cs.doAutoComp = cs.AC_REDO
        else:
            if self.line != (len(self.lines) - 1):
                ln = self.lines[self.line]

                # delete at end of the line of the last line of the
                # element means "join up with next element", so is a 2->1
                # change. otherwise we just delete a character from
                # current element so no element count change. as in
                # deleteBackwardCmd, the speeches around are rewrapped.
                if ln.lb == LB_LAST:
                    wrapFirst, wrapLast = self.getSpeechRangeAround(
                        self.line, self.line + 1
                    )
                    wrapCnt = self.elemsDistance(wrapFirst, wrapLast) + 1

                    u = undo.ManyElems(
                        self, undo.CMD_MISC, wrapFirst, wrapCnt, wrapCnt - 1
                    )
                    mergeUndo = False
                else:
                    if not mergeUndo:
                        u = undo.ManyElems(self, undo.CMD_DEL_FORWARD, self.line, 1, 1)

                if ln.lb == LB_NONE:
                    self.deleteChar(self.line + 1, 0, False)

                self.joinLines(self.line)

                self.markChanged()

        self.rewrapElem()

        if wrapCnt:
            self.rewrapElems(wrapFirst, wrapCnt - 1)

        if u:
            if mergeUndo:
                self.addMergedUndo(u)
            else:
                u.setAfter(self)
                self.addUndo(u)

    # aborts stuff, like selection, auto-completion, etc
    def abortCmd(self, cs):
        self.clearMark()

    # select all text of current scene
    def selectSceneCmd(self, cs):
        l1, l2 = self.getSceneIndexes()

        self.setMark(l1, 0)

        self.line = l2
        self.column = len(self.lines[l2].text)

    # select all text of the screenplay. sets mark at beginning and moves
    # cursor to the end.
    def selectAllCmd(self, cs):
        self.setMark(0, 0)

        self.line = len(self.lines) - 1
        self.column = len(self.lines[self.line].text)

    # select the word at (line, col), as on a double click. clicking on
    # whitespace or punctuation selects the run of it instead. selections
    # are inclusive, so the cursor ends up on the word's last character.
    def selectWordAt(self, line, col):
        self.clearAutoComp()

        s = self.lines[line].text

        if not s:
            self.clearMark()
            self.gotoPos(line, 0)

            return

        col = util.clamp(col, 0, len(s) - 1)

        def charClass(ch):
            if not util.isWordBoundary(ch):
                return 0
            elif ch.isspace():
                return 1
            else:
                return 2

        cls = charClass(s[col])
        start = col
        end = col

        while (start > 0) and (charClass(s[start - 1]) == cls):
            start -= 1

        while (end < (len(s) - 1)) and (charClass(s[end + 1]) == cls):
            end += 1

        self.setMark(line, start)
        self.line = line
        self.column = end

    # select the whole element containing line, as on a triple click.
    def selectElementAt(self, line):
        self.clearAutoComp()

        first, last = self.getElemIndexesFromLine(line)

        self.setMark(first, 0)
        self.line = last
        self.column = len(self.lines[last].text)

    def insertForcedLineBreakCmd(self, cs):
        u = undo.ManyElems(self, undo.CMD_MISC, self.line, 1, 1)

        self.splitLine()

        self.rewrapPara()
        self.rewrapPrevPara()

        u.setAfter(self)
        self.addUndo(u)

    def splitElementCmd(self, cs):
        tcfg = self.cfgGl.getType(self.lines[self.line].lt)
        self.splitElement(tcfg.newTypeEnter)

    def setMarkCmd(self, cs):
        self.setMark(self.line, self.column)

    # either creates a new element or converts the current one to
    # nextTypeTab, depending on circumstances.
    def tabCmd(self, cs):
        if self.mark:
            self.clearMark()

            return

        tcfg = self.cfgGl.getType(self.lines[self.line].lt)

        if self.tabMakesNew():
            self.splitElement(tcfg.newTypeTab)
        else:
            self.convertTypeTo(tcfg.nextTypeTab, True)

    # switch current element to prevTypeTab.
    def toPrevTypeTabCmd(self, cs):
        if self.mark:
            self.clearMark()

            return

        tcfg = self.cfgGl.getType(self.lines[self.line].lt)
        self.convertTypeTo(tcfg.prevTypeTab, True)

    # add character cs.char if it's a valid one.
    def addCharCmd(self, cs):
        char = cs.char

        if len(char) != 1:
            return

        kc = ord(char)

        if not util.isValidInputChar(kc):
            return

        isSpace = char == " "

        # only merge with the previous item in undo history if:
        #   -we are not in middle of undo/redo
        #   -previous item is "add character"
        #   -cursor is exactly where it was left off by the previous item
        #
        # in addition, to get word-level undo, not element-level undo, we
        # want to merge all spaces with the word preceding them, but stop
        # merging when a new word begins. this is implemented by the
        # following algorith:
        #
        # lastUndo    char       merge
        # --------    -------    -----
        # non-space   non-space  Y
        # non-space   space      Y      <- change type of lastUndo to space
        # space       space      Y
        # space       non-space  N

        if (
            not self.currentUndo
            and self.lastUndo
            and (
                self.lastUndo.getType() in (undo.CMD_ADD_CHAR, undo.CMD_ADD_CHAR_SPACE)
            )
            and (self.lastUndo.endPos == self.cursorAsMark())
            and not (
                (self.lastUndo.getType() == undo.CMD_ADD_CHAR_SPACE) and not isSpace
            )
        ):

            u = self.lastUndo
            mergeUndo = True

            if isSpace:
                u.cmdType = undo.CMD_ADD_CHAR_SPACE
        else:
            mergeUndo = False

            if isSpace:
                u = undo.SinglePara(self, undo.CMD_ADD_CHAR_SPACE, self.line)
            else:
                u = undo.SinglePara(self, undo.CMD_ADD_CHAR, self.line)

        if self.capitalizeNeeded():
            char = util.upper(char)

        ls = self.lines
        s = ls[self.line].text

        if self.cfgGl.capitalizeI and (self.column > 0):
            s = ls[self.line].text

            if s[self.column - 1] == "i":
                if not util.isAlnum(char):
                    doIt = False

                    if self.column > 1:
                        if not util.isAlnum(s[self.column - 2]):
                            doIt = True
                    else:
                        if (self.line == 0) or (ls[self.line - 1].lb != LB_NONE):
                            doIt = True

                    if doIt:
                        s = util.replace(s, "I", self.column - 1, 1)

        s = s[: self.column] + char + s[self.column :]
        ls[self.line].text = s
        self.column += 1

        tmp = s.upper()
        if (tmp == "EXT.") or (tmp == "INT."):
            if self.isOnlyLineOfElem(self.line):
                ls[self.line].lt = SCENE
        elif (
            (tmp == "(")
            and ls[self.line].lt in (DIALOGUE, CHARACTER)
            and self.isOnlyLineOfElem(self.line)
        ):
            ls[self.line].lt = PAREN
            ls[self.line].text = "()"

        self.rewrapPara()
        self.markChanged()

        cs.doAutoComp = cs.AC_REDO

        if mergeUndo:
            self.addMergedUndo(u)
        else:
            u.setAfter(self)
            self.addUndo(u)

    def toSceneCmd(self, cs):
        self.convertTypeTo(SCENE, True)

    def toActionCmd(self, cs):
        self.convertTypeTo(ACTION, True)

    def toCharacterCmd(self, cs):
        self.convertTypeTo(CHARACTER, True)

    def toDialogueCmd(self, cs):
        self.convertTypeTo(DIALOGUE, True)

    def toParenCmd(self, cs):
        self.convertTypeTo(PAREN, True)

    def toTransitionCmd(self, cs):
        self.convertTypeTo(TRANSITION, True)

    def toShotCmd(self, cs):
        self.convertTypeTo(SHOT, True)

    def toActBreakCmd(self, cs):
        self.convertTypeTo(ACTBREAK, True)

    def toNoteCmd(self, cs):
        self.convertTypeTo(NOTE, True)

    # return True if we can undo
    def canUndo(self):
        return bool(
            # undo history exists
            self.lastUndo
            # and we either:
            and (
                # are not in the middle of undo/redo
                not self.currentUndo
                or
                # or are, but can still undo more
                self.currentUndo.prev
            )
        )

    # return True if we can redo
    def canRedo(self):
        return bool(self.currentUndo)

    def addUndo(self, u):
        if self.currentUndo:
            # new edit action while navigating undo history; throw away
            # any undo history after current point

            if self.currentUndo.prev:
                # not at beginning of undo history; cut off the rest
                self.currentUndo.prev.next = None
                self.lastUndo = self.currentUndo.prev
            else:
                # beginning of undo history; throw everything away
                self.firstUndo = None
                self.lastUndo = None

            self.currentUndo = None

            # we threw away an unknown number of undo items, so we must go
            # through all of the remaining ones and recalculate how much
            # memory is used
            self.undoMemoryUsed = 0

            tmp = self.firstUndo

            while tmp:
                self.undoMemoryUsed += tmp.memoryUsed()
                tmp = tmp.next

        if not self.lastUndo:
            # no undo history at all yet
            self.firstUndo = u
            self.lastUndo = u
        else:
            self.lastUndo.next = u
            u.prev = self.lastUndo
            self.lastUndo = u

        self.undoMemoryUsed += u.memoryUsed()

        # trim undo history until the estimated memory usage is small
        # enough
        while (self.firstUndo is not self.lastUndo) and (
            self.undoMemoryUsed >= 5000000
        ):

            tmp = self.firstUndo
            tmp.next.prev = None
            self.firstUndo = tmp.next

            # it shouldn't be technically necessary to reset this, but it
            # might make the GC's job easier, and helps detecting bugs if
            # somebody somehow tries to access this later on
            tmp.next = None

            self.undoMemoryUsed -= tmp.memoryUsed()

        self.currentUndo = None

    def addMergedUndo(self, u):
        assert u is self.lastUndo

        memoryUsedBefore = u.memoryUsed()
        u.setAfter(self)
        memoryUsedAfter = u.memoryUsed()
        memoryUsedDiff = memoryUsedAfter - memoryUsedBefore

        self.undoMemoryUsed += memoryUsedDiff

    def undoCmd(self, cs):
        if not self.canUndo():
            return

        # the action to undo
        if self.currentUndo:
            u = self.currentUndo.prev
        else:
            u = self.lastUndo

        u.undo(self)
        self.currentUndo = u

        self.clearMark()
        self.markChanged()

    def redoCmd(self, cs):
        if not self.canRedo():
            return

        self.currentUndo.redo(self)
        self.currentUndo = self.currentUndo.next

        self.clearMark()
        self.markChanged()

    # check script for internal consistency. raises an AssertionError on
    # errors. ONLY MEANT TO BE USED IN TEST CODE.
    def _validate(self):
        # type of previous line, or None when a new element starts
        prevType = None

        # there must be at least one line
        assert len(self.lines) > 0

        # cursor position must be valid
        assert self.line >= 0
        assert self.line < len(self.lines)
        assert self.column >= 0
        assert self.column <= len(self.lines[self.line].text)

        for ln in self.lines:
            tcfg = self.cfg.getType(ln.lt)

            # lines should not contain invalid characters
            assert ln.text == util.toInputStr(ln.text)

            # lines shouldn't be longer than the type's maximum width,
            # unless the extra characters are all spaces
            assert len(ln.text.rstrip(" ")) <= tcfg.width

            # lines with LB_NONE linebreaks that end in a space should be
            # LB_SPACE instead
            if ln.lb == LB_NONE:
                assert not ln.text.endswith(" ")

            if prevType:
                assert ln.lt == prevType

            if ln.lb == LB_LAST:
                prevType = None
            else:
                prevType = ln.lt


# used to keep track of selected area. this marks one of the end-points,
# while the other one is the current position.
class Mark:
    def __init__(self, line, column):
        self.line = line
        self.column = column

    def __eq__(self, other):
        return (self.line == other.line) and (self.column == other.column)


# return True if s is a valid scene color: six hex digits, "rrggbb"
def isValidColor(s):
    return re.fullmatch("[0-9a-fA-F]{6}", s) is not None


# data held in internal clipboard.
class ClipData:
    def __init__(self):

        # list of Line objects
        self.lines = []


# one entry (a scene or an act break) in a script's outline. see
# Screenplay.getOutline.
class OutlineItem:
    def __init__(
        self, lt, sceneNr, startLine, endLine, heading, summary, page, color=None
    ):

        # SCENE or ACTBREAK
        self.lt = lt

        # scene number as a string, or "" for act breaks
        self.sceneNr = sceneNr

        # range of lines covered, inclusive
        self.startLine = startLine
        self.endLine = endLine

        # text of the scene heading / act break element
        self.heading = heading

        # text of the first note in the scene, or if there are none, the
        # first action element. "" if neither exists.
        self.summary = summary

        # label of the page the item starts on, e.g. "16" or "15A"
        self.page = page

        # color to show the item with in the outline ("rrggbb"), or None
        self.color = color

    def __eq__(self, other):
        return isinstance(other, OutlineItem) and (self.__dict__ == other.__dict__)


# stuff we need when handling commands in Screenplay.
class CommandState:

    # what to do about auto-completion
    AC_DEL, AC_REDO, AC_KEEP = list(range(3))

    def __init__(self):

        self.doAutoComp = self.AC_DEL

        # only used for inserting characters, in which case this is the
        # character to insert in a string form.
        self.char = None

        # True if this is a movement command and we should set mark at the
        # current position before moving (note that currently this is just
        # set if shift is down)
        self.mark = False

        # True if we need to make current line visible
        self.needsVisifying = True
