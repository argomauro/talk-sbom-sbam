---
name: vex-triage
description: AI-driven vulnerability triage and VEX generation.
---

# VEX Triage Skill

This skill allows the AI Assistant to perform an intelligent analysis of vulnerabilities identified by Dependency-Track and generate a VEX (Vulnerability Exploitability eXchange) file.

## Workflow

1. **Authentication**: 
   - Ensure the `DT_API_KEY` is available. 
   - The user should provide this key or it can be found in the project's `.env` file.
   - **CRITICAL PERMISSIONS**: This key MUST have `VULNERABILITY_ANALYSIS`, `VIEW_PORTFOLIO`, and `BOM_UPLOAD` permissions.
2. **Fetch Findings**: Use `scripts/get_findings.py` to retrieve active vulnerabilities.
3. **Multi-Source Mapping**: 
   - Dependency-Track often uses **GHSA** (GitHub) as the primary ID for some findings and **CVE** (NVD) for others.
   - For 100% coverage, always include BOTH IDs in the VEX if they are listed as aliases in the finding.
4. **Code Analysis**: Perform a deep scan of the local source code to determine reachability.
5. **Generate VEX (CycloneDX 1.5)**:
   - **Enums**: Use `exploitable` (not `affected`) or `not_affected`.
   - **Metadata**: MUST include a `metadata` section with a valid `timestamp` and `tools` array.
   - **bom-ref**: Use the project's UUID (found in project details or logs) as the `bom-ref` for the `affected` component.

## Best Practices for Portability
- **Atomic Setup**: Keep the `.agent` folder inside the project root for CI/CD consistency.
- **Justifications**: Always provide a `detail` field with the AI's reasoning to satisfy security audits.
- **Universal IDs**: When triage is performed on a component, apply the same logic to all its vulnerability aliases to clear the dashboard entirely.

## Required Environment Variables
- `DT_API_KEY`: API key for Dependency-Track.
- `DT_URL`: Base URL for Dependency-Track (default: http://host.docker.internal:8081).
- `CI_PROJECT_NAME`: Name of the project (default: app-java).
- `CI_COMMIT_BRANCH`: Branch/version of the project (default: main).
