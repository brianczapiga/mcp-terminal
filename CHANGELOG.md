# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial public release
- MCP server for macOS Terminal integration
- Support for Apple Terminal and iTerm2
- Session management and monitoring
- Content retrieval with configurable line limits
- Input control and command execution
- Scroll-back functionality
- Multiple operation modes (focus, recent-output, manual)
- Comprehensive error handling and logging
- Production-ready architecture with graceful degradation

### Features
- **Session Management**: List all Terminal windows and tabs with detailed information
- **Content Retrieval**: Get current screen contents with configurable line limits
- **Input Control**: Send commands or keystrokes to active sessions
- **Multiple Modes**: Support for focus, recent-output, and manual modes
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