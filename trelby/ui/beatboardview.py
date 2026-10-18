# the beat board view: a script's index cards on a board, shown in a tab
# instead of the script and the outline (see MyPanel.showBeatBoard), where
# they can be added, written on, dragged around and colored. see
# screenplay/beatboard.py for the cards.
#
# the view works on its own copy of the script's board, and every change
# made on it (a card added, moved, written on, colored or deleted) is put
# in the script with ed.setBeatBoard, as one undo step. reload takes the
# script's board again, after an undo or when the script is replaced.
#
# a card can have a picture (Beat.image), shown instead of its text with
# its title under it. pictures are added from the right-click menu, by
# dropping picture files (or pictures from other programs) on the board,
# or by pasting them.

import copy
import io
import os

import wx
from wx.lib.wordwrap import wordwrap

import trelby.screenplay.beatboard as beatboard
import trelby.ui.gutil as gutil
import trelby.ui.theming as theming
from trelby.ui.outline import getSceneColors, luminance, str2color, swatchBitmap

# the board's background grid: the size of its squares, in unscaled
# pixels, and how many squares apart its stronger lines are
GRID = 40
GRID_MAJOR = 5

# space around the text on a card, in unscaled pixels
CARD_PAD = 8

# a card's picture is shown at most this big, in unscaled pixels, keeping
# its shape, and its card is at least PICTURE_CARD_MIN_WIDTH wide. the
# title under the picture takes CAPTION_HEIGHT more.
PICTURE_WIDTH = 240
PICTURE_HEIGHT = 180
PICTURE_CARD_MIN_WIDTH = 80
CAPTION_HEIGHT = 22

# how far apart the cards of several pictures added at once are put
CASCADE = 30

# the picture files the file dialog offers
PICTURE_WILDCARD = "*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.tif;*.tiff"


# the picture file 'data' (bytes) as a wx.Image, or None if wx can't read
# it
def decodePicture(data):
    if not data:
        return None

    # wx would show a message box for a file it can't read
    noLog = wx.LogNull()
    img = wx.Image(io.BytesIO(data), wx.BITMAP_TYPE_ANY)
    del noLog

    return img if img.IsOk() else None


def isPngOrJpeg(data):
    return data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8\xff")


# 'img' (a wx.Image) as a card's picture: no bigger than
# beatboard.MAX_IMAGE_SIDE, as a PNG if it has transparency and a JPEG
# otherwise. None if it can't be saved.
def encodePicture(img):
    w, h = img.GetWidth(), img.GetHeight()
    side = max(w, h)

    if side > beatboard.MAX_IMAGE_SIDE:
        scale = beatboard.MAX_IMAGE_SIDE / side
        img = img.Scale(
            max(1, round(w * scale)),
            max(1, round(h * scale)),
            wx.IMAGE_QUALITY_HIGH,
        )

    stream = io.BytesIO()

    if img.HasAlpha() or img.HasMask():
        ok = img.SaveFile(stream, wx.BITMAP_TYPE_PNG)
    else:
        img.SetOption(wx.IMAGE_OPTION_QUALITY, "85")
        ok = img.SaveFile(stream, wx.BITMAP_TYPE_JPEG)

    return stream.getvalue() if ok else None


# a picture file's contents (bytes) as kept on a card (Beat.image): as they
# are if it's a PNG or JPEG that isn't too big, otherwise made smaller and
# converted (see encodePicture). None if it isn't a picture wx can read.
def imageData(data):
    img = decodePicture(data)

    if not img:
        return None

    if (
        isPngOrJpeg(data)
        and (len(data) <= beatboard.MAX_IMAGE_BYTES)
        and (max(img.GetWidth(), img.GetHeight()) <= beatboard.MAX_IMAGE_SIDE)
    ):
        return data

    return encodePicture(img)


# the picture in the file at 'path' as kept on a card, or None if it can't
# be read or isn't a picture
def loadPictureFile(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None

    return imageData(data)


# lets picture files, and pictures from other programs, be dropped on the
# board
class BoardDropTarget(wx.DropTarget):
    def __init__(self, view):
        wx.DropTarget.__init__(self)

        self.view = view

        self.files = wx.FileDataObject()
        self.bitmap = wx.BitmapDataObject()

        self.data = wx.DataObjectComposite()
        self.data.Add(self.files, True)
        self.data.Add(self.bitmap)
        self.SetDataObject(self.data)

    def OnDragOver(self, x, y, defResult):
        return wx.DragCopy

    def OnData(self, x, y, defResult):
        if not self.GetData():
            return wx.DragNone

        pos = wx.Point(x, y)

        # added after the drop has finished, so that the program the
        # pictures came from doesn't wait for a message box
        if self.data.GetReceivedFormat().GetType() == wx.DF_FILENAME:
            paths = self.files.GetFilenames()
            wx.CallAfter(self.view.addPictureFiles, paths, pos)
        else:
            bmp = self.bitmap.GetBitmap()
            wx.CallAfter(self.view.addBitmap, bmp, pos)

        return wx.DragCopy


# a scrollable area with the cards drawn on it. board coordinates are
# unscaled pixels, which FromDIP turns into the window's. panel is the
# trelbypanel.MyPanel it's in, whose ctrl has the script.
class BeatBoardView(wx.ScrolledWindow):
    def __init__(self, parent, panel):
        wx.ScrolledWindow.__init__(
            self, parent, -1, style=wx.BORDER_NONE | wx.WANTS_CHARS
        )

        # the cards' x coordinates are from the left, and a right-to-left
        # window would mirror them
        gutil.keepLeftToRight(self)

        self.panel = panel

        # the board shown, a copy of the script's (see the top of the
        # module)
        self.board = beatboard.BeatBoard()

        # the selected card, or None
        self.selected = None

        # while a card is being dragged: (card, x, y, start x, start y),
        # where (x, y) is where on the card it was grabbed, and the start
        # is where the card was. otherwise None.
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

        # the cards' pictures, decoded: Beat.image -> wx.Image, or None if
        # it can't be read. and those pictures as bitmaps at the size
        # they're drawn at: (Beat.image, width, height) -> wx.Bitmap.
        self.pictures = {}
        self.bitmaps = {}

        self.SetDropTarget(BoardDropTarget(self))

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

    # show sp's board (by default the panel's script's) instead of the
    # one shown, dropping any text being written on a card
    def reload(self, sp=None):
        sp = sp or self.panel.ctrl.sp

        if self.editing:
            ctrl = self.editing[1]
            self.editing = None
            ctrl.Hide()
            wx.CallAfter(ctrl.Destroy)

        if self.HasCapture():
            self.ReleaseMouse()

        self.drag = None
        self.pan = None
        self.selected = None
        self.board = copy.deepcopy(sp.beatBoard)

        # forget the pictures of cards that are gone
        used = {b.image for b in self.board.beats if b.image}
        self.pictures = {k: v for k, v in self.pictures.items() if k in used}
        self.bitmaps = {k: v for k, v in self.bitmaps.items() if k[0] in used}

        self.updateVirtualSize()
        self.updateCursor()
        self.Refresh()

    # put the board in the script, if it has changed, as an undo step
    def commit(self):
        ctrl = self.panel.ctrl

        if ctrl.ed.setBeatBoard(copy.deepcopy(self.board)):
            # the modified mark and the undo buttons
            ctrl.updateScreen(redraw=False)

    # add a new card at (x, y) and let the user write on it. the card goes
    # away again if nothing is written on it.
    def addCard(self, x, y):
        beat = beatboard.Beat("", x, y)
        self.board.beats.append(beat)
        self.updateVirtualSize()
        self.startEdit(beat, True)

        return beat

    # add a card for each of 'images' (Beat.image values), the first one
    # centered at the mouse position pos (or the middle of the window if
    # None) and the others below and right of it, as one undo step. the
    # last one is selected. returns the new cards.
    def addPictureCards(self, images, pos=None):
        if pos is None:
            w, h = self.GetClientSize()
            pos = wx.Point(w // 2, h // 2)

        x, y = self.toBoard(pos)
        beats = []

        for i, image in enumerate(images):
            beat = beatboard.Beat()
            beat.image = image

            w, h = self.cardSize(beat)
            off = i * CASCADE
            beat.x = min(max(0, x - w // 2 + off), beatboard.MAX_COORD)
            beat.y = min(max(0, y - h // 2 + off), beatboard.MAX_COORD)

            self.board.beats.append(beat)
            beats.append(beat)

        if beats:
            self.updateVirtualSize()
            self.select(beats[-1])
            self.commit()

        return beats

    # add cards for the picture files in 'paths' (see addPictureCards),
    # telling the user about the files that aren't pictures
    def addPictureFiles(self, paths, pos=None):
        self.finishEdit(True)

        images = []
        bad = []

        for path in paths:
            image = loadPictureFile(path)

            if image:
                images.append(image)
            else:
                bad.append(os.path.basename(path))

        beats = self.addPictureCards(images, pos)
        self.showUnreadable(bad)

        return beats

    # tell the user that the files called 'names' aren't pictures, if
    # there are any
    def showUnreadable(self, names):
        if names:
            gutil.messageBox(
                _("These files are not pictures Trelby can read:")
                + "\n\n"
                + "\n".join(names),
                _("Error"),
                wx.OK | wx.ICON_ERROR,
                self,
            )

    # add a card for a picture from another program, a wx.Bitmap
    def addBitmap(self, bmp, pos=None):
        self.finishEdit(True)

        image = encodePicture(bmp.ConvertToImage()) if bmp.IsOk() else None

        return self.addPictureCards([image] if image else [], pos)

    # what the clipboard has that can be pasted on the board: ("files",
    # paths), ("bitmap", wx.Bitmap) or None
    def getClipboardPictures(self):
        cb = wx.TheClipboard

        if not cb.Open():
            return None

        try:
            if cb.IsSupported(wx.DataFormat(wx.DF_FILENAME)):
                obj = wx.FileDataObject()

                if cb.GetData(obj):
                    return ("files", obj.GetFilenames())

            if cb.IsSupported(wx.DataFormat(wx.DF_BITMAP)):
                obj = wx.BitmapDataObject()

                if cb.GetData(obj):
                    return ("bitmap", obj.GetBitmap())
        finally:
            cb.Close()

        return None

    def canPaste(self):
        cb = wx.TheClipboard

        if not cb.Open():
            return False

        try:
            return cb.IsSupported(wx.DataFormat(wx.DF_FILENAME)) or cb.IsSupported(
                wx.DataFormat(wx.DF_BITMAP)
            )
        finally:
            cb.Close()

    # paste the pictures on the clipboard at the mouse position pos, or
    # where the mouse is if it's over the board, otherwise in the middle
    def paste(self, pos=None):
        if pos is None:
            pos = self.ScreenToClient(wx.GetMousePosition())

            if not wx.Rect(self.GetClientSize()).Contains(pos):
                pos = None

        got = self.getClipboardPictures()

        if not got:
            wx.Bell()

            return []

        if got[0] == "files":
            return self.addPictureFiles(got[1], pos)

        return self.addBitmap(got[1], pos)

    # ask for picture files to add at the mouse position pos
    def choosePictures(self, pos):
        paths = self.askPictureFiles(True)

        if paths:
            self.addPictureFiles(paths, pos)

    # ask for a picture to put on beat, replacing the one it has
    def choosePicture(self, beat):
        paths = self.askPictureFiles(False)

        if not paths:
            return

        image = loadPictureFile(paths[0])

        if image:
            self.setPicture(beat, image)
        else:
            self.showUnreadable([os.path.basename(paths[0])])

    # return the picture files the user picks, [] if none
    def askPictureFiles(self, multiple):
        style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST

        if multiple:
            style |= wx.FD_MULTIPLE

        dlg = wx.FileDialog(
            self,
            _("Choose pictures") if multiple else _("Choose a picture"),
            wildcard="%s|%s|%s|*" % (_("Pictures"), PICTURE_WILDCARD, _("All files")),
            style=style,
        )

        paths = dlg.GetPaths() if dlg.ShowModal() == wx.ID_OK else []
        dlg.Destroy()

        return paths

    # give beat the picture 'image' (a Beat.image value, or None to take
    # its picture away)
    def setPicture(self, beat, image):
        beat.image = image
        self.updateVirtualSize()
        self.commit()
        self.Refresh()

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

    # beat's picture as a wx.Image, or None if it has none or it can't be
    # read
    def getPicture(self, beat):
        if not beat.image:
            return None

        if beat.image not in self.pictures:
            self.pictures[beat.image] = decodePicture(beat.image)

        return self.pictures[beat.image]

    # the size beat's picture is shown at, (width, height) in unscaled
    # pixels, or None if it has none
    def pictureSize(self, beat):
        img = self.getPicture(beat)

        if not img:
            return None

        w, h = img.GetWidth(), img.GetHeight()
        scale = min(PICTURE_WIDTH / w, PICTURE_HEIGHT / h, 1)

        return (max(1, round(w * scale)), max(1, round(h * scale)))

    # the size of beat's card, (width, height) in unscaled pixels
    def cardSize(self, beat):
        size = self.pictureSize(beat)

        if not size:
            return (beatboard.CARD_WIDTH, beatboard.CARD_HEIGHT)

        w, h = size
        h += 2 * CARD_PAD

        if beat.getTitle():
            h += CAPTION_HEIGHT

        return (max(PICTURE_CARD_MIN_WIDTH, w + 2 * CARD_PAD), h)

    # the rectangle of a card, in the window's unscrolled coordinates
    def cardRect(self, beat):
        dip = self.FromDIP
        w, h = self.cardSize(beat)

        return wx.Rect(dip(beat.x), dip(beat.y), dip(w), dip(h))

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

    # select beat, or nothing if None
    def select(self, beat):
        self.selected = beat
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

        if isNew and not (beat.text.strip() or beat.image):
            self.board.beats.remove(beat)
            self.selected = None
            self.updateVirtualSize()

        self.commit()
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

        self.commit()
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
        self.drawHint(dc, boardColor, textColor)

        for beat in self.board.beats:
            self.drawCard(dc, beat)

    # draw how to add cards in the middle of the window's size, measured
    # from the board's top left corner, so it scrolls with the board.
    # cards are drawn over it.
    def drawHint(self, dc, boardColor, textColor):
        w, h = self.GetClientSize()

        dc.SetFont(self.GetFont().Scaled(1.4))
        dc.SetTextForeground(theming.blendColors(boardColor, textColor, 0.35))

        text = _("Double-click to add a card, or drop pictures here")
        tw, th = dc.GetTextExtent(text)
        dc.DrawText(text, (w - tw) // 2, (h - th) // 2)

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

    # the part of beat's card its text goes in, in the window's unscrolled
    # coordinates
    def textRect(self, beat):
        pad = self.FromDIP(CARD_PAD)

        return self.cardRect(beat).Deflate(pad, pad)

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
        dim = theming.blendColors(cardFg, cardBg, 0.4)

        title = beat.getTitle()

        if self.getPicture(beat):
            self.drawPicture(dc, beat, x, y, width)

            if title:
                dc.SetFont(font.Bold())
                dc.SetTextForeground(cardFg)
                s = wx.Control.Ellipsize(title, dc, wx.ELLIPSIZE_END, width)
                th = dc.GetTextExtent(s)[1]
                dc.DrawText(s, x, bottom - (dip(CAPTION_HEIGHT) + th) // 2)

            dc.DestroyClippingRegion()

            return

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

    # draw beat's picture at the top of its card, centered in 'width'
    # pixels from x
    def drawPicture(self, dc, beat, x, y, width):
        w, h = (self.FromDIP(n) for n in self.pictureSize(beat))
        key = (beat.image, w, h)
        bmp = self.bitmaps.get(key)

        if not bmp:
            img = self.getPicture(beat).Scale(w, h, wx.IMAGE_QUALITY_HIGH)
            bmp = self.bitmaps[key] = wx.Bitmap(img)

        dc.DrawBitmap(bmp, x + (width - w) // 2, y, True)

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
            self.drag = (beat, x - beat.x, y - beat.y, beat.x, beat.y)
            self.CaptureMouse()

    def OnMotion(self, event):
        if self.pan:
            x, y, vx, vy = self.pan
            pos = event.GetPosition()
            self.scrollTo(vx - (pos.x - x), vy - (pos.y - y))

            return

        if not (self.drag and event.Dragging() and event.LeftIsDown()):
            return

        beat, dx, dy, _x, _y = self.drag
        x, y = self.toBoard(event.GetPosition())
        beat.x = min(max(0, x - dx), beatboard.MAX_COORD)
        beat.y = min(max(0, y - dy), beatboard.MAX_COORD)

        self.Refresh()

    # a card that was moved comes to the front
    def endDrag(self):
        if not self.drag:
            return

        beat, _dx, _dy, x, y = self.drag
        self.drag = None

        if (beat.x, beat.y) != (x, y):
            self.board.beats.remove(beat)
            self.board.beats.append(beat)
            self.updateVirtualSize()
            self.commit()
            self.Refresh()

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

        self.addCard(x, y)

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
            add(menu, _("Add card here"), lambda: self.addCard(x, y))
            add(menu, _("Add picture here..."), lambda: self.choosePictures(pos))
            add(menu, _("Paste picture"), lambda: self.paste(pos), self.canPaste())
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

        if beat.image:
            add(menu, _("Change picture..."), lambda: self.choosePicture(beat))
            add(menu, _("Remove picture"), lambda: self.setPicture(beat, None))
        else:
            add(menu, _("Add picture..."), lambda: self.choosePicture(beat))

        menu.AppendSeparator()
        add(menu, _("Delete card"), lambda: self.deleteCard(beat))

        self.PopupMenu(menu, pos)
        menu.Destroy()

    def setColor(self, beat, color):
        beat.color = color
        self.commit()
        self.Refresh()
