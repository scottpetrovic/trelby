# MCP (Model Context Protocol) server that lets AI assistants read and
# edit .trelby files. it runs separately from the app, over stdio:
#
#   python -m trelby.mcpserver
#
# the actual operations are in mcptools.py; this only describes them to
# the MCP SDK, which is an optional dependency (pip install trelby[mcp]).

import threading
from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, Field

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

import trelby.mcptools as mcptools

INSTRUCTIONS = """\
Reads and edits Trelby screenplay files (.trelby). All paths must be absolute.

A script is divided into numbered parts: index 0 is anything before the first
scene heading (e.g. FADE IN:), possibly empty, and index 1, 2, ... are the
scenes and act breaks in order, as returned by list_scenes. A part is a list
of elements, each with a type (scene, action, character, dialogue,
parenthetical, transition, shot, note, act break) and text.

Every result includes the file's revision. Every edit must be given the
revision it is based on, and is refused if the file has changed since, so
read again (list_scenes / read_scenes) after an error like that. Edits return
the new revision and the new list of scenes, whose indexes may have shifted.

Each edit saves the file, keeping the previous version as <file>.bak. If the
script is open in the Trelby app at the same time, the app doesn't see the
change, and saving there overwrites it: ask the user to close the script in
Trelby first, or to reopen it afterwards.
"""

server = MCPServer(name="trelby", instructions=INSTRUCTIONS)

# tools may be run in worker threads; only do one at a time so a write
# can't happen between another write's revision check and save
_lock = threading.Lock()

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
EDIT = ToolAnnotations(destructiveHint=True, idempotentHint=False, openWorldHint=False)

Path = Annotated[str, Field(description="Absolute path of the .trelby file.")]
Revision = Annotated[
    str, Field(description="Revision of the file the edit is based on.")
]
Index = Annotated[int, Field(description="Index of the scene, as in list_scenes.")]


class Element(BaseModel):
    type: Literal[
        "scene",
        "action",
        "character",
        "dialogue",
        "parenthetical",
        "transition",
        "shot",
        "note",
        "act break",
    ]
    text: str = Field(
        description="Element text. Use \\n for a forced line break; normal "
        "word wrapping is done automatically."
    )
    color: Optional[str] = Field(
        None,
        description="Outline color '#rrggbb' of a scene or act break, or "
        "null for none. Left out: replace_scene keeps the old color.",
    )
    dual: bool = Field(
        False,
        description="On a character: this speech is the right-hand column "
        "of a dual dialogue with the speech before it.",
    )


Elements = Annotated[list[Element], Field(min_length=1)]


def _toDicts(elements):
    return [e.model_dump(exclude_unset=True) for e in elements]


# run fn with the lock held, converting mcptools errors to MCP ones
def _call(fn, *args):
    with _lock:
        try:
            return fn(*args)
        except mcptools.ToolError as e:
            raise ToolError(str(e)) from e


@server.tool(annotations=READ)
def get_script_info(path: Path) -> dict[str, Any]:
    """Return the title page and statistics (pages, words, scenes,
    characters) of a script."""
    return _call(mcptools.getInfo, path)


@server.tool(annotations=READ)
def list_scenes(path: Path) -> dict[str, Any]:
    """List the script's scenes and act breaks with their index, heading,
    scene number, page and a short summary. Start here to find a scene's
    index."""
    return _call(mcptools.listScenes, path)


@server.tool(annotations=READ)
def read_scenes(
    path: Path,
    first: Annotated[int, Field(description="Index of the first scene to read.")],
    last: Annotated[
        Optional[int],
        Field(description="Index of the last scene to read; default = first."),
    ] = None,
) -> dict[str, Any]:
    """Return the elements of one scene or a range of scenes. Text is as
    typed; Trelby shows scene headings, characters and transitions in
    capitals regardless."""
    return _call(mcptools.readScenes, path, first, last)


@server.tool(annotations=READ)
def list_characters(path: Path) -> dict[str, Any]:
    """List the speaking characters, with how many speeches they have and
    the indexes of the scenes they speak in."""
    return _call(mcptools.listCharacters, path)


@server.tool(annotations=READ)
def search_script(
    path: Path,
    query: Annotated[str, Field(description="Text to search for.")],
    case_sensitive: bool = False,
) -> dict[str, Any]:
    """Find the elements containing the given text, with the index of the
    scene each is in."""
    return _call(mcptools.search, path, query, case_sensitive)


@server.tool(annotations=ToolAnnotations(openWorldHint=False))
def export_script(
    path: Path,
    format: Literal["pdf", "fountain", "text", "html", "fdx", "rtf"],
    output_path: Annotated[
        Optional[str],
        Field(
            description="Absolute path to write the result to. Without it, "
            "the result is returned (not possible for pdf)."
        ),
    ] = None,
) -> dict[str, Any]:
    """Export the script to another format, using the script's own
    formatting settings."""
    return _call(mcptools.export, path, format, output_path)


@server.tool(annotations=EDIT)
def replace_scene(
    path: Path, revision: Revision, index: Index, elements: Elements
) -> dict[str, Any]:
    """Replace a scene's elements. For index 1 and up, the first element
    must be a scene heading or act break. Further headings in the elements
    create new scenes after it."""
    return _call(mcptools.replaceScene, path, revision, index, _toDicts(elements))


@server.tool(annotations=EDIT)
def insert_scenes(
    path: Path,
    revision: Revision,
    position: Annotated[
        int,
        Field(
            description="Index the first new scene gets: it is inserted "
            "before the scene now at that index. Use the number of scenes + "
            "1 to append at the end."
        ),
    ],
    elements: Elements,
) -> dict[str, Any]:
    """Insert one or more new scenes. The first element must be a scene
    heading or act break."""
    return _call(mcptools.insertScenes, path, revision, position, _toDicts(elements))


@server.tool(annotations=EDIT)
def delete_scene(path: Path, revision: Revision, index: Index) -> dict[str, Any]:
    """Delete a scene (or act break) and everything in it."""
    return _call(mcptools.deleteScene, path, revision, index)


@server.tool(annotations=EDIT)
def move_scene(
    path: Path,
    revision: Revision,
    index: Index,
    new_index: Annotated[int, Field(description="Index the scene ends up at.")],
) -> dict[str, Any]:
    """Move a scene (or act break) to another place in the script, shifting
    the scenes in between."""
    return _call(mcptools.moveScene, path, revision, index, new_index)


@server.tool(annotations=EDIT)
def rename_character(
    path: Path,
    revision: Revision,
    old_name: str,
    new_name: str,
) -> dict[str, Any]:
    """Rename a character everywhere: in character cues (keeping extensions
    like (V.O.)), in mentions in other text, and in its character
    profile."""
    return _call(mcptools.renameCharacter, path, revision, old_name, new_name)


@server.tool(annotations=ToolAnnotations(destructiveHint=False, openWorldHint=False))
def create_script(
    path: Annotated[str, Field(description="Absolute path of the new file.")],
    elements: Elements,
) -> dict[str, Any]:
    """Create a new script with default settings and the given elements.
    Refuses to overwrite an existing file."""
    return _call(mcptools.createScript, path, _toDicts(elements))


def main():
    mcptools.init()
    server.run("stdio")


if __name__ == "__main__":
    main()
