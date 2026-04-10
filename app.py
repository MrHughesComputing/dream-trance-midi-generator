# ==========================================
# Dream Trance MIDI Generator V4.0
# Full Song Composition Engine
# ==========================================

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, FileResponse
from mido import Message, MidiFile, MidiTrack, MetaMessage, bpm2tempo
from pathlib import Path
from uuid import uuid4
import random
import zipfile
import time

app = FastAPI(title="Dream Trance MIDI Generator V4.0")

TICKS = 480
BAR_TICKS = TICKS * 4

EXPORTS_DIR = Path("exports")
EXPORTS_DIR.mkdir(exist_ok=True)

# ===============================
# 🎼 THEORY
# ===============================

NOTE = {"C":0,"C#":1,"D":2,"D#":3,"E":4,"F":5,"F#":6,"G":7,"G#":8,"A":9,"A#":10,"B":11}
SCALE = [0,2,3,5,7,8,10]

PROGRESSIONS = {
    "uplifting":[1,6,3,7],
    "classic":[1,4,6,7]
}

ARRANGEMENTS = {
    "standard":[
        ("Intro",16),
        ("Build",16),
        ("Drop",32),
        ("Breakdown",16),
        ("Drop2",32)
    ]
}

# ===============================
# 🔧 HELPERS
# ===============================

def tick(b): return int(b*TICKS)

def note(root, degree, octave=4):
    return NOTE[root] + SCALE[(degree-1)%7] + (octave+1)*12

def add(events, t, n, l, v=90):
    events.append((t, Message("note_on",note=n,velocity=v,time=0)))
    events.append((t+l, Message("note_off",note=n,velocity=0,time=0)))

# ===============================
# 🧠 V4.0 ARRANGEMENT IDENTITY
# ===============================

def arrangement_identity(rng):
    return {
        "chord_style": rng.choice(["block","rhythmic","syncopated","broken","wide"]),
        "arp_style": rng.choice(["16th","8th","triplet","drive","minimal"]),
        "bass_style": rng.choice(["offbeat","rolling","syncopated","hybrid"]),
        "drum_style": rng.choice(["standard","driving","minimal","festival"]),
        "breakdown_style": rng.choice(["pad","piano","arp","vocal"]),
        "energy": rng.choice(["rise","early","late","double"])
    }

# ===============================
# 🎹 CHORDS V4.0
# ===============================

def chords(root, prog):
    out=[]
    for d in PROGRESSIONS[prog]:
        tri=[note(root,d,4),note(root,d+2,4),note(root,d+4,4)]
        out.append(tri)
    return out

def chord_events(chords, section, style):
    events=[]
    for b in range(section["bars"]):
        chord=chords[b%len(chords)]
        start=bar_tick(section["start"]+b)

        if style=="block":
            add(events,start,chord[0],BAR_TICKS)
            add(events,start,chord[1],BAR_TICKS)
            add(events,start,chord[2],BAR_TICKS)

        elif style=="rhythmic":
            for i in range(4):
                for n in chord:
                    add(events,start+tick(i),n,tick(0.8))

        elif style=="syncopated":
            for t in [0,1.5,2.75]:
                for n in chord:
                    add(events,start+tick(t),n,tick(0.6))

        elif style=="broken":
            for i,n in enumerate(chord):
                add(events,start+tick(i),n,tick(0.9))

        elif style=="wide":
            add(events,start,chord[0]-12,BAR_TICKS)
            for n in chord[1:]:
                add(events,start,n+12,BAR_TICKS)

    return events

# ===============================
# 🔊 ARP
# ===============================

def arp_events(chords, section, style):
    events=[]
    for b in range(section["bars"]):
        chord=chords[b%len(chords)]
        start=bar_tick(section["start"]+b)

        if style=="16th":
            for i in range(16):
                add(events,start+tick(i*0.25),chord[i%3]+12,tick(0.2))

        elif style=="8th":
            for i in range(8):
                add(events,start+tick(i*0.5),chord[i%3]+12,tick(0.3))

        elif style=="triplet":
            for i in range(12):
                add(events,start+tick(i*(4/12)),chord[i%3]+12,tick(0.25))

        elif style=="drive":
            for i in range(16):
                add(events,start+tick(i*0.25),chord[(i+1)%3]+12,tick(0.2))

        elif style=="minimal":
            add(events,start,chord[0]+12,BAR_TICKS)

    return events

# ===============================
# 🔊 BASS
# ===============================

def bass_events(chords, section, style):
    events=[]
    for b in range(section["bars"]):
        root=chords[b%len(chords)][0]-24
        start=bar_tick(section["start"]+b)

        if style=="offbeat":
            for t in [0.5,1.5,2.5,3.5]:
                add(events,start+tick(t),root,tick(0.4))

        elif style=="rolling":
            for i in range(8):
                add(events,start+tick(i*0.5),root,tick(0.3))

        elif style=="syncopated":
            for t in [0.75,1.75,2.25,3.25]:
                add(events,start+tick(t),root,tick(0.3))

        elif style=="hybrid":
            if b%2==0:
                for t in [0.5,1.5,2.5,3.5]:
                    add(events,start+tick(t),root,tick(0.4))
            else:
                for i in range(8):
                    add(events,start+tick(i*0.5),root,tick(0.25))

    return events

# ===============================
# 🥁 DRUMS
# ===============================

def drum_events(section, style):
    events=[]
    for b in range(section["bars"]):
        start=bar_tick(section["start"]+b)

        for beat in [0,1,2,3]:
            add(events,start+tick(beat),36,tick(0.1),100)

        for beat in [1,3]:
            add(events,start+tick(beat),38,tick(0.1),110)

        density=8
        if style=="festival": density=16
        if style=="minimal": density=4

        for i in range(density):
            add(events,start+tick(i*(4/density)),42,tick(0.1),70)

    return events

# ===============================
# 🧱 ARRANGEMENT
# ===============================

def build_sections(arr):
    out=[]
    cur=0
    for name,bars in ARRANGEMENTS[arr]:
        out.append({"name":name,"bars":bars,"start":cur})
        cur+=bars
    return out

def bar_tick(bar): return bar*BAR_TICKS

# ===============================
# 🎼 MAIN GENERATOR
# ===============================

def generate_track(bpm, root, prog):
    rng=random.Random(time.time_ns())

    blueprint=arrangement_identity(rng)
    chords_list=chords(root,prog)
    sections=build_sections("standard")

    tracks={k:[] for k in ["chords","arp","bass","drums"]}

    for sec in sections:
        tracks["chords"]+=chord_events(chords_list,sec,blueprint["chord_style"])
        tracks["arp"]+=arp_events(chords_list,sec,blueprint["arp_style"])
        tracks["bass"]+=bass_events(chords_list,sec,blueprint["bass_style"])
        tracks["drums"]+=drum_events(sec,blueprint["drum_style"])

    return tracks

# ===============================
# 🎧 MIDI EXPORT
# ===============================

def build_midi(tracks,bpm):
    midi=MidiFile()
    tempo=bpm2tempo(bpm)

    for name,events in tracks.items():
        t=MidiTrack()
        t.append(MetaMessage("set_tempo",tempo=tempo,time=0))
        events.sort(key=lambda x:x[0])

        last=0
        for time_abs,msg in events:
            msg.time=time_abs-last
            t.append(msg)
            last=time_abs

        midi.tracks.append(t)

    return midi

# ===============================
# 🌐 API
# ===============================

@app.get("/",response_class=HTMLResponse)
def home():
    return """
    <h1>V4.0 Trance Generator</h1>
    <form method="post" action="/generate">
    BPM: <input name="bpm" value="138"><br>
    Key: <input name="key" value="F"><br>
    <button type="submit">Generate</button>
    </form>
    """

@app.post("/generate")
def generate(bpm:int=Form(...), key:str=Form(...)):
    tracks=generate_track(bpm,key,"uplifting")

    midi=build_midi(tracks,bpm)

    file=EXPORTS_DIR/f"{uuid4()}.mid"
    midi.save(file)

    return FileResponse(file,filename="track.mid")
