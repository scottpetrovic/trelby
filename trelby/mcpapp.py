# the MCP server inside the app (see mcpserver.py). while turned on in the
# settings, it serves the scripts open in the app over HTTP on localhost,
# so AI assistants can read and edit them live.
#
# the server runs in a thread of its own. every tool call is handed to the
# GUI thread and done there, so the scripts are only ever touched by the
# GUI thread, and an edit is a single step as far as the user is
# concerned.

import os
import socket
import threading

import wx

import trelby.mcptools as mcptools

# how long a tool call waits for the GUI thread before giving up, in
# seconds
CALL_TIMEOUT = 30

# the running Server, or None
_server = None


# return True if the MCP SDK (an optional dependency) is installed
def isAvailable():
    try:
        import mcp.server.mcpserver
        import uvicorn
    except ImportError:
        return False

    return True


def url(port):
    return "http://127.0.0.1:%d/mcp" % port


def absPath(path):
    return os.path.abspath(path) if path else None


# return True if two paths point to the same file
def samePath(path1, path2):
    n = lambda p: os.path.normcase(os.path.abspath(p))

    return n(path1) == n(path2)


# return True if a modal dialog is open, in which case scripts can't be
# changed, since dialogs work on copies of things they write back when
# closed.
def isModalOpen():
    return any(
        isinstance(w, wx.Dialog) and w.IsModal() for w in wx.GetTopLevelWindows()
    )


# a script open in the app. one is made for each tool call, in the GUI
# thread.
class AppDoc(mcptools.LiveDoc):
    def __init__(self, gd, ctrl):
        self.gd = gd
        self.ctrl = ctrl

    # LiveDoc's Editor, taken from the tab each time rather than stored,
    # as the tab may replace its script
    @property
    def ed(self):
        return self.ctrl.ed

    def describe(self, sp):
        ret = {
            "path": absPath(self.ctrl.fileName),
            "title": self.ctrl.fileNameDisplay,
        }
        ret.update(mcptools.LiveDoc.describe(self, sp))

        return ret

    def checkWritable(self):
        if isModalOpen():
            raise mcptools.ToolError(
                "A dialog is open in Trelby. Ask the user to close it, then "
                "try again."
            )

    def changed(self):
        self.ctrl.makeLineVisible(self.ed.line)
        self.ctrl.updateScreen()


# return the ctrl of the open script with the given path, or of the
# active tab if path is None.
def findCtrl(gd, path):
    if path is None:
        return gd.mainFrame.panel.ctrl

    for ctrl in gd.mainFrame.getCtrls():
        if ctrl.fileName and samePath(ctrl.fileName, path):
            return ctrl

    paths = [absPath(c.fileName) for c in gd.mainFrame.getCtrls() if c.fileName]

    raise mcptools.ToolError(
        "'%s' is not open in Trelby. Open scripts: %s. Leave out the path to "
        "use the active tab."
        % (path, ", ".join("'%s'" % p for p in paths) or "none with a file")
    )


def listOpenScripts(gd):
    active = gd.mainFrame.panel.ctrl
    scripts = []

    for ctrl in gd.mainFrame.getCtrls():
        scripts.append(
            {
                "path": absPath(ctrl.fileName),
                "title": ctrl.fileNameDisplay,
                "active": ctrl is active,
                "modified": ctrl.sp.isModified(),
            }
        )

    return {"scripts": scripts}


# do a tool call. must be called in the GUI thread.
def perform(gd, name, args):
    if name == "list_open_scripts":
        return listOpenScripts(gd)

    args = dict(args)
    doc = AppDoc(gd, findCtrl(gd, args.pop("path", None)))

    return mcptools.OPS[name](doc, args)


# call fn in the GUI thread and return its result, or raise what it
# raised. called from one of the server's worker threads (see Server).
#
# the lock makes starting and cancelling exclusive: either the GUI thread
# runs fn to the end and we report its outcome, or we cancel it before it
# starts and it never runs. so a call reported as timed out never makes
# its edit later, behind the client's back.
def callInGui(fn):
    done = threading.Event()
    lock = threading.Lock()
    state = {"started": False, "cancelled": False}

    def wrapper():
        with lock:
            if state["cancelled"]:
                return

            state["started"] = True

        try:
            state["result"] = fn()
        except BaseException as e:
            state["error"] = e
        finally:
            done.set()

    wx.CallAfter(wrapper)

    if not done.wait(CALL_TIMEOUT):
        with lock:
            if not state["started"]:
                state["cancelled"] = True

                raise mcptools.ToolError(
                    "Trelby didn't respond in time. It may be busy, or "
                    "showing a dialog."
                )

        # it started just now. wait for it after all, so we don't report
        # a failure for something that happened.
        done.wait()

    if "error" in state:
        raise state["error"]

    return state["result"]


class Server:
    # the SDK and uvicorn are imported here, not at the top, since they're
    # optional: the app must start without them (see isAvailable).
    #
    # a tool call goes: uvicorn's event loop (the server thread) -> run()
    # -> runSync() in an anyio worker thread, which blocks in callInGui
    # while perform() runs in the GUI thread. blocking a worker rather
    # than the event loop keeps the server answering other requests.
    def __init__(self, gd, port):
        import anyio
        import uvicorn
        from mcp.server.mcpserver.exceptions import ToolError
        from mcp.server.transport_security import TransportSecuritySettings

        import trelby.mcpserver as mcpserver

        self.port = port

        def runSync(name, args):
            try:
                return callInGui(lambda: perform(gd, name, args))
            except mcptools.ToolError as e:
                raise ToolError(str(e)) from e

        async def run(name, args):
            return await anyio.to_thread.run_sync(runSync, name, args)

        mcp = mcpserver.makeServer(run, True)

        # only accept requests made to localhost, so web pages can't reach
        # the server through DNS rebinding
        security = TransportSecuritySettings(
            allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"],
            allowed_origins=[
                "http://127.0.0.1:*",
                "http://localhost:*",
                "http://[::1]:*",
            ],
        )

        # stateless: no session is kept between requests, so clients (like
        # the bridge, which opens a session per call) keep working when the
        # server is restarted
        app = mcp.streamable_http_app(
            stateless_http=True,
            json_response=True,
            transport_security=security,
        )

        # log_config=None: don't configure logging, which would write to
        # stderr, and there might not be one
        config = uvicorn.Config(
            app,
            log_config=None,
            log_level="warning",
            access_log=False,
            timeout_graceful_shutdown=2,
        )

        self.uvicorn = uvicorn.Server(config)

        # bind here, so failures (like the port being taken) are reported
        # right away
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            self.sock.bind(("127.0.0.1", port))
        except OSError:
            self.sock.close()
            raise

        self.thread = threading.Thread(
            target=self.uvicorn.run,
            kwargs={"sockets": [self.sock]},
            name="MCP server",
            daemon=True,
        )
        self.thread.start()

    def stop(self):
        self.uvicorn.should_exit = True
        self.thread.join(5)
        self.sock.close()


# start or stop the server to match the global settings. errors are shown
# in a message box with the given parent.
def configure(gd, parent):
    global _server

    cfg = gd.cfgGl
    port = cfg.mcpPort if cfg.mcpEnabled else None

    if _server and (_server.port != port):
        _server.stop()
        _server = None

    if (port is None) or _server:
        return

    if not isAvailable():
        wx.MessageBox(
            _(
                "The MCP server needs the 'mcp' Python package, which isn't "
                "installed. Install it with:\n\npip install trelby[mcp]"
            ),
            _("MCP server"),
            wx.OK,
            parent,
        )

        return

    try:
        _server = Server(gd, port)
    except OSError as e:
        wx.MessageBox(
            _("Couldn't start the MCP server on port {}:\n\n{}").format(
                port, e.strerror or e
            ),
            _("MCP server"),
            wx.OK,
            parent,
        )


def shutdown():
    global _server

    if _server:
        _server.stop()
        _server = None


# return a description of the server's state for the settings
def status():
    if not isAvailable():
        return _("Not available: the 'mcp' Python package isn't installed.")

    if _server:
        return _("Running at {}").format(url(_server.port))

    return _("Not running.")
