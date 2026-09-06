# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-09-04

### Changed
- Modernized the package for Python 3.10+, FastMCP 3, and Pydantic 2.
- Split terminal automation into typed backends, policy-aware management, and a stdio server entry point.
- Made read-only behavior the default and added session/TTY exclusions and self-target protection.
- Documented and sampled current Codex and Claude client configurations.
- Replaced permissive legacy CI with mandatory Ruff, mypy, pytest, and wheel-build checks on Python 3.10–3.13.

### Added
- Eight typed MCP tools, a terminal resource, and four workflow prompts.
- Side-effect-free local installation health diagnostics.

## [1.0.1] - 2025-07-26

### Fixed
- **Void Compatibility**: Fixed tool call handling to support Void's request wrapping pattern
- **Request Format Support**: Added support for `{"request": {}}`, `{"request": ""}`, and `{"request": "string"}` formats
- **Backward Compatibility**: Maintained full compatibility with standard MCP clients like Goose
- **Code Quality**: Fixed all CI linting issues and improved code quality score to 10.00/10
- **Formatting**: Resolved Black formatting conflicts and ensured consistent code style

### Technical Improvements
- Enhanced tool function signatures to accept flexible request parameters
- Improved error handling for various request formats
- Updated CI pipeline configuration for better reliability
- Fixed self-assigning variable issues and implicit string concatenation
- Disabled conflicting Pylint rules that don't align with Black formatting

### Compatibility
- ✅ **Void**: Full compatibility with Void's MCP client
- ✅ **Goose**: Maintained backward compatibility with standard MCP clients
- ✅ **Other MCP Clients**: Should work with any MCP client following the protocol

## [Unreleased]

### Fixed
- Kept Terminal.app session IDs bound to TTYs when tabs are reordered.
- Kept configured session and TTY exclusions absolute when self-target override is enabled.
- Required write tools to receive an explicit or previously selected session instead of choosing one automatically.
- Aligned `make setup` with the documented Python 3.10+ support range.

### Changed
- Replaced the misleading `recent-output` screen mode with deterministic `automatic` selection.

### Added
- Initial public release
- MCP server for macOS Terminal integration
- Support for Apple Terminal and iTerm2
- Session management and monitoring
- Content retrieval with configurable line limits
- Input control and command execution
- Scroll-back functionality
- Multiple operation modes (focus, automatic, manual)
- Comprehensive error handling and logging
- Production-ready architecture with graceful degradation

### Features
- **Session Management**: List all Terminal windows and tabs with detailed information
- **Content Retrieval**: Get current screen contents with configurable line limits
- **Input Control**: Send commands or keystrokes to active sessions
- **Multiple Modes**: Support for focus, automatic, and manual modes
- **Buffer Management**: Rolling buffer for scroll-back functionality
- **Dual Terminal Support**: Primary support for Apple Terminal with iTerm2 fallback
- **Production Ready**: Error handling, logging, and graceful degradation

### Technical Details
- Built with FastMCP for easy integration
- Uses AppleScript for terminal control
- Async operations for better performance
- Type safety with Pydantic models
- Comprehensive error reporting and logging
- stdio transport for secure communication

## [1.0.0] - 2024-07-26

### Added
- Initial release of Terminal MCP Server
- Complete MCP protocol implementation
- macOS Terminal and iTerm2 support
- Full session management capabilities
- Input/output control features
- Comprehensive documentation
- MIT License
- Development tooling and configuration

### Security
- stdio transport for secure communication
- No network exposure
- User permission requirements for AppleScript operations
