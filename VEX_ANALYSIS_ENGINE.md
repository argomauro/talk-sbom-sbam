# Antigravity VEX Analysis Engine

The VEX Analysis Engine is a language-agnostic tool designed to determine the reachability of vulnerabilities (CVEs) in any codebase using a combination of LLM reasoning and lexical context analysis.

## The 3-Phase Process

The engine operates in three distinct phases, moving from high-level vulnerability understanding to low-level code auditing.

### Phase 1: The Strategist (LLM-Driven)
The **Strategist** analyzes the official CVE description and the affected package metadata.
- **Objective**: Identify *how* the vulnerability manifests.
- **Output**: Generates a set of language-agnostic search patterns (e.g., function names like `load`, `parse`, or `execute`) and context requirements (e.g., imports from a specific library).
- **Benefit**: No manual rules are needed for new CVEs. The AI interprets the vulnerability on the fly.

### Phase 2: Agnostic Contextual Scanner (Regex-Based)
The **Scanner** performs a fast, lexical scan across the entire project.
- **Objective**: Find potential "points of interest" where danger might reside.
- **Process**:
    1. Scans codebase using patterns from Phase 1.
    2. When a match is found, it "clips" a **contextual window** (e.g., ±50 lines of code) around the match.
    3. It avoids complex AST (Abstract Syntax Tree) parsing, making it compatible with Python, Java, C++, Go, etc., out of the box.
- **Benefit**: Extremely scalable and language-independent.

### Phase 3: The Auditor (LLM-Reasoning)
The **Auditor** performs deep semantic analysis on the findings from Phase 2.
- **Objective**: Determine if the code usage is actually exploitable.
- **Process**:
    1. Receives the CVE description and the extracted code snippets.
    2. Analyzes the data flow (e.g., "Is this input coming from a user request or a hardcoded constant?").
    3. Uses LLM's cross-language capabilities to evaluate the safety of the implementation.
- **Benefit**: Dramatically reduces false positives by understanding the *intent* and *context* of the code.

## Why this approach?

Traditional static analysis (SAST) often fails in VEX triage because it's too rigid (rules-based) or too specialized (AST-based). By combining **Agnostic Scanning** with **LLM Reasoning**, we achieve:
1. **Zero Configuration**: No need to write custom rules for every library.
2. **Infinite Scalability**: Works on any language the LLM understands.
3. **Precision**: Distinguishes between "usage" and "reachability" by looking at the execution context.
