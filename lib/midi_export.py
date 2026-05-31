from pathlib import Path
import json
import shutil
import tempfile
import zipfile

from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo

from .edm_generator import TICKS
from .edm_generator import option_preview_dict


def add_note(events, start: int, note: int, duration: int, velocity: int, channel: int = 0):
    events.append((start, Message("note_on", note=int(note), velocity=int(velocity), channel=channel, time=0)))
    events.append((start + max(1, int(duration)), Message("note_off", note=int(note), velocity=0, channel=channel, time=0)))


def add_notes(events, start: int, notes, duration: int, velocity: int, channel: int = 0):
    for note in notes:
        add_note(events, start, note, duration, velocity, channel=channel)


def finalise_track(name: str, tempo: int, events, markers=None):
    track = MidiTrack()
    track.append(MetaMessage("track_name", name=name, time=0))
    track.append(MetaMessage("set_tempo", tempo=tempo, time=0))
    working = list(events)
    if markers:
        for abs_time, text in markers:
            working.append((abs_time, MetaMessage("marker", text=text, time=0)))
    working.sort(key=lambda item: (item[0], 0 if getattr(item[1], "type", "") == "note_off" else 1))
    last = 0
    for abs_time, message in working:
        message.time = max(0, int(abs_time - last))
        track.append(message)
        last = abs_time
    track.append(MetaMessage("end_of_track", time=1))
    return track


def option_events(option):
    chords = []
    melody = []
    bass = []
    arp = []
    markers = []
    for section in option.sections:
        markers.append((section.start_bar * TICKS * 4, section.name))
        for event in section.chord_events:
            add_notes(chords, event["start"], event["notes"], event["duration"], event["velocity"], channel=1)
        for event in section.melody_events:
            add_note(melody, event["start"], event["note"], event["duration"], event["velocity"], channel=0)
        for event in section.bass_events:
            add_note(bass, event["start"], event["note"], event["duration"], event["velocity"], channel=2)
        for event in section.arp_events:
            add_note(arp, event["start"], event["note"], event["duration"], event["velocity"], channel=3)
    return chords, melody, bass, arp, markers


def build_option_midi(option):
    tempo = bpm2tempo(option.bpm)
    chords, melody, bass, arp, markers = option_events(option)
    midi = MidiFile(type=1, ticks_per_beat=TICKS)
    midi.tracks.append(finalise_track("Markers", tempo, [], markers=markers))
    if melody:
        midi.tracks.append(finalise_track("Melody", tempo, melody))
    if chords:
        midi.tracks.append(finalise_track("Chords", tempo, chords))
    if bass:
        midi.tracks.append(finalise_track("Bass Root Guide", tempo, bass))
    if arp:
        midi.tracks.append(finalise_track("Arpeggio Pluck", tempo, arp))
    return midi


def build_track_midi(option, track_name: str):
    tempo = bpm2tempo(option.bpm)
    chords, melody, bass, arp, markers = option_events(option)
    event_map = {
        "melody": melody,
        "chords": chords,
        "bass": bass,
        "arp": arp,
    }
    midi = MidiFile(type=1, ticks_per_beat=TICKS)
    midi.tracks.append(finalise_track(track_name.title(), tempo, event_map.get(track_name, []), markers=markers))
    return midi


def build_section_midi(option, section):
    tempo = bpm2tempo(option.bpm)
    midi = MidiFile(type=1, ticks_per_beat=TICKS)
    markers = [(section.start_bar * TICKS * 4, section.name)]
    chords = []
    melody = []
    bass = []
    arp = []
    for event in section.chord_events:
        add_notes(chords, event["start"], event["notes"], event["duration"], event["velocity"], channel=1)
    for event in section.melody_events:
        add_note(melody, event["start"], event["note"], event["duration"], event["velocity"], channel=0)
    for event in section.bass_events:
        add_note(bass, event["start"], event["note"], event["duration"], event["velocity"], channel=2)
    for event in section.arp_events:
        add_note(arp, event["start"], event["note"], event["duration"], event["velocity"], channel=3)
    midi.tracks.append(finalise_track("Markers", tempo, [], markers=markers))
    if melody:
        midi.tracks.append(finalise_track("Melody", tempo, melody))
    if chords:
        midi.tracks.append(finalise_track("Chords", tempo, chords))
    if bass:
        midi.tracks.append(finalise_track("Bass Root Guide", tempo, bass))
    if arp:
        midi.tracks.append(finalise_track("Arpeggio Pluck", tempo, arp))
    return midi


def safe_name(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_")


def idea_pack_work_dir(exports_dir: Path):
    try:
        run_dir = Path(tempfile.mkdtemp(prefix="edm_idea_pack_"))
        build_dir = run_dir / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        return run_dir, build_dir
    except OSError:
        exports_dir.mkdir(parents=True, exist_ok=True)
        run_dir = exports_dir / f"_edm_idea_pack_{safe_name(str(id(exports_dir)))}"
        if run_dir.exists():
            shutil.rmtree(run_dir, ignore_errors=True)
        build_dir = run_dir / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        return run_dir, build_dir


def export_idea_pack(result, exports_dir: Path, app_version: str):
    run_dir, temp_dir = idea_pack_work_dir(exports_dir)
    zip_path = run_dir / f"edm_trance_idea_pack_{safe_name(result.key)}_{safe_name(result.genre)}.zip"
    try:
        manifest = {
            "app_version": app_version,
            "bpm": result.bpm,
            "key": result.key,
            "scale": result.scale,
            "genre": result.genre,
            "generation_type": result.generation_type,
            "options": [option_preview_dict(option) for option in result.options],
        }
        (temp_dir / "preview_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        notes = [
            f"EDM / Trance MIDI Idea Generator {app_version}",
            f"Key: {result.key}",
            f"Scale: {result.scale}",
            f"BPM: {result.bpm}",
            f"Genre: {result.genre}",
            "",
        ]
        for option in result.options:
            option_slug = safe_name(option.id)
            option_dir = temp_dir / option_slug
            option_dir.mkdir(parents=True, exist_ok=True)
            build_option_midi(option).save(option_dir / f"{option_slug}_full_arrangement.mid")
            build_track_midi(option, "melody").save(option_dir / f"{option_slug}_melody_only.mid")
            build_track_midi(option, "chords").save(option_dir / f"{option_slug}_chords_only.mid")
            build_track_midi(option, "bass").save(option_dir / f"{option_slug}_bass_root_guide.mid")
            build_track_midi(option, "arp").save(option_dir / f"{option_slug}_arpeggio_pluck.mid")
            for section in option.sections:
                section_slug = safe_name(section.name)
                build_section_midi(option, section).save(option_dir / f"{option_slug}_{section_slug}.mid")
            notes.append(option.name)
            notes.append(option.purpose)
            for section in option.sections:
                notes.append(f"- {section.name} bars {section.start_bar + 1}-{section.start_bar + section.bars}: {' - '.join(section.progression_symbols)}")
            notes.append("")
        (temp_dir / "producer_notes.txt").write_text("\n".join(notes), encoding="utf-8")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in temp_dir.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(temp_dir))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    return zip_path
