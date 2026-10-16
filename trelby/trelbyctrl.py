# -*- coding: utf-8 -*-

import copy
import os
import os.path
import time

import wx

import trelby.autosave as autosave
import trelby.cfgdlg as cfgdlg
import trelby.commands as commands
import trelby.config as config
import trelby.configgui as configgui
import trelby.formats as formats
import trelby.gutil as gutil
import trelby.keys as keys
import trelby.mcpapp as mcpapp
import trelby.menus as menus
import trelby.misc as misc
import trelby.myimport as myimport
import trelby.opts as opts
import trelby.pml as pml
import trelby.screenplay as screenplay
import trelby.scriptactions as scriptactions
import trelby.textdlg as textdlg
import trelby.textfmt as textfmt
import trelby.textutil as textutil
import trelby.util as util
from trelby.error import TrelbyError
from trelby.ids import ID_EDIT_REDO, ID_EDIT_UNDO

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


# the keyboard commands that edit the script (the ones that aren't menu
# commands), and the Editor method each one runs, given a CommandState.
# the rest are MyCtrl.cmd<name> methods.
EDITOR_COMMANDS = {
    "Abort": "abortCmd",
    "ChangeToAction": "toActionCmd",
    "ChangeToCharacter": "toCharacterCmd",
    "ChangeToDialogue": "toDialogueCmd",
    "ChangeToNote": "toNoteCmd",
    "ChangeToParenthetical": "toParenCmd",
    "ChangeToScene": "toSceneCmd",
    "ChangeToShot": "toShotCmd",
    "ChangeToActBreak": "toActBreakCmd",
    "ChangeToTransition": "toTransitionCmd",
    "ForcedLineBreak": "insertForcedLineBreakCmd",
    "MoveDown": "moveDownCmd",
    "MoveEndOfLine": "moveLineEndCmd",
    "MoveEndOfScript": "moveEndCmd",
    "MoveLeft": "moveLeftCmd",
    "MoveNextWord": "moveNextWordCmd",
    "MovePrevWord": "movePrevWordCmd",
    "MoveRight": "moveRightCmd",
    "MoveSceneDown": "moveSceneDownCmd",
    "MoveSceneUp": "moveSceneUpCmd",
    "MoveStartOfLine": "moveLineStartCmd",
    "MoveStartOfScript": "moveStartCmd",
    "MoveUp": "moveUpCmd",
    "NewElement": "splitElementCmd",
    "SetMark": "setMarkCmd",
    "Tab": "tabCmd",
    "TabPrev": "toPrevTypeTabCmd",
}


# the editor for one open script, one per tab. it owns the Screenplay
# (self.sp) and the Editor on it (self.ed), draws it the way the current
# view mode (gd.vm) lays it out, and turns keys, mouse clicks and menu
# commands into Editor commands.
# menu items reach it through MyFrame's On* methods, which forward to the
# current tab's MyCtrl.
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

        # wx.Rect of the "Title pages" link above the first page, or None
        # if it's not on screen. set by OnPaint.
        self.titleButtonRect = None

        self.createEmptySp()
        self.updateScreen(redraw=False)

    def refreshGuiConfig(self):
        self.gd.cfgGui = configgui.ConfigGui(self.gd.cfgGl, self.gd.zoom)

    def changeType(self, lt):
        cs = screenplay.CommandState()

        self.ed.convertTypeTo(lt, True)
        self.ed.cmdPost(cs)
        self.sp.paginate()

        if cs.needsVisifying:
            self.makeLineVisible(self.ed.line)

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
        self.ed = screenplay.Editor(self.sp)
        self.sp.cfg.setPaper(self.gd.cfgGl.defaultPaper)
        self.sp.titles.addDefaults()
        self.sp.headers.addDefaults()
        self.setFile(None)
        self.refreshCache()

    # update stuff that depends on configuration / view mode etc.
    def refreshCache(self):
        # width of one character and height of one line on paper, in mm,
        # at the script's (PDF) font size
        self.chX = util.getTextWidth(" ", pml.COURIER, self.sp.cfg.fontSize)
        self.chY = util.getTextHeight(self.sp.cfg.fontSize)

        # the scale comes from the screen font, not the paper: the page is
        # drawn as many screen characters wide as the paper holds, so text
        # laid out in mm for the PDF lands on whole character cells. zoom
        # works by scaling the screen fonts.
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
        s = gutil.loadFile(path or fileName, self.gd.mainFrame)
        if s is None:
            return False

        try:
            (sp, msg) = screenplay.Screenplay.load(s, self.gd.cfgGl)
        except TrelbyError as e:
            wx.MessageBox(
                _("Error loading file:\n\n{}").format(e),
                _("Error"),
                wx.OK,
                self.gd.mainFrame,
            )

            return False

        if msg:
            textdlg.showText(self.gd.mainFrame, msg, _("Warning"))

        # whatever was here before has been saved or discarded
        self.removeRecovery()

        self.clearVars()
        self.sp = sp
        self.ed = screenplay.Editor(sp)
        self.setFile(fileName)
        self.refreshCache()

        # saved cursor position might be anywhere, so we can't just
        # display the first page
        self.makeLineVisible(self.ed.line)

        self.checkWideChars("".join(ln.text for ln in self.sp.lines))

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
        fileName = str(textutil.ensureEndsIn(fileName, ".trelby"))

        if gutil.writeToFile(
            fileName, self.ed.save(), self.gd.mainFrame, backup=True
        ):
            self.sp.markChanged(False)
            self.setFile(fileName)
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

        data = self.ed.save()

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

    # import fileName as the formats.Format fmt. if fmt is None, it's
    # guessed from the extension.
    def importFile(self, fileName, fmt=None):
        fmt = fmt or formats.guessImportFormat(fileName)
        importer = getattr(myimport, fmt.importer)
        titlePages = None

        if fmt.importsTitles:
            lines, titlePages = importer(
                fileName, self.gd.mainFrame, self.sp.titles.pages
            ) or (None, None)
        else:
            lines = importer(fileName, self.gd.mainFrame)

        if not lines:
            return

        self.createEmptySp()

        self.sp.lines = lines
        if titlePages:
            self.sp.titles.pages = titlePages
        self.sp.reformatAll()
        self.sp.paginate()
        self.sp.markChanged(True)

        self.checkWideChars("".join(ln.text for ln in self.sp.lines))

    def setFile(self, fileName):
        self.fileName = fileName
        if fileName:
            self.setDisplayName(os.path.basename(fileName))
        else:
            self.setDisplayName("untitled")

        self.setTabText()

    # set the name shown for the script to name, made unique among the open
    # scripts
    def setDisplayName(self, name):
        taken = [
            c.fileNameDisplay for c in self.gd.mainFrame.getCtrls() if c is not self
        ]
        self.fileNameDisplay = util.uniqueName(name, taken)

    # set the tab text and, if this is the current script, the window
    # title
    def setTabText(self):
        self.shownModified = self.sp.isModified()
        self.gd.mainFrame.setTabText(self.panel, self.getTitleText())
        self.gd.mainFrame.updateTitle(self)

    # the script's name for its tab and the window title, with a "*" if it
    # has unsaved changes
    def getTitleText(self):
        return self.fileNameDisplay + ("*" if self.sp.isModified() else "")

    # update the tab text and window title if the script has been modified
    # or saved since they were last set
    def updateModifiedMark(self):
        if self.sp.isModified() != self.shownModified:
            self.setTabText()

    # texts = self.gd.vm.getScreen(self, False)[0], or None, in which case it's
    # called in this function.
    def isLineVisible(self, line, texts=None):
        if texts == None:
            texts = self.gd.vm.getScreen(self, False)[0]

        # paranoia never hurts
        if len(texts) == 0:
            return False

        # not just a range check, since the bottom rows on screen can show
        # the right-hand column of a dual dialogue but not the end of the
        # left one
        return any(t.line == line for t in texts)

    def makeLineVisible(self, line, direction=commands.SCROLL_CENTER):
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

        # positions are line numbers: the thumb's position is the top line.
        # the range has a screenful of padding beyond the last line, so the
        # thumb can go far enough to put the last line at the top.
        self.panel.scrollBar.SetScrollbar(
            self.ed.getTopLine(), approx, len(self.sp.lines) + approx - 1, approx
        )

    def clearAutoComp(self):
        if self.ed.clearAutoComp():
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
        self.updateModifiedMark()

        if setCommon:
            self.updateCommon()

        if redraw:
            self.Refresh(False)

    # update GUI elements shared by all scripts, like statusbar etc
    def updateCommon(self):
        cur = self.gd.cfgGl.getType(self.sp.lines[self.ed.line].lt)

        if self.ed.tabMakesNew():
            tabNext = "%s" % self.gd.cfgGl.getType(cur.newTypeTab).ti.name
        else:
            tabNext = "%s" % self.gd.cfgGl.getType(cur.nextTypeTab).ti.name

        enterNext = self.gd.cfgGl.getType(cur.newTypeEnter).ti.name

        page = self.sp.line2pageLabel(self.ed.line)
        pageCnt = self.sp.line2page(len(self.sp.lines) - 1)

        self.gd.mainFrame.setElemTypeStatus(cur.lt, tabNext, enterNext)
        self.gd.mainFrame.setFormatStatus(
            self.ed.getFormatState(), self.ed.getCenteredState()
        )
        self.gd.mainFrame.setPageStatus(page, pageCnt, self.sp.hasPageLocks())
        self.gd.mainFrame.setLengthStatus(
            self.sp.getWordCount(), self.sp.getPageLength()
        )

        canUndo = self.ed.undoHistory.canUndo()
        canRedo = self.ed.undoHistory.canRedo()

        self.gd.mainFrame.menuBar.Enable(ID_EDIT_UNDO, canUndo)
        self.gd.mainFrame.menuBar.Enable(ID_EDIT_REDO, canRedo)

        self.gd.mainFrame.toolBar.EnableTool(ID_EDIT_UNDO, canUndo)
        self.gd.mainFrame.toolBar.EnableTool(ID_EDIT_REDO, canRedo)

        self.panel.outline.scheduleRefresh()

    # if text has wide characters (Chinese, Japanese, Korean) and the
    # script doesn't use double-width characters, offer to switch to them,
    # only once per script. the question is asked after the current event,
    # so that an input method's whole input gets added first.
    def checkWideChars(self, text):
        cfg = self.sp.cfg

        if cfg.doubleWidth or cfg.doubleWidthAsked or not textutil.hasWideChars(text):
            return

        cfg.doubleWidthAsked = True
        wx.CallAfter(self.offerDoubleWidth, self.sp)

    # ask whether to switch script sp to double-width characters, if it's
    # still the one shown
    def offerDoubleWidth(self, sp):
        if (sp is not self.sp) or sp.cfg.doubleWidth:
            return

        if (
            wx.MessageBox(
                _(
                    "This script has Chinese, Japanese or Korean characters, which are\ntwice as wide as Latin letters, so they don't fit in the columns\nof the page.\n\nSwitch the script to double-width characters? Every character,\nLatin ones too, will then take up two columns.\n\nThis clears the undo history. It can be changed back in\nScript/Script settings/Formatting."
                ),
                _("Double-width characters"),
                wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION,
                self.gd.mainFrame,
            )
            != wx.YES
        ):
            return

        cfg = copy.deepcopy(sp.cfg)
        cfg.doubleWidth = True
        self.applyCfg(cfg)

    # apply per-script config
    def applyCfg(self, newCfg):
        self.ed.applyCfg(newCfg)

        self.refreshCache()
        self.makeLineVisible(self.ed.line)
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
        # depend on whether the theme is dark. compares Theme objects, as
        # reloading the custom themes can change one under the same name.
        appearanceChanged = (
            config.findTheme(self.gd.cfgGl.theme) is not self.gd.cfgGui.themeChoice
        )

        if appearanceChanged:
            configgui.applyAppearance(self.gd.cfgGl.theme)

        self.gd.cfgGl.recalc()
        self.refreshGuiConfig()
        self.gd.mainFrame.updateKeyMap()

        # every script keeps a reference to the global config, which has
        # just been replaced by a copy
        for c in self.gd.mainFrame.getCtrls():
            c.sp.cfgGl = self.gd.cfgGl
            c.refreshCache()
            c.makeLineVisible(c.ed.line)
            c.adjustScrollBar()

        self.updateScreen()

        # in case tab colors have been changed
        self.gd.mainFrame.tabCtrl.Refresh(False)
        self.gd.mainFrame.elemTypeBar.Refresh(False)
        self.gd.mainFrame.formatBar.Refresh(False)
        self.gd.mainFrame.alignBar.Refresh(False)

        for d in self.gd.mainFrame.tbDividers:
            d.Refresh(False)
        self.gd.mainFrame.noFSBtn.Refresh(False)
        self.gd.mainFrame.toolBar.SetBackgroundColour(self.gd.cfgGui.tabBarBgColor)
        self.gd.mainFrame.toolBar.Refresh()
        self.gd.mainFrame.applyThemeColors()

        # and the open dialogs, like the settings dialog this may have been
        # applied from
        gutil.themeAllWindows()

        # the toolbar icons' color depends on the theme
        if appearanceChanged or (
            self.gd.cfgGl.toolbarIconSize != oldCfgGl.toolbarIconSize
        ):
            self.gd.mainFrame.fillToolBar()
            self.gd.mainFrame.SendSizeEvent()
            self.updateCommon()

        if self.gd.cfgGl.autosaveInterval != oldCfgGl.autosaveInterval:
            self.gd.mainFrame.updateAutosaveTimer()

        if (self.gd.cfgGl.mcpEnabled, self.gd.cfgGl.mcpPort) != (
            oldCfgGl.mcpEnabled,
            oldCfgGl.mcpPort,
        ):
            mcpapp.configure(self.gd, self.gd.mainFrame)

        if writeCfg:
            gutil.writeToFile(
                self.gd.confFilename, self.gd.cfgGl.save(), self.gd.mainFrame
            )

        self.gd.mainFrame.checkFonts()

    def OnEraseBackground(self, event):
        pass

    def OnSize(self, event):
        size = self.GetClientSize()

        # OnPaint draws into screenBuf, a class attribute: one bitmap
        # shared by all the tabs, as only the selected one is shown, and
        # only replaced when the size changes. not used when doDblBuf is
        # False (Unix, see misc.init), where wx double-buffers by itself.
        #
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

        # a different number of lines fits now
        self.makeLineVisible(self.ed.line)

    # also called by OnMotion while the button is held down, with mark
    # True: the first such call sets the selection's other end, at about
    # where the button went down, and later ones only move the cursor, so
    # dragging selects text
    def OnLeftDown(self, event, mark=False):
        if not mark and self.isOverTitleButton(event.GetPosition()):
            scriptactions.titlesDlg(self.gd.mainFrame, self)

            return

        if not mark and self.isTripleClick(event.GetPosition()):
            self.lastDClick = None
            self.selectByClick(event, False)

            return

        if not mark:
            self.clickSelectActive = False

        if not self.mouseSelectActive:
            self.ed.clearMark()
            self.updateScreen()

        pos = event.GetPosition()
        line, col = self.gd.vm.pos2linecol(self, pos.x, pos.y)

        self.mouseSelectActive = True

        if line is not None:
            self.ed.gotoPos(line, col, mark)
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
            self.ed.selectWordAt(line, col)
        else:
            self.ed.selectElementAt(line)

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
        cd = self.ed.getSelectedAsCD(False)

        if not cd or ((len(cd.lines) == 1) and (len(cd.lines[0].text) < 2)):
            self.ed.clearMark()

    def OnMotion(self, event):
        if event.LeftIsDown() and not self.clickSelectActive:
            self.OnLeftDown(event, mark=True)

        if self.isOverTitleButton(event.GetPosition()):
            self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        else:
            self.SetCursor(wx.NullCursor)

    def isOverTitleButton(self, pos):
        return bool(self.titleButtonRect) and self.titleButtonRect.Contains(pos)

    def OnRightDown(self, event):
        pos = event.GetPosition()
        line, col = self.gd.vm.pos2linecol(self, pos.x, pos.y)

        if not self.ed.mark and line is not None and (line != self.ed.line):
            self.ed.gotoPos(line, col, False)
            self.updateScreen()

        # type changes apply to every element in the selection, if any
        curLt = self.ed.getSelectionType()

        # dual dialogue works on the speech at the cursor, so it's only
        # offered when there's no selection
        dualState = None

        if not self.ed.mark:
            toggle = self.ed.getDualToggle()

            if toggle:
                dualState = not toggle[1]

        m = menus.makeRightClickMenu(
            self.gd.mainFrame.actions,
            curLt,
            bool(self.ed.mark),
            dualState,
            self.ed.getCenteredState(),
        )
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

        self.ed.setTopLine(self.ed.getTopLine() + delta)
        self.updateScreen()

    def OnScroll(self, event):
        pos = self.panel.scrollBar.GetThumbPosition()
        self.ed.setTopLine(pos)
        self.ed.clearAutoComp()
        self.updateScreen()

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
        if self.ed.acItems:
            cs.doAutoComp = cs.AC_KEEP
            self.ed.pageScrollAutoComp(dir)

            return

        texts, dpages = self.gd.vm.getScreen(self, False)

        # if user has scrolled with scrollbar so that cursor isn't seen,
        # just make cursor visible and don't move
        if not self.isLineVisible(self.ed.line, texts):
            self.gd.vm.makeLineVisible(self, self.ed.line, texts)
            cs.needsVisifying = False

            return

        self.ed.maybeMark(cs.mark)
        self.gd.vm.pageCmd(self, cs, dir, texts, dpages)

    # returns True if something was deleted
    def OnCut(self, doUpdate=True, doDelete=True, copyToClip=True):
        marked = self.ed.getMarkedLines()

        if not marked:
            return False

        cd = self.ed.getSelectedAsCD(doDelete)

        if copyToClip:
            self.gd.clipboard = cd

        if doUpdate:
            if doDelete:
                self.sp.paginate()

            self.makeLineVisible(self.ed.line)
            self.updateScreen()

        return doDelete

    def OnPaste(self, clines=None):
        if not clines:
            cd = self.gd.clipboard

            if not cd:
                return

            clines = cd.lines

        self.ed.paste(clines)
        self.sp.paginate()

        self.makeLineVisible(self.ed.line)
        self.updateScreen()

        self.checkWideChars("".join(ln.text for ln in clines))

    # move the cursor to the start of the given line and scroll it to the
    # top of the screen. used by the outline view.
    def gotoLine(self, line):
        self.clearAutoComp()
        self.ed.clearMark()
        self.ed.gotoPos(line, 0)

        self.ed.setTopLine(line)
        self.makeLineVisible(line)
        self.updateScreen()

    # move the scene containing the given line to position newIndex in the
    # outline. used by the outline view.
    def moveSceneTo(self, line, newIndex):
        self.clearAutoComp()

        if not self.ed.moveSceneTo(line, newIndex):
            return

        self.sp.paginate()
        self.ed.setTopLine(self.ed.line)
        self.makeLineVisible(self.ed.line)
        self.updateScreen()

    # set the outline color of the scene containing the given line, or
    # remove it if color is None. used by the outline view.
    def setSceneColor(self, line, color):
        self.clearAutoComp()

        if self.ed.setSceneColor(line, color):
            self.updateScreen()

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

    # run the keyboard command with the given name, which isn't a menu
    # command
    def runCommand(self, name, cs):
        if name in EDITOR_COMMANDS:
            getattr(self.ed, EDITOR_COMMANDS[name])(cs)
        else:
            getattr(self, "cmd" + name)(cs)

    def cmdDelete(self, cs):
        if not self.ed.mark:
            self.ed.deleteForwardCmd(cs)
        else:
            self.OnCut(doUpdate=False, copyToClip=False)

    def cmdDeleteBackward(self, cs):
        if not self.ed.mark:
            self.ed.deleteBackwardCmd(cs)
        else:
            self.OnCut(doUpdate=False, copyToClip=False)

    def cmdMovePageDown(self, cs):
        self.pageCmd(cs, 1)

    def cmdMovePageUp(self, cs):
        self.pageCmd(cs, -1)

    def cmdSpeedTest(self, cs):
        import trelby.undo as undo

        self.speedTestUndo = []

        def testUndoFullCopy():
            u = undo.FullCopy(self.ed)
            u.setAfter(self.ed)
            self.speedTestUndo.append(u)

        # rewrapping makes the undo history's line numbers meaningless
        # (see Editor.reformatAll), and testAddRemoveChar has added some
        def testReformatAll():
            self.ed.undoHistory.clear()
            self.ed.reformatAll()

        def testPaginate():
            self.sp.paginate()

        def testUpdateScreen():
            self.updateScreen()
            self.Update()

        def testAddRemoveChar():
            self.OnKeyChar(keys.MyKeyEvent(ord("a")))
            self.OnKeyChar(keys.MyKeyEvent(wx.WXK_BACK))

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

            print("{:.5f} seconds per {}".format(t / count, name))

        print("-" * 20)

        # it's annoying having the program ask if you want to save after
        # running these tests, so pretend the script hasn't changed
        self.sp.markChanged(False)

    def cmdTest(self, cs):
        pass

    def OnKeyChar(self, ev):
        char, cmd = commands.resolveKey(
            self.gd.keyMap,
            ev.GetUnicodeKey(),
            ev.GetKeyCode(),
            ev.ControlDown(),
            ev.AltDown(),
            ev.ShiftDown(),
        )

        cs = screenplay.CommandState()
        cs.mark = bool(ev.ShiftDown())
        scrollDirection = commands.SCROLL_CENTER

        if char:
            addChar = True

            # If there's something selected, either remove it, or clear selection.
            if self.ed.mark and self.gd.cfgGl.overwriteSelectionOnInsert:
                if not self.OnCut(doUpdate=False, copyToClip=False):
                    self.ed.clearMark()
                    addChar = False

            if addChar:
                cs.char = char

                # test mode hooks: "\xe5" (a with ring) loads the sample
                # script, "\xa4" (currency sign) runs cmdTest and "\xbd"
                # (one half) runs cmdSpeedTest.
                if opts.isTest and (cs.char == "\xe5"):
                    self.loadFile(misc.getFullPath("trelby/sample.trelby"))
                elif opts.isTest and (cs.char == "\xa4"):
                    self.cmdTest(cs)
                elif opts.isTest and (cs.char == "\xbd"):
                    self.cmdSpeedTest(cs)
                else:
                    self.ed.addCharCmd(cs)
                    self.checkWideChars(cs.char)

        elif cmd:
            # a menu command runs the menus.Action of the same name, which
            # updates the screen itself, so we're done. other commands are
            # cmd<name> methods here, which work on self.sp and leave
            # updating the screen to the code below.
            scrollDirection = cmd.scrollDirection

            if cmd.isMenu:
                self.gd.mainFrame.runAction(cmd.name)

                return

            self.runCommand(cmd.name, cs)
        else:
            ev.Skip()

            return

        self.ed.cmdPost(cs)

        # pagination is cheap (a couple of milliseconds even for a long
        # script), so redo it after every key to keep page breaks current.
        # it can move the cursor's line on screen, so always make sure it's
        # still visible.
        self.sp.paginate()
        self.makeLineVisible(self.ed.line, scrollDirection)

        self.updateScreen()

    def OnPaint(self, event):
        # ldkjfldsj = util.TimerDev("paint")

        ls = self.sp.lines

        if misc.doDblBuf:
            dc = wx.BufferedPaintDC(self, self.screenBuf)
        else:
            dc = wx.PaintDC(self)

        size = self.GetClientSize()
        marked = self.ed.getMarkedLines()
        lineh = self.gd.vm.getLineHeight(self)
        posX = -1
        cursorY = -1

        # auto-comp FontInfo
        acFi = None

        # list of (font, ([text, ...], [(x, y), ...], [wx.Colour, ...]))
        # tuples, drawn after everything else by ViewMode.drawTexts
        texts = []

        # lists of underline-lines to draw, one for normal text and one
        # for header texts. list objects are (x, y, width) tuples.
        ulines = []
        ulinesHdr = []

        strings, dpages = self.gd.vm.getScreen(self, True, True)

        # key = id() of a wx.Font, which isn't hashable, value = x offset
        # (pixels) of a wide character in a double-width cell (see
        # cellOffset)
        wideOffsets = {}

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

        self.titleButtonRect = None

        if dpages and (dpages[0].pageNr == 1):
            self.drawTitleButton(dc, dpages[0])

        for t in strings:
            i = t.line
            y = t.y
            fi = t.fi
            fx = fi.fx

            # width of one character; differs from fx with double-width
            # characters
            cfx = t.getCharPixels()

            if i != -1:
                l = ls[i]

                if l.lt == screenplay.NOTE:
                    dc.SetPen(self.gd.cfgGui.notePen)
                    dc.SetBrush(self.gd.cfgGui.noteBrush)

                    # element widths are in columns, fx pixels each,
                    # while positions in the text are in characters, cfx
                    # pixels each
                    nx = t.x - 5
                    nw = self.sp.cfg.getType(l.lt).width * fx + 10

                    dc.DrawRectangle(nx, y, nw, lineh)

                    dc.SetPen(self.gd.cfgGui.textPen)
                    gutil.drawLine(dc, nx - 1, y, 0, lineh)
                    gutil.drawLine(dc, nx + nw, y, 0, lineh)

                    if self.sp.isFirstLineOfElem(i):
                        gutil.drawLine(dc, nx - 1, y - 1, nw + 2, 0)

                    if self.sp.isLastLineOfElem(i):
                        gutil.drawLine(dc, nx - 1, y + lineh, nw + 2, 0)

                if marked and self.ed.isLineMarked(i, marked):
                    c1, c2 = self.ed.getMarkedColumns(i, marked)

                    dc.SetPen(self.gd.cfgGui.selectedPen)
                    dc.SetBrush(self.gd.cfgGui.selectedBrush)

                    dc.DrawRectangle(t.x + c1 * cfx, y, (c2 - c1 + 1) * cfx, lineh)

                if self.gd.mainFrame.showFormatting:
                    # a centered line's text doesn't start at its margin
                    lx = int(t.x - self.sp.getCenterOffset(i) * fx)

                    dc.SetPen(self.gd.cfgGui.bluePen)
                    gutil.drawLine(dc, lx, y, 0, lineh)

                    extraIndent = 1 if self.sp.needsExtraParenIndent(i) else 0

                    gutil.drawLine(
                        dc,
                        lx + (self.sp.cfg.getType(l.lt).width - extraIndent) * fx,
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
                            gutil.drawLine(dc, 0, y + lineh - 1, size.width, 0)

                    if self.gd.cfgGl.pbi in (
                        config.PBI_REAL,
                        config.PBI_REAL_AND_UNADJ,
                    ):
                        thisPage = self.sp.line2page(i)

                        if thisPage != self.sp.line2page(i + 1):
                            dc.SetPen(self.gd.cfgGui.pagebreakPen)
                            gutil.drawLine(dc, 0, y + lineh - 1, size.width, 0)

                if i == self.ed.line:
                    posX = t.x
                    cursorY = y
                    acFi = fi
                    dc.SetPen(self.gd.cfgGui.cursorPen)
                    dc.SetBrush(self.gd.cfgGui.cursorBrush)
                    dc.DrawRectangle(t.x + self.ed.column * cfx, y, cfx, fi.fy)

            if len(t.text) != 0:
                if t.line != -1:
                    color = self.gd.cfgGui.lt2textColor(ls[t.line].lt)
                    uli = ulines
                else:
                    color = self.gd.cfgGui.textHdrColor
                    uli = ulinesHdr

                if t.isUnderlined:
                    uli.append((t.x, y + lineh - 1, len(t.text) * cfx - 1))

                # bold / italic / underlined parts of the text are drawn
                # separately, each in its own font
                #
                # cfgGui.fonts is indexed by the bold / italic bits, which
                # textfmt and pml share, so a run's style bits are added to
                # the element's own font, e.g. italic text in a bold scene
                # heading gets the bold italic font
                if t.fmt:
                    fonts = self.gd.cfgGui.fonts
                    base = fonts.index(fi)

                    parts = []

                    for a, b, style in textfmt.runs(t.fmt, len(t.text)):
                        x = t.x + a * cfx
                        parts.append((fonts[base | (style & 3)].font, a, b, x))

                        if (style & textfmt.UNDERLINED) and not t.isUnderlined:
                            uli.append((x, y + lineh - 1, (b - a) * cfx - 1))
                else:
                    parts = [(fi.font, 0, len(t.text), t.x)]

                for font, a, b, x in parts:
                    if t.charWidth == 1:
                        tl = ([t.text[a:b]], [(x, y)], [color])
                    else:
                        # each character centered in its own cell
                        chars = []
                        coords = []

                        for k in range(a, b):
                            ch = t.text[k]

                            if ch != " ":
                                off = self.cellOffset(
                                    dc, font, ch, fx, cfx, wideOffsets
                                )
                                chars.append(ch)
                                coords.append((t.x + k * cfx + off, y))

                        tl = (chars, coords, [color] * len(chars))

                    texts.append((font, tl))

        if ulines:
            dc.SetPen(self.gd.cfgGui.textPen)

            for ul in ulines:
                gutil.drawLine(dc, ul[0], ul[1], ul[2], 0)

        if ulinesHdr:
            dc.SetPen(self.gd.cfgGui.textHdrPen)

            for ul in ulinesHdr:
                gutil.drawLine(dc, ul[0], ul[1], ul[2], 0)

        for tl in texts:
            self.gd.vm.drawTexts(self, dc, tl)

        self.drawLocks(dc, strings, dpages, size)

        if self.ed.acItems and (cursorY > 0):
            self.drawAutoComp(dc, posX, cursorY, acFi)

    # return the x offset (pixels) at which to draw character ch in a
    # double-width cell cfx pixels wide, for it to be centered. fx is the
    # width of a narrow (Latin) character in font. wideOffsets caches the
    # offsets of wide characters, which are all the same width, by font.
    @staticmethod
    def cellOffset(dc, font, ch, fx, cfx, wideOffsets):
        if not textutil.isWideChar(ch):
            return (cfx - fx) // 2

        off = wideOffsets.get(id(font))

        if off is None:
            w = dc.GetFullTextExtent(chr(0x4E2D), font)[0]
            off = max(0, (cfx - w) // 2)
            wideOffsets[id(font)] = off

        return off

    # mark each locked page with a lock icon in its right margin, level
    # with the page number, and each scene heading whose number is locked
    # with one in the left margin, left of the scene number. these are
    # only shown on screen. in draft mode, where there are no pages, a
    # locked page's icon goes on the line it starts at.
    def drawLocks(self, dc, strings, dpages, size):
        cfg = self.sp.cfg
        ls = self.sp.lines
        mm2p = self.mm2p

        h = max(6, self.gd.cfgGui.fonts[pml.NORMAL].fy)
        w = h * 3 // 4
        gap = h // 3

        # x offsets (pixels) of the icons from the left edge of the page
        pageX = int((cfg.paperWidth - cfg.marginRight) * mm2p) + gap

        # the left scene number starts 6 characters left of the margin (see
        # screenplay.render.addSceneNumbers)
        sceneX = int((cfg.marginLeft - 6 * self.chX) * mm2p) - gap - w

        draftX = util.clamp((size.width - self.pageW) // 2, 0)

        for dp in dpages:
            if ls[self.sp.page2lines(dp.pageNr)[0]].pageLock:
                self.drawLock(
                    dc, dp.x1 + pageX, dp.y1 + int(cfg.marginTop * mm2p), h, w
                )

        for t in strings:
            i = t.line

            if i == -1:
                continue

            pageLocked = not dpages and ls[i].pageLock
            sceneLocked = self.sp.getSceneLock(i)

            if not (pageLocked or sceneLocked):
                continue

            x = draftX

            for dp in dpages:
                if dp.x1 <= t.x <= dp.x2:
                    x = dp.x1

            if pageLocked:
                self.drawLock(dc, x + pageX, t.y, h, w)

            if sceneLocked:
                self.drawLock(dc, x + sceneX, t.y, h, w)

    # draw a padlock w pixels wide and h pixels high, with its top left
    # corner at (x, y)
    def drawLock(self, dc, x, y, h, w):
        color = self.gd.cfgGui.textHdrColor

        bodyH = h // 2 + 1
        bodyY = y + h - bodyH

        # the shackle, whose lower half the body covers
        pw = max(1, h // 8)
        sw = w - 2 * max(1, w // 6)
        sx = x + (w - sw) // 2

        dc.SetPen(wx.Pen(color, pw))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRoundedRectangle(
            sx, y + pw // 2, sw, (bodyY - y - pw // 2) * 2, sw / 2.0
        )

        dc.SetPen(wx.Pen(color))
        dc.SetBrush(wx.Brush(color))
        dc.DrawRoundedRectangle(x, bodyY, w, bodyH, max(1, h // 10))

        # keyhole, when there's room for one
        if h >= 12:
            kw = max(2, w // 6)
            dc.SetPen(self.gd.cfgGui.textBgPen)
            dc.SetBrush(self.gd.cfgGui.textBgBrush)
            dc.DrawRectangle(x + (w - kw) // 2, bodyY + bodyH // 3, kw, bodyH // 3)

    # draw the button that opens the title pages dialog, centered just
    # above the first page (dp), if there's room for it.
    def drawTitleButton(self, dc, dp):
        dc.SetFont(wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT))

        text = _("Manage title page")
        tw, th = dc.GetTextExtent(text)

        bw = tw + 40
        bh = th + 16
        x = (dp.x1 + dp.x2 - bw) // 2
        y = dp.y1 - bh - 8

        if y < 0:
            return

        dc.SetPen(self.gd.cfgGui.pageBorderPen)
        dc.SetBrush(self.gd.cfgGui.textBgBrush)
        dc.DrawRoundedRectangle(x, y, bw, bh, 4)

        dc.SetTextForeground(self.gd.cfgGui.textColor)
        dc.DrawText(text, x + (bw - tw) // 2, y + (bh - th) // 2)

        self.titleButtonRect = wx.Rect(x, y, bw, bh)

    # draw the auto-completion list below the cursor line, or above it if
    # there's no room below. posX is where the line's text starts.
    def drawAutoComp(self, dc, posX, cursorY, fi):
        ac = self.ed.acItems
        asel = self.ed.acSel

        # space inside the border, around the items
        pad = self.FromDIP(6)

        # space around an item's text, inside its highlight
        itemPadX = self.FromDIP(6)
        itemPadY = self.FromDIP(3)

        # scroll bar width
        sbw = self.FromDIP(6)

        radius = self.FromDIP(4)

        size = self.GetClientSize()

        dc.SetFont(fi.font)

        show = min(self.ed.acMax, len(ac))
        doSbw = show < len(ac)

        # the items shown scroll a page (show items) at a time: the page
        # with the selected item, except that the last page is moved back
        # to be a full one
        startPos = (asel // show) * show
        endPos = min(startPos + show, len(ac))
        if endPos == len(ac):
            startPos = max(0, endPos - show)

        textW = 0
        for i in range(len(ac)):
            textW = max(textW, dc.GetTextExtent(ac[i])[0])

        itemW = textW + itemPadX * 2
        itemH = fi.fy + itemPadY * 2
        listH = show * itemH

        w = itemW + pad * 2
        h = listH + pad * 2

        if doSbw:
            w += sbw + pad

        # line the items' text up with the line's text, keeping the box
        # inside the window
        posX -= pad + itemPadX
        posX = max(0, min(posX, size.width - w))

        posY = cursorY + fi.fy + self.FromDIP(4)

        # if the box doesn't fit on the screen in the normal position, put
        # it above the current line. if it doesn't fit there either,
        # that's just too bad, we don't support window sizes that small.
        if (posY + h) > size.height:
            posY = cursorY - h - self.FromDIP(4)

        cfgGui = self.gd.cfgGui

        dc.SetPen(cfgGui.autoCompBorderPen)
        dc.SetBrush(cfgGui.autoCompBrush)
        dc.DrawRoundedRectangle(posX, posY, w, h, radius)

        dc.SetTextForeground(cfgGui.autoCompFgColor)

        for i in range(startPos, endPos):
            x = posX + pad
            y = posY + pad + (i - startPos) * itemH

            if i == asel:
                dc.SetPen(cfgGui.autoCompSelPen)
                dc.SetBrush(cfgGui.autoCompSelBrush)
                dc.DrawRoundedRectangle(x, y, itemW, itemH, radius - 1)

            dc.DrawText(ac[i], x + itemPadX, y + itemPadY)

        if doSbw:
            dc.SetPen(cfgGui.autoCompBorderPen)
            dc.SetBrush(cfgGui.autoCompBorderBrush)
            dc.DrawRoundedRectangle(
                posX + w - pad - sbw,
                posY + pad + int((float(startPos) / len(ac)) * listH),
                sbw,
                max(sbw, int((float(show) / len(ac)) * listH)),
                sbw // 2,
            )
