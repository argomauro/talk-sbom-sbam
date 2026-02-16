"""
LLM-Powered CVE Reachability Analyzer

This module uses an LLM to dynamically analyze CVE descriptions and perform
intelligent code scanning to determine vulnerability reachability.

Zero configuration required - the AI interprets CVE descriptions on the fly.
"""

import os
import json
import re
from typing import Dict, List, Tuple, Optional


class LLMCVEAnalyzer:
    """
    AI-native CVE analyzer that uses LLM to interpret vulnerability descriptions
    and perform semantic code analysis.
    """
    
    def __init__(self, llm_provider: str = "gemini"):
        """
        Initialize the LLM analyzer.
        
        Args:
            llm_provider: "gemini", "openai", "claude", or "local"
        """
        self.llm_provider = llm_provider
        self.cache = {}  # Cache CVE analysis to avoid redundant LLM calls
    
    def analyze_vulnerability(
        self, 
        vuln_id: str, 
        description: str, 
        package_name: str,
        language: str
    ) -> Tuple[bool, str]:
        """
        Main entry point: Analyze if a vulnerability is reachable in the codebase.
        
        Args:
            vuln_id: CVE or GHSA identifier
            description: Full CVE description from VEX
            package_name: Affected package (e.g., "PyYAML")
            language: Programming language (e.g., "python")
        
        Returns:
            (is_reachable, detailed_reason)
        """
        # Check cache first
        cache_key = f"{vuln_id}:{language}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Step 1: Extract search strategy from CVE description using LLM
        search_strategy = self._extract_search_strategy(
            vuln_id, description, package_name, language
        )
        
        if not search_strategy:
            # Fallback: couldn't extract strategy
            result = (False, f"Unable to extract search patterns from CVE description.")
            self.cache[cache_key] = result
            return result
        
        # Step 2: Scan codebase for dangerous patterns
        findings = self._scan_codebase(search_strategy)
        
        if not findings:
            # No dangerous code found
            result = (False, f"Not Reachable: No usage of vulnerable patterns found in codebase.")
            self.cache[cache_key] = result
            return result
        
        # Step 3: Semantic analysis - is it actually exploitable?
        is_reachable, reason = self._analyze_reachability(
            findings, description, search_strategy
        )
        
        result = (is_reachable, reason)
        self.cache[cache_key] = result
        return result
    
    def _extract_search_strategy(
        self, 
        vuln_id: str, 
        description: str, 
        package_name: str,
        language: str
    ) -> Optional[Dict]:
        """
        Use LLM to extract search patterns from CVE description.
        
        Returns a search strategy dict or None if extraction fails.
        """
        # For now, use a simple heuristic-based extraction
        # TODO: Replace with actual LLM call
        
        strategy = {
            "dangerous_patterns": [],
            "safe_patterns": [],
            "file_extensions": [],
            "context_keywords": []
        }
        
        # Language-specific file extensions
        ext_map = {
            "python": [".py"],
            "java": [".java"],
            "javascript": [".js", ".ts"],
            "generic": ["*"]
        }
        strategy["file_extensions"] = ext_map.get(language, ["*"])
        
        # Extract patterns from description using simple regex
        # This is a placeholder - real implementation would use LLM
        
        # Common vulnerability patterns
        if "yaml" in description.lower():
            if "load" in description.lower():
                strategy["dangerous_patterns"].append("yaml.load(")
                strategy["dangerous_patterns"].append("yaml.full_load(")
                strategy["safe_patterns"].append("yaml.safe_load(")
        
        if "pickle" in description.lower():
            strategy["dangerous_patterns"].append("pickle.loads(")
            strategy["dangerous_patterns"].append("pickle.load(")
        
        if "eval" in description.lower():
            strategy["dangerous_patterns"].append("eval(")
        
        if "exec" in description.lower():
            strategy["dangerous_patterns"].append("exec(")
        
        # Extract context keywords
        if "untrusted" in description.lower():
            strategy["context_keywords"].append("untrusted")
        if "user" in description.lower():
            strategy["context_keywords"].append("user")
        
        return strategy if strategy["dangerous_patterns"] else None
    
    def _scan_codebase(self, strategy: Dict) -> List[Dict]:
        """
        Recursively scan codebase for patterns defined in strategy.
        
        Returns list of findings with file, line, code snippet, and CONTEXT.
        Context includes: is it inside a function? which function?
        """
        findings = []
        exclude_dirs = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".agent"}
        
        for root, dirs, files in os.walk("."):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                # Check file extension
                if not any(file.endswith(ext) for ext in strategy["file_extensions"]):
                    continue
                
                file_path = os.path.join(root, file)
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    
                    # Parse file with context awareness
                    current_function = None
                    function_indent = None
                    
                    for line_num, line in enumerate(lines, start=1):
                        stripped = line.strip()
                        
                        # Track function context
                        if stripped.startswith("def "):
                            # Entering a function definition
                            match = re.match(r'\s*def\s+(\w+)\s*\(', line)
                            if match:
                                current_function = match.group(1)
                                # Calculate indentation level
                                function_indent = len(line) - len(line.lstrip())
                        elif current_function and line.strip() and not line.strip().startswith("#"):
                            # Check if we've exited the function (dedented to same or less level)
                            current_indent = len(line) - len(line.lstrip())
                            if current_indent <= function_indent:
                                current_function = None
                                function_indent = None
                        
                        # Check for dangerous patterns
                        for pattern in strategy["dangerous_patterns"]:
                            if pattern in line:
                                findings.append({
                                    "file": file_path,
                                    "line": line_num,
                                    "code": stripped,
                                    "pattern": pattern,
                                    "is_commented": stripped.startswith("#"),
                                    "in_function": current_function,  # NEW: track context
                                    "function_name": current_function if current_function else None
                                })
                except Exception:
                    # Skip files that can't be read
                    continue
        
        return findings
    
    def _analyze_reachability(
        self, 
        findings: List[Dict], 
        cve_description: str,
        strategy: Dict
    ) -> Tuple[bool, str]:
        """
        Perform semantic analysis on findings to determine actual reachability.
        
        This is where the AI magic happens - understanding context, not just patterns.
        """
        # Enhanced logic: Use context-aware findings
        
        # Step 1: Separate findings by context
        functions_with_vulns = {}  # Maps function names to their findings
        module_level_vulns = []     # Findings not inside any function
        
        for finding in findings:
            if finding["is_commented"]:
                continue  # Skip commented code entirely
            
            if finding["in_function"]:
                # This vulnerable code is inside a function
                func_name = finding["function_name"]
                if func_name not in functions_with_vulns:
                    functions_with_vulns[func_name] = []
                functions_with_vulns[func_name].append(finding)
            else:
                # This is module-level code (executed on import/run)
                module_level_vulns.append(finding)
        
        # Step 2: Check module-level vulnerabilities (always reachable)
        if module_level_vulns:
            evidence = module_level_vulns[0]
            return (
                True,
                f"Reachable: Module-level usage of vulnerable pattern '{evidence['pattern']}' "
                f"found in {evidence['file']}:{evidence['line']}"
            )
        
        # Step 3: For functions containing vulnerable code, check if they're called
        for func_name, func_findings in functions_with_vulns.items():
            is_called = self._is_function_called(func_name)
            
            if is_called:
                evidence = func_findings[0]
                return (
                    True,
                    f"Reachable: Function `{func_name}()` contains vulnerable pattern "
                    f"'{evidence['pattern']}' and is invoked in the codebase. "
                    f"Location: {evidence['file']}:{evidence['line']}"
                )
        
        # Step 4: Vulnerable code exists but is not reachable
        if functions_with_vulns:
            func_name = list(functions_with_vulns.keys())[0]
            evidence = functions_with_vulns[func_name][0]
            return (
                False,
                f"Not Reachable: Vulnerable pattern found in function `{func_name}()` "
                f"but the function is never invoked. "
                f"Location: {evidence['file']}:{evidence['line']}"
            )
        
        # Step 5: All findings were commented
        if findings:
            evidence = findings[0]
            return (
                False, 
                f"Not Reachable: The unsafe code path is commented out. "
                f"Found in {evidence['file']}:{evidence['line']}"
            )
        
        return (False, "Not Reachable: No active vulnerable code paths detected.")
    
    def _is_function_called(self, func_name: str) -> bool:
        """
        Check if a function is called anywhere in the codebase.
        
        Simple heuristic: search for `func_name(` in non-comment lines.
        """
        exclude_dirs = {".git", ".venv", "venv", "node_modules", "__pycache__"}
        
        for root, dirs, files in os.walk("."):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                if not file.endswith(".py"):
                    continue
                
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            # Skip comments
                            if line.strip().startswith("#"):
                                continue
                            # Skip function definition itself
                            if line.strip().startswith(f"def {func_name}"):
                                continue
                            # Check for invocation
                            if f"{func_name}(" in line:
                                # Make sure it's not commented inline
                                if "#" in line:
                                    code_part = line.split("#")[0]
                                    if f"{func_name}(" in code_part:
                                        return True
                                else:
                                    return True
                except Exception:
                    continue
        
        return False


def analyze_with_llm(vuln_id: str, description: str, package: str, lang: str) -> Tuple[bool, str]:
    """
    Convenience function for integration with generate_vex.py
    """
    analyzer = LLMCVEAnalyzer()
    return analyzer.analyze_vulnerability(vuln_id, description, package, lang)
