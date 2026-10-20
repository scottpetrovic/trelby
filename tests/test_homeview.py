import os
import time

import pytest
import wx

import tests.u as u
import trelby.config as config
import trelby.translations as translations
import trelby.ui.configgui as configgui
import trelby.ui.gutil as gutil
import trelby.ui.themes as themes
import trelby.writinglog as writinglog

_ = translations.trelby_translations_load()

import trelby.ui.homeview as homeview  # noqa: E402
import trelby.ui.menus as menus  # noqa: E402
import trelby.ui.mrufiles as mrufiles  # noqa: E402

# the Home screen (ui/homeview.py), shown while no script is open: its rows,
# what clicking them and the keys do, and drawing it in every theme


@pytest.fixture(scope="module")
def app():
    a = wx.App(False)
    gutil.init()
    yield a
    a.Destroy()


# stand-ins for the GlobalData and the main window the view acts through
class GD:
    def __init__(self, theme=None):
        u.init()
        cfgGl = config.ConfigGlobal()

        if theme:
            cfgGl.theme = theme

        self.cfgGl = cfgGl
        self.cfgGui = configgui.ConfigGui(cfgGl, 100)
        self.mru = mrufiles.MRUFiles(5)
        self.writingLog = writinglog.WritingLog()


class Owner:
    def __init__(self, gd):
        self.gd = gd
        menuTable, others = menus.makeTable()
        self.actions = {a.name: a for a in menus.allActions(menuTable, others)}
        self.ran = []
        self.opened = []
        self.removed = []

    def runAction(self, name):
        self.ran.append(name)

    def openRecent(self, i):
        self.opened.append(i)

    # like MyFrame's, refreshing the view
    def openPath(self, path):
        self.opened.append(path)

    def removeRecent(self, i):
        self.removed.append(i)
        self.gd.mru.remove(i)
        self.view.refresh()


# the time the view is shown at, 15:00 on 20 October 2026
NOW = time.mktime((2026, 10, 20, 15, 0, 0, 0, 0, -1))


# a session of 'words' words in the script at path, starting 'days' days
# before NOW, at hour h
def session(days, words, path="/s/Pilot.trelby", h=10, active=1800):
    start = NOW - days * 86400 - (15 - h) * 3600

    return writinglog.Session(
        start, start + active, path, writinglog.scriptName(path or "Untitled"),
        words, words / 250, active,
    )


@pytest.fixture
def frame(app):
    f = wx.Frame(None, size=(900, 800))
    yield f
    f.Destroy()


def makeView(frame, files=(), size=(900, 800), theme=None, sessions=(), goal=0):
    gd = GD(theme)
    gd.cfgGl.dailyGoal = goal

    for s in sessions:
        gd.writingLog.put(s)

    # added in reverse, so that they're listed in the given order
    for path in reversed(files):
        gd.mru.add(path)

    owner = Owner(gd)
    view = homeview.HomeView(frame, owner, clock=lambda: NOW)
    owner.view = view
    view.SetSize(0, 0, *size)
    view.layout()

    return view, owner


def centre(rect):
    return wx.Point(rect.x + rect.width // 2, rect.y + rect.height // 2)


def mouse(view, kind, pos):
    e = wx.MouseEvent(kind)
    e.SetPosition(pos)

    return e


def key(view, code):
    e = wx.KeyEvent(wx.wxEVT_KEY_DOWN)
    e.SetKeyCode(code)
    view.OnKeyDown(e)


# the start section's rows' kinds
def kinds(view):
    return [r.kind for r in view.rows if r.section == 0]


def testHelpers():
    assert homeview.shortcutText("CTRL-N") == "Ctrl+N"
    assert homeview.shortcutText("CTRL-SHIFT-O") == "Ctrl+Shift+O"

    assert writinglog.scriptName(os.path.join("a", "b", "Pilot.trelby")) == "Pilot"
    assert writinglog.scriptName(os.path.join("a", "Pilot.TRELBY")) == "Pilot"
    assert writinglog.scriptName("notes.txt") == "notes.txt"

    now = time.mktime((2026, 10, 20, 15, 0, 0, 0, 0, -1))
    assert homeview.changedText(now - 3600, now) == "Today 14:00"
    assert homeview.changedText(now - 3 * 86400, now) == "2026-10-17"


# the four ways to start a script, then a row per recent file, the gone
# ones dimmed
def testRows(frame, tmp_path):
    there = tmp_path / "Pilot.trelby"
    there.write_text("")
    gone = str(tmp_path / "Gone.trelby")

    view, owner = makeView(frame, [str(there), gone])

    assert kinds(view) == [homeview.ACTION, homeview.MENU] * 2 + [homeview.RECENT] * 2
    assert [r.value for r in view.rows if r.kind == homeview.ACTION and r.section == 0] == [
        "NewScript",
        "OpenScript",
    ]
    assert view.rows[0].note == "Ctrl+N"

    templates = view.rows[1].value
    assert templates and all(n.startswith("NewScript-") for n in templates)
    assert "ImportScript" in view.rows[3].value

    pilot, goneRow = [r for r in view.rows if r.kind == homeview.RECENT]
    assert (pilot.label, pilot.detail, pilot.dim) == ("Pilot", str(tmp_path), False)
    assert (goneRow.label, goneRow.note, goneRow.dim) == ("Gone", _("Not found"), True)

    # nothing overlaps, top to bottom, and all inside the section
    for a, b in zip(view.rows, view.rows[1:]):
        assert a.rect.GetBottom() < b.rect.y

    for r in view.rows:
        section = view.sections[r.section]
        assert section.Contains(r.rect.GetTopLeft())
        assert section.Contains(r.rect.GetBottomRight())


def testNoRecentFilesSaysSo(frame):
    view, owner = makeView(frame)

    assert kinds(view) == [homeview.ACTION, homeview.MENU] * 2
    assert _("The scripts you open will be listed here.") in [
        t[0] for t in view.texts
    ]


# a click runs the row's Action, or opens the recent file
def testClicks(frame, tmp_path):
    view, owner = makeView(frame, [str(tmp_path / "a.trelby")])

    view.OnLeftDown(mouse(view, wx.wxEVT_LEFT_DOWN, centre(view.rows[2].rect)))
    view.OnLeftDown(mouse(view, wx.wxEVT_LEFT_DOWN, centre(view.rows[4].rect)))

    # between the rows, nothing
    view.OnLeftDown(mouse(view, wx.wxEVT_LEFT_DOWN, wx.Point(2, 2)))

    assert owner.ran == ["OpenScript"]
    assert owner.opened == [0]


# hovering a row highlights it, and a recent file's shows its path
def testHover(frame, tmp_path):
    path = str(tmp_path / "a.trelby")
    view, owner = makeView(frame, [path])

    view.OnMotion(mouse(view, wx.wxEVT_MOTION, centre(view.rows[4].rect)))
    assert view.hover == 4
    assert view.GetToolTipText() == path

    view.OnMotion(mouse(view, wx.wxEVT_MOTION, centre(view.rows[0].rect)))
    assert view.hover == 0
    assert view.GetToolTipText() == ""


# the arrow keys pick a row, Enter does what it does, and Delete takes a
# recent file off the list
def testKeys(frame, tmp_path):
    paths = [str(tmp_path / ("%s.trelby" % n)) for n in "abc"]
    view, owner = makeView(frame, paths)

    # Enter before a row has been picked does nothing
    key(view, wx.WXK_RETURN)
    assert owner.ran == []

    key(view, wx.WXK_DOWN)
    assert view.picked == 0
    key(view, wx.WXK_RETURN)
    assert owner.ran == ["NewScript"]

    key(view, wx.WXK_UP)
    assert view.picked == 0

    # the writing section's rows come after the start section's
    key(view, wx.WXK_END)
    assert view.rows[view.picked].value == "WritingGoals"
    key(view, wx.WXK_DOWN)
    assert view.rows[view.picked].value == "WritingGoals"

    key(view, wx.WXK_UP)
    key(view, wx.WXK_UP)
    assert view.picked == 6

    key(view, wx.WXK_DELETE)
    assert owner.removed == [2]
    assert len(view.rows) == 8

    # Delete on a row that's not a recent file does nothing
    key(view, wx.WXK_HOME)
    key(view, wx.WXK_DELETE)
    assert owner.removed == [2]


# in a window too low for it all, the wheel scrolls it, but not past either
# end
def testScrolling(frame, tmp_path):
    paths = [str(tmp_path / ("%d.trelby" % i)) for i in range(5)]
    view, owner = makeView(frame, paths, size=(600, 300))

    assert view.contentH > 300

    def wheel(rotation):
        e = wx.MouseEvent(wx.wxEVT_MOUSEWHEEL)
        e.SetWheelRotation(rotation)
        e.SetWheelDelta(120)
        view.OnWheel(e)

    top = view.rows[0].rect.y

    wheel(120)
    assert view.scrollY == 0

    wheel(-120)
    assert view.scrollY > 0
    assert view.rows[0].rect.y == top - view.scrollY

    for i in range(50):
        wheel(-120)

    assert view.scrollY == view.contentH - 300

    # picking the first row with the keys scrolls back up to it
    key(view, wx.WXK_HOME)
    assert view.rows[0].rect.y >= 0

    # growing the window brings the scroll position back in range
    view.SetSize(0, 0, 600, 2000)
    view.layout()
    assert view.scrollY == 0


# it draws in every theme, all on the workspace color, with no card
@pytest.mark.parametrize("theme", [t.name for t in themes.BUILTIN])
def testDraws(frame, tmp_path, theme):
    there = tmp_path / "Pilot.trelby"
    there.write_text("")
    view, owner = makeView(
        frame,
        [str(there), str(tmp_path / "Gone.trelby")],
        size=(1300, 800),
        theme=theme,
        sessions=[session(0, 412), session(1, 900), session(3, 150, path=None)],
        goal=1000,
    )
    view.hover = 0

    bmp = wx.Bitmap(1300, 800)
    dc = wx.MemoryDC(bmp)
    view.draw(dc)
    dc.SelectObject(wx.NullBitmap)

    img = bmp.ConvertToImage()
    cfgGui = owner.gd.cfgGui

    def color(x, y):
        return (img.GetRed(x, y), img.GetGreen(x, y), img.GetBlue(x, y))

    assert color(2, 2) == cfgGui.workspaceColor.Get(False)

    card = view.card
    assert color(card.x + 10, card.GetBottom() - 4) == cfgGui.workspaceColor.Get(False)

    if os.environ.get("HOMEVIEW_PNG"):
        bmp.SaveFile(
            os.path.join(os.environ["HOMEVIEW_PNG"], "home-%s.png" % theme),
            wx.BITMAP_TYPE_PNG,
        )


# the writing section: today's words, the chart's bars, the goal, and a row
# per script written in lately
def testWritingCard(frame):
    sessions = [
        session(0, 300, h=9),
        session(0, 112, path="/s/Other.trelby", h=11, active=600),
        session(1, 900),
        session(3, 150, path=None),
        # only touched: left out of the recent writing
        session(2, 0, path="/s/Touched.trelby", active=20),
    ]
    view, owner = makeView(frame, sessions=sessions, goal=1000)

    texts = [t[0] for t in view.texts]
    assert "412 words" in texts
    assert "40 min  ·  2-day streak" in texts
    assert "41% of 1,000 words" in texts
    assert "1,462 words" in texts

    kinds = [k for k, r in view.shapes]
    assert kinds.count(homeview.TRACK) == kinds.count(homeview.FILL) == 1
    assert kinds.count(homeview.TODAY_BAR) == 1
    assert kinds.count(homeview.BAR) == 2
    assert kinds.count(homeview.NO_BAR) == homeview.CHART_DAYS - 3
    assert kinds.count(homeview.GOAL_LINE) == 1

    track = [r for k, r in view.shapes if k == homeview.TRACK][0]
    fill = [r for k, r in view.shapes if k == homeview.FILL][0]
    assert fill.width == int(track.width * 0.412)

    act = [r for r in view.rows if r.kind == homeview.ACTIVITY]
    assert [(r.label, r.note) for r in act] == [
        ("Other", "112 words  ·  10 min"),
        ("Pilot", "300 words  ·  30 min"),
        ("Pilot", "900 words  ·  30 min"),
        ("Untitled", "150 words  ·  30 min"),
    ]
    assert act[0].detail.startswith("Today")
    assert act[2].detail.startswith("Yesterday")

    # clicking one opens its script; one never saved can't be
    view.OnLeftDown(mouse(view, wx.wxEVT_LEFT_DOWN, centre(act[1].rect)))
    view.OnLeftDown(mouse(view, wx.wxEVT_LEFT_DOWN, centre(act[3].rect)))
    assert owner.opened == ["/s/Pilot.trelby"]

    # nor picked with the keys
    key(view, wx.WXK_END)
    assert view.rows[view.picked] is act[2]


def testWritingCardEmpty(frame):
    view, owner = makeView(frame)

    texts = [t[0] for t in view.texts]
    assert "0 words" in texts
    assert _("What you write in any script is counted here.") in texts
    assert not any(k == homeview.TRACK for k, r in view.shapes)


def testGoalInPages(frame):
    view, owner = makeView(frame, sessions=[session(0, 500)], goal=3)
    owner.gd.cfgGl.dailyGoalPages = True
    view.refresh()

    texts = [t[0] for t in view.texts]
    assert "2 pages" in texts
    assert "66% of 3 pages" in texts

    view, owner = makeView(frame, sessions=[session(0, 1000)], goal=3)
    owner.gd.cfgGl.dailyGoalPages = True
    view.refresh()
    assert _("Daily goal reached") in [t[0] for t in view.texts]


# one card, its sections side by side with a line down between them in a
# wide window, one above the other with a line across in a narrow one
def testSectionsLayout(frame):
    def divider(view):
        return [r for kind, r in view.shapes if kind == homeview.DIVIDER]

    view, owner = makeView(frame, size=(1300, 800))
    a, b = view.sections
    assert a.y == b.y and a.GetRight() < b.x
    assert view.card.Contains(a) and view.card.Contains(b)
    (line,) = divider(view)
    assert line.width == 1 and line.x == b.x

    view, owner = makeView(frame, size=(700, 800))
    a, b = view.sections
    assert a.x == b.x and a.GetBottom() < b.y
    assert view.card.Contains(a) and view.card.Contains(b)
    (line,) = divider(view)
    assert line.height == 1 and line.y == b.y


# a stand-in for the frame's sprinttimer.SprintTimer
class Timer:
    def __init__(self, active=False, paused=False):
        self.active = active
        self.paused = paused

    def isActive(self):
        return self.active

    def isPaused(self):
        return self.paused

    def statusText(self):
        return "Sprint 18:42  ·  120 words"


def writingActions(view):
    return [(r.label, r.value) for r in view.rows if r.section == 1 and r.kind == homeview.ACTION]


# the sprint's rows start or stop one, and the sprint going on and today's
# are shown
def testSprintSection(frame):
    view, owner = makeView(frame)
    owner.gd.cfgGl.sprintMinutes = 15
    view.refresh()

    assert writingActions(view) == [
        ("Start a 15-minute sprint", "ToggleSprint"),
        (_("Manage Writing Goals") + "...", "WritingGoals"),
    ]
    assert [r.note for r in view.rows if r.value == "ToggleSprint"] == ["F7"]

    owner.sprint = Timer(active=True)
    owner.gd.writingLog.addSprint(
        writinglog.SprintRecord(NOW - 3600, NOW - 2100, 25, 0, 400, True)
    )
    view.refresh()

    assert writingActions(view)[:2] == [
        (_("Stop the sprint"), "ToggleSprint"),
        (_("Pause the sprint"), "PauseSprint"),
    ]

    texts = [t[0] for t in view.texts]
    assert "Sprint 18:42  ·  120 words" in texts
    assert "1 sprint today, 400 words" in texts

    owner.sprint.paused = True
    view.refresh()
    assert writingActions(view)[1] == (_("Resume the sprint"), "PauseSprint")

    # clicking runs them
    row = [r for r in view.rows if r.value == "PauseSprint"][0]
    view.OnLeftDown(mouse(view, wx.wxEVT_LEFT_DOWN, centre(row.rect)))
    assert owner.ran == ["PauseSprint"]


def testWeeklyGoal(frame):
    view, owner = makeView(frame, sessions=[session(0, 300), session(1, 200)])
    owner.gd.cfgGl.weeklyGoal = 2000
    view.refresh()

    assert "500 words of 2,000 words this week" in [t[0] for t in view.texts]
    assert [k for k, r in view.shapes].count(homeview.TRACK) == 1

    owner.gd.cfgGl.weeklyGoal = 400
    view.refresh()
    assert "Weekly goal reached: 500 words this week" in [t[0] for t in view.texts]
