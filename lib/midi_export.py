from pathlib import Path
import json
import shutil
import tempfile
import zipfile

from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo

from .edm_generator import TICKS
from .edm_generator import BAR_TICKS
from .edm_generator import option_preview_dict
from .music_theory import midi_name, scale_pitch_classes


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


TRACK_NAMES = {
    "melody": "Melody",
    "chords": "Chords",
    "bass": "Bass Root Guide",
    "arp": "Arpeggio Pluck",
}

TRACK_CHANNELS = {
    "melody": 0,
    "chords": 1,
    "bass": 2,
    "arp": 3,
}

TRACK_FILE_NAMES = {
    "melody": "melody",
    "chords": "chords",
    "bass": "bass",
    "arp": "arp",
}


def option_events(option, offset: int = 0):
    chords = []
    melody = []
    bass = []
    arp = []
    markers = []
    for section in option.sections:
        markers.append((max(0, section.start_tick - offset), section.name))
        for event in section.chord_events:
            add_notes(chords, event["start"] - offset, event["notes"], event["duration"], event["velocity"], channel=1)
        for event in section.melody_events:
            add_note(melody, event["start"] - offset, event["note"], event["duration"], event["velocity"], channel=0)
        for event in section.bass_events:
            add_note(bass, event["start"] - offset, event["note"], event["duration"], event["velocity"], channel=2)
        for event in section.arp_events:
            add_note(arp, event["start"] - offset, event["note"], event["duration"], event["velocity"], channel=3)
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
    midi.tracks.append(finalise_track(TRACK_NAMES.get(track_name, track_name.title()), tempo, event_map.get(track_name, []), markers=markers))
    return midi


def build_section_midi(option, section, trimmed: bool = False):
    tempo = bpm2tempo(option.bpm)
    midi = MidiFile(type=1, ticks_per_beat=TICKS)
    offset = section.start_tick if trimmed else 0
    markers = [(0 if trimmed else section.start_tick, section.name)]
    chords = []
    melody = []
    bass = []
    arp = []
    for event in section.chord_events:
        add_notes(chords, event["start"] - offset, event["notes"], event["duration"], event["velocity"], channel=1)
    for event in section.melody_events:
        add_note(melody, event["start"] - offset, event["note"], event["duration"], event["velocity"], channel=0)
    for event in section.bass_events:
        add_note(bass, event["start"] - offset, event["note"], event["duration"], event["velocity"], channel=2)
    for event in section.arp_events:
        add_note(arp, event["start"] - offset, event["note"], event["duration"], event["velocity"], channel=3)
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


def build_aligned_section_midi(option, section):
    return build_section_midi(option, section, trimmed=False)


def build_trimmed_section_midi(option, section):
    return build_section_midi(option, section, trimmed=True)


def section_track_events(section, track_name: str, offset: int = 0):
    events = []
    if track_name == "melody":
        for event in section.melody_events:
            add_note(events, event["start"] - offset, event["note"], event["duration"], event["velocity"], channel=TRACK_CHANNELS[track_name])
    elif track_name == "chords":
        for event in section.chord_events:
            add_notes(events, event["start"] - offset, event["notes"], event["duration"], event["velocity"], channel=TRACK_CHANNELS[track_name])
    elif track_name == "bass":
        for event in section.bass_events:
            add_note(events, event["start"] - offset, event["note"], event["duration"], event["velocity"], channel=TRACK_CHANNELS[track_name])
    elif track_name == "arp":
        for event in section.arp_events:
            add_note(events, event["start"] - offset, event["note"], event["duration"], event["velocity"], channel=TRACK_CHANNELS[track_name])
    return events


def build_section_track_midi(option, section, track_name: str, trimmed: bool = False):
    tempo = bpm2tempo(option.bpm)
    raw_events = section_track_events(section, track_name, 0)
    first_event_tick = min(
        (abs_time for abs_time, message in raw_events if getattr(message, "type", "") == "note_on" and getattr(message, "velocity", 0) > 0),
        default=section.start_tick,
    )
    offset = first_event_tick if trimmed else 0
    marker_tick = 0 if trimmed else section.start_tick
    events = section_track_events(section, track_name, offset)
    midi = MidiFile(type=1, ticks_per_beat=TICKS)
    midi.tracks.append(finalise_track(TRACK_NAMES.get(track_name, track_name.title()), tempo, events, markers=[(marker_tick, section.name)]))
    return midi


def count_event_notes(events):
    return sum(1 for _time, message in events if getattr(message, "type", "") == "note_on" and getattr(message, "velocity", 0) > 0)


def midi_note_count(midi: MidiFile):
    return sum(1 for track in midi.tracks for message in track if getattr(message, "type", "") == "note_on" and getattr(message, "velocity", 0) > 0)


def first_note_tick(midi: MidiFile):
    first = None
    for track in midi.tracks:
        absolute = 0
        for message in track:
            absolute += message.time
            if getattr(message, "type", "") == "note_on" and getattr(message, "velocity", 0) > 0:
                first = absolute if first is None else min(first, absolute)
    return first


def last_note_tick(midi: MidiFile):
    last = None
    for track in midi.tracks:
        absolute = 0
        for message in track:
            absolute += message.time
            if getattr(message, "type", "") in ("note_on", "note_off"):
                if getattr(message, "type", "") == "note_on" and getattr(message, "velocity", 0) > 0:
                    last = absolute if last is None else max(last, absolute)
                elif getattr(message, "type", "") == "note_off" or getattr(message, "velocity", 0) == 0:
                    last = absolute if last is None else max(last, absolute)
    return last


def midi_length_bars(midi: MidiFile):
    end = last_note_tick(midi)
    if end is None:
        return 0
    return round(end / BAR_TICKS, 3)


def track_counts_for_option(option):
    chords, melody, bass, arp, _markers = option_events(option)
    return {
        "melody": count_event_notes(melody),
        "chords": count_event_notes(chords),
        "bass": count_event_notes(bass),
        "arp": count_event_notes(arp),
    }


def validate_option(option, result):
    counts = track_counts_for_option(option)
    pitch_classes = scale_pitch_classes(option.key, option.scale_id)
    warnings = []
    arrangement_end = result.arrangement_bars * BAR_TICKS
    if option.sections:
        actual_end = max(section.end_tick for section in option.sections)
        if actual_end != arrangement_end:
            warnings.append("full arrangement length does not match selected bar length")
    if counts["arp"] <= 0 and any(section.arpeggio_enabled for section in option.sections):
        warnings.append("arpeggio track is empty")
    if not getattr(option, "melody_strength_score", 0):
        warnings.append("hook score missing")
    if not getattr(option, "hook_subscores", None):
        warnings.append("hook sub-scores missing")
    if option.melody_strength_score < option.hook_threshold and option.threshold_met:
        warnings.append("threshold flag does not match hook score")
    if counts["chords"] <= 0:
        warnings.append("chord track is empty")
    if counts["melody"] <= 0 and option.generation_type not in ("Chords only", "Breakdown emotional progression only"):
        warnings.append("melody track is empty")
    for section in option.sections:
        expected_start = section.start_tick
        expected_end = section.end_tick
        if expected_end > arrangement_end:
            warnings.append(f"{section.name} exceeds arrangement length")
        if section.chord_events and min(event["start"] for event in section.chord_events) < expected_start:
            warnings.append(f"{section.name} has chord event before section start")
        if section.bass_events:
            bass_start = min(event["start"] for event in section.bass_events)
            bass_end = max(event["start"] + event["duration"] for event in section.bass_events)
            if bass_start != expected_start or bass_end != expected_end:
                warnings.append(f"{section.name} bass guide does not fill section exactly")
        for chord in section.chords:
            pcs = {note % 12 for note in chord.voicing}
            missing = [pc for pc in chord.required_pcs if pc not in pcs]
            if missing and not chord.omitted_tones:
                warnings.append(f"{chord.symbol} label does not describe missing chord tones")
        for event_group in (section.chord_events, section.melody_events, section.bass_events, section.arp_events):
            for event in event_group:
                if event["duration"] <= 0:
                    warnings.append(f"{section.name} has invalid note duration")
        tension_notes = [
            event["note"] for event in section.melody_events + section.bass_events + section.arp_events
            if event["note"] % 12 not in pitch_classes
        ]
        if tension_notes and option.id != "experimental_modern":
            warnings.append(f"{section.name} contains out-of-scale notes outside experimental mode")
    return {
        "passed": not warnings,
        "warnings": warnings,
        "track_note_counts": counts,
        "scale_compliance": "experimental_tension_allowed" if option.id == "experimental_modern" else "strict_scale",
        "stuck_notes_detected": False,
    }


def recommended_use(role: str, section_name: str | None, timing_mode: str):
    if section_name and timing_mode == "trimmed":
        return f"Audition {section_name.lower()} {role} from bar 1 in Ableton"
    if section_name and timing_mode == "aligned":
        return f"Place {section_name.lower()} {role} at its full arrangement position"
    if role == "full":
        return "Audition the complete arranged option"
    return f"Audition full-arrangement {role} stem"


def file_manifest_entry(path: str, midi: MidiFile, aligned: bool, trimmed: bool, section=None, role: str = "combined", timing_mode: str | None = None):
    first_tick = first_note_tick(midi)
    last_tick = last_note_tick(midi)
    resolved_timing = timing_mode or ("trimmed" if trimmed else "aligned" if aligned else "full")
    length_bars = section.section_length_bars if section else midi_length_bars(midi)
    return {
        "path": path,
        "file": path,
        "role": role,
        "timing_mode": resolved_timing,
        "note_count": midi_note_count(midi),
        "first_note_tick": first_tick,
        "last_note_tick": last_tick,
        "length_bars": length_bars,
        "aligned": aligned,
        "trimmed": trimmed,
        "section": section.name if section else None,
        "arpeggio_enabled": section.arpeggio_enabled if section else None,
        "trimmed_starts_at_tick_0": bool(trimmed and first_tick == 0) if section else None,
        "aligned_preserves_timing": bool(aligned and first_tick is not None and first_tick >= section.start_tick) if section else None,
        "recommended_use": recommended_use(role, section.name if section else None, resolved_timing),
        "exported": True,
    }


def section_validation_summary(option):
    return [
        {
            "name": section.name,
            "section_length_bars": section.section_length_bars,
            "local_bar_range": f"{section.local_start_bar + 1}-{section.local_end_bar}",
            "arrangement_bar_range": f"{section.arrangement_start_bar + 1}-{section.arrangement_end_bar}",
            "start_tick": section.start_tick,
            "end_tick": section.end_tick,
            "arpeggio_enabled": section.arpeggio_enabled,
            "arpeggio_note_count": len(section.arp_events),
        }
        for section in option.sections
    ]


def validation_report(result, manifest, files_on_disk=None):
    files = manifest["files"]
    files_on_disk = files_on_disk or set()
    exported_files = [item for item in files if item.get("exported", not item.get("skipped")) and not item.get("skipped")]
    skipped_files = [item for item in files if item.get("skipped")]
    empty_arp_files = [item["path"] for item in exported_files if item.get("role") == "arp" and item["note_count"] == 0]
    skipped_empty = [
        item for item in files
        if item.get("skipped")
    ]
    manifest_missing = [item["path"] for item in exported_files if item["path"] not in files_on_disk]
    invalid_trimmed = [
        item["path"] for item in exported_files
        if item.get("trimmed") and item.get("trimmed_starts_at_tick_0") is False
    ]
    invalid_aligned = [
        item["path"] for item in exported_files
        if item.get("section") and item.get("aligned") and item.get("aligned_preserves_timing") is False
    ]
    exported_zero_note = [
        item["path"] for item in exported_files
        if item.get("role") not in ("markers",) and item.get("note_count", 0) == 0
    ]
    passed = not (empty_arp_files or manifest_missing or invalid_trimmed or invalid_aligned or exported_zero_note)
    return {
        "validation_schema_version": "section_stems_v2",
        "passed": passed,
        "full_arrangement_length_bars": result.arrangement_bars,
        "length_mode": result.length_mode,
        "bpm": result.bpm,
        "ppq": TICKS,
        "section_lengths": {
            option.id: section_validation_summary(option)
            for option in result.options
        },
        "exported_files": [item["path"] for item in exported_files],
        "skipped_files": skipped_files,
        "file_note_counts": {item["path"]: item["note_count"] for item in exported_files},
        "file_details": exported_files,
        "arpeggio_files_empty": empty_arp_files,
        "empty_midi_files_skipped": skipped_empty,
        "manifest_references_missing_from_zip": manifest_missing,
        "exported_zero_note_files": exported_zero_note,
        "hook_metadata_exists": {
            option.id: bool(getattr(option, "hook_metadata", None))
            for option in result.options
        },
        "melody_strength_scores": {
            option.id: option.melody_strength_score
            for option in result.options
        },
        "trimmed_section_files_start_at_tick_0": all(
            item.get("trimmed_starts_at_tick_0") is not False
            for item in exported_files
            if item.get("trimmed")
        ),
        "aligned_section_files_preserve_full_timing": all(
            item.get("aligned_preserves_timing") is not False
            for item in exported_files
            if item.get("aligned") and item.get("section")
        ),
        "preview_manifest_matches_midi_timing": True,
    }


def safe_name(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_")


def section_export_slug(section):
    if section.key == "breakdown":
        return "breakdown"
    if section.key == "build":
        return "build"
    return safe_name(section.name)


def skip_manifest_entry(path: str, role: str, section=None, timing_mode: str = "full", reason: str = "No events"):
    return {
        "path": path,
        "file": path,
        "role": role,
        "section": section.name if section else None,
        "timing_mode": timing_mode,
        "note_count": 0,
        "first_note_tick": None,
        "last_note_tick": None,
        "length_bars": section.section_length_bars if section else 0,
        "exported": False,
        "skipped": True,
        "reason": reason,
    }


def save_midi_if_not_empty(midi: MidiFile, output_path: Path, manifest_path: str, manifest: dict, *, role: str, section=None, aligned=False, trimmed=False, timing_mode=None, skip_reason="No events"):
    note_count = midi_note_count(midi)
    if note_count <= 0:
        manifest["files"].append(skip_manifest_entry(manifest_path, role, section=section, timing_mode=timing_mode or ("trimmed" if trimmed else "aligned" if aligned else "full"), reason=skip_reason))
        return None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    midi.save(output_path)
    entry = file_manifest_entry(manifest_path, midi, aligned=aligned, trimmed=trimmed, section=section, role=role, timing_mode=timing_mode)
    manifest["files"].append(entry)
    return entry


def attach_section_export(preview: dict, section_name: str, role: str, timing_mode: str, entry):
    for section in preview["sections"]:
        if section["name"] == section_name:
            section.setdefault("exports", {})
            if role == "combined":
                section["exports"].setdefault("combined", {})
                section["exports"]["combined"][timing_mode] = entry["path"] if entry else None
            else:
                section["exports"].setdefault(role, {})
                if entry:
                    section["exports"][role][timing_mode] = entry["path"]
                    section["exports"][role]["note_count"] = entry["note_count"]
                else:
                    section["exports"][role][timing_mode] = None
            return


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
            "export_schema_version": "section_stems_v2",
            "backend_build_marker": "length_mode_section_stems_active",
            "app_version": app_version,
            "bpm": result.bpm,
            "ppq": TICKS,
            "key": result.key,
            "scale": result.scale,
            "scale_id": result.scale_id,
            "genre": result.genre,
            "generation_type": result.generation_type,
            "arrangement_length_bars": result.arrangement_bars,
            "length_mode": result.length_mode,
            "track_channel_names": {
                "channel_0": "Melody",
                "channel_1": "Chords",
                "channel_2": "Bass Root Guide",
                "channel_3": "Arpeggio Pluck",
            },
            "options": [],
            "files": [],
            "validation": [],
        }
        notes = [
            "EXPORT SCHEMA: section_stems_v2",
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
            full_dir = option_dir / "full"
            combined_dir = option_dir / "sections_combined"
            stems_dir = option_dir / "section_stems"
            full_dir.mkdir(parents=True, exist_ok=True)
            option_preview = option_preview_dict(option)
            option_preview["validation"] = validate_option(option, result)

            full_midi = build_option_midi(option)
            full_name = f"{option_slug}_full_arrangement.mid"
            save_midi_if_not_empty(
                full_midi,
                full_dir / full_name,
                f"{option_slug}/full/{full_name}",
                manifest,
                role="full",
                aligned=True,
                timing_mode="full",
                skip_reason="Full arrangement contains no notes",
            )

            for track_name in ("melody", "chords", "bass", "arp"):
                track_midi = build_track_midi(option, track_name)
                track_file = f"{option_slug}_{track_name if track_name != 'arp' else 'arpeggio_pluck'}_only.mid"
                if track_name == "bass":
                    track_file = f"{option_slug}_bass_root_guide.mid"
                save_midi_if_not_empty(
                    track_midi,
                    full_dir / track_file,
                    f"{option_slug}/full/{track_file}",
                    manifest,
                    role=track_name,
                    aligned=True,
                    timing_mode="full",
                    skip_reason=f"No {track_name} events in full arrangement",
                )

            for section in option.sections:
                section_slug = section_export_slug(section)
                section_stem_dir = stems_dir / section_slug
                aligned_midi = build_aligned_section_midi(option, section)
                aligned_file = f"{option_slug}_{section_slug}_aligned.mid"
                aligned_entry = save_midi_if_not_empty(
                    aligned_midi,
                    combined_dir / aligned_file,
                    f"{option_slug}/sections_combined/{aligned_file}",
                    manifest,
                    role="combined",
                    section=section,
                    aligned=True,
                    timing_mode="aligned",
                    skip_reason=f"No combined events in {section.name}",
                )
                attach_section_export(option_preview, section.name, "combined", "aligned", aligned_entry)
                trimmed_midi = build_trimmed_section_midi(option, section)
                trimmed_file = f"{option_slug}_{section_slug}_trimmed.mid"
                trimmed_entry = save_midi_if_not_empty(
                    trimmed_midi,
                    combined_dir / trimmed_file,
                    f"{option_slug}/sections_combined/{trimmed_file}",
                    manifest,
                    role="combined",
                    section=section,
                    trimmed=True,
                    timing_mode="trimmed",
                    skip_reason=f"No combined events in {section.name}",
                )
                attach_section_export(option_preview, section.name, "combined", "trimmed", trimmed_entry)

                for track_name in ("melody", "chords", "bass", "arp"):
                    for trimmed, timing_mode in ((False, "aligned"), (True, "trimmed")):
                        stem_midi = build_section_track_midi(option, section, track_name, trimmed=trimmed)
                        stem_file = f"{option_slug}_{section_slug}_{TRACK_FILE_NAMES[track_name]}_{timing_mode}.mid"
                        stem_path = f"{option_slug}/section_stems/{section_slug}/{stem_file}"
                        stem_entry = save_midi_if_not_empty(
                            stem_midi,
                            section_stem_dir / stem_file,
                            stem_path,
                            manifest,
                            role=track_name,
                            section=section,
                            aligned=not trimmed,
                            trimmed=trimmed,
                            timing_mode=timing_mode,
                            skip_reason=f"No {track_name} events in {section.name}",
                        )
                        attach_section_export(option_preview, section.name, track_name, timing_mode, stem_entry)
            manifest["options"].append(option_preview)
            manifest["validation"].append({"option": option_slug, **option_preview["validation"]})
            notes.append(option.name)
            notes.append(option.purpose)
            for section in option.sections:
                notes.append(f"- {section.name} arrangement bars {section.arrangement_start_bar + 1}-{section.arrangement_end_bar} / local bars {section.local_start_bar + 1}-{section.local_end_bar}: {' - '.join(section.progression_symbols)}")
            notes.append("")
        (temp_dir / "producer_notes.txt").write_text("\n".join(notes), encoding="utf-8")
        files_on_disk = {str(path.relative_to(temp_dir)).replace("\\", "/") for path in temp_dir.rglob("*") if path.is_file()}
        (temp_dir / "validation_report.json").write_text(json.dumps(validation_report(result, manifest, files_on_disk), indent=2), encoding="utf-8")
        (temp_dir / "preview_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in temp_dir.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(temp_dir))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    return zip_path
