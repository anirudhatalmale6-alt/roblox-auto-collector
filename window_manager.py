"""
window_manager.py — Roblox window management utilities.

Handles finding, focusing, closing, and launching the Roblox window.
Uses win32gui on Windows for reliable window management.
"""

import os
import time
import subprocess
import logging

logger = logging.getLogger("RobloxBot")


def _is_windows():
    return os.name == "nt"


def find_roblox_window(title_contains="Roblox"):
    """
    Find the Roblox window by title.

    Args:
        title_contains: Substring to search for in window titles.

    Returns:
        Window handle (int) on Windows, or None if not found.
    """
    if not _is_windows():
        logger.warning("Window management only supported on Windows.")
        return None

    import win32gui

    result = []

    def enum_callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title_contains.lower() in title.lower():
                result.append(hwnd)

    win32gui.EnumWindows(enum_callback, None)
    return result[0] if result else None


def bring_to_front(title_contains="Roblox"):
    """
    Bring the Roblox window to the foreground.

    Returns:
        True if window was found and focused, False otherwise.
    """
    if not _is_windows():
        return False

    import win32gui
    import win32con

    hwnd = find_roblox_window(title_contains)
    if hwnd is None:
        return False

    try:
        # Restore if minimized
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        return True
    except Exception as e:
        logger.warning(f"Could not bring window to front: {e}")
        return False


def is_roblox_running(exe_name="RobloxPlayerBeta.exe"):
    """
    Check if Roblox process is currently running.

    Args:
        exe_name: Name of the Roblox executable.

    Returns:
        True if Roblox is running, False otherwise.
    """
    if not _is_windows():
        return False

    try:
        output = subprocess.check_output(
            ["tasklist", "/FI", f"IMAGENAME eq {exe_name}"],
            text=True, creationflags=subprocess.CREATE_NO_WINDOW
        )
        return exe_name.lower() in output.lower()
    except Exception:
        return False


def close_roblox(exe_name="RobloxPlayerBeta.exe"):
    """
    Force-close all Roblox processes.

    Args:
        exe_name: Name of the Roblox executable to kill.

    Returns:
        True if the kill command was issued, False on error.
    """
    if not _is_windows():
        return False

    logger.info(f"Closing Roblox ({exe_name})...")
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", exe_name],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        # Also kill the launcher if running
        subprocess.run(
            ["taskkill", "/F", "/IM", "RobloxPlayerLauncher.exe"],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        time.sleep(1)
        return True
    except Exception as e:
        logger.error(f"Error closing Roblox: {e}")
        return False


def launch_roblox(place_id, url_template="roblox://placeId={place_id}"):
    """
    Launch Roblox game via the roblox:// protocol URL.

    This opens the game through the Roblox launcher, which handles
    authentication and joining the server.

    Args:
        place_id: The Roblox Place ID to join.
        url_template: URL template with {place_id} placeholder.

    Returns:
        True if the launch command was issued successfully.
    """
    if not _is_windows():
        logger.error("Roblox launch only supported on Windows.")
        return False

    url = url_template.replace("{place_id}", str(place_id))
    logger.info(f"Launching Roblox: {url}")

    try:
        os.startfile(url)
        return True
    except Exception as e:
        logger.error(f"Error launching Roblox: {e}")
        return False


def wait_for_roblox_process(exe_name="RobloxPlayerBeta.exe", timeout=60):
    """
    Wait for the Roblox process to appear.

    Args:
        exe_name: Name of the Roblox executable.
        timeout: Maximum seconds to wait.

    Returns:
        True if Roblox started within timeout, False otherwise.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_roblox_running(exe_name):
            return True
        time.sleep(2)
    return False
