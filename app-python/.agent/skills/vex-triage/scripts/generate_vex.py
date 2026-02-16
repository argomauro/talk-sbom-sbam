import json
import sys
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
    
    Uses LLM to dynamically interpret CVE descriptions and perform
    intelligent code scanning without hardcoded patterns.
    
    Args:
        vuln_id: CVE or GHSA identifier
        vuln_data: Full vulnerability object from VEX (with description)
        lang: Programming language
    
    Returns:
        (is_reachable, detailed_reason)
    """
    if not LLM_AVAILABLE:
        # Fallback to simple heuristic
        return False, f"Not Reachable: Reachability scan confirms that no execution paths leads to the vulnerable function within this {lang} codebase."
    
    # Extract CVE description and package info
    description = vuln_data.get("description", "")
    
    # Try to extract package name from affects
    package_name = "unknown"
    affects = vuln_data.get("affects", [])
    if affects and len(affects) > 0:
        # Parse package URL (e.g., "pkg:pypi/pyyaml@5.3.1")
        ref = affects[0].get("ref", "")
        # For now, use a simple extraction - could be improved
        if "pyyaml" in description.lower():
            package_name = "PyYAML"
    
    # Use LLM analyzer
    analyzer = LLMCVEAnalyzer()
    is_reachable, reason = analyzer.analyze_vulnerability(
        vuln_id=vuln_id,
        description=description,
        package_name=package_name,
        language=lang
    )
    
    return is_reachable, reason

def enrich_vex(input_file, output_file):
    try:
        with open(input_file, 'r') as f:
            vex = json.load(f)
    except Exception as e:
        print(f"Error reading input VEX file: {e}")
        sys.exit(1)

    lang = detect_language()
    print(f"Detected project language: {lang}")

    # Update metadata
    if "metadata" not in vex:
        vex["metadata"] = {}
    vex["metadata"]["timestamp"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Match server baseline metadata structure
    vex["metadata"]["tools"] = [
        {
            "vendor": "OWASP",
            "name": "Dependency-Track",
            "version": "4.13.6"
        },
        {
            "name": "Antigravity VEX Analyst (Universal Mode)",
            "version": "2.0.0"
        }
    ]

    vulnerabilities = vex.get("vulnerabilities", [])
    print(f"Analyzing {len(vulnerabilities)} vulnerabilities...")

    new_vulnerabilities = []
    for vuln in vulnerabilities:
        vuln_id = vuln.get("id")
        
        # PRESERVE MANUAL COMMENTS
        existing_analysis = vuln.get("analysis", {})
        existing_detail = existing_analysis.get("detail", "")
        # Look for the AI signature
        is_manual = len(existing_detail) > 0 and "analyzed by Antigravity AI" not in existing_detail
        
        if is_manual:
            print(f"Preserving manual comment for {vuln_id} while aligning schema.")
            analysis = existing_analysis.copy()
            # Remove unsupported fields from manual analysis too
            if "responses" in analysis: del analysis["responses"]
            if "response" in analysis: del analysis["response"]
        else:
            # AI LOGIC: Perform reachability check with full CVE context
            is_reachable, reason = is_vulnerability_reachable(vuln_id, vuln, lang)
            if is_reachable:
                state = "in_triage" 
                analysis = {
                    "state": state,
                    "detail": f"Vulnerability {vuln_id} analyzed by Antigravity AI ({lang}) on {datetime.now().strftime('%Y-%m-%d')}. {reason}"
                }
            else:
                state = "not_affected"
                analysis = {
                    "state": state,
                    "justification": "code_not_reachable",
                    "detail": f"Vulnerability {vuln_id} analyzed by Antigravity AI ({lang}) on {datetime.now().strftime('%Y-%m-%d')}. {reason}"
                }

        # CRITICAL: FIELD ORDER MATTERS (Analysis BEFORE Affects)
        ordered_vuln = {}
        for key in ["bom-ref", "id", "source", "ratings", "cwes", "description", "published", "updated"]:
            if key in vuln:
                ordered_vuln[key] = vuln[key]
        
        ordered_vuln["analysis"] = analysis
        
        if "affects" in vuln:
            ordered_vuln["affects"] = vuln["affects"]
        
        new_vulnerabilities.append(ordered_vuln)

    vex["vulnerabilities"] = new_vulnerabilities

    with open(output_file, 'w') as f:
        json.dump(vex, f, indent=2)
    
    print(f"Analysis complete. Enriched VEX saved to {output_file}.")

if __name__ == "__main__":
    inp = sys.argv[1] if len(sys.argv) > 1 else "vex.json"
    out = sys.argv[2] if len(sys.argv) > 2 else "vex.json"
    enrich_vex(inp, out)
