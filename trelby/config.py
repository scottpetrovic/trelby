# see fileformat.txt for more detailed information about the various
# defines found here.

import os

import trelby.commands as commands
import trelby.misc as misc
import trelby.mypickle as mypickle
import trelby.pdf.fontinfo as fontinfo
import trelby.pdf.pml as pml
import trelby.screenplay as screenplay
import trelby.textutil as textutil
import trelby.ui.themes as themes
import trelby.util as util
from trelby.error import ConfigError

# mapping from character to linebreak. in a saved script (and in
# line.Line's string form) every line starts with two characters, this one
# for how the line ends and then its element type's TypeInfo.char, followed
# by the text. both are part of the file format, so don't change them.
_char2lb = {
    ">": screenplay.LB_SPACE,
    "+": screenplay.LB_SPACE2,
    "&": screenplay.LB_NONE,
    "|": screenplay.LB_FORCED,
    ".": screenplay.LB_LAST,
}

# reverse to above
_lb2char = {}

# what string each linebreak type should be mapped to.
_lb2str = {
    screenplay.LB_SPACE: " ",
    screenplay.LB_SPACE2: "  ",
    screenplay.LB_NONE: "",
    screenplay.LB_FORCED: "\n",
    screenplay.LB_LAST: "\n",
}

# contains a TypeInfo for each element type
_ti = []

# mapping from character to TypeInfo
_char2ti = {}

# mapping from line type to TypeInfo
_lt2ti = {}

# mapping from element name to TypeInfo
_name2ti = {}

# page break indicators. do not change these values as they're saved to
# the config file.
PBI_NONE = 0
PBI_REAL = 1
PBI_REAL_AND_UNADJ = 2

# for range checking above value
PBI_FIRST, PBI_LAST = PBI_NONE, PBI_REAL_AND_UNADJ

# standard paper sizes, (width, height) in mm, by name
PAPER_SIZES = {
    "A4": (210.0, 297.0),
    "Letter": (215.9, 279.4),
}

# the name of the "System default" theme setting, which uses themes.LIGHT or
# themes.DARK following the operating system
THEME_SYSTEM = ""

# the theme names saved as Appearance:N by older versions, indexed by N
_oldAppearances = [
    THEME_SYSTEM,
    "Light",
    "Dark",
    "Parchment",
    "Solarized Light",
    "Solarized Dark",
    "Monokai",
    "Dracula",
    "Nord",
]


# the folder custom theme files are read from
def themesDir():
    return os.path.join(misc.confPath, "themes")


# (re)load the custom themes from themesDir. returns a list of error
# messages for the files that were skipped.
def loadCustomThemes():
    return themes.loadCustom(themesDir())


# the themes.Theme the given theme setting names, or None for the system
# default. a theme that doesn't exist (e.g. a custom theme whose file has
# been removed) also gives the system default, while the setting keeps the
# name in case the theme comes back.
def findTheme(name):
    if name == THEME_SYSTEM:
        return None

    return themes.find(name)


# constants for identifying PDFFontInfos
PDF_FONT_NORMAL = "Normal"
PDF_FONT_BOLD = "Bold"
PDF_FONT_ITALIC = "Italic"
PDF_FONT_BOLD_ITALIC = "Bold-Italic"


# construct reverse lookup tables

for k, v in list(_char2lb.items()):
    _lb2char[v] = k

del k, v


# non-changing information about an element type
class TypeInfo:
    def __init__(self, lt, char, name):

        # line type, e.g. screenplay.ACTION
        self.lt = lt

        # character used in saved scripts, e.g. "."
        self.char = char

        # textual name, e.g. "Action"
        self.name = name


# text type
#
# like the other config classes here, this keeps its mypickle.Vars in the
# class attribute cvars, built by the first instance rather than at import
# time: the variables' defaults can depend on things set up at startup
# (ConfigGlobal's scriptDir default reads misc.progPath, which misc.init
# sets).
class TextType:
    cvars = None

    def __init__(self):
        if not self.__class__.cvars:
            v = self.__class__.cvars = mypickle.Vars()

            v.addBool("isCaps", False, "AllCaps")
            v.addBool("isBold", False, "Bold")
            v.addBool("isItalic", False, "Italic")
            v.addBool("isUnderlined", False, "Underlined")

        self.__class__.cvars.setDefaults(self)

    def save(self, prefix):
        return self.cvars.save(prefix, self)

    def load(self, vals, prefix):
        self.cvars.load(vals, prefix, self)


# script-specific information about an element type
class Type:
    cvars = None

    def __init__(self, lt):

        # line type
        self.lt = lt

        # pointer to TypeInfo
        self.ti = lt2ti(lt)

        # text types, one for screen and one for export
        self.screen = TextType()
        self.export = TextType()

        if not self.__class__.cvars:
            v = self.__class__.cvars = mypickle.Vars()

            # these two are how much empty space to insert a) before the
            # element b) between the element's lines, in units of line /
            # 10.
            v.addInt("beforeSpacing", 0, "BeforeSpacing", 0, 50)
            v.addInt("intraSpacing", 0, "IntraSpacing", 0, 20)

            v.addInt("indent", 0, "Indent", 0, 80)
            v.addInt("width", 5, "Width", 5, 80)

            v.makeDicts()

        self.__class__.cvars.setDefaults(self)

    def save(self, prefix):
        prefix += "%s/" % self.ti.name

        s = self.cvars.save(prefix, self)
        s += self.screen.save(prefix + "Screen/")
        s += self.export.save(prefix + "Export/")

        return s

    def load(self, vals, prefix):
        prefix += "%s/" % self.ti.name

        self.cvars.load(vals, prefix, self)
        self.screen.load(vals, prefix + "Screen/")
        self.export.load(vals, prefix + "Export/")


# global information about an element type
class TypeGlobal:
    cvars = None

    def __init__(self, lt):

        # line type
        self.lt = lt

        # pointer to TypeInfo
        self.ti = lt2ti(lt)

        if not self.__class__.cvars:
            v = self.__class__.cvars = mypickle.Vars()

            # what type of element to insert when user presses enter or tab.
            v.addElemName("newTypeEnter", screenplay.ACTION, "NewTypeEnter")
            v.addElemName("newTypeTab", screenplay.ACTION, "NewTypeTab")

            # what element to switch to when user hits tab / shift-tab.
            v.addElemName("nextTypeTab", screenplay.ACTION, "NextTypeTab")
            v.addElemName("prevTypeTab", screenplay.ACTION, "PrevTypeTab")

            v.makeDicts()

        self.__class__.cvars.setDefaults(self)

    def save(self, prefix):
        prefix += "%s/" % self.ti.name

        return self.cvars.save(prefix, self)

    def load(self, vals, prefix):
        prefix += "%s/" % self.ti.name

        self.cvars.load(vals, prefix, self)


# information about one PDF font
class PDFFontInfo:
    cvars = None

    # list of characters not allowed in pdfNames
    invalidChars = None

    def __init__(self, name, style):
        # our name for the font (one of the PDF_FONT_* constants)
        self.name = name

        # 2 lowest bits of pml.TextOp.flags
        self.style = style

        if not self.__class__.cvars:
            v = self.__class__.cvars = mypickle.Vars()

            # name to use in generated PDF file (CourierNew, MyFontBold,
            # etc.). if empty, use the default PDF Courier font.
            v.addStrLatin1("pdfName", "", "Name")

            # filename for the font to embed, or empty meaning don't
            # embed.
            v.addStrUnicode("filename", "", "Filename")

            v.makeDicts()

            tmp = ""

            for i in range(256):
                # the OpenType font specification 1.4, of all places,
                # contains the most detailed discussion of characters
                # allowed in Postscript font names, in the section on
                # 'name' tables, describing name ID 6 (=Postscript name).
                if (
                    (i <= 32)
                    or (i >= 127)
                    or chr(i) in ("[", "]", "(", ")", "{", "}", "<", ">", "/", "%")
                ):
                    tmp += chr(i)

            self.__class__.invalidChars = tmp

        self.__class__.cvars.setDefaults(self)

    def save(self, prefix):
        prefix += "%s/" % self.name

        return self.cvars.save(prefix, self)

    def load(self, vals, prefix):
        prefix += "%s/" % self.name

        self.cvars.load(vals, prefix, self)

    # fix up invalid values.
    def refresh(self):
        self.pdfName = textutil.deleteChars(self.pdfName, self.invalidChars)

        # to avoid confused users not understanding why their embedded
        # font isn't working, put in an arbitrary font name if needed
        if self.filename and not self.pdfName:
            self.pdfName = "SampleFontName"


# per-script config, each script has its own one of these.
class Config:
    cvars = None

    def __init__(self):

        if not self.__class__.cvars:
            self.setupVars()

        self.__class__.cvars.setDefaults(self)

        # type configs, key = line type, value = Type
        self.types = {}

        # element types
        t = Type(screenplay.SCENE)
        t.beforeSpacing = 10
        t.indent = 0
        t.width = 60
        t.screen.isCaps = True
        t.screen.isBold = True
        t.export.isCaps = True
        self.types[t.lt] = t

        t = Type(screenplay.ACTION)
        t.beforeSpacing = 10
        t.indent = 0
        t.width = 60
        self.types[t.lt] = t

        t = Type(screenplay.CHARACTER)
        t.beforeSpacing = 10
        t.indent = 22
        t.width = 38
        t.screen.isCaps = True
        t.export.isCaps = True
        self.types[t.lt] = t

        t = Type(screenplay.DIALOGUE)
        t.indent = 10
        t.width = 35
        self.types[t.lt] = t

        t = Type(screenplay.PAREN)
        t.indent = 16
        t.width = 25
        self.types[t.lt] = t

        t = Type(screenplay.TRANSITION)
        t.beforeSpacing = 10
        t.indent = 45
        t.width = 20
        t.screen.isCaps = True
        t.export.isCaps = True
        self.types[t.lt] = t

        t = Type(screenplay.SHOT)
        t.beforeSpacing = 10
        t.indent = 0
        t.width = 60
        t.screen.isCaps = True
        t.export.isCaps = True
        self.types[t.lt] = t

        t = Type(screenplay.ACTBREAK)
        t.beforeSpacing = 10
        t.indent = 25
        t.width = 20
        t.screen.isCaps = True
        t.screen.isBold = True
        t.screen.isUnderlined = True
        t.export.isCaps = True
        t.export.isUnderlined = True
        self.types[t.lt] = t

        # pdf font configs, key = PDF_FONT_*, value = PdfFontInfo
        self.pdfFonts = {}

        for name, style in (
            (PDF_FONT_NORMAL, pml.COURIER),
            (PDF_FONT_BOLD, pml.COURIER | pml.BOLD),
            (PDF_FONT_ITALIC, pml.COURIER | pml.ITALIC),
            (PDF_FONT_BOLD_ITALIC, pml.COURIER | pml.BOLD | pml.ITALIC),
        ):
            self.pdfFonts[name] = PDFFontInfo(name, style)

        self.recalc()

    def setupVars(self):
        v = self.__class__.cvars = mypickle.Vars()

        # font size used for PDF generation, in points
        v.addInt("fontSize", 12, "FontSize", 4, 72)

        # margins
        v.addFloat("marginBottom", 25.4, "Margin/Bottom", 0.0, 900.0)
        v.addFloat("marginLeft", 38.1, "Margin/Left", 0.0, 900.0)
        v.addFloat("marginRight", 25.4, "Margin/Right", 0.0, 900.0)
        v.addFloat("marginTop", 12.7, "Margin/Top", 0.0, 900.0)

        # paper size
        v.addFloat("paperHeight", 297.0, "Paper/Height", 100.0, 1000.0)
        v.addFloat("paperWidth", 210.0, "Paper/Width", 50.0, 1000.0)

        # leave at least this many action lines on the end of a page
        v.addInt("pbActionLines", 2, "PageBreakActionLines", 1, 30)

        # leave at least this many dialogue lines on the end of a page
        v.addInt("pbDialogueLines", 2, "PageBreakDialogueLines", 1, 30)

        # whether each act starts on a new page (see
        # Screenplay.isActStart)
        v.addBool("pbActNewPage", True, "PageBreakActNewPage")

        # whether every character takes up two columns instead of one, for
        # Chinese, Japanese and Korean, whose characters are twice as wide
        # as Latin ones (see getCharWidth)
        v.addBool("doubleWidth", False, "DoubleWidth")

        # whether the user has been asked about switching to double-width
        # characters after typing one, so it's only asked once per script
        v.addBool("doubleWidthAsked", False, "DoubleWidthAsked")

        # whether scene continueds are enabled
        v.addBool("sceneContinueds", False, "SceneContinueds")

        # scene continued text indent width
        v.addInt("sceneContinuedIndent", 45, "SceneContinuedIndent", -20, 80)

        # whether to include scene numbers
        v.addBool("pdfShowSceneNumbers", False, "ShowSceneNumbers")

        # whether to include PDF TOC
        v.addBool("pdfIncludeTOC", True, "IncludeTOC")

        # whether to show PDF TOC by default
        v.addBool("pdfShowTOC", True, "ShowTOC")

        # whether to open PDF document on current page

        # whether to draw rectangle showing margins
        v.addBool("pdfShowMargins", False, "ShowMargins")

        # whether to show line numbers next to each line
        v.addBool("pdfShowLineNumbers", False, "ShowLineNumbers")

        # cursor position, line
        v.addInt("cursorLine", 0, "Cursor/Line", 0, 1000000)

        # cursor position, column
        v.addInt("cursorColumn", 0, "Cursor/Column", 0, 1000000)

        # various strings we add to the script
        v.addStrLatin1("strMore", "(MORE)", "String/MoreDialogue")
        v.addStrLatin1("strContinuedPageEnd", "(CONTINUED)", "String/ContinuedPageEnd")
        v.addStrLatin1(
            "strContinuedPageStart", "CONTINUED:", "String/ContinuedPageStart"
        )
        v.addStrLatin1("strDialogueContinued", " (cont'd)", "String/DialogueContinued")

        v.makeDicts()

    # load config from string 's'. does not throw any exceptions, silently
    # ignores any errors, and always leaves config in an ok state.
    def load(self, s):
        vals = self.cvars.makeVals(s)

        self.cvars.load(vals, "", self)

        for t in self.types.values():
            t.load(vals, "Element/")

        for pf in self.pdfFonts.values():
            pf.load(vals, "Font/")

        self.recalc()

    # set the paper size to one of PAPER_SIZES, by name.
    def setPaper(self, name):
        self.paperWidth, self.paperHeight = PAPER_SIZES[name]
        self.recalc()

    # save config into a string and return that.
    def save(self):
        s = self.cvars.save("", self)

        for t in self.types.values():
            s += t.save("Element/")

        for pf in self.pdfFonts.values():
            s += pf.save("Font/")

        return s

    # fix up all invalid config values and recalculate all variables
    # dependent on other variables.
    #
    # if doAll is False, enforces restrictions only on a per-variable
    # basis, e.g. doesn't modify variable v2 based on v1's value. this is
    # useful when user is interactively modifying v1, and it temporarily
    # strays out of bounds (e.g. when deleting the old text in an entry
    # box, thus getting the minimum value), which would then possibly
    # modify the value of other variables which is not what we want.
    def recalc(self, doAll=True):
        for it in self.cvars.numeric.values():
            util.clampObj(self, it.name, it.minVal, it.maxVal)

        for el in self.types.values():
            for it in el.cvars.numeric.values():
                util.clampObj(el, it.name, it.minVal, it.maxVal)

        for it in self.cvars.stringLatin1.values():
            setattr(self, it.name, textutil.toInputStr(getattr(self, it.name)))

        for pf in self.pdfFonts.values():
            pf.refresh()

        # make sure usable space on the page isn't too small
        if doAll and (self.marginTop + self.marginBottom) >= (self.paperHeight - 100.0):
            self.marginTop = 0.0
            self.marginBottom = 0.0

        h = self.paperHeight - self.marginTop - self.marginBottom

        # how many lines on a page. a line is exactly as tall as the font
        # size, so 12 point gives the standard 6 lines per inch.
        self.linesOnPage = int(h / util.getTextHeight(self.fontSize))

    def getType(self, lt):
        return self.types[lt]

    # return how many columns each character takes up: 2 with double-width
    # characters, otherwise 1. element widths and indents are in columns,
    # so a line holds width // getCharWidth() characters.
    def getCharWidth(self):
        return 2 if self.doubleWidth else 1

    # return (indent, width) of element type lt (character, parenthetical
    # or dialogue) in the given column (1 = left, 2 = right) of a dual
    # dialogue. the action width is split into two columns, and each
    # column gets the same layout as a normal speech, scaled down so that
    # dialogue fills the column.
    def getDualIndentWidth(self, lt, col):
        action = self.types[screenplay.ACTION]
        dlg = self.types[screenplay.DIALOGUE]

        gap = 2
        colWidth = (action.width - gap) // 2
        dlgWidth = max(5, colWidth - 2)

        x = action.indent + (0 if col == 1 else colWidth + gap)

        if lt == screenplay.DIALOGUE:
            return (x, dlgWidth)

        t = self.types[lt]
        offset = round(max(0, t.indent - dlg.indent) * dlgWidth / dlg.width)
        width = round(t.width * dlgWidth / dlg.width)
        width = max(5, min(width, colWidth - offset))

        return (x + offset, width)

    # get a PDFFontInfo object for the given font type (PDF_FONT_*)
    def getPDFFont(self, fontType):
        return self.pdfFonts[fontType]

    # return a tuple of all the PDF font types
    def getPDFFontIds(self):
        return (PDF_FONT_NORMAL, PDF_FONT_BOLD, PDF_FONT_ITALIC, PDF_FONT_BOLD_ITALIC)


# the face of the default screen fonts before the bundled font, and the
# fallback when it can't be loaded
def oldDefaultFace():
    return "Courier New" if misc.isWindows else "Monospace"


# the old default screen fonts on Unix, which only differ from other
# Monospace fonts by their size
_oldUnixFonts = (
    "Monospace 12",
    "Monospace Bold 12",
    "Monospace Italic 12",
    "Monospace Bold Italic 12",
)


# return the font string s (see ConfigGlobal.setDefaultFonts) with the
# bundled face in place of Courier New, or the old Unix defaults' Monospace
def migrateFont(s):
    face = fontinfo.BUNDLED_FACE
    fields = s.split(";")

    # Windows: the face name is the last field
    if (len(fields) > 1) and (fields[-1] == "Courier New"):
        return ";".join(fields[:-1] + [face])

    # Pango: the family comes first
    if s.startswith("Courier New "):
        return face + s[len("Courier New") :]

    if s in _oldUnixFonts:
        return face + s[len("Monospace") :]

    return s


# global config. there is only ever one of these active.
class ConfigGlobal:
    cvars = None

    def __init__(self):

        if not self.__class__.cvars:
            self.setupVars()

        self.__class__.cvars.setDefaults(self)

        # type configs, key = line type, value = TypeGlobal
        self.types = {}

        # element types
        t = TypeGlobal(screenplay.SCENE)
        t.newTypeEnter = screenplay.ACTION
        t.newTypeTab = screenplay.CHARACTER
        t.nextTypeTab = screenplay.ACTION
        t.prevTypeTab = screenplay.TRANSITION
        self.types[t.lt] = t

        t = TypeGlobal(screenplay.ACTION)
        t.newTypeEnter = screenplay.ACTION
        t.newTypeTab = screenplay.CHARACTER
        t.nextTypeTab = screenplay.CHARACTER
        t.prevTypeTab = screenplay.CHARACTER
        self.types[t.lt] = t

        t = TypeGlobal(screenplay.CHARACTER)
        t.newTypeEnter = screenplay.DIALOGUE
        t.newTypeTab = screenplay.PAREN
        t.nextTypeTab = screenplay.ACTION
        t.prevTypeTab = screenplay.ACTION
        self.types[t.lt] = t

        t = TypeGlobal(screenplay.DIALOGUE)
        t.newTypeEnter = screenplay.CHARACTER
        t.newTypeTab = screenplay.ACTION
        t.nextTypeTab = screenplay.PAREN
        t.prevTypeTab = screenplay.ACTION
        self.types[t.lt] = t

        t = TypeGlobal(screenplay.PAREN)
        t.newTypeEnter = screenplay.DIALOGUE
        t.newTypeTab = screenplay.ACTION
        t.nextTypeTab = screenplay.CHARACTER
        t.prevTypeTab = screenplay.DIALOGUE
        self.types[t.lt] = t

        t = TypeGlobal(screenplay.TRANSITION)
        t.newTypeEnter = screenplay.SCENE
        t.newTypeTab = screenplay.TRANSITION
        t.nextTypeTab = screenplay.SCENE
        t.prevTypeTab = screenplay.CHARACTER
        self.types[t.lt] = t

        t = TypeGlobal(screenplay.SHOT)
        t.newTypeEnter = screenplay.ACTION
        t.newTypeTab = screenplay.CHARACTER
        t.nextTypeTab = screenplay.ACTION
        t.prevTypeTab = screenplay.SCENE
        self.types[t.lt] = t

        t = TypeGlobal(screenplay.ACTBREAK)
        t.newTypeEnter = screenplay.SCENE
        t.newTypeTab = screenplay.ACTION
        t.nextTypeTab = screenplay.SCENE
        t.prevTypeTab = screenplay.SCENE
        self.types[t.lt] = t

        # keyboard commands
        self.commands = commands.defaultCommands()

        self.recalc()

    def setupVars(self):
        v = self.__class__.cvars = mypickle.Vars()

        # vertical distance between rows, in pixels
        v.addInt("fontYdelta", 18, "FontYDelta", 4, 125)

        # size of the toolbar icons, in pixels (before DPI scaling)
        v.addInt("toolbarIconSize", 18, "ToolbarIconSize", 16, 48)

        # application theme: the name of a built-in or custom theme, or
        # THEME_SYSTEM
        v.addStrUnicode("theme", THEME_SYSTEM, "Theme")

        # user interface language: a translation's folder name, e.g.
        # "it_IT", or "" for the system's language (the LANG environment
        # variable). takes effect on the next startup.
        v.addStrUnicode("language", "", "Language")

        # paper size of new scripts, a key of PAPER_SIZES
        v.addStrLatin1("defaultPaper", "A4", "DefaultPaper")

        # how many lines to scroll per mouse wheel event
        v.addInt("mouseWheelLines", 4, "MouseWheelLines", 1, 50)

        # interval in minutes between writing recovery copies of modified
        # scripts (0 = disabled)
        v.addInt("autosaveInterval", 2, "AutosaveInterval", 0, 60)

        # whether to check script for formatting errors before export / compare
        v.addBool("checkOnExport", True, "CheckScriptForErrors")

        # whether to auto-capitalize start of sentences
        v.addBool("capitalize", True, "CapitalizeSentences")

        # whether to auto-capitalize i -> I
        v.addBool("capitalizeI", True, "CapitalizeI")

        # whether to underline misspelled words in the editor
        v.addBool("checkSpelling", True, "CheckSpellingAsYouType")

        # whether to open scripts on their last saved position
        v.addBool("honorSavedPos", True, "OpenScriptOnSavedPos")

        # whether to recenter screen when cursor moves out of it
        v.addBool("recenterOnScroll", False, "RecenterOnScroll")

        # whether to overwrite selected text on typing
        v.addBool("overwriteSelectionOnInsert", True, "OverwriteSelectionOnInsert")

        # page break indicators to show
        v.addInt("pbi", PBI_REAL, "PageBreakIndicators", PBI_FIRST, PBI_LAST)

        # whether to run the MCP server that lets AI assistants read and
        # edit the open scripts (see mcpserver/app.py), and the localhost port it
        # listens on. the default port must match mcpserver.DEFAULT_PORT.
        v.addBool("mcpEnabled", False, "MCP/Enabled")
        v.addInt("mcpPort", 7789, "MCP/Port", 1024, 65535)

        # whether to show PDFs in the built-in viewer (where the platform
        # supports it) instead of the external viewer program below
        v.addBool("pdfUseBuiltinViewer", True, "PDF/UseBuiltinViewer")

        # PDF viewer program and args. defaults are empty since generating
        # them is a complex process handled by findPDFViewer.
        v.addStrUnicode("pdfViewerPath", "", "PDF/ViewerPath")
        v.addStrBinary("pdfViewerArgs", "", "PDF/ViewerArguments")

        # fonts. real defaults are set in setDefaultFonts.
        v.addStrBinary("fontNormal", "", "FontNormal")
        v.addStrBinary("fontBold", "", "FontBold")
        v.addStrBinary("fontItalic", "", "FontItalic")
        v.addStrBinary("fontBoldItalic", "", "FontBoldItalic")

        # 1 once the fonts have been moved from the old default face to
        # the bundled one (see migrateFont). older configs don't have it.
        v.addInt("fontVersion", 1, "FontVersion", 0, 1)

        # default script directory
        v.addStrUnicode("scriptDir", misc.progPath, "DefaultScriptDirectory")

        v.makeDicts()

    # load config from string 's'. does not throw any exceptions, silently
    # ignores any errors, and always leaves config in an ok state.
    def load(self, s):
        vals = self.cvars.makeVals(s)

        # older versions saved the theme as Appearance:N
        if ("Theme" not in vals) and ("Appearance" in vals):
            n = util.str2int(vals["Appearance"], 0)

            if 0 <= n < len(_oldAppearances):
                vals["Theme"] = _oldAppearances[n]

        # 'Find next error' became 'Check formatting errors': keep its keys
        old, new = "Command/FindNextError/", "Command/CheckFormatting/"

        if not any(k.startswith(new) for k in vals):
            for k in [k for k in vals if k.startswith(old)]:
                vals[new + k[len(old) :]] = vals[k]

        # the default screen fonts used to be Courier New (Monospace on
        # Unix): move fonts still using them to the bundled font, once, so
        # that choosing one of them again afterwards sticks
        if "FontVersion" not in vals:
            for k in ("FontNormal", "FontBold", "FontItalic", "FontBoldItalic"):
                if k in vals:
                    vals[k] = migrateFont(vals[k])

        self.cvars.load(vals, "", self)

        for t in self.types.values():
            t.load(vals, "Element/")

        for cmd in self.commands:
            cmd.load(vals, "Command/")

        self.recalc()

    # save config into a string and return that.
    def save(self):
        s = self.cvars.save("", self)

        for t in self.types.values():
            s += t.save("Element/")

        for cmd in self.commands:
            s += cmd.save("Command/")

        return s

    # fix up all invalid config values.
    def recalc(self):
        for it in self.cvars.numeric.values():
            util.clampObj(self, it.name, it.minVal, it.maxVal)

        if self.defaultPaper not in PAPER_SIZES:
            self.defaultPaper = "A4"

    def getType(self, lt):
        return self.types[lt]

    # the key bindings, for commands.resolveKey (see commands.makeKeyMap).
    # adds the SHIFT versions of the movement keys first.
    def getKeyMap(self):
        commands.addShiftKeys(self.commands)

        return commands.makeKeyMap(self.commands)

    # set default values that vary depending on platform, wxWidgets
    # version, etc. this is not at the end of __init__ because
    # non-interactive uses have no needs for these.
    def setDefaults(self):
        # check keyboard commands are listed in correct order
        commands.checkOrder(self.commands)

        self.setDefaultFonts()
        self.findPDFViewer()

    # set default fonts
    #
    # the strings are wx.NativeFontInfo.ToString() output, which differs
    # per platform: a Pango font description on GTK, and on Windows a
    # version number (0) followed by the fields of a LOGFONT: height (-13,
    # negative meaning character height in pixels), width, escapement,
    # orientation, weight (400 normal, 700 bold), italic (255 = on),
    # underline, strikeout, charset, out precision, clip precision,
    # quality, pitch and family (49 = fixed pitch, modern), face name.
    #
    # the face is the bundled Courier Prime (see fontinfo.BUNDLED_FONTS),
    # which ConfigGui replaces with oldDefaultFace() if it can't be loaded.
    def setDefaultFonts(self):
        fn = ["", "", "", ""]
        face = fontinfo.BUNDLED_FACE

        if misc.isUnix:
            fn[0] = "%s 12" % face
            fn[1] = "%s Bold 12" % face
            fn[2] = "%s Italic 12" % face
            fn[3] = "%s Bold Italic 12" % face

        elif misc.isWindows:
            fn[0] = "0;-13;0;0;0;400;0;0;0;0;3;2;1;49;" + face
            fn[1] = "0;-13;0;0;0;700;0;0;0;0;3;2;1;49;" + face
            fn[2] = "0;-13;0;0;0;400;255;0;0;0;3;2;1;49;" + face
            fn[3] = "0;-13;0;0;0;700;255;0;0;0;3;2;1;49;" + face

        else:
            raise ConfigError(_("Unknown platform"))

        self.fontNormal = fn[0]
        self.fontBold = fn[1]
        self.fontItalic = fn[2]
        self.fontBoldItalic = fn[3]

    # set PDF viewer program to the best one found on the machine.
    def findPDFViewer(self):
        name, args = util.getPDFViewer()
        if name:
            self.pdfViewerPath = name
            self.pdfViewerArgs = args


# look up key in one of the mapping tables above. a missing key is a
# programming error and raises ConfigError, unless raiseException is
# False, which code reading untrusted input (e.g. Screenplay.load) uses to
# get None instead and handle the unknown value itself.
def _conv(dict, key, raiseException=True):
    val = dict.get(key)
    if (val == None) and raiseException:
        raise ConfigError(_("key '{}' not found from '{}'").format(key, dict))

    return val


# get TypeInfos
def getTIs():
    return _ti


def char2lb(char, raiseException=True):
    return _conv(_char2lb, char, raiseException)


def lb2char(lb):
    return _conv(_lb2char, lb)


def lb2str(lb):
    return _conv(_lb2str, lb)


def char2lt(char, raiseException=True):
    ti = _conv(_char2ti, char, raiseException)

    if ti:
        return ti.lt
    else:
        return None


def lt2char(lt):
    return _conv(_lt2ti, lt).char


def name2ti(name, raiseException=True):
    return _conv(_name2ti, name, raiseException)


def lt2ti(lt):
    return _conv(_lt2ti, lt)


def _init():

    for lt, char, name in (
        (screenplay.SCENE, "\\", "Scene"),
        (screenplay.ACTION, ".", "Action"),
        (screenplay.CHARACTER, "_", "Character"),
        (screenplay.DIALOGUE, ":", "Dialogue"),
        (screenplay.PAREN, "(", "Parenthetical"),
        (screenplay.TRANSITION, "/", "Transition"),
        (screenplay.SHOT, "=", "Shot"),
        (screenplay.ACTBREAK, "@", "Act break"),
    ):

        ti = TypeInfo(lt, char, name)

        _ti.append(ti)
        _lt2ti[lt] = ti
        _char2ti[char] = ti
        _name2ti[name] = ti


_init()
