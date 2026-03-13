"""
bot.py — Roblox "Train Robots to Fight" Auto-Collection Rejoin Bot

Specific flow:
1. Launch Roblox and join the game
2. Wait for game to load
3. Click the "Online Gifts" button (gift box above Daily Pack)
4. Wait for the TARGET reward (crosshair icon, ~15 min) → Claim it
5. Wait for the GEAR reward (red gear icon, ~20 min) → Claim it
6. Close Roblox and relaunch for next cycle

Anti-AFK: Presses a key / moves camera every ~5 minutes to prevent
the game's 15-minute inactivity disconnect.

All interaction is image-based (screenshot matching) — no memory
editing or packet injection.

Usage:
    python bot.py              # Run with default config.json
    python bot.py --config my_config.json
    python bot.py --dry-run    # Test mode (no clicks)
"""

import os
import sys
import json
import time
import logging
import argparse
import threading
from datetime import datetime

import pyautogui

from image_matcher import find_on_screen, wait_for_image, wait_for_image_gone
from window_manager import (
    bring_to_front, is_roblox_running, close_roblox,
    launch_roblox, wait_for_roblox_process
)

# ─── Globals ─────────────────────────────────────────────────────────
CONFIG = {}
DRY_RUN = False
logger = logging.getLogger("RobloxBot")

# Anti-AFK thread control
_afk_stop_event = threading.Event()
_afk_thread = None


# ─── Configuration ───────────────────────────────────────────────────

def load_config(path="config.json"):
    """Load and validate configuration from JSON file."""
    global CONFIG
    if not os.path.exists(path):
        print(f"ERROR: Config file not found: {path}")
        sys.exit(1)

    with open(path, "r") as f:
        CONFIG = json.load(f)

    place_id = CONFIG["game"]["place_id"]
    if place_id == "REPLACE_WITH_YOUR_PLACE_ID":
        print("ERROR: Set your game's Place ID in config.json")
        sys.exit(1)

    return CONFIG


def setup_logging():
    """Configure logging to both file and console."""
    log_cfg = CONFIG.get("logging", {})
    log_file = log_cfg.get("log_file", "bot.log")
    log_level = getattr(logging, log_cfg.get("log_level", "INFO"))

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    logger.setLevel(log_level)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    if log_cfg.get("console_output", True):
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        logger.addHandler(ch)


def get_image_path(key):
    """Get the full path to a reference image from config."""
    folder = CONFIG["images"]["folder"]
    filename = CONFIG["images"].get(key, "")
    return os.path.join(folder, filename)


# ─── Safety ──────────────────────────────────────────────────────────

def setup_failsafe():
    """Configure PyAutoGUI failsafe."""
    safety = CONFIG.get("safety", {})
    pyautogui.FAILSAFE = safety.get("failsafe_enabled", True)
    pyautogui.PAUSE = CONFIG["timing"].get("click_delay_seconds", 0.5)


# ─── Anti-AFK System ────────────────────────────────────────────────

def anti_afk_loop():
    """
    Background thread that prevents AFK disconnect.

    The game disconnects after ~15 min of no interaction, so this
    sends a small input (key press or camera nudge) every 5 minutes.
    Runs in a daemon thread and stops when _afk_stop_event is set.
    """
    afk_cfg = CONFIG.get("anti_afk", {})
    interval = afk_cfg.get("interval_seconds", 300)
    action = afk_cfg.get("action", "camera_rotate")
    key = afk_cfg.get("key", "d")
    hold_time = afk_cfg.get("key_hold_seconds", 0.2)

    logger.info(f"Anti-AFK started: {action} every {interval}s")

    while not _afk_stop_event.is_set():
        # Wait for interval, but check stop event frequently
        for _ in range(interval):
            if _afk_stop_event.is_set():
                return
            time.sleep(1)

        if _afk_stop_event.is_set():
            return

        # Only act if Roblox is still running
        if not is_roblox_running(CONFIG["game"]["roblox_exe_name"]):
            continue

        if DRY_RUN:
            logger.info("[DRY RUN] Anti-AFK: would press key")
            continue

        try:
            # Bring Roblox to front
            bring_to_front(CONFIG["window"]["title_contains"])
            time.sleep(0.3)

            if action == "camera_rotate":
                # Small camera rotation — tap a movement key briefly
                pyautogui.keyDown(key)
                time.sleep(hold_time)
                pyautogui.keyUp(key)
                # Tap the opposite key to return roughly to original position
                opposite = {"d": "a", "a": "d", "w": "s", "s": "w"}.get(key, "a")
                time.sleep(0.1)
                pyautogui.keyDown(opposite)
                time.sleep(hold_time)
                pyautogui.keyUp(opposite)
            elif action == "key_press":
                pyautogui.press(key)
            elif action == "mouse_jiggle":
                # Tiny mouse movement and back
                x, y = pyautogui.position()
                pyautogui.moveTo(x + 5, y, duration=0.1)
                pyautogui.moveTo(x, y, duration=0.1)

            logger.debug(f"Anti-AFK: sent {action}")
        except Exception as e:
            logger.warning(f"Anti-AFK error: {e}")


def start_anti_afk():
    """Start the anti-AFK background thread."""
    global _afk_thread
    if not CONFIG.get("anti_afk", {}).get("enabled", True):
        return
    _afk_stop_event.clear()
    _afk_thread = threading.Thread(target=anti_afk_loop, daemon=True)
    _afk_thread.start()


def stop_anti_afk():
    """Stop the anti-AFK background thread."""
    _afk_stop_event.set()
    if _afk_thread and _afk_thread.is_alive():
        _afk_thread.join(timeout=5)
    logger.info("Anti-AFK stopped")


# ─── Core Actions ────────────────────────────────────────────────────

def click_at(x, y, label="target"):
    """Click at screen coordinates with logging."""
    if DRY_RUN:
        logger.info(f"[DRY RUN] Would click {label} at ({x}, {y})")
        return
    logger.debug(f"Clicking {label} at ({x}, {y})")
    pyautogui.click(x, y)


def click_image(image_key, label=None, confidence=None):
    """
    Find an image on screen and click its center.

    Returns:
        True if found and clicked, False if not found.
    """
    if label is None:
        label = image_key

    path = get_image_path(image_key)
    if not os.path.exists(path):
        logger.warning(f"Image file missing: {path} (key: {image_key})")
        return False

    conf = confidence or CONFIG["matching"]["confidence_threshold"]
    grayscale = CONFIG["matching"]["grayscale_matching"]

    result = find_on_screen(path, confidence=conf, grayscale=grayscale)
    if result["found"]:
        logger.info(f"Found {label} at ({result['x']}, {result['y']}) "
                     f"[conf: {result['confidence']}]")
        click_at(result["x"], result["y"], label)
        return True
    return False


def is_image_visible(image_key, confidence=None):
    """Check if an image is currently visible on screen."""
    path = get_image_path(image_key)
    if not os.path.exists(path):
        return False
    conf = confidence or CONFIG["matching"]["confidence_threshold"]
    grayscale = CONFIG["matching"]["grayscale_matching"]
    result = find_on_screen(path, confidence=conf, grayscale=grayscale)
    return result["found"]


# ─── Popup Handling ──────────────────────────────────────────────────

def handle_popups():
    """Check for and dismiss Reconnect / Update popups."""
    if click_image("reconnect_popup", "Reconnect popup"):
        logger.info("Dismissed Reconnect popup")
        time.sleep(2)
        return True
    if click_image("update_popup", "Update popup"):
        logger.info("Dismissed Update popup")
        time.sleep(2)
        return True
    return False


# ─── Game State ──────────────────────────────────────────────────────

def wait_for_game_loaded():
    """
    Wait for the game to finish loading.

    Tries multiple strategies:
    1. Wait for loading screen to disappear (if image provided)
    2. Wait for game_loaded indicator to appear (if image provided)
    3. Fixed wait as fallback
    """
    timing = CONFIG["timing"]
    max_wait = timing["max_loading_wait_seconds"]
    check_interval = timing["loading_check_interval_seconds"]

    logger.info("Waiting for game to load...")

    # Strategy 1: Watch loading screen disappear
    loading_path = get_image_path("loading_screen")
    if os.path.exists(loading_path):
        logger.info("Watching for loading screen to disappear...")
        wait_for_image(loading_path, timeout=30, check_interval=check_interval,
                       confidence=CONFIG["matching"]["confidence_threshold"])
        gone = wait_for_image_gone(loading_path, timeout=max_wait,
                                   check_interval=check_interval,
                                   confidence=CONFIG["matching"]["confidence_threshold"])
        if gone:
            logger.info("Loading screen gone — game loaded")
            time.sleep(5)  # Extra stability wait
            handle_popups()
            return True
        else:
            logger.warning("Loading screen still visible after timeout!")
            return False

    # Strategy 2: Look for game_loaded indicator
    loaded_path = get_image_path("game_loaded")
    if os.path.exists(loaded_path):
        logger.info("Watching for game-loaded indicator...")
        result = wait_for_image(loaded_path, timeout=max_wait,
                                check_interval=check_interval,
                                confidence=CONFIG["matching"]["confidence_threshold"])
        if result["found"]:
            logger.info("Game loaded indicator detected!")
            handle_popups()
            return True
        logger.warning("Game loaded indicator not found within timeout!")
        return False

    # Strategy 3: Fixed wait
    logger.info(f"No loading images configured — waiting {max_wait}s...")
    time.sleep(max_wait)
    handle_popups()
    return True


# ─── Online Gifts Navigation ────────────────────────────────────────

def open_online_gifts():
    """
    Click the "Online Gifts" button to open the reward grid.

    The Online Gifts button is the gift box icon above "Daily Pack"
    on the left side panel.

    Returns:
        True if the panel was opened, False if button not found.
    """
    logger.info("Opening Online Gifts panel...")

    # Try clicking the Online Gifts button
    for attempt in range(3):
        if click_image("online_gifts_button", "Online Gifts button"):
            time.sleep(2)  # Wait for panel animation
            logger.info("Online Gifts panel opened")
            return True
        logger.debug(f"Online Gifts button not found (attempt {attempt+1}/3)")
        time.sleep(2)

    logger.warning("Could not find Online Gifts button!")
    return False


# ─── Reward Collection ───────────────────────────────────────────────

def wait_and_collect_reward(image_key, label, max_wait_minutes):
    """
    Wait for a specific reward's Claim button to appear, then click it.

    While waiting, periodically checks the screen. The anti-AFK thread
    handles keeping the game session alive in the background.

    Args:
        image_key: Config key for the reward's claim button image.
        label: Human-readable name (e.g., "Target Reward").
        max_wait_minutes: Maximum minutes to wait for this reward.

    Returns:
        True if reward was claimed, False on timeout/error.
    """
    check_interval = CONFIG["timing"]["reward_check_interval_seconds"]
    max_wait = (max_wait_minutes + 3) * 60  # Extra 3 min buffer

    logger.info(f"Waiting for {label} (up to {max_wait_minutes} min)...")
    start = time.time()

    while time.time() - start < max_wait:
        # Make sure Roblox is still running
        if not is_roblox_running(CONFIG["game"]["roblox_exe_name"]):
            logger.error("Roblox died while waiting for reward!")
            return False

        # Bring to front
        if CONFIG["window"]["bring_to_front_before_action"]:
            bring_to_front(CONFIG["window"]["title_contains"])

        # Handle popups
        handle_popups()

        # Check for the specific reward's claim button
        if click_image(image_key, f"{label} Claim"):
            elapsed = time.time() - start
            logger.info(f"COLLECTED {label} after {elapsed:.0f}s")
            time.sleep(CONFIG["timing"]["post_collect_wait_seconds"])
            return True

        # Also try the generic green "Claim" button as a fallback,
        # but only if the specific reward image isn't available
        path = get_image_path(image_key)
        if not os.path.exists(path):
            if click_image("claim_button_green", f"{label} (green Claim)"):
                elapsed = time.time() - start
                logger.info(f"COLLECTED {label} via green Claim after {elapsed:.0f}s")
                time.sleep(CONFIG["timing"]["post_collect_wait_seconds"])
                return True

        time.sleep(check_interval)

    logger.warning(f"Timeout waiting for {label}")
    return False


def collect_rewards():
    """
    Collect both rewards in sequence:
    1. Target reward (crosshair, ~15 min)
    2. Gear reward (red gear, ~20 min)

    The Online Gifts panel should already be open before calling this.

    Returns:
        Number of rewards collected (0, 1, or 2).
    """
    timing = CONFIG["timing"]
    delay = timing["between_rewards_delay_seconds"]
    collected = 0

    # ── Reward 1: Target (crosshair) — 15 minutes ───────────────
    if wait_and_collect_reward("target_reward_claim",
                               "Target Reward (crosshair)",
                               timing["target_reward_minutes"]):
        collected += 1
        time.sleep(delay)
    else:
        logger.warning("Missed Target reward — continuing to Gear reward")

    # ── Reward 2: Gear (red gear) — 20 minutes ──────────────────
    # The gear reward timer is longer, but we've already waited ~15 min
    # for the target, so only ~5 more minutes for the gear
    remaining_minutes = timing["gear_reward_minutes"] - timing["target_reward_minutes"] + 3
    if remaining_minutes < 3:
        remaining_minutes = 3

    if wait_and_collect_reward("gear_reward_claim",
                               "Gear Reward (red gear)",
                               remaining_minutes):
        collected += 1
    else:
        logger.warning("Missed Gear reward")

    logger.info(f"Collection complete: {collected}/2 rewards claimed")
    return collected


# ─── Main Cycle ──────────────────────────────────────────────────────

def run_cycle(cycle_num):
    """
    Run one complete collection cycle:
    1. Launch Roblox (if not running)
    2. Wait for game to load
    3. Open Online Gifts panel
    4. Start anti-AFK
    5. Wait for + collect Target reward (~15 min)
    6. Wait for + collect Gear reward (~20 min)
    7. Stop anti-AFK
    8. Close Roblox

    Returns:
        Number of rewards collected (0-2).
    """
    timing = CONFIG["timing"]
    game = CONFIG["game"]

    logger.info(f"{'='*50}")
    logger.info(f"CYCLE {cycle_num} STARTED")
    logger.info(f"{'='*50}")

    # ── Step 1: Launch Roblox ────────────────────────────────────
    if not is_roblox_running(game["roblox_exe_name"]):
        launch_roblox(game["place_id"], game["launch_url_template"])
        logger.info("Roblox launch command sent")

        if not wait_for_roblox_process(game["roblox_exe_name"],
                                       timeout=timing["post_launch_wait_seconds"] * 2):
            logger.error("Roblox did not start!")
            return 0

        logger.info("Roblox process detected")
        time.sleep(timing["post_launch_wait_seconds"])
    else:
        logger.info("Roblox already running")

    # ── Step 2: Wait for game to load ────────────────────────────
    if not wait_for_game_loaded():
        logger.error("Game failed to load")
        close_roblox(game["roblox_exe_name"])
        time.sleep(timing["post_close_wait_seconds"])
        return 0

    logger.info("JOINED — game loaded successfully")

    # ── Step 3: Open the Online Gifts panel ──────────────────────
    time.sleep(3)  # Brief settle time
    if not open_online_gifts():
        logger.warning("Could not open Online Gifts — trying anyway")

    # ── Step 4: Start anti-AFK ───────────────────────────────────
    start_anti_afk()

    # ── Step 5 & 6: Collect rewards ──────────────────────────────
    collected = collect_rewards()

    # ── Step 7: Stop anti-AFK ────────────────────────────────────
    stop_anti_afk()

    # ── Step 8: Close Roblox ─────────────────────────────────────
    logger.info("Closing Roblox for next cycle...")
    close_roblox(game["roblox_exe_name"])
    time.sleep(timing["post_close_wait_seconds"])

    logger.info(f"CYCLE {cycle_num} COMPLETE — collected {collected}/2")
    return collected


# ─── Main Loop ───────────────────────────────────────────────────────

def main():
    """Main entry point — runs the bot in an infinite loop."""
    global DRY_RUN

    parser = argparse.ArgumentParser(
        description="Roblox Train Robots to Fight — Auto-Collection Bot"
    )
    parser.add_argument("--config", default="config.json",
                        help="Path to config file (default: config.json)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Test mode — detect but don't click")
    args = parser.parse_args()

    DRY_RUN = args.dry_run

    load_config(args.config)
    setup_logging()
    setup_failsafe()

    logger.info("=" * 50)
    logger.info("ROBLOX AUTO-COLLECTION BOT STARTED")
    logger.info(f"Game: Train Robots to Fight")
    logger.info(f"Place ID: {CONFIG['game']['place_id']}")
    logger.info(f"Rewards: Target (~{CONFIG['timing']['target_reward_minutes']}m) "
                f"+ Gear (~{CONFIG['timing']['gear_reward_minutes']}m)")
    logger.info(f"Anti-AFK: {'ON' if CONFIG.get('anti_afk', {}).get('enabled') else 'OFF'} "
                f"(every {CONFIG.get('anti_afk', {}).get('interval_seconds', 300)}s)")
    logger.info(f"Dry run: {DRY_RUN}")
    logger.info(f"Failsafe: move mouse to "
                f"{CONFIG['safety']['failsafe_corner']} corner to abort")
    logger.info("=" * 50)

    # Verify critical reference images
    critical_images = ["online_gifts_button"]
    reward_images = ["target_reward_claim", "gear_reward_claim"]
    fallback_images = ["claim_button_green"]

    for key in critical_images + reward_images:
        path = get_image_path(key)
        if not os.path.exists(path):
            logger.warning(f"Missing image: {key} → {path}")

    has_any_reward_img = any(
        os.path.exists(get_image_path(k))
        for k in reward_images + fallback_images
    )
    if not has_any_reward_img:
        logger.warning("No reward claim images found! The bot needs at least "
                       "one of: target_claim.png, gear_claim.png, or claim_green.png")
        logger.warning("See README.md for how to capture these images.")

    # Stats
    total_collected = 0
    total_cycles = 0
    consecutive_failures = 0
    max_failures = CONFIG["safety"]["max_consecutive_failures"]
    start_time = datetime.now()

    try:
        while True:
            total_cycles += 1
            collected = run_cycle(total_cycles)

            if collected > 0:
                total_collected += collected
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    logger.error(
                        f"STOPPING: {consecutive_failures} consecutive failures")
                    break
                pause = CONFIG["safety"]["pause_on_failure_seconds"]
                logger.warning(
                    f"Cycle failed ({consecutive_failures}/{max_failures}). "
                    f"Pausing {pause}s...")
                time.sleep(pause)

            elapsed = datetime.now() - start_time
            logger.info(
                f"STATS: {total_collected} rewards in {total_cycles} cycles "
                f"| Running for {elapsed}")

    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
    except pyautogui.FailSafeException:
        logger.info("Bot stopped by failsafe (mouse moved to corner)")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        stop_anti_afk()
        elapsed = datetime.now() - start_time
        logger.info("=" * 50)
        logger.info("BOT SESSION SUMMARY")
        logger.info(f"Total cycles: {total_cycles}")
        logger.info(f"Total rewards collected: {total_collected}")
        logger.info(f"Runtime: {elapsed}")
        logger.info("=" * 50)


if __name__ == "__main__":
    main()
