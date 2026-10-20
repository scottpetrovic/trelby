# the main toolbar (MainToolBar), and the controls drawn in it.

from collections import namedtuple

import wx

import trelby.config as config
import trelby.screenplay.scriptformats as scriptformats
import trelby.ui.icons as icons
import trelby.ui.ids as ids
import trelby.keys as keys
import trelby.ui.menus as menus
import trelby.textfmt as textfmt
import trelby.ui.theming as theming


# an item label drawn as an icon (an SVG in trelby/resources) instead of text
BarIcon = namedtuple("BarIcon", "filename")


# toolbar control showing the element types as a group of toggle buttons,
# with the current element's type selected. 'items' is a list of (lt,
# label) tuples, where a label is a string or a BarIcon; clicking one calls
# onSelect(lt). getToolTip(lt) returns the tooltip for an item.
class MyElemTypeBar(wx.Control):
    # a BarIcon's size, in DIPs
    ICON = 16

    def __init__(self, parent, id, getCfgGui, items, onSelect, getToolTip, height):
        wx.Control.__init__(self, parent, id, style=wx.BORDER_NONE)

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        self.getCfgGui = getCfgGui
        self.items = items
        self.onSelect = onSelect
        self.getToolTip = getToolTip

        # line type of the current element, and indexes of the selected
        # and hovered items (-1 = none)
        self.curLt = None
        self.selected = -1
        self.hover = -1

        # if True, the items are greyed out and clicking them does
        # nothing. unlike a disabled window, this still shows tooltips,
        # which can say why.
        self.disabled = False

        self.font = self.GetFont()
        self.boldFont = self.font.Bold()

        # BarIcons' wx.BitmapBundles by (filename, color)
        self.bitmaps = {}

        self.margin = self.FromDIP(2)
        self.height = height
        self.layoutItems()

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDown)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeave)

    # work out where each item goes, and the control's size. every item is
    # as wide as its label in bold, so selecting one doesn't shift the
    # others.
    def layoutItems(self):
        padX = self.FromDIP(10)
        height = self.height

        self.rects = []
        x = self.margin

        for lt, label in self.items:
            if isinstance(label, BarIcon):
                w = self.FromDIP(self.ICON)
            else:
                w = self.GetFullTextExtent(label, self.boldFont)[0]

            w += padX * 2
            self.rects.append(wx.Rect(x, self.margin, w, height - self.margin * 2))
            x += w

        size = wx.Size(x + self.margin, height)
        self.SetMinSize(size)
        self.SetSize(size)

    # replace the items with new (value, label) ones. returns whether they
    # changed, in which case the toolbar holding the bar has to be
    # realized again for its new size.
    def setItems(self, items):
        if items == self.items:
            return False

        self.items = items
        self.layoutItems()

        lt = self.curLt
        self.curLt = None
        self.hover = -1
        self.SetValue(lt)

        return True

    def AcceptsFocus(self):
        return False

    def SetValue(self, lt):
        if lt == self.curLt:
            return

        self.curLt = lt
        self.selected = -1

        for i, (itemLt, label) in enumerate(self.items):
            if itemLt == lt:
                self.selected = i

        self.Refresh(False)

    # whether item i is shown highlighted
    def isSelected(self, i):
        return (i == self.selected) and not self.disabled

    # font to draw item i's label in
    def itemFont(self, i, selected):
        return self.boldFont if selected else self.font

    # the bitmap to draw a BarIcon with, in the given color
    def iconBitmap(self, label, color):
        key = (label.filename, color.GetAsString(wx.C2S_HTML_SYNTAX))

        if key not in self.bitmaps:
            self.bitmaps[key] = icons.svgBitmap(
                label.filename, wx.Size(self.ICON, self.ICON), color=color
            )

        return self.bitmaps[key].GetBitmapFor(self)

    def itemAt(self, pos):
        for i, rect in enumerate(self.rects):
            if rect.Contains(pos):
                return i

        return -1

    def OnLeftDown(self, event):
        i = self.itemAt(event.GetPosition())

        if (i != -1) and not self.disabled:
            self.onSelect(self.items[i][0])

    def OnMotion(self, event):
        i = self.itemAt(event.GetPosition())

        if i != self.hover:
            self.hover = i
            self.SetToolTip(self.getToolTip(self.items[i][0]) if i != -1 else "")
            self.Refresh(False)

    def OnLeave(self, event):
        if self.hover != -1:
            self.hover = -1
            self.Refresh(False)

    def OnPaint(self, event):
        cfgGui = self.getCfgGui()

        dc = wx.AutoBufferedPaintDC(self)
        w, h = self.GetClientSize()

        dc.SetBrush(cfgGui.tabBarBgBrush)
        dc.SetPen(cfgGui.tabBarBgPen)
        dc.DrawRectangle(0, 0, w, h)

        radius = self.FromDIP(4)
        group = wx.Rect(0, 0, w, h).Deflate(self.margin - 1)

        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.SetPen(cfgGui.tabBorderPen)
        dc.DrawRoundedRectangle(group, radius)


        inset = self.FromDIP(2)

        for i, rect in enumerate(self.rects):
            label = self.items[i][1]

            # Deflate works in place, and self.rects is also used for
            # hit testing, so deflate a copy
            fillRect = wx.Rect(rect).Deflate(inset)

            if self.isSelected(i):
                dc.SetBrush(cfgGui.toolbarSelBrush)
                dc.SetPen(cfgGui.toolbarSelPen)
                dc.DrawRoundedRectangle(fillRect, radius - 1)
                color = cfgGui.tabTextColor
                dc.SetFont(self.itemFont(i, True))
            else:
                if (i == self.hover) and not self.disabled:
                    dc.SetBrush(cfgGui.tabNonActiveBgBrush)
                    dc.SetPen(cfgGui.tabNonActiveBgPen)
                    dc.DrawRoundedRectangle(fillRect, radius - 1)

                if not self.disabled:
                    color = cfgGui.tabTextColor
                else:
                    color = wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)

                dc.SetFont(self.itemFont(i, False))

            if isinstance(label, BarIcon):
                bmp = self.iconBitmap(label, color)
                bw, bh = bmp.GetSize()
                dc.DrawBitmap(
                    bmp,
                    rect.x + (rect.width - bw) // 2,
                    rect.y + (rect.height - bh) // 2,
                    True,
                )
            else:
                dc.SetTextForeground(color)
                tw, th = dc.GetTextExtent(label)
                dc.DrawText(
                    label,
                    rect.x + (rect.width - tw) // 2,
                    rect.y + (rect.height - th) // 2,
                )

            # divider between two items that are both unhighlighted
            if (
                (i > 0)
                and not self.isSelected(i - 1)
                and not self.isSelected(i)
                and (self.hover not in (i - 1, i))
            ):
                dc.SetPen(cfgGui.tabBorderPen)
                dy = rect.height // 4
                dc.DrawLine(rect.x, rect.y + dy, rect.x, rect.bottom - dy + 1)


# a vertical line between groups of tools in the toolbar
class MyToolbarDivider(wx.Control):
    def __init__(self, parent, getCfgGui, height):
        wx.Control.__init__(self, parent, -1, style=wx.BORDER_NONE)

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.getCfgGui = getCfgGui

        size = wx.Size(self.FromDIP(13), height)
        self.SetMinSize(size)
        self.SetSize(size)

        self.Bind(wx.EVT_PAINT, self.OnPaint)

    def AcceptsFocus(self):
        return False

    def OnPaint(self, event):
        cfgGui = self.getCfgGui()

        dc = wx.AutoBufferedPaintDC(self)
        w, h = self.GetClientSize()

        dc.SetBrush(cfgGui.tabBarBgBrush)
        dc.SetPen(cfgGui.tabBarBgPen)
        dc.DrawRectangle(0, 0, w, h)

        # halfway between the group borders and the text, so that it
        # stands out in both light and dark themes
        a = cfgGui.tabBorderColor
        b = cfgGui.tabTextColor
        color = wx.Colour(
            (a.Red() + b.Red()) // 2,
            (a.Green() + b.Green()) // 2,
            (a.Blue() + b.Blue()) // 2,
        )

        # a filled rectangle rather than a line, for an exact width
        lw = self.FromDIP(2)
        dy = h // 5
        dc.SetBrush(wx.Brush(color))
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.DrawRectangle((w - lw) // 2, dy, lw, h - dy * 2)


# the toolbar's bold / italic / underline toggles, drawn like the element
# type bar but with any number of items on at once. items are (bit, label)
# tuples, where bit is textfmt.BOLD etc., and each label is drawn in the
# style it stands for. onSelect(bit) is called when one is clicked.
class MyFormatBar(MyElemTypeBar):
    def __init__(self, parent, id, getCfgGui, items, onSelect, getToolTip, height):
        MyElemTypeBar.__init__(
            self, parent, id, getCfgGui, items, onSelect, getToolTip, height
        )

        # bits that are on
        self.style = 0

        self.fonts = {
            textfmt.BOLD: self.boldFont,
            textfmt.ITALIC: self.font.Italic(),
            textfmt.UNDERLINED: self.font.Underlined(),
        }

    def SetValue(self, style):
        if style == self.style:
            return

        self.style = style
        self.Refresh(False)

    # grey the items out or not (see MyElemTypeBar.disabled)
    def setDisabled(self, disabled):
        if disabled == self.disabled:
            return

        self.disabled = disabled
        self.Refresh(False)

        # the tooltip can depend on it
        if self.hover != -1:
            self.SetToolTip(self.getToolTip(self.items[self.hover][0]))

    def isSelected(self, i):
        return not self.disabled and bool(self.style & self.items[i][0])

    def itemFont(self, i, selected):
        return self.fonts.get(self.items[i][0], self.font)


# the main window's toolbar: the file, undo, find and view buttons, the
# element type, bold / italic / underline and centering controls, and the
# outline button. tb is the wx.ToolBar and gd the GlobalData. the buttons
# have the same ids as the menu items, so the menu's bindings run them;
# the controls call onAction(name) with the name of the menus.Action to
# run.
class MainToolBar:
    # the align bar's item for centering, a bit that's not one of the
    # textfmt ones
    ALIGN_CENTER = 8

    def __init__(self, tb, gd, onAction):
        self.tb = tb
        self.gd = gd
        self.onAction = onAction

        self.elemTypeBar = None
        self.formatBar = None
        self.alignBar = None
        self.dividers = []

    def getCfgGui(self):
        return self.gd.cfgGui

    def getControls(self):
        return [self.elemTypeBar, self.formatBar, self.alignBar] + self.dividers

    # (re)create the toolbar's tools, with icons at the size set in the
    # global config.
    def fill(self):
        tb = self.tb
        size = wx.Size(self.gd.cfgGl.toolbarIconSize, self.gd.cfgGl.toolbarIconSize)

        # empty space around each icon. wxMSW ignores the toolbar's own
        # margin / packing settings, so it's part of the icons instead.
        pad = 5
        paddedSize = wx.Size(size.width + pad * 2, size.height + pad * 2)

        tb.ClearTools()
        tb.SetToolBitmapSize(paddedSize)

        # ClearTools normally destroys controls along with their tools, but
        # not always, so destroy any that are left. a destroyed wx object
        # is false.
        for c in self.getControls():
            if c:
                c.Destroy()

        self.dividers = []

        # height of the controls in the toolbar
        height = max(
            tb.FromDIP(paddedSize.height), tb.GetCharHeight() + tb.FromDIP(12)
        )

        # a vertical line between groups of tools. the toolbar's own
        # separators don't show against its background color.
        def addDivider():
            d = MyToolbarDivider(tb, self.getCfgGui, height)
            tb.AddControl(d)
            self.dividers.append(d)

        # disabled tools' icons, faded most of the way into the background.
        # wx's own greyed versions barely differ from the normal ones, and
        # on a dark appearance come out lighter.
        disabledColor = theming.blendColors(
            icons.svgIconColor(), self.gd.cfgGui.tabBarBgColor, 0.65
        )

        def addTB(id, iconFilename, toolTip, kind=wx.ITEM_NORMAL):
            bitmap = icons.svgBitmap(iconFilename, size, pad)
            disabledBitmap = icons.svgBitmap(iconFilename, size, pad, disabledColor)
            tool = tb.AddTool(
                id, "", bitmap, disabledBitmap, kind=kind, shortHelp=toolTip
            )

            # the status bar shows this while the tool is hovered
            tool.SetLongHelp(toolTip)

        addTB(ids.ID_EDIT_UNDO, "undo.svg", _("Undo"))
        addTB(ids.ID_EDIT_REDO, "redo.svg", _("Redo"))

        addDivider()

        addTB(ids.ID_EDIT_FIND, "find.svg", _("Find / Replace"))
        addTB(ids.ID_TOOLBAR_VIEWS, "view.svg", _("View mode"))

        addDivider()

        # {line type: name of the menus.Action that changes to it}
        elemActions = {
            lt: "ElemTo" + cmdName[len("ChangeTo") :]
            for lt, id, label, mnemonic, cmdName in menus.elemTypes()
        }

        self.elemTypeBar = MyElemTypeBar(
            tb,
            -1,
            self.getCfgGui,
            self.elemTypeItems(None),
            lambda lt: self.onAction(elemActions[lt]),
            self.getElemTypeToolTip,
            height,
        )
        tb.AddControl(self.elemTypeBar)

        # bold / italic / underline, which go on top of any element type
        addDivider()

        formatActions = {bit: action for bit, *rest, action in self.getFormatTypes()}

        self.formatBar = MyFormatBar(
            tb,
            -1,
            self.getCfgGui,
            [(bit, label) for bit, label, name, key, action in self.getFormatTypes()],
            lambda bit: self.onAction(formatActions[bit]),
            self.getFormatToolTip,
            height,
        )
        tb.AddControl(self.formatBar)

        # centering, which applies to whole action elements
        addDivider()
        self.alignBar = MyFormatBar(
            tb,
            -1,
            self.getCfgGui,
            [(self.ALIGN_CENTER, BarIcon("aligncenter.svg"))],
            lambda bit: self.onAction("ToggleCentered"),
            lambda bit: self.getAlignToolTip(),
            height,
        )
        tb.AddControl(self.alignBar)

        # at the far right, next to where the side panel appears: the beat
        # board, which replaces the script and the side panel, and the side
        # panel with the outline and the notes
        tb.AddStretchableSpace()

        # its icon is changed by setBoardShown
        addTB(ids.ID_VIEW_BEAT_BOARD, "beatboard.svg", "")
        self.iconSize = size
        self.iconPad = pad
        self.boardIconShown = None
        addTB(
            ids.ID_VIEW_SIDE_PANEL,
            "sidepanel.svg",
            _("Outline and notes"),
            wx.ITEM_CHECK,
        )

        tb.SetBackgroundColour(self.gd.cfgGui.tabBarBgColor)
        tb.Realize()

        tb.ToggleTool(ids.ID_VIEW_SIDE_PANEL, self.gd.showSidePanel)
        self.setBoardShown(self.gd.showBeatBoard)

    # redraw the toolbar in the current theme's colors
    def refreshColors(self):
        for c in self.getControls():
            c.Refresh(False)

        self.tb.SetBackgroundColour(self.gd.cfgGui.tabBarBgColor)
        self.tb.Refresh()

    # the format toggles: textfmt bit, label, name, shortcut, and the
    # menus.Action that toggles it
    def getFormatTypes(self):
        return [
            (textfmt.BOLD, "B", _("Bold"), "CTRL+B", "ToggleBold"),
            (textfmt.ITALIC, "I", _("Italic"), "CTRL+I", "ToggleItalic"),
            (textfmt.UNDERLINED, "U", _("Underline"), "CTRL+U", "ToggleUnderline"),
        ]

    def getFormatToolTip(self, bit):
        for itemBit, label, name, key, action in self.getFormatTypes():
            if itemBit == bit:
                return "%s (%s)" % (name, key)

    def getAlignToolTip(self):
        if self.alignBar.disabled:
            return _(
                "Centering is only for Action elements. Put the cursor in"
                " an action, or select one, to center it."
            )

        return _(
            "Center this action on the page, e.g. THE END or a title card."
            " Only Action elements can be centered."
        )

    # the element type bar's items for a script with config cfg, whose
    # format names the types and may not use all of them (see
    # scriptformats), or with None, for a screenplay
    def elemTypeItems(self, cfg):
        if cfg is None:
            cfg = config.Config()

        used = scriptformats.usedTypes(cfg)

        return [
            (lt, scriptformats.typeLabel(cfg, lt))
            for lt, id, label, mnemonic, cmd in menus.elemTypes()
            if lt in used
        ]

    # show the element types of the script with config cfg
    def setElemTypes(self, cfg):
        if self.elemTypeBar.setItems(self.elemTypeItems(cfg)):
            self.tb.Realize()

    def getElemTypeToolTip(self, lt):
        for itemLt, id, label, mnemonic, cmdName in menus.elemTypes():
            if itemLt == lt:
                break

        label = dict(self.elemTypeBar.items).get(lt, label)
        s = _("Change element to %s") % label

        for cmd in self.gd.cfgGl.commands:
            if (cmd.name == cmdName) and cmd.keys:
                s += " (%s)" % keys.Key.fromInt(cmd.keys[0]).toStr()

        return s

    # show the current element's type, which of bold / italic / underline
    # are on at the cursor or for the selection, and whether the action
    # there is centered (None if centering doesn't apply there)
    def setState(self, lt, style, centered):
        self.elemTypeBar.SetValue(lt)
        self.formatBar.SetValue(style)
        self.alignBar.setDisabled((centered is None) or self.gd.showBeatBoard)
        self.alignBar.SetValue(self.ALIGN_CENTER if centered else 0)

    # while the beat board is shown, the controls for editing the script
    # are greyed out (the buttons by menus.onUpdateUI)
    #
    # the beat board button shows what it switches to: the board's cards
    # while the script is shown, and a script page while the board is
    def setBoardShown(self, shown):
        if shown != self.boardIconShown:
            self.boardIconShown = shown

            if shown:
                icon, tip = "script.svg", _("Show the script")
            else:
                icon, tip = "beatboard.svg", _("Show the beat board")

            tip += " (%s)" % menus.BOARD_TOGGLE_KEY.replace("-", "+").title()

            tb = self.tb
            tb.SetToolNormalBitmap(
                ids.ID_VIEW_BEAT_BOARD,
                icons.svgBitmap(icon, self.iconSize, self.iconPad),
            )
            tb.SetToolShortHelp(ids.ID_VIEW_BEAT_BOARD, tip)
            tb.SetToolLongHelp(ids.ID_VIEW_BEAT_BOARD, tip)

        for bar in (self.elemTypeBar, self.formatBar, self.alignBar):
            if bar.disabled != shown:
                bar.disabled = shown
                bar.Refresh(False)

    def enableUndo(self, canUndo, canRedo):
        self.tb.EnableTool(ids.ID_EDIT_UNDO, canUndo)
        self.tb.EnableTool(ids.ID_EDIT_REDO, canRedo)
