import wx

import trelby.gutil as gutil


# shows one or two (one if cbil2 = None) checklistbox widgets with
# contents from cbil1 and possibly cbil2, which are lists of
# CheckBoxItems. btns[12] are bools for whether or not to include helper
# buttons. if OK is pressed, the incoming lists' items' selection status
# will be modified.
class CheckBoxDlg(wx.Dialog):
    def __init__(
        self, parent, title, cbil1, descr1, btns1, cbil2=None, descr2=None, btns2=None
    ):
        wx.Dialog.__init__(self, parent, -1, title, style=wx.DEFAULT_DIALOG_STYLE)

        vsizer = wx.BoxSizer(wx.VERTICAL)

        self.cbil1 = cbil1
        self.list1 = self.addList(descr1, self, vsizer, cbil1, btns1, True)

        if cbil2 != None:
            self.cbil2 = cbil2
            self.list2 = self.addList(descr2, self, vsizer, cbil2, btns2, False, 20)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        hsizer.Add((1, 1), 1)

        cancelBtn = gutil.createStockButton(self, _("Cancel"))
        hsizer.Add(cancelBtn)

        okBtn = gutil.createStockButton(self, "OK")
        hsizer.Add(okBtn, 0, wx.LEFT, 10)

        vsizer.Add(hsizer, 0, wx.EXPAND | wx.TOP, 10)

        gutil.finishWindow(self, vsizer)

        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=cancelBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=okBtn.GetId())

        okBtn.SetFocus()

    def addList(self, descr, parent, sizer, items, doBtns, isFirst, pad=0):
        sizer.Add(wx.StaticText(parent, -1, descr), 0, wx.TOP, pad)

        if doBtns:
            hsizer = wx.BoxSizer(wx.HORIZONTAL)

            if isFirst:
                funcs = [self.OnSet1, self.OnClear1, self.OnToggle1]
            else:
                funcs = [self.OnSet2, self.OnClear2, self.OnToggle2]

            tmp = wx.Button(parent, -1, _("Set"))
            hsizer.Add(tmp)
            self.Bind(wx.EVT_BUTTON, funcs[0], id=tmp.GetId())

            tmp = wx.Button(parent, -1, _("Clear"))
            hsizer.Add(tmp, 0, wx.LEFT, 10)
            self.Bind(wx.EVT_BUTTON, funcs[1], id=tmp.GetId())

            tmp = wx.Button(parent, -1, _("Toggle"))
            hsizer.Add(tmp, 0, wx.LEFT, 10)
            self.Bind(wx.EVT_BUTTON, funcs[2], id=tmp.GetId())

            sizer.Add(hsizer, 0, wx.TOP | wx.BOTTOM, 5)

        tmp = gutil.ThemedListBox(parent, -1, checkable=True)

        longest = -1
        for i in range(len(items)):
            it = items[i]

            tmp.Append(it.text)
            tmp.Check(i, it.selected)

            if isFirst:
                if longest != -1:
                    if len(it.text) > len(items[longest].text):
                        longest = i
                else:
                    longest = 0

        w = -1
        if isFirst:
            h = len(items)
            if longest != -1:
                w = (
                    gutil.getTextExtent(tmp.GetFont(), "[x] " + items[longest].text)[0]
                    + 15
                )
        else:
            h = min(10, len(items))

        # the items and the border
        h = h * tmp.list.rowHeight + 2
        h = max(25, h)

        gutil.setWH(tmp, w, h)
        sizer.Add(tmp, 0, wx.EXPAND)

        return tmp

    def storeResults(self, cbil, ctrl):
        for i in range(len(cbil)):
            cbil[i].selected = bool(ctrl.IsChecked(i))

    def setAll(self, ctrl, state):
        for i in range(ctrl.GetCount()):
            ctrl.Check(i, state)

    def toggle(self, ctrl):
        for i in range(ctrl.GetCount()):
            ctrl.Check(i, not ctrl.IsChecked(i))

    def OnSet1(self, event):
        self.setAll(self.list1, True)

    def OnClear1(self, event):
        self.setAll(self.list1, False)

    def OnToggle1(self, event):
        self.toggle(self.list1)

    def OnSet2(self, event):
        self.setAll(self.list2, True)

    def OnClear2(self, event):
        self.setAll(self.list2, False)

    def OnToggle2(self, event):
        self.toggle(self.list2)

    def OnOK(self, event):
        self.storeResults(self.cbil1, self.list1)

        if hasattr(self, "list2"):
            self.storeResults(self.cbil2, self.list2)

        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)
