# -*- coding: iso-8859-1 -*-

import copy
import os
import os.path
import time

import wx

import trelby
import trelby.autocompletiondlg as autocompletiondlg
import trelby.autosave as autosave
import trelby.cfgdlg as cfgdlg
import trelby.characterprofilesdlg as characterprofilesdlg
import trelby.config as config
import trelby.dialoguechart as dialoguechart
import trelby.finddlg as finddlg
import trelby.gutil as gutil
import trelby.headersdlg as headersdlg
import trelby.locationsdlg as locationsdlg
import trelby.misc as misc
import trelby.myimport as myimport
import trelby.opts as opts
import trelby.pml as pml
import trelby.reports as reports
import trelby.screenplay as screenplay
import trelby.spellcheck as spellcheck
import trelby.spellcheckcfgdlg as spellcheckcfgdlg
import trelby.spellcheckdlg as spellcheckdlg
import trelby.titlesdlg as titlesdlg
import trelby.util as util
import trelby.watermarkdlg as watermarkdlg
from trelby.error import TrelbyError
from trelby.ids import ID_EDIT_REDO, ID_EDIT_UNDO, idToLTMap
from trelby.line import Line

# Boolean to determine if toolbar should be shown or not.
toolbarshown = True

# keycodes
KC_CTRL_A = 1
KC_CTRL_B = 2
KC_CTRL_D = 4
KC_CTRL_E = 5
KC_CTRL_F = 6
KC_CTRL_N = 14
KC_CTRL_P = 16
KC_CTRL_V = 22


class MyCtrl(wx.Control):

    # panel is the trelbypanel.MyPanel we belong to
    def __init__(self, parent, id, gd, panel):
        style = wx.WANTS_CHARS | wx.FULL_REPAINT_ON_RESIZE | wx.NO_BORDER
        wx.Control.__init__(self, parent, id, style=style)

        self.panel = panel
        self.gd = gd

        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDClick)
        self.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)
        self.Bind(wx.EVT_CHAR, self.OnKeyChar)

        # id of this script's recovery copy (see autosave.py), whether
        # one has been written, and the data last written to it
        self.recoveryId = autosave.newRecoveryId()
        self.recoveryWritten = False
        self.autosavedData = None

        # when the recovery copy was last written (seconds since the
        # epoch), and the error from the last failed attempt, if any. shown
        # in the status bar.
        self.autosaveTime = None
        self.autosaveError = None

        self.createEmptySp()
        self.updateScreen(redraw=False)

    def refreshGuiConfig(self):
        self.gd.cfgGui = config.ConfigGui(self.gd.cfgGl, self.gd.zoom)

    def OnChangeType(self, event):
        self.changeType(idToLTMap[event.GetId()])

    def changeType(self, lt):
        cs = screenplay.CommandState()

        self.sp.convertTypeTo(lt, True)
        self.sp.cmdPost(cs)

        if cs.needsVisifying:
            self.makeLineVisible(self.sp.line)

        self.updateScreen()

    def clearVars(self):
        self.mouseSelectActive = False

        # True while the button is still down after a double/triple click
        # selected a word/element, so drags don't disturb that selection
        self.clickSelectActive = False

        # (time, position) of the last double click, to detect triple
        # clicks, which wx has no event for
        self.lastDClick = None

        # find dialog stored settings
        self.findDlgFindText = ""
        self.findDlgReplaceText = ""
        self.findDlgMatchWholeWord = False
        self.findDlgMatchCase = False
        self.findDlgDirUp = False
        self.findDlgUseExtra = False
        self.findDlgElements = None

    def createEmptySp(self):
        self.removeRecovery()
        self.clearVars()
        self.sp = screenplay.Screenplay(self.gd.cfgGl)
        self.sp.titles.addDefaults()
        self.sp.headers.addDefaults()
        self.setFile(None)
        self.refreshCache()

    # update stuff that depends on configuration / view mode etc.
    def refreshCache(self):
        self.chX = util.getTextWidth(" ", pml.COURIER, self.sp.cfg.fontSize)
        self.chY = util.getTextHeight(self.sp.cfg.fontSize)

        self.pageW = self.gd.vm.getPageWidth(self)

        # conversion factor from mm to pixels
        self.mm2p = self.pageW / self.sp.cfg.paperWidth

        # page width and height on screen, in pixels
        self.pageW = int(self.pageW)
        self.pageH = int(self.mm2p * self.sp.cfg.paperHeight)

    def getCfgGui(self):
        return self.gd.cfgGui

    # load script from path and show it as fileName. returns True on
    # success.
    def loadFile(self, fileName, path=None):
        s = util.loadFile(path or fileName, self.gd.mainFrame)
        if s is None:
            return False

        try:
            (sp, msg) = screenplay.Screenplay.load(s, self.gd.cfgGl)
        except TrelbyError as e:
            wx.MessageBox(
                _("Error loading file:\n\n{}".format(e)),
                _("Error"),
                wx.OK,
                self.gd.mainFrame,
            )

            return False

        if msg:
            misc.showText(self.gd.mainFrame, msg, _("Warning"))

        # whatever was here before has been saved or discarded
        self.removeRecovery()

        self.clearVars()
        self.sp = sp
        self.setFile(fileName)
        self.refreshCache()

        # saved cursor position might be anywhere, so we can't just
        # display the first page
        self.makeLineVisible(self.sp.line)

        return True

    # load the recovery copy described by the autosave.RecoveryEntry, and
    # keep maintaining it until the script is saved or discarded. returns
    # True on success.
    def loadRecovery(self, entry):
        if not self.loadFile(entry.original, entry.scriptPath):
            return False

        self.sp.markChanged(True)
        self.recoveryId = entry.recId
        self.recoveryWritten = True
        self.autosaveTime = entry.time
        self.gd.mainFrame.updateAutosaveStatus(self)

        return True

    # save script to given filename. returns True on success.
    def saveFile(self, fileName):
        fileName = str(util.ensureEndsIn(fileName, ".trelby"))

        if util.writeToFile(
            fileName, self.sp.save(), self.gd.mainFrame, backup=True
        ):
            self.setFile(fileName)
            self.sp.markChanged(False)
            self.gd.mru.add(fileName)
            self.removeRecovery()

            return True
        else:
            return False

    # write a recovery copy of the script if it has changes that haven't
    # been saved or autosaved yet (or remove it if there are no unsaved
    # changes anymore). never touches the script's real file.
    def autosave(self):
        if not self.sp.isModified():
            self.removeRecovery()

            return

        data = self.sp.save()

        if data == self.autosavedData:
            return

        try:
            autosave.writeRecovery(
                autosave.getRecoveryDir(),
                self.recoveryId,
                data,
                os.path.abspath(self.fileName) if self.fileName else None,
            )
        except OSError as e:
            # no message box, since this would repeat every interval
            self.autosaveError = e.strerror or str(e)
            self.gd.mainFrame.updateAutosaveStatus(self)

            return

        self.autosavedData = data
        self.recoveryWritten = True
        self.autosaveTime = time.time()
        self.autosaveError = None
        self.gd.mainFrame.updateAutosaveStatus(self)

    # remove the script's recovery copy, if any
    def removeRecovery(self):
        if self.recoveryWritten:
            autosave.removeRecovery(autosave.getRecoveryDir(), self.recoveryId)
            self.recoveryWritten = False

        self.autosavedData = None

        if (self.autosaveTime is not None) or (self.autosaveError is not None):
            self.autosaveTime = None
            self.autosaveError = None
            self.gd.mainFrame.updateAutosaveStatus(self)

    # import fileName as format fmt ("fdx", "celtx", "astx", "fountain",
    # "fadein" or "txt"). if fmt is None, it's guessed from the extension.
    def importFile(self, fileName, fmt=None):
        if fmt is None:
            fmt = os.path.splitext(fileName)[1].lower().lstrip(".")

        titlePages = False
        if fmt == "fdx":
            lines = myimport.importFDX(fileName, self.gd.mainFrame)
        elif fmt == "celtx":
            lines = myimport.importCeltx(fileName, self.gd.mainFrame)
        elif fmt == "astx":
            lines = myimport.importAstx(fileName, self.gd.mainFrame)
        elif fmt == "fountain":
            lines, titlePages = myimport.importFountain(
                fileName, self.gd.mainFrame, self.sp.titles.pages
            )
        elif fmt == "fadein":
            lines = myimport.importFadein(fileName, self.gd.mainFrame)
        else:
            lines = myimport.importTextFile(fileName, self.gd.mainFrame)

        if not lines:
            return

        self.createEmptySp()

        self.sp.lines = lines
        if titlePages:
            self.sp.titles.pages = titlePages
        self.sp.reformatAll()
        self.sp.paginate()
        self.sp.markChanged(True)

    # generate exportable text from given screenplay, or None.
    def getExportText(self, sp):
        inf = []
        inf.append(misc.CheckBoxItem(_("Include page markers")))

        dlg = misc.CheckBoxDlg(
            self.gd.mainFrame, _("Output options"), inf, _("Options:"), False
        )

        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()

            return None

        return sp.generateText(inf[0].selected)

    def getExportHtml(self, sp):
        inf = []
        inf.append(misc.CheckBoxItem(_("Include Notes")))

        dlg = misc.CheckBoxDlg(
            self.gd.mainFrame, _("Output options"), inf, _("Options:"), False
        )

        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()

            return None

        return sp.generateHtml(inf[0].selected)

    def setFile(self, fileName):
        self.fileName = fileName
        if fileName:
            self.setDisplayName(os.path.basename(fileName))
        else:
            self.setDisplayName("untitled")

        self.setTabText()
        self.gd.mainFrame.setTitle(self.fileNameDisplay)

    def setDisplayName(self, name):
        i = 1
        while 1:
            if i == 1:
                tmp = name
            else:
                tmp = name + "-%d" % i

            matched = False

            for c in self.gd.mainFrame.getCtrls():
                if c == self:
                    continue

                if c.fileNameDisplay == tmp:
                    matched = True

                    break

            if not matched:
                break

            i += 1

        self.fileNameDisplay = tmp

    def setTabText(self):
        self.gd.mainFrame.setTabText(self.panel, self.fileNameDisplay)

    # texts = self.gd.vm.getScreen(self, False)[0], or None, in which case it's
    # called in this function.
    def isLineVisible(self, line, texts=None):
        if texts == None:
            texts = self.gd.vm.getScreen(self, False)[0]

        # paranoia never hurts
        if len(texts) == 0:
            return False

        return (line >= texts[0].line) and (line <= texts[-1].line)

    def makeLineVisible(self, line, direction=config.SCROLL_CENTER):
        texts = self.gd.vm.getScreen(self, False)[0]

        if self.isLineVisible(line, texts):
            return

        self.gd.vm.makeLineVisible(self, line, texts, direction)

    def adjustScrollBar(self):
        height = self.GetClientSize().height

        # rough approximation of how many lines fit onto the screen.
        # accuracy is not that important for this, so we don't even care
        # about draft / layout mode differences.
        approx = int(((height / self.mm2p) / self.chY) / 1.3)

        self.panel.scrollBar.SetScrollbar(
            self.sp.getTopLine(), approx, len(self.sp.lines) + approx - 1, approx
        )

    def clearAutoComp(self):
        if self.sp.clearAutoComp():
            self.Refresh(False)

    # returns true if there are no contents at all and we're not
    # attached to any file
    def isUntouched(self):
        if (
            self.fileName
            or (len(self.sp.lines) > 1)
            or (len(self.sp.lines[0].text) > 0)
        ):
            return False
        else:
            return True

    def updateScreen(self, redraw=True, setCommon=True):
        self.adjustScrollBar()

        if setCommon:
            self.updateCommon()

        if redraw:
            self.Refresh(False)

    # update GUI elements shared by all scripts, like statusbar etc
    def updateCommon(self):
        cur = self.gd.cfgGl.getType(self.sp.lines[self.sp.line].lt)

        if self.sp.tabMakesNew():
            tabNext = "%s" % self.gd.cfgGl.getType(cur.newTypeTab).ti.name
        else:
            tabNext = "%s" % self.gd.cfgGl.getType(cur.nextTypeTab).ti.name

        enterNext = self.gd.cfgGl.getType(cur.newTypeEnter).ti.name

        page = self.sp.line2pageLabel(self.sp.line)
        pageCnt = self.sp.line2page(len(self.sp.lines) - 1)

        self.gd.mainFrame.setElemTypeStatus(cur.lt, tabNext, enterNext)
        self.gd.mainFrame.setPageStatus(page, pageCnt, self.sp.hasPageLocks())
        self.gd.mainFrame.setLengthStatus(
            self.sp.getWordCount(), self.sp.getPageLength()
        )

        canUndo = self.sp.canUndo()
        canRedo = self.sp.canRedo()

        self.gd.mainFrame.menuBar.Enable(ID_EDIT_UNDO, canUndo)
        self.gd.mainFrame.menuBar.Enable(ID_EDIT_REDO, canRedo)

        self.gd.mainFrame.toolBar.EnableTool(ID_EDIT_UNDO, canUndo)
        self.gd.mainFrame.toolBar.EnableTool(ID_EDIT_REDO, canRedo)

        self.panel.outline.scheduleRefresh()

    # apply per-script config
    def applyCfg(self, newCfg):
        self.sp.applyCfg(newCfg)

        self.refreshCache()
        self.makeLineVisible(self.sp.line)
        self.updateScreen()

    # apply global config
    def applyGlobalCfg(self, newCfgGl, writeCfg=True):

        oldCfgGl = self.gd.cfgGl

        self.gd.cfgGl = copy.deepcopy(newCfgGl)

        # if user has ventured from the old default directory, keep it as
        # the current one, otherwise set the new default as current.
        if misc.scriptDir == oldCfgGl.scriptDir:
            misc.scriptDir = self.gd.cfgGl.scriptDir

        # must be done before refreshGuiConfig, since the screen colors
        # depend on whether the theme is dark.
        appearanceChanged = self.gd.cfgGl.appearance != oldCfgGl.appearance

        if appearanceChanged:
            config.applyAppearance(self.gd.cfgGl.appearance)

        self.gd.cfgGl.recalc()
        self.refreshGuiConfig()
        self.gd.mainFrame.updateKbdCommands()

        for c in self.gd.mainFrame.getCtrls():
            c.sp.cfgGl = self.gd.cfgGl
            c.refreshCache()
            c.makeLineVisible(c.sp.line)
            c.adjustScrollBar()

        self.updateScreen()

        # in case tab colors have been changed
        self.gd.mainFrame.tabCtrl.Refresh(False)
        self.gd.mainFrame.elemTypeBar.Refresh(False)
        self.gd.mainFrame.noFSBtn.Refresh(False)
        self.gd.mainFrame.toolBar.SetBackgroundColour(self.gd.cfgGui.tabBarBgColor)
        self.gd.mainFrame.toolBar.Refresh()

        # the toolbar icons' color depends on the theme
        if appearanceChanged or (
            self.gd.cfgGl.toolbarIconSize != oldCfgGl.toolbarIconSize
        ):
            self.gd.mainFrame.fillToolBar()
            self.gd.mainFrame.SendSizeEvent()
            self.updateCommon()

        if self.gd.cfgGl.autosaveInterval != oldCfgGl.autosaveInterval:
            self.gd.mainFrame.updateAutosaveTimer()

        if writeCfg:
            util.writeToFile(
                self.gd.confFilename, self.gd.cfgGl.save(), self.gd.mainFrame
            )

        self.gd.mainFrame.checkFonts()

    def applyHeaders(self, newHeaders):
        self.sp.headers = newHeaders
        self.sp.markChanged()
        self.OnPaginate()

    # return an exportable, paginated Screenplay object, or None if for
    # some reason that's not possible / wanted. 'action' is the name of
    # the action, e.g. "export" or "compare", that'll be done to the script,
    # and is used in dialogue with the user if needed.
    def getExportable(self, action):
        if self.gd.cfgGl.checkOnExport and not self.confirmExportable(action):
            return None

        sp = self.sp
        if sp.cfg.pdfRemoveNotes:
            sp = copy.deepcopy(self.sp)
            sp.removeElementTypes({screenplay.NOTE: None}, False)

        sp.paginate()

        return sp

    # check the script before 'action' ("export" or "compare") is done to
    # it. if it's empty or has an error, ask whether to continue anyway,
    # offering to show the error. returns True if we should continue.
    def confirmExportable(self, action):
        anyway = {"export": _("Export Anyway"), "compare": _("Compare Anyway")}[
            action
        ]

        if not any(ln.text.strip() for ln in self.sp.lines):
            dlg = wx.MessageDialog(
                self.gd.mainFrame,
                _("\"{}\" is empty.").format(self.fileNameDisplay),
                _("Empty Script"),
                wx.OK | wx.CANCEL | wx.CANCEL_DEFAULT | wx.ICON_INFORMATION,
            )
            dlg.SetExtendedMessage(_("There is no text in the script yet."))
            dlg.SetOKCancelLabels(anyway, wx.ID_CANCEL)
            ret = dlg.ShowModal()
            dlg.Destroy()

            return ret == wx.ID_OK

        line, msg = self.sp.findError(0)

        if line == -1:
            return True

        dlg = wx.MessageDialog(
            self.gd.mainFrame,
            _("\"{}\" has a problem on page {}.").format(
                self.fileNameDisplay, self.sp.line2pageLabel(line)
            ),
            _("Script Problem"),
            wx.YES_NO | wx.CANCEL | wx.CANCEL_DEFAULT | wx.ICON_WARNING,
        )
        dlg.SetExtendedMessage(msg)
        dlg.SetYesNoCancelLabels(anyway, _("Go to Problem"), wx.ID_CANCEL)
        ret = dlg.ShowModal()
        dlg.Destroy()

        if ret == wx.ID_NO:
            mf = self.gd.mainFrame
            page = mf.findPage(self.panel)
            if page != -1:
                mf.tabCtrl.selectPage(page)

            self.clearAutoComp()
            self.sp.line = line
            self.sp.column = 0
            self.makeLineVisible(line)
            self.updateScreen()

        return ret == wx.ID_YES

    def OnEraseBackground(self, event):
        pass

    def OnSize(self, event):
        size = self.GetClientSize()

        # we can briefly be zero-sized while the outline view's splitter
        # lays us out, and wx can't create empty bitmaps
        if misc.doDblBuf and (size.width > 0) and (size.height > 0):
            sb = wx.Bitmap(size.width, size.height)
            old = getattr(self.__class__, "screenBuf", None)

            if (
                (old == None)
                or (old.GetDepth() != sb.GetDepth())
                or (old.GetHeight() != sb.GetHeight())
                or (old.GetWidth() != sb.GetWidth())
            ):
                self.__class__.screenBuf = sb

        self.makeLineVisible(self.sp.line)

    def OnLeftDown(self, event, mark=False):
        if not mark and self.isTripleClick(event.GetPosition()):
            self.lastDClick = None
            self.selectByClick(event, False)

            return

        if not mark:
            self.clickSelectActive = False

        if not self.mouseSelectActive:
            self.sp.clearMark()
            self.updateScreen()

        pos = event.GetPosition()
        line, col = self.gd.vm.pos2linecol(self, pos.x, pos.y)

        self.mouseSelectActive = True

        if line is not None:
            self.sp.gotoPos(line, col, mark)
            self.updateScreen()

    def OnLeftDClick(self, event):
        self.lastDClick = (time.monotonic(), event.GetPosition())
        self.selectByClick(event, True)

    # True if a click at pos follows the last double click closely enough,
    # in time and space, to make it a triple click.
    def isTripleClick(self, pos):
        if not self.lastDClick:
            return False

        t, dpos = self.lastDClick

        ms = wx.SystemSettings.GetMetric(wx.SYS_DCLICK_MSEC)
        dx = wx.SystemSettings.GetMetric(wx.SYS_DCLICK_X)
        dy = wx.SystemSettings.GetMetric(wx.SYS_DCLICK_Y)

        # metrics are -1 if the platform doesn't report them
        ms = ms if ms > 0 else 500
        dx = dx if dx > 0 else 4
        dy = dy if dy > 0 else 4

        return (
            ((time.monotonic() - t) * 1000 <= ms)
            and (abs(pos.x - dpos.x) <= dx)
            and (abs(pos.y - dpos.y) <= dy)
        )

    # select the word (isWord) or element under the mouse.
    def selectByClick(self, event, isWord):
        pos = event.GetPosition()
        line, col = self.gd.vm.pos2linecol(self, pos.x, pos.y)

        if line is None:
            return

        if isWord:
            self.sp.selectWordAt(line, col)
        else:
            self.sp.selectElementAt(line)

        self.mouseSelectActive = True
        self.clickSelectActive = True
        self.updateScreen()

    def OnLeftUp(self, event):
        self.mouseSelectActive = False

        # a double/triple click selection is deliberate, even if it's
        # just one character
        if self.clickSelectActive:
            self.clickSelectActive = False

            return

        # to avoid phantom selections (Windows sends some strange events
        # sometimes), check if anything worthwhile is actually selected.
        cd = self.sp.getSelectedAsCD(False)

        if not cd or ((len(cd.lines) == 1) and (len(cd.lines[0].text) < 2)):
            self.sp.clearMark()

    def OnMotion(self, event):
        if event.LeftIsDown() and not self.clickSelectActive:
            self.OnLeftDown(event, mark=True)

    def OnRightDown(self, event):
        pos = event.GetPosition()
        line, col = self.gd.vm.pos2linecol(self, pos.x, pos.y)

        if not self.sp.mark and line is not None and (line != self.sp.line):
            self.sp.gotoPos(line, col, False)
            self.updateScreen()

        # type changes apply to every element in the selection, if any
        marked = self.sp.getMarkedLines()

        if marked:
            first, last = marked
        else:
            first = last = self.sp.line

        types = {self.sp.lines[i].lt for i in range(first, last + 1)}
        curLt = types.pop() if len(types) == 1 else None

        m = self.gd.mainFrame.makeRightClickMenu(curLt, bool(self.sp.mark))
        self.PopupMenu(m)
        m.Destroy()

    def OnMouseWheel(self, event):
        if event.ControlDown():
            if event.GetWheelRotation() > 0:
                self.gd.mainFrame.OnZoomIn()
            elif event.GetWheelRotation() < 0:
                self.gd.mainFrame.OnZoomOut()

            return

        if event.GetWheelRotation() > 0:
            delta = -self.gd.cfgGl.mouseWheelLines
        else:
            delta = self.gd.cfgGl.mouseWheelLines

        self.sp.setTopLine(self.sp.getTopLine() + delta)
        self.updateScreen()

    def OnScroll(self, event):
        pos = self.panel.scrollBar.GetThumbPosition()
        self.sp.setTopLine(pos)
        self.sp.clearAutoComp()
        self.updateScreen()

    def OnPaginate(self):
        self.sp.paginate()
        self.makeLineVisible(self.sp.line)
        self.updateScreen()

    def OnLockPages(self):
        self.sp.lockPages()
        self.makeLineVisible(self.sp.line)
        self.updateScreen()

    def OnUnlockPages(self):
        self.sp.unlockPages()
        self.makeLineVisible(self.sp.line)
        self.updateScreen()

    def OnAutoCompletionDlg(self):
        dlg = autocompletiondlg.AutoCompletionDlg(
            self.gd.mainFrame, copy.deepcopy(self.sp.autoCompletion)
        )

        if dlg.ShowModal() == wx.ID_OK:
            self.sp.autoCompletion = dlg.autoCompletion
            self.sp.markChanged()

        dlg.Destroy()

    def OnTitlesDlg(self):
        dlg = titlesdlg.TitlesDlg(
            self.gd.mainFrame, copy.deepcopy(self.sp.titles), self.sp.cfg, self.gd.cfgGl
        )

        if dlg.ShowModal() == wx.ID_OK:
            self.sp.titles = dlg.titles
            self.sp.markChanged()

        dlg.Destroy()

    def OnHeadersDlg(self):
        dlg = headersdlg.HeadersDlg(
            self.gd.mainFrame,
            copy.deepcopy(self.sp.headers),
            self.sp.cfg,
            self.gd.cfgGl,
            self.applyHeaders,
        )

        if dlg.ShowModal() == wx.ID_OK:
            self.applyHeaders(dlg.headers)

        dlg.Destroy()

    def OnLocationsDlg(self):
        dlg = locationsdlg.LocationsDlg(self.gd.mainFrame, copy.deepcopy(self.sp))

        if dlg.ShowModal() == wx.ID_OK:
            self.sp.locations = dlg.sp.locations
            self.sp.markChanged()

        dlg.Destroy()

    def OnCharacterProfilesDlg(self):
        ls = self.sp.lines

        # start with the character whose name or speech the cursor is on
        i = self.sp.line
        while (i > 0) and (ls[i].lt in (screenplay.DIALOGUE, screenplay.PAREN)):
            i -= 1

        selectName = ls[i].text if ls[i].lt == screenplay.CHARACTER else None

        old = self.sp.characterProfiles.save()

        dlg = characterprofilesdlg.CharacterProfilesDlg(
            self.gd.mainFrame,
            copy.deepcopy(self.sp.characterProfiles),
            self.sp.getCharacterNames(),
            selectName,
        )

        if dlg.ShowModal() == wx.ID_OK:
            if dlg.charProfiles.save() != old:
                self.sp.characterProfiles = dlg.charProfiles
                self.sp.markChanged()

            # renaming a character's profile renames the character
            # everywhere in the script too
            if dlg.renames and any(self.sp.renameCharacters(dlg.renames)):
                self.sp.paginate()
                self.makeLineVisible(self.sp.line)
                self.updateScreen()

        dlg.Destroy()

    def OnSpellCheckerScriptDictionaryDlg(self):
        dlg = spellcheckcfgdlg.SCDictDlg(
            self.gd.mainFrame, copy.deepcopy(self.sp.scDict), False
        )

        if dlg.ShowModal() == wx.ID_OK:
            self.sp.scDict = dlg.scDict
            self.sp.markChanged()

        dlg.Destroy()

    def OnWatermark(self):
        dlg = watermarkdlg.WatermarkDlg(
            self.gd.mainFrame, self.sp, self.fileNameDisplay.replace(".trelby", "")
        )
        dlg.ShowModal()
        dlg.Destroy()

    def OnReportDialogueChart(self):
        self.sp.paginate()
        dialoguechart.genDialogueChart(self.gd.mainFrame, self.sp, self.fileNameDisplay)

    def OnReportCharacter(self):
        self.sp.paginate()
        reports.genCharacterReport(self.gd.mainFrame, self.sp, self.fileNameDisplay)

    def OnReportLocation(self):
        self.sp.paginate()
        reports.genLocationReport(self.gd.mainFrame, self.sp, self.fileNameDisplay)

    def OnReportScene(self):
        self.sp.paginate()
        reports.genSceneReport(self.gd.mainFrame, self.sp, self.fileNameDisplay)

    def OnReportScript(self):
        self.sp.paginate()
        reports.genScriptReport(self.gd.mainFrame, self.sp, self.fileNameDisplay)

    def OnCompareScripts(self):
        if self.gd.mainFrame.tabCtrl.getPageCount() < 2:
            wx.MessageBox(
                _("You need at least two scripts open to compare them."),
                _("Error"),
                wx.OK,
                self.gd.mainFrame,
            )

            return

        items = []
        for c in self.gd.mainFrame.getCtrls():
            items.append(c.fileNameDisplay)

        dlg = misc.ScriptChooserDlg(self.gd.mainFrame, items)

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
                self.gd.mainFrame,
            )

            return

        c1 = self.gd.mainFrame.tabCtrl.getPage(sel1).ctrl
        c2 = self.gd.mainFrame.tabCtrl.getPage(sel2).ctrl

        sp1 = c1.getExportable("compare")
        sp2 = c2.getExportable("compare")

        if not sp1 or not sp2:
            return

        if force:
            sp2 = copy.deepcopy(sp2)
            sp2.cfg = copy.deepcopy(sp1.cfg)
            sp2.reformatAll()
            sp2.paginate()

        s = sp1.compareScripts(sp2)

        if s:
            gutil.showTempPDF(s, self.gd.cfgGl, self.gd.mainFrame)
        else:
            wx.MessageBox(
                _("The scripts are identical."), _("Results"), wx.OK, self.gd.mainFrame
            )

    def canBeClosed(self):
        if self.sp.isModified():
            if (
                wx.MessageBox(
                    _(
                        "The script has been modified. Are you sure\nyou want to discard the changes?"
                    ),
                    _("Confirm"),
                    wx.YES_NO | wx.NO_DEFAULT,
                    self.gd.mainFrame,
                )
                == wx.NO
            ):
                return False

        return True

    # page up (dir == -1) or page down (dir == 1) was pressed, handle it.
    # cs = CommandState.
    def pageCmd(self, cs, dir):
        if self.sp.acItems:
            cs.doAutoComp = cs.AC_KEEP
            self.sp.pageScrollAutoComp(dir)

            return

        texts, dpages = self.gd.vm.getScreen(self, False)

        # if user has scrolled with scrollbar so that cursor isn't seen,
        # just make cursor visible and don't move
        if not self.isLineVisible(self.sp.line, texts):
            self.gd.vm.makeLineVisible(self, self.sp.line, texts)
            cs.needsVisifying = False

            return

        self.sp.maybeMark(cs.mark)
        self.gd.vm.pageCmd(self, cs, dir, texts, dpages)

    def OnRevertScript(self):
        if self.fileName:
            if not self.canBeClosed():
                return

            self.loadFile(self.fileName)
            self.updateScreen()

    def OnUndo(self):
        self.sp.cmd("undo")
        self.sp.paginate()
        self.makeLineVisible(self.sp.line)
        self.updateScreen()

    def OnRedo(self):
        self.sp.cmd("redo")
        self.sp.paginate()
        self.makeLineVisible(self.sp.line)
        self.updateScreen()

    # returns True if something was deleted
    def OnCut(self, doUpdate=True, doDelete=True, copyToClip=True):
        marked = self.sp.getMarkedLines()

        if not marked:
            return False

        cd = self.sp.getSelectedAsCD(doDelete)

        if copyToClip:
            self.gd.mainFrame.clipboard = cd

        if doUpdate:
            self.makeLineVisible(self.sp.line)
            self.updateScreen()

        return doDelete

    def OnCopy(self):
        self.OnCut(doDelete=False)

    def OnCopySystem(self, formatted=False):
        cd = self.sp.getSelectedAsCD(False)

        if not cd:
            return

        tmpSp = screenplay.Screenplay(self.gd.cfgGl)
        tmpSp.lines = cd.lines

        if formatted:
            # have to call paginate, otherwise generateText will not
            # process all the text
            tmpSp.paginate()
            s = tmpSp.generateText(False)
        else:
            s = util.String()

            for ln in tmpSp.lines:
                txt = ln.text

                if tmpSp.cfg.getType(ln.lt).export.isCaps:
                    txt = util.upper(txt)

                s += txt + config.lb2str(ln.lb)

            s = str(s).replace("\n", os.linesep)

        if wx.TheClipboard.Open():
            wx.TheClipboard.UsePrimarySelection(False)

            wx.TheClipboard.Clear()
            wx.TheClipboard.AddData(wx.TextDataObject(s))
            wx.TheClipboard.Flush()

            wx.TheClipboard.Close()

    def OnPaste(self, clines=None):
        if not clines:
            cd = self.gd.mainFrame.clipboard

            if not cd:
                return

            clines = cd.lines

        self.sp.paste(clines)

        self.makeLineVisible(self.sp.line)
        self.updateScreen()

    def OnPasteSystemCb(self):
        s = ""

        if wx.TheClipboard.Open():
            wx.TheClipboard.UsePrimarySelection(False)

            df = wx.DataFormat(wx.DF_TEXT)

            if wx.TheClipboard.IsSupported(df):
                data = wx.TextDataObject()
                wx.TheClipboard.GetData(data)
                s = util.cleanInput(data.GetText())

            wx.TheClipboard.Close()

        s = util.fixNL(s)

        if len(s) == 0:
            return

        inLines = s.split("\n")

        # shouldn't be possible, but...
        if len(inLines) == 0:
            return

        lines = []

        for s in inLines:
            if s:
                lines.append(Line(screenplay.LB_LAST, screenplay.ACTION, s))

        self.OnPaste(lines)

    def OnSelectScene(self):
        self.sp.cmd("selectScene")

        self.makeLineVisible(self.sp.line)
        self.updateScreen()

    def OnSelectAll(self):
        self.sp.cmd("selectAll")

        self.makeLineVisible(self.sp.line)
        self.updateScreen()

    def OnGotoScene(self):
        self.sp.paginate()
        self.clearAutoComp()

        scenes = self.sp.getSceneLocations()

        def validateFunc(s):
            if s in [x[0] for x in scenes]:
                return ""
            else:
                return _("Invalid scene number.")

        dlg = misc.TextInputDlg(
            self.gd.mainFrame,
            _("Enter scene number ({} - {}):".format(scenes[0][0], scenes[-1][0])),
            _("Goto scene"),
            validateFunc,
        )

        if dlg.ShowModal() == wx.ID_OK:
            for it in scenes:
                if it[0] == dlg.input:
                    self.sp.line = it[1]
                    self.sp.column = 0

                    break

        # we need to refresh the screen in all cases because pagination
        # might have changed
        self.makeLineVisible(self.sp.line)
        self.updateScreen()

    # move the cursor to the start of the given line and scroll it to the
    # top of the screen. used by the outline view.
    def gotoLine(self, line):
        self.clearAutoComp()
        self.sp.clearMark()
        self.sp.gotoPos(line, 0)

        self.sp.setTopLine(line)
        self.makeLineVisible(line)
        self.updateScreen()

    # move the scene containing the given line to position newIndex in the
    # outline. used by the outline view.
    def moveSceneTo(self, line, newIndex):
        self.clearAutoComp()

        if not self.sp.moveSceneTo(line, newIndex):
            return

        self.sp.paginate()
        self.sp.setTopLine(self.sp.line)
        self.makeLineVisible(self.sp.line)
        self.updateScreen()

    def OnGotoPage(self):
        self.sp.paginate()
        self.clearAutoComp()

        pages = self.sp.getPageNumbers()

        def validateFunc(s):
            if self.sp.label2page(s) != -1:
                return ""
            else:
                return _("Invalid page number.")

        dlg = misc.TextInputDlg(
            self.gd.mainFrame,
            _("Enter page number ({} - {}):".format(pages[0], pages[-1])),
            _("Goto page"),
            validateFunc,
        )

        if dlg.ShowModal() == wx.ID_OK:
            page = self.sp.label2page(dlg.input)
            self.sp.line = self.sp.page2lines(page)[0]
            self.sp.column = 0

        # we need to refresh the screen in all cases because pagination
        # might have changed
        self.makeLineVisible(self.sp.line)
        self.updateScreen()

    def OnInsertNbsp(self):
        self.OnKeyChar(util.MyKeyEvent(160))

    def OnFindNextError(self):
        self.clearAutoComp()

        line, msg = self.sp.findError(self.sp.line)

        if line != -1:
            self.sp.line = line
            self.sp.column = 0

            self.makeLineVisible(self.sp.line)
            self.updateScreen()

        else:
            msg = _("No errors found.")

        wx.MessageBox(msg, _("Results"), wx.OK, self.gd.mainFrame)

    def OnFind(self):
        self.sp.clearMark()
        self.clearAutoComp()
        self.updateScreen()

        dlg = finddlg.FindDlg(self.gd.mainFrame, self)
        dlg.ShowModal()
        dlg.saveState()
        dlg.Destroy()

        self.sp.clearMark()
        self.makeLineVisible(self.sp.line)
        self.updateScreen()

    def OnSpellCheckerDlg(self):
        self.sp.clearMark()
        self.clearAutoComp()

        wasAtStart = self.sp.line == 0

        wx.BeginBusyCursor()

        if not spellcheck.loadDict(self.gd.mainFrame):
            wx.EndBusyCursor()

            return

        sc = spellcheck.SpellChecker(self.sp, self.gd.scDict)
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
                self.gd.mainFrame,
            )

            return

        dlg = spellcheckdlg.SpellCheckDlg(self.gd.mainFrame, self, sc, self.gd.scDict)
        dlg.ShowModal()

        if dlg.changedGlobalDict:
            self.gd.saveScDict()

        dlg.Destroy()

        self.sp.clearMark()
        self.makeLineVisible(self.sp.line)
        self.updateScreen()

    def OnDeleteElements(self):
        # even though Screenplay.removeElementTypes does this as well, do
        # it here so that screen is cleared from the auto-comp box before
        # we open the dialog
        self.clearAutoComp()

        types = []
        for t in config.getTIs():
            types.append(misc.CheckBoxItem(t.name, False, t.lt))

        dlg = misc.CheckBoxDlg(
            self.gd.mainFrame,
            _("Delete elements"),
            types,
            _("Element types to delete:"),
            True,
        )

        ok = False
        if dlg.ShowModal() == wx.ID_OK:
            ok = True

            tdict = misc.CheckBoxItem.getClientData(types)

        dlg.Destroy()

        if not ok or (len(tdict) == 0):
            return

        self.sp.removeElementTypes(tdict, True)
        self.sp.paginate()
        self.makeLineVisible(self.sp.line)
        self.updateScreen()

    def OnSave(self):
        if self.fileName:
            self.saveFile(self.fileName)
        else:
            self.OnSaveScriptAs()

    def OnSaveScriptAs(self):
        if self.fileName:
            dDir = os.path.dirname(self.fileName)
            dFile = os.path.basename(self.fileName)
        else:
            dDir = misc.scriptDir
            dFile = ""

        dlg = wx.FileDialog(
            self.gd.mainFrame,
            _("Filename to save as"),
            defaultDir=dDir,
            defaultFile=dFile,
            wildcard="Trelby files (*.trelby)|*.trelby|All files|*",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        )
        if dlg.ShowModal() == wx.ID_OK:
            self.saveFile(dlg.GetPath())

        dlg.Destroy()

    # export the script in format 'fmt', which is the file suffix
    # without the dot ("pdf", "rtf", "fdx", "html", "fountain" or "txt").
    def OnExportScript(self, fmt):
        name, generate = {
            "pdf": ("PDF", lambda sp: sp.generatePDF()),
            "rtf": ("RTF", lambda sp: sp.generateRTF()),
            "fdx": ("Final Draft XML", lambda sp: sp.generateFDX()),
            "html": ("HTML", self.getExportHtml),
            "fountain": ("Fountain", lambda sp: sp.generateFountain()),
            "txt": (_("Formatted text"), self.getExportText),
        }[fmt]

        sp = self.getExportable("export")
        if not sp:
            return

        suffix = "." + fmt

        dlg = wx.FileDialog(
            self.gd.mainFrame,
            _("Filename to export as"),
            misc.scriptDir,
            wildcard="%s (*%s)|*%s" % (name, suffix, suffix),
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        )

        if dlg.ShowModal() == wx.ID_OK:
            misc.scriptDir = dlg.GetDirectory()

            data = generate(sp)
            fileName = util.ensureEndsIn(dlg.GetPath(), suffix)

            if data:
                util.writeToFile(fileName, data, self.gd.mainFrame)

        dlg.Destroy()

    def OnSettings(self):
        dlg = cfgdlg.CfgDlg(
            self.gd.mainFrame,
            copy.deepcopy(self.gd.cfgGl),
            self.applyGlobalCfg,
            True,
            self.gd,
        )

        if dlg.ShowModal() == wx.ID_OK:
            self.applyGlobalCfg(dlg.cfg)

        dlg.Destroy()

    def OnScriptSettings(self):
        dlg = cfgdlg.CfgDlg(
            self.gd.mainFrame,
            copy.deepcopy(self.sp.cfg),
            self.applyCfg,
            False,
            self.gd,
        )

        if dlg.ShowModal() == wx.ID_OK:
            self.applyCfg(dlg.cfg)

        dlg.Destroy()

    def cmdAbort(self, cs):
        self.sp.abortCmd(cs)

    def cmdChangeToAction(self, cs):
        self.sp.toActionCmd(cs)

    def cmdChangeToCharacter(self, cs):
        self.sp.toCharacterCmd(cs)

    def cmdChangeToDialogue(self, cs):
        self.sp.toDialogueCmd(cs)

    def cmdChangeToNote(self, cs):
        self.sp.toNoteCmd(cs)

    def cmdChangeToParenthetical(self, cs):
        self.sp.toParenCmd(cs)

    def cmdChangeToScene(self, cs):
        self.sp.toSceneCmd(cs)

    def cmdChangeToShot(self, cs):
        self.sp.toShotCmd(cs)

    def cmdChangeToActBreak(self, cs):
        self.sp.toActBreakCmd(cs)

    def cmdChangeToTransition(self, cs):
        self.sp.toTransitionCmd(cs)

    def cmdDelete(self, cs):
        if not self.sp.mark:
            self.sp.deleteForwardCmd(cs)
        else:
            self.OnCut(doUpdate=False, copyToClip=False)

    def cmdDeleteBackward(self, cs):
        if not self.sp.mark:
            self.sp.deleteBackwardCmd(cs)
        else:
            self.OnCut(doUpdate=False, copyToClip=False)

    def cmdForcedLineBreak(self, cs):
        self.sp.insertForcedLineBreakCmd(cs)

    def cmdMoveDown(self, cs):
        self.sp.moveDownCmd(cs)

    def cmdMoveEndOfLine(self, cs):
        self.sp.moveLineEndCmd(cs)

    def cmdMoveEndOfScript(self, cs):
        self.sp.moveEndCmd(cs)

    def cmdMoveLeft(self, cs):
        self.sp.moveLeftCmd(cs)

    def cmdMoveNextWord(self, cs):
        self.sp.moveNextWordCmd(cs)

    def cmdMovePageDown(self, cs):
        self.pageCmd(cs, 1)

    def cmdMovePageUp(self, cs):
        self.pageCmd(cs, -1)

    def cmdMovePrevWord(self, cs):
        self.sp.movePrevWordCmd(cs)

    def cmdMoveRight(self, cs):
        self.sp.moveRightCmd(cs)

    def cmdMoveSceneDown(self, cs):
        self.sp.moveSceneDownCmd(cs)

    def cmdMoveSceneUp(self, cs):
        self.sp.moveSceneUpCmd(cs)

    def cmdMoveStartOfLine(self, cs):
        self.sp.moveLineStartCmd(cs)

    def cmdMoveStartOfScript(self, cs):
        self.sp.moveStartCmd(cs)

    def cmdMoveUp(self, cs):
        self.sp.moveUpCmd(cs)

    def cmdNewElement(self, cs):
        self.sp.splitElementCmd(cs)

    def cmdSetMark(self, cs):
        self.sp.setMarkCmd(cs)

    def cmdTab(self, cs):
        self.sp.tabCmd(cs)

    def cmdTabPrev(self, cs):
        self.sp.toPrevTypeTabCmd(cs)

    def cmdSpeedTest(self, cs):
        import undo

        self.speedTestUndo = []

        def testUndoFullCopy():
            u = undo.FullCopy(self.sp)
            u.setAfter(self.sp)
            self.speedTestUndo.append(u)

        def testReformatAll():
            self.sp.reformatAll()

        def testPaginate():
            self.sp.paginate()

        def testUpdateScreen():
            self.updateScreen()
            self.Update()

        def testAddRemoveChar():
            self.OnKeyChar(util.MyKeyEvent(ord("a")))
            self.OnKeyChar(util.MyKeyEvent(wx.WXK_BACK))

        def testDeepcopy():
            copy.deepcopy(self.sp)

        # contains (name, func) tuples
        tests = []

        for name, var in locals().items():
            if callable(var):
                tests.append((name, var))

        tests.sort()
        count = 100

        print(("-" * 20))

        for name, func in tests:
            t = time.time()

            for i in range(count):
                func()

            t = time.time() - t

            print(_("{.5f} seconds per {}".format(t / count, name)))

        print("-" * 20)

        # it's annoying having the program ask if you want to save after
        # running these tests, so pretend the script hasn't changed
        self.sp.markChanged(False)

    def cmdTest(self, cs):
        pass

    def OnKeyChar(self, ev):
        kc = ev.GetUnicodeKey()

        cs = screenplay.CommandState()
        cs.mark = bool(ev.ShiftDown())
        scrollDirection = config.SCROLL_CENTER

        if not ev.ControlDown() and not ev.AltDown() and util.isValidInputChar(kc):
            # WX2.6-FIXME: we should probably use GetUnicodeKey() (dunno
            # how to get around the isValidInputChar test in the preceding
            # line, need to test what GetUnicodeKey() returns on
            # non-input-character events)

            addChar = True

            # If there's something selected, either remove it, or clear selection.
            if self.sp.mark and self.gd.cfgGl.overwriteSelectionOnInsert:
                if not self.OnCut(doUpdate=False, copyToClip=False):
                    self.sp.clearMark()
                    addChar = False

            if addChar:
                cs.char = chr(kc)

                if opts.isTest and (cs.char == "�"):
                    self.loadFile("sample.trelby")
                elif opts.isTest and (cs.char == "�"):
                    self.cmdTest(cs)
                elif opts.isTest and (cs.char == "�"):
                    self.cmdSpeedTest(cs)
                else:
                    self.sp.addCharCmd(cs)

        else:
            cmd = self.gd.mainFrame.kbdCommands.get(
                util.Key(kc, ev.ControlDown(), ev.AltDown(), ev.ShiftDown()).toInt()
            )

            if cmd:
                scrollDirection = cmd.scrollDirection
                if cmd.isMenu:
                    getattr(self.gd.mainFrame, "On" + cmd.name)()
                    return
                else:
                    getattr(self, "cmd" + cmd.name)(cs)
            else:
                ev.Skip()
                return

        self.sp.cmdPost(cs)

        if self.gd.cfgGl.paginateInterval > 0:
            now = time.time()

            if (now - self.sp.lastPaginated) >= self.gd.cfgGl.paginateInterval:
                self.sp.paginate()

                cs.needsVisifying = True

        if cs.needsVisifying:
            self.makeLineVisible(self.sp.line, scrollDirection)

        self.updateScreen()

    def OnPaint(self, event):
        # ldkjfldsj = util.TimerDev("paint")

        ls = self.sp.lines

        if misc.doDblBuf:
            dc = wx.BufferedPaintDC(self, self.screenBuf)
        else:
            dc = wx.PaintDC(self)

        size = self.GetClientSize()
        marked = self.sp.getMarkedLines()
        lineh = self.gd.vm.getLineHeight(self)
        posX = -1
        cursorY = -1

        # auto-comp FontInfo
        acFi = None

        # key = font, value = ([text, ...], [(x, y), ...], [wx.Colour, ...])
        texts = []

        # lists of underline-lines to draw, one for normal text and one
        # for header texts. list objects are (x, y, width) tuples.
        ulines = []
        ulinesHdr = []

        strings, dpages = self.gd.vm.getScreen(self, True, True)

        dc.SetBrush(self.gd.cfgGui.workspaceBrush)
        dc.SetPen(self.gd.cfgGui.workspacePen)
        dc.DrawRectangle(0, 0, size.width, size.height)

        dc.SetPen(self.gd.cfgGui.tabBorderPen)
        dc.DrawLine(0, 0, 0, size.height)

        if not dpages:
            # draft mode; draw an infinite page
            lx = util.clamp((size.width - self.pageW) // 2, 0)
            rx = lx + self.pageW

            dc.SetBrush(self.gd.cfgGui.textBgBrush)
            dc.SetPen(self.gd.cfgGui.textBgPen)
            dc.DrawRectangle(lx, 5, self.pageW, size.height - 5)

            dc.SetPen(self.gd.cfgGui.pageBorderPen)
            dc.DrawLine(lx, 5, lx, size.height)
            dc.DrawLine(rx, 5, rx, size.height)

        else:
            dc.SetBrush(self.gd.cfgGui.textBgBrush)
            dc.SetPen(self.gd.cfgGui.pageBorderPen)
            for dp in dpages:
                dc.DrawRectangle(dp.x1, dp.y1, dp.x2 - dp.x1 + 1, dp.y2 - dp.y1 + 1)

            dc.SetPen(self.gd.cfgGui.pageShadowPen)
            for dp in dpages:
                # + 2 because DrawLine doesn't draw to end point but stops
                # one pixel short...
                dc.DrawLine(dp.x1 + 1, dp.y2 + 1, dp.x2 + 1, dp.y2 + 1)
                dc.DrawLine(dp.x2 + 1, dp.y1 + 1, dp.x2 + 1, dp.y2 + 2)

        for t in strings:
            i = t.line
            y = t.y
            fi = t.fi
            fx = fi.fx

            if i != -1:
                l = ls[i]

                if l.lt == screenplay.NOTE:
                    dc.SetPen(self.gd.cfgGui.notePen)
                    dc.SetBrush(self.gd.cfgGui.noteBrush)

                    nx = t.x - 5
                    nw = self.sp.cfg.getType(l.lt).width * fx + 10

                    dc.DrawRectangle(nx, y, nw, lineh)

                    dc.SetPen(self.gd.cfgGui.textPen)
                    util.drawLine(dc, nx - 1, y, 0, lineh)
                    util.drawLine(dc, nx + nw, y, 0, lineh)

                    if self.sp.isFirstLineOfElem(i):
                        util.drawLine(dc, nx - 1, y - 1, nw + 2, 0)

                    if self.sp.isLastLineOfElem(i):
                        util.drawLine(dc, nx - 1, y + lineh, nw + 2, 0)

                if marked and self.sp.isLineMarked(i, marked):
                    c1, c2 = self.sp.getMarkedColumns(i, marked)

                    dc.SetPen(self.gd.cfgGui.selectedPen)
                    dc.SetBrush(self.gd.cfgGui.selectedBrush)

                    dc.DrawRectangle(t.x + c1 * fx, y, (c2 - c1 + 1) * fx, lineh)

                if self.gd.mainFrame.showFormatting:
                    dc.SetPen(self.gd.cfgGui.bluePen)
                    util.drawLine(dc, t.x, y, 0, lineh)

                    extraIndent = 1 if self.sp.needsExtraParenIndent(i) else 0

                    util.drawLine(
                        dc,
                        t.x + (self.sp.cfg.getType(l.lt).width - extraIndent) * fx,
                        y,
                        0,
                        lineh,
                    )

                    dc.SetTextForeground(self.gd.cfgGui.redColor)
                    dc.SetFont(self.gd.cfgGui.fonts[pml.NORMAL].font)
                    dc.DrawText(config.lb2char(l.lb), t.x - 10, y)

                if not dpages:
                    if self.gd.cfgGl.pbi == config.PBI_REAL_AND_UNADJ:
                        if self.sp.line2pageNoAdjust(i) != self.sp.line2pageNoAdjust(
                            i + 1
                        ):
                            dc.SetPen(self.gd.cfgGui.pagebreakNoAdjustPen)
                            util.drawLine(dc, 0, y + lineh - 1, size.width, 0)

                    if self.gd.cfgGl.pbi in (
                        config.PBI_REAL,
                        config.PBI_REAL_AND_UNADJ,
                    ):
                        thisPage = self.sp.line2page(i)

                        if thisPage != self.sp.line2page(i + 1):
                            dc.SetPen(self.gd.cfgGui.pagebreakPen)
                            util.drawLine(dc, 0, y + lineh - 1, size.width, 0)

                if i == self.sp.line:
                    posX = t.x
                    cursorY = y
                    acFi = fi
                    dc.SetPen(self.gd.cfgGui.cursorPen)
                    dc.SetBrush(self.gd.cfgGui.cursorBrush)
                    dc.DrawRectangle(t.x + self.sp.column * fx, y, fx, fi.fy)

            if len(t.text) != 0:
                # tl = texts.get(fi.font)
                if fi.font not in texts:
                    # if tl == None:
                    tl = ([], [], [])
                    texts.append((fi.font, tl))

                tl[0].append(t.text)
                tl[1].append((t.x, y))
                if t.line != -1:
                    if self.gd.cfgGl.useCustomElemColors:
                        tl[2].append(self.gd.cfgGui.lt2textColor(ls[t.line].lt))
                    else:
                        tl[2].append(self.gd.cfgGui.textColor)
                else:
                    tl[2].append(self.gd.cfgGui.textHdrColor)

                if t.isUnderlined:
                    if t.line != -1:
                        uli = ulines
                    else:
                        uli = ulinesHdr

                    uli.append((t.x, y + lineh - 1, len(t.text) * fx - 1))

        if ulines:
            dc.SetPen(self.gd.cfgGui.textPen)

            for ul in ulines:
                util.drawLine(dc, ul[0], ul[1], ul[2], 0)

        if ulinesHdr:
            dc.SetPen(self.gd.cfgGui.textHdrPen)

            for ul in ulinesHdr:
                util.drawLine(dc, ul[0], ul[1], ul[2], 0)

        for tl in texts:
            self.gd.vm.drawTexts(self, dc, tl)

        if self.sp.acItems and (cursorY > 0):
            self.drawAutoComp(dc, posX, cursorY, acFi)

    def drawAutoComp(self, dc, posX, cursorY, fi):
        ac = self.sp.acItems
        asel = self.sp.acSel

        offset = 5
        selBleed = 2

        # scroll bar width
        sbw = 10

        size = self.GetClientSize()

        dc.SetFont(fi.font)

        show = min(self.sp.acMax, len(ac))
        doSbw = show < len(ac)

        startPos = (asel // show) * show
        endPos = min(startPos + show, len(ac))
        if endPos == len(ac):
            startPos = max(0, endPos - show)

        w = 0
        for i in range(len(ac)):
            tw = dc.GetTextExtent(ac[i])[0]
            w = max(w, tw)

        w += offset * 2
        h = show * fi.fy + offset * 2

        itemW = w - offset * 2 + selBleed * 2
        if doSbw:
            w += sbw + offset * 2
            sbh = h - offset * 2 + selBleed * 2

        posY = cursorY + fi.fy + 5

        # if the box doesn't fit on the screen in the normal position, put
        # it above the current line. if it doesn't fit there either,
        # that's just too bad, we don't support window sizes that small.
        if (posY + h) > size.height:
            posY = cursorY - h - 1

        dc.SetPen(self.gd.cfgGui.autoCompPen)
        dc.SetBrush(self.gd.cfgGui.autoCompBrush)
        dc.DrawRectangle(posX, posY, w, h)

        dc.SetTextForeground(self.gd.cfgGui.autoCompFgColor)

        for i in range(startPos, endPos):
            if i == asel:
                dc.SetPen(self.gd.cfgGui.autoCompRevPen)
                dc.SetBrush(self.gd.cfgGui.autoCompRevBrush)
                dc.SetTextForeground(self.gd.cfgGui.autoCompBgColor)
                dc.DrawRectangle(
                    posX + offset - selBleed,
                    posY + offset + (i - startPos) * fi.fy - selBleed,
                    itemW,
                    fi.fy + selBleed * 2,
                )
                dc.SetTextForeground(self.gd.cfgGui.autoCompBgColor)
                dc.SetPen(self.gd.cfgGui.autoCompPen)
                dc.SetBrush(self.gd.cfgGui.autoCompBrush)

            dc.DrawText(ac[i], posX + offset, posY + offset + (i - startPos) * fi.fy)

            if i == asel:
                dc.SetTextForeground(self.gd.cfgGui.autoCompFgColor)

        if doSbw:
            dc.SetPen(self.gd.cfgGui.autoCompPen)
            dc.SetBrush(self.gd.cfgGui.autoCompRevBrush)
            util.drawLine(dc, posX + w - offset * 2 - sbw, posY, 0, h)
            dc.DrawRectangle(
                posX + w - offset - sbw,
                posY + offset - selBleed + int((float(startPos) / len(ac)) * sbh),
                sbw,
                int((float(show) / len(ac)) * sbh),
            )
