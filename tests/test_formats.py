import asyncio
import os

import pytest

import tests.u as u
import trelby.formats as formats
import trelby.mcptools as mcptools
import trelby.translations as translations

_ = translations.trelby_translations_load()

# the import / export format registry (formats.py), which the File menu,
# its file dialogs and the MCP server's export tool use


def testKeysAreUnique():
    for fmts in (formats.EXPORT_FORMATS, formats.IMPORT_FORMATS):
        keys = [f.key for f in fmts]
        assert len(keys) == len(set(keys))

        mnemonics = [f.mnemonic for f in fmts]
        assert len(mnemonics) == len(set(mnemonics))


def testExportersWork():
    sp = u.load()
    sp.paginate()

    for f in formats.EXPORT_FORMATS:
        data = f.generate(sp)
        assert data, f.key
        assert isinstance(data, bytes if f.binary else (str, bytes)), f.key

        if f.options:
            options = {name: False for name, label in f.options}
            assert f.generate(sp, **options), f.key


def testImportersExist():
    import trelby.myimport as myimport

    for f in formats.IMPORT_FORMATS:
        assert callable(getattr(myimport, f.importer)), f.key


@pytest.mark.parametrize(
    "fileName, key",
    [
        ("a.fdx", "fdx"),
        ("A.FDX", "fdx"),
        ("dir.x/a.fountain", "fountain"),
        ("a.celtx", "celtx"),
        ("a.astx", "astx"),
        ("a.fadein", "fadein"),
        # Fountain files can be .txt too, but formatted text comes first
        ("a.txt", "text"),
        ("a.doc", "text"),
        ("a", "text"),
    ],
)
def testGuessImportFormat(fileName, key):
    assert formats.guessImportFormat(fileName).key == key


def testWildcard():
    f = formats.find(formats.IMPORT_FORMATS, "fountain")

    assert f.getWildcard() == "Fountain (*.fountain;*.txt)|*.fountain;*.txt"
    assert formats.find(formats.IMPORT_FORMATS, "nope") is None


# the MCP tool's format argument lists the formats for its clients
def testMcpServerListsFormats():
    pytest.importorskip("mcp")

    import trelby.mcpserver as mcpserver

    server = mcpserver.makeServer(None, False)
    tools = asyncio.run(server.list_tools())
    schema = [t for t in tools if t.name == "export_script"][0].input_schema

    assert schema["properties"]["format"]["enum"] == [
        f.key for f in formats.EXPORT_FORMATS
    ]


def testMcpExportUsesRegistry(tmp_path):
    path = str(tmp_path / "a.trelby")

    with open(u.fixtureFilePath("test.trelby"), encoding="utf-8") as f:
        data = f.read()

    with open(path, "w", encoding="utf-8") as f:
        f.write(data)

    mcptools.init()
    doc = mcptools.FileDoc(path)

    for fmt in formats.EXPORT_FORMATS:
        if fmt.binary:
            with pytest.raises(mcptools.ToolError):
                mcptools.export(doc, fmt.key)

            out = str(tmp_path / ("out." + fmt.extensions[0]))
            mcptools.export(doc, fmt.key, out)
            assert os.path.getsize(out) > 0
        else:
            assert mcptools.export(doc, fmt.key)["content"]

    with pytest.raises(mcptools.ToolError, match="Valid formats: pdf, rtf"):
        mcptools.export(doc, "doc")
