# serve-git

Temporarily share a local Git repository with a peer over the internet.

`serve-git` starts a read-only Git smart HTTP server for a local worktree or bare
repository, opens an [ngrok](https://ngrok.com/) HTTPS tunnel to it, and prints
ready-to-run `git clone` and `git remote add` commands. `stop-serve-git` tears
everything down.

There is no authentication: anyone who has the URL can clone or fetch while the
tunnel is running.

## Requirements

- Python 3.10+
- `git` with `git-http-backend`
- `ngrok` on `PATH`, already authenticated (`ngrok config check`)

## Install

### With pipx (recommended)

```bash
pipx install serve-git
```

Or install directly from GitHub:

```bash
pipx install git+https://github.com/pablogventura/serve-git.git
```

This installs the `serve-git` and `stop-serve-git` commands globally in an isolated environment.

Upgrade later with:

```bash
pipx upgrade serve-git
```

### Editable install (development)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Without packaging

Add the `bin/` directory to your `PATH`:

```bash
export PATH="/path/to/serve-git/bin:$PATH"
```

## Usage

On your machine:

```bash
serve-git /path/to/local/repo
```

Example output:

```text
Share these commands with your peer:

# Clone into a new directory
git -c http.extraHeader="ngrok-skip-browser-warning:true" clone https://xxxx.ngrok-free.app/my-repo.git

# Or add as a remote on an existing clone
git remote add serve-git https://xxxx.ngrok-free.app/my-repo.git
git -c http.extraHeader="ngrok-skip-browser-warning:true" fetch serve-git

When finished on your machine, run: stop-serve-git
```

The `http.extraHeader` value skips ngrok's free-tier browser warning page so Git
HTTP clients can talk to the tunnel.

When you are done:

```bash
stop-serve-git
```

Only one serve session is supported at a time. Push is disabled (read-only).

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Tests exercise repository resolution, session state, command formatting, ngrok
API parsing (mocked), and a real `git clone` against the local smart HTTP server.
They do not open a live ngrok tunnel.

### Manual ngrok check

```bash
serve-git /path/to/repo
# on another machine or after copying the printed URL:
# git -c http.extraHeader="ngrok-skip-browser-warning:true" clone <url>
stop-serve-git
```

## License

MIT
