# offering to restore the recovery copies (see autosave.py) left over by a
# session that didn't exit cleanly.

import time

import wx

import trelby.autosave as autosave
import trelby.misc as misc


# if there are recovery copies, offer to restore them, each in a tab of the
# main window (trelbyframe.MyFrame) frame
def offerRecovery(frame):
    entries = autosave.listRecoveries(autosave.getRecoveryDir())

    if not entries:
        return

    names = "\n".join(
        "    %s  (%s)"
        % (
            e.getDisplayName(),
            time.strftime("%Y-%m-%d %H:%M", time.localtime(e.time)),
        )
        for e in entries
    )

    dlg = wx.MessageDialog(
        frame,
        _(
            "Trelby did not close normally last time. Unsaved changes\nto the following scripts were recovered:\n\n{}\n\nDo you want to restore them?"
        ).format(names),
        _("Recover Unsaved Changes"),
        wx.YES_NO | wx.CANCEL | wx.YES_DEFAULT | wx.ICON_QUESTION,
    )
    dlg.SetYesNoCancelLabels(
        misc.mnemonic("R", _("Restore")),
        misc.mnemonic("D", _("Discard")),
        misc.mnemonic("L", _("Decide later")),
    )
    response = dlg.ShowModal()
    dlg.Destroy()

    if response == wx.ID_YES:
        for e in entries:
            if not frame.panel.ctrl.isUntouched():
                frame.panel = frame.createNewPanel()

            frame.panel.ctrl.loadRecovery(e)
            frame.panel.ctrl.updateScreen()

    elif response == wx.ID_NO:
        if (
            wx.MessageBox(
                _(
                    "Are you sure you want to permanently discard\nthe recovered changes?"
                ),
                _("Confirm"),
                wx.YES_NO | wx.NO_DEFAULT,
                frame,
            )
            == wx.YES
        ):
            for e in entries:
                autosave.removeRecovery(autosave.getRecoveryDir(), e.recId)
