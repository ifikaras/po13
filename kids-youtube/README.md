# 🎬 Μικροί Εξερευνητές — Παιδικό YouTube Κανάλι

Αυτόματη παραγωγή εκπαιδευτικών βίντεο 3–4 λεπτών για παιδιά, στα ελληνικά.

## Τι περιλαμβάνει

| Στοιχείο | Περιγραφή |
|----------|-----------|
| **Κανάλι** | Μικροί Εξερευνητές |
| **Επεισόδιο 1** | Τα Ζώα του Δάσους (~3 λεπτά) |
| **Branding** | Logo + banner για YouTube |
| **Pipeline** | Εικόνες → αφήγηση → μουσική → export MP4 |

## Γρήγορη εκκίνηση

```bash
cd kids-youtube
pip install -r requirements.txt
python3 src/generate_video.py
```

Το βίντεο δημιουργείται στο `output/`.

## Δημιουργία YouTube καναλιού (εσύ)

1. **Δημιουργία λογαριασμού** — [youtube.com](https://www.youtube.com) → Σύνδεση με Google
2. **Δημιουργία καναλιού** — Προφίλ → Δημιουργία καναλιού → Όνομα: **Μικροί Εξερευνητές**
3. **Branding** (YouTube Studio → Προσαρμογή):
   - **Εικόνα προφίλ:** `branding/channel_logo.png`
   - **Banner:** `branding/channel_banner.png`
4. **Ανέβασμα βίντεο** (YouTube Studio → Δημιουργία → Ανέβασμα):
   - Αρχείο: `output/episode_01_01_ta_zoa_tou_dasous.mp4`
   - Thumbnail: `output/episode_01_01_ta_zoa_tou_dasous_thumbnail.png`
   - Τίτλος/περιγραφή/tags: `output/episode_01_01_ta_zoa_tou_dasous_youtube.txt`
5. **Ρυθμίσεις για παιδιά:**
   - Ενεργοποίησε **«Φτιαγμένο για παιδιά»** (Made for Kids)
   - Απενεργοποίησε σχόλια αν το θέλεις (συνιστάται για μικρά παιδιά)
   - Κατηγορία: **Εκπαίδευση**

## Νέο επεισόδιο

```bash
python3 src/new_episode.py 03_ta_noumera --id 03 --title "Μαθαίνω τους Αριθμούς"
```

Μετά:
1. Πρόσθεσε εικόνες PNG στο `episodes/03_ta_noumera/assets/`
2. Επεξεργάσου το `script.json` (σκηνές, αφήγηση, κείμενα οθόνης)
3. Τρέξε: `python3 src/generate_video.py 03_ta_noumera`

## Δομή σεναρίου (`script.json`)

Κάθε σκηνή έχει:
- `image` — αρχείο εικόνας στο `assets/`
- `narration` — κείμενο αφήγησης (TTS ελληνικά)
- `on_screen` — τίτλος στην οθόνη
- `subtitle` — υπότιτλος

**Στόχος διάρκειας:** 3–4 λεπτά (240 δευτ. max). Κάθε σκηνή ≈ 20–35 δευτερόλεπτα.

## Ιδέες για επόμενα επεισόδια

| # | Θέμα | Slug |
|---|------|------|
| 02 | Μαθαίνω τα Χρώματα | `02_ta_chromata` |
| 03 | Οι Αριθμοί 1–10 | `03_ta_noumera` |
| 04 | Τα Μέρη του Σώματος | `04_to_soma` |
| 05 | Τα Φρούτα | `05_ta_frukta` |
| 06 | Ο Καιρός | `06_o_kairos` |

## Ρυθμίσεις καναλιού

Επεξεργάσου `config/channel.yaml` για χρώματα, φωνή TTS, ανάλυση βίντεο.

## Τεχνολογίες

- **TTS:** Microsoft Edge (ελληνική φωνή Athina/Nestoras)
- **Video:** MoviePy + FFmpeg
- **Εικόνες:** AI-generated + επεξεργασία Pillow
- **Μουσική:** Αυτόματα generated cheerful background loop

---

Καλή επιτυχία με το κανάλι σου! 🌟
