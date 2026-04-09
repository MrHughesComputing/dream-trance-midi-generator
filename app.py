from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from mido import Message, MidiFile, MidiTrack, MetaMessage, bpm2tempo
from pathlib import Path
import tempfile, zipfile

app = FastAPI(title="Dream Trance MIDI Generator V1.1")
app.mount("/static", StaticFiles(directory="static"), name="static")

TICKS = 480
STEMS = [
    "kick", "clap_snare", "hats", "offbeat_bass", "rolling_bass", "arp", "pluck", "pad",
    "supersaw_chords", "lead", "countermelody", "strings", "piano", "vocal_melody"
]
NOTE = {"C":0,"C#":1,"Db":1,"D":2,"D#":3,"Eb":3,"E":4,"F":5,"F#":6,"Gb":6,"G":7,"G#":8,"Ab":8,"A":9,"A#":10,"Bb":10,"B":11}
SCALES = {"minor":[0,2,3,5,7,8,10]}
PROGRESSIONS = {
    "Emotional Lift (i-VI-III-VII)": [1,6,3,7],
    "Classic Uplift (i-iv-VI-VII)": [1,4,6,7],
    "Festival Drive (VI-III-VII-i)": [6,3,7,1],
    "Hopeful Pull (i-v-VI-iv)": [1,5,6,4],
}
ARRANGEMENTS = {
    "Club/Extended": [("Intro",16),("Verse",16),("Build",16),("Drop 1",32),("Breakdown",24),("Build 2",16),("Drop 2",32),("Outro",16)],
    "Radio/Compact": [("Intro",8),("Verse",16),("Build",8),("Drop 1",24),("Breakdown",16),("Build 2",8),("Drop 2",24),("Outro",8)],
    "Breakdown Focused": [("Intro",12),("Verse",16),("Build",12),("Drop 1",24),("Breakdown",32),("Build 2",16),("Drop 2",24),("Outro",12)],
}
ENERGY_LEVELS = {"Low":0.8,"Medium":1.0,"High":1.2}
VOCAL_RANGES = {
    "Female Soprano": (72,84),
    "Female Airy": (69,81),
    "Male Tenor": (60,72),
}

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dream Trance MIDI Generator V1.1</title>
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
        <div class="eyebrow">Dream Trance MIDI Generator • V1.1</div>
        <h1>Build uplifting trance MIDI packs with a cleaner, faster workflow.</h1>
        <p class="sub">
          Section-aware trance generation for vocals, hooks, builds, drops, and aligned stem export.
          Choose your key, progression, arrangement, energy, and vocalist range, then generate a full MIDI pack for Ableton or Logic.
        </p>
        <div class="pill">Exports aligned full-length stems + combined arrangement MIDI</div>
      </div>

      <div class="hero-side">
        <div class="stat">
          <div class="stat-label">Primary use</div>
          <div class="stat-value">Uplifting vocal and melodic trance sketch generation</div>
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
                <select id="key_root" name="key_root">{key_opts}</select>
              </div>

              <div class="field full">
                <label for="progression">Progression</label>
                <select id="progression" name="progression">{prog_opts}</select>
              </div>

              <div class="field">
                <label for="arrangement">Arrangement</label>
                <select id="arrangement" name="arrangement">{arr_opts}</select>
              </div>

              <div class="field">
                <label for="energy">Energy</label>
                <select id="energy" name="energy">{energy_opts}</select>
              </div>

              <div class="field full">
                <label for="vocalist">Vocalist</label>
                <select id="vocalist" name="vocalist">{vocal_opts}</select>
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
          <h3>What changed in V1.1</h3>
          <ul>
            <li>Real section starts, not everything from bar 1.</li>
            <li>Lead motif system with repetition and variation.</li>
            <li>Singable topline phrases with rests and cadences.</li>
            <li>Build snare rolls and 8/16-bar fill logic.</li>
            <li>Drop energy staging by section.</li>
            <li>Aligned full-length stem export for Logic and Ableton.</li>
          </ul>
        </div>

        <div class="tip">
          <h3>Included stems</h3>
          <ul class="stem-list">
            {stem_items}
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
    return HTML.format(
        key_opts="".join(f"<option>{k}</option>" for k in ["F","F#","G","G#","A","A#","C","D"]),
        prog_opts="".join(f"<option>{p}</option>" for p in PROGRESSIONS),
        arr_opts="".join(f"<option>{a}</option>" for a in ARRANGEMENTS),
        energy_opts="".join(f"<option>{e}</option>" for e in ENERGY_LEVELS),
        vocal_opts="".join(f"<option>{v}</option>" for v in VOCAL_RANGES),
        stem_items="".join(f"<li>{s}</li>" for s in STEMS),
    )


@app.get("/", response_class=HTMLResponse)
def home():
    return html_page()


def tick(beats: float) -> int:
    return int(round(beats * TICKS))


def bar_tick(bar_index: int) -> int:
    return tick(bar_index * 4)


def note_name_to_midi(root: str, degree: int, octave: int = 4, mode="minor"):
    scale = SCALES[mode]
    root_pc = NOTE[root]
    pc = (root_pc + scale[(degree - 1) % 7]) % 12
    return pc + 12 * (octave + 1)


def progression_chords(root: str, progression_name: str):
    degs = PROGRESSIONS[progression_name]
    triad_map = {1:(1,3,5),2:(2,4,6),3:(3,5,7),4:(4,6,1),5:(5,7,2),6:(6,1,3),7:(7,2,4)}
    chords = []
    for d in degs:
        chord = [note_name_to_midi(root, dd, 4 if dd not in (6,7) else 3) for dd in triad_map[d]]
        chords.append((d, sorted(chord)))
    return chords


def arrange_sections(arrangement_name: str):
    sections = []
    bar = 0
    for name, length in ARRANGEMENTS[arrangement_name]:
        sections.append({"name": name, "start_bar": bar, "bars": length, "end_bar": bar + length})
        bar += length
    return sections


def section_type(name: str):
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
    typ = section_type(section_name)
    base = {
        "intro": {"dens": 0.35, "vel": 72},
        "verse": {"dens": 0.55, "vel": 82},
        "build": {"dens": 0.8, "vel": 96},
        "drop": {"dens": 1.0, "vel": 110},
        "breakdown": {"dens": 0.45, "vel": 78},
        "outro": {"dens": 0.35, "vel": 70},
        "other": {"dens": 0.5, "vel": 80},
    }[typ]
    return {"density": min(1.0, base["dens"] * energy_factor), "vel": min(124, int(base["vel"] * energy_factor))}


def add_events(event_list, start_tick, notes, length_tick, velocity=90, channel=0):
    if isinstance(notes, int):
        notes = [notes]
    for n in notes:
        event_list.append((start_tick, Message("note_on", note=int(n), velocity=int(max(1, min(127, velocity))), channel=channel, time=0)))
        event_list.append((start_tick + length_tick, Message("note_off", note=int(n), velocity=0, channel=channel, time=0)))


def finalise_track(name, tempo, events, markers=None):
    track = MidiTrack()
    track.append(MetaMessage("track_name", name=name, time=0))
    track.append(MetaMessage("set_tempo", tempo=tempo, time=0))
    if markers:
        for t, txt in markers:
            events.append((t, MetaMessage("marker", text=txt, time=0)))
    events.sort(key=lambda x: (x[0], 0 if getattr(x[1], "type", "") == "note_off" else 1))
    last = 0
    for t, msg in events:
        delta = max(0, int(t - last))
        msg.time = delta
        track.append(msg)
        last = t
    track.append(MetaMessage("end_of_track", time=1))
    return track


def choose_chord(chords, bar_number):
    return chords[bar_number % len(chords)]


def build_motif(root: str):
    tonic = note_name_to_midi(root, 1, 5)
    third = note_name_to_midi(root, 3, 5)
    fifth = note_name_to_midi(root, 5, 5)
    seventh = note_name_to_midi(root, 7, 5)
    return [tonic, third, fifth, seventh, fifth, third]


def generate_pack(bpm: int, key_root: str, progression: str, arrangement: str, energy: str, vocalist: str, out_zip: Path):
    tempo = bpm2tempo(bpm)
    sections = arrange_sections(arrangement)
    chords = progression_chords(key_root, progression)
    energy_factor = ENERGY_LEVELS[energy]
    vocal_min, vocal_max = VOCAL_RANGES[vocalist]
    motif = build_motif(key_root)

    tracks = {stem: [] for stem in STEMS}
    markers = []

    for sec in sections:
        markers.append((bar_tick(sec["start_bar"]), f"{sec['name']} ({sec['bars']} bars)"))
        prof = energy_profile(sec["name"], energy_factor)
        stype = section_type(sec["name"])

        for local_bar in range(sec["bars"]):
            global_bar = sec["start_bar"] + local_bar
            _, chord = choose_chord(chords, global_bar)
            bar_start = bar_tick(global_bar)
            bars_left = sec["bars"] - local_bar

            if stype in ("intro", "verse", "breakdown", "build", "drop", "outro"):
                if stype in ("intro", "breakdown"):
                    add_events(tracks["pad"], bar_start, [n - 12 for n in chord], tick(4), velocity=60 + int(prof["vel"] * 0.15))
                    if local_bar % 2 == 0:
                        add_events(tracks["strings"], bar_start, [chord[0], chord[1], chord[2] + 12], tick(8), velocity=52 + int(prof["vel"] * 0.12))
                elif stype == "drop":
                    add_events(tracks["supersaw_chords"], bar_start, [chord[0], chord[1], chord[2], chord[0] + 12], tick(4), velocity=prof["vel"])
                    add_events(tracks["pad"], bar_start, [n - 12 for n in chord], tick(4), velocity=65)
                    if local_bar % 2 == 0:
                        add_events(tracks["strings"], bar_start, [chord[0], chord[1], chord[2] + 12], tick(4), velocity=72)
                elif stype == "build":
                    add_events(tracks["pluck"], bar_start, chord, tick(1), velocity=76)
                    add_events(tracks["pad"], bar_start, [n - 12 for n in chord], tick(4), velocity=58)
                elif stype == "verse":
                    add_events(tracks["piano"], bar_start, chord, tick(2), velocity=68)
                    add_events(tracks["pad"], bar_start, [n - 12 for n in chord], tick(4), velocity=55)
                elif stype == "outro" and local_bar < sec["bars"] // 2:
                    add_events(tracks["pad"], bar_start, [n - 12 for n in chord], tick(4), velocity=52)
                    add_events(tracks["piano"], bar_start, chord, tick(2), velocity=60)

            if stype in ("verse", "build", "drop", "outro"):
                kick_pattern = [0, 1, 2, 3] if stype in ("drop", "outro") or local_bar > 1 else [0, 2]
                for beat_pos in kick_pattern:
                    add_events(tracks["kick"], bar_start + tick(beat_pos), 36, tick(0.45), velocity=110 if stype == "drop" else 95)

            if stype in ("verse", "build", "drop"):
                for beat_pos in (1, 3):
                    add_events(tracks["clap_snare"], bar_start + tick(beat_pos), 39, tick(0.25), velocity=98 if stype == "drop" else 88)

            if stype in ("build", "drop"):
                for off in [0.5, 1.5, 2.5, 3.5]:
                    add_events(tracks["hats"], bar_start + tick(off), 46, tick(0.2), velocity=70 if stype == "drop" else 58)
                if stype == "drop":
                    for off in [0.25, 0.75, 1.25, 1.75, 2.25, 2.75, 3.25, 3.75]:
                        add_events(tracks["hats"], bar_start + tick(off), 42, tick(0.12), velocity=52)

            if stype in ("build", "drop") and bars_left == 1:
                for pos in [0, 0.5, 1, 1.5, 2, 2.25, 2.5, 2.75, 3, 3.125, 3.25, 3.375, 3.5, 3.625, 3.75, 3.875]:
                    vel = 70 + int(pos * 12)
                    add_events(tracks["clap_snare"], bar_start + tick(pos), 38, tick(0.09), velocity=min(125, vel))
            elif stype == "verse" and bars_left == 1:
                for pos in [2, 2.5, 3, 3.5]:
                    add_events(tracks["clap_snare"], bar_start + tick(pos), 37, tick(0.09), velocity=72)

            root_note = chord[0] - 24
            fifth_note = chord[2] - 24
            if stype in ("verse", "drop", "outro"):
                if stype in ("verse", "outro"):
                    for off in [0.5, 1.5, 2.5, 3.5]:
                        add_events(tracks["offbeat_bass"], bar_start + tick(off), root_note, tick(0.42), velocity=92)
                if stype == "drop":
                    seq = [root_note, root_note, fifth_note, root_note, root_note, root_note, fifth_note, root_note]
                    for i, n in enumerate(seq):
                        add_events(tracks["rolling_bass"], bar_start + tick(i * 0.5), n, tick(0.22), velocity=96)

            if stype in ("build", "drop", "breakdown"):
                arp_notes = [chord[0] + 12, chord[1] + 12, chord[2] + 12, chord[1] + 12]
                step = 0.5 if stype != "drop" else 0.25
                reps = int(4 / step)
                for i in range(reps):
                    n = arp_notes[i % len(arp_notes)] + (12 if (stype == "drop" and i % 8 == 7) else 0)
                    add_events(tracks["arp"], bar_start + tick(i * step), n, tick(step * 0.7), velocity=65 if stype != "drop" else 78)

            if stype == "drop":
                for i, start in enumerate([0, 1, 2, 3]):
                    base = motif[(local_bar * 2 + i) % len(motif)]
                    phrase = [base, base + 2 if i % 2 == 0 else base, motif[(i + 2) % len(motif)], base]
                    for j, n in enumerate(phrase):
                        add_events(tracks["lead"], bar_start + tick(start + j * 0.25), n, tick(0.22), velocity=100)
                if local_bar % 4 == 3:
                    add_events(tracks["countermelody"], bar_start + tick(2), [motif[1] - 12, motif[2] - 12, motif[4] - 12], tick(1.5), velocity=74)

            elif stype == "breakdown" and local_bar % 2 == 0:
                phrase = [motif[0] - 12, motif[1] - 12, motif[2] - 12, motif[1] - 12]
                for j, n in enumerate(phrase):
                    add_events(tracks["lead"], bar_start + tick(j), n, tick(0.8), velocity=68)

            if stype in ("verse", "breakdown", "build"):
                high_chord = [max(vocal_min, min(vocal_max, x + 12)) for x in chord]
                if local_bar % 4 in (0, 1):
                    phrase = [high_chord[0], high_chord[1], high_chord[0], high_chord[2]]
                    starts = [0, 1, 2, 3]
                    lens = [0.75, 0.75, 0.75, 1.2]
                elif local_bar % 4 == 2:
                    phrase = [high_chord[1], high_chord[0], high_chord[1]]
                    starts = [0.5, 1.5, 2.5]
                    lens = [0.7, 0.7, 1.0]
                else:
                    phrase = [high_chord[2], high_chord[1], high_chord[0]]
                    starts = [0, 1.25, 2.5]
                    lens = [1.0, 0.9, 1.3]

                for n, st, ln in zip(phrase, starts, lens):
                    add_events(tracks["vocal_melody"], bar_start + tick(st), n, tick(ln), velocity=82 if stype != "build" else 90)

    out_zip.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        combined = MidiFile(type=1, ticks_per_beat=TICKS)
        combined.tracks.append(finalise_track("Markers", tempo, [], markers=markers))

        for stem in STEMS:
            mf = MidiFile(type=1, ticks_per_beat=TICKS)
            track = finalise_track(stem, tempo, tracks[stem][:], markers=markers if stem == "kick" else None)
            mf.tracks.append(track)
            stem_path = td / f"{stem}.mid"
            mf.save(stem_path)
            combined.tracks.append(finalise_track(stem, tempo, tracks[stem][:]))

        combined_path = td / "full_arrangement.mid"
        combined.save(combined_path)

        notes = td / "production_notes.txt"
        sections_text = "\\n".join(f"- {s['name']}: bars {s['start_bar'] + 1}-{s['end_bar']}" for s in sections)
        notes.write_text(
            f"Dream Trance MIDI Generator V1.1\\n\\n"
            f"BPM: {bpm}\\n"
            f"Key: {key_root} minor\\n"
            f"Progression: {progression}\\n"
            f"Arrangement: {arrangement}\\n"
            f"Energy: {energy}\\n"
            f"Vocalist: {vocalist}\\n\\n"
            f"Sections:\\n{sections_text}\\n\\n"
            f"V1.1 changes:\\n"
            f"- Section-aware entries\\n"
            f"- Motif-led drops\\n"
            f"- Singable topline phrases\\n"
            f"- Build snare ramps\\n"
            f"- Stronger drop density\\n"
        )

        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(combined_path, combined_path.name)
            zf.write(notes, notes.name)
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
    out_zip = out_dir / "dream_trance_midi_pack_v1_1.zip"
    generate_pack(bpm, key_root, progression, arrangement, energy, vocalist, out_zip)
    return FileResponse(out_zip, filename=out_zip.name, media_type="application/zip")
