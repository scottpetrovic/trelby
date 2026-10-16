import os

import trelby.config as config
import trelby.gutil as gutil
import trelby.themes as themes
import wx


# the names of the built-in themes, as shown. listed here so they're found
# for translation.
def builtinLabels():
    return {
        "Light": _("Light"),
        "Dark": _("Dark"),
        "Parchment": _("Parchment"),
        "Solarized Light": _("Solarized Light"),
        "Solarized Dark": _("Solarized Dark"),
        "Monokai": "Monokai",
        "Dracula": "Dracula",
        "Nord": "Nord",
    }


class ThemePanel(wx.Panel):
    def __init__(self, parent, id, cfg):
        wx.Panel.__init__(self, parent, id)
        self.cfg = cfg

        vsizer = wx.BoxSizer(wx.VERTICAL)

        vsizer.Add(wx.StaticText(self, -1, _("Theme:")), 0, wx.BOTTOM, 5)

        self.themeList = gutil.ThemedListBox(self, -1, size=self.FromDIP(wx.Size(250, 220)))
        vsizer.Add(self.themeList, 0, wx.BOTTOM, 10)

        vsizer.Add(
            gutil.WrappedText(
                self,
                _(
                    "System default follows the light or dark mode setting "
                    "of your operating system.\n\n"
                    "To make your own theme, export one as a starting point, "
                    "edit the file's colors, and click Reload. Theme files "
                    "are read from the themes folder."
                ),
            ),
            0,
            wx.EXPAND | wx.BOTTOM,
            10,
        )

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        self.exportBtn = wx.Button(self, -1, _("Export") + "...")
        self.exportBtn.SetToolTip(_("Save the selected theme as a theme file"))
        hsizer.Add(self.exportBtn, 0, wx.RIGHT, 10)

        folderBtn = wx.Button(self, -1, _("Open themes folder"))
        hsizer.Add(folderBtn, 0, wx.RIGHT, 10)

        reloadBtn = wx.Button(self, -1, _("Reload"))
        reloadBtn.SetToolTip(_("Read the theme files again"))
        hsizer.Add(reloadBtn)

        vsizer.Add(hsizer, 0, wx.BOTTOM, 10)

        # problems with the theme files
        self.errorsEntry = wx.TextCtrl(
            self,
            -1,
            size=self.FromDIP(wx.Size(-1, 90)),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP,
        )
        vsizer.Add(self.errorsEntry, 0, wx.EXPAND)

        # pick up theme files added since the last time
        self.reload()

        gutil.finishWindow(self, vsizer, center=False)

        self.Bind(wx.EVT_LISTBOX, self.OnMisc, id=self.themeList.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnExport, id=self.exportBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnOpenFolder, id=folderBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnReload, id=reloadBtn.GetId())

    # read the theme files and refill the list
    def reload(self):
        errors = config.loadCustomThemes()

        labels = builtinLabels()

        # theme setting values, in list order
        self.names = [config.THEME_SYSTEM]
        items = [_("System default")]

        for t in themes.getAll():
            self.names.append(t.name)
            items.append(labels.get(t.name, t.name) if t.isBuiltin() else t.name)

        self.themeList.Set(items)

        lines = []

        if self.cfg.theme not in self.names:
            lines.append(
                _("The theme '{}' wasn't found, so System default is used.").format(
                    self.cfg.theme
                )
            )

        if errors:
            lines.append(_("Skipped theme files:"))
            lines.extend(errors)

        self.errorsEntry.SetValue("\n".join(lines))
        self.errorsEntry.Show(bool(lines))
        self.Layout()

        self.cfg2gui()

    def OnMisc(self, event=None):
        sel = self.themeList.GetSelection()

        if sel != wx.NOT_FOUND:
            self.cfg.theme = self.names[sel]

        self.updateExportBtn()

    def OnReload(self, event):
        self.reload()

    def OnOpenFolder(self, event):
        path = config.themesDir()

        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            wx.MessageBox(
                _("Can't create the themes folder '{}': {}").format(path, e),
                _("Error"),
                wx.OK,
                self,
            )
            return

        wx.LaunchDefaultApplication(path)

    # save the selected theme as a theme file, named after the file
    def OnExport(self, event):
        theme = config.findTheme(self.cfg.theme)
        if theme is None:
            return

        dirName = config.themesDir()

        try:
            os.makedirs(dirName, exist_ok=True)
        except OSError:
            dirName = ""

        dlg = wx.FileDialog(
            self,
            _("Theme file to save as (its name becomes the theme's name)"),
            defaultDir=dirName,
            defaultFile=_("My {}").format(theme.name) + ".json",
            wildcard=_("Theme files") + " (*.json)|*.json",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        )

        path = None
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()

        dlg.Destroy()

        if not path:
            return

        name = os.path.splitext(os.path.basename(path))[0]

        # overwriting a custom theme's own file is fine
        other = themes.find(name)
        if other and (
            other.isBuiltin()
            or os.path.normcase(os.path.abspath(other.path))
            != os.path.normcase(os.path.abspath(path))
        ):
            wx.MessageBox(
                _(
                    "There's already a theme named '{}'. Choose another file name."
                ).format(name),
                _("Error"),
                wx.OK,
                self,
            )
            return

        if gutil.writeToFile(path, themes.toJson(theme, name), self):
            self.reload()

    def updateExportBtn(self):
        # the system default is either Light or Dark, so export one of
        # those instead
        self.exportBtn.Enable(config.findTheme(self.cfg.theme) is not None)

    def cfg2gui(self):
        if self.cfg.theme in self.names:
            self.themeList.SetSelection(self.names.index(self.cfg.theme))
        else:
            self.themeList.SetSelection(0)

        self.updateExportBtn()
