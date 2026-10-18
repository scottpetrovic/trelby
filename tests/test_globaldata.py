import builtins
import os
from unittest import mock

import tests.u as u
import trelby.ui.globaldata as globaldata
import trelby.misc as misc
import trelby.mypickle as mypickle
import trelby.translations as translations

translations.trelby_translations_load()


def italian(s):
    return {"Files": "File"}.get(s, s)


def testRenameOldFilesKey():
    vals = mypickle.Vars.makeVals(
        "Zoom:100\nFile:2\nFile/1:/a.trelby\nFile/2:/b.trelby\n"
    )

    with mock.patch.object(builtins, "_", italian):
        globaldata.renameOldFilesKey(vals)

    assert vals == {
        "Zoom": "100",
        "Files": "2",
        "Files/1": "/a.trelby",
        "Files/2": "/b.trelby",
    }


def testRenameOldFilesKeyLeavesNewKey():
    s = "Files:1\nFiles/1:/new.trelby\nFile:1\nFile/1:/old.trelby\n"
    vals = mypickle.Vars.makeVals(s)

    with mock.patch.object(builtins, "_", italian):
        globaldata.renameOldFilesKey(vals)

    assert vals == mypickle.Vars.makeVals(s)


def testRenameOldFilesKeyEnglish():
    s = "Files:1\nFiles/1:/a.trelby\n"
    vals = mypickle.Vars.makeVals(s)
    globaldata.renameOldFilesKey(vals)

    assert vals == mypickle.Vars.makeVals(s)


# makeConfDir used to have an invalid except clause, which raised a
# TypeError instead of showing the error
def testMakeConfDirError(tmp_path):
    u.init()
    path = str(tmp_path / "conf")

    with (
        mock.patch.object(misc, "confPath", path, create=True),
        mock.patch.object(os, "mkdir", side_effect=PermissionError(13, "Denied")),
        mock.patch.object(globaldata.wx, "MessageBox") as box,
    ):
        globaldata.GlobalData.makeConfDir(None)

    assert box.call_count == 1
    assert path in box.call_args[0][0]
    assert "Denied" in box.call_args[0][0]


# the beat board has its own zoom level, which the zoom commands step
# through while it's shown
def testBoardZoom():
    gd = globaldata.GlobalData.__new__(globaldata.GlobalData)
    gd.zoom = 100
    gd.boardZoom = 50
    gd.showBeatBoard = False
    assert gd.currentZoom() == 100
    assert gd.getZoomStep(-1) == 90

    gd.showBeatBoard = True
    assert gd.currentZoom() == 50
    assert gd.getZoomStep(-1) == 33
    assert gd.getZoomStep(1) == 67

    gd.boardZoom = globaldata.GlobalData.BOARD_ZOOM_LEVELS[0]
    assert gd.getZoomStep(-1) == gd.boardZoom
