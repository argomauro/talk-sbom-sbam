---
name: vex-triage
description: AI-driven local VEX enrichment for reachable vulnerability analysis.
---

# VEX Triage Skill (AI-Native Analyst Mode)

This skill performs a local, **AI-native analysis** of vulnerabilities identified in the `vex.json` file. Unlike traditional scanners, this analyst dynamically interprets CVE descriptions and performs intelligent, context-aware code analysis to determine actual reachability.

## Workflow

1. **Pull Baseline**: 
   - Use `git pull` to ensure your local `vex.json` is synchronized with the latest state from the CI/CD pipeline.
2. **AI-Native Analysis & Enrichment**:
   - Execute `python3 .agent/skills/vex-triage/scripts/generate_vex.py`.
   - **Modes**:
     - `--mode full` (Default): Analyzes all vulnerabilities.
     - `--mode critical`: Focuses only on critical/high impact items for faster triage.
   - The **AI-Native Analyst** reads the CVE description, identifies dangerous functions, and scans the codebase (tracking scope and calls) to confirm reachability.
3. **Developer Review**:
   - Open `.agent/skills/vex-triage/dashboard/triage-dashboard.html` in your browser.
   - Review findings and add developer comments to prioritize real risks.
4. **Commit & Push**:
   - Commit the updated `vex.json`. 
   - The consolidated GitLab CI pipeline will automatically handle the upload to Dependency-Track.

## Best Practices
- **Security First**: No `DT_API_KEY` or sensitive credentials are required or allowed in this local workflow.
- **Traceable Decisions**: By committing the enriched VEX, you maintain a versioned history of all triage decisions.

## Required Environment Variables
- **None**: This skill operates strictly in offline mode.

