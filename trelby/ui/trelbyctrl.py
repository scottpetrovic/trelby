# -*- coding: utf-8 -*-

import copy
import os
import os.path
import time

import wx

import trelby.ui.autosave as autosave
import trelby.commands as commands
import trelby.config as config
import trelby.dialogs.finddlg as finddlg
import trelby.formats as formats
import trelby.keys as keys
import trelby.ui.fileio as fileio
import trelby.ui.gutil as gutil
import trelby.ui.menus as menus
import trelby.misc as misc
import trelby.ui.myimport as myimport
import trelby.ui.noteeditor as noteeditor
import trelby.opts as opts
import trelby.screenplay as screenplay
import trelby.spellcheck as spellcheck
import trelby.ui.scriptactions as scriptactions
import trelby.ui.scriptpainter as scriptpainter
import trelby.dialogs.textdlg as textdlg
import trelby.textutil as textutil
import trelby.thesaurus as thesaurus
import trelby.util as util
from trelby.error import TrelbyError

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


# how many replacements the right-click menu suggests for a misspelled word
SUGGESTIONS = 5

# the right-click menu's synonyms: at most this many senses of the word,
# with at most this many words each
SYNONYM_SENSES = 5
SYNONYMS_PER_SENSE = 5

# how long a sense's definition can be in the synonyms menu
SYNONYM_DEFINITION_LENGTH = 50


# load the thesaurus if it isn't loaded already, showing a message box
# with 'frame' as parent on errors. if it can't be loaded, an empty one is
# used, so the error is only shown once.
def loadThesaurus(frame):
    if thesaurus.gThesaurus is None:
        s = fileio.loadMaybeCompressedFile(thesaurus.FILENAME, frame)
        thesaurus.gThesaurus = thesaurus.Thesaurus(s or "")

    return thesaurus.gThesaurus


# (ms, dx, dy): how soon and how close (pixels) a click must follow the
# one before it to make a double click
def dclickLimits():
    ms = wx.SystemSettings.GetMetric(wx.SYS_DCLICK_MSEC)
    dx = wx.SystemSettings.GetMetric(wx.SYS_DCLICK_X)
    dy = wx.SystemSettings.GetMetric(wx.SYS_DCLICK_Y)

    # metrics are -1 if the platform doesn't report them
    return (ms if ms > 0 else 500, dx if dx > 0 else 4, dy if dy > 0 else 4)


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

        # the script is laid out left to right even when the interface
        # isn't, and the drawing and the mouse handling need it to be
        gutil.keepLeftToRight(self)

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

        # the notes beside the page, as a list of (wx.Rect, line, index)
        # (see ScriptPainter.drawNoteMarkers). set by OnPaint.
        self.noteMarkers = []

        # the "resolved" checkboxes on the cards, likewise
        # (ScriptPainter.noteChecks)
        self.noteChecks = []

        # the tooltip shown, a note's text while the mouse is over its card
        self.noteTip = None

        # the noteeditor.NoteEditor editing a note on its card, or None
        self.noteEditor = None

        # the first line of the paragraph a new note is being written on,
        # which gets a blank card for it beside the page, or None
        self.newNoteLine = None

        # the right-click menu's items for a misspelled word: its
        # suggested replacements, and adding it to the user's or the
        # script's dictionary
        self.suggestionIds = [wx.NewIdRef() for i in range(SUGGESTIONS)]
        self.addWordId = wx.NewIdRef()
        self.addScriptWordId = wx.NewIdRef()

        for id in self.suggestionIds + [self.addWordId, self.addScriptWordId]:
            self.Bind(wx.EVT_MENU, self.OnSpellingMenu, id=id)

        # (line, col, word, suggestions) of the misspelled word the
        # right-click menu was last opened on, or None
        self.spellingWord = None

        # the right-click menu's synonyms for the word clicked on, and
        # (line, col, word, synonyms) for them, or None
        self.synonymIds = [
            wx.NewIdRef() for i in range(SYNONYM_SENSES * SYNONYMS_PER_SENSE)
        ]
        self.synonymWord = None

        for id in self.synonymIds:
            self.Bind(wx.EVT_MENU, self.OnSynonymMenu, id=id)

        self.createEmptySp()
        self.updateScreen(redraw=False)

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

        # (time, (line, index)) of the last click on a note beside the
        # page, so that a double click edits the note clicked on even if
        # the first click moved it (by opening the notes sidebar, or
        # scrolling to its paragraph)
        self.lastNoteClick = None

        # a note being edited is in the old script
        if getattr(self, "noteEditor", None):
            self.noteEditor.finish(False)

        # what the find dialog was left showing
        self.findState = finddlg.FindState()

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
        self.panel.board.reload(self.sp)

    # update stuff that depends on configuration / view mode etc.
    # (see scriptpainter.Viewport for what these are)
    def refreshCache(self):
        vp = self.getViewport(refresh=True)

        self.chX = vp.chX
        self.chY = vp.chY
        self.mm2p = vp.mm2p
        self.pageW = vp.pageW
        self.pageH = vp.pageH

    def getCfgGui(self):
        return self.gd.cfgGui

    # while the beat board is shown in the script's place, the script is
    # hidden and must not get the keyboard, so the board gets it instead
    # (see MyPanel.showBeatBoard)
    def SetFocus(self):
        panel = getattr(self, "panel", None)

        if panel and panel.boardShown:
            panel.board.SetFocus()
        else:
            wx.Window.SetFocus(self)

    # load script from path and show it as fileName. returns True on
    # success.
    def loadFile(self, fileName, path=None):
        s = fileio.loadFile(path or fileName, self.gd.mainFrame)
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
        self.panel.board.reload(sp)

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

        if fileio.writeToFile(
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
        result = myimport.importFile(fileName, fmt, self.gd.mainFrame, self.sp)

        if not result:
            return

        self.createEmptySp()

        self.sp.lines = result.lines
        if result.titlePages:
            self.sp.titles.pages = result.titlePages
        self.sp.reformatAll()
        self.sp.paginate()
        self.sp.markChanged(True)

        self.checkWideChars("".join(ln.text for ln in self.sp.lines))

    def setFile(self, fileName):
        self.fileName = fileName
        if fileName:
            self.setDisplayName(os.path.basename(fileName))
        else:
            self.setDisplayName(_("untitled"))

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
        self.gd.mainFrame.showScriptState(self)
        self.panel.outline.scheduleRefresh()
        self.panel.notes.scheduleRefresh()

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
        # the event isn't skipped, so wx doesn't give us the focus itself.
        # taking it ends editing a note in the notes sidebar, keeping it.
        # (mark is True when OnMotion extends a selection by dragging.)
        if not mark and not self.HasFocus():
            self.SetFocus()

        if not mark and self.isOverTitleButton(event.GetPosition()):
            scriptactions.titlesDlg(self.gd.mainFrame, self)

            return

        if not mark and self.toggleNoteCheckAt(event.GetPosition()):
            return

        marker = None if mark else self.noteMarkerAt(event.GetPosition())

        if marker is not None:
            self.lastNoteClick = (time.monotonic(), marker)
            self.showNote(marker[0], marker[1], marker[1] is None)

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
        # the second click of a double click on a checkbox toggles it back
        if self.toggleNoteCheckAt(event.GetPosition()):
            return

        marker = None

        if self.lastNoteClick:
            t, marker = self.lastNoteClick
            self.lastNoteClick = None

            if (time.monotonic() - t) * 1000 > dclickLimits()[0]:
                marker = None

        if marker is not None:
            self.noteDClick(*marker)

            return

        self.lastDClick = (time.monotonic(), event.GetPosition())
        self.selectByClick(event, True)

    # True if a click at pos follows the last double click closely enough,
    # in time and space, to make it a triple click.
    def isTripleClick(self, pos):
        if not self.lastDClick:
            return False

        t, dpos = self.lastDClick
        ms, dx, dy = dclickLimits()

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

        pos = event.GetPosition()

        marker = self.noteMarkerAt(pos)

        if self.isOverTitleButton(pos) or (marker is not None):
            self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        else:
            self.SetCursor(wx.NullCursor)

        # a note's whole text, which its card may cut off
        tip = None

        if marker and (marker[1] is not None):
            notes = self.sp.getParaNotes(marker[0])

            if marker[1] < len(notes):
                tip = notes[marker[1]].text

                if self.noteCheckAt(pos):
                    if notes[marker[1]].resolved:
                        tip = _("Mark as not resolved")
                    else:
                        tip = _("Mark as resolved")

        if tip != self.noteTip:
            self.noteTip = tip
            self.SetToolTip(tip)

    def isOverTitleButton(self, pos):
        return bool(self.titleButtonRect) and self.titleButtonRect.Contains(pos)

    # (line, index) of the note whose card beside the page is at pos:
    # the first line of its paragraph, and its index among the paragraph's
    # notes, which is None for a note icon (see ScriptPainter.drawNoteMarkers).
    # None if there's none at pos.
    def noteMarkerAt(self, pos):
        for rect, line, index in self.noteMarkers:
            if rect.Contains(pos):
                return line, index

        return None

    # (line, index) of the note whose "resolved" checkbox is at pos, like
    # noteMarkerAt's, or None
    def noteCheckAt(self, pos):
        for rect, line, index in self.noteChecks:
            if rect.Contains(pos):
                return line, index

        return None

    # if pos is on a note's "resolved" checkbox, mark the note resolved or
    # not and return True
    def toggleNoteCheckAt(self, pos):
        check = self.noteCheckAt(pos)

        if check is None:
            return False

        line, index = check
        notes = self.sp.getParaNotes(line)

        if index < len(notes):
            note = notes[index]
            self.setNote(line, index, note.replace(resolved=not note.resolved))

        return True

    # put the cursor on the paragraph starting at line, and select its note
    # at index in the notes sidebar, or its first one if index is None, if
    # the sidebar is shown or 'openSidebar' is True. (only a note icon
    # opens it, since its notes can't be read anywhere else.)
    def showNote(self, line, index, openSidebar=False):
        if openSidebar and not self.gd.showNotes:
            self.gd.mainFrame.setShowNotes(True)

        self.showLine(line)

        if self.gd.showNotes:
            self.panel.notes.showNotesOf(line, index)

    # a double click on the note at (line, index) beside the page (see
    # noteMarkerAt), which edits it. a note icon for more than one note
    # has nothing to edit: the first click showed them in the sidebar.
    def noteDClick(self, line, index):
        if index is None:
            if len(self.sp.getParaNotes(line)) != 1:
                return

            index = 0

        self.editNote(line, index)

    # edit the note at index among the notes of the paragraph starting at
    # line on its card beside the page, or in the notes sidebar if it has
    # no card (there's only a note icon for it)
    def editNote(self, line, index):
        self.finishNoteEdit(True)

        # the cards are where the last drawing put them, and the click
        # that got us here may have moved them
        self.Update()

        rect = self.noteCardRect(line, index)

        if rect is None:
            self.showNote(line, index, True)
            self.panel.notes.startEdit(self.panel.notes.list.GetSelection())

            return

        self.noteEditor = noteeditor.NoteEditor(self, line, index, rect)

    # start writing a new note on the paragraph at the cursor, on a blank
    # card after its notes beside the page, or in the notes sidebar if
    # there's no room for cards
    def newNote(self):
        self.clearAutoComp()
        self.finishNoteEdit(True)

        line = self.sp.getParaFirstIndexFromLine(self.ed.line)
        self.makeLineVisible(line)

        self.newNoteLine = line
        self.Refresh(False)
        self.Update()

        rect = self.noteCardRect(line, len(self.sp.getParaNotes(line)))

        if rect is None:
            self.newNoteLine = None
            self.Refresh(False)

            if not self.gd.showNotes:
                self.gd.mainFrame.setShowNotes(True)

            self.panel.notes.addNote()

            return

        self.noteEditor = noteeditor.NoteEditor(self, line, None, rect)

    # the wx.Rect of the card of the note at index among the notes of the
    # paragraph starting at line, as last drawn, or None if it has none
    def noteCardRect(self, line, index):
        return next(
            (r for r, l, i in self.noteMarkers if (l, i) == (line, index)), None
        )

    # stop editing a note on its card, if one is, keeping the new text or
    # not
    def finishNoteEdit(self, keep):
        if self.noteEditor:
            self.noteEditor.finish(keep)

    # the right-click menu of the note at (line, index) beside the page,
    # at pos: edit it, mark it resolved or not, or delete it. a note icon
    # for more than one note shows them in the sidebar instead.
    def noteMenu(self, line, index, pos):
        notes = self.sp.getParaNotes(line)

        if index is None:
            if len(notes) != 1:
                self.showNote(line, None, True)

                return

            index = 0

        if index >= len(notes):
            return

        note = notes[index]

        menu = wx.Menu()
        editId = wx.NewIdRef()
        resolveId = wx.NewIdRef()
        deleteId = wx.NewIdRef()

        menu.Append(editId, _("Edit"))

        if note.resolved:
            menu.Append(resolveId, _("Mark as not resolved"))
        else:
            menu.Append(resolveId, _("Mark as resolved"))

        menu.Append(deleteId, _("Delete"))

        try:
            sel = self.GetPopupMenuSelectionFromUser(menu, pos)
        finally:
            menu.Destroy()

        if sel == int(editId):
            self.editNote(line, index)
        elif sel == int(resolveId):
            self.setNote(line, index, note.replace(resolved=not note.resolved))
        elif sel == int(deleteId):
            self.deleteNote(line, index)

    def OnRightDown(self, event):
        pos = event.GetPosition()
        marker = self.noteMarkerAt(pos)

        if marker is not None:
            self.noteMenu(marker[0], marker[1], pos)

            return

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
            self.spellingMenu(line, col),
            self.synonymsMenu(line, col),
        )
        self.PopupMenu(m)
        m.Destroy()

    # the right-click menu's items for the word at (line, col), if it's
    # misspelled and misspelled words are underlined, otherwise None. sets
    # self.spellingWord.
    def spellingMenu(self, line, col):
        self.spellingWord = None

        if (line is None) or not self.gd.cfgGl.checkSpelling or not spellcheck.gdict:
            return None

        found = spellcheck.wordAt(self.sp.lines[line].text, col)

        if not found:
            return None

        start, word = found
        sc = spellcheck.SpellChecker(self.sp, self.gd.scDict)

        if sc.isKnown(word):
            return None

        items = spellcheck.suggest(
            word, [self.gd.scDict, self.sp.scDict], SUGGESTIONS
        )
        self.spellingWord = (line, start, word, items)

        res = [(None, _("Spelling"))]
        res += zip(self.suggestionIds, items)

        if not items:
            res.append((None, _("No suggestions")))

        res.append((self.addWordId, _('Add "{}" to dictionary').format(word)))
        res.append(
            (self.addScriptWordId, _('Add "{}" to script dictionary').format(word))
        )

        return res

    def OnSpellingMenu(self, event):
        if not self.spellingWord:
            return

        line, col, word, items = self.spellingWord
        self.spellingWord = None
        id = event.GetId()

        # the other tabs are drawn again when they're switched to
        if id == int(self.addWordId):
            self.gd.scDict.add(word)
            self.gd.saveScDict()
        elif id == int(self.addScriptWordId):
            self.sp.scDict.add(word)
            self.sp.markChanged()
        else:
            self.clearAutoComp()
            i = [int(x) for x in self.suggestionIds].index(id)
            self.ed.replaceRange(line, col, len(word), items[i])
            self.sp.paginate()
            self.makeLineVisible(self.ed.line)

        self.updateScreen()

    # the items of the right-click menu's synonyms submenu for the word at
    # (line, col): a header for each sense, then its words. None if there
    # are none. sets self.synonymWord.
    def synonymsMenu(self, line, col):
        self.synonymWord = None

        if line is None:
            return None

        found = spellcheck.wordAt(self.sp.lines[line].text, col)

        if not found:
            return None

        start, word = found

        # a possessive's "'s" stays
        if textutil.lower(word).endswith("'s"):
            word = word[:-2]

        # the paragraph's text before the word, which tells "has walked"
        # from "walked"
        ls = self.sp.lines
        first = self.sp.getParaFirstIndexFromLine(line)
        before = "".join(ls[i].text + config.lb2str(ls[i].lb) for i in range(first, line))
        before += ls[line].text[:start]

        th = loadThesaurus(self.gd.mainFrame)
        posNames = {"n": _("noun"), "v": _("verb"), "a": _("adjective"), "r": _("adverb")}
        res = []
        words = []

        for sense in th.lookup(word, before):
            ws = [w for w in sense.words if w not in words][:SYNONYMS_PER_SENSE]

            if not ws:
                continue

            definition = sense.definition

            if len(definition) > SYNONYM_DEFINITION_LENGTH:
                definition = definition[: SYNONYM_DEFINITION_LENGTH - 1].rstrip() + "…"

            header = "{} ({}): {}".format(sense.word, posNames[sense.pos], definition)

            res.append((None, header))
            res += zip(self.synonymIds[len(words) :], ws)
            words += ws

            if len(res) - len(words) == SYNONYM_SENSES:
                break

        if not words:
            return None

        self.synonymWord = (line, start, word, words)

        return res

    def OnSynonymMenu(self, event):
        if not self.synonymWord:
            return

        line, col, word, words = self.synonymWord
        self.synonymWord = None

        i = [int(x) for x in self.synonymIds].index(event.GetId())
        self.clearAutoComp()
        self.ed.replaceRange(line, col, len(word), words[i])
        self.sp.paginate()
        self.makeLineVisible(self.ed.line)
        self.updateScreen()

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

    # put the cursor at the start of the given line, scrolling only if it
    # isn't on screen. used by the notes sidebar.
    def showLine(self, line):
        self.clearAutoComp()
        self.ed.clearMark()
        self.ed.gotoPos(line, 0)
        self.makeLineVisible(line)
        self.updateScreen()

    # the notes sidebar's edits, see Editor.addNote etc. addNote returns
    # (first line of the paragraph, index of the new note in its notes).
    def addNote(self, line, text):
        self.clearAutoComp()
        index = self.ed.addNote(line, text)
        self.updateScreen()

        return (self.sp.getParaFirstIndexFromLine(line), index)

    def setNote(self, line, index, note):
        self.clearAutoComp()

        if self.ed.setNote(line, index, note):
            self.updateScreen()

    def deleteNote(self, line, index):
        self.clearAutoComp()
        self.ed.deleteNote(line, index)
        self.updateScreen()

    # set the outline color of the scene containing the given line, or
    # remove it if color is None. used by the outline view.
    def setSceneColor(self, line, color):
        self.clearAutoComp()

        if self.ed.setSceneColor(line, color):
            self.updateScreen()

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

    # what's on screen, for drawing (see scriptpainter.Viewport). if
    # refresh, its scale is worked out anew.
    def getViewport(self, refresh=False):
        if refresh:
            return scriptpainter.Viewport.make(
                self.sp,
                self.ed,
                self.gd.cfgGui,
                self.gd.vm,
                self.GetClientSize(),
                self.FromDIP,
            )

        return scriptpainter.Viewport(
            self.sp,
            self.ed,
            self.gd.cfgGui,
            self.GetClientSize(),
            self.mm2p,
            self.pageW,
            self.pageH,
            self.chX,
            self.chY,
            self.FromDIP,
        )

    def OnPaint(self, event):
        if misc.doDblBuf:
            dc = wx.BufferedPaintDC(self, self.screenBuf)
        else:
            dc = wx.PaintDC(self)

        painter = scriptpainter.ScriptPainter(
            self.getViewport(),
            self.gd.vm,
            self.gd.cfgGl,
            self.gd.showFormatting,
            self.gd.scDict if self.gd.cfgGl.checkSpelling else None,
            self.newNoteLine,
        )
        self.titleButtonRect = painter.paint(dc)
        self.noteMarkers = painter.noteMarkers
        self.noteChecks = painter.noteChecks

        if self.noteEditor:
            self.noteEditor.update(self.noteMarkers)
