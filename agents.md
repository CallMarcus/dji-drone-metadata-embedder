# AI Coding Assistant – Task Breakdown (`agents.md`)

*Last updated: July 23rd, 2025*

***

## Phase 0 – Core plumbing

**✔ Package structure consolidated** **⚠ CI / workflow YAML needs formatting** **⚠ .pre‑commit file needs formatting**

**T0.A · Reformat YAML files**  
*Files*: .github/workflows/*.yml, .precommitconfig.yaml  
*Checklist*:

-   Prettyprint with newlines & proper indent  
-   yamllint --strict passes  
    *Done when*: CI still green **and** git diff shows readable YAML.

**T0.B · Verify Winget workflow**  
*Files*: .github/workflows/publish-winget.yml  
*Checklist*:

-   Ensure on: workflow_dispatch so it can be run manually  
-   Run the job once; artefact = valid manifest in manifests/  
-   Use `winget validate` prior to submission (replaces deprecated `wingetcreate validate`)  
-   Install winget from https://aka.ms/getwinget if the CLI is missing  
    *Done when*: First successful run appears in the Actions tab.

***

## 📋 PHASE 1: Core Functionality Verification

>   **Goal**: Ensure all features work correctly before deployment

### 1.1 · Test Core Features

| Task      | Description                                                        | Status  |
|-----------|--------------------------------------------------------------------|---------|
| **1.1.1** | Verify SRT parsing for all formats (Mini 3/4 Pro, Avata 2, legacy) | ❌ TODO |
| **1.1.2** | Test video metadata embedding with FFmpeg                          | ❌ TODO |
| **1.1.3** | Test ExifTool GPS metadata embedding                               | ❌ TODO |
| **1.1.4** | Verify DAT file parsing and integration                            | ❌ TODO |
| **1.1.5** | Test telemetry export (GPX, CSV)                                   | ❌ TODO |

### 1.2 · Documentation Update

| Task      | Description                                          | Status  |
|-----------|------------------------------------------------------|---------|
| **1.2.1** | Update README with correct installation instructions | ❌ TODO |
| **1.2.2** | Document all CLI commands and options                | ❌ TODO |
| **1.2.3** | Add troubleshooting guide                            | ❌ TODO |
| **1.2.4** | Update CHANGELOG.md                                  | ❌ TODO |

***

## 📋 PHASE 2: Windows User Experience

>   **Goal**: Zero‑friction install for everyday Windows pilots

### 2.1 · PowerShell Bootstrap Script (📜 `tools/bootstrap.ps1`)

| Step | What the script does                      | Implementation hints                | Status   |
|------|-------------------------------------------|-------------------------------------|----------|
| 1    | **Self‑elevate if needed**                | Use `#Requires -RunAsAdministrator` | ✅ DONE  |
| 2    | Ensure **Python ≥ 3.10**                  | Install
