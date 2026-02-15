---
name: vex-triage
description: AI-driven vulnerability triage and VEX generation.
---

# VEX Triage Skill

This skill allows the AI Assistant to perform an intelligent analysis of vulnerabilities identified by Dependency-Track and generate a VEX (Vulnerability Exploitability eXchange) file.

## Workflow

1. **Authentication**: 
   - Ensure the `DT_API_KEY` is available. 
   - The user should provide this key or it can be found in the `app-java/.env` file.
   - This key must have `VULNERABILITY_ANALYSIS` and `VIEW_PORTFOLIO` permissions.
2. **Fetch Findings**: Use `scripts/get_findings.py` to retrieve active vulnerabilities for the current project.
3. **Code Analysis**: Perform a deep scan of the local source code to determine if the vulnerable components are reachable and if the specific vulnerable functions are being used.
4. **Reasoning**: Document the reasoning for each vulnerability.
   - If reachable: Mark as `affected`.
   - If NOT reachable: Mark as `not_affected` with justification `code_not_reachable`.
5. **Generate VEX**: Create a `vex.json` file in CycloneDX 1.5 format with the findings in the `app-java/` directory.

## Required Environment Variables
- `DT_API_KEY`: API key for Dependency-Track.
- `DT_URL`: Base URL for Dependency-Track (default: http://host.docker.internal:8081).
- `CI_PROJECT_NAME`: Name of the project (default: app-java).
- `CI_COMMIT_BRANCH`: Branch/version of the project (default: main).
