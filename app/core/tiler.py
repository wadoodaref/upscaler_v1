"""Image tiling and seam blending for memory-bounded upscaling."""

from __future__ import annotations

import math
from typing import Callable

import cv2
import numpy as np


def process_tiles(
    img: np.ndarray,
    scale: int,
    tile_size: int,
    tile_pad: int,
    forward_fn: Callable[[np.ndarray], np.ndarray],
    progress_callback: Callable[[int, int], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
    fixed_shape: bool = False,
) -> np.ndarray:
    """Split img (H, W, C) into overlapping tiles, process each through forward_fn,
    and blend back seamlessly with linear ramp weighting.
    """
    h, w, c = img.shape

    # If tile_size is 0 or image is smaller than tile_size, run directly
    if tile_size <= 0 or (h <= tile_size and w <= tile_size):
        if is_cancelled and is_cancelled():
            raise InterruptedError("Cancelled by user")
        out = forward_fn(img)
        if progress_callback:
            progress_callback(1, 1)
        return out

    out_h = h * scale
    out_w = w * scale
    output = np.zeros((out_h, out_w, c), dtype=np.float32)
    weights = np.zeros((out_h, out_w, 1), dtype=np.float32)

    tiles_x = math.ceil(w / tile_size)
    tiles_y = math.ceil(h / tile_size)
    total_tiles = tiles_x * tiles_y
    done_tiles = 0

    for yi in range(tiles_y):
        for xi in range(tiles_x):
            if is_cancelled and is_cancelled():
                raise InterruptedError("Cancelled by user")

            # Tile coordinates in input space
            x = xi * tile_size
            y = yi * tile_size
            x_end = min(x + tile_size, w)
            y_end = min(y + tile_size, h)

            # Pad coordinates
            pad_x_start = max(0, x - tile_pad)
            pad_y_start = max(0, y - tile_pad)
            pad_x_end = min(w, x_end + tile_pad)
            pad_y_end = min(h, y_end + tile_pad)

            tile_in = img[pad_y_start:pad_y_end, pad_x_start:pad_x_end]
            real_h, real_w = tile_in.shape[:2]

            if fixed_shape:
                # DirectML recompiles its GPU kernels for every new input shape
                # (7-15 s each on the Photo model). Feeding every tile the same
                # size compiles once; the added border is cropped off the output.
                full = tile_size + 2 * tile_pad
                bh, bw = full - real_h, full - real_w
                if bh or bw:
                    mode = cv2.BORDER_REFLECT_101 if (bh < real_h and bw < real_w) else cv2.BORDER_REPLICATE
                    tile_in = cv2.copyMakeBorder(tile_in, 0, bh, 0, bw, mode)

            # Forward through engine
            tile_out = forward_fn(tile_in).astype(np.float32)
            if fixed_shape:
                tile_out = tile_out[: real_h * scale, : real_w * scale]

            # Output coordinates
            out_pad_x_start = pad_x_start * scale
            out_pad_y_start = pad_y_start * scale
            out_pad_x_end = pad_x_end * scale
            out_pad_y_end = pad_y_end * scale

            th, tw = tile_out.shape[:2]

            # Linear ramp blending mask to eliminate seam artifacts
            ramp_x = np.ones(tw, dtype=np.float32)
            ramp_y = np.ones(th, dtype=np.float32)

            pad_px = tile_pad * scale
            if pad_x_start > 0:
                ramp_x[:pad_px] = np.linspace(0, 1, pad_px)
            if pad_x_end < w:
                ramp_x[-pad_px:] = np.linspace(1, 0, pad_px)

            if pad_y_start > 0:
                ramp_y[:pad_px] = np.linspace(0, 1, pad_px)
            if pad_y_end < h:
                ramp_y[-pad_px:] = np.linspace(1, 0, pad_px)

            mask = (ramp_y[:, None] * ramp_x[None, :])[:, :, None]

            output[out_pad_y_start:out_pad_y_end, out_pad_x_start:out_pad_x_end] += tile_out * mask
            weights[out_pad_y_start:out_pad_y_end, out_pad_x_start:out_pad_x_end] += mask

            done_tiles += 1
            if progress_callback:
                progress_callback(done_tiles, total_tiles)

    # Normalize blended output
    weights = np.maximum(weights, 1e-5)
    output = output / weights
    return np.clip(output, 0, 255).astype(np.uint8)
