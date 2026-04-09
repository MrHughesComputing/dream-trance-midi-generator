from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from mido import Message, MidiFile, MidiTrack, MetaMessage, bpm2tempo
from pathlib import Path
import tempfile
import zipfile

app = FastAPI(title="Dream Trance MIDI Generator V2.8")
app.mount("/static", StaticFiles(directory="static"), name="static")

TICKS = 480
BAR_TICKS = TICKS * 4

STEMS = [
    "kick",
    "clap_snare",
    "hats",
    "offbeat_bass",
    "rolling_bass",
    "arp",
    "pluck",
    "pad",
    "supersaw_chords",
    "lead",
    "countermelody",
    "strings",
    "piano",
    "vocal_melody",
]

NOTE = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
    "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11
}

SCALES = {
    "minor": [0, 2, 3, 5, 7, 8, 10]
}

PROGRESSIONS = {
    "Emotional Lift (i-VI-III-VII)": [1, 6, 3, 7],
    "Classic Uplift (i-iv-VI-VII)": [1, 4, 6, 7],
    "Festival Drive (VI-III-VII-i)": [6, 3, 7, 1],
    "Hopeful Pull (i-v-VI-iv)": [1, 5, 6, 4],
}

ARRANGEMENTS = {
    "Club/Extended": [
        ("Intro", 16), ("Verse", 16), ("Build", 16), ("Drop 1", 32),
        ("Breakdown", 24), ("Build 2", 16), ("Drop 2", 32), ("Outro", 16)
    ],
    "Radio/Compact": [
        ("Intro", 8), ("Verse", 16), ("Build", 8), ("Drop 1", 24),
        ("Breakdown", 16), ("Build 2", 8), ("Drop 2", 24), ("Outro", 8)
    ],
    "Breakdown Focused": [
        ("Intro", 12), ("Verse", 16), ("Build", 12), ("Drop 1", 24),
        ("Breakdown", 32), ("Build 2", 16), ("Drop 2", 24), ("Outro", 12)
    ],
}

ENERGY_LEVELS = {
    "Low": 0.85,
    "Medium": 1.0,
    "High": 1.12,
}

VOCAL_RANGES = {
    "Female Soprano": (72, 84),
    "Female Airy": (69, 81),
    "Male Tenor": (60, 72),
}

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dream Trance MIDI Generator V2.8</title>
  <style>
    :root {
      --bg: #061121;
      --bg-soft: #0b1c38;
      --panel: rgba(12, 25, 51, 0.88);
      --panel-2: rgba(17, 34, 68, 0.92);
      --border: rgba(151, 180, 255, 0.18);
      --text: #edf3ff;
      --muted: #b8c8ee;
      --accent: #8fb0ff;
      --accent-2: #c89dff;
      --success: #88e2c4;
      --shadow: 0 18px 44px rgba(0,0,0,0.34);
      --radius: 22px;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: Inter, Arial, sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(143,176,255,0.16), transparent 28%),
        radial-gradient(circle at top right, rgba(200,157,255,0.14), transparent 24%),
        linear-gradient(180deg, #04101d 0%, #071429 42%, #0a1730 100%);
      min-height: 100vh;
    }

    .shell {
      max-width: 1440px;
      margin: 0 auto;
      padding: 28px;
    }

    .hero {
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 24px;
      margin-bottom: 24px;
      align-items: stretch;
    }

    .hero-card,
    .panel,
    .stat,
    .tip {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }

    .hero-card {
      padding: 30px;
      position: relative;
      overflow: hidden;
    }

    .hero-card::after {
      content: "";
      position: absolute;
      right: -40px;
      bottom: -50px;
      width: 260px;
      height: 260px;
      background: radial-gradient(circle, rgba(143,176,255,0.18), transparent 65%);
      pointer-events: none;
    }

    .eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(143,176,255,0.12);
      border: 1px solid rgba(143,176,255,0.22);
      color: var(--muted);
      font-size: 13px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      margin-bottom: 14px;
    }

    h1 {
      margin: 0 0 12px;
      font-size: clamp(34px, 4vw, 56px);
      line-height: 1.04;
      letter-spacing: -0.03em;
    }

    .sub {
      margin: 0;
      font-size: 18px;
      line-height: 1.6;
      color: var(--muted);
      max-width: 820px;
    }

    .hero-side {
      display: grid;
      gap: 16px;
    }

    .stat {
      padding: 20px;
      background: var(--panel-2);
    }

    .stat-label {
      color: var(--muted);
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 8px;
    }

    .stat-value {
      font-size: 22px;
      font-weight: 700;
      line-height: 1.35;
    }

    .main-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.1fr) 360px;
      gap: 24px;
      align-items: start;
    }

    .panel {
      padding: 24px;
    }

    .panel h2 {
      margin: 0 0 8px;
      font-size: 24px;
    }

    .panel p {
      margin: 0 0 22px;
      color: var(--muted);
      line-height: 1.6;
    }

    .section {
      margin-bottom: 24px;
      padding: 20px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid rgba(255,255,255,0.05);
    }

    .section:last-child {
      margin-bottom: 0;
    }

    .section-title {
      margin: 0 0 14px;
      font-size: 16px;
      font-weight: 700;
      letter-spacing: 0.01em;
    }

    .form-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }

    .field {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .field.full {
      grid-column: 1 / -1;
    }

    label {
      font-size: 14px;
      font-weight: 600;
      color: #dce7ff;
    }

    input,
    select {
      width: 100%;
      border: 1px solid rgba(255,255,255,0.09);
      background: rgba(4, 11, 24, 0.72);
      color: var(--text);
      border-radius: 14px;
      padding: 14px 14px;
      font-size: 15px;
      outline: none;
      transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }

    input:focus,
    select:focus {
      border-color: rgba(143,176,255,0.72);
      box-shadow: 0 0 0 4px rgba(143,176,255,0.12);
    }

    .actions {
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
      margin-top: 20px;
    }

    button {
      border: 0;
      border-radius: 16px;
      padding: 15px 22px;
      font-size: 15px;
      font-weight: 700;
      cursor: pointer;
      transition: transform 0.18s ease, box-shadow 0.18s ease, opacity 0.18s ease;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
    }

    button:hover {
      transform: translateY(-1px);
    }

    .primary {
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      color: #081224;
      box-shadow: 0 10px 22px rgba(143,176,255,0.24);
      min-width: 220px;
    }

    .secondary {
      background: rgba(255,255,255,0.04);
      border: 1px solid rgba(255,255,255,0.08);
      color: var(--text);
    }

    .sidebar {
      display: grid;
      gap: 18px;
      position: sticky;
      top: 24px;
    }

    .tip {
      padding: 20px;
    }

    .tip h3 {
      margin: 0 0 10px;
      font-size: 17px;
    }

    .tip p,
    .tip li {
      color: var(--muted);
      line-height: 1.55;
      font-size: 14px;
    }

    .tip ul {
      margin: 0;
      padding-left: 18px;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(136,226,196,0.1);
      border: 1px solid rgba(136,226,196,0.22);
      color: var(--success);
      font-size: 13px;
      font-weight: 700;
      margin-top: 10px;
    }

    .stem-list {
      columns: 2;
      gap: 18px;
      padding-left: 18px;
      margin: 0;
    }

    .stem-list li {
      margin-bottom: 8px;
      break-inside: avoid;
      color: var(--muted);
    }

    .quick-box {
      display: grid;
      gap: 10px;
    }

    .quick-item {
      background: rgba(255,255,255,0.04);
      border: 1px solid rgba(255,255,255,0.08);
      padding: 14px 16px;
      border-radius: 16px;
      color: var(--text);
      font-size: 14px;
      font-weight: 600;
    }

    @media (max-width: 1100px) {
      .hero,
      .main-grid {
        grid-template-columns: 1fr;
      }

      .sidebar {
        position: static;
      }
    }

    @media (max-width: 720px) {
      .shell {
        padding: 16px;
      }

      .hero-card,
      .panel,
      .stat,
      .tip {
        border-radius: 18px;
      }

      .form-grid {
        grid-template-columns: 1fr;
      }

      .stem-list {
        columns: 1;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="hero-card">
        <div class="eyebrow">Dream Trance MIDI Generator • V2.8 Anthem Engine</div>
        <h1>Build uplifting trance MIDI with a stronger anthem hook and cleaner emotional payoff.</h1>
        <p class="sub">
          V2.8 tightens the lead identity, simplifies Drop 1, enlarges Drop 2, and improves breakdown recall so the final drop feels more earned and more memorable.
        </p>
        <div class="pill">Exports aligned full-length stems + combined arrangement MIDI</div>
      </div>

      <div class="hero-side">
        <div class="stat">
          <div class="stat-label">Primary use</div>
          <div class="stat-value">Anthem-style uplifting / melodic trance sketch generation</div>
        </div>
        <div class="stat">
          <div class="stat-label">Output</div>
          <div class="stat-value">Full arrangement MIDI + production notes + individual stems</div>
        </div>
        <div class="stat">
          <div class="stat-label">Best quick test</div>
          <div class="stat-value">138 BPM • F minor • Emotional Lift • Club/Extended</div>
        </div>
      </div>
    </section>

    <div class="main-grid">
      <section class="panel">
        <h2>Generator Control Panel</h2>
        <p>These controls are matched exactly to your current FastAPI backend.</p>

        <form method="post" action="/generate">
          <div class="section">
            <h3 class="section-title">Core settings</h3>
            <div class="form-grid">
              <div class="field">
                <label for="bpm">BPM</label>
                <input id="bpm" type="number" name="bpm" min="132" max="142" value="138">
              </div>

              <div class="field">
                <label for="key_root">Key Root</label>
                <select id="key_root" name="key_root">__KEY_OPTS__</select>
              </div>

              <div class="field full">
                <label for="progression">Progression</label>
                <select id="progression" name="progression">__PROG_OPTS__</select>
              </div>

              <div class="field">
                <label for="arrangement">Arrangement</label>
                <select id="arrangement" name="arrangement">__ARR_OPTS__</select>
              </div>

              <div class="field">
                <label for="energy">Energy</label>
                <select id="energy" name="energy">__ENERGY_OPTS__</select>
              </div>

              <div class="field full">
                <label for="vocalist">Vocalist</label>
                <select id="vocalist" name="vocalist">__VOCAL_OPTS__</select>
              </div>
            </div>

            <div class="actions">
              <button class="primary" type="submit">Generate MIDI Pack</button>
              <button class="secondary" type="reset">Reset Settings</button>
            </div>
          </div>
        </form>
      </section>

      <aside class="sidebar">
        <div class="tip">
          <h3>What changed in V2.8</h3>
          <ul>
            <li>One signature hook cell anchors the lead.</li>
            <li>Drop 1 is simpler and more memorable.</li>
            <li>Drop 2 is bigger, brighter, and more active.</li>
            <li>Reduced arp clutter in the first drop.</li>
            <li>Breakdown piano and lead recall are stronger.</li>
            <li>Countermelody only answers in stronger gaps.</li>
          </ul>
        </div>

        <div class="tip">
          <h3>Included stems</h3>
          <ul class="stem-list">
            __STEM_ITEMS__
          </ul>
        </div>

        <div class="tip">
          <h3>Recommended first test</h3>
          <div class="quick-box">
            <div class="quick-item">BPM: 138</div>
            <div class="quick-item">Key: F minor</div>
            <div class="quick-item">Progression: Emotional Lift</div>
            <div class="quick-item">Arrangement: Club/Extended</div>
            <div class="quick-item">Energy: Medium</div>
            <div class="quick-item">Vocalist: Female Soprano</div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</body>
</html>
"""


def html_page():
    html = HTML
    html = html.replace(
        "__KEY_OPTS__",
        "".join(f"<option>{k}</option>" for k in ["F", "F#", "G", "G#", "A", "A#", "C", "D"])
    )
    html = html.replace(
        "__PROG_OPTS__",
        "".join(f"<option>{p}</option>" for p in PROGRESSIONS)
    )
    html = html.replace(
        "__ARR_OPTS__",
        "".join(f"<option>{a}</option>" for a in ARRANGEMENTS)
    )
    html = html.replace(
        "__ENERGY_OPTS__",
        "".join(f"<option>{e}</option>" for e in ENERGY_LEVELS)
    )
    html = html.replace(
        "__VOCAL_OPTS__",
        "".join(f"<option>{v}</option>" for v in VOCAL_RANGES)
    )
    html = html.replace(
        "__STEM_ITEMS__",
        "".join(f"<li>{s}</li>" for s in STEMS)
    )
    return html


@app.get("/", response_class=HTMLResponse)
def home():
    return html_page()


def tick(beats: float) -> int:
    return int(round(beats * TICKS))


def bar_tick(bar_index: int) -> int:
    return bar_index * BAR_TICKS


def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def note_name_to_midi(root: str, degree: int, octave: int = 4, mode: str = "minor") -> int:
    scale = SCALES[mode]
    root_pc = NOTE[root]
    pc = (root_pc + scale[(degree - 1) % 7]) % 12
    return pc + 12 * (octave + 1)


def progression_chords(root: str, progression_name: str):
    degrees = PROGRESSIONS[progression_name]
    triad_map = {
        1: (1, 3, 5),
        2: (2, 4, 6),
        3: (3, 5, 7),
        4: (4, 6, 1),
        5: (5, 7, 2),
        6: (6, 1, 3),
        7: (7, 2, 4),
    }
    chords = []
    for degree in degrees:
        triad_degrees = triad_map[degree]
        triad = [note_name_to_midi(root, d, 4 if d not in (6, 7) else 3) for d in triad_degrees]
        triad = sorted(triad)
        chords.append({
            "degree": degree,
            "notes": triad,
            "root": triad[0],
            "third": triad[1],
            "fifth": triad[2],
        })
    return chords


def arrange_sections(arrangement_name: str):
    sections = []
    current_bar = 0
    for name, bars in ARRANGEMENTS[arrangement_name]:
        sections.append({
            "name": name,
            "bars": bars,
            "start_bar": current_bar,
            "end_bar": current_bar + bars,
        })
        current_bar += bars
    return sections


def section_type(name: str) -> str:
    n = name.lower()
    if "intro" in n:
        return "intro"
    if "verse" in n:
        return "verse"
    if "build" in n:
        return "build"
    if "drop" in n:
        return "drop"
    if "breakdown" in n:
        return "breakdown"
    if "outro" in n:
        return "outro"
    return "other"


def energy_profile(section_name: str, energy_factor: float):
    st = section_type(section_name)
    base = {
        "intro": {"velocity": 74, "density": 0.42},
        "verse": {"velocity": 82, "density": 0.56},
        "build": {"velocity": 94, "density": 0.80},
        "drop": {"velocity": 108, "density": 1.00},
        "breakdown": {"velocity": 76, "density": 0.48},
        "outro": {"velocity": 72, "density": 0.38},
        "other": {"velocity": 80, "density": 0.50},
    }[st]
    return {
        "velocity": clamp(int(base["velocity"] * energy_factor), 1, 124),
        "density": min(1.0, base["density"] * energy_factor),
    }


def add_events(event_list, start_tick_value: int, notes, length_tick: int, velocity: int = 90, channel: int = 0):
    if isinstance(notes, int):
        notes = [notes]
    for n in notes:
        event_list.append((start_tick_value, Message("note_on", note=int(n), velocity=int(velocity), channel=channel, time=0)))
        event_list.append((start_tick_value + length_tick, Message("note_off", note=int(n), velocity=0, channel=channel, time=0)))


def finalise_track(name: str, tempo: int, events, markers=None):
    track = MidiTrack()
    track.append(MetaMessage("track_name", name=name, time=0))
    track.append(MetaMessage("set_tempo", tempo=tempo, time=0))

    working_events = list(events)
    if markers:
        for t, text in markers:
            working_events.append((t, MetaMessage("marker", text=text, time=0)))

    working_events.sort(key=lambda x: (x[0], 0 if getattr(x[1], "type", "") == "note_off" else 1))
    last_time = 0
    for abs_time, msg in working_events:
        delta = max(0, int(abs_time - last_time))
        msg.time = delta
        track.append(msg)
        last_time = abs_time

    track.append(MetaMessage("end_of_track", time=1))
    return track


def choose_chord(chords, bar_number: int):
    return chords[bar_number % len(chords)]


def chord_tones_in_range(chord, low: int, high: int):
    tones = []
    for octave_shift in range(-2, 4):
        for base_note in chord["notes"]:
            n = base_note + octave_shift * 12
            if low <= n <= high:
                tones.append(n)
    return sorted(set(tones))


def scale_notes_in_range(root: str, low: int, high: int):
    notes = []
    for octave in range(1, 8):
        for degree in range(1, 8):
            n = note_name_to_midi(root, degree, octave)
            if low <= n <= high:
                notes.append(n)
    return sorted(set(notes))


def nearest_note_from_pool(target: int, pool):
    return min(pool, key=lambda x: (abs(x - target), x))


def build_signature_hook_cell(root: str, first_chord, second_chord):
    """
    Returns the core signature note set used across the anthem.
    The goal is to keep vocabulary tight and recognisable.
    """
    anchor = nearest_note_from_pool(note_name_to_midi(root, 5, 5), chord_tones_in_range(first_chord, 72, 84))
    support = nearest_note_from_pool(note_name_to_midi(root, 3, 5), chord_tones_in_range(first_chord, 70, 84))
    lift = nearest_note_from_pool(note_name_to_midi(root, 1, 6), chord_tones_in_range(second_chord, 72, 88))
    resolve = nearest_note_from_pool(note_name_to_midi(root, 1, 5), chord_tones_in_range(first_chord, 67, 81))
    return {
        "anchor": anchor,
        "support": support,
        "lift": lift,
        "resolve": resolve,
    }


def build_drop_blueprint(root: str, chords, drop_variant: int):
    """
    Signature cell:
    anchor -> support -> anchor -> lift

    Drop 1:
    tighter, fewer notes, stronger memory

    Drop 2:
    same identity, more lift and slightly more motion
    """
    signature = build_signature_hook_cell(root, chords[0], chords[1])

    if drop_variant == 2:
        return {
            0: [
                (0.00, 0.75, signature["anchor"]),
                (1.00, 0.50, signature["support"]),
                (2.00, 0.50, signature["anchor"]),
                (2.75, 0.25, signature["lift"]),
                (3.00, 0.75, signature["lift"]),
            ],
            1: [
                (0.00, 0.75, signature["anchor"]),
                (1.00, 0.50, signature["support"]),
                (2.00, 0.50, signature["anchor"]),
                (2.75, 0.25, signature["lift"]),
                (3.00, 0.75, signature["lift"]),
            ],
            2: [
                (0.00, 0.50, signature["anchor"]),
                (1.00, 0.50, signature["support"]),
                (1.75, 0.50, signature["lift"]),
                (2.50, 0.50, signature["support"]),
                (3.25, 0.50, signature["anchor"]),
            ],
            3: [
                (0.00, 0.75, signature["support"]),
                (1.00, 0.50, signature["anchor"]),
                (2.00, 0.50, signature["support"]),
                (2.75, 0.25, signature["anchor"]),
                (3.00, 1.00, signature["resolve"]),
            ],
        }

    return {
        0: [
            (0.00, 0.75, signature["anchor"]),
            (1.00, 0.50, signature["support"]),
            (2.00, 0.50, signature["anchor"]),
            (3.00, 0.75, signature["lift"]),
        ],
        1: [
            (0.00, 0.75, signature["anchor"]),
            (1.00, 0.50, signature["support"]),
            (2.00, 0.50, signature["anchor"]),
            (3.00, 0.75, signature["lift"]),
        ],
        2: [
            (0.00, 0.50, signature["anchor"]),
            (1.00, 0.50, signature["support"]),
            (2.00, 0.50, signature["lift"]),
            (3.00, 0.50, signature["anchor"]),
        ],
        3: [
            (0.00, 0.75, signature["support"]),
            (1.00, 0.50, signature["anchor"]),
            (2.00, 0.50, signature["support"]),
            (3.00, 1.00, signature["resolve"]),
        ],
    }


def build_breakdown_recall_blueprint(root: str, chords):
    signature = build_signature_hook_cell(root, chords[0], chords[1])
    return {
        0: [
            (0.00, 1.00, signature["anchor"] - 12),
            (2.00, 1.00, signature["support"] - 12),
        ],
        1: [
            (0.50, 1.00, signature["anchor"] - 12),
            (2.50, 1.00, signature["lift"] - 12),
        ],
        2: [
            (0.00, 1.00, signature["support"] - 12),
            (2.00, 1.00, signature["anchor"] - 12),
        ],
        3: [
            (0.00, 1.00, signature["support"] - 12),
            (2.50, 1.25, signature["resolve"] - 12),
        ],
    }


def adapt_note_to_bar(note: int, root: str, chord, section_kind: str):
    chord_pool = chord_tones_in_range(chord, 60, 90)
    scale_pool = scale_notes_in_range(root, 60, 90)

    if section_kind in ("drop", "breakdown"):
        if note in chord_pool:
            return note
        return nearest_note_from_pool(note, chord_pool)

    if note in chord_pool:
        return note
    return nearest_note_from_pool(note, scale_pool)


def generate_drop_lead_events(root: str, chords, absolute_start_bar: int, bars_to_write: int, velocity: int, drop_variant: int):
    blueprint = build_drop_blueprint(root, chords, drop_variant)
    events = []

    for i in range(bars_to_write):
        local_slot = i % 4
        chord = chords[(absolute_start_bar + i) % len(chords)]
        bar_start = bar_tick(absolute_start_bar + i)

        for beat_pos, beat_len, raw_note in blueprint[local_slot]:
            note = adapt_note_to_bar(raw_note, root, chord, "drop")
            length = tick(beat_len * 0.82)
            events.append((bar_start + tick(beat_pos), note, length, velocity))

    return events


def generate_build_lead_events(root: str, chords, absolute_start_bar: int, bars_to_write: int, velocity: int, build_variant: int):
    signature = build_signature_hook_cell(root, chords[0], chords[1])
    events = []

    for i in range(bars_to_write):
        bar_start = bar_tick(absolute_start_bar + i)
        chord = chords[(absolute_start_bar + i) % len(chords)]
        local_slot = i % 4

        if build_variant == 2:
            phrase_map = {
                0: [(0.00, 0.75, signature["anchor"]), (2.00, 0.75, signature["support"])],
                1: [(0.50, 0.75, signature["anchor"]), (2.50, 0.75, signature["lift"])],
                2: [(0.00, 0.50, signature["support"]), (1.50, 0.50, signature["anchor"]), (3.00, 0.50, signature["lift"])],
                3: [(0.00, 0.75, signature["support"]), (2.00, 1.00, signature["lift"])],
            }
        else:
            phrase_map = {
                0: [(0.00, 0.75, signature["anchor"]), (2.00, 0.75, signature["support"])],
                1: [(0.50, 0.75, signature["anchor"]), (2.50, 0.75, signature["lift"])],
                2: [(0.00, 0.75, signature["support"]), (2.00, 0.75, signature["anchor"])],
                3: [(0.00, 0.75, signature["support"]), (2.50, 1.00, signature["lift"])],
            }

        for beat_pos, beat_len, raw_note in phrase_map[local_slot]:
            note = adapt_note_to_bar(raw_note, root, chord, "build")
            events.append((bar_start + tick(beat_pos), note, tick(beat_len * 0.9), clamp(velocity - 6, 50, 118)))

    return events


def generate_breakdown_recall_events(root: str, chords, absolute_start_bar: int, bars_to_write: int, velocity: int):
    blueprint = build_breakdown_recall_blueprint(root, chords)
    events = []

    for i in range(bars_to_write):
        local_slot = i % 4
        chord = chords[(absolute_start_bar + i) % len(chords)]
        bar_start = bar_tick(absolute_start_bar + i)

        for beat_pos, beat_len, raw_note in blueprint[local_slot]:
            note = adapt_note_to_bar(raw_note, root, chord, "breakdown")
            events.append((bar_start + tick(beat_pos), note, tick(beat_len), clamp(velocity - 18, 42, 98)))

    return events


def add_phrase_events_to_track(track_events, phrase_events):
    for start, note, length, vel in phrase_events:
        add_events(track_events, start, note, length, velocity=vel)


def generate_vocal_phrase(root: str, chord, vocal_min: int, vocal_max: int, bar_index: int):
    pool = chord_tones_in_range(chord, vocal_min, vocal_max)
    if not pool:
        pool = [clamp(note_name_to_midi(root, 1, 5), vocal_min, vocal_max)]

    root_note = nearest_note_from_pool(note_name_to_midi(root, 1, 5), pool)
    third_note = nearest_note_from_pool(note_name_to_midi(root, 3, 5), pool)
    fifth_note = nearest_note_from_pool(note_name_to_midi(root, 5, 5), pool)

    if bar_index % 4 == 0:
        return [
            (0.0, 0.8, root_note),
            (1.0, 0.6, third_note),
            (2.0, 0.6, root_note),
            (3.0, 1.0, fifth_note),
        ]
    if bar_index % 4 == 1:
        return [
            (0.5, 0.7, third_note),
            (1.5, 0.7, root_note),
            (2.5, 1.0, third_note),
        ]
    if bar_index % 4 == 2:
        return [
            (0.0, 0.7, fifth_note),
            (1.25, 0.7, third_note),
            (2.5, 0.9, root_note),
        ]
    return [
        (0.0, 1.0, third_note),
        (1.5, 0.8, root_note),
        (3.0, 1.0, root_note),
    ]


def generate_breakdown_piano_phrase(root: str, chord, global_bar: int):
    pool = chord_tones_in_range(chord, 60, 79)
    anchor = nearest_note_from_pool(note_name_to_midi(root, 1, 4), pool)
    support = nearest_note_from_pool(note_name_to_midi(root, 3, 4), pool)
    fifth = nearest_note_from_pool(note_name_to_midi(root, 5, 4), pool)

    if global_bar % 4 == 0:
        return [(0.00, 1.0, anchor), (2.00, 1.0, support)]
    if global_bar % 4 == 1:
        return [(0.50, 1.0, anchor), (2.50, 1.0, fifth)]
    if global_bar % 4 == 2:
        return [(0.00, 1.0, support), (2.00, 1.0, anchor)]
    return [(0.00, 1.0, support), (2.50, 1.25, anchor)]


def add_offbeat_bass(track_events, start_tick_value: int, root_note: int, velocity: int):
    for beat_pos in [0.5, 1.5, 2.5, 3.5]:
        add_events(track_events, start_tick_value + tick(beat_pos), root_note, tick(0.42), velocity=velocity)


def add_rolling_bass(track_events, start_tick_value: int, chord, velocity: int, drop_variant: int):
    root_note = chord["root"] - 24
    fifth_note = chord["fifth"] - 24

    if drop_variant == 2:
        pattern = [root_note, root_note, fifth_note, root_note, root_note + 12, root_note, fifth_note, root_note]
        lengths = [0.22, 0.20, 0.22, 0.18, 0.12, 0.18, 0.20, 0.22]
        velocities = [velocity, velocity - 2, velocity - 3, velocity - 5, velocity - 10, velocity - 3, velocity - 4, velocity]
    else:
        pattern = [root_note, root_note, fifth_note, root_note, root_note, root_note, fifth_note, root_note]
        lengths = [0.22] * 8
        velocities = [velocity] * 8

    for i, note in enumerate(pattern):
        add_events(track_events, start_tick_value + tick(i * 0.5), note, tick(lengths[i]), velocity=clamp(velocities[i], 60, 122))


def add_kick(track_events, start_tick_value: int, section_kind: str, velocity: int):
    if section_kind in ("drop", "build", "verse", "outro"):
        beats = [0, 1, 2, 3]
    else:
        beats = []
    for beat_pos in beats:
        add_events(track_events, start_tick_value + tick(beat_pos), 36, tick(0.42), velocity=velocity)


def add_clap_snare(track_events, start_tick_value: int, section_kind: str, velocity: int, is_last_bar_of_section: bool, is_build_2: bool = False):
    if section_kind in ("verse", "build", "drop"):
        for beat_pos in [1, 3]:
            add_events(track_events, start_tick_value + tick(beat_pos), 39, tick(0.20), velocity=velocity)

    if section_kind == "build" and is_last_bar_of_section:
        if is_build_2:
            roll_positions = [0, 0.5, 1.0, 1.5, 2.0, 2.25, 2.5, 2.75, 3.0, 3.125, 3.25, 3.375, 3.5, 3.625, 3.75, 3.875]
        else:
            roll_positions = [0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.25, 3.5, 3.75]

        for idx, beat_pos in enumerate(roll_positions):
            add_events(track_events, start_tick_value + tick(beat_pos), 38, tick(0.08), velocity=clamp(76 + idx * 3, 76, 124))


def add_hats(track_events, start_tick_value: int, section_kind: str, velocity: int, drop_variant: int = 1):
    if section_kind in ("build", "drop"):
        for beat_pos in [0.5, 1.5, 2.5, 3.5]:
            add_events(track_events, start_tick_value + tick(beat_pos), 46, tick(0.14), velocity=velocity)

    if section_kind == "drop":
        if drop_variant == 2:
            drop_positions = [0.25, 0.75, 1.25, 1.75, 2.25, 2.75, 3.25, 3.75, 0.125, 1.125, 2.125, 3.125]
            hat_velocity = clamp(velocity - 12, 40, 110)
        else:
            drop_positions = [0.75, 1.75, 2.75, 3.75]
            hat_velocity = clamp(velocity - 18, 36, 96)

        for beat_pos in drop_positions:
            add_events(track_events, start_tick_value + tick(beat_pos), 42, tick(0.08), velocity=hat_velocity)


def add_pad_strings_piano(tracks, start_tick_value: int, chord, section_kind: str, velocity: int, local_bar: int, lift_level: int = 1):
    low_chord = [chord["root"] - 12, chord["third"] - 12, chord["fifth"] - 12]
    full_chord = [chord["root"], chord["third"], chord["fifth"]]
    bright_chord = [chord["root"], chord["third"], chord["fifth"], chord["root"] + 12]

    if section_kind in ("intro", "breakdown"):
        add_events(tracks["pad"], start_tick_value, low_chord, tick(4), velocity=clamp(velocity - 20, 40, 100))
        if local_bar % 2 == 0:
            add_events(tracks["strings"], start_tick_value, [chord["root"], chord["third"], chord["fifth"] + 12], tick(4), velocity=clamp(velocity - 24, 38, 96))

    elif section_kind == "verse":
        add_events(tracks["piano"], start_tick_value, full_chord, tick(2), velocity=clamp(velocity - 16, 42, 102))
        add_events(tracks["pad"], start_tick_value, low_chord, tick(4), velocity=clamp(velocity - 24, 36, 96))

    elif section_kind == "build":
        add_events(tracks["pluck"], start_tick_value, full_chord, tick(0.9), velocity=clamp(velocity - 12, 48, 112))
        add_events(tracks["pad"], start_tick_value, low_chord, tick(4), velocity=clamp(velocity - 26, 36, 96))
        if lift_level == 2 and local_bar % 2 == 1:
            add_events(tracks["strings"], start_tick_value + tick(2), [chord["third"], chord["fifth"], chord["root"] + 12], tick(2), velocity=clamp(velocity - 10, 52, 118))

    elif section_kind == "drop":
        spread_chord = bright_chord[:] if lift_level == 1 else bright_chord + [chord["third"] + 12]
        add_events(tracks["supersaw_chords"], start_tick_value, spread_chord, tick(4), velocity=velocity)
        add_events(tracks["pad"], start_tick_value, low_chord, tick(4), velocity=clamp(velocity - 28, 34, 90))
        if local_bar % 2 == 0:
            string_notes = [chord["root"], chord["third"], chord["fifth"] + 12]
            if lift_level == 2:
                string_notes.append(chord["root"] + 24)
            add_events(tracks["strings"], start_tick_value, string_notes, tick(2), velocity=clamp(velocity - 18, 45, 112))

    elif section_kind == "outro":
        add_events(tracks["pad"], start_tick_value, low_chord, tick(4), velocity=clamp(velocity - 26, 34, 90))
        if local_bar < 4:
            add_events(tracks["piano"], start_tick_value, full_chord, tick(2), velocity=clamp(velocity - 18, 40, 100))


def add_breakdown_piano(tracks, start_tick_value: int, root: str, chord, global_bar: int, velocity: int):
    phrase = generate_breakdown_piano_phrase(root, chord, global_bar)
    for beat_pos, beat_len, note in phrase:
        add_events(
            tracks["piano"],
            start_tick_value + tick(beat_pos),
            note,
            tick(beat_len),
            velocity=clamp(velocity - 12, 44, 96)
        )


def add_arp(tracks, start_tick_value: int, chord, section_kind: str, velocity: int, drop_variant: int = 1):
    if section_kind not in ("build", "drop", "breakdown"):
        return

    if section_kind == "drop":
        if drop_variant == 1:
            arp_notes = [chord["root"] + 12, chord["third"] + 12, chord["fifth"] + 12, chord["third"] + 12]
            step = 0.5
        else:
            arp_notes = [chord["root"] + 12, chord["third"] + 12, chord["fifth"] + 12, chord["root"] + 24]
            step = 0.25
    elif section_kind == "build":
        arp_notes = [chord["root"] + 12, chord["third"] + 12, chord["fifth"] + 12, chord["third"] + 12]
        step = 0.5
    else:
        arp_notes = [chord["root"] + 12, chord["third"] + 12, chord["fifth"] + 12, chord["third"] + 12]
        step = 0.5

    reps = int(4 / step)
    for i in range(reps):
        note = arp_notes[i % len(arp_notes)]
        if section_kind == "drop" and drop_variant == 2 and i % 8 == 7:
            note += 12
        add_events(tracks["arp"], start_tick_value + tick(i * step), note, tick(step * 0.72), velocity=velocity)


def add_countermelody(tracks, start_tick_value: int, chord, local_bar: int, velocity: int, drop_variant: int = 1):
    """
    More selective response:
    - only bars 2 and 4
    - late in the bar
    - smaller in Drop 1, fuller in Drop 2
    """
    bar_slot = local_bar % 4

    if bar_slot == 1:
        phrase = [
            (2.75, 0.50, chord["third"] - 12),
            (3.50, 0.40, chord["fifth"] - 12),
        ]
    elif bar_slot == 3:
        phrase = [
            (2.50, 0.50, chord["root"]),
            (3.25, 0.75, chord["third"]),
        ]
    else:
        return

    if drop_variant == 2 and bar_slot == 3:
        phrase = phrase + [(3.875, 0.10, chord["fifth"])]

    for beat_pos, beat_len, note in phrase:
        add_events(tracks["countermelody"], start_tick_value + tick(beat_pos), note, tick(beat_len), velocity=velocity)


def generate_pack(bpm: int, key_root: str, progression: str, arrangement: str, energy: str, vocalist: str, out_zip: Path):
    tempo = bpm2tempo(bpm)
    sections = arrange_sections(arrangement)
    chords = progression_chords(key_root, progression)
    energy_factor = ENERGY_LEVELS[energy]
    vocal_min, vocal_max = VOCAL_RANGES[vocalist]

    tracks = {stem: [] for stem in STEMS}
    markers = []

    for sec in sections:
        markers.append((bar_tick(sec["start_bar"]), f"{sec['name']} ({sec['bars']} bars)"))
        sec_kind = section_type(sec["name"])
        sec_profile = energy_profile(sec["name"], energy_factor)

        sec_name_lower = sec["name"].lower()
        is_drop_2 = "drop 2" in sec_name_lower
        is_build_2 = "build 2" in sec_name_lower

        lift_level = 2 if (is_drop_2 or is_build_2) else 1
        drop_variant = 2 if is_drop_2 else 1
        build_variant = 2 if is_build_2 else 1

        if sec_kind == "drop":
            lead_events = generate_drop_lead_events(
                key_root,
                chords,
                sec["start_bar"],
                sec["bars"],
                clamp(sec_profile["velocity"] + (6 if is_drop_2 else 0), 1, 124),
                drop_variant
            )
            add_phrase_events_to_track(tracks["lead"], lead_events)

        elif sec_kind == "build":
            build_lead_events = generate_build_lead_events(
                key_root,
                chords,
                sec["start_bar"],
                sec["bars"],
                clamp(sec_profile["velocity"] + (4 if is_build_2 else 0), 1, 124),
                build_variant
            )
            add_phrase_events_to_track(tracks["lead"], build_lead_events)

        elif sec_kind == "breakdown":
            breakdown_events = generate_breakdown_recall_events(
                key_root,
                chords,
                sec["start_bar"],
                sec["bars"],
                sec_profile["velocity"]
            )
            add_phrase_events_to_track(tracks["lead"], breakdown_events)

        for local_bar in range(sec["bars"]):
            global_bar = sec["start_bar"] + local_bar
            chord = choose_chord(chords, global_bar)
            start = bar_tick(global_bar)
            is_last_bar_of_section = local_bar == sec["bars"] - 1

            local_velocity = sec_profile["velocity"]
            if is_drop_2:
                local_velocity = clamp(local_velocity + 6, 1, 124)
            elif is_build_2:
                local_velocity = clamp(local_velocity + 4, 1, 124)

            add_pad_strings_piano(
                tracks,
                start,
                chord,
                sec_kind,
                local_velocity,
                local_bar,
                lift_level=lift_level
            )

            if sec_kind == "breakdown":
                add_breakdown_piano(tracks, start, key_root, chord, global_bar, local_velocity)

            add_kick(tracks["kick"], start, sec_kind, clamp(local_velocity, 80, 122))
            add_clap_snare(
                tracks["clap_snare"],
                start,
                sec_kind,
                clamp(local_velocity - 8, 64, 118),
                is_last_bar_of_section,
                is_build_2=is_build_2
            )
            add_hats(
                tracks["hats"],
                start,
                sec_kind,
                clamp(local_velocity - 28, 40, 95),
                drop_variant=drop_variant
            )
            add_arp(
                tracks,
                start,
                chord,
                sec_kind,
                clamp(local_velocity - 22, 46, 104),
                drop_variant=drop_variant
            )

            if sec_kind in ("verse", "outro"):
                add_offbeat_bass(
                    tracks["offbeat_bass"],
                    start,
                    chord["root"] - 24,
                    clamp(local_velocity - 6, 70, 116)
                )

            if sec_kind == "drop":
                add_rolling_bass(
                    tracks["rolling_bass"],
                    start,
                    chord,
                    clamp(local_velocity - 10, 72, 120),
                    drop_variant=drop_variant
                )
                add_countermelody(
                    tracks,
                    start,
                    chord,
                    local_bar,
                    clamp(local_velocity - 24, 44, 100),
                    drop_variant=drop_variant
                )

            if sec_kind in ("verse", "breakdown", "build"):
                vocal_phrase = generate_vocal_phrase(key_root, chord, vocal_min, vocal_max, global_bar)
                for beat_pos, beat_len, note in vocal_phrase:
                    add_events(
                        tracks["vocal_melody"],
                        start + tick(beat_pos),
                        note,
                        tick(beat_len),
                        velocity=clamp(local_velocity - 2, 58, 108)
                    )

    out_zip.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        td = Path(temp_dir)

        combined = MidiFile(type=1, ticks_per_beat=TICKS)
        combined.tracks.append(finalise_track("Markers", tempo, [], markers=markers))

        for stem in STEMS:
            stem_midi = MidiFile(type=1, ticks_per_beat=TICKS)
            stem_track = finalise_track(stem, tempo, tracks[stem][:], markers=markers if stem == "kick" else None)
            stem_midi.tracks.append(stem_track)
            stem_path = td / f"{stem}.mid"
            stem_midi.save(stem_path)
            combined.tracks.append(finalise_track(stem, tempo, tracks[stem][:]))

        full_arrangement_path = td / "full_arrangement.mid"
        combined.save(full_arrangement_path)

        sections_text = "\n".join(
            f"- {s['name']}: bars {s['start_bar'] + 1}-{s['end_bar']}"
            for s in sections
        )

        notes_path = td / "production_notes.txt"
        notes_path.write_text(
            "Dream Trance MIDI Generator V2.8\n\n"
            f"BPM: {bpm}\n"
            f"Key: {key_root} minor\n"
            f"Progression: {progression}\n"
            f"Arrangement: {arrangement}\n"
            f"Energy: {energy}\n"
            f"Vocalist: {vocalist}\n\n"
            "V2.8 Anthem Engine:\n"
            "- One signature lead hook cell\n"
            "- Tighter pitch vocabulary for stronger memory\n"
            "- Simpler Drop 1\n"
            "- Bigger Drop 2\n"
            "- Reduced Drop 1 arp clutter\n"
            "- Stronger breakdown piano and lead recall\n"
            "- More selective countermelody response\n\n"
            f"Sections:\n{sections_text}\n"
        )

        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(full_arrangement_path, full_arrangement_path.name)
            zf.write(notes_path, notes_path.name)
            for stem in STEMS:
                p = td / f"{stem}.mid"
                zf.write(p, f"stems/{p.name}")


@app.post("/generate")
def generate(
    bpm: int = Form(...),
    key_root: str = Form(...),
    progression: str = Form(...),
    arrangement: str = Form(...),
    energy: str = Form(...),
    vocalist: str = Form(...),
):
    out_dir = Path("exports")
    out_dir.mkdir(exist_ok=True)
    out_zip = out_dir / "dream_trance_midi_pack_v2_8.zip"
    generate_pack(bpm, key_root, progression, arrangement, energy, vocalist, out_zip)
    return FileResponse(out_zip, filename=out_zip.name, media_type="application/zip")
