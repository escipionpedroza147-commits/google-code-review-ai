# Contributing to Google Code Review AI

Thanks for wanting to contribute! Here's how to get started.

## Getting Started

1. **Fork** the repository
2. **Clone** your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/google-code-review-ai.git
   cd google-code-review-ai
   ```
3. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
4. **Create a branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Workflow

### Running the Server

```bash
cp .env.example .env
# Edit .env with your API keys
python main.py
```

### Running Tests

```bash
python -m pytest tests/ -v
```

All tests must pass before submitting a PR. Tests should NOT require API keys — mock all external calls.

### Code Style

- Follow PEP 8 for Python code
- Use type hints everywhere
- Keep functions under 50 lines
- Write docstrings for public functions
- No hardcoded secrets — ever

## Pull Request Process

1. **Write tests** for any new functionality
2. **Run the full test suite** and ensure everything passes
3. **Update documentation** if you've changed APIs or added features
4. **Keep PRs focused** — one feature or fix per PR
5. **Write a clear PR description** explaining what and why

### PR Checklist

- [ ] Tests pass (`python -m pytest tests/ -v`)
- [ ] No hardcoded secrets or API keys
- [ ] Docstrings added for new public functions
- [ ] README updated if needed
- [ ] No breaking changes to existing API endpoints

## Adding New Static Analysis Checks

The static analyzer (`src/core/static_analyzer.py`) is the best place to contribute:

1. Add your check function in the appropriate category (`_check_security`, `_check_complexity`, `_check_quality`)
2. Add tests in `tests/test_static_analyzer.py`
3. Update the README if it's a notable feature

## Adding Language Support

1. Add the language to the `Language` enum in `src/models/schemas.py`
2. Add file extension mapping in `detect_language()`
3. Add language-specific patterns in static analysis
4. Add tests for the new language

## Reporting Issues

- Use GitHub Issues
- Include: steps to reproduce, expected behavior, actual behavior
- Include the Python version and OS

## Code of Conduct

Be respectful. Be constructive. We're all here to build something great.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
