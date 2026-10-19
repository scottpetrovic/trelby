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
#
# a card is resized by dragging its bottom right corner (with shift held
# down, keeping its shape). its picture is fitted in it, so it grows and
# shrinks with the card.
#
# each card has an "x" in its top right corner that deletes it.
#
# several cards can be selected, by ctrl- or shift-clicking them or by
# dragging a box around them on the empty board (with ctrl or shift held
# down, adding to the selection), or all of them with ctrl+A. dragging one
# of them moves them all, and Delete deletes them all, each as one undo
# step.
#
# the board has its own zoom level (self.zoom, GlobalData.boardZoom), which
# scales the cards, their text and the grid, and the cards' text is in
# Courier Prime, like the script's.
#
# the board is drawn on a paper texture in the theme's board color (made
# when it's first needed, see paperShading), with the grid over it.

import copy
import io
import math
import os
import random

import wx
from wx.lib.wordwrap import wordwrap

import trelby.formats as formats
import trelby.screenplay.beatboard as beatboard
import trelby.ui.gutil as gutil
import trelby.ui.ids as ids
import trelby.ui.theming as theming
from trelby.ui.outline import getSceneColors, luminance, str2color, swatchBitmap

# the keyboard shortcut that switches between the script and the board (the
# View menu's Beat board item, see menus.py), shown in the right-click
# menus
BOARD_TOGGLE_KEY = "CTRL-SPACE"

# the cards' font size at 100% zoom, in points
CARD_FONT_SIZE = 9

# the board's background grid: the size of its squares, in unscaled
# pixels, and how many squares apart its stronger lines are
GRID = 40
GRID_MAJOR = 5

# the board's paper texture: the size of the square tile it repeats, in
# pixels, and how far its lightest and darkest spots are from the theme's
# board color (out of 255)
PAPER_TILE = 512
PAPER_DEPTH = 18

# space around the text on a card, in unscaled pixels
CARD_PAD = 14

# a card's picture is shown at most this big, in unscaled pixels, keeping
# its shape, and its card is at least PICTURE_CARD_MIN_WIDTH wide. the
# title under the picture takes CAPTION_HEIGHT more.
PICTURE_WIDTH = 240
PICTURE_HEIGHT = 180
PICTURE_CARD_MIN_WIDTH = 80
CAPTION_HEIGHT = 22

# the size of the corner of a card that resizes it when dragged, in
# unscaled pixels
RESIZE_GRIP = 14

# the size of the button that deletes a card, in its top right corner, and
# its distance from the corner, in unscaled pixels
CLOSE_SIZE = 14
CLOSE_MARGIN = 3

# how far apart the cards of several pictures added at once are put
CASCADE = 30

# the picture files the file dialog offers
PICTURE_WILDCARD = "*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.tif;*.tiff"


# smooth noise that repeats seamlessly: cells x cells random grays (from
# rnd, a random.Random), scaled up to size x size pixels. returns its
# grays, one byte per pixel. it's scaled up tiled 3 x 3 and the middle cut
# out, so its edges match.
def tiledNoise(rnd, cells, size):
    grays = bytes(rnd.randrange(256) for _ in range(cells * cells))
    rows = [grays[y * cells : (y + 1) * cells] * 3 for y in range(cells)] * 3

    img = wx.Image(cells * 3, cells * 3)
    img.SetData(bytes(v for v in b"".join(rows) for _ in range(3)))
    img = img.Scale(size * 3, size * 3, wx.IMAGE_QUALITY_BICUBIC)

    return img.GetSubImage(wx.Rect(size, size, size, size)).GetData()[::3]


# paper fibers: short, slightly curved light and dark strokes on mid gray,
# drawn again a tile away on each side so they continue across its edges.
# returns their grays like tiledNoise.
def paperFibers(rnd, size):
    bmp = wx.Bitmap(size, size)
    dc = wx.MemoryDC(bmp)
    dc.SetBackground(wx.Brush(wx.Colour(128, 128, 128)))
    dc.Clear()
    gc = wx.GraphicsContext.Create(dc)

    for _ in range(size * size // 250):
        x, y = rnd.uniform(0, size), rnd.uniform(0, size)
        angle = rnd.uniform(0, math.pi)
        length = rnd.uniform(4, 22)
        dx, dy = math.cos(angle) * length, math.sin(angle) * length
        bendX, bendY = rnd.uniform(-3, 3), rnd.uniform(-3, 3)
        v = 128 + rnd.choice((-1, 1)) * rnd.randint(30, 90)
        gc.SetPen(wx.Pen(wx.Colour(v, v, v, 90), 1))

        for ox in (-size, 0, size):
            for oy in (-size, 0, size):
                path = gc.CreatePath()
                path.MoveToPoint(x + ox, y + oy)
                path.AddQuadCurveToPoint(
                    x + ox + dx / 2 + bendX,
                    y + oy + dy / 2 + bendY,
                    x + ox + dx,
                    y + oy + dy,
                )
                gc.StrokePath(path)

    del gc
    dc.SelectObject(wx.NullBitmap)

    return bmp.ConvertToImage().GetData()[::3]


# the paper texture's shading, made the first time it's needed (see
# paperShading)
_paperShading = None


# the paper texture as a PAPER_TILE square of how much lighter or darker
# than the board color each pixel is, from -1 to 1, as bytes (128 + 127 *
# that): blotches of three sizes, fibers and a fine grain. it's the same
# every time.
def paperShading():
    global _paperShading

    if _paperShading is None:
        size = PAPER_TILE
        rnd = random.Random(7)

        layers = (
            (tiledNoise(rnd, 4, size), 0.3),
            (tiledNoise(rnd, 16, size), 0.25),
            (tiledNoise(rnd, 64, size), 0.3),
            (rnd.randbytes(size * size), 0.22),
            (paperFibers(rnd, size), 0.9),
        )

        # the weights add up to more than 1, but the layers seldom all
        # go the same way
        (a, wa), (b, wb), (c, wc), (d, wd), (e, we) = layers
        shading = (
            wa * (pa - 128)
            + wb * (pb - 128)
            + wc * (pc - 128)
            + wd * (pd - 128)
            + we * (pe - 128)
            for pa, pb, pc, pd, pe in zip(a, b, c, d, e)
        )
        _paperShading = bytes(max(1, min(255, 128 + round(s))) for s in shading)

    return _paperShading


# a tile of the paper texture in 'color' (a wx.Colour), as a wx.Bitmap
def paperTile(color):
    shading = paperShading()
    data = bytearray(len(shading) * 3)

    for i, base in enumerate((color.Red(), color.Green(), color.Blue())):
        table = bytes(
            max(0, min(255, base + round((s - 128) / 127 * PAPER_DEPTH)))
            for s in range(256)
        )
        data[i::3] = shading.translate(table)

    img = wx.Image(PAPER_TILE, PAPER_TILE)
    img.SetData(bytes(data))

    return wx.Bitmap(img)


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


# the size of 'img' (a wx.Image) fitted in w x h, keeping its shape, and
# not made bigger unless 'grow'
def fitPicture(img, w, h, grow):
    iw, ih = img.GetWidth(), img.GetHeight()
    scale = min(w / iw, h / ih)

    if not grow:
        scale = min(scale, 1)

    return (max(1, round(iw * scale)), max(1, round(ih * scale)))


# lets picture files, and pictures from other programs, be dropped on the
# board. scripts dropped on it are opened, as on the rest of the main window
# (trelbyframe.ScriptDropTarget).
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
            scripts = [p for p in paths if formats.openFormat(p)]
            pictures = [p for p in paths if not formats.openFormat(p)]

            if scripts:
                wx.CallAfter(self.view.panel.gd.mainFrame.openFiles, scripts)

            if pictures:
                wx.CallAfter(self.view.addPictureFiles, pictures, pos)
        else:
            bmp = self.bitmap.GetBitmap()
            wx.CallAfter(self.view.addBitmap, bmp, pos)

        return wx.DragCopy


# a scrollable area with the cards drawn on it. board coordinates are
# unscaled pixels, which px turns into the window's at the zoom level.
# panel is the trelbypanel.MyPanel it's in, whose ctrl has the script.
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

        # the selected cards, the last one selected last (see selected)
        self.selection = []

        # while cards are being dragged: (card, x, y, starts, click),
        # where card is the one grabbed, (x, y) is where on it, starts is
        # [(card, x, y)] for each card being moved, where it was, and click
        # is a card to select alone if the mouse is let go without moving
        # it (one of several selected ones that was clicked), or None.
        # otherwise None.
        self.drag = None

        # while a box is being dragged out on the board to select the cards
        # in it: (x, y, x, y, cards), the corner it started at and the
        # mouse position, in the window's unscrolled coordinates, and the
        # cards selected before it (when it adds to them, otherwise []).
        # otherwise None.
        self.band = None

        # while a card is being resized: (card, x, y, width, height, its
        # Beat.width, its Beat.height), where (x, y) is where the mouse was
        # pressed, on the board, and the rest are the card's size when it
        # was. otherwise None.
        self.resize = None

        # whether the mouse is over a card's resizing corner
        self.overGrip = False

        # the card whose delete button the mouse is over, or None
        self.hover = None

        # whether the last left button press was on a delete button
        self.lastClickButton = False

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

        # the zoom level, in percent (see setZoom)
        self.zoom = 100

        # the cards' pictures, decoded: Beat.image -> wx.Image, or None if
        # it can't be read. and those pictures as bitmaps at the size
        # they're drawn at: (Beat.image, width, height) -> wx.Bitmap.
        self.pictures = {}
        self.bitmaps = {}

        # the board's paper texture: (its color, a tile of it as a
        # wx.Bitmap), or None until it's first drawn
        self.paper = None

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
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeaveWindow)
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
        self.band = None
        self.resize = None
        self.pan = None
        self.selection = []
        self.hover = None
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
        beat.color = beatboard.DEFAULT_COLOR
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
            beat.color = beatboard.DEFAULT_COLOR
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
    # pixels, or None if it has none. on a card that hasn't been resized,
    # it's at most PICTURE_WIDTH x PICTURE_HEIGHT, and the card is made to
    # fit it; on one that has, it fills the card's picture area.
    def pictureSize(self, beat):
        img = self.getPicture(beat)

        if not img:
            return None

        if not beat.width:
            return fitPicture(img, PICTURE_WIDTH, PICTURE_HEIGHT, False)

        return fitPicture(img, *self.pictureArea(beat), True)

    # the space for beat's picture on its card, (width, height) in
    # unscaled pixels: the card without its padding and caption
    def pictureArea(self, beat):
        w, h = self.cardSize(beat)
        w -= 2 * CARD_PAD
        h -= 2 * CARD_PAD

        if beat.getTitle():
            h -= CAPTION_HEIGHT

        return (max(1, w), max(1, h))

    # the size of beat's card, (width, height) in unscaled pixels
    def cardSize(self, beat):
        if beat.width:
            return (beat.width, beat.height)

        size = self.pictureSize(beat)

        if not size:
            return (beatboard.CARD_WIDTH, beatboard.CARD_HEIGHT)

        w, h = size
        h += 2 * CARD_PAD

        if beat.getTitle():
            h += CAPTION_HEIGHT

        return (max(PICTURE_CARD_MIN_WIDTH, w + 2 * CARD_PAD), h)

    # n unscaled pixels (board coordinates) in the window's pixels, at the
    # zoom level
    def px(self, n):
        return self.FromDIP(round(n * self.zoom / 100))

    # the window's pixels p in unscaled pixels (the opposite of px)
    def unpx(self, p):
        return round(self.ToDIP(p) * 100 / self.zoom)

    # the cards' font, at the zoom level
    def cardFont(self):
        font = wx.Font(self.GetFont())
        font.SetFaceName(gutil.courierFace())
        font.SetFractionalPointSize(CARD_FONT_SIZE * self.zoom / 100)

        return font

    # zoom to 'zoom' percent, keeping the point at the mouse position pos
    # (by default the middle of the window) where it is
    def setZoom(self, zoom, pos=None):
        if zoom == self.zoom:
            return

        # the text control would be in the wrong place and size
        self.finishEdit(True)

        if pos is None:
            w, h = self.GetClientSize()
            pos = wx.Point(w // 2, h // 2)

        x, y = self.CalcUnscrolledPosition(pos.x, pos.y)
        scale = zoom / self.zoom

        self.zoom = zoom
        self.bitmaps = {}
        self.updateVirtualSize()
        self.scrollTo(round(x * scale) - pos.x, round(y * scale) - pos.y)
        self.Refresh()

    # the rectangle of a card, in the window's unscrolled coordinates
    def cardRect(self, beat):
        px = self.px
        w, h = self.cardSize(beat)

        return wx.Rect(px(beat.x), px(beat.y), px(w), px(h))

    # convert a mouse position to the board's coordinates
    def toBoard(self, pos):
        x, y = self.CalcUnscrolledPosition(pos.x, pos.y)

        return (self.unpx(x), self.unpx(y))

    # return the topmost card at the mouse position pos, or None
    def hitTest(self, pos):
        x, y = self.CalcUnscrolledPosition(pos.x, pos.y)

        for beat in reversed(self.board.beats):
            if self.cardRect(beat).Contains(x, y):
                return beat

        return None

    # the corner of beat's card that resizes it, in the window's
    # unscrolled coordinates
    def gripRect(self, beat):
        r = self.cardRect(beat)
        size = self.px(RESIZE_GRIP)

        return wx.Rect(r.GetRight() + 1 - size, r.GetBottom() + 1 - size, size, size)

    # the card whose resizing corner is at the mouse position pos (and
    # isn't under another card), or None
    def gripHitTest(self, pos):
        beat = self.hitTest(pos)

        if beat and self.gripRect(beat).Contains(self.CalcUnscrolledPosition(pos)):
            return beat

        return None

    # the button that deletes beat, in its top right corner, in the
    # window's unscrolled coordinates
    def closeRect(self, beat):
        r = self.cardRect(beat)
        size = self.px(CLOSE_SIZE)
        margin = self.px(CLOSE_MARGIN)

        return wx.Rect(r.GetRight() + 1 - margin - size, r.y + margin, size, size)

    # the card whose delete button is at the mouse position pos (and isn't
    # under another card), or None
    def closeHitTest(self, pos):
        beat = self.hitTest(pos)

        if beat and self.closeRect(beat).Contains(self.CalcUnscrolledPosition(pos)):
            return beat

        return None

    # note which card's delete button the mouse is over at pos (None when
    # it's not in the window), redrawing it and changing the tooltip if
    # that changed
    def setHover(self, pos):
        hover = self.closeHitTest(pos) if pos else None

        if hover is self.hover:
            return

        self.hover = hover

        if hover:
            self.SetToolTip(_("Delete card"))
        else:
            self.UnsetToolTip()

        self.Refresh()

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
            gap = self.px(beatboard.GAP)
            self.scrollTo(r.x - gap, r.y - gap)

    # show the hand cursor while space is held down or the board is being
    # panned, and the resizing one over a card's corner or while resizing
    def updateCursor(self):
        if self.pan or self.spaceDown:
            self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        elif self.resize or self.overGrip:
            self.SetCursor(wx.Cursor(wx.CURSOR_SIZENWSE))
        else:
            self.SetCursor(wx.NullCursor)

    def startPan(self, event):
        if self.drag or self.band or self.resize or self.pan:
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

    # the card selected last, or None if none is
    @property
    def selected(self):
        return self.selection[-1] if self.selection else None

    # select beat alone, or nothing if None
    def select(self, beat):
        self.setSelection([beat] if beat else [])

    # select the cards in the list 'beats', in that order
    def setSelection(self, beats):
        self.selection = list(beats)
        self.Refresh()

    # select or unselect beat, keeping the others selected
    def toggleSelected(self, beat):
        if beat in self.selection:
            self.setSelection([b for b in self.selection if b is not beat])
        else:
            self.setSelection(self.selection + [beat])

    def selectAll(self):
        self.setSelection(self.board.beats)

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
            # no scroll bar: it's an index card, its text fits on it
            style=wx.TE_MULTILINE | wx.TE_NO_VSCROLL | wx.BORDER_NONE,
        )
        ctrl.SetBackgroundColour(bg)
        ctrl.SetForegroundColour(fg)
        ctrl.SetFont(self.cardFont())
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
            self.selection = [b for b in self.selection if b is not beat]
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
        self.deleteCards([beat])

    # delete the cards in the list 'beats', as one undo step
    def deleteCards(self, beats):
        if not beats:
            return

        beats = list(beats)
        self.board.beats = [b for b in self.board.beats if b not in beats]
        self.selection = [b for b in self.selection if b not in beats]

        if self.hover in beats:
            self.hover = None
            self.UnsetToolTip()

        self.updateVirtualSize()
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

        self.drawPaper(dc, boardColor)
        self.drawGrid(dc, boardColor, textColor)
        self.drawHint(dc, boardColor, textColor)

        for beat in self.board.beats:
            self.drawCard(dc, beat)

        self.drawBand(dc)

    # draw the box being dragged out to select cards, if one is, in a tint
    # of the accent color
    def drawBand(self, dc):
        if not self.band:
            return

        accent = self.getColors()[5]
        tint = wx.Colour(accent.Red(), accent.Green(), accent.Blue(), 40)

        gc = wx.GraphicsContext.Create(dc)
        gc.SetPen(wx.Pen(accent, max(1, self.FromDIP(1))))
        gc.SetBrush(wx.Brush(tint))

        r = self.bandRect()
        gc.DrawRectangle(r.x, r.y, r.width, r.height)

    # the box being dragged out to select cards, in the window's unscrolled
    # coordinates
    def bandRect(self):
        x0, y0, x1, y1 = self.band[:4]

        return wx.Rect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))

    # draw the button that deletes beat, an x that gets a circle behind it
    # when the mouse is over it
    def drawClose(self, dc, beat, cardBg, cardFg):
        r = self.closeRect(beat)
        cx = r.x + r.width // 2
        cy = r.y + r.height // 2

        if self.hover is beat:
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(theming.blendColors(cardBg, cardFg, 0.15)))
            dc.DrawCircle(cx, cy, r.width // 2)
            color = cardFg
        else:
            color = theming.blendColors(cardFg, cardBg, 0.5)

        d = max(2, r.width // 4)
        dc.SetPen(wx.Pen(color, max(1, self.FromDIP(1))))
        dc.DrawLine(cx - d, cy - d, cx + d + 1, cy + d + 1)
        dc.DrawLine(cx - d, cy + d, cx + d + 1, cy - d - 1)

    # draw how to add cards in the middle of the window's size, measured
    # from the board's top left corner, so it scrolls with the board.
    # cards are drawn over it.
    def drawHint(self, dc, boardColor, textColor):
        w, h = self.GetClientSize()

        dc.SetFont(self.GetFont().Scaled(2.2))
        dc.SetTextForeground(theming.blendColors(boardColor, textColor, 0.35))

        text = _("Double-click to add a card, or drop pictures here")
        tw, th = dc.GetTextExtent(text)
        dc.DrawText(text, (w - tw) // 2, (h - th) // 2)

    # fill the visible part of the board with the paper texture in the
    # board color. it's fixed to the board, so it scrolls with it, but it
    # isn't zoomed.
    def drawPaper(self, dc, boardColor):
        key = boardColor.GetRGB()

        if not self.paper or self.paper[0] != key:
            self.paper = (key, paperTile(boardColor))

        tile = self.paper[1]
        size = PAPER_TILE

        x0, y0 = self.CalcUnscrolledPosition(0, 0)
        w, h = self.GetClientSize()

        for x in range(x0 // size * size, x0 + w, size):
            for y in range(y0 // size * size, y0 + h, size):
                dc.DrawBitmap(tile, x, y)

    # draw the board's grid, faint lines a little toward the text color,
    # so it works on light and dark themes alike, with every
    # GRID_MAJOR'th line a bit stronger
    def drawGrid(self, dc, boardColor, textColor):
        step = max(2, self.px(GRID))

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
        pad = self.px(CARD_PAD)

        return self.cardRect(beat).Deflate(pad, pad)

    def drawCard(self, dc, beat):
        dip = self.FromDIP
        px = self.px
        _board, _bg, _fg, border, shadow, accent = self.getColors()
        cardBg, cardFg = self.getCardColors(beat)

        r = self.cardRect(beat)
        radius = px(6)

        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(shadow))
        dc.DrawRoundedRectangle(r.x + px(2), r.y + px(3), r.width, r.height, radius)

        if beat in self.selection:
            dc.SetPen(wx.Pen(accent, dip(2)))
        else:
            dc.SetPen(wx.Pen(border))

        dc.SetBrush(wx.Brush(cardBg))
        dc.DrawRoundedRectangle(r, radius)

        inside = self.textRect(beat)
        dc.SetClippingRegion(inside)
        self.drawContents(dc, beat, inside, cardBg, cardFg)
        dc.DestroyClippingRegion()

        self.drawClose(dc, beat, cardBg, cardFg)

        if beat in self.selection:
            self.drawGrip(dc, beat, theming.blendColors(cardFg, cardBg, 0.5))

    # draw beat's text or picture in 'r', the inside of its card
    def drawContents(self, dc, beat, r, cardBg, cardFg):
        px = self.px
        width = r.width
        x = r.x
        y = r.y
        bottom = r.GetBottom()

        font = self.cardFont()
        dim = theming.blendColors(cardFg, cardBg, 0.4)

        title = beat.getTitle().upper()

        if self.getPicture(beat):
            height = r.height

            if title:
                height -= px(CAPTION_HEIGHT)
                dc.SetFont(font)
                dc.SetTextForeground(cardFg)
                s = wx.Control.Ellipsize(title, dc, wx.ELLIPSIZE_END, width)
                th = dc.GetTextExtent(s)[1]
                dc.DrawText(s, x, bottom - (px(CAPTION_HEIGHT) + th) // 2)

            self.drawPicture(dc, beat, x, y, width, height)

            return

        if not title:
            dc.SetFont(font.Italic())
            dc.SetTextForeground(dim)
            dc.DrawText(_("Empty card"), x, y)

            return

        # the title in capitals, a line under it, then the rest of the text
        lines = beat.text.strip().splitlines()
        rest = "\n".join(lines[1:]).strip()

        dc.SetFont(font)
        dc.SetTextForeground(cardFg)
        lh = dc.GetTextExtent("X")[1]

        for i, text in enumerate((title, rest)):
            if not text:
                continue

            for s in wordwrap(text, width, dc).split("\n"):
                if y + lh > bottom:
                    break

                dc.DrawText(s, x, y)
                y += lh

            if i == 0:
                y += px(4)
                dc.SetPen(wx.Pen(dim, max(1, self.FromDIP(1))))
                dc.DrawLine(x, y, x + width, y)
                y += px(6)

    # draw beat's picture centered in the width x height pixels at (x, y)
    def drawPicture(self, dc, beat, x, y, width, height):
        w, h = (self.px(n) for n in self.pictureSize(beat))
        key = (beat.image, w, h)
        bmp = self.bitmaps.get(key)

        if bmp:
            pass
        elif self.resize and (self.resize[0] is beat):
            # while the card is being resized, scaled quicker and not kept
            img = self.getPicture(beat).Scale(w, h, wx.IMAGE_QUALITY_BILINEAR)
            bmp = wx.Bitmap(img)
        else:
            img = self.getPicture(beat).Scale(w, h, wx.IMAGE_QUALITY_HIGH)
            bmp = self.bitmaps[key] = wx.Bitmap(img)

        dc.DrawBitmap(bmp, x + (width - w) // 2, y + (height - h) // 2, True)

    # draw the lines in the corner of beat's card that show it can be
    # resized from there
    def drawGrip(self, dc, beat, color):
        px = self.px
        r = self.cardRect(beat)
        right = r.GetRight() - px(3)
        bottom = r.GetBottom() - px(3)

        dc.SetPen(wx.Pen(color, max(1, self.FromDIP(1))))

        for n in (4, 8):
            d = px(n)
            dc.DrawLine(right - d, bottom, right, bottom - d)

    def OnLeftDown(self, event):
        self.finishEdit(True)
        self.SetFocus()

        if self.pan:
            return

        if self.spaceDown:
            self.startPan(event)

            return

        pos = event.GetPosition()
        closing = self.closeHitTest(pos)
        self.lastClickButton = bool(closing)

        if closing:
            self.deleteCard(closing)
            self.setHover(pos)

            return

        beat = self.hitTest(pos)
        adding = event.ControlDown() or event.ShiftDown()

        # on the empty board, start a box selecting the cards in it
        if not beat:
            x, y = self.CalcUnscrolledPosition(pos.x, pos.y)
            self.band = (x, y, x, y, self.selection if adding else [])
            self.setSelection(self.band[4])
            self.CaptureMouse()

            return

        x, y = self.toBoard(pos)

        if self.gripHitTest(pos) is beat:
            if beat not in self.selection:
                self.select(beat)

            w, h = self.cardSize(beat)
            self.resize = (beat, x, y, w, h, beat.width, beat.height)
            self.updateCursor()
            self.CaptureMouse()

            return

        click = None

        if adding:
            self.toggleSelected(beat)

            # one that was unselected isn't moved
            if beat not in self.selection:
                return
        elif beat in self.selection:
            # the others stay selected, to be moved along with it, unless
            # it's let go without moving it
            if len(self.selection) > 1:
                click = beat
        else:
            self.select(beat)

        starts = [(b, b.x, b.y) for b in self.selection]
        self.drag = (beat, x - beat.x, y - beat.y, starts, click)
        self.CaptureMouse()

    def OnMotion(self, event):
        if self.pan:
            x, y, vx, vy = self.pan
            pos = event.GetPosition()
            self.scrollTo(vx - (pos.x - x), vy - (pos.y - y))

            return

        if self.resize:
            if event.Dragging() and event.LeftIsDown():
                self.resizeTo(event)

            return

        if self.band:
            if event.Dragging() and event.LeftIsDown():
                self.bandTo(event.GetPosition())

            return

        if not self.drag:
            over = bool(self.gripHitTest(event.GetPosition()))

            if over != self.overGrip:
                self.overGrip = over
                self.updateCursor()

            self.setHover(event.GetPosition())

        if not (self.drag and event.Dragging() and event.LeftIsDown()):
            return

        beat, grabX, grabY, starts = self.drag[:4]
        x, y = self.toBoard(event.GetPosition())
        xs = [sx for _b, sx, _sy in starts]
        ys = [sy for _b, _sx, sy in starts]
        startX, startY = next((sx, sy) for b, sx, sy in starts if b is beat)

        # how far they're moved, keeping them all on the board
        dx = min(max(x - grabX - startX, -min(xs)), beatboard.MAX_COORD - max(xs))
        dy = min(max(y - grabY - startY, -min(ys)), beatboard.MAX_COORD - max(ys))

        for b, sx, sy in starts:
            b.x = sx + dx
            b.y = sy + dy

        self.Refresh()

    def OnLeaveWindow(self, event):
        event.Skip()

        if not (self.drag or self.band or self.resize or self.pan):
            self.setHover(None)

    # cards that were moved come to the front, in the order they were in,
    # as one undo step. a card clicked among several selected ones without
    # moving it is selected alone.
    def endDrag(self):
        if not self.drag:
            return

        _beat, _x, _y, starts, click = self.drag
        self.drag = None

        if any((b.x, b.y) != (x, y) for b, x, y in starts):
            moved = [b for b, _x, _y in starts]
            beats = self.board.beats
            self.board.beats = [b for b in beats if b not in moved] + [
                b for b in beats if b in moved
            ]
            self.updateVirtualSize()
            self.commit()
            self.Refresh()
        elif click:
            self.select(click)

    # the box selecting cards was dragged to the mouse position pos: select
    # the cards it touches, after the ones selected before it
    def bandTo(self, pos):
        x0, y0, _x, _y, before = self.band
        x, y = self.CalcUnscrolledPosition(pos.x, pos.y)
        self.band = (x0, y0, x, y, before)

        r = self.bandRect()
        inside = [
            b
            for b in self.board.beats
            if (b not in before) and r.Intersects(self.cardRect(b))
        ]

        self.setSelection(before + inside)

    def endBand(self):
        if not self.band:
            return

        self.band = None
        self.Refresh()

    # resize the card being resized for the mouse event 'event', keeping
    # its shape if shift is held down
    def resizeTo(self, event):
        beat, x0, y0, w0, h0 = self.resize[:5]
        x, y = self.toBoard(event.GetPosition())
        w = w0 + x - x0
        h = h0 + y - y0

        if event.ShiftDown():
            scale = max(
                w / w0,
                h / h0,
                beatboard.MIN_CARD_WIDTH / w0,
                beatboard.MIN_CARD_HEIGHT / h0,
            )
            w, h = round(w0 * scale), round(h0 * scale)

        beat.setSize(w, h)
        self.updateVirtualSize()
        self.Refresh()

    # a card that was resized comes to the front
    def endResize(self):
        if not self.resize:
            return

        beat, _x, _y, w, h, oldWidth, oldHeight = self.resize
        self.resize = None
        self.updateCursor()

        # back where it started, it keeps its old size, which may be the
        # default one
        if self.cardSize(beat) == (w, h):
            beat.width, beat.height = oldWidth, oldHeight
            self.Refresh()

            return

        self.board.beats.remove(beat)
        self.board.beats.append(beat)

        # forget the pictures at the sizes they're no longer shown at
        shown = set()

        for b in self.board.beats:
            size = self.pictureSize(b)

            if size:
                shown.add((b.image,) + tuple(self.px(n) for n in size))

        self.bitmaps = {k: v for k, v in self.bitmaps.items() if k in shown}

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
        self.endBand()
        self.endResize()

    def OnCaptureLost(self, event):
        self.endDrag()
        self.endBand()
        self.endResize()
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
        # with ctrl held down, it zooms in or out around the mouse, like
        # the script
        if event.ControlDown():
            rotation = event.GetWheelRotation()

            if rotation:
                gd = self.panel.gd
                zoom = gd.getZoomStep(1 if rotation > 0 else -1)
                gd.mainFrame.setZoom(zoom, event.GetPosition())

            return

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
        # the second click on a delete button: where a card was deleted,
        # nothing is added or edited
        if self.lastClickButton:
            return

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
            # held down, it keeps repeating. CTRL-SPACE switches to the
            # script (BOARD_TOGGLE_KEY), and mustn't leave the board
            # panning.
            if not (self.spaceDown or event.ControlDown()):
                self.spaceDown = True
                self.updateCursor()
        elif self.selection and (kc in (wx.WXK_DELETE, wx.WXK_BACK)):
            self.deleteCards(self.selection)
        elif self.selected and (kc in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)):
            self.startEdit(self.selected)
        elif event.ControlDown() and (kc == ord("A")):
            self.selectAll()
        elif self.selection and (kc == wx.WXK_ESCAPE):
            self.select(None)
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

        # a card among several selected ones keeps them selected, and the
        # color and deleting are for all of them
        if beat not in self.selection:
            self.select(beat)

        cards = list(self.selection) if beat else []
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
            self.addScriptItem(menu)
            self.PopupMenu(menu, pos)
            menu.Destroy()
            self.updateVirtualSize()

            return

        add(menu, _("Edit text"), lambda: self.startEdit(beat))

        colorMenu = wx.Menu()
        add(colorMenu, _("No color"), lambda: self.setColor(cards, None))

        for name, color in getSceneColors():
            item = wx.MenuItem(colorMenu, -1, name)
            item.SetBitmap(swatchBitmap(color, color == beat.color))
            colorMenu.Append(item)
            self.Bind(
                wx.EVT_MENU,
                lambda e, c=color: self.setColor(cards, c),
                id=item.GetId(),
            )

        menu.AppendSubMenu(colorMenu, _("Color"))

        if beat.image:
            add(menu, _("Change picture..."), lambda: self.choosePicture(beat))
            add(menu, _("Remove picture"), lambda: self.setPicture(beat, None))
        else:
            add(menu, _("Add picture..."), lambda: self.choosePicture(beat))

        resized = [b for b in cards if b.width]

        if resized:
            add(menu, _("Reset size"), lambda: self.resetSizes(resized))

        menu.AppendSeparator()

        if len(cards) > 1:
            label = _("Delete %d cards") % len(cards)
        else:
            label = _("Delete card")

        add(menu, label, lambda: self.deleteCards(cards))
        self.addScriptItem(menu)

        self.PopupMenu(menu, pos)
        menu.Destroy()

    # add the item that goes back to the script to a right-click menu. it
    # has the View menu's Beat board item's id, so the main window runs it.
    def addScriptItem(self, menu):
        menu.AppendSeparator()
        menu.Append(
            ids.ID_VIEW_BEAT_BOARD, _("Go to script") + "\t" + BOARD_TOGGLE_KEY
        )

    # resize beat to w x h, or back to its default size if w is None
    def setSize(self, beat, w, h=None):
        beat.setSize(w, h)
        self.updateVirtualSize()
        self.commit()
        self.Refresh()

    # put the cards in the list 'beats' back to their default size, as one
    # undo step
    def resetSizes(self, beats):
        for beat in beats:
            beat.setSize(None)

        self.updateVirtualSize()
        self.commit()
        self.Refresh()

    # give the cards in the list 'beats' the color 'color', as one undo step
    def setColor(self, beats, color):
        for beat in beats:
            beat.color = color

        self.commit()
        self.Refresh()
