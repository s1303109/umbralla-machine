#!/usr/bin/env python3
"""Build the 480x320 RGB565 LCD background from the supplied dashboard PNG."""

from __future__ import annotations

import binascii
import struct
import sys
import zlib
from pathlib import Path


LCD_WIDTH = 480
LCD_HEIGHT = 320


def read_png(path: Path) -> tuple[int, int, bytearray]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("input is not a PNG")

    offset = 8
    compressed = bytearray()
    width = height = 0
    while offset < len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk = data[offset + 8 : offset + 8 + length]
        offset += length + 12
        if chunk_type == b"IHDR":
            width, height, depth, color_type, compression, filtering, interlace = (
                struct.unpack(">IIBBBBB", chunk)
            )
            if (depth, color_type, compression, filtering, interlace) != (8, 2, 0, 0, 0):
                raise ValueError("expected non-interlaced 8-bit RGB PNG")
        elif chunk_type == b"IDAT":
            compressed.extend(chunk)
        elif chunk_type == b"IEND":
            break

    raw = zlib.decompress(compressed)
    stride = width * 3
    pixels = bytearray(width * height * 3)
    source = 0
    previous = bytearray(stride)
    for y in range(height):
        filter_type = raw[source]
        source += 1
        scanline = bytearray(raw[source : source + stride])
        source += stride
        for index in range(stride):
            left = scanline[index - 3] if index >= 3 else 0
            above = previous[index]
            upper_left = previous[index - 3] if index >= 3 else 0
            if filter_type == 1:
                scanline[index] = (scanline[index] + left) & 0xFF
            elif filter_type == 2:
                scanline[index] = (scanline[index] + above) & 0xFF
            elif filter_type == 3:
                scanline[index] = (scanline[index] + ((left + above) >> 1)) & 0xFF
            elif filter_type == 4:
                estimate = left + above - upper_left
                pa = abs(estimate - left)
                pb = abs(estimate - above)
                pc = abs(estimate - upper_left)
                predictor = left if pa <= pb and pa <= pc else (above if pb <= pc else upper_left)
                scanline[index] = (scanline[index] + predictor) & 0xFF
            elif filter_type != 0:
                raise ValueError(f"unsupported PNG filter {filter_type}")
        start = y * stride
        pixels[start : start + stride] = scanline
        previous = scanline
    return width, height, pixels


def resize_bilinear(
    source: bytearray,
    source_width: int,
    source_height: int,
) -> bytearray:
    output = bytearray(LCD_WIDTH * LCD_HEIGHT * 3)
    for y in range(LCD_HEIGHT):
        source_y = (y + 0.5) * source_height / LCD_HEIGHT - 0.5
        y0 = max(0, min(source_height - 1, int(source_y)))
        y1 = min(source_height - 1, y0 + 1)
        fy = max(0.0, source_y - y0)
        for x in range(LCD_WIDTH):
            source_x = (x + 0.5) * source_width / LCD_WIDTH - 0.5
            x0 = max(0, min(source_width - 1, int(source_x)))
            x1 = min(source_width - 1, x0 + 1)
            fx = max(0.0, source_x - x0)
            destination = (y * LCD_WIDTH + x) * 3
            for channel in range(3):
                top_left = source[(y0 * source_width + x0) * 3 + channel]
                top_right = source[(y0 * source_width + x1) * 3 + channel]
                bottom_left = source[(y1 * source_width + x0) * 3 + channel]
                bottom_right = source[(y1 * source_width + x1) * 3 + channel]
                top = top_left * (1.0 - fx) + top_right * fx
                bottom = bottom_left * (1.0 - fx) + bottom_right * fx
                output[destination + channel] = round(top * (1.0 - fy) + bottom * fy)
    return output


def inpaint_horizontal(pixels: bytearray, x: int, y: int, width: int, height: int) -> None:
    left_x = max(0, x - 1)
    right_x = min(LCD_WIDTH - 1, x + width)
    for row in range(max(0, y), min(LCD_HEIGHT, y + height)):
        left_index = (row * LCD_WIDTH + left_x) * 3
        right_index = (row * LCD_WIDTH + right_x) * 3
        left = pixels[left_index : left_index + 3]
        right = pixels[right_index : right_index + 3]
        for column in range(x, min(LCD_WIDTH, x + width)):
            ratio = (column - x + 1) / (width + 1)
            destination = (row * LCD_WIDTH + column) * 3
            for channel in range(3):
                pixels[destination + channel] = round(
                    left[channel] * (1.0 - ratio) + right[channel] * ratio
                )


def sharpen_edges(pixels: bytearray) -> bytearray:
    """Restore a little edge contrast lost when the large artwork is reduced."""
    source = pixels
    output = bytearray(source)
    for y in range(1, LCD_HEIGHT - 1):
        for x in range(1, LCD_WIDTH - 1):
            center = (y * LCD_WIDTH + x) * 3
            neighbor_indices = (
                center - LCD_WIDTH * 3,
                center + LCD_WIDTH * 3,
                center - 3,
                center + 3,
            )
            for channel in range(3):
                value = source[center + channel]
                blurred = sum(source[index + channel] for index in neighbor_indices) // 4
                detail = value - blurred
                # A restrained 5/8 unsharp mask improves lettering without
                # producing bright halos around the dashboard panels.
                sharpened = value + detail * 5 // 8
                output[center + channel] = max(0, min(255, sharpened))
    return output


def write_preview_png(path: Path, pixels: bytearray) -> None:
    scanlines = bytearray()
    stride = LCD_WIDTH * 3
    for y in range(LCD_HEIGHT):
        scanlines.append(0)
        scanlines.extend(pixels[y * stride : (y + 1) * stride])

    def chunk(name: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + name
            + payload
            + struct.pack(">I", binascii.crc32(name + payload) & 0xFFFFFFFF)
        )

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", LCD_WIDTH, LCD_HEIGHT, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(scanlines, 9))
        + chunk(b"IEND", b"")
    )


def write_rgb565(path: Path, pixels: bytearray) -> None:
    output = bytearray(LCD_WIDTH * LCD_HEIGHT * 2)
    for pixel in range(LCD_WIDTH * LCD_HEIGHT):
        red, green, blue = pixels[pixel * 3 : pixel * 3 + 3]
        color = ((red >> 3) << 11) | ((green >> 2) << 5) | (blue >> 3)
        struct.pack_into(">H", output, pixel * 2, color)
    path.write_bytes(output)


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: make_dashboard_asset.py INPUT.png OUTPUT.rgb565 PREVIEW.png")
    source_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    preview_path = Path(sys.argv[3])
    width, height, source = read_png(source_path)
    pixels = resize_bilinear(source, width, height)
    pixels = sharpen_edges(pixels)

    # Remove demonstration-only content. Firmware redraws these small regions.
    dynamic_regions = (
        (102, 39, 175, 14),  # tiny title subtitle; firmware redraws it bold
        (168, 83, 132, 14),  # tiny system-status label
        (374, 8, 90, 14),    # fixed example date
        (371, 29, 91, 19),   # fixed header status
        (22, 72, 126, 94),   # static fan and wind marks
        (169, 99, 270, 55),  # blower state and instruction
        (130, 181, 23, 22),  # sensor 1 example check
        (17, 196, 62, 14),   # sensor 1 tiny distance label
        (65, 210, 82, 31),   # sensor 1 example distance
        (18, 244, 130, 9),   # sensor 1 example progress
        (286, 181, 23, 22),  # sensor 2 example check
        (175, 196, 62, 14),  # sensor 2 tiny distance label
        (221, 210, 83, 31),  # sensor 2 example distance
        (176, 244, 130, 9),  # sensor 2 example progress
        (442, 181, 23, 22),  # ultrasonic example check
        (331, 196, 62, 14),  # ultrasonic tiny distance label
        (377, 210, 87, 31),  # ultrasonic example distance
        (332, 244, 132, 9),  # ultrasonic example progress
        (61, 277, 180, 27),  # fixed three-sensor confirmation
        (319, 284, 42, 14),  # tiny relay label
        (364, 279, 48, 23),  # fixed relay ON pill
    )
    for region in dynamic_regions:
        inpaint_horizontal(pixels, *region)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_rgb565(output_path, pixels)
    write_preview_png(preview_path, pixels)
    print(f"wrote {output_path} ({output_path.stat().st_size} bytes)")
    print(f"wrote {preview_path} ({LCD_WIDTH}x{LCD_HEIGHT})")


if __name__ == "__main__":
    main()
