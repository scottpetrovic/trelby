import wx

import trelby.misc as misc
import trelby.screenplay as screenplay
import trelby.textutil as textutil
import trelby.ui.gutil as gutil
import trelby.ui.widgets as widgets


# edits a scene's synopsis (see Screenplay.getSynopsis). heading is the
# scene heading's text, shown above it. after OK, self.text is the new
# synopsis (possibly empty).
class SynopsisDlg(wx.Dialog):
    def __init__(self, parent, heading, text):
        wx.Dialog.__init__(
            self,
            parent,
            -1,
            _("Scene synopsis"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.text = text

        dip = self.FromDIP

        vsizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(
            self, -1, heading, style=wx.ST_ELLIPSIZE_END | wx.ST_NO_AUTORESIZE
        )
        label.SetFont(label.GetFont().Bold())
        gutil.keepLeftToRight(label)
        vsizer.Add(label, 0, wx.EXPAND)

        tmp = wx.StaticText(
            self,
            -1,
            _(
                "What happens in the scene, in a sentence or two. It's shown in"
                " the outline, and never printed."
            ),
        )
        tmp.Wrap(dip(400))
        vsizer.Add(tmp, 0, wx.TOP, 5)

        textBox = widgets.ThemedTextCtrl(
            self, value=text, size=dip(wx.Size(400, 120))
        )
        self.textCtrl = textBox.text
        vsizer.Add(textBox, 1, wx.EXPAND | wx.TOP, 10)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add((1, 1), 1)

        cancelBtn = gutil.createStockButton(self, _("Cancel"))
        hsizer.Add(cancelBtn, 0, wx.LEFT, 10)

        okBtn = gutil.createStockButton(self, "OK")
        hsizer.Add(okBtn, 0, wx.LEFT, 10)

        vsizer.Add(hsizer, 0, wx.EXPAND | wx.TOP, 10)

        gutil.finishWindow(self, vsizer, center=True)

        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=cancelBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=okBtn.GetId())
        self.Bind(wx.EVT_CHAR_HOOK, self.OnCharHook)

        self.textCtrl.SetFocus()
        self.textCtrl.SetInsertionPointEnd()

    # Ctrl+Enter is OK (Enter starts a new line), Escape cancels
    def OnCharHook(self, event):
        kc = event.GetKeyCode()

        if (kc in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)) and event.ControlDown():
            self.OnOK()
        elif kc == wx.WXK_ESCAPE:
            self.OnCancel()
        else:
            event.Skip()

    def OnOK(self, event=None):
        self.text = misc.fromGUI(self.textCtrl.GetValue())

        self.EndModal(wx.ID_OK)

    def OnCancel(self, event=None):
        self.EndModal(wx.ID_CANCEL)


# let the user edit the synopsis of the scene whose heading starts at the
# given line in ctrl's script, and set it
def editSynopsis(parent, ctrl, line):
    sp = ctrl.sp
    heading = sp.getElemText(line)

    if sp.cfg.getType(screenplay.SCENE).screen.isCaps:
        heading = textutil.upper(heading)

    dlg = SynopsisDlg(parent, heading, sp.getSynopsis(line) or "")

    try:
        if dlg.ShowModal() != wx.ID_OK:
            return
    finally:
        dlg.Destroy()

    ctrl.setSynopsis(line, dlg.text)
