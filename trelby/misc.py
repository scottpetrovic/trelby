# -*- coding: iso-8859-1 -*-

# the platform, paths and version globals the rest of trelby reads.

import os
import os.path
import sys
from typing import AnyStr

import trelby.opts as opts
import trelby.util as util

version = "2.4.16.2"

# the folder file dialogs start in. trelby.py sets it once the global config
# is loaded, and it's updated as the user picks folders in the open, import
# and export dialogs.
scriptDir = ""


# set the platform and path globals below. they don't exist until this has
# run, so it must come before anything that reads them (getFullPath,
# config.ConfigGlobal, ...): the app calls it at startup, tests and the
# MCP server with doWX=False.
#
# progPath is the folder containing the trelby package, which data files
# are found relative to: the repo root when running from source, or the
# exe's _internal folder in the PyInstaller build. in test mode (--test,
# or doWX=False) it's "." and confPath is ".trelby", both relative to the
# current directory, so those must be run from the repo root.
def init(doWX=True):
    global isWindows, isUnix, isMac, unicodeFS, doDblBuf, progPath, confPath, tmpPrefix

    # prefix used for temp files
    tmpPrefix = "trelby-tmp-"

    isWindows = False
    isUnix = False
    isMac = False

    if sys.platform == "win32":
        isWindows = True
    else:
        isUnix = True
        isMac = sys.platform == "darwin"

    # does this platform support using Python's unicode strings in various
    # filesystem calls; if not, we need to convert filenames to UTF-8
    # before using them.
    unicodeFS = isWindows

    # wxGTK2 does not need us to do double buffering ourselves, others do
    doDblBuf = not isUnix

    # stupid hack to keep testcases working, since they don't initialize
    # opts (the doWX name is just for similarity with util)
    if not doWX or opts.isTest:
        progPath = "."
        confPath = ".trelby"
    else:
        if isUnix:
            progPath = str(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

            default_confPath = str(os.environ["HOME"]) + "/.trelby"

            if os.environ.get("XDG_CONFIG_HOME"):
                confPath = str(os.environ["XDG_CONFIG_HOME"]) + "/trelby"
            elif os.path.exists(default_confPath):
                confPath = default_confPath
            else:
                confPath = str(os.environ["HOME"]) + "/.config/trelby"

        else:
            progPath = str(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )  # Removed the registry function because the older installer creator doesn't work anymore and for portable setups it's pointless to setup a check for a registry key

            confPath = util.getWindowsUnicodeEnvVar("USERPROFILE") + r"\Trelby\conf"

        if not os.path.exists(confPath):
            os.makedirs(confPath)


# convert s, which is returned from the wxWidgets GUI and is an Unicode
# string, to a normal string.
def fromGUI(s):
    return s


# convert s, which is an Unicode string, to an object suitable for passing
# to Python's file APIs. this is either the Unicode string itself, if the
# platform supports Unicode-based APIs (and Python has implemented support
# for it), or the Unicode string converted to UTF-8 on other platforms.
def toPath(s: str) -> AnyStr:
    if unicodeFS:
        return s
    else:
        return s.encode("UTF-8")


# return the absolute path of a file under the install dir. so passing in
# "resources/blaa.png" might return "/opt/trelby/resources/blaa.png" for
# example.
def getFullPath(relative):
    return progPath + "/" + relative


# return menu label 'label' (already translated, optionally followed by
# "\t<accelerator>") with a mnemonic for 'key'. the '&' goes before the
# first occurrence of 'key' in the text (preferring an exact case match),
# so it's only underlined while Alt is held. if the text doesn't contain
# 'key' at all (e.g. in some translations), " (&KEY)" is appended instead.
def mnemonic(key, label):
    text, sep, accel = label.partition("\t")

    i = text.find(key)
    if i == -1:
        i = text.lower().find(key.lower())

    if i != -1:
        text = text[:i] + "&" + text[i:]
    else:
        text += " (&%s)" % key.upper()

    return text + sep + accel
