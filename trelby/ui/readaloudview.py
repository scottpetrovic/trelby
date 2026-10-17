import re

import wx

import trelby.screenplay.tableread as tableread
import trelby.speech as speech
import trelby.ui.icons as icons
import trelby.ui.theming as theming
from trelby.screenplay.tableread import NARRATOR, VoiceChoice
from trelby.ui.scrollbar import ScrollBar

# the side panel's Read aloud tab: buttons to play, pause and stop the table
# read (frame.reader, a tablereader.TableReader) and to go from element to
# element, and the cast: the narrator and each character with their voice
# and speed, which can be changed, and a button to hear them. the voices
# chosen are kept in the script (sp.readAloud); the rest are the ones
# tableread.assignVoices picks, shown as they'd be read now. the reader
# tells the frame whenever what it's doing changes, and the frame calls
# updateState.

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


# one speaker's controls: their name and a button to hear their voice,
# over their voice and speed
class CastRow:
    def __init__(self, panel, parent, name, voiceNames):
        self.name = name

        self.label = wx.StaticText(
            parent,
            -1,
            _("Narrator") if name == NARRATOR else name,
            style=wx.ST_ELLIPSIZE_END,
        )
        self.label.SetMinSize(wx.Size(parent.FromDIP(40), -1))

        self.sampleBtn = wx.BitmapButton(
            parent, -1, panel.sampleBitmap, style=wx.BORDER_NONE
        )
        self.sampleBtn.SetToolTip(_("Hear this voice"))

        self.voice = wx.Choice(parent, -1, choices=voiceNames)
        self.voice.SetMinSize(wx.Size(parent.FromDIP(60), -1))
        self.voice.SetToolTip(_("Voice"))

        self.speed = wx.Choice(
            parent, -1, choices=["%d%%" % round(f * 100) for f in SPEEDS]
        )
        self.speed.SetToolTip(_("Speed"))

        self.sampleBtn.Bind(wx.EVT_BUTTON, lambda e: panel.playSample(self))
        self.voice.Bind(wx.EVT_CHOICE, lambda e: panel.OnChoice(self))
        self.speed.Bind(wx.EVT_CHOICE, lambda e: panel.OnChoice(self))

    def windows(self):
        return (self.label, self.sampleBtn, self.voice, self.speed)


class ReadAloudPanel(wx.Panel):

    # how long to wait after the last change before refreshing, in ms
    REFRESH_DELAY = 300

    # how far a turn of the mouse wheel scrolls the cast, in DIPs per line
    WHEEL_LINE = 20

    # the reset button (in self.tools) is made in toolParent, as in the
    # outline (see outline.OutlinePanel)
    def __init__(self, parent, scriptPanel, toolParent=None):
        wx.Panel.__init__(self, parent, -1)

        # trelbypanel.MyPanel whose script we show
        self.scriptPanel = scriptPanel

        # the speakers shown (NARRATOR, then the characters), with a
        # CastRow each, and the voices (speech.Voices) their lists offer.
        # names is None until the cast has been shown.
        self.names = None
        self.rows = []
        self.voices = []

        # the engine's normal rate, which SPEEDS are factors of
        self.baseRate = 0

        # the row of the speaker being read, or None
        self.currentRow = None

        # how far the cast is scrolled down, in pixels
        self.scrollPos = 0

        # the configgui.ConfigGui last applied, to theme new rows with
        self.cfgGui = None

        self.sampleBitmap = icons.svgBitmap("speaker.svg", wx.Size(14, 14))

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

        # the cast's rows are on inner, which is moved up and down inside
        # holder as scrollBar says (a native scrolled window's scrollbar
        # wouldn't take the theme's colors)
        self.holder = wx.Window(self, -1, style=wx.BORDER_NONE)
        self.inner = wx.Panel(self.holder, -1)
        self.scrollBar = ScrollBar(self, self.inner)

        csizer = wx.BoxSizer(wx.HORIZONTAL)
        csizer.Add(self.holder, 1, wx.EXPAND)
        csizer.Add(self.scrollBar, 0, wx.EXPAND)
        vsizer.Add(csizer, 1, wx.EXPAND)

        self.SetSizer(vsizer)

        self.timer = wx.Timer(self)

        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        self.holder.Bind(wx.EVT_SIZE, self.OnHolderSize)
        self.scrollBar.Bind(wx.EVT_COMMAND_SCROLL, self.OnScroll)
        self.resetBtn.Bind(wx.EVT_BUTTON, self.OnReset)

        for w in (self.holder, self.inner):
            w.Bind(wx.EVT_MOUSEWHEEL, self.OnWheel)

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

    # use the colors of the theme in the given configgui.ConfigGui: all of
    # it like the tab bar, and the drop-down lists like the buttons
    def applyTheme(self, cfgGui):
        self.cfgGui = cfgGui

        for w in (self, self.tools, self.resetBtn, self.holder, self.inner):
            w.SetBackgroundColour(cfgGui.tabBarBgColor)
            w.SetForegroundColour(cfgGui.tabTextColor)

        for w in self.GetChildren():
            if isinstance(w, (wx.StaticText, wx.BitmapButton)):
                w.SetBackgroundColour(cfgGui.tabBarBgColor)
                w.SetForegroundColour(cfgGui.tabTextColor)

        self.scrollBar.setColors(cfgGui.tabBarBgColor, cfgGui.tabTextColor)
        self.themeRows()
        self.tools.Refresh()
        self.Refresh()

    def themeRows(self):
        cfgGui = self.cfgGui

        if not cfgGui:
            return

        theming.themeChildren(self.inner, cfgGui)

        for row in self.rows:
            row.sampleBtn.SetBackgroundColour(cfgGui.tabBarBgColor)
            self.colorLabel(row)

    # the speaker being read in the accent color, in bold
    def colorLabel(self, row):
        cfgGui = self.cfgGui
        current = row is self.currentRow

        if cfgGui:
            row.label.SetBackgroundColour(cfgGui.tabBarBgColor)
            row.label.SetForegroundColour(
                cfgGui.accentColor if current else cfgGui.tabTextColor
            )

        font = self.inner.GetFont()
        row.label.SetFont(font.Bold() if current else font)
        row.label.Refresh()

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

        if (names != self.names) or (voices != self.voices):
            self.voices = voices
            self.makeRows(names)

        self.baseRate = backend.defaultRate
        ids = [v.id for v in voices]

        for row in self.rows:
            choice = cast.voiceFor(row.name or None)
            setSelection(
                row.voice, ids.index(choice.voiceId) if choice.voiceId in ids else 0
            )
            setSelection(row.speed, speedIndex(choice.rate, self.baseRate))

        self.resetBtn.Enable(sp.readAloud.hasInfo())
        self.showMessage(None)
        self.updateState()

    # show msg in place of the cast, saying why there's no reading aloud,
    # or the cast if msg is None
    def showMessage(self, msg):
        if msg is not None:
            msg = _("Reading aloud isn't available.\n\n{}").format(msg)
            self.message.SetLabel(msg)
            width = self.GetClientSize().width - self.FromDIP(20)

            if width > 0:
                self.message.Wrap(width)

        elif not self.message.IsShown():
            return

        self.message.Show(msg is not None)
        self.holder.Show(msg is None)

        if msg is not None:
            self.scrollBar.Hide()
            self.resetBtn.Disable()

        for btn in (self.playBtn, self.prevBtn, self.stopBtn, self.nextBtn):
            btn.Show(msg is None)

        self.Layout()

        if msg is None:
            self.layoutCast()

    # make a CastRow for each of names
    def makeRows(self, names):
        self.inner.Freeze()

        try:
            self.inner.DestroyChildren()
            self.rows = []
            self.currentRow = None

            sizer = wx.BoxSizer(wx.VERTICAL)
            voiceNames = voiceLabels(self.voices)
            pad = self.FromDIP(6)

            for name in names:
                row = CastRow(self, self.inner, name, voiceNames)
                self.rows.append(row)

                grid = wx.FlexGridSizer(2, self.FromDIP(4), self.FromDIP(4))
                grid.AddGrowableCol(0)
                grid.Add(row.label, 0, wx.EXPAND)
                grid.Add(row.sampleBtn, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
                grid.Add(row.voice, 0, wx.EXPAND)
                grid.Add(row.speed, 0)

                sizer.Add(grid, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, pad)

                for w in row.windows():
                    w.Bind(wx.EVT_MOUSEWHEEL, self.OnWheel)

            self.inner.SetSizer(sizer)
            self.names = names
            self.themeRows()
        finally:
            self.inner.Thaw()

        self.layoutCast()

    # size and place inner in holder at the scroll position, and show
    # scrollBar if it can scroll
    def layoutCast(self):
        size = self.holder.GetClientSize()
        sizer = self.inner.GetSizer()
        height = sizer.CalcMin().height if sizer else 0

        self.scrollPos = max(0, min(self.scrollPos, height - size.height))
        self.inner.SetSize(
            0, -self.scrollPos, size.width, max(height, size.height)
        )
        self.inner.Layout()

        self.scrollBar.SetScrollbar(self.scrollPos, size.height, height, size.height)
        show = self.holder.IsShown() and self.scrollBar.canScroll()

        if show != self.scrollBar.IsShown():
            self.scrollBar.Show(show)
            self.Layout()

    def scrollTo(self, pos):
        if pos != self.scrollPos:
            self.scrollPos = pos
            self.layoutCast()

    # scroll so that row shows
    def showRow(self, row):
        top = row.label.GetPosition().y + self.scrollPos - self.FromDIP(6)
        bottom = row.voice.GetRect().GetBottom() + self.scrollPos + self.FromDIP(6)
        height = self.holder.GetClientSize().height

        if top < self.scrollPos:
            self.scrollTo(top)
        elif bottom > self.scrollPos + height:
            self.scrollTo(max(top, bottom - height))

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
        row = None

        if speaker is not False:
            name = NARRATOR if speaker is None else speaker
            row = next((r for r in self.rows if r.name == name), None)

        if row is not self.currentRow:
            old = self.currentRow
            self.currentRow = row

            for r in (old, row):
                if r:
                    self.colorLabel(r)

            if row:
                self.showRow(row)

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

    # the VoiceChoice row's lists show
    def rowChoice(self, row):
        voice = self.voices[max(0, row.voice.GetSelection())]
        factor = SPEEDS[max(0, row.speed.GetSelection())]

        return VoiceChoice(voice.id, int(round(self.baseRate * factor)))

    # the voice or speed of row's speaker was changed: keep it in the
    # script, and read in it from now on
    def OnChoice(self, row):
        choices = dict(self.getCtrl().sp.readAloud.choices)
        choices[row.name] = self.rowChoice(row)
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

    # say a bit of what row's speaker says in their voice
    def playSample(self, row):
        sp = self.getCtrl().sp
        speaker = row.name or None
        text = tableread.sampleText(tableread.utterances(sp), speaker)

        if not text:
            if speaker is None:
                text = _("This is the narrator.")
            else:
                text = _("This is {}.").format(speaker.title())

        self.getReader().preview(text, self.rowChoice(row))

    def OnHolderSize(self, event):
        self.layoutCast()

    def OnScroll(self, event):
        self.scrollTo(self.scrollBar.GetThumbPosition())

    def OnWheel(self, event):
        lines = -event.GetWheelRotation() / max(1, event.GetWheelDelta())
        step = lines * event.GetLinesPerAction() * self.FromDIP(self.WHEEL_LINE)
        self.scrollTo(self.scrollPos + int(step))

    def OnTimer(self, event):
        self.refresh()

    def OnDestroy(self, event):
        if event.GetEventObject() is self:
            self.timer.Stop()

        event.Skip()
