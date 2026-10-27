# 1. Getting started

## Requirements

- Python **3.11 or 3.12** (3.13 can fail to build `growwapi`'s old `clint`/`args` dependencies)
- Git
- A Groww account with Trade API access (only needed for Groww data and live orders;
  paper trading and backtests also work with free Yahoo Finance data)
- Claude Code (optional, for the skills)

## Install on Windows (PowerShell)

```powershell
cd $HOME\Personal\trading-skills
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements-dev.txt
copy config.example.toml config.toml
copy .env.example .env
python -m growwbot doctor
python -m pytest
```

## Install on macOS / Linux

```bash
cd ~/Personal/trading-skills
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp config.example.toml config.toml && cp .env.example .env
python -m growwbot doctor && python -m pytest
```

## First hour

1. `python -m growwbot regime`: what kind of market is it?
2. `python -m growwbot backtest --all --split 0.7`: which strategies held up on
   your watchlist, including out of sample?
3. `python -m growwbot scan` and `python -m growwbot analyze RELIANCE`.
4. Pick one strategy in `config.toml`, then `python -m growwbot run` during
   market hours to paper trade.
5. `python -m growwbot report` at the end of each week.

## Using it from Claude Code

```bash
python -m growwbot install-skills           # copies skills into .claude/skills for this folder
claude                                       # then just ask, e.g. "scan my watchlist"
```

To use the skills from any folder: `python -m growwbot install-skills --scope global`
and set the `GROWWBOT_HOME` environment variable to this repo's path.

Next: [Groww API setup](02-groww-api-setup.md).
