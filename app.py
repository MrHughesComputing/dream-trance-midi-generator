from typing import Literal, Annotated
from uuid import uuid4
from pathlib import Path
import tempfile
import zipfile

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from mido import Message, MidiFile, MidiTrack, MetaMessage, bpm2tempo

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
EXPORTS_DIR = BASE_DIR / "exports"

app = FastAPI(title="Dream Trance MIDI Generator V3.6")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


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

KEY_ROOT_OPTIONS = ["F", "F#", "G", "G#", "A", "A#", "C", "D"]

KeyRootType = Literal["F", "F#", "G", "G#", "A", "A#", "C", "D"]
ProgressionType = Literal[
    "Emotional Lift (i-VI-III-VII)",
    "Classic Uplift (i-iv-VI-VII)",
    "Festival Drive (VI-III-VII-i)",
    "Hopeful Pull (i-v-VI-iv)",
]
ArrangementType = Literal["Club/Extended", "Radio/Compact", "Breakdown Focused"]
EnergyType = Literal["Low", "Medium", "High"]
VocalistType = Literal["Female Soprano", "Female Airy", "Male Tenor"]

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dream Trance MIDI Generator V3.6</title>
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
        <div class="eyebrow">Dream Trance MIDI Generator • V3.6 Motif Evolution Engine</div>
        <h1>Push the generator toward motif-driven trance writing with evolving hook families, phrase-role-aware drops, breakdown memory, stronger countermelody, and a more decisive final Drop 2 climax.</h1>
        <p class="sub">
          V3.6 preserves the V3.5 stability and hook authority while adding motif-family writing, phrase-role-aware drops, emotional breakdown memory, stronger countermelody answers, and a true final Drop 2 climax.
        </p>
        <div class="pill">Exports aligned full-length stems + combined arrangement MIDI</div>
      </div>

      <div class="hero-side">
        <div class="stat">
          <div class="stat-label">Primary use</div>
          <div class="stat-value">Festival-ready uplifting / melodic trance sketch generation</div>
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
          <h3>What changed in V3.5</h3>
          <ul>
            <li>Lead generation now writes around a track identity blueprint plus a motif family with one enforced hero note per 4-bar cycle.</li>
            <li>Bar-4 payoff phrases now lock to a dominant hero note instead of letting all notes compete equally.</li>
            <li>Drop 2 now escalates more decisively in register, support, and final payoff authority.</li>
            <li>Rolling bass and countermelody now leave more space underneath lead payoff moments.</li>
            <li>Breakdown recall now behaves like motif memory and anticipation instead of replaying the drop literally.</li>
            <li>The vocal melody stem is now more motif-aware and shaped like a simplified topline candidate.</li>
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
        "".join("<option>" + k + "</option>" for k in KEY_ROOT_OPTIONS)
    )
    html = html.replace(
        "__PROG_OPTS__",
        "".join("<option>" + p + "</option>" for p in PROGRESSIONS)
    )
    html = html.replace(
        "__ARR_OPTS__",
        "".join("<option>" + a + "</option>" for a in ARRANGEMENTS)
    )
    html = html.replace(
        "__ENERGY_OPTS__",
        "".join("<option>" + e + "</option>" for e in ENERGY_LEVELS)
    )
    html = html.replace(
        "__VOCAL_OPTS__",
        "".join("<option>" + v + "</option>" for v in VOCAL_RANGES)
    )
    html = html.replace(
        "__STEM_ITEMS__",
        "".join("<li>" + s + "</li>" for s in STEMS)
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
        event_list.append((start_tick_value + max(1, length_tick), Message("note_off", note=int(n), velocity=0, channel=channel, time=0)))


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
    if not pool:
        return target
    return min(pool, key=lambda x: (abs(x - target), x))


def nearest_distinct_note_from_pool(target: int, pool, avoid_note: int | None = None, prefer_direction: int = 1):
    if not pool:
        return target
    candidates = [n for n in pool if n != avoid_note]
    if not candidates:
        candidates = pool[:]
    def score(n: int):
        direction_penalty = 0
        if avoid_note is not None:
            if prefer_direction > 0 and n <= avoid_note:
                direction_penalty = 0.6
            elif prefer_direction < 0 and n >= avoid_note:
                direction_penalty = 0.6
        return (abs(n - target) + direction_penalty, abs((n if avoid_note is None else n - avoid_note)), n)
    return min(candidates, key=score)



def adapt_drop_note_to_bar(note: int, root: str, chord, previous_note: int | None = None, prefer_direction: int = 1, allow_tension: bool = False):
    chord_pool = chord_tones_in_range(chord, 68, 100)
    scale_pool = scale_notes_in_range(root, 68, 100)

    if note in chord_pool:
        chosen = note
    elif note in scale_pool and allow_tension:
        chosen = note
    elif note in scale_pool:
        chosen = nearest_note_from_pool(note, chord_pool)
    else:
        nearest_scale = nearest_note_from_pool(note, scale_pool)
        if allow_tension and abs(nearest_scale - note) <= 2:
            chosen = nearest_scale
        elif abs(nearest_scale - note) <= 1:
            chosen = nearest_scale
        else:
            chosen = nearest_note_from_pool(note, chord_pool)

    if previous_note is not None and chosen == previous_note:
        ordered_pool = sorted(set(chord_pool + scale_pool))
        chosen = nearest_distinct_note_from_pool(chosen, ordered_pool, avoid_note=previous_note, prefer_direction=prefer_direction)

    return chosen


def allow_tension_for_phrase(slot: int, idx: int, note_count: int, drop_variant: int, phase: int) -> bool:
    if slot == 1 and idx in (0, note_count - 1):
        return True
    if slot == 2 and idx >= max(0, note_count - 2):
        return True
    if slot == 3 and idx in (max(0, note_count - 2), note_count - 1):
        return True
    if drop_variant == 2 and phase >= 2 and idx >= max(0, note_count - 3):
        return True
    return False


def phrase_velocity_boost(slot: int, idx: int, note_count: int, phase: int, drop_variant: int) -> int:
    if slot == 0:
        if idx == 0:
            return 10
        if idx == note_count - 1:
            return 6
        return 1
    if slot == 1:
        if idx == 0:
            return 7
        if idx == note_count - 1:
            return 5
        return 0
    if slot == 2:
        if idx >= max(0, note_count - 2):
            return 8 if phase >= 2 else 6
        return 1
    if slot == 3:
        if idx == note_count - 1:
            return 16 if (drop_variant == 2 and phase >= 2) else 12
        if idx == note_count - 2:
            return 9
        return 2
    return 0


def phrase_length_multiplier(slot: int, idx: int, note_count: int, phase: int, drop_variant: int) -> float:
    if slot == 0:
        if idx == 0:
            return 0.92
        if idx == note_count - 1:
            return 0.90
        return 0.82
    if slot == 1:
        if idx == 0:
            return 0.86
        if idx == note_count - 1:
            return 0.88
        return 0.78 if phase < 2 else 0.74
    if slot == 2:
        if idx >= max(0, note_count - 2):
            return 0.92
        return 0.80 if phase < 2 else 0.76
    if slot == 3:
        if idx == note_count - 1:
            return 1.18 if (drop_variant == 2 and phase >= 2) else 1.08
        if idx == note_count - 2:
            return 0.94
        return 0.82
    return 0.84


def add_lead_support_octave(events, start_tick_value: int, note: int, length_tick: int, velocity: int):
    octave_note = clamp(note - 12, 62, 86)
    events.append(
        (
            start_tick_value,
            octave_note,
            max(tick(0.20), int(length_tick * 0.58)),
            clamp(velocity - 14, 54, 112),
        )
    )





def build_signature_hook_cell(root: str, first_chord, second_chord):
    """
    V3.5:
    Build a reusable hook vocabulary, but do not treat it as the final composition.
    This is now only the raw pitch material for the track identity blueprint.
    """
    first_pool = chord_tones_in_range(first_chord, 72, 90)
    second_pool = chord_tones_in_range(second_chord, 72, 96)
    scale_pool = scale_notes_in_range(root, 72, 98)

    anchor = nearest_note_from_pool(note_name_to_midi(root, 5, 5), first_pool)
    support = nearest_note_from_pool(note_name_to_midi(root, 3, 5), first_pool)
    answer = nearest_note_from_pool(note_name_to_midi(root, 1, 5), first_pool)
    passing = nearest_note_from_pool(note_name_to_midi(root, 2, 5), scale_pool)
    tension = nearest_note_from_pool(note_name_to_midi(root, 6, 5), scale_pool)
    pivot = nearest_note_from_pool(note_name_to_midi(root, 7, 5), second_pool)
    lift = nearest_note_from_pool(note_name_to_midi(root, 1, 6), second_pool)
    apex = nearest_note_from_pool(note_name_to_midi(root, 3, 6), second_pool)
    leap = nearest_note_from_pool(note_name_to_midi(root, 5, 6), scale_pool)
    resolve = nearest_note_from_pool(note_name_to_midi(root, 1, 5), chord_tones_in_range(first_chord, 70, 84))
    payoff = nearest_note_from_pool(note_name_to_midi(root, 5, 5), chord_tones_in_range(second_chord, 72, 88))
    accent = nearest_note_from_pool(note_name_to_midi(root, 1, 6), chord_tones_in_range(second_chord, 83, 98))
    final = nearest_note_from_pool(note_name_to_midi(root, 3, 6), chord_tones_in_range(second_chord, 84, 99))
    terminal = nearest_note_from_pool(note_name_to_midi(root, 5, 6), scale_pool)

    return {
        "anchor": clamp(anchor, 74, 86),
        "support": clamp(support, 72, 84),
        "answer": clamp(answer, 71, 83),
        "passing": clamp(passing, 72, 85),
        "tension": clamp(tension, 74, 88),
        "pivot": clamp(pivot, 74, 88),
        "lift": clamp(lift, 76, 91),
        "apex": clamp(apex, 79, 94),
        "leap": clamp(leap, 84, 98),
        "resolve": clamp(resolve, 71, 84),
        "payoff": clamp(payoff, 72, 88),
        "accent": clamp(accent, 84, 98),
        "final": clamp(final, 85, 99),
        "terminal": clamp(terminal, 86, 100),
        "dominant": clamp(max(anchor, lift), 78, 92),
    }


def choose_track_contour(arrangement: str, energy: str) -> str:
    if "Breakdown" in arrangement:
        return "arc"
    if energy == "High":
        return "late_peak"
    if arrangement == "Radio/Compact":
        return "lift"
    return "late_peak"


def build_track_identity_blueprint(root: str, chords, arrangement: str, energy: str):
    hook_signature = build_signature_hook_cell(root, chords[0], chords[1])
    contour_type = choose_track_contour(arrangement, energy)

    if contour_type == "late_peak":
        hero_note = clamp(max(hook_signature["accent"], hook_signature["final"]), 86, 100)
        drop2_apex_note = clamp(max(hook_signature["terminal"], hero_note + 2), 88, 102)
        lead_register_peak = 100
    elif contour_type == "lift":
        hero_note = clamp(max(hook_signature["payoff"], hook_signature["accent"]), 84, 97)
        drop2_apex_note = clamp(max(hero_note + 2, hook_signature["final"]), 86, 100)
        lead_register_peak = 98
    else:
        hero_note = clamp(max(hook_signature["final"], hook_signature["accent"]), 85, 99)
        drop2_apex_note = clamp(max(hero_note + 1, hook_signature["terminal"]), 87, 101)
        lead_register_peak = 99

    leap_candidates = [7, 8, 9, 12]
    signature_leap_interval = 9 if energy == "High" else 7

    return {
        "hook_signature": hook_signature,
        "hero_note": hero_note,
        "hero_bar_slot": 3,
        "signature_leap_interval": signature_leap_interval,
        "leap_candidates": leap_candidates,
        "primary_resolution_note": clamp(hook_signature["payoff"], 76, 90),
        "breakdown_memory_note": clamp(hook_signature["anchor"] - 12, 60, 84),
        "drop2_apex_note": drop2_apex_note,
        "lead_register_base": 74,
        "lead_register_peak": lead_register_peak,
        "track_contour_type": contour_type,
    }


def apply_register_shift(note: int, shift: int, low: int = 72, high: int = 102) -> int:
    return clamp(note + shift, low, high)


def phrase_role_velocity_offset(role: str) -> int:
    return {
        "passing": -10,
        "support": -4,
        "strong": 4,
        "hero": 16,
    }.get(role, 0)


def phrase_role_length_multiplier(role: str) -> float:
    return {
        "passing": 0.72,
        "support": 0.84,
        "strong": 0.98,
        "hero": 1.36,
    }.get(role, 0.84)


def enforce_signature_leap(note_sequence, preferred_intervals=(7, 8, 9, 12)):
    if len(note_sequence) < 4:
        return note_sequence[:]

    for i in range(1, len(note_sequence)):
        if abs(note_sequence[i] - note_sequence[i - 1]) in preferred_intervals:
            return note_sequence[:]

    seq = note_sequence[:]
    anchor = seq[-3]
    leap_interval = preferred_intervals[0]
    seq[-2] = clamp(anchor + leap_interval, 78, 100)
    if seq[-1] >= seq[-2]:
        seq[-1] = clamp(seq[-2] - 2, 74, 96)
    return seq


def enforce_hero_note(phrase_events, hero_note: int, hero_start_min_beat: float = 2.75):
    if not phrase_events:
        return phrase_events

    working = [dict(event) for event in phrase_events]
    hero_idx = None

    for idx in range(len(working) - 1, -1, -1):
        if working[idx]["bar_offset"] == 3 and working[idx]["beat_pos"] >= hero_start_min_beat:
            hero_idx = idx
            break

    if hero_idx is None:
        hero_idx = len(working) - 1

    for idx, event in enumerate(working):
        if idx != hero_idx and event["role"] == "hero":
            event["role"] = "strong"

    working[hero_idx]["raw_note"] = hero_note
    working[hero_idx]["role"] = "hero"
    working[hero_idx]["allow_tension"] = False
    working[hero_idx]["beat_len"] = max(working[hero_idx]["beat_len"], 0.88)

    for idx in range(hero_idx + 1, len(working)):
        working[idx]["role"] = "passing"
        working[idx]["beat_len"] = min(working[idx]["beat_len"], 0.18)

    return working



def invert_fragment(notes, pivot):
    inverted = []
    for n in notes:
        interval = n - pivot
        inverted.append(clamp(pivot - interval, 60, 102))
    return inverted


def rotate_fragment(notes, steps: int = 1):
    if not notes:
        return []
    steps = steps % len(notes)
    return notes[steps:] + notes[:steps]


def build_motif_rhythm_family():
    return {
        "statement": [
            (0, 0.00, 0.72, "strong"),
            (0, 1.00, 0.42, "passing"),
            (0, 2.00, 0.48, "support"),
            (0, 3.00, 0.68, "strong"),
            (1, 0.00, 0.50, "support"),
            (1, 1.00, 0.34, "passing"),
            (1, 2.00, 0.42, "support"),
            (1, 3.00, 0.66, "strong"),
            (2, 0.00, 0.40, "support"),
            (2, 0.75, 0.24, "passing"),
            (2, 1.50, 0.34, "support"),
            (2, 2.25, 0.32, "strong"),
            (2, 3.00, 0.64, "strong"),
            (3, 0.00, 0.44, "support"),
            (3, 0.90, 0.34, "support"),
            (3, 1.75, 0.30, "strong"),
            (3, 2.60, 0.22, "passing"),
            (3, 3.05, 0.88, "hero"),
        ],
        "variation": [
            (0, 0.00, 0.62, "strong"),
            (0, 0.75, 0.26, "passing"),
            (0, 1.50, 0.32, "support"),
            (0, 2.25, 0.28, "passing"),
            (0, 3.00, 0.66, "strong"),
            (1, 0.00, 0.44, "support"),
            (1, 1.00, 0.26, "passing"),
            (1, 1.75, 0.30, "support"),
            (1, 2.40, 0.22, "passing"),
            (1, 3.00, 0.68, "strong"),
            (2, 0.00, 0.38, "support"),
            (2, 0.75, 0.24, "passing"),
            (2, 1.35, 0.28, "support"),
            (2, 2.00, 0.30, "strong"),
            (2, 2.70, 0.24, "passing"),
            (2, 3.00, 0.62, "strong"),
            (3, 0.00, 0.38, "support"),
            (3, 0.82, 0.28, "support"),
            (3, 1.56, 0.28, "strong"),
            (3, 2.28, 0.18, "passing"),
            (3, 2.64, 0.20, "strong"),
            (3, 3.10, 0.90, "hero"),
        ],
        "lift": [
            (0, 0.00, 0.56, "strong"),
            (0, 0.75, 0.24, "passing"),
            (0, 1.50, 0.28, "support"),
            (0, 2.25, 0.24, "passing"),
            (0, 3.00, 0.64, "strong"),
            (1, 0.00, 0.40, "support"),
            (1, 0.75, 0.20, "passing"),
            (1, 1.35, 0.24, "support"),
            (1, 2.00, 0.24, "passing"),
            (1, 2.55, 0.24, "strong"),
            (1, 3.00, 0.56, "strong"),
            (2, 0.00, 0.34, "support"),
            (2, 0.62, 0.18, "passing"),
            (2, 1.10, 0.20, "support"),
            (2, 1.58, 0.18, "passing"),
            (2, 2.02, 0.22, "strong"),
            (2, 2.46, 0.20, "passing"),
            (2, 2.82, 0.24, "strong"),
            (2, 3.18, 0.38, "strong"),
            (3, 0.00, 0.34, "support"),
            (3, 0.68, 0.18, "passing"),
            (3, 1.18, 0.20, "support"),
            (3, 1.82, 0.20, "strong"),
            (3, 2.34, 0.18, "passing"),
            (3, 2.72, 0.22, "strong"),
            (3, 3.18, 0.98, "hero"),
        ],
        "climax": [
            (0, 0.00, 0.58, "strong"),
            (0, 0.62, 0.22, "passing"),
            (0, 1.10, 0.24, "support"),
            (0, 1.58, 0.20, "passing"),
            (0, 2.00, 0.24, "strong"),
            (0, 2.48, 0.20, "passing"),
            (0, 2.84, 0.26, "strong"),
            (0, 3.20, 0.56, "strong"),
            (1, 0.00, 0.38, "support"),
            (1, 0.58, 0.18, "passing"),
            (1, 1.02, 0.20, "support"),
            (1, 1.46, 0.18, "passing"),
            (1, 1.88, 0.22, "strong"),
            (1, 2.32, 0.20, "passing"),
            (1, 2.72, 0.24, "strong"),
            (1, 3.10, 0.56, "strong"),
            (2, 0.00, 0.32, "support"),
            (2, 0.52, 0.16, "passing"),
            (2, 0.92, 0.18, "support"),
            (2, 1.30, 0.18, "passing"),
            (2, 1.72, 0.22, "strong"),
            (2, 2.18, 0.20, "passing"),
            (2, 2.56, 0.24, "strong"),
            (2, 2.94, 0.22, "strong"),
            (2, 3.22, 0.50, "strong"),
            (3, 0.00, 0.34, "support"),
            (3, 0.58, 0.18, "passing"),
            (3, 1.02, 0.20, "support"),
            (3, 1.46, 0.18, "passing"),
            (3, 1.92, 0.22, "strong"),
            (3, 2.34, 0.18, "passing"),
            (3, 2.72, 0.22, "strong"),
            (3, 3.10, 1.12, "hero"),
        ],
    }


def derive_statement_from_cell(cell, identity_blueprint):
    sig = identity_blueprint["hook_signature"]
    return [
        cell[0], cell[1], cell[2], sig["dominant"],
        cell[0], cell[1], sig["pivot"], sig["lift"],
        cell[1], cell[0], sig["pivot"], sig["lift"], sig["apex"],
        sig["answer"], sig["anchor"], sig["pivot"], sig["lift"], sig["payoff"],
    ]


def derive_variation_from_cell(cell, identity_blueprint):
    sig = identity_blueprint["hook_signature"]
    rotated = rotate_fragment(cell, 1)
    return [
        rotated[0], rotated[1], rotated[2], sig["dominant"],
        rotated[0], sig["passing"], sig["pivot"], sig["tension"], sig["lift"],
        cell[1], cell[0], sig["pivot"], sig["lift"], sig["apex"], sig["leap"],
        sig["answer"], sig["anchor"], sig["pivot"], sig["tension"], sig["lift"], sig["payoff"],
    ]


def derive_lift_from_cell(cell, identity_blueprint):
    sig = identity_blueprint["hook_signature"]
    expanded = [cell[0], cell[1], cell[2], sig["pivot"], sig["lift"], sig["apex"]]
    return [
        expanded[0], expanded[1], expanded[2], sig["dominant"],
        expanded[1], sig["passing"], sig["pivot"], sig["tension"], sig["lift"],
        cell[1], sig["anchor"], sig["pivot"], sig["lift"], sig["apex"], sig["leap"],
        sig["answer"], sig["pivot"], sig["tension"], sig["lift"], sig["apex"], sig["final"],
    ]


def derive_climax_from_cell(cell, identity_blueprint):
    sig = identity_blueprint["hook_signature"]
    hero = identity_blueprint["drop2_apex_note"]
    return [
        cell[0], cell[1], sig["pivot"], sig["lift"], sig["apex"], sig["leap"],
        cell[1], sig["pivot"], sig["tension"], sig["lift"], sig["apex"], sig["leap"],
        sig["anchor"], sig["pivot"], sig["lift"], sig["apex"], sig["final"], hero - 1,
        sig["answer"], sig["anchor"], sig["pivot"], sig["tension"], sig["lift"], sig["apex"], sig["final"], hero,
    ]


def build_motif_family(identity_blueprint, root: str, chords):
    sig = identity_blueprint["hook_signature"]
    base_cell = [
        clamp(sig["anchor"], 72, 92),
        clamp(sig["support"], 72, 92),
        clamp(sig["answer"], 72, 92),
    ]
    family = {
        "cell": base_cell,
        "statement": derive_statement_from_cell(base_cell, identity_blueprint),
        "variation": derive_variation_from_cell(base_cell, identity_blueprint),
        "lift": derive_lift_from_cell(base_cell, identity_blueprint),
        "climax": derive_climax_from_cell(base_cell, identity_blueprint),
        "breakdown_hint": [
            clamp(base_cell[0] - 12, 60, 84),
            clamp(base_cell[2] - 12, 60, 84),
            clamp(sig["pivot"] - 12, 60, 84),
            clamp(sig["payoff"] - 12, 60, 84),
        ],
    }
    family["inversion"] = invert_fragment(base_cell, base_cell[0])
    return family


def plan_drop_phrase_roles(section_name: str, bars: int):
    cycles = max(1, (bars + 3) // 4)
    if "drop 2" in section_name.lower():
        seed = ["variation", "lift", "statement", "lift", "variation", "lift", "statement", "climax"]
    else:
        seed = ["statement", "variation", "statement", "lift", "variation", "lift", "statement", "climax"]
    roles = []
    for i in range(cycles):
        if i < len(seed):
            roles.append(seed[i])
        else:
            roles.append(seed[-2] if i < cycles - 1 else seed[-1])
    if cycles == 1:
        roles = ["climax" if "drop 2" in section_name.lower() else "statement"]
    elif cycles == 2 and "drop 2" in section_name.lower():
        roles[-1] = "climax"
    elif cycles >= 2:
        roles[-1] = "climax" if "drop 2" in section_name.lower() else max(["statement","variation","lift"], key=lambda r: {"statement":0,"variation":1,"lift":2}[roles[-1]])
    return roles


def plan_final_climax_window(section_name: str, local_bar: int, total_bars: int):
    if "drop 2" not in section_name.lower():
        return {"in_final_8": False, "in_final_4": False, "is_peak_phrase": False}
    return {
        "in_final_8": local_bar >= max(0, total_bars - 8),
        "in_final_4": local_bar >= max(0, total_bars - 4),
        "is_peak_phrase": local_bar >= max(0, total_bars - 4),
    }


def evolve_hero_strategy(phrase_role: str, identity_blueprint, drop_variant: int, phase: int):
    peak = identity_blueprint["lead_register_peak"]
    base = identity_blueprint["hero_note"]
    if phrase_role == "statement":
        return {"hero_note": clamp(base, 78, peak), "hero_start": 3.00, "hold_beats": 0.92}
    if phrase_role == "variation":
        return {"hero_note": clamp(base + (1 if drop_variant == 2 else 0), 79, peak), "hero_start": 3.08, "hold_beats": 0.94}
    if phrase_role == "lift":
        return {"hero_note": clamp(base + 1 + phase, 80, peak), "hero_start": 3.18, "hold_beats": 1.00}
    return {"hero_note": clamp(max(identity_blueprint["drop2_apex_note"], base + 2), 82, 102), "hero_start": 3.10, "hold_beats": 1.12}


def compose_motif_phrase(identity_blueprint, motif_family, phrase_role: str, drop_variant: int, phase: int, cycle_index: int):
    rhythm_family = build_motif_rhythm_family()
    rhythm = rhythm_family.get(phrase_role, rhythm_family["statement"])
    note_pool = motif_family.get(phrase_role, motif_family["statement"])[:]
    if phrase_role == "variation" and cycle_index % 2 == 1:
        note_pool = rotate_fragment(note_pool, 1)
    elif phrase_role == "lift" and cycle_index % 2 == 1:
        note_pool = rotate_fragment(note_pool, 2)
    hero_strategy = evolve_hero_strategy(phrase_role, identity_blueprint, drop_variant, phase)
    contour_bonus = {"statement": 0, "variation": 1, "lift": 2, "climax": 3}[phrase_role]
    register_shift = 0
    if drop_variant == 2:
        register_shift += 1
    if phase >= 2:
        register_shift += 1
    if phrase_role == "climax":
        register_shift += 1

    phrase = []
    prev_note = None
    for idx, (bar_offset, beat_pos, beat_len, role) in enumerate(rhythm):
        raw = note_pool[idx % len(note_pool)]
        if role == "hero":
            raw = hero_strategy["hero_note"]
            beat_pos = hero_strategy["hero_start"]
            beat_len = hero_strategy["hold_beats"]
        elif role == "strong" and phrase_role in ("lift", "climax") and beat_pos >= 2.5:
            raw = apply_register_shift(raw, register_shift + contour_bonus, 74, 102)
        else:
            raw = apply_register_shift(raw, register_shift + min(contour_bonus, 2), 72, identity_blueprint["lead_register_peak"])

        phrase.append({
            "bar_offset": bar_offset,
            "beat_pos": beat_pos,
            "beat_len": beat_len,
            "raw_note": raw,
            "role": role,
            "allow_tension": phrase_role in ("lift", "climax") and role in ("passing", "strong") and beat_pos >= 2.0,
            "support_octave": role in ("hero",) or (phrase_role == "climax" and role == "strong" and beat_pos >= 2.8),
            "prefer_direction": 1 if prev_note is None or raw >= prev_note else -1,
            "phrase_role": phrase_role,
        })
        prev_note = raw

    phrase = enforce_hero_note(phrase, hero_strategy["hero_note"], hero_start_min_beat=hero_strategy["hero_start"])
    return phrase


def build_countermelody_response(motif_family, phrase_role: str, chord, local_bar: int, drop_variant: int, phase: int):
    cell = motif_family["cell"]
    root_line = clamp(chord["root"], 60, 81)
    third_line = clamp(chord["third"], 60, 83)
    fifth_line = clamp(chord["fifth"], 60, 84)
    echo_a = clamp(cell[1] - 12, 60, 81)
    echo_b = clamp(cell[2] - 12, 60, 82)

    if local_bar % 4 == 0:
        if phrase_role == "statement":
            return [(2.75, 0.42, echo_a, "support"), (3.35, 0.42, third_line, "support")]
        if phrase_role == "variation":
            return [(2.50, 0.28, echo_a, "passing"), (2.92, 0.34, echo_b, "support"), (3.45, 0.34, fifth_line, "support")]
        if phrase_role == "lift":
            return [(2.42, 0.24, echo_a, "passing"), (2.78, 0.26, echo_b, "support"), (3.15, 0.30, fifth_line, "strong"), (3.58, 0.28, third_line, "support")]
        return [(2.34, 0.22, echo_a, "passing"), (2.66, 0.22, echo_b, "support"), (2.98, 0.26, fifth_line, "strong"), (3.36, 0.56, root_line, "hero")]

    if local_bar % 4 == 1:
        if phrase_role in ("lift", "climax") and drop_variant == 2:
            return [(2.88, 0.24, third_line, "support"), (3.26, 0.30, fifth_line, "strong"), (3.70, 0.18, root_line, "support")]
        return [(2.92, 0.28, third_line, "support"), (3.44, 0.32, fifth_line, "support")]

    if local_bar % 4 == 3 and phrase_role == "climax":
        return [(2.36, 0.22, echo_b, "support"), (2.72, 0.22, fifth_line, "strong")]

    return []


def build_breakdown_memory_map_v2(identity_blueprint, motif_family, root: str, chords):
    hint = motif_family["breakdown_hint"]
    sig = identity_blueprint["hook_signature"]
    return {
        0: {
            "lead": [(0.00, 1.40, hint[0], "strong"), (2.85, 0.70, hint[1], "support")],
            "piano": [(0.00, 1.00, hint[0], "support"), (2.00, 1.10, hint[2], "support")],
            "vocal": [(0.50, 0.85, hint[1], "support"), (2.60, 0.90, hint[2], "strong")],
        },
        1: {
            "lead": [(0.75, 0.88, hint[1], "support"), (2.65, 1.00, hint[2], "strong")],
            "piano": [(0.50, 1.00, hint[0], "support"), (2.50, 1.00, hint[3], "support")],
            "vocal": [(0.80, 0.72, hint[1], "support"), (2.70, 0.95, hint[2], "strong")],
        },
        2: {
            "lead": [(0.00, 0.62, hint[1], "support"), (2.10, 0.60, hint[2], "support"), (3.35, 0.26, hint[3], "passing")],
            "piano": [(0.00, 0.95, hint[0], "support"), (2.00, 1.00, hint[1], "support")],
            "vocal": [(0.10, 0.58, hint[1], "support"), (2.25, 0.54, hint[3], "passing")],
        },
        3: {
            "lead": [(0.00, 0.82, hint[1], "support"), (2.35, 0.56, hint[3], "strong"), (3.00, 1.02, clamp(sig["resolve"] - 12, 60, 84), "hero")],
            "piano": [(0.00, 1.00, hint[1], "support"), (2.50, 1.15, hint[3], "strong")],
            "vocal": [(0.20, 0.70, hint[1], "support"), (2.82, 1.00, clamp(sig["resolve"] - 12, 60, 84), "hero")],
        },
    }


def compose_hook_cycle(identity_blueprint, drop_variant: int, phase: int, cycle_index: int):
    signature = identity_blueprint["hook_signature"]
    contour_type = identity_blueprint["track_contour_type"]

    register_shift = 0
    if contour_type == "late_peak":
        if drop_variant == 2 and phase >= 2:
            register_shift = 3
        elif drop_variant == 2 or phase >= 2:
            register_shift = 2
        elif phase == 1:
            register_shift = 1
    elif contour_type == "lift":
        register_shift = 1 if phase >= 1 else 0
        if drop_variant == 2:
            register_shift += 1
    else:
        if phase >= 2:
            register_shift = 2
        elif phase == 1:
            register_shift = 1

    hero_note = apply_register_shift(identity_blueprint["hero_note"], register_shift, 78, identity_blueprint["lead_register_peak"])
    drop2_apex_note = apply_register_shift(identity_blueprint["drop2_apex_note"], register_shift, 82, 102)

    bar1_notes = [
        signature["anchor"],
        signature["support"],
        signature["answer"],
        signature["dominant"],
    ]
    if cycle_index % 2 == 1:
        bar1_notes = [
            signature["anchor"],
            signature["passing"],
            signature["answer"],
            signature["dominant"],
        ]

    bar2_notes = [
        signature["answer"],
        signature["passing"],
        signature["pivot"],
        signature["tension"],
        signature["lift"],
    ]
    if phase == 0:
        bar2_notes = [
            signature["answer"],
            signature["passing"],
            signature["pivot"],
            signature["lift"],
        ]

    bar3_notes = [
        signature["support"],
        signature["anchor"],
        signature["pivot"],
        signature["lift"],
        signature["apex"] if drop_variant == 1 else drop2_apex_note - 2,
        signature["leap"],
    ]
    bar3_notes = enforce_signature_leap(
        [apply_register_shift(n, register_shift, 74, 100) for n in bar3_notes],
        preferred_intervals=tuple(identity_blueprint["leap_candidates"]),
    )

    bar1 = [
        {"bar_offset": 0, "beat_pos": 0.00, "beat_len": 0.70, "raw_note": apply_register_shift(bar1_notes[0], register_shift), "role": "strong", "allow_tension": False, "support_octave": True, "prefer_direction": 1},
        {"bar_offset": 0, "beat_pos": 1.00, "beat_len": 0.45, "raw_note": apply_register_shift(bar1_notes[1], register_shift), "role": "passing", "allow_tension": False, "support_octave": False, "prefer_direction": 0},
        {"bar_offset": 0, "beat_pos": 2.00, "beat_len": 0.45, "raw_note": apply_register_shift(bar1_notes[2], register_shift), "role": "support", "allow_tension": False, "support_octave": False, "prefer_direction": -1},
        {"bar_offset": 0, "beat_pos": 3.00, "beat_len": 0.68, "raw_note": apply_register_shift(bar1_notes[3], register_shift), "role": "strong", "allow_tension": False, "support_octave": False, "prefer_direction": 1},
    ]

    if len(bar2_notes) == 4:
        bar2 = [
            {"bar_offset": 1, "beat_pos": 0.00, "beat_len": 0.52, "raw_note": apply_register_shift(bar2_notes[0], register_shift), "role": "support", "allow_tension": False, "support_octave": False, "prefer_direction": -1},
            {"bar_offset": 1, "beat_pos": 1.00, "beat_len": 0.40, "raw_note": apply_register_shift(bar2_notes[1], register_shift), "role": "passing", "allow_tension": True, "support_octave": False, "prefer_direction": 1},
            {"bar_offset": 1, "beat_pos": 2.00, "beat_len": 0.44, "raw_note": apply_register_shift(bar2_notes[2], register_shift), "role": "support", "allow_tension": False, "support_octave": False, "prefer_direction": 1},
            {"bar_offset": 1, "beat_pos": 3.00, "beat_len": 0.66, "raw_note": apply_register_shift(bar2_notes[3], register_shift), "role": "strong", "allow_tension": False, "support_octave": False, "prefer_direction": 1},
        ]
    else:
        bar2 = [
            {"bar_offset": 1, "beat_pos": 0.00, "beat_len": 0.50, "raw_note": apply_register_shift(bar2_notes[0], register_shift), "role": "support", "allow_tension": False, "support_octave": False, "prefer_direction": -1},
            {"bar_offset": 1, "beat_pos": 1.00, "beat_len": 0.34, "raw_note": apply_register_shift(bar2_notes[1], register_shift), "role": "passing", "allow_tension": True, "support_octave": False, "prefer_direction": 1},
            {"bar_offset": 1, "beat_pos": 2.00, "beat_len": 0.42, "raw_note": apply_register_shift(bar2_notes[2], register_shift), "role": "support", "allow_tension": False, "support_octave": False, "prefer_direction": 1},
            {"bar_offset": 1, "beat_pos": 2.70, "beat_len": 0.22, "raw_note": apply_register_shift(bar2_notes[3], register_shift), "role": "passing", "allow_tension": True, "support_octave": False, "prefer_direction": 1},
            {"bar_offset": 1, "beat_pos": 3.00, "beat_len": 0.68, "raw_note": apply_register_shift(bar2_notes[4], register_shift), "role": "strong", "allow_tension": False, "support_octave": False, "prefer_direction": 1},
        ]

    bar3_positions = [(0.00, 0.42), (0.75, 0.24), (1.25, 0.34), (2.00, 0.36), (2.55, 0.24), (3.00, 0.64)]
    bar3_roles = ["support", "passing", "support", "strong", "passing", "strong"]
    bar3 = []
    for idx, ((beat_pos, beat_len), raw_note) in enumerate(zip(bar3_positions, bar3_notes)):
        bar3.append({
            "bar_offset": 2,
            "beat_pos": beat_pos,
            "beat_len": beat_len,
            "raw_note": raw_note,
            "role": bar3_roles[idx],
            "allow_tension": idx in (1, 4),
            "support_octave": idx == len(bar3_notes) - 1 and phase >= 1,
            "prefer_direction": 1,
        })

    if drop_variant == 2:
        bar4 = [
            {"bar_offset": 3, "beat_pos": 0.00, "beat_len": 0.40, "raw_note": apply_register_shift(signature["answer"], register_shift), "role": "support", "allow_tension": False, "support_octave": False, "prefer_direction": -1},
            {"bar_offset": 3, "beat_pos": 0.82, "beat_len": 0.32, "raw_note": apply_register_shift(signature["anchor"], register_shift), "role": "support", "allow_tension": False, "support_octave": False, "prefer_direction": 1},
            {"bar_offset": 3, "beat_pos": 1.58, "beat_len": 0.30, "raw_note": apply_register_shift(signature["pivot"], register_shift), "role": "strong", "allow_tension": False, "support_octave": False, "prefer_direction": 1},
            {"bar_offset": 3, "beat_pos": 2.20, "beat_len": 0.18, "raw_note": apply_register_shift(signature["tension"], register_shift), "role": "passing", "allow_tension": True, "support_octave": False, "prefer_direction": 1},
            {"bar_offset": 3, "beat_pos": 2.48, "beat_len": 0.18, "raw_note": apply_register_shift(signature["lift"], register_shift), "role": "strong", "allow_tension": False, "support_octave": False, "prefer_direction": 1},
            {"bar_offset": 3, "beat_pos": 2.82, "beat_len": 0.20, "raw_note": drop2_apex_note - 1, "role": "strong", "allow_tension": False, "support_octave": False, "prefer_direction": 1},
            {"bar_offset": 3, "beat_pos": 3.10, "beat_len": 0.94, "raw_note": hero_note, "role": "hero", "allow_tension": False, "support_octave": True, "prefer_direction": 1},
        ]
    else:
        bar4 = [
            {"bar_offset": 3, "beat_pos": 0.00, "beat_len": 0.42, "raw_note": apply_register_shift(signature["answer"], register_shift), "role": "support", "allow_tension": False, "support_octave": False, "prefer_direction": -1},
            {"bar_offset": 3, "beat_pos": 0.92, "beat_len": 0.34, "raw_note": apply_register_shift(signature["anchor"], register_shift), "role": "support", "allow_tension": False, "support_octave": False, "prefer_direction": 1},
            {"bar_offset": 3, "beat_pos": 1.74, "beat_len": 0.32, "raw_note": apply_register_shift(signature["pivot"], register_shift), "role": "strong", "allow_tension": False, "support_octave": False, "prefer_direction": 1},
            {"bar_offset": 3, "beat_pos": 2.52, "beat_len": 0.22, "raw_note": apply_register_shift(signature["lift"], register_shift), "role": "strong", "allow_tension": False, "support_octave": False, "prefer_direction": 1},
            {"bar_offset": 3, "beat_pos": 3.02, "beat_len": 0.90, "raw_note": hero_note, "role": "hero", "allow_tension": False, "support_octave": True, "prefer_direction": 1},
        ]

    phrase = bar1 + bar2 + bar3 + bar4
    return enforce_hero_note(phrase, hero_note)


def build_breakdown_emotion_map(identity_blueprint, root: str, chords):
    signature = identity_blueprint["hook_signature"]
    memory = clamp(identity_blueprint["breakdown_memory_note"], 60, 84)
    resolve = clamp(signature["resolve"] - 12, 60, 82)
    support = clamp(signature["support"] - 12, 60, 82)
    lift = clamp(signature["lift"] - 12, 62, 84)

    return {
        0: [
            (0.00, 1.85, memory, "strong"),
            (2.90, 0.65, support, "support"),
        ],
        1: [
            (0.85, 0.80, clamp(signature["answer"] - 12, 60, 82), "support"),
            (2.85, 0.95, lift, "strong"),
        ],
        2: [
            (0.00, 0.65, support, "support"),
            (2.10, 0.62, clamp(signature["pivot"] - 12, 60, 84), "support"),
            (3.35, 0.28, clamp(signature["tension"] - 12, 62, 84), "passing"),
        ],
        3: [
            (0.00, 0.82, clamp(signature["answer"] - 12, 60, 82), "support"),
            (2.25, 0.55, clamp(signature["payoff"] - 12, 60, 84), "strong"),
            (3.00, 1.02, resolve, "hero"),
        ],
    }



def generate_topline_candidate_from_identity(identity_blueprint, root: str, chord, vocal_min: int, vocal_max: int, global_bar: int, section_kind: str):
    motif_family = identity_blueprint.get("motif_family") or build_motif_family(identity_blueprint, root, [chord, chord])
    pool = chord_tones_in_range(chord, vocal_min, vocal_max)
    scale_pool = scale_notes_in_range(root, vocal_min, vocal_max)
    slot = global_bar % 4

    if section_kind == "breakdown":
        memory_map = build_breakdown_memory_map_v2(identity_blueprint, motif_family, root, [chord, chord])
        phrase = memory_map[slot]["vocal"]
        out = []
        for beat_pos, beat_len, raw_note, role in phrase:
            note = nearest_note_from_pool(clamp(raw_note, vocal_min, vocal_max), pool if role != "passing" else scale_pool)
            out.append((beat_pos, beat_len, note, role))
        return out

    phrase_role = ["statement", "variation", "lift", "climax"][slot] if slot < 4 else "statement"
    source = motif_family["statement"] if phrase_role == "statement" else motif_family[phrase_role]
    reduced = [source[0], source[min(2, len(source)-1)], source[min(4, len(source)-1)], source[-1]]

    beat_templates = {
        "statement": [(0.00, 0.72, "strong"), (1.60, 0.50, "support"), (3.00, 0.92, "support")],
        "variation": [(0.50, 0.60, "support"), (2.10, 0.42, "passing"), (2.82, 0.88, "strong")],
        "lift": [(0.00, 0.56, "support"), (1.52, 0.42, "support"), (3.02, 0.92, "strong")],
        "climax": [(0.00, 0.66, "support"), (2.58, 0.32, "strong"), (3.06, 1.12, "hero")],
    }
    out = []
    for idx, (beat_pos, beat_len, role) in enumerate(beat_templates[phrase_role]):
        raw_note = reduced[idx % len(reduced)] - 12
        note = nearest_note_from_pool(clamp(raw_note, vocal_min, vocal_max), pool if role != "passing" else scale_pool)
        out.append((beat_pos, beat_len, note, role))
    return out

def derive_bass_energy_mask_from_lead(lead_phrase_events, absolute_start_bar: int, bars_to_write: int):
    mask = {}
    for i in range(bars_to_write):
        bar_abs = absolute_start_bar + i
        bar_start = bar_tick(bar_abs)
        bar_end = bar_start + BAR_TICKS
        bar_events = [e for e in lead_phrase_events if bar_start <= e[0] < bar_end]
        hero_starts = [e[0] for e in bar_events if e[3] >= 118]
        if hero_starts:
            first_hero = min(hero_starts)
            mask[i] = {
                "hero_beat": max(0.0, min(3.75, (first_hero - bar_start) / TICKS)),
                "has_hero": True,
            }
        else:
            mask[i] = {"hero_beat": None, "has_hero": False}
    return mask


def section_tension_level(section_name: str, local_bar: int, total_bars: int) -> float:
    st = section_type(section_name)
    if st == "intro":
        return 0.20
    if st == "verse":
        return 0.35
    if st == "build":
        return 0.60 + 0.25 * (local_bar / max(1, total_bars - 1))
    if st == "drop":
        return 0.88 if "Drop 1" in section_name else 1.00
    if st == "breakdown":
        return 0.45 + 0.25 * (local_bar / max(1, total_bars - 1))
    if st == "outro":
        return 0.25
    return 0.50


def voicing_profile_for_section(section_kind: str, lift_level: int, tension_level: float):
    if section_kind == "intro":
        return {"spread_top": 0, "add_sus2": False, "add_high_root": False}
    if section_kind == "verse":
        return {"spread_top": 0, "add_sus2": tension_level > 0.35, "add_high_root": False}
    if section_kind == "build":
        return {"spread_top": 1, "add_sus2": True, "add_high_root": lift_level == 2}
    if section_kind == "drop":
        return {"spread_top": 1 if lift_level == 1 else 2, "add_sus2": False, "add_high_root": True}
    if section_kind == "breakdown":
        return {"spread_top": 0, "add_sus2": tension_level > 0.55, "add_high_root": False}
    return {"spread_top": 0, "add_sus2": False, "add_high_root": False}

def build_hook_rhythm_lock(drop_variant: int, phase: int):
    """
    Rhythm identity lock remains, but V3.0 keeps bar-end space
    available for more emphatic bar-4 payoffs.
    """
    if drop_variant == 1:
        if phase == 0:
            return [
                (0.00, 0.75),
                (1.00, 0.50),
                (2.00, 0.50),
                (3.00, 0.75),
            ]
        if phase == 1:
            return [
                (0.00, 0.75),
                (1.00, 0.50),
                (2.00, 0.50),
                (2.875, 0.25),
                (3.00, 0.75),
            ]
        if phase == 2:
            return [
                (0.00, 0.50),
                (1.00, 0.50),
                (2.00, 0.50),
                (2.75, 0.25),
                (3.00, 0.75),
            ]
        return [
            (0.00, 0.50),
            (0.75, 0.25),
            (1.00, 0.50),
            (2.00, 0.50),
            (2.75, 0.25),
            (3.00, 0.75),
        ]

    if phase == 0:
        return [
            (0.00, 0.75),
            (1.00, 0.50),
            (2.00, 0.50),
            (2.875, 0.25),
            (3.00, 0.75),
        ]
    if phase == 1:
        return [
            (0.00, 0.75),
            (1.00, 0.50),
            (1.75, 0.25),
            (2.00, 0.50),
            (2.875, 0.25),
            (3.00, 0.75),
        ]
    if phase == 2:
        return [
            (0.00, 0.50),
            (1.00, 0.50),
            (1.75, 0.25),
            (2.00, 0.50),
            (2.75, 0.25),
            (3.00, 0.50),
            (3.50, 0.25),
        ]
    return [
        (0.00, 0.50),
        (0.75, 0.25),
        (1.00, 0.50),
        (1.75, 0.25),
        (2.00, 0.50),
        (2.75, 0.25),
        (3.00, 0.50),
        (3.50, 0.25),
    ]




def build_pitch_sequence(signature, slot: int, phase: int, drop_variant: int):
    """
    V3.4:
    Phrase roles are now more explicit and more memorable.
    - bar 1 = statement with identity
    - bar 2 = answer with controlled colour
    - bar 3 = climb with a real signature leap
    - bar 4 = reserved for authored payoff handling elsewhere
    """
    if slot == 0:
        if phase == 0:
            return [signature["anchor"], signature["support"], signature["answer"], signature["dominant"]]
        if phase == 1:
            return [signature["anchor"], signature["support"], signature["answer"], signature["pivot"], signature["dominant"]]
        return [signature["anchor"], signature["support"], signature["answer"], signature["pivot"], signature["dominant"], signature["leap"]]

    if slot == 1:
        if phase == 0:
            return [signature["answer"], signature["passing"], signature["pivot"], signature["anchor"]]
        if phase == 1:
            return [signature["answer"], signature["passing"], signature["pivot"], signature["tension"], signature["lift"]]
        return [signature["answer"], signature["passing"], signature["pivot"], signature["tension"], signature["lift"], signature["pivot"]]

    if slot == 2:
        if phase == 0:
            return [signature["support"], signature["anchor"], signature["pivot"], signature["lift"]]
        if phase == 1:
            return [signature["support"], signature["anchor"], signature["pivot"], signature["lift"], signature["leap"]]
        if drop_variant == 2:
            return [signature["support"], signature["anchor"], signature["pivot"], signature["lift"], signature["apex"], signature["leap"]]
        return [signature["support"], signature["anchor"], signature["pivot"], signature["lift"], signature["apex"], signature["dominant"]]

    if drop_variant == 2 and phase >= 2:
        return [signature["answer"], signature["anchor"], signature["pivot"], signature["tension"], signature["apex"], signature["terminal"]]

    if phase == 0:
        return [signature["answer"], signature["anchor"], signature["pivot"], signature["payoff"]]
    if phase == 1:
        return [signature["answer"], signature["anchor"], signature["pivot"], signature["lift"], signature["payoff"]]
    return [signature["answer"], signature["anchor"], signature["pivot"], signature["tension"], signature["payoff"], signature["resolve"]]

def drop_phase_for_bar(local_bar: int, total_bars: int):
    if total_bars >= 32:
        if local_bar < 8:
            return 0
        if local_bar < 16:
            return 1
        if local_bar < 24:
            return 2
        return 3

    quarter = max(1, total_bars // 4)
    if local_bar < quarter:
        return 0
    if local_bar < quarter * 2:
        return 1
    if local_bar < quarter * 3:
        return 2
    return 3




def build_bar4_payoff_phrase(signature, drop_variant: int, phase: int):
    """
    V3.4:
    Bar 4 must feel like the emotional command point of the hook.
    It now uses a clearer pre-lift, a higher terminal lane, and a longer final hold.
    """
    if drop_variant == 2:
        if phase >= 2:
            return [
                (0.00, 0.42, signature["answer"]),
                (0.78, 0.40, signature["anchor"]),
                (1.56, 0.40, signature["pivot"]),
                (2.20, 0.22, signature["tension"]),
                (2.52, 0.22, signature["lift"]),
                (2.82, 0.24, signature["apex"]),
                (3.12, 0.76, signature["terminal"]),
            ]
        return [
            (0.00, 0.44, signature["answer"]),
            (0.92, 0.40, signature["anchor"]),
            (1.74, 0.38, signature["pivot"]),
            (2.46, 0.24, signature["lift"]),
            (2.84, 0.24, signature["accent"]),
            (3.14, 0.70, signature["final"]),
        ]

    if phase >= 2:
        return [
            (0.00, 0.44, signature["answer"]),
            (0.86, 0.40, signature["anchor"]),
            (1.66, 0.38, signature["pivot"]),
            (2.38, 0.22, signature["tension"]),
            (2.70, 0.24, signature["lift"]),
            (3.04, 0.74, signature["accent"]),
        ]
    return [
        (0.00, 0.45, signature["answer"]),
        (0.94, 0.40, signature["anchor"]),
        (1.78, 0.38, signature["pivot"]),
        (2.58, 0.24, signature["lift"]),
        (3.00, 0.78, signature["payoff"]),
    ]




def build_drop2_arrival_phrase(signature, phase: int, bar_index: int):
    """
    V3.4:
    Drop 2 must escalate across pitch, density, and authority.
    The first two bars now open higher and finish with a more obvious reward.
    """
    if bar_index == 0:
        if phase >= 2:
            return [
                (0.00, 0.64, signature["dominant"]),
                (0.76, 0.32, signature["pivot"]),
                (1.26, 0.26, signature["tension"]),
                (1.64, 0.28, signature["lift"]),
                (2.02, 0.22, signature["apex"]),
                (2.32, 0.22, signature["leap"]),
                (2.66, 0.24, signature["accent"]),
                (3.00, 0.70, signature["terminal"]),
            ]
        return [
            (0.00, 0.72, signature["dominant"]),
            (0.92, 0.42, signature["pivot"]),
            (1.78, 0.28, signature["lift"]),
            (2.26, 0.24, signature["apex"]),
            (2.72, 0.26, signature["accent"]),
            (3.08, 0.58, signature["final"]),
        ]

    if phase >= 2:
        return [
            (0.00, 0.38, signature["answer"]),
            (0.62, 0.34, signature["anchor"]),
            (1.10, 0.22, signature["tension"]),
            (1.46, 0.26, signature["pivot"]),
            (1.92, 0.28, signature["lift"]),
            (2.34, 0.22, signature["apex"]),
            (2.68, 0.24, signature["payoff"]),
            (3.02, 0.60, signature["accent"]),
        ]
    return [
        (0.00, 0.46, signature["answer"]),
        (0.86, 0.40, signature["anchor"]),
        (1.62, 0.24, signature["pivot"]),
        (2.04, 0.28, signature["lift"]),
        (2.62, 0.24, signature["payoff"]),
        (3.02, 0.54, signature["accent"]),
    ]




def build_breakdown_recall_blueprint(root: str, chords):
    signature = build_signature_hook_cell(root, chords[0], chords[1])
    return {
        0: [
            (0.00, 1.85, signature["anchor"] - 12),
            (2.90, 0.70, signature["support"] - 12),
        ],
        1: [
            (0.75, 0.90, signature["answer"] - 12),
            (2.80, 1.05, signature["lift"] - 12),
        ],
        2: [
            (0.00, 0.70, signature["support"] - 12),
            (2.10, 0.70, signature["pivot"] - 12),
            (3.35, 0.35, signature["tension"] - 12),
        ],
        3: [
            (0.00, 0.85, signature["answer"] - 12),
            (2.30, 0.55, signature["payoff"] - 12),
            (3.00, 0.95, signature["resolve"] - 12),
        ],
    }

def adapt_note_to_bar(note: int, root: str, chord, section_kind: str):
    chord_pool = chord_tones_in_range(chord, 60, 98)
    scale_pool = scale_notes_in_range(root, 60, 98)

    if section_kind in ("drop", "breakdown"):
        if note in chord_pool:
            return note
        return nearest_note_from_pool(note, chord_pool)

    if note in chord_pool:
        return note
    return nearest_note_from_pool(note, scale_pool)





def generate_drop_lead_events(root: str, chords, absolute_start_bar: int, bars_to_write: int, velocity: int, drop_variant: int, identity_blueprint, section_name: str = "Drop"):
    """
    V3.6 lead rules:
    - write drop phrases from a motif family rather than one repeating phrase template
    - assign phrase roles across 4-bar cycles
    - preserve hero-note enforcement while evolving its setup by phrase role
    - reserve final Drop 2 cycles for a real climax form
    """
    events = []
    cycles = max(1, (bars_to_write + 3) // 4)
    motif_family = build_motif_family(identity_blueprint, root, chords)
    identity_blueprint["motif_family"] = motif_family
    phrase_roles = plan_drop_phrase_roles(section_name, bars_to_write)

    for cycle_index in range(cycles):
        cycle_start_local = cycle_index * 4
        if cycle_start_local >= bars_to_write:
            break

        phase = drop_phase_for_bar(min(cycle_start_local, bars_to_write - 1), bars_to_write)
        phrase_role = phrase_roles[min(cycle_index, len(phrase_roles) - 1)]
        if "drop 2" in section_name.lower():
            window = plan_final_climax_window(section_name, cycle_start_local, bars_to_write)
            if window["in_final_8"] and phrase_role == "statement":
                phrase_role = "lift"
            if window["is_peak_phrase"]:
                phrase_role = "climax"

        phrase = compose_motif_phrase(identity_blueprint, motif_family, phrase_role, drop_variant, phase, cycle_index)

        previous_note = None
        for event in phrase:
            local_bar = cycle_start_local + event["bar_offset"]
            if local_bar >= bars_to_write:
                continue

            absolute_bar = absolute_start_bar + local_bar
            chord = chords[absolute_bar % len(chords)]
            bar_start = bar_tick(absolute_bar)

            note = adapt_drop_note_to_bar(
                event["raw_note"],
                root,
                chord,
                previous_note=previous_note,
                prefer_direction=event.get("prefer_direction", 1),
                allow_tension=event.get("allow_tension", False),
            )
            window = plan_final_climax_window(section_name, local_bar, bars_to_write)
            peak_high = 102 if window["in_final_8"] else identity_blueprint["lead_register_peak"]
            note = clamp(note, identity_blueprint["lead_register_base"], peak_high)

            role = event["role"]
            role_velocity = phrase_role_velocity_offset(role)
            phrase_boost = {"statement": 0, "variation": 2, "lift": 5, "climax": 9}[event.get("phrase_role", phrase_role)]
            if window["in_final_4"]:
                phrase_boost += 4
            note_velocity = clamp(velocity + role_velocity + phrase_boost, 1, 124)
            add_length = tick(event["beat_len"] * phrase_role_length_multiplier(role))
            start_tick_value = bar_start + tick(event["beat_pos"])

            events.append((start_tick_value, note, add_length, note_velocity))
            previous_note = note

            if event.get("support_octave"):
                add_lead_support_octave(events, start_tick_value, note, add_length, note_velocity)

    return events


def generate_build_lead_events(root: str, chords, absolute_start_bar: int, bars_to_write: int, velocity: int, build_variant: int, identity_blueprint):
    signature = identity_blueprint["hook_signature"]
    events = []

    for i in range(bars_to_write):
        bar_start = bar_tick(absolute_start_bar + i)
        chord = chords[(absolute_start_bar + i) % len(chords)]
        local_slot = i % 4
        last_four_bars = i >= max(0, bars_to_write - 4)

        phrase_map = {
            0: [(0.00, 0.75, signature["anchor"]), (2.00, 0.75, signature["support"])],
            1: [(0.50, 0.70, signature["answer"]), (2.45, 0.78, signature["lift"])],
            2: [(0.00, 0.55, signature["support"]), (1.50, 0.50, signature["anchor"]), (3.00, 0.52, signature["pivot"])],
            3: [(0.00, 0.72, signature["answer"]), (2.30, 0.62, signature["lift"])],
        }

        phrase = phrase_map[local_slot][:]

        if build_variant == 2 and local_slot in (2, 3):
            phrase.append((3.55, 0.18, signature["tension"] if local_slot == 2 else signature["apex"]))

        if last_four_bars:
            if i == bars_to_write - 3:
                phrase.append((3.20, 0.45, signature["pivot"]))
            if i == bars_to_write - 2:
                phrase.append((3.20, 0.22, signature["lift"]))
                phrase.append((3.48, 0.24, signature["apex"]))
            if i == bars_to_write - 1:
                phrase = [
                    (0.00, 0.50, signature["answer"]),
                    (1.00, 0.50, signature["anchor"]),
                    (2.00, 0.50, signature["pivot"]),
                    (3.00, 0.35, signature["lift"]),
                ]

        for idx, (beat_pos, beat_len, raw_note) in enumerate(phrase):
            note = adapt_note_to_bar(raw_note, root, chord, "build")
            note = clamp(note, 72, 98)
            role = "support"
            if idx == len(phrase) - 1:
                role = "strong"
            if last_four_bars and i == bars_to_write - 1 and idx == len(phrase) - 1:
                role = "strong"
            vel = clamp(velocity + phrase_role_velocity_offset(role) - 8, 50, 122)
            if last_four_bars and beat_pos >= 3.0:
                vel = clamp(vel + 4, 50, 122)
            events.append((bar_start + tick(beat_pos), note, tick(beat_len * phrase_role_length_multiplier(role)), vel))

    return events



def generate_breakdown_recall_events(root: str, chords, absolute_start_bar: int, bars_to_write: int, velocity: int, identity_blueprint):
    motif_family = identity_blueprint.get("motif_family") or build_motif_family(identity_blueprint, root, chords)
    identity_blueprint["motif_family"] = motif_family
    memory_map = build_breakdown_memory_map_v2(identity_blueprint, motif_family, root, chords)
    events = []

    for i in range(bars_to_write):
        local_slot = i % 4
        chord = chords[(absolute_start_bar + i) % len(chords)]
        bar_start = bar_tick(absolute_start_bar + i)

        phrase = memory_map[local_slot]["lead"][:]
        if local_slot == 3 and i >= max(0, bars_to_write - 8):
            phrase.append((3.56, 0.22, clamp(motif_family["breakdown_hint"][2], 60, 84), "passing"))

        for beat_pos, beat_len, raw_note, role in phrase:
            note = adapt_note_to_bar(raw_note, root, chord, "breakdown")
            note = clamp(note, 60, 84)
            vel = clamp(velocity - 18 + phrase_role_velocity_offset(role), 36, 102)
            length_mult = 1.08 if role in ("strong", "hero") else phrase_role_length_multiplier(role)
            events.append((bar_start + tick(beat_pos), note, tick(beat_len * length_mult), vel))

    return events

def add_phrase_events_to_track(track_events, phrase_events):
    for start, note, length, vel in phrase_events:
        add_events(track_events, start, note, length, velocity=vel)



def generate_vocal_phrase(identity_blueprint, root: str, chord, vocal_min: int, vocal_max: int, bar_index: int, section_kind: str):
    return generate_topline_candidate_from_identity(identity_blueprint, root, chord, vocal_min, vocal_max, bar_index, section_kind)

def generate_breakdown_piano_phrase(root: str, chord, global_bar: int):
    pool = chord_tones_in_range(chord, 60, 79)
    anchor = nearest_note_from_pool(note_name_to_midi(root, 1, 4), pool)
    support = nearest_note_from_pool(note_name_to_midi(root, 3, 4), pool)
    fifth = nearest_note_from_pool(note_name_to_midi(root, 5, 4), pool)
    seventh = nearest_note_from_pool(note_name_to_midi(root, 7, 4), scale_notes_in_range(root, 60, 79))

    if global_bar % 4 == 0:
        return [(0.00, 1.0, anchor), (2.00, 1.0, support)]
    if global_bar % 4 == 1:
        return [(0.50, 1.0, anchor), (2.50, 1.0, fifth)]
    if global_bar % 4 == 2:
        return [(0.00, 1.0, support), (2.00, 1.0, seventh)]
    return [(0.00, 1.0, support), (2.50, 1.25, anchor)]


def add_offbeat_bass(track_events, start_tick_value: int, root_note: int, velocity: int):
    for beat_pos in [0.5, 1.5, 2.5, 3.5]:
        add_events(track_events, start_tick_value + tick(beat_pos), root_note, tick(0.42), velocity=velocity)



def add_rolling_bass(track_events, start_tick_value: int, chord, velocity: int, drop_variant: int, local_bar: int, total_bars: int, hero_info=None):
    root_note = chord["root"] - 24
    fifth_note = chord["fifth"] - 24
    phase = drop_phase_for_bar(local_bar, total_bars)

    if drop_variant == 2:
        if phase < 2:
            pattern = [root_note, root_note, fifth_note, root_note, root_note + 12, root_note, fifth_note, root_note]
            lengths = [0.22, 0.20, 0.22, 0.18, 0.12, 0.18, 0.20, 0.22]
        else:
            pattern = [root_note, root_note, fifth_note, root_note, root_note + 12, fifth_note, root_note, root_note]
            lengths = [0.22, 0.20, 0.22, 0.16, 0.12, 0.18, 0.18, 0.22]
        velocities = [velocity, velocity - 2, velocity - 3, velocity - 5, velocity - 10, velocity - 3, velocity - 4, velocity]
    else:
        if phase == 0:
            pattern = [root_note, root_note, fifth_note, root_note, root_note, root_note, fifth_note, root_note]
            lengths = [0.22] * 8
        elif phase == 1:
            pattern = [root_note, root_note, fifth_note, root_note, root_note + 12, root_note, fifth_note, root_note]
            lengths = [0.22, 0.22, 0.22, 0.18, 0.12, 0.18, 0.20, 0.22]
        else:
            pattern = [root_note, root_note, fifth_note, root_note, root_note + 12, fifth_note, root_note, root_note]
            lengths = [0.22, 0.20, 0.22, 0.16, 0.12, 0.18, 0.18, 0.22]
        velocities = [velocity] * 8

    hero_beat = hero_info["hero_beat"] if hero_info and hero_info.get("has_hero") else None

    for i, note in enumerate(pattern):
        beat_pos = i * 0.5

        if hero_beat is not None and beat_pos >= max(0.0, hero_beat - 0.10):
            note = root_note
            velocities[i] = clamp(velocities[i] - 10, 54, 118)
            lengths[i] = min(lengths[i], 0.16)

        add_events(
            track_events,
            start_tick_value + tick(beat_pos),
            note,
            tick(lengths[i]),
            velocity=clamp(velocities[i], 60, 122)
        )

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
            roll_positions = [0, 0.5, 1.0, 1.5, 2.0, 2.25, 2.5, 2.75, 3.0, 3.125, 3.25, 3.375, 3.5, 3.625, 3.75]
        else:
            roll_positions = [0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.25, 3.5, 3.75]

        for idx, beat_pos in enumerate(roll_positions):
            add_events(track_events, start_tick_value + tick(beat_pos), 38, tick(0.08), velocity=clamp(76 + idx * 3, 76, 124))


def add_hats(track_events, start_tick_value: int, section_kind: str, velocity: int, drop_variant: int = 1, local_bar: int = 0, total_bars: int = 32):
    if section_kind in ("build", "drop"):
        for beat_pos in [0.5, 1.5, 2.5, 3.5]:
            add_events(track_events, start_tick_value + tick(beat_pos), 46, tick(0.14), velocity=velocity)

    if section_kind != "drop":
        return

    phase = drop_phase_for_bar(local_bar, total_bars)

    if drop_variant == 1:
        if phase == 0:
            drop_positions = [0.75, 1.75, 2.75, 3.75]
            hat_velocity = clamp(velocity - 22, 32, 90)
        elif phase == 1:
            drop_positions = [0.25, 0.75, 1.75, 2.75, 3.75]
            hat_velocity = clamp(velocity - 20, 34, 94)
        else:
            drop_positions = [0.25, 0.75, 1.75, 2.25, 2.75, 3.75]
            hat_velocity = clamp(velocity - 18, 36, 96)
    else:
        if phase == 0:
            drop_positions = [0.25, 0.75, 1.25, 1.75, 2.25, 2.75, 3.25, 3.75]
            hat_velocity = clamp(velocity - 16, 38, 102)
        elif phase == 1:
            drop_positions = [0.25, 0.75, 1.25, 1.75, 2.25, 2.75, 3.25, 3.75, 1.125, 3.125]
            hat_velocity = clamp(velocity - 14, 40, 106)
        elif phase == 2:
            drop_positions = [0.25, 0.75, 1.25, 1.75, 2.25, 2.75, 3.25, 3.75, 0.125, 2.125]
            hat_velocity = clamp(velocity - 13, 42, 108)
        else:
            drop_positions = [0.25, 0.75, 1.25, 1.75, 2.25, 2.75, 3.25, 3.75, 0.125, 1.125, 2.125]
            hat_velocity = clamp(velocity - 12, 44, 110)

    for beat_pos in drop_positions:
        add_events(track_events, start_tick_value + tick(beat_pos), 42, tick(0.08), velocity=hat_velocity)



def add_pad_strings_piano(tracks, start_tick_value: int, chord, section_kind: str, velocity: int, local_bar: int, lift_level: int = 1, tension_level: float = 0.5, section_name: str = ""):
    low_chord = [chord["root"] - 12, chord["third"] - 12, chord["fifth"] - 12]
    full_chord = [chord["root"], chord["third"], chord["fifth"]]
    bright_chord = [chord["root"], chord["third"], chord["fifth"], chord["root"] + 12]
    profile = voicing_profile_for_section(section_kind, lift_level, tension_level)

    if profile["add_sus2"]:
        sus2 = clamp(chord["root"] + 2, chord["root"] - 1, chord["root"] + 14)
        if sus2 not in full_chord:
            full_chord = sorted(full_chord + [sus2])
        if sus2 - 12 not in low_chord:
            low_chord = sorted(low_chord + [sus2 - 12])

    if profile["add_high_root"]:
        bright_chord = sorted(set(bright_chord + [chord["root"] + 24]))

    if profile["spread_top"] >= 2:
        bright_chord = sorted(set(bright_chord + [chord["third"] + 12]))

    if section_kind in ("intro", "breakdown"):
        add_events(tracks["pad"], start_tick_value, low_chord, tick(4), velocity=clamp(velocity - 20, 40, 100))
        if local_bar % 2 == 0:
            string_notes = [chord["root"], chord["third"], chord["fifth"] + 12]
            if section_kind == "breakdown" and tension_level > 0.55:
                string_notes.append(chord["root"] + 12)
            add_events(tracks["strings"], start_tick_value, string_notes, tick(4), velocity=clamp(velocity - 24, 38, 96))

    elif section_kind == "verse":
        add_events(tracks["piano"], start_tick_value, full_chord, tick(2), velocity=clamp(velocity - 16, 42, 102))
        add_events(tracks["pad"], start_tick_value, low_chord, tick(4), velocity=clamp(velocity - 24, 36, 96))

    elif section_kind == "build":
        add_events(tracks["pluck"], start_tick_value, full_chord, tick(0.9), velocity=clamp(velocity - 12, 48, 112))
        add_events(tracks["pad"], start_tick_value, low_chord, tick(4), velocity=clamp(velocity - 26, 36, 96))
        if lift_level == 2 and local_bar % 2 == 1:
            add_events(tracks["strings"], start_tick_value + tick(2), [chord["third"], chord["fifth"], chord["root"] + 12], tick(2), velocity=clamp(velocity - 10, 52, 118))

    elif section_kind == "drop":
        spread_chord = bright_chord[:]
        add_events(tracks["supersaw_chords"], start_tick_value, spread_chord, tick(4), velocity=velocity)
        add_events(tracks["pad"], start_tick_value, low_chord, tick(4), velocity=clamp(velocity - 28, 34, 90))
        if local_bar % 2 == 0:
            string_notes = [chord["root"], chord["third"], chord["fifth"] + 12]
            if lift_level == 2:
                string_notes.extend([chord["root"] + 24, chord["third"] + 12])
            add_events(tracks["strings"], start_tick_value, sorted(set(string_notes)), tick(2), velocity=clamp(velocity - 18, 45, 112))

        if lift_level == 1:
            pluck_phrase = [
                (0.75, chord["root"] + 12, 0.18, clamp(velocity - 20, 42, 96)),
                (2.75, chord["third"] + 12, 0.18, clamp(velocity - 18, 42, 98)),
            ]
        else:
            pluck_phrase = [
                (0.50, chord["root"] + 12, 0.16, clamp(velocity - 18, 46, 100)),
                (1.50, chord["third"] + 12, 0.16, clamp(velocity - 16, 46, 102)),
                (2.50, chord["fifth"] + 12, 0.16, clamp(velocity - 14, 48, 104)),
                (3.25, chord["root"] + 24, 0.22, clamp(velocity - 10, 52, 108)),
            ]

        for beat_pos, note, beat_len, note_velocity in pluck_phrase:
            add_events(
                tracks["pluck"],
                start_tick_value + tick(beat_pos),
                note,
                tick(beat_len),
                velocity=note_velocity
            )

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




def add_arp(tracks, start_tick_value: int, chord, section_kind: str, velocity: int, drop_variant: int = 1, local_bar: int = 0, total_bars: int = 32, phrase_role: str = "statement", section_name: str = ""):
    if section_kind not in ("build", "drop", "breakdown"):
        return

    if section_kind == "breakdown":
        arp_phrase = [
            (0.90, chord["third"] + 24, 0.22),
            (2.85, chord["fifth"] + 24, 0.22),
        ]
        for beat_pos, note, beat_len in arp_phrase:
            add_events(
                tracks["arp"],
                start_tick_value + tick(beat_pos),
                clamp(note, 88, 103),
                tick(beat_len),
                velocity=clamp(velocity - 18, 28, 74)
            )
        return

    if section_kind == "build":
        arp_phrase = [
            (0.50, chord["root"] + 24, 0.24),
            (1.50, chord["third"] + 24, 0.24),
            (2.50, chord["fifth"] + 24, 0.24),
            (3.50, chord["third"] + 24, 0.26),
        ]
        for beat_pos, note, beat_len in arp_phrase:
            add_events(
                tracks["arp"],
                start_tick_value + tick(beat_pos),
                clamp(note, 88, 104),
                tick(beat_len),
                velocity=clamp(velocity - 8, 34, 86)
            )
        return

    phase = drop_phase_for_bar(local_bar, total_bars)
    bar_slot = local_bar % 4
    climax_window = plan_final_climax_window(section_name, local_bar, total_bars)

    if drop_variant == 1:
        if bar_slot == 0:
            arp_phrase = [
                (0.50, chord["third"] + 24, 0.20),
                (2.50, chord["fifth"] + 24, 0.20),
            ]
        elif bar_slot == 1:
            arp_phrase = [
                (0.50, chord["root"] + 24, 0.18),
                (1.50, chord["third"] + 24, 0.18),
                (3.50, chord["fifth"] + 24, 0.22),
            ]
        elif bar_slot == 2:
            arp_phrase = [
                (0.50, chord["root"] + 24, 0.18),
                (1.50, chord["third"] + 24, 0.18),
                (2.50, chord["fifth"] + 24, 0.18),
                (3.50, chord["root"] + 36, 0.24),
            ]
        else:
            arp_phrase = [
                (0.50, chord["third"] + 24, 0.18),
                (2.50, chord["root"] + 24, 0.22),
            ]
        arp_velocity = clamp(velocity - 14 + (3 if phrase_role in ("lift","climax") else 0), 30, 90)
    else:
        if bar_slot == 0:
            arp_phrase = [
                (0.25, chord["root"] + 24, 0.16),
                (0.50, chord["third"] + 24, 0.16),
                (1.50, chord["fifth"] + 24, 0.16),
                (2.50, chord["root"] + 36, 0.18),
                (3.50, chord["third"] + 24, 0.20),
            ]
        elif bar_slot == 1:
            arp_phrase = [
                (0.50, chord["third"] + 24, 0.16),
                (1.25, chord["fifth"] + 24, 0.16),
                (1.50, chord["root"] + 36, 0.16),
                (2.50, chord["third"] + 24, 0.16),
                (3.25, chord["fifth"] + 24, 0.18),
                (3.50, chord["root"] + 24, 0.18),
            ]
        elif bar_slot == 2:
            arp_phrase = [
                (0.25, chord["root"] + 24, 0.16),
                (0.50, chord["third"] + 24, 0.16),
                (1.25, chord["fifth"] + 24, 0.16),
                (1.50, chord["root"] + 36, 0.16),
                (2.50, chord["third"] + 24, 0.18),
                (3.25, chord["fifth"] + 24, 0.18),
                (3.50, chord["root"] + 36, 0.20),
            ]
        else:
            arp_phrase = [
                (0.50, chord["third"] + 24, 0.16),
                (2.50, chord["fifth"] + 24, 0.16),
                (3.50, chord["root"] + 36, 0.22),
            ]

        if phase >= 2 and bar_slot in (1, 2):
            arp_phrase = arp_phrase + [(3.75, chord["third"] + 24, 0.12)]

        arp_velocity = clamp(velocity - 10, 34, 94)

    for beat_pos, note, beat_len in arp_phrase:
        add_events(
            tracks["arp"],
            start_tick_value + tick(beat_pos),
            clamp(note, 88, 108),
            tick(beat_len),
            velocity=arp_velocity
        )




def add_countermelody(tracks, start_tick_value: int, chord, local_bar: int, velocity: int, drop_variant: int = 1, total_bars: int = 32, hero_info=None, motif_family=None, phrase_role: str = "statement", section_name: str = "Drop"):
    phase = drop_phase_for_bar(local_bar, total_bars)

    if hero_info and hero_info.get("has_hero") and local_bar % 4 == 3 and phrase_role != "climax":
        return

    if motif_family is None:
        motif_family = {
            "cell": [clamp(chord["root"] + 12, 72, 84), clamp(chord["third"] + 12, 72, 84), clamp(chord["fifth"] + 12, 72, 84)]
        }

    phrase = build_countermelody_response(motif_family, phrase_role, chord, local_bar, drop_variant, phase)
    if not phrase:
        return

    climax_window = plan_final_climax_window(section_name, local_bar, total_bars)
    for beat_pos, beat_len, note, role in phrase:
        local_velocity = velocity + phrase_role_velocity_offset(role)
        if phrase_role in ("lift", "climax"):
            local_velocity += 4
        if climax_window["in_final_8"]:
            local_velocity += 4
        if climax_window["in_final_4"]:
            local_velocity += 3
            beat_len *= 1.08
        add_events(
            tracks["countermelody"],
            start_tick_value + tick(beat_pos),
            clamp(note, 60, 84),
            tick(beat_len * phrase_role_length_multiplier(role)),
            velocity=clamp(local_velocity, 42, 112)
        )

def add_predrop_impact_gap(tracks, bar_index: int):
    gap_start = bar_tick(bar_index) + tick(3.75)

    silence_note_ranges = {
        "pad": range(24, 109),
        "supersaw_chords": range(24, 109),
        "strings": range(24, 109),
        "arp": range(24, 109),
        "lead": range(24, 109),
        "piano": range(24, 109),
        "pluck": range(24, 109),
        "countermelody": range(24, 109),
        "vocal_melody": range(24, 109),
    }

    for stem, note_range in silence_note_ranges.items():
        for note in note_range:
            tracks[stem].append((gap_start, Message("note_off", note=int(note), velocity=0, channel=0, time=0)))

    tracks["hats"].append((gap_start, Message("note_off", note=42, velocity=0, channel=0, time=0)))
    tracks["hats"].append((gap_start, Message("note_off", note=46, velocity=0, channel=0, time=0)))



def generate_pack(bpm: int, key_root: str, progression: str, arrangement: str, energy: str, vocalist: str, out_zip: Path):
    tempo = bpm2tempo(bpm)
    sections = arrange_sections(arrangement)
    chords = progression_chords(key_root, progression)
    energy_factor = ENERGY_LEVELS[energy]
    vocal_min, vocal_max = VOCAL_RANGES[vocalist]
    identity_blueprint = build_track_identity_blueprint(key_root, chords, arrangement, energy)
    motif_family = build_motif_family(identity_blueprint, key_root, chords)
    identity_blueprint["motif_family"] = motif_family

    tracks = {stem: [] for stem in STEMS}
    markers = []

    build2_start_bar = None
    for sec in sections:
        if sec["name"].lower() == "build 2":
            build2_start_bar = sec["start_bar"]

    if build2_start_bar is not None:
        markers.append((bar_tick(build2_start_bar) + tick(3.75), "Pre-Drop Impact Gap"))

    drop_lead_maps = {}

    for sec in sections:
        markers.append((bar_tick(sec["start_bar"]), sec["name"] + " (" + str(sec["bars"]) + " bars)"))
        sec_kind = section_type(sec["name"])
        sec_profile = energy_profile(sec["name"], energy_factor)

        sec_name_lower = sec["name"].lower()
        is_drop_2 = "drop 2" in sec_name_lower
        is_build_2 = "build 2" in sec_name_lower

        lift_level = 2 if (is_drop_2 or is_build_2) else 1
        drop_variant = 2 if is_drop_2 else 1
        build_variant = 2 if is_build_2 else 1

        if sec_kind == "drop":
            phrase_roles = plan_drop_phrase_roles(sec["name"], sec["bars"])
            lead_events = generate_drop_lead_events(
                key_root,
                chords,
                sec["start_bar"],
                sec["bars"],
                clamp(sec_profile["velocity"] + (6 if is_drop_2 else 0), 1, 124),
                drop_variant,
                identity_blueprint,
                section_name=sec["name"],
            )
            add_phrase_events_to_track(tracks["lead"], lead_events)
            drop_lead_maps[sec["start_bar"]] = derive_bass_energy_mask_from_lead(lead_events, sec["start_bar"], sec["bars"])

        elif sec_kind == "build":
            phrase_roles = ["statement"] * max(1, (sec["bars"] + 3) // 4)
            build_lead_events = generate_build_lead_events(
                key_root,
                chords,
                sec["start_bar"],
                sec["bars"],
                clamp(sec_profile["velocity"] + (4 if is_build_2 else 0), 1, 124),
                build_variant,
                identity_blueprint,
            )
            add_phrase_events_to_track(tracks["lead"], build_lead_events)

        elif sec_kind == "breakdown":
            phrase_roles = ["statement"] * max(1, (sec["bars"] + 3) // 4)
            breakdown_events = generate_breakdown_recall_events(
                key_root,
                chords,
                sec["start_bar"],
                sec["bars"],
                sec_profile["velocity"],
                identity_blueprint,
            )
            add_phrase_events_to_track(tracks["lead"], breakdown_events)

        for local_bar in range(sec["bars"]):
            global_bar = sec["start_bar"] + local_bar
            cycle_index = local_bar // 4
            phrase_role = phrase_roles[min(cycle_index, len(phrase_roles) - 1)] if sec_kind in ("drop", "build", "breakdown") else "statement"
            chord = choose_chord(chords, global_bar)
            start = bar_tick(global_bar)
            is_last_bar_of_section = local_bar == sec["bars"] - 1
            tension_level = section_tension_level(sec["name"], local_bar, sec["bars"])

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
                lift_level=lift_level,
                tension_level=tension_level,
                section_name=sec["name"],
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
                drop_variant=drop_variant,
                local_bar=local_bar,
                total_bars=sec["bars"]
            )
            add_arp(
                tracks,
                start,
                chord,
                sec_kind,
                clamp(local_velocity - 22, 46, 104),
                drop_variant=drop_variant,
                local_bar=local_bar,
                total_bars=sec["bars"],
                phrase_role=phrase_role,
                section_name=sec["name"]
            )

            if sec_kind in ("verse", "outro"):
                add_offbeat_bass(
                    tracks["offbeat_bass"],
                    start,
                    chord["root"] - 24,
                    clamp(local_velocity - 6, 70, 116)
                )

            hero_info = None
            if sec_kind == "drop":
                hero_info = drop_lead_maps.get(sec["start_bar"], {}).get(local_bar)

                add_rolling_bass(
                    tracks["rolling_bass"],
                    start,
                    chord,
                    clamp(local_velocity - 10, 72, 120),
                    drop_variant=drop_variant,
                    local_bar=local_bar,
                    total_bars=sec["bars"],
                    hero_info=hero_info,
                )
                add_countermelody(
                    tracks,
                    start,
                    chord,
                    local_bar,
                    clamp(local_velocity - 24, 44, 100),
                    drop_variant=drop_variant,
                    total_bars=sec["bars"],
                    hero_info=hero_info,
                    motif_family=motif_family,
                    phrase_role=phrase_role,
                    section_name=sec["name"],
                )

            if sec_kind in ("verse", "breakdown", "build"):
                vocal_phrase = generate_vocal_phrase(identity_blueprint, key_root, chord, vocal_min, vocal_max, global_bar, sec_kind)
                for beat_pos, beat_len, note, role in vocal_phrase:
                    add_events(
                        tracks["vocal_melody"],
                        start + tick(beat_pos),
                        note,
                        tick(beat_len * phrase_role_length_multiplier(role)),
                        velocity=clamp(local_velocity - 6 + phrase_role_velocity_offset(role), 54, 112)
                    )

        if is_build_2:
            add_predrop_impact_gap(tracks, sec["end_bar"] - 1)

    out_zip.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        td = Path(temp_dir)

        combined = MidiFile(type=1, ticks_per_beat=TICKS)
        combined.tracks.append(finalise_track("Markers", tempo, [], markers=markers))

        for stem in STEMS:
            stem_midi = MidiFile(type=1, ticks_per_beat=TICKS)
            stem_track = finalise_track(stem, tempo, tracks[stem][:], markers=markers if stem == "kick" else None)
            stem_midi.tracks.append(stem_track)
            stem_path = td / (stem + ".mid")
            stem_midi.save(stem_path)
            combined.tracks.append(finalise_track(stem, tempo, tracks[stem][:]))

        full_arrangement_path = td / "full_arrangement.mid"
        combined.save(full_arrangement_path)

        sections_text = "\n".join(
            "- " + s["name"] + ": bars " + str(s["start_bar"] + 1) + "-" + str(s["end_bar"])
            for s in sections
        )

        notes_path = td / "production_notes.txt"
        notes_path.write_text(
            "Dream Trance MIDI Generator V3.6\n\n"
            + "BPM: " + str(bpm) + "\n"
            + "Key: " + key_root + " minor\n"
            + "Progression: " + progression + "\n"
            + "Arrangement: " + arrangement + "\n"
            + "Energy: " + energy + "\n"
            + "Vocalist: " + vocalist + "\n\n"
            + "V3.6 Motif Evolution Engine:\n"
            + "- New track identity blueprint locks the track around one dominant hook concept\n"
            + "- One hero note is enforced inside every 4-bar drop cycle\n"
            + "- A deliberate signature leap is forced into the hook so phrases are more memorable\n"
            + "- Breakdown writing now recalls the hook as memory rather than replaying it literally\n"
            + "- Drop 2 now opens higher and resolves more decisively than Drop 1\n"
            + "- Rolling bass now makes more space under lead payoff moments\n"
            + "- Vocal melody stem now behaves more like a simplified topline candidate\n"
            + "- Chord voicings are more section-aware, with stronger build tension and brighter Drop 2 voicing\n\n"
            + "V3.4 Foundations Retained:\n"
            + "- Unique export ZIP file per request\n"
            + "- Server-side form validation for bpm and select fields\n"
            + "- Base-directory path handling for static and export folders\n"
            + "- Pre-drop impact gap retained before Drop 2\n\n"
            + "Sections:\n" + sections_text + "\n"
        )

        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(full_arrangement_path, full_arrangement_path.name)
            zf.write(notes_path, notes_path.name)
            for stem in STEMS:
                p = td / (stem + ".mid")
                zf.write(p, "stems/" + p.name)


@app.post("/generate")
def generate(
    bpm: Annotated[int, Form(..., ge=132, le=142)],
    key_root: Annotated[KeyRootType, Form(...)],
    progression: Annotated[ProgressionType, Form(...)],
    arrangement: Annotated[ArrangementType, Form(...)],
    energy: Annotated[EnergyType, Form(...)],
    vocalist: Annotated[VocalistType, Form(...)],
):
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    request_id = uuid4().hex
    out_zip = EXPORTS_DIR / ("dream_trance_midi_pack_v3_6_" + request_id + ".zip")

    generate_pack(bpm, key_root, progression, arrangement, energy, vocalist, out_zip)

    return FileResponse(
        path=out_zip,
        filename="dream_trance_midi_pack_v3_6.zip",
        media_type="application/zip",
        background=BackgroundTask(lambda: out_zip.unlink(missing_ok=True))
    )

print("LOADED FILE:", __file__)
for route in app.routes:
    methods = getattr(route, "methods", None)
    print("ROUTE:", route.path, methods)
