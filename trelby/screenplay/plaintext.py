# script lines as plain text and back, for copying to and pasting from the
# system clipboard, which only has the text.

import os

import trelby.config as config
import trelby.screenplay.export as export
import trelby.textutil as textutil
from trelby.screenplay.line import Line
from trelby.screenplay.constants import ACTION, LB_LAST
from trelby.screenplay.model import Screenplay


# return the given lines (from a ClipData) as text, with the platform's
# line breaks. formatted text is laid out like the plain text export;
# otherwise each element is one line, upper-cased if its type is exported
# that way. cfgGl is the global config.
def linesToText(lines, cfgGl, formatted):
    sp = Screenplay(cfgGl)
    sp.lines = lines

    if formatted:
        # without paginating, generateText doesn't process all the text
        sp.paginate()

        return export.generateText(sp, False)

    parts = []

    for ln in lines:
        txt = ln.text

        if sp.cfg.getType(ln.lt).export.isCaps:
            txt = textutil.upper(txt)

        parts.append(txt + config.lb2str(ln.lb))

    return "".join(parts).replace("\n", os.linesep)


# return text from the clipboard as a list of action lines, one per
# non-empty line of text, with the characters that can't be typed removed
def textToLines(s):
    s = textutil.removeInvalidChars(
        textutil.toInputStr(textutil.fixNL(textutil.cleanInput(s)))
    )

    return [Line(LB_LAST, ACTION, t) for t in s.split("\n") if t]
