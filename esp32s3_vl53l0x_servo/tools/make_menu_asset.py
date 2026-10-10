#!/usr/bin/env python3
"""Build the rose-glass 480x320 LCD menu and deterministic state previews."""

from __future__ import annotations

import math
import struct
import subprocess
import sys
import zlib
from pathlib import Path

from make_dashboard_asset import (
    LCD_HEIGHT,
    LCD_WIDTH,
    read_png,
    write_preview_png,
    write_rgb565,
)


WHITE = (250, 246, 244)
MUTED = (190, 166, 161)
UI_SCALE = 1.04
UI_CENTER = (240.0, 150.0)

FAN_REGION = (56, 75, 110, 110)
# Measured from the circular hub edge in the LCD-scaled source image.  Keep the
# half-pixel vertical center so every rotated frame stays on the same axis.
FAN_CENTER = (55.0, 54.75)
FAN_HUB_RADIUS = 15.6
FAN_ROTATION_RADIUS = 53.0
FAN_EDGE_MARGIN = 1
FAN_FRAME_COUNT = 72
BLOWER_ON_REGION = (176, 112, 88, 35)
RELAY_ON_REGION = (189, 214, 70, 29)
SENSOR_LIGHT_X = 423
SENSOR_LIGHT_Y = (52, 123, 194)
SENSOR_LIGHT_WIDTH = 33
SENSOR_LIGHT_HEIGHT = 30
DIGIT_ATLAS_WIDTH = 276
DIGIT_ATLAS_HEIGHT = 31
DIGIT_CELL_WIDTH = 23
DIGIT_CHARACTERS = "0123456789m-"
DIGIT_ADVANCE = 17
UNIT_ADVANCE = 10
UNIT_GAP = 2
STATUS_ATLAS_WIDTH = 128
STATUS_ATLAS_HEIGHT = 16
STATUS_CELL_WIDTH = 64
STATUS_TEXT_COLOR = (207, 197, 195)

def resize_bilinear(
    source: bytearray,
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
) -> bytearray:
    output = bytearray(target_width * target_height * 3)
    for y in range(target_height):
        source_y = (y + 0.5) * source_height / target_height - 0.5
        y0 = max(0, min(source_height - 1, int(source_y)))
        y1 = min(source_height - 1, y0 + 1)
        fy = max(0.0, source_y - y0)
        for x in range(target_width):
            source_x = (x + 0.5) * source_width / target_width - 0.5
            x0 = max(0, min(source_width - 1, int(source_x)))
            x1 = min(source_width - 1, x0 + 1)
            fx = max(0.0, source_x - x0)
            destination = (y * target_width + x) * 3
            for channel in range(3):
                top_left = source[(y0 * source_width + x0) * 3 + channel]
                top_right = source[(y0 * source_width + x1) * 3 + channel]
                bottom_left = source[(y1 * source_width + x0) * 3 + channel]
                bottom_right = source[(y1 * source_width + x1) * 3 + channel]
                top = top_left * (1.0 - fx) + top_right * fx
                bottom = bottom_left * (1.0 - fx) + bottom_right * fx
                output[destination + channel] = round(top * (1.0 - fy) + bottom * fy)
    return output


def zoom_bilinear(
    source: bytearray,
    width: int,
    height: int,
    scale: float,
    center_x: float,
    center_y: float,
) -> bytearray:
    output = bytearray(width * height * 3)
    for y in range(height):
        source_y = center_y + (y - center_y) / scale
        y0 = max(0, min(height - 1, math.floor(source_y)))
        y1 = min(height - 1, y0 + 1)
        fy = max(0.0, source_y - y0)
        for x in range(width):
            source_x = center_x + (x - center_x) / scale
            x0 = max(0, min(width - 1, math.floor(source_x)))
            x1 = min(width - 1, x0 + 1)
            fx = max(0.0, source_x - x0)
            destination = (y * width + x) * 3
            for channel in range(3):
                top_left = source[(y0 * width + x0) * 3 + channel]
                top_right = source[(y0 * width + x1) * 3 + channel]
                bottom_left = source[(y1 * width + x0) * 3 + channel]
                bottom_right = source[(y1 * width + x1) * 3 + channel]
                top = top_left * (1.0 - fx) + top_right * fx
                bottom = bottom_left * (1.0 - fx) + bottom_right * fx
                output[destination + channel] = round(
                    top * (1.0 - fy) + bottom * fy
                )
    return output


def fit_to_lcd(source: bytearray, width: int, height: int) -> bytearray:
    # Preserve the supplied artwork, then apply a small uniform zoom around the
    # menu group so every UI element grows by the same proportion.
    fitted = resize_bilinear(source, width, height, LCD_WIDTH, LCD_HEIGHT)
    return zoom_bilinear(
        fitted,
        LCD_WIDTH,
        LCD_HEIGHT,
        UI_SCALE,
        *UI_CENTER,
    )


def inpaint_horizontal(
    pixels: bytearray, x: int, y: int, width: int, height: int
) -> None:
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


def extract_region(
    pixels: bytearray, x: int, y: int, width: int, height: int
) -> bytearray:
    output = bytearray(width * height * 3)
    for row in range(height):
        source = ((y + row) * LCD_WIDTH + x) * 3
        destination = row * width * 3
        output[destination : destination + width * 3] = pixels[
            source : source + width * 3
        ]
    return output


def paste_region(
    pixels: bytearray,
    region: bytearray,
    x: int,
    y: int,
    width: int,
    height: int,
) -> None:
    for row in range(height):
        source = row * width * 3
        destination = ((y + row) * LCD_WIDTH + x) * 3
        pixels[destination : destination + width * 3] = region[
            source : source + width * 3
        ]


def write_rgb565_pixels(path: Path, pixels: bytearray) -> None:
    output = bytearray(len(pixels) // 3 * 2)
    for index in range(len(pixels) // 3):
        red, green, blue = pixels[index * 3 : index * 3 + 3]
        color = ((red >> 3) << 11) | ((green >> 2) << 5) | (blue >> 3)
        struct.pack_into(">H", output, index * 2, color)
    path.write_bytes(output)


def read_png_pixels(path: Path) -> tuple[int, int, int, bytearray]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("input is not a PNG")
    offset = 8
    compressed = bytearray()
    width = height = color_type = 0
    while offset < len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk = data[offset + 8 : offset + 8 + length]
        offset += length + 12
        if chunk_type == b"IHDR":
            width, height, depth, color_type, compression, filtering, interlace = (
                struct.unpack(">IIBBBBB", chunk)
            )
            if depth != 8 or color_type not in (2, 6) or compression or filtering or interlace:
                raise ValueError("expected a non-interlaced 8-bit RGB/RGBA PNG")
        elif chunk_type == b"IDAT":
            compressed.extend(chunk)
        elif chunk_type == b"IEND":
            break
    channels = 3 if color_type == 2 else 4
    stride = width * channels
    raw = zlib.decompress(compressed)
    pixels = bytearray(width * height * channels)
    source = 0
    previous = bytearray(stride)
    for y in range(height):
        filter_type = raw[source]
        source += 1
        scanline = bytearray(raw[source : source + stride])
        source += stride
        for index in range(stride):
            left = scanline[index - channels] if index >= channels else 0
            above = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
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
        destination = y * stride
        pixels[destination : destination + stride] = scanline
        previous = scanline
    return width, height, channels, pixels


def render_digit_atlas(atlas_png_path: Path) -> bytearray:
    svg_path = Path(__file__).with_name("menu_digits.svg")
    subprocess.run(
        [
            "rsvg-convert",
            "--width",
            str(DIGIT_ATLAS_WIDTH),
            "--height",
            str(DIGIT_ATLAS_HEIGHT),
            "--background-color",
            "black",
            "--output",
            str(atlas_png_path),
            str(svg_path),
        ],
        check=True,
    )
    width, height, channels, pixels = read_png_pixels(atlas_png_path)
    if (width, height) != (DIGIT_ATLAS_WIDTH, DIGIT_ATLAS_HEIGHT):
        raise ValueError(f"unexpected digit atlas size {width}x{height}")
    alpha = bytearray(width * height)
    for index in range(width * height):
        red = pixels[index * channels]
        green = pixels[index * channels + 1]
        blue = pixels[index * channels + 2]
        alpha[index] = max(red, green, blue)
    return alpha


def render_status_atlas(atlas_png_path: Path) -> bytearray:
    svg_path = Path(__file__).with_name("menu_status.svg")
    subprocess.run(
        [
            "rsvg-convert",
            "--width",
            str(STATUS_ATLAS_WIDTH),
            "--height",
            str(STATUS_ATLAS_HEIGHT),
            "--background-color",
            "black",
            "--output",
            str(atlas_png_path),
            str(svg_path),
        ],
        check=True,
    )
    width, height, channels, pixels = read_png_pixels(atlas_png_path)
    if (width, height) != (STATUS_ATLAS_WIDTH, STATUS_ATLAS_HEIGHT):
        raise ValueError(f"unexpected status atlas size {width}x{height}")
    alpha = bytearray(width * height)
    for index in range(width * height):
        alpha[index] = max(
            pixels[index * channels],
            pixels[index * channels + 1],
            pixels[index * channels + 2],
        )
    return alpha


def inpaint_patch_horizontal(
    pixels: bytearray,
    patch_width: int,
    patch_height: int,
    x: int,
    y: int,
    width: int,
    height: int,
) -> None:
    left_x = max(0, x - 1)
    right_x = min(patch_width - 1, x + width)
    for row in range(max(0, y), min(patch_height, y + height)):
        left_index = (row * patch_width + left_x) * 3
        right_index = (row * patch_width + right_x) * 3
        left = pixels[left_index : left_index + 3]
        right = pixels[right_index : right_index + 3]
        for column in range(x, min(patch_width, x + width)):
            ratio = (column - x + 1) / (width + 1)
            destination = (row * patch_width + column) * 3
            for channel in range(3):
                pixels[destination + channel] = round(
                    left[channel] * (1.0 - ratio) + right[channel] * ratio
                )


def draw_status_word(
    pixels: bytearray,
    patch_width: int,
    patch_height: int,
    alpha: bytearray,
    word_index: int,
    x: int,
    y: int,
) -> None:
    source_x = word_index * STATUS_CELL_WIDTH
    for row in range(STATUS_ATLAS_HEIGHT):
        for column in range(STATUS_CELL_WIDTH):
            coverage = alpha[
                row * STATUS_ATLAS_WIDTH + source_x + column
            ]
            target_x = x + column
            target_y = y + row
            if coverage == 0 or not (
                0 <= target_x < patch_width and 0 <= target_y < patch_height
            ):
                continue
            destination = (target_y * patch_width + target_x) * 3
            for channel in range(3):
                pixels[destination + channel] = (
                    pixels[destination + channel] * (255 - coverage)
                    + STATUS_TEXT_COLOR[channel] * coverage
                ) // 255


def make_gray_state_patch(
    active: bytearray,
    background: bytearray,
) -> bytearray:
    """Keep the original shape but change its active pink accent to gray."""
    inactive = bytearray(background)
    for pixel in range(len(active) // 3):
        offset = pixel * 3
        source = active[offset : offset + 3]
        base = background[offset : offset + 3]
        difference = max(abs(int(source[c]) - int(base[c])) for c in range(3))
        if difference <= 5:
            continue
        strength = min(1.0, (difference - 5) / 26.0)
        luminance = round(
            source[0] * 0.24 + source[1] * 0.68 + source[2] * 0.08
        )
        neutral = (luminance, max(0, luminance - 2), max(0, luminance - 3))
        for channel in range(3):
            inactive[offset + channel] = round(
                base[channel] * (1.0 - strength)
                + neutral[channel] * strength
            )
    return inactive


def draw_rounded_text(
    pixels: bytearray,
    alpha: bytearray,
    x: int,
    y: int,
    text: str,
) -> None:
    cursor_x = x
    previous_character = ""
    for character in text:
        if character == "m" and previous_character != "m":
            cursor_x += UNIT_GAP
        glyph_index = DIGIT_CHARACTERS.index(character)
        glyph_x = glyph_index * DIGIT_CELL_WIDTH
        color = MUTED if character == "m" else WHITE
        for row in range(DIGIT_ATLAS_HEIGHT):
            for column in range(DIGIT_CELL_WIDTH):
                coverage = alpha[
                    row * DIGIT_ATLAS_WIDTH + glyph_x + column
                ]
                if coverage == 0:
                    continue
                target_x = cursor_x + column
                target_y = y + row
                if not (0 <= target_x < LCD_WIDTH and 0 <= target_y < LCD_HEIGHT):
                    continue
                destination = (target_y * LCD_WIDTH + target_x) * 3
                for channel in range(3):
                    pixels[destination + channel] = (
                        pixels[destination + channel] * (255 - coverage)
                        + color[channel] * coverage
                    ) // 255
        cursor_x += UNIT_ADVANCE if character == "m" else DIGIT_ADVANCE
        previous_character = character


def build_original_fan_frames(
    scaled: bytearray, template: bytearray
) -> list[bytearray]:
    x, y, width, height = FAN_REGION
    original = extract_region(scaled, x, y, width, height)
    background = extract_region(template, x, y, width, height)
    delta = [
        int(original[index]) - int(background[index])
        for index in range(len(original))
    ]
    center_x, center_y = FAN_CENTER
    frames: list[bytearray] = []
    for frame_index in range(FAN_FRAME_COUNT):
        if frame_index == 0:
            frames.append(original)
            continue
        # Use a complete revolution instead of assuming all five blades have
        # identical lighting.  A short 72-degree loop made the last frame look
        # as though it snapped backward to the original photograph.
        angle = math.radians(frame_index * (360.0 / FAN_FRAME_COUNT))
        cosine = math.cos(angle)
        sine = math.sin(angle)
        frame = bytearray(background)
        for target_y in range(height):
            for target_x in range(width):
                # Do not rotate pixels touching the crop boundary.  Those
                # partial samples previously formed a horizontal line above
                # the fan when the blade reached the top of the crop.
                if (
                    target_x < FAN_EDGE_MARGIN
                    or target_x >= width - FAN_EDGE_MARGIN
                    or target_y < FAN_EDGE_MARGIN
                    or target_y >= height - FAN_EDGE_MARGIN
                ):
                    continue
                dx = target_x - center_x
                dy = target_y - center_y
                if dx * dx + dy * dy > FAN_ROTATION_RADIUS**2:
                    continue
                source_x = cosine * dx + sine * dy + center_x
                source_y = -sine * dx + cosine * dy + center_y
                x0 = math.floor(source_x)
                y0 = math.floor(source_y)
                if (
                    x0 < FAN_EDGE_MARGIN
                    or y0 < FAN_EDGE_MARGIN
                    or x0 + 1 >= width - FAN_EDGE_MARGIN
                    or y0 + 1 >= height - FAN_EDGE_MARGIN
                ):
                    continue
                fx = source_x - x0
                fy = source_y - y0
                destination = (target_y * width + target_x) * 3
                sampled = []
                for channel in range(3):
                    top_left = delta[(y0 * width + x0) * 3 + channel]
                    top_right = delta[(y0 * width + x0 + 1) * 3 + channel]
                    bottom_left = delta[((y0 + 1) * width + x0) * 3 + channel]
                    bottom_right = delta[((y0 + 1) * width + x0 + 1) * 3 + channel]
                    top = top_left * (1.0 - fx) + top_right * fx
                    bottom = bottom_left * (1.0 - fx) + bottom_right * fx
                    sampled.append(round(top * (1.0 - fy) + bottom * fy))
                magnitude = max(abs(value) for value in sampled)
                if magnitude < 24:
                    continue
                strength = 1.0 if magnitude >= 40 else (magnitude - 24) / 16.0
                for channel in range(3):
                    value = frame[destination + channel] + round(sampled[channel] * strength)
                    frame[destination + channel] = max(0, min(255, value))

        # The hub is not animated: copy its original pixels back after rotating
        # the blades.  This preserves the exact circle and removes interpolation
        # wobble at the shaft.
        for target_y in range(height):
            for target_x in range(width):
                dx = target_x - center_x
                dy = target_y - center_y
                if dx * dx + dy * dy <= FAN_HUB_RADIUS**2:
                    destination = (target_y * width + target_x) * 3
                    frame[destination : destination + 3] = original[
                        destination : destination + 3
                    ]
        frames.append(frame)
    return frames


def build_fan_delta_asset(
    scaled: bytearray, template: bytearray
) -> tuple[bytearray, bytearray]:
    """Encode one original RGB565 frame plus signed RGB565 component deltas."""
    x, y, width, height = FAN_REGION
    original = extract_region(scaled, x, y, width, height)
    background = extract_region(template, x, y, width, height)
    delta_asset = bytearray(width * height * 3)
    center_x, center_y = FAN_CENTER
    for pixel_y in range(height):
        for pixel_x in range(width):
            dx = pixel_x - center_x
            dy = pixel_y - center_y
            if (
                pixel_x < FAN_EDGE_MARGIN
                or pixel_x >= width - FAN_EDGE_MARGIN
                or pixel_y < FAN_EDGE_MARGIN
                or pixel_y >= height - FAN_EDGE_MARGIN
                or dx * dx + dy * dy > FAN_ROTATION_RADIUS**2
                or dx * dx + dy * dy <= FAN_HUB_RADIUS**2
            ):
                continue
            offset = (pixel_y * width + pixel_x) * 3
            source = original[offset : offset + 3]
            base = background[offset : offset + 3]
            magnitude = max(
                abs(int(source[channel]) - int(base[channel]))
                for channel in range(3)
            )
            if magnitude < 24:
                continue
            strength = 1.0 if magnitude >= 40 else (magnitude - 24) / 16.0
            source_components = (
                source[0] >> 3,
                source[1] >> 2,
                source[2] >> 3,
            )
            base_components = (
                base[0] >> 3,
                base[1] >> 2,
                base[2] >> 3,
            )
            for channel in range(3):
                change = round(
                    (source_components[channel] - base_components[channel])
                    * strength
                )
                delta_asset[offset + channel] = change & 0xFF
    return original, delta_asset


def build_sensor_light_patches(
    scaled: bytearray, template: bytearray
) -> list[bytearray]:
    source_y = SENSOR_LIGHT_Y[0]
    source_on = extract_region(
        scaled,
        SENSOR_LIGHT_X,
        source_y,
        SENSOR_LIGHT_WIDTH,
        SENSOR_LIGHT_HEIGHT,
    )
    source_off = extract_region(
        template,
        SENSOR_LIGHT_X,
        source_y,
        SENSOR_LIGHT_WIDTH,
        SENSOR_LIGHT_HEIGHT,
    )
    delta = [int(on) - int(off) for on, off in zip(source_on, source_off)]
    patches = []
    for target_y in SENSOR_LIGHT_Y:
        patch = extract_region(
            template,
            SENSOR_LIGHT_X,
            target_y,
            SENSOR_LIGHT_WIDTH,
            SENSOR_LIGHT_HEIGHT,
        )
        for index, change in enumerate(delta):
            patch[index] = max(0, min(255, patch[index] + change))
        patches.append(patch)
    return patches


def build_sensor_light_off_patches(
    on_patches: list[bytearray], template: bytearray
) -> list[bytearray]:
    patches = []
    for index, target_y in enumerate(SENSOR_LIGHT_Y):
        background = extract_region(
            template,
            SENSOR_LIGHT_X,
            target_y,
            SENSOR_LIGHT_WIDTH,
            SENSOR_LIGHT_HEIGHT,
        )
        patches.append(make_gray_state_patch(on_patches[index], background))
    return patches


def draw_sensor(
    pixels: bytearray,
    digit_alpha: bytearray,
    light_on_patch: bytearray,
    light_off_patch: bytearray,
    index: int,
    distance_mm: int,
    active: bool,
    valid: bool = True,
) -> None:
    value_y = (80, 151, 222)[index]
    paste_region(
        pixels,
        light_on_patch if active and valid else light_off_patch,
        SENSOR_LIGHT_X,
        SENSOR_LIGHT_Y[index],
        SENSOR_LIGHT_WIDTH,
        SENSOR_LIGHT_HEIGHT,
    )
    value = f"{distance_mm}mm" if valid else "---"
    draw_rounded_text(pixels, digit_alpha, 291, value_y, value)


def draw_preview(
    template: bytearray,
    fan_frames: list[bytearray],
    blower_on: bytearray,
    blower_off: bytearray,
    relay_on: bytearray,
    relay_off: bytearray,
    sensor_lights_on: list[bytearray],
    sensor_lights_off: list[bytearray],
    digit_alpha: bytearray,
    running: bool,
    distances: tuple[int, int, int],
) -> bytearray:
    pixels = bytearray(template)
    active = (
        distances[0] < 101,
        distances[1] < 101,
        distances[2] < 65,
    )
    paste_region(pixels, fan_frames[3 if running else 0], *FAN_REGION)
    paste_region(
        pixels,
        blower_on if running else blower_off,
        *BLOWER_ON_REGION,
    )
    paste_region(
        pixels,
        relay_on if running else relay_off,
        *RELAY_ON_REGION,
    )
    for index, distance in enumerate(distances):
        draw_sensor(
            pixels,
            digit_alpha,
            sensor_lights_on[index],
            sensor_lights_off[index],
            index,
            distance,
            active[index],
        )
    return pixels


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: make_menu_asset.py INPUT.png ASSET_DIRECTORY PREVIEW_DIRECTORY"
        )
    source_path = Path(sys.argv[1])
    asset_directory = Path(sys.argv[2])
    preview_directory = Path(sys.argv[3])
    output_path = asset_directory / "dashboard.rgb565"
    fan_original_path = asset_directory / "fan_original.rgb565"
    fan_delta_path = asset_directory / "fan_delta.s8"
    blower_on_path = asset_directory / "blower_on.rgb565"
    blower_off_path = asset_directory / "blower_off.rgb565"
    relay_on_path = asset_directory / "relay_on.rgb565"
    relay_off_path = asset_directory / "relay_off.rgb565"
    sensor_lights_path = asset_directory / "sensor_lights_on.rgb565"
    sensor_lights_off_path = asset_directory / "sensor_lights_off.rgb565"
    digit_alpha_path = asset_directory / "menu_digits.alpha8"
    template_preview_path = preview_directory / "menu-template-preview.png"
    off_preview_path = preview_directory / "menu-gpio7-off-preview.png"
    on_preview_path = preview_directory / "menu-gpio7-on-preview.png"
    digit_atlas_preview_path = preview_directory / "menu-digits-atlas.png"
    status_atlas_preview_path = preview_directory / "menu-status-atlas.png"

    width, height, source = read_png(source_path)
    scaled = fit_to_lcd(source, width, height)
    template = bytearray(scaled)

    # Remove all sample-only content. Firmware redraws these exact regions.
    dynamic_regions = (
        FAN_REGION,           # original fan is restored from extracted frames
        BLOWER_ON_REGION,      # blower lamp and state pill
        RELAY_ON_REGION,       # relay lamp and ON/OFF text
        (423, 52, 33, 30),    # ToF 1 lamp
        (289, 80, 118, 31),   # ToF 1 value
        (423, 123, 33, 30),   # ToF 2 lamp
        (289, 151, 118, 31),  # ToF 2 value
        (423, 194, 33, 30),   # ultrasonic lamp
        (289, 222, 118, 31),  # ultrasonic value
    )
    for region in dynamic_regions:
        inpaint_horizontal(template, *region)

    # The fan cleanup overlaps the bottom of this static label; restore only
    # those untouched original label pixels after removing the rotor.
    blower_label_region = (28, 74, 48, 14)
    paste_region(
        template,
        extract_region(scaled, *blower_label_region),
        *blower_label_region,
    )

    fan_frames = build_original_fan_frames(scaled, template)
    fan_original, fan_delta = build_fan_delta_asset(scaled, template)
    blower_on = extract_region(scaled, *BLOWER_ON_REGION)
    relay_on = extract_region(scaled, *RELAY_ON_REGION)
    sensor_lights_on = build_sensor_light_patches(scaled, template)
    sensor_lights_off = build_sensor_light_off_patches(
        sensor_lights_on, template
    )

    asset_directory.mkdir(parents=True, exist_ok=True)
    preview_directory.mkdir(parents=True, exist_ok=True)
    digit_alpha = render_digit_atlas(digit_atlas_preview_path)
    status_alpha = render_status_atlas(status_atlas_preview_path)
    blower_off = make_gray_state_patch(
        blower_on, extract_region(template, *BLOWER_ON_REGION)
    )
    inpaint_patch_horizontal(blower_off, 88, 35, 31, 7, 52, 21)
    draw_status_word(blower_off, 88, 35, status_alpha, 0, 32, 9)
    relay_off = make_gray_state_patch(
        relay_on, extract_region(template, *RELAY_ON_REGION)
    )
    inpaint_patch_horizontal(relay_off, 70, 29, 28, 4, 32, 20)
    draw_status_word(relay_off, 70, 29, status_alpha, 1, 29, 7)
    write_rgb565(output_path, template)
    write_rgb565_pixels(fan_original_path, fan_original)
    fan_delta_path.write_bytes(fan_delta)
    write_rgb565_pixels(blower_on_path, blower_on)
    write_rgb565_pixels(blower_off_path, blower_off)
    write_rgb565_pixels(relay_on_path, relay_on)
    write_rgb565_pixels(relay_off_path, relay_off)
    write_rgb565_pixels(sensor_lights_path, bytearray().join(sensor_lights_on))
    write_rgb565_pixels(
        sensor_lights_off_path, bytearray().join(sensor_lights_off)
    )
    digit_alpha_path.write_bytes(digit_alpha)
    write_preview_png(template_preview_path, template)
    write_preview_png(
        off_preview_path,
        draw_preview(
            template,
            fan_frames,
            blower_on,
            blower_off,
            relay_on,
            relay_off,
            sensor_lights_on,
            sensor_lights_off,
            digit_alpha,
            False,
            (82, 156, 241),
        ),
    )
    write_preview_png(
        on_preview_path,
        draw_preview(
            template,
            fan_frames,
            blower_on,
            blower_off,
            relay_on,
            relay_off,
            sensor_lights_on,
            sensor_lights_off,
            digit_alpha,
            True,
            (82, 94, 54),
        ),
    )
    print(f"wrote {output_path} ({output_path.stat().st_size} bytes)")
    print(f"wrote {fan_original_path} ({fan_original_path.stat().st_size} bytes)")
    print(f"wrote {fan_delta_path} ({fan_delta_path.stat().st_size} bytes)")
    print(f"wrote {blower_off_path} ({blower_off_path.stat().st_size} bytes)")
    print(f"wrote {relay_off_path} ({relay_off_path.stat().st_size} bytes)")
    print(f"wrote {digit_alpha_path} ({digit_alpha_path.stat().st_size} bytes)")
    print(f"wrote {off_preview_path} ({LCD_WIDTH}x{LCD_HEIGHT})")
    print(f"wrote {on_preview_path} ({LCD_WIDTH}x{LCD_HEIGHT})")


if __name__ == "__main__":
    main()
