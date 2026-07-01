from __future__ import annotations

import hashlib
import json
import math
import random
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "frontend" / "public" / "stimuli" / "v1"
CATALOG = OUTPUT / "catalog.json"
LICENSE_URL = "https://creativecommons.org/publicdomain/zero/1.0/"
IMAGE_SIZE = (512, 384)
SAMPLE_RATE = 16_000


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_image(identifier: str, category: str, title: str, draw_fn, tags: list[str]) -> dict:
    path = OUTPUT / category / f"{identifier}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", IMAGE_SIZE, "#d8dadd")
    drawing = ImageDraw.Draw(image)
    draw_fn(drawing, random.Random(identifier))
    image.save(path, optimize=True)
    return asset_record(identifier, title, category, "image", path, tags, "image/png")


def face_with_expression(expression: str):
    def face(drawing: ImageDraw.ImageDraw, rng: random.Random) -> None:
        skin = rng.choice(["#e7b98a", "#9c6644", "#6f4518", "#f2ccad", "#c68662"])
        cx = 256
        drawing.ellipse((150, 45, 362, 345), fill=skin, outline="#262626", width=5)
        eye_y = 165 + rng.randint(-8, 8)
        for eye_x in (215, 297):
            drawing.ellipse((eye_x - 13, eye_y - 9, eye_x + 13, eye_y + 9), fill="#ffffff")
            drawing.ellipse((eye_x - 5, eye_y - 5, eye_x + 5, eye_y + 5), fill="#202020")
        drawing.line((cx, eye_y + 10, cx - 8, 230, cx + 12, 235), fill="#4d3326", width=4)
        if expression == "happy":
            drawing.arc((205, 230, 307, 300), 10, 170, fill="#5a2828", width=6)
        else:
            drawing.line((215, 275, 297, 275), fill="#5a2828", width=6)
        hair = rng.choice(["#191919", "#5b3a29", "#d6b04b", "#7a1f1f"])
        drawing.arc((148, 35, 364, 180), 180, 360, fill=hair, width=30)

    return face
def house(drawing: ImageDraw.ImageDraw, rng: random.Random) -> None:
    sky = rng.choice(["#8fc9ef", "#b7d7f0", "#d9c7e8"])
    drawing.rectangle((0, 0, 512, 250), fill=sky)
    drawing.rectangle((0, 250, 512, 384), fill="#7fa66a")
    x = rng.randint(100, 180)
    width = rng.randint(220, 290)
    drawing.rectangle((x, 150, x + width, 330), fill=rng.choice(["#d8a47f", "#e4d4b7", "#b8c4d4"]), outline="#333333", width=5)
    drawing.polygon([(x - 25, 155), (x + width // 2, 70), (x + width + 25, 155)], fill="#7a3f35", outline="#333333")
    drawing.rectangle((x + width // 2 - 25, 240, x + width // 2 + 25, 330), fill="#5b4031")
    for wx in (x + 45, x + width - 85):
        drawing.rectangle((wx, 195, wx + 40, 240), fill="#cae9ff", outline="#333333", width=3)


def landscape(drawing: ImageDraw.ImageDraw, rng: random.Random) -> None:
    drawing.rectangle((0, 0, 512, 230), fill=rng.choice(["#9ed5f2", "#f0c7a5", "#bfcbea"]))
    drawing.polygon([(0, 275), (130, 120), (250, 275)], fill="#667a62")
    drawing.polygon([(170, 280), (350, 100), (512, 280)], fill="#52695b")
    drawing.rectangle((0, 275, 512, 384), fill="#789b68")
    sun_x = rng.randint(40, 420)
    drawing.ellipse((sun_x, 40, sun_x + 55, 95), fill="#f3df7b")


def object_shape(drawing: ImageDraw.ImageDraw, rng: random.Random) -> None:
    drawing.rectangle((0, 0, 512, 384), fill="#c7c9cc")
    color = rng.choice(["#d44a4a", "#3b75c4", "#d8a62e", "#3d9b69"])
    shape = rng.choice(["circle", "square", "triangle"])
    if shape == "circle":
        drawing.ellipse((155, 80, 357, 282), fill=color, outline="#222222", width=7)
    elif shape == "square":
        drawing.rounded_rectangle((155, 80, 357, 282), radius=12, fill=color, outline="#222222", width=7)
    else:
        drawing.polygon([(256, 65), (380, 290), (132, 290)], fill=color, outline="#222222")


def word_image(word: str):
    def draw(drawing: ImageDraw.ImageDraw, rng: random.Random) -> None:
        drawing.rectangle((0, 0, 512, 384), fill="#e5e5e5")
        font = ImageFont.load_default(size=54)
        box = drawing.textbbox((0, 0), word, font=font)
        drawing.text(((512 - (box[2] - box[0])) / 2, 165), word, fill="#111111", font=font)

    return draw


def pattern(drawing: ImageDraw.ImageDraw, rng: random.Random) -> None:
    drawing.rectangle((0, 0, 512, 384), fill="#eeeeee")
    spacing = rng.choice([20, 24, 32, 40])
    color_a = rng.choice(["#202020", "#174a7e", "#7a1f3d"])
    color_b = rng.choice(["#f0c929", "#e85d3f", "#4da167"])
    for y in range(0, 384, spacing):
        for x in range(0, 512, spacing):
            color = color_a if (x // spacing + y // spacing) % 2 == 0 else color_b
            drawing.rectangle((x, y, x + spacing - 2, y + spacing - 2), fill=color)


def write_tone(identifier: str, title: str, frequencies: list[float], tags: list[str]) -> dict:
    path = OUTPUT / "audio" / f"{identifier}.wav"
    path.parent.mkdir(parents=True, exist_ok=True)
    duration_seconds = 6
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for sample_index in range(duration_seconds * SAMPLE_RATE):
            second = sample_index / SAMPLE_RATE
            frequency = frequencies[int(second * 2) % len(frequencies)]
            envelope = min(1.0, sample_index / 800) * min(1.0, (duration_seconds * SAMPLE_RATE - sample_index) / 800)
            value = int(0.25 * envelope * math.sin(2 * math.pi * frequency * second) * 32767)
            frames.extend(value.to_bytes(2, byteorder="little", signed=True))
        output.writeframes(frames)
    record = asset_record(identifier, title, "audio", "audio", path, tags, "audio/wav")
    record["duration_ms"] = duration_seconds * 1000
    record["sample_rate_hz"] = SAMPLE_RATE
    return record


def asset_record(
    identifier: str,
    title: str,
    category: str,
    modality: str,
    path: Path,
    tags: list[str],
    mime_type: str,
) -> dict:
    relative = path.relative_to(ROOT / "frontend" / "public").as_posix()
    return {
        "id": identifier,
        "title": title,
        "category": category,
        "modality": modality,
        "tags": tags,
        "public_path": f"/{relative}",
        "object_key": f"stimulus-library/v1/{path.relative_to(OUTPUT).as_posix()}",
        "mime_type": mime_type,
        "sha256": sha256(path),
        "license": "CC0-1.0",
        "license_url": LICENSE_URL,
        "creator": "Cortex Lab procedural stimulus generator",
        "source_url": "https://github.com/",
        "attribution": "Cortex Lab procedural stimulus, CC0 1.0",
        "redistribution_permitted": True,
        "generated": True,
    }


def generate() -> list[dict]:
    assets = []
    for index in range(40):
        expression = "neutral" if index < 20 else "happy"
        assets.append(
            save_image(
                f"face-{index + 1:03}",
                "faces",
                f"{expression.title()} schematic face {index + 1}",
                face_with_expression(expression),
                ["face", "social", expression, "emotion"],
            )
        )
    for index in range(20):
        assets.append(save_image(f"house-{index + 1:03}", "scenes", f"House scene {index + 1}", house, ["house", "scene"]))
    for index in range(20):
        assets.append(save_image(f"landscape-{index + 1:03}", "scenes", f"Landscape scene {index + 1}", landscape, ["landscape", "scene"]))
    for index in range(40):
        assets.append(save_image(f"object-{index + 1:03}", "objects", f"Geometric object {index + 1}", object_shape, ["object", "shape"]))
    words = [
        "BRAIN", "LANGUAGE", "MEMORY", "VISION", "MUSIC", "HOUSE", "FACE", "RIVER", "MOTION", "OBJECT",
        "COLOR", "SOUND", "STORY", "LIGHT", "SPACE", "THOUGHT", "VOICE", "SCENE", "FOCUS", "REST",
    ]
    for index in range(40):
        word = words[index % len(words)]
        assets.append(save_image(f"word-{index + 1:03}", "words", f"Rendered word {word} {index + 1}", word_image(word), ["word", "reading"]))
    for index in range(40):
        assets.append(save_image(f"pattern-{index + 1:03}", "patterns", f"Abstract pattern {index + 1}", pattern, ["pattern", "retinotopy"]))
    assets.extend(
        [
            write_tone("music-major-01", "Major arpeggio", [261.63, 329.63, 392.00, 523.25], ["music", "instrumental"]),
            write_tone("music-minor-01", "Minor arpeggio", [220.00, 261.63, 329.63, 440.00], ["music", "instrumental"]),
            write_tone("auditory-control-01", "Auditory control tones", [180.0, 240.0, 300.0], ["audio", "control"]),
            write_tone("auditory-control-02", "Auditory control pulses", [320.0, 160.0], ["audio", "control"]),
        ]
    )
    CATALOG.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "catalog_version": "v1",
                "license_policy": "cc0-public-domain",
                "asset_count": len(assets),
                "assets": assets,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return assets


if __name__ == "__main__":
    generated = generate()
    print(f"Generated {len(generated)} assets in {OUTPUT}")
