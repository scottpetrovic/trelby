# small classes used with Screenplay: selection marks, clipboard contents,
# outline items, and per-command state.

import re


# used to keep track of selected area. this marks one of the end-points,
# while the other one is the current position.
class Mark:
    def __init__(self, line, column):
        self.line = line
        self.column = column

    def __eq__(self, other):
        return (self.line == other.line) and (self.column == other.column)


# return True if s is a valid scene color: six hex digits, "rrggbb"
def isValidColor(s):
    return re.fullmatch("[0-9a-fA-F]{6}", s) is not None


# data held in internal clipboard.
class ClipData:
    def __init__(self):

        # list of Line objects
        self.lines = []


# one entry (a scene or an act break) in a script's outline. see
# Screenplay.getOutline.
class OutlineItem:
    def __init__(
        self,
        lt,
        sceneNr,
        startLine,
        endLine,
        heading,
        summary,
        page,
        color=None,
        synopsis=None,
    ):

        # SCENE or ACTBREAK
        self.lt = lt

        # scene number as a string, or "" for act breaks
        self.sceneNr = sceneNr

        # range of lines covered, inclusive
        self.startLine = startLine
        self.endLine = endLine

        # text of the scene heading / act break element
        self.heading = heading

        # the start of the scene's action (see getSceneSummary), "" if it
        # has none
        self.summary = summary

        # label of the page the item starts on, e.g. "16" or "15A"
        self.page = page

        # color to show the item with in the outline ("rrggbb"), or None
        self.color = color

        # the scene's synopsis (see Screenplay.getSynopsis), or None. the
        # outline shows it in place of the summary.
        self.synopsis = synopsis

    def __eq__(self, other):
        return isinstance(other, OutlineItem) and (self.__dict__ == other.__dict__)


# stuff we need when handling commands in Editor.
class CommandState:

    # what to do about auto-completion after the command (see cmdPost):
    # AC_DEL closes the list, which is the default so that any command
    # that doesn't care about it closes it; AC_REDO refills it from the
    # current line's text; AC_KEEP leaves it as it is, e.g. when moving
    # the selection in it.
    AC_DEL, AC_REDO, AC_KEEP = list(range(3))

    def __init__(self):

        self.doAutoComp = self.AC_DEL

        # only used for inserting characters, in which case this is the
        # character to insert in a string form.
        self.char = None

        # True if this is a movement command and we should set mark at the
        # current position before moving (note that currently this is just
        # set if shift is down)
        self.mark = False

        # True if we need to make current line visible
        self.needsVisifying = True
