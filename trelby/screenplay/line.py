# -*- coding: utf-8 -*-

import trelby.config as config
import trelby.textfmt as textfmt

# constants that could not be removed yet
from trelby.screenplay import ACTION, LB_LAST


# one line in a screenplay
class Line:
    def __init__(
        self,
        lb=LB_LAST,
        lt=ACTION,
        text="",
        pageLock=None,
        dual=False,
        color=None,
        fmt=None,
        centered=False,
        sceneLock=None,
        sceneId=None,
    ):

        # line break type: what separates this line from the next one
        # (LB_LAST ends the element). see the LB_* constants in
        # screenplay.
        self.lb = lb

        # line type
        self.lt = lt

        # text
        self.text = text

        # if not None, the page labeled with this string (e.g. "16" or
        # "15A") is locked to start at this line. see
        # Screenplay.paginate.
        self.pageLock = pageLock

        # True on the first line of a character element whose speech is
        # the right-hand column of a dual dialogue, paired with the
        # speech just before it. only meaningful on such lines; see
        # Screenplay.getDualBlock.
        self.dual = dual

        # on the first line of a scene heading or act break element: the
        # color the scene is shown with in the outline view, as six
        # lower-case hex digits ("rrggbb"), or None. only meaningful on
        # such lines; see Screenplay.getSceneColor.
        self.color = color

        # the bold / italic / underline formatting of the text, as a
        # format string (see textfmt), or None if it has none
        self.fmt = textfmt.compact(textfmt.fit(fmt, len(text))) if fmt else None

        # True on the first line of an action element that's centered on
        # the page. only meaningful on such lines; see
        # Screenplay.isCentered.
        self.centered = centered

        # on the first line of a scene heading element: if not None, the
        # scene numbers are locked and this scene is numbered with this
        # string (e.g. "16" or "15A"). only meaningful on such lines; see
        # Screenplay.getSceneLabels.
        self.sceneLock = sceneLock

        # on the first line of a scene heading or act break element: the
        # id a beat board card links to the scene by, or None. only
        # meaningful on such lines; see Screenplay.getSceneId.
        self.sceneId = sceneId

    # return a copy of this line, including its page lock, dual flag,
    # color, formatting, centered flag, scene lock and scene id
    def copy(self):
        return Line(
            self.lb,
            self.lt,
            self.text,
            self.pageLock,
            self.dual,
            self.color,
            self.fmt,
            self.centered,
            self.sceneLock,
            self.sceneId,
        )

    # return the format string, exactly as long as the text
    def getFmt(self):
        return textfmt.fit(self.fmt, len(self.text))

    # return the format string for text[a:b], or None if it's plain
    def sliceFmt(self, a, b=None):
        if not self.fmt:
            return None

        return textfmt.compact(self.getFmt()[a:b])

    # set the text and its format string (None for plain text)
    def setText(self, text, fmt=None):
        self.text = text
        self.fmt = textfmt.compact(textfmt.fit(fmt, len(text))) if fmt else None

    # insert s, all of it with the given style, at column col
    def insertText(self, col, s, style=0):
        if not self.fmt and not style:
            self.text = self.text[:col] + s + self.text[col:]

            return

        fmt = self.getFmt()
        self.setText(
            self.text[:col] + s + self.text[col:],
            fmt[:col] + textfmt.char(style) * len(s) + fmt[col:],
        )

    # replace 'length' characters at column col with s, which gets the
    # style of the first replaced character
    def replaceText(self, col, length, s):
        if not self.fmt:
            self.text = self.text[:col] + s + self.text[col + length :]

            return

        fmt = self.getFmt()
        style = textfmt.styleAt(fmt, col)
        self.setText(
            self.text[:col] + s + self.text[col + length :],
            fmt[:col] + textfmt.char(style) * len(s) + fmt[col + length :],
        )

    # delete characters a - b (b exclusive)
    def deleteText(self, a, b):
        if not self.fmt:
            self.text = self.text[:a] + self.text[b:]

            return

        fmt = self.getFmt()
        self.setText(self.text[:a] + self.text[b:], fmt[:a] + fmt[b:])

    # append another line's text and formatting to this one
    def appendLine(self, other):
        if not self.fmt and not other.fmt:
            self.text += other.text

            return

        self.setText(self.text + other.text, self.getFmt() + other.getFmt())

    # only the line break, type and text. undo.lines2storage keeps the
    # other attributes alongside, and fromStr below leaves them unset.
    def __str__(self):
        return config.lb2char(self.lb) + config.lt2char(self.lt) + self.text

    def __repr__(self) -> str:
        return self.__str__()

    def __ne__(self, other):
        return (
            (self.lt != other.lt)
            or (self.lb != other.lb)
            or (self.text != other.text)
            or (self.pageLock != other.pageLock)
            or (self.dual != other.dual)
            or (self.color != other.color)
            or (textfmt.compact(self.fmt) != textfmt.compact(other.fmt))
            or (self.centered != other.centered)
            or (self.sceneLock != other.sceneLock)
            or (self.sceneId != other.sceneId)
        )

    def __eq__(self, other):
        return not self.__ne__(other)

    # opposite of __str__. NOTE: only meant for storing data internally by
    # the program! NOT USABLE WITH EXTERNAL INPUT DUE TO COMPLETE LACK OF
    # ERROR CHECKING!
    @staticmethod
    def fromStr(s):
        return Line(config.char2lb(s[0]), config.char2lt(s[1]), s[2:])
