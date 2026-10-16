# ut:ignore
# text dumps of the reports' output, compared against the files in
# tests/fixtures/reports/ by test_reportoutput.py. run this (from the repo
# root) to rewrite them after an intended change to a report:
#
#   .venv/Scripts/python -m tests.reportdump

import os

import tests.u as u
import trelby.reports.characterreport as characterreport
import trelby.reports.dialoguechart as dialoguechart
import trelby.reports.locationreport as locationreport
import trelby.reports.scenereport as scenereport
import trelby.reports.scriptreport as scriptreport
import trelby.translations as translations

_ = translations.trelby_translations_load()

DIR = os.path.join(os.path.dirname(__file__), "fixtures", "reports")

# the scripts the reports are run on, relative to tests/fixtures
SCRIPTS = ["test.trelby", "reports/edge.trelby"]


def textReports(sp):
    return {
        "scene": scenereport.SceneReport(sp),
        "location": locationreport.LocationReport(scenereport.SceneReport(sp)),
        "character": characterreport.CharacterReport(sp),
        "script": scriptreport.ScriptReport(sp),
    }


# one line per drawing operation, with its attributes
def dumpDoc(doc):
    out = ["doc %.2f x %.2f" % (doc.w, doc.h)]

    for i, pg in enumerate(doc.pages):
        out.append("page %d" % i)

        for op in pg.ops:
            attrs = []

            for k, v in sorted(vars(op).items()):
                if isinstance(v, float):
                    v = "%.3f" % v
                elif isinstance(v, list):
                    v = [tuple("%.3f" % c for c in p) for p in v]

                attrs.append("%s=%s" % (k, v))

            out.append("  %s %s" % (type(op).__name__, " ".join(attrs)))

    return "\n".join(out) + "\n"


# the dialogue chart's data, and its layout in each sort order
def dumpChart(sp):
    out = []
    chart = dialoguechart.DialogueChart(sp)

    for ci in sorted(chart.cinfo, key=lambda ci: ci.name):
        out.append(
            "char %s first=%d last=%d lines=%d"
            % (ci.name, ci.firstPage, ci.lastPage, ci.lineCnt)
        )

    for i, pi in enumerate(chart.pages):
        out.append(
            "page %d types=%s speakers=%s"
            % (i, sorted(pi.lineCounts.items()), sorted(pi.speakers.items()))
        )

    out.append(
        "with 10 or more lines: %s" % sorted(ci.name for ci in chart.getChars(10))
    )

    for name, label, key in dialoguechart.SORTS:
        out.append(dumpDoc(dialoguechart.generateDoc(chart, sp.cfg, [name])))

    return "\n".join(out)


# return {file name: contents} of every dump for the script 'name'
def dumps(name):
    sp = u.load(name)
    base = os.path.basename(name).replace(".trelby", "")
    ret = {}

    for key, report in textReports(sp).items():
        html = report.generateHtml()
        ret["%s-%s.html" % (base, key)] = html.replace("<br>", "<br>\n")

    ret["%s-dialoguechart.txt" % base] = dumpChart(sp)

    return ret


def main():
    os.makedirs(DIR, exist_ok=True)

    for name in SCRIPTS:
        for fname, s in dumps(name).items():
            path = os.path.join(DIR, fname)

            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(s)

            print("wrote", fname)


if __name__ == "__main__":
    main()
