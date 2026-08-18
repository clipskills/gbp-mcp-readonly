# gbp-mcp

Standalone **MCP server** for [Google Business Profile](https://developers.google.com/my-business). It exposes accounts, locations, reviews, posts, media, Q&A, insights, and a few write actions as JSON tools for Cursor, Claude Desktop, and Claude Code.

This repository is **not** the Streamlit [GMB-Management-System](https://github.com/marcusbtc/GMB-Management-System) app. There is no web UI, PDF export, Plotly charts, i18n dashboard, or Gemini reply drafting. Google API calls live in this repo (`data_fetcher.py`, `drive_helper.py`). You do not need to clone or run the Streamlit project.

## Tools

Read:

- `list_accounts`
- `list_locations`
- `get_daily_metrics`
- `get_search_keywords`
- `list_reviews`
- `list_posts`
- `list_media`
- `list_questions`
- `profile_health_check`

Write:

- `create_local_post`
- `upload_image_to_drive`
- `reply_to_review`

Auth helpers:

- `start_oauth`
- `complete_oauth`

Every tool returns JSON only (no DataFrame, PDF, or chart objects).

Location IDs accept `accounts/{accountId}/locations/{locationId}`, `locations/{locationId}`, or a bare id. v4 calls (reviews, posts, media) go through `resolve_location_parent`. Dates are `YYYY-MM-DD`. Drive uploads take base64 image bytes (`file_base64`) and can return a public URL for GBP posts.

## Requirements

- Python 3.10+
- A Google Cloud OAuth **user** client (Desktop or Web). Service accounts are not supported.
- These OAuth scopes:
  - `https://www.googleapis.com/auth/business.manage`
  - `https://www.googleapis.com/auth/drive.file`
  - `https://www.googleapis.com/auth/drive.metadata.readonly`

Enable the Google APIs your tools will call, typically:

- My Business Account Management API
- My Business Business Information API
- My Business Q&A API
- Business Profile Performance API
- Google Drive API
- Google My Business API (v4 discovery, used for reviews / posts / media)

## Install

```bash
git clone https://github.com/marcusbtc/gbp-mcp.git
cd gbp-mcp
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` and export the values, or put them in your MCP client `env` block. Do not commit `.env`, `client_secret.json`, or token files.

```bash
cp .env.example .env
```

## Authenticate (user OAuth only)

Never put tokens, refresh tokens, or `client_secret.json` in git.

You need a Google Cloud OAuth client ID and secret (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`). Optional: place a local `client_secret.json` in the repo root (gitignored).

Add this redirect URI on the OAuth client (unless you override it):

```text
http://localhost:8753/
```

Then pick one of:

1. **Per-call token** — pass `access_token` on any tool.
2. **Environment token** — set `GOOGLE_ACCESS_TOKEN`. Optional refresh: `GOOGLE_REFRESH_TOKEN` plus client id/secret.
3. **Local helper** (opens a browser, writes a gitignored token file, default `.gmb-mcp-token.json`):

```bash
python mcp_server.py --oauth
```

4. **MCP tools** — call `start_oauth`, approve access, then `complete_oauth` with the `code` query parameter from the redirect URL.

`complete_oauth` and `--oauth` never print tokens. Override the token path with `GMB_MCP_TOKEN_PATH`. Override the redirect with `GOOGLE_REDIRECT_URI`.

## Run

stdio (default — Cursor, Claude Desktop, Claude Code):

```bash
python mcp_server.py
# or: python -m src.gmb_mcp
```

Optional Streamable HTTP:

```bash
python mcp_server.py --http --host 127.0.0.1 --port 8765
```

Endpoint: `http://127.0.0.1:8765/mcp`

## Connect from Cursor

Add to MCP settings (project `.cursor/mcp.json` or user MCP config). Use an **absolute** path. Do not put tokens in a committed file.

```json
{
  "mcpServers": {
    "google-business-profile": {
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "/absolute/path/to/gbp-mcp",
      "env": {
        "GOOGLE_CLIENT_ID": "<your-oauth-client-id>",
        "GOOGLE_CLIENT_SECRET": "<your-oauth-client-secret>"
      }
    }
  }
}
```

If you already have a user access token and prefer not to run `--oauth`:

```json
{
  "mcpServers": {
    "google-business-profile": {
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "/absolute/path/to/gbp-mcp",
      "env": {
        "GOOGLE_ACCESS_TOKEN": "<your-oauth-access-token>"
      }
    }
  }
}
```

Point `command` at the venv interpreter if you do not want to activate it first, for example `/absolute/path/to/gbp-mcp/.venv/bin/python`.

HTTP instead of stdio (start the server yourself first):

```json
{
  "mcpServers": {
    "google-business-profile": {
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

## Connect from Claude Desktop / Claude Code

Claude Desktop (`claude_desktop_config.json`) and Claude Code use the same stdio shape:

```json
{
  "mcpServers": {
    "google-business-profile": {
      "command": "/absolute/path/to/gbp-mcp/.venv/bin/python",
      "args": ["/absolute/path/to/gbp-mcp/mcp_server.py"],
      "env": {
        "GOOGLE_CLIENT_ID": "<your-oauth-client-id>",
        "GOOGLE_CLIENT_SECRET": "<your-oauth-client-secret>"
      }
    }
  }
}
```

Run `python mcp_server.py --oauth` once in that working directory so `.gmb-mcp-token.json` exists, or set `GOOGLE_ACCESS_TOKEN`.

## Security

- Never commit `client_secret.json`, `.env`, or `.gmb-mcp-token.json`.
- Never paste access tokens into chat, issues, or screenshots.
- Tools and OAuth helpers do not return tokens.
- Drive uploads with `make_public=true` create a world-readable file URL. Use that only when you intend to attach the image to a public GBP post.

## Development

```bash
pip install -r requirements-dev.txt
ruff check src tests mcp_server.py
pytest
python -m py_compile mcp_server.py data_fetcher.py drive_helper.py health_check.py
python mcp_server.py --help
```

## License

MIT (see `LICENSE`).
