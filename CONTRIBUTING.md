# Contributing to Terminal MCP Server

Thank you for your interest in contributing to the Terminal MCP Server! This document provides guidelines and information for contributors.

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

- Use the GitHub issue tracker
- Include detailed steps to reproduce the bug
- Provide your macOS version and Python version
- Include any error messages or logs
- Describe the expected behavior vs. actual behavior

### Suggesting Enhancements

- Use the GitHub issue tracker with the "enhancement" label
- Clearly describe the feature and its benefits
- Consider the impact on existing functionality
- Provide examples of how the feature would be used

### Pull Requests

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes**:
   - Follow the coding style guidelines
   - Add tests for new functionality
   - Update documentation as needed
4. **Test your changes**: `make test`
5. **Commit your changes**: Use conventional commit messages
6. **Push to your fork**: `git push origin feature/amazing-feature`
7. **Create a Pull Request**

## Development Setup

### Prerequisites

- macOS (required for AppleScript integration)
- Python 3.8 or higher
- Terminal.app or iTerm2 installed

### Local Development

1. **Clone your fork**:
   ```bash
   git clone https://github.com/your-username/mcp-terminal.git
   cd mcp-terminal
   ```

2. **Set up development environment**:
   ```bash
   make dev-setup
   source venv/bin/activate
   ```

3. **Install pre-commit hooks** (optional but recommended):
   ```bash
   pip install pre-commit
   pre-commit install
   ```

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
pytest tests/test_specific.py

# Run with coverage
pytest --cov=terminal_mcp_server tests/
```

### Code Quality

```bash
# Format code
make format

# Run linting
make lint

# Run all checks
make check
```

## Coding Standards

### Python Style

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guidelines
- Use Black for code formatting (line length: 88)
- Use type hints for all function parameters and return values
- Write docstrings for all public functions and classes

### Code Structure

- Keep functions focused and single-purpose
- Use meaningful variable and function names
- Add comments for complex logic
- Handle errors gracefully with appropriate logging

### Testing

- Write unit tests for new functionality
- Aim for good test coverage
- Use descriptive test names
- Mock external dependencies when appropriate

## Commit Message Guidelines

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

Types:
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to the build process or auxiliary tools

Examples:
```
feat: add support for iTerm2 sessions
fix: handle AppleScript timeout errors gracefully
docs: update installation instructions for macOS Ventura
```

## Review Process

1. **Automated Checks**: All PRs must pass CI checks
2. **Code Review**: At least one maintainer must approve
3. **Testing**: Changes must be tested on macOS
4. **Documentation**: New features must be documented

## Release Process

1. **Version Bump**: Update version in `pyproject.toml`
2. **Changelog**: Update `CHANGELOG.md` with new changes
3. **Tag Release**: Create a new git tag
4. **Publish**: Release to PyPI (maintainers only)

## Getting Help

- **Issues**: Use GitHub issues for bugs and feature requests
- **Discussions**: Use GitHub Discussions for questions and ideas
- **Documentation**: Check the README and inline code documentation

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Recognition

Contributors will be recognized in the README and release notes. Significant contributions may be invited to become maintainers.

Thank you for contributing to Terminal MCP Server! 🚀 