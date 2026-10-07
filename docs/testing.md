# Testing

Category Radar maintains a comprehensive test suite enforcing minimum 60% coverage.

## Running Tests

```bash
# Run pytest with coverage report
pytest

# View HTML coverage report
open htmlcov/index.html

# Run specific test suites
pytest tests/test_normalize_comprehensive.py
pytest tests/test_fetch_resilience.py
pytest tests/test_async_and_api.py
```

## Quality Assurance Checks

```bash
# Linting
ruff check src/ tests/

# Formatting check
ruff format --check src/ tests/

# Security audit
bandit -r src/

# Dependency vulnerability scan
pip-audit
```
