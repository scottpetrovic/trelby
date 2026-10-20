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


# Actions that do something else on the beat board must be blocked there
# otherwise, and run a method the board has
def testOnBoardActions():
    import trelby.ui.beatboardview as beatboardview

    names = actionMap()

    for name, method in menus.ON_BOARD.items():
        assert name in names and name in menus.SCRIPT_ONLY, name
        assert callable(getattr(beatboardview.BeatBoardView, method, None)), name


# while the board is shown, Paste pastes on it instead of in the script,
# and stays enabled, and Copy does nothing
def testPasteOnBoard():
    class Board:
        pasted = 0

        def paste(self):
            self.pasted += 1

    class Panel:
        boardShown = True
        board = Board()
        ctrl = None

    class Frame:
        panel = Panel()

    class Event:
        def Enable(self, on):
            self.enabled = on

    frame = Frame()
    acts = actionMap()
    ran = []

    for name in ("Paste", "Copy"):
        acts[name].run = lambda f, name=name: ran.append(name)
        menus.runAction(frame, acts[name])

    assert frame.panel.board.pasted == 1
    assert ran == []

    for name, enabled in (("Paste", True), ("Copy", False)):
        e = Event()
        menus.onUpdateUI(frame, e, acts[name])
        assert e.enabled == enabled, name

    # with the script shown, Paste runs normally
    frame.panel.boardShown = False
    menus.runAction(frame, acts["Paste"])
    assert ran == ["Paste"]


# while the Home screen is shown, only the Actions that don't need a script
# run, and the others are greyed out
def testHomeBlocksScriptActions():
    class Panel:
        boardShown = False
        ctrl = None

    class Sprint:
        def isActive(self):
            return False

        def isPaused(self):
            return False

    class Frame:
        homeShown = True
        panel = Panel()
        sprint = Sprint()

    class Event:
        def Enable(self, on):
            self.enabled = on

        def Check(self, on):
            self.checked = on

    frame = Frame()
    acts = actionMap()
    ran = []

    for a in acts.values():
        a.run = lambda f, name=a.name: ran.append(name)

    allowed = [
        "NewScript",
        "NewScript-sitcom",
        "OpenScript",
        "ImportFdx",
        "Quit",
        "ToggleSprint",
        "WritingGoals",
    ]
    blocked = ["Copy", "SaveScript", "CloseScript", "ZoomIn", "ToggleRevisionMode"]

    for name in allowed + blocked:
        menus.runAction(frame, acts[name])

        e = Event()
        menus.onUpdateUI(frame, e, acts[name])
        assert e.enabled == (name in allowed), name

    assert ran == allowed

    # with a script shown, they all run
    frame.homeShown = False
    menus.runAction(frame, acts["Copy"])
    assert ran[-1] == "Copy"


# every Action ON_HOME allows exists
def testOnHomeActionsExist():
    names = actionMap()

    for name in menus.ON_HOME:
        assert name in names, name


# CTRL-SPACE switches to the beat board, a fixed key: a config saved when
# it was Set mark's loses it there, keeping Set mark's other keys
def testFixedKeyTakenFromOldBinding():
    import trelby.config as config

    space = commands.keys.Key(commands.keys.WXK_SPACE, ctrl=True).toInt()
    f8 = commands.keys.Key(commands.keys.WXK_F8, ctrl=True).toInt()

    cfg = config.ConfigGlobal()
    cfg.load(
        "Command/SetMark/Keys:2\n"
        "Command/SetMark/Keys/1:%d\n"
        "Command/SetMark/Keys/2:%d\n" % (space, f8)
    )

    cmds = {cmd.name: cmd for cmd in cfg.commands}
    assert cmds["SetMark"].keys == [f8]
    assert cmds["ToggleBeatBoard"].keys == [space]
    assert cfg.getKeyMap().get(space) is None


# CTRL+SHIFT+Space moved from Insert non-breaking space to the side panel:
# older configs (which have every command's keys) get it moved once, unless
# it was on another command, and newer ones are left alone
def testSidePanelKeyMovedFromNbsp():
    import trelby.config as config

    key = commands.SIDE_PANEL_KEY
    f8 = commands.keys.Key(commands.keys.WXK_F8, ctrl=True).toInt()

    def load(s):
        cfg = config.ConfigGlobal()
        cfg.load(s)

        return {cmd.name: cmd.keys for cmd in cfg.commands}

    nbspAndPanel = (
        "Command/InsertNbsp/Keys:2\n"
        "Command/InsertNbsp/Keys/1:%d\n"
        "Command/InsertNbsp/Keys/2:%d\n"
        "Command/ToggleSidePanel/Keys:1\n"
        "Command/ToggleSidePanel/Keys/1:0\n" % (key, f8)
    )

    cmds = load(nbspAndPanel)
    assert cmds["InsertNbsp"] == [f8]
    assert cmds["ToggleSidePanel"] == [key]

    # the user had moved it to another command
    cmds = load(
        "Command/InsertNbsp/Keys:1\n"
        "Command/InsertNbsp/Keys/1:%d\n"
        "Command/SetMark/Keys:1\n"
        "Command/SetMark/Keys/1:%d\n"
        "Command/ToggleSidePanel/Keys:1\n"
        "Command/ToggleSidePanel/Keys/1:0\n" % (f8, key)
    )
    assert cmds["SetMark"] == [key]
    assert cmds["ToggleSidePanel"] == []

    # a config saved since then keeps what it has
    cmds = load("KeysVersion:1\n" + nbspAndPanel)
    assert cmds["InsertNbsp"] == [key, f8]
    assert cmds["ToggleSidePanel"] == []

    # and a new one gets the defaults
    cmds = load("")
    assert cmds["InsertNbsp"] == []
    assert cmds["ToggleSidePanel"] == [key]
