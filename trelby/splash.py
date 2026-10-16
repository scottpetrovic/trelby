# -*- coding: utf-8 -*-

import random

import wx

import trelby.misc as misc
import trelby.util as util


class Quote:
    def __init__(self, source, lines):
        # unicode string
        self.source = source

        # list of unicode strings
        self.lines = lines


class SplashWindow(wx.Frame):
    inited = False

    # Quote objects
    quotes = []

    def __init__(self, parent, delay):
        wx.Frame.__init__(
            self, parent, -1, _("Splash"), style=wx.FRAME_FLOAT_ON_PARENT | wx.NO_BORDER
        )

        if not SplashWindow.inited:
            SplashWindow.inited = True
            wx.Image.AddHandler(wx.JPEGHandler())

            self.loadQuotes(parent)

        self.pickRandomQuote()

        self.pic = misc.getBitmap("trelby/resources/logo.jpg")

        if self.pic.IsOk():
            w, h = (self.pic.GetWidth(), self.pic.GetHeight())
        else:
            w, h = (500, 400)

        self.w, self.h = w, h

        util.setWH(self, w, h)
        self.CenterOnScreen()

        # dark slate, matching the wordmark in logo.jpg
        self.textColor = wx.Colour(52, 66, 82)

        self.font = util.createPixelFont(14, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        self.versionFont = util.createPixelFont(
            19, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD
        )

        self.quoteFont = util.createPixelFont(
            16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL
        )

        self.sourceFont = util.createPixelFont(
            15, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL
        )

        if delay != -1:
            self.timer = wx.Timer(self)
            wx.Timer()
            self.timer.Start(delay, True)

        self.Bind(wx.EVT_LEFT_DOWN, self.OnClick)

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)

    def OnClick(self, event):
        self.Close()

    def OnPaint(self, event):
        dc = wx.PaintDC(self)

        dc.SetTextForeground(self.textColor)

        if self.pic.IsOk():
            dc.DrawBitmap(self.pic, 0, 0, False)

        # version and website in the empty top-right corner
        dc.SetFont(self.versionFont)
        util.drawText(dc, "Version %s" % (misc.version), self.w - 12, 10, util.ALIGN_RIGHT)

        dc.SetFont(self.font)
        util.drawText(dc, "http://www.trelby.org/", self.w - 12, 34, util.ALIGN_RIGHT)

        # quote centered in the band below the wordmark, bottom-aligned
        if self.quote:
            cx = self.w // 2

            dc.SetFont(self.sourceFont)
            util.drawText(dc, "— " + self.quote.source, cx, self.h - 28, util.ALIGN_CENTER)

            dc.SetFont(self.quoteFont)

            count = len(self.quote.lines)
            for i, line in enumerate(self.quote.lines):
                y = self.h - 52 - (count - i - 1) * 18

                if i == 0:
                    line = "“" + line

                if i == (count - 1):
                    line = line + "”"

                util.drawText(dc, line, cx, y, util.ALIGN_CENTER)

    def OnTimer(self, event):
        self.timer.Stop()
        self.Close()

    def OnCloseWindow(self, event):
        self.Destroy()
        self.Refresh()

    def pickRandomQuote(self):
        if not SplashWindow.quotes:
            self.quote = None
        else:
            self.quote = random.choice(SplashWindow.quotes)

    @staticmethod
    def loadQuotes(parent):
        try:
            data = util.loadFile(
                misc.getFullPath("trelby/resources/quotes.txt"), parent
            )
            if data is None:
                return

            # data = data.decode("utf-8")
            lines = data.splitlines()

            quotes = []

            # lines saved for current quote being processed
            tmp = []

            for i, line in enumerate(lines):
                if line.startswith("#") or not line.strip():
                    continue

                if line.startswith("  "):
                    if not tmp:
                        raise Exception(
                            _("No lines defined for quote at line {}").format(i + 1)
                        )

                    if len(tmp) > 3:
                        raise Exception(
                            _("Too many lines defined for quote at line {}").format(
                                i + 1
                            )
                        )

                    quotes.append(Quote(line.strip(), tmp))
                    tmp = []
                else:
                    tmp.append(line.strip())

            if tmp:
                raise Exception(_("Last quote does not have source"))

            SplashWindow.quotes = quotes

        except Exception as e:
            wx.MessageBox(
                _("Error loading quotes: {}").format(str(e)), _("Error"), wx.OK, parent
            )
