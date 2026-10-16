# the menu commands that work on one script: functions taking the main
# window (trelbyframe.MyFrame, the parent for dialogs) and the script's
# trelbyctrl.MyCtrl, which menus.py binds to the menu items and keyboard
# commands.

import copy
import os.path
from functools import partial

import wx

import trelby.dialogs.autocompletiondlg as autocompletiondlg
import trelby.dialogs.cfgdlg as cfgdlg
import trelby.dialogs.characterprofilesdlg as characterprofilesdlg
import trelby.dialogs.charmapdlg as charmapdlg
import trelby.dialogs.checkboxdlg as checkboxdlg
import trelby.checkboxitem as checkboxitem
import trelby.config as config
import trelby.dialogs.finddlg as finddlg
import trelby.dialogs.headersdlg as headersdlg
import trelby.keys as keys
import trelby.dialogs.locationsdlg as locationsdlg
import trelby.misc as misc
import trelby.dialogs.namesdlg as namesdlg
import trelby.pagelock as pagelock
import trelby.pdf.writer as pdf
import trelby.screenplay as screenplay
import trelby.screenplay.compare as compare
import trelby.screenplay.plaintext as plaintext
import trelby.screenplay.proofing as proofing
import trelby.screenplay.render as render
import trelby.dialogs.scriptchooserdlg as scriptchooserdlg
import trelby.spellcheck as spellcheck
import trelby.dialogs.spellcheckcfgdlg as spellcheckcfgdlg
import trelby.dialogs.spellcheckdlg as spellcheckdlg
import trelby.dialogs.textdlg as textdlg
import trelby.textutil as textutil
import trelby.dialogs.titlesdlg as titlesdlg
import trelby.dialogs.watermarkdlg as watermarkdlg
import trelby.dialogs.worldbuildingdlg as worldbuildingdlg
import trelby.ui.fileio as fileio


# change the type of the element at the cursor or the selected ones to lt
def changeType(frame, ctrl, lt):
    ctrl.changeType(lt)


def lockPages(frame, ctrl):
    ctrl.ed.lockPages()
    ctrl.makeLineVisible(ctrl.ed.line)
    ctrl.updateScreen()


def unlockPages(frame, ctrl):
    ctrl.ed.unlockPages()
    ctrl.makeLineVisible(ctrl.ed.line)
    ctrl.updateScreen()


def lockScenes(frame, ctrl):
    ctrl.ed.lockScenes()
    ctrl.updateScreen()


def unlockScenes(frame, ctrl):
    ctrl.ed.unlockScenes()
    ctrl.updateScreen()


def autoCompletionDlg(frame, ctrl):
    dlg = autocompletiondlg.AutoCompletionDlg(
        frame, copy.deepcopy(ctrl.sp.autoCompletion)
    )

    if dlg.ShowModal() == wx.ID_OK:
        ctrl.sp.autoCompletion = dlg.autoCompletion
        ctrl.sp.markChanged()

    dlg.Destroy()


def titlesDlg(frame, ctrl):
    dlg = titlesdlg.TitlesDlg(
        frame, copy.deepcopy(ctrl.sp.titles), ctrl.sp.cfg, ctrl.gd.cfgGl
    )

    if dlg.ShowModal() == wx.ID_OK:
        ctrl.sp.titles = dlg.titles
        ctrl.sp.markChanged()

    dlg.Destroy()


def applyHeaders(ctrl, newHeaders):
    ctrl.sp.headers = newHeaders
    ctrl.sp.markChanged()
    ctrl.sp.paginate()
    ctrl.makeLineVisible(ctrl.ed.line)
    ctrl.updateScreen()


def headersDlg(frame, ctrl):
    dlg = headersdlg.HeadersDlg(
        frame,
        copy.deepcopy(ctrl.sp.headers),
        ctrl.sp.cfg,
        ctrl.gd.cfgGl,
        partial(applyHeaders, ctrl),
    )

    if dlg.ShowModal() == wx.ID_OK:
        applyHeaders(ctrl, dlg.headers)

    dlg.Destroy()


def locationsDlg(frame, ctrl):
    dlg = locationsdlg.LocationsDlg(frame, copy.deepcopy(ctrl.sp))

    if dlg.ShowModal() == wx.ID_OK:
        ctrl.sp.locations = dlg.sp.locations
        ctrl.sp.markChanged()

    dlg.Destroy()


def characterProfilesDlg(frame, ctrl):
    # start with the character whose name or speech the cursor is on
    selectName = ctrl.sp.getCharacterAt(ctrl.ed.line)

    old = ctrl.sp.characterProfiles.save()

    dlg = characterprofilesdlg.CharacterProfilesDlg(
        frame,
        copy.deepcopy(ctrl.sp.characterProfiles),
        ctrl.sp.getCharacterNames(),
        selectName,
    )

    if dlg.ShowModal() == wx.ID_OK:
        if dlg.charProfiles.save() != old:
            ctrl.sp.characterProfiles = dlg.charProfiles
            ctrl.sp.markChanged()

        # renaming a character's profile renames the character
        # everywhere in the script too
        if dlg.renames and any(ctrl.ed.renameCharacters(dlg.renames)):
            ctrl.sp.paginate()
            ctrl.makeLineVisible(ctrl.ed.line)
            ctrl.updateScreen()

    dlg.Destroy()


def worldBuildingDlg(frame, ctrl):
    dlg = worldbuildingdlg.WorldBuildingDlg(
        frame, copy.deepcopy(ctrl.sp.worldBuilding)
    )

    if dlg.ShowModal() == wx.ID_OK:
        if dlg.worldBuilding.text != ctrl.sp.worldBuilding.text:
            ctrl.sp.worldBuilding = dlg.worldBuilding
            ctrl.sp.markChanged()

    dlg.Destroy()


def scriptDictionaryDlg(frame, ctrl):
    dlg = spellcheckcfgdlg.SCDictDlg(
        frame, copy.deepcopy(ctrl.sp.scDict), False
    )

    if dlg.ShowModal() == wx.ID_OK:
        ctrl.sp.scDict = dlg.scDict
        ctrl.sp.markChanged()

    dlg.Destroy()


def watermark(frame, ctrl):
    dlg = watermarkdlg.WatermarkDlg(
        frame, ctrl.sp, ctrl.fileNameDisplay.replace(".trelby", "")
    )
    dlg.ShowModal()
    dlg.Destroy()


# show a report on the script, made by gen, e.g. reports.genSceneReport
def report(frame, ctrl, gen):
    ctrl.sp.paginate()
    gen(frame, ctrl.sp, ctrl.fileNameDisplay)


def compareScripts(frame, ctrl):
    if frame.tabCtrl.getPageCount() < 2:
        wx.MessageBox(
            _("You need at least two scripts open to compare them."),
            _("Error"),
            wx.OK,
            frame,
        )

        return

    items = []
    for c in frame.getCtrls():
        items.append(c.fileNameDisplay)

    dlg = scriptchooserdlg.ScriptChooserDlg(frame, items)

    sel1 = -1
    sel2 = -1
    if dlg.ShowModal() == wx.ID_OK:
        sel1 = dlg.sel1
        sel2 = dlg.sel2
        force = dlg.forceSameCfg

    dlg.Destroy()

    if sel1 == -1:
        return

    if sel1 == sel2:
        wx.MessageBox(
            _("You can't compare a script to itself."),
            _("Error"),
            wx.OK,
            frame,
        )

        return

    c1 = frame.tabCtrl.getPage(sel1).ctrl
    c2 = frame.tabCtrl.getPage(sel2).ctrl

    sp1 = getExportable(frame, c1, "compare")
    sp2 = getExportable(frame, c2, "compare")

    if not sp1 or not sp2:
        return

    if force:
        sp2 = copy.deepcopy(sp2)
        sp2.cfg = copy.deepcopy(sp1.cfg)
        sp2.reformatAll()
        sp2.paginate()

    s = compare.compareScripts(sp1, sp2)

    if s:
        fileio.showTempPDF(s, ctrl.gd.cfgGl, frame)
    else:
        wx.MessageBox(
            _("The scripts are identical."), _("Results"), wx.OK, frame
        )


# return an exportable, paginated Screenplay object, or None if for
# some reason that's not possible / wanted. 'action' is the name of
# the action, e.g. "export" or "compare", that'll be done to the script,
# and is used in dialogue with the user if needed.
def getExportable(frame, ctrl, action):
    if ctrl.gd.cfgGl.checkOnExport and not confirmExportable(frame, ctrl, action):
        return None

    sp = ctrl.sp
    if sp.cfg.pdfRemoveNotes:
        sp = copy.deepcopy(ctrl.sp)
        screenplay.Editor(sp).removeElementTypes({screenplay.NOTE: None}, False)

    sp.paginate()

    return sp


# check the script before 'action' ("export" or "compare") is done to
# it. if it's empty or has an error, ask whether to continue anyway,
# offering to show the error. returns True if we should continue.
def confirmExportable(frame, ctrl, action):
    anyway = {"export": _("Export Anyway"), "compare": _("Compare Anyway")}[
        action
    ]

    if ctrl.sp.isEmpty():
        dlg = wx.MessageDialog(
            frame,
            _("\"{}\" is empty.").format(ctrl.fileNameDisplay),
            _("Empty Script"),
            wx.OK | wx.CANCEL | wx.CANCEL_DEFAULT | wx.ICON_INFORMATION,
        )
        dlg.SetExtendedMessage(_("There is no text in the script yet."))
        dlg.SetOKCancelLabels(anyway, wx.ID_CANCEL)
        ret = dlg.ShowModal()
        dlg.Destroy()

        return ret == wx.ID_OK

    line, msg = proofing.findError(ctrl.sp, 0)

    if line == -1:
        return True

    dlg = wx.MessageDialog(
        frame,
        _("\"{}\" has a problem on page {}.").format(
            ctrl.fileNameDisplay, ctrl.sp.line2pageLabel(line)
        ),
        _("Script Problem"),
        wx.YES_NO | wx.CANCEL | wx.CANCEL_DEFAULT | wx.ICON_WARNING,
    )
    dlg.SetExtendedMessage(msg)
    dlg.SetYesNoCancelLabels(anyway, _("Go to Problem"), wx.ID_CANCEL)
    ret = dlg.ShowModal()
    dlg.Destroy()

    if ret == wx.ID_NO:
        page = frame.findPage(ctrl.panel)
        if page != -1:
            frame.tabCtrl.selectPage(page)

        ctrl.clearAutoComp()
        ctrl.ed.line = line
        ctrl.ed.column = 0
        ctrl.makeLineVisible(line)
        ctrl.updateScreen()

    return ret == wx.ID_YES


def revert(frame, ctrl):
    if ctrl.fileName:
        if not ctrl.canBeClosed():
            return

        ctrl.loadFile(ctrl.fileName)
        ctrl.updateScreen()


def undo(frame, ctrl):
    ctrl.ed.cmd("undo")
    ctrl.sp.paginate()
    ctrl.makeLineVisible(ctrl.ed.line)
    ctrl.updateScreen()


def redo(frame, ctrl):
    ctrl.ed.cmd("redo")
    ctrl.sp.paginate()
    ctrl.makeLineVisible(ctrl.ed.line)
    ctrl.updateScreen()


def cut(frame, ctrl):
    ctrl.OnCut()


def copySelection(frame, ctrl):
    ctrl.OnCut(doDelete=False)


def paste(frame, ctrl):
    ctrl.OnPaste()


# copy the selection to the system clipboard, as plain text
def copySystem(frame, ctrl, formatted=False):
    cd = ctrl.ed.getSelectedAsCD(False)

    if not cd:
        return

    s = plaintext.linesToText(cd.lines, ctrl.gd.cfgGl, formatted)

    if wx.TheClipboard.Open():
        wx.TheClipboard.UsePrimarySelection(False)

        wx.TheClipboard.Clear()
        wx.TheClipboard.AddData(wx.TextDataObject(s))
        wx.TheClipboard.Flush()

        wx.TheClipboard.Close()


# paste the text on the system clipboard as action lines
def pasteSystem(frame, ctrl):
    s = ""

    if wx.TheClipboard.Open():
        wx.TheClipboard.UsePrimarySelection(False)

        df = wx.DataFormat(wx.DF_TEXT)

        if wx.TheClipboard.IsSupported(df):
            data = wx.TextDataObject()
            wx.TheClipboard.GetData(data)
            s = data.GetText()

        wx.TheClipboard.Close()

    lines = plaintext.textToLines(s)

    # given no lines, OnPaste would paste Trelby's own clipboard
    if lines:
        ctrl.OnPaste(lines)


def selectScene(frame, ctrl):
    ctrl.ed.cmd("selectScene")

    ctrl.makeLineVisible(ctrl.ed.line)
    ctrl.updateScreen()


def selectAll(frame, ctrl):
    ctrl.ed.cmd("selectAll")

    ctrl.makeLineVisible(ctrl.ed.line)
    ctrl.updateScreen()


def gotoScene(frame, ctrl):
    ctrl.sp.paginate()
    ctrl.clearAutoComp()

    scenes = ctrl.sp.getSceneLocations()

    # the menu item is disabled then, but not the shortcut
    if not scenes:
        return

    def validateFunc(s):
        if pagelock.normalize(s) in [x[0] for x in scenes]:
            return ""
        else:
            return _("Invalid scene number.")

    dlg = textdlg.TextInputDlg(
        frame,
        _("Enter scene number ({} - {}):").format(scenes[0][0], scenes[-1][0]),
        _("Goto scene"),
        validateFunc,
    )

    if dlg.ShowModal() == wx.ID_OK:
        for it in scenes:
            if it[0] == pagelock.normalize(dlg.input):
                ctrl.ed.line = it[1]
                ctrl.ed.column = 0

                break

    # we need to refresh the screen in all cases because pagination
    # might have changed
    ctrl.makeLineVisible(ctrl.ed.line)
    ctrl.updateScreen()


def gotoPage(frame, ctrl):
    ctrl.sp.paginate()
    ctrl.clearAutoComp()

    pages = ctrl.sp.getPageNumbers()

    def validateFunc(s):
        if ctrl.sp.label2page(s) != -1:
            return ""
        else:
            return _("Invalid page number.")

    dlg = textdlg.TextInputDlg(
        frame,
        _("Enter page number ({} - {}):").format(pages[0], pages[-1]),
        _("Goto page"),
        validateFunc,
    )

    if dlg.ShowModal() == wx.ID_OK:
        page = ctrl.sp.label2page(dlg.input)
        ctrl.ed.line = ctrl.sp.page2lines(page)[0]
        ctrl.ed.column = 0

    # we need to refresh the screen in all cases because pagination
    # might have changed
    ctrl.makeLineVisible(ctrl.ed.line)
    ctrl.updateScreen()


def insertNbsp(frame, ctrl):
    ctrl.OnKeyChar(keys.MyKeyEvent(160))


def dualDialogue(frame, ctrl):
    ctrl.clearAutoComp()

    if not ctrl.ed.toggleDualDialogue():
        wx.MessageBox(
            _(
                "Dual dialogue needs two speeches in a row (a character"
                " followed by its dialogue), with the cursor in one of"
                " them."
            ),
            _("Error"),
            wx.OK,
            frame,
        )

        return

    ctrl.sp.paginate()
    ctrl.makeLineVisible(ctrl.ed.line)
    ctrl.updateScreen()


# toggle a formatting bit (textfmt.BOLD etc.) on the selected text, or
# for the text typed next
def toggleFormat(frame, ctrl, bit):
    ctrl.clearAutoComp()
    ctrl.ed.toggleFormat(bit)
    ctrl.updateScreen()


# center the action at the cursor or in the selection, or stop
# centering it
def toggleCentered(frame, ctrl):
    ctrl.clearAutoComp()

    if ctrl.ed.toggleCentered():
        ctrl.sp.paginate()
        ctrl.updateScreen()


def findNextError(frame, ctrl):
    ctrl.clearAutoComp()

    line, msg = proofing.findError(ctrl.sp, ctrl.ed.line)

    if line != -1:
        ctrl.ed.line = line
        ctrl.ed.column = 0

        ctrl.makeLineVisible(ctrl.ed.line)
        ctrl.updateScreen()

    else:
        msg = _("No errors found.")

    wx.MessageBox(msg, _("Results"), wx.OK, frame)


def find(frame, ctrl):
    ctrl.ed.clearMark()
    ctrl.clearAutoComp()
    ctrl.updateScreen()

    dlg = finddlg.FindDlg(frame, ctrl)
    dlg.ShowModal()
    dlg.saveState()
    dlg.Destroy()

    ctrl.ed.clearMark()
    ctrl.makeLineVisible(ctrl.ed.line)
    ctrl.updateScreen()


def spellCheck(frame, ctrl):
    ctrl.ed.clearMark()
    ctrl.clearAutoComp()

    wasAtStart = ctrl.ed.line == 0

    wx.BeginBusyCursor()

    if not spellcheckdlg.loadDict(frame):
        wx.EndBusyCursor()

        return

    sc = spellcheck.SpellChecker(ctrl.sp, ctrl.gd.scDict, ctrl.ed.line)
    found = sc.findNext()

    wx.EndBusyCursor()

    if not found:
        s = ""

        if not wasAtStart:
            s = _(
                "\n\n(Starting position was not at\nthe beginning of the script.)"
            )
        wx.MessageBox(
            _("Spell checker found no errors.") + s,
            _("Results"),
            wx.OK,
            frame,
        )

        return

    dlg = spellcheckdlg.SpellCheckDlg(frame, ctrl, sc, ctrl.gd.scDict)
    dlg.ShowModal()

    if dlg.changedGlobalDict:
        ctrl.gd.saveScDict()

    dlg.Destroy()

    ctrl.ed.clearMark()
    ctrl.makeLineVisible(ctrl.ed.line)
    ctrl.updateScreen()


def deleteElements(frame, ctrl):
    # even though Editor.removeElementTypes does this as well, do
    # it here so that screen is cleared from the auto-comp box before
    # we open the dialog
    ctrl.clearAutoComp()

    types = []
    for t in config.getTIs():
        types.append(checkboxitem.CheckBoxItem(t.name, False, t.lt))

    dlg = checkboxdlg.CheckBoxDlg(
        frame,
        _("Delete elements"),
        types,
        _("Element types to delete:"),
        True,
    )

    ok = False
    if dlg.ShowModal() == wx.ID_OK:
        ok = True

        tdict = checkboxitem.CheckBoxItem.getClientData(types)

    dlg.Destroy()

    if not ok or (len(tdict) == 0):
        return

    ctrl.ed.removeElementTypes(tdict, True)
    ctrl.sp.paginate()
    ctrl.makeLineVisible(ctrl.ed.line)
    ctrl.updateScreen()


def save(frame, ctrl):
    if ctrl.fileName:
        ctrl.saveFile(ctrl.fileName)
    else:
        saveAs(frame, ctrl)


def saveAs(frame, ctrl):
    if ctrl.fileName:
        dDir = os.path.dirname(ctrl.fileName)
        dFile = os.path.basename(ctrl.fileName)
    else:
        dDir = misc.scriptDir
        dFile = ""

    dlg = wx.FileDialog(
        frame,
        _("Filename to save as"),
        defaultDir=dDir,
        defaultFile=dFile,
        wildcard="Trelby files (*.trelby)|*.trelby|All files|*",
        style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
    )
    if dlg.ShowModal() == wx.ID_OK:
        ctrl.saveFile(dlg.GetPath())

    dlg.Destroy()


# ask for the formats.Format fmt's export options, if it has any.
# returns them as a dict, or None if cancelled.
def askExportOptions(frame, fmt):
    if not fmt.options:
        return {}

    inf = [checkboxitem.CheckBoxItem(label()) for name, label in fmt.options]

    dlg = checkboxdlg.CheckBoxDlg(
        frame, _("Output options"), inf, _("Options:"), False
    )
    ok = dlg.ShowModal() == wx.ID_OK
    dlg.Destroy()

    if not ok:
        return None

    return {name: it.selected for (name, label), it in zip(fmt.options, inf)}


# if the PDF fonts can't show some of sp's characters, ask whether to
# export it anyway. returns True to go ahead.
def confirmPdfChars(frame, sp):
    chars = pdf.unsupportedChars(render.generatePML(sp))

    if chars:
        if len(chars) > 40:
            chars = chars[:40] + "..."

        if (
            wx.MessageBox(
                _(
                    "The built-in PDF fonts can't show these characters, so they will\nbe shown as boxes or in a different font:\n\n{}\n\nTo show them, choose a TrueType font that has them in\nScript/Script settings/PDF/Fonts.\n\nExport anyway?"
                ).format(" ".join(chars)),
                _("Confirm"),
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
                frame,
            )
            == wx.NO
        ):
            return False

    return True


# export the script in the formats.Format fmt
def exportScript(frame, ctrl, fmt):
    sp = getExportable(frame, ctrl, "export")
    if not sp:
        return

    dlg = wx.FileDialog(
        frame,
        _("Filename to export as"),
        misc.scriptDir,
        wildcard=fmt.getWildcard(),
        style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
    )

    if dlg.ShowModal() == wx.ID_OK:
        misc.scriptDir = dlg.GetDirectory()
        fileName = textutil.ensureEndsIn(dlg.GetPath(), "." + fmt.extensions[0])
        options = askExportOptions(frame, fmt)

        if (options is not None) and (
            (fmt.key != "pdf") or confirmPdfChars(frame, sp)
        ):
            fileio.writeToFile(fileName, fmt.generate(sp, **options), frame)

    dlg.Destroy()


def scriptSettings(frame, ctrl):
    dlg = cfgdlg.CfgDlg(
        frame,
        copy.deepcopy(ctrl.sp.cfg),
        ctrl.applyCfg,
        False,
        ctrl.gd,
    )

    if dlg.ShowModal() == wx.ID_OK:
        ctrl.applyCfg(dlg.cfg)

    dlg.Destroy()


# the LoadScriptSettings / SaveScriptSettingsAs keyboard commands. the
# script settings dialog has buttons for these too.
def loadScriptSettings(frame, ctrl):
    path = cfgdlg.askScriptSettingsFile(frame, ctrl.gd.scriptSettingsPath, False)
    if not path:
        return

    c = cfgdlg.loadScriptCfg(path, frame)
    if c:
        ctrl.applyCfg(c)
        ctrl.gd.scriptSettingsPath = os.path.dirname(path)


def saveScriptSettingsAs(frame, ctrl):
    path = cfgdlg.askScriptSettingsFile(frame, ctrl.gd.scriptSettingsPath, True)
    if not path:
        return

    if fileio.writeToFile(path, ctrl.sp.saveCfg(), frame):
        ctrl.gd.scriptSettingsPath = os.path.dirname(path)


def nameDatabase(frame, ctrl):
    if not namesdlg.readNames(frame):
        wx.MessageBox(_("Error opening name database."), _("Error"), wx.OK, frame)

        return

    dlg = namesdlg.NamesDlg(frame, ctrl)
    dlg.ShowModal()
    dlg.Destroy()


def characterMap(frame, ctrl):
    dlg = charmapdlg.CharMapDlg(frame, ctrl)
    dlg.ShowModal()
    dlg.Destroy()
