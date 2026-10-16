import io
import re
import zipfile
from typing import List, Optional

import wx
from lxml import etree

import trelby.checkboxdlg as checkboxdlg
import trelby.checkboxitem as checkboxitem
import trelby.config as config
import trelby.gutil as gutil
import trelby.screenplay as screenplay
import trelby.textfmt as textfmt
import trelby.textutil as textutil
import trelby.titles as titles
from trelby.importdlg import ImportDlg
from trelby.indent import Indent
from trelby.line import Line

# special linetype that means that indent contains action and scene lines,
# and scene lines are the ones that begin with "EXT." or "INT."
SCENE_ACTION = -2

# special linetype that means don't import those lines; useful for page
# numbers etc
IGNORE = -3


# like importTextFile, but for Adobe Story files.
def importAstx(fileName, frame):
    # astx files are xml files. The textlines can be found under
    # AdobeStory/document/stream/section/scene/paragraph which contain
    # one or more textRun/break elements, to be joined. The paragraph
    # attribute "element" gives us the element style.

    data = gutil.loadFile(fileName, frame, -1)

    if data == None:
        return None

    if len(data) == 0:
        wx.MessageBox(_("File is empty."), _("Error"), wx.OK, frame)

        return None

    elemMap = {
        "Action": screenplay.ACTION,
        "Character": screenplay.CHARACTER,
        "Dialog": screenplay.DIALOGUE,
        "Parenthetical": screenplay.PAREN,
        "SceneHeading": screenplay.SCENE,
        "Shot": screenplay.SHOT,
        "Transition": screenplay.TRANSITION,
    }

    try:
        root = etree.XML(data)
    except etree.XMLSyntaxError as e:
        wx.MessageBox(_("Error parsing file: {}").format(e), _("Error"), wx.OK, frame)
        return None

    lines = []

    def addElem(eleType, items):
        # if elem ends in a newline, last line is empty and useless;
        # get rid of it
        if not items[-1] and (len(items) > 1):
            items = items[:-1]

        for s in items[:-1]:
            lines.append(Line(screenplay.LB_FORCED, eleType, textutil.cleanInput(s)))

        lines.append(Line(screenplay.LB_LAST, eleType, textutil.cleanInput(items[-1])))

    for para in root.xpath("/AdobeStory/document/stream/section/scene/paragraph"):
        lt = elemMap.get(para.get("element"), screenplay.ACTION)

        items = []
        s = ""

        for text in para:
            if text.tag == "textRun" and text.text:
                s += text.text
            elif text.tag == "break":
                items.append(s.rstrip())
                s = ""

        items.append(s.rstrip())

        addElem(lt, items)

    if not lines:
        wx.MessageBox(_("File has no content."), _("Error"), wx.OK, frame)
        return None

    return lines


# like importTextFile, but for fadein files.
def importFadein(fileName, frame):
    # Fadein file is a zipped document.xml file.
    # the .xml is in open screenplay format:
    # http://sourceforge.net/projects/openscrfmt/files/latest/download

    try:
        with zipfile.ZipFile(fileName) as fadein_file:
            with fadein_file.open("document.xml") as fadein_document:
                data = fadein_document.read()
    except:
        wx.MessageBox(_("File is not a valid .fadein file."), _("Error"), wx.OK, frame)
        return None

    if data == None:
        return None

    if len(data) == 0:
        wx.MessageBox(_("File is empty."), _("Error"), wx.OK, frame)
        return None

    elemMap = {
        "Action": screenplay.ACTION,
        "Character": screenplay.CHARACTER,
        "Dialogue": screenplay.DIALOGUE,
        "Parenthetical": screenplay.PAREN,
        "Scene Heading": screenplay.SCENE,
        "Shot": screenplay.SHOT,
        "Transition": screenplay.TRANSITION,
    }

    try:
        root = etree.XML(data)
    except etree.XMLSyntaxError as e:
        wx.MessageBox(_("Error parsing file: {}").format(e), _("Error"), wx.OK, frame)
        return None

    lines = []

    def addElem(eleType, lns):
        # if elem ends in a newline, last line is empty and useless;
        # get rid of it
        if not lns[-1] and (len(lns) > 1):
            lns = lns[:-1]

        for s in lns[:-1]:
            lines.append(Line(screenplay.LB_FORCED, eleType, textutil.cleanInput(s)))

        lines.append(Line(screenplay.LB_LAST, eleType, textutil.cleanInput(lns[-1])))

    # removes html formatting from s, and returns list of lines.
    # if s is None, return a list with single empty string.
    re_rem = [r"<font[^>]*>", r"<size[^>]*>", r"<bgcolor[^>]*>"]
    rem = [
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

    def sanitizeStr(s):
        if s:
            s = "" + s
            for r in re_rem:
                s = re.sub(r, "", s)
            for r in rem:
                s = s.replace(r, "")

            if s:
                return s.split("<br>")
            else:
                return [""]
        else:
            return [""]

    for para in root.xpath("paragraphs/para"):
        # check for notes/synopsis, import as Note.
        if para.get("note"):
            lt = screenplay.NOTE
            items = sanitizeStr("" + para.get("note"))
            addElem(lt, items)

        if para.get("synopsis"):
            lt = screenplay.NOTE
            items = sanitizeStr("" + para.get("synopsis"))
            addElem(lt, items)

        # look for the <style> and <text> tags. Bail if no <text> found.
        styl = para.xpath("style")
        txt = para.xpath("text")
        if txt:
            if styl:
                lt = elemMap.get(styl[0].get("basestylename"), screenplay.ACTION)
            else:
                lt = screenplay.ACTION

            items = sanitizeStr(txt[0].text)

            if (lt == screenplay.PAREN) and items and (items[0][0] != "("):
                items[0] = "(" + items[0]
                items[-1] = items[-1] + ")"
        else:
            continue

        addElem(lt, items)

    if len(lines) == 0:
        wx.MessageBox(
            _("The file contains no importable lines"), _("Error"), wx.OK, frame
        )
        return None

    return lines


# like importTextFile, but for Celtx files.
def importCeltx(fileName, frame):
    # Celtx files are zipfiles, and the script content is within a file
    # called "script-xxx.html", where xxx can be random.
    try:
        z = zipfile.ZipFile(fileName)
    except:
        wx.MessageBox(
            _("File is not a valid Celtx script file."), _("Error"), wx.OK, frame
        )
        return None

    files = z.namelist()
    scripts = [s for s in files if s.startswith("script")]

    if len(scripts) == 0:
        wx.MessageBox(
            _("Unable to find script in this Celtx file."), _("Error"), wx.OK, frame
        )
        return None

    f = z.open(scripts[0])
    content = f.read()
    z.close()

    if not content:
        wx.MessageBox(_("Script seems to be empty."), _("Error"), wx.OK, frame)
        return None

    elemMap = {
        "action": screenplay.ACTION,
        "character": screenplay.CHARACTER,
        "dialog": screenplay.DIALOGUE,
        "parenthetical": screenplay.PAREN,
        "sceneheading": screenplay.SCENE,
        "shot": screenplay.SHOT,
        "transition": screenplay.TRANSITION,
        "act": screenplay.ACTBREAK,
    }

    try:
        parser = etree.HTMLParser()
        root = etree.XML(content, parser)
    except etree.XMLSyntaxError as e:
        wx.MessageBox(_("Error parsing file: {}").format(e), _("Error"), wx.OK, frame)
        return None

    lines = []

    def addElem(eleType, lns):
        # if elem ends in a newline, last line is empty and useless;
        # get rid of it
        if not lns[-1] and (len(lns) > 1):
            lns = lns[:-1]

        for s in lns[:-1]:
            lines.append(Line(screenplay.LB_FORCED, eleType, textutil.cleanInput(s)))

        lines.append(Line(screenplay.LB_LAST, eleType, textutil.cleanInput(lns[-1])))

    for para in root.xpath("/html/body/p"):
        items = []
        for line in para.itertext():
            text = line.replace("\n", " ").strip()
            if text != "":
                items.append(text)

        lt = elemMap.get(para.get("class"), screenplay.ACTION)

        if items:
            addElem(lt, items)

    if len(lines) == 0:
        wx.MessageBox(
            _("The file contains no importable lines"), _("Error"), wx.OK, frame
        )
        return None

    return lines


# like importTextFile, but for Final Draft files.
def importFDX(fileName, frame):
    elemMap = {
        "Action": screenplay.ACTION,
        "Character": screenplay.CHARACTER,
        "Dialogue": screenplay.DIALOGUE,
        "Parenthetical": screenplay.PAREN,
        "Scene Heading": screenplay.SCENE,
        "Shot": screenplay.SHOT,
        "Transition": screenplay.TRANSITION,
    }

    data = gutil.loadFile(fileName, frame, -1)

    if data == None:
        return None

    if len(data) == 0:
        wx.MessageBox(_("File is empty."), _("Error"), wx.OK, frame)

        return None

    # https://github.com/trelby/trelby/issues/61
    data = data.replace("\u2028", "\n")

    try:
        root = etree.XML(data.encode("UTF-8"))
        lines = []

        # fmt is the format string for eleText, or None
        def addElem(eleType, eleText, fmt=None):
            lns = eleText.split("\n")

            # if elem ends in a newline, last line is empty and useless;
            # get rid of it
            if not lns[-1] and (len(lns) > 1):
                lns = lns[:-1]

            # fmt has a character for each one of eleText, newlines
            # included, so each line's part starts one past the previous
            # line's end
            pos = 0

            for i, s in enumerate(lns):
                lb = screenplay.LB_LAST if (i == len(lns) - 1) else screenplay.LB_FORCED
                lineFmt = fmt and fmt[pos : pos + len(s)]
                pos += len(s) + 1

                lines.append(Line(lb, eleType, textutil.cleanInput(s), fmt=lineFmt))

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
                addElem(screenplay.NOTE, s)
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
                # text.text is None for paragraphs with no text, and +=
                # blows up trying to add a string object and None, so
                # guard against that
                if text.text:
                    s += text.text

                    styles = (text.get("Style") or "").split("+")
                    style = 0

                    for name, bit in (
                        ("Bold", textfmt.BOLD),
                        ("Italic", textfmt.ITALIC),
                        ("Underline", textfmt.UNDERLINED),
                    ):
                        if name in styles:
                            style |= bit

                    fmt += textfmt.char(style) * len(text.text)

            # don't remove paragraphs with no text, unless that paragraph
            # contained a scriptnote
            if s or not addedNote:
                lt = elemMap.get(et, screenplay.ACTION)
                firstLine = len(lines)
                addElem(lt, s, textfmt.compact(fmt))

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

        if len(lines) == 0:
            wx.MessageBox(
                _("The file contains no importable lines"), _("Error"), wx.OK, frame
            )
            return None

        return lines

    except etree.XMLSyntaxError as e:
        wx.MessageBox(_("Error parsing file: {}").format(e), _("Error"), wx.OK, frame)
        return None


# import Fountain files.
# http://fountain.io
def importFountain(fileName, frame, titlePages):
    boneyard_re = re.compile("/\\*.*?\\*/", flags=re.DOTALL)

    data = gutil.loadFile(fileName, frame, -1)

    if data == None:
        return None

    if len(data) == 0:
        wx.MessageBox(_("File is empty."), _("Error"), wx.OK, frame)
        return None

    inf = []
    inf.append(checkboxitem.CheckBoxItem(_("Import titles to title page.")))
    inf.append(checkboxitem.CheckBoxItem(_("Import titles as action lines."), selected=False))
    inf.append(
        checkboxitem.CheckBoxItem(_("Import bold, italic and underline markup as formatting."))
    )
    inf.append(checkboxitem.CheckBoxItem(_("Import section/synopsis as notes.")))

    dlg = checkboxdlg.CheckBoxDlg(
        frame, _("Fountain import options"), inf, _("Import options:"), False
    )

    if dlg.ShowModal() != wx.ID_OK:
        dlg.Destroy()
        return None, titlePages

    importTitlePage = inf[0].selected
    importTitles = inf[1].selected
    convertMarkup = inf[2].selected
    importSectSyn = inf[3].selected

    # pre-process data - fix newlines, remove boneyard.
    data = textutil.fixNL(data)
    data = boneyard_re.sub("", data)
    prelines = [textutil.cleanInput(l) for l in data.split("\n")]
    lines = []

    tabWidth = 4
    lns = []

    # in Fountain, a line of just two spaces is a blank line that doesn't
    # end the element. two trailing spaces are also used here as a marker
    # on title page lines that go into the script, which keeps the first
    # pass from taking them for scene headings or character names.
    TWOSPACE = "  "
    skipone = False

    # First check if title lines are present:
    c = 0
    while c < len(prelines):
        if prelines[c] != "":
            c = c + 1
        else:
            break

    # prelines[0:c] are the first bunch of lines, that could be titles,
    # and prelines[c] is the blank line after them (prelines[c + 1:] is
    # the script proper). if the title lines run to the end of the file,
    # c == len(prelines).
    # Our check for title is simple:
    #   - the line does not start with 'fade'
    #   - the first line has a single ':'

    if c > 0:
        l = textutil.toInputStr(prelines[0].expandtabs(tabWidth).lstrip().lower())
        if not l.startswith("fade") and l.count(":") == 1:
            # these are title lines. Now do what the user requested.
            if importTitlePage:
                # Extract usable title page lines
                kwPattern = re.compile(r"^([A-Za-z][^:]+:)")
                continuePattern = re.compile(
                    r"^\s\s\s+"
                )  # line begins with 3 or more spaces
                titleIdx = 0
                gatheredTitles = []
                rejects = []
                while titleIdx < c:
                    l = prelines[titleIdx]
                    match = kwPattern.split(l)
                    match = [ll.strip() for ll in match]
                    if len(match) == 3:  # keyword line
                        if match[2] == "":
                            follows = []
                            titleIdx += 1  # gather indented prelines
                            while titleIdx < c and continuePattern.match(
                                prelines[titleIdx]
                            ):
                                follows.append(prelines[titleIdx].strip("_* \t"))
                                titleIdx += 1
                            titleIdx -= 1
                            gatheredTitles.append([match[1], follows])
                        else:
                            gatheredTitles.append([match[1], [match[2].strip("_* \t")]])
                    else:
                        l += TWOSPACE
                        rejects.append(l)
                    titleIdx += 1
                # replace default titles with imported ones. Title, Author
                # and Contact overwrite strings 0 - 2 of titlePages[0]
                # (changed in place), assuming the order of the default
                # title page made by Titles.addDefaults.
                # other keys become new strings: Credit / Source centered,
                # going down the page from y = 150 (mm from the top), the
                # rest at the left, going up from y = 220.
                leftX = 15.0
                leftY = 220.0
                centreX = 0.0
                centreY = 150.0
                for t in gatheredTitles:
                    titlenr = -1
                    if t[0] == "Title:":
                        titlenr = 0
                    elif t[0] == "Author:" or t[0] == "Authors:":
                        titlenr = 1
                        t[1] = ["by", ""] + t[1]
                    elif t[0] == "Contact:":
                        titlenr = 2
                    else:
                        titlenr = len(titlePages[0])
                        if t[0] == "Credit:" or t[0] == "Source:":
                            centred = True
                            thisX = centreX
                            thisY = centreY
                            centreY += 5
                        else:
                            centred = False
                            thisX = leftX
                            thisY = leftY
                            leftY -= 5
                        if len(t[1]) == 1:
                            newItems = [t[0] + " " + t[1][0]]
                        else:
                            newItems = [t[0]] + t[1]
                        newTitleString = titles.TitleString(
                            newItems, y=thisY, isCentered=centred
                        )
                        titlePages[0].append(newTitleString)
                        continue
                    targetTitle = titlePages[0][titlenr]
                    targetTitle.items = t[1]
                # user might request that titles go into both title page & script
                if not importTitles:
                    rejects += prelines[c + 1 :]
                    prelines = rejects
            if importTitles:
                # add TWOSPACE to all the title lines.
                for i in range(c):
                    prelines[i] += TWOSPACE
            elif not importTitlePage:
                # remove these lines
                prelines = prelines[c + 1 :]

    for l in prelines:
        if l != TWOSPACE:
            lines.append(textutil.toInputStr(l.expandtabs(tabWidth)))
        else:
            lines.append(TWOSPACE)

    linesLen = len(lines)

    def isPrevEmpty():
        if lns and lns[-1].text == "":
            return True
        return False

    def isPrevType(ltype):
        return lns and lns[-1].lt == ltype

    # looks ahead to check if next line exists and is empty
    def isNextEmpty(i):
        return i + 1 < len(lines) and lines[i + 1] == ""

    def getPrevType():
        if lns:
            return lns[-1].lt
        else:
            return screenplay.ACTION

    def isParen(s):
        return s.startswith("(") and s.endswith(")")

    def isScene(s):
        if s.endswith(TWOSPACE):
            return False
        if s.startswith(".") and not s.startswith(".."):
            return True
        tmp = s.upper()
        if (
            re.match(r"^(INT|EXT|EST)[ .]", tmp)
            or re.match(r"^(INT\.?/EXT\.?)[ .]", tmp)
            or re.match(r"^I/E[ .]", tmp)
        ):
            return True
        return False

    def isTransition(s):
        return (s.isupper() and s.endswith("TO:")) or (
            s.startswith(">") and not s.endswith("<")
        )

    def isCentered(s):
        return s.startswith(">") and s.endswith("<")

    def isPageBreak(s):
        return s.startswith("===") and s.lstrip("=") == ""

    def isNote(s):
        return s.startswith("[[") and s.endswith("]]")

    def isSection(s):
        return s.startswith("#")

    def isSynopsis(s):
        return s.startswith("=") and not s.startswith("==")

    # first pass - identify linetypes. each source line (but skipped
    # sections / synopses) becomes a Line of its own with LB_FORCED, blank
    # lines included (as empty actions); the
    # second pass groups them into elements. the checks rely on Fountain's
    # blank-line rules, e.g. a character name has a blank line before it
    # and none after it, and a transition has blank lines on both sides.
    for i in range(linesLen):
        if skipone:
            skipone = False
            continue

        s = lines[i]
        sl = s.lstrip()
        # mark as ACTION by default.
        line = Line(screenplay.LB_FORCED, screenplay.ACTION, s)

        # Start testing lines for element type. Go in order:
        # Scene Character, Paren, Dialog, Transition, Note.

        if s == "" or isPageBreak(s):
            # do nothing - import as action.
            pass

        elif isCentered(s.strip()):
            # an action, but centered. for now every centered line has the
            # flag, so that the second pass can tell where they start and
            # end.
            line.centered = True
            line.text = s.strip()[1:-1].strip()

        elif s == TWOSPACE:
            line.lt = getPrevType()

        elif isScene(s):
            line.lt = screenplay.SCENE
            if sl.startswith("."):
                line.text = sl[1:]
            else:
                line.text = sl

        elif isTransition(sl) and isPrevEmpty() and isNextEmpty(i):
            line.lt = screenplay.TRANSITION
            if line.text.startswith(">"):
                line.text = sl[1:].lstrip()

        elif s.isupper() and isPrevEmpty() and not isNextEmpty(i):
            line.lt = screenplay.CHARACTER
            if s.endswith(TWOSPACE):
                line.lt = screenplay.ACTION

        elif isParen(sl) and (
            isPrevType(screenplay.CHARACTER) or isPrevType(screenplay.DIALOGUE)
        ):
            line.lt = screenplay.PAREN

        elif (
            isPrevType(screenplay.CHARACTER)
            or isPrevType(screenplay.DIALOGUE)
            or isPrevType(screenplay.PAREN)
        ):
            line.lt = screenplay.DIALOGUE

        elif isNote(sl):
            line.lt = screenplay.NOTE
            line.text = sl.strip("[]")

        elif isSection(s) or isSynopsis(s):
            if not importSectSyn:
                if isNextEmpty(i):
                    skipone = True
                continue

            line.lt = screenplay.NOTE
            line.text = sl.lstrip("=#")

        if line.text == TWOSPACE:
            pass

        elif line.lt != screenplay.ACTION:
            line.text = line.text.lstrip()

        else:
            line.text = line.text.rstrip()

        if convertMarkup:
            line.text, line.fmt = textfmt.fromMarkup(line.text)

        # "^" after a character name makes it the right-hand column of a
        # dual dialogue
        if line.lt == screenplay.CHARACTER and line.text.rstrip().endswith("^"):
            line.setText(line.text.rstrip()[:-1].rstrip(), line.fmt)
            line.dual = True

        lns.append(line)

    ret = []

    # second pass helper functions.
    def isLastLBForced():
        return ret and ret[-1].lb == screenplay.LB_FORCED

    def makeLastLBLast():
        if ret:
            ret[-1].lb = screenplay.LB_LAST

    def isRetPrevType(t):
        return ret and ret[-1].lt == t

    # second pass - remove unneeded empty lines, and fix the linebreaks.
    # consecutive lines of the same type (and centering) stay one element,
    # and a change of type ends it. a blank line ends the open element
    # and is dropped, or if none is open (e.g. right after another blank
    # line), it's kept as an empty line, which the next blank line ends.
    # so runs of blank lines still leave some space.
    for ln in lns:
        if ln.text == "":
            if isLastLBForced():
                makeLastLBLast()
            else:
                ret.append(ln)

        elif not isRetPrevType(ln.lt) or (ret[-1].centered != ln.centered):
            makeLastLBLast()
            ret.append(ln)

        else:
            ret.append(ln)

    makeLastLBLast()

    # the centered flag only goes on the first line of an element
    for i in range(1, len(ret)):
        if ret[i - 1].lb != screenplay.LB_LAST:
            ret[i].centered = False

    return ret, titlePages


# import text file from fileName, return list of Line objects for the
# screenplay or None if something went wrong. returned list always
# contains at least one line.
def importTextFile(fileName: str, frame: wx.Frame) -> Optional[List[Line]]:

    data = gutil.loadFile(fileName, frame, -1)

    if data == None:
        return None

    if len(data) == 0:
        wx.MessageBox(_("File is empty."), _("Error"), wx.OK, frame)

        return None

    data = textutil.fixNL(data)
    lines = data.split("\n")

    tabWidth = 4

    # key = indent level, value = Indent
    indDict = {}

    for i in range(len(lines)):
        s = textutil.toInputStr(lines[i].rstrip().expandtabs(tabWidth))

        # don't count empty lines towards indentation statistics
        if s.strip() == "":
            lines[i] = ""

            continue

        cnt = textutil.countInitial(s, " ")

        ind = indDict.get(cnt)
        if not ind:
            ind = Indent(cnt)
            indDict[cnt] = ind

        tmp = s.upper()

        if textutil.multiFind(tmp, ["EXT.", "INT."]):
            ind.sceneStart += 1

        if textutil.multiFind(tmp, ["CUT TO:", "DISSOLVE TO:"]):
            ind.trans += 1

        if re.match(r"^ +\(.*\)$", tmp):
            ind.paren += 1

        ind.lines.append(s.lstrip())
        lines[i] = s

    if len(indDict) == 0:
        wx.MessageBox(_("File contains only empty lines."), _("Error"), wx.OK, frame)

        return None

    # guess each indent level's type. the order matters: each setType only
    # looks at the levels not assigned yet, so e.g. dialogue is the
    # most-used level once scene/action has been taken. the user can fix
    # the guesses in the ImportDlg below.

    # scene/action indent
    setType(SCENE_ACTION, indDict, lambda v: v.sceneStart)

    # indent with most lines is dialogue in non-pure-action scripts
    setType(screenplay.DIALOGUE, indDict, lambda v: len(v.lines))

    # remaining indent with lines is character most likely
    setType(screenplay.CHARACTER, indDict, lambda v: len(v.lines))

    # transitions
    setType(screenplay.TRANSITION, indDict, lambda v: v.trans)

    # parentheticals
    setType(screenplay.PAREN, indDict, lambda v: v.paren)

    # some text files have this type of parens:
    #
    #        JOE
    #      (smiling and
    #       hopping along)
    #
    # this handles them.
    parenIndent = findIndent(indDict, lambda v: v.lt == screenplay.PAREN)
    if parenIndent != -1:
        paren2Indent = findIndent(
            indDict, lambda v, var: (v.lt == -1) and (v.indent == var), parenIndent + 1
        )

        if paren2Indent != -1:
            indDict[paren2Indent].lt = screenplay.PAREN

    # set line type to ACTION for any indents not recognized
    for v in indDict.values():
        if v.lt == -1:
            v.lt = screenplay.ACTION

    dlg = ImportDlg(frame, list(indDict.values()), SCENE_ACTION, IGNORE)

    if dlg.ShowModal() != wx.ID_OK:
        dlg.Destroy()

        return None

    dlg.Destroy()

    ret = []

    # consecutive lines of the same type are taken to be one paragraph
    # wrapped in the source, so they're joined with LB_SPACE (rewrapped
    # later by reformatAll). a blank line or a change of type ends the
    # element.
    for i in range(len(lines)):
        s = lines[i]
        cnt = textutil.countInitial(s, " ")
        s = s.lstrip()
        sUp = s.upper()

        if s:
            lt = indDict[cnt].lt

            if lt == IGNORE:
                continue

            if lt == SCENE_ACTION:
                if s.startswith("EXT.") or s.startswith("INT."):
                    lt = screenplay.SCENE
                else:
                    lt = screenplay.ACTION

            if ret and (ret[-1].lt != lt):
                ret[-1].lb = screenplay.LB_LAST

            if lt == screenplay.CHARACTER:
                if sUp.endswith("(CONT'D)"):
                    s = sUp[:-8].rstrip()

            elif lt == screenplay.PAREN:
                if s == "(continuing)":
                    s = ""

            if s:
                line = Line(screenplay.LB_SPACE, lt, s)
                ret.append(line)

        elif ret:
            ret[-1].lb = screenplay.LB_LAST

    if len(ret) == 0:
        ret.append(Line(screenplay.LB_LAST, screenplay.ACTION))

    # make sure the last line ends an element
    ret[-1].lb = screenplay.LB_LAST

    return ret


# go through indents, find the one with maximum value in something, and
# set its linetype to given lt.
def setType(lt, indDict, func):
    maxCount = 0
    found = -1

    for v in indDict.values():
        # don't touch indents already set
        if v.lt != -1:
            continue

        val = func(v)

        if val > maxCount:
            maxCount = val
            found = v.indent

    if found != -1:
        indDict[found].lt = lt


# go through indents calling func(it, *vars) on each. return indent count
# for the indent func returns True, or -1 if it returns False for each.
def findIndent(indDict, func, *vars):
    for v in indDict.values():
        if func(v, *vars):
            return v.indent

    return -1
