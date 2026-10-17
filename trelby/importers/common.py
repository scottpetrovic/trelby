# what the importers share: their result and error types, and helpers for
# building the lines and parsing XML.

from lxml import etree

import trelby.screenplay as screenplay
import trelby.screenplay.notes as notes
import trelby.textutil as textutil
from trelby.screenplay.line import Line


# a successful import: the script's lines (at least one), and title pages
# to replace the script's with, or None to leave them as they are.
#
# the importers add the formats' notes as note elements (screenplay.NOTE)
# after what they're about, which become notes on the paragraph before each
# here (see screenplay/notes.py).
class ImportResult:
    def __init__(self, lines, titlePages=None, revisions=None):
        notes.absorbNoteElements(lines)

        self.lines = lines
        self.titlePages = titlePages

        # the script's revision settings (screenplay.revisions.Revisions),
        # for formats that have them, or None
        self.revisions = revisions


# an import that failed. message is for the user.
class ImportFailed(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def checkNotEmpty(data):
    if len(data) == 0:
        raise ImportFailed(_("File is empty."))


# raise ImportFailed if lines is empty, with the given message or the
# usual one
def checkLines(lines, message=None):
    if not lines:
        raise ImportFailed(message or _("The file contains no importable lines"))


# parse data (str or bytes) as XML, or with an lxml parser like
# etree.HTMLParser(), and return the root element. a str is parsed as
# UTF-8, so that it can have an XML declaration.
def parseXML(data, parser=None):
    if isinstance(data, str):
        data = data.encode("UTF-8")

    try:
        return etree.XML(data, parser)
    except etree.XMLSyntaxError as e:
        raise ImportFailed(_("Error parsing file: {}").format(e))


# append an element of type lt, with the lines of text in items, to lines.
# an empty last item (the element ending in a newline) is dropped. fmt is
# the format string for "\n".join(items), or None.
# revs is likewise its revision marks (see screenplay/revisions.py).
def addElem(lines, lt, items, fmt=None, revs=None):
    if not items[-1] and (len(items) > 1):
        items = items[:-1]

    # fmt has a character for each one of the joined text, newlines
    # included, so each line's part starts one past the previous line's
    # end
    pos = 0

    for i, s in enumerate(items):
        lb = screenplay.LB_LAST if (i == len(items) - 1) else screenplay.LB_FORCED
        lineFmt = fmt and fmt[pos : pos + len(s)]
        lineRevs = revs and revs[pos : pos + len(s)]
        pos += len(s) + 1

        lines.append(
            Line(lb, lt, textutil.cleanInput(s), fmt=lineFmt, revs=lineRevs)
        )
