# importing scripts in the GUI: reading the file, asking for the import
# options and showing the errors, around the importers in
# trelby/importers/, which don't use wx.

import wx

import trelby.dialogs.checkboxdlg as checkboxdlg
import trelby.checkboxitem as checkboxitem
import trelby.importers as importers
import trelby.ui.fileio as fileio
from trelby.dialogs.importdlg import ImportDlg


# import fileName as the formats.Format fmt, asking for its options first.
# sp is the script it's going to replace, whose title pages Fountain
# titles are put on (a copy of them). return an importers.ImportResult, or
# None if the import was cancelled or failed (after showing the error).
def importFile(fileName, fmt, frame, sp):
    importer = fmt.importer
    data = fileio.loadFile(fileName, frame, binary=importer.BINARY)

    if data is None:
        return None

    try:
        options = None
        askOptions = ASK_OPTIONS.get(fmt.key)

        if askOptions:
            options = askOptions(data, frame, sp)

            if options is None:
                return None

        result = importer.parse(data, options)
    except importers.ImportFailed as e:
        wx.MessageBox(e.message, _("Error"), wx.OK, frame)

        return None

    if not result.lines:
        return None

    return result


# ask for the Fountain import options. return importers.fountain.Options,
# or None if cancelled.
def askFountainOptions(data, frame, sp):
    # an empty file is reported before asking anything
    importers.common.checkNotEmpty(data)

    inf = []
    inf.append(checkboxitem.CheckBoxItem(_("Import titles to title page.")))
    inf.append(
        checkboxitem.CheckBoxItem(_("Import titles as action lines."), selected=False)
    )
    inf.append(
        checkboxitem.CheckBoxItem(
            _("Import bold, italic and underline markup as formatting.")
        )
    )
    inf.append(checkboxitem.CheckBoxItem(_("Import section/synopsis as notes.")))

    dlg = checkboxdlg.CheckBoxDlg(
        frame, _("Fountain import options"), inf, _("Import options:"), False
    )

    ok = dlg.ShowModal() == wx.ID_OK
    dlg.Destroy()

    if not ok:
        return None

    return importers.fountain.Options(
        titlePage=inf[0].selected,
        titlesAsAction=inf[1].selected,
        markup=inf[2].selected,
        sectionsAsNotes=inf[3].selected,
        titlePages=sp.titles.pages,
        paperSize=(sp.cfg.paperWidth, sp.cfg.paperHeight),
    )


# show the guessed line type of each indent level in a text file, for the
# user to fix. return importers.text.Options, or None if cancelled.
def askTextOptions(data, frame, sp):
    text = importers.text
    indents = text.guessIndents(data)

    dlg = ImportDlg(frame, indents, text.SCENE_ACTION, text.IGNORE)
    ok = dlg.ShowModal() == wx.ID_OK
    dlg.Destroy()

    if not ok:
        return None

    return text.Options(lineTypes={ind.indent: ind.lt for ind in indents})


# the same for a PDF file, whose lines are indented like a text file's.
# return importers.pdf.Options, or None if cancelled.
def askPdfOptions(data, frame, sp):
    pdf = importers.pdf
    indents = pdf.guessIndents(data)

    dlg = ImportDlg(frame, indents, importers.text.SCENE_ACTION, importers.text.IGNORE)
    ok = dlg.ShowModal() == wx.ID_OK
    dlg.Destroy()

    if not ok:
        return None

    return pdf.Options(lineTypes={ind.indent: ind.lt for ind in indents})


# the formats with import options, by key, and the function asking for
# them
ASK_OPTIONS = {
    "fountain": askFountainOptions,
    "pdf": askPdfOptions,
    "text": askTextOptions,
}
