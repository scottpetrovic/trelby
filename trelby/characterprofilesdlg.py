import io
import random

import wx

import trelby.characterprofiles as characterprofiles
import trelby.gutil as gutil
import trelby.namesdlg as namesdlg
import trelby.textutil as textutil
import trelby.util as util

# photos are scaled down to fit in a square this big, in pixels, before
# being stored in the script, to keep file sizes reasonable
MAX_PHOTO_SIZE = 800

# how many names the name generator suggests at a time
GENERATED_NAME_COUNT = 15

# the name generator's last used settings: type name (None = any) and
# sex (None = any, 0 = female, 1 = male)
lastNameType = None
lastNameSex = None


# load an image file and return its contents scaled down and re-encoded
# for storing in a profile, as PNG or JPEG bytes, or None if the file
# can't be read.
def loadPhoto(path):
    noLog = wx.LogNull()
    img = wx.Image(path)
    del noLog

    if not img.IsOk():
        return None

    w, h = img.GetWidth(), img.GetHeight()
    scale = MAX_PHOTO_SIZE / max(w, h)

    if scale < 1.0:
        img = img.Scale(
            max(1, round(w * scale)), max(1, round(h * scale)), wx.IMAGE_QUALITY_HIGH
        )

    buf = io.BytesIO()

    if img.HasAlpha() or img.HasMask():
        ok = img.SaveFile(buf, wx.BITMAP_TYPE_PNG)
    else:
        img.SetOption(wx.IMAGE_OPTION_QUALITY, "88")
        ok = img.SaveFile(buf, wx.BITMAP_TYPE_JPEG)

    return buf.getvalue() if ok else None


# return a stored photo as a wx.Image, or None if it can't be decoded
def photoToImage(data):
    noLog = wx.LogNull()
    img = wx.Image(io.BytesIO(data))
    del noLog

    return img if img.IsOk() else None


# return 'img' scaled down to fit in (w, h), keeping its aspect ratio, as
# a wx.Bitmap
def fitBitmap(img, w, h):
    scale = min(w / img.GetWidth(), h / img.GetHeight(), 1.0)

    if scale < 1.0:
        img = img.Scale(
            max(1, round(img.GetWidth() * scale)),
            max(1, round(img.GetHeight() * scale)),
            wx.IMAGE_QUALITY_HIGH,
        )

    return wx.Bitmap(img)


# shows one photo, scaled to fit, or a placeholder text if there's none
class PhotoPanel(wx.Panel):
    def __init__(self, parent, size):
        wx.Panel.__init__(self, parent, -1, size=size)

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        # wx.Image being shown, or None
        self.img = None

        # self.img scaled to the panel's current size, or None
        self.bitmap = None

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)

    def setImage(self, img):
        self.img = img
        self.bitmap = None
        self.Refresh()

    def OnSize(self, event):
        self.bitmap = None
        self.Refresh()
        event.Skip()

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        w, h = self.GetClientSize()

        bg = self.GetBackgroundColour()
        dim = gutil.blendColors(bg, self.GetForegroundColour(), 0.5)

        dc.SetBackground(wx.Brush(bg))
        dc.Clear()

        if self.img:
            if not self.bitmap:
                self.bitmap = fitBitmap(self.img, w - 2, h - 2)

            bw, bh = self.bitmap.GetSize()
            dc.DrawBitmap(self.bitmap, (w - bw) // 2, (h - bh) // 2)
        else:
            text = _("No photo")
            dc.SetFont(self.GetFont())
            dc.SetTextForeground(dim)
            tw, th = dc.GetTextExtent(text)
            dc.DrawText(text, (w - tw) // 2, (h - th) // 2)

        dc.SetPen(wx.Pen(dim))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle(0, 0, w, h)


# shows one photo at a larger size
class PhotoViewDlg(wx.Dialog):
    def __init__(self, parent, img, title):
        wx.Dialog.__init__(
            self,
            parent,
            -1,
            title,
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        dw, dh = wx.GetDisplaySize()
        w = min(img.GetWidth(), int(dw * 0.8))
        h = min(img.GetHeight(), int(dh * 0.8))

        panel = PhotoPanel(self, (w, h))

        vsizer = wx.BoxSizer(wx.VERTICAL)
        vsizer.Add(panel, 1, wx.EXPAND)

        okBtn = gutil.createStockButton(self, "OK")
        vsizer.Add(okBtn, 0, wx.ALIGN_RIGHT | wx.TOP, 10)

        gutil.finishWindow(self, vsizer, 10, center=True)

        panel.setImage(img)

        self.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK), id=okBtn.GetId())


# picks random names from the name database
class NameGeneratorDlg(wx.Dialog):
    def __init__(self, parent):
        wx.Dialog.__init__(
            self,
            parent,
            -1,
            _("Name generator"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        # the picked name, set when the dialog closes with wx.ID_OK
        self.name = ""

        nameArr = namesdlg.nameArr

        # type names in the order they're listed in self.typeChoice,
        # starting with None for "any"
        self.typeNames = [None] + sorted(nameArr.typeNamesById, key=str.lower)

        vsizer = wx.BoxSizer(wx.VERTICAL)

        grid = wx.FlexGridSizer(2, 2, 5, 10)
        grid.AddGrowableCol(1)

        grid.Add(wx.StaticText(self, -1, _("Origin:")), 0, wx.ALIGN_CENTER_VERTICAL)
        self.typeChoice = wx.Choice(
            self, -1, choices=[_("Any")] + self.typeNames[1:]
        )
        grid.Add(self.typeChoice, 0, wx.EXPAND)

        grid.Add(wx.StaticText(self, -1, _("Gender:")), 0, wx.ALIGN_CENTER_VERTICAL)
        self.sexChoice = wx.Choice(self, -1, choices=[_("Any"), _("Female"), _("Male")])
        grid.Add(self.sexChoice, 0, wx.EXPAND)

        vsizer.Add(grid, 0, wx.EXPAND)

        self.namesLb = gutil.ThemedListBox(self, -1, size=self.FromDIP(wx.Size(260, 280)))
        vsizer.Add(self.namesLb, 1, wx.EXPAND | wx.TOP, 10)

        genBtn = wx.Button(self, -1, _("Generate"))
        vsizer.Add(genBtn, 0, wx.TOP, 5)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add((1, 1), 1)

        cancelBtn = gutil.createStockButton(self, _("Cancel"))
        hsizer.Add(cancelBtn, 0, wx.LEFT, 10)

        self.useBtn = wx.Button(self, -1, _("Use name"))
        self.useBtn.SetDefault()
        hsizer.Add(self.useBtn, 0, wx.LEFT, 10)

        vsizer.Add(hsizer, 0, wx.EXPAND | wx.TOP, 10)

        gutil.finishWindow(self, vsizer)

        self.typeChoice.SetSelection(
            self.typeNames.index(lastNameType) if lastNameType in self.typeNames else 0
        )
        self.sexChoice.SetSelection(0 if lastNameSex is None else lastNameSex + 1)

        self.Bind(wx.EVT_BUTTON, self.OnGenerate, id=genBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=cancelBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnUse, id=self.useBtn.GetId())
        self.typeChoice.Bind(wx.EVT_CHOICE, self.OnGenerate)
        self.sexChoice.Bind(wx.EVT_CHOICE, self.OnGenerate)
        self.namesLb.Bind(wx.EVT_LISTBOX_DCLICK, self.OnUse)

        self.generate()

    def generate(self):
        global lastNameType, lastNameSex

        nameArr = namesdlg.nameArr

        lastNameType = self.typeNames[self.typeChoice.GetSelection()]
        sexSel = self.sexChoice.GetSelection()
        lastNameSex = None if sexSel <= 0 else sexSel - 1

        typeIds = None
        if lastNameType is not None:
            typeIds = {nameArr.typeId[lastNameType]}

        names = nameArr.randomNames(
            GENERATED_NAME_COUNT, typeIds, lastNameSex, random.Random()
        )

        self.namesLb.Set(names)

        if names:
            self.namesLb.SetSelection(0)

        self.useBtn.Enable(bool(names))

    def OnGenerate(self, event):
        self.generate()

    def OnUse(self, event):
        sel = self.namesLb.GetSelection()

        if sel == wx.NOT_FOUND:
            return

        self.name = self.namesLb.GetString(sel)
        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)


# edits a script's character profiles. 'profiles' is a
# characterprofiles.CharacterProfiles that's modified in place, so pass
# in a copy. 'scriptNames' is an iterable of the character names used in
# the script, and 'selectName' the name of the character to show first,
# or None.
class CharacterProfilesDlg(wx.Dialog):
    def __init__(self, parent, profiles, scriptNames, selectName=None):
        wx.Dialog.__init__(
            self,
            parent,
            -1,
            _("Character profiles"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.charProfiles = profiles

        normalize = characterprofiles.normalizeName

        # normalized names of characters in the script
        self.scriptNames = {normalize(n) for n in scriptNames} - {""}

        # the profiles shown in the list, in the same order. script
        # characters without a profile get an empty one, which is dropped
        # again on OK unless the user fills it in.
        self.profiles = list(profiles.profiles)

        haveNames = {normalize(p.name) for p in self.profiles}

        for name in self.scriptNames - haveNames:
            self.profiles.append(characterprofiles.CharacterProfile(name))

        self.sortProfiles()

        # name of each profile when the dialog opened. key = id(profile),
        # value = (profile, normalized name). the profile is kept here so
        # that its id can't get reused by a new one if it's deleted.
        self.origNames = {id(p): (p, normalize(p.name)) for p in self.profiles}

        # set on OK: script characters whose profile was renamed. key = old
        # name, value = new name, both normalized.
        self.renames = {}

        # profile being shown, or None
        self.cur = None

        # index of the photo being shown in self.cur.photos
        self.photoIdx = 0

        # True while we fill in the controls ourselves, so that their
        # change events don't get treated as edits
        self.updating = False

        dip = self.FromDIP

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        # left side: character list

        vsizer = wx.BoxSizer(wx.VERTICAL)
        vsizer.Add(wx.StaticText(self, -1, _("Characters:")))

        self.charList = gutil.ThemedListBox(self, -1, size=dip(wx.Size(190, -1)))
        vsizer.Add(self.charList, 1, wx.EXPAND | wx.TOP, 3)

        hint = wx.StaticText(self, -1, _("Grayed out: no profile yet"))
        hint.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))
        vsizer.Add(hint, 0, wx.TOP, 3)

        btnSizer = wx.BoxSizer(wx.HORIZONTAL)

        newBtn = wx.Button(self, -1, _("New"))
        btnSizer.Add(newBtn)

        self.delBtn = gutil.createStockButton(self, _("Delete"))
        btnSizer.Add(self.delBtn, 0, wx.LEFT, 5)

        vsizer.Add(btnSizer, 0, wx.TOP, 5)

        hsizer.Add(vsizer, 0, wx.EXPAND)

        # right side: the selected profile

        self.form = wx.Panel(self, -1)
        formSizer = wx.BoxSizer(wx.VERTICAL)

        # photo carousel: the current photo, with arrows on its sides to
        # page through the photos
        carouselSizer = wx.BoxSizer(wx.HORIZONTAL)

        self.prevBtn = wx.Button(self.form, -1, "<", style=wx.BU_EXACTFIT)
        self.prevBtn.SetToolTip(_("Previous photo"))
        carouselSizer.Add(self.prevBtn, 0, wx.EXPAND | wx.RIGHT, 5)

        self.photoPanel = PhotoPanel(self.form, dip(wx.Size(420, 260)))
        self.photoPanel.SetToolTip(_("Double-click to view a larger version"))
        carouselSizer.Add(self.photoPanel, 1, wx.EXPAND)

        self.nextBtn = wx.Button(self.form, -1, ">", style=wx.BU_EXACTFIT)
        self.nextBtn.SetToolTip(_("Next photo"))
        carouselSizer.Add(self.nextBtn, 0, wx.EXPAND | wx.LEFT, 5)

        formSizer.Add(carouselSizer, 0, wx.EXPAND)

        photoBtnSizer = wx.BoxSizer(wx.HORIZONTAL)

        self.photoLabel = wx.StaticText(self.form, -1, "")
        photoBtnSizer.Add(self.photoLabel, 1, wx.ALIGN_CENTER_VERTICAL)

        self.addPhotoBtn = wx.Button(self.form, -1, _("Add photo..."))
        photoBtnSizer.Add(self.addPhotoBtn)

        self.removePhotoBtn = wx.Button(self.form, -1, _("Remove photo"))
        photoBtnSizer.Add(self.removePhotoBtn, 0, wx.LEFT, 5)

        formSizer.Add(photoBtnSizer, 0, wx.EXPAND | wx.TOP, 5)

        # key = attribute name, value = the control editing it
        self.ctrls = {}

        # name, which is what ties the profile to the script, so it gets
        # its own line and a bold font
        nameSizer = wx.BoxSizer(wx.HORIZONTAL)

        nameLabel = wx.StaticText(self.form, -1, _("Name:"))
        nameLabel.SetFont(nameLabel.GetFont().Bold())
        nameSizer.Add(nameLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self.ctrls["name"] = wx.TextCtrl(self.form, -1)
        self.ctrls["name"].SetFont(self.ctrls["name"].GetFont().Bold())
        nameSizer.Add(self.ctrls["name"], 1, wx.ALIGN_CENTER_VERTICAL)

        genBtn = wx.Button(self.form, -1, _("Generate..."))
        genBtn.SetToolTip(_("Pick a name from the name database"))
        nameSizer.Add(genBtn, 0, wx.LEFT, 5)

        formSizer.Add(nameSizer, 0, wx.EXPAND | wx.TOP, 15)

        formSizer.Add(wx.StaticText(self.form, -1, _("Notes:")), 0, wx.TOP, 10)

        self.ctrls["notes"] = wx.TextCtrl(
            self.form,
            -1,
            size=dip(wx.Size(-1, 220)),
            style=wx.TE_MULTILINE,
        )
        formSizer.Add(self.ctrls["notes"], 1, wx.EXPAND | wx.TOP, 3)

        self.form.SetSizer(formSizer)

        hsizer.Add(self.form, 1, wx.EXPAND | wx.LEFT, 15)

        topVsizer = wx.BoxSizer(wx.VERTICAL)
        topVsizer.Add(hsizer, 1, wx.EXPAND)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add((1, 1), 1)

        cancelBtn = gutil.createStockButton(self, _("Cancel"))
        hsizer.Add(cancelBtn, 0, wx.LEFT, 10)

        okBtn = gutil.createStockButton(self, "OK")
        hsizer.Add(okBtn, 0, wx.LEFT, 10)

        topVsizer.Add(hsizer, 0, wx.EXPAND | wx.TOP, 10)

        gutil.finishWindow(self, topVsizer, center=True)

        self.charList.Bind(wx.EVT_LISTBOX, self.OnCharSelected)
        self.Bind(wx.EVT_BUTTON, self.OnNew, id=newBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnDelete, id=self.delBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnGenerateName, id=genBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnPrevPhoto, id=self.prevBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnNextPhoto, id=self.nextBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnAddPhoto, id=self.addPhotoBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnRemovePhoto, id=self.removePhotoBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=cancelBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=okBtn.GetId())
        self.photoPanel.Bind(wx.EVT_LEFT_DCLICK, self.OnPhotoDClick)

        for attr, ctrl in self.ctrls.items():
            ctrl.Bind(wx.EVT_TEXT, lambda e, attr=attr: self.OnFieldChange(attr))

        self.fillList()

        sel = 0
        if selectName:
            sel = self.findProfile(selectName)

        self.selectProfile(max(sel, 0))

    def sortProfiles(self):
        self.profiles.sort(key=lambda p: characterprofiles.normalizeName(p.name))

    # return the index in self.profiles of the given character, or -1
    def findProfile(self, name):
        name = characterprofiles.normalizeName(name)

        for i, prof in enumerate(self.profiles):
            if characterprofiles.normalizeName(prof.name) == name:
                return i

        return -1

    def fillList(self):
        self.charList.Set([""] * len(self.profiles))

        for i in range(len(self.profiles)):
            self.updateListItem(i)

    # update list item 'i' to match the profile it shows
    def updateListItem(self, i):
        prof = self.profiles[i]

        self.charList.SetString(i, textutil.upper(prof.name) or _("(unnamed)"))
        self.charList.SetItemDimmed(i, not prof.hasInfo())

    # show profile number 'i', or nothing if it's out of range
    def selectProfile(self, i):
        if 0 <= i < len(self.profiles):
            self.cur = self.profiles[i]
            self.charList.SetSelection(i)
        else:
            self.cur = None

        self.photoIdx = 0
        self.showProfile()

    # fill in the form from self.cur
    def showProfile(self):
        self.updating = True

        for attr, ctrl in self.ctrls.items():
            ctrl.ChangeValue(getattr(self.cur, attr) if self.cur else "")

        self.updating = False

        self.form.Enable(self.cur is not None)
        self.delBtn.Enable(self.cur is not None)
        self.showPhoto()

    def showPhoto(self):
        photos = self.cur.photos if self.cur else []

        self.photoIdx = util.clamp(self.photoIdx, 0, max(0, len(photos) - 1))

        img = None
        if photos:
            img = photoToImage(photos[self.photoIdx])
            self.photoLabel.SetLabel("%d / %d" % (self.photoIdx + 1, len(photos)))
        else:
            self.photoLabel.SetLabel("")

        self.photoPanel.setImage(img)

        self.prevBtn.Enable(self.photoIdx > 0)
        self.nextBtn.Enable(self.photoIdx < (len(photos) - 1))
        self.removePhotoBtn.Enable(bool(photos))

    def curIndex(self):
        for i, prof in enumerate(self.profiles):
            if prof is self.cur:
                return i

        return -1

    def OnCharSelected(self, event):
        i = event.GetSelection()

        if self.profiles[i] is not self.cur:
            self.cur = self.profiles[i]
            self.photoIdx = 0
            self.showProfile()

    def OnFieldChange(self, attr):
        if self.updating or not self.cur:
            return

        setattr(self.cur, attr, self.ctrls[attr].GetValue())
        self.updateListItem(self.curIndex())

    def OnNew(self, event):
        self.profiles.append(characterprofiles.CharacterProfile())
        self.charList.Append("")
        self.updateListItem(len(self.profiles) - 1)
        self.selectProfile(len(self.profiles) - 1)

        self.ctrls["name"].SetFocus()

    def OnDelete(self, event):
        if not self.cur:
            return

        name = textutil.upper(self.cur.name) or _("(unnamed)")

        if self.cur.hasInfo() and (
            wx.MessageBox(
                _("Delete the profile of {}?").format(name),
                _("Confirm"),
                wx.YES_NO | wx.NO_DEFAULT,
                self,
            )
            != wx.YES
        ):
            return

        i = self.curIndex()
        normName = characterprofiles.normalizeName(self.cur.name)

        # characters that are in the script stay in the list, just
        # without a profile
        if normName in self.scriptNames:
            self.profiles[i] = characterprofiles.CharacterProfile(normName)
            self.updateListItem(i)
        else:
            del self.profiles[i]
            self.charList.Delete(i)
            i = min(i, len(self.profiles) - 1)

        self.selectProfile(i)

    def OnGenerateName(self, event):
        if not namesdlg.readNames(self):
            return

        dlg = NameGeneratorDlg(self)

        if dlg.ShowModal() == wx.ID_OK:
            self.ctrls["name"].SetValue(textutil.upper(dlg.name))

        dlg.Destroy()

    def OnPrevPhoto(self, event):
        self.photoIdx -= 1
        self.showPhoto()

    def OnNextPhoto(self, event):
        self.photoIdx += 1
        self.showPhoto()

    def OnAddPhoto(self, event):
        dlg = wx.FileDialog(
            self,
            _("Choose photos"),
            wildcard=_("Images")
            + " (*.jpg;*.jpeg;*.png;*.gif;*.bmp)|*.jpg;*.jpeg;*.png;*.gif;*.bmp|"
            + _("All files")
            + "|*",
            style=wx.FD_OPEN | wx.FD_MULTIPLE | wx.FD_FILE_MUST_EXIST,
        )

        if dlg.ShowModal() == wx.ID_OK:
            failed = []

            for path in dlg.GetPaths():
                data = loadPhoto(path)

                if data:
                    self.cur.photos.append(data)
                    self.photoIdx = len(self.cur.photos) - 1
                else:
                    failed.append(path)

            if failed:
                wx.MessageBox(
                    _("Couldn't read these images:") + "\n\n" + "\n".join(failed),
                    _("Error"),
                    wx.OK,
                    self,
                )

            self.showPhoto()
            self.updateListItem(self.curIndex())

        dlg.Destroy()

    def OnRemovePhoto(self, event):
        if not self.cur.photos:
            return

        if (
            wx.MessageBox(
                _("Remove this photo?"), _("Confirm"), wx.YES_NO | wx.NO_DEFAULT, self
            )
            != wx.YES
        ):
            return

        del self.cur.photos[self.photoIdx]
        self.showPhoto()
        self.updateListItem(self.curIndex())

    def OnPhotoDClick(self, event):
        if self.photoPanel.img:
            dlg = PhotoViewDlg(
                self, self.photoPanel.img, textutil.upper(self.cur.name) or _("Photo")
            )
            dlg.ShowModal()
            dlg.Destroy()

    def OnOK(self, event):
        normalize = characterprofiles.normalizeName

        keep = []
        seen = {}

        for i, prof in enumerate(self.profiles):
            name = normalize(prof.name)

            # empty profiles of script characters are just placeholders,
            # but keep ones the user created with New, even if they only
            # have a name so far
            if not prof.hasInfo() and ((name in self.scriptNames) or not name):
                continue

            if not name:
                self.selectProfile(i)
                wx.MessageBox(
                    _("Every profile needs a name."), _("Error"), wx.OK, self
                )

                return

            if name in seen:
                self.selectProfile(i)
                wx.MessageBox(
                    _("There is more than one profile for {}.").format(name),
                    _("Error"),
                    wx.OK,
                    self,
                )

                return

            seen[name] = None
            prof.name = textutil.upper(prof.name.strip())
            keep.append(prof)

        self.renames = {}

        for prof in keep:
            old = self.origNames.get(id(prof), (None, None))[1]
            new = normalize(prof.name)

            if old and (old != new) and (old in self.scriptNames):
                self.renames[old] = new

        self.charProfiles.profiles = keep
        self.charProfiles.sort()

        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)
