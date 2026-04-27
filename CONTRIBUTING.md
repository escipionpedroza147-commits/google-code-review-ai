# Contributing to Google Code Review AI

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

```bash
git clone https://github.com/escipionpedroza147-commits/google-code-review-ai.git
cd google-code-review-ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -v
```

## Code Style

- Python 3.9+ with type hints
- Docstrings on all public functions and classes
- Follow existing patterns in `src/`

## Commit Messages

Use conventional commits:
- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation
- `test:` — adding/updating tests
- `ci:` — CI/CD changes
- `refactor:` — code restructuring

## Pull Request Checklist

- [ ] All tests pass (`python -m pytest tests/ -v`)
- [ ] New features include tests
- [ ] Code has type hints and docstrings
- [ ] README updated if adding endpoints/features

## Reporting Issues

Open a GitHub issue with:
1. What you expected
2. What happened
3. Steps to reproduce
4. Python version and OS

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
