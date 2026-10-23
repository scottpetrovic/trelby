import wx

import trelby.misc as misc
import trelby.screenplay as screenplay
import trelby.screenplay.alternates as alternates
import trelby.screenplay.scriptformats as scriptformats
import trelby.textutil as textutil
import trelby.ui.gutil as gutil
import trelby.ui.widgets as widgets


# the takes being edited in AlternatesDlg: a list of Takes, the first one
# being the one shown in the script, and which one is selected. kept
# apart from the dialog's controls so that it can be tested without them.
class TakeList:
    def __init__(self, shown, others):
        self.takes = [shown] + list(others)
        self.selected = 0

    # set the selected take's text, keeping its formatting if the text is
    # the same
    def setText(self, text):
        old = self.takes[self.selected]

        if text != old.text:
            self.takes[self.selected] = alternates.Take(text)

    # add an empty take after the others and select it
    def add(self):
        self.takes.append(alternates.Take(""))
        self.selected = len(self.takes) - 1

    # make the selected take the shown one. the takes are a ring, so they
    # keep their order, as Editor.switchAlternate does.
    def show(self):
        k = self.selected
        self.takes = self.takes[k:] + self.takes[:k]
        self.selected = 0

    # move the selected take up (step -1) or down (1). moving one to the
    # top makes it the shown one.
    def move(self, step):
        k = self.selected
        n = k + step

        if 0 <= n < len(self.takes):
            self.takes[k], self.takes[n] = self.takes[n], self.takes[k]
            self.selected = n

    # delete the selected take, unless it's the only one. deleting the
    # shown one shows the next one.
    def delete(self):
        if len(self.takes) > 1:
            del self.takes[self.selected]
            self.selected = min(self.selected, len(self.takes) - 1)

    # the takes as Editor.setTakes takes them: (shown, others), tidied up
    # (alternates.cleanText) and without empty ones (unless all are, when
    # the shown one is empty)
    def result(self):
        takes = [alternates.makeTake(t.text, t) for t in self.takes]
        takes = [t for t in takes if t.text] or [alternates.Take("")]

        return takes[0], takes[1:]

    # the list's label for take k
    def label(self, k):
        s = self.takes[k].preview(70) or _("(empty)")

        if k == 0:
            return _("Shown: {}").format(s)

        return s


# view, edit, reorder and delete the takes of an element (see
# screenplay/alternates.py). title says which element. after OK,
# self.takes.result() is the new (shown take, other takes).
class AlternatesDlg(wx.Dialog):
    def __init__(self, parent, title, shown, others):
        wx.Dialog.__init__(
            self,
            parent,
            -1,
            _("Alternate Dialogue"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.takes = TakeList(shown, others)

        dip = self.FromDIP

        vsizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(
            self, -1, title, style=wx.ST_ELLIPSIZE_END | wx.ST_NO_AUTORESIZE
        )
        label.SetFont(label.GetFont().Bold())
        gutil.keepLeftToRight(label)
        vsizer.Add(label, 0, wx.EXPAND)

        tmp = wx.StaticText(
            self,
            -1,
            _(
                "Other versions of the element's text. The first one is shown"
                " and printed; the others are kept for switching to."
            ),
        )
        tmp.Wrap(dip(460))
        vsizer.Add(tmp, 0, wx.TOP, 5)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        self.list = widgets.ThemedListBox(self, -1, size=dip(wx.Size(360, 160)))
        gutil.keepLeftToRight(self.list)
        hsizer.Add(self.list, 1, wx.EXPAND)

        bsizer = wx.BoxSizer(wx.VERTICAL)
        self.newBtn = self.addButton(bsizer, _("New"), self.OnNew)
        self.showBtn = self.addButton(bsizer, _("Show this one"), self.OnShow)
        self.upBtn = self.addButton(bsizer, _("Move up"), lambda e: self.OnMove(-1))
        self.downBtn = self.addButton(bsizer, _("Move down"), lambda e: self.OnMove(1))
        self.deleteBtn = self.addButton(bsizer, _("Delete"), self.OnDelete)
        hsizer.Add(bsizer, 0, wx.LEFT, 10)

        vsizer.Add(hsizer, 1, wx.EXPAND | wx.TOP, 10)

        textBox = widgets.ThemedTextCtrl(self, size=dip(wx.Size(460, 90)))
        self.textCtrl = textBox.text
        gutil.keepLeftToRight(self.textCtrl)
        vsizer.Add(textBox, 0, wx.EXPAND | wx.TOP, 10)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add((1, 1), 1)

        cancelBtn = gutil.createStockButton(self, _("Cancel"))
        hsizer.Add(cancelBtn, 0, wx.LEFT, 10)

        okBtn = gutil.createStockButton(self, "OK")
        hsizer.Add(okBtn, 0, wx.LEFT, 10)

        vsizer.Add(hsizer, 0, wx.EXPAND | wx.TOP, 10)

        gutil.finishWindow(self, vsizer, center=True)

        self.list.Bind(wx.EVT_LISTBOX, self.OnSelect)
        self.textCtrl.Bind(wx.EVT_TEXT, self.OnText)
        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=cancelBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=okBtn.GetId())
        self.Bind(wx.EVT_CHAR_HOOK, self.OnCharHook)

        self.refresh()
        self.textCtrl.SetFocus()
        self.textCtrl.SetInsertionPointEnd()

    def addButton(self, sizer, label, handler):
        btn = gutil.createStockButton(self, label)
        sizer.Add(btn, 0, wx.EXPAND | wx.BOTTOM, 5)
        btn.Bind(wx.EVT_BUTTON, handler)

        return btn

    # show self.takes in the list and the selected one's text in the text
    # field
    def refresh(self):
        tl = self.takes
        self.list.Set([tl.label(k) for k in range(len(tl.takes))])
        self.list.SetSelection(tl.selected)

        self.updating = True
        self.textCtrl.ChangeValue(tl.takes[tl.selected].text)
        self.updating = False

        for btn, enable in (
            (self.showBtn, tl.selected != 0),
            (self.upBtn, tl.selected > 0),
            (self.downBtn, tl.selected < len(tl.takes) - 1),
            (self.deleteBtn, len(tl.takes) > 1),
        ):
            # Windows draws a button itself when it's enabled, without the
            # theme's look (see theming), so it's drawn again
            if btn.Enable(enable):
                btn.Refresh()

    def OnSelect(self, event=None):
        k = self.list.GetSelection()

        if k != -1:
            self.takes.selected = k
            self.refresh()

    def OnText(self, event=None):
        if self.updating:
            return

        tl = self.takes
        tl.setText(misc.fromGUI(self.textCtrl.GetValue()))
        self.list.SetString(tl.selected, tl.label(tl.selected))

    def OnNew(self, event=None):
        self.takes.add()
        self.refresh()
        self.textCtrl.SetFocus()

    def OnShow(self, event=None):
        self.takes.show()
        self.refresh()

    def OnMove(self, step):
        self.takes.move(step)
        self.refresh()

    def OnDelete(self, event=None):
        self.takes.delete()
        self.refresh()

    # Ctrl+Enter is OK (Enter starts a new paragraph), Escape cancels
    def OnCharHook(self, event):
        kc = event.GetKeyCode()

        if (kc in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)) and event.ControlDown():
            self.OnOK()
        elif kc == wx.WXK_ESCAPE:
            self.OnCancel()
        else:
            event.Skip()

    def OnOK(self, event=None):
        self.EndModal(wx.ID_OK)

    def OnCancel(self, event=None):
        self.EndModal(wx.ID_CANCEL)


# let the user manage the takes of the element containing line in ctrl's
# script, and set them. returns whether anything changed.
def manageAlternates(parent, ctrl, line):
    sp = ctrl.sp
    first = sp.getElemFirstIndexFromLine(line)
    lt = sp.lines[first].lt
    title = scriptformats.typeLabel(sp.cfg, lt)

    # and the speaker's name, for dialogue and parentheticals
    if lt in (screenplay.DIALOGUE, screenplay.PAREN):
        name = sp.getCharacterAt(first)

        if name:
            title += ": " + textutil.upper(name)

    dlg = AlternatesDlg(
        parent, title, sp.getShownTake(line), sp.getAlternates(line)
    )

    try:
        if dlg.ShowModal() != wx.ID_OK:
            return False
    finally:
        dlg.Destroy()

    shown, others = dlg.takes.result()

    return ctrl.setTakes(line, shown, others)
