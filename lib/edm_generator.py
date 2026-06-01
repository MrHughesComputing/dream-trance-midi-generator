from dataclasses import dataclass, field
import random

from .music_theory import (
    MODE_LABELS,
    pc_name,
    clamp,
    midi_name,
    nearest_in_scale,
    parse_key,
    rotate,
    scale_note,
    scale_pitch_classes,
)

TICKS = 480
BAR_TICKS = TICKS * 4

GENRE_LABELS = {
    "uplifting_trance": "Uplifting Trance",
    "progressive_trance": "Progressive Trance",
    "dark_emotional_trance": "Dark / Emotional Trance",
    "melodic_edm": "Melodic EDM",
    "classic_2000s_trance": "Classic 2000s Trance",
    "experimental_trance_edm": "Experimental Trance / EDM",
}

GENERATION_LABELS = {
    "chords_only": "Chords only",
    "melody_only": "Melody only",
    "chords_melody": "Chords + melody",
    "full_section_sketch": "Full section sketch",
    "drop_hook_only": "Drop hook only",
    "breakdown_progression_only": "Breakdown emotional progression only",
}

SECTION_LABELS = {
    "intro": "Intro",
    "breakdown": "Verse / Breakdown",
    "build": "Build-up",
    "drop": "Drop",
    "outro": "Outro",
    "full": "Full mini-arrangement",
}

COMPLEXITY_LABELS = {
    "simple": "Simple",
    "medium": "Medium",
    "advanced": "Advanced",
    "experimental": "Experimental",
}

ENERGY_LABELS = {
    "low_atmospheric": "Low / atmospheric",
    "emotional": "Emotional",
    "building": "Building",
    "peak_time": "Peak-time",
    "festival_drop": "Festival drop",
    "dark_tension": "Dark tension",
}

RISK_LABELS = {
    "safe_radio": "Safe / radio-friendly",
    "club_ready": "Club-ready",
    "emotional_cinematic": "Emotional / cinematic",
    "experimental_usable": "Experimental but usable",
    "outside_box": "Outside-the-box",
}

OPTION_PROFILES = [
    {
        "id": "classic_reliable",
        "name": "Option 1: Classic / Reliable",
        "purpose": "Polished trance-friendly progression with clear chord-tone melody targets.",
        "risk": "Safe, familiar, DAW-ready.",
    },
    {
        "id": "emotional_cinematic",
        "name": "Option 2: Emotional / Cinematic",
        "purpose": "More suspended, expressive, and phrase-led with stronger tension and release.",
        "risk": "Emotional and cinematic while staying mixable.",
    },
    {
        "id": "experimental_modern",
        "name": "Option 3: Experimental / Outside-the-Box",
        "purpose": "Borrowed colour, rhythmic displacement, and modal tension without random notes.",
        "risk": "Creative but still usable for trance and melodic EDM.",
    },
]

PROGRESSION_PATTERNS = {
    "uplifting_trance": {
        "intro": [[1, 6, 7, 1], [1, 6, 3, 7]],
        "breakdown": [[1, 6, 3, 7], [1, 4, 6, 7]],
        "drop": [[1, 6, 3, 7], [6, 7, 1, 1], [1, 7, 6, 7]],
    },
    "progressive_trance": {
        "intro": [[1, 6, 7, 1], [6, 1, 7, 4]],
        "breakdown": [[1, 4, 6, 7], [1, 3, 7, 6]],
        "drop": [[1, 6, 7, 1], [6, 1, 7, 4]],
    },
    "dark_emotional_trance": {
        "intro": [[1, 7, 6, 4], [1, 6, 4, 5]],
        "breakdown": [[1, 4, 5, 6], [1, 3, 4, 7]],
        "drop": [[1, 7, 6, 4], [1, 6, 4, 5], [1, 2, 6, 5]],
    },
    "melodic_edm": {
        "intro": [[1, 6, 4, 5], [6, 4, 1, 5]],
        "breakdown": [[1, 5, 6, 4], [6, 4, 1, 5]],
        "drop": [[1, 5, 6, 4], [6, 4, 1, 5], [1, 6, 4, 5]],
    },
    "classic_2000s_trance": {
        "intro": [[1, 7, 6, 7], [6, 7, 1, 1]],
        "breakdown": [[1, 6, 3, 7], [1, 7, 6, 7]],
        "drop": [[1, 6, 3, 7], [6, 7, 1, 1]],
    },
    "experimental_trance_edm": {
        "intro": [[1, 2, 6, 5], [1, 6, 2, 7]],
        "breakdown": [[1, 4, 2, 6], [6, 2, 1, 5]],
        "drop": [[1, 2, 6, 7], [1, 3, 2, 6], [6, 7, 1, 2]],
    },
}

ROMAN = {1: "i", 2: "II", 3: "III", 4: "iv", 5: "v", 6: "VI", 7: "VII"}


@dataclass
class ChordIdea:
    degree: int
    root: int
    quality: str
    tones: list[int]
    required_pcs: list[int]
    voicing: list[int]
    symbol: str
    roman: str
    voicing_type: str = "full"
    omitted_tones: list[str] = field(default_factory=list)


@dataclass
class SectionIdea:
    key: str
    name: str
    start_bar: int
    bars: int
    energy: str
    chords: list[ChordIdea]
    section_length_bars: int = 0
    local_start_bar: int = 0
    local_end_bar: int = 0
    arrangement_start_bar: int = 0
    arrangement_end_bar: int = 0
    start_tick: int = 0
    end_tick: int = 0
    arpeggio_enabled: bool = True
    chord_events: list[dict] = field(default_factory=list)
    melody_events: list[dict] = field(default_factory=list)
    bass_events: list[dict] = field(default_factory=list)
    arp_events: list[dict] = field(default_factory=list)
    motif_summary: str = ""

    def __post_init__(self):
        if not self.section_length_bars:
            self.section_length_bars = self.bars
        if not self.local_end_bar:
            self.local_end_bar = self.section_length_bars
        self.arrangement_start_bar = self.start_bar
        self.arrangement_end_bar = self.start_bar + self.bars
        self.start_tick = bar_tick(self.arrangement_start_bar)
        self.end_tick = bar_tick(self.arrangement_end_bar)

    @property
    def progression_symbols(self):
        return [chord.symbol for chord in self.chords]


@dataclass
class GeneratedOption:
    id: str
    name: str
    purpose: str
    risk: str
    genre: str
    key: str
    scale: str
    scale_id: str
    bpm: int
    generation_type: str
    sections: list[SectionIdea]
    energy_description: str
    creative_risk_description: str
    hook_summary: str
    core_motif_notes: list[str]
    core_motif_rhythm: list[float]
    phrase_structure: str
    strongest_hook_bar: int
    melody_strength_score: int
    hook_subscores: dict
    candidates_generated: int
    candidates_rejected: int
    hook_threshold: int
    threshold_met: bool
    selected_reason: str
    hook_metadata: dict
    melody_audit: dict
    core_hook_audit: dict
    full_arrangement_melody_audit: dict
    top_candidate_summaries: list[dict] = field(default_factory=list)


@dataclass
class GenerationResult:
    bpm: int
    key: str
    scale: str
    scale_id: str
    genre: str
    generation_type: str
    arrangement_bars: int
    length_mode: str
    options: list[GeneratedOption]


def tick(beats: float) -> int:
    return int(round(beats * TICKS))


def bar_tick(bar_index: int) -> int:
    return bar_index * BAR_TICKS


def section_plan(generation_type: str, arrangement_section: str, bars: int, length_mode: str = "per_section"):
    if generation_type == "full_section_sketch" or arrangement_section == "full":
        if length_mode == "per_section":
            return [("Intro", bars), ("Verse / Breakdown", bars), ("Drop", bars)]
        if bars == 8:
            return [("Intro", 2), ("Verse / Breakdown", 2), ("Drop", 4)]
        if bars == 16:
            return [("Intro", 4), ("Verse / Breakdown", 4), ("Drop", 8)]
        if bars == 32:
            return [("Intro", 8), ("Verse / Breakdown", 8), ("Build-up", 8), ("Drop", 8)]
        intro = max(1, bars // 4)
        breakdown = max(1, bars // 4)
        return [("Intro", intro), ("Verse / Breakdown", breakdown), ("Drop", bars - intro - breakdown)]
    if generation_type == "drop_hook_only":
        return [("Drop", bars)]
    if generation_type == "breakdown_progression_only":
        return [("Verse / Breakdown", bars)]
    return [(SECTION_LABELS.get(arrangement_section, "Drop"), bars)]


def section_key(name: str) -> str:
    lowered = name.lower()
    if "intro" in lowered:
        return "intro"
    if "drop" in lowered:
        return "drop"
    if "build" in lowered:
        return "build"
    if "outro" in lowered:
        return "outro"
    return "breakdown"


def degree_triad(key_label: str, mode: str, degree: int, option_id: str, section: str, genre: str) -> ChordIdea:
    root = scale_note(key_label, mode, degree, 3 if degree in (6, 7) else 4)
    third = scale_note(key_label, mode, degree + 2, 3 if degree in (6, 7) else 4)
    fifth = scale_note(key_label, mode, degree + 4, 3 if degree in (6, 7) else 4)
    while third <= root:
        third += 12
    while fifth <= third:
        fifth += 12
    tones = [root, third, fifth]
    semis = sorted([(tone - root) % 12 for tone in tones])
    quality = "minor" if 3 in semis and 7 in semis else "dim" if 3 in semis and 6 in semis else "aug" if 4 in semis and 8 in semis else "major"
    base_quality = quality

    if option_id == "emotional_cinematic" and section in ("breakdown", "intro"):
        quality = "add9" if quality in ("minor", "major") and degree in (1, 6) else "sus2" if degree in (4, 7) else quality
    elif option_id == "experimental_modern":
        if degree == 2 and genre in ("dark_emotional_trance", "experimental_trance_edm"):
            quality = "sus4"
        elif section == "drop" and degree == 2:
            quality = "sus2"
        elif degree in (1, 6):
            quality = "m9" if quality == "minor" else "maj7"
        elif section == "drop" and degree in (5, 7):
            quality = "power"

    required_pcs = required_pitch_classes(root, quality, base_quality == "major")
    if quality in ("add9", "sus2", "sus4") and option_id != "experimental_modern":
        required_pcs = diatonic_extension_pcs(key_label, mode, degree, quality)
    return ChordIdea(
        degree=degree,
        root=root,
        quality=quality,
        tones=tones,
        required_pcs=required_pcs,
        voicing=[],
        symbol=quality_symbol(root, quality, required_pcs),
        roman=ROMAN.get(degree, str(degree)),
    )


def required_pitch_classes(root: int, quality: str, major_hint: bool = False):
    third = 4 if major_hint else 3
    interval_map = {
        "minor": [0, 3, 7],
        "major": [0, 4, 7],
        "dim": [0, 3, 6],
        "aug": [0, 4, 8],
        "sus2": [0, 2, 7],
        "sus4": [0, 5, 7],
        "add9": [0, third, 7, 14],
        "m7": [0, 3, 7, 10],
        "m9": [0, 3, 7, 10, 14],
        "maj7": [0, 4, 7, 11],
        "power": [0, 7],
    }
    return [((root + interval) % 12) for interval in interval_map.get(quality, [0, third, 7])]


def diatonic_extension_pcs(key_label: str, mode: str, degree: int, quality: str):
    root = scale_note(key_label, mode, degree, 4)
    third = scale_note(key_label, mode, degree + 2, 4)
    fifth = scale_note(key_label, mode, degree + 4, 4)
    second = scale_note(key_label, mode, degree + 1, 4)
    fourth = scale_note(key_label, mode, degree + 3, 4)
    ninth = scale_note(key_label, mode, degree + 8, 4)
    if quality == "sus2":
        return [root % 12, second % 12, fifth % 12]
    if quality == "sus4":
        return [root % 12, fourth % 12, fifth % 12]
    return [root % 12, third % 12, fifth % 12, ninth % 12]


def quality_symbol(root: int, quality: str, required_pcs):
    suffix = {
        "minor": "m",
        "major": "",
        "dim": "dim",
        "aug": "aug",
        "sus2": "sus2",
        "sus4": "sus4",
        "add9": "add9",
        "m7": "m7",
        "m9": "m9",
        "maj7": "maj7",
        "power": "5",
    }.get(quality, "")
    return f"{pc_name(root)}{suffix}"


def pitch_for_pc(target_pc: int, near: int, low: int, high: int):
    candidates = [pitch for pitch in range(low, high + 1) if pitch % 12 == target_pc]
    if not candidates:
        return clamp(near, low, high)
    return min(candidates, key=lambda pitch: (abs(pitch - near), pitch))


def fit_pitch_preserve_pc(note: int, low: int, high: int):
    while note > high:
        note -= 12
    while note < low:
        note += 12
    return clamp(note, low, high)


def chord_extension_notes(chord: ChordIdea, register_low: int, register_high: int):
    targets = []
    for idx, pc in enumerate(chord.required_pcs):
        near = chord.root + (0 if idx == 0 else 4 + idx * 3)
        targets.append(pitch_for_pc(pc, near, register_low, register_high))
    return sorted(dict.fromkeys(targets))


def label_voicing(chord: ChordIdea, notes):
    pcs = {note % 12 for note in notes}
    missing = [pc for pc in chord.required_pcs if pc not in pcs]
    chord.omitted_tones = [pc_name(pc) for pc in missing]
    if not missing:
        chord.voicing_type = "full" if chord.quality in ("minor", "major", "dim", "aug") else "extended" if chord.quality in ("add9", "m7", "m9", "maj7") else "suspended" if chord.quality.startswith("sus") else "power"
        return chord.symbol
    suffix = ""
    if (chord.root + 3) % 12 in missing or (chord.root + 4) % 12 in missing:
        suffix += " no3"
    if (chord.root + 7) % 12 in missing:
        suffix += " no5"
    if chord.quality in ("add9", "m9") and (chord.root + 14) % 12 in missing:
        suffix += " no9"
    chord.voicing_type = "open/rootless" if chord.root % 12 in missing else "open"
    return f"{chord.symbol}{suffix}".strip()


def voice_chord(chord: ChordIdea, key_label: str, mode: str, section: str, option_id: str, energy: str):
    pitch_classes = scale_pitch_classes(key_label, mode)
    root_low = pitch_for_pc(chord.root % 12, chord.root - 12, 36, 58)
    base = chord_extension_notes(chord, 52, 88)
    if section == "intro":
        notes = [root_low] + base if option_id != "classic_reliable" or chord.quality in ("add9", "sus2", "sus4") else [root_low] + base[:3]
    elif section == "breakdown":
        notes = [root_low] + base
        if option_id in ("emotional_cinematic", "experimental_modern") and not chord.quality.startswith("sus"):
            notes.append(pitch_for_pc(chord.tones[1] % 12, chord.tones[1] + 12, 67, 91))
    elif section == "drop":
        notes = [root_low] + base
        if energy in ("peak_time", "festival_drop"):
            notes.append(pitch_for_pc(chord.root % 12, chord.root + 24, 72, 96))
    else:
        notes = [root_low] + base
    voicing = sorted(dict.fromkeys(fit_pitch_preserve_pc(note, 36, 96) for note in notes))
    chord.symbol = label_voicing(chord, voicing)
    return voicing


def select_pattern(genre: str, section: str, option_id: str, rng: random.Random, variant: int = 0):
    patterns = PROGRESSION_PATTERNS.get(genre, PROGRESSION_PATTERNS["uplifting_trance"]).get(section)
    if not patterns:
        patterns = PROGRESSION_PATTERNS.get(genre, PROGRESSION_PATTERNS["uplifting_trance"])["breakdown"]
    index = 0 if option_id == "classic_reliable" else 1 if option_id == "emotional_cinematic" and len(patterns) > 1 else len(patterns) - 1
    if variant and patterns:
        index = (index + variant) % len(patterns)
    chosen = list(patterns[index])
    if option_id == "experimental_modern":
        if section == "drop" and genre == "uplifting_trance":
            chosen = [1, 2, 6, 7]
        elif section == "drop" and genre in ("melodic_edm", "progressive_trance"):
            chosen = [6, 2, 1, 5]
        elif genre in ("experimental_trance_edm", "dark_emotional_trance"):
            chosen = rotate(chosen, 1 if section == "drop" else 0)
        elif section == "breakdown":
            chosen = chosen[:2] + [2 if 2 not in chosen else 4] + chosen[-1:]
    return chosen


def chord_duration(section: str, complexity: str, energy: str):
    if section == "intro":
        return 8.0 if complexity == "simple" else 4.0
    if section == "drop":
        return 4.0
    if complexity == "advanced":
        return 2.0 if energy in ("building", "dark_tension") else 4.0
    return 4.0


def build_chords(key_label: str, mode: str, genre: str, section: str, option_id: str, complexity: str, energy: str, rng, variant: int = 0):
    pattern = select_pattern(genre, section, option_id, rng, variant)
    chords = [degree_triad(key_label, mode, degree, option_id, section, genre) for degree in pattern]
    for chord in chords:
        chord.voicing = voice_chord(chord, key_label, mode, section, option_id, energy)
    return chords


def melody_pattern(section: str, option_id: str, complexity: str, genre: str):
    if section == "intro":
        return [(2.5, 0.45), (3.25, 0.65)] if option_id == "experimental_modern" else [(2.0, 0.5), (3.0, 0.75)] if complexity != "simple" else [(3.0, 0.75)]
    if section == "breakdown":
        if option_id == "emotional_cinematic":
            return [(0.0, 0.75), (1.0, 1.0), (2.5, 0.5), (3.25, 1.25)]
        if option_id == "experimental_modern":
            return [(0.25, 0.5), (1.25, 0.75), (2.25, 0.5), (3.5, 0.45)]
        return [(0.0, 0.75), (1.5, 0.75), (2.75, 1.0), (3.5, 0.5)]
    if genre == "classic_2000s_trance" or complexity == "advanced":
        return [(0.0, 0.25), (0.5, 0.25), (1.0, 0.25), (1.5, 0.25), (2.0, 0.5), (3.0, 0.75)]
    if option_id == "experimental_modern":
        return [(0.0, 0.45), (0.75, 0.45), (1.5, 0.65), (2.5, 0.45), (3.25, 0.65)]
    return [(0.0, 0.5), (1.0, 0.5), (2.0, 0.75), (3.0, 0.75), (3.5, 0.4)]


def create_hook_identity(key_label: str, mode: str, option_id: str, genre: str, candidate_index: int = 0, rng: random.Random | None = None):
    rng = rng or random.Random(candidate_index)
    if option_id == "classic_reliable":
        role_variants = [
            ["root", "third", "fifth", "third", "root"],
            ["root", "fifth", "third", "fifth", "root"],
            ["third", "root", "fifth", "third", "root"],
        ]
        rhythm_variants = [
            [(0.0, 0.5), (0.75, 0.5), (1.5, 0.75), (2.5, 0.5), (3.0, 1.0)],
            [(0.0, 0.5), (1.0, 0.5), (1.75, 0.5), (2.5, 0.75), (3.25, 0.75)],
            [(0.0, 0.75), (1.25, 0.5), (2.0, 0.5), (2.75, 0.5), (3.25, 0.75)],
        ]
        fingerprints = ["short_short_long_rest_short", "eighth_note_hook", "question_answer_space"]
        roles = role_variants[candidate_index % len(role_variants)]
        rhythm_index = (candidate_index // len(role_variants)) % len(rhythm_variants)
        rhythm = rhythm_variants[rhythm_index]
        rhythmic_fingerprint = fingerprints[rhythm_index]
        summary = "Five-note rising-and-returning F# minor style hook with a clean chord-tone identity and final-bar resolution. Best for supersaw or pluck lead."
        structure = "A - A' - B - A''"
        emotional_target = "euphoric resolution"
        recommended_synth_role = "supersaw or pluck lead"
    elif option_id == "emotional_cinematic":
        role_variants = [
            ["third", "root", "fifth", "third", "upper_root", "fifth"],
            ["root", "third", "fifth", "upper_root", "third", "root"],
            ["third", "fifth", "root", "third", "fifth", "upper_root"],
            ["fifth", "third", "root", "fifth", "upper_root", "third"],
        ]
        rhythm_variants = [
            [(0.0, 0.75), (1.0, 0.75), (2.0, 1.0), (3.0, 0.5), (3.5, 1.25), (0.5, 0.5)],
            [(0.5, 0.75), (1.5, 0.75), (2.5, 0.75), (3.25, 1.25), (0.0, 0.5), (2.0, 0.5)],
            [(0.0, 1.0), (1.25, 0.5), (2.0, 0.75), (3.0, 1.0), (3.5, 0.75), (0.75, 0.5)],
        ]
        fingerprints = ["long_short_short_long", "offbeat_answer", "held_payoff"]
        roles = role_variants[candidate_index % len(role_variants)]
        rhythm_index = (candidate_index // len(role_variants)) % len(rhythm_variants)
        rhythm = rhythm_variants[rhythm_index]
        rhythmic_fingerprint = fingerprints[rhythm_index]
        summary = "Expressive call-and-response hook with longer endings, stronger thirds/fifths, and a cinematic lift into the payoff. Best for piano, vocal guide, strings, or emotional lead."
        structure = "A - A' - lift - payoff"
        emotional_target = "cinematic lift"
        recommended_synth_role = "piano, strings, vocal guide, or emotional lead"
    else:
        role_variants = [
            ["fifth", "second", "root", "third", "flat_second", "root"],
            ["root", "flat_second", "fifth", "third", "second", "root"],
            ["third", "fifth", "second", "root", "upper_root", "flat_second"],
            ["fifth", "root", "second", "flat_second", "third", "root"],
        ]
        rhythm_variants = [
            [(0.0, 0.45), (0.75, 0.45), (1.5, 0.65), (2.25, 0.45), (3.25, 0.65), (3.75, 0.4)],
            [(0.0, 0.5), (0.5, 0.35), (1.25, 0.65), (2.0, 0.5), (2.75, 0.75), (3.5, 0.4)],
            [(0.25, 0.45), (1.0, 0.45), (1.75, 0.65), (2.5, 0.45), (3.0, 0.75), (3.75, 0.35)],
        ]
        fingerprints = ["syncopated_push", "offbeat_answer", "sixteenth_note_lift"]
        roles = role_variants[candidate_index % len(role_variants)]
        rhythm_index = (candidate_index // len(role_variants)) % len(rhythm_variants)
        rhythm = rhythm_variants[rhythm_index]
        rhythmic_fingerprint = fingerprints[rhythm_index]
        summary = "Modern syncopated hook with controlled neighbour-tone tension and a displaced answer phrase that resolves into the drop. Best for progressive EDM or darker festival lead."
        structure = "A - displaced answer - tension - resolution"
        emotional_target = "controlled modern tension"
        recommended_synth_role = "progressive EDM lead, pluck stack, or darker festival lead"
    preview_chord = degree_triad(key_label, mode, 1, option_id, "drop", genre)
    preview_chord.voicing = voice_chord(preview_chord, key_label, mode, "drop", option_id, "peak_time")
    midi_notes = [hook_pitch_for_role(role, preview_chord, key_label, mode, option_id, "drop") for role in roles[:6]]
    notes = [midi_name(note) for note in midi_notes]
    interval_shape = [midi_notes[idx] - midi_notes[idx - 1] for idx in range(1, len(midi_notes))]
    intentional_tension_notes = []
    if option_id == "experimental_modern" and "flat_second" in roles:
        intentional_tension_notes.append({
            "note": midi_name(hook_pitch_for_role("flat_second", preview_chord, key_label, mode, option_id, "drop")),
            "reason": "chromatic lower neighbour used for modern Phrygian-style tension",
            "resolved_to": midi_name(hook_pitch_for_role("root", preview_chord, key_label, mode, option_id, "drop")),
        })
    return {
        "roles": roles,
        "rhythm": rhythm,
        "summary": summary,
        "structure": structure,
        "notes": notes,
        "midi_notes": midi_notes,
        "motif_interval_shape": interval_shape,
        "rhythmic_fingerprint": rhythmic_fingerprint,
        "payoff_note": notes[-1] if notes else "",
        "emotional_target": emotional_target,
        "recommended_synth_role": recommended_synth_role,
        "intentional_tension_notes": intentional_tension_notes,
        "candidate_index": candidate_index,
    }


def hook_pitch_for_role(role: str, chord: ChordIdea, key_label: str, mode: str, option_id: str, section: str):
    pitch_classes = scale_pitch_classes(key_label, mode)
    low, high = (60, 78) if section in ("intro", "breakdown") else (72, 92)
    root = pitch_for_pc(chord.root % 12, chord.root + 12, low, high)
    third = pitch_for_pc(chord.required_pcs[1 % len(chord.required_pcs)], chord.root + 15, low, high)
    fifth_pc = chord.required_pcs[2 % len(chord.required_pcs)] if len(chord.required_pcs) > 2 else (chord.root + 7) % 12
    fifth = pitch_for_pc(fifth_pc, chord.root + 19, low, high)
    if role == "root":
        return root
    if role == "third":
        return third
    if role == "fifth":
        return fifth
    if role == "upper_root":
        return fit_pitch_preserve_pc(root + 12, low, high + 5)
    if role == "second":
        return nearest_in_scale(root + 2, pitch_classes, low, high)
    if role == "flat_second" and option_id == "experimental_modern":
        return fit_pitch_preserve_pc(root + 1, low, high)
    return nearest_in_scale((root + fifth) // 2, pitch_classes, low, high)


def hook_events_for_bar(chord: ChordIdea, hook_identity, key_label: str, mode: str, section: str, option_id: str, local_bar: int, start: int):
    roles = hook_identity["roles"]
    rhythm = hook_identity["rhythm"]
    if section == "intro":
        role_slice = roles[:2] if local_bar % 2 == 0 else roles[-2:-1]
        rhythm_slice = [(2.5, 0.55), (3.25, 0.75)][:len(role_slice)]
    elif section == "breakdown":
        if local_bar % 4 in (0, 1):
            role_slice = roles[:4]
        elif local_bar % 4 == 2:
            role_slice = roles[1:5]
        else:
            role_slice = roles[2:5] + ["upper_root"]
        rhythm_slice = [(beat, max(length, 0.75)) for beat, length in rhythm[:len(role_slice)]]
    else:
        if local_bar % 4 in (0, 2):
            role_slice = roles[:5]
        elif local_bar % 4 == 1:
            role_slice = roles[1:] + roles[:1]
        else:
            role_slice = roles[2:] + ["upper_root", "root"]
        rhythm_slice = rhythm[:len(role_slice)]
    events = []
    for idx, role in enumerate(role_slice):
        beat, length = rhythm_slice[idx % len(rhythm_slice)]
        pitch = hook_pitch_for_role(role, chord, key_label, mode, option_id, section)
        if section == "breakdown" and idx == len(role_slice) - 1:
            length = max(length, 1.25)
        if section == "drop" and local_bar % 4 == 3 and idx == len(role_slice) - 2:
            pitch = fit_pitch_preserve_pc(pitch + 12, 72, 96)
        if section == "drop" and local_bar % 4 == 3 and idx == len(role_slice) - 1:
            length = max(length, 1.0)
        events.append({"start": start + tick(beat), "duration": tick(length), "note": pitch, "velocity": 72 if section == "intro" else 88 if section == "breakdown" else 106})
    return events


def clamp_score(value):
    return int(clamp(round(value), 0, 100))


def event_bar(section: SectionIdea, event):
    return max(0, (event["start"] - section.start_tick) // BAR_TICKS)


def event_beat(event):
    return round((event["start"] % BAR_TICKS) / TICKS, 3)


def motif_signature(events, limit):
    ordered = sorted(events, key=lambda item: (item["start"], item["note"]))[:limit]
    if not ordered:
        return []
    first_pitch = ordered[0]["note"]
    first_start = ordered[0]["start"]
    return [
        (
            event["note"] - first_pitch,
            round((event["start"] - first_start) / TICKS, 2),
            round(event["duration"] / TICKS, 2),
        )
        for event in ordered
    ]


def rhythm_signature(events, limit=None):
    ordered = sorted(events, key=lambda item: (item["start"], item["note"]))
    if limit:
        ordered = ordered[:limit]
    return [
        (round((event["start"] % BAR_TICKS) / TICKS, 2), round(event["duration"] / TICKS, 2))
        for event in ordered
    ]


def signature_similarity(a, b):
    if not a or not b:
        return 0.0
    length = min(len(a), len(b))
    matches = sum(1 for idx in range(length) if a[idx] == b[idx])
    return matches / max(len(a), len(b))


def section_by_key(sections, key):
    return next((section for section in sections if section.key == key), None)


def chord_for_event(section: SectionIdea, event):
    if not section.chords:
        return None
    local_bar = event_bar(section, event)
    return section.chords[local_bar % len(section.chords)]


def strong_beat(event):
    beat = event_beat(event)
    return beat in (0.0, 1.0, 2.0, 3.0) or abs(beat - round(beat)) < 0.01


def weighted_hook_total(scores):
    return clamp_score(
        scores["motif_clarity"] * 0.20
        + scores["hummability"] * 0.20
        + scores["rhythmic_identity"] * 0.15
        + scores["chord_tone_targeting"] * 0.15
        + scores["phrase_shape"] * 0.15
        + scores["repetition_variation"] * 0.10
        + scores["edm_suitability"] * 0.05
    )


def score_hook_identity(option_id: str, sections: list[SectionIdea], hook_identity):
    melody = [event for section in sections for event in section.melody_events]
    if not melody:
        return {"total": 0, "motif_clarity": 0, "rhythmic_identity": 0, "hummability": 0, "singability": 0, "chord_tone_targeting": 0, "phrase_shape": 0, "repetition_variation": 0, "edm_suitability": 0, "score_explanation": {}, "score_confidence": "rule_based_structural_analysis"}
    section_map = {section.key: section for section in sections}
    intro = section_map.get("intro")
    breakdown = section_map.get("breakdown")
    drop = section_map.get("drop")
    drop_events = sorted((drop.melody_events if drop else []), key=lambda item: (item["start"], item["note"]))
    intro_events = sorted((intro.melody_events if intro else []), key=lambda item: (item["start"], item["note"]))
    breakdown_events = sorted((breakdown.melody_events if breakdown else []), key=lambda item: (item["start"], item["note"]))
    pitches = [event["note"] for event in melody]
    starts = [event["start"] % BAR_TICKS for event in melody]
    durations = [event["duration"] for event in melody]
    intervals = [abs(pitches[idx] - pitches[idx - 1]) for idx in range(1, len(pitches))]
    motif_len = len(hook_identity["roles"])
    motif_sig = motif_signature(drop_events or melody, motif_len)
    drop_windows = [drop_events[idx:idx + motif_len] for idx in range(0, max(0, len(drop_events) - motif_len + 1), max(1, motif_len))]
    motif_matches = sum(1 for window in drop_windows[1:] if signature_similarity(motif_sig, motif_signature(window, motif_len)) >= 0.55)
    intro_reference = signature_similarity(motif_sig[:max(1, min(3, len(motif_sig)))], motif_signature(intro_events, max(1, min(3, motif_len))))
    breakdown_reference = signature_similarity(motif_sig[:max(1, min(4, len(motif_sig)))], motif_signature(breakdown_events, max(1, min(4, motif_len))))
    unrelated_penalty = max(0, len(set(pitches)) - motif_len - 3) * 2
    motif_clarity = clamp_score(54 + (18 if 3 <= motif_len <= 7 else -12) + motif_matches * 5 + intro_reference * 9 + breakdown_reference * 9 - unrelated_penalty)

    rhythm_sig = rhythm_signature(drop_events, motif_len)
    rhythm_windows = [rhythm_signature(window) for window in drop_windows if window]
    rhythm_repeats = sum(1 for sig in rhythm_windows[1:] if signature_similarity(rhythm_sig, sig) >= 0.6)
    unique_durations = len(set(round(duration / TICKS, 2) for duration in durations))
    unique_starts = len(set(round(start / TICKS, 2) for start in starts))
    syncopated = sum(1 for start in starts if (start % TICKS) not in (0, TICKS // 2))
    density = len(melody) / max(1, sum(section.section_length_bars for section in sections))
    rhythm_complexity_penalty = max(0, unique_starts - 8) * 2 + max(0, syncopated - 48) * 0.25
    rhythmic_identity = min(96, clamp_score(42 + rhythm_repeats * 3.5 + unique_durations * 4 + min(9, unique_starts * 1.1) + min(7, syncopated * 0.12) - (16 if unique_durations <= 1 else 0) - max(0, density - 6) * 5 - rhythm_complexity_penalty))

    range_span = max(pitches) - min(pitches)
    large_leaps = sum(1 for interval in intervals if interval > 12)
    avg_interval = sum(intervals) / max(1, len(intervals))
    stepwise_ratio = sum(1 for interval in intervals if interval <= 5) / max(1, len(intervals))
    final_pitch = drop_events[-1]["note"] if drop_events else melody[-1]["note"]
    final_repeats_motif = final_pitch % 12 in {note % 12 for note in hook_identity.get("midi_notes", [])}
    hummability = clamp_score(72 + stepwise_ratio * 20 - large_leaps * 5 - max(0, range_span - 15) * 1.6 - max(0, avg_interval - 7) * 2 + (7 if final_repeats_motif else -5))

    strong_hits = 0
    strong_total = 0
    ending_hits = 0
    ending_total = 0
    tension_count = 0
    resolved_tension = 0
    for section in sections:
        ordered = sorted(section.melody_events, key=lambda item: (item["start"], item["note"]))
        for idx, event in enumerate(ordered):
            chord = chord_for_event(section, event)
            if not chord:
                continue
            chord_pcs = set(chord.required_pcs)
            is_hit = event["note"] % 12 in chord_pcs
            if strong_beat(event):
                strong_total += 1
                strong_hits += 1 if is_hit else 0
            local_beat = event_beat(event)
            if event["duration"] >= tick(0.75) or local_beat >= 3.0:
                ending_total += 1
                ending_hits += 1 if is_hit else 0
            if not is_hit:
                tension_count += 1
                if idx + 1 < len(ordered) and ordered[idx + 1]["note"] % 12 in chord_pcs:
                    resolved_tension += 1
    strong_ratio = strong_hits / max(1, strong_total)
    ending_ratio = ending_hits / max(1, ending_total)
    tension_resolution = resolved_tension / max(1, tension_count)
    chord_tone_targeting = clamp_score(46 + strong_ratio * 26 + ending_ratio * 18 + tension_resolution * 10 - max(0, tension_count - 4) * (3 if option_id != "experimental_modern" else 1.2))

    phrase_peaks = []
    for section in sections:
        for block_start in range(0, section.section_length_bars, 4):
            block = [event["note"] for event in section.melody_events if block_start <= event_bar(section, event) < block_start + 4]
            if block:
                phrase_peaks.append(max(block) - min(block))
    high_point = max(pitches)
    high_point_late = any(event["note"] == high_point and (event["start"] - (drop.start_tick if drop else 0)) >= BAR_TICKS * 4 for event in drop_events)
    final_long = bool(drop_events and drop_events[-1]["duration"] >= tick(0.75))
    contour_changes = sum(1 for idx in range(2, len(pitches)) if (pitches[idx] - pitches[idx - 1]) * (pitches[idx - 1] - pitches[idx - 2]) < 0)
    phrase_shape = clamp_score(50 + min(16, sum(phrase_peaks) / max(1, len(phrase_peaks))) + (12 if high_point_late else 0) + (10 if final_long else 0) + min(10, contour_changes) - (10 if range_span < 5 else 0))

    exact_repetition = sum(1 for window in drop_windows[1:] if signature_similarity(motif_sig, motif_signature(window, motif_len)) >= 0.9)
    related_variation = sum(1 for window in drop_windows[1:] if 0.45 <= signature_similarity(motif_sig, motif_signature(window, motif_len)) < 0.9)
    section_development = (1 if intro_reference > 0.3 else 0) + (1 if breakdown_reference > 0.3 else 0)
    repetition_variation = clamp_score(50 + exact_repetition * 8 + related_variation * 7 + section_development * 8 - (10 if exact_repetition > 5 and related_variation == 0 else 0) - (12 if exact_repetition == 0 else 0))

    drop_density = len(drop_events) / max(1, drop.section_length_bars if drop else 1)
    bar_aligned = sum(1 for event in drop_events if event_beat(event) in (0.0, 1.0, 2.0, 3.0)) / max(1, len(drop_events))
    register_ok = 68 <= (sum(drop_event["note"] for drop_event in drop_events) / max(1, len(drop_events))) <= 90 if drop_events else False
    phrase_cell_count = len({(event_bar(drop, event) // 4, round(event_beat(event), 2)) for event in drop_events}) if drop else 0
    edm_suitability = clamp_score(55 + (14 if drop_events else -20) + bar_aligned * 10 + (8 if register_ok else -8) + (8 if 2 <= drop_density <= 7 else -8) + min(8, phrase_cell_count / 4))

    scores = {
        "motif_clarity": motif_clarity,
        "rhythmic_identity": rhythmic_identity,
        "hummability": hummability,
        "chord_tone_targeting": chord_tone_targeting,
        "phrase_shape": phrase_shape,
        "repetition_variation": repetition_variation,
        "edm_suitability": edm_suitability,
    }
    total = weighted_hook_total(scores)
    explanations = {
        "motif_clarity": f"Motif length {motif_len}, drop repeats {motif_matches}, intro similarity {intro_reference:.2f}, breakdown similarity {breakdown_reference:.2f}.",
        "rhythmic_identity": f"{unique_durations} duration values, {rhythm_repeats} repeated rhythm cells, density {density:.2f} notes/bar, syncopated attacks {syncopated}.",
        "hummability": f"Range {range_span} semitones, average interval {avg_interval:.2f}, stepwise ratio {stepwise_ratio:.2f}, large leaps {large_leaps}.",
        "chord_tone_targeting": f"Strong-beat chord-tone ratio {strong_ratio:.2f}, phrase-ending ratio {ending_ratio:.2f}, tension resolution {tension_resolution:.2f}.",
        "phrase_shape": f"High point {'late in drop' if high_point_late else 'not late'}, contour changes {contour_changes}, final note {'held' if final_long else 'short'}.",
        "repetition_variation": f"Exact repeats {exact_repetition}, related variations {related_variation}, section development references {section_development}.",
        "edm_trance_suitability": f"Drop density {drop_density:.2f} notes/bar, bar alignment {bar_aligned:.2f}, register {'suitable' if register_ok else 'less suitable'}.",
    }
    return {
        "total": total,
        **scores,
        "singability": hummability,
        "score_explanation": explanations,
        "score_confidence": "rule_based_structural_analysis",
    }


def passing_tone_between(first: int, second: int, key_label: str, mode: str, option_id: str):
    if first == second:
        return first
    midpoint = (first + second) // 2
    if option_id == "experimental_modern" and abs(first - second) <= 5:
        return clamp(midpoint, 48, 96)
    return nearest_in_scale(midpoint, scale_pitch_classes(key_label, mode), min(first, second) - 2, max(first, second) + 2)


def target_pool(chord: ChordIdea, key_label: str, mode: str, section: str, option_id: str):
    pitch_classes = scale_pitch_classes(key_label, mode)
    low, high = (60, 78) if section in ("intro", "breakdown") else (72, 91)
    if option_id == "emotional_cinematic":
        low -= 2
        high -= 2
    if option_id == "experimental_modern":
        low -= 5
        high += 2
    tones = [
        nearest_in_scale(chord.root + 12, pitch_classes, low, high),
        nearest_in_scale(chord.tones[1] + 12, pitch_classes, low, high),
        nearest_in_scale(chord.tones[2] + 12, pitch_classes, low, high),
        nearest_in_scale(chord.root + 24, pitch_classes, low, high),
    ]
    if option_id == "experimental_modern":
        tones.append(nearest_in_scale(chord.root + 13, pitch_classes, low, high))
    return tones


def build_section_events(section_idea: SectionIdea, key_label: str, mode: str, genre: str, option_id: str, generation_type: str, complexity: str, energy: str, hook_identity, include_arpeggio_pluck: bool = True):
    include_chords = generation_type in ("chords_only", "chords_melody", "full_section_sketch", "breakdown_progression_only")
    include_melody = generation_type in ("melody_only", "chords_melody", "full_section_sketch", "drop_hook_only")
    include_arp = include_chords and include_arpeggio_pluck
    if section_idea.name == "Drop":
        include_chords = generation_type != "melody_only"
        include_melody = generation_type != "chords_only" and generation_type != "breakdown_progression_only"
        include_arp = include_arp or (include_arpeggio_pluck and genre == "classic_2000s_trance")

    section = section_key(section_idea.name)
    section_idea.arpeggio_enabled = bool(include_arp)
    dur = chord_duration(section, complexity, energy)
    chord_cycle = section_idea.chords
    bars_per_chord = max(1, int(round(dur / 4.0)))
    for local_bar in range(section_idea.section_length_bars):
        chord = chord_cycle[(local_bar // bars_per_chord) % len(chord_cycle)]
        start = section_idea.start_tick + bar_tick(local_bar)
        if include_chords and local_bar % bars_per_chord == 0:
            hold_bars = min(bars_per_chord, section_idea.section_length_bars - local_bar)
            section_idea.chord_events.append({"start": start, "duration": BAR_TICKS * hold_bars, "notes": chord.voicing, "velocity": 58 if section == "intro" else 74 if section == "breakdown" else 94})
        if include_melody:
            section_idea.melody_events.extend(hook_events_for_bar(chord, hook_identity, key_label, mode, section, option_id, local_bar, start))
        if include_chords:
            bass_note = pitch_for_pc(chord.root % 12, chord.root - 24, 34, 52)
            section_idea.bass_events.append({"start": start, "duration": BAR_TICKS, "note": bass_note, "velocity": 82 if section == "drop" else 62})
        if include_arp and include_chords:
            for event in arp_events_for_bar(chord, start, section, option_id, complexity, genre):
                section_idea.arp_events.append(event)

    if section == "intro":
        section_idea.motif_summary = "Sparse teaser version of the central hook motif with space between notes."
    elif section == "breakdown":
        section_idea.motif_summary = "Emotional call-and-response version of the motif with longer phrase endings."
    else:
        section_idea.motif_summary = "Strongest hook statement: repeated motif, varied answer, lift, and resolution."


def arp_events_for_bar(chord: ChordIdea, start: int, section: str, option_id: str, complexity: str, genre: str):
    base = sorted(dict.fromkeys(chord.voicing[1:] if len(chord.voicing) > 3 else chord.voicing))
    if not base:
        return []
    if option_id == "classic_reliable":
        pattern_name = "up_down" if section == "drop" else "up"
    elif option_id == "emotional_cinematic":
        pattern_name = "octave_spread"
    else:
        pattern_name = "syncopated_pluck" if section == "drop" else "down"
    step = 0.25 if section == "drop" and (complexity in ("advanced", "experimental") or genre == "classic_2000s_trance") else 0.5
    if pattern_name == "down":
        order = list(reversed(base))
    elif pattern_name == "up_down":
        order = base + list(reversed(base[1:-1] or base))
    elif pattern_name == "octave_spread":
        order = []
        for note in base:
            order.extend([note, fit_pitch_preserve_pc(note + 12, 48, 96)])
    elif pattern_name == "syncopated_pluck":
        order = base[1:] + base[:1]
    else:
        order = base
    events = []
    positions = [round(i * step, 3) for i in range(int(4 / step))]
    if pattern_name == "syncopated_pluck":
        positions = [0.0, 0.75, 1.5, 2.0, 2.75, 3.5]
    for idx, beat in enumerate(positions):
        if section == "intro" and idx % 2 == 1:
            continue
        note = order[idx % len(order)]
        events.append({"start": start + tick(beat), "duration": tick(step * 0.72), "note": note, "velocity": 56 if section == "intro" else 70 if section == "breakdown" else 82, "pattern": pattern_name})
    return events


def energy_for_section(section: str, selected_energy: str):
    if section == "intro":
        return "low_atmospheric"
    if section == "breakdown":
        return "emotional" if selected_energy != "dark_tension" else "dark_tension"
    if section == "drop":
        return selected_energy if selected_energy in ("peak_time", "festival_drop", "dark_tension") else "peak_time"
    return selected_energy


def candidate_attempt_count(option_id: str, audition_depth: str):
    if audition_depth == "draft":
        return 3
    if audition_depth == "deep":
        return {"classic_reliable": 16, "emotional_cinematic": 24, "experimental_modern": 32}.get(option_id, 20)
    return {"classic_reliable": 8, "emotional_cinematic": 12, "experimental_modern": 16}.get(option_id, 8)


def hook_threshold(option_id: str):
    return {"classic_reliable": 75, "emotional_cinematic": 78, "experimental_modern": 70}.get(option_id, 75)


def default_arpeggio_enabled(generation_type: str, genre: str, complexity: str, raw_value=None):
    if raw_value is not None and str(raw_value).lower() in ("true", "1", "yes", "on"):
        return True
    if raw_value is not None and str(raw_value).lower() in ("false", "0", "no", "off"):
        return False
    if generation_type == "full_section_sketch":
        return True
    if genre in ("classic_2000s_trance", "progressive_trance"):
        return True
    if genre == "uplifting_trance" and complexity != "simple":
        return True
    return False


def arrangement_length_bars(controls):
    return sum(length for _name, length in section_plan(
        controls["generation_type"],
        controls["arrangement_section"],
        int(controls["bars"]),
        controls["length_mode"],
    ))


def hook_weaknesses(score_detail):
    weaknesses = []
    labels = {
        "motif_clarity": "motif could be clearer",
        "hummability": "hummability could be stronger",
        "rhythmic_identity": "rhythmic fingerprint could be more distinct",
        "chord_tone_targeting": "important notes could target chord tones more strongly",
        "phrase_shape": "phrase contour could have a clearer peak",
        "repetition_variation": "repetition/variation balance could improve",
        "edm_suitability": "drop payoff could be more EDM-focused",
    }
    for key, label in labels.items():
        if score_detail.get(key, 100) < 76:
            weaknesses.append(label)
    return weaknesses[:3]


def build_hook_metadata(option_id: str, hook_identity, score_detail, strongest_hook_bar: int):
    hummability = "Excellent" if score_detail["hummability"] >= 88 else "Strong" if score_detail["hummability"] >= 75 else "Developing"
    return {
        "core_motif_notes": hook_identity["notes"],
        "core_motif_rhythm": [beat for beat, _length in hook_identity["rhythm"]],
        "motif_interval_shape": hook_identity["motif_interval_shape"],
        "phrase_structure": hook_identity["structure"],
        "strongest_hook_bar": strongest_hook_bar,
        "payoff_note": hook_identity["payoff_note"],
        "emotional_target": hook_identity["emotional_target"],
        "hook_score": score_detail["total"],
        "melody_strength_score": score_detail["total"],
        "melody_description": hook_identity["summary"],
        "rhythmic_fingerprint": hook_identity["rhythmic_fingerprint"],
        "intro_teaser_description": "Sparse 2-4 note teaser using the same central motif with wide space.",
        "breakdown_development_description": "Emotional call-and-response development of the motif with longer phrase endings.",
        "drop_hook_description": "Primary repeated hook statement with controlled variation and a clearer payoff note.",
        "hummability_rating": hummability,
        "motif_clarity_score": score_detail["motif_clarity"],
        "rhythmic_identity_score": score_detail["rhythmic_identity"],
        "hummability_score": score_detail["hummability"],
        "singability_score": score_detail["hummability"],
        "chord_tone_targeting_score": score_detail["chord_tone_targeting"],
        "phrase_shape_score": score_detail["phrase_shape"],
        "repetition_variation_score": score_detail["repetition_variation"],
        "edm_trance_suitability_score": score_detail["edm_suitability"],
        "intentional_tension_notes": hook_identity["intentional_tension_notes"],
        "recommended_synth_role": hook_identity["recommended_synth_role"],
        "weaknesses": hook_weaknesses(score_detail),
        "score_explanation": score_detail.get("score_explanation", {}),
        "score_confidence": score_detail.get("score_confidence", "rule_based_structural_analysis"),
        "option_type": option_id,
    }


def build_melody_audit(option_id: str, hook_identity, score_detail, audition, selected_rank: int):
    return {
        "hook_score": score_detail["total"],
        "threshold": audition["hook_threshold"],
        "threshold_met": audition["threshold_met"],
        "candidates_tested": audition["candidates_generated"],
        "selected_candidate_rank": selected_rank,
        "motif_clarity_score": score_detail["motif_clarity"],
        "hummability_score": score_detail["hummability"],
        "rhythmic_identity_score": score_detail["rhythmic_identity"],
        "chord_tone_targeting_score": score_detail["chord_tone_targeting"],
        "phrase_shape_score": score_detail["phrase_shape"],
        "repetition_variation_score": score_detail["repetition_variation"],
        "edm_trance_suitability_score": score_detail["edm_suitability"],
        "selected_reason": audition["selected_reason"],
        "weaknesses": hook_weaknesses(score_detail),
        "recommended_use": hook_identity["recommended_synth_role"],
        "score_explanation": score_detail.get("score_explanation", {}),
        "score_confidence": score_detail.get("score_confidence", "rule_based_structural_analysis"),
    }


def build_core_hook_audit(hook_identity, score_detail):
    notes = hook_identity.get("midi_notes", [])
    intervals = [abs(notes[idx] - notes[idx - 1]) for idx in range(1, len(notes))]
    motif_len = len(notes)
    range_span = max(notes) - min(notes) if notes else 0
    avg_interval = sum(intervals) / max(1, len(intervals))
    large_leaps = sum(1 for interval in intervals if interval > 12)
    rhythm = hook_identity.get("rhythm", [])
    rhythm_values = [round(length, 2) for _beat, length in rhythm]
    start_values = [round(beat, 2) for beat, _length in rhythm]
    unique_rhythm = len(set(rhythm_values))
    has_payoff = bool(hook_identity.get("payoff_note")) and (rhythm[-1][1] >= 0.65 if rhythm else False)
    interval_score = clamp_score(92 - max(0, avg_interval - 5) * 5 - large_leaps * 12 - max(0, range_span - 14) * 1.5)
    hummability = clamp_score(70 + interval_score * 0.25 + (12 if 3 <= motif_len <= 6 else -10) + (8 if has_payoff else -6) - max(0, range_span - 15))
    rhythm_score = clamp_score(64 + unique_rhythm * 7 + len(set(start_values)) * 2 - (10 if unique_rhythm <= 1 else 0) - (8 if len(start_values) > 7 else 0))
    motif_length_score = clamp_score(96 if 3 <= motif_len <= 6 else 72 if motif_len == 7 else 55)
    payoff_score = clamp_score(84 + (10 if has_payoff else -18) + (6 if hook_identity.get("payoff_note") in hook_identity.get("notes", []) else 0))
    repeated_identity = clamp_score(score_detail.get("motif_clarity", 0) * 0.65 + score_detail.get("repetition_variation", 0) * 0.35)
    contour_score = clamp_score(76 + (8 if range_span >= 7 else -8) - large_leaps * 5 + (6 if notes and notes[0] == notes[-1] else 0))
    core_score = clamp_score(
        hummability * 0.30
        + motif_length_score * 0.15
        + interval_score * 0.15
        + rhythm_score * 0.15
        + payoff_score * 0.15
        + repeated_identity * 0.05
        + contour_score * 0.05
    )
    return {
        "core_hook_score": core_score,
        "core_hook_hummability": hummability,
        "core_hook_rhythm_score": rhythm_score,
        "core_hook_interval_score": interval_score,
        "core_hook_payoff_score": payoff_score,
        "core_hook_description": hook_identity.get("summary", ""),
        "can_hum_after_one_listen": hummability >= 82 and motif_len <= 6,
        "motif_length_score": motif_length_score,
        "repeated_identity_score": repeated_identity,
        "hook_contour_score": contour_score,
    }


def build_full_arrangement_melody_audit(sections, score_detail):
    section_map = {section.key: section for section in sections}
    intro = section_map.get("intro")
    breakdown = section_map.get("breakdown")
    drop = section_map.get("drop")
    all_events = [event for section in sections for event in section.melody_events]
    intro_count = len(intro.melody_events) if intro else 0
    breakdown_unique = len({event["note"] for event in breakdown.melody_events}) if breakdown else 0
    drop_count = len(drop.melody_events) if drop else 0
    total_bars = sum(section.section_length_bars for section in sections)
    density = len(all_events) / max(1, total_bars)
    pitches = [event["note"] for event in all_events]
    range_span = max(pitches) - min(pitches) if pitches else 0
    intro_teaser_score = clamp_score(86 - max(0, intro_count / max(1, intro.section_length_bars if intro else 1) - 2.5) * 12 if intro else 0)
    breakdown_development_score = clamp_score(64 + breakdown_unique * 5 + score_detail.get("phrase_shape", 0) * 0.15 if breakdown else 0)
    drop_payoff_score = clamp_score(58 + min(24, drop_count / max(1, drop.section_length_bars if drop else 1) * 3) + score_detail.get("edm_suitability", 0) * 0.20 if drop else 0)
    section_densities = [
        len(section.melody_events) / max(1, section.section_length_bars)
        for section in sections
    ]
    section_contrast_score = clamp_score(68 + (max(section_densities) - min(section_densities)) * 8 if section_densities else 0)
    long_form_range_score = clamp_score(92 - max(0, range_span - 24) * 2 - (8 if density > 6 else 0))
    arrangement_score = clamp_score(
        intro_teaser_score * 0.18
        + breakdown_development_score * 0.20
        + drop_payoff_score * 0.24
        + section_contrast_score * 0.18
        + long_form_range_score * 0.20
    )
    return {
        "arrangement_melody_score": arrangement_score,
        "intro_teaser_score": intro_teaser_score,
        "breakdown_development_score": breakdown_development_score,
        "drop_payoff_score": drop_payoff_score,
        "section_contrast_score": section_contrast_score,
        "long_form_range_score": long_form_range_score,
    }


def build_sections_for_hook(profile, controls, hook_identity, rng: random.Random):
    bars = int(controls["bars"])
    plan = section_plan(controls["generation_type"], controls["arrangement_section"], bars, controls["length_mode"])
    current_bar = 0
    sections = []
    for name, section_bars in plan:
        skey = section_key(name)
        section_energy = energy_for_section(skey, controls["energy"])
        seed_value = int(controls.get("variation_seed", 0) or 0)
        regenerate_mode = controls.get("regenerate_mode", "full_option")
        chord_variant = 0 if regenerate_mode == "melody_only" or seed_value == 0 else (seed_value + current_bar + len(profile["id"])) % 3
        chords = build_chords(
            controls["key"],
            controls["scale"],
            controls["genre"],
            skey,
            profile["id"],
            controls["complexity"],
            section_energy,
            rng,
            chord_variant,
        )
        idea = SectionIdea(
            key=skey,
            name=name,
            start_bar=current_bar,
            bars=max(1, section_bars),
            energy=ENERGY_LABELS.get(section_energy, section_energy),
            chords=chords,
            section_length_bars=max(1, section_bars),
            local_start_bar=0,
            local_end_bar=max(1, section_bars),
        )
        build_section_events(
            idea,
            controls["key"],
            controls["scale"],
            controls["genre"],
            profile["id"],
            controls["generation_type"],
            controls["complexity"],
            section_energy,
            hook_identity,
            controls["include_arpeggio_pluck"],
        )
        sections.append(idea)
        current_bar += max(1, section_bars)
    return sections


def reason_for_candidate(score_detail, threshold_met: bool):
    strengths = []
    if score_detail["motif_clarity"] >= 78:
        strengths.append("strong motif clarity")
    if score_detail["rhythmic_identity"] >= 75:
        strengths.append("clear rhythmic identity")
    if score_detail["hummability"] >= 78:
        strengths.append("high hummability")
    if score_detail["phrase_shape"] >= 76:
        strengths.append("clear phrase contour")
    if score_detail["repetition_variation"] >= 75:
        strengths.append("good repetition with variation")
    if not strengths:
        strengths.append("best available balance across hook categories")
    prefix = "Selected because: " if threshold_met else "Best available candidate, but below preferred hook threshold. Selected because: "
    return prefix + ", ".join(strengths) + "."


def generate_best_hook(profile, controls, rng: random.Random):
    attempts = candidate_attempt_count(profile["id"], controls["audition_depth"])
    threshold = hook_threshold(profile["id"])
    candidates = []
    seed_offset = int(controls.get("variation_seed", 0) or 0) % 997
    for candidate_index in range(attempts):
        candidate_rng = random.Random(f"{profile['id']}|{candidate_index}|{seed_offset}|{controls['key']}|{controls['scale']}|{controls['genre']}")
        hook_identity = create_hook_identity(controls["key"], controls["scale"], profile["id"], controls["genre"], candidate_index + seed_offset, candidate_rng)
        sections = build_sections_for_hook(profile, controls, hook_identity, candidate_rng)
        score_detail = score_hook_identity(profile["id"], sections, hook_identity)
        candidates.append({
            "hook_identity": hook_identity,
            "sections": sections,
            "score_detail": score_detail,
            "candidate_index": candidate_index,
        })
    candidates.sort(key=lambda item: item["score_detail"]["total"], reverse=True)
    winner = next((candidate for candidate in candidates if candidate["score_detail"]["total"] >= threshold), candidates[0])
    threshold_met = winner["score_detail"]["total"] >= threshold
    top_summaries = [
        {
            "candidate": item["candidate_index"] + 1,
            "score": item["score_detail"]["total"],
            "motif_notes": item["hook_identity"]["notes"],
            "summary": item["hook_identity"]["summary"],
            "rejection_reason": "" if item is winner else "lower weighted hook score than selected candidate",
        }
        for item in candidates[:3]
    ]
    return winner, {
        "candidates_generated": attempts,
        "candidates_rejected": max(0, attempts - 1),
        "hook_threshold": threshold,
        "threshold_met": threshold_met,
        "selected_reason": reason_for_candidate(winner["score_detail"], threshold_met),
        "top_candidate_summaries": top_summaries,
        "selected_candidate_rank": candidates.index(winner) + 1,
    }


def generate_option(profile, controls, rng: random.Random) -> GeneratedOption:
    winner, audition = generate_best_hook(profile, controls, rng)
    hook_identity = winner["hook_identity"]
    sections = winner["sections"]
    strongest_hook_bar = next((section.start_bar + 1 for section in sections if section.key == "drop"), sections[-1].start_bar + 1 if sections else 1)
    score_detail = winner["score_detail"]
    hook_metadata = build_hook_metadata(profile["id"], hook_identity, score_detail, strongest_hook_bar)
    melody_audit = build_melody_audit(profile["id"], hook_identity, score_detail, audition, audition["selected_candidate_rank"])
    core_hook_audit = build_core_hook_audit(hook_identity, score_detail)
    full_arrangement_melody_audit = build_full_arrangement_melody_audit(sections, score_detail)
    return GeneratedOption(
        id=profile["id"],
        name=profile["name"],
        purpose=profile["purpose"],
        risk=profile["risk"],
        genre=GENRE_LABELS.get(controls["genre"], controls["genre"]),
        key=controls["key"],
        scale=MODE_LABELS.get(controls["scale"], controls["scale"]),
        scale_id=controls["scale"],
        bpm=int(controls["bpm"]),
        generation_type=GENERATION_LABELS.get(controls["generation_type"], controls["generation_type"]),
        sections=sections,
        energy_description=ENERGY_LABELS.get(controls["energy"], controls["energy"]),
        creative_risk_description=RISK_LABELS.get(controls["creative_risk"], controls["creative_risk"]),
        hook_summary=hook_identity["summary"],
        core_motif_notes=hook_identity["notes"],
        core_motif_rhythm=[beat for beat, _length in hook_identity["rhythm"]],
        phrase_structure=hook_identity["structure"],
        strongest_hook_bar=strongest_hook_bar,
        melody_strength_score=score_detail["total"],
        hook_subscores=score_detail,
        candidates_generated=audition["candidates_generated"],
        candidates_rejected=audition["candidates_rejected"],
        hook_threshold=audition["hook_threshold"],
        threshold_met=audition["threshold_met"],
        selected_reason=audition["selected_reason"],
        hook_metadata=hook_metadata,
        melody_audit=melody_audit,
        core_hook_audit=core_hook_audit,
        full_arrangement_melody_audit=full_arrangement_melody_audit,
        top_candidate_summaries=audition["top_candidate_summaries"],
    )


def normalize_controls(raw):
    parsed = parse_key(raw.get("key", "F# minor"))
    scale = raw.get("scale", "natural_minor")
    if scale == "major" and parsed.quality == "minor":
        scale = "natural_minor"
    bars = int(raw.get("bars", 16))
    if bars not in (4, 8, 16, 32):
        bars = 16
    generation_type = raw.get("generation_type", "full_section_sketch")
    genre = raw.get("genre", "uplifting_trance")
    complexity = raw.get("complexity", "medium")
    return {
        "key": parsed.label,
        "scale": scale,
        "bpm": clamp(int(raw.get("bpm", 138)), 120, 150),
        "genre": genre,
        "generation_type": generation_type,
        "arrangement_section": raw.get("arrangement_section", "full"),
        "bars": bars,
        "complexity": complexity,
        "energy": raw.get("energy", "emotional"),
        "creative_risk": raw.get("creative_risk", "club_ready"),
        "length_mode": raw.get("length_mode", "per_section"),
        "include_arpeggio_pluck": default_arpeggio_enabled(generation_type, genre, complexity, raw.get("include_arpeggio_pluck")),
        "audition_depth": raw.get("hook_search_depth", raw.get("audition_depth", "balanced")),
        "regenerate_mode": raw.get("regenerate_mode", "full_option"),
        "variation_seed": raw.get("variation_seed", 0),
    }


def generate_edm_ideas(raw_controls) -> GenerationResult:
    controls = normalize_controls(raw_controls)
    seed_text = "|".join(str(controls[key]) for key in sorted(controls))
    rng = random.Random(seed_text)
    options = [generate_option(profile, controls, rng) for profile in OPTION_PROFILES]
    return GenerationResult(
        bpm=controls["bpm"],
        key=controls["key"],
        scale=MODE_LABELS.get(controls["scale"], controls["scale"]),
        scale_id=controls["scale"],
        genre=GENRE_LABELS.get(controls["genre"], controls["genre"]),
        generation_type=GENERATION_LABELS.get(controls["generation_type"], controls["generation_type"]),
        arrangement_bars=arrangement_length_bars(controls),
        length_mode=controls["length_mode"],
        options=options,
    )


def option_preview_dict(option: GeneratedOption):
    return {
        "id": option.id,
        "name": option.name,
        "key": option.key,
        "scale": option.scale,
        "bpm": option.bpm,
        "genre": option.genre,
        "generation_type": option.generation_type,
        "hook_summary": option.hook_summary,
        "core_motif_notes": option.core_motif_notes,
        "core_motif_rhythm": option.core_motif_rhythm,
        "phrase_structure": option.phrase_structure,
        "strongest_hook_bar": option.strongest_hook_bar,
        "melody_strength_score": option.melody_strength_score,
        "hook_subscores": option.hook_subscores,
        "candidates_generated": option.candidates_generated,
        "candidates_rejected": option.candidates_rejected,
        "hook_threshold": option.hook_threshold,
        "threshold_met": option.threshold_met,
        "selected_reason": option.selected_reason,
        "hook_metadata": option.hook_metadata,
        "melody_audit": option.melody_audit,
        "core_hook_audit": option.core_hook_audit,
        "full_arrangement_melody_audit": option.full_arrangement_melody_audit,
        "rhythmic_fingerprint": option.hook_metadata["rhythmic_fingerprint"],
        "intentional_tension_notes": option.hook_metadata["intentional_tension_notes"],
        "top_candidate_summaries": option.top_candidate_summaries,
        "sections": [
            {
                "name": section.name,
                "bars": f"{section.arrangement_start_bar + 1}-{section.arrangement_end_bar}",
                "section_length_bars": section.section_length_bars,
                "local_bar_range": f"{section.local_start_bar + 1}-{section.local_end_bar}",
                "arrangement_bar_range": f"{section.arrangement_start_bar + 1}-{section.arrangement_end_bar}",
                "start_tick": section.start_tick,
                "end_tick": section.end_tick,
                "arpeggio_enabled": section.arpeggio_enabled,
                "energy": section.energy,
                "chords": section.progression_symbols,
                "roman": [chord.roman for chord in section.chords],
                "notes": [", ".join(midi_name(note) for note in chord.voicing) for chord in section.chords],
                "voicing_type": [chord.voicing_type for chord in section.chords],
                "omitted_tones": [chord.omitted_tones for chord in section.chords],
                "motif_summary": section.motif_summary,
            }
            for section in option.sections
        ],
        "energy_description": option.energy_description,
        "creative_risk_description": option.creative_risk_description,
    }
