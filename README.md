# Terminal MCP Server

A Python MCP (Model Context Protocol) server that allows AI tools (like Goose or Void) to collaborate with macOS Terminal sessions. The server provides tools to list, monitor, and control Terminal windows and tabs through AppleScript integration.

## Features

- **Session Management**: List all Terminal windows and tabs with detailed information
- **Content Retrieval**: Get current screen contents with configurable line limits
- **Input Control**: Send commands or keystrokes to active sessions
- **Multiple Modes**: Support for focus, recent-output, and manual modes
- **Buffer Management**: Rolling buffer for scroll-back functionality
- **Dual Terminal Support**: Primary support for Apple Terminal with iTerm2 fallback
- **Production Ready**: Error handling, logging, and graceful degradation

## Installation

### Prerequisites

- macOS (required for AppleScript integration)
- Python 3.10 or higher
- Terminal.app or iTerm2 installed

### Setup

1. **Clone or download the project**:
   ```bash
   git clone https://github.com/brianczapiga/mcp-terminal.git
   cd mcp-terminal
   ```

2. **Set up virtual environment and install dependencies**:
   ```bash
   # Option 1: Using Makefile (recommended)
   make setup
   
   # Option 2: Manual setup
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **For development setup** (optional):
   ```bash
   make dev-setup
   ```

3. **Grant necessary permissions**:
   - Go to **System Preferences** → **Security & Privacy** → **Privacy**
   - Add Terminal.app (or iTerm2) to **Accessibility** permissions
   - This allows the server to control your terminal applications

## Usage

### Starting the Server

The MCP server uses stdio transport for secure communication with AI tools:

```bash
# Option 1: Using Makefile (recommended)
make run

# Option 2: Manual execution
source venv/bin/activate
python terminal_mcp_server.py
```

The server will automatically detect whether you're using Apple Terminal or iTerm2.

### Available MCP Capabilities

The server provides the standard MCP discovery endpoints:

#### **Tools** - Interactive terminal operations
1. `list_sessions()` - List all Terminal sessions (windows/tabs)
2. `set_active_session(session_id)` - Select active session
3. `get_screen(lines=100, mode="focus")` - Get screen contents
4. `send_input(text, execute=True, session_id=None)` - Send commands/keystrokes
5. `scroll_back(pages=1, session_id=None)` - Access older content

#### **Resources** - Terminal session content
- **URI Format**: `terminal://session/{session_id}`
- **MIME Type**: `text/plain`
- **Content**: Current terminal session output
- **Metadata**: Session information (window_id, tab_id, tty_device, etc.)

#### **Prompts** - AI assistance templates
1. `terminal_session_summary` - Generate session summaries
2. `terminal_command_suggestion` - Suggest next commands
3. `terminal_troubleshooting` - Analyze session for issues

### Tool Details

#### `list_sessions()`
Lists all Terminal sessions (windows/tabs) with their information.

**Returns:**
- `session_id`: Unique identifier for the session
- `window_id`: Terminal window ID
- `tab_id`: Tab ID within the window
- `name`: Session name/title
- `tty_device`: Associated TTY device (if available)
- `is_active`: Whether the session is currently active
- `last_activity`: Timestamp of last activity

#### `set_active_session(session_id)`
Manually select which session the AI should watch/control.

**Parameters:**
- `session_id`: The session ID to set as active

#### `get_screen(lines=100, mode="focus")`
Get the current screen contents of terminal sessions.

**Parameters:**
- `lines`: Number of lines to retrieve (default: 100)
- `mode`: Session selection mode
  - `focus` (default): Use the last focused session
  - `recent-output`: Find session with most recent TTY activity
  - `manual`: Use currently set active session
  

#### `send_input(text, execute=True, session_id=None)`
Send input (commands or keystrokes) to the terminal.

**Parameters:**
- `text`: Text to send to the terminal
- `execute`: Whether to execute the command (press Enter) (default: true)
- `session_id`: Session ID to send to (uses active if not specified)

#### `scroll_back(pages=1, session_id=None)`
Scroll back to get older content from the terminal buffer.

**Parameters:**
- `pages`: Number of pages to scroll back (default: 1)
- `session_id`: Session ID to scroll back (uses active if not specified)

## Connecting to AI Tools

### Goose Integration

1. **Add the server to your Goose configuration** (see `examples/goose_config.json`):
   ```json
   {
     "tools": [
       {
         "name": "terminal-mcp",
         "type": "mcp",
         "config": {
           "command": "python",
           "args": ["terminal_mcp_server.py"],
           "cwd": "/path/to/mcp-terminal",
           "env": {
             "PYTHONPATH": "/path/to/mcp-terminal"
           }
         }
       }
     ]
   }
   ```

2. **Restart Goose** to load the new tool configuration.

### Void Integration

1. **Configure Void to use the MCP server** (see `examples/void_config.yaml`):
   ```yaml
   tools:
     - name: terminal-mcp
       type: mcp
       config:
         command: python
         args: [terminal_mcp_server.py]
         cwd: /path/to/mcp-terminal
         env:
           PYTHONPATH: /path/to/mcp-terminal
   ```

2. **Restart Void** to apply the configuration.

### Other MCP-Compatible Tools

The server follows the MCP specification and should work with any MCP-compatible AI tool. The server uses stdio transport for secure communication, ensuring that only the parent AI tool process can interact with the terminal.

## Example Usage Scenarios

### 1. Monitoring Active Development
```python
# List all sessions
sessions = await list_sessions()

# Set focus to the most active session
await set_active_session(sessions[0]["session_id"])

# Get current screen content
content = await get_screen(lines=50, mode="focus")

# Send a command
await send_input("ls -la", execute=True)
```

### 2. Multi-Session Management
```python
# Get content from all visible sessions
all_content = await get_all_terminal_info()

# Find session with recent output
recent_content = await get_screen(mode="recent-output")
```

### 3. Command Review Mode
```python
# Type a command without executing
await send_input("rm -rf /important/directory", execute=False)

# Let user review, then execute
await send_input("", execute=True)  # Just press Enter
```

## Architecture

### TerminalManager Class
The core class that abstracts terminal operations:

- **Session Detection**: Automatically detects Apple Terminal vs iTerm2
- **AppleScript Integration**: Uses `osascript` for terminal control
- **Buffer Management**: Maintains rolling buffers for scroll-back
- **Error Handling**: Graceful degradation when operations fail

### MCP Server
Built with FastMCP for easy integration:

- **Async Operations**: All tools are async for better performance
- **Type Safety**: Uses Pydantic models for request/response validation
- **Error Reporting**: Comprehensive error messages and logging

## Troubleshooting

### Common Issues

1. **Permission Denied Errors**:
   - Ensure Terminal.app/iTerm2 has Accessibility permissions
   - Check System Preferences → Security & Privacy → Privacy → Accessibility

2. **No Sessions Found**:
   - Make sure Terminal.app or iTerm2 is running
   - Check that you have at least one terminal window open

3. **AppleScript Timeout**:
   - The server has a 10-second timeout for AppleScript operations
   - Complex terminal operations may take longer

4. **iTerm2 Not Detected**:
   - Ensure iTerm2 is properly installed and running
   - The server falls back to Apple Terminal if iTerm2 is not available

### Debug Mode

Enable debug logging by modifying the logging level in the script:

```python
logging.basicConfig(level=logging.DEBUG)
```

### Health Check

The server provides a health check endpoint:

```bash
curl http://localhost:8000/health
```

## Security Considerations

### Input Injection Safety

**⚠️ IMPORTANT**: This server can send arbitrary commands to your terminal, which could be dangerous if the AI tool is compromised or makes poor decisions.

**Security Features:**
- **Readonly Mode**: Set `MCP_TERMINAL_READONLY=1` to disable all input injection
- **stdio transport**: Only the parent AI tool process can communicate with the server
- **AppleScript permissions**: Requires user permission and Accessibility access
- **No network exposure**: All communication is through stdin/stdout
- **Terminal control limited**: Only to the user's own terminal sessions

### Recommended Security Practices

1. **Use Readonly Mode by Default**:
   ```bash
   export MCP_TERMINAL_READONLY=1
   python terminal_mcp_server.py
   ```

2. **Review Commands Before Execution**: 
   - Don't blanket trust AI tools to run commands
   - Review suggested commands before approval
   - Use the AI tool's built-in approval mechanisms

3. **Enable Input Injection Only When Needed**:
   ```bash
   # Only enable when you need input injection
   export MCP_TERMINAL_READONLY=0
   python terminal_mcp_server.py
   ```

4. **Monitor Terminal Activity**: 
   - Keep an eye on your terminal when input injection is enabled
   - Be aware of what commands are being executed

### Security Warnings

- Commands like `rm -rf /`, `sudo`, or other destructive operations are possible
- Malicious AI tools or compromised clients could execute dangerous commands
- Always review and approve commands before execution
- Consider using readonly mode for production or sensitive environments

## Development

### Adding New Tools

1. Define the tool function with `@server.tool()` decorator
2. Create Pydantic models for request/response
3. Add error handling and logging
4. Update documentation

### Testing

```bash
# Run all tests
make test

# Run specific test file
pytest tests/test_terminal_mcp_server.py

# Run with coverage
pytest --cov=terminal_mcp_server tests/

# Run only unit tests (skip integration tests)
pytest -m "not slow" tests/
```

## Development

This project was developed using [Cursor](https://cursor.sh), an AI-powered code editor, demonstrating modern AI-assisted development workflows. The codebase was primarily "vibe coded" - a collaborative process between human developer and AI assistant.

The project follows standard Python development practices and is fully maintainable by human developers.

### Code Quality

```bash
# Format code
make format

# Run linting
make lint

# Run all checks (lint, format, test)
make check

# Clean up generated files
make clean
```

### Adding New Tools

1. Define the tool function with `@server.tool()` decorator
2. Create Pydantic models for request/response
3. Add error handling and logging
4. Update documentation

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details on how to:

- Report bugs
- Suggest enhancements
- Submit pull requests
- Follow our coding standards

## Code of Conduct

This project adheres to the Contributor Covenant Code of Conduct. Please read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for details.

## Support

For issues and questions:

1. Check the [troubleshooting section](#troubleshooting)
2. Review the logs for error messages
3. Open an issue on the [GitHub repository](https://github.com/brianczapiga/mcp-terminal/issues)
4. Ensure you're running on macOS with proper permissions

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a list of changes and version history. 