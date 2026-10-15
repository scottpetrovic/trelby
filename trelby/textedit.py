import trelby.util as util


# editing state for a small block of multi-line text: the lines, a caret
# and an optional selection. positions are (line, column) tuples. has no
# wx dependencies; the widget using it handles drawing and keys.
class TextEdit:
    def __init__(self, lines):
        self.lines = list(lines) or [""]

        # caret position, and the other end of the selection (None if
        # nothing is selected)
        self.caret = (len(self.lines) - 1, len(self.lines[-1]))
        self.anchor = None

    def hasSelection(self):
        return (self.anchor is not None) and (self.anchor != self.caret)

    # return (start, end) of the selection, in order
    def getSelection(self):
        return min(self.anchor, self.caret), max(self.anchor, self.caret)

    def getSelectedText(self):
        if not self.hasSelection():
            return ""

        (l1, c1), (l2, c2) = self.getSelection()

        if l1 == l2:
            return self.lines[l1][c1:c2]

        parts = [self.lines[l1][c1:]] + self.lines[l1 + 1 : l2] + [self.lines[l2][:c2]]

        return "\n".join(parts)

    def selectAll(self):
        self.anchor = (0, 0)
        self.caret = (len(self.lines) - 1, len(self.lines[-1]))

    # move the caret to 'pos' (clamped to the text), extending the
    # selection if 'extend' is True and clearing it otherwise
    def setCaret(self, pos, extend=False):
        line = util.clamp(pos[0], 0, len(self.lines) - 1)
        col = util.clamp(pos[1], 0, len(self.lines[line]))

        if extend:
            if self.anchor is None:
                self.anchor = self.caret
        else:
            self.anchor = None

        self.caret = (line, col)

    def moveLeft(self, extend=False, word=False):
        if self.hasSelection() and not extend:
            self.setCaret(self.getSelection()[0])

            return

        line, col = self.caret

        if col > 0:
            col = self.wordStart(line, col) if word else col - 1
        elif line > 0:
            line -= 1
            col = len(self.lines[line])

        self.setCaret((line, col), extend)

    def moveRight(self, extend=False, word=False):
        if self.hasSelection() and not extend:
            self.setCaret(self.getSelection()[1])

            return

        line, col = self.caret

        if col < len(self.lines[line]):
            col = self.wordEnd(line, col) if word else col + 1
        elif line < len(self.lines) - 1:
            line += 1
            col = 0

        self.setCaret((line, col), extend)

    def moveHome(self, extend=False, doc=False):
        self.setCaret((0 if doc else self.caret[0], 0), extend)

    def moveEnd(self, extend=False, doc=False):
        line = len(self.lines) - 1 if doc else self.caret[0]
        self.setCaret((line, len(self.lines[line])), extend)

    # column of the start of the word before 'col' on 'line'
    def wordStart(self, line, col):
        s = self.lines[line]

        while (col > 0) and s[col - 1].isspace():
            col -= 1

        while (col > 0) and not s[col - 1].isspace():
            col -= 1

        return col

    # column of the end of the word after 'col' on 'line'
    def wordEnd(self, line, col):
        s = self.lines[line]

        while (col < len(s)) and s[col].isspace():
            col += 1

        while (col < len(s)) and not s[col].isspace():
            col += 1

        return col

    # select the word at 'pos'
    def selectWord(self, pos):
        self.setCaret(pos)
        line, col = self.caret
        s = self.lines[line]

        start = end = col

        while (start > 0) and not s[start - 1].isspace():
            start -= 1

        while (end < len(s)) and not s[end].isspace():
            end += 1

        self.anchor = (line, start)
        self.caret = (line, end)

    def deleteSelection(self):
        if not self.hasSelection():
            self.anchor = None

            return False

        (l1, c1), (l2, c2) = self.getSelection()

        self.lines[l1 : l2 + 1] = [self.lines[l1][:c1] + self.lines[l2][c2:]]
        self.caret = (l1, c1)
        self.anchor = None

        return True

    # insert 's', which can contain newlines, replacing the selection.
    # characters that aren't valid in a script are dropped.
    def insert(self, s):
        self.deleteSelection()

        s = util.toInputStr(s.replace("\r\n", "\n").replace("\r", "\n"))
        s = "".join(ch for ch in s if (ch == "\n") or util.isValidInputChar(ord(ch)))

        line, col = self.caret
        cur = self.lines[line]

        parts = s.split("\n")
        parts[0] = cur[:col] + parts[0]
        newCol = len(parts[-1])
        parts[-1] += cur[col:]

        self.lines[line : line + 1] = parts
        self.caret = (line + len(parts) - 1, newCol)

    def backspace(self):
        if self.deleteSelection():
            return

        line, col = self.caret

        if col > 0:
            s = self.lines[line]
            self.lines[line] = s[: col - 1] + s[col:]
            self.caret = (line, col - 1)
        elif line > 0:
            prevLen = len(self.lines[line - 1])
            self.lines[line - 1] += self.lines.pop(line)
            self.caret = (line - 1, prevLen)

    def delete(self):
        if self.deleteSelection():
            return

        line, col = self.caret
        s = self.lines[line]

        if col < len(s):
            self.lines[line] = s[:col] + s[col + 1 :]
        elif line < len(self.lines) - 1:
            self.lines[line] += self.lines.pop(line + 1)
