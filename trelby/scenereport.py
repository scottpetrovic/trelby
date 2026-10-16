import trelby.pml as pml
import trelby.screenplay as screenplay
import trelby.screenplay.speeches as speeches
import trelby.textreport as textreport
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

        # count each speech's dialogue lines in its scene. a speech before
        # the first scene heading or act break is in the part starting at
        # line 0.
        byStart = {si.startLine: si for si in self.scenes}

        for speech in speeches.iterSpeeches(sp):
            si = byStart[speech.scene or 0]
            si.chars[speech.name] = si.chars.get(speech.name, 0) + len(speech.dialogue)

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
        self.name = speeches.sceneName(sp, startLine)

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

        # key = character name (see screenplay/speeches.py), value =
        # number of dialogue lines
        self.chars = {}

    # read the scene's pages and number of action lines
    def readLines(self, sp):
        self.pages.addPage(sp.line2pageLabel(self.startLine))

        for i in range(self.bodyLine, self.endLine + 1):
            self.pages.addPage(sp.line2pageLabel(i))

            if sp.lines[i].lt == screenplay.ACTION:
                self.actionLines += 1
