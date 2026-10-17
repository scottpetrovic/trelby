# editing a note in place on its card beside the page in the script (see
# ScriptPainter.drawNoteMarkers), after double-clicking the card or
# choosing Edit from its right-click menu, or writing a new one on a blank
# card after Edit / Add note (MyCtrl.newNoteLine): a text field over the
# card, at
# least EDIT_LINES lines high, which follows the card as the script
# scrolls. as in the notes sidebar, Ctrl+Enter or clicking elsewhere
# finishes, Esc cancels, and a note left empty is deleted.

import wx

from trelby.screenplay.notes import Note

# how many lines the text field has at least
EDIT_LINES = 4


class NoteEditor:

    # edit the note at 'index' among the notes of the paragraph starting
    # at 'line' in ctrl (the MyCtrl, which keeps us in ctrl.noteEditor),
    # whose card is at rect, or write a new one there if index is None,
    # which isn't in the script until it's finished
    def __init__(self, ctrl, line, index, rect):
        self.ctrl = ctrl
        self.line = line
        self.index = index

        if index is None:
            self.note = Note("")
        else:
            self.note = ctrl.sp.getParaNotes(line)[index]

        cfgGui = ctrl.getCfgGui()

        self.text = wx.TextCtrl(
            ctrl, -1, self.note.text, style=wx.TE_MULTILINE | wx.BORDER_SIMPLE
        )
        self.text.SetBackgroundColour(cfgGui.textBgColor)
        self.text.SetForegroundColour(cfgGui.textColor)
        self.text.SetFont(wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT))
        self.text.SetToolTip(
            _("Ctrl+Enter or click elsewhere to finish, Esc to cancel")
        )
        self.place(rect)

        self.text.Bind(wx.EVT_CHAR_HOOK, self.OnKey)
        self.text.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)

        self.text.SetFocus()
        self.text.SetInsertionPointEnd()

    # put the text field over the card at rect
    def place(self, rect):
        h = self.text.GetCharHeight() * EDIT_LINES + self.text.FromDIP(10)
        r = wx.Rect(rect.x, rect.y, rect.width, max(rect.height, h))

        if self.text.GetRect() != r:
            self.text.SetRect(r)

    # follow the card after the script has been drawn, given its new
    # ctrl.noteMarkers. if it's gone (scrolled out of view, or there's no
    # room for cards any more), the editing ends.
    def update(self, markers):
        key = (self.line, self.index)

        # the blank card after the paragraph's notes
        if self.index is None:
            key = (self.line, len(self.ctrl.sp.getParaNotes(self.line)))

        for rect, line, index in markers:
            if (line, index) == key:
                self.place(rect)

                return

        # not while the script is being drawn
        self.finishLater()

    # stop editing, keeping the new text or not. a note left empty is
    # deleted.
    def finish(self, keep):
        ctrl = self.ctrl

        if ctrl.noteEditor is not self:
            return

        ctrl.noteEditor = None

        if self.index is None:
            ctrl.newNoteLine = None

        text = self.text.GetValue().replace("\r\n", "\n").strip()

        # this can be called from the text field's own event handlers, so
        # it's destroyed later
        self.text.Hide()
        wx.CallAfter(self.text.Destroy)

        index = None if self.index is None else self.findNote()

        if self.index is None:
            if keep and text:
                ctrl.addNote(self.line, text)
        elif keep and (index is not None) and (text != self.note.text):
            if text:
                ctrl.setNote(self.line, index, self.note.replace(text=text))
            else:
                ctrl.deleteNote(self.line, index)

        ctrl.Refresh(False)

    # finish, keeping the text, after the current event, unless the editing
    # has ended by then
    def finishLater(self):
        wx.CallAfter(self.finish, True)

    # the note's index among its paragraph's notes now, which can have
    # changed if the script was changed while it was being edited (by undo
    # from the menu, say), or None if it's gone
    def findNote(self):
        sp = self.ctrl.sp

        if self.line >= len(sp.lines):
            return None

        notes = sp.getParaNotes(self.line)

        if (self.index < len(notes)) and (notes[self.index] == self.note):
            return self.index

        for k, note in enumerate(notes):
            if note == self.note:
                return k

        return None

    def OnKey(self, event):
        kc = event.GetKeyCode()

        if kc == wx.WXK_ESCAPE:
            self.finish(False)
            self.ctrl.SetFocus()
        elif event.ControlDown() and (kc in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)):
            self.finish(True)
            self.ctrl.SetFocus()
        else:
            event.Skip()

    # clicking elsewhere ends the editing, once the focus has moved
    def OnKillFocus(self, event):
        event.Skip()
        self.finishLater()
