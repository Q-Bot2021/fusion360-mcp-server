# Devcontainer setup

Run the MCP **on the Windows host**, over stdio, while VS Code keeps your workspace
in a same-PC devcontainer. TCP bridge startup is unconditionally disabled.

## Supported Host-local Setup

1. Install this changed checkout on Windows (`uv sync --dev --python 3.12`) and
  copy its updated add-in to Fusion's AddIns location. Restart the add-in.
2. In the local VS Code user profile, use **MCP: Open User Configuration**. Do not
  put this server in container workspace or remote-user configuration.
3. Use a Windows-local executable from this checkout. For example, adapting the
  checkout path to your installation:

```json
{
  "servers": {
   "fusion360": {
    "type": "stdio",
    "command": "C:\\GitRepo\\fusion360-mcp-server\\.venv\\Scripts\\python.exe",
    "args": ["-m", "fusion360_mcp", "--mode", "socket"],
    "env": {"FUSION_MCP_HOST": "127.0.0.1", "FUSION_MCP_PORT": "9876"}
   }
  }
}
```

4. Remove the old wrapper entry from active client configuration. Confirm the MCP
  process runs on Windows, not in Docker, while the workspace remains in Docker.
5. Call `ping` and `get_scene_info` through VS Code. The only Fusion listener must
  be `127.0.0.1` on the configured port, with no bridge forwarding rules.

[VS Code documents local user-profile MCP servers](https://code.visualstudio.com/docs/copilot/customization/mcp-servers)
as running locally even in remote workspaces. Verify on your installed client;
do not silently restore networking if that integration is unavailable.
Container-native Claude Code/Cursor processes need a separately designed local
IPC integration and are not supported by this replacement.

## Existing Bridge Cleanup

Changing source does not remove persistent Windows networking rules or stop old
relay processes. Inventory Fusion-specific `netsh interface portproxy show all`
entries and firewall rules first. With administrator approval, run cleanup for
each previously configured Fusion port from an elevated terminal:

```powershell
.\devcontainer\fusion-mcp-bridge.ps1 -Remove -Port 9876
```

Inspect for leftover rules targeting removed adapters or old wildcard bindings;
remove only identified Fusion rules. Confirm ownership before stopping old
wrapper processes. Do not delete unrelated proxy/firewall rules. The setup path
now errors, while its original implementation and cleanup path remain in source.

See [developer rules](../dev_rules.md) for protocol and live-Fusion verification.

<details>
<summary>Historical bridge reference (disabled; do not follow these setup steps)</summary>

The following describes the retained legacy implementation, not the supported
setup. Private address ranges do not prove an adapter belongs to Docker, and a
proxy can mask a remote client's source as loopback.

## The problem

`fusion360-mcp-server` connects to `localhost:9876` to reach the Fusion add-in. From inside a Docker container, `localhost` is the container's own loopback — not the Windows host where Fusion is running. Three things stand in the way:

1. The container's `localhost` does not reach the host
2. The Fusion add-in binds to `127.0.0.1` on Windows, so even traffic that reaches the host gets dropped if it comes in on a different interface
3. Windows Firewall blocks inbound traffic from the Docker subnet by default

## The fix

```
Devcontainer
  MCP client
    └── spawns fusion-mcp-wrapper.sh (stdio MCP subprocess)
         ├── Python TCP relay  localhost:9876 ──────────────────────┐
         └── uvx fusion360-mcp-server  (connects to localhost:9876) ┘
                                                                     │ relayed to
                                                              host.docker.internal:9876
                                                                     │
Windows host (netsh portproxy)                                       │
  Docker bridge IP:9876 ──forwards──► 127.0.0.1:9876 ◄───────────────┘
                                            │
                                     Fusion MCP add-in
```

Two scripts handle it:

1. **`fusion-mcp-bridge.ps1`** (Windows-side, run once as Administrator) — adds `netsh portproxy` rules forwarding the Docker bridge adapter IPs to `127.0.0.1:9876`, plus a Windows Firewall inbound rule scoped to the Docker subnet only. Both rules persist across reboots.
2. **`fusion-mcp-wrapper.sh`** (devcontainer-side, configured as your MCP client's stdio command) — starts a Python TCP relay forwarding the container's `localhost:9876` to `host.docker.internal:9876`, then execs `uvx fusion360-mcp-server --mode socket`. The MCP server connects to `localhost:9876` unchanged; the relay bridges it to the Windows host.

## Setup

### 1. Install the Fusion add-in (Windows)

Follow the main README — copy the `addon` directory into Fusion's add-ins folder and start it via Shift+S → Add-Ins → Fusion360MCP → Run. Confirm in TEXT COMMANDS:

```
[MCP] Server listening on localhost:9876
```

### 2. Run the Windows bridge script (once, as Administrator)

```powershell
.\devcontainer\fusion-mcp-bridge.ps1
```

The script:
1. Historically selected adapters by a 172.16–31.x heuristic, which can also include LAN/VPN adapters
2. Adds a `netsh portproxy` rule per adapter forwarding to `127.0.0.1:9876`
3. Adds a Windows Firewall inbound rule scoped to those subnets

Idempotent. Re-run after Docker network changes. To remove:

```powershell
.\devcontainer\fusion-mcp-bridge.ps1 -Remove
```

### 3. Verify connectivity from the devcontainer

```bash
python3 -c "
import socket
s = socket.socket()
s.settimeout(3)
s.connect(('host.docker.internal', 9876))
print('OK')
s.close()
"
```

If you get `Connection refused`: Fusion add-in isn't running.  
If you get `Connection timed out`: portproxy or firewall rule missing — re-run the bridge script.

### 4. Configure your MCP client

Point your MCP client's stdio command at the wrapper script (use an absolute path).

**Claude Code (`.claude/settings.json`):**
```json
{
  "mcpServers": {
    "fusion": {
      "command": "/absolute/path/to/devcontainer/fusion-mcp-wrapper.sh",
      "args": []
    }
  }
}
```

**VS Code MCP (`.vscode/mcp.json`):**
```json
{
  "servers": {
    "fusion": {
      "type": "stdio",
      "command": "/absolute/path/to/devcontainer/fusion-mcp-wrapper.sh"
    }
  }
}
```

**Cursor (`~/.cursor/mcp.json`):**
```json
{
  "mcpServers": {
    "fusion": {
      "command": "/absolute/path/to/devcontainer/fusion-mcp-wrapper.sh"
    }
  }
}
```

### 5. Test

Ask your MCP client to call the `ping` tool. If it returns `{"pong": true}`, you're connected end-to-end.

## Prerequisites

- **Docker Desktop** on Windows (the wrapper relies on `host.docker.internal`, which Docker Desktop populates automatically)
- **`uv`** in the devcontainer (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Python 3.8+** in the devcontainer (for the TCP relay — uses only stdlib)
- The wrapper script must be executable: `chmod +x devcontainer/fusion-mcp-wrapper.sh`

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| MCP client shows server disconnected | Wrapper failed to start | Run the wrapper manually (`bash devcontainer/fusion-mcp-wrapper.sh`) and check stderr |
| `uvx: not found` | uv not installed in container | Install uv (see Prerequisites) |
| Python relay error: address in use | Stale relay from a previous run | `lsof -ti:9876 \| xargs kill` |
| TCP test: connection refused | Fusion add-in not running on host | Shift+S → Add-Ins → Fusion360MCP → Run |
| TCP test: connection timed out | Bridge script not run, or firewall blocking | Re-run `fusion-mcp-bridge.ps1` as Administrator |
| Bridge script: no Docker adapters found | Docker Desktop not running, or unusual network setup | Check `Get-NetIPAddress` shows a 172.16–31.x adapter |

## Why not bind the add-in to 0.0.0.0?

That would expose the Fusion API on LAN/VPN interfaces. Wildcard binding and
bridge startup are now disabled; private-subnet matching was not a sufficient
same-machine security boundary.

</details>
