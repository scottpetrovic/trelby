import subprocess
import sys

import trelby.opts as opts
import trelby.trelby as trelbyapp
import trelby.translations as translations

# tests for starting Trelby again after the language is changed


def testRestartArgs(monkeypatch):
    # put back whatever opts.init() set before, for the other tests
    for name in ("isTest", "conf", "filenames"):
        monkeypatch.setattr(opts, name, getattr(opts, name, None), raising=False)

    monkeypatch.setattr(sys, "argv", ["trelby.py", "--test", "a.trelby"])
    opts.init()
    assert trelbyapp.restartArgs(["/x/b.trelby"]) == ["--test", "/x/b.trelby"]

    monkeypatch.setattr(sys, "argv", ["trelby.py", "a.trelby"])
    opts.init()
    assert trelbyapp.restartArgs([]) == []

    monkeypatch.setattr(opts, "conf", "my.conf")
    assert trelbyapp.restartArgs(["/x/b.trelby"]) == [
        "--conf",
        "my.conf",
        "/x/b.trelby",
    ]


def testRestartCommandFrozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Trelby\Trelby.exe")

    cmd, env = trelbyapp.restartCommand(["--test"])
    assert cmd == [r"C:\Trelby\Trelby.exe", "--test"]
    assert env["PYINSTALLER_RESET_ENVIRONMENT"] == "1"


# from source, the command finds the package from any directory
def testRestartCommandSource(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTHONPATH", raising=False)

    cmd, env = trelbyapp.restartCommand(["--test"])
    assert cmd[0] == sys.executable
    assert cmd[-1] == "--test"

    res = subprocess.run(
        [sys.executable, "-c", "import trelby.trelby"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert res.returncode == 0, res.stderr


def testRestartDialogTranslated():
    it = translations.getTranslation("it_IT").gettext

    assert it("Language change needs a restart.") != (
        "Language change needs a restart."
    )
    assert it("Restart now") == "Riavvia ora"
    assert it("Restart later") == "Riavvia più tardi"
