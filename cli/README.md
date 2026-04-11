# Yoke CLI

`yoke` is the command-line interface for the [Yoke Agent](https://github.com/Empreiteiro/yoke-agent)
AI Quality Studio. It lets humans and AI agents drive the same backend
the web UI uses, over a typed HTTP client.

## Install

One-liner (curl | sh):

```sh
curl -fsSL https://raw.githubusercontent.com/Empreiteiro/yoke-agent/main/install.sh | sh
```

Or, from a local checkout:

```sh
pipx install ./cli
```

## Quick start

```sh
# 1. Bootstrap a local Yoke checkout (clones the repo, copies .env)
yoke install

# 2. Start the local stack (docker compose up)
yoke serve

# 3. Verify CLI <-> backend connectivity
yoke doctor

# 4. Manage providers
yoke providers list
yoke providers create --name openai --type openai --api-key $OPENAI_API_KEY \
  --llm-models gpt-4o-mini,gpt-4.1-mini --default-llm gpt-4o-mini

# 5. Run a RAG experiment
yoke datasets list
yoke experiments create --dataset-id 1 --name "baseline"
yoke experiments configure-grid 1 --chunk-sizes 512,1024 --top-k 3,5
yoke experiments run 1
yoke experiments report 1

# 6. Run an agent experiment
yoke agents configs
yoke agents create --name smoke --config-id 1 \
  --variants 1,2 --models gpt-4o-mini,o3 --temperatures 0.0,0.5
yoke agents run 1
yoke agents status 1
yoke agents report 1
```

## Configuration

Settings resolve in this order: CLI flag → environment variable → config file → default.

| Setting     | Env var          | Config key   | Default                       |
|-------------|------------------|--------------|-------------------------------|
| Backend URL | `YOKE_BASE_URL`  | `base_url`   | `http://localhost:4040/api`   |
| API key     | `YOKE_API_KEY`   | `api_key`    | (empty)                       |
| Repo path   | —                | `repo_path`  | (set by `yoke install`)       |

The config file lives at `~/.yoke/config.json` (override with `YOKE_HOME`).
Use `yoke config show` / `yoke config set <key> <value>` to inspect or edit it.

Legacy env vars `RAG_BASE_URL` / `RAG_API_KEY` are still honoured.

## Agent-friendly behaviour

* Every read command supports `--json` for machine-parsable output.
* Exit codes: `0` ok, `2` usage error, `4` backend unreachable, `5` backend 4xx/5xx.
* Destructive commands take `--yes` to skip confirmation prompts.
* `yoke doctor` is the canonical onboarding check — agents should run it first.

## Reuse with the MCP server

The CLI's HTTP client (`yoke_cli/client.py`) is a vendored copy of the
canonical `backend/yoke_client.py`, which is also imported by
`backend/mcp_server.py`. Both surfaces — MCP tool calls and `yoke` CLI
invocations — exercise the exact same code path.

If you change `backend/yoke_client.py`, run `make sync-cli-client` from
the repo root to regenerate the vendored copy.
