# -*- coding: utf-8 -*-

import trelby.config as config

# constants that could not be removed yet
from trelby.screenplay import ACTION, LB_LAST


# one line in a screenplay
class Line:
    def __init__(
        self, lb=LB_LAST, lt=ACTION, text="", pageLock=None, dual=False, color=None
    ):

        # line break type
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

    # return a copy of this line, including its page lock, dual flag and
    # color
    def copy(self):
        return Line(self.lb, self.lt, self.text, self.pageLock, self.dual, self.color)

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
        )

    def __eq__(self, other):
        return not self.__ne__(other)

    # opposite of __str__. NOTE: only meant for storing data internally by
    # the program! NOT USABLE WITH EXTERNAL INPUT DUE TO COMPLETE LACK OF
    # ERROR CHECKING!
    @staticmethod
    def fromStr(s):
        return Line(config.char2lb(s[0]), config.char2lt(s[1]), s[2:])
