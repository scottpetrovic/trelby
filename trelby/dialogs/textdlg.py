import wx

import trelby.ui.gutil as gutil
import trelby.misc as misc


# shows a multi-line string to the user in a scrollable text control.
class TextDlg(wx.Dialog):
    def __init__(self, parent, text, title):
        wx.Dialog.__init__(
            self, parent, -1, title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )

        vsizer = wx.BoxSizer(wx.VERTICAL)

        tc = wx.TextCtrl(
            self,
            -1,
            size=wx.Size(400, 200),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_LINEWRAP,
        )
        tc.SetValue(text)
        vsizer.Add(tc, 1, wx.EXPAND)

        vsizer.Add(gutil.Separator(self), 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)

        okBtn = gutil.createStockButton(self, "OK")
        vsizer.Add(okBtn, 0, wx.ALIGN_CENTER)

        gutil.finishWindow(self, vsizer)

        self.Bind(wx.EVT_BUTTON, self.OnOK, id=okBtn.GetId())

        okBtn.SetFocus()

    def OnOK(self, event):
        self.EndModal(wx.ID_OK)


# helper function for using TextDlg
def showText(parent, text, title="Message"):
    dlg = TextDlg(parent, text, title)
    dlg.ShowModal()
    dlg.Destroy()


# ask user for a single-line text input.
class TextInputDlg(wx.Dialog):
    def __init__(self, parent, text, title, validateFunc=None):
        wx.Dialog.__init__(
            self, parent, -1, title, style=wx.DEFAULT_DIALOG_STYLE | wx.WANTS_CHARS
        )

        # function to call to validate the input string on OK. can be
        # None, in which case it is not called. if it returns "", the
        # input is valid, otherwise the string it returns is displayed in
        # a message box and the dialog is not closed.
        self.validateFunc = validateFunc

        vsizer = wx.BoxSizer(wx.VERTICAL)

        vsizer.Add(wx.StaticText(self, -1, text), 1, wx.EXPAND | wx.BOTTOM, 5)

        self.tc = wx.TextCtrl(self, -1, style=wx.TE_PROCESS_ENTER)
        vsizer.Add(self.tc, 1, wx.EXPAND)

        vsizer.Add(gutil.Separator(self), 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        cancelBtn = gutil.createStockButton(self, _("Cancel"))
        hsizer.Add(cancelBtn)

        okBtn = gutil.createStockButton(self, "OK")
        hsizer.Add(okBtn, 0, wx.LEFT, 10)

        vsizer.Add(hsizer, 0, wx.EXPAND | wx.TOP, 5)

        gutil.finishWindow(self, vsizer)

        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=cancelBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=okBtn.GetId())

        self.Bind(wx.EVT_TEXT_ENTER, self.OnOK, id=self.tc.GetId())

        self.tc.Bind(wx.EVT_CHAR, self.OnCharEntry)
        cancelBtn.Bind(wx.EVT_CHAR, self.OnCharButton)
        okBtn.Bind(wx.EVT_CHAR, self.OnCharButton)

        self.tc.SetFocus()

    def OnCharEntry(self, event):
        self.OnChar(event, True)

    def OnCharButton(self, event):
        self.OnChar(event, False)

    def OnChar(self, event, isEntry):
        kc = event.GetKeyCode()

        if kc == wx.WXK_ESCAPE:
            self.OnCancel()

        elif (kc == wx.WXK_RETURN) and isEntry:
            self.OnOK()

        else:
            event.Skip()

    def OnOK(self, event=None):
        self.input = misc.fromGUI(self.tc.GetValue())

        if self.validateFunc:
            msg = self.validateFunc(self.input)

            if msg:
                wx.MessageBox(msg, _("Error"), wx.OK, self)

                return

        self.EndModal(wx.ID_OK)

    def OnCancel(self, event=None):
        self.EndModal(wx.ID_CANCEL)
