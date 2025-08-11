# Agents.md — dji-drone-metadata-embedder

_Last updated: 2025-08-09_

## Purpose
This file defines how AI coding agents (e.g. ChatGPT Codex, Claude Code) contribute to this repository in a predictable, high-quality way.  
Agents are expected to follow these instructions unless explicitly told otherwise.

---

## 1. Repository Context
- **Repo:** [CallMarcus/dji-drone-metadata-embedder](https://github.com/CallMarcus/dji-drone-metadata-embedder)
- **Default branch:** `main`
- **Language:** Python 3.10–3.12
- **CI:** GitHub Actions
- **Tests:** `pytest`
- **Package:** `pip` (`pyproject.toml` + optional `requirements.lock`)
- **CLI entry point:** `dji-embed`

---

## 2. Operating Rules for Agents

### 2.1 General Workflow
1. Select an open issue from GitHub (see [Milestones](#4-milestones--scope-overview)), oldest first unless told otherwise.
2. Read the **entire issue body** and acceptance criteria.
3. Work in a **feature branch**:
   ```
   feat/issue-<ISSUE#>-<short-summary>
   ```
4. Make the **minimum set of changes** to meet acceptance criteria.
5. Add/adjust **tests** and **documentation**.
6. Run tests locally:
   ```bash
   pytest -q
   ```
7. Open a PR referencing the issue:
   ```
   feat: <issue title> (#<ISSUE#>)
   ```
8. Use the PR template and tick all relevant checkboxes.
9. If blocked, open a **draft PR** with a note explaining the blocker and proposed options.

---

### 2.2 Coding Standards
- Follow [PEP 8](https://peps.python.org/pep-0008/) style.
- Keep functions short and purpose-driven.
- Prefer existing dependencies over adding new ones.
- No large media files (>1 MB) — generate test fixtures programmatically where possible.
- Don’t change release version numbers unless the issue is explicitly about a release.

---

### 2.3 Testing & CI
- All changes must be covered by tests (`pytest`).
- Code must pass in **Windows & Linux** CI matrix (Python 3.10–3.12).
- CLI changes must include at least one smoke test (`--help`, `--version`).
- Parser changes require golden-file tests where applicable.

---

### 2.4 Documentation
- Update `README.md` for new CLI flags or commands.
- Add troubleshooting entries for known error patterns.
- Keep examples **copy-pasteable** and minimal.

---

## 3. How to Ask an Agent to Work

### 3.1 One-Shot Prompt — Single Issue
Use when you want the agent to handle a specific issue end-to-end:

```
You are contributing to the GitHub repo CallMarcus/dji-drone-metadata-embedder.

Task: Implement issue #<NUMBER>. Read the issue description and acceptance criteria and deliver a PR.

Rules:
- Branch: feat/issue-<NUMBER>-<kebab-summary>
- Minimal changes to satisfy acceptance criteria
- Add/update tests (pytest)
- Update docs if CLI changes
- Run tests locally and ensure CI passes on Windows & Linux
- Open a PR titled "<type>: <issue title> (#{NUMBER})"
- If blocked, open a draft PR with blocker note
```

---

### 3.2 Multi-Issue Prompt — Work a Milestone
Use when you want sequential work through a milestone:

```
Context: Repo CallMarcus/dji-drone-metadata-embedder.

Goal: Process all OPEN issues in milestone "M<NUMBER> – <title>" from lowest to highest number.

For each issue:
1. Implement per acceptance criteria.
2. Add/adjust tests and docs.
3. Open a PR and post the link.
4. WAIT for confirmation before next issue.

Rules:
- One issue per PR.
- Keep PRs focused.
- If blocked, open draft PR with blocker description.
```

---

## 4. Milestones & Scope Overview

**[M1 – Stabilise & Version Cohesion](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues?q=is%3Aopen+is%3Aissue+milestone%3A%22M1+%E2%80%93+Stabilise+%26+Version+Cohesion+%28Week+1%E2%80%932%29%22+sort%3Acreated-asc)**  
- Single-source versioning  
- Tag-driven releases  
- SHA256 + toolchain version output

**[M2 – CI/Build Reliability](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues?q=is%3Aopen+is%3Aissue+milestone%3A%22M2+%E2%80%93+CI%2FBuild+Reliability+%28Week+2%E2%80%933%29%22+sort%3Acreated-asc)**  
- Windows + Linux matrix  
- Smoke tests with tiny fixtures  
- Pin toolchain & deps

**[M3 – Parser Hardening & CLI UX](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues?q=is%3Aopen+is%3Aissue+milestone%3A%22M3+%E2%80%93+Parser+Hardening+%26+CLI+UX+%28Week+3%E2%80%935%29%22+sort%3Acreated-asc)**  
- Golden-file tests for DJI model families  
- `--lenient`, `--time-offset`, `validate` command  
- Consistent exit codes & JSON log option

**[M4 – Docs, Samples & Release Hygiene](https://github.com/CallMarcus/dji-drone-metadata-embedder/issues?q=is%3Aopen+is%3Aissue+milestone%3A%22M4+%E2%80%93+Docs%2C+Samples+%26+Release+Hygiene+%28Week+5%E2%80%936%29%22+sort%3Acreated-asc)**  
- Decision table & recipes  
- Troubleshooting guide  
- Public tiny sample fixtures  
- Auto-changelog  
- Winget manifest sync

---

## 5. Common Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
pip install -U pip
pip install -e ".[dev]" || pip install -r requirements.txt

# Lint/type-check (if configured)
ruff . || true
mypy src || true

# Tests
pytest -q

# Build (wheel)
python -m build
pip install dist/*.whl

# CLI smoke
dji-embed --help
dji-embed --version
```

