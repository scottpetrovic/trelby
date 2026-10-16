import builtins
import gc
import os
from types import SimpleNamespace
from unittest import mock

import tests.u as u
import trelby.gutil as gutil
import trelby.misc as misc
import trelby.translations as translations
import trelby.util as util

translations.trelby_translations_load()

# regression tests for small bugs in util.py


def testLoadFileMemoryError():
    u.init()

    class TooBig:
        def read(self, size):
            raise MemoryError("too big")

        def close(self):
            pass

    with mock.patch.object(builtins, "open", lambda *args, **kw: TooBig()):
        assert gutil.loadFile("x.trelby", None) is None


def testTimerDev(capsys):
    t = util.TimerDev("thing")
    del t
    gc.collect()

    assert "thing took " in capsys.readouterr().out


def testUnixPDFViewer():
    u.init()

    with (
        mock.patch.object(misc, "isMac", False),
        mock.patch.object(misc, "isUnix", True),
        mock.patch.object(misc, "isWindows", False),
        mock.patch.object(util, "fileExists", lambda p: p == "/usr/bin/xdg-open"),
    ):
        assert util.getPDFViewer() == ("/usr/bin/xdg-open", "")


# when the configured viewer is missing, the warning names both it and the
# one used instead
def testShowPDFExternalFallbackMessage():
    u.init()

    cfgGl = SimpleNamespace(pdfViewerPath="/no/such/viewer", pdfViewerArgs="")

    with (
        mock.patch.object(misc, "isMac", False),
        mock.patch.object(util, "fileExists", lambda p: False),
        mock.patch.object(util, "getPDFViewer", lambda: ("/found/viewer", "")),
        mock.patch.object(gutil.wx, "MessageBox") as box,
        mock.patch.object(os, "spawnv") as spawnv,
    ):
        gutil.showPDFExternal("/tmp/x.pdf", cfgGl, None)

    msg = box.call_args[0][0]
    assert "/no/such/viewer" in msg
    assert "/found/viewer" in msg
    assert "%s" not in msg
    assert spawnv.call_count == 1
