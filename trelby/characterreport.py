import functools
from functools import reduce

import trelby.checkboxitem as checkboxitem
import trelby.pml as pml
import trelby.screenplay as screenplay
import trelby.textreport as textreport
import trelby.textutil as textutil
import trelby.util as util
from trelby.pagelist import PageList


class CharacterReport(textreport.TextReport):
    margin = 20.0

    def __init__(self, sp):
        self.sp = sp

        ls = sp.lines

        # key = character name, value = CharInfo
        chars = {}

        name = None
        scene = "(NO SCENE NAME)"

        # how many lines processed for current speech
        curSpeechLines = 0

        # 'name' is the current speaker: set by the last line of a
        # character element, and cleared by any line that isn't dialogue
        # or a parenthetical. 'scene' is the last line of the latest scene
        # heading. the per-scene counts are of dialogue and parenthetical
        # lines.
        for i in range(len(ls)):
            line = ls[i]

            if (line.lt == screenplay.SCENE) and (line.lb == screenplay.LB_LAST):
                scene = textutil.upper(line.text)

            elif (line.lt == screenplay.CHARACTER) and (line.lb == screenplay.LB_LAST):
                name = textutil.upper(line.text)
                curSpeechLines = 0

            elif line.lt in (screenplay.DIALOGUE, screenplay.PAREN) and name:
                ci = chars.get(name)
                if not ci:
                    ci = CharInfo(name, sp)
                    chars[name] = ci

                if scene:
                    ci.scenes[scene] = ci.scenes.get(scene, 0) + 1

                if curSpeechLines == 0:
                    ci.speechCnt += 1

                curSpeechLines += 1

                # PAREN lines don't count as spoken words
                if line.lt == screenplay.DIALOGUE:
                    ci.lineCnt += 1

                    words = textutil.splitToWords(line.text)

                    ci.wordCnt += len(words)
                    ci.wordCharCnt += reduce(lambda x, y: x + len(y), words, 0)

                ci.pages.addPage(sp.line2pageLabel(i))

            else:
                name = None
                curSpeechLines = 0

        # list of CharInfo objects
        self.cinfo = []
        for v in list(chars.values()):
            self.cinfo.append(v)

        self.cinfo = sorted(self.cinfo, key=functools.cmp_to_key(cmpLines))

        self.totalSpeechCnt = self.sum("speechCnt")
        self.totalLineCnt = self.sum("lineCnt")
        self.totalWordCnt = self.sum("wordCnt")
        self.totalWordCharCnt = self.sum("wordCharCnt")

        # information types and what to include
        self.INF_BASIC, self.INF_PAGES, self.INF_LOCATIONS = list(range(3))
        self.inf = []
        for s in [_("Basic information"), _("Page list"), _("Location list")]:
            self.inf.append(checkboxitem.CheckBoxItem(s))

    # calculate total sum of self.cinfo.{name} and return it.
    def sum(self, name):
        return reduce(lambda tot, ci: tot + getattr(ci, name), self.cinfo, 0)

    def format(self, tf) -> None:
        for ci in self.cinfo:
            if not ci.include:
                continue

            tf.addText(ci.name, fs=14, style=pml.BOLD | pml.UNDERLINED)

            if self.inf[self.INF_BASIC].selected:
                tf.addText(
                    _("Speeches: {}, Lines: {} %{:.2f}, per speech: {:.2f}").format(
                        ci.speechCnt,
                        ci.lineCnt,
                        util.pctf(ci.lineCnt, self.totalLineCnt),
                        util.safeDiv(ci.lineCnt, ci.speechCnt),
                    )
                )

                tf.addText(
                    _("Words: {}, per speech: {:.2f}, characters per: {:.2f}").format(
                        ci.wordCnt,
                        util.safeDiv(ci.wordCnt, ci.speechCnt),
                        util.safeDiv(ci.wordCharCnt, ci.wordCnt),
                    )
                )

            if self.inf[self.INF_PAGES].selected:
                tf.addWrappedText(
                    _("Pages: {}, list: {}").format(len(ci.pages), ci.pages), "       "
                )

            if self.inf[self.INF_LOCATIONS].selected:
                tf.addSpace(2.5)

                for it in util.sortDict(ci.scenes):
                    tf.addText("%3d %s" % (it[1], it[0]), x=tf.margin * 2.0, fs=10)

            tf.addSpace(5.0)



# information about one character
class CharInfo:
    def __init__(self, name, sp):
        self.name = name

        self.speechCnt = 0
        self.lineCnt = 0
        self.wordCnt = 0
        self.wordCharCnt = 0
        self.scenes = {}
        self.include = True
        self.pages = PageList(sp.getPageNumbers())


def cmpfunc(a, b):
    return (a > b) - (a < b)


def cmpLines(c1, c2):
    ret = cmpfunc(c2.lineCnt, c1.lineCnt)

    if ret != 0:
        return ret
    else:
        return cmpfunc(c1.name, c2.name)
