# ==========================================
# Dream Trance MIDI Generator V4.0.1
# Modern UI + Full Song Engine
# ==========================================

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, FileResponse
from mido import Message, MidiFile, MidiTrack, MetaMessage, bpm2tempo
from pathlib import Path
from uuid import uuid4
import random
import time

app = FastAPI(title="Dream Trance Generator V4.0.1")

EXPORTS = Path("exports")
EXPORTS.mkdir(exist_ok=True)

TICKS = 480
BAR = TICKS * 4

# ===============================
# 🎼 THEORY
# ===============================

NOTE = {"C":0,"C#":1,"D":2,"D#":3,"E":4,"F":5,"F#":6,"G":7,"G#":8,"A":9,"A#":10,"B":11}
SCALE = [0,2,3,5,7,8,10]

def n(root, degree, octave=4):
    return NOTE[root] + SCALE[(degree-1)%7] + (octave+1)*12

def tick(b): return int(b*TICKS)

def add(ev,t,note,len,vel=90):
    ev.append((t,Message("note_on",note=note,velocity=vel,time=0)))
    ev.append((t+len,Message("note_off",note=note,velocity=0,time=0)))

# ===============================
# 🧠 V4 ENGINE
# ===============================

def blueprint(rng):
    return {
        "chord": rng.choice(["block","rhythmic","syncopated","broken","wide"]),
        "arp": rng.choice(["16","8","triplet","drive","minimal"]),
        "bass": rng.choice(["offbeat","rolling","sync","hybrid"]),
        "drums": rng.choice(["std","drive","minimal","festival"])
    }

# ===============================
# 🎹 GENERATORS
# ===============================

def chords(root):
    return [
        [n(root,1),n(root,3),n(root,5)],
        [n(root,6),n(root,1,3),n(root,3,3)],
        [n(root,3),n(root,5),n(root,7)],
        [n(root,7),n(root,2,5),n(root,4,5)]
    ]

def gen_chords(chords,style,bars):
    ev=[]
    for b in range(bars):
        c=chords[b%4]
        t0=b*BAR

        if style=="block":
            for note_ in c:
                add(ev,t0,note_,BAR)

        elif style=="rhythmic":
            for i in range(4):
                for note_ in c:
                    add(ev,t0+tick(i),note_,tick(0.8))

        elif style=="syncopated":
            for i in [0,1.5,2.75]:
                for note_ in c:
                    add(ev,t0+tick(i),note_,tick(0.6))

        elif style=="broken":
            for i,note_ in enumerate(c):
                add(ev,t0+tick(i),note_,tick(0.8))

        elif style=="wide":
            add(ev,t0,c[0]-12,BAR)
            for note_ in c[1:]:
                add(ev,t0,note_+12,BAR)

    return ev

def gen_arp(chords,style,bars):
    ev=[]
    for b in range(bars):
        c=chords[b%4]
        t0=b*BAR

        if style=="16":
            for i in range(16):
                add(ev,t0+tick(i*0.25),c[i%3]+12,tick(0.2))

        elif style=="8":
            for i in range(8):
                add(ev,t0+tick(i*0.5),c[i%3]+12,tick(0.3))

        elif style=="triplet":
            for i in range(12):
                add(ev,t0+tick(i*(4/12)),c[i%3]+12,tick(0.25))

        elif style=="drive":
            for i in range(16):
                add(ev,t0+tick(i*0.25),c[(i+1)%3]+12,tick(0.2))

        elif style=="minimal":
            add(ev,t0,c[0]+12,BAR)

    return ev

def gen_bass(chords,style,bars):
    ev=[]
    for b in range(bars):
        root=chords[b%4][0]-24
        t0=b*BAR

        if style=="offbeat":
            for i in [0.5,1.5,2.5,3.5]:
                add(ev,t0+tick(i),root,tick(0.4))

        elif style=="rolling":
            for i in range(8):
                add(ev,t0+tick(i*0.5),root,tick(0.3))

        elif style=="sync":
            for i in [0.75,1.75,2.25,3.25]:
                add(ev,t0+tick(i),root,tick(0.3))

        elif style=="hybrid":
            if b%2==0:
                for i in [0.5,1.5,2.5,3.5]:
                    add(ev,t0+tick(i),root,tick(0.4))
            else:
                for i in range(8):
                    add(ev,t0+tick(i*0.5),root,tick(0.25))

    return ev

def gen_drums(style,bars):
    ev=[]
    for b in range(bars):
        t0=b*BAR

        for beat in [0,1,2,3]:
            add(ev,t0+tick(beat),36,tick(0.1),100)

        for beat in [1,3]:
            add(ev,t0+tick(beat),38,tick(0.1),110)

        density=8
        if style=="festival": density=16
        if style=="minimal": density=4

        for i in range(density):
            add(ev,t0+tick(i*(4/density)),42,tick(0.1),70)

    return ev

# ===============================
# 🎧 BUILD TRACK
# ===============================

def build_track(bpm,root):
    rng=random.Random(time.time_ns())
    bp=blueprint(rng)
    ch=chords(root)

    bars=64

    tracks={
        "chords": gen_chords(ch,bp["chord"],bars),
        "arp": gen_arp(ch,bp["arp"],bars),
        "bass": gen_bass(ch,bp["bass"],bars),
        "drums": gen_drums(bp["drums"],bars)
    }

    return tracks

# ===============================
# 🎼 MIDI EXPORT
# ===============================

def to_midi(tracks,bpm):
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
# 🌐 MODERN UI
# ===============================

@app.get("/",response_class=HTMLResponse)
def home():
    return """
    <html>
    <head>
    <title>Trance Generator V4</title>
    <style>
    body{background:#0b0f1a;color:white;font-family:Arial;text-align:center;padding:40px}
    .card{background:#111827;padding:30px;border-radius:15px;max-width:400px;margin:auto}
    input,button{padding:10px;margin:10px;border-radius:8px;border:none}
    button{background:#6366f1;color:white;font-weight:bold;cursor:pointer}
    </style>
    </head>
    <body>
    <div class="card">
    <h2>🎧 Trance Generator V4</h2>
    <form method="post" action="/generate">
    BPM:<br><input name="bpm" value="138"><br>
    Key:<br><input name="key" value="F"><br>
    <button type="submit">Generate Track</button>
    </form>
    </div>
    </body>
    </html>
    """

@app.post("/generate")
def generate(bpm:int=Form(...),key:str=Form(...)):
    tracks=build_track(bpm,key)
    midi=to_midi(tracks,bpm)

    file=EXPORTS/f"{uuid4()}.mid"
    midi.save(file)

    return FileResponse(file,filename="trance.mid")
