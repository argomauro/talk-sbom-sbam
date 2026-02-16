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
   
   > [!NOTE]
   > Scegli la modalità di analisi:
   > - **Full**: Scansione completa di tutte le vulnerabilità.
   > - **Critical**: Focus solo su ciò che è CRITICAL/HIGH o già marcato come Affected.

   ```bash
   # Opzione 1: Analisi COMPLETA
   python3 .agent/skills/vex-triage/scripts/generate_vex.py vex.json vex.json --mode full

   # Opzione 2: Analisi CRITICA (Più veloce)
   python3 .agent/skills/vex-triage/scripts/generate_vex.py vex.json vex.json --mode critical
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
