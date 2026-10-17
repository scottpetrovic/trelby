# the parts of the config that need wx: the application theme, and
# ConfigGui, the global config's fonts, colors, pens and brushes as wx
# objects.

import wx

import trelby.config as config
import trelby.ui.gutil as gutil
import trelby.screenplay as screenplay
import trelby.ui.themes as themes
import trelby.ui.theming as theming

# key = line type, value = the name of its text color in a theme
_lt2themeElem = {
    screenplay.SCENE: "scene",
    screenplay.ACTION: "action",
    screenplay.CHARACTER: "character",
    screenplay.DIALOGUE: "dialogue",
    screenplay.PAREN: "parenthetical",
    screenplay.TRANSITION: "transition",
    screenplay.SHOT: "shot",
    screenplay.ACTBREAK: "actBreak",
    screenplay.NOTE: "noteText",
}


# make the application use the given theme setting. the colors we draw
# ourselves are picked up by the next ConfigGui created.
def applyAppearance(name):
    theme = config.findTheme(name)

    if theme is None:
        a = wx.App.Appearance.System
    elif theme.dark:
        a = wx.App.Appearance.Dark
    else:
        a = wx.App.Appearance.Light

    wx.GetApp().SetAppearance(a)


# the themes.Theme for the given theme setting. must be called after
# applyAppearance.
def getTheme(name):
    theme = config.findTheme(name)

    if theme is None:
        return themes.DARK if theming.isDarkAppearance() else themes.LIGHT

    return theme


# information about one screen font
class FontInfo:
    def __init__(self):
        self.font = None

        # font width and height
        self.fx = 1
        self.fy = 1


# config stuff that are wxwindows objects, so can't be in normal
# ConfigGlobal (deepcopy dies)
class ConfigGui:

    # constants
    constantsInited = False
    bluePen = None
    redColor = None
    blackColor = None

    # zoom is the screen zoom level in percent; it scales the fonts and
    # the draft mode line spacing.
    def __init__(self, cfgGl, zoom=100):

        if not ConfigGui.constantsInited:
            ConfigGui.bluePen = wx.Pen(wx.Colour(0, 0, 255))
            ConfigGui.redColor = wx.Colour(255, 0, 0)
            ConfigGui.blackColor = wx.Colour(0, 0, 0)

            ConfigGui.constantsInited = True

        theme = getTheme(cfgGl.theme)

        # the theme setting's themes.Theme, None for the system default, to
        # tell when the theme needs applying again (see applyGlobalCfg)
        self.themeChoice = config.findTheme(cfgGl.theme)

        # the theme's colors, e.g. "textBg" -> self.textBgColor
        for name in themes.COLORS:
            setattr(self, name + "Color", wx.Colour(*theme.colors[name]))

        # key = line type, value = wx.Colour
        self._lt2textColor = {
            lt: wx.Colour(*theme.elementColor(elem))
            for lt, elem in _lt2themeElem.items()
        }

        self.textPen = wx.Pen(self.textColor)
        self.spellErrorPen = wx.Pen(wx.Colour(*theme.spellErrorColor()))
        self.textHdrPen = wx.Pen(self.textHdrColor)

        self.workspaceBrush = wx.Brush(self.workspaceColor)
        self.workspacePen = wx.Pen(self.workspaceColor)

        self.textBgBrush = wx.Brush(self.textBgColor)
        self.textBgPen = wx.Pen(self.textBgColor)

        self.pageBorderPen = wx.Pen(self.pageBorderColor)
        self.pageShadowPen = wx.Pen(self.pageShadowColor)

        self.selectedBrush = wx.Brush(self.selectedColor)
        self.selectedPen = wx.Pen(self.selectedColor)

        self.cursorBrush = wx.Brush(self.cursorColor)
        self.cursorPen = wx.Pen(self.cursorColor)

        self.noteBrush = wx.Brush(self.noteColor)
        self.notePen = wx.Pen(self.noteColor)

        # the theme's accent color, for the selected item in lists and
        # toolbars we draw ourselves: the system's highlight color, unless
        # the theme has its own
        if "accent" in theme.colors:
            self.accentColor = wx.Colour(*theme.colors["accent"])
            self.accentTextColor = wx.Colour(*theme.colors["accentText"])
        else:
            self.accentColor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
            self.accentTextColor = wx.SystemSettings.GetColour(
                wx.SYS_COLOUR_HIGHLIGHTTEXT
            )
        self.accentBrush = wx.Brush(self.accentColor)
        self.accentPen = wx.Pen(self.accentColor)

        # the selected item in the toolbar's controls: the toolbar's
        # background tinted with the accent color, under the normal text
        self.toolbarSelColor = theming.blendColors(
            self.tabBarBgColor, self.accentColor, theming.ACCENT_TINT
        )
        self.toolbarSelBrush = wx.Brush(self.toolbarSelColor)
        self.toolbarSelPen = wx.Pen(self.toolbarSelColor)

        self.autoCompBrush = wx.Brush(self.autoCompBgColor)

        # border and scroll bar, a third of the way from the background to
        # the text
        fg, bg = self.autoCompFgColor, self.autoCompBgColor
        self.autoCompBorderColor = wx.Colour(
            *[(2 * b + f) // 3 for f, b in zip(fg.Get(False), bg.Get(False))]
        )
        self.autoCompBorderPen = wx.Pen(self.autoCompBorderColor)
        self.autoCompBorderBrush = wx.Brush(self.autoCompBorderColor)

        # the selected item: the accent color blended into the background,
        # like the current scene in the outline, so the text stays as is
        ac = self.accentColor
        self.autoCompSelColor = wx.Colour(
            *[int(b * 0.8 + a * 0.2) for a, b in zip(ac.Get(False), bg.Get(False))]
        )
        self.autoCompSelBrush = wx.Brush(self.autoCompSelColor)
        self.autoCompSelPen = wx.Pen(self.autoCompSelColor)

        self.pagebreakPen = wx.Pen(self.pagebreakColor)
        self.pagebreakNoAdjustPen = wx.Pen(self.pagebreakNoAdjustColor, style=wx.DOT)

        self.tabTextPen = wx.Pen(self.tabTextColor)
        self.tabBorderPen = wx.Pen(self.tabBorderColor)

        self.tabBarBgBrush = wx.Brush(self.tabBarBgColor)
        self.tabBarBgPen = wx.Pen(self.tabBarBgColor)

        self.tabNonActiveBgBrush = wx.Brush(self.tabNonActiveBgColor)
        self.tabNonActiveBgPen = wx.Pen(self.tabNonActiveBgColor)

        # push buttons in dialogs: like a non-active tab in dark themes;
        # light themes' non-active tabs are too dark for that, so halfway
        # there from the background
        self.buttonBgColor = theming.blendColors(
            self.tabBarBgColor, self.tabNonActiveBgColor, 1.0 if theme.dark else 0.5
        )

        # a 4-item list of FontInfo objects, indexed by the two lowest
        # bits of pml.TextOp.flags.
        self.fonts = []

        for fname in ["fontNormal", "fontBold", "fontItalic", "fontBoldItalic"]:
            fi = FontInfo()

            s = getattr(cfgGl, fname)

            # evil users can set the font name to empty by modifying the
            # config file, and some wxWidgets ports crash hard when trying
            # to create a font from an empty string, so we must guard
            # against that.
            if s:
                nfi = wx.NativeFontInfo()
                nfi.FromString(s)

                try:
                    fi.font = wx.Font(nfi)

                    # likewise, evil users can set the font name to "z" or
                    # something equally silly, resulting in an
                    # invalid/non-existent font. on wxGTK2 and wxMSW we can
                    # detect this by checking the point size of the font.
                    if fi.font.GetPointSize() == 0:
                        fi.font = None
                except wx._core.wxAssertionError:
                    # Some platforms (mac) will assert internally if point size
                    # is 0, preventing us from even trying to check, so just
                    # catch that too.
                    fi.font = None

            # if either of the above failures happened, create a dummy
            # font and use it. this sucks but is preferable to crashing or
            # displaying an empty screen.
            if not fi.font:
                fi.font = wx.Font(
                    10,
                    wx.FONTFAMILY_MODERN,
                    wx.FONTSTYLE_NORMAL,
                    wx.FONTWEIGHT_NORMAL,
                    encoding=wx.FONTENCODING_ISO8859_1,
                )
                setattr(cfgGl, fname, fi.font.GetNativeFontInfo().ToString())

            if zoom != 100:
                fi.font = fi.font.Scaled(zoom / 100.0)

            fx, fy = gutil.getTextExtent(fi.font, "O")

            fi.fx = max(1, fx)
            fi.fy = max(1, fy)

            self.fonts.append(fi)

        # vertical distance between rows in draft mode, in pixels
        self.fontYdelta = max(1, round(cfgGl.fontYdelta * zoom / 100.0))

    # TextType -> FontInfo
    def tt2fi(self, tt):
        return self.fonts[tt.isBold | (tt.isItalic << 1)]

    # line type -> wx.Colour
    def lt2textColor(self, lt):
        return self._lt2textColor[lt]
