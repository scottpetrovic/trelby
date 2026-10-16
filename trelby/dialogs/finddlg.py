import dataclasses

import wx

import trelby.config as config
import trelby.ui.gutil as gutil
import trelby.misc as misc
import trelby.screenplay.search as search
import trelby.ui.widgets as widgets


# what the dialog was left showing, kept per script (MyCtrl.findState) for
# the next time it's opened
class FindState:
    def __init__(self):
        # opts.elementTypes is the element types checked in the list, or
        # None for all
        self.opts = search.FindOptions()
        self.replaceText = ""

        # whether the element type list is shown. when it isn't, every
        # element type is searched.
        self.showTypes = False


# the search itself is in screenplay/search.py: this is the dialog, and
# what it remembers between searches (the last match)
class FindDlg(wx.Dialog):
    def __init__(self, parent, ctrl):
        wx.Dialog.__init__(
            self,
            parent,
            -1,
            _("Find & Replace"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.WANTS_CHARS,
        )

        self.ctrl = ctrl

        # the search.Match found last, or None. it's what Replace
        # replaces, and Find steps past it when the cursor is still at its
        # start. the options and texts outlive the dialog in
        # ctrl.findState (see loadState / saveState).
        self.match = None

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        vsizer = wx.BoxSizer(wx.VERTICAL)

        gsizer = wx.FlexGridSizer(2, 2, 5, 20)
        gsizer.AddGrowableCol(1)

        gsizer.Add(
            wx.StaticText(self, -1, _("Find what:")), 0, wx.ALIGN_CENTER_VERTICAL
        )
        self.findEntry = wx.TextCtrl(self, -1, style=wx.TE_PROCESS_ENTER)
        gsizer.Add(self.findEntry, 0, wx.EXPAND)

        gsizer.Add(
            wx.StaticText(self, -1, _("Replace with:")), 0, wx.ALIGN_CENTER_VERTICAL
        )
        self.replaceEntry = wx.TextCtrl(self, -1, style=wx.TE_PROCESS_ENTER)
        gsizer.Add(self.replaceEntry, 0, wx.EXPAND)

        vsizer.Add(gsizer, 0, wx.EXPAND | wx.BOTTOM, 10)

        hsizer2 = wx.BoxSizer(wx.HORIZONTAL)

        vsizer2 = wx.BoxSizer(wx.VERTICAL)

        # wxGTK adds way more space by default than wxMSW between the
        # items, have to adjust for that
        pad = 0
        if misc.isWindows:
            pad = 5

        self.matchWholeCb = wx.CheckBox(self, -1, _("Match whole word only"))
        vsizer2.Add(self.matchWholeCb, 0, wx.TOP, pad)

        self.matchCaseCb = wx.CheckBox(self, -1, _("Match case"))
        vsizer2.Add(self.matchCaseCb, 0, wx.TOP, pad)

        hsizer2.Add(vsizer2, 0, wx.EXPAND | wx.RIGHT, 10)

        self.direction = wx.RadioBox(
            self, -1, _("Direction"), choices=[_("Up"), _("Down")]
        )
        self.direction.SetSelection(1)

        hsizer2.Add(self.direction, 1, 0)

        vsizer.Add(hsizer2, 0, wx.EXPAND | wx.BOTTOM, 10)

        self.extraLabel = wx.StaticText(self, -1, _("Search in:"))
        vsizer.Add(self.extraLabel)

        self.elements = widgets.ThemedListBox(self, -1, checkable=True)

        # sucky wxMSW doesn't support client data for checklistbox items,
        # so we have to store it ourselves
        self.elementTypes = []

        for t in config.getTIs():
            self.elements.Append(t.name)
            self.elementTypes.append(t.lt)

        # tall enough to show every element type without scrolling
        self.elements.SetMinSize(
            wx.Size(-1, len(self.elementTypes) * self.elements.list.rowHeight + 2)
        )
        vsizer.Add(self.elements, 1, wx.EXPAND)

        hsizer.Add(vsizer, 1, wx.EXPAND)

        vsizer = wx.BoxSizer(wx.VERTICAL)

        find = wx.Button(self, -1, "&Find next")
        vsizer.Add(find, 0, wx.EXPAND | wx.BOTTOM, 5)

        replace = wx.Button(self, -1, "&Replace")
        vsizer.Add(replace, 0, wx.EXPAND | wx.BOTTOM, 5)

        replaceAll = wx.Button(self, -1, " Replace all ")
        vsizer.Add(replaceAll, 0, wx.EXPAND | wx.BOTTOM, 5)

        self.moreButton = wx.Button(self, -1, "")
        vsizer.Add(self.moreButton, 0, wx.EXPAND | wx.BOTTOM, 5)

        hsizer.Add(vsizer, 0, wx.EXPAND | wx.LEFT, 30)

        self.Bind(wx.EVT_BUTTON, self.OnFind, id=find.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnReplace, id=replace.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnReplaceAll, id=replaceAll.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnMore, id=self.moreButton.GetId())

        gutil.btnDblClick(find, self.OnFind)
        gutil.btnDblClick(replace, self.OnReplace)

        self.Bind(wx.EVT_TEXT, self.OnText, id=self.findEntry.GetId())

        self.Bind(wx.EVT_TEXT_ENTER, self.OnFind, id=self.findEntry.GetId())
        self.Bind(wx.EVT_TEXT_ENTER, self.OnFind, id=self.replaceEntry.GetId())

        self.Bind(wx.EVT_CHAR, self.OnCharMisc)
        self.findEntry.Bind(wx.EVT_CHAR, self.OnCharEntry)
        self.replaceEntry.Bind(wx.EVT_CHAR, self.OnCharEntry)
        find.Bind(wx.EVT_CHAR, self.OnCharButton)
        replace.Bind(wx.EVT_CHAR, self.OnCharButton)
        replaceAll.Bind(wx.EVT_CHAR, self.OnCharButton)
        self.moreButton.Bind(wx.EVT_CHAR, self.OnCharButton)
        self.matchWholeCb.Bind(wx.EVT_CHAR, self.OnCharMisc)
        self.matchCaseCb.Bind(wx.EVT_CHAR, self.OnCharMisc)
        self.direction.Bind(wx.EVT_CHAR, self.OnCharMisc)
        self.elements.Bind(wx.EVT_CHAR, self.OnCharMisc)

        gutil.finishWindow(self, hsizer, center=False)

        self.loadState()
        self.findEntry.SetFocus()

    def loadState(self):
        state = self.ctrl.findState
        opts = state.opts

        self.findEntry.SetValue(opts.text)
        self.findEntry.SetSelection(-1, -1)

        self.replaceEntry.SetValue(state.replaceText)

        self.matchWholeCb.SetValue(opts.wholeWord)
        self.matchCaseCb.SetValue(opts.matchCase)

        self.direction.SetSelection(int(not opts.up))

        for i, lt in enumerate(self.elementTypes):
            self.elements.Check(
                i, (opts.elementTypes is None) or (lt in opts.elementTypes)
            )

        self.showExtra(state.showTypes)

    def saveState(self):
        state = FindState()
        state.opts = self.getOptions()
        state.replaceText = misc.fromGUI(self.replaceEntry.GetValue())
        state.showTypes = self.showTypes

        self.ctrl.findState = state

    def OnMore(self, event):
        self.showExtra(not self.showTypes)

    def OnText(self, event):
        if self.ctrl.ed.mark:
            self.ctrl.ed.clearMark()
            self.ctrl.updateScreen()

    def OnCharEntry(self, event):
        self.OnChar(event, True, False)

    def OnCharButton(self, event):
        self.OnChar(event, False, True)

    def OnCharMisc(self, event):
        self.OnChar(event, False, False)

    def OnChar(self, event, isEntry, isButton):
        kc = event.GetKeyCode()

        if kc == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_OK)
            return

        if kc == wx.WXK_RETURN:
            if isButton:
                event.Skip()
                return
            else:
                self.OnFind()
                return

        if isEntry:
            event.Skip()
        else:
            if kc < 256:
                if chr(kc) == "f":
                    self.OnFind()
                elif chr(kc) == "r":
                    self.OnReplace()
                else:
                    event.Skip()
            else:
                event.Skip()

    def showExtra(self, flag):
        self.extraLabel.Show(flag)
        self.elements.Show(flag)

        self.showTypes = flag

        if flag:
            self.moreButton.SetLabel(_("<<< Less"))
        else:
            self.moreButton.SetLabel(_("More >>>"))

        # size the dialog from its sizers, which skip hidden items, so
        # nothing gets squeezed at other DPI or font sizes
        self.SetMinSize(wx.DefaultSize)
        self.SetMinSize(self.GetBestSize())
        self.Fit()

    # the options the dialog shows, with the checked element types (None
    # if they all are)
    def getOptions(self):
        types = frozenset(
            lt for i, lt in enumerate(self.elementTypes) if self.elements.IsChecked(i)
        )

        if len(types) == len(self.elementTypes):
            types = None

        return search.FindOptions(
            text=misc.fromGUI(self.findEntry.GetValue()),
            matchCase=self.matchCaseCb.IsChecked(),
            wholeWord=self.matchWholeCb.IsChecked(),
            up=self.direction.GetSelection() == 0,
            elementTypes=types,
        )

    # the options to search with: every element type when the list is
    # hidden
    def searchOptions(self):
        opts = self.getOptions()

        if not self.showTypes:
            opts = dataclasses.replace(opts, elementTypes=None)

        return opts

    # Find next: find the next match from the cursor and select it,
    # offering to continue at the other end of the script when there are
    # no more
    def OnFind(self, event=None):
        opts = self.searchOptions()
        if not opts.text:
            return

        ed = self.ctrl.ed
        sp = self.ctrl.sp
        line, col = ed.line, ed.column

        # the cursor is still at the start of the last match, so going
        # down, start one character past it (which can be on the next
        # line), so as not to find it again. (going up, a match must end
        # at or before the cursor anyway.)
        if (
            self.match
            and not opts.up
            and ((line, col) == (self.match.line, self.match.col))
        ):
            line, col = search.advance(sp, line, col, 1)

        # a search from the very start (or end, going up) covers the whole
        # script
        fullSearch = (line, col) == search.startPos(sp, opts.up)

        self.match = search.findNext(sp, line, col, opts)

        if not self.match and not fullSearch:
            if opts.up:
                s1 = _("start")
                s2 = _("end")
            else:
                s1 = _("end")
                s2 = _("start")

            if (
                wx.MessageBox(
                    _("Search finished at the {} of the script. Do\nyou want to continue at the {} of the script?").format(
                        s1, s2
                    ),
                    _("Continue?"),
                    wx.YES_NO | wx.YES_DEFAULT,
                    self,
                )
                != wx.YES
            ):
                self.ctrl.updateScreen()

                return

            self.match = search.findNext(sp, *search.startPos(sp, opts.up), opts)

        if self.match:
            m = self.match
            ed.gotoPos(m.line, m.col)

            # selections are inclusive, so the mark is on the match's last
            # character, which can be on a later line
            ed.setMark(*search.advance(sp, m.line, m.col, m.length - 1))

            self.ctrl.makeLineVisible(m.line)
        else:
            wx.MessageBox(
                _("Search finished without results."),
                _("No matches"),
                wx.OK,
                self,
            )

        self.ctrl.updateScreen()

    # Replace: replace the current match, and find the next one
    def OnReplace(self, event=None):
        if not self.match:
            return

        opts = self.searchOptions()

        self.ctrl.ed.replaceAt(
            self.match, misc.fromGUI(self.replaceEntry.GetValue()), opts.up
        )
        self.match = None
        self.ctrl.sp.paginate()

        self.OnFind()

    # replace every match in the script
    def OnReplaceAll(self, event=None):
        opts = self.searchOptions()
        ed = self.ctrl.ed

        count = ed.replaceAll(opts, misc.fromGUI(self.replaceEntry.GetValue()))

        self.match = None

        if count != 0:
            self.ctrl.sp.paginate()
            self.ctrl.makeLineVisible(ed.line)
            self.ctrl.updateScreen()

        wx.MessageBox(_("Replaced {} matches").format(count), _("Results"), wx.OK, self)
