"""
image_matcher.py — Screen image matching utilities using OpenCV.

Provides robust template matching to locate UI elements on screen.
Supports confidence thresholds and optional multi-scale matching
for different screen resolutions.
"""

import os
import cv2
import numpy as np
import pyautogui


def screenshot_to_cv2():
    """Capture the current screen and convert to OpenCV BGR format."""
    pil_img = pyautogui.screenshot()
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def load_template(image_path, grayscale=False):
    """
    Load a template image from disk.

    Args:
        image_path: Path to the template image file.
        grayscale: If True, convert to grayscale for faster matching.

    Returns:
        The loaded image as a numpy array, or None if file not found.
    """
    if not os.path.exists(image_path):
        return None
    flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
    return cv2.imread(image_path, flag)


def find_on_screen(template_path, confidence=0.8, grayscale=False,
                   multi_scale=False, scales=None, region=None):
    """
    Search the screen for an image template.

    Args:
        template_path: Path to the template image to find.
        confidence: Minimum match confidence (0.0 to 1.0). Default 0.8.
        grayscale: Use grayscale matching for speed. Default False.
        multi_scale: Try matching at multiple scales. Default False.
        scales: List of scale factors to try. Default [0.8..1.2].
        region: Optional (x, y, w, h) tuple to limit search area.

    Returns:
        A dict with keys: found (bool), x (int), y (int), confidence (float),
        width (int), height (int). x,y is the CENTER of the matched region.
        Returns found=False if not found.
    """
    result = {"found": False, "x": 0, "y": 0, "confidence": 0.0,
              "width": 0, "height": 0}

    template = load_template(template_path, grayscale)
    if template is None:
        return result

    # Capture screen
    screen = screenshot_to_cv2()
    if region:
        rx, ry, rw, rh = region
        screen = screen[ry:ry+rh, rx:rx+rw]

    if grayscale:
        screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)

    if not multi_scale:
        scales_to_try = [1.0]
    else:
        scales_to_try = scales or [0.8, 0.9, 1.0, 1.1, 1.2]

    best_match = None

    for scale in scales_to_try:
        if scale != 1.0:
            w = int(template.shape[1] * scale)
            h = int(template.shape[0] * scale)
            if w < 1 or h < 1:
                continue
            scaled = cv2.resize(template, (w, h), interpolation=cv2.INTER_AREA)
        else:
            scaled = template

        # Make sure template isn't bigger than screen
        if (scaled.shape[0] > screen.shape[0] or
                scaled.shape[1] > screen.shape[1]):
            continue

        match = cv2.matchTemplate(screen, scaled, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(match)

        if max_val >= confidence:
            if best_match is None or max_val > best_match["confidence"]:
                th, tw = scaled.shape[:2]
                cx = max_loc[0] + tw // 2
                cy = max_loc[1] + th // 2
                # Adjust for region offset
                if region:
                    cx += region[0]
                    cy += region[1]
                best_match = {
                    "found": True,
                    "x": cx,
                    "y": cy,
                    "confidence": round(max_val, 4),
                    "width": tw,
                    "height": th
                }

    return best_match if best_match else result


def find_all_on_screen(template_path, confidence=0.8, grayscale=False,
                       max_results=10):
    """
    Find ALL occurrences of a template on screen.

    Useful when multiple identical UI elements appear (e.g., multiple
    reward buttons that look the same).

    Args:
        template_path: Path to the template image.
        confidence: Minimum match confidence.
        grayscale: Use grayscale matching.
        max_results: Maximum number of matches to return.

    Returns:
        List of dicts, each with: x, y, confidence, width, height.
        Sorted by confidence (highest first).
    """
    results = []

    template = load_template(template_path, grayscale)
    if template is None:
        return results

    screen = screenshot_to_cv2()
    if grayscale:
        screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)

    th, tw = template.shape[:2]
    match = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)

    # Find all locations above threshold
    locations = np.where(match >= confidence)
    points = list(zip(*locations[::-1]))  # (x, y) pairs

    if not points:
        return results

    # Non-maximum suppression: remove overlapping matches
    # Group nearby points (within template-size distance)
    used = set()
    for pt in sorted(points, key=lambda p: -match[p[1], p[0]]):
        if len(results) >= max_results:
            break
        # Check if too close to an already-found match
        too_close = False
        for existing in results:
            if (abs(pt[0] + tw//2 - existing["x"]) < tw * 0.5 and
                    abs(pt[1] + th//2 - existing["y"]) < th * 0.5):
                too_close = True
                break
        if not too_close:
            results.append({
                "x": pt[0] + tw // 2,
                "y": pt[1] + th // 2,
                "confidence": round(float(match[pt[1], pt[0]]), 4),
                "width": tw,
                "height": th
            })

    return results


def wait_for_image(template_path, timeout=60, check_interval=1.0,
                   confidence=0.8, grayscale=False):
    """
    Wait until an image appears on screen, or timeout.

    Args:
        template_path: Path to the template image.
        timeout: Maximum seconds to wait. Default 60.
        check_interval: Seconds between checks. Default 1.0.
        confidence: Minimum match confidence.
        grayscale: Use grayscale matching.

    Returns:
        Match result dict (with found=True) if found, or found=False on timeout.
    """
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = find_on_screen(template_path, confidence, grayscale)
        if result["found"]:
            return result
        time.sleep(check_interval)
    return {"found": False, "x": 0, "y": 0, "confidence": 0.0,
            "width": 0, "height": 0}


def wait_for_image_gone(template_path, timeout=60, check_interval=1.0,
                        confidence=0.8, grayscale=False):
    """
    Wait until an image DISAPPEARS from screen, or timeout.

    Useful for waiting for loading screens to finish.

    Args:
        template_path: Path to the template image.
        timeout: Maximum seconds to wait.
        check_interval: Seconds between checks.
        confidence: Minimum match confidence.
        grayscale: Use grayscale matching.

    Returns:
        True if the image disappeared within timeout, False otherwise.
    """
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = find_on_screen(template_path, confidence, grayscale)
        if not result["found"]:
            return True
        time.sleep(check_interval)
    return False
