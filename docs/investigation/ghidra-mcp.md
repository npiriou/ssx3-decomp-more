# Ghidra and the GhidraMCP backend

## Install

- Ghidra **12.1.4** was used for the analysis below. Install Ghidra for your
  platform; it is optional for building and playing.
- Install these extensions through Ghidra's extension manager:
  - **GhidraMCP** (`com.lauriewired`) — serves the loopback HTTP backend.
  - **ghidra-emotionengine-reloaded** (`chaoticgd`) — adds the R5900 language.

## How GhidraMCP works (v2.0.0)

It is **two** pieces:

1. A Ghidra plugin (`GhidraMCPPlugin`) that starts an in-process HTTP server on
   `127.0.0.1:8080` (configurable under *Edit → Tool Options → GhidraMCP HTTP
   Server*). It is **loopback-only** and only runs when the plugin is enabled in
   an open CodeBrowser with a program loaded.
2. A Python MCP server (`uvx --from git+https://github.com/LaurieWired/GhidraMCP
   ghidra-mcp`) that translates MCP calls into requests to that backend.

Lifecycle: `init()` starts the listener, `dispose()` stops it. Toggling the
plugin checkbox is the start/stop control. If it is disabled the backend is
simply absent (`curl http://127.0.0.1:8080/health` fails).

## Useful REST endpoints (hit directly with curl)

```sh
curl "http://127.0.0.1:8080/health"
curl "http://127.0.0.1:8080/program_info"
curl "http://127.0.0.1:8080/functions?offset=0&limit=2000"
curl "http://127.0.0.1:8080/function?address=0x001001c8"
curl "http://127.0.0.1:8080/disassemble_function?address=0x00100008&limit=5000"
```

Notes:
- List endpoints page; **`/functions` caps a page at 2000** regardless of
  `limit`, so full exports must paginate.
- `/function` returns `body_start`, **`body_end`** (inclusive) and `body_size`.
  This is how exact function extents are obtained.
- `disassemble_function` reports bytes in **raw memory order** (little-endian),
  e.g. `entry` starts `280c0070` = word `0x70000c28`.
- The backend handles requests on a single dedicated thread; sequential calls
  run ~0.8 ms each (≈10 s for 11,844 `/function` queries).

## Optional MCP client

Configure a local stdio server in your MCP client using this command:

```sh
uvx --from git+https://github.com/LaurieWired/GhidraMCP ghidra-mcp --ghidra-server http://127.0.0.1:8080/
```

Allow enough startup time for the first `uvx` clone/build. Importing the ELF
is a one-time action in Ghidra's GUI.

## Program state (as analysed)

- Name `SLUS_207.72`, format ELF, language **`r5900:LE:32:default`** (`MIPS-R5900`),
  image base `00100000`, entry `00100008`, little-endian, 32-bit.
- After Auto Analyze: **11,844 functions**.
- MD5 `9e64f3df7ed6e898061411ce43fe75eb`,
  SHA-256 `1b49d05ca2793922180851b9e1ce9ae2291d61a7863565ac4e71f12e967af7bc`.
