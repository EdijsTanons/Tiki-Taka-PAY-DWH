# TikiTaka PAY DWH — test → build → NSIS → commit → push

Run the full release pipeline for this project in this exact order:

## 1. Check git status
Run `git status --short` and `git log --oneline -3` so we know what is uncommitted and where HEAD is.

## 2. Run the test suite
Use the venv pytest directly (no `uv` on PATH):
```
c:\Users\edijs.tanons\Documents\Git\TikiTaka DWH\.venv\Scripts\pytest.exe --tb=short -q
```
All tests must be **green** before proceeding. If any fail, stop, report the failures, and wait for the user to fix them.

## 3. Stage and commit any pending changes
- `git add -A` to stage everything that is not already staged.
- Ask the user for a commit message, or propose one based on what changed (follow Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, etc.).
- End every commit message with:
  ```
  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
  ```
- If nothing is uncommitted, skip this step.

## 4. PyInstaller build
Run from the repo root using the venv executable:
```
c:\Users\edijs.tanons\Documents\Git\TikiTaka DWH\.venv\Scripts\pyinstaller.exe packaging/pyinstaller.spec --noconfirm
```
Output lands in `dist/TikiTakaPAYDWH/`. The spec file is `packaging/pyinstaller.spec`.
Watch for **errors** in the last 30 lines of output; warnings about `pycparser.lextab` / `pycparser.yacctab` are benign and can be ignored.

## 5. NSIS installer build
Run from `packaging/windows/`:
```
& "C:\Program Files (x86)\NSIS\makensis.exe" installer.nsi
```
Output: `packaging/windows/TikiTakaPAYDWH-Setup-x64.exe`
Confirm the file was created and report its size in MB.

**NSIS is NOT committed to git** — `.gitignore` excludes `packaging/windows/*.exe`.

## 6. Push to GitHub
```
git push origin main
```
The remote is `https://github.com/EdijsTanons/Tiki-Taka-PAY-DWH.git`.

## Key facts about this project
- **Venv location:** `c:\Users\edijs.tanons\Documents\Git\TikiTaka DWH\.venv\Scripts\`  
  (`uv` is not on PATH — always use venv binaries directly)
- **PyInstaller spec:** `packaging/pyinstaller.spec` (one-folder build → `dist/TikiTakaPAYDWH/`)
- **NSIS script:** `packaging/windows/installer.nsi`  
  Version defines at top: `APP_VERSION`, `VER_MAJOR`, `VER_MINOR` — bump all three when releasing a new version, along with `pyproject.toml` and `src/tikitaka_dwh/__init__.py`
- **Hidden imports:** all `tikitaka_dwh.*` modules must be listed in `pyinstaller.spec`'s `hidden` list — new UI modules added without updating this list cause silent runtime crashes in the packaged exe
- **Data dir** (`%LOCALAPPDATA%\TikiTakaPAYDWH`) is separate from the install dir (`%LOCALAPPDATA%\Programs\TikiTakaPAYDWH`) — the NSIS installer/uninstaller intentionally never touches the data dir
- **50 tests** in `tests/` — run all of them; none should be skipped
