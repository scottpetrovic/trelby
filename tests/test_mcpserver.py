import asyncio
import shutil
import socket
import subprocess
import sys

import pytest

pytest.importorskip("mcp")

from mcp.server.mcpserver.exceptions import ToolError

import tests.u as u
import trelby.mcpserver as mcpserver

# tests for the MCP tool definitions and how calls reach the operations


def call(server, name, args):
    return asyncio.run(server.call_tool(name, args))


# call a tool that should fail, and return its error message
def callError(server, name, args):
    with pytest.raises(ToolError) as e:
        call(server, name, args)

    return str(e.value)


def toolNames(server):
    return [t.name for t in asyncio.run(server.list_tools())]


def schema(server, name):
    return [t for t in asyncio.run(server.list_tools()) if t.name == name][0].input_schema


@pytest.fixture
def script(tmp_path):
    path = str(tmp_path / "test.trelby")
    shutil.copy(u.fixtureFilePath("test.trelby"), path)

    return path


def testFileServer(script):
    server = mcpserver.makeFileServer()

    assert "create_script" in toolNames(server)
    assert "list_open_scripts" not in toolNames(server)
    assert "path" in schema(server, "list_scenes")["required"]

    res = call(server, "list_scenes", {"path": script})
    assert not res.is_error
    rev = res.structured_content["revision"]

    res = call(
        server,
        "replace_scene",
        {
            "path": script,
            "revision": rev,
            "index": 1,
            "elements": [{"type": "scene", "text": "INT. NEW - DAY"}],
        },
    )
    assert not res.is_error
    assert res.structured_content["scenes"][0]["heading"] == "INT. NEW - DAY"

    # errors from the operations come back as tool errors
    msg = callError(
        server, "delete_scene", {"path": script, "revision": rev, "index": 1}
    )
    assert "changed" in msg


def testAppServerArgs():
    calls = []

    async def run(name, args):
        calls.append((name, args))

        return {"ok": True}

    server = mcpserver.makeServer(run, True)

    assert "list_open_scripts" in toolNames(server)
    assert "create_script" not in toolNames(server)
    assert "path" not in schema(server, "list_scenes").get("required", [])

    call(server, "list_scenes", {})
    call(
        server,
        "replace_scene",
        {
            "revision": "r",
            "index": 2,
            "elements": [
                {"type": "scene", "text": "INT. A"},
                {"type": "action", "text": "B", "color": None},
            ],
        },
    )

    assert calls[0] == ("list_scenes", {"path": None})

    # elements are passed on as dicts with only the keys that were given,
    # so a missing color can be told apart from removing it
    assert calls[1] == (
        "replace_scene",
        {
            "path": None,
            "revision": "r",
            "index": 2,
            "elements": [
                {"type": "scene", "text": "INT. A"},
                {"type": "action", "text": "B", "color": None},
            ],
        },
    )


def testBridgeWithoutApp():
    # find a port nothing listens on
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    server = mcpserver.makeBridgeServer(port)
    assert "Can't reach Trelby" in callError(server, "list_scenes", {})


def testArgs():
    for bad in (["--port", "1"], ["--app", "--port"], ["--app", "--port", "x"], ["-x"]):
        with pytest.raises(SystemExit):
            mcpserver.main(bad)



# Trelby.exe --mcp-bridge runs the bridge instead of the app. it's given
# a bad argument here, so it stops right after parsing them.
def testExeBridgeArg():
    res = subprocess.run(
        [sys.executable, "trelby.py", "--mcp-bridge", "--bad"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert res.returncode == 2
    assert "usage:" in res.stderr
