# AI Coding Assistant – Task Breakdown (`agents.md`)

*Last updated: 16 July 2025*

---

## 🎯 Primary mission: **Zero‑friction install for everyday Windows pilots**

> We now treat *"novice Windows hobbyists"* as **the** target persona. All roadmap items must ladder up to a "double‑click and go" experience; professional cross‑platform users are still served via Docker/CLI, but they are *not* the optimisation focus.

Claude’s audit highlighted five blockers (Python, PATH, FFmpeg, ExifTool, CLI fear). Below are the two **turnkey on‑ramps** that must be production‑ready *before* v1.0.  After those ship we loop back to polish cross‑platform/advanced features.

---

### 1 · PowerShell Bootstrap Script (📜 `tools/bootstrap.ps1`)

| Step | What the script does                                                                                                                      | Implementation hints                                              |
| ---- | ----------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| 1    | **Self‑elevate if needed**, or fall back to user‑mode install when corporate GPOs block admin rights.                                     | Use `#Requires -RunAsAdministrator` and graceful downgrade logic. |
| 2    | Ensure **Python ≥ 3.10** – Install silently from MS Store, else `winget` fallback.                                                        | Print friendly emoji feedback (✔ Installed / ⚠ Skipped).          |
| 3    | Download & verify **static FFmpeg + ExifTool** bundles from GitHub Release assets, then extract to `%LOCALAPPDATA%\dji‑embed\bin`.        | SHA‑256 validation + retry on hash mismatch.                      |
| 4    | `pip install --upgrade dji‑metadata‑embedder` into the freshly‑installed Python env.                                                      | No global PATH edits if user‑mode; rely on shim script.           |
| 5    | Update PATH for the **current session** so the user can type `dji-embed` immediately; persist PATH for future shells when policy permits. | `[Environment]::SetEnvironmentVariable -Scope User`.              |
| 6    | Auto‑launch **wizard UI** (`dji-embed wizard`) or **drag‑&‑drop GUI** once Task C2 ships.                                                 | Provide `-NoLaunch` flag for automation.                          |

---

### 2 · winget One‑liner installer (Task A2)

```powershell
winget install -e --id CallMarcus.DJI-Embed
```

This single package **bundles** the PyInstaller build *and* the needed binaries. Advanced users can still install individual deps as before.

\---- | --------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- | | 1    | **Self‑elevate** if not running as Admin.                                                                 | `#Requires -RunAsAdministrator` or `Start-Process -Verb runAs`. | | 2    | Detect **Python ≥ 3.10**; if absent, install via the Microsoft Store silent CLI (`storecli install`).     | Fallback: winget.                                               | | 3    | Grab **static FFmpeg + ExifTool zips** from GitHub Releases, extract into `%LOCALAPPDATA%\dji‑embed\bin`. | Use SHA‑256 checksum validation.                                | | 4    | Run `pip install --upgrade --no‑cache-dir dji‑metadata‑embedder` *inside the same PowerShell session*.    | Works even if system Python just got installed.                 | | 5    | Add `%LOCALAPPDATA%\dji‑embed\bin` and `%APPDATA%\Python\Scripts` to the *current user* PATH (no reboot). | `[Environment]::SetEnvironmentVariable` with "User" scope.      | | 6    | Launch `dji-embed wizard` so the pilot sees the Rich UI immediately.                                      | Optional banner + analytics ping.                               |

**Call to Codex (completed):**

* Write `tools/bootstrap.ps1` (< 150 lines) with verbose logging and a `-Silent` flag. **✓ Done**
* Add a CI job (`windows‑bootstrap‑smoke‑test`) that spins up a fresh `windows-latest` GH runner, executes the script, and asserts `dji-embed --version` works. **✓ Done**
* Update `docs/installation.md` with a copy‑paste one‑liner: **✓ Done**

  ```powershell
  iwr -useb https://raw.githubusercontent.com/CallMarcus/dji-drone-metadata-embedder/master/tools/bootstrap.ps1 | iex
  ```

---

### 2 · **winget** One‑liner Paths

Once the winget manifests are accepted upstream (Task A2), users can either:

```powershell
# Full meta‑installer (bundles Python, FFmpeg, ExifTool)
winget install -e --id CallMarcus.DJI-Embed

# OR step‑by‑step manual path if they want granular control
winget install -e --id Python.Python.3
winget install -e --id Gyan.FFmpeg
winget install -e --id PhilHarvey.ExifTool
pip install dji-metadata-embedder
```

**Winget packaging tasks for Codex (completed):**

1. Add `installer.yaml` to `.github/winget/` (upgrade‑safe). **✓ Done**
2. GH Action `publish-winget.yml` builds the PyInstaller EXE and submits a PR to `microsoft/winget-pkgs` via `wingetcreate`. **✓ Done**
3. On success, bump README badges (`winget | GitHub Release | PyPI`). **✓ Done**

---

## ⛭ Rolling this into the existing roadmap

Add the following under **Phase 1 – Foundation** in the primary `agents.md` roadmap:

| Ref      | Task                                                                    | Owner | Status |
| -------- | ----------------------------------------------------------------------- | ----- | ------ |
| **A1.4** | `tools/bootstrap.ps1` with CI smoke‑test                                | Codex | ☑ DONE |
| **A2.1** | winget full package manifest (`CallMarcus.DJI-Embed`)                   | Codex | ☑ DONE |
| **A2.2** | Incremental winget manifests for Python, FFmpeg, ExifTool references    | Codex | ☐ TODO |
| **P1.1** | **PyPI trusted‑publisher hookup** – finish `release.yml` & first upload | Codex | ☐ TODO |

---

### 🔑 **P1.1 – PyPI trusted‑publisher hookup**

*Problem:* PyPI shows "pending publisher" because no workflow run has yet *signed in* via OIDC.

**Acceptance criteria**

1. `release.yml` builds sdist + wheel via `pypa/build` and then publishes with **`pypa/gh-action-pypi-publish`** using **trusted‑publisher** (OIDC) – *no API token needed*.
2. The workflow is attached to the **Environment** selected in PyPI (or "Any" if no env).  Add `environment: pypi` in the `deploy` job.
3. Upload succeeds on a signed Git tag starting with `v`, e.g. `v0.3.0`, and PyPI project page shows the artefacts within \~2 min.
4. README badge auto‑displays the new version.

**Steps for Codex**

1. Update **`release.yml`**:

   ```yaml
   permissions:
     id-token: write      # allow OIDC auth with PyPI
     contents: read       # minimal required
   jobs:
     deploy:
       environment: pypi  # must match PyPI "pending" line
       steps:
         - uses: actions/checkout@v4
         - uses: pypa/gh-action-pypi-publish@release/v1
           with:
             print-auth-token: false  # safety
             skip-existing: true
   ```
2. In PyPI **Settings → Trusted Publishers** select *GitHub Actions*, repo `CallMarcus/dji-drone-metadata-embedder`, branch pattern `refs/tags/v*`, environment `pypi`.
3. Commit, push, then create annotated tag `v0.3.0` – trigger workflow.
4. If success, tick this task.

📌 *Fallback:* For testing you can still use a classic `PYPI_API_TOKEN` secret; OIDC is preferred.

---

## 📑 Documentation delta

* **docs/installation.md** gets a new *“Windows quick‑start”* heading with:

  1. The PowerShell one‑liner;
  2. The single‑command winget install;
  3. A footnote on corporate PCs (no Store).
* **docs/faq.md** gains *“My antivirus blocked the EXE”* and *“Winget cannot find package”* entries.

---

> **Outcome:** A Windows DJI hobbyist with zero Python or CLI knowledge can embed GPS metadata in < 3 minutes and 1‑2 clicks. That knocks out pain‑points #1–4 and slashes onboarding friction.

---

