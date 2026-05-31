from dataclasses import dataclass, field
import random

from .music_theory import (
    MODE_LABELS,
    clamp,
    chord_symbol,
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
    voicing: list[int]
    symbol: str
    roman: str


@dataclass
class SectionIdea:
    key: str
    name: str
    start_bar: int
    bars: int
    energy: str
    chords: list[ChordIdea]
    chord_events: list[dict] = field(default_factory=list)
    melody_events: list[dict] = field(default_factory=list)
    bass_events: list[dict] = field(default_factory=list)
    arp_events: list[dict] = field(default_factory=list)
    motif_summary: str = ""

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
    bpm: int
    generation_type: str
    sections: list[SectionIdea]
    energy_description: str
    creative_risk_description: str


@dataclass
class GenerationResult:
    bpm: int
    key: str
    scale: str
    genre: str
    generation_type: str
    options: list[GeneratedOption]


def tick(beats: float) -> int:
    return int(round(beats * TICKS))


def bar_tick(bar_index: int) -> int:
    return bar_index * BAR_TICKS


def section_plan(generation_type: str, arrangement_section: str, bars: int):
    if generation_type == "full_section_sketch" or arrangement_section == "full":
        each = max(4, bars // 3)
        return [("Intro", each), ("Verse / Breakdown", each), ("Drop", bars - each * 2)]
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
    third = scale_note(key_label, mode, degree + 2, 3 if degree + 2 > 7 else 4)
    fifth = scale_note(key_label, mode, degree + 4, 3 if degree + 4 > 7 else 4)
    tones = sorted([root, third, fifth])
    semis = sorted([(tone - tones[0]) % 12 for tone in tones])
    quality = "minor" if 3 in semis and 7 in semis else "dim" if 3 in semis and 6 in semis else "major"

    if option_id == "emotional_cinematic" and section in ("breakdown", "intro"):
        quality = "add9" if quality in ("minor", "major") and degree in (1, 6) else "sus2" if degree in (4, 7) else quality
    elif option_id == "experimental_modern":
        if degree == 2 and genre in ("dark_emotional_trance", "experimental_trance_edm"):
            quality = "sus4"
        elif degree in (1, 6):
            quality = "m9" if quality == "minor" else "maj7"
        elif section == "drop" and degree in (5, 7):
            quality = "power"

    return ChordIdea(
        degree=degree,
        root=tones[0],
        quality=quality,
        tones=tones,
        voicing=[],
        symbol=chord_symbol(tones[0], quality),
        roman=ROMAN.get(degree, str(degree)),
    )


def chord_extension_notes(chord: ChordIdea, key_label: str, mode: str, pitch_classes, register_low: int, register_high: int):
    root = nearest_in_scale(chord.root, pitch_classes, register_low, register_high)
    third = nearest_in_scale(chord.tones[1], pitch_classes, register_low, register_high)
    fifth = nearest_in_scale(chord.tones[2], pitch_classes, register_low, register_high)
    second = nearest_in_scale(chord.root + 2, pitch_classes, register_low, register_high)
    fourth = nearest_in_scale(chord.root + 5, pitch_classes, register_low, register_high)
    seventh = nearest_in_scale(chord.root + 10, pitch_classes, register_low, register_high)
    ninth = nearest_in_scale(chord.root + 14, pitch_classes, register_low, register_high)
    if chord.quality == "sus2":
        return [root, second, fifth]
    if chord.quality == "sus4":
        return [root, fourth, fifth]
    if chord.quality == "add9":
        return [root, third, fifth, ninth]
    if chord.quality == "m7":
        return [root, third, fifth, seventh]
    if chord.quality == "m9":
        return [root, third, fifth, seventh, ninth]
    if chord.quality == "maj7":
        major_seventh = nearest_in_scale(chord.root + 11, pitch_classes, register_low, register_high)
        return [root, third, fifth, major_seventh]
    if chord.quality == "power":
        return [root, fifth, root + 12 if root + 12 <= register_high else root]
    return [root, third, fifth]


def voice_chord(chord: ChordIdea, key_label: str, mode: str, section: str, option_id: str, energy: str):
    pitch_classes = scale_pitch_classes(key_label, mode)
    root_low = nearest_in_scale(chord.root - 12, pitch_classes, 36, 58)
    base = chord_extension_notes(chord, key_label, mode, pitch_classes, 52, 84)
    if section == "intro":
        notes = [root_low, base[0], base[-1]]
        if option_id != "classic_reliable":
            notes.append(nearest_in_scale(chord.root + 14, pitch_classes, 64, 86))
    elif section == "breakdown":
        notes = [root_low] + base
        if option_id in ("emotional_cinematic", "experimental_modern"):
            notes.append(nearest_in_scale(chord.tones[1] + 12, pitch_classes, 67, 88))
    elif section == "drop":
        notes = [root_low, base[0], base[2] if len(base) > 2 else base[-1], nearest_in_scale(chord.root + 12, pitch_classes, 64, 88)]
        if energy in ("peak_time", "festival_drop"):
            notes.append(nearest_in_scale(chord.tones[1] + 12, pitch_classes, 67, 91))
    else:
        notes = [root_low] + base[:3]
    return sorted(dict.fromkeys(clamp(note, 36, 96) for note in notes))


def select_pattern(genre: str, section: str, option_id: str, rng: random.Random):
    patterns = PROGRESSION_PATTERNS.get(genre, PROGRESSION_PATTERNS["uplifting_trance"]).get(section)
    if not patterns:
        patterns = PROGRESSION_PATTERNS.get(genre, PROGRESSION_PATTERNS["uplifting_trance"])["breakdown"]
    index = 0 if option_id == "classic_reliable" else 1 if option_id == "emotional_cinematic" and len(patterns) > 1 else len(patterns) - 1
    chosen = list(patterns[index])
    if option_id == "experimental_modern":
        if genre in ("experimental_trance_edm", "dark_emotional_trance"):
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


def build_chords(key_label: str, mode: str, genre: str, section: str, option_id: str, complexity: str, energy: str, rng):
    pattern = select_pattern(genre, section, option_id, rng)
    chords = [degree_triad(key_label, mode, degree, option_id, section, genre) for degree in pattern]
    for chord in chords:
        chord.voicing = voice_chord(chord, key_label, mode, section, option_id, energy)
    return chords


def melody_pattern(section: str, option_id: str, complexity: str, genre: str):
    if section == "intro":
        return [(2.0, 0.5), (3.0, 0.75)] if complexity != "simple" else [(3.0, 0.75)]
    if section == "breakdown":
        if option_id == "emotional_cinematic":
            return [(0.5, 1.0), (2.0, 0.75), (3.0, 1.0)]
        if option_id == "experimental_modern":
            return [(0.75, 0.5), (1.75, 0.75), (3.25, 0.5)]
        return [(0.0, 0.75), (1.5, 0.75), (2.75, 1.0)]
    if genre == "classic_2000s_trance" or complexity == "advanced":
        return [(0.0, 0.25), (0.5, 0.25), (1.0, 0.25), (1.5, 0.25), (2.0, 0.5), (3.0, 0.75)]
    if option_id == "experimental_modern":
        return [(0.0, 0.5), (0.75, 0.5), (1.5, 0.75), (2.75, 0.5), (3.5, 0.5)]
    return [(0.0, 0.5), (1.0, 0.5), (2.0, 0.75), (3.0, 0.75)]


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


def build_section_events(section_idea: SectionIdea, key_label: str, mode: str, genre: str, option_id: str, generation_type: str, complexity: str, energy: str):
    include_chords = generation_type in ("chords_only", "chords_melody", "full_section_sketch", "breakdown_progression_only")
    include_melody = generation_type in ("melody_only", "chords_melody", "full_section_sketch", "drop_hook_only")
    include_arp = complexity in ("advanced", "experimental") or genre in ("classic_2000s_trance", "progressive_trance")
    if section_idea.name == "Drop":
        include_chords = generation_type != "melody_only"
        include_melody = generation_type != "chords_only" and generation_type != "breakdown_progression_only"
        include_arp = include_arp or genre == "classic_2000s_trance"

    section = section_key(section_idea.name)
    dur = chord_duration(section, complexity, energy)
    chord_cycle = section_idea.chords
    bars_per_chord = max(1, int(round(dur / 4.0)))
    for local_bar in range(section_idea.bars):
        chord = chord_cycle[(local_bar // bars_per_chord) % len(chord_cycle)]
        start = bar_tick(section_idea.start_bar + local_bar)
        if include_chords and local_bar % bars_per_chord == 0:
            hold_bars = min(bars_per_chord, section_idea.bars - local_bar)
            section_idea.chord_events.append({"start": start, "duration": BAR_TICKS * hold_bars, "notes": chord.voicing, "velocity": 58 if section == "intro" else 74 if section == "breakdown" else 94})
        if include_melody:
            pool = target_pool(chord, key_label, mode, section, option_id)
            pattern = melody_pattern(section, option_id, complexity, genre)
            rotated = rotate(pool, local_bar + (1 if option_id == "emotional_cinematic" else 2 if option_id == "experimental_modern" else 0))
            for idx, (beat, length) in enumerate(pattern):
                if section == "intro" and local_bar % 2 == 1:
                    continue
                pitch = rotated[idx % len(rotated)]
                if option_id == "experimental_modern" and idx == len(pattern) - 1 and local_bar % 4 == 3:
                    pitch = nearest_in_scale(pitch + 2, scale_pitch_classes(key_label, mode), 58, 94)
                section_idea.melody_events.append({"start": start + tick(beat), "duration": tick(length), "note": pitch, "velocity": 72 if section == "intro" else 88 if section == "breakdown" else 104})
        if include_chords:
            bass_note = nearest_in_scale(chord.root - 24, scale_pitch_classes(key_label, mode), 34, 52)
            section_idea.bass_events.append({"start": start, "duration": tick(0.5 if section == "drop" else 1.0), "note": bass_note, "velocity": 82 if section == "drop" else 62})
        if include_arp and include_chords:
            arp_notes = chord.voicing[-3:]
            step = 0.25 if section == "drop" and complexity in ("advanced", "experimental") else 0.5
            for idx in range(int(4 / step)):
                if section == "intro" and idx % 2:
                    continue
                note = arp_notes[idx % len(arp_notes)]
                section_idea.arp_events.append({"start": start + tick(idx * step), "duration": tick(step * 0.78), "note": note, "velocity": 58 if section == "intro" else 72})

    if section == "intro":
        section_idea.motif_summary = "Sparse pad/pluck motif, root-focused and spacious."
    elif section == "breakdown":
        section_idea.motif_summary = "Expressive phrase with suspensions, inversions, and longer endings."
    else:
        section_idea.motif_summary = "Drop-ready hook with repetition, chord-tone targets, and stronger resolution."


def energy_for_section(section: str, selected_energy: str):
    if section == "intro":
        return "low_atmospheric"
    if section == "breakdown":
        return "emotional" if selected_energy != "dark_tension" else "dark_tension"
    if section == "drop":
        return selected_energy if selected_energy in ("peak_time", "festival_drop", "dark_tension") else "peak_time"
    return selected_energy


def generate_option(profile, controls, rng: random.Random) -> GeneratedOption:
    bars = int(controls["bars"])
    plan = section_plan(controls["generation_type"], controls["arrangement_section"], bars)
    current_bar = 0
    sections = []
    for name, section_bars in plan:
        skey = section_key(name)
        section_energy = energy_for_section(skey, controls["energy"])
        chords = build_chords(
            controls["key"],
            controls["scale"],
            controls["genre"],
            skey,
            profile["id"],
            controls["complexity"],
            section_energy,
            rng,
        )
        idea = SectionIdea(
            key=skey,
            name=name,
            start_bar=current_bar,
            bars=max(1, section_bars),
            energy=ENERGY_LABELS.get(section_energy, section_energy),
            chords=chords,
        )
        build_section_events(idea, controls["key"], controls["scale"], controls["genre"], profile["id"], controls["generation_type"], controls["complexity"], section_energy)
        sections.append(idea)
        current_bar += max(1, section_bars)
    return GeneratedOption(
        id=profile["id"],
        name=profile["name"],
        purpose=profile["purpose"],
        risk=profile["risk"],
        genre=GENRE_LABELS.get(controls["genre"], controls["genre"]),
        key=controls["key"],
        scale=MODE_LABELS.get(controls["scale"], controls["scale"]),
        bpm=int(controls["bpm"]),
        generation_type=GENERATION_LABELS.get(controls["generation_type"], controls["generation_type"]),
        sections=sections,
        energy_description=ENERGY_LABELS.get(controls["energy"], controls["energy"]),
        creative_risk_description=RISK_LABELS.get(controls["creative_risk"], controls["creative_risk"]),
    )


def normalize_controls(raw):
    parsed = parse_key(raw.get("key", "F# minor"))
    scale = raw.get("scale", "natural_minor")
    if scale == "major" and parsed.quality == "minor":
        scale = "natural_minor"
    bars = int(raw.get("bars", 16))
    if bars not in (4, 8, 16, 32):
        bars = 16
    return {
        "key": parsed.label,
        "scale": scale,
        "bpm": clamp(int(raw.get("bpm", 138)), 120, 150),
        "genre": raw.get("genre", "uplifting_trance"),
        "generation_type": raw.get("generation_type", "full_section_sketch"),
        "arrangement_section": raw.get("arrangement_section", "full"),
        "bars": bars,
        "complexity": raw.get("complexity", "medium"),
        "energy": raw.get("energy", "emotional"),
        "creative_risk": raw.get("creative_risk", "club_ready"),
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
        genre=GENRE_LABELS.get(controls["genre"], controls["genre"]),
        generation_type=GENERATION_LABELS.get(controls["generation_type"], controls["generation_type"]),
        options=options,
    )


def option_preview_dict(option: GeneratedOption):
    return {
        "name": option.name,
        "key": option.key,
        "scale": option.scale,
        "bpm": option.bpm,
        "genre": option.genre,
        "generation_type": option.generation_type,
        "sections": [
            {
                "name": section.name,
                "bars": f"{section.start_bar + 1}-{section.start_bar + section.bars}",
                "energy": section.energy,
                "chords": section.progression_symbols,
                "roman": [chord.roman for chord in section.chords],
                "notes": [", ".join(midi_name(note) for note in chord.voicing) for chord in section.chords],
                "motif_summary": section.motif_summary,
            }
            for section in option.sections
        ],
        "energy_description": option.energy_description,
        "creative_risk_description": option.creative_risk_description,
    }

