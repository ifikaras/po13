#!/usr/bin/env python3
"""Generate kids YouTube videos from episode scripts."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import subprocess
import sys
import textwrap
import wave
from pathlib import Path

import edge_tts
import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFont
from moviepy import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
    vfx,
)

ROOT = Path(__file__).resolve().parent.parent


def load_config() -> dict:
    with open(ROOT / "config" / "channel.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_episode(episode_dir: Path) -> dict:
    with open(episode_dir / "script.json", encoding="utf-8") as f:
        return json.load(f)


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def find_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def fit_image(image_path: Path, width: int, height: int) -> Image.Image:
    img = Image.open(image_path).convert("RGBA")
    scale = max(width / img.width, height / img.height)
    new_size = (int(img.width * scale), int(img.height * scale))
    img = img.resize(new_size, Image.Resampling.LANCZOS)
    left = (img.width - width) // 2
    top = (img.height - height) // 2
    return img.crop((left, top, left + width, top + height))


def create_scene_frame(
    image_path: Path,
    title: str,
    subtitle: str,
    config: dict,
    width: int,
    height: int,
) -> Image.Image:
    branding = config["branding"]
    bg = Image.new("RGB", (width, height), hex_to_rgb(branding["background_color"]))
    draw = ImageDraw.Draw(bg)

    # Soft gradient overlay at bottom for text readability
    gradient = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(gradient)
    for y in range(height // 2, height):
        alpha = int(180 * ((y - height // 2) / (height // 2)) ** 1.2)
        gdraw.line([(0, y), (width, y)], fill=(255, 255, 255, alpha))
    bg = Image.alpha_composite(bg.convert("RGBA"), gradient).convert("RGB")

    scene_img = fit_image(image_path, width, height)
    bg.paste(scene_img, (0, 0))

    draw = ImageDraw.Draw(bg)

    # Decorative top bar
    bar_height = 18
    draw.rectangle([0, 0, width, bar_height], fill=hex_to_rgb(branding["primary_color"]))
    draw.rectangle([0, bar_height, width, bar_height + 8], fill=hex_to_rgb(branding["secondary_color"]))
    draw.rectangle([0, bar_height + 8, width, bar_height + 14], fill=hex_to_rgb(branding["accent_color"]))

    title_font = find_font(78, bold=True)
    subtitle_font = find_font(48, bold=False)

    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_w = title_bbox[2] - title_bbox[0]
    title_x = (width - title_w) // 2
    title_y = height - 220

    # Title pill background
    pad_x, pad_y = 36, 18
    draw.rounded_rectangle(
        [
            title_x - pad_x,
            title_y - pad_y,
            title_x + title_w + pad_x,
            title_y + (title_bbox[3] - title_bbox[1]) + pad_y,
        ],
        radius=28,
        fill=hex_to_rgb(branding["primary_color"]),
    )
    draw.text((title_x, title_y), title, font=title_font, fill=(255, 255, 255))

    sub_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
    sub_w = sub_bbox[2] - sub_bbox[0]
    sub_x = (width - sub_w) // 2
    sub_y = title_y + 95
    draw.text((sub_x, sub_y), subtitle, font=subtitle_font, fill=hex_to_rgb(branding["font_title"]))

    # Channel watermark
    watermark_font = find_font(28, bold=True)
    draw.text((40, 40), config["channel"]["name"], font=watermark_font, fill=(255, 255, 255))

    return bg


async def synthesize_narration(text: str, voice: str, output_path: Path) -> None:
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))


def generate_background_music(duration: float, output_path: Path, sample_rate: int = 44100) -> None:
    """Generate a simple cheerful loop suitable for kids content."""
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)

    # C major pentatonic melody pattern (looping)
    notes_hz = [261.63, 293.66, 329.63, 392.00, 440.00, 392.00, 329.63, 293.66]
    beat = 0.55
    signal = np.zeros_like(t)

    for i, freq in enumerate(notes_hz * math.ceil(int(duration / beat) + 1)):
        start = i * beat
        end = start + beat * 0.92
        mask = (t >= start) & (t < end)
        if not mask.any():
            break
        local_t = t[mask] - start
        envelope = np.sin(np.pi * local_t / (beat * 0.92)) ** 0.7
        signal[mask] += 0.09 * np.sin(2 * np.pi * freq * local_t) * envelope
        signal[mask] += 0.04 * np.sin(2 * np.pi * freq * 2 * local_t) * envelope

    # Soft pad
    pad = 0.025 * np.sin(2 * np.pi * 130.81 * t) + 0.015 * np.sin(2 * np.pi * 196.0 * t)
    signal = np.clip(signal + pad, -1.0, 1.0)

    pcm = (signal * 32767 * 0.55).astype(np.int16)
    with wave.open(str(output_path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


def build_scene_clip(
    scene: dict,
    assets_dir: Path,
    cache_dir: Path,
    config: dict,
    width: int,
    height: int,
    fps: int,
) -> CompositeVideoClip:
    image_path = assets_dir / scene["image"]
    frame_path = cache_dir / f"{scene['id']}_frame.png"
    audio_path = cache_dir / f"{scene['id']}.mp3"

    frame = create_scene_frame(
        image_path,
        scene.get("on_screen", ""),
        scene.get("subtitle", ""),
        config,
        width,
        height,
    )
    frame.save(frame_path)

    voice = config["channel"]["voice"]
    if scene["id"] == "intro":
        voice = config["channel"].get("voice_intro", voice)

    asyncio.run(synthesize_narration(scene["narration"], voice, audio_path))

    audio = AudioFileClip(str(audio_path))
    duration = min(audio.duration + 0.6, config["video"]["max_duration_seconds"])

    img_clip = (
        ImageClip(str(frame_path))
        .with_duration(duration)
        .with_fps(fps)
        .with_effects([vfx.FadeIn(0.4), vfx.FadeOut(0.4)])
    )

    # Gentle zoom for visual interest
    def zoom(get_frame, t):
        frame_arr = get_frame(t)
        return frame_arr

    clip = img_clip.with_audio(audio)
    return clip


def create_thumbnail(episode: dict, assets_dir: Path, branding_dir: Path, output_path: Path, config: dict) -> None:
    width, height = 1280, 720
    base = fit_image(assets_dir / "intro.png", width, height).convert("RGBA")
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(height // 3, height):
        alpha = int(200 * ((y - height // 3) / (2 * height / 3)))
        draw.line([(0, y), (width, y)], fill=(255, 107, 157, alpha))
    composed = Image.alpha_composite(base, overlay)

    draw = ImageDraw.Draw(composed)
    title_font = find_font(86, bold=True)
    sub_font = find_font(44, bold=True)

    title = episode.get("thumbnail_text", episode["title"])
    draw.rounded_rectangle([60, 420, width - 60, 620], radius=30, fill=(255, 107, 157, 230))
    draw.text((90, 450), title, font=title_font, fill=(255, 255, 255))
    draw.text((90, 560), config["channel"]["name"], font=sub_font, fill=(255, 230, 109))

    composed.convert("RGB").save(output_path)


def generate_video(episode_dir: Path, output_name: str | None = None) -> Path:
    config = load_config()
    episode = load_episode(episode_dir)
    assets_dir = episode_dir / "assets"
    cache_dir = episode_dir / ".cache"
    cache_dir.mkdir(exist_ok=True)
    output_dir = ROOT / "output"
    output_dir.mkdir(exist_ok=True)

    width = config["video"]["width"]
    height = config["video"]["height"]
    fps = config["video"]["fps"]

    print(f"Creating: {episode['title']}")

    clips = []
    total_duration = 0.0
    max_duration = config["video"]["max_duration_seconds"]

    for scene in episode["scenes"]:
        if total_duration >= max_duration:
            break
        print(f"  -> Scene: {scene['id']}")
        clip = build_scene_clip(scene, assets_dir, cache_dir, config, width, height, fps)
        remaining = max_duration - total_duration
        if clip.duration > remaining:
            clip = clip.subclipped(0, remaining)
        clips.append(clip)
        total_duration += clip.duration

    video = concatenate_videoclips(clips, method="compose")

    music_path = cache_dir / "background_music.wav"
    generate_background_music(video.duration + 1, music_path)
    music = AudioFileClip(str(music_path)).subclipped(0, video.duration)
    music = music.with_volume_scaled(10 ** (config["music"]["volume_db"] / 20))

    if video.audio:
        voice = video.audio.with_volume_scaled(10 ** (config["music"]["voice_volume_db"] / 20))
        final_audio = CompositeAudioClip([music, voice])
    else:
        final_audio = music

    video = video.with_audio(final_audio)

    slug = output_name or f"episode_{episode['id']}_{episode_dir.name}"
    output_path = output_dir / f"{slug}.mp4"

    print(f"  -> Exporting video ({video.duration:.1f}s)...")
    video.write_videofile(
        str(output_path),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
        logger="bar",
    )

    thumb_path = output_dir / f"{slug}_thumbnail.png"
    create_thumbnail(episode, assets_dir, ROOT / "branding", thumb_path, config)
    print(f"Done: {output_path}")
    print(f"Thumbnail: {thumb_path}")

    # Save YouTube metadata (SEO-friendly)
    yt_title = episode.get("youtube_title") or f"{episode['title']} | {config['channel']['name']}"
    meta = {
        "title": yt_title,
        "description": episode["description"] + f"\n\nSubscribe for more fun learning videos!\n{config['channel']['name']}\n\n#kids #toddlers #preschool #learnanimals #forestanimals #educational",
        "tags": episode.get("tags", []),
        "duration_seconds": round(video.duration, 1),
    }
    meta_path = output_dir / f"{slug}_youtube.txt"
    meta_path.write_text(
        f"Title:\n{meta['title']}\n\n"
        f"Description:\n{meta['description']}\n\n"
        f"Tags: {', '.join(meta['tags'])}\n\n"
        f"Duration: {meta['duration_seconds']} seconds\n",
        encoding="utf-8",
    )

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Generate kids YouTube episode video")
    parser.add_argument(
        "episode",
        nargs="?",
        default="01_forest_animals",
        help="Episode folder name under episodes/",
    )
    parser.add_argument("--output-name", help="Custom output filename slug")
    args = parser.parse_args()

    episode_dir = ROOT / "episodes" / args.episode
    if not episode_dir.exists():
        print(f"Episode not found: {episode_dir}", file=sys.stderr)
        sys.exit(1)

    generate_video(episode_dir, args.output_name)


if __name__ == "__main__":
    main()
