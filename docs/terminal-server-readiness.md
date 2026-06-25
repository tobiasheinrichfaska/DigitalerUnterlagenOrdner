# Briefing — make the build/install pass current AND Terminal Server (RDS) installs

**Audience:** a Claude session refining BelegTool's build & install.
**Goal:** the installer must work for **both** (A) today's single-user / per-machine desktop
installs *and* (B) future **Terminal Server / RDS multi-user** installs — concurrent
non-admin users on one machine, roaming **FSLogix** profiles. Don't regress A while adding B.

---

## Where we are (what already works)

- **onedir** PyInstaller build (`build.ps1`) → `dist\BelegTool\BelegTool.exe` (pywebview + React, Edge WebView2).
- **Machine-wide installer** [`packaging/install-machinewide.ps1`](../packaging/install-machinewide.ps1):
  copies onedir → `C:\Program Files\BelegTool`, registers `.belegtool` in **HKLM** (ProgID
  `BelegTool.Document`), adds an ARP/uninstall entry, `-Uninstall`. **This is the RDS-correct
  install model** and is the one to build on. Verified installing on a real RDS host.
- **MSIX** ([`packaging/`](../packaging/README.md)) is **per-user / Store-only**. ⚠️ Do **not** use MSIX
  for RDS: per-user MSIX state does not roam under FSLogix → the `.belegtool` association breaks at
  logoff / "package not found". (This was the real-world failure that motivated the machine-wide path.)

## What's already RDS-safe (keep — don't regress)

| Concern | Status | Where |
|---|---|---|
| Logs under `%LOCALAPPDATA%` (not the install dir) | ✅ | [`infra/log_config.py`](../infra/log_config.py) |
| Temp/warm + materialized-view dirs in per-user `%TEMP%` | ✅ | `tempfile.gettempdir()` in [`host.py`](../host.py), [`core/api.py`](../core/api.py) (`beleg_view_*`) |
| IPC pipe name is **per-user** (`belegtool-core-<user>`) | ✅ | [`core/ipc/pipe.py`](../core/ipc/pipe.py) `default_pipe_name` (and the GUI path is in-process anyway) |
| File association in **HKLM**, one handler for all users | ✅ | `install-machinewide.ps1` |
| WebView2 runtime **detected** at startup, fails loudly not blank | ✅ | `host.py` `_webview2_installed` / `_warn_missing_webview2` |

## The refinements (prioritized)

### P1 — WebView2 user-data folder MUST be per-user (the one real gap)
`webview.start(_prewarm, http_port=…)` ([`host.py`](../host.py) ~L394) passes **no `storage_path`**, so
the Edge WebView2 **user-data folder** (UDF: `Default/`, `GPUCache/`, `Code Cache/`, `blob_storage/`)
is created at pywebview's default location. On a desktop this is usually fine; on **RDS it's the top
risk**: if it lands next to the exe in `C:\Program Files\BelegTool`, **standard users can't write there
→ blank window / launch failure**, and two concurrent users would collide.
- **Fix:** set an explicit **per-user** UDF, e.g. `webview.start(..., storage_path=<%LOCALAPPDATA%\BelegTool\WebView2>)`
  (and/or export `WEBVIEW2_USER_DATA_FOLDER` before the runtime loads). Create the dir if absent.
- **Verify** (this is currently UNVERIFIED): launch as a **non-admin** user with the app in
  `C:\Program Files\BelegTool` and confirm the UDF is created under the user's profile, the UI renders,
  and a second concurrent user gets an independent UDF.
- **Audit rule:** nothing the app writes at runtime may target the **install dir** or **HKLM** — all
  per-user state goes under `%LOCALAPPDATA%` / `%APPDATA%` / per-user `%TEMP%`.

### P2 — Terminal Server install semantics
- An RDS app should install in **install mode** (`change user /install` … `change user /execute`) so
  per-machine registration is correct. Document this for `install-machinewide.ps1`, or better ship an
  **MSI** (e.g. WiX wrapping the onedir) — MSIs handle TS install mode, silent `/qn`, ARP, and
  GPO/SCCM/Intune Win32 deployment cleanly. Recommend an MSI as the enterprise/RDS deliverable
  (keep the PS installer for ad-hoc, MSIX for the Store).

### P2 — WebView2 runtime guarantee on Server SKUs
Windows Server / minimal images often **lack** the in-box WebView2 runtime. The installer should
**ensure** it (bundle the Evergreen bootstrapper and run it if `_webview2_installed()` is false, or
declare the dependency) so RDS rollout doesn't blank-window on first launch.

### P2 — FSLogix profile hygiene (roaming)
The per-user WebView2 UDF caches (`GPUCache`/`Code Cache`/`blob_storage`) are churny and bloat/risk the
FSLogix container. Ship guidance (a sample `redirections.xml`) to **exclude the BelegTool cache
subfolders** from the profile container — pairs with the P1 UDF path (put cache somewhere excludable).

### P3 — Code signing
Sign `BelegTool.exe` + the installer for distribution — avoids SmartScreen/AV friction on enterprise/RDS
(the unsigned zip already trips Norton/SmartScreen, see `packaging/README.md`).

### Updates on RDS
No per-user auto-update on RDS. Update = admin re-runs the machine-wide installer (or `-Uninstall` +
reinstall) **in a maintenance window** with users off; the onedir in Program Files is replaced. The
planned update-checker must stay **admin-driven** (no silent auto-install) for the RDS install.

## Acceptance test matrix (definition of done for B)
1. Clean **Windows Server + RDS role**; machine-wide install (install mode); WebView2 ensured.
2. **Two different non-admin users**, concurrent sessions: each launches BelegTool, opens a
   `.belegtool`, edits, saves, exports → **no collisions** (independent WebView2 UDF, temp, pipe).
3. **Logoff → logon**: the `.belegtool` association and the app persist (machine-wide, not per-user).
4. **Double-click** `.belegtool` resolves to the single HKLM handler for **every** user.
5. **FSLogix**: container does not bloat with WebView2 cache (exclusions applied); no per-user MSIX in play.
6. A/desktop install still works unchanged (no regression).

## Out of scope / keep as-is
- MSIX remains the **Store / single-user** path — not for RDS.
- Don't reshape OS-owned scheduled tasks or rely on per-user registration for the association.
