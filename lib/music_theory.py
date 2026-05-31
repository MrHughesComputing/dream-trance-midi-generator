from dataclasses import dataclass


NOTE_TO_PC = {
    "C": 0,
    "C#": 1,
    "Db": 1,
    "D": 2,
    "D#": 3,
    "Eb": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "Gb": 6,
    "G": 7,
    "G#": 8,
    "Ab": 8,
    "A": 9,
    "A#": 10,
    "Bb": 10,
    "B": 11,
}

PC_TO_NAME = {
    0: "C",
    1: "C#",
    2: "D",
    3: "D#",
    4: "E",
    5: "F",
    6: "F#",
    7: "G",
    8: "G#",
    9: "A",
    10: "A#",
    11: "B",
}

MODES = {
    "natural_minor": [0, 2, 3, 5, 7, 8, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "melodic_minor": [0, 2, 3, 5, 7, 9, 11],
    "major": [0, 2, 4, 5, 7, 9, 11],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "aeolian": [0, 2, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "custom_experimental": [0, 1, 3, 5, 6, 7, 10],
}

MODE_LABELS = {
    "natural_minor": "Natural minor",
    "harmonic_minor": "Harmonic minor",
    "melodic_minor": "Melodic minor",
    "major": "Major",
    "dorian": "Dorian",
    "phrygian": "Phrygian",
    "aeolian": "Aeolian",
    "lydian": "Lydian",
    "custom_experimental": "Custom / experimental",
}

KEY_OPTIONS = [
    "B minor",
    "F# minor",
    "D major",
    "A minor",
    "C# minor",
    "G minor",
    "E minor",
    "F minor",
    "A major",
    "C minor",
]


@dataclass(frozen=True)
class ParsedKey:
    label: str
    tonic: str
    tonic_pc: int
    quality: str


def parse_key(label: str) -> ParsedKey:
    parts = (label or "F# minor").strip().split()
    tonic = parts[0] if parts else "F#"
    quality = parts[1].lower() if len(parts) > 1 else "minor"
    if tonic not in NOTE_TO_PC:
        tonic = "F#"
    if quality not in ("minor", "major"):
        quality = "minor"
    return ParsedKey(f"{tonic} {quality}", tonic, NOTE_TO_PC[tonic], quality)


def mode_intervals(mode: str, key_quality: str = "minor"):
    if mode in MODES:
        return MODES[mode]
    return MODES["major" if key_quality == "major" else "natural_minor"]


def scale_pitch_classes(key_label: str, mode: str):
    parsed = parse_key(key_label)
    return {(parsed.tonic_pc + interval) % 12 for interval in mode_intervals(mode, parsed.quality)}


def scale_note(key_label: str, mode: str, degree: int, octave: int = 4) -> int:
    parsed = parse_key(key_label)
    intervals = mode_intervals(mode, parsed.quality)
    degree_index = (degree - 1) % 7
    octave_offset = (degree - 1) // 7
    return parsed.tonic_pc + intervals[degree_index] + (octave + 1 + octave_offset) * 12


def pc_name(pc: int) -> str:
    return PC_TO_NAME[pc % 12]


def midi_name(note: int) -> str:
    octave = (note // 12) - 1
    return f"{pc_name(note)}{octave}"


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def nearest_in_scale(target: int, pitch_classes, low: int, high: int) -> int:
    candidates = [pitch for pitch in range(low, high + 1) if pitch % 12 in pitch_classes]
    if not candidates:
        return clamp(target, low, high)
    return min(candidates, key=lambda pitch: (abs(pitch - target), pitch))


def rotate(items, amount: int):
    if not items:
        return []
    amount = amount % len(items)
    return list(items[amount:]) + list(items[:amount])


def chord_symbol(root_note: int, quality: str) -> str:
    root = pc_name(root_note)
    suffix = {
        "minor": "m",
        "major": "",
        "dim": "dim",
        "sus2": "sus2",
        "sus4": "sus4",
        "add9": "add9",
        "m7": "m7",
        "m9": "m9",
        "maj7": "maj7",
        "power": "5",
    }.get(quality, "")
    return f"{root}{suffix}"

