"""
bot.py — Roblox Auto-Collection Rejoin Bot

Main bot loop that:
1. Launches Roblox and joins the specified game
2. Waits for rewards to appear
3. Collects all 3 rewards in sequence
4. Closes Roblox and relaunches for the next cycle

All interaction is image-based (screenshot matching) — no memory
editing or packet injection. Uses PyAutoGUI for mouse/keyboard input
and OpenCV for template matching.

Usage:
    python bot.py              # Run with default config.json
    python bot.py --config my_config.json  # Custom config
    python bot.py --dry-run    # Test mode (no clicks)
"""

import os
import sys
import json
import time
import logging
import argparse
from datetime import datetime, timedelta

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


# ─── Configuration ───────────────────────────────────────────────────

def load_config(path="config.json"):
    """Load and validate configuration from JSON file."""
    global CONFIG
    if not os.path.exists(path):
        print(f"ERROR: Config file not found: {path}")
        print("Copy config.json.example to config.json and fill in your settings.")
        sys.exit(1)

    with open(path, "r") as f:
        CONFIG = json.load(f)

    # Validate required fields
    place_id = CONFIG["game"]["place_id"]
    if place_id == "REPLACE_WITH_YOUR_PLACE_ID":
        print("ERROR: You must set your game's Place ID in config.json")
        print("Find it in the game's Roblox URL: roblox.com/games/PLACE_ID/...")
        sys.exit(1)

    return CONFIG


def setup_logging():
    """Configure logging to both file and console."""
    log_cfg = CONFIG.get("logging", {})
    log_file = log_cfg.get("log_file", "bot.log")
    log_level = getattr(logging, log_cfg.get("log_level", "INFO"))

    # Create formatter with timestamps
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    logger.setLevel(log_level)

    # File handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Console handler
    if log_cfg.get("console_output", True):
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        logger.addHandler(ch)


def get_image_path(key):
    """
    Get the full path to a reference image from config.

    Args:
        key: The image key from config (e.g., 'reward_button_1').

    Returns:
        Full path to the image file.
    """
    folder = CONFIG["images"]["folder"]
    filename = CONFIG["images"].get(key, "")
    return os.path.join(folder, filename)


# ─── Safety ──────────────────────────────────────────────────────────

def setup_failsafe():
    """Configure PyAutoGUI failsafe (move mouse to corner to abort)."""
    safety = CONFIG.get("safety", {})
    pyautogui.FAILSAFE = safety.get("failsafe_enabled", True)
    pyautogui.PAUSE = CONFIG["timing"].get("click_delay_seconds", 0.5)


# ─── Core Actions ────────────────────────────────────────────────────

def click_at(x, y, label="target"):
    """
    Click at screen coordinates with logging.

    In dry-run mode, logs the action without clicking.
    """
    if DRY_RUN:
        logger.info(f"[DRY RUN] Would click {label} at ({x}, {y})")
        return
    logger.debug(f"Clicking {label} at ({x}, {y})")
    pyautogui.click(x, y)


def click_image(image_key, label=None, confidence=None):
    """
    Find an image on screen and click its center.

    Args:
        image_key: Config key for the image (e.g., 'reward_button_1').
        label: Human-readable label for logging.
        confidence: Override matching confidence threshold.

    Returns:
        True if found and clicked, False if not found.
    """
    if label is None:
        label = image_key

    path = get_image_path(image_key)
    if not os.path.exists(path):
        logger.warning(f"Image file not found: {path} (key: {image_key})")
        return False

    conf = confidence or CONFIG["matching"]["confidence_threshold"]
    grayscale = CONFIG["matching"]["grayscale_matching"]

    result = find_on_screen(path, confidence=conf, grayscale=grayscale)
    if result["found"]:
        logger.info(f"Found {label} at ({result['x']}, {result['y']}) "
                     f"[confidence: {result['confidence']}]")
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
    """
    Check for and dismiss any popups (Reconnect, Update, etc.).

    Returns:
        True if a popup was found and handled, False otherwise.
    """
    # Check for Reconnect popup
    if click_image("reconnect_popup", "Reconnect popup"):
        logger.info("Dismissed Reconnect popup")
        time.sleep(2)
        return True

    # Check for Update popup
    if click_image("update_popup", "Update popup"):
        logger.info("Dismissed Update popup")
        time.sleep(2)
        return True

    return False


# ─── Game State Detection ────────────────────────────────────────────

def wait_for_game_loaded():
    """
    Wait for the game to finish loading.

    Strategy:
    1. If a loading screen image is configured, wait for it to disappear.
    2. If a game_loaded image is configured, wait for it to appear.
    3. Otherwise, wait a fixed time from config.

    Returns:
        True if game loaded successfully, False on timeout.
    """
    timing = CONFIG["timing"]
    max_wait = timing["max_loading_wait_seconds"]
    check_interval = timing["loading_check_interval_seconds"]

    logger.info("Waiting for game to load...")

    # Method 1: Wait for loading screen to disappear
    loading_path = get_image_path("loading_screen")
    if os.path.exists(loading_path):
        logger.info("Watching for loading screen to disappear...")
        # First, wait for loading screen to appear (confirms we're loading)
        wait_for_image(loading_path, timeout=30,
                       check_interval=check_interval,
                       confidence=CONFIG["matching"]["confidence_threshold"])
        # Then wait for it to go away
        gone = wait_for_image_gone(loading_path, timeout=max_wait,
                                   check_interval=check_interval,
                                   confidence=CONFIG["matching"]["confidence_threshold"])
        if gone:
            logger.info("Loading screen gone — game should be loaded.")
            time.sleep(3)  # Brief extra wait for stability

            # Handle any post-load popups
            handle_popups()
            return True
        else:
            logger.warning("Loading screen still visible after timeout!")
            return False

    # Method 2: Wait for game_loaded indicator
    loaded_path = get_image_path("game_loaded")
    if os.path.exists(loaded_path):
        logger.info("Watching for game-loaded indicator...")
        result = wait_for_image(loaded_path, timeout=max_wait,
                                check_interval=check_interval,
                                confidence=CONFIG["matching"]["confidence_threshold"])
        if result["found"]:
            logger.info("Game loaded indicator found!")
            handle_popups()
            return True
        else:
            logger.warning("Game loaded indicator not found within timeout!")
            return False

    # Method 3: Fixed wait
    logger.info(f"No loading images configured — waiting {max_wait}s...")
    time.sleep(max_wait)
    handle_popups()
    return True


# ─── Reward Collection ───────────────────────────────────────────────

def check_rewards_available():
    """
    Check if any reward buttons are currently visible.

    Returns:
        List of reward keys that are visible (e.g., ['reward_button_1']).
    """
    available = []
    for key in ["reward_button_1", "reward_button_2", "reward_button_3"]:
        if is_image_visible(key):
            available.append(key)
    return available


def collect_rewards():
    """
    Attempt to collect all 3 rewards in sequence.

    Clicks each reward button with a short delay between them.

    Returns:
        Number of rewards successfully collected (0-3).
    """
    delay = CONFIG["timing"]["between_rewards_delay_seconds"]
    post_wait = CONFIG["timing"]["post_collect_wait_seconds"]
    collected = 0

    for i, key in enumerate(["reward_button_1", "reward_button_2",
                              "reward_button_3"], 1):
        label = f"Reward {i}/3"

        if click_image(key, label):
            collected += 1
            logger.info(f"Collected {label}")
            time.sleep(delay)
        else:
            # Reward button not found — might need to wait or scroll
            logger.warning(f"{label} not found on screen")
            time.sleep(1)

            # Retry once after a short pause
            if click_image(key, f"{label} (retry)"):
                collected += 1
                logger.info(f"Collected {label} on retry")
                time.sleep(delay)
            else:
                logger.warning(f"Could not find {label} — skipping")

    if collected > 0:
        logger.info(f"Collection complete: {collected}/3 rewards claimed")
        time.sleep(post_wait)

    return collected


def wait_for_rewards():
    """
    Wait for rewards to become available.

    Periodically checks the screen for reward button images.
    Also handles popups that might appear during the wait.

    Returns:
        True when rewards are detected, False on fatal error.
    """
    timing = CONFIG["timing"]
    check_interval = timing["reward_check_interval_seconds"]
    cycle_minutes = timing["reward_cycle_minutes"]

    logger.info(f"Waiting for rewards (cycle: ~{cycle_minutes} min)...")

    # We'll check periodically, but also handle popups
    start_time = time.time()
    max_wait = (cycle_minutes + 5) * 60  # Extra 5 min buffer

    while time.time() - start_time < max_wait:
        # Ensure Roblox is still running
        exe_name = CONFIG["game"]["roblox_exe_name"]
        if not is_roblox_running(exe_name):
            logger.error("Roblox process died while waiting for rewards!")
            return False

        # Bring window to front periodically
        if CONFIG["window"]["bring_to_front_before_action"]:
            bring_to_front(CONFIG["window"]["title_contains"])

        # Handle any popups
        handle_popups()

        # Check for rewards
        available = check_rewards_available()
        if available:
            elapsed = time.time() - start_time
            logger.info(f"Rewards detected after {elapsed:.0f}s: "
                        f"{len(available)} visible")
            return True

        time.sleep(check_interval)

    logger.warning(f"No rewards detected after {max_wait/60:.0f} minutes")
    return False


# ─── Main Cycle ──────────────────────────────────────────────────────

def run_cycle(cycle_num):
    """
    Run one complete collection cycle:
    1. Launch Roblox (if not running)
    2. Wait for game to load
    3. Wait for rewards
    4. Collect rewards
    5. Close Roblox

    Args:
        cycle_num: Current cycle number for logging.

    Returns:
        Number of rewards collected in this cycle.
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

        # Wait for process to start
        if not wait_for_roblox_process(game["roblox_exe_name"],
                                       timeout=timing["post_launch_wait_seconds"] * 2):
            logger.error("Roblox did not start!")
            return 0

        logger.info("Roblox process detected — waiting for game to load")
        time.sleep(timing["post_launch_wait_seconds"])
    else:
        logger.info("Roblox already running")

    # ── Step 2: Wait for game to load ────────────────────────────
    if not wait_for_game_loaded():
        logger.error("Game failed to load within timeout")
        close_roblox(game["roblox_exe_name"])
        time.sleep(timing["post_close_wait_seconds"])
        return 0

    logger.info("JOINED — game is loaded and ready")

    # ── Step 3: Handle server selection if needed ────────────────
    if click_image("server_select", "Server selection"):
        time.sleep(2)
        if click_image("play_button", "Play button"):
            time.sleep(timing["post_launch_wait_seconds"])
            wait_for_game_loaded()

    # ── Step 4: Wait for rewards ─────────────────────────────────
    if not wait_for_rewards():
        logger.warning("Reward detection failed — restarting cycle")
        close_roblox(game["roblox_exe_name"])
        time.sleep(timing["post_close_wait_seconds"])
        return 0

    # ── Step 5: Collect rewards ──────────────────────────────────
    if CONFIG["window"]["bring_to_front_before_action"]:
        bring_to_front(CONFIG["window"]["title_contains"])

    collected = collect_rewards()

    # ── Step 6: Close Roblox ─────────────────────────────────────
    logger.info("Closing Roblox for next cycle...")
    close_roblox(game["roblox_exe_name"])
    time.sleep(timing["post_close_wait_seconds"])

    logger.info(f"CYCLE {cycle_num} COMPLETE — collected {collected}/3")
    return collected


# ─── Main Loop ───────────────────────────────────────────────────────

def main():
    """Main entry point — runs the bot in an infinite loop."""
    global DRY_RUN

    parser = argparse.ArgumentParser(
        description="Roblox Auto-Collection Rejoin Bot"
    )
    parser.add_argument("--config", default="config.json",
                        help="Path to config file (default: config.json)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Test mode — detect but don't click")
    args = parser.parse_args()

    DRY_RUN = args.dry_run

    # Load config and set up
    load_config(args.config)
    setup_logging()
    setup_failsafe()

    logger.info("=" * 50)
    logger.info("ROBLOX AUTO-COLLECTION BOT STARTED")
    logger.info(f"Game Place ID: {CONFIG['game']['place_id']}")
    logger.info(f"Dry run: {DRY_RUN}")
    logger.info(f"Failsafe: {CONFIG['safety']['failsafe_enabled']} "
                f"(move mouse to {CONFIG['safety']['failsafe_corner']} "
                f"corner to abort)")
    logger.info("=" * 50)

    # Verify reference images exist
    missing = []
    for key in ["reward_button_1", "reward_button_2", "reward_button_3"]:
        path = get_image_path(key)
        if not os.path.exists(path):
            missing.append(f"  - {key}: {path}")
    if missing:
        logger.warning("Missing REQUIRED reference images:")
        for m in missing:
            logger.warning(m)
        logger.warning("The bot needs these screenshots to find rewards!")
        logger.warning("See README.md for how to capture reference images.")

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
                        f"STOPPING: {consecutive_failures} consecutive "
                        f"failures (max: {max_failures})"
                    )
                    break
                pause = CONFIG["safety"]["pause_on_failure_seconds"]
                logger.warning(
                    f"Cycle failed ({consecutive_failures}/{max_failures}). "
                    f"Pausing {pause}s before retry..."
                )
                time.sleep(pause)

            # Print running stats
            elapsed = datetime.now() - start_time
            logger.info(
                f"STATS: {total_collected} rewards in {total_cycles} cycles "
                f"| Running for {elapsed}"
            )

    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
    except pyautogui.FailSafeException:
        logger.info("Bot stopped by failsafe (mouse moved to corner)")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        elapsed = datetime.now() - start_time
        logger.info("=" * 50)
        logger.info("BOT SESSION SUMMARY")
        logger.info(f"Total cycles: {total_cycles}")
        logger.info(f"Total rewards collected: {total_collected}")
        logger.info(f"Runtime: {elapsed}")
        logger.info("=" * 50)


if __name__ == "__main__":
    main()
