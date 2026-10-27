# 10. Running automatically

The engine (`python -m growwbot run`) trades from 09:15 to 15:30 IST and exits
after the close. Start it every trading day a little before 09:15. The
computer's clock should be on IST (the engine converts to Asia/Kolkata itself,
but scheduling uses local time).

## Windows: Task Scheduler

1. Create `run-bot.bat` in the repo folder:

   ```bat
   @echo off
   cd /d %USERPROFILE%\Desktop\groww-trading-skills
   call .venv\Scripts\activate.bat
   python -m growwbot run >> state\engine.log 2>&1
   ```

   For live trading, change the last line to `python -m growwbot run --live ...`
   only after the [go-live checklist](09-paper-to-live.md).

2. Task Scheduler → Create Task:
   - **General:** "Run whether user is logged on or not".
   - **Triggers:** Weekly, Mon-Fri, 09:05.
   - **Actions:** Start a program → `run-bot.bat`, "Start in" = the repo folder.
   - **Conditions:** untick "Start only if on AC power"; tick "Wake the computer to run this task".
   - **Settings:** "Stop the task if it runs longer than" 8 hours.
3. Power settings: never sleep on AC while the engine runs.

## macOS / Linux: cron

```cron
5 9 * * 1-5 cd ~/Desktop/groww-trading-skills && .venv/bin/python -m growwbot run >> state/engine.log 2>&1
```

macOS: allow cron Full Disk Access, and use `caffeinate -i` to stop sleep.

## A small cloud VM

A Linux VM in Mumbai (AWS ap-south-1, GCP asia-south1, Azure Central India)
gives a stable connection and a static IP you can register with Groww. Keep
`.env` readable only by your user (`chmod 600 .env`).

## Alerts and the daily plan

```cron
50 8 * * 1-5  cd ~/groww-trading-skills && .venv/bin/python -m growwbot plan > /dev/null
*/5 9-15 * * 1-5 cd ~/groww-trading-skills && .venv/bin/python -m growwbot alerts watch --once
```

## Monitoring

- `state/engine.log`: every signal, risk verdict, entry and exit.
- `state/orders.log`: every live API call and response.
- `python -m growwbot positions --live`: bot view vs Groww's view.

If the engine crashes, live positions keep their Groww SL-M stops. Restart it;
it reloads `state/positions_live.json` and reconciles with Groww.
