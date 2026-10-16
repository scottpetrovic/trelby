from types import SimpleNamespace
from unittest import mock

import tests.u as u
import trelby.translations as translations
import trelby.dialogs.watermarkdlg as watermarkdlg

_ = translations.trelby_translations_load()


def entry(value):
    return SimpleNamespace(GetValue=lambda: value)


# stands in for the dialog: OnGenerate comes from WatermarkDlg, the
# controls are plain values
class FakeDlg:
    def __init__(self, sp, items):
        self.sp = sp
        self.itemsEntry = entry(items)
        self.commonMark = entry("")
        self.dirEntry = entry("/out")
        self.markSize = entry(40)
        self.filenamePrefix = entry("script")

    def __getattr__(self, name):
        return watermarkdlg.WatermarkDlg.__dict__[name].__get__(self)


# the file name used to be made from the unstripped line, so surrounding
# spaces ended up in it as dashes
def testFileNamesAreStripped():
    sp = u.load()
    dlg = FakeDlg(sp, " Jane Doe \nBob\n\n")

    with (
        mock.patch.object(watermarkdlg.fileio, "writeToFile", return_value=True) as w,
        mock.patch.object(watermarkdlg.wx, "MessageBox"),
    ):
        dlg.OnGenerate(None)

    names = sorted(call.args[0] for call in w.call_args_list)
    assert names == ["/out/script-Bob.pdf", "/out/script-Jane-Doe.pdf"]
