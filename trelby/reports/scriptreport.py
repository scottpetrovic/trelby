import trelby.config as config
import trelby.pdf.pml as pml
import trelby.reports.scenereport as scenereport
import trelby.screenplay as screenplay
import trelby.screenplay.speeches as speeches
import trelby.reports.textreport as textreport
import trelby.textutil as textutil
import trelby.util as util


class ScriptReport(textreport.TextReport):
    def __init__(self, sp):
        super().__init__(sp)
        self.scenes = scenereport.splitScenes(sp)

        # the characters with a speech
        self.speakers = {s.name for s in speeches.iterSpeeches(sp)}

    def format(self, tf) -> None:
        ls = self.sp.lines

        total = len(ls)
        tf.addText(_("Total lines in script: {}").format(total))

        tf.addSpace(2.0)

        for t in config.getTIs():
            cnt = sum([1 for line in ls if line.lt == t.lt])
            tf.addText(
                "        %13s:  %4d (%d%%)" % (t.name, cnt, util.pct(cnt, total))
            )

        tf.addSpace(4.0)

        intLines = sum(
            [
                si.lines
                for si in self.scenes
                if textutil.upper(si.name).startswith("INT.")
            ]
        )
        extLines = sum(
            [
                si.lines
                for si in self.scenes
                if textutil.upper(si.name).startswith("EXT.")
            ]
        )

        tf.addText(
            _("Interior / exterior scenes")
            + ": %d%% / %d%%"
            % (
                util.pct(intLines, intLines + extLines),
                util.pct(extLines, intLines + extLines),
            )
        )

        tf.addSpace(4.0)

        lineSeq = [si.lines for si in self.scenes]

        tf.addText(
            _("Max / avg. scene length in lines")
            + ": %d / %.2f" % (max(lineSeq), sum(lineSeq) / len(lineSeq))
        )

        # lengths of action elements
        actions = []

        # length of current action element
        curLen = 0

        for ln in ls:
            if curLen > 0:
                if ln.lt == screenplay.ACTION:
                    curLen += 1

                    if ln.lb == screenplay.LB_LAST:
                        actions.append(curLen)
                        curLen = 0
                else:
                    actions.append(curLen)
                    curLen = 0
            else:
                if ln.lt == screenplay.ACTION:
                    curLen = 1

        if curLen > 0:
            actions.append(curLen)

        tf.addSpace(4.0)

        # avoid divide-by-zero
        if len(actions) > 0:
            maxA = max(actions)
            avgA = sum(actions) / float(len(actions))
        else:
            maxA = 0
            avgA = 0.0

        tf.addText(
            _("Max / avg. action element length in lines")
            + ": %d / %.2f" % (maxA, avgA)
        )

        tf.addSpace(4.0)

        tf.addText(_("Speaking characters") + ": %d" % len(self.speakers))

