# RTF export.

import trelby.config as config
import trelby.error as error
import trelby.textfmt as textfmt
import trelby.util as util
from trelby.screenplay.constants import (
    LB_FORCED,
    LB_LAST,
    LB_NONE,
    LB_SPACE,
)


# generate RTF and return it as a string.
def generateRTF(sp):
    ls = sp.lines
    s = util.String()

    s += r"{\rtf1\ansi\deff0{\fonttbl{\f0\fmodern Courier;}}" + "\n"

    s += "{\\stylesheet\n"

    mt = util.mm2twips
    fs = sp.cfg.fontSize

    # since some of our units (beforeSpacing, indent, width) are
    # easier to handle if we assume normal font size, this is a scale
    # factor from actual font size to normal font size
    sf = fs / 12.0

    for ti in config.getTIs():
        t = sp.cfg.getType(ti.lt)
        tt = t.export

        # font size is expressed as font size * 2 in RTF
        tmp = " \\fs%d" % (fs * 2)

        if tt.isCaps:
            tmp += r" \caps"

        if tt.isBold:
            tmp += r" \b"

        if tt.isItalic:
            tmp += r" \i"

        if tt.isUnderlined:
            tmp += r" \ul"

        # some hairy conversions going on here...
        #
        # RTF measures in twips (1/20 pt). indent and width are in
        # characters, and a 12pt Courier character is 7.2pt = 144
        # twips wide; the right indent is what's left of the paper
        # after the margins and indent + width. beforeSpacing is in
        # tenths of a 12pt (240 twips) line, so 24 twips each.
        tmp += r" \li%d\ri%d" % (
            sf * t.indent * 144,
            mt(sp.cfg.paperWidth)
            - (
                mt(sp.cfg.marginLeft + sp.cfg.marginRight)
                + (t.indent + t.width) * 144 * sf
            ),
        )

        tmp += r" \sb%d" % (sf * t.beforeSpacing * 24)

        s += "{\\s%d%s %s}\n" % (ti.lt, tmp, ti.name)

    s += "}\n"

    s += r"\paperw%d\paperh%d\margt%d\margr%d\margb%d\margl%d" % (
        mt(sp.cfg.paperWidth),
        mt(sp.cfg.paperHeight),
        mt(sp.cfg.marginTop),
        mt(sp.cfg.marginRight),
        mt(sp.cfg.marginBottom),
        mt(sp.cfg.marginLeft),
    )
    s += "\n"

    s += sp.titles.generateRTF()

    length = len(ls)
    i = 0

    while i < length:
        lt = ls[i].lt
        text = ""

        # centered actions are only centered paragraphs, not a style
        align = r"\qc " if sp.hasCenteredFlag(i) else ""

        while 1:
            ln = ls[i]
            i += 1

            lb = ln.lb

            # bold / italic / underlined runs go in groups of their own
            for a, b, style in textfmt.runs(ln.fmt, len(ln.text)):
                part = util.escapeRTF(ln.text[a:b])

                if style:
                    codes = "".join(
                        code
                        for bit, code in (
                            (textfmt.BOLD, r"\b"),
                            (textfmt.ITALIC, r"\i"),
                            (textfmt.UNDERLINED, r"\ul"),
                        )
                        if style & bit
                    )
                    part = "{%s %s}" % (codes, part)

                text += part

            if lb in (LB_SPACE, LB_NONE):
                text += config.lb2str(lb)
            elif lb == LB_FORCED:
                text += r"\line "
            elif lb == LB_LAST:
                break
            else:
                raise error.MiscError(
                    _("Unknown line break style {} in generateRTF").format(lb)
                )

        s += (r"{\pard \s%d " % lt) + align + text + "}{\\par}\n"

    s += "}"

    return str(s)
