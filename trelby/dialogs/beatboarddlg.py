# the beat board dialog: the script's index cards on a board, where they
# can be added, written on, dragged around, colored and linked to scenes.
# see screenplay/beatboard.py for the cards and how links work. the dialog
# works on a copy of the board, which scriptactions.beatBoardDlg puts in
# the script (with ed.setBeatBoard) when it's closed with OK.

import copy

import wx
from wx.lib.wordwrap import wordwrap

import trelby.screenplay.beatboard as beatboard
import trelby.ui.gutil as gutil
import trelby.ui.theming as theming
import trelby.ui.widgets as widgets
from trelby.screenplay.constants import SCENE
from trelby.ui.outline import getSceneColors, luminance, str2color, swatchBitmap

# the board's background grid: the size of its squares, in unscaled
# pixels, and how many squares apart its stronger lines are
GRID = 40
GRID_MAJOR = 5

# space around the text on a card, in unscaled pixels, and the size of
# the link's text at its bottom compared to the rest
CARD_PAD = 8
LINK_FONT_SCALE = 0.85


# return the text a scene is shown with: its number and heading
def sceneLabel(item):
    if item.sceneNr:
        return "%s. %s" % (item.sceneNr, item.heading)

    return item.heading


class BeatBoardDlg(wx.Dialog):
    # sp is the script, which the dialog doesn't change. its pagination
    # should be up to date, for the scene numbers.
    def __init__(self, parent, sp):
        wx.Dialog.__init__(
            self,
            parent,
            -1,
            _("Beat board"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX,
        )

        self.sp = sp

        # the board being edited
        self.board = copy.deepcopy(sp.beatBoard)

        # scene ids for the scenes linked to that didn't have one yet:
        # {first line of the scene: id}
        self.newIds = {}

        # if not None, the line to move the cursor to after closing
        self.gotoLine = None

        # the scenes and act breaks, and the line each scene id is on
        # (including the new ones)
        self.outline = sp.getOutline()
        self.itemsByLine = {it.startLine: it for it in self.outline}
        self.idLines = sp.getSceneIdLines()

        dip = self.FromDIP

        vsizer = wx.BoxSizer(wx.VERTICAL)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        addBtn = wx.Button(self, -1, _("Add card"))
        hsizer.Add(addBtn)

        scenesBtn = wx.Button(self, -1, _("Add cards for scenes"))
        scenesBtn.SetToolTip(
            _("Add a card linked to each scene that no card is linked to yet")
        )
        hsizer.Add(scenesBtn, 0, wx.LEFT, dip(10))

        hint = wx.StaticText(
            self,
            -1,
            _(
                "Double-click the board to add a card, or a card to write on"
                " it. Drag cards to move them, and right-click one to color it"
                " or link it to a scene. To move around the board, drag with"
                " the middle mouse button, or hold down space and drag."
            ),
        )
        hint.Wrap(dip(560))
        hsizer.Add(hint, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, dip(20))

        vsizer.Add(hsizer, 0, wx.EXPAND)

        self.canvas = BoardCanvas(self)
        self.canvas.SetMinSize(dip(wx.Size(960, 560)))
        vsizer.Add(self.canvas, 1, wx.EXPAND | wx.TOP, dip(10))

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add((1, 1), 1)

        cancelBtn = gutil.createStockButton(self, _("Cancel"))
        hsizer.Add(cancelBtn, 0, wx.LEFT, 10)

        okBtn = gutil.createStockButton(self, "OK")
        hsizer.Add(okBtn, 0, wx.LEFT, 10)

        vsizer.Add(hsizer, 0, wx.EXPAND | wx.TOP, 10)

        gutil.finishWindow(self, vsizer, center=True)

        self.Bind(wx.EVT_BUTTON, self.OnAddCard, id=addBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnAddSceneCards, id=scenesBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=cancelBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=okBtn.GetId())

        self.canvas.updateVirtualSize()
        self.canvas.SetFocus()

    # return the first line of the scene 'beat' is linked to, or -1 if it
    # isn't linked or the scene has been deleted
    def getLinkedLine(self, beat):
        if not beat.sceneId:
            return -1

        return self.idLines.get(beat.sceneId, -1)

    # the text shown at the bottom of a card for its link, or None if it
    # isn't linked
    def getLinkLabel(self, beat):
        if not beat.sceneId:
            return None

        item = self.itemsByLine.get(self.getLinkedLine(beat))

        if not item:
            return _("Linked scene was deleted")

        return sceneLabel(item)

    # link 'beat' to the scene starting at 'line', giving the scene an id
    # if it doesn't have one yet
    def linkBeat(self, beat, line):
        sid = self.sp.getSceneId(line) or self.newIds.get(line)

        if not sid:
            sid = beatboard.newSceneId(
                beatboard.usedSceneIds(self.sp)
                | set(self.idLines)
                | self.board.getSceneIds()
            )
            self.newIds[line] = sid
            self.idLines[sid] = line

        beat.sceneId = sid

    # add a new card at (x, y) and let the user write on it, on the board.
    # the card goes away again if nothing is written on it.
    def addCard(self, x, y):
        beat = beatboard.Beat("", x, y)
        self.board.beats.append(beat)
        self.canvas.updateVirtualSize()
        self.canvas.startEdit(beat, True)

        return beat

    # let the user choose the scene for beat to link to
    def chooseScene(self, beat):
        if not self.outline:
            wx.MessageBox(
                _("The script has no scenes to link to."),
                _("Beat board"),
                wx.OK,
                self,
            )

            return

        linked = self.getLinkedLine(beat)
        sel = next(
            (i for i, it in enumerate(self.outline) if it.startLine == linked), 0
        )

        dlg = SceneChooserDlg(self, [sceneLabel(it) for it in self.outline], sel)

        if dlg.ShowModal() == wx.ID_OK:
            self.linkBeat(beat, self.outline[dlg.selection].startLine)
            self.canvas.Refresh()

        dlg.Destroy()

    # close the dialog, keeping the changes, and go to the scene beat is
    # linked to
    def gotoScene(self, beat):
        self.canvas.finishEdit(True)
        self.gotoLine = self.getLinkedLine(beat)
        self.EndModal(wx.ID_OK)

    def OnAddCard(self, event):
        x, y = beatboard.findFreeSpot(self.board)
        self.addCard(x, y)

    # the button gives the board the focus back, so that space pans it
    # instead of pressing the button again
    def OnAddSceneCards(self, event):
        self.canvas.finishEdit(True)
        self.canvas.SetFocus()
        linked = {self.getLinkedLine(b) for b in self.board.beats}
        added = None

        for it in self.outline:
            if (it.lt != SCENE) or (it.startLine in linked):
                continue

            text = it.heading

            if it.summary:
                text += "\n" + it.summary

            x, y = beatboard.findFreeSpot(self.board)
            beat = beatboard.Beat(text, x, y)
            self.linkBeat(beat, it.startLine)
            self.board.beats.append(beat)
            added = added or beat

        if not added:
            wx.MessageBox(
                _("Every scene already has a card linked to it."),
                _("Beat board"),
                wx.OK,
                self,
            )

            return

        self.canvas.updateVirtualSize()
        self.canvas.select(added)
        self.canvas.makeVisible(added)

    def OnOK(self, event):
        self.canvas.finishEdit(True)
        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)


# the board itself, a scrollable area with the cards drawn on it. board
# coordinates are unscaled pixels, which FromDIP turns into the window's.
class BoardCanvas(wx.ScrolledWindow):
    def __init__(self, dlg):
        wx.ScrolledWindow.__init__(
            self, dlg, -1, style=wx.BORDER_NONE | wx.WANTS_CHARS
        )

        self.dlg = dlg
        self.board = dlg.board

        # the selected card, or None
        self.selected = None

        # while a card is being dragged: (card, x, y), where (x, y) is
        # where on the card it was grabbed. otherwise None.
        self.drag = None

        # while the board is being panned (dragged with the middle button,
        # or the left one with space held down): (x, y, view x, view y),
        # the mouse position and the scroll position when it started, in
        # pixels. otherwise None.
        self.pan = None

        # whether the space bar is held down, which makes dragging pan
        self.spaceDown = False

        # while a card's text is being edited on the board: (card, the
        # text control on top of it, whether the card is new). otherwise
        # None.
        self.editing = None

        self.cfgGui = theming.currentCfgGui()

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        # scrolling by pixels, so panning follows the mouse exactly. the
        # wheel scrolls by more (see OnMouseWheel).
        self.SetScrollRate(1, 1)

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDClick)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_MIDDLE_DOWN, self.OnMiddleDown)
        self.Bind(wx.EVT_MIDDLE_UP, self.OnMiddleUp)
        self.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self.OnCaptureLost)
        self.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind(wx.EVT_KEY_UP, self.OnKeyUp)
        self.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)

    # called by theming.themeWindow
    def applyTheme(self, cfgGui):
        self.cfgGui = cfgGui
        self.Refresh()

    # the colors used: (board, card, card text, card border, shadow,
    # selection)
    def getColors(self):
        cg = self.cfgGui

        if cg:
            return (
                cg.workspaceColor,
                cg.textBgColor,
                cg.textColor,
                cg.pageBorderColor,
                cg.pageShadowColor,
                cg.accentColor,
            )

        ss = wx.SystemSettings.GetColour

        return (
            ss(wx.SYS_COLOUR_APPWORKSPACE),
            ss(wx.SYS_COLOUR_WINDOW),
            ss(wx.SYS_COLOUR_WINDOWTEXT),
            ss(wx.SYS_COLOUR_GRAYTEXT),
            ss(wx.SYS_COLOUR_3DSHADOW),
            ss(wx.SYS_COLOUR_HIGHLIGHT),
        )

    # the rectangle of a card, in the window's unscrolled coordinates
    def cardRect(self, beat):
        dip = self.FromDIP

        return wx.Rect(
            dip(beat.x),
            dip(beat.y),
            dip(beatboard.CARD_WIDTH),
            dip(beatboard.CARD_HEIGHT),
        )

    # convert a mouse position to the board's coordinates
    def toBoard(self, pos):
        x, y = self.CalcUnscrolledPosition(pos.x, pos.y)

        return (self.ToDIP(x), self.ToDIP(y))

    # return the topmost card at the mouse position pos, or None
    def hitTest(self, pos):
        x, y = self.CalcUnscrolledPosition(pos.x, pos.y)

        for beat in reversed(self.board.beats):
            if self.cardRect(beat).Contains(x, y):
                return beat

        return None

    # make the board big enough to scroll to every card, and a screenful
    # past them, so there's always empty space to pan to and put cards in
    def updateVirtualSize(self):
        cw, ch = self.GetClientSize()
        w = h = 0

        for beat in self.board.beats:
            r = self.cardRect(beat)
            w = max(w, r.GetRight())
            h = max(h, r.GetBottom())

        self.SetVirtualSize(w + cw, h + ch)

    # scroll to (x, y), in pixels, as far as the board goes
    def scrollTo(self, x, y):
        # Scroll treats -1 as "leave as it is", so never go below 0
        self.Scroll(max(0, x), max(0, y))

    # scroll so that beat is visible
    def makeVisible(self, beat):
        r = self.cardRect(beat)
        x, y = self.CalcScrolledPosition(r.x, r.y)
        cw, ch = self.GetClientSize()

        if (x < 0) or (y < 0) or (x + r.width > cw) or (y + r.height > ch):
            gap = self.FromDIP(beatboard.GAP)
            self.scrollTo(r.x - gap, r.y - gap)

    # show the hand cursor while space is held down or the board is being
    # panned
    def updateCursor(self):
        if self.pan or self.spaceDown:
            self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        else:
            self.SetCursor(wx.NullCursor)

    def startPan(self, event):
        if self.drag or self.pan:
            return

        pos = event.GetPosition()
        vx, vy = self.GetViewStart()
        self.pan = (pos.x, pos.y, vx, vy)
        self.updateCursor()

        if not self.HasCapture():
            self.CaptureMouse()

    def endPan(self):
        if not self.pan:
            return

        self.pan = None
        self.updateCursor()

        if self.HasCapture():
            self.ReleaseMouse()

    # select beat (or nothing, if None), and bring it to the front
    def select(self, beat):
        self.selected = beat

        if beat:
            self.board.beats.remove(beat)
            self.board.beats.append(beat)

        self.Refresh()

    # edit beat's text on the board, in a text control on top of the card.
    # a new card is deleted if it's left empty.
    def startEdit(self, beat, isNew=False):
        self.finishEdit(True)
        self.select(beat)
        self.makeVisible(beat)

        r = self.textRect(beat)
        bg, fg = self.getCardColors(beat)

        ctrl = wx.TextCtrl(
            self,
            -1,
            beat.text,
            self.CalcScrolledPosition(r.GetTopLeft()),
            r.GetSize(),
            style=wx.TE_MULTILINE | wx.BORDER_NONE,
        )
        ctrl.SetBackgroundColour(bg)
        ctrl.SetForegroundColour(fg)
        ctrl.SetFont(self.GetFont())
        ctrl.SetToolTip(
            _("Ctrl+Enter or click outside the card to finish, Esc to cancel")
        )

        ctrl.Bind(wx.EVT_CHAR_HOOK, self.OnEditKey)
        ctrl.Bind(wx.EVT_KILL_FOCUS, lambda e: self.OnEditKillFocus(e, ctrl))

        self.editing = (beat, ctrl, isNew)

        ctrl.SetFocus()
        ctrl.SetInsertionPointEnd()

    # stop editing a card's text, if one is being edited, keeping the new
    # text or not. 'refocus' gives the board the focus back.
    def finishEdit(self, keep, refocus=False):
        if not self.editing:
            return

        beat, ctrl, isNew = self.editing
        self.editing = None

        if keep:
            beat.text = ctrl.GetValue()

        # this can be called from the control's own event handlers, so
        # it's destroyed later
        ctrl.Hide()
        wx.CallAfter(ctrl.Destroy)

        if refocus:
            self.SetFocus()

        if isNew and not beat.text.strip():
            self.deleteCard(beat)
            self.updateVirtualSize()

        self.Refresh()

    def OnEditKey(self, event):
        kc = event.GetKeyCode()

        if kc == wx.WXK_ESCAPE:
            self.finishEdit(False, True)
        elif event.ControlDown() and (kc in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)):
            self.finishEdit(True, True)
        else:
            event.Skip()

    # clicking elsewhere ends the editing. it's done after the focus has
    # moved, and only if that control is still being edited with.
    def OnEditKillFocus(self, event, ctrl):
        event.Skip()

        def finish():
            if self.editing and (self.editing[1] is ctrl):
                self.finishEdit(True)

        wx.CallAfter(finish)

    def deleteCard(self, beat):
        self.board.beats.remove(beat)

        if self.selected is beat:
            self.selected = None

        self.Refresh()

    def OnSize(self, event):
        self.updateVirtualSize()
        event.Skip()

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        self.DoPrepareDC(dc)
        self.paint(dc)

    # draw the visible part of the board on dc, which is set up for the
    # scroll position
    def paint(self, dc):
        boardColor, _card, textColor = self.getColors()[:3]
        dc.SetBackground(wx.Brush(boardColor))
        dc.Clear()

        self.drawGrid(dc, boardColor, textColor)

        for beat in self.board.beats:
            self.drawCard(dc, beat)

    # draw the board's grid, faint lines a little toward the text color,
    # so it works on light and dark themes alike, with every
    # GRID_MAJOR'th line a bit stronger
    def drawGrid(self, dc, boardColor, textColor):
        step = self.FromDIP(GRID)

        # the visible part of the board, in its unscrolled coordinates
        x0, y0 = self.CalcUnscrolledPosition(0, 0)
        w, h = self.GetClientSize()
        x1, y1 = x0 + w, y0 + h

        minorPen = wx.Pen(theming.blendColors(boardColor, textColor, 0.05))
        majorPen = wx.Pen(theming.blendColors(boardColor, textColor, 0.1))

        for i in range(x0 // step, x1 // step + 1):
            dc.SetPen(majorPen if (i % GRID_MAJOR) == 0 else minorPen)
            dc.DrawLine(i * step, y0, i * step, y1)

        for i in range(y0 // step, y1 // step + 1):
            dc.SetPen(majorPen if (i % GRID_MAJOR) == 0 else minorPen)
            dc.DrawLine(x0, i * step, x1, i * step)

    # return (background, text color) of beat's card
    def getCardColors(self, beat):
        _board, cardBg, cardFg = self.getColors()[:3]

        if beat.color:
            cardBg = str2color(beat.color)

            # the card colors are light, but a theme's text may not be dark
            if luminance(cardBg) - luminance(cardFg) < 0.4:
                cardFg = wx.Colour(32, 32, 32)

        return (cardBg, cardFg)

    # the part of beat's card its text goes in, above the link if it has
    # one, in the window's unscrolled coordinates
    def textRect(self, beat):
        pad = self.FromDIP(CARD_PAD)
        r = self.cardRect(beat).Deflate(pad, pad)

        if beat.sceneId:
            dc = wx.ClientDC(self)
            dc.SetFont(self.GetFont().Scaled(LINK_FONT_SCALE))
            r.height -= dc.GetTextExtent("X")[1] + self.FromDIP(4)

        return r

    def drawCard(self, dc, beat):
        dip = self.FromDIP
        _board, _bg, _fg, border, shadow, accent = self.getColors()
        cardBg, cardFg = self.getCardColors(beat)

        r = self.cardRect(beat)
        radius = dip(6)

        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(shadow))
        dc.DrawRoundedRectangle(r.x + dip(2), r.y + dip(3), r.width, r.height, radius)

        if beat is self.selected:
            dc.SetPen(wx.Pen(accent, dip(2)))
        else:
            dc.SetPen(wx.Pen(border))

        dc.SetBrush(wx.Brush(cardBg))
        dc.DrawRoundedRectangle(r, radius)

        pad = dip(CARD_PAD)
        width = r.width - 2 * pad
        x = r.x + pad
        y = r.y + pad
        bottom = r.GetBottom() - pad

        dc.SetClippingRegion(r.x + pad, r.y + pad, width, r.height - 2 * pad)

        font = self.GetFont()
        smallFont = font.Scaled(LINK_FONT_SCALE)
        dim = theming.blendColors(cardFg, cardBg, 0.4)

        # the link goes at the bottom
        link = self.dlg.getLinkLabel(beat)

        if link:
            dc.SetFont(smallFont)
            lh = dc.GetTextExtent("X")[1]
            bottom -= lh

            missing = self.dlg.getLinkedLine(beat) == -1
            dc.SetTextForeground(dim if missing else cardFg)
            dc.DrawText(
                wx.Control.Ellipsize(
                    "→ " + link, dc, wx.ELLIPSIZE_END, width
                ),
                x,
                bottom,
            )

            bottom -= dip(4)

        title = beat.getTitle()

        if not title:
            dc.SetFont(font.Italic())
            dc.SetTextForeground(dim)
            dc.DrawText(_("Empty card"), x, y)
            dc.DestroyClippingRegion()

            return

        # the title in bold, then the rest of the text
        lines = beat.text.strip().splitlines()
        rest = "\n".join(lines[1:]).strip()

        dc.SetTextForeground(cardFg)

        for text, f in ((title, font.Bold()), (rest, font)):
            if not text:
                continue

            dc.SetFont(f)
            lh = dc.GetTextExtent("X")[1]

            for s in wordwrap(text, width, dc).split("\n"):
                if y + lh > bottom:
                    break

                dc.DrawText(s, x, y)
                y += lh

            y += dip(4)

        dc.DestroyClippingRegion()

    def OnLeftDown(self, event):
        self.finishEdit(True)
        self.SetFocus()

        if self.pan:
            return

        if self.spaceDown:
            self.startPan(event)

            return

        beat = self.hitTest(event.GetPosition())
        self.select(beat)

        if beat:
            x, y = self.toBoard(event.GetPosition())
            self.drag = (beat, x - beat.x, y - beat.y)
            self.CaptureMouse()

    def OnMotion(self, event):
        if self.pan:
            x, y, vx, vy = self.pan
            pos = event.GetPosition()
            self.scrollTo(vx - (pos.x - x), vy - (pos.y - y))

            return

        if not (self.drag and event.Dragging() and event.LeftIsDown()):
            return

        beat, dx, dy = self.drag
        x, y = self.toBoard(event.GetPosition())
        beat.x = min(max(0, x - dx), beatboard.MAX_COORD)
        beat.y = min(max(0, y - dy), beatboard.MAX_COORD)

        self.Refresh()

    def endDrag(self):
        if self.drag:
            self.drag = None
            self.updateVirtualSize()

    def OnLeftUp(self, event):
        if self.pan:
            self.endPan()

            return

        if self.HasCapture():
            self.ReleaseMouse()

        self.endDrag()

    def OnCaptureLost(self, event):
        self.endDrag()
        self.pan = None
        self.updateCursor()

    def OnMiddleDown(self, event):
        self.finishEdit(True)
        self.SetFocus()
        self.startPan(event)

    def OnMiddleUp(self, event):
        self.endPan()

    # the wheel scrolls up and down, or with shift held down (or a
    # horizontal wheel), left and right
    def OnMouseWheel(self, event):
        lines = event.GetWheelRotation() / event.GetWheelDelta()
        amount = int(lines * event.GetLinesPerAction() * self.FromDIP(20))
        vx, vy = self.GetViewStart()

        if event.GetWheelAxis() == wx.MOUSE_WHEEL_HORIZONTAL:
            self.scrollTo(vx + amount, vy)
        elif event.ShiftDown():
            self.scrollTo(vx - amount, vy)
        else:
            self.scrollTo(vx, vy - amount)

    def OnLeftDClick(self, event):
        self.finishEdit(True)

        if self.spaceDown:
            return

        beat = self.hitTest(event.GetPosition())

        if beat:
            self.startEdit(beat)

            return

        # a new card, centered where the board was clicked
        x, y = self.toBoard(event.GetPosition())
        x = max(0, x - beatboard.CARD_WIDTH // 2)
        y = max(0, y - beatboard.CARD_HEIGHT // 2)

        self.dlg.addCard(x, y)

    def OnKeyDown(self, event):
        kc = event.GetKeyCode()

        if kc == wx.WXK_SPACE:
            # held down, it keeps repeating
            if not self.spaceDown:
                self.spaceDown = True
                self.updateCursor()
        elif self.selected and (kc in (wx.WXK_DELETE, wx.WXK_BACK)):
            self.deleteCard(self.selected)
        elif self.selected and (kc in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)):
            self.startEdit(self.selected)
        else:
            event.Skip()

    def OnKeyUp(self, event):
        if event.GetKeyCode() == wx.WXK_SPACE:
            self.spaceDown = False
            self.updateCursor()
        else:
            event.Skip()

    # the key-up of space goes elsewhere then
    def OnKillFocus(self, event):
        self.spaceDown = False
        self.updateCursor()
        event.Skip()

    def OnContextMenu(self, event):
        self.finishEdit(True)
        pos = event.GetPosition()

        # from the keyboard, the menu is for the selected card
        if pos == wx.DefaultPosition:
            beat = self.selected
            pos = wx.Point(0, 0)

            if beat:
                pos = self.CalcScrolledPosition(self.cardRect(beat).GetTopLeft())
        else:
            pos = self.ScreenToClient(pos)
            beat = self.hitTest(pos)

        self.select(beat)
        menu = wx.Menu()

        def add(m, label, handler, enable=True):
            item = m.Append(-1, label)
            item.Enable(enable)
            self.Bind(wx.EVT_MENU, lambda e: handler(), id=item.GetId())

            return item

        if not beat:
            x, y = self.toBoard(pos)
            add(menu, _("Add card here"), lambda: self.dlg.addCard(x, y))
            self.PopupMenu(menu, pos)
            menu.Destroy()
            self.updateVirtualSize()

            return

        add(menu, _("Edit text"), lambda: self.startEdit(beat))

        colorMenu = wx.Menu()
        add(colorMenu, _("No color"), lambda: self.setColor(beat, None))

        for name, color in getSceneColors():
            item = wx.MenuItem(colorMenu, -1, name)
            item.SetBitmap(swatchBitmap(color, color == beat.color))
            colorMenu.Append(item)
            self.Bind(
                wx.EVT_MENU,
                lambda e, c=color: self.setColor(beat, c),
                id=item.GetId(),
            )

        menu.AppendSubMenu(colorMenu, _("Color"))
        menu.AppendSeparator()

        add(menu, _("Link to scene..."), lambda: self.dlg.chooseScene(beat))
        add(
            menu,
            _("Go to scene"),
            lambda: self.dlg.gotoScene(beat),
            self.dlg.getLinkedLine(beat) != -1,
        )
        add(menu, _("Unlink from scene"), lambda: self.unlink(beat), bool(beat.sceneId))
        menu.AppendSeparator()
        add(menu, _("Delete card"), lambda: self.deleteCard(beat))

        self.PopupMenu(menu, pos)
        menu.Destroy()

    def setColor(self, beat, color):
        beat.color = color
        self.Refresh()

    def unlink(self, beat):
        beat.sceneId = None
        self.Refresh()


# choosing a scene from a list of their labels. the chosen one's index is
# in 'selection' after OK.
class SceneChooserDlg(wx.Dialog):
    def __init__(self, parent, labels, sel):
        wx.Dialog.__init__(
            self,
            parent,
            -1,
            _("Link to scene"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        dip = self.FromDIP

        vsizer = wx.BoxSizer(wx.VERTICAL)

        self.list = widgets.ThemedListBox(
            self, -1, size=dip(wx.Size(420, 360)), choices=labels
        )
        self.list.SetSelection(sel)
        vsizer.Add(self.list, 1, wx.EXPAND)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add((1, 1), 1)

        cancelBtn = gutil.createStockButton(self, _("Cancel"))
        hsizer.Add(cancelBtn, 0, wx.LEFT, 10)

        okBtn = gutil.createStockButton(self, "OK")
        hsizer.Add(okBtn, 0, wx.LEFT, 10)

        vsizer.Add(hsizer, 0, wx.EXPAND | wx.TOP, 10)

        gutil.finishWindow(self, vsizer, center=True)

        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=cancelBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=okBtn.GetId())
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, self.OnOK)

        self.list.SetFocus()

    def OnOK(self, event):
        self.selection = self.list.GetSelection()

        if self.selection != -1:
            self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)
