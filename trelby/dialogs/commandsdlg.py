import xml.sax.saxutils as xss

import wx
import wx.html

import trelby.keys as keys
import trelby.ui.fileio as fileio


class CommandsDlg(wx.Frame):
    def __init__(self, cfgGl):
        wx.Frame.__init__(
            self, None, -1, _("Commands"), size=(650, 600), style=wx.DEFAULT_FRAME_STYLE
        )

        # self.Center()

        vsizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(vsizer)

        htmlWin = wx.html.HtmlWindow(self)
        rep = htmlWin.GetInternalRepresentation()
        rep.SetIndent(0, wx.html.HTML_INDENT_BOTTOM)

        # shown in the current theme's colors, but saved in light ones so
        # the file looks normal in a browser
        self.html = self.buildHtml(cfgGl, "#ffffff", "#000000", "#e8e8e8", "#a0a0a0")

        bg = htmlWin.GetBackgroundColour()
        fg = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT)
        alt = bg.ChangeLightness(85 if bg.GetLuminance() > 0.5 else 125)
        border = bg.ChangeLightness(60 if bg.GetLuminance() > 0.5 else 160)
        htmlWin.SetPage(
            self.buildHtml(
                cfgGl,
                bg.GetAsString(wx.C2S_HTML_SYNTAX),
                fg.GetAsString(wx.C2S_HTML_SYNTAX),
                alt.GetAsString(wx.C2S_HTML_SYNTAX),
                border.GetAsString(wx.C2S_HTML_SYNTAX),
            )
        )
        htmlWin.SetFocus()

        vsizer.Add(htmlWin, 1, wx.EXPAND)

        id = wx.NewIdRef()
        menu = wx.Menu()
        menu.Append(id, "&Save as...")

        mb = wx.MenuBar()
        mb.Append(menu, "&File")
        self.SetMenuBar(mb)

        self.Bind(wx.EVT_MENU, self.OnSave, id=id)

        self.Layout()

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)

    # return the commands list as an HTML page using the given colors
    def buildHtml(self, cfgGl, bgColor, textColor, keyBgColor, borderColor):
        s = (
            '<table width="100%%" border="0" cellspacing="1" cellpadding="5"'
            ' bgcolor="%s">'
            '<tr><td width="30%%" bgcolor="%s"><b>%s</b></td>'
            '<td bgcolor="%s"><b>%s</b></td></tr>'
            % (borderColor, keyBgColor, _("Key(s)"), keyBgColor, _("Command"))
        )

        for cmd in cfgGl.commands:
            s += '<tr><td width="30%%" bgcolor="%s" valign="top">' % keyBgColor

            if cmd.keys:
                s += "<br>".join(
                    xss.escape(keys.Key.fromInt(key).toStr()) for key in cmd.keys
                )
            else:
                s += "<i>%s</i>" % _("No key defined")

            s += '</td><td bgcolor="%s" valign="top">' % bgColor
            s += xss.escape(cmd.desc)
            s += "</td></tr>"

        s += "</table>"

        return """
<html><head></head><body bgcolor="%s" text="%s">

%s

<pre>
<b>Mouse:</b>

Left click             Position cursor
Left click + drag      Select text
Right click            Unselect

<b>Keyboard shortcuts in Find/Replace dialog:</b>

F                      Find
R                      Replace
</pre>
</body></html>
""" % (
            bgColor,
            textColor,
            s,
        )

    def OnCloseWindow(self, event):
        self.Destroy()

    def OnSave(self, event):
        dlg = wx.FileDialog(
            self,
            _("Filename to save as"),
            wildcard=_("HTML files (*.html)|*.html|All files|*"),
            style=wx.FD_SAVE | wx.OVERWRITE_PROMPT,
        )

        if dlg.ShowModal() == wx.ID_OK:
            fileio.writeToFile(dlg.GetPath(), self.html, self)

        dlg.Destroy()
