# Contributing

Terminal MCP Server supports macOS and Python 3.10+. Fork the repository, create a focused branch, and install the package and development tools:

```bash
git clone https://github.com/YOUR-NAME/mcp-terminal.git
cd mcp-terminal
make setup
cp env.example .env
```

Before submitting a pull request, run the same mandatory checks as CI:

```bash
make check
```

Useful narrower commands are `make test`, `make lint`, and `make format`. Run one test with `.venv/bin/pytest tests/unit/test_config.py`. Smoke tests that exercise real terminal applications or macOS permissions must be marked `smoke`; the normal CI suite excludes them.

Add behavior-focused tests for executable changes and update user documentation when interfaces change. Do not make tests depend on prose wording. Ruff owns formatting and linting; mypy checks `terminal_mcp` and `tests`.

Use clear conventional commit subjects such as `fix: handle an unavailable terminal`. Pull requests should describe the behavior, risk, and commands used to verify it. By contributing, you agree that your work is licensed under the [MIT License](LICENSE) and follows the [Code of Conduct](CODE_OF_CONDUCT.md).
