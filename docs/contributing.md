# Contributing

Contributions and enhancements are welcome!

## Development Workflow

1. Fork and clone the repository.
2. Create a dedicated feature branch.
3. Install dependencies in editable mode: `pip install -e ".[browser,dev,docs]"`.
4. Ensure code passes `ruff check`, `ruff format`, and `pytest`.
5. Submit a pull request.

## Code Guidelines

- Maintain type annotations on all public functions.
- Preserve backward compatibility with existing command arguments.
- Add offline HTML fixture tests when adding new channel adapters.
