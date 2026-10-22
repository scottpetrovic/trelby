import wx

import trelby.translations as translations

_ = translations.trelby_translations_load()

import trelby.dialogs.textdlg as textdlg  # noqa: E402

# the dialog that shows a multi-line message, e.g. the warnings from
# loading a script


def textCtrls(win):
    for child in win.GetChildren():
        if isinstance(child, wx.TextCtrl):
            yield child

        yield from textCtrls(child)


def testTextDlgShowsTextWrapped(app):
    text = "Line 1: unknown element type.\nLine 2: " + "word " * 100

    dlg = textdlg.TextDlg(None, text, "Warnings")

    try:
        assert dlg.GetTitle() == "Warnings"

        (tc,) = textCtrls(dlg)
        assert tc.GetValue() == text
        assert tc.HasFlag(wx.TE_READONLY)
        assert tc.HasFlag(wx.TE_MULTILINE)
        assert tc.HasFlag(wx.TE_WORDWRAP)
    finally:
        dlg.Destroy()
