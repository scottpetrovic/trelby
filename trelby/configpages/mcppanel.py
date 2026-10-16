import json
import os.path
import sys

import trelby
import trelby.gutil as gutil
import trelby.mcpapp as mcpapp
import trelby.util as util
import wx


class MCPPanel(wx.Panel):
    def __init__(self, parent, id, cfg):
        wx.Panel.__init__(self, parent, id)
        self.cfg = cfg

        vsizer = wx.BoxSizer(wx.VERTICAL)

        vsizer.Add(
            gutil.WrappedText(
                self,
                _(
                    "The MCP server lets AI assistants like Claude read and edit "
                    "the scripts open in Trelby. Their edits show up right away "
                    "and can be undone, but aren't saved until you save the script."
                ),
            ),
            0,
            wx.EXPAND | wx.BOTTOM,
            10,
        )

        self.enabledCb = wx.CheckBox(self, -1, _("Turn on the MCP server"))
        vsizer.Add(self.enabledCb, 0, wx.BOTTOM, 10)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        hsizer.Add(
            wx.StaticText(self, -1, _("Port:")),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )

        self.portEntry = wx.SpinCtrl(self, -1)
        self.portEntry.SetRange(*self.cfg.cvars.getMinMax("mcpPort"))
        hsizer.Add(self.portEntry)

        vsizer.Add(hsizer, 0, wx.BOTTOM, 10)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        hsizer.Add(
            wx.StaticText(self, -1, _("Address:")),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )

        self.urlEntry = wx.TextCtrl(self, -1, style=wx.TE_READONLY)
        hsizer.Add(self.urlEntry, 1, wx.ALIGN_CENTER_VERTICAL)

        vsizer.Add(hsizer, 0, wx.EXPAND | wx.BOTTOM, 5)

        vsizer.Add(
            gutil.WrappedText(
                self,
                _(
                    "Only programs on this computer can connect. Clients that "
                    "connect by URL (like Claude Code) can use the address above."
                ),
            ),
            0,
            wx.EXPAND | wx.BOTTOM,
            10,
        )

        # Claude Desktop can only start servers, so it needs the stdio
        # bridge: "python -m trelby.mcpserver --app" from source, or
        # "Trelby.exe --mcp-bridge" for the exe.
        self.desktopBtn = wx.Button(self, -1, _("Copy Claude Desktop config"))
        self.desktopBtn.SetToolTip(
            _(
                "Copy the claude_desktop_config.json entry that connects "
                "Claude Desktop to Trelby"
            )
        )
        vsizer.Add(self.desktopBtn, 0, wx.BOTTOM, 10)
        self.Bind(wx.EVT_BUTTON, self.OnCopyDesktop, id=self.desktopBtn.GetId())

        self.statusText = wx.StaticText(self, -1, "")
        vsizer.Add(self.statusText, 0, wx.TOP, 5)

        self.cfg2gui()

        util.finishWindow(self, vsizer, center=False)

        self.Bind(wx.EVT_CHECKBOX, self.OnMisc, id=self.enabledCb.GetId())
        self.Bind(wx.EVT_SPINCTRL, self.OnMisc, id=self.portEntry.GetId())
        self.portEntry.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)

    def OnKillFocus(self, event):
        self.OnMisc()

        # if we don't call this, the spin entry on wxGTK gets stuck in
        # some weird state
        event.Skip()

    def OnMisc(self, event=None):
        self.cfg.mcpEnabled = self.enabledCb.GetValue()
        self.cfg.mcpPort = util.getSpinValue(self.portEntry)

        self.updateUrl()

    def updateUrl(self):
        self.urlEntry.SetValue(mcpapp.url(self.cfg.mcpPort))

    def OnCopyDesktop(self, event):
        port = ["--port", str(self.cfg.mcpPort)]

        if getattr(sys, "frozen", False):
            server = {"command": sys.executable, "args": ["--mcp-bridge"] + port}
        else:
            # the directory trelby is imported from
            root = os.path.dirname(os.path.abspath(trelby.__path__[0]))

            server = {
                "command": sys.executable,
                "args": ["-m", "trelby.mcpserver", "--app"] + port,
                "env": {"PYTHONPATH": root},
            }

        entry = {"trelby-app": server}

        # the inside of the "mcpServers" object, ready to be pasted in
        text = json.dumps(entry, indent=2)[1:-1].strip("\n")

        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(text))
            wx.TheClipboard.Close()

            wx.MessageBox(
                _(
                    "Copied. Quit Claude Desktop, paste this inside the\n"
                    '"mcpServers" section of claude_desktop_config.json, and\n'
                    "start Claude Desktop again."
                ),
                _("MCP server"),
                wx.OK,
                self,
            )

    def cfg2gui(self):
        self.enabledCb.SetValue(self.cfg.mcpEnabled)
        self.portEntry.SetValue(self.cfg.mcpPort)
        self.updateUrl()

        available = mcpapp.isAvailable()

        self.enabledCb.Enable(available or self.cfg.mcpEnabled)

        self.statusText.SetLabel(_("Status: {}").format(mcpapp.status()))
