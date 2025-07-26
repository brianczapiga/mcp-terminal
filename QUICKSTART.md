# Quick Start Guide

Get up and running with Terminal MCP Server in minutes!

## Prerequisites

- macOS (required)
- Python 3.8 or higher
- Terminal.app or iTerm2 installed

## Installation

### Option 1: Automated Installation (Recommended)

```bash
# Clone the repository
git clone https://github.com/brianczapiga/mcp-terminal.git
cd mcp-terminal

# Run the installation script
./install.sh
```

### Option 2: Manual Installation

```bash
# Clone the repository
git clone https://github.com/brianczapiga/mcp-terminal.git
cd mcp-terminal

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Setup

1. **Grant Accessibility Permissions**:
   - Open **System Preferences** → **Security & Privacy** → **Privacy**
   - Select **Accessibility** from the left sidebar
   - Click the lock icon to make changes
   - Add **Terminal.app** (or **iTerm2**) to the list
   - Check the box next to it

2. **Verify Installation**:
   ```bash
   # Run health check
   make health
   # or
   python health_check.py
   ```

## Usage

### Running the Server

```bash
# Activate virtual environment (if not already active)
source venv/bin/activate

# Start the server (recommended: readonly mode for safety)
make run-safe
# or for full functionality (use with caution)
make run
# or manually
python terminal_mcp_server.py
```

The server will start and wait for MCP client connections via stdio.

**Security Note**: The `run-safe` command starts the server in readonly mode, which disables input injection for safety. Use `make run` only when you need full functionality.

### Connecting with AI Tools

#### Goose
1. Copy the configuration from `examples/goose_config.json`
2. Update the `cwd` path to point to your installation directory
3. Add the configuration to your Goose setup
4. Restart Goose

#### Void
1. Copy the configuration from `examples/void_config.yaml`
2. Update the `cwd` path to point to your installation directory
3. Add the configuration to your Void setup
4. Restart Void

## Basic Commands

Once connected, you can use these MCP tools:

- `list_sessions()` - List all terminal sessions
- `get_screen()` - Get current screen content
- `send_input(text, execute=True)` - Send commands to terminal
- `scroll_back(pages=1)` - Access scrollback buffer

## Troubleshooting

### Common Issues

1. **"Permission denied" errors**:
   - Ensure Terminal.app/iTerm2 has Accessibility permissions
   - Restart the terminal application after granting permissions

2. **"No sessions found"**:
   - Make sure you have at least one terminal window open
   - Try opening a new terminal window

3. **"AppleScript timeout"**:
   - The server has a 10-second timeout for AppleScript operations
   - Complex terminal operations may take longer

### Getting Help

- Run `make health` to check your setup
- Check the [troubleshooting section](README.md#troubleshooting) in the README
- Open an issue on [GitHub](https://github.com/brianczapiga/mcp-terminal/issues)

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check out the [examples](examples/) directory for configuration samples
- Explore the [API documentation](README.md#available-mcp-capabilities) for all available tools

Happy coding! 🚀 