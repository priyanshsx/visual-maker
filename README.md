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

For the 3D demo videos (device_demo) you also need Node.js, then install Remotion once:

```bash
brew install node
cd remotion && npm install && cd ..
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

## 3D product demos (device_demo, made with Remotion)

A screenshot on a floating 3D screen. The camera glides to the points you pick while a
caption explains each one, then closes on your title and a call-to-action button.
Length: 2.2s intro + 3s per step + 3s close (or set `duration`). YAML file only:

```yaml
- template: device_demo
  name: correlations-demo
  sizes: [portrait, landscape]
  kicker: New in Quartermaster          # small label on the intro (40)
  title: "Correlations. *Now live.*"     # intro and closing line (70)
  image: correlations-chart.png          # main screenshot in inputs/<client>/
  cta: Free at app.quartermasterlabs.com # closing button (60, optional)
  look: cinematic                        # or clean (default): flat background
  steps:                                 # 1 to 6
    - caption: "Each asset's rolling correlation with *Bitcoin*"   # (90)
    - caption: "*S&P 500, Apple and gold* on one chart"
      focus: [0.165, 0.2]   # across, down: 0 = left/top, 1 = right/bottom
      zoom: 2.4             # 1 = whole screenshot, up to 3
      marker: true          # pulse a ring on the focus point
      # image: other.png    # optional: another screenshot for this step
```

```bash
python -m visuals --client quartermaster --file correlations-demo.yaml
```

`look: cinematic` adds fog (the screen emerges from it), a wet-looking reflective floor,
floating dust, a soft light beam, glow on bright lines, a slow handheld camera, film grain,
a vignette and titles that come into focus. No 3D models needed. The pieces live in
`remotion/src/cinematic/` so other videos can reuse them.

Takes a few minutes per size. To fine-tune timing and look in the browser, add `--html`
(keeps a `.props.json` next to the video), then:

```bash
cd remotion && npx remotion studio src/index.ts --props=../outputs/<client>/<date>/<name>_<size>.props.json
```

## Event recap image (event_recap, made with Remotion)

One rich portrait image (1080x1350, saved at 2x for sharpness) about an event, like a
magazine page: event badge, two-line headline, intro, up to 3 stat chips and a 3D hero
(steel bearing + lubricant drop), 2–4 speaker cards, a dark "bigger picture" band with up
to 4 themes, and a closing line. See `inputs/vizcorn/lubricant-expo-recap.yaml`.
Icons: flask, leaf, globe, shield, recycle, thermometer, droplet, bearing, mic, molecule,
chart, people, scale, gear. Add `video: true` for a 5-second animated version too.

The 3D code lives in `remotion/src/` (React + Three.js). Remotion is free for individuals and
companies of up to 3 people; bigger teams need a Remotion company licence.

## Templates

| Template | Fields (max characters) |
|---|---|
| quote | quote (280), author (60), role (80) |
| stat | stat (12), headline (110), body (240), source (120) |
| carousel | 2–12 slides, each: title (90), body (320). First slide is the cover. |
| stat_motion | as stat (animated, see below) |
| quote_motion | as quote (animated, see below) |
| device_demo | title (70), image, 1–6 steps, kicker (40), cta (60) (3D, see below) |
| event_recap | badge (50), title (60), title_accent (60), intro (230), stats (≤3), 2–4 cards, big_picture, closing (130) |

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
visuals/     the code (cli, brand, specs, render, video, remotion_bridge)
remotion/    the 3D video project (React + Three.js, rendered by Remotion)
inputs/      your words, one YAML file per batch
outputs/     finished images (not in git)
tests/       automatic checks
```
