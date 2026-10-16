# -*- coding: utf-8 -*-

# text helpers: case mapping, character classes, wrapping, escaping and
# words. these work on plain strings and don't depend on the rest of
# trelby.

import functools
import re
import unicodedata

# map some fancy unicode characters to their nearest ASCII/Latin-1
# equivalents so when people import text it's not mangled to uselessness
_fancy_unicode_map = {
    #    ord('‘') : "'",
    #    ord('’') : "'",
    #    ord('“') : '"',
    #    ord('”') : '"',
    #    ord('—') : "--",
    #    ord('–') : "-",
}


# like str.upper/lower, but the result always has the same length as s,
# since the script's layout counts characters. characters whose case
# mapping is longer than one character (e.g. "ß" -> "SS") are kept as they
# are.
def upper(s):
    u = s.upper()

    if len(u) == len(s):
        return u

    return "".join(_sameLength(c, c.upper()) for c in s)


def lower(s):
    l = s.lower()

    if len(l) == len(s):
        return l

    return "".join(_sameLength(c, c.lower()) for c in s)


def _sameLength(c, mapped):
    return mapped if len(mapped) == 1 else c


def capitalize(s):
    return upper(s[:1]) + s[1:]


# return 's', which must be a unicode string, converted to a ISO-8859-1
# 8-bit string. characters not representable in ISO-8859-1 are discarded.
def toLatin1(s):
    return s.encode("ISO-8859-1", "ignore")


# toUTF8 and fromUTF8 converted between the Latin-1 strings the program
# used internally and the UTF-8 in its files. strings are Unicode
# throughout now, and files are decoded when read, so both return s as it
# is; they're kept to mark the places that read and write saved text.
def toUTF8(s):
    return s


def fromUTF8(s):
    return s


# Unicode general categories of characters that can't be in a script:
# control characters (C0, DEL and C1), format characters (soft hyphen,
# zero-width and bidi marks, ...), surrogates, private use, unassigned code
# points, and the line and paragraph separators.
_invalidCategories = frozenset(("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"))


# returns True if kc, a Unicode code point, is a valid character to add to
# the script. 0xA0 (non-breaking space) is valid.
@functools.lru_cache(maxsize=4096)
def isValidInputChar(kc):
    if (kc < 32) or (kc > 0x10FFFF):
        return False

    return unicodedata.category(chr(kc)) not in _invalidCategories


# returns True if ch is a wide character, one that takes up two columns in
# a monospaced font: Chinese, Japanese and Korean characters, and the
# full-width forms of Latin letters and punctuation.
def isWideChar(ch):
    return unicodedata.east_asian_width(ch) in ("W", "F")


# returns True if s contains any wide characters (see isWideChar)
def hasWideChars(s):
    return not s.isascii() and any(isWideChar(ch) for ch in s)


# wide punctuation that mustn't start a line
_NO_BREAK_BEFORE = "，。、；：？！）」』》〉】”’"


# split s into the pieces wrapText may put on different lines: a line can
# be broken after a space, or between two characters if one of them is
# wide, since Chinese, Japanese and Korean text has no spaces. spaces stay
# at the end of the piece before them.
def _wrapPieces(s):
    pieces = []
    start = 0

    for i in range(1, len(s)):
        prev, ch = s[i - 1], s[i]

        if ch == " ":
            continue

        if (prev == " ") or (
            (isWideChar(prev) or isWideChar(ch)) and (ch not in _NO_BREAK_BEFORE)
        ):
            pieces.append(s[start:i])
            start = i

    pieces.append(s[start:])

    return pieces


# wrap text to fit in width, where measure(s) returns the width of string
# s, and return it with line breaks added. existing line breaks are kept.
# a word that doesn't fit by itself gets a line of its own.
def wrapText(text, width, measure):
    lines = []

    for para in text.split("\n"):
        line = ""

        for piece in _wrapPieces(para):
            if line and (measure((line + piece).rstrip()) > width):
                lines.append(line.rstrip())
                line = piece
            else:
                line += piece

        lines.append(line.rstrip())

    return "\n".join(lines)


# return s with the characters that can't be in a script dropped, except
# for the ones in 'keep'
def removeInvalidChars(s, keep="\n"):
    return "".join(ch for ch in s if (ch in keep) or isValidInputChar(ord(ch)))


# return s with all non-valid input characters converted to valid input
# characters, except form feeds, which are just deleted.
def toInputStr(s):
    return str(s).replace("\f", "").replace("\t", "|")


# replace fancy unicode characters with their ASCII/Latin1 equivalents.
def removeFancyUnicode(s):
    return s.translate(_fancy_unicode_map)


# transform external input (unicode) into a form suitable for having in a
# script: compose accented letters that come as a letter followed by a
# combining accent, since each character takes up one column.
def cleanInput(s):
    return unicodedata.normalize("NFC", s)


# replace s[start:start + width] with toInputStr(new) and return s
def replace(s, new, start, width):
    return s[0:start] + toInputStr(new) + s[start + width :]


# delete all characters in 'chars' from s and return that.
def deleteChars(s: str, chars: str) -> str:
    for char in chars:
        s = s.replace(char, "")
    return s


# returns s with all possible different types of newlines converted to
# unix newlines, i.e. a single "\n"
def fixNL(s):
    return s.replace("\r\n", "\n").replace("\r", "\n")


# return items, which is a list of ISO-8859-1 strings, as a single string
# with \n between each string. any \ characters in the individual strings
# are escaped as \\.
#
# the \n is the two characters "\" and "n", not a newline, so the result
# fits on one line of a saved script (title page strings are stored this
# way). an empty last item doesn't survive unescapeStrings.
def escapeStrings(items):
    return "\\n".join([s.replace("\\", "\\\\") for s in items])


# opposite of escapeStrings. takes in a string, returns a list of strings.
def unescapeStrings(s):
    if not s:
        return []

    items = []

    tmp = ""
    i = 0
    while i < (len(s) - 1):
        ch = s[i]

        if ch != "\\":
            tmp += ch
            i += 1
        else:
            ch = s[i + 1]

            if ch == "n":
                items.append(tmp)
                tmp = ""
            else:
                tmp += ch

            i += 2

    if i < len(s):
        tmp += s[i]
        items.append(tmp)

    return items


# return s encoded so that all characters outside the range [32,126] (and
# "\\") are escaped.
#
# characters up to U+00FF are written as "\" plus two hex digits ("\A4"),
# the original format, which existing config files contain. anything above
# that is written as "\u" plus four hex digits, or "\U" plus eight outside
# the BMP. old versions wrote those as "\" plus however many digits they
# needed ("\30B4"), which never read back correctly; such strings still
# decode the way they always did ("0B4").
def encodeStr(s):
    ret = ""

    for ch in s:
        c = ord(ch)

        # ord("\\") == 92 == 0x5C
        if c == 92:
            ret += "\\5C"
        elif (c >= 32) and (c <= 126):
            ret += ch
        elif c <= 0xFF:
            ret += "\\%02X" % c
        elif c <= 0xFFFF:
            ret += "\\u%04X" % c
        else:
            ret += "\\U%08X" % c

    return ret


_decodeRe = re.compile(r"\\u[0-9A-Fa-f]{4}|\\U[0-9A-Fa-f]{8}|\\..")


# reverse of encodeStr. if string contains invalid escapes, they're
# silently and arbitrarily replaced by something.
def decodeStr(s):
    return _decodeRe.sub(_decodeRepl, s)


# converts "\A4", "ゴ" and "\U0001F600" style matches to their
# character values.
def _decodeRepl(mo):
    esc = mo.group(0)

    if len(esc) > 3:
        val = int(esc[2:], 16)

        return chr(val) if val <= 0x10FFFF else ""

    # like util.str2int(esc[1:], 256, 0, 256, 16)
    try:
        val = int(esc[1:], 16)
    except ValueError:
        val = 256

    val = min(max(val, 0), 256)

    if val != 256:
        return chr(val)
    else:
        return ""


# return string s escaped for use in RTF. non-ASCII characters are written
# as \uN control words (N being a signed 16-bit UTF-16 code unit), each
# followed by "?" for readers that don't know them.
def escapeRTF(s):
    s = s.replace("\\", "\\\\").replace("{", r"\{").replace("}", r"\}")

    if s.isascii():
        return s

    out = []

    for ch in s:
        if ord(ch) < 128:
            out.append(ch)
        else:
            data = ch.encode("UTF-16-LE")

            for i in range(0, len(data), 2):
                unit = int.from_bytes(data[i : i + 2], "little", signed=True)
                out.append("\\u%d?" % unit)

    return "".join(out)


# return True if c is not a word character, i.e. is either empty, not an
# alphanumeric character or a "'", or is more than one character.
def isWordBoundary(c):
    if len(c) != 1:
        return True

    if c == "'":
        return False

    return not isAlnum(c)


# return True if c is an alphanumeric character
def isAlnum(c):
    return str(c).isalnum()


# make sure s (unicode) ends in suffix (case-insensitively) and return
# that. suffix must already be lower-case.
def ensureEndsIn(s, suffix):
    if s.lower().endswith(suffix):
        return s
    else:
        return s + suffix


# return string 's' split into words (as a list), using isWordBoundary.
def splitToWords(s):
    tmp = ""

    for c in s:
        if isWordBoundary(c):
            tmp += " "
        else:
            tmp += c

    return tmp.split()


# return two-character prefix of s, using characters a-z only: A-Z are
# lowercased and everything else becomes "z". len(s) must be at least 2.
def getWordPrefix(s):
    return "".join(_prefixChar(c) for c in s[:2])


def _prefixChar(c):
    if "a" <= c <= "z":
        return c

    if "A" <= c <= "Z":
        return chr(ord(c) + 32)

    return "z"


# return count of how many 'ch' characters 's' begins with.
def countInitial(s, ch):
    cnt = 0

    for i in range(len(s)):
        if s[i] != ch:
            break

        cnt += 1

    return cnt


# searches string 's' for each item of list 'seq', returning True if any
# of them were found.
def multiFind(s, seq):
    for it in seq:
        if s.find(it) != -1:
            return True

    return False
