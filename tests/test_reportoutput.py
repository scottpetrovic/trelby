import os

import pytest

import tests.reportdump as reportdump

# the reports' output on the scripts in reportdump.SCRIPTS must stay the
# same as in tests/fixtures/reports/. after an intended change, rewrite
# those files with ".venv/Scripts/python -m tests.reportdump" and check
# the diff.


@pytest.mark.parametrize("name", reportdump.SCRIPTS)
def testReportOutput(name):
    for fname, s in reportdump.dumps(name).items():
        with open(os.path.join(reportdump.DIR, fname), encoding="utf-8") as f:
            assert s == f.read(), fname
