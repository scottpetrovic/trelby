# MCP (Model Context Protocol) servers that let AI assistants read and
# edit scripts. there are three ways to run one, all with the same tools:
#
#  python -m trelby.mcpserver
#   works on .trelby files on disk, over stdio.
#
#  inside the app (Settings > MCP server, see app.py)
#   works on the scripts open in the app, over HTTP on localhost.
#
#  python -m trelby.mcpserver --app [--port N]
#   a stdio bridge to the server in the app, for clients like Claude
#   Desktop that can only start servers, not connect to them. the exe runs
#   it as "Trelby.exe --mcp-bridge [--port N]" (see trelby.main).
#
# the actual operations are in tools.py. the MCP SDK is an optional
# dependency (pip install trelby[mcp]), always bundled in the exe.

import sys
import threading
from typing import Annotated, Any, Literal, Optional

import anyio
from pydantic import BaseModel, Field

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

import trelby.formats as formats
import trelby.mcpserver.tools as mcptools
import trelby.screenplay.breakdown as breakdown
import trelby.screenplay.scriptformats as scriptformats

# port the server in the app listens on by default
DEFAULT_PORT = 7789

COMMON_INSTRUCTIONS = """\
A script is divided into numbered parts: index 0 is anything before the first
scene heading (e.g. FADE IN:), possibly empty, and index 1, 2, ... are the
scenes and act breaks in order, as returned by list_scenes. A part is a list
of elements, each with a type (scene, action, character, dialogue,
parenthetical, transition, shot, act break) and text.

An element can have notes: the writer's (or a reader's) notes about it,
shown in Trelby's notes sidebar and never printed, each with a text and
whether it's resolved. read_scenes returns them with the elements. When
replacing a scene, give each element the notes it had, unless asked to
change them; an element left without notes loses them.

A scene heading can have a synopsis: a sentence or two on what happens in
the scene, shown in Trelby's outline and never printed. list_scenes and
read_scenes return it. When replacing a scene, leave synopsis out to keep
the old one, unless the change makes it wrong.

Every result includes the script's revision. Every edit must be given the
revision it is based on, and is refused if the script has changed since, so
read again (list_scenes / read_scenes) after an error like that. Edits return
the new revision and the new list of scenes, whose indexes may have shifted.

A script has a format (get_script_info), which is how it's laid out and
what some element types stand for in it:
- screenplay: a film or single-camera TV script, the default.
- sitcom: a multi-camera sitcom, with the usual element types. Each scene
  starts on a new page.
- stageplay: a stage play. Action elements are stage directions and act
  breaks are the acts (ACT ONE); shots aren't used.
- audiodrama: a radio play or podcast drama. Shot elements are sound
  effects, transitions are music cues, and action elements describe the
  scene.
- comic: a comic book script. Scene headings are the comic's pages (PAGE
  ONE), shots are its panels (PANEL 1), action elements describe what a
  panel shows, and act breaks are chapters. Captions and sound effects are
  speeches (character CAPTION or SFX, then dialogue); transitions aren't
  used.

An element can also have breakdown tags: the things its scene needs for
production (cast, extras, props, vehicles, wardrobe, special effects, ...),
each with a category, the element's name and the element's text it was made
from (highlighted in Trelby wherever it appears in the element), or no text
for something the text doesn't mention. get_breakdown lists what each scene
needs and the scenes each element is in. To tag something, replace its
scene with the tag added to the element that mentions it. When replacing a
scene, give each element the tags it had, unless asked to change them; an
element left without tags loses them.

A script can also have world building notes (get_world_building), the
writer's free-text notes about the story's world, and character profiles
(get_character_profiles) with notes about each character. When they exist,
read them before writing or changing scenes and keep the script consistent
with them.
"""

FILE_INSTRUCTIONS = (
    """\
Reads and edits Trelby screenplay files (.trelby). All paths must be absolute.

"""
    + COMMON_INSTRUCTIONS
    + """
Each edit saves the file, keeping the previous version as <file>.bak. If the
script is open in the Trelby app at the same time, the app doesn't see the
change, and saving there overwrites it: ask the user to close the script in
Trelby first, or to reopen it afterwards.
"""
)

APP_INSTRUCTIONS = (
    """\
Reads and edits the screenplays open in the Trelby app, live. The path
argument picks an open script by its file path; leave it out to use the
script in the active tab. list_open_scripts lists them.

"""
    + COMMON_INSTRUCTIONS
    + """
Edits show up in the app immediately and can be undone there one at a time.
They are not saved to disk; the user saves the script in Trelby. Edits are
refused while a dialog is open in the app.
"""
)

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
EDIT = ToolAnnotations(destructiveHint=True, idempotentHint=False, openWorldHint=False)

Revision = Annotated[
    str, Field(description="Revision of the script the edit is based on.")
]
Index = Annotated[int, Field(description="Index of the scene, as in list_scenes.")]

Result = dict[str, Any]


class ElementNote(BaseModel):
    text: str = Field(description="The note's text.")
    resolved: bool = Field(
        False, description="Whether the note has been dealt with."
    )


class ElementTag(BaseModel):
    category: Literal[tuple(c.key for c in breakdown.CATEGORIES)] = Field(
        description="The breakdown category."
    )
    name: str = Field(
        description="The element's name, the same wherever it's tagged "
        "(e.g. 'Revolver'); case is ignored."
    )
    text: str = Field(
        "",
        description="The words of this element's text the tag was made "
        "from (e.g. 'his gun'), or empty for something it doesn't mention.",
    )


class Element(BaseModel):
    type: Literal[
        "scene",
        "action",
        "character",
        "dialogue",
        "parenthetical",
        "transition",
        "shot",
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
    synopsis: Optional[str] = Field(
        None,
        description="On a scene heading: a short description of what "
        "happens in the scene, shown in the outline and never printed, or "
        "null for none. Left out: replace_scene keeps the old synopsis.",
    )
    dual: bool = Field(
        False,
        description="On a character: this speech is the right-hand column "
        "of a dual dialogue with the speech before it.",
    )
    centered: bool = Field(
        False,
        description="On an action: it's centered on the page, e.g. THE END "
        "or a title card.",
    )
    notes: list[ElementNote] = Field(
        [],
        description="Notes about this element, shown in the notes sidebar "
        "and never printed.",
    )
    tags: list[ElementTag] = Field(
        [],
        description="Production breakdown tags on this element.",
    )


Elements = Annotated[list[Element], Field(min_length=1)]


# exclude_unset: a field the client left out stays out of the dict, which
# isn't the same as null for color and synopsis (replace_scene keeps the
# old one only if there's no key at all).
def toDicts(elements):
    return [e.model_dump(exclude_unset=True) for e in elements]


# create a server with all the tools. run(name, args) is an async function
# that performs the tool with the given name and dict of arguments and
# returns its result, raising ToolError on failure. inApp is True for the
# server in the app and the bridge to it, where the script is picked from
# the open ones.
def makeServer(run, inApp):
    if inApp:
        Path = Annotated[
            Optional[str],
            Field(
                default=None,
                description="Absolute path of a script open in Trelby. Leave "
                "out to use the active tab.",
            ),
        ]
    else:
        Path = Annotated[str, Field(description="Absolute path of the .trelby file.")]

    server = MCPServer(
        name="trelby-app" if inApp else "trelby",
        instructions=APP_INSTRUCTIONS if inApp else FILE_INSTRUCTIONS,
        log_level="WARNING",
    )

    if inApp:

        @server.tool(annotations=READ)
        async def list_open_scripts() -> Result:
            """List the scripts open in Trelby: their path (null if never
            saved), tab title, and whether each is the active one and has
            unsaved changes."""
            return await run("list_open_scripts", {})

    @server.tool(annotations=READ)
    async def get_script_info(*, path: Path) -> Result:
        """Return the title page and statistics (pages, words, scenes,
        characters) of a script, its number of character profiles, and
        whether it has world building notes (see get_world_building)."""
        return await run("get_script_info", {"path": path})

    @server.tool(annotations=READ)
    async def list_scenes(*, path: Path) -> Result:
        """List the script's scenes and act breaks with their index,
        heading, scene number (e.g. "12", or "12A" for a scene added after
        scene numbers were locked), page, synopsis if it has one, and the
        start of its action (summary). Start here to
        find a scene's index, which is not the same as its scene number."""
        return await run("list_scenes", {"path": path})

    @server.tool(annotations=READ)
    async def read_scenes(
        *,
        path: Path,
        first: Annotated[int, Field(description="Index of the first scene to read.")],
        last: Annotated[
            Optional[int],
            Field(description="Index of the last scene to read; default = first."),
        ] = None,
    ) -> Result:
        """Return the elements of one scene or a range of scenes. Text is
        as typed; Trelby shows scene headings, characters and transitions
        in capitals regardless."""
        return await run("read_scenes", {"path": path, "first": first, "last": last})

    @server.tool(annotations=READ)
    async def list_characters(*, path: Path) -> Result:
        """List the speaking characters, with how many speeches they have
        and the indexes of the scenes they speak in."""
        return await run("list_characters", {"path": path})

    @server.tool(annotations=READ)
    async def get_breakdown(
        *,
        path: Path,
        cast_speakers: Annotated[
            bool,
            Field(description="Count the speaking characters as cast."),
        ] = True,
    ) -> Result:
        """Return the script's production breakdown: for each scene (by
        index, as in list_scenes) its scene number, heading, INT./EXT.,
        time of day, page, length in eighths of a page and the elements it
        needs by category; and every element with the indexes of the
        scenes it's in."""
        return await run(
            "get_breakdown", {"path": path, "cast_speakers": cast_speakers}
        )

    @server.tool(annotations=READ)
    async def search_script(
        *,
        path: Path,
        query: Annotated[str, Field(description="Text to search for.")],
        case_sensitive: bool = False,
    ) -> Result:
        """Find the elements containing the given text, with the index of
        the scene each is in."""
        return await run(
            "search_script",
            {"path": path, "query": query, "case_sensitive": case_sensitive},
        )

    @server.tool(annotations=ToolAnnotations(openWorldHint=False))
    async def export_script(
        *,
        path: Path,
        format: Literal[tuple(f.key for f in formats.EXPORT_FORMATS)],
        output_path: Annotated[
            Optional[str],
            Field(
                description="Absolute path to write the result to. Without "
                "it, the result is returned (not possible for pdf)."
            ),
        ] = None,
    ) -> Result:
        """Export the script to another format, using the script's own
        formatting settings."""
        return await run(
            "export_script",
            {"path": path, "format": format, "output_path": output_path},
        )

    @server.tool(annotations=EDIT)
    async def replace_scene(
        *, path: Path, revision: Revision, index: Index, elements: Elements
    ) -> Result:
        """Replace a scene's elements. For index 1 and up, the first
        element must be a scene heading or act break. Further headings in
        the elements create new scenes after it."""
        return await run(
            "replace_scene",
            {
                "path": path,
                "revision": revision,
                "index": index,
                "elements": toDicts(elements),
            },
        )

    @server.tool(annotations=EDIT)
    async def insert_scenes(
        *,
        path: Path,
        revision: Revision,
        position: Annotated[
            int,
            Field(
                description="Index the first new scene gets: it is inserted "
                "before the scene now at that index. Use the number of scenes "
                "+ 1 to append at the end."
            ),
        ],
        elements: Elements,
    ) -> Result:
        """Insert one or more new scenes. The first element must be a
        scene heading or act break."""
        return await run(
            "insert_scenes",
            {
                "path": path,
                "revision": revision,
                "position": position,
                "elements": toDicts(elements),
            },
        )

    @server.tool(annotations=EDIT)
    async def delete_scene(*, path: Path, revision: Revision, index: Index) -> Result:
        """Delete a scene (or act break) and everything in it."""
        return await run(
            "delete_scene", {"path": path, "revision": revision, "index": index}
        )

    @server.tool(annotations=EDIT)
    async def move_scene(
        *,
        path: Path,
        revision: Revision,
        index: Index,
        new_index: Annotated[int, Field(description="Index the scene ends up at.")],
    ) -> Result:
        """Move a scene (or act break) to another place in the script,
        shifting the scenes in between."""
        return await run(
            "move_scene",
            {"path": path, "revision": revision, "index": index, "new_index": new_index},
        )

    @server.tool(annotations=EDIT)
    async def rename_character(
        *, path: Path, revision: Revision, old_name: str, new_name: str
    ) -> Result:
        """Rename a character everywhere: in character cues (keeping
        extensions like (V.O.)), in mentions in other text, and in its
        character profile."""
        return await run(
            "rename_character",
            {
                "path": path,
                "revision": revision,
                "old_name": old_name,
                "new_name": new_name,
            },
        )

    @server.tool(annotations=READ)
    async def get_world_building(*, path: Path) -> Result:
        """Return the script's world building notes: free text the writer
        keeps about the story's world (places, history, cultures, rules of
        magic or technology, ...). get_script_info's has_world_building
        says whether there are any. Read them before writing or revising
        scenes, and keep new material consistent with them."""
        return await run("get_world_building", {"path": path})

    @server.tool(annotations=EDIT)
    async def set_world_building(
        *,
        path: Path,
        revision: Revision,
        text: Annotated[
            str,
            Field(
                description="The complete new notes. They replace the old "
                "ones, so to add to them, include the existing text."
            ),
        ],
    ) -> Result:
        """Replace the script's world building notes (the free text shown
        in Tools > World building). Use it to record facts about the world
        that scenes establish, so later scenes stay consistent. Doesn't
        change the script's scenes."""
        return await run(
            "set_world_building", {"path": path, "revision": revision, "text": text}
        )

    @server.tool(annotations=READ)
    async def get_character_profiles(
        *,
        path: Path,
        name: Annotated[
            Optional[str],
            Field(description="Character to return the profile of; default = all."),
        ] = None,
    ) -> Result:
        """Return the character profiles: the writer's notes about each
        character (background, personality, look, arcs, ...), how many
        photos each has, and whether the character speaks in the script.
        Read a character's profile before writing them, and keep their
        behavior and details consistent with it."""
        return await run("get_character_profiles", {"path": path, "name": name})

    @server.tool(annotations=EDIT)
    async def set_character_profile(
        *,
        path: Path,
        revision: Revision,
        name: Annotated[
            str,
            Field(
                description="Character name; case and extensions like "
                "(V.O.) are ignored."
            ),
        ],
        notes: Annotated[
            str,
            Field(
                description="The complete new notes. They replace the old "
                "ones, so to add to them, include the existing text."
            ),
        ],
    ) -> Result:
        """Create a character's profile, or replace its notes (the free
        text shown in Tools > Character profiles). Photos are kept. To
        rename a character, use rename_character instead."""
        return await run(
            "set_character_profile",
            {"path": path, "revision": revision, "name": name, "notes": notes},
        )

    @server.tool(annotations=EDIT)
    async def delete_character_profile(
        *, path: Path, revision: Revision, name: str
    ) -> Result:
        """Delete a character's profile, including its notes and photos.
        The character's lines in the script are not touched."""
        return await run(
            "delete_character_profile",
            {"path": path, "revision": revision, "name": name},
        )

    if not inApp:

        @server.tool(
            annotations=ToolAnnotations(destructiveHint=False, openWorldHint=False)
        )
        async def create_script(
            *,
            path: Annotated[str, Field(description="Absolute path of the new file.")],
            elements: Elements,
            format: Annotated[
                Literal[tuple(f.key for f in scriptformats.FORMATS)],
                Field(
                    description="The kind of script, which sets its layout "
                    "and what the element types stand for (see the "
                    "instructions)."
                ),
            ] = scriptformats.SCREENPLAY,
        ) -> Result:
            """Create a new script with the given elements, laid out as a
            screenplay or another format. Refuses to overwrite an existing
            file."""
            return await run(
                "create_script",
                {"path": path, "elements": toDicts(elements), "format": format},
            )

    return server


# run a mcptools function, converting its errors to MCP ones.
def callTool(fn, *args):
    try:
        return fn(*args)
    except mcptools.ToolError as e:
        raise ToolError(str(e)) from e


# server working on files on disk
def makeFileServer():
    # tools run in worker threads; only do one at a time so a write can't
    # happen between another write's revision check and save
    lock = threading.Lock()

    def runSync(name, args):
        with lock:
            args = dict(args)
            path = args.pop("path")

            if name == "create_script":
                return callTool(
                    mcptools.createScript,
                    path,
                    args["elements"],
                    args.get("format", scriptformats.SCREENPLAY),
                )

            return callTool(
                lambda: mcptools.OPS[name](mcptools.FileDoc(path), args)
            )

    async def run(name, args):
        return await anyio.to_thread.run_sync(runSync, name, args)

    return makeServer(run, False)


# bridge to the server in the app on the given port
def makeBridgeServer(port):
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    url = "http://127.0.0.1:%d/mcp" % port

    # every call opens a session of its own: the app's server is stateless,
    # so there's nothing to keep, and the app can be restarted (or turned
    # on) between calls. the except is for failing to talk to the app; a
    # tool that fails there comes back as an is_error result, whose
    # message is passed on as is. on success, the app's result dict is
    # returned, for this server to send on unchanged.
    async def run(name, args):
        try:
            async with streamable_http_client(url) as (r, w):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    res = await session.call_tool(name, args)
        except Exception as e:
            raise ToolError(
                "Can't reach Trelby at %s. Is Trelby running, with the MCP "
                "server turned on in its settings (and on port %d)? (%s: %s)"
                % (url, port, type(e).__name__, e)
            ) from e

        if res.is_error:
            raise ToolError(" ".join(c.text for c in res.content if c.type == "text"))

        return res.structured_content

    return makeServer(run, True)


def usage():
    print(
        "usage: python -m trelby.mcpserver [--app [--port N]]\n"
        "       Trelby.exe --mcp-bridge [--port N]   (same as --app)\n\n"
        "Without --app, works on .trelby files on disk. With --app, connects "
        "to the scripts open in a running Trelby (default port %d)." % DEFAULT_PORT,
        file=sys.stderr,
    )
    sys.exit(2)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    port = None
    app = False

    while args:
        arg = args.pop(0)

        if arg == "--app":
            app = True
        elif (arg == "--port") and args:
            try:
                port = int(args.pop(0))
            except ValueError:
                usage()
        else:
            usage()

    if (port is not None) and not app:
        usage()

    if app:
        server = makeBridgeServer(port or DEFAULT_PORT)
    else:
        mcptools.init()
        server = makeFileServer()

    server.run("stdio")


if __name__ == "__main__":
    main()
