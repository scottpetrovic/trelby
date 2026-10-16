import bisect

import trelby.pml as pml
import trelby.screenplay as screenplay
import trelby.screenplay.speeches as speeches
import trelby.textreport as textreport
import trelby.textutil as textutil
import trelby.util as util
from trelby.pagelist import PageList


class SceneReport(textreport.TextReport):
    options = [("speakers", lambda: _("Speakers"))]

    def __init__(self, sp):
        super().__init__(sp)

        # list of SceneInfos
        self.scenes = splitScenes(sp)

        for si in self.scenes:
            si.readLines(sp)

        # count each speech's dialogue lines in the scene it's in. a speech
        # with no character element before it isn't counted, and the
        # speaker's name is the first line of the character element.
        starts = [si.startLine for si in self.scenes]

        for speech in speeches.iterSpeeches(sp):
            if (speech.charLine is None) or not speech.dialogue:
                continue

            si = self.scenes[bisect.bisect_right(starts, speech.start) - 1]

            s = textutil.upper(sp.lines[speech.charLine].text)
            if len(s.strip()) == 0:
                name = "(EMPTY CHARACTER NAME)"
            else:
                name = s

            si.chars[name] = si.chars.get(name, 0) + len(speech.dialogue)

    def format(self, tf) -> None:
        for si in self.scenes:
            tf.addSpace(5.0)

            tf.addText("%-4s %s" % (si.number, si.name), style=pml.BOLD)

            tf.addSpace(1.0)

            tf.addText(
                _("     Lines: {} (%{} action), Pages: {} ({})").format(
                    si.lines,
                    util.pct(si.actionLines, si.lines),
                    len(si.pages),
                    si.pages,
                )
            )

            if self.opts["speakers"]:
                tf.addSpace(2.5)

                for it in util.sortDict(si.chars):
                    tf.addText("     %3d  %s" % (it[1], it[0]))



# split the whole script into consecutive parts, each starting at a scene
# heading or act break, and return a SceneInfo for each, with its number,
# name and size. the part before the first heading, if any, and the parts
# starting at act breaks get the name "(NO SCENE NAME)".
def splitScenes(sp):
    ret = []
    line = 0

    while line < len(sp.lines):
        startLine, endLine = sp.getSceneIndexesFromLine(line)
        ret.append(SceneInfo(sp, startLine, endLine))
        line = endLine + 1

    return ret


# information about one scene
class SceneInfo:
    def __init__(self, sp, startLine, endLine):
        ls = sp.lines

        # the scene's first and last line
        self.startLine = startLine
        self.endLine = endLine

        # scene number, e.g. "42A"
        self.number = sp.getSceneNumber(startLine) or "0"

        # scene name, e.g. "INT. MOTEL ROOM - NIGHT"
        # TODO: handle multi-line scene names
        if ls[startLine].lt == screenplay.SCENE:
            s = textutil.upper(ls[startLine].text)

            if len(s.strip()) == 0:
                self.name = "(EMPTY SCENE NAME)"
            else:
                self.name = s
        else:
            self.name = "(NO SCENE NAME)"

        # the first line after the scene heading
        line = startLine
        while (line <= endLine) and (ls[line].lt == screenplay.SCENE):
            line = sp.getElemLastIndexFromLine(line) + 1

        self.bodyLine = line

        # total lines, excluding scene lines
        self.lines = max(0, endLine - line + 1)

        # action lines
        self.actionLines = 0

        # page numbers
        self.pages = PageList(sp.getPageNumbers())

        # key = character name (upper cased), value = number of dialogue
        # lines
        self.chars = {}

    # read the scene's pages and number of action lines
    def readLines(self, sp):
        self.pages.addPage(sp.line2pageLabel(self.startLine))

        for i in range(self.bodyLine, self.endLine + 1):
            self.pages.addPage(sp.line2pageLabel(i))

            if sp.lines[i].lt == screenplay.ACTION:
                self.actionLines += 1
