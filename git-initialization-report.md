# Craftbox: Git initialization readiness report

Date: 2026-11-05 · Location audited: `D:\Development\craftbox` · Craftbox 0.3.0

**Verdict: ready for a first commit once you approve the steps in section 10.** No secrets were found. No old-path references exist in anything that would be committed. The app launches from the new location and all 248 tests pass.

Changes made during this audit: `.gitignore` was rewritten (section 3) and this report was created. Nothing else was changed, and no Git operation was run in the project. To test the ignore rules I used a throwaway repository in the scratch folder, outside the project.

## 1. Git state

| Check | Result |
|---|---|
| `.git` in project root | None |
| Nested repositories (`.git`, `.gitmodules`, `.hg`, `.svn`) | None, including inside `.venv` |
| Git installed | 2.53.0.windows.1 |
| Git identity | `user.name` and `user.email` are set globally |
| `core.autocrlf` / `core.eol` | Not set globally (see section 7) |

## 2. Project inventory

2,589 files and 141.7 MB on disk, of which **258 files (about 2.4 MB) are commit candidates**. The rest is `.venv` (about 2,300 files, including a 90 MB Playwright `node.exe`) and `__pycache__`.

| Area | Contents | Commit? |
|---|---|---|
| `app/` | FastAPI server, 23 craft folders (manifest, engine, fixtures, schemas), 20 JSON schemas, static UI (`app/static`) | Yes |
| `tests/` | 248 tests: API, engines, samples, and Playwright browser tests | Yes |
| `samples/` | Sample treatments, plans, shot lists, and Art Library registers and manifests (`samples/art`), light and change-tracking samples. Required by the `test_*_samples` tests. | Yes |
| `guidelines/` | `ui-standard.md`, `feature-template.md`, `story-process.md` | Yes |
| `docs/` | Implementation reports, acceptance checklists, development standards | Yes |
| `scripts/`, `examples/` | `check_env.py`, `make_*samples.py`, `pipeline.py` | Yes |
| Root files | `README.md`, `CLAUDE.md`, `craftbox-roadmap.md`, `requirements*.txt`, `start-craftbox.bat` | Yes |
| `.venv/` | Python 3.13.2 virtual environment | No |
| `data/` | `craftbox.db` (68 KB, one experiment named "Opening Scene") and `logs/craftbox.log` | No |

Dependencies: `requirements.txt` (fastapi, uvicorn) and `requirements-dev.txt` (httpx, playwright). Installed versions satisfy the pins: fastapi 0.162.0, uvicorn 0.54.0, httpx 0.28.1, playwright 1.64.1.

**Where the Art Library lives.** The Art Library has no source-controlled storage of its own. Its working data is in the SQLite database (experiments and runs) and in `data/assets/<aa>/<sha256>.<ext>`, a content-addressed image store. Neither exists in a committable form. `data/assets/` does not exist yet. The Art Library metadata worth preserving is the sample set in `samples/art/` and `app/crafts/art_direction/` (fixtures and schemas), and both are kept by the new `.gitignore`.

## 3. `.gitignore`

The old file had 8 rules: caches, `.venv`, `.env`, `output/`, `data/`, and `pilot-edit-plan.json`. It is now grouped by purpose:

- Python environments and caches: `.venv/`, `venv/`, `__pycache__/`, `*.py[cod]`, `*.pyd`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `build/`, `dist/`, `*.egg-info/`
- Secrets: `.env`, `.env.*` (with `!.env.example` kept), `*.pem`, `*.key`, `*.pfx`, `*.p12`, `*.crt`, `secrets/`, `credentials*.json`, `*token*.json`
- Local data and temp files: `data/`, `*.db`, `*.db-wal`, `*.db-shm`, `*.sqlite*`, `*.log`, `*.part`, `*.tmp`, `*.bak`, `tmp/`
- Generated output: `output/`, `outputs/`, `renders/`, `generated/`, `exports/`, `pilot-edit-plan.json`
- Media: `*.mp4 *.mov *.mkv *.avi *.webm *.wav *.mp3 *.flac *.exr *.blend *.psd`
- Model weights and large downloads: `models/`, `weights/`, `checkpoints/`, `*.safetensors *.ckpt *.pt *.pth *.onnx *.gguf *.bin`, archives
- Playwright artifacts: `test-results/`, `playwright-report/`, `traces/`, `screenshots/`
- Editor and OS files: `.vscode/`, `.idea/`, `Thumbs.db`, `desktop.ini`

**Deliberate choice:** image formats (`.png`, `.jpg`, `.svg`) are not ignored globally, so future UI assets and test images are not lost silently. Generated images are excluded by location instead (`data/`, `output/`, `renders/`, `generated/`, `exports/`).

**Verified in a throwaway repository** (outside the project):

- All 258 existing source files are un-ignored.
- `.venv`, caches, `data/*`, `.env*`, keys, output, media and weights are ignored.
- Sample treatments, `app/static/art.js`, `guidelines/ui-standard.md` and `.env.example` are not ignored.

Watch-outs: `*.bin`, `*.zip` and `*.log` are broad. If a legitimate small binary fixture is added later, force-add it with `git add -f` or add a `!` exception.

## 4. Hard-coded paths to the old directory

The old location was `E:\Cloud Storage\Dropbox\Projects\allPython\craftbox`.

| Where | Finding | Action |
|---|---|---|
| Source code, scripts, tests, launcher | **None.** Paths come from `Path(__file__)`, `%~dp0`, or `CRAFTBOX_DATA_DIR`. | None |
| `data/logs/craftbox.log` | Old `data_dir` recorded in 5 log lines | Ignored; harmless |
| `.venv/pyvenv.cfg`, `.venv/Scripts/activate*` | Old path embedded (virtualenvs are not relocatable) | Ignored; see section 9 |
| `README.md:59` | "Dropbox note" says the project may live in Dropbox | Stale, optional edit after first commit |
| `docs/dreambox-overlap-audit.md:3` | Mentions `E:\...\allPython\dreambox` as a historical audit reference | Prose only; keep or genericize |
| `craftbox-roadmap.md:9,225` | Mentions a `craftbox-starter` working directory | Prose only |
| `app/static/artlib.js`, `app/assetstore.py` | `C:\Pictures\oak.png` and `C:\` are UI placeholder examples | Not real paths |

## 5. Secrets and sensitive data

Scanned all non-`.venv` files for API keys, tokens, passwords, bearer tokens, private-key headers and cloud-key prefixes (AWS, GitHub, Slack, OpenAI-style).

- **No secrets found.** The only hits are environment-variable *names* in `app/ai_adapters.py` (`OPENAI_API_KEY`, `GEMINI_API_KEY`, `VENICE_API_KEY`), which are disabled stubs, plus policy text saying keys are never stored.
- No `.env`, `.pem` or `.key` files exist outside `.venv`. The two `.pem` files are certifi CA bundles.
- `data/craftbox.db` holds your own experiment content ("Opening Scene"), so it is excluded.
- The code makes no outbound network calls, and `localhost` is the only host used.
- Personal data in committed files: none found. The Git identity `Chakravarthy Tenneti <tenneti.chakravarthy@gmail.com>` will appear in commit metadata. Confirm that is what you want on the repository.

## 6. `.gitattributes` (recommended, not created)

All 258 files currently use CRLF, except the new `.gitignore`, which has LF. Recommended contents:

```gitattributes
# Let Git detect text files; store LF in the repository.
* text=auto

# Windows scripts must stay CRLF in the working tree.
*.bat text eol=crlf
*.cmd text eol=crlf
*.ps1 text eol=crlf

# Shell scripts must stay LF.
*.sh text eol=lf

# Source and data: LF in the repository.
*.py   text diff=python
*.js   text
*.html text
*.css  text
*.json text
*.md   text
*.csv  text
*.txt  text
*.fountain text

# Binary: never alter.
*.png  binary
*.jpg  binary
*.gif  binary
*.webp binary
*.ttf  binary
*.db   binary
```

Also recommended: run `git config core.autocrlf false` for this repository, so `.gitattributes` is the single source of truth. After the first commit, run `git add --renormalize .` and confirm the diff is clean.

Caution: `output_sha256` and `input_hash` values are computed by the app. The sample tests passed with CRLF files. After the first fresh clone, re-run `unittest discover -s tests` once to confirm line-ending normalization does not affect any fixture hash.

## 7. Files that must stay outside Git but are needed to run Craftbox

| Item | Needed for | How it is restored on a new machine |
|---|---|---|
| `.venv/` | Launching | `start-craftbox.bat` recreates it automatically with `py -3 -m venv .venv` and `pip install -r requirements.txt`. For tests, also run `pip install -r requirements-dev.txt`. |
| Python 3.10 or newer, with the `py` launcher | Launching | Install from python.org |
| `data/craftbox.db`, `data/assets/` | Your saved experiments, runs, approvals and Art Library | The app creates an empty database on first run (verified). **Existing work is not recoverable from Git.** Back it up separately. |
| Playwright Chromium (`%LOCALAPPDATA%\ms-playwright`) | Browser tests only | `python -m playwright install chromium` |
| API keys | Nothing today (the AI adapters are stubs) | Set environment variables when needed, never files |

## 8. Launch and test verification

Run from `D:\Development\craftbox`, with scratch data directories so your real `data\` was never touched (`craftbox.db` modification time is unchanged, 2026-11-01 20:45):

- `scripts/check_env.py` passed: Python 3.13.2, `.venv` at the new D: path, fastapi and uvicorn import, data directory writable, port 8099 free.
- `start-craftbox.bat` launched with `CRAFTBOX_PORT=8199`, `CRAFTBOX_NO_BROWSER=1` and a scratch `CRAFTBOX_DATA_DIR`. `GET /` returned **HTTP 200**, the log showed `app.started` for version 0.3.0 with DB schema 2, and the port was free again after I stopped the process I started. (`/api/health` returns 404 because that route does not exist; it is not a defect.)
- `python -m unittest discover -s tests` ran **248 tests, all OK** in 97 s, including the Playwright browser tests.
- A first launch attempt from Git Bash failed only because of how I invoked `cmd`, not because of Craftbox.

## 9. Issues and recommendations

1. **Recreate `.venv` (recommended).** It works because `python.exe -m app.run` only needs `pyvenv.cfg`'s `home` path, which points at the system Python. But `activate*` scripts and the `.venv\Scripts\*.exe` launchers (`pip.exe` etc.) still carry the old E: path, so `activate` and `pip.exe` can misbehave. Fix: delete `.venv` and let `start-craftbox.bat` rebuild it. This needs your approval because it deletes files.
2. **Stale references in `guidelines/ui-standard.md`.** It was copied from another project and mentions `backend/api/static/ui.js`, `core/jobqueue.py` and `tests/ui/ui_contract.py`. In Craftbox these are `app/static/ui.js` and `tests/ui_contract.py`. I did not edit it, because that is a guideline document rather than UI work. A follow-up edit to fix the paths is worthwhile.
3. **No `tests/__init__.py`.** The documented command (`unittest discover -s tests`) works. `-t .` fails. This is expected, not a bug.
4. **Create `.env.example`.** The `.gitignore` already allows it. It is optional while no keys are used.
5. **`.gitignore` uses LF line endings** while everything else is CRLF. The `.gitattributes` above resolves this.
6. Test runs print a Starlette deprecation warning about `httpx` vs `httpx2`. It does not affect the commit.

## 10. Proposed next steps (awaiting your approval; none have been run)

```powershell
cd D:\Development\craftbox
# 1. Create .gitattributes (content in section 6)
git init -b main
git config core.autocrlf false
git add --dry-run .          # review the file list: expect about 258 files
git add .
git status                   # confirm no .venv, data, or secrets are staged
git commit -m "Initial commit: Craftbox 0.3.0"
git remote add origin <your private repo URL>
git push -u origin main
```

I need from you:

- Approval to create `.gitattributes` and run `git init`, with the branch name (`main`?).
- The private repository URL.
- Whether to proceed with the optional `.venv` rebuild (item 1 above), and whether to fix the `ui-standard.md` paths before or after the first commit.
- Confirmation of the commit author identity, and whether the commit message should carry a Claude co-author trailer, since this session's attribution guidance adds one by default.
