# inline text formatting: each character of a line's text can be bold,
# italic and/or underlined, on top of whatever style the element type
# itself has. a line keeps this in a "format string" (Line.fmt) with one
# character per character of text, "0" - "7", whose value is a combination
# of the BOLD / ITALIC / UNDERLINED bits below. a line with no formatting
# has None instead, and most code only needs to care about that case.
#
# format strings can always be sliced and joined just like the text they
# go with. code that changes a line's text without updating the format
# string leaves them out of step; fit() handles that by padding or
# truncating, so the worst that happens is formatting on the wrong
# characters.

import re

BOLD = 1
ITALIC = 2
UNDERLINED = 4

# bits of the style values in a format string
ALL = BOLD | ITALIC | UNDERLINED


# return the format string character for the given style value
def char(style):
    return chr(48 + style)


# return the style value at index i of fmt (0 if out of range)
def styleAt(fmt, i):
    if fmt and (0 <= i < len(fmt)):
        return ord(fmt[i]) - 48

    return 0


# return fmt as a format string exactly n characters long, padding it with
# plain characters or truncating it as needed. None counts as all plain.
def fit(fmt, n):
    if not fmt:
        return "0" * n

    if len(fmt) == n:
        return fmt

    return (fmt + "0" * n)[:n]


# return fmt, or None if it has no formatting in it
def compact(fmt):
    if fmt and fmt.strip("0"):
        return fmt

    return None


# return a list of (start, end, style) tuples (end exclusive) for the
# runs of characters with the same style in a text n characters long
# formatted with fmt. covers the whole text; empty for n == 0.
def runs(fmt, n):
    if n == 0:
        return []

    if not fmt:
        return [(0, n, 0)]

    fmt = fit(fmt, n)
    ret = []
    start = 0

    for i in range(1, n + 1):
        if (i == n) or (fmt[i] != fmt[start]):
            ret.append((start, i, ord(fmt[start]) - 48))
            start = i

    return ret


# style for a separator character (a space put back between two wrapped
# lines) between characters with styles a and b: what they have in
# common, so that e.g. a space between two underlined words is underlined
def joinStyle(a, b):
    return a & b


# return the format string for the text of the lines whose (text, fmt)
# pairs are given, joined with the separators given in seps (one fewer
# than the lines, each "" or " "), or None if there's no formatting
def join(parts, seps):
    if not any(fmt for text, fmt in parts):
        return None

    ret = []

    for i, (text, fmt) in enumerate(parts):
        fmt = fit(fmt, len(text))

        if i != 0:
            prev = ret[-1][-1:] if ret and ret[-1] else "0"
            sep = seps[i - 1]

            if sep:
                style = joinStyle(styleAt(prev, 0), styleAt(fmt, 0))
                ret.append(char(style) * len(sep))

        ret.append(fmt)

    return compact("".join(ret))


# like re.sub(pattern, repl, text), but also returns the format string
# for the result, or None if there's no formatting: (text, fmt). each
# replacement gets the style of the first character it replaces.
def sub(pattern, repl, text, fmt):
    if not fmt:
        return (pattern.sub(repl, text), None)

    fmt = fit(fmt, len(text))
    newText = []
    newFmt = []
    pos = 0

    for m in pattern.finditer(text):
        s = repl(m)

        newText.append(text[pos : m.start()])
        newFmt.append(fmt[pos : m.start()])
        newText.append(s)
        newFmt.append(char(styleAt(fmt, m.start())) * len(s))
        pos = m.end()

    newText.append(text[pos:])
    newFmt.append(fmt[pos:])

    return ("".join(newText), compact("".join(newFmt)))


_flagChars = ((BOLD, "b"), (ITALIC, "i"), (UNDERLINED, "u"))


# return fmt in the form saved to files: comma-separated "start-end:flags"
# items for its formatted runs, where end is exclusive and flags is any of
# "b", "i" and "u". returns "" if there's no formatting.
def encode(fmt):
    if not fmt:
        return ""

    items = []

    for start, end, style in runs(fmt, len(fmt)):
        if style:
            flags = "".join(c for bit, c in _flagChars if style & bit)
            items.append("%d-%d:%s" % (start, end, flags))

    return ",".join(items)


_itemRe = re.compile(r"^(\d+)-(\d+):([biu]+)$")


# opposite of encode(), for a text n characters long. invalid items and
# the parts of items past the end of the text are ignored. returns None
# if there's no (valid) formatting.
def decode(s, n):
    fmt = ["0"] * n

    for item in s.split(","):
        m = _itemRe.match(item.strip())

        if not m:
            continue

        style = 0

        for bit, c in _flagChars:
            if c in m.group(3):
                style |= bit

        for i in range(int(m.group(1)), min(int(m.group(2)), n)):
            fmt[i] = char(style)

    return compact("".join(fmt))


# Fountain-style markup: *italic*, **bold**, ***bold italic***,
# _underline_. markers for the bold / italic bits.
_markers = {BOLD: "**", ITALIC: "*", BOLD | ITALIC: "***"}


# return s with "*" and "_" escaped, so that they don't count as markup
def _escape(s):
    return s.replace("*", "\\*").replace("_", "\\_")


# return text with its formatting written as Fountain-style markup.
# spaces at the edges of a formatted run are kept outside its markers,
# since a marker next to a space doesn't count as one. literal "*" and
# "_" characters are escaped if they'd otherwise be read as markup.
def toMarkup(text, fmt):
    if not fmt:
        if fromMarkup(text) == (text, None):
            return text

        return _escape(text)

    ret = []

    for start, end, style in runs(fmt, len(text)):
        s = _escape(text[start:end])

        if not style or not s.strip():
            ret.append(s)
            continue

        core = s.strip()
        lead = s[: len(s) - len(s.lstrip())]
        trail = s[len(s.rstrip()) :]

        m = _markers.get(style & (BOLD | ITALIC), "")
        core = m + core + m

        if style & UNDERLINED:
            core = "_" + core + "_"

        ret.append(lead + core + trail)

    return "".join(ret)


# parse Fountain-style markup (see toMarkup) in s and return (text, fmt),
# where text has the markers removed and fmt is None if there was no
# formatting. a marker only counts if a matching one comes later, and an
# opening one must not be followed by a space. "\*" and "\_" are literal
# "*" and "_".
def fromMarkup(s):
    if ("*" not in s) and ("_" not in s):
        return (s, None)

    # tokenize into literal characters and markers
    tokens = []
    i = 0

    while i < len(s):
        c = s[i]

        if (c == "\\") and (s[i + 1 : i + 2] in ("*", "_")):
            tokens.append(("c", s[i + 1]))
            i += 2
        elif c == "*":
            n = len(s[i:]) - len(s[i:].lstrip("*"))
            n = min(n, 3)
            tokens.append(("m", "*" * n))
            i += n
        elif c == "_":
            tokens.append(("m", "_"))
            i += 1
        else:
            tokens.append(("c", c))
            i += 1

    bits = {"*": ITALIC, "**": BOLD, "***": BOLD | ITALIC, "_": UNDERLINED}

    text = []
    fmt = []
    style = 0

    # bits currently on, and the marker that turned them on
    open_ = {}

    for k, (kind, val) in enumerate(tokens):
        if kind == "c":
            text.append(val)
            fmt.append(char(style))
            continue

        bit = bits[val]

        if val in open_:
            # closing marker: must follow a non-space
            if text and not text[-1].isspace():
                del open_[val]
                style &= ~bit
                continue
        else:
            nextTok = tokens[k + 1] if (k + 1) < len(tokens) else None
            closes = any(t == ("m", val) for t in tokens[k + 1 :])

            if (
                closes
                and not (style & bit)
                and nextTok
                and not ((nextTok[0] == "c") and nextTok[1].isspace())
            ):
                open_[val] = True
                style |= bit
                continue

        # not a valid marker; keep it as text
        for c in val:
            text.append(c)
            fmt.append(char(style))

    return ("".join(text), compact("".join(fmt)))
