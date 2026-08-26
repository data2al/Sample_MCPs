# Deploying to Render + connecting to Claude

This repo folder builds two independent MCP servers, each its own `uv` project:

- `weather/` — NWS weather alerts & forecasts (`weather.py`)
- `currency/` — currency exchange rates & conversion (`currency.py`)

Both are built the same way (see the numbered files in this folder) and both
deploy the same way, described once below.

## How the transport switch works

Locally, Claude Desktop launches the server as a subprocess and talks to it
over **stdio**. Render instead runs it as a long-lived web process and needs
**streamable-http**. Both apps' `main()` picks the transport automatically:

```python
def main():
    port = os.environ.get("PORT")
    if port:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=int(port))
    else:
        mcp.run(transport="stdio")
```

Render always sets a `PORT` environment variable for web services, so nothing
needs to be configured — the same `weather.py` / `currency.py` file runs
correctly in both places. Test the HTTP path locally first with
`005_run_http_locally.ps1` (weather) or `010_run_http_locally_currency.ps1`
(currency) before deploying.

## 1. Push each app to its own GitHub repo

Render deploys from a git repo, one service per repo. `weather/` and
`currency/` are already separate git repos (created by `uv init`), just
without commits or a remote yet. For each folder:

```powershell
cd weather   # or currency
git add -A
git commit -m "Initial commit"
```

Then create an empty repo on GitHub (one named `weather`, one named
`currency`) and push:

```powershell
git remote add origin https://github.com/<your-username>/weather.git
git branch -M main
git push -u origin main
```

## 2. Create the Render web service

Repeat for each app:

1. [dashboard.render.com](https://dashboard.render.com) → **New +** → **Web Service**.
2. Connect the GitHub repo (`weather` or `currency`).
3. **Runtime**: Python 3.
4. **Build Command**:
   ```
   pip install uv && uv sync
   ```
   (Don't use `uv sync --locked` here — Render's Python runtime version and
   uv version won't always match what generated `uv.lock` locally, and
   `--locked` hard-fails the build on any mismatch instead of just
   re-resolving. Plain `uv sync` updates the lock at build time if needed.)
5. **Start Command** (matches the local test command exactly):
   ```
   uv run weather.py
   ```
   (or `uv run currency.py` for the second service)
6. **Instance type**: Free is fine to start. Note that free instances spin
   down after inactivity, so the first request after idle time can take
   ~30-60s while it wakes back up — later requests are fast.
7. Leave **Health Check Path** blank/default. The MCP endpoint only answers
   `POST /mcp`, so an HTTP health check pointed at it (or at `/`) can report
   false failures; Render's default TCP check is sufficient.
8. Create the service and wait for the first deploy to finish.

You do not need to set a `PORT` environment variable yourself — Render
injects it, and that's exactly what triggers the streamable-http branch in
`main()` above.

## 3. Verify the deployed server responds

The path is always `/mcp` — it doesn't change per app, so don't append the
app name (`/mcp/currency` etc. will 404).

In Windows PowerShell, use `Invoke-RestMethod` rather than `curl` — `curl` is
aliased to `Invoke-WebRequest` (no `-X`/`-d` support), and even `curl.exe`
called explicitly is unreliable here: PowerShell re-escapes arguments when
calling a native `.exe`, which can strip the double quotes out of an inline
JSON string and produce exactly the parse error you'd see back
(`"key must be a string"`). Building the body as a PowerShell object and
letting `ConvertTo-Json` serialize it sidesteps that entirely:

```powershell
$body = @{
    jsonrpc = "2.0"
    id      = 1
    method  = "initialize"
    params  = @{
        protocolVersion = "2025-06-18"
        capabilities    = @{}
        clientInfo      = @{ name = "test"; version = "1.0" }
    }
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Uri "https://<your-service>.onrender.com/mcp" -Method Post `
  -Headers @{ "Accept" = "application/json, text/event-stream" } `
  -ContentType "application/json" `
  -Body $body
```

A JSON-RPC result back (not an `error` field) means the server is live.

## 4. Connect Claude to the deployed server

On [claude.ai](https://claude.ai): **Settings → Connectors → Add custom
connector**, and paste the Render URL with `/mcp` on the end, e.g.
`https://weather-xxxx.onrender.com/mcp`. Repeat for the currency service.
Claude will list `get_alerts` / `get_forecast` (weather) or
`get_exchange_rate` / `convert` (currency) as available tools once connected.

## Local use (Claude Desktop) still works unchanged

Claude Desktop's `claude_desktop_config.json` launches the server locally
over stdio — it doesn't touch Render or `PORT` at all:

```json
{
  "mcpServers": {
    "weather": {
      "command": "uv",
      "args": ["--directory", "C:\\Users\\alanl\\Desktop\\coding\\python-mcp\\weather", "run", "weather.py"]
    },
    "currency": {
      "command": "uv",
      "args": ["--directory", "C:\\Users\\alanl\\Desktop\\coding\\python-mcp\\currency", "run", "currency.py"]
    }
  }
}
```

## Redeploying after changes

Render auto-deploys on every push to the connected branch. Commit, push, and
the dashboard shows the new build/deploy.


curl https://currency-lly8.onrender.com/mcp/currency `
  -X POST `
  -H "Content-Type: application/json" `
  -H "Accept: application/json, text/event-stream" `
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
