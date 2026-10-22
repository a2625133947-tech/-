# Point-in-Time Snapshot Collector Scheduling Guide

This guide describes how to configure automated, recurrent snapshot collection for the prospective point-in-time catalog using `cron` (Linux / macOS) or `launchd` (macOS).

**Important Safety Rules**:
- The project does **not** install or modify system services automatically.
- Automated collection runs standalone: it captures, validates, deduplicates, and evaluates shadow results. It does **not** trigger production trades or alter graph state.

---

## 1. Manual / Interactive Command

To execute snapshot capture manually for active coverage tickers:

```bash
poetry run collect-shadow-snapshots \
  --tickers 600519 000858 000333 300750 601398 600036 601127 600418 000063 688256 000651 002460 002594 300014 300207 300274 600111 000001 600438 688347 \
  --output-dir docs/baselines/shadow/live/snapshots \
  --catalog docs/baselines/shadow/live/temporal_catalog.json \
  --mode current
```

---

## 2. Option A: Cron Configuration (Linux / macOS)

A-share markets close at 15:00 CST (UTC+8). Post-market processing, settlement, and vendor updates typically stabilize by 17:30 CST.

Run `crontab -e` and add the following entry (adjust paths to your environment):

```cron
# Run Monday through Friday at 17:30 CST (UTC+8)
30 17 * * 1-5 cd /Users/niuyufei/ai-hedge-fund-2025 && /Users/niuyufei/.local/bin/poetry run collect-shadow-snapshots --tickers 600519 000858 000333 300750 601398 600036 601127 600418 000063 688256 000651 002460 002594 300014 300207 300274 600111 000001 600438 688347 >> /Users/niuyufei/ai-hedge-fund-2025/logs/snapshot_cron.log 2>&1
```

---

## 3. Option B: macOS Launchd Configuration

Create a plist definition file at `~/Library/LaunchAgents/com.ai-hedge-fund.snapshot-collector.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ai-hedge-fund.snapshot-collector</string>

    <key>WorkingDirectory</key>
    <string>/Users/niuyufei/ai-hedge-fund-2025</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/niuyufei/.local/bin/poetry</string>
        <string>run</string>
        <string>collect-shadow-snapshots</string>
        <string>--tickers</string>
        <string>600519</string>
        <string>000858</string>
        <string>000333</string>
        <string>300750</string>
        <string>601398</string>
        <string>600036</string>
        <string>601127</string>
        <string>600418</string>
        <string>000063</string>
        <string>688256</string>
        <string>000651</string>
        <string>002460</string>
        <string>002594</string>
        <string>300014</string>
        <string>300207</string>
        <string>300274</string>
        <string>600111</string>
        <string>000001</string>
        <string>600438</string>
        <string>688347</string>
        <string>--output-dir</string>
        <string>docs/baselines/shadow/live/snapshots</string>
        <string>--catalog</string>
        <string>docs/baselines/shadow/live/temporal_catalog.json</string>
        <string>--mode</string>
        <string>current</string>
    </array>

    <key>StartCalendarInterval</key>
    <array>
        <!-- Monday through Friday at 17:30 local time -->
        <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>17</integer><key>Minute</key><integer>30</integer></dict>
        <dict><key>Weekday</key><integer>2</integer><key>Hour</key><integer>17</integer><key>Minute</key><integer>30</integer></dict>
        <dict><key>Weekday</key><integer>3</integer><key>Hour</key><integer>17</integer><key>Minute</key><integer>30</integer></dict>
        <dict><key>Weekday</key><integer>4</integer><key>Hour</key><integer>17</integer><key>Minute</key><integer>30</integer></dict>
        <dict><key>Weekday</key><integer>5</integer><key>Hour</key><integer>17</integer><key>Minute</key><integer>30</integer></dict>
    </array>

    <key>StandardOutPath</key>
    <string>/Users/niuyufei/ai-hedge-fund-2025/logs/snapshot_launchd.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/niuyufei/ai-hedge-fund-2025/logs/snapshot_launchd.stderr.log</string>
</dict>
</plist>
```

### Loading and Managing the Service:

```bash
# Load the agent
launchctl load ~/Library/LaunchAgents/com.ai-hedge-fund.snapshot-collector.plist

# Manually trigger a test run immediately
launchctl start com.ai-hedge-fund.snapshot-collector

# Unload the agent
launchctl unload ~/Library/LaunchAgents/com.ai-hedge-fund.snapshot-collector.plist
```

---

## 4. Deduplication and Retention Behavior

- **Weekend / Holiday Invariance**: If no new trading day or announcement occurred, `compute_content_hash` matches previous capture. The collector logs `DUPLICATE` and avoids creating redundant `.snapshot.json` files.
- **Milestone Protection**: When new financial statements appear or corporate actions occur, `SnapshotRetentionPolicy` classifies the event (`EARNINGS_RELEASE`, `CORPORATE_ACTION_DIVIDEND`, etc.) and ensures persistent retention.
