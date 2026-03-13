"""
capture_tool.py — Helper tool for capturing reference screenshots.

Run this BEFORE using the bot to capture screenshots of the game UI
elements that the bot needs to recognize. Each capture is saved to
the images/ folder with the correct filename.

Usage:
    python capture_tool.py

The tool walks you through capturing each required image:
1. Shows what to capture
2. Lets you select a region on screen
3. Saves the cropped image

You can also capture images manually — just take a screenshot, crop
the UI element tightly, and save it to images/ with the right name.
"""

import os
import sys
import json
import time

try:
    import pyautogui
    from PIL import Image
except ImportError:
    print("Missing dependencies. Run: pip install pyautogui Pillow")
    sys.exit(1)


def load_config(path="config.json"):
    """Load config to get image filenames."""
    with open(path, "r") as f:
        return json.load(f)


def ensure_images_dir(config):
    """Create images directory if it doesn't exist."""
    folder = config["images"]["folder"]
    os.makedirs(folder, exist_ok=True)
    return folder


def capture_region_interactive(save_path, description):
    """
    Guide user through capturing a screen region.

    Steps:
    1. User positions the UI element on screen
    2. User provides coordinates (or we use a simple click method)
    3. Region is captured and saved
    """
    print(f"\n{'='*60}")
    print(f"CAPTURE: {description}")
    print(f"{'='*60}")
    print(f"Save to: {save_path}")
    print()

    if os.path.exists(save_path):
        resp = input(f"  File already exists. Overwrite? (y/N): ").strip().lower()
        if resp != 'y':
            print("  Skipped.")
            return False

    print("  OPTIONS:")
    print("  1) Full-screen screenshot (you'll crop manually)")
    print("  2) Enter pixel coordinates (x, y, width, height)")
    print("  3) Click two corners (top-left, bottom-right)")
    print("  s) Skip this image")
    print()

    choice = input("  Choose (1/2/3/s): ").strip().lower()

    if choice == 's':
        print("  Skipped.")
        return False

    if choice == '1':
        input("  Press Enter to take full screenshot...")
        screenshot = pyautogui.screenshot()
        screenshot.save(save_path)
        print(f"  Saved full screenshot to {save_path}")
        print(f"  IMPORTANT: Open this file and crop to JUST the UI element!")
        return True

    if choice == '2':
        try:
            x = int(input("  X (left edge): "))
            y = int(input("  Y (top edge): "))
            w = int(input("  Width: "))
            h = int(input("  Height: "))
        except ValueError:
            print("  Invalid input. Skipped.")
            return False
        region = pyautogui.screenshot(region=(x, y, w, h))
        region.save(save_path)
        print(f"  Saved {w}x{h} region to {save_path}")
        return True

    if choice == '3':
        print("  Move your mouse to the TOP-LEFT corner of the element...")
        print("  You have 5 seconds...")
        time.sleep(5)
        x1, y1 = pyautogui.position()
        print(f"  Got top-left: ({x1}, {y1})")

        print("  Now move to the BOTTOM-RIGHT corner...")
        print("  You have 5 seconds...")
        time.sleep(5)
        x2, y2 = pyautogui.position()
        print(f"  Got bottom-right: ({x2}, {y2})")

        w = abs(x2 - x1)
        h = abs(y2 - y1)
        x = min(x1, x2)
        y = min(y1, y2)

        if w < 5 or h < 5:
            print("  Region too small. Skipped.")
            return False

        region = pyautogui.screenshot(region=(x, y, w, h))
        region.save(save_path)
        print(f"  Saved {w}x{h} region to {save_path}")
        return True

    print("  Invalid choice. Skipped.")
    return False


def main():
    config = load_config()
    folder = ensure_images_dir(config)

    # Define all images to capture with descriptions
    captures = [
        ("reward_button_1", "Reward Button 1",
         "The FIRST reward/power button when it appears on screen.\n"
         "  Crop tightly around just the button."),
        ("reward_button_2", "Reward Button 2",
         "The SECOND reward button (if it looks different from #1).\n"
         "  If all 3 look the same, you can copy reward_1.png."),
        ("reward_button_3", "Reward Button 3",
         "The THIRD reward button (if it looks different).\n"
         "  If all 3 look the same, you can copy reward_1.png."),
        ("game_loaded", "Game Loaded Indicator",
         "Something that's ALWAYS visible when the game is fully loaded.\n"
         "  Could be a HUD element, health bar, or UI button.\n"
         "  Should NOT appear on loading screens."),
        ("loading_screen", "Loading Screen",
         "The Roblox loading screen (the spinner or progress bar).\n"
         "  Capture a distinctive part of the loading UI."),
        ("reconnect_popup", "Reconnect Popup (optional)",
         "The 'Reconnect' button that appears when disconnected.\n"
         "  Skip if you haven't seen this popup."),
        ("update_popup", "Update Popup (optional)",
         "The 'Update' or 'OK' button on update notifications.\n"
         "  Skip if you haven't seen this popup."),
        ("play_button", "Play/Join Button (optional)",
         "If there's a server selection screen with a Play button.\n"
         "  Skip if the game auto-joins."),
        ("server_select", "Server Selection (optional)",
         "Any server list or selection screen element.\n"
         "  Skip if the game auto-joins a server."),
    ]

    print("\n" + "=" * 60)
    print("  ROBLOX BOT — Reference Image Capture Tool")
    print("=" * 60)
    print()
    print("This tool helps you capture screenshots of game UI elements")
    print("that the bot needs to recognize. You'll capture each element")
    print("one at a time.")
    print()
    print("TIPS:")
    print("• Open the Roblox game first so the UI elements are visible")
    print("• Crop images TIGHTLY — don't include extra background")
    print("• The 3 reward buttons are REQUIRED; others are optional")
    print()
    input("Press Enter to begin...")

    captured = 0
    skipped = 0

    for key, name, desc in captures:
        filename = config["images"][key]
        path = os.path.join(folder, filename)

        if capture_region_interactive(path, f"{name}\n  {desc}"):
            captured += 1
        else:
            skipped += 1

    print(f"\n{'='*60}")
    print(f"  DONE: {captured} captured, {skipped} skipped")
    print(f"  Images saved to: {folder}/")
    print(f"{'='*60}")
    print()
    print("Next steps:")
    print("1. Verify each image looks correct (tight crop, clear)")
    print("2. Update config.json with your game's Place ID")
    print("3. Run: python bot.py --dry-run   (test without clicking)")
    print("4. Run: python bot.py             (start the bot)")


if __name__ == "__main__":
    main()
