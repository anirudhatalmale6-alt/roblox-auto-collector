# Roblox Auto-Collection Rejoin Bot

Automated bot that collects power rewards in a Roblox game, then closes and relaunches the game to repeat the cycle. Uses **image-based screen matching** — no memory editing or packet injection.

## How It Works

1. **Launches** your Roblox game via the `roblox://` protocol
2. **Waits** for the game to fully load (detects loading screen)
3. **Monitors** the screen for reward buttons to appear (~20 min cycle)
4. **Clicks** all 3 reward buttons in sequence
5. **Closes** Roblox and **relaunches** for the next cycle
6. Handles Reconnect/Update popups automatically

## Requirements

- **Windows 10/11** (uses win32 APIs for window management)
- **Python 3.8+** ([download](https://www.python.org/downloads/))
- **Roblox** installed via the Microsoft Store or website

## Quick Start

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Your Game's Place ID

Open `config.json` and replace `REPLACE_WITH_YOUR_PLACE_ID` with your game's Place ID:

```json
"place_id": "123456789"
```

**How to find the Place ID:** Go to the game's page on roblox.com — the URL looks like `roblox.com/games/123456789/Game-Name`. The number is your Place ID.

### 3. Capture Reference Screenshots

The bot needs screenshots of the game's UI elements to know what to look for. Run the capture tool:

```bash
python capture_tool.py
```

This walks you through capturing each image. You need **at minimum**:

| Image | Filename | What to capture |
|-------|----------|----------------|
| Reward 1 | `images/reward_1.png` | The first reward button when it appears |
| Reward 2 | `images/reward_2.png` | The second reward button |
| Reward 3 | `images/reward_3.png` | The third reward button |

**Optional but recommended:**

| Image | Filename | What to capture |
|-------|----------|----------------|
| Game Loaded | `images/game_loaded.png` | A HUD element visible when game is loaded |
| Loading Screen | `images/loading_screen.png` | The Roblox loading spinner/bar |
| Reconnect | `images/reconnect.png` | The "Reconnect" button in disconnect popup |
| Update | `images/update.png` | The "OK/Update" button in update popup |

**Screenshot tips:**
- Crop tightly around just the button/element
- Don't include surrounding background
- Use PNG format (lossless)
- If all 3 reward buttons look identical, just copy `reward_1.png` to `reward_2.png` and `reward_3.png`

### 4. Test with Dry Run

```bash
python bot.py --dry-run
```

This runs the bot in test mode — it detects everything but doesn't click. Check the console output to verify it finds your UI elements correctly.

### 5. Run the Bot

```bash
python bot.py
```

The bot will run continuously until you stop it.

**To stop:** Press `Ctrl+C` or move your mouse to the **top-left corner** of the screen (failsafe).

## Configuration Reference

All settings are in `config.json`:

### `game`
| Key | Description | Default |
|-----|-------------|---------|
| `place_id` | Your Roblox game's Place ID | (required) |
| `roblox_exe_name` | Roblox process name | `RobloxPlayerBeta.exe` |

### `timing`
| Key | Description | Default |
|-----|-------------|---------|
| `reward_cycle_minutes` | Expected time between reward drops | `20` |
| `reward_check_interval_seconds` | How often to check for rewards | `5` |
| `post_collect_wait_seconds` | Wait after collecting rewards | `2` |
| `post_close_wait_seconds` | Wait after closing Roblox | `5` |
| `post_launch_wait_seconds` | Wait after launching Roblox | `15` |
| `max_loading_wait_seconds` | Max time to wait for game to load | `120` |
| `between_rewards_delay_seconds` | Delay between clicking each reward | `1.5` |

### `matching`
| Key | Description | Default |
|-----|-------------|---------|
| `confidence_threshold` | Min match confidence (0.0–1.0) | `0.8` |
| `grayscale_matching` | Use grayscale (faster but less precise) | `false` |
| `multi_scale` | Try multiple image scales | `false` |
| `scales` | Scale factors for multi-scale | `[0.8–1.2]` |

### `safety`
| Key | Description | Default |
|-----|-------------|---------|
| `failsafe_enabled` | Mouse-to-corner abort | `true` |
| `max_consecutive_failures` | Max failed cycles before stopping | `5` |
| `pause_on_failure_seconds` | Wait between retries on failure | `10` |

## Updating Reference Images

When the game's UI changes:

1. Take new screenshots of the changed elements
2. Crop tightly and save as PNG to `images/`
3. Use the same filenames (or update `config.json` → `images` section)
4. Test with `--dry-run` before running

Or re-run `python capture_tool.py` for guided capture.

## Log Output

The bot logs to both console and `bot.log`:

```
[2026-03-13 02:15:30] INFO: CYCLE 1 STARTED
[2026-03-13 02:15:31] INFO: Roblox launch command sent
[2026-03-13 02:15:45] INFO: JOINED — game is loaded and ready
[2026-03-13 02:35:50] INFO: Rewards detected after 1205s: 3 visible
[2026-03-13 02:35:51] INFO: Collected Reward 1/3
[2026-03-13 02:35:53] INFO: Collected Reward 2/3
[2026-03-13 02:35:55] INFO: Collected Reward 3/3
[2026-03-13 02:35:57] INFO: Closing Roblox for next cycle...
[2026-03-13 02:36:02] INFO: CYCLE 1 COMPLETE — collected 3/3
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Bot can't find reward buttons | Lower `confidence_threshold` to 0.7, or recapture cleaner screenshots |
| Bot clicks wrong things | Raise `confidence_threshold` to 0.85–0.9, capture more specific images |
| Game takes too long to load | Increase `max_loading_wait_seconds` |
| Bot stops after a few cycles | Check `max_consecutive_failures` — increase if your game is flaky |
| Roblox won't launch | Make sure you're logged into Roblox in the browser first |
| "FailSafe" triggered | You moved your mouse to the screen corner — this is a safety feature |

## File Structure

```
roblox-bot/
├── bot.py              # Main bot script
├── image_matcher.py    # OpenCV screen matching
├── window_manager.py   # Roblox window control
├── capture_tool.py     # Screenshot capture helper
├── config.json         # All settings (edit this)
├── requirements.txt    # Python dependencies
├── bot.log            # Runtime log (created on first run)
├── images/            # Reference screenshots (you provide these)
│   ├── reward_1.png
│   ├── reward_2.png
│   ├── reward_3.png
│   ├── game_loaded.png
│   ├── loading_screen.png
│   ├── reconnect.png
│   ├── update.png
│   └── ...
└── README.md
```
