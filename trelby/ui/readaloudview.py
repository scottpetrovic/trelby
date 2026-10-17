import re

import wx

import trelby.screenplay.tableread as tableread
import trelby.speech as speech
import trelby.ui.gutil as gutil
import trelby.ui.icons as icons
import trelby.ui.theming as theming
from trelby.screenplay.tableread import NARRATOR, VoiceChoice
from trelby.ui.scrollbar import ScrollBar
from trelby.ui.theming import blendColors

# the side panel's Read aloud tab: buttons to play, pause and stop the table
# read (frame.reader, a tablereader.TableReader) and to go from element to
# element, the cast as a grid (the narrator and each character with their
# voice and speed), and below it the selected speaker's voice and speed,
# which can be changed, and a button to hear them. once one has been
# changed, everyone's voice is kept in the script (sp.readAloud), so that
# changing one doesn't change the others; until then, and for characters
# added after, they're the ones tableread.assignVoices picks, shown as
# they'd be read now. the reader tells the frame whenever what it's doing
# changes, and the frame calls updateState.

# the speeds offered, as factors of the engine's normal rate
SPEEDS = sorted(tableread.RATE_FACTORS)


# a voice's name made shorter for a narrow list: Windows' "Microsoft David
# Desktop - English (United States)" becomes "David"
def shortVoiceName(name):
    s = name.split(" - ")[0]
    s = re.sub(r"^Microsoft\s+", "", s)
    s = re.sub(r"\s+Desktop$", "", s)

    return s.strip() or name


# the names to show for voices (speech.Voices): short ones, except where
# two would be the same
def voiceLabels(voices):
    short = [shortVoiceName(v.name or str(v.id)) for v in voices]

    return [
        s if short.count(s) == 1 else (v.name or str(v.id))
        for s, v in zip(short, voices)
    ]


# the index in SPEEDS of the speed nearest to rate
def speedIndex(rate, baseRate):
    return min(
        range(len(SPEEDS)), key=lambda i: abs(baseRate * SPEEDS[i] - rate)
    )


# select item idx of wx.Choice w, if it isn't already: selecting draws the
# native field over the themed one (see theming), so it's drawn again
def setSelection(w, idx):
    if w.GetSelection() != idx:
        w.SetSelection(idx)
        w.Refresh()


# the cast as a grid: a row per speaker with their name, voice and speed.
# the selected row is the one the panel's lists below it change, and the
# speaker being read is shown in the accent color, in bold.
class CastList(wx.VListBox):
    def __init__(self, parent):
        wx.VListBox.__init__(self, parent, -1, style=wx.BORDER_NONE)

        # (name, voice, speed) shown on each row
        self.entries = []

        # index of the row of the speaker being read, or None
        self.currentIdx = None

        self.normalFont = self.GetFont()
        self.boldFont = self.normalFont.Bold()

        # color of the selection and the speaker being read. the panel's
        # applyTheme sets the theme's accent color.
        self.highlight = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)

        self.pad = self.FromDIP(wx.Size(6, 5))
        self.gap = self.FromDIP(8)
        self.lineHeight = max(
            self.GetFullTextExtent("Ag", font)[1]
            for font in (self.normalFont, self.boldFont)
        )
        self.rowHeight = self.pad.y * 2 + self.lineHeight

        # the speed column is as wide as its widest label
        self.speedWidth = max(
            self.GetFullTextExtent(s, self.boldFont)[0]
            for s in [_("Speed")] + speedLabels()
        )

    def setEntries(self, entries):
        if entries != self.entries:
            self.entries = entries
            self.SetItemCount(len(entries))
            self.Refresh()

    def setCurrent(self, idx):
        old = self.currentIdx
        self.currentIdx = idx

        for i in (old, idx):
            if (i is not None) and (i < self.GetItemCount()):
                self.RefreshRow(i)

        if (idx is not None) and not self.IsRowVisible(idx):
            self.ScrollToRow(idx)

    # the x positions of the name, voice and speed columns and the right
    # edge of the last, in a row width wide
    def columns(self, width):
        speedX = width - self.pad.x - self.speedWidth
        rest = max(0, speedX - self.gap * 2 - self.pad.x)
        voiceX = self.pad.x + rest * 9 // 20 + self.gap

        return (self.pad.x, voiceX, speedX, width - self.pad.x)

    def OnMeasureItem(self, n):
        return self.rowHeight

    def getRowColor(self, n):
        bg = self.GetBackgroundColour()

        if self.IsSelected(n):
            return blendColors(bg, self.highlight, 0.2 if self.HasFocus() else 0.12)

        return bg

    def OnDrawBackground(self, dc, rect, n):
        bg = self.GetBackgroundColour()
        fill = self.getRowColor(n)

        if fill != bg:
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(fill))
            dc.DrawRectangle(rect)

        # separator between rows
        dc.SetPen(wx.Pen(blendColors(bg, self.GetForegroundColour(), 0.12)))
        y = rect.GetBottom()
        dc.DrawLine(rect.GetLeft(), y, rect.GetRight() + 1, y)

    def OnDrawItem(self, dc, rect, n):
        name, voice, speed = self.entries[n]
        nameX, voiceX, speedX, right = [
            rect.x + x for x in self.columns(rect.width)
        ]
        y = rect.y + self.pad.y
        fg = self.GetForegroundColour()
        current = n == self.currentIdx

        dc.SetFont(self.boldFont if current else self.normalFont)
        dc.SetTextForeground(self.highlight if current else fg)
        drawClipped(dc, name, nameX, y, voiceX - self.gap - nameX)

        dc.SetFont(self.normalFont)
        dc.SetTextForeground(fg)
        drawClipped(dc, voice, voiceX, y, speedX - self.gap - voiceX)
        dc.DrawText(speed, right - dc.GetTextExtent(speed).width, y)


# the column titles over a CastList
class CastHeader(wx.Window):
    def __init__(self, parent, castList):
        wx.Window.__init__(self, parent, -1, style=wx.BORDER_NONE)

        self.castList = castList
        self.titles = (_("Character"), _("Voice"), _("Speed"))

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetMinSize(
            wx.Size(-1, castList.lineHeight + castList.pad.y + self.FromDIP(2))
        )

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, lambda e: self.Refresh())

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        bg = self.GetBackgroundColour()
        fg = self.GetForegroundColour()
        lc = self.castList

        dc.SetBackground(wx.Brush(bg))
        dc.Clear()
        dc.SetFont(lc.normalFont)
        dc.SetTextForeground(blendColors(fg, bg, 0.35))

        # the columns line up with the list's, which is as wide as listHolder
        nameX, voiceX, speedX, right = lc.columns(lc.GetClientSize().width)
        y = self.FromDIP(2)
        name, voice, speed = self.titles

        drawClipped(dc, name, nameX, y, voiceX - lc.gap - nameX)
        drawClipped(dc, voice, voiceX, y, speedX - lc.gap - voiceX)
        dc.DrawText(speed, right - dc.GetTextExtent(speed).width, y)


# draw text at x, y on dc, shortened with "..." to fit in width
def drawClipped(dc, text, x, y, width):
    if width > 0:
        dc.DrawText(wx.Control.Ellipsize(text, dc, wx.ELLIPSIZE_END, width), x, y)


def speedLabels():
    return ["%d%%" % round(f * 100) for f in SPEEDS]


def displayName(name):
    return _("Narrator") if name == NARRATOR else name


class ReadAloudPanel(wx.Panel):

    # how long to wait after the last change before refreshing, in ms
    REFRESH_DELAY = 300

    # the reset button (in self.tools) is made in toolParent, as in the
    # outline (see outline.OutlinePanel)
    def __init__(self, parent, scriptPanel, toolParent=None):
        wx.Panel.__init__(self, parent, -1)

        # trelbypanel.MyPanel whose script we show
        self.scriptPanel = scriptPanel

        # the speakers shown (NARRATOR, then the characters), and the
        # voices (speech.Voices) the voice list offers. names is None until
        # the cast has been shown.
        self.names = None
        self.voices = []

        # the (voice, speed) indexes in the lists for each of names, and the
        # VoiceChoice each is read in
        self.cast = []
        self.castChoices = []

        # the engine's normal rate, which SPEEDS are factors of
        self.baseRate = 0

        self.tools = wx.Panel(toolParent or self, -1)
        hdr = wx.BoxSizer(wx.HORIZONTAL)

        self.resetBtn = wx.BitmapButton(
            self.tools,
            -1,
            icons.svgBitmap("undo.svg", wx.Size(16, 16)),
            style=wx.BORDER_NONE,
        )
        self.resetBtn.SetToolTip(_("Go back to the voices picked automatically"))
        hdr.Add(self.resetBtn, 0, wx.ALL, self.FromDIP(2))
        self.tools.SetSizer(hdr)

        vsizer = wx.BoxSizer(wx.VERTICAL)

        if toolParent is None:
            vsizer.Add(self.tools, 0, wx.ALIGN_RIGHT)

        bar = wx.BoxSizer(wx.HORIZONTAL)

        self.prevBtn = self.makeButton(
            bar, "skipback.svg", _("Previous element"), self.OnPrev
        )
        self.playBtn = self.makeButton(bar, "play.svg", "", self.OnPlay)
        self.stopBtn = self.makeButton(bar, "stop.svg", _("Stop reading"), self.OnStop)
        self.nextBtn = self.makeButton(
            bar, "skipforward.svg", _("Next element"), self.OnNext
        )

        self.playBitmap = self.playBtn.GetBitmapLabel()
        self.pauseBitmap = icons.svgBitmap("pause.svg", wx.Size(20, 20))

        self.status = wx.StaticText(self, -1, "")
        bar.Add(self.status, 1, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, self.FromDIP(6))

        vsizer.Add(bar, 0, wx.EXPAND | wx.ALL, self.FromDIP(6))

        # shown instead of the cast when there's no speech engine
        self.message = wx.StaticText(self, -1, "")
        vsizer.Add(self.message, 0, wx.EXPAND | wx.ALL, self.FromDIP(10))

        # the list's native scrollbar ignores the theme's colors, so when
        # the list has one, it's sized to put it just past the right edge of
        # listHolder, out of sight, and scrollBar stands in for it (as in
        # the outline). the names are the script's text, which is left to
        # right in a right-to-left interface too, and the titles go with
        # them.
        self.listHolder = wx.Window(self, -1, style=wx.BORDER_NONE)
        gutil.keepLeftToRight(self.listHolder)
        self.list = CastList(self.listHolder)
        self.scrollBar = ScrollBar(self, self.list)

        self.header = CastHeader(self, self.list)
        gutil.keepLeftToRight(self.header)
        vsizer.Add(self.header, 0, wx.EXPAND)

        lsizer = wx.BoxSizer(wx.HORIZONTAL)
        lsizer.Add(self.listHolder, 1, wx.EXPAND)
        lsizer.Add(self.scrollBar, 0, wx.EXPAND)
        vsizer.Add(lsizer, 0, wx.EXPAND)

        # the selected speaker's name and a button to hear them, over
        # their voice and speed
        self.editor = wx.Panel(self, -1)
        esizer = wx.BoxSizer(wx.VERTICAL)

        nsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.selName = wx.StaticText(self.editor, -1, "", style=wx.ST_ELLIPSIZE_END)
        self.selName.SetFont(self.selName.GetFont().Bold())
        nsizer.Add(self.selName, 1, wx.ALIGN_CENTER_VERTICAL)

        self.sampleBtn = wx.BitmapButton(
            self.editor,
            -1,
            icons.svgBitmap("speaker.svg", wx.Size(16, 16)),
            style=wx.BORDER_NONE,
        )
        self.sampleBtn.SetToolTip(_("Hear this voice"))
        nsizer.Add(self.sampleBtn, 0, wx.ALIGN_CENTER_VERTICAL)
        esizer.Add(nsizer, 0, wx.EXPAND | wx.BOTTOM, 5)

        grid = wx.FlexGridSizer(2, 5, 10)
        grid.AddGrowableCol(1)

        self.voice = wx.Choice(self.editor, -1)
        self.voice.SetMinSize(wx.Size(self.FromDIP(60), -1))
        self.speed = wx.Choice(self.editor, -1, choices=speedLabels())

        for label, w, flags in (
            (_("Voice"), self.voice, wx.EXPAND),
            (_("Speed"), self.speed, 0),
        ):
            grid.Add(
                wx.StaticText(self.editor, -1, label), 0, wx.ALIGN_CENTER_VERTICAL
            )
            grid.Add(w, 0, flags)

        esizer.Add(grid, 0, wx.EXPAND)
        gutil.spaceSizer(esizer)
        self.editor.SetSizer(esizer)
        vsizer.Add(self.editor, 0, wx.EXPAND | wx.ALL, self.FromDIP(6))

        self.SetSizer(vsizer)

        self.timer = wx.Timer(self)

        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.listHolder.Bind(wx.EVT_SIZE, self.OnListHolderSize)
        self.scrollBar.Bind(wx.EVT_COMMAND_SCROLL, self.OnScroll)
        self.list.Bind(wx.EVT_SIZE, self.OnListSize)
        self.list.Bind(wx.EVT_IDLE, self.OnListIdle)
        self.list.Bind(wx.EVT_LISTBOX, lambda e: self.showSelected())
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.playSample())
        self.list.Bind(wx.EVT_SET_FOCUS, self.OnListFocus)
        self.list.Bind(wx.EVT_KILL_FOCUS, self.OnListFocus)
        self.resetBtn.Bind(wx.EVT_BUTTON, self.OnReset)
        self.sampleBtn.Bind(wx.EVT_BUTTON, lambda e: self.playSample())
        self.voice.Bind(wx.EVT_CHOICE, self.OnChoice)
        self.speed.Bind(wx.EVT_CHOICE, self.OnChoice)

        self.message.Hide()
        self.scrollBar.Hide()
        self.updateState()

    def makeButton(self, sizer, iconFilename, tip, handler):
        btn = wx.BitmapButton(
            self,
            -1,
            icons.svgBitmap(iconFilename, wx.Size(20, 20)),
            style=wx.BORDER_NONE,
        )
        btn.SetToolTip(tip)
        btn.Bind(wx.EVT_BUTTON, handler)
        sizer.Add(btn, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, self.FromDIP(2))

        return btn

    def getCtrl(self):
        return self.scriptPanel.ctrl

    def getReader(self):
        return self.scriptPanel.gd.mainFrame.reader

    # use the colors of the theme in the given configgui.ConfigGui: the
    # buttons and the lists like the tab bar, and the cast like the page
    def applyTheme(self, cfgGui):
        bg, fg = cfgGui.tabBarBgColor, cfgGui.tabTextColor

        theming.themeChildren(self, cfgGui)

        for w in [self, self.tools, self.resetBtn, self.header, self.sampleBtn] + [
            w for w in self.GetChildren() if isinstance(w, wx.BitmapButton)
        ]:
            w.SetBackgroundColour(bg)
            w.SetForegroundColour(fg)

        self.list.SetBackgroundColour(cfgGui.textBgColor)
        self.list.SetForegroundColour(cfgGui.textColor)
        self.list.highlight = cfgGui.accentColor
        self.listHolder.SetBackgroundColour(cfgGui.textBgColor)
        self.scrollBar.setColors(cfgGui.textBgColor, cfgGui.textColor)

        self.tools.Refresh()
        self.Refresh()

    # refresh the cast once things have been quiet for a moment
    def scheduleRefresh(self):
        if self.IsShown():
            self.timer.StartOnce(self.REFRESH_DELAY)

    # refresh the cast right away: the speakers, and their voices as
    # they'd be read now
    def refresh(self):
        self.timer.Stop()

        if not self.IsShown():
            return

        reader = self.getReader()
        backend = reader.ensureBackend()

        if not backend:
            self.showMessage(reader.noBackendReason)

            return

        sp = self.getCtrl().sp

        try:
            voices = reader.getVoices()
            cast = reader.makeCast(sp)
        except Exception as e:
            self.showMessage(str(e) or e.__class__.__name__)

            return

        # an engine with no voices to choose from has its default voice
        voices = voices or [speech.Voice(None, _("Default voice"))]
        names = [NARRATOR] + list(cast.characters)
        labels = voiceLabels(voices)

        if voices != self.voices:
            self.voices = voices
            self.voice.Set(labels)

        self.baseRate = backend.defaultRate
        ids = [v.id for v in voices]
        self.cast = []
        self.castChoices = [cast.voiceFor(name or None) for name in names]

        for choice in self.castChoices:
            self.cast.append(
                (
                    ids.index(choice.voiceId) if choice.voiceId in ids else 0,
                    speedIndex(choice.rate, self.baseRate),
                )
            )

        speeds = speedLabels()
        self.list.setEntries(
            [
                (displayName(name), labels[v], speeds[s])
                for name, (v, s) in zip(names, self.cast)
            ]
        )

        # the same speaker stays selected
        if names != self.names:
            sel = self.selectedName()
            self.names = names
            self.list.currentIdx = None
            self.list.SetSelection(names.index(sel) if sel in names else 0)

        self.resetBtn.Enable(sp.readAloud.hasInfo())
        self.showMessage(None)
        self.showSelected()
        self.updateState()

    # the speaker of the selected row, or None
    def selectedName(self):
        idx = self.list.GetSelection()

        if self.names and (0 <= idx < len(self.names)):
            return self.names[idx]

        return None

    # select row idx, showing its speaker's voice in the lists below
    def select(self, idx):
        self.list.SetSelection(idx)
        self.showSelected()

    # show the selected speaker's voice and speed in the lists below
    def showSelected(self):
        idx = self.list.GetSelection()

        if not (0 <= idx < len(self.cast)):
            return

        v, s = self.cast[idx]
        self.selName.SetLabel(displayName(self.names[idx]))
        setSelection(self.voice, v)
        setSelection(self.speed, s)

    # show msg in place of the cast, saying why there's no reading aloud,
    # or the cast if msg is None
    def showMessage(self, msg):
        if msg is not None:
            msg = _("Reading aloud isn't available.\n\n{}").format(msg)
            self.message.SetLabel(msg)
            width = self.GetClientSize().width - self.FromDIP(20)

            if width > 0:
                self.message.Wrap(width)

        self.message.Show(msg is not None)

        for w in (self.header, self.listHolder, self.editor):
            w.Show(msg is None)

        if msg is not None:
            self.scrollBar.Hide()
            self.resetBtn.Disable()

        for btn in (self.playBtn, self.prevBtn, self.stopBtn, self.nextBtn):
            btn.Show(msg is None)

        self.fitCast()

    # make the cast as tall as its rows, so that the lists are right below
    # it, unless they don't fit, when it scrolls
    def fitCast(self):
        if self.listHolder.IsShown():
            lc = self.list
            self.listHolder.SetMinSize(wx.Size(-1, 0))
            room = self.GetClientSize().height - self.GetSizer().CalcMin().height
            rows = lc.GetItemCount() * lc.rowHeight
            height = min(rows, max(room, lc.rowHeight))
            self.listHolder.SetMinSize(wx.Size(-1, height))

        self.Layout()

    # size the list to fill listHolder, plus the width of its native
    # scrollbar if it has one. called again when the scrollbar comes or goes.
    def layoutList(self):
        lc = self.list
        size = self.listHolder.GetClientSize()
        sbWidth = lc.GetSize().width - lc.GetClientSize().width
        rect = wx.Rect(0, 0, size.width + sbWidth, size.height)

        if lc.GetRect() != rect:
            lc.SetSize(rect)

        self.header.Refresh()
        self.updateScrollBar()

    # make scrollBar match the list's native scrollbar, and show it only
    # when the list can scroll
    def updateScrollBar(self):
        lc = self.list
        thumb = lc.GetScrollThumb(wx.VERTICAL)

        self.scrollBar.SetScrollbar(
            lc.GetScrollPos(wx.VERTICAL), thumb, lc.GetScrollRange(wx.VERTICAL), thumb
        )

        show = self.listHolder.IsShown() and self.scrollBar.canScroll()

        if show != self.scrollBar.IsShown():
            self.scrollBar.Show(show)
            self.Layout()

    # show what the reader is doing: the play button as a pause button
    # while it's reading, which buttons can be used, and which speaker is
    # being read. called by the frame whenever that changes.
    def updateState(self):
        reader = getattr(self.scriptPanel.gd.mainFrame, "reader", None)
        ours = bool(reader) and reader.isActive() and (reader.ctrl is self.getCtrl())
        reading = ours and reader.isReading()

        self.playBtn.SetBitmapLabel(self.pauseBitmap if reading else self.playBitmap)
        self.playBtn.SetToolTip(
            _("Pause")
            if reading
            else (_("Resume") if ours else _("Read aloud from the cursor"))
        )

        for btn in (self.prevBtn, self.stopBtn, self.nextBtn):
            btn.Enable(ours)

        if not ours:
            status = ""
        elif reading:
            status = _("Reading")
        else:
            status = _("Paused")

        self.status.SetLabel(status)

        speaker = reader.currentSpeaker() if ours else False
        idx = None

        if (speaker is not False) and self.names:
            name = NARRATOR if speaker is None else speaker

            if name in self.names:
                idx = self.names.index(name)

        if idx != self.list.currentIdx:
            self.list.setCurrent(idx)

    # after a button has been used, the keyboard goes back to the script
    def focusScript(self):
        self.getCtrl().SetFocus()

    def OnPlay(self, event):
        self.getReader().toggle(self.getCtrl())
        self.focusScript()

    def OnStop(self, event):
        self.getReader().stop()
        self.focusScript()

    def OnPrev(self, event):
        self.getReader().skip(-1)
        self.focusScript()

    def OnNext(self, event):
        self.getReader().skip(1)
        self.focusScript()

    # the VoiceChoice the lists show
    def shownChoice(self):
        voice = self.voices[max(0, self.voice.GetSelection())]
        factor = SPEEDS[max(0, self.speed.GetSelection())]

        return VoiceChoice(voice.id, int(round(self.baseRate * factor)))

    # the voice or speed of the selected speaker was changed: keep it in
    # the script, and read in it from now on. everyone else's voice is kept
    # as it is too, or tableread.assignVoices would give some of them other
    # voices to make room for this one.
    def OnChoice(self, event=None):
        name = self.selectedName()

        if name is None:
            return

        choices = dict(self.getCtrl().sp.readAloud.choices)
        choices.update(zip(self.names, self.castChoices))
        choices[name] = self.shownChoice()
        self.setChoices(choices)

    def OnReset(self, event):
        self.setChoices({})

    # replace the voices chosen in the script with choices
    def setChoices(self, choices):
        ctrl = self.getCtrl()
        settings = ctrl.sp.readAloud

        if choices != settings.choices:
            settings.choices = choices
            ctrl.sp.markChanged()
            ctrl.updateScreen()
            self.getReader().recast(ctrl)

        # the others' voices may have changed too
        self.refresh()

    # say a bit of what the selected speaker says, in the voice shown
    def playSample(self):
        name = self.selectedName()

        if name is None:
            return

        sp = self.getCtrl().sp
        speaker = name or None
        text = tableread.sampleText(tableread.utterances(sp), speaker)

        if not text:
            if speaker is None:
                text = _("This is the narrator.")
            else:
                text = _("This is {}.").format(speaker.title())

        self.getReader().preview(text, self.shownChoice())

    def OnSize(self, event):
        self.fitCast()

    def OnListHolderSize(self, event):
        self.layoutList()

    def OnListSize(self, event):
        event.Skip()
        self.layoutList()

    # the list can scroll in many ways (the mouse wheel, the keyboard, the
    # selection changing, ...), which all end with it going idle
    def OnListIdle(self, event):
        event.Skip()
        self.updateScrollBar()

    def OnScroll(self, event):
        self.list.ScrollToRow(self.scrollBar.GetThumbPosition())

    # the selection is drawn stronger while the list has the focus
    def OnListFocus(self, event):
        event.Skip()
        self.list.Refresh()

    def OnTimer(self, event):
        self.refresh()

    def OnDestroy(self, event):
        if event.GetEventObject() is self:
            self.timer.Stop()

        event.Skip()
