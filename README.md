# visual-maker

Branded images from your own words. You write the text; the tool applies the client's
colours, font and logo and renders sharp PNGs (and a PDF for carousels).

## Setup (once)

```bash
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
| `--size portrait` / `square` / `landscape` | 1080×1350 (default), 1080×1080, 1200×675. Repeat for several. |
| `--out <folder>` | Save somewhere else |
| `--html` | Also save the HTML, to check a design in a browser |

## Templates

| Template | Fields (max characters) |
|---|---|
| quote | quote (280), author (60), role (80) |
| stat | stat (12), headline (110), body (240), source (120) |
| carousel | 2–12 slides, each: title (90), body (320). First slide is the cover. |

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
visuals/     the code (cli, brand, specs, render)
inputs/      your words, one YAML file per batch
outputs/     finished images (not in git)
tests/       automatic checks
```
