# visual-maker

Branded images from your own words. You write the text; the tool applies the client's
colours, font and logo and renders sharp PNGs (and a PDF for carousels).

## Setup (once)

```bash
brew install ffmpeg            # for videos
source .venv/bin/activate
pip install -e .
playwright install chromium
python -m pytest -q
```

## Make images

Write your words in `inputs/<client>/<file>.yaml` (see `inputs/vizcorn/example.yaml`), then:

```bash
python -m visuals --client vizcorn --file example.yaml
```

Or one image straight from the command line:

```bash
python -m visuals --client vizcorn --template quote --quote "Clean data first." --author VizCorn
python -m visuals --client vizcorn --template stat --stat "42%" --headline "..." --source "..."
python -m visuals --client vizcorn --template carousel --slide "Cover title | subtitle" --slide "Point one | detail"
```

Images land in `outputs/<client>/<today>/`.

| Option | What it does |
|---|---|
| `--size portrait` / `square` / `landscape` / `story` | Output size (see below). Repeat for several. |
| `--out <folder>` | Save somewhere else |
| `--html` | Also save the HTML, to check a design in a browser |
| `--video` | Also make a slideshow MP4 of every entry |
| `--seconds 4` | Seconds per slide in videos (default 3.5) |
| `--music track.mp3` | Background music for videos (file in `inputs/<client>/`) |

Sizes: `portrait` 1080×1350 (default), `square` 1080×1080, `landscape` 1200×675, `story` 1080×1920.

## Videos

Add `video: true` to any entry (or use `--video`). Each slide zooms in slowly and the next
slide swipes in, like a carousel; a quote or stat card becomes a single zooming shot.
Optional `seconds_per_slide` and `music`. The video slides leave out the "Swipe" hint.

Needs FFmpeg once: `brew install ffmpeg`. A 5-slide video takes about 15 seconds to make.

## Motion templates

Animated videos (MP4 + a poster PNG of the final frame, for the video thumbnail):

| Template | What moves | Fields |
|---|---|---|
| stat_motion | The number counts up to your exact figure, then headline, body and source slide in | as stat |
| quote_motion | The quote appears line by line; `*emphasised*` words turn brand colour | as quote |

Optional `duration` (3–30 seconds; default: as long as the animation needs plus a 2.5s hold)
and `music`. Stats like "75%", "€1.2M", "1,250" count up; "3 in 4", "Q3" or a year fade in
instead, because counting them would look wrong. About 10 seconds to make a 6-second video.

```bash
python -m visuals --client vizcorn --template stat_motion --stat "75%" --headline "..." --source "..."
python -m visuals --client vizcorn --template quote_motion --quote "Fix the *data* first." --author VizCorn
```

`*asterisks*` around words also work in the static quote card.

## Templates

| Template | Fields (max characters) |
|---|---|
| quote | quote (280), author (60), role (80) |
| stat | stat (12), headline (110), body (240), source (120) |
| carousel | 2–12 slides, each: title (90), body (320). First slide is the cover. |
| stat_motion | as stat (animated, see below) |
| quote_motion | as quote (animated, see below) |

Text shrinks automatically to fit. If it still doesn't fit, the image is not made and you get
a message saying which text to shorten.

**Rule:** only use numbers you can back up, and put the source in `source`.

## Add a client

Create `brands/<client>/brand.yaml` (copy `brands/vizcorn/brand.yaml`) and drop the logo file
next to it. No code changes.

## Layout

```
brands/      one folder per client: brand.yaml + logo
fonts/       bundled font files (Inter, SIL Open Font License)
templates/   HTML/CSS designs shared by all clients
visuals/     the code (cli, brand, specs, render, video)
inputs/      your words, one YAML file per batch
outputs/     finished images (not in git)
tests/       automatic checks
```
