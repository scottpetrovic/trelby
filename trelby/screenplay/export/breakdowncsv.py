# the production breakdown (see screenplay/breakdown.py) as CSV, a row per
# scene and a column per category, for importing into scheduling software
# or a spreadsheet. a cell's elements are separated by "; ".

import csv
import io

import trelby.screenplay.breakdown as breakdown


def generateBreakdownCSV(sp, castSpeakers=True):
    # with a byte order mark, without which Excel takes the file as being
    # in the system's code page
    out = io.StringIO()
    out.write("﻿")
    w = csv.writer(out, lineterminator="\r\n")

    w.writerow(
        [
            _("Scene"),
            _("Heading"),
            _("Int/Ext"),
            _("Location"),
            _("Time"),
            _("Page"),
            _("Pages"),
            _("Eighths"),
        ]
        + [c.label() for c in breakdown.CATEGORIES]
    )

    for sb in sp.getBreakdown(castSpeakers):
        w.writerow(
            [
                sb.number,
                sb.heading,
                sb.intExt,
                sb.place,
                sb.time,
                sb.page,
                breakdown.eighthsText(sb.eighths),
                sb.eighths,
            ]
            + ["; ".join(sb.names(c.key)) for c in breakdown.CATEGORIES]
        )

    return out.getvalue()
