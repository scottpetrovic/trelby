# the Home screen, shown in place of the tabs while no script is open (see
# MyFrame.setHomeShown). it's drawn by hand, in the theme's colors, straight
# on the workspace color: the logo, and under it two sections, side by side
# with a line between them in a wide window and one above the other
# otherwise:
#
# - the ways to start a script, and the scripts opened recently
# - what's been written, in all scripts (see writinglog.py): the last two
#   weeks as a bar chart, today against the daily goal, the sprints, and
#   which scripts were written in lately
#
# a click on a row (or Enter on the one picked with the arrow keys) runs
# its Action, pops up a menu of Actions, or opens the script.

import os
import time

import wx

import trelby.keys as keys
import trelby.ui.icons as icons
import trelby.ui.theming as theming
import trelby.writinglog as writinglog
from trelby.writinglog import scriptName

# sizes, in DIPs: a section's width at most, the space around the card and
# inside the sections, the rows' heights, the gap before a heading, the
# logo above the card and the gap under it, and the bar chart's height
SECTION_WIDTH = 560
MARGIN = 32
PAD = 40
ACTION_ROW = 34
RECENT_ROW = 48
SECTION_GAP = 24
LOGO_SIZE = 128
LOGO_GAP = 20
CHART_HEIGHT = 72

# how many days the chart shows
CHART_DAYS = 14

# the kinds of row: one that runs an Action, one that pops up a menu of
# Actions, and a recent script
ACTION, MENU, RECENT = list(range(3))

# the kinds of shape drawn besides the texts and the rows (see
# HomeView.shapes): the goal's progress bar, empty and filled, the chart's
# bars, today's, the mark for a day with nothing written, and the goal's
# line across the chart, and the line between the sections
TRACK, FILL, BAR, TODAY_BAR, NO_BAR, GOAL_LINE, DIVIDER = list(range(7))


# a row: its kind, its label, the dimmer text under the label (a script's
# folder) and at its right (a shortcut, or when the script was changed),
# and what it does: an Action's name, a list of them, or the index of the
# recent file. section is the section it's in: 0 for the start section, 1
# for the writing section. rect is where it is, set by HomeView.layout.
class Row:
    def __init__(self, kind, label, value, detail="", note="", dim=False, section=0):
        self.kind = kind
        self.section = section
        self.label = label
        self.value = value
        self.detail = detail
        self.note = note

        # whether the label is shown dimmed, for a script that's gone
        self.dim = dim

        self.rect = wx.Rect()


# the first key of the keyboard command 'name' in the global config cfgGl,
# as text ("F7"), or "" if it has none
def commandKeyText(cfgGl, name):
    for cmd in cfgGl.commands:
        if (cmd.name == name) and cmd.keys and cmd.keys[0]:
            return keys.Key.fromInt(cmd.keys[0]).toStr()

    return ""


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
# and removeRecent(i), and gd (globaldata.GlobalData) for the
# recent files, the writing log, the daily goal and the theme. clock gives
# the time (seconds since the epoch).
class HomeView(wx.Window):
    def __init__(self, parent, owner, clock=time.time):
        wx.Window.__init__(self, parent, -1, style=wx.WANTS_CHARS | wx.BORDER_NONE)

        self.owner = owner
        self.clock = clock

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        # the rows, made by refresh: the start section's, then the
        # writing section's
        self.rows = []

        # what the writing section shows, made by refresh: today's
        # writinglog.Total, the chart's days' Totals, oldest first, the
        # streak, in days, and today's date
        self.todayTotal = None
        self.chartDays = []
        self.streak = 0
        self.today = None

        # this week's writinglog.Total, today's sprints' SprintRecords, and
        # the sprint going on's state (see SprintTimer.statusText), or None
        self.weekTotal = None
        self.sprintsToday = []
        self.sprintText = None

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
        # the area the sections take up (card, not drawn) and the sections,
        # as wx.Rects
        self.texts = []
        self.shapes = []
        self.card = wx.Rect()
        self.sections = []

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
        self.weekTotal = log.weekTotal(self.today)
        self.sprintsToday = log.sprintsOn(self.today)

        timer = getattr(self.owner, "sprint", None)
        sprinting = bool(timer) and timer.isActive()
        self.sprintText = timer.statusText() if sprinting else None

        # starting and stopping a sprint, and the goals
        cfgGl = gd.cfgGl

        if sprinting:
            rows.append(
                Row(
                    ACTION,
                    _("Stop the sprint"),
                    "ToggleSprint",
                    note=commandKeyText(cfgGl, "ToggleSprint"),
                    section=1,
                )
            )
            rows.append(
                Row(
                    ACTION,
                    _("Resume the sprint") if timer.isPaused() else _("Pause the sprint"),
                    "PauseSprint",
                    note=commandKeyText(cfgGl, "PauseSprint"),
                    section=1,
                )
            )
        else:
            rows.append(
                Row(
                    ACTION,
                    _("Start a %d-minute sprint") % cfgGl.sprintMinutes,
                    "ToggleSprint",
                    note=commandKeyText(cfgGl, "ToggleSprint"),
                    section=1,
                )
            )

        rows.append(Row(ACTION, _("Manage Writing Goals") + "...", "WritingGoals", section=1))

        # refreshed every second during a sprint, the row under the mouse
        # stays highlighted
        if (self.hover is not None) and (self.hover >= len(rows)):
            self.hover = None

        self.rows = rows

        if (self.picked is not None) and (self.picked >= len(rows)):
            self.picked = len(rows) - 1

        self.layout()
        self.Refresh(False)

    def fonts(self):
        base = self.GetFont()

        return {
            "big": base.Scaled(1.8).Bold(),
            "heading": base.Scaled(1.25).Bold(),
            "label": base.Scaled(1.1),
            "base": base,
        }

    # place the card, its sections' texts, shapes and rows for the window's
    # size and the scroll position
    def layout(self):
        px = self.px
        w, h = self.GetClientSize()

        self.dc = wx.ClientDC(self)
        self.fontSet = self.fonts()
        self.texts = []
        self.shapes = []
        self.sections = []

        secW = max(px(200), min(px(SECTION_WIDTH), w - px(MARGIN) * 2))
        wide = w >= px(SECTION_WIDTH) * 2 + px(MARGIN) * 2
        top = px(MARGIN) - self.scrollY

        # the logo, centered above the card
        self.logoPos = wx.Point((w - px(LOGO_SIZE)) // 2, top)
        top += px(LOGO_SIZE) + px(LOGO_GAP)

        start = [r for r in self.rows if r.section == 0]
        writing = [r for r in self.rows if r.section == 1]

        # the line between the sections stops short of the card's edges
        if wide:
            x = (w - secW * 2) // 2
            bottom1 = self.layoutStart(x, top, secW, start)
            bottom2 = self.layoutWriting(x + secW, top, secW, writing)
            bottom = max(bottom1, bottom2)
            self.card = wx.Rect(x, top, secW * 2, bottom - top)
            divider = wx.Rect(x + secW, top + px(PAD), 1, bottom - top - px(PAD) * 2)
        else:
            x = (w - secW) // 2
            middle = self.layoutStart(x, top, secW, start)
            bottom = self.layoutWriting(x, middle, secW, writing)
            self.card = wx.Rect(x, top, secW, bottom - top)
            divider = wx.Rect(x + px(PAD), middle, secW - px(PAD) * 2, 1)

        self.shapes.append((DIVIDER, divider))

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

    # put the rows one after the other from y, as wide as the section's inside
    # (x, width). returns where they end.
    def placeRows(self, rows, x, y, width):
        px = self.px

        for row in rows:
            rowH = px(ACTION_ROW if row.kind in (ACTION, MENU) else RECENT_ROW)

            # the rows' highlights reach a bit into the section's padding
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

    # the start section, at (secX, top), secW wide, with the rows. returns
    # where it ends.
    def layoutStart(self, secX, top, secW, rows):
        px = self.px
        x = secX + px(PAD)
        innerW = secW - px(PAD) * 2
        y = top + px(PAD)
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
        self.sections.append(wx.Rect(secX, top, secW, y - top))

        return y

    # a progress bar from x to x + width at y, for 'done' of 'goal', with a
    # line of text under it: 'reached' once it's reached, else what
    # 'text(percent)' returns. returns where it ends.
    def progress(self, x, y, width, done, goal, reached, text):
        px = self.px
        part = min(1.0, max(0.0, done) / goal)
        barH = px(8)
        self.shapes.append((TRACK, wx.Rect(x, y, width, barH)))

        if part > 0:
            self.shapes.append((FILL, wx.Rect(x, y, max(barH, int(width * part)), barH)))

        y += barH + px(6)

        return self.note(reached if done >= goal else text(int(100 * part)), x, y)

    # the writing section, at (secX, top), secW wide, with its rows: the
    # sprint's and the goals'. the chart comes first, then the goals'
    # progress and the sprint. returns where it ends.
    def layoutWriting(self, secX, top, secW, rows):
        px = self.px
        cfgGl = self.owner.gd.cfgGl
        x = secX + px(PAD)
        innerW = secW - px(PAD) * 2
        right = x + innerW
        y = top + px(PAD)
        today = self.todayTotal
        goal = cfgGl.dailyGoal

        def amount(t):
            return t.shownPages() if self.inPages() else t.shownWords()

        def goalText(n):
            return pagesText(n) if self.inPages() else wordsText(n)

        # the last two weeks, a bar per day, today's last, with how much
        # was written in them, how long it took and the streak at the right
        # of the heading, lined up with its bottom
        y = self.heading(_("Activity Tracker"), x, y)
        total = writinglog.Total(self.today)

        for t in self.chartDays:
            total.words += t.shownWords()
            total.pages += t.shownPages()
            total.active += t.active

        parts = [self.amountText(total)]

        if total.active:
            parts.append(durationText(total.active))

        if self.streak > 1:
            parts.append(_("%d-day streak") % self.streak)

        side = "  ·  ".join(parts)
        self.texts.append(
            (
                side,
                right - self.textW(side, "base"),
                y - px(6) - self.lineH("base"),
                "base",
                True,
            )
        )
        y += px(12)

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

        # today against the daily goal, and this week against the weekly
        if goal:
            y = self.progress(
                x,
                y,
                innerW,
                amount(today),
                goal,
                _("Daily goal reached"),
                lambda pc: _("Daily goal: %d%% of %s") % (pc, goalText(goal)),
            )

        weekly = cfgGl.weeklyGoal

        if weekly:
            week = self.weekTotal
            y += px(10)
            y = self.progress(
                x,
                y,
                innerW,
                amount(week),
                weekly,
                _("Weekly goal reached: %s this week") % self.amountText(week),
                lambda pc: _("%s of %s this week")
                % (self.amountText(week), goalText(weekly)),
            )

        y += px(SECTION_GAP)

        # the sprint going on, today's sprints, and the rows to start or
        # stop one and set the goals

        if self.sprintText:
            self.texts.append((self.sprintText, x, y, "label", False))
            y += self.lineH("label") + px(8)

        if self.sprintsToday:
            n = len(self.sprintsToday)
            words = sum(sp.words for sp in self.sprintsToday)

            if n == 1:
                text = _("1 sprint today, %s") % wordsText(words)
            else:
                text = _("%d sprints today, %s") % (n, wordsText(words))

            y = self.note(text, x, y)

        y = self.placeRows(rows, x, y, innerW)

        y += px(PAD)
        self.sections.append(wx.Rect(secX, top, secW, y - top))

        return y

    def getLogo(self):
        size = self.px(LOGO_SIZE)

        # home-silhouette.png is 256 pixels, scaled down to the logo's size
        if (self.logo is None) or (self.logo.GetWidth() != size):
            img = icons.getBitmap("trelby/resources/home-silhouette.png").ConvertToImage()

            if img.GetWidth() != size:
                img = img.Scale(size, size, wx.IMAGE_QUALITY_HIGH)

            self.logo = wx.Bitmap(img)

        return self.logo

    # the index of the row at pos that can be clicked, or None
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
        fonts = self.fonts()

        textColor = cfgGui.textColor
        dimColor = cfgGui.textHdrColor
        accent = cfgGui.accentColor
        bg = cfgGui.workspaceColor
        hiColor = theming.blendColors(bg, accent, theming.ACCENT_TINT)

        shapeColors = {
            TRACK: theming.blendColors(bg, dimColor, 0.25),
            FILL: accent,
            BAR: theming.blendColors(bg, accent, 0.45),
            TODAY_BAR: accent,
            NO_BAR: theming.blendColors(bg, dimColor, 0.35),
            GOAL_LINE: dimColor,
            DIVIDER: cfgGui.pageBorderColor,
        }

        dc.SetBackground(wx.Brush(bg))
        dc.Clear()

        dc.DrawBitmap(self.getLogo(), self.logoPos)

        for kind, r in self.shapes:
            color = shapeColors[kind]

            if kind == GOAL_LINE:
                dc.SetPen(wx.Pen(color, 1, wx.PENSTYLE_SHORT_DASH))
                dc.DrawLine(r.x, r.y, r.GetRight(), r.y)
            elif kind == DIVIDER:
                dc.SetPen(wx.TRANSPARENT_PEN)
                dc.SetBrush(wx.Brush(color))
                dc.DrawRectangle(r)
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
            if key == wx.WXK_HOME:
                i = 0
            elif key == wx.WXK_END:
                i = n - 1
            elif not self.keyNav or (self.picked is None):
                i = 0
            elif key == wx.WXK_UP:
                i = max(0, self.picked - 1)
            else:
                i = min(n - 1, self.picked + 1)

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
