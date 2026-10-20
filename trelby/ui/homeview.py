# the Home screen, shown in place of the tabs while no script is open (see
# MyFrame.setHomeShown). it's drawn by hand, in the theme's colors, as two
# cards, side by side in a wide window and one above the other otherwise:
#
# - the ways to start a script, and the scripts opened recently
# - what's been written, in all scripts (see writinglog.py): today against
#   the daily goal, the last two weeks as a bar chart, and which scripts
#   were written in lately
#
# a click on a row (or Enter on the one picked with the arrow keys) runs
# its Action, pops up a menu of Actions, or opens the script.

import datetime
import os
import time

import wx

import trelby.ui.icons as icons
import trelby.ui.theming as theming
import trelby.writinglog as writinglog
from trelby.writinglog import scriptName

# sizes, in DIPs: a card's width at most, the space around and between the
# cards and inside them, the rows' heights, the gap before a section's
# heading, and the bar chart's height
CARD_WIDTH = 560
MARGIN = 32
CARD_GAP = 24
PAD = 28
ACTION_ROW = 34
RECENT_ROW = 48
SECTION_GAP = 24
LOGO_SIZE = 48
CHART_HEIGHT = 72

# how many days the chart shows, and how many scripts' days the recent
# activity lists at most
CHART_DAYS = 14
ACTIVITY_ROWS = 6

# the kinds of row: one that runs an Action, one that pops up a menu of
# Actions, a recent script, and a script written in lately
ACTION, MENU, RECENT, ACTIVITY = list(range(4))

# the kinds of shape drawn besides the texts and the rows (see
# HomeView.shapes): the goal's progress bar, empty and filled, the chart's
# bars, today's, the mark for a day with nothing written, and the goal's
# line across the chart
TRACK, FILL, BAR, TODAY_BAR, NO_BAR, GOAL_LINE = list(range(6))


# a row: its kind, its label, the dimmer text under the label (a script's
# folder) and at its right (a shortcut, or when the script was changed, or
# how much was written), and what it does: an Action's name, a list of
# them, the index of the recent file, or the path of the script written
# in (None for one never saved, which can't be opened). rect is where it
# is, set by HomeView.layout.
class Row:
    def __init__(self, kind, label, value, detail="", note="", dim=False):
        self.kind = kind
        self.label = label
        self.value = value
        self.detail = detail
        self.note = note

        # whether the label is shown dimmed, for a script that's gone
        self.dim = dim

        self.rect = wx.Rect()

    # whether clicking it does something
    def isEnabled(self):
        return not ((self.kind == ACTIVITY) and (self.value is None))


# "CTRL-N" -> "Ctrl+N"
def shortcutText(accel):
    parts = accel.split("-")

    return "+".join(p.capitalize() if len(p) > 1 else p for p in parts)


# when a file was last changed, for the recent files: the time today, else
# the date
def changedText(mtime, now=None):
    now = time.time() if now is None else now

    if time.localtime(mtime)[:3] == time.localtime(now)[:3]:
        return _("Today %s") % time.strftime("%H:%M", time.localtime(mtime))

    return time.strftime("%Y-%m-%d", time.localtime(mtime))


# "Today", "Yesterday", or the date, for day 'day' seen on day 'today'
def dayText(day, today):
    if day == today:
        return _("Today")

    if day == today - datetime.timedelta(days=1):
        return _("Yesterday")

    return day.strftime("%a %d %b")


# time spent writing, in seconds: "35 min", "1 h 5 min", or "<1 min"
def durationText(seconds):
    minutes = int(seconds // 60)

    if minutes < 1:
        return _("<1 min")

    if minutes < 60:
        return _("%d min") % minutes

    return _("%d h %d min") % divmod(minutes, 60)


def wordsText(words):
    if words == 1:
        return _("1 word")

    # a real minus sign, for scripts that got shorter
    return (_("%s words") % "{:,}".format(words)).replace("-", "−")


def pagesText(pages):
    s = ("%.1f" % pages).rstrip("0").rstrip(".")

    if s == "1":
        return _("1 page")

    return (_("%s pages") % s).replace("-", "−")


# owner is what the rows act through, the main window (trelbyframe.MyFrame):
# its actions ({name: menus.Action}), runAction(name), openRecent(i),
# removeRecent(i) and openPath(path), and gd (globaldata.GlobalData) for the
# recent files, the writing log, the daily goal and the theme. clock gives
# the time (seconds since the epoch).
class HomeView(wx.Window):
    def __init__(self, parent, owner, clock=time.time):
        wx.Window.__init__(self, parent, -1, style=wx.WANTS_CHARS | wx.BORDER_NONE)

        self.owner = owner
        self.clock = clock

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        # the rows, made by refresh: the start card's, then the writing
        # card's
        self.rows = []

        # what the writing card shows, made by refresh: today's
        # writinglog.Total, the chart's days' Totals, oldest first, the
        # streak, in days, and today's date
        self.todayTotal = None
        self.chartDays = []
        self.streak = 0
        self.today = None

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

        # what layout places besides the rows: the texts, as (text, x, y,
        # font name (see fonts), dim), the shapes, as (kind, wx.Rect), and
        # the cards, as wx.Rects
        self.texts = []
        self.shapes = []
        self.cards = []

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

    # whether amounts are in pages, as the daily goal is
    def inPages(self):
        return self.owner.gd.cfgGl.dailyGoalPages

    def amountText(self, total):
        if self.inPages():
            return pagesText(total.pages)

        return wordsText(total.words)

    # make the rows again, from the Actions, the recent files, which may
    # have changed or been deleted since, and the writing log
    def refresh(self):
        gd = self.owner.gd
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

        mru = gd.mru

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

        log = gd.writingLog
        self.today = writinglog.localDay(self.clock())
        self.todayTotal = log.dayTotal(self.today)
        self.chartDays = log.days(self.today, CHART_DAYS)
        self.streak = log.streak(self.today)

        # what was written in each script lately, leaving out the days a
        # script was only touched
        activity = [
            t for t in log.recentActivity(ACTIVITY_ROWS * 3)
            if (t.words != 0) or (t.active >= 60)
        ][:ACTIVITY_ROWS]

        for t in activity:
            detail = dayText(t.day, self.today)

            if t.path:
                detail += "  ·  " + os.path.dirname(t.path)

            rows.append(
                Row(
                    ACTIVITY,
                    t.title,
                    t.path,
                    detail=detail,
                    note="%s  ·  %s"
                    % (self.amountText(t), durationText(t.active)),
                    dim=bool(t.path) and not os.path.exists(t.path),
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
            "big": base.Scaled(1.8).Bold(),
            "heading": base.Bold(),
            "label": base.Scaled(1.1),
            "base": base,
        }

    # place the cards, their texts, shapes and rows for the window's size
    # and the scroll position
    def layout(self):
        px = self.px
        w, h = self.GetClientSize()

        self.dc = wx.ClientDC(self)
        self.fontSet = self.fonts()
        self.texts = []
        self.shapes = []
        self.cards = []

        cardW = max(px(200), min(px(CARD_WIDTH), w - px(MARGIN) * 2))
        wide = w >= px(CARD_WIDTH) * 2 + px(CARD_GAP) + px(MARGIN) * 2
        top = px(MARGIN) - self.scrollY

        start = [r for r in self.rows if r.kind != ACTIVITY]
        activity = [r for r in self.rows if r.kind == ACTIVITY]

        if wide:
            x = (w - cardW * 2 - px(CARD_GAP)) // 2
            bottom1 = self.layoutStart(x, top, cardW, start)
            bottom2 = self.layoutWriting(x + cardW + px(CARD_GAP), top, cardW, activity)
            bottom = max(bottom1, bottom2)
        else:
            x = (w - cardW) // 2
            bottom = self.layoutStart(x, top, cardW, start)
            bottom = self.layoutWriting(x, bottom + px(CARD_GAP), cardW, activity)

        del self.dc

        self.contentH = bottom + self.scrollY + px(MARGIN)

        # keep the scroll position in range after a resize
        maxScroll = max(0, self.contentH - h)

        if self.scrollY > maxScroll:
            self.scrollY = maxScroll
            self.layout()

    def lineH(self, font):
        self.dc.SetFont(self.fontSet[font])

        return self.dc.GetTextExtent("Ag")[1]

    def textW(self, text, font):
        self.dc.SetFont(self.fontSet[font])

        return self.dc.GetTextExtent(text)[0]

    # put the rows one after the other from y, as wide as the card's inside
    # (x, width). returns where they end.
    def placeRows(self, rows, x, y, width):
        px = self.px

        for row in rows:
            rowH = px(ACTION_ROW if row.kind in (ACTION, MENU) else RECENT_ROW)

            # the rows' highlights reach a bit into the card's padding
            row.rect = wx.Rect(x - px(10), y, width + px(20), rowH)
            y += rowH

        return y

    def heading(self, text, x, y):
        self.texts.append((text, x, y, "heading", True))

        return y + self.lineH("heading") + self.px(6)

    # a line of dim text. returns where it ends.
    def note(self, text, x, y):
        self.texts.append((text, x, y, "base", True))

        return y + self.lineH("base") + self.px(8)

    # the start card, at (cardX, top), cardW wide, with the rows. returns
    # where it ends.
    def layoutStart(self, cardX, top, cardW, rows):
        px = self.px
        x = cardX + px(PAD)
        innerW = cardW - px(PAD) * 2
        y = top + px(PAD)

        # the logo, with the name beside it
        logoH = px(LOGO_SIZE)
        self.logoPos = wx.Point(x, y)
        self.texts.append(
            (
                "Trelby",
                x + logoH + px(14),
                y + (logoH - self.lineH("title")) // 2,
                "title",
                False,
            )
        )
        y += logoH + px(SECTION_GAP)

        y = self.heading(_("Start"), x, y)
        actions = [r for r in rows if r.kind != RECENT]
        recent = [r for r in rows if r.kind == RECENT]
        y = self.placeRows(actions, x, y, innerW)

        y += px(SECTION_GAP)
        y = self.heading(_("Recent scripts"), x, y)

        if recent:
            y = self.placeRows(recent, x, y, innerW)
        else:
            y = self.note(
                _("The scripts you open will be listed here."), x, y + px(4)
            )

        y += px(PAD)
        self.cards.append(wx.Rect(cardX, top, cardW, y - top))

        return y

    # the writing card, at (cardX, top), cardW wide, with the recent
    # activity's rows. returns where it ends.
    def layoutWriting(self, cardX, top, cardW, rows):
        px = self.px
        cfgGl = self.owner.gd.cfgGl
        x = cardX + px(PAD)
        innerW = cardW - px(PAD) * 2
        right = x + innerW
        y = top + px(PAD)
        today = self.todayTotal
        goal = cfgGl.dailyGoal

        y = self.heading(_("Today"), x, y)

        # what's been written today, big, and how long it took and the
        # streak beside it
        bigH = self.lineH("big")
        self.texts.append((self.amountText(today), x, y, "big", False))

        parts = []

        if today.active:
            parts.append(durationText(today.active))

        if self.streak > 1:
            parts.append(_("%d-day streak") % self.streak)

        if parts:
            side = "  ·  ".join(parts)
            sideW = self.textW(side, "base")
            self.texts.append(
                (side, right - sideW, y + bigH - self.lineH("base"), "base", True)
            )

        y += bigH + px(10)

        if goal:
            done = today.shownPages() if self.inPages() else today.shownWords()
            part = min(1.0, done / goal)
            barH = px(8)
            track = wx.Rect(x, y, innerW, barH)
            self.shapes.append((TRACK, track))

            if part > 0:
                self.shapes.append(
                    (FILL, wx.Rect(x, y, max(barH, int(innerW * part)), barH))
                )

            y += barH + px(6)

            if done >= goal:
                text = _("Daily goal reached")
            elif self.inPages():
                text = _("%d%% of %s") % (100 * part, pagesText(goal))
            else:
                text = _("%d%% of %s") % (100 * part, wordsText(goal))

            y = self.note(text, x, y)

        y += px(SECTION_GAP)

        # the last two weeks, a bar per day, today's last
        y = self.heading(_("Last %d days") % CHART_DAYS, x, y)
        total = writinglog.Total(self.today)

        for t in self.chartDays:
            total.words += t.shownWords()
            total.pages += t.shownPages()

        totalText = self.amountText(total)
        self.texts.append(
            (
                totalText,
                right - self.textW(totalText, "base"),
                y - self.lineH("heading") - px(6),
                "base",
                True,
            )
        )

        def amount(t):
            return t.shownPages() if self.inPages() else t.shownWords()

        scale = max([amount(t) for t in self.chartDays] + [goal, 1])
        chartH = px(CHART_HEIGHT)
        slot = innerW / CHART_DAYS
        barW = max(px(4), int(slot * 0.6))
        baseY = y + chartH

        for i, t in enumerate(self.chartDays):
            bx = int(x + slot * i + (slot - barW) / 2)
            v = amount(t)

            if v <= 0:
                self.shapes.append((NO_BAR, wx.Rect(bx, baseY - px(2), barW, px(2))))
            else:
                bh = max(px(3), int(chartH * v / scale))
                kind = TODAY_BAR if t.day == self.today else BAR
                self.shapes.append((kind, wx.Rect(bx, baseY - bh, barW, bh)))

        if goal:
            gy = baseY - int(chartH * goal / scale)
            self.shapes.append((GOAL_LINE, wx.Rect(x, gy, innerW, 1)))

        y = baseY + px(6)

        # the first day's date under its bar, and "Today" under the last
        first = self.chartDays[0].day.strftime("%d %b")
        self.texts.append((first, x, y, "base", True))
        last = _("Today")
        self.texts.append((last, right - self.textW(last, "base"), y, "base", True))
        y += self.lineH("base") + px(SECTION_GAP)

        y = self.heading(_("Recent writing"), x, y)

        if rows:
            y = self.placeRows(rows, x, y, innerW)
        else:
            y = self.note(
                _("What you write in any script is counted here."), x, y + px(4)
            )

        y += px(PAD)
        self.cards.append(wx.Rect(cardX, top, cardW, y - top))

        return y

    def getLogo(self):
        size = self.px(LOGO_SIZE)

        if (self.logo is None) or (self.logo.GetWidth() != size):
            img = icons.getBitmap("trelby/resources/icon128.png").ConvertToImage()
            self.logo = wx.Bitmap(img.Scale(size, size, wx.IMAGE_QUALITY_HIGH))

        return self.logo

    # the index of the row at pos that can be clicked, or None
    def rowAt(self, pos):
        for i, row in enumerate(self.rows):
            if row.rect.Contains(pos) and row.isEnabled():
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
        fonts = self.fonts()

        textColor = cfgGui.textColor
        dimColor = cfgGui.textHdrColor
        accent = cfgGui.accentColor
        bg = cfgGui.textBgColor
        hiColor = theming.blendColors(bg, accent, theming.ACCENT_TINT)

        shapeColors = {
            TRACK: theming.blendColors(bg, dimColor, 0.25),
            FILL: accent,
            BAR: theming.blendColors(bg, accent, 0.45),
            TODAY_BAR: accent,
            NO_BAR: theming.blendColors(bg, dimColor, 0.35),
            GOAL_LINE: dimColor,
        }

        dc.SetBackground(wx.Brush(cfgGui.workspaceColor))
        dc.Clear()

        dc.SetPen(wx.Pen(cfgGui.pageBorderColor))
        dc.SetBrush(wx.Brush(bg))

        for card in self.cards:
            dc.DrawRoundedRectangle(card, px(8))

        dc.DrawBitmap(self.getLogo(), self.logoPos)

        for kind, r in self.shapes:
            color = shapeColors[kind]

            if kind == GOAL_LINE:
                dc.SetPen(wx.Pen(color, 1, wx.PENSTYLE_SHORT_DASH))
                dc.DrawLine(r.x, r.y, r.GetRight(), r.y)
            else:
                dc.SetPen(wx.TRANSPARENT_PEN)
                dc.SetBrush(wx.Brush(color))
                dc.DrawRoundedRectangle(r, min(px(3), r.height // 2, r.width // 2))

        for text, x, y, font, dim in self.texts:
            dc.SetFont(fonts[font])
            dc.SetTextForeground(dimColor if dim else textColor)
            dc.DrawText(text, x, y)

        showPicked = self.keyNav and self.HasFocus()

        for i, row in enumerate(self.rows):
            r = row.rect

            if (i == self.hover) or (showPicked and (i == self.picked)):
                dc.SetBrush(wx.Brush(hiColor))

                if showPicked and (i == self.picked):
                    dc.SetPen(wx.Pen(accent))
                else:
                    dc.SetPen(wx.TRANSPARENT_PEN)

                dc.DrawRoundedRectangle(r, px(5))

            self.drawRow(dc, row, fonts, textColor, dimColor)

    def drawRow(self, dc, row, fonts, textColor, dimColor):
        px = self.px
        r = row.rect
        textX = r.x + px(10)
        right = r.GetRight() - px(10)

        # the note at the right, then the label and the detail in what's
        # left of the width
        noteW = 0

        dc.SetFont(fonts["base"])

        if row.note:
            noteW = dc.GetTextExtent(row.note)[0] + px(16)

        labelFont = fonts["base"] if row.kind in (ACTION, MENU) else fonts["label"]
        dc.SetFont(labelFont)
        labelH = dc.GetTextExtent("Ag")[1]
        room = right - textX - noteW

        if row.detail:
            dc.SetFont(fonts["base"])
            detailH = dc.GetTextExtent("Ag")[1]
            labelY = r.y + (r.height - labelH - detailH) // 2
        else:
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
        elif row and (row.kind == ACTIVITY):
            self.SetToolTip(row.value)
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

    # the index of the next row from i that can be clicked, going by step
    # (1 or -1), or i if there's none
    def nextEnabled(self, i, step):
        j = i + step

        while 0 <= j < len(self.rows):
            if self.rows[j].isEnabled():
                return j

            j += step

        return i

    def OnKeyDown(self, event):
        key = event.GetKeyCode()
        n = len(self.rows)

        if key in (wx.WXK_UP, wx.WXK_DOWN, wx.WXK_HOME, wx.WXK_END):
            if key == wx.WXK_HOME:
                i = 0
            elif key == wx.WXK_END:
                i = self.nextEnabled(n, -1)
            elif not self.keyNav or (self.picked is None):
                i = 0
            elif key == wx.WXK_UP:
                i = self.nextEnabled(self.picked, -1)
            else:
                i = self.nextEnabled(self.picked, 1)

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
        elif row.kind == RECENT:
            self.owner.openRecent(row.value)
        elif row.value:
            self.owner.openPath(row.value)

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
