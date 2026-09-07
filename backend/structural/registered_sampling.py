"""Experimental image registration using only standard QR function patterns.

No payload or re-encoded data matrix enters the fit. Caller must independently
validate the resulting grid; registration is not a safety verdict.
"""
import cv2
import numpy as np
import qrcode
from scipy.optimize import minimize


def sample_registered_grid(gray, corners, n):
    if not 21 <= n <= 177 or (n - 17) % 4:
        return None
    probe = qrcode.QRCode(version=(n - 17) // 4, border=0)
    probe.modules_count = n
    probe.modules = [[None] * n for _ in range(n)]
    probe.setup_position_probe_pattern(0, 0)
    probe.setup_position_probe_pattern(n - 7, 0)
    probe.setup_position_probe_pattern(0, n - 7)
    probe.setup_position_adjust_pattern()
    probe.setup_timing_pattern()
    fixed = np.array([[v is not None for v in row] for row in probe.modules])
    lo, hi = int(n * .35), int(np.ceil(n * .65))
    fixed[lo:hi, lo:hi] = False
    expected = np.array([[bool(v) for v in row] for row in probe.modules])
    black, white = fixed & expected, fixed & ~expected
    side = n * 12
    # Keep real quiet-zone pixels around the warp; otherwise a shifted edge
    # sample silently reads OpenCV's artificial black out-of-bounds border.
    target = np.float32([[12, 12], [side + 12, 12], [side + 12, side + 12], [12, side + 12]])
    warped = cv2.warpPerspective(gray, cv2.getPerspectiveTransform(
        np.asarray(corners, dtype=np.float32).reshape(4, 2), target), (side + 24, side + 24))
    threshold, _ = cv2.threshold(warped, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    binary = (warped >= threshold).astype(np.uint8)
    clearance = (cv2.distanceTransform(binary, cv2.DIST_L2, 5)
                 - cv2.distanceTransform(1 - binary, cv2.DIST_L2, 5))
    rows, cols = np.indices((n, n), dtype=np.float32)
    nx, ny = cols / (n - 1) - .5, rows / (n - 1) - .5

    def sample(parameters, source):
        x, y, ax, ay, bx, by, axy, bxy = parameters
        return cv2.remap(source,
            (cols * 12 + 18 + x + ax * nx + ay * ny + axy * nx * ny).astype(np.float32),
            (rows * 12 + 18 + y + bx * nx + by * ny + bxy * nx * ny).astype(np.float32),
            cv2.INTER_LINEAR)

    def objective(parameters):
        values = sample(parameters, clearance)
        return float(values[black].mean() - values[white].mean())

    # One bounded bilinear correction for the entire QR, never per-data-cell
    # adjustments. Choose position by distance from fixed-pattern edges.
    initial = min(([x, y, 0, 0, 0, 0, 0, 0]
                   for y in range(-6, 7) for x in range(-6, 7)), key=objective)
    fit = minimize(objective, initial, method='Powell',
        bounds=[(-6, 6), (-6, 6)] + [(-12, 12)] * 6,
        options={'maxiter': 40, 'maxfev': 3000})
    if not fit.success or not np.isfinite(fit.x).all():
        return None
    values = sample(fit.x, cv2.blur(warped, (3, 3)))
    observed = values < threshold
    # Every known function module must match, and actual contrast must remain.
    if np.any(observed[fixed] != expected[fixed]):
        return None
    if float(values[white].mean() - values[black].mean()) < 60:
        return None
    return observed
