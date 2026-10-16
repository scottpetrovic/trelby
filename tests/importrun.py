# ut:ignore
# runs the script importers on files for the tests (test_importers.py),
# and turns their results into plain values to compare.

from unittest import mock

import wx

import tests.u as u
import trelby.formats as formats
import trelby.ui.myimport as myimport
import trelby.screenplay as screenplay
import trelby.translations as translations

_ = translations.trelby_translations_load()

LB_NAMES = {
    screenplay.LB_SPACE: "SPACE",
    screenplay.LB_NONE: "NONE",
    screenplay.LB_FORCED: "FORCED",
    screenplay.LB_LAST: "LAST",
}

LT_NAMES = {
    screenplay.SCENE: "SCENE",
    screenplay.ACTION: "ACTION",
    screenplay.CHARACTER: "CHARACTER",
    screenplay.DIALOGUE: "DIALOGUE",
    screenplay.PAREN: "PAREN",
    screenplay.TRANSITION: "TRANSITION",
    screenplay.SHOT: "SHOT",
    screenplay.NOTE: "NOTE",
    screenplay.ACTBREAK: "ACTBREAK",
}

# the Fountain import options, in the order its dialog lists them, and
# their defaults
FOUNTAIN_OPTIONS = [
    ("titlePage", True),
    ("titlesAsAction", False),
    ("markup", True),
    ("sectionsAsNotes", True),
]


# an import that failed with an error message
class Failed(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


# import the file at 'path' as the format 'key' (as in
# formats.IMPORT_FORMATS), answering the options dialog with 'options'
# (Fountain: FOUNTAIN_OPTIONS; text: lineTypes, a dict of indent -> line
# type to set over the guesses), or cancelling it. titlePages are the
# title pages of the script being replaced. return (lines, title pages or
# None), or None if cancelled. raise Failed if the import shows an error.
def run(key, path, cancel=False, titlePages=None, lineTypes=None, **options):
    u.init()
    path = str(path)
    messages = []

    dlg = mock.Mock()
    dlg.ShowModal.return_value = wx.ID_CANCEL if cancel else wx.ID_OK

    def checkBoxDlg(parent, title, items, descr, rememberLast):
        for item, (name, default) in zip(items, FOUNTAIN_OPTIONS):
            item.selected = options.get(name, default)

        return dlg

    def importDlg(parent, indents, sceneAction, ignore):
        for ind in indents:
            if lineTypes and (ind.indent in lineTypes):
                ind.lt = lineTypes[ind.indent]

        return dlg

    def messageBox(msg, *args):
        messages.append(msg)

    frame = mock.Mock()

    # the script being replaced
    sp = u.new()

    if titlePages is not None:
        sp.titles.pages = titlePages

    with mock.patch.object(wx, "MessageBox", messageBox), mock.patch.object(
        myimport.checkboxdlg, "CheckBoxDlg", checkBoxDlg
    ), mock.patch.object(myimport, "ImportDlg", importDlg):
        result = myimport.importFile(
            path, formats.find(formats.IMPORT_FORMATS, key), frame, sp
        )

    if messages:
        assert len(messages) == 1, messages
        raise Failed(messages[0])

    if result is None:
        return None

    return result.lines, result.titlePages


# lines as strings: line break, line type, text, and any formatting and
# flags
def dumpLines(lines):
    ret = []

    for ln in lines:
        s = "%s %s %r" % (LB_NAMES[ln.lb], LT_NAMES[ln.lt], ln.text)

        if ln.fmt:
            s += " fmt=" + ln.fmt

        if ln.centered:
            s += " centered"

        if ln.dual:
            s += " dual"

        ret.append(s)

    return ret


# title pages as lists of (items, x, y, centered, kind), with the position
# rounded to 0.01 mm
def dumpTitles(pages):
    if pages is None:
        return None

    return [
        [
            (ts.items, round(ts.x, 2), round(ts.y, 2), ts.isCentered, ts.kind)
            for ts in page
        ]
        for page in pages
    ]
