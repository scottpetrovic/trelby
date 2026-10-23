# the breakdown report: a breakdown sheet per scene, listing what it needs
# by category, and a list of every element with the scenes it's in (see
# screenplay/breakdown.py).

import trelby.pdf.pml as pml
import trelby.reports.textreport as textreport
import trelby.screenplay.breakdown as breakdown

# how far the lines under a heading are indented
INDENT = "     "


class BreakdownReport(textreport.TextReport):
    options = [
        ("sheets", lambda: _("Scene breakdowns")),
        ("elements", lambda: _("Element list")),
        ("speakers", lambda: _("Speaking characters as cast")),
    ]

    def format(self, tf) -> None:
        sp = self.sp
        speakers = self.opts["speakers"]

        if self.opts["sheets"]:
            for sb in sp.getBreakdown(speakers):
                self.formatScene(tf, sb)

        if self.opts["elements"]:
            elements = sp.getElementList(speakers)

            if elements:
                self.formatElements(tf, sp, elements)

    def formatScene(self, tf, sb):
        tf.addSpace(5.0)

        heading = sb.heading or _("(BEFORE THE FIRST SCENE)")
        tf.addText("%-4s %s" % (sb.number, heading), style=pml.BOLD)

        tf.addSpace(1.0)

        info = _("Page {}, length {}").format(sb.page, breakdown.eighthsText(sb.eighths))

        if sb.intExt:
            info += ", " + sb.intExt

        if sb.time:
            info += ", " + sb.time

        tf.addText(INDENT + info)

        if not sb.elements:
            tf.addText(INDENT + _("Nothing tagged."))

            return

        tf.addSpace(1.5)

        for c in breakdown.CATEGORIES:
            names = sb.names(c.key)

            if names:
                tf.addWrappedText(
                    "%s%s: %s" % (INDENT, c.label(), ", ".join(names)),
                    INDENT + "  ",
                )

    def formatElements(self, tf, sp, elements):
        # scene numbers by the scene's first line; the part before the
        # first heading has none
        numbers = {sb.start: sb.number or "-" for sb in sp.getBreakdown(False)}

        tf.addSpace(10.0)
        tf.addText(_("ELEMENTS"), fs=self.fontSize + 2, style=pml.BOLD)

        current = None

        for e in elements:
            if e.category != current:
                current = e.category
                tf.addSpace(4.0)
                tf.addText(breakdown.category(current).label(), style=pml.BOLD)

            scenes = ", ".join(numbers.get(s, "?") for s in e.scenes)
            tf.addWrappedText(
                "%s%s (%s)" % (INDENT, e.name, scenes), INDENT + "  "
            )
