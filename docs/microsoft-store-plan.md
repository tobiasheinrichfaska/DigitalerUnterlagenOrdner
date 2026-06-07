# Microsoft Store publication plan (MSIX)

> **Goal:** distribute BelegTool via the Microsoft Store so it is **Microsoft-signed** and
> served through a trusted channel — which stops antivirus (Norton CyberCapture) and
> SmartScreen from flagging the unsigned PyInstaller bundle (the v3.8.0 tester crash:
> Norton sandboxed `Python.Runtime.dll`, the app wouldn't start). Bonus: auto-updates and
> clean `.belegtool` file-association registration. Cheaper than buying an OV/EV cert
> (one-time dev-account fee, Microsoft does the signing).
>
> Status: **plan / not started.** Alternative if we stay off the Store: **Azure Trusted
> Signing** (cheap cloud Authenticode signing for the existing zip) — see Deferred items.

## Naming — decide the permanent identity first

Only the **package identity / Package Family Name** (generated from the *first* reserved
name) is **permanent**; you can reserve several names and the **display name is editable
per submission**. So:

- **Identity (permanent):** pick a **distinctive** string — *not* the generic, hard-to-own
  "BelegTool". (Decision pending + a DPMA/EUIPO trademark check.)
- **Display name (editable):** **"BelegTool"** — good German discoverability ("Beleg").
- `DigitalerUnterlagenOrdner` stays the **repo name only** (weak consumer brand).

Availability (checked): no existing Store app uses "BelegTool" / "DigitalerUnterlagenOrdner".
A feature competitor, **dokublick**, exists in the niche (not a name clash). "Belegtool" is
generic/descriptive → weak/hard to defend; trademark check still owed.

## Steps

### Phase 0 — Decide & set up
1. Lock the **permanent identity name** + publisher type (Individual = Tobias Heinrich, vs Company).
2. Register a **Partner Center / Microsoft Store developer account** (one-time fee).
3. Publish a **privacy policy** URL (required) — host on the GitHub Pages homepage.
4. Channels: **Store for stable + GitHub zip for betas** (keep beta iteration fast).

### Phase 1 — Feasibility spike (before any account spend)
5. Build a **test MSIX** from `dist\BelegTool` (`runFullTrust`), self-sign, sideload-install.
6. Verify on a clean machine (ideally with **Norton**):
   - launches with **no CyberCapture/SmartScreen block** (the whole point);
   - **WebView2 + pythonnet/clr** load (the component Norton tripped on);
   - open / save / export; the **`.bak`**; **file lock on an SMB share**; **Office COM import**;
     `.belegtool` **file association**.
7. Finalise the **capabilities** list (likely `runFullTrust` + `broadFileSystemAccess`).

### Phase 2 — Packaging
8. Add MSIX packaging beside `build.ps1` (MSIX Packaging Tool or Advanced Installer).
   Manifest: Identity (= reserved name), DisplayName "BelegTool", version (`version_info.py`),
   capabilities, **`.belegtool` file-type association**, WebView2 dependency, icons/assets.
9. Store assets: logos (44×44, 150×150, …), screenshots, listing text (DE + EN), category
   **Productivity**.

### Phase 3 — Submit & certify
10. Partner Center: reserve name(s) → create product → upload MSIX → listing, **age-rating**
    questionnaire, markets, **Free** pricing, privacy-policy URL.
11. **Justify `broadFileSystemAccess`** (restricted capability → extra review): opens/saves
    user-selected `.belegtool` files anywhere incl. network shares; single-writer lock on
    shared stores.
12. Submit → certification (hours–days) → published & **Microsoft-signed**.

### Phase 4 — Ops
13. Updates: bump version → repackage MSIX → submit → Store auto-updates users. Keep GitHub
    betas in parallel.

## Risks to watch
- `broadFileSystemAccess` review scrutiny.
- WebView2 runtime handling inside the MSIX container.
- **DATEV** "open for edit / check-in" may behave differently for a packaged app — test in the
  spike (file-association registration could help; see the open DATEV check-in question).
- Open-source / AGPLv3 + commercial dual-license is fine on the Store.
