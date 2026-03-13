"""
capture_tool.py — Helper tool for capturing reference screenshots.

Run this BEFORE using the bot to capture screenshots of the game UI
elements that the bot needs to recognize.

Usage:
    python capture_tool.py

You can also capture images manually — just screenshot, crop tightly,
and save as PNG to the images/ folder with the correct filename.
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
    with open(path, "r") as f:
        return json.load(f)


def ensure_images_dir(config):
    folder = config["images"]["folder"]
    os.makedirs(folder, exist_ok=True)
    return folder


def capture_region_interactive(save_path, description):
    """Guide user through capturing a screen region."""
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
    print("  1) Full-screen screenshot (you crop it later)")
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
        print(f"  IMPORTANT: Open and crop to JUST the UI element!")
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
        print("  Move mouse to TOP-LEFT corner of the element...")
        print("  You have 5 seconds...")
        time.sleep(5)
        x1, y1 = pyautogui.position()
        print(f"  Got top-left: ({x1}, {y1})")

        print("  Now move to BOTTOM-RIGHT corner...")
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

    # Images to capture, in order of importance
    captures = [
        ("online_gifts_button", "Online Gifts Button (REQUIRED)",
         "The gift box button above 'Daily Pack' on the left side panel.\n"
         "  This is what the bot clicks to open the rewards grid.\n"
         "  Crop tightly around just the button."),

        ("target_reward_claim", "Target Reward Claim Button (REQUIRED)",
         "The green crosshair/target reward tile when it shows 'Claim'.\n"
         "  Wait until the 15-min timer finishes and it becomes claimable,\n"
         "  then capture it. Crop the entire tile including the Claim text."),

        ("gear_reward_claim", "Gear Reward Claim Button (REQUIRED)",
         "The red gear reward tile when it shows 'Claim'.\n"
         "  Wait until the 20-min timer finishes, then capture it.\n"
         "  Crop the entire tile including the Claim text."),

        ("claim_button_green", "Green 'Claim' Button (RECOMMENDED)",
         "The green 'Claim' button/text that appears on claimable rewards.\n"
         "  Just the green 'Claim' portion, not the whole tile.\n"
         "  This is a fallback if the specific reward images don't match."),

        ("game_loaded", "Game Loaded Indicator (RECOMMENDED)",
         "Something visible when the game is fully loaded (HUD, health bar, etc.).\n"
         "  Should NOT appear on loading screens."),

        ("loading_screen", "Loading Screen (OPTIONAL)",
         "The Roblox loading spinner or progress bar.\n"
         "  Helps the bot detect when loading is finished."),

        ("reconnect_popup", "Reconnect Popup (OPTIONAL)",
         "The 'Reconnect' button if you've seen a disconnect popup.\n"
         "  Skip if you haven't encountered this."),

        ("update_popup", "Update Popup (OPTIONAL)",
         "The 'OK/Update' button on update notifications.\n"
         "  Skip if you haven't encountered this."),

        ("close_reward_panel", "Close Reward Panel Button (OPTIONAL)",
         "The X or close button on the Online Reward grid.\n"
         "  Skip if not needed."),
    ]

    print("\n" + "=" * 60)
    print("  ROBLOX BOT — Reference Image Capture Tool")
    print("  Game: Train Robots to Fight")
    print("=" * 60)
    print()
    print("This tool captures screenshots of game UI elements.")
    print("The bot uses these to find and click buttons automatically.")
    print()
    print("TIPS:")
    print("• Open the game first so UI elements are visible")
    print("• Crop images TIGHTLY — no extra background")
    print("• Use PNG format (lossless quality)")
    print("• For the reward Claim images, wait until the timer finishes")
    print("  so the Claim button is visible, then capture")
    print()
    input("Press Enter to begin...")

    captured = 0
    skipped = 0

    for key, name, desc in captures:
        filename = config["images"].get(key, f"{key}.png")
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
    print("2. Set your Place ID in config.json")
    print("3. Test: python bot.py --dry-run")
    print("4. Run:  python bot.py")


if __name__ == "__main__":
    main()
