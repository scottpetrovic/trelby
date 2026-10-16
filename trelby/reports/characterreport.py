import trelby.pdf.pml as pml
import trelby.screenplay.speeches as speeches
import trelby.reports.textreport as textreport
import trelby.textutil as textutil
import trelby.util as util
from trelby.ui.pagelist import PageList


class CharacterReport(textreport.TextReport):
    margin = 20.0

    options = [
        ("basic", lambda: _("Basic information")),
        ("pages", lambda: _("Page list")),
        ("locations", lambda: _("Location list")),
    ]

    def __init__(self, sp):
        super().__init__(sp)

        # key = character name, value = CharInfo
        chars = {}

        # what counts as a speech, and as a spoken line, is described in
        # screenplay/speeches.py
        for speech in speeches.iterSpeeches(sp):
            ci = chars.get(speech.name)
            if not ci:
                ci = CharInfo(speech.name, sp)
                chars[speech.name] = ci

            scene = speeches.sceneName(sp, speech.scene)
            ci.scenes[scene] = ci.scenes.get(scene, 0) + len(speech.dialogue)

            ci.speechCnt += 1

            for i in speech.dialogue:
                ci.lineCnt += 1

                words = textutil.splitToWords(sp.lines[i].text)

                ci.wordCnt += len(words)
                ci.wordCharCnt += sum(len(w) for w in words)

                ci.pages.addPage(sp.line2pageLabel(i))

        # list of CharInfo objects, the most lines first
        self.cinfo = sorted(chars.values(), key=lambda ci: (-ci.lineCnt, ci.name))

        self.totalSpeechCnt = self.sum("speechCnt")
        self.totalLineCnt = self.sum("lineCnt")
        self.totalWordCnt = self.sum("wordCnt")
        self.totalWordCharCnt = self.sum("wordCharCnt")

    # calculate total sum of self.cinfo.{name} and return it.
    def sum(self, name):
        return sum(getattr(ci, name) for ci in self.cinfo)

    def format(self, tf) -> None:
        for ci in self.cinfo:
            if not ci.include:
                continue

            tf.addText(ci.name, fs=14, style=pml.BOLD | pml.UNDERLINED)

            if self.opts["basic"]:
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

            if self.opts["pages"]:
                tf.addWrappedText(
                    _("Pages: {}, list: {}").format(len(ci.pages), ci.pages), "       "
                )

            if self.opts["locations"]:
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

