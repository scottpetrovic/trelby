# Script -> Compare scripts: a PDF showing the differences between two
# scripts.

import difflib

import trelby.pdf.writer as pdf
import trelby.pdf.pml as pml
import trelby.util as util
from trelby.screenplay.export.text import generateText


# compare sp to sp2 (both Screenplays), return a PDF file (as a
# string) of the differences, or None if the scripts are identical.
def compareScripts(sp, sp2) -> bytes:
    s1 = generateText(sp, False).split("\n")
    s2 = generateText(sp2, False).split("\n")

    dltTmp = difflib.unified_diff(s1, s2, lineterm="")

    # get rid of stupid delta generator object that doesn't allow
    # subscription or anything else really. also expands hunk
    # separators into three lines.
    #
    # the first three lines skipped are the "---" / "+++" headers and
    # the first "@@" hunk header. each later "@@" becomes the
    # pseudo-lines "1", "2", "3"; see the drawing loop below.
    dlt = []
    i = 0
    for s in dltTmp:
        if i >= 3:
            if s[0] == "@":
                dlt.extend(["1", "2", "3"])
            else:
                dlt.append(s)

        i += 1

    if len(dlt) == 0:
        return None

    dltTmp = dlt

    # now, generate changed-lines for single-line diffs
    dlt = []
    for i in range(len(dltTmp)):
        s = dltTmp[i]

        dlt.append(s)

        # this checks that we've just added a sequence of lines whose
        # first characters are " -+", where " " means '"not -" or
        # missing line', and that we're either at end of list or next
        # line does not start with "+".

        if (
            (s[0] == "+")
            and (i != 0)
            and (dltTmp[i - 1][0] == "-")
            and ((i == 1) or (dltTmp[i - 2][0] != "-"))
            and ((i == (len(dltTmp) - 1)) or (dltTmp[i + 1][0] != "+"))
        ):

            # generate line with "^" character at every position that
            # the lines differ

            s1 = dltTmp[i - 1]
            s2 = dltTmp[i]

            minCnt = min(len(s1), len(s2))
            maxCnt = max(len(s1), len(s2))

            res = "^"

            for i in range(1, minCnt):
                if s1[i] != s2[i]:
                    res += "^"
                else:
                    res += " "

            res += "^" * (maxCnt - minCnt)

            dlt.append(res)

    tmp = [
        "  Color information:",
        "1",
        "-  Deleted lines",
        "+  Added lines",
        "^  Positions of single-line changes (marked with ^)",
        "1",
        "2",
        "2",
        "3",
    ]
    tmp.extend(dlt)
    dlt = tmp

    cfg = sp.cfg
    chY = util.getTextHeight(cfg.fontSize)

    doc = pml.Document(cfg.paperWidth, cfg.paperHeight)

    # how many lines put on current page
    y = 0

    pg = pml.Page(doc)

    # we need to gather text ops for each page into a separate list
    # and add that list to the page only after all other ops are
    # added, otherwise the colored bars will be drawn partially over
    # some characters.
    textOps = []

    # each entry's first character says how to draw it: "1" and "3"
    # are blank lines and "2" a grey bar (together, a separator between
    # hunks), and "-", "+" and "^" lines get a red, green or yellow
    # background. the rest of the entry is the text.
    for s in dlt:

        if y >= cfg.linesOnPage:
            pg.ops.extend(textOps)
            doc.add(pg)

            pg = pml.Page(doc)

            textOps = []
            y = 0

        if s[0] == "1":
            pass

        elif s[0] == "3":
            pass

        elif s[0] == "2":
            pg.add(pml.PDFOp("0.75 g"))
            w = 50.0
            pg.add(
                pml.RectOp(
                    doc.w / 2.0 - w / 2.0,
                    cfg.marginTop + y * chY + chY / 4,
                    w,
                    chY / 2.0,
                )
            )
            pg.add(pml.PDFOp("0.0 g"))

        else:
            color = ""

            if s[0] == "-":
                color = "1.0 0.667 0.667"
            elif s[0] == "+":
                color = "0.667 1.0 0.667"
            elif s[0] == "^":
                color = "1.0 1.0 0.467"

            if color:
                pg.add(pml.PDFOp("%s rg" % color))
                pg.add(
                    pml.RectOp(
                        cfg.marginLeft,
                        cfg.marginTop + y * chY,
                        doc.w - cfg.marginLeft - 5.0,
                        chY,
                    )
                )
                pg.add(pml.PDFOp("0.0 g"))

            textOps.append(
                pml.TextOp(
                    s[1:], cfg.marginLeft, cfg.marginTop + y * chY, cfg.fontSize
                )
            )

        y += 1

    pg.ops.extend(textOps)
    doc.add(pg)

    return pdf.generate(doc)
