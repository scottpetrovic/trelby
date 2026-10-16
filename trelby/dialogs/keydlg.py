import wx

import trelby.ui.gutil as gutil
import trelby.keys as keys
import trelby.ui.widgets as widgets


# asks the user for a keypress and stores it.
class KeyDlg(wx.Dialog):
    def __init__(self, parent, cmdName):
        wx.Dialog.__init__(
            self, parent, -1, _("Key capture"), style=wx.DEFAULT_DIALOG_STYLE
        )

        vsizer = wx.BoxSizer(wx.VERTICAL)

        vsizer.Add(
            widgets.WrappedText(
                self,
                _("Press the key combination you want to bind to the command '{}'.").format(
                    cmdName
                ),
                width=250,
            )
        )

        tmp = KeyDlgWidget(self, -1, (1, 1))
        vsizer.Add(tmp)

        gutil.finishWindow(self, vsizer)

        tmp.SetFocus()


# used by KeyDlg
class KeyDlgWidget(wx.Window):
    def __init__(self, parent, id, size):
        wx.Window.__init__(self, parent, id, size=size, style=wx.WANTS_CHARS)

        self.Bind(wx.EVT_CHAR, self.OnKeyChar)

    def OnKeyChar(self, ev):
        p = self.GetParent()
        p.key = keys.Key.fromKE(ev)
        p.EndModal(wx.ID_OK)
