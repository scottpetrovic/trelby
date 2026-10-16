# the file formats scripts can be exported to and imported from: the File
# menu's Export and Import submenus, their file dialogs, and the MCP
# server's export_script tool all come from EXPORT_FORMATS and
# IMPORT_FORMATS. this doesn't need wx: importers are named by their
# function in myimport (which shows message boxes), and looked up there
# when used.
#
# the texts are functions returning them, as the formats are defined
# before the translations are loaded.

import os.path

import trelby.screenplay.export as export


class Format:
    def __init__(
        self,
        key,
        name,
        menuLabel,
        mnemonic,
        extensions,
        generate=None,
        binary=False,
        options=(),
        importer=None,
        importsTitles=False,
    ):
        # id, e.g. "fdx", which the MCP server's clients use
        self.key = key

        # file type description for the file dialogs
        self.name = name

        # the menu item's label, and the letter to underline in it
        self.menuLabel = menuLabel
        self.mnemonic = mnemonic

        # file name extensions, without the dot. an export is saved with
        # the first one.
        self.extensions = extensions

        # export formats: a function taking a paginated Screenplay and
        # returning the file's contents, as str or bytes. options are
        # booleans the GUI asks for first, as (name, label) pairs, passed
        # as keyword arguments; without them the function's defaults apply.
        self.generate = generate
        self.options = options

        # whether the export can't be shown as text, and has to be saved
        # to a file
        self.binary = binary

        # import formats: the name of the myimport function that reads
        # one, taking (fileName, frame) and returning a list of Lines, or
        # None on errors. if importsTitles, it also takes the script's
        # title pages, and returns (lines, title pages).
        self.importer = importer
        self.importsTitles = importsTitles

    # the file dialog's wildcard for this format
    def getWildcard(self):
        patterns = ";".join("*." + ext for ext in self.extensions)

        return "%s (%s)|%s" % (self.name(), patterns, patterns)


EXPORT_FORMATS = [
    Format(
        "pdf",
        lambda: "PDF",
        lambda: _("PDF"),
        "P",
        ["pdf"],
        export.generatePDF,
        binary=True,
    ),
    Format(
        "rtf",
        lambda: "RTF",
        lambda: _("Rich Text (RTF)"),
        "R",
        ["rtf"],
        export.generateRTF,
    ),
    Format(
        "fdx",
        lambda: "Final Draft XML",
        lambda: _("Final Draft (FDX)"),
        "D",
        ["fdx"],
        export.generateFDX,
    ),
    Format(
        "html",
        lambda: "HTML",
        lambda: _("HTML"),
        "H",
        ["html"],
        lambda sp, includeNotes=True: export.generateHtml(sp, includeNotes),
        options=[("includeNotes", lambda: _("Include Notes"))],
    ),
    Format(
        "fountain",
        lambda: "Fountain",
        lambda: _("Fountain"),
        "F",
        ["fountain"],
        export.generateFountain,
    ),
    Format(
        "text",
        lambda: _("Formatted text"),
        lambda: _("Formatted Text"),
        "T",
        ["txt"],
        lambda sp, pageMarkers=False: export.generateText(sp, pageMarkers),
        options=[("pageMarkers", lambda: _("Include page markers"))],
    ),
]

IMPORT_FORMATS = [
    Format(
        "fdx",
        lambda: "Final Draft XML",
        lambda: _("Final Draft (FDX)"),
        "D",
        ["fdx"],
        importer="importFDX",
    ),
    Format(
        "fountain",
        lambda: "Fountain",
        lambda: _("Fountain"),
        "F",
        ["fountain", "txt"],
        importer="importFountain",
        importsTitles=True,
    ),
    Format(
        "celtx",
        lambda: "Celtx",
        lambda: _("Celtx"),
        "C",
        ["celtx"],
        importer="importCeltx",
    ),
    Format(
        "astx",
        lambda: "Adobe Story XML",
        lambda: _("Adobe Story (ASTX)"),
        "A",
        ["astx"],
        importer="importAstx",
    ),
    Format(
        "fadein",
        lambda: "Fade In",
        lambda: _("Fade In"),
        "I",
        ["fadein"],
        importer="importFadein",
    ),
    Format(
        "text",
        lambda: _("Formatted text"),
        lambda: _("Formatted Text"),
        "T",
        ["txt"],
        importer="importTextFile",
    ),
]


# return the Format with the given key in formats, or None
def find(formats, key):
    return next((f for f in formats if f.key == key), None)


# return the import format to read fileName as, going by its extension: the
# first one that lists it first, e.g. formatted text for a .txt file, even
# though Fountain files can have that extension too. anything unknown is
# read as formatted text.
def guessImportFormat(fileName):
    ext = os.path.splitext(fileName)[1].lower().lstrip(".")

    for f in IMPORT_FORMATS:
        if f.extensions[0] == ext:
            return f

    return find(IMPORT_FORMATS, "text")
