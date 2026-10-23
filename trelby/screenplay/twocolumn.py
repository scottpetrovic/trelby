# two-column (AV) scripts: laying out a format's left and right columns
# side by side (see scriptformats.ScriptFormat.columns).
#
# the script stays one list of elements, and each element type's indent
# and width keep it in its column. a row is a run of left-column elements
# followed by a run of right-column ones: the right run starts at the top
# of the left one instead of below it, and what follows the row goes
# below the longer of the two. a right run with no left run before it (or
# a left run with no right run after it) just takes its place like any
# other element, and elements of the types in neither column go across
# the page, ending the row.
#
# RowLayout does the placing, in whatever units it's given, for render
# (the PDF and the page views), pagination and the draft view, so they
# agree. a row is kept on one page unless it starts a page and still
# doesn't fit, when it's split like other text is: its right column
# continuing at the top of the next page, or if the left one alone
# doesn't fit, both going on there.

import trelby.screenplay.scriptformats as scriptformats

LEFT = scriptformats.LEFT
RIGHT = scriptformats.RIGHT

# a full-width element's column
FULL = 0

# the room the column headings take at the top of each page, in tenths of
# a line: their line and a blank one
HEADINGS_HEIGHT = 20


# places lines one after another, each in its column, given the space
# before it and its height, and keeps track of where the next one goes
class RowLayout:
    def __init__(self, y=0):
        # where the next line goes, if it doesn't start a right run: the
        # bottom of the last line placed, in its column
        self.y = y

        # the top of the current row's left run
        self.rowTop = y

        # while in a row's right run, the bottom of its left run, else
        # None
        self.leftBottom = None

        # the column of the last line placed, None before the first
        self.prevCol = None

    # place a line in column col (LEFT, RIGHT or FULL), 'spacing' below
    # the line before it unless it starts a row's right run (or it's the
    # first line), and return its top
    def place(self, col, spacing, height=10):
        if self.prevCol is None:
            top = self.y
        elif (col == RIGHT) and (self.prevCol == LEFT):
            self.leftBottom = self.y
            top = self.rowTop
        else:
            if (col != RIGHT) and (self.leftBottom is not None):
                self.y = max(self.y, self.leftBottom)
                self.leftBottom = None

            top = self.y + spacing

        if (col == LEFT) and (self.prevCol != LEFT):
            self.rowTop = top

        self.prevCol = col
        self.y = top + height

        return top

    # whether the last line placed is in a row's right run, beside a left
    # one
    def inRightRun(self):
        return self.leftBottom is not None

    # the bottom of everything placed so far
    def bottom(self):
        if self.leftBottom is None:
            return self.y

        return max(self.y, self.leftBottom)


class TwoColumnMixin:
    # whether the script's format has two columns
    def isTwoColumn(self):
        return scriptformats.columns(self.cfg) is not None

    # {line type: column} for every line type, FULL for those in neither
    # column, or None if the script's format has one column
    def getColumns(self):
        cols = scriptformats.columns(self.cfg)

        if cols is None:
            return None

        return {lt: cols.get(lt, FULL) for lt in self.cfg.types}

    # a RowLayout starting at y, or None if the script has one column
    def makeRowLayout(self, y=0):
        if not self.isTwoColumn():
            return None

        return RowLayout(y)

    # return the rows lying within lines start - end (inclusive) that
    # have both columns, as a {line: (column, first, right, last)} dict
    # containing all of their lines, like getDualLines: first is the
    # row's first line, right the first line of its right run and last
    # its last line. a row reaching past start or end is cut there, so a
    # page's rows are those it shows side by side.
    def getRowLines(self, start, end):
        cols = self.getColumns()
        ret = {}

        if not cols:
            return ret

        ls = self.lines
        i = start

        while i <= end:
            if cols[ls[i].lt] != LEFT:
                i += 1

                continue

            first = i

            while (i <= end) and (cols[ls[i].lt] == LEFT):
                i += 1

            right = i

            while (i <= end) and (cols[ls[i].lt] == RIGHT):
                i += 1

            if i > right:
                for j in range(first, i):
                    ret[j] = (LEFT if j < right else RIGHT, first, right, i - 1)

        return ret

    # the lines within start - end shown in two columns, in the format
    # of getDualLines: a two-column script's rows, or another script's
    # dual dialogues
    def getSideBySideLines(self, start, end):
        if self.isTwoColumn():
            return self.getRowLines(start, end)

        return self.getDualLines(start, end)

    # whether line i is in a row's left run, with a right run after it
    def isBesideRightRun(self, i):
        cols = self.getColumns()
        ls = self.lines

        if not cols or (cols[ls[i].lt] != LEFT):
            return False

        while (i < len(ls)) and (cols[ls[i].lt] == LEFT):
            i += 1

        return (i < len(ls)) and (cols[ls[i].lt] == RIGHT)

    # the row (see getRowLines) line i is in, as (first, right, last), or
    # None if it's not in one
    def getRowAround(self, i):
        cols = self.getColumns()
        ls = self.lines

        if not cols or (cols[ls[i].lt] == FULL):
            return None

        right = i

        while (right > 0) and (cols[ls[right - 1].lt] == RIGHT):
            right -= 1

        if cols[ls[i].lt] == LEFT:
            right = i

            while (right < len(ls)) and (cols[ls[right].lt] == LEFT):
                right += 1

        first = right

        while (first > 0) and (cols[ls[first - 1].lt] == LEFT):
            first -= 1

        last = right

        while ((last + 1) < len(ls)) and (cols[ls[last + 1].lt] == RIGHT):
            last += 1

        if (first == right) or (right == len(ls)) or (cols[ls[right].lt] != RIGHT):
            return None

        return (first, right, last)

    # which column (LEFT or RIGHT) the cursor is in on line i at column
    # col: a column's lines are in their own, and on lines across the
    # page, the one under the cursor
    def getColumnAt(self, i, col):
        cols = self.getColumns()
        c = cols[self.lines[i].lt]

        if c != FULL:
            return c

        x = self.cfg.getType(self.lines[i].lt).indent + col

        return RIGHT if x >= self.getColumnBounds()[1][0] else LEFT

    # the line the Down arrow goes to from line i with the cursor at
    # column col: the next one, except that in a two-column script it
    # goes down the cursor's column, past the other one. None if there's
    # nothing below.
    def getLineBelow(self, i, col):
        if not self.isTwoColumn():
            return (i + 1) if (i + 1) < len(self.lines) else None

        side = self.getColumnAt(i, col)
        row = self.getRowAround(i)

        # from the bottom of a row's left column, below the row
        if row and (i == (row[1] - 1)):
            i = row[2]

        if (i + 1) >= len(self.lines):
            return None

        # into a row, at the top of the cursor's column
        row = self.getRowAround(i + 1)

        if row and (row[0] == (i + 1)) and (side == RIGHT):
            return row[1]

        return i + 1

    # the line the Up arrow goes to from line i with the cursor at column
    # col, like getLineBelow
    def getLineAbove(self, i, col):
        if not self.isTwoColumn():
            return (i - 1) if i > 0 else None

        side = self.getColumnAt(i, col)
        row = self.getRowAround(i)

        # from the top of a row's right column, above the row
        if row and (i == row[1]):
            i = row[0]

        if i == 0:
            return None

        # into a row, at the bottom of the cursor's column
        row = self.getRowAround(i - 1)

        if row and (row[2] == (i - 1)) and (side == LEFT):
            return row[1] - 1

        return i - 1

    # the height of lines first - last laid out on a page starting with
    # 'first', in tenths of a line
    def getRowsHeight(self, first, last):
        cols = self.getColumns()
        layout = RowLayout()

        for i in range(first, last + 1):
            col = cols[self.lines[i].lt] if cols else FULL
            layout.place(col, self.getSpacingBefore(i))

        return layout.bottom()

    # the columns' places on the page, as ((left x, right x) of the left
    # column, (left x, right x) of the right one), in characters from the
    # left margin: where their element types start and end
    def getColumnBounds(self):
        cols = self.getColumns()
        ret = []

        for col in (LEFT, RIGHT):
            types = [self.cfg.getType(lt) for lt, c in cols.items() if c == col]

            ret.append(
                (min(t.indent for t in types), max(t.indent + t.width for t in types))
            )

        return tuple(ret)

    # the room the column headings take on each page, in tenths of a
    # line (0 if there are none)
    def getColumnHeadingsHeight(self):
        fmt = scriptformats.ofConfig(self.cfg)

        return HEADINGS_HEIGHT if (fmt.columns and fmt.headings) else 0

    # the titles printed above the columns on every page, as [(text,
    # indent in characters)], or [] if there are none. each starts where
    # its column does.
    def getColumnHeadings(self):
        if not self.getColumnHeadingsHeight():
            return []

        titles = scriptformats.ofConfig(self.cfg).headings

        return [
            (title(), x) for title, (x, _end) in zip(titles, self.getColumnBounds())
        ]
