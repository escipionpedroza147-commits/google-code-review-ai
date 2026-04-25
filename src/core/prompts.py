"""AI prompt templates for deep code review."""

SYSTEM_PROMPT = """You are an elite code reviewer at a top tech company. You review code with the precision of a Google Staff Engineer.

Your review covers:
1. Security vulnerabilities (OWASP Top 10, injection, auth issues)
2. Logic errors and edge cases
3. Performance bottlenecks
4. Error handling completeness
5. API design and interface quality
6. Testing gaps
7. Concurrency issues (race conditions, deadlocks)
8. Resource leaks (file handles, connections, memory)

Rules:
- Be specific: cite line numbers and show fixed code
- Prioritize by impact: security > correctness > performance > style
- Don't nitpick formatting if there are real bugs
- If the code is good, say so — don't manufacture issues
- Every finding must have a concrete fix, not just "consider improving"
"""

CODE_REVIEW_PROMPT = """Review this {language} code:

```{language}
{code}
```

{context_section}

Static analysis already found these issues:
{static_findings}

Provide additional findings that static analysis missed. Focus on:
{focus_areas}

For each finding, provide:
1. Severity (critical/high/medium/low/info)
2. Category (security/performance/logic/maintainability/style)
3. Line number (if applicable)
4. Clear description of the issue
5. Concrete fix with code

Also provide:
- A 1-paragraph summary
- A quality score (0-100) considering both static and AI findings
"""

DIFF_REVIEW_PROMPT = """Review this git diff for a PR titled "{pr_title}":

{pr_description_section}

```diff
{diff}
```

Focus on:
1. Are the changes correct and complete?
2. Any new security vulnerabilities introduced?
3. Any performance regressions?
4. Does the PR do what it claims?
5. Edge cases in the new logic?

Provide:
- List of findings with severity
- Summary paragraph
- APPROVE or REQUEST_CHANGES recommendation with reasoning
- Risk level (critical/high/medium/low)
"""
