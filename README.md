# Roblox Auto-Collection Rejoin Bot

Automated bot for **Train Robots to Fight** that collects Online Reward gifts, then closes and relaunches the game to repeat the cycle. Uses **image-based screen matching** — no memory editing or packet injection.

## What It Does

Each cycle:
1. **Launches** Roblox and joins the game
2. **Clicks** the "Online Gifts" button to open the reward grid
3. **Waits** for the **Target reward** (crosshair, ~15 min) → Claims it
4. **Waits** for the **Gear reward** (red gear, ~20 min) → Claims it
5. **Closes** Roblox and **relaunches** for the next cycle
6. **Anti-AFK**: sends small inputs every 5 min to prevent the 15-min idle disconnect

## Requirements

- **Windows 10/11**
- **Python 3.8+** ([download](https://www.python.org/downloads/))
- **Roblox** installed
- **Screen resolution**: 2560x1440 (or adjust screenshots accordingly)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Your Place ID

Open `config.json` and set:
```json
"place_id": "YOUR_PLACE_ID"
```

Find it in the game URL: `roblox.com/games/PLACE_ID/Train-Robots-to-Fight`

### 3. Capture Reference Screenshots

The bot needs screenshots of game UI elements to know what to click.

```bash
python capture_tool.py
```

Or capture them manually (screenshot → crop → save as PNG to `images/`):

**Required images:**

| File | What to capture |
|------|----------------|
| `images/online_gifts_button.png` | The gift box button above "Daily Pack" (opens the reward grid) |
| `images/target_claim.png` | The crosshair/target reward tile when it shows "Claim" |
| `images/gear_claim.png` | The red gear reward tile when it shows "Claim" |

**Recommended:**

| File | What to capture |
|------|----------------|
| `images/claim_green.png` | Just the green "Claim" button text (fallback) |
| `images/game_loaded.png` | Any HUD element visible when game is fully loaded |
| `images/loading_screen.png` | The Roblox loading spinner/bar |

**Optional (popup handling):**

| File | What to capture |
|------|----------------|
| `images/reconnect.png` | "Reconnect" button on disconnect popup |
| `images/update.png` | "OK/Update" button on update popup |

**Tips:**
- Crop tightly — just the button/tile, no extra background
- PNG format only (lossless)
- For reward Claim images: wait until the timer finishes so the green "Claim" button is visible, then screenshot

### 4. Test First

```bash
python bot.py --dry-run
```

Runs in test mode — detects elements but doesn't click. Check console output to verify detection works.

### 5. Run the Bot

```bash
python bot.py
```

Runs continuously. Each cycle takes ~20-25 minutes.

**To stop:**
- `Ctrl+C` — clean shutdown
- Move mouse to **top-left corner** — failsafe instant stop

## Configuration

All settings are in `config.json`:

### Timing
| Setting | Description | Default |
|---------|-------------|---------|
| `target_reward_minutes` | Expected time for target reward | `15` |
| `gear_reward_minutes` | Expected time for gear reward | `20` |
| `reward_check_interval_seconds` | How often to check for Claim | `5` |
| `max_loading_wait_seconds` | Max time to wait for game load | `120` |

### Anti-AFK
| Setting | Description | Default |
|---------|-------------|---------|
| `enabled` | Turn anti-AFK on/off | `true` |
| `interval_seconds` | Seconds between keep-alive inputs | `300` (5 min) |
| `action` | Type: `camera_rotate`, `key_press`, `mouse_jiggle` | `camera_rotate` |
| `key` | Which key to press | `d` |

### Image Matching
| Setting | Description | Default |
|---------|-------------|---------|
| `confidence_threshold` | Min match confidence (0.0–1.0) | `0.8` |
| `grayscale_matching` | Faster but less precise | `false` |

### Safety
| Setting | Description | Default |
|---------|-------------|---------|
| `failsafe_enabled` | Mouse-to-corner abort | `true` |
| `max_consecutive_failures` | Failed cycles before stopping | `5` |

## Updating Images

When the game UI changes:
1. Take new screenshots of the changed elements
2. Crop tightly, save as PNG to `images/`
3. Test with `--dry-run`

Or re-run `python capture_tool.py`.

## Log Output

Logs to console and `bot.log`:

```
[2026-03-13 02:15:30] INFO: CYCLE 1 STARTED
[2026-03-13 02:15:31] INFO: Roblox launch command sent
[2026-03-13 02:15:45] INFO: JOINED — game loaded successfully
[2026-03-13 02:15:48] INFO: Online Gifts panel opened
[2026-03-13 02:15:48] INFO: Anti-AFK started: camera_rotate every 300s
[2026-03-13 02:30:50] INFO: COLLECTED Target Reward (crosshair) after 903s
[2026-03-13 02:35:55] INFO: COLLECTED Gear Reward (red gear) after 1207s
[2026-03-13 02:35:57] INFO: Closing Roblox for next cycle...
[2026-03-13 02:36:02] INFO: CYCLE 1 COMPLETE — collected 2/2
[2026-03-13 02:36:02] INFO: STATS: 2 rewards in 1 cycles | Running for 0:20:32
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Bot can't find buttons | Lower `confidence_threshold` to 0.7, recapture cleaner screenshots |
| Bot clicks wrong things | Raise `confidence_threshold` to 0.85, use more specific crops |
| AFK disconnect still happens | Lower `anti_afk.interval_seconds` to 180 (3 min) |
| Game loads slowly | Increase `max_loading_wait_seconds` to 180 |
| Roblox won't launch | Make sure you're logged into Roblox in the browser |

## File Structure

```
roblox-bot/
├── bot.py              # Main bot (cycle loop + reward collection)
├── image_matcher.py    # OpenCV template matching engine
├── window_manager.py   # Roblox window focus/close/launch
├── capture_tool.py     # Screenshot capture helper
├── config.json         # All settings
├── requirements.txt    # Python dependencies
├── bot.log             # Runtime log (auto-created)
├── images/             # Your reference screenshots go here
│   ├── online_gifts_button.png
│   ├── target_claim.png
│   ├── gear_claim.png
│   ├── claim_green.png
│   └── ...
└── README.md
```
