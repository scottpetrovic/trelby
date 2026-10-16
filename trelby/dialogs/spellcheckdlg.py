import wx

import trelby.ui.fileio as fileio
import trelby.ui.gutil as gutil
import trelby.misc as misc
import trelby.spellcheck as spellcheck


# load the word dictionary if it isn't loaded already, showing a message
# box with 'frame' as parent on errors. returns True on success.
def loadDict(frame):
    if spellcheck.gdict:
        return True

    s = fileio.loadMaybeCompressedFile(spellcheck.DICT_FILENAME, frame)
    if not s:
        return False

    spellcheck.loadDict(s)

    return True


class SpellCheckDlg(wx.Dialog):
    def __init__(self, parent, ctrl, sc, gScDict):
        wx.Dialog.__init__(
            self,
            parent,
            -1,
            _("Spell checker"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.WANTS_CHARS,
        )

        self.ctrl = ctrl

        # spellcheck.SpellCheck
        self.sc = sc

        # user's global spell checker dictionary
        self.gScDict = gScDict

        # have we added any words to global dictionary
        self.changedGlobalDict = False

        vsizer = wx.BoxSizer(wx.VERTICAL)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        hsizer.Add(
            wx.StaticText(self, -1, _("Word:")),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self.replaceEntry = wx.TextCtrl(self, -1, style=wx.TE_PROCESS_ENTER)
        hsizer.Add(self.replaceEntry, 1, wx.EXPAND)

        vsizer.Add(hsizer, 1, wx.EXPAND | wx.BOTTOM, 15)

        gsizer = wx.FlexGridSizer(2, 2, 10, 10)
        gsizer.AddGrowableCol(1)

        replaceBtn = wx.Button(self, -1, "&Replace")
        gsizer.Add(replaceBtn)

        addScriptBtn = wx.Button(self, -1, "Add to &script dictionary")
        gsizer.Add(addScriptBtn, 0, wx.EXPAND)

        skipBtn = wx.Button(self, -1, "S&kip")
        gsizer.Add(skipBtn)

        addGlobalBtn = wx.Button(self, -1, "Add to &global dictionary")
        gsizer.Add(addGlobalBtn, 0, wx.EXPAND)

        vsizer.Add(gsizer, 0, wx.EXPAND, 0)

        suggestBtn = wx.Button(self, -1, "S&uggest replacement")
        vsizer.Add(suggestBtn, 0, wx.EXPAND | wx.TOP, 10)

        self.Bind(wx.EVT_TEXT_ENTER, self.OnReplace, id=self.replaceEntry.GetId())

        self.Bind(wx.EVT_BUTTON, self.OnReplace, id=replaceBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnAddScript, id=addScriptBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnAddGlobal, id=addGlobalBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnSkip, id=skipBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnSuggest, id=suggestBtn.GetId())

        self.Bind(wx.EVT_CHAR, self.OnChar)
        self.replaceEntry.Bind(wx.EVT_CHAR, self.OnChar)
        replaceBtn.Bind(wx.EVT_CHAR, self.OnChar)
        addScriptBtn.Bind(wx.EVT_CHAR, self.OnChar)
        skipBtn.Bind(wx.EVT_CHAR, self.OnChar)
        addGlobalBtn.Bind(wx.EVT_CHAR, self.OnChar)
        suggestBtn.Bind(wx.EVT_CHAR, self.OnChar)

        gutil.finishWindow(self, vsizer)

        self.showWord()

    def showWord(self):
        self.ctrl.ed.line = self.sc.line
        self.ctrl.ed.column = self.sc.col
        self.ctrl.ed.setMark(self.sc.line, self.sc.col + len(self.sc.word) - 1)

        self.replaceEntry.SetValue(self.sc.word)

        self.ctrl.makeLineVisible(self.sc.line)
        self.ctrl.updateScreen()

    def gotoNext(self, incCol=True):
        if incCol:
            self.sc.col += len(self.sc.word)

        if not self.sc.findNext():
            wx.MessageBox(
                _("No more incorrect words found."), _("Results"), wx.OK, self
            )

            self.EndModal(wx.ID_OK)

            return

        self.showWord()

    def OnChar(self, event):
        kc = event.GetKeyCode()

        if kc == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_OK)

            return

        event.Skip()

    def OnReplace(self, event):
        if not self.sc.word:
            return

        ed = self.ctrl.ed
        word = misc.fromGUI(self.replaceEntry.GetValue())

        ed.replaceRange(self.sc.line, self.sc.col, len(self.sc.word), word)

        # carry on past the new word, wherever rewrapping put it
        self.sc.line = ed.line
        self.sc.col = ed.column

        self.ctrl.sp.paginate()

        self.gotoNext(False)

    def OnSkip(self, event=None, autoFind=False):
        if not self.sc.word:
            return

        self.gotoNext()

    def OnAddScript(self, event):
        if not self.sc.word:
            return

        self.ctrl.sp.scDict.add(self.sc.word)
        self.ctrl.sp.markChanged()
        self.gotoNext()

    def OnAddGlobal(self, event):
        if not self.sc.word:
            return

        self.gScDict.add(self.sc.word)
        self.changedGlobalDict = True

        self.gotoNext()

    def OnSuggest(self, event):
        if not self.sc.word:
            return

        wx.BeginBusyCursor()
        items = spellcheck.suggest(self.sc.word, [self.gScDict, self.ctrl.sp.scDict])
        wx.EndBusyCursor()

        if len(items) == 0:
            wx.MessageBox(_("No similar words found."), _("Results"), wx.OK, self)

            return

        dlg = wx.SingleChoiceDialog(
            self, _("Most similar words:"), _("Suggestions"), items
        )

        if dlg.ShowModal() == wx.ID_OK:
            self.replaceEntry.SetValue(items[dlg.GetSelection()])

        dlg.Destroy()
