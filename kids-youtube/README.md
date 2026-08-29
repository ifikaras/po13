# Happy Little Learners — Kids YouTube Channel

Automated production of short, simple, happy educational videos (3–4 min) for toddlers and preschoolers. English narration, SEO-friendly titles.

## What's included

| Item | Description |
|------|-------------|
| **Channel** | Happy Little Learners |
| **Episode 1** | Forest Animals for Kids (~3 min) |
| **Branding** | Logo + banner for YouTube |
| **Pipeline** | Images → narration → music → MP4 export |

## Quick start

```bash
cd kids-youtube
pip install -r requirements.txt
python3 src/generate_video.py
```

Output goes to `output/`.

## Create your YouTube channel

1. **Create account** — [youtube.com](https://www.youtube.com) → Sign in with Google
2. **Create channel** — Profile → Create channel → Name: **Happy Little Learners**
3. **Branding** (YouTube Studio → Customization):
   - **Profile picture:** `branding/channel_logo.png`
   - **Banner:** `branding/channel_banner.png`
4. **Upload video** (YouTube Studio → Create → Upload):
   - File: `output/episode_01_01_forest_animals.mp4`
   - Thumbnail: `output/episode_01_01_forest_animals_thumbnail.png`
   - Title, description, tags: `output/episode_01_01_forest_animals_youtube.txt`
5. **Kids settings:**
   - Enable **Made for Kids**
   - Consider disabling comments (recommended for young kids)
   - Category: **Education**

## SEO tips (easy to find on YouTube)

Use the ready-made title from `_youtube.txt`. It includes popular search terms:

- `forest animals for kids`
- `learn animal names`
- `animals for toddlers`
- `preschool learning`

## New episode

```bash
python3 src/new_episode.py 03_numbers --id 03 --title "Numbers for Kids"
```

Then:
1. Add PNG images to `episodes/03_numbers/assets/`
2. Edit `script.json` (scenes, narration, on-screen text)
3. Run: `python3 src/generate_video.py 03_numbers`

## Episode ideas

| # | Topic | Folder |
|---|-------|--------|
| 02 | Learn Colors | `02_colors` |
| 03 | Numbers 1–10 | `03_numbers` |
| 04 | Body Parts | `04_body_parts` |
| 05 | Fruits | `05_fruits` |
| 06 | Weather | `06_weather` |

## Settings

Edit `config/channel.yaml` for voice, colors, and video resolution.

---

Good luck with your channel!
