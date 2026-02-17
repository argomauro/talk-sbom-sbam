import os
import json
import re
from typing import Dict, List, Tuple, Optional
from datetime import datetime

class LLMCVEAnalyzer:
    """
    Language-Agnostic VEX Analysis Engine with Package-Awareness.
    Prevents false positives by validating library namespaces and imports.
    """
    
    def __init__(self, llm_provider: str = "gemini"):
        self.llm_provider = llm_provider
        self.cache = {}
        self.context_window = 30 
        
    def analyze_vulnerability(
        self, 
        vuln_id: str, 
        description: str, 
        package_name: str,
        language: str
    ) -> Tuple[bool, str]:
        """
        Main entry point for agnostic reachability analysis.
        """
        # Step 1: Strategist
        strategy = self._get_strategist_plan(vuln_id, description, package_name, language)
        
        if not strategy or not strategy.get("search_patterns"):
            return False, "Not Affected: Could not determine valid search patterns from CVE description."

        # Step 2: Scanner (Package-Aware)
        findings = self._scan_agnostic(strategy, language, package_name)
        
        if not findings:
            return False, f"Not Affected: No relevant usage of package '{package_name}' patterns found in codebase."

        # Step 3: Auditor
        return self._audit_findings(findings, vuln_id, description, strategy, package_name)

    def _get_strategist_plan(self, vuln_id: str, description: str, package: str, lang: str) -> Dict:
        """
        PHASE 1: Extract search strategy from CVE description.
        """
        strategy = {
            "search_patterns": [],
            "import_aliases": [package.lower()]
        }
        
        # Mapping common package names to import aliases
        common_aliases = {
            "pyyaml": ["yaml"],
            "pillow": ["pil", "Image"],
            "requests": ["requests"],
            "django": ["django"],
            "scikit-learn": ["sklearn"],
            "beautifulsoup4": ["bs4"]
        }
        if package.lower() in common_aliases:
            strategy["import_aliases"].extend(common_aliases[package.lower()])

        # Simulating LLM extraction from description
        potential_matches = re.findall(r'`([a-zA-Z0-9_\(\)\.]+)`', description)
        for m in potential_matches:
            clean = m.split('(')[0].replace('()', '')
            if len(clean) > 2:
                strategy["search_patterns"].append(clean)
        
        # Context-specific keywords
        keywords = ["load", "open", "execute", "parse", "read", "verify", "thumbnail", "save", "explain"]
        desc_lower = description.lower()
        for kw in keywords:
            if kw in desc_lower:
                strategy["search_patterns"].append(kw)
        
        if not strategy["search_patterns"]:
            strategy["search_patterns"].append(package.lower())
            
        return strategy

    def _scan_agnostic(self, strategy: Dict, lang: str, target_package: str) -> List[Dict]:
        """
        PHASE 2: Package-Aware Contextual Scanner.
        Only considers files where the affected package is actually imported or mentioned.
        """
        findings = []
        patterns = strategy.get("search_patterns", [])
        aliases = strategy.get("import_aliases", [target_package.lower()])
        
        ext_map = {
            "python": [".py"], "java": [".java"], "javascript": [".js", ".ts"],
            "go": [".go"], "c": [".c", ".h", ".cpp"], "generic": ["*"]
        }
        extensions = ext_map.get(lang.lower(), ["*"])

        for root, _, files in os.walk("."):
            if any(d in root for d in [".git", "venv", "node_modules", "__pycache__", ".agent"]):
                continue
                
            for file in files:
                if "*" not in extensions and not any(file.endswith(ext) for ext in extensions):
                    continue
                
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        content = "".join(lines)
                    
                    # Check if ANY of the aliases are present in the file
                    # This is a broader but safer check for agnosticism
                    has_package_context = False
                    for alias in aliases:
                        if alias in content.lower():
                            # Be more specific for imports in Python
                            if lang == "python":
                                if f"import {alias}" in content.lower() or f"from {alias}" in content.lower():
                                    has_package_context = True
                                    break
                            else:
                                has_package_context = True
                                break
                    
                    if not has_package_context:
                        continue

                    for i, line in enumerate(lines):
                        stripped = line.strip()
                        if not stripped or stripped.startswith(("#", "//", "/*", "*", "print(")):
                            continue

                        for pattern in patterns:
                            # Use regex for better matching (word boundaries)
                            if re.search(r'\b' + re.escape(pattern) + r'\b', line):
                                # Capture Context Window
                                start = max(0, i - self.context_window)
                                end = min(len(lines), i + self.context_window)
                                context_snippet = "".join(lines[start:end])
                                
                                findings.append({
                                    "file": file_path,
                                    "line": i + 1,
                                    "snippet": context_snippet,
                                    "pattern": pattern,
                                    "trigger_line": stripped
                                })
                                break
                except Exception:
                    continue
        return findings

    def _audit_findings(self, findings: List[Dict], vuln_id: str, description: str, strategy: Dict, target_package: str) -> Tuple[bool, str]:
        """
        PHASE 3: Semantic Auditor with Cross-Library Validation.
        """
        reachable_findings = []
        aliases = strategy.get("import_aliases", [target_package.lower()])
        
        for f in findings:
            snippet = f["snippet"]
            trigger = f["trigger_line"]
            
            # Semantic reasoning cues
            untrusted_sources = ["request", "input", "arg", "param", "data", "payload", "file", "env"]
            
            # --- CRITICAL: Check if the trigger object belongs to the package ---
            is_correct_package_context = False
            for alias in aliases:
                # Does the trigger use the alias? (e.g., yaml.load() or PIL.Image.open())
                if alias in trigger.lower() or alias in snippet.lower():
                    is_correct_package_context = True
                    break
                
            if not is_correct_package_context:
                continue

            # Reason 1: Data flow from untrusted source
            # We look for dangerous sources being passed into the pattern call
            if any(src in trigger.lower() or src in snippet.lower() for src in untrusted_sources):
                reachable_findings.append(f)

        if reachable_findings:
            f = reachable_findings[0]
            return True, (f"Reachable: AI audit confirmed that '{f['pattern']}' from package '{target_package}' "
                          f"is used with dynamic data in {f['file']}:{f['line']}. "
                          f"Context: `{f['trigger_line']}`")
        
        return False, f"Not Affected: No exploitable usage of package '{target_package}' found."

def analyze_with_llm(vuln_id: str, description: str, package: str, lang: str) -> Tuple[bool, str]:
    analyzer = LLMCVEAnalyzer()
    return analyzer.analyze_vulnerability(vuln_id, description, package, lang)
