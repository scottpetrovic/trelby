# the Home screen, shown in place of the tabs while no script is open (see
# MyFrame.setHomeShown): the ways to start a script, and the scripts opened
# recently. it's drawn by hand, in the theme's colors, as a column of rows
# on a card in the middle of the window: a click on a row (or Enter on the
# one picked with the arrow keys) runs its Action, pops up a menu of
# Actions, or opens the recent script.

import os
import time

import wx

import trelby.ui.icons as icons
import trelby.ui.theming as theming

# sizes, in DIPs: the card's width at most, the space around it and inside
# it, the rows' heights, and the gap before a section's heading
CARD_WIDTH = 560
MARGIN = 32
PAD = 28
ACTION_ROW = 34
RECENT_ROW = 48
SECTION_GAP = 24
LOGO_SIZE = 48

# the kinds of row: one that runs an Action, one that pops up a menu of
# Actions, and a recent script
ACTION, MENU, RECENT = list(range(3))


# a row: its kind, its label, the dimmer text under the label (a recent
# script's folder) and at its right (a shortcut, or when the script was
# changed), and what it does: an Action's name, a list of them, or the
# index of the recent file. rect is where it is, set by HomeView.layout.
class Row:
    def __init__(self, kind, label, value, detail="", note="", dim=False):
        self.kind = kind
        self.label = label
        self.value = value
        self.detail = detail
        self.note = note

        # whether the label is shown dimmed, for a recent file that's gone
        self.dim = dim

        self.rect = wx.Rect()


# "CTRL-N" -> "Ctrl+N"
def shortcutText(accel):
    parts = accel.split("-")

    return "+".join(p.capitalize() if len(p) > 1 else p for p in parts)


# the name shown for a script file: its file name without the .trelby
def scriptName(path):
    name = os.path.basename(path)
    base, ext = os.path.splitext(name)

    return base if ext.lower() == ".trelby" else name


# when a file was last changed, for the recent files: the time today, else
# the date
def changedText(mtime, now=None):
    now = time.time() if now is None else now

    if time.localtime(mtime)[:3] == time.localtime(now)[:3]:
        return _("Today %s") % time.strftime("%H:%M", time.localtime(mtime))

    return time.strftime("%Y-%m-%d", time.localtime(mtime))


# owner is what the rows act through, the main window (trelbyframe.MyFrame):
# its actions ({name: menus.Action}), runAction(name), openRecent(i) and
# removeRecent(i), and gd (globaldata.GlobalData) for the recent files and
# the theme
class HomeView(wx.Window):
    def __init__(self, parent, owner):
        wx.Window.__init__(self, parent, -1, style=wx.WANTS_CHARS | wx.BORDER_NONE)

        self.owner = owner

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        # the rows, made by refresh
        self.rows = []

        # index of the row under the mouse, and of the one picked with the
        # keyboard, or None
        self.hover = None
        self.picked = None

        # whether the picked row is shown, which it is once the arrow keys
        # have been used, until the mouse is
        self.keyNav = False

        # how far the content is scrolled up, and its height, set by layout
        self.scrollY = 0
        self.contentH = 0

        # the texts layout places besides the rows' own: (text, x, y, font,
        # dim)
        self.texts = []

        # where the card and the logo are, set by layout
        self.card = wx.Rect()
        self.logoPos = wx.Point()
        self.logo = None

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeave)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)
        self.Bind(wx.EVT_MOUSEWHEEL, self.OnWheel)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind(wx.EVT_SET_FOCUS, lambda event: self.Refresh(False))
        self.Bind(wx.EVT_KILL_FOCUS, lambda event: self.Refresh(False))

        self.refresh()

    def px(self, n):
        return self.FromDIP(n)

    # make the rows again, from the Actions and the recent files, which
    # may have changed or been deleted since
    def refresh(self):
        acts = self.owner.actions

        def actionRow(name):
            a = acts[name]

            return Row(
                ACTION,
                a.label + ("..." if a.dots else ""),
                name,
                note=shortcutText(a.accel) if a.accel else "",
            )

        templates = [n for n in acts if n.startswith("NewScript-")]
        imports = [n for n in acts if n.startswith("Import")]

        rows = [
            actionRow("NewScript"),
            Row(MENU, _("New from template") + "...", templates),
            actionRow("OpenScript"),
            Row(MENU, _("Import") + "...", imports),
        ]

        mru = self.owner.gd.mru

        for i in range(mru.getCount()):
            path = mru.get(i)

            try:
                note = changedText(os.path.getmtime(path))
                gone = False
            except OSError:
                note = _("Not found")
                gone = True

            rows.append(
                Row(
                    RECENT,
                    scriptName(path),
                    i,
                    detail=os.path.dirname(os.path.abspath(path)),
                    note=note,
                    dim=gone,
                )
            )

        self.rows = rows
        self.hover = None

        if (self.picked is not None) and (self.picked >= len(rows)):
            self.picked = len(rows) - 1

        self.layout()
        self.Refresh(False)

    def fonts(self):
        base = self.GetFont()

        return {
            "title": base.Scaled(2.0).Bold(),
            "heading": base.Bold(),
            "label": base.Scaled(1.1),
            "base": base,
        }

    # place the card, the texts and the rows for the window's size and the
    # scroll position
    def layout(self):
        px = self.px
        w, h = self.GetClientSize()
        fonts = self.fonts()

        dc = wx.ClientDC(self)

        def lineH(font):
            dc.SetFont(font)

            return dc.GetTextExtent("Ag")[1]

        cardW = max(px(200), min(px(CARD_WIDTH), w - px(MARGIN) * 2))
        cardX = (w - cardW) // 2
        x = cardX + px(PAD)
        innerW = cardW - px(PAD) * 2
        y = px(MARGIN) + px(PAD) - self.scrollY
        top = y - px(PAD)

        self.texts = []

        # the logo, with the name beside it
        titleH = lineH(fonts["title"])
        logoH = px(LOGO_SIZE)
        self.logoPos = wx.Point(x, y)
        self.texts.append(
            (
                "Trelby",
                x + logoH + px(14),
                y + (logoH - titleH) // 2,
                fonts["title"],
                False,
            )
        )
        y += logoH + px(SECTION_GAP)

        def heading(text):
            nonlocal y
            self.texts.append((text, x, y, fonts["heading"], True))
            y += lineH(fonts["heading"]) + px(6)

        heading(_("Start"))

        recentStarted = False

        for row in self.rows:
            if row.kind == RECENT and not recentStarted:
                recentStarted = True
                y += px(SECTION_GAP)
                heading(_("Recent scripts"))

            rowH = px(RECENT_ROW if row.kind == RECENT else ACTION_ROW)

            # the rows' highlights reach a bit into the card's padding
            row.rect = wx.Rect(x - px(10), y, innerW + px(20), rowH)
            y += rowH

        if not recentStarted:
            y += px(SECTION_GAP)
            heading(_("Recent scripts"))
            self.texts.append(
                (
                    _("The scripts you open will be listed here."),
                    x,
                    y + px(4),
                    fonts["base"],
                    True,
                )
            )
            y += lineH(fonts["base"]) + px(8)

        y += px(PAD)
        self.card = wx.Rect(cardX, top, cardW, y - top)
        self.contentH = y + self.scrollY + px(MARGIN)

        # keep the scroll position in range after a resize
        maxScroll = max(0, self.contentH - h)

        if self.scrollY > maxScroll:
            self.scrollY = maxScroll
            self.layout()

    def getLogo(self):
        size = self.px(LOGO_SIZE)

        if (self.logo is None) or (self.logo.GetWidth() != size):
            img = icons.getBitmap("trelby/resources/icon128.png").ConvertToImage()
            self.logo = wx.Bitmap(img.Scale(size, size, wx.IMAGE_QUALITY_HIGH))

        return self.logo

    # the index of the row at pos, or None
    def rowAt(self, pos):
        for i, row in enumerate(self.rows):
            if row.rect.Contains(pos):
                return i

        return None

    def OnSize(self, event):
        self.layout()
        self.Refresh(False)
        event.Skip()

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        self.draw(dc)

    def draw(self, dc):
        cfgGui = self.owner.gd.cfgGui
        px = self.px

        textColor = cfgGui.textColor
        dimColor = cfgGui.textHdrColor
        hiColor = theming.blendColors(
            cfgGui.textBgColor, cfgGui.accentColor, theming.ACCENT_TINT
        )

        dc.SetBackground(wx.Brush(cfgGui.workspaceColor))
        dc.Clear()

        dc.SetPen(wx.Pen(cfgGui.pageBorderColor))
        dc.SetBrush(wx.Brush(cfgGui.textBgColor))
        dc.DrawRoundedRectangle(self.card, px(8))

        dc.DrawBitmap(self.getLogo(), self.logoPos)

        for text, x, y, font, dim in self.texts:
            dc.SetFont(font)
            dc.SetTextForeground(dimColor if dim else textColor)
            dc.DrawText(text, x, y)

        fonts = self.fonts()
        showPicked = self.keyNav and self.HasFocus()

        for i, row in enumerate(self.rows):
            r = row.rect

            if (i == self.hover) or (showPicked and (i == self.picked)):
                dc.SetBrush(wx.Brush(hiColor))

                if showPicked and (i == self.picked):
                    dc.SetPen(wx.Pen(cfgGui.accentColor))
                else:
                    dc.SetPen(wx.TRANSPARENT_PEN)

                dc.DrawRoundedRectangle(r, px(5))

            textX = r.x + px(10)
            right = r.GetRight() - px(10)

            # the note at the right, then the label and the detail in what's
            # left of the width
            noteW = 0

            dc.SetFont(fonts["base"])

            if row.note:
                noteW = dc.GetTextExtent(row.note)[0] + px(16)

            labelFont = fonts["label"] if row.kind == RECENT else fonts["base"]
            dc.SetFont(labelFont)
            labelH = dc.GetTextExtent("Ag")[1]
            room = right - textX - noteW

            if row.detail:
                dc.SetFont(fonts["base"])
                detailH = dc.GetTextExtent("Ag")[1]
                labelY = r.y + (r.height - labelH - detailH) // 2
            else:
                detailH = 0
                labelY = r.y + (r.height - labelH) // 2

            dc.SetFont(labelFont)
            dc.SetTextForeground(dimColor if row.dim else textColor)
            dc.DrawText(
                wx.Control.Ellipsize(row.label, dc, wx.ELLIPSIZE_END, room),
                textX,
                labelY,
            )

            dc.SetFont(fonts["base"])
            dc.SetTextForeground(dimColor)

            if row.detail:
                dc.DrawText(
                    wx.Control.Ellipsize(row.detail, dc, wx.ELLIPSIZE_MIDDLE, room),
                    textX,
                    labelY + labelH,
                )

            if row.note:
                w, h = dc.GetTextExtent(row.note)
                dc.DrawText(row.note, right - w, r.y + (r.height - h) // 2)

    def setHover(self, i):
        if i == self.hover:
            return

        self.hover = i
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND if i is not None else wx.CURSOR_ARROW))

        row = self.rows[i] if i is not None else None

        if row and (row.kind == RECENT):
            self.SetToolTip(self.owner.gd.mru.get(row.value))
        else:
            self.UnsetToolTip()

        self.Refresh(False)

    def OnMotion(self, event):
        self.setHover(self.rowAt(event.GetPosition()))

    def OnLeave(self, event):
        self.setHover(None)

    def OnLeftDown(self, event):
        self.SetFocus()
        self.keyNav = False

        i = self.rowAt(event.GetPosition())

        if i is not None:
            self.picked = i
            self.activate(i)

    def OnRightDown(self, event):
        i = self.rowAt(event.GetPosition())

        if (i is None) or (self.rows[i].kind != RECENT):
            return

        index = self.rows[i].value

        menu = wx.Menu()
        openItem = menu.Append(wx.ID_ANY, _("Open"))
        removeItem = menu.Append(wx.ID_ANY, _("Remove from recent files"))

        self.Bind(wx.EVT_MENU, lambda e: self.owner.openRecent(index), openItem)
        self.Bind(wx.EVT_MENU, lambda e: self.owner.removeRecent(index), removeItem)

        self.PopupMenu(menu)
        menu.Destroy()

    def OnWheel(self, event):
        lines = event.GetWheelRotation() / event.GetWheelDelta()
        self.scrollTo(self.scrollY - int(lines * self.px(ACTION_ROW)))

    def scrollTo(self, y):
        h = self.GetClientSize()[1]
        y = max(0, min(y, self.contentH - h))

        if y != self.scrollY:
            self.scrollY = y
            self.layout()
            self.setHover(self.rowAt(self.ScreenToClient(wx.GetMousePosition())))
            self.Refresh(False)

    # scroll so that row i is in view
    def showRow(self, i):
        r = self.rows[i].rect
        h = self.GetClientSize()[1]

        if r.y < 0:
            self.scrollTo(self.scrollY + r.y - self.px(MARGIN))
        elif r.GetBottom() > h:
            self.scrollTo(self.scrollY + r.GetBottom() - h + self.px(MARGIN))

    def OnKeyDown(self, event):
        key = event.GetKeyCode()
        n = len(self.rows)

        if key in (wx.WXK_UP, wx.WXK_DOWN, wx.WXK_HOME, wx.WXK_END):
            if not self.keyNav or (self.picked is None):
                i = 0
            elif key == wx.WXK_UP:
                i = max(0, self.picked - 1)
            elif key == wx.WXK_DOWN:
                i = min(n - 1, self.picked + 1)
            elif key == wx.WXK_HOME:
                i = 0
            else:
                i = n - 1

            self.keyNav = True
            self.picked = i
            self.showRow(i)
            self.Refresh(False)
        elif (
            key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER, wx.WXK_SPACE)
            and self.keyNav
            and (self.picked is not None)
        ):
            self.activate(self.picked)
        elif (
            key == wx.WXK_DELETE
            and self.keyNav
            and (self.picked is not None)
            and (self.rows[self.picked].kind == RECENT)
        ):
            self.owner.removeRecent(self.rows[self.picked].value)
        else:
            event.Skip()

    # do what row i does
    def activate(self, i):
        row = self.rows[i]

        if row.kind == ACTION:
            self.owner.runAction(row.value)
        elif row.kind == MENU:
            self.popupActions(row)
        else:
            self.owner.openRecent(row.value)

    # pop up a menu of the row's Actions below it. their menu items have
    # the Actions' ids, which the main window has bound.
    def popupActions(self, row):
        menu = wx.Menu()

        for name in row.value:
            a = self.owner.actions[name]
            menu.Append(a.id, a.label + ("..." if a.dots else ""))

        r = row.rect
        self.PopupMenu(menu, wx.Point(r.x + self.px(10), r.GetBottom()))
        menu.Destroy()
