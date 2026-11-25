# datev-dokab

Headless, dependency-free Python client for the **DATEVconnect Dokumentenablage (DMS v2)**:
read documents, file new ones, and write edited bytes back to an existing document with a
conservative, pure guard (`datev.writeback.decide_save_back`) that refuses to overwrite when the
server state no longer matches what was opened. The import name is `datev`.

Extracted from the DigitalerUnterlagenOrdner (BelegTool) project, which consumes it in its
optional "DATEV mode". No UI, no third-party dependencies; the transport is injected, so everything
except the real network call is unit-testable.

## Requirements

- Python >= 3.10
- **Windows with `curl.exe`** (in-box since Windows 10 1803) for the default SSO transport
  (`--negotiate -u :`, authenticates as the logged-in Windows user). The pure logic and the tests run on any OS.
- A reachable on-prem DATEVconnect server (not included; no vendor spec is shipped).

## Install

```
pip install .                     # from this directory
pip install "datev-dokab @ git+https://github.com/<owner>/datev-dokab.git@v0.1.0"
pip install -e .[dev] && pytest   # development
```

## Configuration

`datev.config.json` (`base_url`, `auth`, `user`, `password`, `verify_tls`) is read **only next to
the executable** when frozen, or from the folder named by the environment variable
`DATEV_CONFIG_DIR` (source/dev runs), otherwise from the folder containing the `datev` package.
It is **never** read from the current working directory.
The built-in default host `your-datev-server:58452` is a placeholder; set the real host in the config.

## Security notes

- The DATEV host must be **https only**, without credentials in the URL; other schemes are rejected
  and fall back to the placeholder. curl runs with `--proto =https --proto-redir =https`.
- The config is never taken from the CWD (a planted file next to a received document could redirect
  SSO traffic to an attacker host).
- `curl.exe`/`whoami.exe` are invoked by absolute System32 path.
- Write-back is guarded: any non-ok verdict writes nothing. DokAb keeps no revision, so an accepted
  write-back is a permanent overwrite (callers should back up first, as `DatevService` does).
- Vendor OpenAPI specs are vendor IP and are deliberately not part of this repository.

## Trademark notice

DATEV and DATEVconnect are trademarks of DATEV eG. This project is an independent, unofficial client and is
**not affiliated with, endorsed or sponsored by DATEV eG**. The name is used only to describe the system this
library talks to. No DATEV specification or other vendor material is included.

## License

AGPL-3.0-or-later, see [LICENSE](LICENSE) and [COPYING](COPYING) (full AGPL text) - the same as the main project. As in the main project
([DigitalerUnterlagenOrdner](https://github.com/tobiasheinrichfaska/DigitalerUnterlagenOrdner)), a
**commercial license** is available for closed-source or proprietary use (contact:
tobias.a.w.heinrich@gmail.com; terms in that repository's `LICENSE_COMMERCIAL.md`). Contributions
are subject to the project's **Contributor License Agreement** (see `CONTRIBUTING.md` of the main
repository): you grant the maintainer a perpetual, worldwide, non-exclusive, royalty-free,
irrevocable right to use, modify and redistribute your contribution under any license, including
commercial licenses.
