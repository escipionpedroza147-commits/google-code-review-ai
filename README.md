# Google Code Review AI

**AI-powered code review with the precision of a Google Staff Engineer.**

Stop shipping bugs. Start reviewing code like a top-tier engineering team.

## The Problem

Code reviews are inconsistent. Junior devs miss security flaws. Senior devs don't have time to review every PR. Static linters catch formatting issues but miss logic bugs, race conditions, and subtle vulnerabilities. Meanwhile, one missed SQL injection costs you months.

**Google Code Review AI** combines free static analysis with deep AI-powered review to catch what humans and linters miss — before it hits production.

## Features

- 🔍 **Static + AI Hybrid** — Static analysis catches the obvious stuff for free. AI handles nuanced logic, security, and architecture issues
- 🤖 **Dual AI Provider** — Choose Google Gemini or OpenAI as your review engine
- 🔒 **Security-First** — Detects OWASP Top 10 vulnerabilities, hardcoded secrets, SQL injection, unsafe deserialization
- 🌐 **Multi-Language** — Python, JavaScript, TypeScript, Go, Java, Rust, C++ with auto-detection
- 🔗 **GitHub Webhook** — Auto-review PRs on open/push with signature verification
- 📊 **Quality Scoring** — 0-100 score with severity breakdown and metrics
- ⚡ **Zero-Cost Mode** — Static analysis endpoint runs instantly with no AI cost
- 🗜️ **Prompt Optimization** — Detects redundancy, bloat, and waste in code
- 🚨 **Severity Tiers** — Critical → High → Medium → Low → Info with actionable fixes

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/review/code` | Full code review (static + AI) |
| POST | `/api/v1/review/diff` | PR/diff review with approve/reject |
| POST | `/api/v1/analyze/static` | Static analysis only (free, no AI) |
| POST | `/api/v1/webhook/github` | GitHub webhook for auto-review |
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/stats` | Review statistics and metrics |

## Quick Start

```bash
git clone https://github.com/escipionpedroza147-commits/google-code-review-ai.git
cd google-code-review-ai
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
python main.py
```

Server at `http://localhost:8000` — Interactive docs at `/docs`.

## Usage Examples

### Full Code Review (Static + AI)

```bash
curl -X POST http://localhost:8000/api/v1/review/code \
  -H "Content-Type: application/json" \
  -d '{
    "code": "import pickle\ndef load(data):\n    return pickle.loads(data)",
    "language": "python"
  }'
```

Response:

```json
{
  "findings": [
    {
      "severity": "high",
      "category": "security",
      "line": 3,
      "title": "Unsafe Deserialization",
      "description": "pickle.loads can execute arbitrary code from untrusted data.",
      "suggestion": "Use json for data interchange. If YAML needed, use yaml.safe_load()."
    }
  ],
  "summary": "Reviewed 3 lines of python. Quality score: 65/100. Significant issues found.",
  "score": 65,
  "language_detected": "python",
  "lines_reviewed": 3
}
```

### Static Analysis Only (Free)

```bash
curl -X POST http://localhost:8000/api/v1/analyze/static \
  -H "Content-Type: application/json" \
  -d '{
    "code": "api_key = \"sk-abc123def456ghi789jkl012mno345pqr678\"",
    "language": "python"
  }'
```

### PR Diff Review

```bash
curl -X POST http://localhost:8000/api/v1/review/diff \
  -H "Content-Type: application/json" \
  -d '{
    "diff": "diff --git a/auth.py b/auth.py\n+ query = f\"SELECT * FROM users WHERE id = {uid}\"",
    "pr_title": "Add user lookup",
    "pr_description": "New endpoint for fetching user profiles"
  }'
```

## Architecture

```
Request → Static Analysis (free, instant) → AI Review (deep, nuanced) → Combined Report
```

**Why hybrid?** Static analysis is deterministic, fast, and free — it catches hardcoded secrets, SQL injection patterns, eval/exec usage, complexity issues, and code smells without spending a single API token. AI fills the gaps: logic errors, architectural problems, subtle security issues, and context-aware recommendations.

This means even without an API key configured, you get valuable security and quality analysis for zero cost.

## Project Structure

```
google-code-review-ai/
├── main.py                          # FastAPI app with lifespan
├── config/
│   └── settings.py                  # Env-based configuration
├── src/
│   ├── api/
│   │   └── routes.py                # 6 API endpoints
│   ├── core/
│   │   ├── prompts.py               # AI prompt templates
│   │   └── static_analyzer.py       # Static analysis engine
│   ├── models/
│   │   └── schemas.py               # Pydantic v2 schemas
│   └── services/
│       └── review_service.py        # Orchestration (static + AI)
├── tests/                           # 70+ tests across 5 files
│   ├── test_static_analyzer.py      # Static analysis patterns
│   ├── test_schemas.py              # Model validation
│   ├── test_routes.py               # API endpoints
│   ├── test_review_service.py       # Service orchestration
│   └── test_prompts.py              # Prompt templates
├── requirements.txt
├── LICENSE
└── CONTRIBUTING.md
```

## Supported Languages

| Language | Extension | Detection | Static Analysis |
|----------|-----------|-----------|-----------------|
| Python | .py | ✅ | Full (secrets, SQL, eval, pickle, complexity) |
| JavaScript | .js | ✅ | Core (secrets, SQL, complexity) |
| TypeScript | .ts, .tsx | ✅ | Core (secrets, SQL, complexity) |
| Go | .go | ✅ | Core (secrets, complexity) |
| Java | .java | ✅ | Core (secrets, SQL, complexity) |
| Rust | .rs | ✅ | Core (secrets, complexity) |
| C/C++ | .c, .cpp, .cc | ✅ | Core (secrets, complexity) |

## Static Analysis Checks

- 🔑 **Hardcoded Secrets** — API keys, GitHub tokens, AWS credentials, passwords
- 💉 **SQL Injection** — f-strings, .format(), string concatenation in queries
- ⚠️ **Dangerous Functions** — eval(), exec(), pickle.loads(), yaml.load()
- 🕳️ **Empty Exception Handlers** — except: pass, bare except blocks
- 📏 **Complexity** — Long functions (>50 lines), deep nesting (>4 levels)
- 📝 **Code Markers** — TODO, FIXME, HACK, XXX comments

## Use Cases

- **Enterprise Code Review** — Consistent, thorough reviews at scale
- **CI/CD Integration** — Auto-review every PR before human review
- **Security Auditing** — Catch vulnerabilities before they ship
- **Code Quality Gates** — Block merges below a quality score threshold
- **Developer Training** — Learn from detailed, actionable feedback

## Testing

```bash
python -m pytest tests/ -v
```

All tests run offline — no API keys required.

## License

MIT — see [LICENSE](LICENSE).

## Built By

**Escipion Pedroza**

GitHub: [@escipionpedroza147-commits](https://github.com/escipionpedroza147-commits)
