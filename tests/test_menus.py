import tests.u as u
import trelby.commands as commands
import trelby.ui.menus as menus
import trelby.screenplay as screenplay
import trelby.translations as translations
import trelby.ui.trelbyctrl as trelbyctrl
import trelby.ui.trelbyframe as trelbyframe

_ = translations.trelby_translations_load()
u.init()

# the menus and keyboard commands (menus.py, commands.py) must agree with
# the code that runs them

# keyboard commands that are listed in Help / Commands, with a key, but
# that nothing runs. PrintScript (CTRL+P) has never had a handler.
UNHANDLED = {"PrintScript"}


def actions():
    return menus.allActions(*menus.makeTable())


def actionMap():
    return {a.name: a for a in actions()}


# the code an action runs must exist
def checkRunnable(a):
    run = a.run

    if isinstance(run, menus.OnFrame):
        assert callable(getattr(trelbyframe.MyFrame, run.method, None)), a.name
    else:
        assert isinstance(run, menus.OnScript), a.name
        assert callable(run.func), a.name


def testEveryActionHasAHandler():
    for a in actions():
        checkRunnable(a)


def testMenuItemsHaveIdsAndLabels():
    def check(items):
        for it in items:
            if isinstance(it, menus.Menu):
                assert it.label and it.mnemonic

                if isinstance(it.items, str):
                    assert it.items in ("recent", "language")
                else:
                    check(it.items)
            elif it is not menus.SEP:
                assert it.id is not None, it.name
                assert it.label, it.name

    check(menus.makeTable()[0])


def testNamesAndIdsAreUnique():
    acts = actions()
    names = [a.name for a in acts]
    ids = [int(a.id) for a in acts if a.id is not None]

    assert len(names) == len(set(names))
    assert len(ids) == len(set(ids))


# every keyboard command is run by something: a menu command by the Action
# of the same name, the others by MyCtrl.runCommand
def testEveryKeyCommandHasAHandler():
    acts = actionMap()

    for cmd in commands.defaultCommands():
        if cmd.name in UNHANDLED:
            assert cmd.name not in acts
            assert not hasattr(trelbyctrl.MyCtrl, "cmd" + cmd.name)

            continue

        if cmd.isMenu:
            assert cmd.name in acts, cmd.name
            checkRunnable(acts[cmd.name])
        else:
            assert (cmd.name in trelbyctrl.EDITOR_COMMANDS) or callable(
                getattr(trelbyctrl.MyCtrl, "cmd" + cmd.name, None)
            ), cmd.name


def testEditorCommandsExist():
    for name, method in trelbyctrl.EDITOR_COMMANDS.items():
        assert callable(getattr(screenplay.Editor, method, None)), name


# a fixed menu command's key is its menu item's accelerator, so the two
# must match
def testFixedMenuCommandsMatchAccelerators():
    acts = actionMap()

    for cmd in commands.defaultCommands():
        if cmd.isFixed and cmd.isMenu and (cmd.name not in UNHANDLED):
            a = acts[cmd.name]
            key = commands.keys.Key.fromInt(cmd.defKeys[0])

            assert a.accel, cmd.name
            assert key.toStr().replace("+", "-").upper() == a.accel.upper(), (
                cmd.name,
                key.toStr(),
                a.accel,
            )


def testElemTypesCoverAllTypes():
    types = menus.elemTypes()
    acts = actionMap()

    assert {lt for lt, *rest in types} == {
        screenplay.SCENE,
        screenplay.ACTION,
        screenplay.CHARACTER,
        screenplay.DIALOGUE,
        screenplay.PAREN,
        screenplay.TRANSITION,
        screenplay.SHOT,
        screenplay.ACTBREAK,
    }

    for lt, id, label, mnemonic, cmdName in types:
        assert cmdName in trelbyctrl.EDITOR_COMMANDS
        assert acts["ElemTo" + cmdName[len("ChangeTo") :]].id == id


def mnemonics(items):
    return [it.mnemonic.lower() for it in items if it is not menus.SEP]


def testProductionMenu():
    bar = menus.makeTable()[0]
    m = {it.label: it for it in bar}["Production"]
    names = [it.name for it in m.items if it is not menus.SEP]

    assert [it.label for it in bar] == [
        "File",
        "Edit",
        "Script",
        "View",
        "Tools",
        "Reports",
        "Production",
        "Language",
        "Help",
    ]
    assert len(set(mnemonics(bar))) == len(bar)
    assert len(set(mnemonics(m.items))) == len(names)

    assert names == [
        "ToggleRevisionMode",
        "RevisionsDlg",
        "ToggleSceneNumbers",
        "ToggleSceneLocks",
        "OmitScene",
        "TogglePageLocks",
        "ExportRevisedPages",
        "ClearRevisionMarks",
    ]


class FakeCtrl:
    def __init__(self, ed):
        self.ed = ed
        self.sp = ed.sp
        self.updates = 0

    def updateScreen(self):
        self.updates += 1


# showing scene numbers changes no wrapping, so it keeps the undo history
def testToggleSceneNumbers():
    ed = u.loadEditor()
    ed.cmd("addChar", char="x")
    ed.sp.markChanged(False)
    ctrl = FakeCtrl(ed)
    a = actionMap()["ToggleSceneNumbers"]
    shown = ed.sp.cfg.pdfShowSceneNumbers

    a.run.func(None, ctrl)

    assert ed.sp.cfg.pdfShowSceneNumbers == (not shown)
    assert a.isChecked(None, ctrl) == (not shown)
    assert ed.sp.hasChanged
    assert ed.undoHistory.canUndo()
    assert ctrl.updates == 1

    a.run.func(None, ctrl)
    assert ed.sp.cfg.pdfShowSceneNumbers == shown


class FakeLockCtrl(FakeCtrl):
    def makeLineVisible(self, line):
        pass


# locking pages and scene numbers are check items that lock and unlock
def testToggleLocks():
    for name, isLocked in [
        ("TogglePageLocks", lambda sp: sp.hasPageLocks()),
        ("ToggleSceneLocks", lambda sp: sp.hasAnySceneLock()),
    ]:
        ed = u.loadEditor()
        ctrl = FakeLockCtrl(ed)
        a = actionMap()[name]

        assert not isLocked(ed.sp)
        assert not a.isChecked(None, ctrl)

        a.run.func(None, ctrl)
        assert isLocked(ed.sp)
        assert a.isChecked(None, ctrl)

        a.run.func(None, ctrl)
        assert not isLocked(ed.sp)
        assert not a.isChecked(None, ctrl)
        assert ctrl.updates == 2
