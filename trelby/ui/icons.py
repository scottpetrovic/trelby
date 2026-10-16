import re

import wx

import trelby.misc as misc
import trelby.ui.theming as theming

# bitmaps and SVG icons from trelby/resources


# load one of the black SVG icons in trelby/resources as a bitmap bundle of
# the given size (in DIPs), recolored to show up on a dark appearance. a
# non-zero padding (in DIPs) adds that much empty space on every side of the
# icon, by growing the SVG's viewBox, so the bundle is size + 2 * padding.
# a color (wx.Colour) draws the icon in that color instead.
#
# the recoloring is a plain text replace, so it only reaches the parts of
# an icon written as "fill:#000000" in a style attribute, which is how all
# the bundled icons do it; any other way of writing black stays black.
def svgBitmap(iconFilename, size, padding=0, color=None):
    filepath = misc.getFullPath("trelby/resources/%s" % iconFilename)

    with open(filepath, "r") as svg_file:
        svg_content = svg_file.read()

    if color is None:
        color = svgIconColor()

    svg_content = svg_content.replace(
        "fill:#000000", "fill:%s" % color.GetAsString(wx.C2S_HTML_SYNTAX)
    )

    if padding:
        svg_content = re.sub(
            r'viewBox="([^"]*)"',
            lambda m: 'viewBox="%s"' % padViewBox(m.group(1), size, padding),
            svg_content,
            count=1,
        )
        size = wx.Size(size.width + padding * 2, size.height + padding * 2)

    return wx.BitmapBundle.FromSVG(svg_content.encode(), size)


# return bitmap created from the given file. argument is as for
# getFullPath.
def getBitmap(filename):
    return wx.Bitmap(misc.getFullPath(filename))


# the color svgBitmap draws icons in by default
def svgIconColor():
    if theming.isDarkAppearance():
        return wx.Colour(0xCC, 0xCC, 0xCC)

    return wx.Colour(0, 0, 0)


# return the SVG viewBox 'box' grown on every side by 'padding' DIPs, for an
# icon drawn at 'size' DIPs
def padViewBox(box, size, padding):
    x, y, w, h = [float(v) for v in box.replace(",", " ").split()]
    padX = w * padding / size.width
    padY = h * padding / size.height

    return "%g %g %g %g" % (x - padX, y - padY, w + padX * 2, h + padY * 2)
