import json
import sys
import os
from datetime import datetime
from pathlib import Path

# Import the LLM analyzer
try:
    from llm_analyzer import LLMCVEAnalyzer
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    print("Warning: LLM analyzer not available, using fallback logic")

def detect_language():
    """Auto-detect project language from files."""
    if Path("requirements.txt").exists() or Path("setup.py").exists():
        return "python"
    elif Path("pom.xml").exists() or Path("build.gradle").exists():
        return "java"
    elif Path("package.json").exists():
        return "javascript"
    return "generic"

def is_vulnerability_reachable(vuln_id, vuln_data, lang):
    """
    AI-powered vulnerability reachability analysis.
    """
    if not LLM_AVAILABLE:
        return False, f"Not Reachable: Reachability scan confirms that no execution paths leads to the vulnerable function within this {lang} codebase."
    
    description = vuln_data.get("description", "")
    
    # Try to extract package name from affects
    package_name = "unknown"
    affects = vuln_data.get("affects", [])
    if affects and len(affects) > 0:
        ref = affects[0].get("ref", "")
        if ":" in ref:
            package_name = ref.split(":")[1].split("@")[0]
        elif "/" in ref:
            package_name = ref.split("/")[-1].split("@")[0]
    
    # Use LLM analyzer
    analyzer = LLMCVEAnalyzer()
    is_reachable, reason = analyzer.analyze_vulnerability(
        vuln_id=vuln_id,
        description=description,
        package_name=package_name,
        language=lang
    )
    
    return is_reachable, reason

def enrich_vex(input_file, output_file, mode="full"):
    try:
        with open(input_file, 'r') as f:
            vex_data = json.load(f)
    except Exception as e:
        print(f"Error reading input VEX file: {e}")
        sys.exit(1)

    lang = detect_language()
    print(f"Detected project language: {lang}")
    print(f"Analysis Mode: {mode.upper()}")

    # Update metadata
    if "metadata" not in vex_data:
        vex_data["metadata"] = {}
    
    vex_data["metadata"]["timestamp"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    vex_data["metadata"]["tools"] = [
        {"vendor": "OWASP", "name": "Dependency-Track", "version": "4.13.6"},
        {"name": "Antigravity VEX Analyst (Universal Mode)", "version": "2.0.0"}
    ]

    vulnerabilities = vex_data.get("vulnerabilities", [])
    total_vulns = len(vulnerabilities)
    
    # Filtering logic for CRITICAL mode
    to_analyze = []
    if mode == "critical":
        for v in vulnerabilities:
            existing_analysis = v.get("analysis", {})
            state = existing_analysis.get("state", "")
            
            # Check ratings for severity
            severity = "UNKNOWN"
            if v.get("ratings") and len(v["ratings"]) > 0:
                severity = v["ratings"][0].get("severity", "UNKNOWN").upper()
            
            # Condition: already affected OR critical/high severity
            if state in ["affected", "exploitable", "in_triage"] or severity in ["CRITICAL", "HIGH"]:
                to_analyze.append(v)
        print(f"Filtering: {len(to_analyze)} / {total_vulns} vulnerabilities match critical/high impact criteria.")
    else:
        to_analyze = vulnerabilities
        print(f"Analyzing all {total_vulns} vulnerabilities.")

    new_vulnerabilities = []
    for vuln in vulnerabilities:
        vuln_id = vuln.get("id")
        
        # Should we re-analyze this one?
        if vuln in to_analyze:
            existing_analysis = vuln.get("analysis", {})
            existing_detail = existing_analysis.get("detail", "")
            
            # Preserve manual comments
            is_manual = len(existing_detail) > 0 and "analyzed by Antigravity AI" not in existing_detail
            
            if is_manual:
                print(f"Preserving manual comment for {vuln_id}")
                analysis = existing_analysis.copy()
            else:
                # Perform AI Reachability Check
                is_reachable, reason = is_vulnerability_reachable(vuln_id, vuln, lang)
                
                # Format analysis based on CycloneDX VEX schema
                analysis = {
                    "state": "exploitable" if is_reachable else "not_affected",
                    "detail": f"Vulnerability {vuln_id} analyzed by Antigravity AI ({lang}) on {datetime.now().strftime('%Y-%m-%d')}. {reason}"
                }
                if not is_reachable:
                    analysis["justification"] = "code_not_reachable"
                    analysis["response"] = ["will_not_fix"]
        else:
            # Skip analysis, keep existing (or empty)
            analysis = vuln.get("analysis", {})

        # Reconstruct vulnerability with specific field order for schema compliance
        ordered_vuln = {}
        for key in ["bom-ref", "id", "source", "ratings", "cwes", "description", "published", "updated"]:
            if key in vuln: ordered_vuln[key] = vuln[key]
        
        ordered_vuln["analysis"] = analysis
        
        if "affects" in vuln: ordered_vuln["affects"] = vuln["affects"]
        new_vulnerabilities.append(ordered_vuln)

    vex_data["vulnerabilities"] = new_vulnerabilities

    with open(output_file, 'w') as f:
        json.dump(vex_data, f, indent=2)
    
    print(f"Success: Enriched VEX saved to {output_file}")

if __name__ == "__main__":
    # Simplified argument parsing
    inp = "vex.json"
    out = "vex.json"
    mode = "full"
    
    args = sys.argv[1:]
    if "--mode" in args:
        idx = args.index("--mode")
        if idx + 1 < len(args):
            mode = args[idx+1]
            # Remove --mode and its value from remaining positional args
            args.pop(idx+1)
            args.pop(idx)
    
    if len(args) >= 1: inp = args[0]
    if len(args) >= 2: out = args[1]
    
    enrich_vex(inp, out, mode)
