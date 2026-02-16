---
description: Universal VEX Synchronization Workflow
---

# Universal VEX Synchronization Workflow

This workflow ensures that vulnerability triage is consistent, versioned, and synchronized across all programming languages.

## Steps

1. **Pull Latest Baseline**
   Ensure your local environment has the latest findings from Dependency-Track.
   ```bash
   git pull origin main
   ```

2. **Run AI Reachability Analysis**
   Use the `vex-triage` skill to automatically enrich the local `vex.json`.
   ```bash
   # From the project root
   python3 .agent/skills/vex-triage/scripts/generate_vex.py
   ```

3. **Review & Comment (Developer Triage)**
   Open the **VEX Dashboard** to review AI justifications and add developer notes.
   ```bash
   # Open the dashboard from the skill directory
   open .agent/skills/vex-triage/dashboard/triage-dashboard.html
   ```

4. **Commit & Push**
   Finalize the triage by pushing the enriched file to GitLab.
   ```bash
   git add vex.json
   git commit -m "docs: AI-enriched VEX analysis with developer comments"
   git push origin main
   ```

// turbo
5. **Verify in CI**
   Check the GitLab CI pipeline to ensure the `sync` stage uploaded the VEX correctly to Dependency-Track.
