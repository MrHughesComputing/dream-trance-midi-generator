from pathlib import Path
from time import time_ns
from typing import Annotated, Literal
from uuid import uuid4
import base64
import json
import copy
import random
import shutil
import zipfile
from fastapi import FastAPI, Form
from fastapi.responses import FileResponse, HTMLResponse
from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo
from starlette.background import BackgroundTask
from lib.edm_generator import (
    COMPLEXITY_LABELS,
    ENERGY_LABELS,
    GENRE_LABELS,
    GENERATION_LABELS,
    RISK_LABELS,
    SECTION_LABELS,
    generate_edm_ideas,
    option_preview_dict,
)
from lib.midi_export import export_idea_pack
from lib.music_theory import KEY_OPTIONS as EDM_KEY_OPTIONS
from lib.music_theory import MODE_LABELS

BASE_DIR = Path(__file__).resolve().parent
EXPORTS_DIR = BASE_DIR / "exports"
APP_VERSION = "V11.5"
ADVISOR_UI_VERSION = "V9.8"
HOOK_MODE = True
TRACK_IDENTITY_MODE = "auto"
RECENT_TRACK_IDENTITIES = []
RECENT_IDENTITY_VARIATIONS = {}
LATEST_ADVISOR_DIR = EXPORTS_DIR / "_latest_advisor"
GENERATED_PACKS = {}
DEFAULT_GUI_VALUES = {
    "bpm": 138,
    "key": "F#",
    "progression": "uplifting",
    "arrangement": "extended",
    "density": "medium",
    "variation": "medium",
    "energy_bias": "medium",
    "track_identity": TRACK_IDENTITY_MODE,
}
EXPORT_VERSION = APP_VERSION.lower().replace(".", "_")

app = FastAPI(title=f"Dream Trance Generator {APP_VERSION}")

TICKS = 480
BAR_TICKS = TICKS * 4


def export_slug(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_")

KEY_OPTIONS = ["E", "F", "F#", "G", "G#", "A", "A#", "C", "D"]
PROGRESSIONS = {
    "uplifting": [1, 6, 3, 7],
    "classic": [1, 4, 6, 7],
    "festival": [6, 3, 7, 1],
    "hopeful": [1, 5, 6, 4],
    "progressive": [6, 4, 1, 5],
}

TRACK_IDENTITY_PROFILES = {
    "ANTHEMIC_UPLIFTING": {
        "identity_name": "Anthemic Uplifting",
        "description": "Classic emotional peak-time uplifting trance with a hands-in-the-air hook.",
        "emotional_target": "Hopeful, euphoric, hands in the air",
        "chord_progressions": ["uplifting", "festival", "classic"],
        "preferred_keys": ["F#", "G", "A", "E"],
        "intro_behavior": "pad_supersaw_tease",
        "bass_behavior": "offbeat_plus_rolling",
        "lead_behavior": "simple_sustained_hook",
        "hook_shape": "long_response_long_peak",
        "supersaw_behavior": "wide_bright_dominant",
        "arp_behavior": "supportive_moderate",
        "pluck_behavior": "restrained_tease",
        "breakdown_behavior": "emotional_piano_strings",
        "drum_build_behavior": "classic_8_bar_roll",
        "drop_behavior": "euphoric_supersaw_release",
        "density_targets": {"lead_max": 2.0, "supersaw_min": 5.0, "arp_max": 3.0, "bass_min": 2.0},
        "validation_targets": {"lead_avg_len_min": 0.9, "intro_signature": "pad_or_supersaw", "breakdown_focus": "piano_strings"},
        "blueprint_overrides": {
            "bass_style": "rolling_drive", "arp_style": "uplift_drive", "drum_style": "driving", "breakdown_style": "piano_led",
            "lead_archetype": "anthemic", "supersaw_identity": "wall_stack", "drop_arrival_style": "hook_first",
            "breakdown_narrative": "piano_confession", "energy_profile": "late_peak", "opening_scene": "pad_seed",
            "archetype_arp_grammar": "stream", "archetype_pluck_grammar": "foreshadow", "drop_layer_budget": 6,
        },
    },
    "EMOTIONAL_VOCAL_TRANCE": {
        "identity_name": "Emotional Vocal Trance",
        "description": "A longing vocal-friendly trance identity with more space for topline phrases.",
        "emotional_target": "Longing, romantic, vulnerable",
        "chord_progressions": ["festival", "uplifting", "hopeful"],
        "preferred_keys": ["F#", "G#", "A", "E"],
        "intro_behavior": "vocal_or_piano_hint",
        "bass_behavior": "soft_offbeat",
        "lead_behavior": "sparse_sustained_support",
        "hook_shape": "long_space_answer",
        "supersaw_behavior": "warm_supportive_wide",
        "arp_behavior": "minimal_gentle_motion",
        "pluck_behavior": "mostly_off",
        "breakdown_behavior": "piano_vocal_space",
        "drum_build_behavior": "smooth_4_to_8_bar_roll",
        "drop_behavior": "emotional_supportive_release",
        "density_targets": {"lead_max": 2.0, "supersaw_max": 8.0, "arp_max": 3.5, "bass_max": 4.5},
        "validation_targets": {"lead_avg_len_min": 1.0, "intro_signature": "vocal_or_piano", "breakdown_focus": "vocal_piano"},
        "blueprint_overrides": {
            "bass_style": "classic_offbeat", "arp_style": "gated_8th", "drum_style": "standard", "breakdown_style": "vocal_focus",
            "lead_archetype": "yearning", "vocal_archetype": "held_emotive", "supersaw_identity": "bloom_stack",
            "drop_arrival_style": "glide_in", "breakdown_narrative": "vocal_spotlight", "energy_profile": "gradual_rise",
            "opening_scene": "hook_tease", "archetype_topline_density": "vocal_heavy", "archetype_arp_grammar": "breath",
            "archetype_pluck_grammar": "drop_gap", "drop_layer_budget": 4,
        },
    },
    "PROGRESSIVE_TRANCE": {
        "identity_name": "Progressive Trance",
        "description": "Groove-led, hypnotic trance with a slower emotional build.",
        "emotional_target": "Deep, rolling, atmospheric",
        "chord_progressions": ["progressive", "festival", "classic"],
        "preferred_keys": ["E", "F#", "G", "A"],
        "intro_behavior": "groove_pad_atmosphere",
        "bass_behavior": "rolling_syncopated_groove",
        "lead_behavior": "late_repetitive_motif",
        "hook_shape": "repeated_motif_low_peak",
        "supersaw_behavior": "smooth_warm_less_dense",
        "arp_behavior": "active_rhythmic_motion",
        "pluck_behavior": "subtle_motion",
        "breakdown_behavior": "atmospheric_pad_led",
        "drum_build_behavior": "long_subtle_roll",
        "drop_behavior": "groove_first_melody_second",
        "density_targets": {"lead_max": 2.2, "supersaw_max": 8.0, "arp_min": 1.0, "rolling_bass_min": 2.0},
        "validation_targets": {"lead_avg_len_min": 0.7, "intro_signature": "groove_or_pad", "breakdown_focus": "pad"},
        "blueprint_overrides": {
            "bass_style": "hybrid", "arp_style": "gated_8th", "drum_style": "minimal", "breakdown_style": "pad_space",
            "lead_archetype": "yearning", "supersaw_identity": "bloom_stack", "drop_arrival_style": "glide_in",
            "breakdown_narrative": "space_then_lift", "energy_profile": "gradual_rise", "opening_scene": "bass_tease",
            "archetype_arp_grammar": "stream", "archetype_pluck_grammar": "pulse", "drop_layer_budget": 4,
        },
    },
    "TECH_UPLIFT": {
        "identity_name": "Tech Uplift",
        "description": "Sharper, darker, club-focused uplifting trance with aggressive build tension.",
        "emotional_target": "Tense, energetic, club-focused",
        "chord_progressions": ["progressive", "festival", "hopeful"],
        "preferred_keys": ["F", "F#", "G", "G#"],
        "intro_behavior": "kick_bass_percussion_tension",
        "bass_behavior": "aggressive_rolling",
        "lead_behavior": "short_rhythmic_hook",
        "hook_shape": "short_sharp_response",
        "supersaw_behavior": "tight_mid_forward",
        "arp_behavior": "prominent_percussive",
        "pluck_behavior": "active_rhythmic",
        "breakdown_behavior": "short_tension_texture",
        "drum_build_behavior": "aggressive_dense_fill",
        "drop_behavior": "impact_drive_over_emotion",
        "density_targets": {"lead_max": 2.5, "supersaw_max": 4.5, "arp_min": 3.0, "bass_min": 3.0},
        "validation_targets": {"lead_avg_len_max": 1.1, "intro_signature": "drums_or_bass", "breakdown_focus": "tension"},
        "blueprint_overrides": {
            "bass_style": "rolling_drive", "arp_style": "rolling_16th", "drum_style": "festival", "breakdown_style": "arp_texture",
            "lead_archetype": "driving", "supersaw_identity": "pulse_stack", "drop_arrival_style": "slam",
            "breakdown_narrative": "space_then_lift", "energy_profile": "early_energy", "opening_scene": "drum_tease",
            "archetype_arp_grammar": "lift_rush", "archetype_pluck_grammar": "pulse", "drop_layer_budget": 5,
        },
    },
    "ORCHESTRAL_UPLIFTING": {
        "identity_name": "Orchestral Uplifting",
        "description": "Cinematic trance where piano and strings carry the emotional scale.",
        "emotional_target": "Epic, cinematic, emotional",
        "chord_progressions": ["festival", "progressive", "uplifting"],
        "preferred_keys": ["F#", "G", "A", "C"],
        "intro_behavior": "piano_strings_teaser",
        "bass_behavior": "standard_trance_support",
        "lead_behavior": "broad_sustained_late_entry",
        "hook_shape": "wide_sustained_anthem",
        "supersaw_behavior": "big_but_string_safe",
        "arp_behavior": "minimal_to_moderate",
        "pluck_behavior": "restrained",
        "breakdown_behavior": "piano_strings_central",
        "drum_build_behavior": "cinematic_8_bar_ramp",
        "drop_behavior": "orchestral_supersaw_blend",
        "density_targets": {"lead_max": 1.8, "strings_min": 1.0, "arp_max": 2.5, "supersaw_max": 5.0},
        "validation_targets": {"lead_avg_len_min": 1.0, "intro_signature": "piano_strings", "breakdown_focus": "orchestral"},
        "blueprint_overrides": {
            "bass_style": "classic_offbeat", "arp_style": "uplift_drive", "drum_style": "standard", "breakdown_style": "piano_led",
            "lead_archetype": "anthemic", "supersaw_identity": "octave_shine", "drop_arrival_style": "glide_in",
            "breakdown_narrative": "piano_confession", "energy_profile": "late_peak", "opening_scene": "pad_seed",
            "archetype_harmony_emphasis": "string_lift", "archetype_arp_grammar": "breath", "drop_layer_budget": 5,
        },
    },
    "CLASSIC_2000S_TRANCE": {
        "identity_name": "Classic 2000s Trance",
        "description": "Older-school melodic trance with obvious repetition and classic arp/pluck motion.",
        "emotional_target": "Nostalgic, bright, driving",
        "chord_progressions": ["uplifting", "festival", "classic"],
        "preferred_keys": ["E", "F#", "G", "A"],
        "intro_behavior": "early_arp_pluck_motif",
        "bass_behavior": "simple_offbeat_drive",
        "lead_behavior": "clear_repetitive_pluck_lead",
        "hook_shape": "simple_repeated_melody",
        "supersaw_behavior": "bright_simple_less_massive",
        "arp_behavior": "classic_gated_sequence",
        "pluck_behavior": "important_motif_layer",
        "breakdown_behavior": "pad_arp_motif",
        "drum_build_behavior": "classic_snare_roll",
        "drop_behavior": "melodic_hook_focus",
        "density_targets": {"lead_max": 2.4, "supersaw_max": 8.0, "arp_min": 1.0, "pluck_min": 1.0},
        "validation_targets": {"lead_avg_len_min": 0.75, "intro_signature": "arp_or_pluck", "breakdown_focus": "pad_arp"},
        "blueprint_overrides": {
            "bass_style": "classic_offbeat", "arp_style": "rolling_16th", "drum_style": "standard", "breakdown_style": "arp_texture",
            "lead_archetype": "uplift_hook", "supersaw_identity": "pulse_stack", "drop_arrival_style": "hook_first",
            "breakdown_narrative": "memory_recall", "energy_profile": "double_peak", "opening_scene": "hook_tease",
            "archetype_arp_grammar": "stream", "archetype_pluck_grammar": "pulse", "drop_layer_budget": 5,
        },
    },
    "DARK_EUPHORIC": {
        "identity_name": "Dark Euphoric",
        "description": "Minor-leaning dramatic trance with darker low movement and euphoric release.",
        "emotional_target": "Dark, dramatic, euphoric release",
        "chord_progressions": ["progressive", "festival", "hopeful"],
        "preferred_keys": ["F", "F#", "G", "G#"],
        "intro_behavior": "low_pad_dark_motif",
        "bass_behavior": "dark_heavy_rolling",
        "lead_behavior": "dramatic_minor_intervals",
        "hook_shape": "minor_leap_release",
        "supersaw_behavior": "wide_darker_lower_brightness",
        "arp_behavior": "tense_hypnotic",
        "pluck_behavior": "dark_sparse",
        "breakdown_behavior": "low_strings_sparse_piano",
        "drum_build_behavior": "tense_dramatic_roll",
        "drop_behavior": "dramatic_release_not_happy",
        "density_targets": {"lead_max": 2.2, "supersaw_max": 8.0, "arp_min": 0.5, "bass_min": 2.0},
        "validation_targets": {"lead_avg_len_min": 0.8, "intro_signature": "low_dark_pad", "breakdown_focus": "dark"},
        "blueprint_overrides": {
            "bass_style": "rolling_drive", "arp_style": "gated_8th", "drum_style": "driving", "breakdown_style": "pad_space",
            "lead_archetype": "yearning", "supersaw_identity": "bloom_stack", "drop_arrival_style": "staggered",
            "breakdown_narrative": "space_then_lift", "energy_profile": "late_peak", "opening_scene": "pad_seed",
            "archetype_harmony_emphasis": "pad_anchor", "archetype_arp_grammar": "answer", "archetype_pluck_grammar": "drop_gap",
            "drop_layer_budget": 5,
        },
    },
}

GENRE_VARIATIONS = {
    "uplifting": [
        "ANTHEMIC_UPLIFTING",
        "EMOTIONAL_VOCAL_TRANCE",
        "ORCHESTRAL_UPLIFTING",
        "CLASSIC_2000S_TRANCE",
    ],
    "progressive": [
        "PROGRESSIVE_TRANCE",
    ],
    "festival": [
        "ANTHEMIC_UPLIFTING",
        "TECH_UPLIFT",
    ],
    "classic": [
        "CLASSIC_2000S_TRANCE",
    ],
    "hopeful": [
        "EMOTIONAL_VOCAL_TRANCE",
        "ANTHEMIC_UPLIFTING",
    ],
}
PROGRESSION_FUNCTIONS = {
    "uplifting": ["I", "V", "vi", "IV"],
    "classic": ["I", "IV", "vi", "V"],
    "festival": ["vi", "IV", "I", "V"],
    "hopeful": ["I", "V", "vi", "IV"],
    "progressive": ["vi", "IV", "I", "V"],
}
HARMONIC_INTENT = {
    "I": {
        "emotion": "home",
        "primary_targets": ["root", "fifth"],
        "secondary_targets": ["third"],
        "allow_tension": False,
    },
    "V": {
        "emotion": "tension",
        "primary_targets": ["fifth", "third"],
        "secondary_targets": ["root"],
        "allow_tension": True,
    },
    "vi": {
        "emotion": "longing",
        "primary_targets": ["third", "root"],
        "secondary_targets": ["fifth"],
        "allow_tension": False,
    },
    "IV": {
        "emotion": "lift",
        "primary_targets": ["third", "fifth"],
        "secondary_targets": ["root"],
        "allow_tension": False,
    },
}
ARRANGEMENTS = {
    "extended": [
        ("Intro", 8), ("Verse", 16), ("Build", 16), ("Drop 1", 24),
        ("Breakdown", 16), ("Build 2", 16), ("Drop 2", 24), ("Outro", 8),
    ],
    "compact": [
        ("Intro", 8), ("Verse", 12), ("Build", 8), ("Drop 1", 16),
        ("Breakdown", 12), ("Build 2", 8), ("Drop 2", 16), ("Outro", 8),
    ],
}

ARRANGEMENT_STORY_PROFILES = {
    "ANTHEMIC_UPLIFTING": {
        "story_name": "early_anthem_long_breakdown",
        "description": "Early euphoric release, long emotional reset, and a stronger Drop 2 lift.",
        "section_bars": {
            "extended": [("Intro", 8), ("Verse", 12), ("Build", 12), ("Drop 1", 24), ("Breakdown", 20), ("Build 2", 12), ("Drop 2", 28), ("Outro", 8)],
            "compact": [("Intro", 8), ("Verse", 8), ("Build", 8), ("Drop 1", 16), ("Breakdown", 16), ("Build 2", 8), ("Drop 2", 20), ("Outro", 8)],
        },
        "intro_instruments": ["pad", "supersaw_chords", "hats"],
        "lead_entry": ("Drop 1", 0),
        "arp_entry": ("Build", 0),
        "bass_entry": ("Verse", 0),
        "breakdown_instruments": ["piano", "strings", "pad"],
        "drop2_energy_boost": 1.12,
    },
    "EMOTIONAL_VOCAL_TRANCE": {
        "story_name": "vocal_space_delayed_hook",
        "description": "More air before the hook, vocal/piano hints early, and a smoother emotional arrival.",
        "section_bars": {
            "extended": [("Intro", 12), ("Verse", 16), ("Build", 12), ("Drop 1", 20), ("Breakdown", 20), ("Build 2", 12), ("Drop 2", 24), ("Outro", 8)],
            "compact": [("Intro", 12), ("Verse", 8), ("Build", 8), ("Drop 1", 16), ("Breakdown", 16), ("Build 2", 8), ("Drop 2", 16), ("Outro", 8)],
        },
        "intro_instruments": ["piano", "vocal_melody", "pad"],
        "lead_entry": ("Drop 1", 4),
        "arp_entry": ("Build", 4),
        "bass_entry": ("Verse", 4),
        "breakdown_instruments": ["piano", "vocal_melody", "strings"],
        "drop2_energy_boost": 1.04,
    },
    "PROGRESSIVE_TRANCE": {
        "story_name": "long_groove_late_melody",
        "description": "Longer groove intro, later lead ownership, and subtler drop escalation.",
        "section_bars": {
            "extended": [("Intro", 16), ("Verse", 16), ("Build", 16), ("Drop 1", 20), ("Breakdown", 16), ("Build 2", 16), ("Drop 2", 24), ("Outro", 8)],
            "compact": [("Intro", 12), ("Verse", 12), ("Build", 8), ("Drop 1", 16), ("Breakdown", 12), ("Build 2", 12), ("Drop 2", 16), ("Outro", 8)],
        },
        "intro_instruments": ["pad", "rolling_bass", "hats"],
        "lead_entry": ("Drop 1", 8),
        "arp_entry": ("Verse", 0),
        "bass_entry": ("Intro", 4),
        "breakdown_instruments": ["pad", "strings"],
        "drop2_energy_boost": 1.03,
    },
    "TECH_UPLIFT": {
        "story_name": "driving_club_pressure",
        "description": "Longer percussive groove, later lead hook, short tension breakdown, hard return.",
        "section_bars": {
            "extended": [("Intro", 16), ("Verse", 12), ("Build", 12), ("Drop 1", 24), ("Breakdown", 12), ("Build 2", 12), ("Drop 2", 28), ("Outro", 8)],
            "compact": [("Intro", 12), ("Verse", 8), ("Build", 8), ("Drop 1", 20), ("Breakdown", 8), ("Build 2", 8), ("Drop 2", 20), ("Outro", 8)],
        },
        "intro_instruments": ["kick", "rolling_bass", "hats", "clap_snare"],
        "lead_entry": ("Drop 1", 4),
        "arp_entry": ("Verse", 0),
        "bass_entry": ("Intro", 0),
        "breakdown_instruments": ["arp", "pad"],
        "drop2_energy_boost": 1.08,
    },
    "ORCHESTRAL_UPLIFTING": {
        "story_name": "cinematic_intro_delayed_drop",
        "description": "Piano/strings opening, delayed first drop, extended cinematic breakdown.",
        "section_bars": {
            "extended": [("Intro", 16), ("Verse", 12), ("Build", 16), ("Drop 1", 20), ("Breakdown", 24), ("Build 2", 16), ("Drop 2", 28), ("Outro", 8)],
            "compact": [("Intro", 12), ("Verse", 8), ("Build", 12), ("Drop 1", 16), ("Breakdown", 20), ("Build 2", 8), ("Drop 2", 20), ("Outro", 8)],
        },
        "intro_instruments": ["piano", "strings", "pad"],
        "lead_entry": ("Drop 1", 8),
        "arp_entry": ("Build", 4),
        "bass_entry": ("Build", 0),
        "breakdown_instruments": ["piano", "strings", "pad"],
        "drop2_energy_boost": 1.10,
    },
    "CLASSIC_2000S_TRANCE": {
        "story_name": "classic_arp_first",
        "description": "Arp/pluck identity appears immediately, with compact classic club pacing.",
        "section_bars": {
            "extended": [("Intro", 12), ("Verse", 12), ("Build", 12), ("Drop 1", 20), ("Breakdown", 16), ("Build 2", 12), ("Drop 2", 20), ("Outro", 8)],
            "compact": [("Intro", 8), ("Verse", 8), ("Build", 8), ("Drop 1", 16), ("Breakdown", 12), ("Build 2", 8), ("Drop 2", 16), ("Outro", 8)],
        },
        "intro_instruments": ["arp", "pluck", "offbeat_bass", "hats"],
        "lead_entry": ("Drop 1", 0),
        "arp_entry": ("Intro", 0),
        "bass_entry": ("Intro", 4),
        "breakdown_instruments": ["pad", "arp", "pluck"],
        "drop2_energy_boost": 1.05,
    },
    "DARK_EUPHORIC": {
        "story_name": "dark_slow_reveal",
        "description": "Low, tense opening with heavier bass movement and dramatic release.",
        "section_bars": {
            "extended": [("Intro", 12), ("Verse", 16), ("Build", 16), ("Drop 1", 20), ("Breakdown", 20), ("Build 2", 16), ("Drop 2", 28), ("Outro", 8)],
            "compact": [("Intro", 12), ("Verse", 8), ("Build", 8), ("Drop 1", 16), ("Breakdown", 16), ("Build 2", 8), ("Drop 2", 20), ("Outro", 8)],
        },
        "intro_instruments": ["pad", "strings", "rolling_bass"],
        "lead_entry": ("Drop 1", 4),
        "arp_entry": ("Verse", 4),
        "bass_entry": ("Intro", 4),
        "breakdown_instruments": ["pad", "strings", "piano"],
        "drop2_energy_boost": 1.07,
    },
}

IDENTITY_VARIATIONS = {
    "ANTHEMIC_UPLIFTING": [
        "EARLY_DROP",
        "DELAYED_DROP",
        "PIANO_BREAK",
        "ARP_DRIVEN",
        "SUPERSAW_HEAVY",
    ],
    "EMOTIONAL_VOCAL_TRANCE": [
        "VOCAL_SPACE",
        "PIANO_CONFESSION",
        "SOFT_EARLY_DROP",
        "LATE_HOOK",
    ],
    "ORCHESTRAL_UPLIFTING": [
        "PIANO_INTRO",
        "STRING_CINEMA",
        "DELAYED_DROP",
        "SOFT_DROP1",
    ],
    "CLASSIC_2000S_TRANCE": [
        "ARP_DRIVEN",
        "PLUCK_INTRO",
        "EARLY_DROP",
        "PAD_BREAK",
    ],
    "PROGRESSIVE_TRANCE": [
        "LONG_GROOVE",
        "PAD_DRIFT",
        "LATE_LEAD",
    ],
    "TECH_UPLIFT": [
        "DRIVING_INTRO",
        "SHORT_BREAK",
        "ARP_PRESSURE",
    ],
    "DARK_EUPHORIC": [
        "LOW_INTRO",
        "DELAYED_DROP",
        "DARK_BREAK",
    ],
}

IDENTITY_VARIATION_BEHAVIOR = {
    "ANTHEMIC_UPLIFTING": {
        "EARLY_DROP": {
            "summary": "Minimal intro, fast Drop 1 arrival, lead owns the first impact, arp stays supportive.",
            "story": {
                "story_name": "anthemic_early_drop",
                "description": "Anthemic identity with a short setup and a fast euphoric first drop.",
                "section_bars": {
                    "extended": [("Intro", 4), ("Verse", 4), ("Build", 4), ("Drop 1", 24), ("Breakdown", 20), ("Build 2", 12), ("Drop 2", 28), ("Outro", 8)],
                    "compact": [("Intro", 4), ("Verse", 4), ("Build", 4), ("Drop 1", 16), ("Breakdown", 16), ("Build 2", 8), ("Drop 2", 20), ("Outro", 8)],
                },
                "intro_instruments": ["pad", "hats"],
                "lead_entry": ("Drop 1", 0),
                "arp_entry": ("Build", 0),
                "bass_entry": ("Verse", 0),
                "breakdown_instruments": ["piano", "strings", "pad"],
                "drop2_energy_boost": 1.12,
            },
            "blueprint": {"opening_scene": "drum_tease", "drop_arrival_style": "slam", "archetype_arp_grammar": "breath"},
        },
        "DELAYED_DROP": {
            "summary": "Longer intro/verse tease, late lead entry, bigger payoff after a patient build.",
            "story": {
                "story_name": "anthemic_delayed_drop",
                "description": "Anthemic identity with a longer runway before the first hook impact.",
                "section_bars": {
                    "extended": [("Intro", 12), ("Verse", 16), ("Build", 16), ("Drop 1", 24), ("Breakdown", 20), ("Build 2", 12), ("Drop 2", 28), ("Outro", 8)],
                    "compact": [("Intro", 12), ("Verse", 8), ("Build", 12), ("Drop 1", 16), ("Breakdown", 16), ("Build 2", 8), ("Drop 2", 20), ("Outro", 8)],
                },
                "intro_instruments": ["pad", "supersaw_chords"],
                "lead_entry": ("Drop 1", 4),
                "arp_entry": ("Build", 4),
                "bass_entry": ("Verse", 4),
                "breakdown_instruments": ["piano", "strings", "pad"],
                "drop2_energy_boost": 1.14,
            },
            "blueprint": {"opening_scene": "pad_seed", "drop_arrival_style": "glide_in", "energy_profile": "late_peak"},
        },
        "PIANO_BREAK": {
            "summary": "Standard anthemic drop path but the breakdown pivots hard into piano and strings.",
            "story": {
                "story_name": "anthemic_piano_break",
                "description": "Anthemic identity with a piano-led emotional center and softer Drop 1 contrast.",
                "section_bars": {
                    "extended": [("Intro", 8), ("Verse", 12), ("Build", 12), ("Drop 1", 20), ("Breakdown", 24), ("Build 2", 12), ("Drop 2", 28), ("Outro", 8)],
                    "compact": [("Intro", 8), ("Verse", 8), ("Build", 8), ("Drop 1", 16), ("Breakdown", 20), ("Build 2", 8), ("Drop 2", 20), ("Outro", 8)],
                },
                "intro_instruments": ["pad", "piano"],
                "lead_entry": ("Drop 1", 0),
                "arp_entry": ("Build", 4),
                "bass_entry": ("Verse", 0),
                "breakdown_instruments": ["piano", "strings"],
                "drop2_energy_boost": 1.15,
            },
            "blueprint": {"breakdown_style": "piano_led", "breakdown_narrative": "piano_confession", "drop_arrival_style": "hook_first"},
        },
        "ARP_DRIVEN": {
            "summary": "Arp appears from the first bars, bass is more rolling, supersaw leaves more rhythmic space.",
            "story": {
                "story_name": "anthemic_arp_driven",
                "description": "Anthemic identity with a classic moving arp foreground and a less static intro.",
                "section_bars": {
                    "extended": [("Intro", 8), ("Verse", 16), ("Build", 12), ("Drop 1", 20), ("Breakdown", 16), ("Build 2", 12), ("Drop 2", 24), ("Outro", 8)],
                    "compact": [("Intro", 8), ("Verse", 12), ("Build", 8), ("Drop 1", 16), ("Breakdown", 12), ("Build 2", 8), ("Drop 2", 20), ("Outro", 8)],
                },
                "intro_instruments": ["arp", "pluck", "hats", "pad"],
                "lead_entry": ("Drop 1", 0),
                "arp_entry": ("Intro", 0),
                "bass_entry": ("Verse", 0),
                "breakdown_instruments": ["arp", "pad", "piano"],
                "drop2_energy_boost": 1.08,
            },
            "blueprint": {"arp_style": "rolling_16th", "archetype_arp_grammar": "stream", "supersaw_identity": "pulse_stack"},
        },
        "SUPERSAW_HEAVY": {
            "summary": "Supersaw presence is obvious early, arp is minimal, Drop 2 becomes the widest moment.",
            "story": {
                "story_name": "anthemic_supersaw_heavy",
                "description": "Anthemic identity focused on chord-wall energy and a larger Drop 2 expansion.",
                "section_bars": {
                    "extended": [("Intro", 8), ("Verse", 12), ("Build", 12), ("Drop 1", 24), ("Breakdown", 16), ("Build 2", 12), ("Drop 2", 32), ("Outro", 8)],
                    "compact": [("Intro", 8), ("Verse", 8), ("Build", 8), ("Drop 1", 20), ("Breakdown", 12), ("Build 2", 8), ("Drop 2", 24), ("Outro", 8)],
                },
                "intro_instruments": ["supersaw_chords", "pad"],
                "lead_entry": ("Drop 1", 0),
                "arp_entry": ("Build", 8),
                "bass_entry": ("Verse", 0),
                "breakdown_instruments": ["pad", "strings"],
                "drop2_energy_boost": 1.18,
            },
            "blueprint": {"supersaw_identity": "wall_stack", "archetype_arp_grammar": "breath", "drop_layer_budget": 6},
        },
    },
    "EMOTIONAL_VOCAL_TRANCE": {
        "VOCAL_SPACE": {
            "summary": "Vocal guide appears early, lead is delayed, and the breakdown stays sparse.",
            "story": {"intro_instruments": ["vocal_melody", "piano", "pad"], "lead_entry": ("Drop 1", 8), "breakdown_instruments": ["vocal_melody", "piano"], "drop2_energy_boost": 1.03},
            "blueprint": {"archetype_topline_density": "vocal_heavy", "breakdown_style": "vocal_focus"},
        },
        "PIANO_CONFESSION": {
            "summary": "Piano carries the emotional identity before the drop opens up.",
            "story": {"intro_instruments": ["piano", "pad"], "breakdown_instruments": ["piano", "strings"], "lead_entry": ("Drop 1", 4), "drop2_energy_boost": 1.05},
            "blueprint": {"breakdown_narrative": "piano_confession", "breakdown_style": "piano_led"},
        },
        "SOFT_EARLY_DROP": {
            "summary": "Shorter intro with a gentle early drop and warm support layers.",
            "story": {"section_bars": {"extended": [("Intro", 8), ("Verse", 8), ("Build", 8), ("Drop 1", 20), ("Breakdown", 20), ("Build 2", 12), ("Drop 2", 24), ("Outro", 8)]}, "lead_entry": ("Drop 1", 4), "bass_entry": ("Verse", 4)},
            "blueprint": {"drop_arrival_style": "glide_in"},
        },
        "LATE_HOOK": {
            "summary": "Lead hook waits until the drop has space, leaving more topline air.",
            "story": {"lead_entry": ("Drop 1", 8), "arp_entry": ("Build", 4), "breakdown_instruments": ["vocal_melody", "strings"]},
            "blueprint": {"lead_vocal_relationship": "lead_answers_vocal"},
        },
    },
    "ORCHESTRAL_UPLIFTING": {
        "PIANO_INTRO": {"summary": "Piano is the first emotional object, strings enter later.", "story": {"intro_instruments": ["piano", "pad"], "breakdown_instruments": ["piano", "strings"]}, "blueprint": {"breakdown_narrative": "piano_confession"}},
        "STRING_CINEMA": {"summary": "Strings dominate the first scene and the breakdown gets wider.", "story": {"intro_instruments": ["strings", "pad"], "breakdown_instruments": ["strings", "piano", "pad"], "drop2_energy_boost": 1.12}, "blueprint": {"archetype_harmony_emphasis": "string_lift"}},
        "DELAYED_DROP": {"summary": "Long cinematic runway before the first drop.", "story": {"section_bars": {"extended": [("Intro", 16), ("Verse", 16), ("Build", 16), ("Drop 1", 20), ("Breakdown", 24), ("Build 2", 16), ("Drop 2", 28), ("Outro", 8)]}, "lead_entry": ("Drop 1", 8)}, "blueprint": {"energy_profile": "late_peak"}},
        "SOFT_DROP1": {"summary": "Drop 1 is restrained so Drop 2 feels more cinematic.", "story": {"drop2_energy_boost": 1.16, "breakdown_instruments": ["piano", "strings"]}, "blueprint": {"drop_pair_profile": "drop1_tease_drop2_release"}},
    },
    "CLASSIC_2000S_TRANCE": {
        "ARP_DRIVEN": {"summary": "Classic arp is active immediately and remains the identity cue.", "story": {"intro_instruments": ["arp", "hats"], "arp_entry": ("Intro", 0), "breakdown_instruments": ["arp", "pad"]}, "blueprint": {"arp_style": "rolling_16th"}},
        "PLUCK_INTRO": {"summary": "Pluck motif opens the track before the full arp joins.", "story": {"intro_instruments": ["pluck", "pad"], "arp_entry": ("Verse", 0), "breakdown_instruments": ["pluck", "pad"]}, "blueprint": {"archetype_pluck_grammar": "pulse"}},
        "EARLY_DROP": {"summary": "Compact old-school arrangement with a fast hook arrival.", "story": {"section_bars": {"extended": [("Intro", 8), ("Verse", 8), ("Build", 8), ("Drop 1", 20), ("Breakdown", 16), ("Build 2", 8), ("Drop 2", 20), ("Outro", 8)]}, "lead_entry": ("Drop 1", 0)}, "blueprint": {"drop_arrival_style": "hook_first"}},
        "PAD_BREAK": {"summary": "Breakdown recalls classic pad/arp emotion instead of cinematic piano.", "story": {"breakdown_instruments": ["pad", "arp"], "intro_instruments": ["arp", "pluck", "pad"]}, "blueprint": {"breakdown_style": "pad_space"}},
    },
}
STEMS = [
    "kick",
    "offbeat_bass",
    "rolling_bass",
    "sub_bass",
    "clap_snare",
    "hats",
    "lead",
    "supersaw_chords",
    "pad",
    "arp",
    "pluck",
    "strings",
    "piano",
    "countermelody",
    "vocal_melody",
]

STEM_EXPORT_LABELS = {
    "kick": "01_kick",
    "offbeat_bass": "02_offbeat_bass",
    "rolling_bass": "03_rolling_bass",
    "sub_bass": "04_sub_bass",
    "clap_snare": "05_clap_snare",
    "hats": "06_hats",
    "lead": "07_lead",
    "supersaw_chords": "08_supersaw_chords",
    "pad": "09_pad",
    "arp": "10_arp",
    "pluck": "11_pluck",
    "strings": "12_strings",
    "piano": "13_piano",
    "countermelody": "14_countermelody",
    "vocal_melody": "15_vocal_melody",
}

NOTE = {
    "C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
    "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11,
}
SCALE = [0, 2, 3, 5, 7, 8, 10]
LEVEL_FACTOR = {"low": 0.88, "medium": 1.0, "high": 1.12}
VARIATION_SPREAD = {"low": 0, "medium": 1, "high": 2}
HOOK_ARCHETYPES = ["declarative", "yearning", "driving", "open"]
DRAMA_PROFILES = ["lift_jump", "delayed_answer", "suspended_hold", "surprise_gap"]
COUNTER_ANSWER_MODES = ["echo_answer", "octave_lift_answer", "long_note_glow", "tail_response"]
HOOK_CANDIDATE_POOL = [
    ("declarative", 0),
    ("yearning", 0),
    ("driving", 0),
    ("open", 0),
    ("declarative", 1),
    ("yearning", 1),
    ("driving", 1),
    ("open", 1),
]
ARP_PATTERNS = [
    [0.0, 0.5, 1.5, 2.0],
    [0.0, 1.0, 2.0, 3.0],
    [0.5, 1.5, 2.5, 3.5],
]
ARP_PATTERN_NAMES = {
    0: "accent_push",
    1: "quarter_lock",
    2: "offbeat_lift",
}

KeyType = Literal["E", "F", "F#", "G", "G#", "A", "A#", "C", "D"]
ProgressionType = Literal["uplifting", "classic", "festival", "hopeful", "progressive"]
DensityType = Literal["low", "medium", "high"]
VariationType = Literal["low", "medium", "high"]
EnergyBiasType = Literal["low", "medium", "high"]
ArrangementType = Literal["extended", "compact"]
TrackIdentityType = Literal[
    "auto",
    "ANTHEMIC_UPLIFTING",
    "EMOTIONAL_VOCAL_TRANCE",
    "PROGRESSIVE_TRANCE",
    "TECH_UPLIFT",
    "ORCHESTRAL_UPLIFTING",
    "CLASSIC_2000S_TRANCE",
    "DARK_EUPHORIC",
]

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dream Trance Generator __APP_VERSION__</title>
  <style>
    :root {
      --bg: #08111f;
      --panel: rgba(10, 21, 42, 0.9);
      --line: rgba(145, 179, 255, 0.18);
      --text: #eef3ff;
      --muted: #b9c7e9;
      --accent: #7fd0ff;
      --accent-2: #ffd783;
      --shadow: 0 18px 42px rgba(0,0,0,0.32);
      --radius: 22px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--text);
      font-family: Georgia, "Trebuchet MS", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(127, 208, 255, 0.14), transparent 28%),
        radial-gradient(circle at right center, rgba(255, 215, 131, 0.10), transparent 26%),
        linear-gradient(180deg, #050c16 0%, #091325 48%, #0d1831 100%);
      min-height: 100vh;
    }
    .shell { max-width: 1320px; margin: 0 auto; padding: 28px; }
    .hero, .main { display: grid; gap: 24px; }
    .hero { grid-template-columns: 1.2fr 0.8fr; margin-bottom: 24px; }
    .card, .panel, .tip {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }
    .card, .panel, .tip { padding: 24px; }
    .eyebrow {
      display: inline-block;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--muted);
      margin-bottom: 16px;
    }
    h1 { margin: 0 0 12px; font-size: clamp(18px, 2.2vw, 32px); line-height: 1.12; max-width: 18ch; }
    p { color: var(--muted); line-height: 1.6; }
    .hero-side { display: grid; gap: 16px; }
    .stat { padding: 18px; border-radius: 18px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); }
    .stat strong { display: block; font-size: 20px; margin-top: 8px; }
    .main { grid-template-columns: minmax(0, 1fr) 340px; }
    .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
    .field { display: flex; flex-direction: column; gap: 8px; }
    .field.full { grid-column: 1 / -1; }
    label { font-size: 14px; font-weight: 700; }
    input, select {
      width: 100%;
      border: 1px solid rgba(255,255,255,0.08);
      background: rgba(3, 10, 20, 0.72);
      color: var(--text);
      border-radius: 14px;
      padding: 14px;
      font-size: 15px;
    }
    .actions { margin-top: 20px; display: flex; gap: 12px; flex-wrap: wrap; }
    button, .button-link {
      border: 0;
      border-radius: 16px;
      padding: 15px 22px;
      font-size: 15px;
      font-weight: 700;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 48px;
      text-decoration: none;
    }
    .primary { background: linear-gradient(135deg, var(--accent), var(--accent-2)); color: #07111f; }
    .secondary { background: rgba(255,255,255,0.05); color: var(--text); }
    ul { margin: 0; padding-left: 18px; color: var(--muted); line-height: 1.6; }
    @media (max-width: 980px) {
      .hero, .main, .grid { grid-template-columns: 1fr; }
      .shell { padding: 16px; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="card">
        <div class="eyebrow">Dream Trance Generator __APP_VERSION__</div>
        <h1>Generate a full MIDI pack, then produce it from an interactive Advisor Dashboard.</h1>
        <p>__APP_VERSION__ adds the Motif / Phrase / Story Engine while __ADVISOR_UI_VERSION__ keeps the context-aware production dashboard current for every exported stem.</p>
      </div>
      <div class="hero-side">
        <div class="stat">Blueprint-driven stems<strong>Chords, pads, piano, arp, bass, drums, lead, and vocal all follow one authored plan.</strong></div>
        <div class="stat">Export package<strong>Combined arrangement MIDI plus aligned per-stem MIDI files in one ZIP.</strong></div>
        <div class="stat">Best first test<strong>138 BPM, D or F#, uplifting, medium density, medium variation.</strong></div>
      </div>
    </section>
    <section class="main">
      <div class="panel">
        <h2>Composer Controls</h2>
        <p>Use the same settings across multiple renders to hear the arrangement identity engine create distinct full-track ideas.</p>
        <form method="post" action="/generate">
          <div class="grid">
            <div class="field">
              <label for="bpm">BPM</label>
              <input id="bpm" name="bpm" type="number" min="120" max="142" value="__DEFAULT_BPM__">
            </div>
            <div class="field">
              <label for="key">Key</label>
              <select id="key" name="key">__KEYS__</select>
            </div>
            <div class="field">
              <label for="progression">Progression</label>
              <select id="progression" name="progression">__PROGRESSIONS__</select>
            </div>
            <div class="field">
              <label for="arrangement">Arrangement</label>
              <select id="arrangement" name="arrangement">__ARRANGEMENTS__</select>
            </div>
            <div class="field">
              <label for="density">Density</label>
              <select id="density" name="density">__DENSITIES__</select>
            </div>
            <div class="field">
              <label for="variation">Variation Intensity</label>
              <select id="variation" name="variation">__VARIATIONS__</select>
            </div>
            <div class="field full">
              <label for="energy_profile">Energy Bias</label>
              <select id="energy_profile" name="energy_profile">__ENERGY__</select>
            </div>
            <div class="field full">
              <label for="track_identity">Track Identity</label>
              <select id="track_identity" name="track_identity">__TRACK_IDENTITIES__</select>
            </div>
          </div>
          <div class="actions">
            <button class="primary" type="submit">Generate MIDI Pack</button>
            <button class="secondary" type="reset">Reset</button>
            <a class="button-link secondary" href="/melody-lab">Melody Lab</a>
          </div>
        </form>
      </div>
      <aside class="tip">
        <h3>What __APP_VERSION__ changes</h3>
        <ul>
          <li>V11.5 gives the lead a defined role: silence early, teaser before the drop, controlled Drop 1 hook, and stronger Drop 2 payoff.</li>
          <li>Lead, piano, arp, vocal guide, and countermelody are now tied to a shared phrase identity instead of unrelated fragments.</li>
          <li>Breakdowns expose the emotional motif with space, while Drop 2 returns as the strongest motif payoff.</li>
          <li>Each pack exports motif_story.json with motif notes, reveal plan, shiver moment, and story validation scores.</li>
          <li>Generated result pages still show Download ZIP and Open Advisor Dashboard actions.</li>
          <li>ZIP naming follows the active composition build and selected progression.</li>
        </ul>
      </aside>
    </section>
  </div>
</body>
</html>
"""

RESULT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dream Trance Generator __APP_VERSION__ - Pack Ready</title>
  <style>
    :root { --bg:#07101f; --panel:#0d1a32; --line:rgba(145,179,255,.2); --text:#eef3ff; --muted:#b9c7e9; --accent:#7fd0ff; --gold:#ffd783; }
    * { box-sizing: border-box; }
    body { margin:0; min-height:100vh; color:var(--text); font-family: Georgia, "Trebuchet MS", sans-serif; background:radial-gradient(circle at 20% 10%, rgba(127,208,255,.18), transparent 30%), linear-gradient(180deg,#050b15,#0b1730); display:grid; place-items:center; padding:24px; }
    .card { width:min(760px,100%); background:rgba(13,26,50,.94); border:1px solid var(--line); border-radius:24px; padding:30px; box-shadow:0 22px 60px rgba(0,0,0,.34); }
    .eyebrow { color:var(--muted); text-transform:uppercase; letter-spacing:.12em; font-size:12px; }
    h1 { margin:10px 0 8px; font-size:clamp(26px,4vw,44px); }
    p { color:var(--muted); line-height:1.6; }
    .meta { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; margin:22px 0; }
    .pill { border:1px solid rgba(255,255,255,.08); background:rgba(255,255,255,.04); padding:12px 14px; border-radius:16px; }
    .pill span { color:var(--muted); display:block; font-size:12px; margin-bottom:5px; }
    .actions { display:flex; flex-wrap:wrap; gap:12px; margin-top:22px; }
    a { text-decoration:none; font-weight:800; border-radius:16px; padding:15px 20px; display:inline-block; }
    .primary { color:#07101f; background:linear-gradient(135deg,var(--accent),var(--gold)); }
    .secondary { color:var(--text); background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.1); }
    @media(max-width:700px){ .meta{grid-template-columns:1fr;} }
  </style>
</head>
<body>
  <main class="card">
    <div class="eyebrow">Dream Trance Generator __APP_VERSION__</div>
    <h1>MIDI pack ready</h1>
    <p>Your ZIP has been generated. Open the Advisor Dashboard when you want an interactive stem-by-stem production view instead of digging through text files.</p>
    <section class="meta">
      <div class="pill"><span>Genre</span>__GENRE__</div>
      <div class="pill"><span>Identity</span>__IDENTITY__</div>
      <div class="pill"><span>Variation</span>__VARIATION__</div>
      <div class="pill"><span>BPM / Key</span>__BPM__ / __KEY__</div>
    </section>
    <div class="actions">
      <a class="primary" href="__DOWNLOAD_URL__">Download ZIP</a>
      <a class="secondary" href="/advisor" target="_blank" rel="noopener">Open Advisor Dashboard</a>
      <a class="secondary" href="/">Generate Another</a>
    </div>
  </main>
</body>
</html>
"""

ADVISOR_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Advisor Dashboard - Dream Trance Generator __APP_VERSION__</title>
  <style>
    :root {
      --bg:#06101d; --panel:#0c1a31; --panel2:#101f3b; --line:rgba(151,184,255,.18);
      --text:#f0f5ff; --muted:#b9c7e9; --accent:#8ad8ff; --gold:#ffd783;
      --lead:#b68cff; --bass:#62a8ff; --drum:#ff7b7b; --pad:#78d79a;
    }
    * { box-sizing:border-box; }
    body { margin:0; color:var(--text); font-family: Georgia, "Trebuchet MS", sans-serif; background:radial-gradient(circle at 16% 6%, rgba(138,216,255,.16), transparent 28%), radial-gradient(circle at 90% 20%, rgba(255,215,131,.11), transparent 25%), linear-gradient(180deg,#050b15,#09172c 52%,#0d1930); min-height:100vh; }
    .shell { max-width:1500px; margin:0 auto; padding:22px; }
    .header { display:grid; grid-template-columns:1.2fr .8fr; gap:16px; margin-bottom:16px; }
    .card, .sidebar, .main, .quick { background:rgba(12,26,49,.94); border:1px solid var(--line); border-radius:22px; box-shadow:0 18px 50px rgba(0,0,0,.28); }
    .card, .quick { padding:22px; }
    .eyebrow { color:var(--muted); font-size:12px; letter-spacing:.12em; text-transform:uppercase; }
    h1,h2,h3 { margin:8px 0 10px; }
    p { color:var(--muted); line-height:1.55; }
    .meta { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
    .metric { background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.06); border-radius:16px; padding:12px; }
    .metric span { display:block; color:var(--muted); font-size:12px; margin-bottom:4px; }
    .quick ol, .quick ul { color:var(--muted); line-height:1.6; padding-left:22px; margin:8px 0; }
    .layout { display:grid; grid-template-columns:300px minmax(0,1fr); gap:16px; align-items:start; }
    .sidebar { padding:14px; position:sticky; top:16px; max-height:calc(100vh - 32px); overflow:auto; }
    .stem-btn { width:100%; border:1px solid rgba(255,255,255,.08); background:rgba(255,255,255,.035); color:var(--text); border-radius:14px; padding:12px; margin:5px 0; text-align:left; cursor:pointer; font-weight:800; }
    .stem-btn.active { outline:2px solid var(--accent); background:rgba(138,216,255,.12); }
    .stem-btn.drum { border-left:5px solid var(--drum); }
    .stem-btn.bass { border-left:5px solid var(--bass); }
    .stem-btn.lead { border-left:5px solid var(--lead); }
    .stem-btn.pad { border-left:5px solid var(--pad); }
    .main { padding:22px; min-height:720px; }
    .tabs { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:16px; }
    .tab { border:0; border-radius:999px; padding:11px 15px; color:var(--text); background:rgba(255,255,255,.06); cursor:pointer; font-weight:800; }
    .tab.active { color:#06101d; background:linear-gradient(135deg,var(--accent),var(--gold)); }
    .stem-title { display:flex; flex-wrap:wrap; align-items:center; gap:10px; }
    .badge { color:#06101d; background:var(--gold); padding:6px 10px; border-radius:999px; font-size:12px; font-weight:900; }
    .badge.soft { color:var(--text); background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.1); }
    .badge.high { background:#90f0b0; color:#06101d; }
    .badge.medium { background:#ffd783; color:#06101d; }
    .badge.low { background:#ff9b9b; color:#06101d; }
    .stem-summary { display:grid; gap:10px; margin-bottom:14px; padding:16px; border-radius:20px; background:linear-gradient(135deg,rgba(138,216,255,.09),rgba(255,215,131,.06)); border:1px solid rgba(255,255,255,.1); }
    .summary-line { display:flex; flex-wrap:wrap; gap:10px; align-items:center; color:var(--muted); }
    .summary-line strong { color:var(--text); }
    .preset-row { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:4px 0 12px; }
    .tag { color:#dce9ff; border:1px solid rgba(138,216,255,.18); background:rgba(138,216,255,.07); border-radius:999px; padding:5px 9px; font-size:12px; font-weight:800; }
    .search-pills { display:flex; flex-wrap:wrap; gap:8px; }
    .pill-btn { border:1px solid rgba(138,216,255,.24); background:rgba(138,216,255,.08); color:var(--text); border-radius:999px; padding:8px 11px; cursor:pointer; font-weight:800; }
    .pill-btn.copied { background:var(--gold); color:#06101d; }
    .grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }
    details { background:rgba(255,255,255,.035); border:1px solid rgba(255,255,255,.07); border-radius:16px; padding:14px; }
    summary { cursor:pointer; font-weight:900; }
    .build-guide { grid-column:1 / -1; }
    .build-shell { display:grid; gap:12px; }
    .action-bar { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; padding:12px; border-radius:16px; background:linear-gradient(135deg,rgba(146,220,255,.16),rgba(244,214,137,.12)); border:1px solid rgba(255,255,255,.12); margin-bottom:14px; }
    .action-item { display:grid; gap:4px; }
    .action-item span { color:var(--muted); font-size:.74rem; font-weight:900; text-transform:uppercase; letter-spacing:.08em; }
    .action-item strong { color:var(--text); font-size:.92rem; line-height:1.25; }
    .core-build, .pro-tweaks { background:rgba(255,255,255,.04); }
    .guide-sections { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; margin-top:12px; }
    .mini-section { border:1px solid rgba(255,255,255,.07); border-radius:14px; padding:10px; background:rgba(3,10,23,.36); }
    .mini-section h4 { margin:0 0 6px; font-size:.82rem; letter-spacing:.06em; text-transform:uppercase; }
    .mini-section ul { margin:.25rem 0 0 1rem; padding:0; }
    .mini-section li { margin:.22rem 0; }
    .mix-insight { grid-column:1 / -1; background:rgba(255,215,131,.07); border-color:rgba(255,215,131,.18); }
    .mix-insight strong { color:var(--gold); }
    ul { color:var(--muted); line-height:1.55; padding-left:20px; }
    .tech { display:none; }
    .mono { font-family: "Cascadia Mono", Consolas, monospace; color:#d7e6ff; }
    .warn { color:#ffd783; }
    @media(max-width:1000px){ .header,.layout,.grid,.meta,.action-bar,.guide-sections{grid-template-columns:1fr;} .sidebar{position:static; max-height:none;} }
  </style>
</head>
<body>
  <div class="shell">
    <section class="header">
      <div class="card">
        <div class="eyebrow">Advisor Dashboard</div>
        <h1>Interactive Production Advisor</h1>
        <p>Click a stem and load the recommended sound in Ableton without opening the text files.</p>
        <div class="meta" id="meta"></div>
      </div>
      <div class="quick">
        <h2>Start Here</h2>
        <ol>
          <li>Load Kick</li>
          <li>Load Bass</li>
          <li>Load Supersaw</li>
          <li>Load Lead</li>
          <li>Add FX: Reverb + Delay</li>
        </ol>
        <h3>Primary Focus</h3>
        <p id="focus"></p>
        <h3>Top Warnings</h3>
        <ul id="warnings"></ul>
      </div>
    </section>
    <section class="layout">
      <aside class="sidebar">
        <h2>Stems</h2>
        <div id="stemList"></div>
      </aside>
      <main class="main">
        <div class="tabs">
          <button class="tab active" id="advisorTab">Advisor Card</button>
          <button class="tab" id="techTab">Technical Analysis</button>
        </div>
        <section id="advisorPanel"></section>
        <section id="techPanel" class="tech"></section>
      </main>
    </section>
  </div>
  <script id="advisor-data" type="application/json">__ADVISOR_JSON__</script>
  <script>
    const data = JSON.parse(document.getElementById('advisor-data').textContent);
    const stems = [
      ['01_kick','01 Kick','drum'], ['02_offbeat_bass','02 Offbeat Bass','bass'], ['03_rolling_bass','03 Rolling Bass','bass'],
      ['04_sub_bass','04 Sub Bass','bass'], ['05_clap_snare','05 Clap/Snare','drum'], ['06_hats','06 Hats','drum'],
      ['07_lead','07 Lead','lead'], ['08_supersaw_chords','08 Supersaw','lead'], ['09_pad','09 Pad','pad'],
      ['10_arp','10 Arp','pad'], ['11_pluck','11 Pluck','pad'], ['12_strings','12 Strings','pad'],
      ['13_piano','13 Piano','pad'], ['14_countermelody','14 Countermelody','lead'], ['15_vocal_melody','15 Vocal Melody','lead']
    ];
    let selected = stems[6][0];
    const recommendations = data.recommendations || {};
    const meta = [
      ['Genre / Progression', data.progression_name || data.selected_chord_progression || 'unknown'],
      ['Track Identity', data.track_identity || 'unknown'],
      ['Variation Type', data.variation_type || 'DEFAULT'],
      ['BPM / Key', `${data.bpm || 'unknown'} / ${data.key || 'unknown'}`]
    ];
    document.getElementById('meta').innerHTML = meta.map(([k,v]) => `<div class="metric"><span>${k}</span>${v}</div>`).join('');
    function primaryFocus() {
      const identity = (data.track_identity || '').toLowerCase();
      if (identity.includes('orchestral')) return 'Piano + strings emotional setup into supersaw release.';
      if (identity.includes('vocal')) return 'Vocal space with warm lead and supportive supersaw.';
      if (identity.includes('classic')) return 'Arp/pluck identity with a clear melodic hook.';
      return 'Supersaw + lead driven trance drop.';
    }
    document.getElementById('focus').textContent = primaryFocus();
    function uniqueItems(items) {
      const seen = new Set();
      return (items || []).map(item => String(item || '').trim()).filter(item => {
        const key = item.toLowerCase();
        if (!item || seen.has(key)) return false;
        seen.add(key);
        return true;
      });
    }
    const warningPool = uniqueItems(Object.values(recommendations).flatMap(item => [...(item.mix_context_advice || []), ...(item.dynamic_midi_advice || [])]));
    document.getElementById('warnings').innerHTML = (warningPool.length ? warningPool.slice(0,3) : ['No urgent warnings. Balance kick, bass, lead, and supersaw first.']).map(item => `<li class="warn">${item}</li>`).join('');
    function list(items) {
      if (!items) return '<ul><li>None listed</li></ul>';
      if (!Array.isArray(items)) items = [items];
      return `<ul>${items.filter(Boolean).map(item => `<li>${item}</li>`).join('') || '<li>None listed</li>'}</ul>`;
    }
    function guideSectionsHtml(sections) {
      return `<div class="guide-sections">${sections.map(section => `
        <div class="mini-section">
          <h4>${section.icon || ''} ${section.title}</h4>
          ${list(section.items)}
        </div>`).join('')}</div>`;
    }
    function guideModel(plugin) {
      const guide = plugin.sound_design_guide || {};
      const action = guide.action || [
        `Load ${pluginName(plugin)} -> Init Preset`,
        `Search: ${(plugin.internal_search_terms || [plugin.category || 'clean preset'])[0]}`,
        `Goal: ${plugin.preset_type || plugin.preset_family || plugin.category || 'sit clearly in the mix'}`
      ];
      const coreBuild = guide.core_build || {
        oscillators: guide.oscillators || plugin.build_from_scratch,
        filter: guide.filter,
        envelope: guide.envelope,
        fx: guide.built_in_fx || plugin.fx_chain
      };
      const proTweaks = guide.pro_tweaks || {
        modulation: guide.modulation,
        advanced: guide.advanced_features,
        mix_position: guide.external_fx || plugin.fx_chain,
        listen_for: guide.listen_for,
        common_mistakes: guide.common_mistakes || plugin.avoid
      };
      return { action, coreBuild, proTweaks };
    }
    function simplifyPreset(plugin) {
      const raw = String(plugin.preset_type || plugin.preset_family || plugin.category || 'Clean production-ready sound');
      const parts = raw.split('/').map(item => item.trim()).filter(Boolean);
      const preset = parts[0] || raw;
      const tagWords = [];
      parts.slice(1).forEach(part => part.split(/[, ]+/).forEach(word => {
        const clean = word.replace(/[^a-zA-Z0-9+-]/g, '').trim();
        if (clean.length > 2) tagWords.push(clean[0].toUpperCase() + clean.slice(1));
      }));
      return { preset, tags: uniqueItems(tagWords).slice(0,7) };
    }
    function confidenceFor(rec) {
      const a = rec.analysis || {};
      const role = (rec.role || '').toLowerCase();
      const density = Number(a.notes_per_active_bar || 0);
      const avg = Number(a.avg_note_length || 0);
      const range = (Number(a.max_pitch || 0) - Number(a.min_pitch || 0));
      let level = 'Medium';
      let reason = 'role matches the selected stem, but MIDI behaviour is mixed';
      if (role.includes('lead') && avg >= 0.9 && range >= 8) { level = 'High'; reason = 'sustained lead notes and wide pitch range detected'; }
      else if (role.includes('bass') && density >= 1) { level = 'High'; reason = 'consistent bass rhythm detected'; }
      else if ((role.includes('arp') || role.includes('pluck')) && density >= 2) { level = 'High'; reason = 'dense rhythmic pattern detected'; }
      else if ((role.includes('pad') || role.includes('chord') || role.includes('strings')) && avg >= 1.5) { level = 'High'; reason = 'sustained harmonic material detected'; }
      else if (a.note_count === 0 || density === 0) { level = 'Low'; reason = 'little or no MIDI activity detected for this stem'; }
      return { level, reason };
    }
    function keySettings(plugin, rec) {
      if (plugin.contextual_key_settings) return plugin.contextual_key_settings;
      if (rec && rec.contextual_key_settings) return rec.contextual_key_settings;
      const model = guideModel(plugin);
      const pool = [...(model.coreBuild.oscillators || []), ...(model.coreBuild.filter || []), ...(model.coreBuild.envelope || [])];
      const chosen = pool.filter(item => /voice|detune|stereo|filter|cutoff|low-pass|sustain|release/i.test(item)).slice(0,4);
      return chosen.length ? chosen.map(item => item.replace(/[.]$/,'')).join(' | ') : 'Start clean | shape source | place with filter | add light FX';
    }
    function actionStrip(plugin, rec) {
      const model = guideModel(plugin);
      const action = model.action || [];
      return `
        <div class="action-bar">
          <div class="action-item"><span>Action</span><strong>${action[0] || `Load ${pluginName(plugin)} -> preset`}</strong></div>
          <div class="action-item"><span>Search</span><strong>${(action[1] || 'Search: clean preset').replace(/^Search:\\s*/,'')}</strong></div>
          <div class="action-item"><span>Target Sound</span><strong>${(action[2] || 'Goal: sit clearly in the mix').replace(/^Goal:\\s*/,'')}</strong></div>
          <div class="action-item"><span>Key Settings</span><strong>${keySettings(plugin, rec)}</strong></div>
        </div>`;
    }
    function searchPills(terms) {
      const items = uniqueItems(terms || []).slice(0,8);
      return `<div class="search-pills">${items.map(term => `<button class="pill-btn" type="button" data-copy="${term.replace(/"/g,'&quot;')}">${term}</button>`).join('') || '<span class="tag">No search terms listed</span>'}</div>`;
    }
    function mixInsight(rec) {
      const insight = rec.contextual_mix_insight || uniqueItems([...(rec.mix_context_advice || []), ...(rec.dynamic_midi_advice || [])])[0] || 'Balance this stem after kick, bass, lead, and supersaw are speaking clearly.';
      return `<details class="mix-insight" open><summary>Mix Insight</summary><p><strong>Action:</strong> ${insight}</p></details>`;
    }
    function soundDesignGuide(plugin) {
      const model = guideModel(plugin);
      const coreSections = [
        { title:'OSCILLATORS', icon:'🎛', items:model.coreBuild.oscillators },
        { title:'FILTER', icon:'🎚', items:model.coreBuild.filter },
        { title:'ENVELOPE', icon:'▣', items:model.coreBuild.envelope },
        { title:'FX', icon:'🔊', items:model.coreBuild.fx }
      ];
      const proSections = [
        { title:'MODULATION', icon:'〰', items:model.proTweaks.modulation },
        { title:'ADVANCED', icon:'✦', items:model.proTweaks.advanced },
        { title:'MIX POSITION', icon:'↔', items:model.proTweaks.mix_position },
        { title:'LISTEN FOR', icon:'👂', items:model.proTweaks.listen_for },
        { title:'COMMON MISTAKES', icon:'!', items:model.proTweaks.common_mistakes }
      ];
      return `
        <div class="build-shell">
          <details class="core-build" open><summary>CORE BUILD</summary>${guideSectionsHtml(coreSections)}</details>
          <details class="pro-tweaks" data-pro="${encodeURIComponent(JSON.stringify(proSections))}"><summary>PRO TWEAKS</summary><div class="pro-body"></div></details>
        </div>`;
    }
    function pluginName(plugin) { return (plugin && plugin.plugin) || 'Not specified'; }
    function firstIndustry(rec) { return (rec.industry_alternative_plugins || [])[0] || {}; }
    function avoidNotes(rec) {
      const primary = rec.primary_plugin || {};
      return primary.avoid_notes || rec.dynamic_midi_advice || rec.mix_context_advice || [];
    }
    function mixLevel(key) {
      const levels = { '01_kick':'-8 dB','02_offbeat_bass':'-12 dB','03_rolling_bass':'-14 dB','04_sub_bass':'-14 dB','05_clap_snare':'-14 dB','06_hats':'-18 dB','07_lead':'-14 dB','08_supersaw_chords':'-16 dB','09_pad':'-22 dB','10_arp':'-20 dB','11_pluck':'-21 dB','12_strings':'-20 dB','13_piano':'-18 dB','14_countermelody':'-18 dB','15_vocal_melody':'-18 dB' };
      return levels[key] || '-18 dB';
    }
    function renderStemList() {
      document.getElementById('stemList').innerHTML = stems.map(([key,label,cls]) => `<button class="stem-btn ${cls} ${key===selected?'active':''}" data-stem="${key}">${label}</button>`).join('');
      document.querySelectorAll('.stem-btn').forEach(btn => btn.addEventListener('click', () => { selected = btn.dataset.stem; render(); }));
    }
    function renderAdvisor() {
      const rec = recommendations[selected] || {};
      const primary = rec.primary_plugin || {};
      const alt = rec.alternative_owned_plugin || {};
      const industry = firstIndustry(rec);
      const label = stems.find(item => item[0] === selected)?.[1] || selected;
      const preset = simplifyPreset(primary);
      const confidence = confidenceFor(rec);
      const primaryAction = (guideModel(primary).action || [])[0] || `Load ${pluginName(primary)}`;
      const roleBadge = rec.arrangement_role_label || (rec.arrangement_role || 'Support').replace(/_/g,' ');
      document.getElementById('advisorPanel').innerHTML = `
        <div class="stem-summary">
          <div class="stem-title"><h2>${label}</h2><span class="badge">${pluginName(primary)}</span><span class="badge ${confidence.level.toLowerCase()}">Confidence: ${confidence.level}</span><span class="badge soft">Role: ${roleBadge}</span></div>
          <div class="summary-line"><strong>Role:</strong> ${rec.role || 'Not specified'} <span class="badge soft">Mix: ${mixLevel(selected)}</span></div>
          <div class="summary-line"><strong>Primary Action:</strong> ${primaryAction} -> search "${((guideModel(primary).action || [])[1] || (primary.internal_search_terms || ['clean preset'])[0]).replace(/^Search:\\s*/,'')}"</div>
          <div class="summary-line"><strong>Reason:</strong> ${confidence.reason}</div>
        </div>
        ${actionStrip(primary, rec)}
        <div class="preset-row"><strong>Preset Type:</strong> <span class="tag">${preset.preset}</span> ${preset.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}</div>
        <div class="grid">
          ${mixInsight(rec)}
          <details class="build-guide" open><summary>Sound Design Guide</summary>${soundDesignGuide(primary)}</details>
          <details><summary>Search Terms</summary>${searchPills(primary.internal_search_terms)}</details>
          <details><summary>External FX Chain</summary>${list(primary.fx_chain)}</details>
          <details><summary>Alternative Plugin (Owned)</summary><ul><li>${pluginName(alt)}</li><li>${alt.category || ''}</li></ul>${list(alt.internal_search_terms)}</details>
          <details><summary>Alternative Build Guide</summary>${soundDesignGuide(alt)}</details>
          <details><summary>Industry Alternative</summary><ul><li>${pluginName(industry)}</li><li>${industry.category || ''}</li></ul>${list(industry.internal_search_terms || industry.internet_search_terms)}</details>
          <details><summary>Industry Build Guide</summary>${soundDesignGuide(industry)}</details>
          <details><summary>Avoid Notes</summary>${list(avoidNotes(rec))}</details>
          <details open><summary>Mix Level</summary><ul><li>Start around ${mixLevel(selected)}</li></ul></details>
        </div>`;
    }
    function renderTech() {
      const rec = recommendations[selected] || {};
      const a = rec.analysis || {};
      const techWarnings = uniqueItems([...(rec.mix_context_advice || []), ...(rec.dynamic_midi_advice || [])]);
      document.getElementById('techPanel').innerHTML = `
        <h2>Technical Analysis</h2>
        <div class="grid">
          <details open><summary>Arrangement Role</summary><p class="mono">${rec.arrangement_role_label || rec.arrangement_role || 'unknown'}</p></details>
          <details open><summary>Role Reason</summary><p>${rec.role_reason || 'No role context available.'}</p></details>
          <details open><summary>Dominance Level</summary><p class="mono">${rec.dominance_level || 'unknown'}</p></details>
          <details open><summary>Sound Design Intensity</summary><p class="mono">${rec.sound_design_intensity || 'unknown'}</p></details>
          <details open><summary>Note Count</summary><p class="mono">${a.note_count ?? 'unknown'}</p></details>
          <details open><summary>Pitch Range</summary><p class="mono">${a.min_pitch ?? 'none'}-${a.max_pitch ?? 'none'}</p></details>
          <details open><summary>Density</summary><p class="mono">${a.notes_per_active_bar ?? 'unknown'} notes / active bar</p></details>
          <details open><summary>Average Note Length</summary><p class="mono">${a.avg_note_length ?? 'unknown'} beats</p></details>
          <details open><summary>Warnings</summary>${list(techWarnings)}</details>
        </div>`;
    }
    function render() { renderStemList(); renderAdvisor(); renderTech(); }
    document.addEventListener('toggle', event => {
      const node = event.target;
      if (!node.classList || !node.classList.contains('pro-tweaks') || !node.open || node.dataset.rendered) return;
      const sections = JSON.parse(decodeURIComponent(node.dataset.pro || '[]'));
      node.querySelector('.pro-body').innerHTML = guideSectionsHtml(sections);
      node.dataset.rendered = '1';
    }, true);
    document.addEventListener('click', event => {
      const pill = event.target.closest('.pill-btn');
      if (!pill) return;
      const text = pill.dataset.copy || pill.textContent;
      if (navigator.clipboard) navigator.clipboard.writeText(text);
      pill.classList.add('copied');
      const original = pill.textContent;
      pill.textContent = 'Copied';
      setTimeout(() => { pill.classList.remove('copied'); pill.textContent = original; }, 900);
    });
    document.getElementById('advisorTab').addEventListener('click', () => {
      document.getElementById('advisorTab').classList.add('active'); document.getElementById('techTab').classList.remove('active');
      document.getElementById('advisorPanel').style.display = 'block'; document.getElementById('techPanel').style.display = 'none';
    });
    document.getElementById('techTab').addEventListener('click', () => {
      document.getElementById('techTab').classList.add('active'); document.getElementById('advisorTab').classList.remove('active');
      document.getElementById('advisorPanel').style.display = 'none'; document.getElementById('techPanel').style.display = 'block';
    });
    render();
  </script>
</body>
</html>
"""


def page() -> str:
    html = HTML.replace("__APP_VERSION__", APP_VERSION)
    html = html.replace("__ADVISOR_UI_VERSION__", ADVISOR_UI_VERSION)
    html = html.replace("__DEFAULT_BPM__", str(DEFAULT_GUI_VALUES["bpm"]))
    html = html.replace(
        "__KEYS__",
        "".join(
            f"<option{' selected' if key == DEFAULT_GUI_VALUES['key'] else ''}>{key}</option>"
            for key in KEY_OPTIONS
        ),
    )
    html = html.replace(
        "__PROGRESSIONS__",
        "".join(
            f"<option value=\"{name}\"{' selected' if name == DEFAULT_GUI_VALUES['progression'] else ''}>{name.title()}</option>"
            for name in PROGRESSIONS
        ),
    )
    html = html.replace(
        "__ARRANGEMENTS__",
        "".join(
            f"<option value=\"{name}\"{' selected' if name == DEFAULT_GUI_VALUES['arrangement'] else ''}>{name.title()}</option>"
            for name in ARRANGEMENTS
        ),
    )
    html = html.replace(
        "__DENSITIES__",
        "".join(
            f"<option value=\"{level}\"{' selected' if level == DEFAULT_GUI_VALUES['density'] else ''}>{level.title()}</option>"
            for level in LEVEL_FACTOR
        ),
    )
    html = html.replace(
        "__VARIATIONS__",
        "".join(
            f"<option value=\"{level}\"{' selected' if level == DEFAULT_GUI_VALUES['variation'] else ''}>{level.title()}</option>"
            for level in LEVEL_FACTOR
        ),
    )
    html = html.replace(
        "__ENERGY__",
        "".join(
            f"<option value=\"{level}\"{' selected' if level == DEFAULT_GUI_VALUES['energy_bias'] else ''}>{level.title()}</option>"
            for level in LEVEL_FACTOR
        ),
    )
    identity_options = [("auto", "Auto")] + [
        (key, profile["identity_name"]) for key, profile in TRACK_IDENTITY_PROFILES.items()
    ]
    html = html.replace(
        "__TRACK_IDENTITIES__",
        "".join(
            f"<option value=\"{value}\"{' selected' if value == DEFAULT_GUI_VALUES['track_identity'] else ''}>{label}</option>"
            for value, label in identity_options
        ),
    )
    return html


def html_escape(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def result_page(download_url: str, blueprint: dict, bpm: int, key: str):
    return (
        RESULT_HTML
        .replace("__APP_VERSION__", APP_VERSION)
        .replace("__DOWNLOAD_URL__", download_url)
        .replace("__GENRE__", html_escape(blueprint.get("genre", blueprint.get("progression_name", ""))))
        .replace("__IDENTITY__", html_escape(blueprint.get("track_identity", "")))
        .replace("__VARIATION__", html_escape(blueprint.get("variation_type", "DEFAULT")))
        .replace("__BPM__", html_escape(bpm))
        .replace("__KEY__", html_escape(key))
    )


def latest_advisor_json_path():
    return LATEST_ADVISOR_DIR / "plugin_recommendations.json"


def persist_latest_advisor(plugin_recommendations):
    LATEST_ADVISOR_DIR.mkdir(parents=True, exist_ok=True)
    latest_advisor_json_path().write_text(json.dumps(plugin_recommendations, indent=2))


def advisor_dashboard_page(plugin_recommendations):
    advisor_json = json.dumps(plugin_recommendations).replace("</", "<\\/")
    return (
        ADVISOR_HTML
        .replace("__APP_VERSION__", f"{APP_VERSION} / Advisor {ADVISOR_UI_VERSION}")
        .replace("__ADVISOR_JSON__", advisor_json)
    )


def no_advisor_page():
    return """
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>No Advisor Data</title></head>
<body style="margin:0;min-height:100vh;display:grid;place-items:center;background:#07101f;color:#eef3ff;font-family:Georgia,'Trebuchet MS',sans-serif;padding:24px;">
  <main style="max-width:680px;background:#0d1a32;border:1px solid rgba(145,179,255,.2);border-radius:24px;padding:28px;">
    <h1>No advisor dashboard yet</h1>
    <p style="color:#b9c7e9;line-height:1.6;">Generate a MIDI pack first, then open the Advisor Dashboard. The dashboard reads the latest exported plugin_recommendations.json.</p>
    <a href="/" style="display:inline-block;margin-top:14px;border-radius:16px;padding:14px 18px;background:linear-gradient(135deg,#8ad8ff,#ffd783);color:#07101f;text-decoration:none;font-weight:800;">Generate Pack</a>
  </main>
</body>
</html>
"""


def get_progression_degree_name(index, progression_length=4):
    degree_cycle = ["I", "V", "vi", "IV"]
    return degree_cycle[index % progression_length]


def resolve_progression_function_cycle(progression_name: str, progression_family: str = ""):
    if progression_name in PROGRESSION_FUNCTIONS:
        return PROGRESSION_FUNCTIONS[progression_name]
    family_map = {
        "lifted": PROGRESSION_FUNCTIONS["uplifting"],
        "classic_warmth": PROGRESSION_FUNCTIONS["classic"],
        "festival_cycle": PROGRESSION_FUNCTIONS["festival"],
        "hopeful_pull": PROGRESSION_FUNCTIONS["hopeful"],
        "progressive_flow": PROGRESSION_FUNCTIONS["progressive"],
    }
    return family_map.get(progression_family, PROGRESSION_FUNCTIONS["uplifting"])


def build_harmonic_state(bar_index, progression_name, chord, progression_family: str = ""):
    function_cycle = resolve_progression_function_cycle(progression_name, progression_family)
    function_name = function_cycle[bar_index % len(function_cycle)]
    intent = HARMONIC_INTENT[function_name]
    tone_map = {
        "root": chord["root"],
        "third": chord["third"],
        "fifth": chord["fifth"],
    }
    primary_pitches = [tone_map[name] for name in intent["primary_targets"]]
    secondary_pitches = [tone_map[name] for name in intent["secondary_targets"]]
    return {
        "function": function_name,
        "emotion": intent["emotion"],
        "primary_pitches": primary_pitches,
        "secondary_pitches": secondary_pitches,
        "allow_tension": intent["allow_tension"],
    }


def harmonic_target_pool(harmonic_state, octave_shift=12):
    primary = [p + octave_shift for p in harmonic_state["primary_pitches"]]
    secondary = [p + octave_shift for p in harmonic_state["secondary_pitches"]]
    return {
        "primary": primary,
        "secondary": secondary,
    }


def pick_harmonic_target(harmonic_state, preference="primary", octave_shift=12):
    pool = harmonic_target_pool(harmonic_state, octave_shift)
    choices = pool["primary"] if preference == "primary" else pool["secondary"] or pool["primary"]
    return random.choice(choices)


def build_lead_bar_from_harmonic_state(rhythm_pattern, harmonic_state, register_range, emphasis="primary"):
    notes = []
    pool = harmonic_target_pool(harmonic_state, octave_shift=12)
    target_pool = pool["primary"] if emphasis == "primary" else pool["secondary"] or pool["primary"]
    for idx, beat in enumerate(rhythm_pattern):
        pitch = clamp(random.choice(target_pool), register_range[0], register_range[1])
        length = 0.5 if idx < 2 else 0.75
        notes.append((beat, length, pitch))
    return notes


def build_supersaw_voicing_from_harmonic_state(chord, harmonic_state, max_pitch=84):
    function_name = harmonic_state["function"]
    if function_name == "I":
        voicing = [chord["root"], chord["fifth"], chord["root"] + 12]
    elif function_name == "V":
        voicing = [chord["root"], chord["third"], chord["fifth"]]
    elif function_name == "vi":
        voicing = [chord["root"], chord["third"], chord["fifth"], chord["third"] + 12]
    elif function_name == "IV":
        voicing = [chord["root"], chord["fifth"], chord["third"] + 12]
    else:
        voicing = [chord["root"], chord["third"], chord["fifth"]]
    return clamp_supersaw_register(voicing, max_pitch=max_pitch)


def build_supersaw_voicing(chord, role):
    base_notes = list(chord.get("tones", chord.get("notes", [chord["root"], chord["third"], chord["fifth"]])))
    if role == "controlled":
        return sorted(dict.fromkeys([
            chord["root"] - 12,
            chord["fifth"] - 12,
            chord["root"],
            chord["third"],
            chord["fifth"],
            chord["root"] + 12,
        ]))
    return build_uplifting_supersaw_voicing(chord)


def build_uplifting_supersaw_voicing(chord):
    root = chord["root"]
    third = chord["third"]
    fifth = chord["fifth"]
    fifth_lift = root + 7
    return sorted(dict.fromkeys([
        root - 12,
        fifth - 12,
        root,
        third,
        fifth_lift,
        fifth + 12,
        root + 12,
        third + 12,
    ]))


def get_register_span(notes):
    return max(notes) - min(notes) if notes else 0


def get_supersaw_rhythm(role):
    return [0.0, 2.0] if role == "controlled" else [0.0, 1.0]


def get_supersaw_length(role):
    return 1.25 if role == "controlled" else 3.0


def get_supersaw_drop_role(is_second_pass: bool):
    return "expanded" if is_second_pass else "controlled"


def ensure_supersaw_register_span(notes, role, min_span=18):
    widened = sorted(dict.fromkeys(notes))
    if role != "expanded" or not widened:
        return widened
    while get_register_span(widened) < min_span:
        low = min(widened)
        high = max(widened)
        candidate = high + 12 if high + 12 <= 88 else low - 12
        widened.append(candidate)
        widened = sorted(dict.fromkeys(widened))
        if min(widened) < 36 or max(widened) > 88:
            break
    return sorted(dict.fromkeys(widened))


def ensure_supersaw_min_note_count(notes, min_count=6, max_pitch=88):
    dense = sorted(dict.fromkeys(notes))
    if not dense:
        return dense
    source = list(dense)
    layers = (12, -12, 7, -7, 24)
    while len(dense) < min_count:
        changed = False
        for pitch in source:
            for interval in layers:
                candidate = pitch + interval
                while candidate > max_pitch:
                    candidate -= 12
                if 36 <= candidate <= max_pitch and candidate not in dense:
                    dense.append(candidate)
                    dense = sorted(dense)
                    changed = True
                    if len(dense) >= min_count:
                        return dense
        if not changed:
            break
        source = list(dense)
    return sorted(dict.fromkeys(dense))


def spread_supersaw_voicing(notes, min_distance=5, max_pitch=88):
    spaced = []
    for pitch in sorted(dict.fromkeys(notes)):
        candidate = pitch
        while any(abs(candidate - existing) < min_distance for existing in spaced) and candidate + 12 <= max_pitch:
            candidate += 12
        while candidate > max_pitch:
            candidate -= 12
        if candidate not in spaced:
            spaced.append(candidate)
    return sorted(dict.fromkeys(spaced))


def upper_octave_ratio(notes, threshold=72):
    if not notes:
        return 0.0
    return sum(1 for pitch in notes if pitch >= threshold) / len(notes)


def ensure_supersaw_upper_ratio(notes, min_ratio=0.4, threshold=72, max_pitch=88):
    lifted = sorted(dict.fromkeys(notes))
    if not lifted:
        return lifted
    while upper_octave_ratio(lifted, threshold=threshold) < min_ratio:
        low_candidates = [pitch for pitch in lifted if pitch < threshold and pitch + 12 <= max_pitch and pitch + 12 not in lifted]
        if not low_candidates:
            break
        source = low_candidates[0]
        lifted.remove(source)
        lifted.append(source + 12)
        lifted = sorted(dict.fromkeys(lifted))
    return lifted


def vary_supersaw_voicing_for_drop2(notes, chord, bar_offset, max_pitch=88):
    varied = sorted(dict.fromkeys(notes))
    if not varied:
        return varied
    variation_slot = (bar_offset // 2) % 3
    if variation_slot == 1:
        mid_candidates = [pitch for pitch in varied if chord["root"] <= pitch < chord["root"] + 12 and pitch + 12 <= max_pitch]
        if mid_candidates:
            source = mid_candidates[0]
            varied.remove(source)
            varied.append(source + 12)
    elif variation_slot == 2:
        low_candidates = [pitch for pitch in varied if pitch < chord["root"] and pitch + 12 <= max_pitch]
        if low_candidates:
            varied.append(low_candidates[-1] + 12)
    varied = ensure_supersaw_upper_ratio(varied, min_ratio=0.4, threshold=chord["root"] + 12, max_pitch=max_pitch)
    varied = ensure_supersaw_min_note_count(varied, min_count=6, max_pitch=max_pitch)
    return sorted(dict.fromkeys(varied))


def build_supersaw_drop_voicing(chord, role):
    notes = build_supersaw_voicing(chord, role)
    max_pitch = 88 if role == "expanded" else 84
    if role == "expanded":
        notes = spread_supersaw_voicing(notes, min_distance=5, max_pitch=max_pitch)
        notes = ensure_supersaw_upper_ratio(notes, min_ratio=0.4, threshold=chord["root"] + 12, max_pitch=max_pitch)
        notes = ensure_supersaw_min_note_count(notes, min_count=6, max_pitch=max_pitch)
    notes = ensure_supersaw_register_span(notes, role, min_span=18)
    notes = clamp_supersaw_register(notes, max_pitch=max_pitch)
    if role == "expanded":
        notes = spread_supersaw_voicing(notes, min_distance=5, max_pitch=max_pitch)
        notes = ensure_supersaw_upper_ratio(notes, min_ratio=0.4, threshold=chord["root"] + 12, max_pitch=max_pitch)
        notes = ensure_supersaw_min_note_count(notes, min_count=6, max_pitch=max_pitch)
    return sorted(dict.fromkeys(notes))


def supersaw_internal_movement_pitch(chord, voicing, bar_offset, max_pitch=88):
    movement_targets = [chord["fifth"] + 12, chord["root"] + 12, chord["third"] + 12]
    target = movement_targets[(bar_offset // 2) % len(movement_targets)]
    while target > max_pitch:
        target -= 12
    if target in voicing:
        alternative = target + 12 if target + 12 <= max_pitch else target - 12
        if alternative >= 48:
            target = alternative
    return clamp(target, 48, max_pitch)


def avg_note_length(notes):
    return sum(length_beats(note_data) for note_data in notes) / max(1, len(notes))


def build_supersaw_section_notes(start_bar, end_bar, chords, role):
    notes = []
    velocity = 96 if role == "controlled" else 112
    for bar_index in range(start_bar, end_bar):
        bar_offset = bar_index - start_bar
        chord = chords[bar_index % len(chords)]
        voicing = build_supersaw_drop_voicing(chord, role)
        if role == "expanded":
            voicing = vary_supersaw_voicing_for_drop2(voicing, chord, bar_offset)
        length = get_supersaw_length(role)
        for beat_pos in get_supersaw_rhythm(role):
            start = bar_tick(bar_index) + tick(beat_pos)
            if role == "expanded":
                end = start + tick(length + 0.25)
            else:
                end = min(bar_tick(bar_index + 1), start + tick(length))
            notes.extend({
                "start": start,
                "end": end,
                "pitch": pitch,
                "velocity": velocity,
                "channel": 0,
            } for pitch in voicing)
            if role == "expanded":
                movement_start = start + tick(1.5)
                movement_pitch = supersaw_internal_movement_pitch(chord, voicing, bar_offset)
                notes.append({
                    "start": movement_start,
                    "end": end,
                    "pitch": movement_pitch,
                    "velocity": max(1, velocity - 8),
                    "channel": 0,
                })
    return sorted(notes, key=lambda item: (item["start"], item["pitch"]))


def supersaw_drop_stats(notes):
    event_counts = {}
    event_pitches = {}
    event_ends = {}
    for note_data in notes:
        event_counts.setdefault(note_data["start"], 0)
        event_counts[note_data["start"]] += 1
        event_pitches.setdefault(note_data["start"], [])
        event_pitches[note_data["start"]].append(note_data["pitch"])
        event_ends[note_data["start"]] = max(event_ends.get(note_data["start"], 0), note_data["end"])
    chord_event_density = [count for count in event_counts.values() if count >= 6]
    event_density = chord_event_density or list(event_counts.values())
    pitches = [note_data["pitch"] for note_data in notes]
    ordered_starts = sorted(event_ends)
    overlap_count = 0
    for idx, start in enumerate(ordered_starts[:-1]):
        if event_ends[start] > ordered_starts[idx + 1]:
            overlap_count += 1
    chord_signatures = {
        tuple(sorted(pitches_for_event))
        for start, pitches_for_event in event_pitches.items()
        if event_counts.get(start, 0) >= 6
    }
    return {
        "note_count": len(notes),
        "span": get_register_span(pitches),
        "avg_length": round(avg_note_length(notes), 3),
        "min_event_count": min(event_density, default=0),
        "avg_event_count": round(sum(event_density) / max(1, len(event_density)), 2),
        "upper_ratio": round(upper_octave_ratio(pitches), 3),
        "avg_pitch": round(sum(pitches) / max(1, len(pitches)), 2),
        "variation_count": max(0, len(chord_signatures) - 1),
        "overlap_ratio": round(overlap_count / max(1, len(ordered_starts) - 1), 3),
    }


def score_drop_upgrade(drop1_notes, drop2_notes):
    score = 0
    drop1_stats = supersaw_drop_stats(drop1_notes)
    drop2_stats = supersaw_drop_stats(drop2_notes)
    if drop2_stats["note_count"] >= drop1_stats["note_count"] * 1.3:
        score += 10
    if drop2_stats["span"] >= drop1_stats["span"] * 1.2:
        score += 10
    if drop2_stats["avg_length"] > drop1_stats["avg_length"]:
        score += 10
    return score


def score_supersaw_weight(drop1_notes, drop2_notes):
    score = score_drop_upgrade(drop1_notes, drop2_notes)
    drop2_stats = supersaw_drop_stats(drop2_notes)
    if drop2_stats["min_event_count"] >= 6:
        score += 10
    if drop2_stats["avg_length"] >= 2.0:
        score += 10
    return score


def score_supersaw_voicing(drop1_notes, drop2_notes):
    score = 0
    drop1_stats = supersaw_drop_stats(drop1_notes)
    drop2_stats = supersaw_drop_stats(drop2_notes)
    if drop2_stats["avg_pitch"] > drop1_stats["avg_pitch"]:
        score += 10
    if drop2_stats["upper_ratio"] >= 0.3:
        score += 10
    if drop2_stats["span"] > drop1_stats["span"]:
        score += 10
    if drop2_stats["avg_event_count"] > drop1_stats["avg_event_count"]:
        score += 10
    return score


def score_supersaw_dynamic(drop1_notes, drop2_notes):
    score = 0
    drop1_stats = supersaw_drop_stats(drop1_notes)
    drop2_stats = supersaw_drop_stats(drop2_notes)
    if drop2_stats["variation_count"] > 0:
        score += 10
    if drop2_stats["overlap_ratio"] > 0:
        score += 10
    if drop2_stats["avg_pitch"] > drop1_stats["avg_pitch"]:
        score += 10
    if drop2_stats["avg_length"] > drop1_stats["avg_length"]:
        score += 10
    return score


def apply_drop2_supersaw_dominance(note_tracks, drop2_section):
    start_bar = drop2_section["start_bar"]
    end_bar = drop2_section["end_bar"]

    lead_reduced = []
    for note_data in note_tracks["lead"]:
        fixed = dict(note_data)
        if bar_tick(start_bar) <= fixed["start"] < bar_tick(end_bar):
            fixed["velocity"] = max(1, fixed["velocity"] - 15)
        lead_reduced.append(fixed)
    note_tracks["lead"] = sorted(lead_reduced, key=lambda item: (item["start"], item["pitch"]))

    for bar_index in range(start_bar, end_bar):
        arp_bar = sorted(notes_starting_in_bar(note_tracks["arp"], bar_index), key=lambda item: (item["start"], item["pitch"]))
        if len(arp_bar) > 1:
            keep_count = max(1, (len(arp_bar) + 1) // 2)
            note_tracks["arp"] = replace_notes_in_bar_range(note_tracks["arp"], bar_index, bar_index + 1, arp_bar[:keep_count])
        note_tracks["pluck"] = remove_notes_in_bar_range(note_tracks["pluck"], bar_index, bar_index + 1)


def repair_drop1_lead_balance(note_tracks, drop1_section, chords):
    start_bar = drop1_section["start_bar"]
    end_bar = drop1_section["end_bar"]
    repairs = 0
    for bar_index in range(start_bar, end_bar):
        chord = chords[bar_index % len(chords)]
        bar_notes = sorted(notes_starting_in_bar(note_tracks["lead"], bar_index), key=lambda item: (item["start"], item["pitch"]))
        fixed_bar = []
        for note_data in bar_notes[:2]:
            fixed = dict(note_data)
            min_end = fixed["start"] + tick(0.75)
            if fixed["end"] < min_end:
                fixed["end"] = min(min_end, bar_tick(bar_index + 1))
                repairs += 1
            fixed_bar.append(fixed)
        if not fixed_bar:
            fixed_bar.append({
                "start": bar_tick(bar_index),
                "end": bar_tick(bar_index) + tick(1.0),
                "pitch": clamp(chord["root"] + 12, 60, 86),
                "velocity": 92,
                "channel": 0,
            })
            repairs += 1
        elif not any(length_beats(note) >= 0.75 for note in fixed_bar):
            fixed_bar[0]["end"] = min(bar_tick(bar_index + 1), fixed_bar[0]["start"] + tick(0.75))
            repairs += 1
        if len(bar_notes) > len(fixed_bar):
            repairs += len(bar_notes) - len(fixed_bar)
        note_tracks["lead"] = replace_notes_in_bar_range(note_tracks["lead"], bar_index, bar_index + 1, fixed_bar)
    return repairs


def score_drop_balance(drop1_saw_notes, drop2_saw_notes, drop1_lead_notes):
    drop1_stats = supersaw_drop_stats(drop1_saw_notes)
    drop2_stats = supersaw_drop_stats(drop2_saw_notes)
    density_ratio = drop1_stats["note_count"] / max(1, drop2_stats["note_count"])
    score = 0
    if density_ratio >= 0.7:
        score += 10
    if drop1_stats["avg_length"] >= 1.25:
        score += 10
    if drop1_stats["span"] >= 18:
        score += 10
    if drop2_stats["avg_length"] > drop1_stats["avg_length"] and drop2_stats["span"] >= drop1_stats["span"]:
        score += 10
    if drop1_lead_notes and avg_note_length(drop1_lead_notes) >= 0.75:
        score += 10
    return score


def remove_pre_drop_tail(notes, drop_start_bar, gap_beats=0.5):
    gap_start = bar_tick(drop_start_bar) - tick(gap_beats)
    drop_start_tick = bar_tick(drop_start_bar)
    return [
        note for note in notes
        if not (
            note["start"] < drop_start_tick
            and note["end"] > gap_start
            and note["start"] >= bar_tick(max(0, drop_start_bar - 1))
        )
    ]


def force_drop1_first_hit(note_tracks, drop1_section, chords):
    drop_start = drop1_section["start_bar"]
    chord = chords[drop_start % len(chords)]
    first_hit_voicing = sorted(dict.fromkeys([
        chord["root"] - 12,
        chord["root"],
        chord["third"],
        chord["fifth"],
        chord["root"] + 12,
    ]))
    saw_notes = [{
        "start": bar_tick(drop_start),
        "end": bar_tick(drop_start) + tick(1.5),
        "pitch": clamp(pitch, 48, 88),
        "velocity": 108,
        "channel": 0,
    } for pitch in first_hit_voicing]
    note_tracks["supersaw_chords"] = replace_notes_in_bar_range(note_tracks["supersaw_chords"], drop_start, drop_start + 1, saw_notes)

    lead_pitch = clamp(max(chord["root"] + 12, chord["third"] + 12), 66, 86)
    lead_note = {
        "start": bar_tick(drop_start),
        "end": bar_tick(drop_start) + tick(1.75),
        "pitch": lead_pitch,
        "velocity": 104,
        "channel": 0,
    }
    note_tracks["lead"] = replace_notes_in_bar_range(note_tracks["lead"], drop_start, drop_start + 1, [lead_note])


def build_drop1_hook_notes(drop1_section, chords):
    drop_start = drop1_section["start_bar"]
    phrase_notes = []
    for pair_offset in (0, 2):
        chord_a = chords[(drop_start + pair_offset) % len(chords)]
        chord_b = chords[(drop_start + pair_offset + 1) % len(chords)]
        if pair_offset == 0:
            opening_pitch = clamp(chord_a["root"] + 12, 64, 86)
            response_pitch = clamp(chord_a["third"] + 12, 64, 86)
            resolve_pitch = clamp(chord_b["fifth"] + 12, 64, 86)
        else:
            opening_pitch = clamp(chord_a["third"] + 12, 64, 86)
            response_pitch = clamp(chord_a["fifth"] + 12, 64, 86)
            resolve_pitch = clamp(chord_b["root"] + 12, 64, 86)
        phrase_notes.extend([
            {
                "start": bar_tick(drop_start + pair_offset),
                "end": bar_tick(drop_start + pair_offset) + tick(1.75),
                "pitch": opening_pitch,
                "velocity": 106 if pair_offset == 0 else 102,
                "channel": 0,
            },
            {
                "start": bar_tick(drop_start + pair_offset) + tick(2.5),
                "end": bar_tick(drop_start + pair_offset) + tick(3.25),
                "pitch": response_pitch,
                "velocity": 96,
                "channel": 0,
            },
            {
                "start": bar_tick(drop_start + pair_offset + 1),
                "end": bar_tick(drop_start + pair_offset + 1) + tick(1.75),
                "pitch": resolve_pitch,
                "velocity": 104 if pair_offset == 0 else 100,
                "channel": 0,
            },
        ])
    return sorted(phrase_notes, key=lambda item: (item["start"], item["pitch"]))


def apply_drop1_hook_engine(note_tracks, drop_sections, chords):
    if not drop_sections:
        return {"drop1_hook_repairs": 0}
    drop1 = drop_sections[0]
    hook_notes = build_drop1_hook_notes(drop1, chords)
    note_tracks["lead"] = replace_notes_in_bar_range(note_tracks["lead"], drop1["start_bar"], min(drop1["end_bar"], drop1["start_bar"] + 4), hook_notes)
    return {"drop1_hook_repairs": 1}


def drop1_hook_metrics(note_tracks, sections):
    drop1 = next((section for section in sections if section["name"] == "Drop 1"), None)
    if not drop1:
        return {
            "drop1_hook_note_count": 0,
            "drop1_hook_avg_length": 0,
            "drop1_hook_repeat_score": 0,
            "drop1_hook_strength": 0,
        }
    start_bar = drop1["start_bar"]
    hook_notes = [note for offset in range(4) for note in notes_starting_in_bar(note_tracks["lead"], start_bar + offset)]
    bars_1_2 = [note for offset in range(2) for note in notes_starting_in_bar(note_tracks["lead"], start_bar + offset)]
    bars_3_4 = [note for offset in range(2, 4) for note in notes_starting_in_bar(note_tracks["lead"], start_bar + offset)]
    first_note = min(hook_notes, key=lambda item: item["start"], default=None)
    signature_a = rhythm_pattern_signature(note_tracks["lead"], start_bar, bars=2, step=0.25)
    signature_b = rhythm_pattern_signature(note_tracks["lead"], start_bar + 2, bars=2, step=0.25)
    repeat_score = 10 if signature_a == signature_b and signature_a else 0
    avg_length = round(avg_note_length(hook_notes), 2)
    score = 0
    if first_note and first_note["start"] == bar_tick(start_bar) and length_beats(first_note) >= 1.5:
        score += 10
    if len(bars_1_2) <= 3 and len(bars_3_4) <= 3:
        score += 10
    if avg_length >= 1.25:
        score += 10
    if repeat_score:
        score += 10
    if hook_notes and sum(1 for note in hook_notes if length_beats(note) >= 1.5) >= 4:
        score += 10
    return {
        "drop1_hook_note_count": len(hook_notes),
        "drop1_hook_avg_length": avg_length,
        "drop1_hook_repeat_score": repeat_score,
        "drop1_hook_strength": score,
    }


def generate_hook(harmonic_context):
    chord = harmonic_context["chord"]
    register_low, register_high = harmonic_context.get("register_range", (64, 88))
    root = clamp(chord["root"] + 12, register_low, register_high)
    third = clamp(chord["third"] + 12, register_low, register_high)
    leap_target = third + 7
    fifth = clamp(leap_target if leap_target <= register_high else chord["fifth"] + 12, register_low, register_high)
    return [
        (0.0, 1.25, root),
        (2.0, 0.5, third),
        (3.0, 2.0, fifth),
    ]


def generate_hook_candidates(harmonic_context):
    chord = harmonic_context["chord"]
    register_low, register_high = harmonic_context.get("register_range", (64, 88))
    tones = {
        "root": clamp(chord["root"] + 12, register_low, register_high),
        "third": clamp(chord["third"] + 12, register_low, register_high),
        "fifth": clamp(chord["fifth"] + 12, register_low, register_high),
        "upper_root": clamp(chord["root"] + 24, register_low, register_high),
        "upper_third": clamp(chord["third"] + 24, register_low, register_high),
    }
    raw_candidates = [
        ("root_third_peak", [(0.0, 1.25, tones["root"]), (2.0, 0.5, tones["third"]), (3.0, 2.0, clamp(tones["third"] + 7, register_low, register_high))]),
        ("third_root_peak", [(0.0, 1.25, tones["third"]), (2.0, 0.5, tones["root"]), (3.0, 2.0, clamp(tones["root"] + 7, register_low, register_high))]),
        ("root_fifth_peak", [(0.0, 1.25, tones["root"]), (2.0, 0.5, tones["fifth"]), (3.0, 2.0, tones["upper_root"])]),
        ("third_fifth_peak", [(0.0, 1.25, tones["third"]), (2.0, 0.5, tones["fifth"]), (3.0, 2.0, tones["upper_third"])]),
        ("fifth_third_peak", [(0.0, 1.25, tones["fifth"]), (2.0, 0.5, tones["third"]), (3.0, 2.0, tones["upper_root"])]),
    ]
    candidates = []
    for variation_type, hook in raw_candidates:
        normalized = [(beat, length, clamp(pitch, register_low, register_high)) for beat, length, pitch in hook]
        if validate_hook(normalized):
            candidates.append({"variation_type": variation_type, "hook": normalized, "score": score_hook_candidate(normalized)})
    return candidates


def score_hook_candidate(hook):
    score = 0
    jump = hook_interval_jump(hook)
    range_size = hook_range(hook)
    dominance = hook_dominance_ratio(hook)
    if jump in (3, 5, 7):
        score += 20
    if dominance > 1.25:
        score += 20
    if 5 <= range_size <= 12:
        score += 20
    elif 3 <= range_size <= 12:
        score += 10
    if hook_peak_event(hook) == hook[-1]:
        score += 20
    if hook_pre_peak_silence(hook) >= 0.25:
        score += 10
    if len(hook) <= 3:
        score += 10
    return score


def select_best_hook(harmonic_context):
    candidates = generate_hook_candidates(harmonic_context)
    if not candidates:
        fallback = generate_hook(harmonic_context)
        return {"hook": fallback, "score": score_hook_candidate(fallback), "variation_type": "fallback", "candidate_count": 1}
    selected = max(candidates, key=lambda item: (item["score"], hook_peak_note(item["hook"]), hook_range(item["hook"])))
    return {
        "hook": selected["hook"],
        "score": selected["score"],
        "variation_type": selected["variation_type"],
        "candidate_count": len(candidates),
    }


def hook_interval_jump(hook):
    pitches = [pitch for _beat, _length, pitch in hook]
    jumps = [right - left for left, right in zip(pitches, pitches[1:])]
    expressive = [jump for jump in jumps if jump in (3, 5, 7)]
    return expressive[0] if expressive else 0


def hook_range(hook):
    pitches = [pitch for _beat, _length, pitch in hook]
    return max(pitches, default=0) - min(pitches, default=0)


def hook_peak_note(hook):
    if not hook:
        return 0
    return max(pitch for _beat, _length, pitch in hook)


def hook_peak_event(hook):
    if not hook:
        return None
    return max(hook, key=lambda item: (item[2], item[1], item[0]))


def hook_peak_length(hook):
    peak = hook_peak_event(hook)
    return round(peak[1], 2) if peak else 0


def hook_pre_peak_silence(hook):
    peak = hook_peak_event(hook)
    if not peak:
        return 0
    peak_start = peak[0]
    previous_ends = [beat + length for beat, length, pitch in hook if beat < peak_start]
    if not previous_ends:
        return round(peak_start, 2)
    return round(peak_start - max(previous_ends), 2)


def hook_dominance_ratio(hook):
    if not hook:
        return 0
    peak_len = hook_peak_length(hook)
    other_lengths = [length for beat, length, pitch in hook if (beat, length, pitch) != hook_peak_event(hook)]
    return round(peak_len / max(0.01, sum(other_lengths) / max(1, len(other_lengths))), 3)


def validate_hook(hook):
    if len(hook) > 4:
        return False
    if not any(length >= 1.5 for _beat, length, _pitch in hook):
        return False
    if sum(1 for _beat, length, _pitch in hook if length < 0.5) > 0:
        return False
    if hook_interval_jump(hook) == 0:
        return False
    if hook_range(hook) > 12:
        return False
    max_pitch = hook_peak_note(hook)
    peak_events = [(beat, length, pitch) for beat, length, pitch in hook if pitch == max_pitch]
    if not peak_events or not any(beat >= 3.0 and length >= 1.75 for beat, length, pitch in peak_events):
        return False
    if hook_peak_length(hook) < max(length for _beat, length, _pitch in hook):
        return False
    if not 0.25 <= hook_pre_peak_silence(hook) <= 0.75:
        return False
    if hook_dominance_ratio(hook) <= 1.25:
        return False
    return bool(hook)


def adapt_hook_for_section(hook, section_name):
    if "Drop 2" in section_name:
        return [(beat, length + (0.25 if length >= 1.5 else 0.0), clamp(pitch + 5, 64, 92)) for beat, length, pitch in hook]
    if "Breakdown" in section_name:
        return [(beat, max(1.5, length), clamp(pitch - 12, 56, 82)) for beat, length, pitch in hook if length >= 1.5]
    return list(hook)


def hook_notes_for_section(section, chords, selected_hook=None):
    start_bar = section["start_bar"]
    chord = chords[start_bar % len(chords)]
    hook = selected_hook or generate_hook({"chord": chord, "register_range": (64, 88)})
    if not validate_hook(hook):
        return []
    adapted = adapt_hook_for_section(hook, section["name"])
    notes = []
    repeat_bars = min(section["end_bar"], start_bar + (4 if section_kind(section["name"]) == "drop" else 2))
    for phrase_start in range(start_bar, repeat_bars, 2):
        bar_start = bar_tick(phrase_start)
        for beat, length, pitch in adapted:
            notes.append({
                "start": bar_start + tick(beat),
                "end": bar_start + tick(beat + length),
                "pitch": clamp(pitch, 52, 96),
                "velocity": 104 if section_kind(section["name"]) == "drop" else 82,
                "channel": 0,
            })
    return sorted(notes, key=lambda item: (item["start"], item["pitch"]))


def apply_hook_engine(note_tracks, sections, chords):
    metrics = {
        "hook_note_count": 0,
        "hook_avg_length": 0,
        "hook_repeat_usage": 0,
        "hook_sections_applied": "",
        "hook_strength_score": 0,
        "hook_interval_jump": 0,
        "hook_peak_note": 0,
        "hook_range": 0,
        "hook_emotion_score": 0,
        "hook_peak_length": 0,
        "hook_pre_peak_silence": 0,
        "hook_peak_emphasis_score": 0,
        "hook_dominance_ratio": 0,
        "hook_candidates_generated": 0,
        "hook_selected_score": 0,
        "hook_variation_type": "",
    }
    if not HOOK_MODE:
        return metrics
    applied_sections = []
    all_hook_notes = []
    selected_hook_result = None
    for section in sections:
        if section["name"] not in ("Drop 1", "Drop 2", "Breakdown"):
            continue
        if selected_hook_result is None:
            selected_hook_result = select_best_hook({"chord": chords[section["start_bar"] % len(chords)], "register_range": (64, 88)})
        hook_notes = hook_notes_for_section(section, chords, selected_hook=selected_hook_result["hook"])
        if not hook_notes:
            continue
        replace_end = min(section["end_bar"], section["start_bar"] + (4 if section_kind(section["name"]) == "drop" else 2))
        note_tracks["lead"] = replace_notes_in_bar_range(note_tracks["lead"], section["start_bar"], replace_end, hook_notes)
        applied_sections.append(section["name"])
        all_hook_notes.extend(hook_notes)
    if not all_hook_notes:
        return metrics
    metrics["hook_note_count"] = len(all_hook_notes)
    metrics["hook_avg_length"] = round(avg_note_length(all_hook_notes), 2)
    metrics["hook_repeat_usage"] = sum(1 for name in applied_sections if "Drop" in name)
    metrics["hook_sections_applied"] = ",".join(applied_sections)
    score = 0
    if metrics["hook_note_count"] <= 18:
        score += 10
    if metrics["hook_avg_length"] >= 1.0:
        score += 10
    if metrics["hook_repeat_usage"] >= 2:
        score += 10
    if "Breakdown" in applied_sections:
        score += 10
    if all(length_beats(note) >= 0.75 for note in all_hook_notes):
        score += 10
    metrics["hook_strength_score"] = score
    source_hook = selected_hook_result["hook"] if selected_hook_result else []
    metrics["hook_candidates_generated"] = selected_hook_result["candidate_count"] if selected_hook_result else 0
    metrics["hook_selected_score"] = selected_hook_result["score"] if selected_hook_result else 0
    metrics["hook_variation_type"] = selected_hook_result["variation_type"] if selected_hook_result else ""
    metrics["hook_interval_jump"] = hook_interval_jump(source_hook)
    metrics["hook_peak_note"] = hook_peak_note(source_hook)
    metrics["hook_range"] = hook_range(source_hook)
    metrics["hook_peak_length"] = hook_peak_length(source_hook)
    metrics["hook_pre_peak_silence"] = hook_pre_peak_silence(source_hook)
    metrics["hook_dominance_ratio"] = hook_dominance_ratio(source_hook)
    emotion_score = 0
    if metrics["hook_interval_jump"] in (3, 5, 7):
        emotion_score += 10
    if metrics["hook_peak_note"] and source_hook and source_hook[-1][2] == metrics["hook_peak_note"] and source_hook[-1][1] >= 1.5:
        emotion_score += 10
    if 3 <= metrics["hook_range"] <= 12:
        emotion_score += 10
    if len(source_hook) <= 4:
        emotion_score += 10
    metrics["hook_emotion_score"] = emotion_score
    peak_score = 0
    if metrics["hook_peak_length"] >= 1.75:
        peak_score += 10
    if 0.25 <= metrics["hook_pre_peak_silence"] <= 0.75:
        peak_score += 10
    if metrics["hook_dominance_ratio"] > 1.25:
        peak_score += 10
    if source_hook and source_hook[-1][2] == metrics["hook_peak_note"]:
        peak_score += 10
    metrics["hook_peak_emphasis_score"] = peak_score
    return metrics


MELODIC_CLEANUP_STEMS = (
    "lead",
    "supersaw_chords",
    "pad",
    "arp",
    "pluck",
    "strings",
    "piano",
    "countermelody",
    "vocal_melody",
)


def global_note_cleanup(note_tracks):
    metrics = {
        "global_note_cleanup_removed": 0,
        "global_note_cleanup_extended": 0,
        "global_melodic_avg_note_length": 0,
    }
    all_lengths = []
    preserve_short_stems = {"arp", "pluck"}
    for stem in MELODIC_CLEANUP_STEMS:
        cleaned = []
        for note_data in sorted(note_tracks[stem], key=lambda item: (item["start"], item["pitch"])):
            fixed = dict(note_data)
            note_len = length_beats(fixed)
            if note_len < 0.5 and stem not in preserve_short_stems:
                metrics["global_note_cleanup_removed"] += 1
                continue
            min_length = 0.5 if stem in preserve_short_stems and note_len < 0.5 else 0.75
            if length_beats(fixed) < min_length:
                fixed["end"] = max(fixed["end"], fixed["start"] + tick(min_length))
                metrics["global_note_cleanup_extended"] += 1
            cleaned.append(fixed)
        avg_len = avg_note_length(cleaned)
        if cleaned and avg_len < 0.75:
            adjusted = []
            for note_data in cleaned:
                fixed = dict(note_data)
                if length_beats(fixed) < 0.75:
                    fixed["end"] = max(fixed["end"], fixed["start"] + tick(0.75))
                    metrics["global_note_cleanup_extended"] += 1
                adjusted.append(fixed)
            cleaned = adjusted
        note_tracks[stem] = sorted(cleaned, key=lambda item: (item["start"], item["pitch"]))
        all_lengths.extend(length_beats(note_data) for note_data in note_tracks[stem])
    metrics["global_melodic_avg_note_length"] = round(sum(all_lengths) / max(1, len(all_lengths)), 3)
    return metrics


def apply_drop1_impact_engine(note_tracks, drop_sections, chords):
    if not drop_sections:
        return {"drop1_impact_repairs": 0}
    drop1 = drop_sections[0]
    drop_start = drop1["start_bar"]
    repairs = 0
    for lane in ("lead", "supersaw_chords", "arp", "pluck", "strings", "piano", "countermelody", "vocal_melody"):
        before = len(note_tracks[lane])
        note_tracks[lane] = remove_pre_drop_tail(note_tracks[lane], drop_start, gap_beats=0.5)
        repairs += max(0, before - len(note_tracks[lane]))
    force_drop1_first_hit(note_tracks, drop1, chords)
    return {"drop1_impact_repairs": repairs + 2}


def drop1_impact_metrics(note_tracks, sections):
    drop1 = next((section for section in sections if section["name"] == "Drop 1"), None)
    if not drop1:
        return {
            "drop1_impact_score": 0,
            "drop1_first_hit_density": 0,
            "drop1_lead_entry_type": "missing",
            "drop1_has_gap": False,
        }
    drop_start = drop1["start_bar"]
    build_bar = max(0, drop_start - 1)
    first_saw = notes_starting_in_bar(note_tracks["supersaw_chords"], drop_start)
    first_lead = notes_starting_in_bar(note_tracks["lead"], drop_start)
    build_notes = []
    drop_notes = []
    for lane in ("lead", "supersaw_chords"):
        build_notes.extend(notes_starting_in_bar(note_tracks[lane], build_bar))
        drop_notes.extend(notes_starting_in_bar(note_tracks[lane], drop_start))
    gap_start = bar_tick(drop_start) - tick(0.5)
    drop_tick = bar_tick(drop_start)
    gap_has_notes = any(
        note["start"] < drop_tick and note["end"] > gap_start
        for lane in ("lead", "supersaw_chords", "arp", "pluck", "strings", "piano", "countermelody", "vocal_melody")
        for note in note_tracks[lane]
    )
    lead_entry_type = "long_single" if len(first_lead) == 1 and length_beats(first_lead[0]) >= 1.5 and first_lead[0]["start"] == drop_tick else "gradual"
    score = 0
    if len(first_saw) >= 5 and all(note["start"] == drop_tick for note in first_saw):
        score += 10
    if lead_entry_type == "long_single":
        score += 10
    if not gap_has_notes:
        score += 10
    if avg_note_length(drop_notes) > avg_note_length(build_notes):
        score += 10
    if get_register_span([note["pitch"] for note in drop_notes]) > get_register_span([note["pitch"] for note in build_notes]):
        score += 10
    if len(drop_notes) > len(build_notes):
        score += 10
    return {
        "drop1_impact_score": score,
        "drop1_first_hit_density": len(first_saw),
        "drop1_lead_entry_type": lead_entry_type,
        "drop1_has_gap": not gap_has_notes,
    }


def repair_supersaw_drop_energy(note_tracks, drop_sections, chords):
    if len(drop_sections) < 2:
        return {"score": 0, "repaired": False}
    drop1 = drop_sections[0]
    drop2 = drop_sections[1]
    original_drop1 = section_note_slice(note_tracks["supersaw_chords"], drop1["start_bar"], drop1["end_bar"])
    original_drop2 = section_note_slice(note_tracks["supersaw_chords"], drop2["start_bar"], drop2["end_bar"])
    original_score = score_drop_upgrade(original_drop1, original_drop2)
    controlled = build_supersaw_section_notes(drop1["start_bar"], drop1["end_bar"], chords, "controlled")
    expanded = build_supersaw_section_notes(drop2["start_bar"], drop2["end_bar"], chords, "expanded")
    note_tracks["supersaw_chords"] = replace_notes_in_bar_range(note_tracks["supersaw_chords"], drop1["start_bar"], drop1["end_bar"], controlled)
    note_tracks["supersaw_chords"] = replace_notes_in_bar_range(note_tracks["supersaw_chords"], drop2["start_bar"], drop2["end_bar"], expanded)
    apply_drop2_supersaw_dominance(note_tracks, drop2)
    score = score_drop_upgrade(controlled, expanded)
    changed = original_drop1 != controlled or original_drop2 != expanded
    return {"score": score, "repaired": changed or original_score < 20}


def build_pad_voicing_from_harmonic_state(chord, harmonic_state):
    function_name = harmonic_state["function"]
    if function_name == "I":
        return [chord["root"] - 12, chord["fifth"] - 12, chord["root"]]
    if function_name == "V":
        return [chord["third"] - 12, chord["fifth"] - 12, chord["root"]]
    if function_name == "vi":
        return [chord["root"] - 12, chord["third"], chord["fifth"]]
    if function_name == "IV":
        return [chord["root"] - 12, chord["fifth"], chord["third"]]
    return [chord["root"], chord["third"], chord["fifth"]]


HARMONIC_ARP_PATTERNS = {
    "home": [0.0, 1.0, 2.0, 3.0],
    "tension": [0.5, 1.5, 2.5, 3.5],
    "longing": [0.0, 0.5, 2.0, 2.5],
    "lift": [0.0, 1.5, 2.0, 3.0],
}


def build_arp_bar_from_harmonic_state(harmonic_state, register_low=60, register_high=78):
    pattern = HARMONIC_ARP_PATTERNS[harmonic_state["emotion"]]
    pool = harmonic_target_pool(harmonic_state, octave_shift=0)["primary"]
    notes = []
    for idx, beat in enumerate(pattern):
        pitch = clamp(pool[idx % len(pool)], register_low, register_high)
        notes.append((beat, 0.25, pitch))
    return notes


def build_pluck_bar_from_harmonic_state(harmonic_state):
    pool = harmonic_target_pool(harmonic_state, octave_shift=12)["primary"]
    return [
        (0.0, 0.3, pool[0]),
        (1.5, 0.3, pool[min(1, len(pool) - 1)]),
        (3.0, 0.3, pool[0]),
    ]


def build_strings_from_harmonic_state(chord, harmonic_state):
    function_name = harmonic_state["function"]
    if function_name == "I":
        return [chord["root"], chord["fifth"], chord["root"] + 12]
    if function_name == "V":
        return [chord["third"], chord["fifth"], chord["root"] + 12]
    if function_name == "vi":
        return [chord["third"], chord["fifth"], chord["third"] + 12]
    if function_name == "IV":
        return [chord["fifth"], chord["root"] + 12, chord["third"] + 12]
    return [chord["root"], chord["third"], chord["fifth"]]


def build_piano_hits_from_harmonic_state(harmonic_state, chord):
    function_name = harmonic_state["function"]
    if function_name == "I":
        return [(0.0, 1.0, [chord["root"], chord["fifth"]])]
    if function_name == "V":
        return [(0.0, 0.75, [chord["third"], chord["fifth"]]), (2.5, 0.75, [chord["root"]])]
    if function_name == "vi":
        return [(0.0, 1.0, [chord["third"], chord["fifth"]]), (2.0, 0.75, [chord["root"]])]
    if function_name == "IV":
        return [(0.0, 0.9, [chord["third"], chord["fifth"]]), (2.0, 0.9, [chord["root"]])]
    return [(0.0, 1.0, [chord["root"], chord["third"]])]


def get_breakdown_phrase_role(local_bar):
    pos = local_bar % 8
    if pos in (0, 1):
        return "motif"
    if pos in (2, 3):
        return "repeat_variation"
    if pos in (4, 5):
        return "develop"
    return "tension"


def breakdown_target(harmonic_state, preference="primary", octave_shift=12, register_low=60, register_high=84):
    pool = harmonic_target_pool(harmonic_state, octave_shift=octave_shift)
    choices = pool["primary"] if preference == "primary" else pool["secondary"] or pool["primary"]
    return clamp(choices[0], register_low, register_high)


def build_breakdown_piano_bar(chord, harmonic_state, role, local_bar=0):
    phrase_pos = local_bar % 8
    root_note = clamp(chord["root"] + 12, 60, 82)
    third_note = clamp(chord["third"] + 12, 60, 82)
    higher_note = clamp(max(third_note + 5, chord["fifth"] + 12), 64, 86)
    highest_note = clamp(max(chord["root"] + 24, chord["third"] + 24, chord["fifth"] + 12), 66, 88)
    if phrase_pos in (0, 1):
        return [(0.0, 2.0, root_note)]
    if phrase_pos in (2, 3):
        return [(0.0, 2.0, third_note)]
    if phrase_pos in (4, 5):
        return [(0.0, 2.0, higher_note)]
    return [(0.0, 3.0, highest_note)]


def build_breakdown_strings_bar(chord, harmonic_state, role, local_bar=0):
    phrase_pos = local_bar % 8
    if phrase_pos % 2 != 0:
        return []
    if phrase_pos < 4:
        return [(0.0, 8.0, [chord["root"] - 12, chord["fifth"] - 12, chord["third"]], 62)]
    if phrase_pos < 6:
        return [(0.0, 8.0, [chord["root"] - 12, chord["fifth"] - 12, chord["third"] + 12], 74)]
    lifted_top = clamp(chord["third"] + 17, 60, 91)
    return [(0.0, 8.0, [chord["root"] - 24, chord["fifth"] - 12, lifted_top], 84)]


def build_breakdown_emotion_section(start_bar, end_bar, chords, progression_name, progression_family):
    piano_notes = []
    strings_notes = []
    for bar_index in range(start_bar, end_bar):
        local_bar = bar_index - start_bar
        chord = chords[bar_index % len(chords)]
        harmonic_state = build_harmonic_state(bar_index, progression_name, chord, progression_family)
        phrase_role = get_breakdown_phrase_role(local_bar)
        bar_start = bar_tick(bar_index)
        piano_velocity = {"motif": 68, "repeat_variation": 70, "develop": 76, "tension": 84}[phrase_role]
        for beat_pos, beat_len, pitch in build_breakdown_piano_bar(chord, harmonic_state, phrase_role, local_bar=local_bar):
            piano_notes.append({"start": bar_start + tick(beat_pos), "end": bar_start + tick(beat_pos + beat_len), "pitch": clamp(pitch, 52, 88), "velocity": piano_velocity, "channel": 0})
        for beat_pos, beat_len, pitches, velocity in build_breakdown_strings_bar(chord, harmonic_state, phrase_role, local_bar=local_bar):
            for pitch in pitches:
                strings_notes.append({"start": bar_start + tick(beat_pos), "end": bar_start + tick(beat_pos + beat_len), "pitch": clamp(pitch, 43, 91), "velocity": velocity, "channel": 0})
    return (
        remove_bad_breakdown_piano_notes(
            enforce_breakdown_anchor_space(
                enforce_breakdown_piano_space(sorted(piano_notes, key=lambda item: (item["start"], item["pitch"])), start_bar, end_bar),
                start_bar,
                end_bar,
            ),
            start_bar,
            end_bar,
        ),
        remove_overlapping_breakdown_strings(sorted(strings_notes, key=lambda item: (item["start"], item["pitch"]))),
    )


def enforce_breakdown_piano_space(piano_notes, start_bar, end_bar):
    repaired = list(piano_notes)
    for block_start in range(start_bar, end_bar, 2):
        block_end_tick = bar_tick(min(end_bar, block_start + 2))
        block_start_tick = bar_tick(block_start)
        block_notes = [note for note in repaired if block_start_tick <= note["start"] < block_end_tick]
        total_beats = sum(max(0, min(note["end"], block_end_tick) - max(note["start"], block_start_tick)) for note in block_notes) / TICKS
        if total_beats > 7.0 and len(block_notes) > 2:
            lowest_priority = sorted(block_notes, key=lambda item: (length_beats(item), -item["start"]))[0]
            repaired.remove(lowest_priority)
    return sorted(repaired, key=lambda item: (item["start"], item["pitch"]))


def get_breakdown_anchor_note(piano_notes, start_bar, end_bar):
    final_notes = [
        note for note in piano_notes
        if bar_tick(max(start_bar, end_bar - 2)) <= note["start"] < bar_tick(end_bar)
        and length_beats(note) >= 1.5
    ]
    if not final_notes:
        return None
    return max(final_notes, key=lambda item: (length_beats(item), item["pitch"], item["start"]))


def breakdown_pre_anchor_silence(piano_notes, anchor):
    if not anchor:
        return 0.0
    previous = [note for note in piano_notes if note["end"] <= anchor["start"]]
    if not previous:
        return round((anchor["start"] % BAR_TICKS) / TICKS, 2)
    return round((anchor["start"] - max(note["end"] for note in previous)) / TICKS, 2)


def enforce_breakdown_anchor_space(piano_notes, start_bar, end_bar):
    anchor = get_breakdown_anchor_note(piano_notes, start_bar, end_bar)
    if not anchor:
        return piano_notes
    gap = tick(0.75)
    repaired = []
    for note in piano_notes:
        if note is anchor:
            repaired.append(note)
            continue
        if note["start"] < anchor["start"] and anchor["start"] - note["end"] < gap:
            continue
        if anchor["start"] <= note["start"] < min(bar_tick(end_bar), anchor["end"]):
            continue
        repaired.append(note)
    return sorted(repaired, key=lambda item: (item["start"], item["pitch"]))


def remove_bad_breakdown_piano_notes(piano_notes, start_bar, end_bar):
    cleaned = []
    for note in piano_notes:
        if not (bar_tick(start_bar) <= note["start"] < bar_tick(end_bar)):
            cleaned.append(note)
            continue
        if length_beats(note) < 0.75:
            continue
        cleaned.append(note)
    return sorted(cleaned, key=lambda item: (item["start"], item["pitch"]))


def remove_overlapping_breakdown_strings(strings_notes):
    repaired = []
    active_by_pitch = {}
    for note in sorted(strings_notes, key=lambda item: (item["start"], item["pitch"])):
        pitch = note["pitch"]
        fixed = dict(note)
        previous = active_by_pitch.get(pitch)
        if previous and previous["end"] > fixed["start"]:
            previous["end"] = fixed["start"]
        repaired.append(fixed)
        active_by_pitch[pitch] = fixed
    return sorted(repaired, key=lambda item: (item["start"], item["pitch"]))


def breakdown_string_change_count(strings_notes, start_bar, end_bar):
    signatures = []
    for block_start in range(start_bar, end_bar, 2):
        block_notes = []
        for bar in range(block_start, min(end_bar, block_start + 2)):
            block_notes.extend(notes_starting_in_bar(strings_notes, bar))
        if block_notes:
            signatures.append(tuple(sorted({note["pitch"] for note in block_notes})))
    return sum(1 for idx in range(1, len(signatures)) if signatures[idx] != signatures[idx - 1])


def breakdown_piano_jump_count(piano_notes, start_bar, end_bar):
    phrase_notes = sorted(
        [note for note in piano_notes if bar_tick(start_bar) <= note["start"] < bar_tick(end_bar)],
        key=lambda item: (item["start"], item["pitch"]),
    )
    jumps = 0
    for left, right in zip(phrase_notes, phrase_notes[1:]):
        if right["pitch"] - left["pitch"] in (3, 5, 7):
            jumps += 1
    return jumps


def breakdown_space_score(piano_notes, start_bar, end_bar):
    checks = []
    for block_start in range(start_bar, end_bar, 2):
        block_end_tick = bar_tick(min(end_bar, block_start + 2))
        block_start_tick = bar_tick(block_start)
        block_notes = [note for note in piano_notes if block_start_tick <= note["start"] < block_end_tick]
        total_beats = sum(max(0, min(note["end"], block_end_tick) - max(note["start"], block_start_tick)) for note in block_notes) / TICKS
        checks.append(total_beats <= 7.0)
    return 10 if checks and all(checks) else 0


def validate_breakdown_emotion(piano_notes, strings_notes, start_bar, end_bar):
    first_sig = rhythm_pattern_signature(piano_notes, start_bar, bars=1, step=0.5)
    second_sig = rhythm_pattern_signature(piano_notes, start_bar + 1, bars=1, step=0.5) if start_bar + 1 < end_bar else []
    variation_sig = rhythm_pattern_signature(piano_notes, start_bar + 2, bars=1, step=0.5) if start_bar + 2 < end_bar else []
    motif_score = 10 if first_sig and first_sig == second_sig and (not variation_sig or variation_sig == first_sig) else 0
    space_score = breakdown_space_score(piano_notes, start_bar, end_bar)
    avg_notes = sum(len(notes_starting_in_bar(piano_notes, bar)) for bar in range(start_bar, end_bar)) / max(1, end_bar - start_bar)
    max_notes_per_bar = max((len(notes_starting_in_bar(piano_notes, bar)) for bar in range(start_bar, end_bar)), default=0)
    long_note_count = sum(1 for note in piano_notes if length_beats(note) >= 1.0)
    total_duration = sum(length_beats(note) for note in piano_notes)
    long_duration = sum(length_beats(note) for note in piano_notes if length_beats(note) >= 1.0)
    piano_long_note_ratio = round(long_duration / max(0.01, total_duration), 3)
    anchor = get_breakdown_anchor_note(piano_notes, start_bar, end_bar)
    anchor_length = round(length_beats(anchor), 2) if anchor else 0
    anchor_pitch = anchor["pitch"] if anchor else 0
    pre_anchor_silence = breakdown_pre_anchor_silence(piano_notes, anchor)
    long_score = 10 if anchor and anchor_length >= 1.5 else 0
    string_signatures = {tuple(sorted(note["pitch"] for note in notes_starting_in_bar(strings_notes, bar))) for bar in range(start_bar, end_bar) if notes_starting_in_bar(strings_notes, bar)}
    string_changes_count = breakdown_string_change_count(strings_notes, start_bar, end_bar)
    strings_motion_score = 10 if 1 <= string_changes_count <= 2 else 0
    first_window = [note for bar in range(start_bar, min(end_bar, start_bar + 2)) for note in notes_starting_in_bar(strings_notes + piano_notes, bar)]
    final_window = [note for bar in range(max(start_bar, end_bar - 2), end_bar) for note in notes_starting_in_bar(strings_notes + piano_notes, bar)]
    first_energy = average_pitch(first_window) + (sum(note["velocity"] for note in first_window) / max(1, len(first_window)))
    final_energy = average_pitch(final_window) + (sum(note["velocity"] for note in final_window) / max(1, len(final_window)))
    tension_score = 10 if final_energy > first_energy else 0
    strings_span = get_register_span([note["pitch"] for note in strings_notes])
    first_string_tops = [max((note["pitch"] for note in notes_starting_in_bar(strings_notes, bar)), default=0) for bar in range(start_bar, min(end_bar, start_bar + 2))]
    final_string_tops = [max((note["pitch"] for note in notes_starting_in_bar(strings_notes, bar)), default=0) for bar in range(max(start_bar, end_bar - 2), end_bar)]
    strings_rise_amount = max(final_string_tops, default=0) - max(first_string_tops, default=0)
    anchor_space_score = 10 if 0.5 <= pre_anchor_silence <= 4.0 else 0
    strings_rise_score = 10 if strings_rise_amount > 0 else 0
    string_velocities = [note["velocity"] for note in strings_notes]
    velocity_curve = f"{min(string_velocities, default=0)}-{max(string_velocities, default=0)}"
    string_start_bars = sorted({note["start"] // BAR_TICKS for note in strings_notes})
    strings_every_two_bars = all((bar - start_bar) % 2 == 0 for bar in string_start_bars)
    piano_jump_count = breakdown_piano_jump_count(piano_notes, start_bar, end_bar)
    simple_score = 10 if max_notes_per_bar <= 2 and piano_long_note_ratio >= 0.9 and string_changes_count <= 2 and motif_score > 0 and strings_every_two_bars and piano_jump_count <= 1 else 0
    score = motif_score + space_score + long_score + anchor_space_score + strings_motion_score + strings_rise_score + tension_score + simple_score
    return score >= 40, {
        "breakdown_piano_motif_score": motif_score,
        "breakdown_piano_space_score": space_score,
        "breakdown_piano_avg_notes_per_bar": round(avg_notes, 2),
        "breakdown_piano_long_note_count": long_note_count,
        "breakdown_strings_motion_score": strings_motion_score,
        "breakdown_strings_velocity_curve": velocity_curve,
        "breakdown_strings_register_span": strings_span,
        "breakdown_tension_score": tension_score,
        "breakdown_emotion_score": score,
        "breakdown_anchor_note_length": anchor_length,
        "breakdown_anchor_pitch": anchor_pitch,
        "breakdown_pre_anchor_silence": pre_anchor_silence,
        "strings_rise_amount": strings_rise_amount,
        "breakdown_simple_mode": True,
        "piano_note_count_avg": round(avg_notes, 2),
        "piano_long_note_ratio": piano_long_note_ratio,
        "string_changes_count": string_changes_count,
        "emotional_anchor_present": bool(anchor and anchor_length >= 2.0),
        "breakdown_piano_jump_count": piano_jump_count,
    }


def apply_breakdown_emotion_engine(note_tracks, sections, chords, blueprint):
    progression_name = blueprint.get("progression_name", "uplifting")
    progression_family = blueprint.get("progression_family", "")
    aggregate = {
        "breakdown_engine_mode": "emotional_piano_strings",
        "breakdown_piano_motif_score": 0,
        "breakdown_piano_space_score": 0,
        "breakdown_piano_avg_notes_per_bar": 0,
        "breakdown_piano_long_note_count": 0,
        "breakdown_strings_motion_score": 0,
        "breakdown_strings_velocity_curve": "",
        "breakdown_strings_register_span": 0,
        "breakdown_tension_score": 0,
        "breakdown_anchor_note_length": 0,
        "breakdown_anchor_pitch": 0,
        "breakdown_pre_anchor_silence": 0,
        "strings_rise_amount": 0,
        "breakdown_emotion_score": 0,
        "breakdown_simple_mode": True,
        "piano_note_count_avg": 0,
        "piano_long_note_ratio": 0,
        "string_changes_count": 0,
        "emotional_anchor_present": False,
        "breakdown_piano_jump_count": 0,
        "breakdown_repairs_applied": 0,
    }
    reports = []
    for section in sections:
        if section["name"] != "Breakdown":
            continue
        start_bar = section["start_bar"]
        end_bar = section["end_bar"]
        piano_notes, strings_notes = build_breakdown_emotion_section(start_bar, end_bar, chords, progression_name, progression_family)
        piano_notes = remove_bad_breakdown_piano_notes(
            enforce_breakdown_anchor_space(enforce_breakdown_piano_space(piano_notes, start_bar, end_bar), start_bar, end_bar),
            start_bar,
            end_bar,
        )
        valid, section_report = validate_breakdown_emotion(piano_notes, strings_notes, start_bar, end_bar)
        note_tracks["piano"] = replace_notes_in_bar_range(note_tracks["piano"], start_bar, end_bar, piano_notes)
        note_tracks["strings"] = replace_notes_in_bar_range(note_tracks["strings"], start_bar, end_bar, strings_notes)
        section_report["breakdown_repairs_applied"] = 0 if valid else 1
        reports.append(section_report)
    if not reports:
        return aggregate
    aggregate["breakdown_piano_motif_score"] = round(sum(item["breakdown_piano_motif_score"] for item in reports) / len(reports), 2)
    aggregate["breakdown_piano_space_score"] = round(sum(item["breakdown_piano_space_score"] for item in reports) / len(reports), 2)
    aggregate["breakdown_piano_avg_notes_per_bar"] = round(sum(item["breakdown_piano_avg_notes_per_bar"] for item in reports) / len(reports), 2)
    aggregate["breakdown_piano_long_note_count"] = sum(item["breakdown_piano_long_note_count"] for item in reports)
    aggregate["breakdown_strings_motion_score"] = round(sum(item["breakdown_strings_motion_score"] for item in reports) / len(reports), 2)
    aggregate["breakdown_strings_velocity_curve"] = ",".join(item["breakdown_strings_velocity_curve"] for item in reports)
    aggregate["breakdown_strings_register_span"] = max(item["breakdown_strings_register_span"] for item in reports)
    aggregate["breakdown_tension_score"] = round(sum(item["breakdown_tension_score"] for item in reports) / len(reports), 2)
    aggregate["breakdown_anchor_note_length"] = max(item["breakdown_anchor_note_length"] for item in reports)
    aggregate["breakdown_anchor_pitch"] = max(item["breakdown_anchor_pitch"] for item in reports)
    aggregate["breakdown_pre_anchor_silence"] = round(sum(item["breakdown_pre_anchor_silence"] for item in reports) / len(reports), 2)
    aggregate["strings_rise_amount"] = max(item["strings_rise_amount"] for item in reports)
    aggregate["breakdown_emotion_score"] = round(sum(item["breakdown_emotion_score"] for item in reports) / len(reports), 2)
    aggregate["breakdown_simple_mode"] = all(item["breakdown_simple_mode"] for item in reports)
    aggregate["piano_note_count_avg"] = round(sum(item["piano_note_count_avg"] for item in reports) / len(reports), 2)
    aggregate["piano_long_note_ratio"] = round(sum(item["piano_long_note_ratio"] for item in reports) / len(reports), 3)
    aggregate["string_changes_count"] = sum(item["string_changes_count"] for item in reports)
    aggregate["emotional_anchor_present"] = any(item["emotional_anchor_present"] for item in reports)
    aggregate["breakdown_piano_jump_count"] = sum(item["breakdown_piano_jump_count"] for item in reports)
    aggregate["breakdown_repairs_applied"] = sum(item["breakdown_repairs_applied"] for item in reports)
    return aggregate


def tick(beats: float) -> int:
    return int(round(beats * TICKS))


def bar_tick(bar_index: int) -> int:
    return bar_index * BAR_TICKS


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def finishability_factor(blueprint) -> float:
    progression = blueprint.get("progression_family", "")
    track_archetype = blueprint.get("track_archetype", "")
    factor = 1.0
    if progression in ("lifted", "classic_warmth", "hopeful_pull", "progressive_flow"):
        factor *= 0.96
    if track_archetype in ("vocal_melodic", "emotional_uplifter"):
        factor *= 0.97
    if blueprint.get("section_weight_profile") == "late_bloom":
        factor *= 0.98
    return factor


def bounded_variant(blueprint, key: str, fallback: float = 1.0) -> float:
    return float(blueprint.get(key, fallback))


def filter_beats_to_grid(beats, allowed):
    return [beat for beat in beats if any(abs(beat - marker) < 1e-6 for marker in allowed)]


def filter_to_step_grid(beats, step: float):
    snapped = []
    seen = set()
    for beat in beats:
        snapped_beat = round(round(beat / step) * step, 4)
        if snapped_beat not in seen:
            seen.add(snapped_beat)
            snapped.append(snapped_beat)
    return snapped


def trance_phrase_grid(phrase, step: float = 0.5, min_length: float = 0.28, max_events: int = 5):
    normalized = []
    seen = set()
    for beat, length, pitch in phrase:
        snapped_beat = round(round(beat / step) * step, 4)
        snapped_length = max(min_length, round(round(length / 0.25) * 0.25, 2))
        if snapped_beat < 0.0 or snapped_beat > 3.5:
            continue
        key = (snapped_beat, pitch)
        if key in seen:
            continue
        seen.add(key)
        normalized.append((snapped_beat, snapped_length, pitch))
    normalized.sort(key=lambda item: (item[0], item[2]))
    return normalized[:max_events]


def trance_hook_phrase(family: str, bar_slot: int, anchor: int, support: int, lift: int, resolve: int, high_anchor: int):
    hook_bank = {
        "anthemic": {
            0: [(0.0, 0.75, anchor), (1.0, 0.5, support), (2.0, 0.75, lift), (3.0, 1.0, resolve)],
            1: [(0.0, 0.75, anchor), (1.5, 0.5, support), (2.0, 0.5, lift), (3.0, 1.0, high_anchor)],
            2: [(0.0, 0.5, support), (1.0, 0.5, anchor), (2.0, 0.75, lift), (3.0, 1.0, resolve)],
            3: [(0.0, 0.5, anchor), (1.0, 0.5, support), (2.0, 0.5, lift), (3.0, 1.0, high_anchor)],
        },
        "yearning": {
            0: [(0.0, 0.75, support), (1.0, 0.5, anchor), (2.0, 0.75, lift), (3.0, 1.0, resolve)],
            1: [(0.0, 0.75, support), (1.5, 0.5, anchor), (2.0, 0.75, lift), (3.0, 1.0, high_anchor)],
            2: [(0.0, 0.5, anchor), (1.0, 0.5, support), (2.0, 0.75, lift), (3.0, 1.0, resolve)],
            3: [(0.0, 0.5, support), (1.0, 0.5, lift), (2.0, 0.75, resolve), (3.0, 1.0, high_anchor)],
        },
        "driving": {
            0: [(0.0, 0.5, anchor), (1.0, 0.5, support), (2.0, 0.5, anchor), (3.0, 0.75, resolve)],
            1: [(0.0, 0.5, anchor), (1.0, 0.5, support), (2.0, 0.5, lift), (3.0, 0.75, resolve)],
            2: [(0.0, 0.5, anchor), (1.0, 0.5, anchor), (2.0, 0.5, support), (3.0, 0.75, lift)],
            3: [(0.0, 0.5, anchor), (1.0, 0.5, support), (2.0, 0.5, lift), (3.0, 1.0, high_anchor)],
        },
        "uplift_hook": {
            0: [(0.0, 0.75, anchor), (1.0, 0.5, support), (2.0, 0.5, anchor), (3.0, 1.0, high_anchor)],
            1: [(0.0, 0.75, anchor), (1.5, 0.5, support), (2.0, 0.5, lift), (3.0, 1.0, high_anchor)],
            2: [(0.0, 0.5, support), (1.0, 0.5, anchor), (2.0, 0.75, lift), (3.0, 1.0, resolve)],
            3: [(0.0, 0.5, anchor), (1.0, 0.5, support), (2.0, 0.5, lift), (3.0, 1.0, high_anchor)],
        },
    }
    family_bank = hook_bank.get(family, hook_bank["uplift_hook"])
    return family_bank[bar_slot % 4][:]


def early_verse_allows(kind: str, local_bar: int, lane: str) -> bool:
    if kind != "verse":
        return True
    lane_open_bar = {
        "drums_core": 0,
        "pad": 0,
        "bass": 1,
        "piano": 2,
        "strings": 3,
        "lead": 4,
        "counter": 3,
        "vocal": 3,
    }
    return local_bar >= lane_open_bar.get(lane, 0)


def ease_in_harmony_hits(hits, minimum_start: float, sustain_scale: float = 0.88):
    if not hits:
        return hits
    eased = []
    for beat_pos, beat_len, pitches in hits:
        if beat_pos < minimum_start:
            continue
        eased.append((beat_pos, max(0.5, beat_len * sustain_scale), pitches))
    if eased:
        return eased
    beat_pos, beat_len, pitches = hits[-1]
    return [(max(minimum_start, beat_pos), max(0.5, beat_len * sustain_scale), pitches)]


def outro_release_stage(local_bar: int, section_bars: int) -> str:
    if section_bars <= 2:
        return "final"
    if local_bar >= section_bars - 1:
        return "final"
    if local_bar >= section_bars - 3:
        return "tail"
    if local_bar >= section_bars - 5:
        return "thin"
    return "full"


def second_drop_cleanup_stage(kind: str, local_bar: int, is_second_pass: bool) -> str | None:
    if kind != "drop" or not is_second_pass or local_bar >= 2:
        return None
    return "entry" if local_bar == 0 else "settle"


def verse_drum_entry_stage(kind: str, local_bar: int, entry_variant: str) -> str | None:
    if kind != "verse":
        return None
    if local_bar == 0:
        return "kick_only"
    if local_bar == 1:
        return "hat_tease"
    if local_bar == 2:
        if entry_variant in ("kick_only", "clap_late"):
            return "hat_tease"
        if entry_variant == "rolling_open":
            return "settle_in"
        return "clap_arrives"
    if local_bar == 3:
        if entry_variant == "clap_late":
            return "clap_arrives"
        if entry_variant == "rolling_open":
            return "open_up"
        return "settle_in"
    if local_bar == 4:
        return "open_up"
    return None


def verse_harmonic_stage(kind: str, local_bar: int) -> str:
    if kind != "verse":
        return "full"
    if local_bar == 0:
        return "seed"
    if local_bar == 1:
        return "answer"
    if local_bar == 2:
        return "lift"
    if local_bar == 3:
        return "rise"
    return "full"


def exposed_harmonic_authority(kind: str, role: str, verse_stage: str, breakdown_style: str, breakdown_focus: str):
    if kind == "verse":
        if verse_stage in ("seed", "answer", "lift", "rise"):
            return "piano_leads"
        return "shared"
    if kind == "breakdown":
        if breakdown_style == "piano_led" or breakdown_focus == "piano_memory":
            return "piano_leads"
        if breakdown_style in ("pad_space", "arp_texture") and role in ("establish", "repeat", "develop", "lift", "transition"):
            return "strings_lead"
    return "shared"


def authored_piano_hits(chord, role: str, stage: str, progression_family: str):
    root_stack = [chord["root"], chord["third"], chord["fifth"]]
    answer_stack = [chord["third"], chord["fifth"], chord["root"] + 12]
    lift_stack = [chord["fifth"], chord["root"] + 12, chord["third"] + 12]
    shine_stack = [chord["root"] + 12, chord["third"] + 12, chord["fifth"] + 12]

    if progression_family == "classic_warmth":
        root_stack = [chord["root"] - 12, chord["root"], chord["third"], chord["fifth"]]
        answer_stack = [chord["third"] - 12, chord["third"], chord["fifth"], chord["root"] + 12]
    elif progression_family == "hopeful_pull":
        answer_stack = [chord["third"], chord["fifth"], chord["root"] + 12, chord["third"] + 12]
        lift_stack = [chord["fifth"], chord["root"] + 12, chord["third"] + 12, chord["fifth"] + 12]
    elif progression_family == "festival_cycle":
        root_stack = [chord["root"], chord["fifth"], chord["root"] + 12]
        answer_stack = [chord["third"], chord["fifth"], chord["root"] + 12]
    elif progression_family == "progressive_flow":
        root_stack = [chord["root"] - 12, chord["root"], chord["fifth"]]
        answer_stack = [chord["third"], chord["fifth"], chord["root"] + 12]
        lift_stack = [chord["fifth"], chord["root"] + 12, chord["third"] + 12]
        shine_stack = [chord["root"] + 12, chord["fifth"] + 12]

    if stage == "seed":
        return [(3.0, 1.0, root_stack)]
    if stage == "answer":
        return [(2.0, 0.85, root_stack), (3.25, 0.75, answer_stack)]
    if stage == "lift":
        return [(1.0, 0.75, root_stack), (2.0, 0.75, answer_stack), (3.0, 0.7, lift_stack)]
    if role in ("establish", "repeat"):
        return [(0.0, 0.9, root_stack), (2.0, 0.85, answer_stack)]
    if role == "develop":
        return [(0.0, 0.8, root_stack), (1.5, 0.7, answer_stack), (3.0, 0.65, lift_stack)]
    if role in ("lift", "transition"):
        return [(0.0, 0.85, answer_stack), (2.0, 0.75, lift_stack), (3.0, 0.8, shine_stack)]
    return [(0.0, 0.9, root_stack), (2.0, 0.8, answer_stack)]


def authored_string_hits(chord, role: str, stage: str, progression_family: str):
    bed_stack = [chord["root"] - 12, chord["fifth"] - 12, chord["root"], chord["third"], chord["fifth"]]
    glow_stack = [chord["third"], chord["fifth"], chord["root"] + 12]
    lift_stack = [chord["third"], chord["fifth"] + 12, chord["root"] + 24]

    if progression_family == "festival_cycle":
        bed_stack = [chord["root"] - 12, chord["fifth"] - 12, chord["root"], chord["fifth"], chord["root"] + 12]
    elif progression_family == "hopeful_pull":
        glow_stack = [chord["third"], chord["fifth"], chord["root"] + 12, chord["third"] + 12]
        lift_stack = [chord["third"], chord["fifth"] + 12, chord["root"] + 24, chord["third"] + 24]
    elif progression_family == "progressive_flow":
        bed_stack = [chord["root"] - 12, chord["root"], chord["fifth"], chord["root"] + 12]
        glow_stack = [chord["fifth"], chord["root"] + 12, chord["third"] + 12]
        lift_stack = [chord["third"], chord["fifth"] + 12, chord["root"] + 24]

    if stage == "seed":
        return []
    if stage == "answer":
        return [(2.5, 1.4, glow_stack)]
    if stage == "lift":
        return [(1.5, 1.8, bed_stack)]
    if stage == "rise":
        return [(2.75, 1.0, glow_stack)]
    if role in ("establish", "repeat"):
        return [(2.0, 1.6, glow_stack)]
    if role == "develop":
        return [(1.5, 1.9, bed_stack)]
    if role in ("lift", "transition"):
        return [(1.0, 2.25, lift_stack)]
    return [(2.0, 1.6, glow_stack)]


def build_story_stage(kind: str, local_bar: int, section_bars: int, is_second_pass: bool) -> str | None:
    if kind != "build":
        return None
    if is_second_pass:
        if local_bar < 4:
            return "recover"
        if local_bar < max(6, section_bars - 6):
            return "gather"
        return "launch"
    if local_bar < 4:
        return "prepare"
    if local_bar < max(6, section_bars - 4):
        return "stack"
    return "launch"


def breakdown_story_stage(local_bar: int, section_bars: int) -> str:
    if local_bar < 4:
        return "reset"
    if local_bar < max(6, section_bars - 8):
        return "hold"
    if local_bar < max(8, section_bars - 3):
        return "ramp"
    return "launch"


def add_phrase_motion(phrase, family: str, role: str, section_kind: str, local_bar: int, anchor: int, support: int, lift: int, resolve: int):
    motion = list(phrase)
    if not motion:
        return motion
    if section_kind == "drop":
        if role in ("repeat", "develop") and local_bar % 2 == 1:
            motion.append((2.5, 0.35, lift if family != "yearning" else resolve))
        if role in ("lift", "transition"):
            motion.append((3.5, 0.25, anchor if family == "driving" else resolve))
    elif section_kind == "build":
        if role in ("develop", "lift"):
            motion.append((2.5, 0.3, support if family == "yearning" else lift))
    elif section_kind == "verse":
        if local_bar % 4 in (1, 2):
            motion.append((2.5, 0.35, support if family in ("anthemic", "yearning") else resolve))
    return motion


def section_matched_lead_phrase(kind: str, role: str, local_bar: int, lead_archetype: str, progression_family: str, cadence_profile: str, drop_harmony_entry: str, relation, anchor: int, support: int, lift: int, resolve: int, high_anchor: int):
    if kind == "verse":
        verse_bank = {
            "establish": [(2.0, 0.5, support), (3.0, 0.75, resolve)],
            "repeat": [(2.0, 0.5, anchor), (3.0, 0.75, resolve)],
            "develop": [(1.5, 0.4, support), (2.5, 0.5, lift), (3.0, 0.6, resolve)],
            "lift": [(2.0, 0.5, lift), (3.0, 0.85, high_anchor if lead_archetype in ("anthemic", "uplift_hook") else resolve)],
            "transition": [(2.0, 0.45, support), (3.0, 0.6, lift), (3.5, 0.25, resolve)],
        }
        phrase = verse_bank.get(role, verse_bank["repeat"])[:]
        if relation["vocal_answers"] or relation["shared_hook"]:
            phrase = [entry for entry in phrase if entry[0] >= 2.0]
        if progression_family == "hopeful_pull":
            phrase = [(beat, length, support if idx == 0 else lift) for idx, (beat, length, _pitch) in enumerate(phrase)]
        elif progression_family == "classic_warmth":
            phrase = [(beat, min(0.7, length + 0.1), resolve if idx == len(phrase) - 1 else anchor) for idx, (beat, length, _pitch) in enumerate(phrase)]
        elif progression_family == "progressive_flow":
            phrase = [(beat, min(0.9, length + 0.15), support if idx == 0 else resolve) for idx, (beat, length, _pitch) in enumerate(phrase) if beat >= 2.0]
        return phrase
    if kind == "build":
        build_bank = {
            "establish": [(1.0, 0.45, support), (2.0, 0.5, lift), (3.0, 0.75, resolve)],
            "repeat": [(1.0, 0.45, anchor), (2.0, 0.5, support), (3.0, 0.75, lift)],
            "develop": [(1.0, 0.4, support), (2.0, 0.45, lift), (2.5, 0.35, resolve), (3.0, 0.75, high_anchor)],
            "lift": [(1.5, 0.4, support), (2.0, 0.45, lift), (3.0, 0.8, high_anchor)],
            "transition": [(2.0, 0.4, support), (2.5, 0.35, lift), (3.0, 0.6, resolve), (3.5, 0.25, high_anchor)],
        }
        phrase = build_bank.get(role, build_bank["repeat"])[:]
        if drop_harmony_entry == "delayed_bloom":
            phrase = [entry for entry in phrase if entry[0] >= 2.0] or phrase[-2:]
        elif drop_harmony_entry == "sustain_first":
            phrase = [(beat, min(0.9, length + 0.1), pitch) for beat, length, pitch in phrase]
        if cadence_profile == "delayed_resolve":
            phrase[-1] = (phrase[-1][0], phrase[-1][1], resolve)
        return phrase
    return trance_hook_phrase(lead_archetype, local_bar, anchor, support, lift, resolve, high_anchor)


def drop_section_role(blueprint, is_second_pass: bool) -> str:
    drop_pair_profile = blueprint.get("drop_pair_profile", "drop1_statement_drop2_upgrade")
    pair_map = {
        "drop1_statement_drop2_upgrade": ("statement", "upgrade"),
        "drop1_tease_drop2_release": ("tease", "release"),
        "drop1_full_drop2_wider": ("full", "wider"),
        "drop1_tight_drop2_emotional": ("tight", "emotional"),
    }
    first_role, second_role = pair_map.get(drop_pair_profile, ("statement", "upgrade"))
    return second_role if is_second_pass else first_role


def section_marker_text(section_name: str, blueprint) -> str:
    kind = section_kind(section_name)
    if kind == "drop":
        focus = drop_section_role(blueprint, "2" in section_name)
    elif kind == "breakdown":
        focus = blueprint.get("breakdown_function", "harmonic_lift")
    elif kind == "build":
        focus = blueprint.get("final_lift_profile", "anthem_push") if "2" in section_name else blueprint.get("drop_pair_profile", "drop1_statement_drop2_upgrade")
    elif kind == "intro":
        focus = blueprint.get("energy_profile", "gradual_rise")
    elif kind == "verse":
        focus = blueprint.get("lead_vocal_relationship", "shared_hook")
    elif kind == "outro":
        focus = blueprint.get("section_weight_profile", "balanced")
    else:
        focus = blueprint.get("macro_journey_profile", "anthem_arc")
    return f"{section_name} | {blueprint['macro_journey_profile']} | {focus} | {blueprint['chord_style']} | {blueprint['bass_style']}"


def section_display_name(kind: str, is_second_pass: bool) -> str:
    mapping = {
        "intro": "Intro",
        "verse": "Verse",
        "build": "Build 2" if is_second_pass else "Build",
        "drop": "Drop 2" if is_second_pass else "Drop 1",
        "breakdown": "Breakdown",
        "outro": "Outro",
    }
    return mapping.get(kind, kind.title())


def get_supersaw_energy(section_name: str) -> float:
    energy_map = {
        "Intro": 0.20,
        "Verse": 0.35,
        "Build": 0.55,
        "Drop 1": 0.82,
        "Breakdown": 0.18,
        "Build 2": 0.68,
        "Drop 2": 1.00,
        "Outro": 0.30,
    }
    return energy_map.get(section_name, 0.5)


def get_lead_register_targets(section_name: str):
    if section_name == "Drop 1":
        return {"a_range": (72, 79), "b_range": (76, 82), "payoff_range": (79, 84)}
    if section_name == "Drop 2":
        return {"a_range": (74, 81), "b_range": (78, 84), "payoff_range": (81, 86)}
    return {"a_range": (69, 76), "b_range": (72, 79), "payoff_range": (76, 81)}


def constrain_phrase_to_range(phrase, target_range):
    low, high = target_range
    return [(beat, length, clamp(pitch, low, high)) for beat, length, pitch in phrase]


def note(root: str, degree: int, octave: int = 4) -> int:
    return NOTE[root] + SCALE[(degree - 1) % 7] + (octave + 1) * 12


def add_event(events, start_tick: int, pitch: int, length_tick: int, velocity: int = 90, channel: int = 0):
    events.append((start_tick, Message("note_on", note=int(pitch), velocity=int(velocity), channel=channel, time=0)))
    events.append((start_tick + max(1, length_tick), Message("note_off", note=int(pitch), velocity=0, channel=channel, time=0)))


def add_events(events, start_tick: int, pitches, length_tick: int, velocity: int = 90, channel: int = 0):
    if isinstance(pitches, int):
        pitches = [pitches]
    for pitch in pitches:
        add_event(events, start_tick, pitch, length_tick, velocity=velocity, channel=channel)


def finalise_track(name: str, tempo: int, events, markers=None) -> MidiTrack:
    track = MidiTrack()
    track.append(MetaMessage("track_name", name=name, time=0))
    track.append(MetaMessage("set_tempo", tempo=tempo, time=0))
    working = list(events)
    if markers:
        for abs_time, text in markers:
            working.append((abs_time, MetaMessage("marker", text=text, time=0)))
    working.sort(key=lambda item: (item[0], 0 if getattr(item[1], "type", "") == "note_off" else 1))
    last_time = 0
    for abs_time, message in working:
        message.time = max(0, int(abs_time - last_time))
        track.append(message)
        last_time = abs_time
    track.append(MetaMessage("end_of_track", time=1))
    return track


def events_to_notes(events):
    ordered = sorted(events, key=lambda item: (item[0], 0 if getattr(item[1], "type", "") == "note_off" else 1))
    active = {}
    notes = []
    for abs_time, message in ordered:
        if getattr(message, "type", "") == "note_on" and getattr(message, "velocity", 0) > 0:
            key = (getattr(message, "note", 0), getattr(message, "channel", 0))
            active.setdefault(key, []).append((abs_time, getattr(message, "velocity", 0)))
        elif getattr(message, "type", "") == "note_off":
            key = (getattr(message, "note", 0), getattr(message, "channel", 0))
            stack = active.get(key)
            if stack:
                start_time, velocity = stack.pop(0)
                notes.append({
                    "start": start_time,
                    "end": max(start_time + 1, abs_time),
                    "pitch": getattr(message, "note", 0),
                    "velocity": velocity,
                    "channel": getattr(message, "channel", 0),
                })
    return sorted(notes, key=lambda note_data: (note_data["start"], note_data["pitch"]))


def notes_to_events(notes):
    rebuilt = []
    for note_data in sorted(notes, key=lambda item: (item["start"], item["pitch"])):
        add_event(
            rebuilt,
            int(note_data["start"]),
            int(note_data["pitch"]),
            max(1, int(note_data["end"] - note_data["start"])),
            velocity=int(note_data.get("velocity", 90)),
            channel=int(note_data.get("channel", 0)),
        )
    return rebuilt


def notes_starting_in_bar(notes, bar_index: int):
    bar_start = bar_tick(bar_index)
    bar_end = bar_tick(bar_index + 1)
    return [note_data for note_data in notes if bar_start <= note_data["start"] < bar_end]


def notes_overlapping_bar(notes, bar_index: int):
    bar_start = bar_tick(bar_index)
    bar_end = bar_tick(bar_index + 1)
    return [note_data for note_data in notes if note_data["start"] < bar_end and note_data["end"] > bar_start]


def remove_notes_in_bar_range(notes, start_bar: int, end_bar: int):
    start_tick = bar_tick(start_bar)
    end_tick = bar_tick(end_bar)
    return [note_data for note_data in notes if not (start_tick <= note_data["start"] < end_tick)]


def replace_notes_in_bar_range(notes, start_bar: int, end_bar: int, replacements):
    retained = remove_notes_in_bar_range(notes, start_bar, end_bar)
    retained.extend(replacements)
    return sorted(retained, key=lambda item: (item["start"], item["pitch"]))


def quantized_bar_positions(notes, bar_index: int, step: float = 0.25):
    bar_start = bar_tick(bar_index)
    positions = []
    for note_data in notes_starting_in_bar(notes, bar_index):
        beat = round((note_data["start"] - bar_start) / TICKS, 4)
        positions.append(round(round(beat / step) * step, 2))
    return positions


def bar_note_density(notes, bar_index: int):
    return len(notes_starting_in_bar(notes, bar_index))


def is_offbeat_position(beat_pos: float):
    return round(beat_pos % 1.0, 2) in (0.25, 0.5, 0.75)


def length_beats(note_data) -> float:
    return round((note_data["end"] - note_data["start"]) / TICKS, 4)


def average_pitch(notes) -> float:
    if not notes:
        return 0.0
    return sum(note_data["pitch"] for note_data in notes) / len(notes)


def reduce_to_pattern(notes, max_events: int = 6):
    ordered = sorted(notes, key=lambda item: (item["start"], item["pitch"]))
    if len(ordered) <= max_events:
        return ordered
    selected = ordered[: max(1, max_events - 1)]
    tail = ordered[-1]
    if tail not in selected:
        selected.append(tail)
    return sorted(selected, key=lambda item: (item["start"], item["pitch"]))


def enforce_arp_pattern(notes, bar_index: int, max_events: int = 6):
    bar_notes = notes_starting_in_bar(notes, bar_index)
    if len(bar_notes) <= max_events:
        return sorted(notes, key=lambda item: (item["start"], item["pitch"]))
    retained = [note_data for note_data in notes if note_data["start"] // BAR_TICKS != bar_index]
    retained.extend(reduce_to_pattern(bar_notes, max_events=max_events))
    return sorted(retained, key=lambda item: (item["start"], item["pitch"]))


def enforce_offbeat_groove(notes):
    offbeat_notes = []
    for note_data in notes:
        beat_pos = round((note_data["start"] % BAR_TICKS) / TICKS, 2)
        if is_offbeat_position(beat_pos):
            offbeat_notes.append(note_data)
    return sorted(offbeat_notes or notes, key=lambda item: (item["start"], item["pitch"]))


def rhythm_pattern_signature(notes, start_bar: int, bars: int = 2, step: float = 0.5):
    signature = []
    for offset in range(bars):
        signature.extend(quantized_bar_positions(notes, start_bar + offset, step))
    return tuple(signature)


def rhythm_pattern_match_ratio(pattern_a, pattern_b):
    if not pattern_a and not pattern_b:
        return 1.0
    if not pattern_a or not pattern_b:
        return 0.0
    length = max(len(pattern_a), len(pattern_b))
    matches = 0
    for idx in range(min(len(pattern_a), len(pattern_b))):
        if abs(pattern_a[idx] - pattern_b[idx]) <= 0.3:
            matches += 1
    return matches / max(1, length)


def build_hook_phrase_pipeline(lead_notes, start_bar: int):
    bars_1_4 = []
    bars_5_6 = []
    bars_7_8 = []
    for note_data in lead_notes:
        bar_index = note_data["start"] // BAR_TICKS
        if start_bar <= bar_index < start_bar + 4:
            bars_1_4.append(note_data)
        elif start_bar + 4 <= bar_index < start_bar + 6:
            bars_5_6.append(note_data)
        elif start_bar + 6 <= bar_index < start_bar + 8:
            bars_7_8.append(note_data)
    return {
        "start_bar": start_bar,
        "all_notes": sorted(lead_notes, key=lambda item: (item["start"], item["pitch"])),
        "bars_1_4": {"start_bar": start_bar, "notes": sorted(bars_1_4, key=lambda item: (item["start"], item["pitch"]))},
        "bars_5_6": {"start_bar": start_bar + 4, "notes": sorted(bars_5_6, key=lambda item: (item["start"], item["pitch"]))},
        "bars_7_8": {"start_bar": start_bar + 6, "notes": sorted(bars_7_8, key=lambda item: (item["start"], item["pitch"]))},
    }


def validate_motif(bars_1_4):
    start_bar = bars_1_4["start_bar"]
    lead_notes = bars_1_4["notes"]
    first_four = [tuple(quantized_bar_positions(lead_notes, start_bar + offset, 0.5)) for offset in range(4)]
    motif_hits = 0
    if first_four[0] and first_four[0] == first_four[2]:
        motif_hits += 1
    if first_four[1] and first_four[1] == first_four[3]:
        motif_hits += 1
    repeated_two_bar_patterns = 0
    for pair_start in range(0, 4, 2):
        first_pair = []
        second_pair = []
        for offset in range(pair_start, pair_start + 2):
            first_pair.extend(quantized_bar_positions(lead_notes, start_bar + offset, 0.5))
        for offset in range(pair_start + 2, pair_start + 4):
            second_pair.extend(quantized_bar_positions(lead_notes, start_bar + offset, 0.5))
        if first_pair and tuple(first_pair[:4]) == tuple(second_pair[:4]):
            repeated_two_bar_patterns += 1
    motif_score = 4 if motif_hits == 2 or repeated_two_bar_patterns >= 1 else 2 if motif_hits == 1 else 0
    bars_1_2_pattern = rhythm_pattern_signature(lead_notes, start_bar, bars=2, step=0.5)
    bars_3_4_pattern = rhythm_pattern_signature(lead_notes, start_bar + 2, bars=2, step=0.5)
    pattern_match = rhythm_pattern_match_ratio(bars_1_2_pattern, bars_3_4_pattern)
    evenly_spaced_bars = 0
    for fingerprint in first_four:
        if len(fingerprint) >= 3:
            intervals = [round(fingerprint[idx + 1] - fingerprint[idx], 2) for idx in range(len(fingerprint) - 1)]
            if len(set(intervals)) <= 1:
                evenly_spaced_bars += 1
    rhythmic_identity_score = 0
    if pattern_match >= 0.7:
        rhythmic_identity_score += 3
    elif pattern_match >= 0.45:
        rhythmic_identity_score += 1
    if len({fingerprint for fingerprint in first_four if fingerprint}) >= 2:
        rhythmic_identity_score += 1
    if evenly_spaced_bars >= 3:
        rhythmic_identity_score = max(0, rhythmic_identity_score - 2)
    rejection_reasons = []
    if motif_score < 2:
        rejection_reasons.append("no_repeating_rhythm")
    if pattern_match < 0.45:
        rejection_reasons.append("motif_identity_not_locked")
    if evenly_spaced_bars >= 3:
        rejection_reasons.append("too_evenly_spaced")
    return {
        "motif_score": motif_score,
        "rhythmic_identity_score": rhythmic_identity_score,
        "pattern_match": pattern_match,
        "rejection_reasons": rejection_reasons,
    }


def phrase_note_density(notes, start_bar: int, bars: int = 8):
    return sum(bar_note_density(notes, start_bar + offset) for offset in range(bars)) / max(1, bars)


def phrase_pitch_span(notes, start_bar: int, bars: int = 8):
    window = [note_data["pitch"] for offset in range(bars) for note_data in notes_starting_in_bar(notes, start_bar + offset)]
    return max(window, default=0) - min(window, default=0) if window else 0


def rhythmic_overlap_score(notes_a, notes_b, start_bar: int, bars: int = 8, step: float = 0.5):
    positions_a = set()
    positions_b = set()
    for offset in range(bars):
        bar_index = start_bar + offset
        positions_a.update((offset, pos) for pos in quantized_bar_positions(notes_a, bar_index, step))
        positions_b.update((offset, pos) for pos in quantized_bar_positions(notes_b, bar_index, step))
    if not positions_a:
        return 1.0
    return len(positions_a & positions_b) / max(1, len(positions_a))


def contains_phrase_peak(payoff_notes, phrase_notes):
    if not payoff_notes or not phrase_notes:
        return False
    phrase_pitches = sorted((note_data["pitch"] for note_data in phrase_notes), reverse=True)
    threshold = phrase_pitches[1] if len(phrase_pitches) > 1 else phrase_pitches[0]
    return max(note_data["pitch"] for note_data in payoff_notes) >= threshold


def score_anthem_payoff(phrase_notes, start_bar: int, root_pc: int, third_pc: int):
    payoff_notes = [note_data for note_data in phrase_notes if start_bar + 6 <= note_data["start"] // BAR_TICKS < start_bar + 8]
    pre_payoff_notes = [note_data for note_data in phrase_notes if start_bar + 4 <= note_data["start"] // BAR_TICKS < start_bar + 6]
    long_note_score = 2 if any((note_data["end"] - note_data["start"]) / TICKS >= 1.25 for note_data in payoff_notes) else 0
    density_reduction_score = 2 if len(payoff_notes) < len(pre_payoff_notes) else 0
    final_resolve_score = 2 if payoff_notes and (payoff_notes[-1]["pitch"] % 12) in (root_pc, third_pc) else 0
    peak_score = 2 if contains_phrase_peak(payoff_notes, phrase_notes) else 0
    anthem_payoff_score = long_note_score + density_reduction_score + final_resolve_score + peak_score
    release_score = (2 if density_reduction_score else 0) + (1 if long_note_score else 0)
    dominance_score = (2 if peak_score else 0) + (1 if final_resolve_score else 0)
    return {
        "anthem_payoff_score": anthem_payoff_score,
        "release_score": release_score,
        "dominance_score": dominance_score,
        "valid": anthem_payoff_score >= 6,
    }


def contains_large_interval_jump(phrase_notes, min_semitones: int = 5):
    pitches = [note_data["pitch"] for note_data in sorted(phrase_notes, key=lambda item: (item["start"], item["pitch"]))]
    return any(abs(pitches[idx + 1] - pitches[idx]) >= min_semitones for idx in range(len(pitches) - 1))


def contains_unexpected_gap(phrase_notes, min_gap_beats: float = 0.75):
    ordered = sorted(phrase_notes, key=lambda item: (item["start"], item["pitch"]))
    for idx in range(len(ordered) - 1):
        gap = (ordered[idx + 1]["start"] - ordered[idx]["end"]) / TICKS
        if gap >= min_gap_beats:
            return True
    return False


def contains_delayed_entry(phrase_notes, bars):
    for note_data in phrase_notes:
        bar_index = note_data["start"] // BAR_TICKS
        if bar_index in bars:
            beat = (note_data["start"] - bar_tick(bar_index)) / TICKS
            if beat >= 1.0:
                return True
    return False


def has_surprise_moment(phrase_notes, start_bar: int):
    surprise_count = 0
    if contains_large_interval_jump(phrase_notes, min_semitones=5):
        surprise_count += 1
    if contains_unexpected_gap(phrase_notes, min_gap_beats=0.75):
        surprise_count += 1
    if contains_delayed_entry(phrase_notes, bars=(start_bar + 4, start_bar + 5)):
        surprise_count += 1
    return surprise_count >= 1


def score_crowd_response(candidate_scores):
    score = 0
    if candidate_scores["motif_score"] >= 4:
        score += 2
    if candidate_scores["rhythmic_identity_score"] >= 4:
        score += 2
    if candidate_scores["anthem_payoff_score"] >= 6:
        score += 2
    if candidate_scores["singability_score"] >= 3:
        score += 2
    if candidate_scores["supersaw_contrast_score"] >= 1:
        score += 1
    return score


def score_supersaw_contrast(lead_notes, supersaw_notes, start_bar: int):
    overlap = rhythmic_overlap_score(lead_notes, supersaw_notes, start_bar, bars=8, step=0.5)
    if overlap > 0.7:
        return {"score": -2, "overlap": overlap, "rejection_reasons": ["lead_blends_with_supersaw"]}
    if overlap < 0.3:
        return {"score": 2, "overlap": overlap, "rejection_reasons": []}
    return {"score": 0, "overlap": overlap, "rejection_reasons": []}


def score_lead_supersaw_cohesion(lead_notes, supersaw_notes, start_bar: int):
    if not supersaw_notes:
        return {
            "score": 0,
            "payoff_crown_ok": False,
            "accent_alignment_ok": False,
            "shared_harmonic_ok": False,
            "rejection_reasons": ["no_supersaw_reference"],
        }
    lead_window = [note_data for offset in range(8) for note_data in notes_starting_in_bar(lead_notes, start_bar + offset)]
    if not lead_window:
        return {
            "score": 0,
            "payoff_crown_ok": False,
            "accent_alignment_ok": False,
            "shared_harmonic_ok": False,
            "rejection_reasons": ["no_lead_window"],
        }
    supersaw_window = [note_data for note_data in supersaw_notes if bar_tick(start_bar) <= note_data["start"] < bar_tick(start_bar + 8)]
    if not supersaw_window:
        supersaw_window = supersaw_notes
    supersaw_pitch_classes = {note_data["pitch"] % 12 for note_data in supersaw_window}

    payoff_lead = [note_data for note_data in lead_window if start_bar + 6 <= note_data["start"] // BAR_TICKS < start_bar + 8]
    if not payoff_lead:
        payoff_lead = [note_data for note_data in lead_window if start_bar + 4 <= note_data["start"] // BAR_TICKS < start_bar + 8]
    payoff_highest = max((note_data["pitch"] for note_data in payoff_lead), default=max(note_data["pitch"] for note_data in lead_window))
    payoff_crown_ok = (payoff_highest % 12) in supersaw_pitch_classes

    supersaw_accents = set()
    for note_data in supersaw_window:
        bar_index = note_data["start"] // BAR_TICKS
        if not (start_bar <= bar_index < start_bar + 8):
            continue
        beat = round((note_data["start"] - bar_tick(bar_index)) / TICKS, 2)
        if length_beats(note_data) >= 0.75 or note_data["velocity"] >= 80:
            supersaw_accents.add((bar_index - start_bar, round(beat * 2) / 2))
    lead_attacks = []
    for note_data in lead_window:
        bar_index = note_data["start"] // BAR_TICKS
        beat = round((note_data["start"] - bar_tick(bar_index)) / TICKS, 2)
        lead_attacks.append((bar_index - start_bar, round(beat * 2) / 2, is_offbeat_position(beat)))
    accent_hits = sum(1 for rel_bar, quant_beat, offbeat in lead_attacks if (rel_bar, quant_beat) in supersaw_accents or offbeat)
    accent_alignment_ratio = accent_hits / max(1, len(lead_attacks))
    accent_alignment_ok = accent_alignment_ratio >= 0.6

    lead_peak_notes = sorted(lead_window, key=lambda item: (item["pitch"], item["velocity"]), reverse=True)[:6]
    shared_harmonic_ratio = sum(1 for note_data in lead_peak_notes if (note_data["pitch"] % 12) in supersaw_pitch_classes) / max(1, len(lead_peak_notes))
    shared_harmonic_ok = shared_harmonic_ratio >= 0.66

    score = 0
    if payoff_crown_ok:
        score += 2
    if accent_alignment_ok:
        score += 2
    if shared_harmonic_ok:
        score += 2
    rejection_reasons = []
    if not payoff_crown_ok:
        rejection_reasons.append("lead_payoff_not_crowned_by_supersaw")
    if not accent_alignment_ok:
        rejection_reasons.append("lead_attacks_conflict_with_supersaw_accents")
    if not shared_harmonic_ok:
        rejection_reasons.append("lead_harmonic_identity_detached_from_supersaw")
    return {
        "score": score,
        "payoff_crown_ok": payoff_crown_ok,
        "accent_alignment_ok": accent_alignment_ok,
        "shared_harmonic_ok": shared_harmonic_ok,
        "rejection_reasons": rejection_reasons,
    }


def nearest_pitch_for_pitch_classes(source_pitch: int, allowed_pitch_classes):
    if not allowed_pitch_classes:
        return source_pitch
    best_pitch = source_pitch
    best_distance = 999
    for candidate in range(60, 99):
        if candidate % 12 in allowed_pitch_classes:
            distance = abs(candidate - source_pitch)
            if distance < best_distance:
                best_distance = distance
                best_pitch = candidate
    return best_pitch


def build_drop_allowed_pitch_classes(chord):
    return {
        chord["root"] % 12,
        chord["third"] % 12,
        chord["fifth"] % 12,
    }


def lead_note_is_drop_safe(note_pitch, allowed_pitch_classes):
    return (note_pitch % 12) in allowed_pitch_classes


def remap_to_safe_drop_tone(source_pitch, allowed_pitch_classes, low=60, high=98):
    best = source_pitch
    best_dist = 999
    for candidate in range(low, high + 1):
        if candidate % 12 in allowed_pitch_classes:
            dist = abs(candidate - source_pitch)
            if dist < best_dist:
                best = candidate
                best_dist = dist
    return best


def simplify_drop_lead_bar(bar_notes):
    ordered = sorted(bar_notes, key=lambda n: (n["start"], n["pitch"]))
    if len(ordered) <= 2:
        return ordered
    keep = [ordered[0], ordered[-1]]
    return sorted(keep, key=lambda n: (n["start"], n["pitch"]))


def clamp_supersaw_register(chord_pitches, max_pitch=84):
    clamped = []
    for pitch in chord_pitches:
        while pitch > max_pitch:
            pitch -= 12
        clamped.append(pitch)
    return sorted(clamped)


def enforce_drop_lead_harmony_rules(lead_notes, start_bar: int, chords, supersaw_notes=None):
    if not supersaw_notes:
        return sorted(lead_notes, key=lambda item: (item["start"], item["pitch"])), {
            "lead_drop_density_repairs": 0,
            "drop_safe_tone_repairs": 0,
            "unsafe_peak_note_repairs": 0,
        }
    repaired = sorted((dict(note_data) for note_data in lead_notes), key=lambda item: (item["start"], item["pitch"]))
    density_repairs = 0
    safe_tone_repairs = 0
    peak_repairs = 0
    for offset in range(8):
        bar_index = start_bar + offset
        bar_start = bar_tick(bar_index)
        bar_end = bar_tick(bar_index + 1)
        chord = chords[bar_index % len(chords)]
        allowed = build_drop_allowed_pitch_classes(chord)
        bar_notes = [dict(note_data) for note_data in repaired if bar_start <= note_data["start"] < bar_end]
        if not bar_notes:
            continue
        for note_data in bar_notes:
            if not lead_note_is_drop_safe(note_data["pitch"], allowed):
                note_data["pitch"] = remap_to_safe_drop_tone(note_data["pitch"], allowed)
                safe_tone_repairs += 1
            note_data["end"] = max(note_data["end"], min(bar_end, note_data["start"] + tick(0.75)))
        peak_idx = max(range(len(bar_notes)), key=lambda idx: (bar_notes[idx]["pitch"], bar_notes[idx]["velocity"]))
        if not lead_note_is_drop_safe(bar_notes[peak_idx]["pitch"], allowed):
            bar_notes[peak_idx]["pitch"] = remap_to_safe_drop_tone(bar_notes[peak_idx]["pitch"], allowed)
            peak_repairs += 1
        simplified = simplify_drop_lead_bar(bar_notes)
        if len(simplified) < len(bar_notes):
            density_repairs += len(bar_notes) - len(simplified)
        repaired = replace_notes_in_bar_range(repaired, bar_index, bar_index + 1, simplified)
    return sorted(repaired, key=lambda item: (item["start"], item["pitch"])), {
        "lead_drop_density_repairs": density_repairs,
        "drop_safe_tone_repairs": safe_tone_repairs,
        "unsafe_peak_note_repairs": peak_repairs,
    }


def validate_drop_harmony(lead_notes, supersaw_notes, start_bar, end_bar, chord_lookup):
    issues = []
    safe_ratio_total = []
    unsafe_peak_note_count = 0
    supersaw_max_pitch = 0
    for bar_index in range(start_bar, end_bar):
        chord = chord_lookup(bar_index)
        allowed = build_drop_allowed_pitch_classes(chord)
        lead_bar = notes_starting_in_bar(lead_notes, bar_index)
        supersaw_bar = notes_starting_in_bar(supersaw_notes, bar_index)
        if lead_bar:
            safe_count = sum(1 for n in lead_bar if lead_note_is_drop_safe(n["pitch"], allowed))
            safe_ratio = safe_count / max(1, len(lead_bar))
            safe_ratio_total.append(safe_ratio)
            if safe_ratio < 0.8:
                issues.append((bar_index, "lead_harmony_drift"))
            peak_pitch = max(n["pitch"] for n in lead_bar)
            if (peak_pitch % 12) not in allowed:
                issues.append((bar_index, "unsafe_peak_note"))
                unsafe_peak_note_count += 1
            if len(lead_bar) > 2:
                issues.append((bar_index, "lead_too_busy_for_drop"))
            if any(length_beats(n) < 0.75 for n in lead_bar):
                issues.append((bar_index, "lead_note_too_short"))
        if supersaw_bar:
            supersaw_max_pitch = max(supersaw_max_pitch, max(n["pitch"] for n in supersaw_bar))
            if supersaw_max_pitch > 84:
                issues.append((bar_index, "supersaw_too_high"))
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "avg_safe_ratio": sum(safe_ratio_total) / max(1, len(safe_ratio_total)),
        "unsafe_peak_note_count": unsafe_peak_note_count,
        "supersaw_max_pitch": supersaw_max_pitch,
    }


def repair_drop_harmony(lead_notes, supersaw_notes, start_bar, end_bar, chord_lookup):
    repaired_lead = list(lead_notes)
    repaired_saw = list(supersaw_notes)
    supersaw_register_repairs = 0
    lead_drop_density_repairs = 0
    drop_safe_tone_repairs = 0
    unsafe_peak_note_repairs = 0
    for bar_index in range(start_bar, end_bar):
        chord = chord_lookup(bar_index)
        allowed = build_drop_allowed_pitch_classes(chord)
        bar_lead = notes_starting_in_bar(repaired_lead, bar_index)
        fixed_bar = []
        unsafe_before = 0
        for note_data in bar_lead:
            fixed = dict(note_data)
            if not lead_note_is_drop_safe(fixed["pitch"], allowed):
                fixed["pitch"] = remap_to_safe_drop_tone(fixed["pitch"], allowed)
                unsafe_before += 1
            fixed["end"] = max(fixed["end"], min(bar_tick(bar_index + 1), fixed["start"] + tick(0.75)))
            fixed_bar.append(fixed)
        if fixed_bar:
            peak_pitch_before = max(n["pitch"] for n in fixed_bar)
            if (peak_pitch_before % 12) not in allowed:
                unsafe_peak_note_repairs += 1
        fixed_bar = simplify_drop_lead_bar(sorted(fixed_bar, key=lambda n: (n["start"], n["pitch"])))
        lead_drop_density_repairs += max(0, len(bar_lead) - len(fixed_bar))
        drop_safe_tone_repairs += unsafe_before
        repaired_lead = replace_notes_in_bar_range(repaired_lead, bar_index, bar_index + 1, fixed_bar)
        bar_saw = notes_starting_in_bar(repaired_saw, bar_index)
        fixed_saw = []
        for note_data in bar_saw:
            fixed = dict(note_data)
            original_pitch = fixed["pitch"]
            while fixed["pitch"] > 84:
                fixed["pitch"] -= 12
            if fixed["pitch"] != original_pitch:
                supersaw_register_repairs += 1
            fixed_saw.append(fixed)
        repaired_saw = replace_notes_in_bar_range(repaired_saw, bar_index, bar_index + 1, fixed_saw)
    return repaired_lead, repaired_saw, {
        "supersaw_register_repairs": supersaw_register_repairs,
        "lead_drop_density_repairs": lead_drop_density_repairs,
        "drop_safe_tone_repairs": drop_safe_tone_repairs,
        "unsafe_peak_note_repairs": unsafe_peak_note_repairs,
    }


def validate_bar_harmonic_unity(bar_index, harmonic_state, stem_notes):
    allowed_pitch_classes = {
        p % 12 for p in harmonic_state["primary_pitches"] + harmonic_state["secondary_pitches"]
    }
    issues = []
    per_stem = {}
    for stem_name in ("lead", "supersaw_chords", "pad", "arp", "pluck", "strings", "piano"):
        notes = stem_notes.get(stem_name, [])
        bar_notes = notes_starting_in_bar(notes, bar_index)
        if not bar_notes:
            continue
        safe_ratio = sum(1 for n in bar_notes if (n["pitch"] % 12) in allowed_pitch_classes) / max(1, len(bar_notes))
        per_stem[stem_name] = safe_ratio
        if safe_ratio < 0.8:
            issues.append((stem_name, "harmonic_unity_fail", round(safe_ratio, 3)))
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "per_stem": per_stem,
    }


def remap_bar_to_harmonic_targets(bar_notes, harmonic_state, low=48, high=98):
    allowed = {p % 12 for p in harmonic_state["primary_pitches"] + harmonic_state["secondary_pitches"]}
    fixed = []
    for note_data in bar_notes:
        repaired = dict(note_data)
        if repaired["pitch"] % 12 not in allowed:
            repaired["pitch"] = remap_to_safe_drop_tone(repaired["pitch"], allowed, low=low, high=high)
        fixed.append(repaired)
    return fixed


def harmonic_note_bounds(stem_name: str):
    bounds = {
        "lead": (60, 98),
        "supersaw_chords": (48, 84),
        "pad": (36, 84),
        "arp": (58, 78),
        "pluck": (60, 90),
        "strings": (55, 98),
        "piano": (48, 90),
    }
    return bounds.get(stem_name, (48, 98))


def harmonic_alignment_ratio(notes, start_bar: int, end_bar: int, chord_lookup, progression_name: str, progression_family: str = ""):
    total_notes = 0
    safe_notes = 0
    for bar_index in range(start_bar, end_bar):
        harmonic_state = build_harmonic_state(bar_index, progression_name, chord_lookup(bar_index), progression_family)
        allowed = {p % 12 for p in harmonic_state["primary_pitches"] + harmonic_state["secondary_pitches"]}
        for note_data in notes_starting_in_bar(notes, bar_index):
            total_notes += 1
            if note_data["pitch"] % 12 in allowed:
                safe_notes += 1
    return round(safe_notes / max(1, total_notes), 3)


def lock_lead_to_supersaw_motif(candidate_notes, supersaw_notes, start_bar: int):
    if not supersaw_notes:
        return candidate_notes
    locked = []
    for offset in range(8):
        bar_index = start_bar + offset
        bar_start = bar_tick(bar_index)
        bar_end = bar_tick(bar_index + 1)
        bar_lead = [dict(note_data) for note_data in candidate_notes if bar_start <= note_data["start"] < bar_end]
        if not bar_lead:
            continue
        bar_saw = [note_data for note_data in supersaw_notes if bar_start <= note_data["start"] < bar_end]
        saw_pitch_classes = {note_data["pitch"] % 12 for note_data in bar_saw}
        saw_accents = sorted(
            {
                round((note_data["start"] - bar_start) / TICKS, 2)
                for note_data in bar_saw
                if length_beats(note_data) >= 0.75 or note_data["velocity"] >= 80
            }
        )
        # Accent lock: first lead attack in each bar is nudged to nearest supersaw accent.
        first_idx = min(range(len(bar_lead)), key=lambda idx: bar_lead[idx]["start"])
        if saw_accents:
            first_beat = round((bar_lead[first_idx]["start"] - bar_start) / TICKS, 2)
            nearest_accent = min(saw_accents, key=lambda beat: abs(beat - first_beat))
            if abs(nearest_accent - first_beat) <= 0.5:
                length_beats_current = length_beats(bar_lead[first_idx])
                bar_lead[first_idx]["start"] = bar_start + tick(nearest_accent)
                bar_lead[first_idx]["end"] = min(bar_end, bar_lead[first_idx]["start"] + tick(length_beats_current))
        # Harmonic lock: all lead notes in drop phrase adopt nearest supersaw harmonic pitch class.
        if saw_pitch_classes:
            for note_data in bar_lead:
                note_data["pitch"] = clamp(nearest_pitch_for_pitch_classes(note_data["pitch"], saw_pitch_classes), 60, 98)
        locked.extend(bar_lead)
    return sorted(locked or candidate_notes, key=lambda item: (item["start"], item["pitch"]))


def enforce_rhythm_contrast(phrase_notes):
    short_notes = [note_data for note_data in phrase_notes if length_beats(note_data) <= 0.5]
    long_notes = [note_data for note_data in phrase_notes if length_beats(note_data) >= 1.0]
    return bool(short_notes) and bool(long_notes)


def enforce_peak_moment(phrase_notes):
    if not phrase_notes:
        return False
    highest = max(note_data["pitch"] for note_data in phrase_notes)
    peaks = [note_data for note_data in phrase_notes if note_data["pitch"] == highest]
    return any(length_beats(note_data) >= 1.0 for note_data in peaks)


def resolve_hook_role(role: str, tones):
    return clamp(tones.get(role, tones["anchor"]), 60, 102)


def drama_profile_for_candidate(archetype: str, variant_index: int):
    profile_map = {
        ("declarative", 0): "lift_jump",
        ("declarative", 1): "surprise_gap",
        ("yearning", 0): "suspended_hold",
        ("yearning", 1): "delayed_answer",
        ("driving", 0): "lift_jump",
        ("driving", 1): "delayed_answer",
        ("open", 0): "surprise_gap",
        ("open", 1): "suspended_hold",
    }
    return profile_map.get((archetype, variant_index), DRAMA_PROFILES[(variant_index) % len(DRAMA_PROFILES)])


def hook_cell_for_archetype(archetype: str):
    cell_bank = {
        "declarative": [
            (0.0, 1.25, "anchor"),
            (2.0, 0.5, "support"),
            (3.0, 0.75, "high_anchor"),
        ],
        "yearning": [
            (0.0, 1.5, "support"),
            (2.5, 1.0, "lift"),
        ],
        "driving": [
            (0.0, 0.5, "anchor"),
            (0.5, 0.25, "support"),
            (1.0, 0.25, "anchor"),
            (1.5, 0.25, "support"),
            (2.0, 0.25, "anchor"),
            (2.5, 0.25, "lift"),
            (3.0, 0.5, "high_anchor"),
        ],
        "open": [
            (0.5, 0.75, "anchor"),
            (3.0, 1.25, "lift"),
        ],
    }
    return list(cell_bank.get(archetype, cell_bank["declarative"]))


def render_hook_cell(cell, tones, target_range, beat_shift: float = 0.0, register_shift: int = 0, length_scale: float = 1.0, rhythm_opening: bool = False, max_events: int = 5):
    rendered = []
    for idx, (beat, length, role) in enumerate(cell):
        local_beat = beat + beat_shift
        if rhythm_opening and idx > 0:
            local_beat += 0.25 * idx
        local_beat = min(3.5, max(0.0, local_beat))
        pitch = resolve_hook_role(role, tones) + register_shift
        rendered.append((local_beat, max(0.3, min(1.5, length * length_scale)), pitch))
    rendered = constrain_phrase_to_range(rendered, target_range)
    return trance_phrase_grid(rendered, step=0.5, min_length=0.3, max_events=max_events)


def vary_hook_cell(cell, archetype: str):
    varied = list(cell)
    if not varied:
        return varied
    if archetype == "declarative":
        varied = [
            (0.0, 1.0, "anchor"),
            (1.5, 0.5, "support"),
            (3.0, 1.0, "resolve"),
        ]
    elif archetype == "yearning":
        varied = [
            (0.0, 1.25, "support"),
            (2.0, 0.75, "lift"),
            (3.25, 0.75, "high_anchor"),
        ]
    elif archetype == "driving":
        varied = [
            (0.0, 0.25, "anchor"),
            (0.5, 0.25, "support"),
            (1.0, 0.25, "anchor"),
            (1.5, 0.25, "support"),
            (2.5, 0.25, "lift"),
            (3.25, 0.5, "resolve"),
        ]
    elif archetype == "open":
        varied = [(0.0, 0.5, "anchor"), (2.5, 0.75, "lift"), (3.5, 0.5, "resolve")]
    return varied


def simplify_hook_cell(cell, include_pickup: bool = True):
    if not cell:
        return []
    simple = [cell[0]]
    if include_pickup and len(cell) > 1:
        simple.append((min(3.0, cell[-1][0]), max(0.5, cell[-1][1]), cell[-1][2]))
    return simple[:2]


def add_interval_jump(phrase, min_jump: int = 5):
    if not phrase:
        return phrase
    adjusted = list(phrase)
    beat, length, pitch = adjusted[-1]
    adjusted[-1] = (beat, length, pitch + min_jump)
    return adjusted


def add_space_before_resolution(phrase):
    if not phrase:
        return phrase
    adjusted = []
    for idx, (beat, length, pitch) in enumerate(phrase):
        if idx == len(phrase) - 1:
            adjusted.append((min(3.25, beat + 0.5), length, pitch))
        else:
            adjusted.append((beat, length, pitch))
    return adjusted


def force_suspension_then_resolve(payoff):
    if not payoff:
        return payoff
    adjusted = list(payoff)
    if len(adjusted) == 1:
        beat, length, pitch = adjusted[0]
        return [(beat, max(0.75, length * 0.5), pitch + 2), (min(3.0, beat + 1.0), max(1.25, length), pitch)]
    beat, length, pitch = adjusted[-1]
    adjusted[-1] = (beat, max(1.25, length), pitch - 2)
    adjusted.append((min(3.5, beat + 1.0), 1.25, pitch))
    return adjusted


def insert_half_bar_gap_before_peak(payoff):
    if not payoff:
        return payoff
    adjusted = []
    for idx, (beat, length, pitch) in enumerate(payoff):
        if idx == len(payoff) - 1:
            adjusted.append((min(3.0, beat + 0.5), max(1.0, length), pitch))
        else:
            adjusted.append((beat, length, pitch))
    return adjusted


def apply_drama_profile(phrase_b, payoff, profile):
    if profile == "lift_jump":
        phrase_b = add_interval_jump(phrase_b, min_jump=5)
    elif profile == "delayed_answer":
        phrase_b = add_space_before_resolution(phrase_b)
    elif profile == "suspended_hold":
        payoff = force_suspension_then_resolve(payoff)
    elif profile == "surprise_gap":
        payoff = insert_half_bar_gap_before_peak(payoff)
    return phrase_b, payoff


def phrase_tones_for_bar(chord, identity, offset: int, section_name: str):
    register_targets = get_lead_register_targets(section_name)
    a_low, a_high = register_targets["a_range"]
    b_low, b_high = register_targets["b_range"]
    p_low, p_high = register_targets["payoff_range"]
    anchor = clamp(max(identity["anchor"], chord["root"] + 12), a_low, a_high + 4)
    support = clamp(max(chord["third"] + 12, identity["support"] - 12), a_low, b_high)
    lift = clamp(max(chord["fifth"] + 12, identity["lift"] - 12), b_low, p_high + 2)
    resolve = clamp(max(chord["root"] + 12, identity["resolve"] - 12), a_low, p_high)
    high_anchor = clamp(max(anchor + 5, chord["root"] + 24), b_low, p_high + 4)
    return {
        "anchor": anchor,
        "support": support,
        "lift": lift,
        "resolve": resolve,
        "high_anchor": high_anchor,
        "register_targets": register_targets,
        "bar_offset": offset,
    }


def generate_hook_phrase_candidate(start_bar: int, chords, identity, section_name: str, archetype: str, variant_index: int = 0):
    candidate = []
    cell = hook_cell_for_archetype(archetype)
    varied_cell = vary_hook_cell(cell, archetype)
    phrase_b_cell = vary_hook_cell(varied_cell, archetype)
    payoff_cell = simplify_hook_cell(cell, include_pickup=True)
    drama_profile = drama_profile_for_candidate(archetype, variant_index)
    register_targets = get_lead_register_targets(section_name)
    for offset in range(8):
        chord = chords[(start_bar + offset) % len(chords)]
        tones = phrase_tones_for_bar(chord, identity, offset, section_name)
        beat_shift = 0.0
        register_shift = 0
        length_scale = 1.0
        if variant_index == 1:
            if archetype == "declarative":
                beat_shift = 0.0
                register_shift = 2 if offset >= 4 else 0
                length_scale = 0.95
            elif archetype == "yearning":
                length_scale = 1.25
                register_shift = -3 if offset < 4 else 3
            elif archetype == "driving":
                beat_shift = 0.0
                length_scale = 0.8
                register_shift = 2 if offset >= 4 else 0
            elif archetype == "open":
                beat_shift = 0.5 if offset in (0, 2, 4) else 0.0
                length_scale = 1.2
                register_shift = -2 if offset < 4 else 0
        if offset == 0:
            phrase = render_hook_cell(cell, tones, register_targets["a_range"], beat_shift=beat_shift, register_shift=register_shift, length_scale=length_scale, max_events=4)
        elif offset == 1:
            phrase = render_hook_cell(varied_cell, tones, register_targets["a_range"], beat_shift=beat_shift, register_shift=register_shift, length_scale=0.95 * length_scale, max_events=4)
        elif offset == 2:
            phrase = render_hook_cell(cell, tones, register_targets["a_range"], beat_shift=beat_shift, register_shift=register_shift, max_events=4)
        elif offset == 3:
            phrase = render_hook_cell(varied_cell, tones, register_targets["a_range"], beat_shift=beat_shift, register_shift=register_shift, length_scale=1.0 * length_scale, max_events=4)
        elif offset == 4:
            phrase = render_hook_cell(phrase_b_cell, tones, register_targets["b_range"], beat_shift=beat_shift, register_shift=5 + register_shift, length_scale=0.9 * length_scale, max_events=4)
        elif offset == 5:
            phrase = render_hook_cell(phrase_b_cell, tones, register_targets["b_range"], beat_shift=beat_shift, register_shift=(7 if archetype != "open" else 5) + register_shift, length_scale=1.0 * length_scale, rhythm_opening=True, max_events=4)
            phrase, _ = apply_drama_profile(phrase, [], drama_profile)
        elif offset == 6:
            prep = payoff_cell + [(2.5, 0.5, "lift")]
            phrase = render_hook_cell(prep, tones, register_targets["payoff_range"], beat_shift=beat_shift, register_shift=5 + register_shift, length_scale=1.1 * length_scale, rhythm_opening=True, max_events=3)
        else:
            highest = max(tones["high_anchor"], tones["lift"] + 2)
            if archetype == "declarative":
                phrase = [
                    (0.0, 0.75, clamp(tones["lift"], register_targets["payoff_range"][0], register_targets["payoff_range"][1])),
                    (2.0, 2.0, clamp(max(highest, tones["high_anchor"]), register_targets["payoff_range"][0], register_targets["payoff_range"][1])),
                ]
            elif archetype == "yearning":
                phrase = [
                    (0.5, 1.0, clamp(tones["lift"], register_targets["payoff_range"][0], register_targets["payoff_range"][1])),
                    (2.5, 1.5, clamp(tones["resolve"], register_targets["payoff_range"][0], register_targets["payoff_range"][1])),
                ]
            elif archetype == "driving":
                phrase = [
                    (0.0, 0.5, clamp(tones["lift"], register_targets["payoff_range"][0], register_targets["payoff_range"][1])),
                    (1.0, 0.5, clamp(highest, register_targets["payoff_range"][0], register_targets["payoff_range"][1])),
                    (2.0, 0.5, clamp(tones["lift"], register_targets["payoff_range"][0], register_targets["payoff_range"][1])),
                    (3.0, 1.0, clamp(max(highest, tones["high_anchor"]), register_targets["payoff_range"][0], register_targets["payoff_range"][1])),
                ]
            else:
                phrase = [
                    (1.0, 0.75, clamp(tones["lift"], register_targets["payoff_range"][0], register_targets["payoff_range"][1])),
                    (3.0, 1.0, clamp(tones["resolve"], register_targets["payoff_range"][0], register_targets["payoff_range"][1])),
                ]
            _, phrase = apply_drama_profile([], phrase, drama_profile)
            phrase = trance_phrase_grid(phrase, step=0.5, min_length=0.5, max_events=3)
        bar_start = bar_tick(start_bar + offset)
        velocity = 96 if offset >= 4 else 88
        if offset >= 6:
            velocity = 102
        for beat_pos, beat_len, pitch in phrase:
            candidate.append({
                "start": bar_start + tick(beat_pos),
                "end": bar_start + tick(beat_pos + beat_len),
                "pitch": clamp(pitch, 60, 98),
                "velocity": velocity,
                "channel": 0,
            })
    return sorted(candidate, key=lambda item: (item["start"], item["pitch"])), drama_profile


def extract_supersaw_accent_pattern(supersaw_notes, start_bar, bars=2, step=0.5):
    pattern = []
    for offset in range(bars):
        bar_index = start_bar + offset
        bar_start = bar_tick(bar_index)
        bar_notes = [
            n for n in supersaw_notes
            if bar_start <= n["start"] < bar_tick(bar_index + 1)
        ]
        accents = []
        for note_data in bar_notes:
            beat = round((note_data["start"] - bar_start) / TICKS, 2)
            if length_beats(note_data) >= 0.75 or note_data["velocity"] >= 80:
                accents.append(round(round(beat / step) * step, 2))
        pattern.extend(sorted(set(accents)))
    return pattern[:4]


def generate_motif_seed(chord, identity, rhythm_pattern, register_range):
    tones = [
        clamp(chord["root"] + 12, register_range[0], register_range[1]),
        clamp(chord["third"] + 12, register_range[0], register_range[1]),
        clamp(chord["fifth"] + 12, register_range[0], register_range[1]),
    ]
    motif = []
    ordered_pattern = rhythm_pattern[:4] if rhythm_pattern else [0.0, 1.0, 2.0, 3.0]
    pitch_order = [tones[0], tones[1], tones[2], tones[0]]
    for idx, beat in enumerate(ordered_pattern):
        length = 0.5 if idx < 2 else 0.75
        motif.append((beat, length, pitch_order[idx % len(pitch_order)]))
    return motif


def vary_motif_pitch_only(motif, chord, register_range):
    variation = list(motif)
    chord_tones = [
        clamp(chord["root"] + 12, register_range[0], register_range[1]),
        clamp(chord["third"] + 12, register_range[0], register_range[1]),
        clamp(chord["fifth"] + 12, register_range[0], register_range[1]),
    ]
    for idx in range(1, min(3, len(variation))):
        beat, length, pitch = variation[idx]
        replacement = chord_tones[(idx + 1) % len(chord_tones)]
        if replacement != pitch:
            variation[idx] = (beat, length, replacement)
            break
    return variation


def build_answer_phrase_from_motif(motif, chord, register_range):
    answer = []
    for idx, (beat, length, pitch) in enumerate(motif):
        new_pitch = pitch + (5 if idx % 2 == 0 else 7)
        answer.append((beat, length if idx < 2 else 0.75, clamp(new_pitch, register_range[0], register_range[1])))
    return answer[:4]


def build_payoff_from_motif(motif, chord, register_range):
    root = clamp(chord["root"] + 12, register_range[0], register_range[1])
    third = clamp(chord["third"] + 12, register_range[0], register_range[1])
    fifth = clamp(chord["fifth"] + 12, register_range[0], register_range[1])
    high_note = clamp(fifth + 12, register_range[0], register_range[1])
    return [
        (0.0, 0.75, fifth),
        (1.5, 0.5, high_note),
        (2.5, 1.5, root if random.choice([True, False]) else third),
    ]


def safe_lead_tone_for_chord(source_pitch, chord, low=72, high=86, prefer=("root", "third", "fifth")):
    allowed = {chord[name] % 12 for name in prefer}
    return remap_to_safe_drop_tone(clamp(source_pitch, low, high), allowed, low=low, high=high)


def hook_target_from_harmonic_state(harmonic_state, chord, low=72, high=84, preference="primary"):
    pool = harmonic_target_pool(harmonic_state, octave_shift=12)
    choices = pool["primary"] if preference == "primary" else pool["secondary"] or pool["primary"]
    if not choices:
        choices = [chord["root"] + 12, chord["third"] + 12]
    return safe_lead_tone_for_chord(choices[0], chord, low=low, high=high)


def hook_rhythm_from_supersaw(supersaw_notes, start_bar):
    accents = extract_supersaw_accent_pattern(supersaw_notes, start_bar, bars=2, step=0.5)
    usable = []
    for beat in accents:
        local_beat = round(beat % 4.0, 2)
        if 0.0 <= local_beat <= 2.75 and all(abs(local_beat - existing) >= 1.0 for existing in usable):
            usable.append(local_beat)
        if len(usable) == 2:
            break
    return tuple(usable) if len(usable) == 2 else (0.0, 2.0)


def simplify_lead_bar_for_hook(bar_notes):
    ordered = sorted((dict(note_data) for note_data in bar_notes), key=lambda n: (n["start"], n["pitch"]))
    if len(ordered) <= 2:
        return ordered
    first = ordered[0]
    strongest = max(
        ordered[1:],
        key=lambda n: (n["velocity"], n["pitch"], n["end"] - n["start"]),
        default=first,
    )
    kept = [first]
    if strongest is not first:
        kept.append(strongest)
    return sorted(kept[:2], key=lambda n: (n["start"], n["pitch"]))


def build_simple_motif(chord, harmonic_state, rhythm_pattern, register_range=(76, 80)):
    first_pitch = hook_target_from_harmonic_state(harmonic_state, chord, low=register_range[0], high=register_range[1], preference="primary")
    second_source = harmonic_target_pool(harmonic_state, octave_shift=12)["secondary"] or [chord["fifth"] + 12]
    second_pitch = safe_lead_tone_for_chord(second_source[0], chord, low=register_range[0], high=register_range[1])
    if second_pitch == first_pitch:
        second_pitch = safe_lead_tone_for_chord(first_pitch + 4, chord, low=register_range[0], high=register_range[1])
    return [
        (rhythm_pattern[0], 1.0, first_pitch),
        (rhythm_pattern[1], 1.25, second_pitch),
    ]


def build_lift_from_motif(motif, chord, register_shift=3, register_range=(76, 84)):
    lifted = []
    for beat, length, pitch in motif[:2]:
        lifted.append((
            beat,
            max(1.0, length),
            safe_lead_tone_for_chord(pitch + register_shift, chord, low=register_range[0], high=register_range[1]),
        ))
    return lifted


def build_single_lift_note_from_motif(motif, chord, register_shift=4, register_range=(79, 84), expressive=True):
    beat, length, pitch = motif[-1] if motif else (2.0, 1.0, chord["third"] + 12)
    shifted_beat = min(2.5, beat + 0.5)
    lift_interval = 7 if expressive and pitch + 7 <= register_range[1] else 4 if expressive else register_shift
    return [(
        shifted_beat,
        max(1.0, min(1.25, length)),
        safe_lead_tone_for_chord(pitch + max(register_shift, lift_interval), chord, low=register_range[0], high=register_range[1]),
    )]


def build_long_payoff_note(chord, harmonic_state, start_beat=1.0, length=1.75, register_range=(78, 86), prefer_third=False):
    target_name = "third" if prefer_third else ("root" if harmonic_state["function"] in ("I", "vi") else "third")
    pitch = safe_lead_tone_for_chord(chord[target_name] + 24, chord, low=register_range[0], high=register_range[1], prefer=("root", "third"))
    return [(start_beat, length, pitch)]


def build_pre_payoff_leap_note(payoff_pitch, start_beat=0.0, length=0.75):
    leap_interval = 7 if payoff_pitch - 7 >= 72 else 5
    return (start_beat, length, clamp(payoff_pitch - leap_interval, 72, 84))


def motif_template_from_bar(lead_notes, bar_index):
    template = []
    for note_data in simplify_lead_bar_for_hook(notes_starting_in_bar(lead_notes, bar_index)):
        beat = round((note_data["start"] - bar_tick(bar_index)) / TICKS, 2)
        template.append((
            beat,
            max(0.65, min(1.25, length_beats(note_data))),
            note_data["pitch"],
            note_data["velocity"],
        ))
    return template[:2]


def motif_identity_positions(lead_notes, start_bar):
    positions = set()
    for offset in range(4):
        bar_index = start_bar + offset
        for note_data in notes_starting_in_bar(lead_notes, bar_index):
            beat = round((note_data["start"] - bar_tick(bar_index)) / TICKS, 2)
            positions.add((bar_index, beat))
    return positions


def lead_duration_report(lead_notes):
    lengths = [length_beats(note_data) for note_data in lead_notes]
    total_duration = sum(lengths)
    long_duration = sum(length for length in lengths if length >= 1.0)
    return {
        "lead_long_note_ratio": round(long_duration / max(0.01, total_duration), 3),
        "lead_avg_note_length": round(total_duration / max(1, len(lengths)), 2),
        "lead_sustained_note_count": sum(1 for length in lengths if length >= 1.0),
    }


def merge_adjacent_lead_notes(lead_notes, start_bar, max_gap_beats=0.5, max_pitch_distance=2):
    ordered = sorted((dict(note_data) for note_data in lead_notes), key=lambda item: (item["start"], item["pitch"]))
    if not ordered:
        return [], 0, False
    merged = []
    merge_count = 0
    for note_data in ordered:
        if not merged:
            merged.append(note_data)
            continue
        previous = merged[-1]
        same_bar = previous["start"] // BAR_TICKS == note_data["start"] // BAR_TICKS
        gap_beats = (note_data["start"] - previous["end"]) / TICKS
        close_pitch = abs(note_data["pitch"] - previous["pitch"]) <= max_pitch_distance
        in_phrase = start_bar <= note_data["start"] // BAR_TICKS < start_bar + 8
        if in_phrase and same_bar and close_pitch and 0 <= gap_beats <= max_gap_beats:
            previous["end"] = max(previous["end"], note_data["end"])
            previous["pitch"] = max(previous["pitch"], note_data["pitch"])
            previous["velocity"] = max(previous["velocity"], note_data["velocity"])
            merge_count += 1
        else:
            merged.append(note_data)
    return merged, merge_count, merge_count > 0


def enforce_lead_sustain_dominance(lead_notes, start_bar):
    motif_positions = motif_identity_positions(lead_notes, start_bar)
    repaired = []
    removed_count = 0
    changed = False
    for note_data in sorted((dict(note) for note in lead_notes), key=lambda item: (item["start"], item["pitch"])):
        bar_index = note_data["start"] // BAR_TICKS
        beat = round((note_data["start"] - bar_tick(bar_index)) / TICKS, 2)
        is_motif_identity = (bar_index, beat) in motif_positions and start_bar <= bar_index < start_bar + 4
        min_allowed = 0.75 if start_bar <= bar_index < start_bar + 8 else 0.5
        if length_beats(note_data) < min_allowed and not is_motif_identity:
            removed_count += 1
            changed = True
            continue
        min_length = 1.0 if is_motif_identity else 0.75
        if bar_index >= start_bar + 6:
            min_length = 1.75
        original_end = note_data["end"]
        note_data["end"] = max(note_data["end"], min(bar_tick(bar_index + 1), note_data["start"] + tick(min_length)))
        if note_data["end"] != original_end:
            changed = True
        repaired.append(note_data)

    repaired, merge_count, merged = merge_adjacent_lead_notes(repaired, start_bar)
    changed = changed or merged

    report = lead_duration_report(repaired)
    if report["lead_long_note_ratio"] < 0.6:
        for note_data in repaired:
            bar_index = note_data["start"] // BAR_TICKS
            original_end = note_data["end"]
            note_data["end"] = max(note_data["end"], min(bar_tick(bar_index + 1), note_data["start"] + tick(1.0)))
            if note_data["end"] != original_end:
                changed = True
        report = lead_duration_report(repaired)
    report["lead_short_note_removed_count"] = removed_count
    report["lead_merged_note_count"] = merge_count
    return sorted(repaired, key=lambda item: (item["start"], item["pitch"])), changed, report


def enforce_single_hook_identity(lead_notes, start_bar):
    motif_template = motif_template_from_bar(lead_notes, start_bar)
    if not motif_template:
        return sorted(lead_notes, key=lambda item: (item["start"], item["pitch"])), False
    repaired = [dict(note_data) for note_data in lead_notes]
    changed = False
    for offset in range(4):
        bar_index = start_bar + offset
        bar_start = bar_tick(bar_index)
        replacement = []
        for beat, length, pitch, velocity in motif_template:
            replacement.append({
                "start": bar_start + tick(beat),
                "end": bar_start + tick(min(4.0, beat + length)),
                "pitch": clamp(pitch, 72, 86),
                "velocity": clamp(velocity, 0, 124),
                "channel": 0,
            })
        original = notes_starting_in_bar(repaired, bar_index)
        if original != replacement:
            changed = True
        repaired = replace_notes_in_bar_range(repaired, bar_index, bar_index + 1, replacement)
    repaired, _, merged = merge_adjacent_lead_notes(repaired, start_bar)
    return sorted(repaired, key=lambda item: (item["start"], item["pitch"])), changed or merged


def enforce_hook_pitch_spread(lead_notes, max_spread=10):
    payoff = get_payoff_note(lead_notes)
    if not payoff:
        return sorted(lead_notes, key=lambda item: (item["start"], item["pitch"])), False
    changed = False
    low = max(72, payoff["pitch"] - max_spread)
    high = min(84, payoff["pitch"] - 2)
    if high < low:
        high = low
    repaired = []
    for note_data in lead_notes:
        is_payoff = note_data is payoff
        cloned = dict(note_data)
        if not is_payoff and cloned["start"] < payoff["start"]:
            original_pitch = cloned["pitch"]
            cloned["pitch"] = clamp(cloned["pitch"], low, high)
            if cloned["pitch"] != original_pitch:
                changed = True
        repaired.append(cloned)
    return sorted(repaired, key=lambda item: (item["start"], item["pitch"])), changed


def motif_pitch_change_count(lead_notes, start_bar):
    base = sorted(notes_starting_in_bar(lead_notes, start_bar), key=lambda item: (item["start"], item["pitch"]))
    changes = 0
    for offset in range(1, 4):
        current = sorted(notes_starting_in_bar(lead_notes, start_bar + offset), key=lambda item: (item["start"], item["pitch"]))
        if len(current) != len(base):
            changes += abs(len(current) - len(base))
        for idx in range(min(len(base), len(current))):
            base_beat = round((base[idx]["start"] - bar_tick(start_bar)) / TICKS, 2)
            current_beat = round((current[idx]["start"] - bar_tick(start_bar + offset)) / TICKS, 2)
            if abs(base_beat - current_beat) > 0.01 or base[idx]["pitch"] != current[idx]["pitch"]:
                changes += 1
    return changes


def lead_interval_jump_report(lead_notes, start_bar):
    ordered = sorted(
        [note_data for offset in range(8) for note_data in notes_starting_in_bar(lead_notes, start_bar + offset)],
        key=lambda item: (item["start"], item["pitch"]),
    )
    expressive_jumps = []
    pre_payoff_jump = 0
    payoff = get_payoff_note(ordered)
    for idx in range(len(ordered) - 1):
        current = ordered[idx]
        nxt = ordered[idx + 1]
        interval = nxt["pitch"] - current["pitch"]
        current_bar = current["start"] // BAR_TICKS
        next_bar = nxt["start"] // BAR_TICKS
        in_lift_zone = current_bar >= start_bar + 4 or next_bar >= start_bar + 4
        if in_lift_zone and interval in (4, 5, 7):
            expressive_jumps.append(interval)
        if payoff and nxt["start"] == payoff["start"]:
            pre_payoff_jump = interval
    return {
        "lead_expressive_jump_count": len(expressive_jumps),
        "lead_largest_upward_jump": max(expressive_jumps, default=0),
        "lead_pre_payoff_jump": pre_payoff_jump,
        "lead_controlled_jump_passed": 1 <= len(expressive_jumps) <= 2 and pre_payoff_jump in (5, 7),
    }


def build_hook_dominant_lead_phrase(start_bar, chords, harmonic_states, section_name, supersaw_notes=None):
    rhythm = hook_rhythm_from_supersaw(supersaw_notes or [], start_bar)
    phrase_map = []
    motif = build_simple_motif(chords[start_bar % len(chords)], harmonic_states[0], rhythm, register_range=(76, 80))
    for offset in range(8):
        chord = chords[(start_bar + offset) % len(chords)]
        harmonic_state = harmonic_states[offset]
        if offset in (0, 1, 2, 3):
            phrase = motif
        elif offset == 4:
            phrase = build_single_lift_note_from_motif(motif, chord, register_shift=2, register_range=(78, 82), expressive=False)
        elif offset == 5:
            phrase = build_single_lift_note_from_motif(motif, chord, register_shift=4, register_range=(79, 84))
        elif offset == 6:
            payoff = build_long_payoff_note(chord, harmonic_state, start_beat=1.0, length=2.25, register_range=(81, 86), prefer_third=False)[0]
            phrase = [build_pre_payoff_leap_note(payoff[2], start_beat=0.0, length=0.75), payoff]
        else:
            phrase = build_long_payoff_note(chord, harmonic_state, start_beat=0.5, length=2.5, register_range=(80, 86), prefer_third=True)
        phrase_map.append(phrase)

    phrase_notes = []
    for offset, phrase in enumerate(phrase_map):
        bar_start = bar_tick(start_bar + offset)
        velocity = 84 if offset < 4 else 99
        if offset >= 6:
            velocity = 108
        for beat, length, pitch in phrase[:2]:
            phrase_notes.append({
                "start": bar_start + tick(beat),
                "end": bar_start + tick(min(4.0, beat + length)),
                "pitch": clamp(pitch, 72, 86),
                "velocity": velocity,
                "channel": 0,
            })
    phrase_notes, _ = enforce_single_hook_identity(sorted(phrase_notes, key=lambda item: (item["start"], item["pitch"])), start_bar)
    phrase_notes, _ = enforce_payoff_dominance(phrase_notes)
    phrase_notes, _ = enforce_hook_pitch_spread(phrase_notes, max_spread=10)
    phrase_notes, _ = enforce_single_hook_identity(phrase_notes, start_bar)
    phrase_notes, _, _ = enforce_lead_sustain_dominance(phrase_notes, start_bar)
    phrase_notes, _ = enforce_payoff_dominance(phrase_notes)
    return phrase_notes


def build_drop_lead_phrase_from_motif(start_bar, chords, supersaw_notes, identity, section_name):
    progression_name = identity.get("progression_name", "uplifting")
    progression_family = identity.get("progression_family", "")
    harmonic_states = [
        build_harmonic_state(start_bar + offset, progression_name, chords[(start_bar + offset) % len(chords)], progression_family)
        for offset in range(8)
    ]
    return build_hook_dominant_lead_phrase(start_bar, chords, harmonic_states, section_name, supersaw_notes=supersaw_notes)


def enforce_motif_interval_grammar(candidate_notes, start_bar: int):
    if not candidate_notes:
        return candidate_notes
    ordered = sorted((dict(note_data) for note_data in candidate_notes), key=lambda item: (item["start"], item["pitch"]))
    previous_pitch = ordered[0]["pitch"]
    for idx in range(1, len(ordered)):
        note_data = ordered[idx]
        bar_index = note_data["start"] // BAR_TICKS
        jump_limit = 9 if bar_index >= start_bar + 6 else 7
        interval = note_data["pitch"] - previous_pitch
        if abs(interval) > jump_limit:
            note_data["pitch"] = clamp(previous_pitch + (jump_limit if interval > 0 else -jump_limit), 60, 98)
        previous_pitch = note_data["pitch"]
    return ordered


def motif_interval_profile(notes, start_bar: int, bars: int):
    profile = []
    ordered = sorted(
        [note_data for offset in range(bars) for note_data in notes_starting_in_bar(notes, start_bar + offset)],
        key=lambda item: (item["start"], item["pitch"]),
    )
    for idx in range(len(ordered) - 1):
        delta = ordered[idx + 1]["pitch"] - ordered[idx]["pitch"]
        if delta > 0:
            profile.append(1)
        elif delta < 0:
            profile.append(-1)
        else:
            profile.append(0)
    return tuple(profile)


def score_motif_interval_identity(lead_notes, start_bar: int):
    ordered = sorted(
        [note_data for offset in range(8) for note_data in notes_starting_in_bar(lead_notes, start_bar + offset)],
        key=lambda item: (item["start"], item["pitch"]),
    )
    if len(ordered) < 4:
        return {"score": 0, "passed": False, "rejection_reasons": ["motif_interval_profile_missing"]}
    max_interval = max(abs(ordered[idx + 1]["pitch"] - ordered[idx]["pitch"]) for idx in range(len(ordered) - 1))
    bars_1_2_profile = motif_interval_profile(lead_notes, start_bar, bars=2)
    bars_3_4_profile = motif_interval_profile(lead_notes, start_bar + 2, bars=2)
    contour_match = rhythm_pattern_match_ratio(bars_1_2_profile, bars_3_4_profile) if bars_1_2_profile or bars_3_4_profile else 0.0
    score = 0
    if max_interval <= 9:
        score += 2
    if contour_match >= 0.55:
        score += 2
    rejection_reasons = []
    if max_interval > 9:
        rejection_reasons.append("motif_interval_jumps_too_large")
    if contour_match < 0.55:
        rejection_reasons.append("motif_interval_contour_not_repeating")
    return {"score": score, "passed": score >= 3, "rejection_reasons": rejection_reasons}


def build_motif_driven_hook_phrase(start_bar: int, chords, identity, section_name: str):
    return enforce_motif_interval_grammar(
        build_drop_lead_phrase_from_motif(start_bar, chords, [], identity, section_name),
        start_bar,
    )


def candidate_distinctiveness(candidate_notes, reference_notes, start_bar: int):
    candidate_sig = rhythm_pattern_signature(candidate_notes, start_bar, bars=4, step=0.5)
    reference_sig = rhythm_pattern_signature(reference_notes, start_bar, bars=4, step=0.5)
    rhythm_distance = 1.0 - rhythm_pattern_match_ratio(candidate_sig, reference_sig)
    density_distance = min(1.0, abs(phrase_note_density(candidate_notes, start_bar, 8) - phrase_note_density(reference_notes, start_bar, 8)) / 2.0)
    span_distance = min(1.0, abs(phrase_pitch_span(candidate_notes, start_bar, 8) - phrase_pitch_span(reference_notes, start_bar, 8)) / 8.0)
    return round(rhythm_distance * 2.5 + density_distance * 1.0 + span_distance * 0.75, 2)


def candidate_window_signature(candidate_notes, start_bar: int):
    return {
        "archetype_rhythm": rhythm_pattern_signature(candidate_notes, start_bar, bars=4, step=0.5),
        "payoff_shape": extract_payoff_shape(candidate_notes, start_bar),
    }


def hook_repetition_penalty(candidate, recent_winners, start_bar: int):
    if not recent_winners:
        return 0.0
    penalty = 0.0
    signature = candidate_window_signature(candidate["notes"], start_bar)
    last = recent_winners[-1]
    if candidate["archetype"] == last.get("archetype"):
        penalty += 0.9
    if signature["archetype_rhythm"] == last.get("signature", {}).get("archetype_rhythm"):
        penalty += 0.9
    if signature["payoff_shape"] and signature["payoff_shape"] == last.get("signature", {}).get("payoff_shape"):
        penalty += 0.7
    if len(recent_winners) >= 2:
        two_back = recent_winners[-2]
        if candidate["archetype"] == two_back.get("archetype"):
            penalty += 0.45
    return round(min(2.25, penalty), 2)


def extract_rhythm_fingerprint(candidate_notes, start_bar: int):
    return rhythm_pattern_signature(candidate_notes, start_bar, bars=4, step=0.5)


def extract_interval_profile(candidate_notes):
    ordered = sorted(candidate_notes, key=lambda item: (item["start"], item["pitch"]))
    return tuple(abs(ordered[idx + 1]["pitch"] - ordered[idx]["pitch"]) for idx in range(len(ordered) - 1))


def extract_payoff_shape(candidate_notes, start_bar: int):
    payoff = [note_data for note_data in candidate_notes if start_bar + 6 <= note_data["start"] // BAR_TICKS < start_bar + 8]
    return tuple((round((note_data["end"] - note_data["start"]) / TICKS, 2), note_data["pitch"]) for note_data in payoff[:4])


def candidate_diversity_signature(candidate_notes, start_bar: int, drama_profile: str):
    return {
        "rhythm": extract_rhythm_fingerprint(candidate_notes, start_bar),
        "density": round(phrase_note_density(candidate_notes, start_bar, 8), 2),
        "interval_profile": extract_interval_profile(candidate_notes),
        "payoff_shape": extract_payoff_shape(candidate_notes, start_bar),
        "drama_profile": drama_profile,
    }


def compare_signatures(sig_a, sig_b):
    overlap = 0.0
    if sig_a["rhythm"] == sig_b["rhythm"]:
        overlap += 0.4
    if abs(sig_a["density"] - sig_b["density"]) <= 0.5:
        overlap += 0.15
    if sig_a["payoff_shape"] == sig_b["payoff_shape"]:
        overlap += 0.2
    if sig_a["drama_profile"] == sig_b["drama_profile"]:
        overlap += 0.1
    if sig_a["interval_profile"][:4] == sig_b["interval_profile"][:4]:
        overlap += 0.15
    return overlap


def too_similar(sig_a, sig_b):
    return compare_signatures(sig_a, sig_b) > 0.75


def enforce_payoff_rules(bars_7_8, root_pc: int, third_pc: int, previous_density: int, phrase_highest_pitch: int):
    payoff_notes = list(bars_7_8["notes"])
    adjusted = []
    payoff_start_bar = bars_7_8["start_bar"]
    if not payoff_notes:
        return {"notes": payoff_notes, "changed": False, "rejection_reasons": ["no_sustained_payoff_note", "no_clear_resolution", "no_emotional_peak_in_payoff"]}
    payoff_start = bar_tick(payoff_start_bar)
    payoff_end = bar_tick(payoff_start_bar + 2)
    highest_pitch = max(note_data["pitch"] for note_data in payoff_notes)
    final_note_idx = max(range(len(payoff_notes)), key=lambda idx: payoff_notes[idx]["end"])
    adjusted_payoff = []
    for idx, note_data in enumerate(sorted(payoff_notes, key=lambda item: (item["start"], item["pitch"]))):
        cloned = dict(note_data)
        if idx == final_note_idx:
            target_pc = cloned["pitch"] % 12
            if target_pc not in (root_pc, third_pc):
                if (cloned["pitch"] - target_pc + root_pc) <= 98:
                    cloned["pitch"] = clamp(cloned["pitch"] - target_pc + root_pc, 60, 98)
                else:
                    cloned["pitch"] = clamp(cloned["pitch"] - target_pc + third_pc, 60, 98)
            cloned["end"] = max(cloned["end"], min(payoff_end, cloned["start"] + tick(1.5)))
            highest_pitch = max(highest_pitch, cloned["pitch"])
        adjusted_payoff.append(cloned)
    if adjusted_payoff:
        peak_idx = max(range(len(adjusted_payoff)), key=lambda idx: adjusted_payoff[idx]["pitch"])
        adjusted_payoff[peak_idx]["pitch"] = max(adjusted_payoff[peak_idx]["pitch"], min(98, max(highest_pitch, phrase_highest_pitch)))
        adjusted_payoff[peak_idx]["end"] = max(adjusted_payoff[peak_idx]["end"], min(payoff_end, adjusted_payoff[peak_idx]["start"] + tick(1.0)))
    payoff_density = len(adjusted_payoff)
    if payoff_density >= previous_density and len(adjusted_payoff) > 2:
        adjusted_payoff = sorted(adjusted_payoff, key=lambda item: (item["end"] - item["start"], item["pitch"]), reverse=True)[:2]
        adjusted_payoff = sorted(adjusted_payoff, key=lambda item: (item["start"], item["pitch"]))
    rejection_reasons = []
    if not any((note_data["end"] - note_data["start"]) / TICKS >= 1.0 for note_data in adjusted_payoff):
        rejection_reasons.append("no_sustained_payoff_note")
    final_pitch = adjusted_payoff[-1]["pitch"] % 12 if adjusted_payoff else None
    if final_pitch not in (root_pc, third_pc):
        rejection_reasons.append("no_clear_resolution")
    if len(adjusted_payoff) >= previous_density:
        rejection_reasons.append("payoff_not_sparser_than_bars_5_6")
    if max((note_data["pitch"] for note_data in adjusted_payoff), default=0) < phrase_highest_pitch:
        rejection_reasons.append("no_emotional_peak_in_payoff")
    return {
        "notes": sorted(adjusted_payoff, key=lambda item: (item["start"], item["pitch"])),
        "changed": True,
        "rejection_reasons": rejection_reasons,
    }


def apply_payoff_rules_to_phrase(lead_notes, start_bar: int, root_pc: int, third_pc: int):
    pipeline = build_hook_phrase_pipeline(lead_notes, start_bar)
    previous_density = len(pipeline["bars_5_6"]["notes"])
    phrase_highest_pitch = max((note_data["pitch"] for note_data in pipeline["all_notes"]), default=0)
    payoff_result = enforce_payoff_rules(
        pipeline["bars_7_8"],
        root_pc,
        third_pc,
        previous_density,
        phrase_highest_pitch,
    )
    adjusted = list(pipeline["bars_1_4"]["notes"]) + list(pipeline["bars_5_6"]["notes"]) + list(payoff_result["notes"])
    return sorted(adjusted, key=lambda item: (item["start"], item["pitch"])), payoff_result


def validate_motif_phrase_structure(phrase_notes, start_bar, root_pc, third_pc):
    pipeline = build_hook_phrase_pipeline(phrase_notes, start_bar)
    bars_1_2_a = rhythm_pattern_signature(pipeline["all_notes"], start_bar, bars=1, step=0.5)
    bars_1_2_b = rhythm_pattern_signature(pipeline["all_notes"], start_bar + 1, bars=1, step=0.5)
    bars_3_4_a = rhythm_pattern_signature(pipeline["all_notes"], start_bar + 2, bars=1, step=0.5)
    bars_3_4_b = rhythm_pattern_signature(pipeline["all_notes"], start_bar + 3, bars=1, step=0.5)
    payoff = pipeline["bars_7_8"]["notes"]
    answer = pipeline["bars_5_6"]["notes"]
    conditions = {
        "motif_repeat_ok": bars_1_2_a == bars_1_2_b,
        "variation_retains_rhythm": bars_3_4_a == bars_3_4_b or rhythm_pattern_match_ratio(bars_3_4_a, bars_3_4_b) >= 0.7,
        "answer_lifts": average_pitch(answer) > average_pitch(pipeline["bars_1_4"]["notes"]),
        "payoff_sparser": len(payoff) < len(answer),
        "payoff_has_long_note": any(length_beats(n) >= 1.0 for n in payoff),
        "payoff_resolves": payoff and (payoff[-1]["pitch"] % 12) in (root_pc, third_pc),
    }
    return all(conditions.values()), conditions


def strongest_payoff_note(payoff_notes):
    if not payoff_notes:
        return None
    return max(
        payoff_notes,
        key=lambda note_data: (
            length_beats(note_data),
            note_data["velocity"],
            note_data["pitch"],
        ),
    )


def get_payoff_notes(phrase_notes):
    if not phrase_notes:
        return []
    phrase_start_bar = min(note_data["start"] // BAR_TICKS for note_data in phrase_notes)
    return [
        note_data
        for note_data in phrase_notes
        if phrase_start_bar + 6 <= note_data["start"] // BAR_TICKS < phrase_start_bar + 8
    ]


def get_payoff_note(phrase_notes):
    return strongest_payoff_note(get_payoff_notes(phrase_notes))


def payoff_pre_gap_beats(phrase_notes, payoff_note):
    if not payoff_note:
        return 0.0
    previous_notes = [note_data for note_data in phrase_notes if note_data["end"] <= payoff_note["start"]]
    if not previous_notes:
        return 4.0
    previous_end = max(note_data["end"] for note_data in previous_notes)
    return round((payoff_note["start"] - previous_end) / TICKS, 2)


def payoff_rank_in_phrase(phrase_notes, payoff_note):
    if not payoff_note:
        return 0
    ranked_pitches = sorted({note_data["pitch"] for note_data in phrase_notes}, reverse=True)
    return ranked_pitches.index(payoff_note["pitch"]) + 1 if payoff_note["pitch"] in ranked_pitches else 0


def enforce_pre_payoff_gap(phrase_notes):
    payoff = get_payoff_note(phrase_notes)
    if not payoff:
        return phrase_notes, False
    filtered = []
    changed = False
    for note_data in phrase_notes:
        if note_data is payoff:
            filtered.append(note_data)
            continue
        if note_data["start"] < payoff["start"] and payoff["start"] - note_data["end"] < tick(0.5):
            changed = True
            continue
        filtered.append(note_data)
    return sorted(filtered, key=lambda item: (item["start"], item["pitch"])), changed


def enforce_payoff_dominance(phrase_notes):
    if not phrase_notes:
        return [], {"changed": False, "payoff_is_dominant": False, "payoff_rank_in_phrase": 0, "payoff_velocity": 0, "pre_payoff_gap": 0.0}
    adjusted = [dict(note_data) for note_data in phrase_notes]
    payoff_notes = get_payoff_notes(adjusted)
    if not payoff_notes:
        return adjusted, {"changed": False, "payoff_is_dominant": False, "payoff_rank_in_phrase": 0, "payoff_velocity": 0, "pre_payoff_gap": 0.0}

    dominant = strongest_payoff_note(payoff_notes)
    phrase_start_bar = min(note_data["start"] // BAR_TICKS for note_data in adjusted)
    dominant_bar = dominant["start"] // BAR_TICKS
    other_pitches = [note_data["pitch"] for note_data in adjusted if note_data is not dominant]
    highest = max(other_pitches, default=dominant["pitch"])
    changed = False
    if dominant["pitch"] <= highest:
        dominant["pitch"] = clamp(dominant["pitch"] + 2, 72, 86)
        if dominant["pitch"] <= highest:
            dominant["pitch"] = clamp(dominant["pitch"] + 3, 72, 86)
        if dominant["pitch"] <= highest:
            dominant["pitch"] = clamp(highest + 1, 72, 86)
        changed = True
    dominant["pitch"] = clamp(dominant["pitch"], 72, 86)

    other_lengths = [length_beats(note_data) for note_data in adjusted if note_data is not dominant]
    required_length = min(2.5, max(2.25, max(other_lengths, default=1.25) + 0.5))
    dominant_bar_end = bar_tick(dominant["start"] // BAR_TICKS + 1)
    original_end = dominant["end"]
    dominant["end"] = max(dominant["end"], min(dominant_bar_end, dominant["start"] + tick(required_length)))
    if dominant["end"] != original_end:
        changed = True

    for note_data in adjusted:
        if note_data is dominant:
            continue
        note_bar = note_data["start"] // BAR_TICKS
        if phrase_start_bar <= note_bar < phrase_start_bar + 4:
            original_velocity = note_data["velocity"]
            original_end = note_data["end"]
            note_data["velocity"] = clamp(note_data["velocity"] - 8, 0, 124)
            note_data["end"] = max(note_data["start"] + tick(0.65), note_data["end"] - tick(0.2))
            if note_data["velocity"] != original_velocity or note_data["end"] != original_end:
                changed = True
        elif phrase_start_bar + 4 <= note_bar < phrase_start_bar + 6:
            original_velocity = note_data["velocity"]
            note_data["velocity"] = clamp(note_data["velocity"] - 3, 0, 124)
            if note_data["velocity"] != original_velocity:
                changed = True

    average_velocity = sum(note_data["velocity"] for note_data in adjusted if note_data is not dominant) / max(1, len(adjusted) - 1)
    original_velocity = dominant["velocity"]
    dominant["velocity"] = clamp(int(average_velocity + 15), 0, 124)
    if dominant["velocity"] != original_velocity:
        changed = True

    gap_start = dominant["start"] - tick(0.5)
    filtered = []
    for note_data in adjusted:
        if note_data is dominant:
            filtered.append(note_data)
            continue
        if note_data["start"] // BAR_TICKS == dominant_bar and note_data["start"] >= dominant["start"]:
            changed = True
            continue
        before_payoff = note_data["start"] < dominant["start"]
        competing_register = note_data["pitch"] == dominant["pitch"] or abs(note_data["pitch"] - dominant["pitch"]) <= 2
        if before_payoff and competing_register:
            changed = True
            continue
        if note_data["end"] > gap_start and note_data["start"] < dominant["start"]:
            shortened = dict(note_data)
            shortened["end"] = min(shortened["end"], gap_start)
            if shortened["end"] - shortened["start"] >= tick(0.5):
                filtered.append(shortened)
            changed = True
            continue
        filtered.append(note_data)

    leap_pitch = clamp(dominant["pitch"] - (7 if dominant["pitch"] - 7 >= 72 else 5), 72, 84)
    leap_note = {
        "start": max(bar_tick(dominant_bar), dominant["start"] - tick(1.0)),
        "end": max(bar_tick(dominant_bar) + tick(0.5), dominant["start"] - tick(0.5)),
        "pitch": leap_pitch,
        "velocity": clamp(dominant["velocity"] - 14, 0, 124),
        "channel": 0,
    }
    if leap_note["end"] <= leap_note["start"]:
        leap_note["end"] = leap_note["start"] + tick(0.5)
    if not any(note_data["start"] == leap_note["start"] and note_data["pitch"] == leap_note["pitch"] for note_data in filtered):
        filtered.append(leap_note)
        changed = True

    filtered, gap_changed = enforce_pre_payoff_gap(sorted(filtered, key=lambda item: (item["start"], item["pitch"])))
    changed = changed or gap_changed
    final_payoff = strongest_payoff_note(get_payoff_notes(filtered))
    rank = payoff_rank_in_phrase(filtered, final_payoff)
    pre_gap = payoff_pre_gap_beats(filtered, final_payoff)
    is_dominant = bool(
        final_payoff
        and rank == 1
        and all(length_beats(final_payoff) > length_beats(note_data) for note_data in filtered if note_data is not final_payoff)
        and pre_gap >= 0.5
    )
    return filtered, {
        "changed": changed or final_payoff != dominant,
        "payoff_is_dominant": is_dominant,
        "payoff_rank_in_phrase": rank,
        "payoff_velocity": final_payoff["velocity"] if final_payoff else 0,
        "pre_payoff_gap": pre_gap,
    }


def hook_dominance_report(lead_notes, start_bar, chords):
    bar_counts = [len(notes_starting_in_bar(lead_notes, start_bar + offset)) for offset in range(8)]
    all_phrase_notes = [note_data for offset in range(8) for note_data in notes_starting_in_bar(lead_notes, start_bar + offset)]
    payoff_notes = [note_data for offset in (6, 7) for note_data in notes_starting_in_bar(lead_notes, start_bar + offset)]
    long_notes = [note_data for note_data in all_phrase_notes if length_beats(note_data) >= 1.5]
    payoff_note = strongest_payoff_note(payoff_notes)
    payoff_pitch = payoff_note["pitch"] if payoff_note else 0
    payoff_length = round(length_beats(payoff_note), 2) if payoff_note else 0
    phrase_pitches = sorted((note_data["pitch"] for note_data in all_phrase_notes), reverse=True)
    second_highest = phrase_pitches[1] if len(phrase_pitches) > 1 else (phrase_pitches[0] if phrase_pitches else 0)
    phrase_highest = phrase_pitches[0] if phrase_pitches else 0
    payoff_is_highest_or_second = bool(payoff_note and payoff_note["pitch"] >= second_highest)
    payoff_is_highest = bool(payoff_note and payoff_note["pitch"] >= phrase_highest)
    final_payoff = sorted(payoff_notes, key=lambda item: (item["start"], item["pitch"]))[-1] if payoff_notes else None
    final_bar = final_payoff["start"] // BAR_TICKS if final_payoff else start_bar + 7
    payoff_bar = payoff_note["start"] // BAR_TICKS if payoff_note else start_bar + 7
    final_chord = chords[final_bar % len(chords)]
    payoff_chord = chords[payoff_bar % len(chords)]
    payoff_resolves = bool(
        payoff_note
        and final_payoff
        and (payoff_note["pitch"] % 12) in (payoff_chord["root"] % 12, payoff_chord["third"] % 12)
        and (final_payoff["pitch"] % 12) in (final_chord["root"] % 12, final_chord["third"] % 12)
    )
    motif_signature = rhythm_pattern_signature(lead_notes, start_bar, bars=1, step=0.5)
    bar_2_signature = rhythm_pattern_signature(lead_notes, start_bar + 1, bars=1, step=0.5)
    bar_3_signature = rhythm_pattern_signature(lead_notes, start_bar + 2, bars=1, step=0.5)
    bar_4_signature = rhythm_pattern_signature(lead_notes, start_bar + 3, bars=1, step=0.5)
    motif_pitch_changes = motif_pitch_change_count(lead_notes, start_bar)
    first_half_spread = phrase_pitch_span(lead_notes, start_bar, 4)
    phrase_spread = phrase_pitch_span(lead_notes, start_bar, 8)
    motif_repeat_passed = (
        motif_signature == bar_2_signature
        and motif_signature == bar_3_signature
        and motif_signature == bar_4_signature
        and motif_pitch_changes <= 1
        and all(count <= 2 for count in bar_counts[:4])
    )
    variation_identity_passed = (
        rhythm_pattern_match_ratio(motif_signature, bar_3_signature) >= 0.9
        and rhythm_pattern_match_ratio(motif_signature, bar_4_signature) >= 0.9
        and motif_pitch_changes <= 1
        and bar_counts[2] <= 2
        and bar_counts[3] <= 2
    )
    bars_1_2_notes = [note_data for offset in (0, 1) for note_data in notes_starting_in_bar(lead_notes, start_bar + offset)]
    bars_5_6_notes = [note_data for offset in (4, 5) for note_data in notes_starting_in_bar(lead_notes, start_bar + offset)]
    lift_passed = average_pitch(bars_5_6_notes) > average_pitch(bars_1_2_notes)
    payoff_has_long = any(length_beats(note_data) >= 1.5 for note_data in payoff_notes)
    payoff_dominates = payoff_has_long and payoff_is_highest_or_second and payoff_resolves
    payoff_rank = payoff_rank_in_phrase(all_phrase_notes, payoff_note)
    pre_payoff_gap = payoff_pre_gap_beats(all_phrase_notes, payoff_note)
    payoff_velocity = payoff_note["velocity"] if payoff_note else 0
    interval_report = lead_interval_jump_report(lead_notes, start_bar)
    duration_report = lead_duration_report(all_phrase_notes)
    payoff_is_dominant = payoff_dominates and payoff_is_highest and payoff_rank == 1 and pre_payoff_gap >= 0.5 and all(
        length_beats(payoff_note) > length_beats(note_data)
        for note_data in all_phrase_notes
        if payoff_note and note_data is not payoff_note
    )
    hook_dominance_score = 0
    hook_dominance_score += 2 if max(bar_counts, default=0) <= 2 else 0
    hook_dominance_score += 2 if motif_repeat_passed else 0
    hook_dominance_score += 2 if variation_identity_passed else 0
    hook_dominance_score += 2 if lift_passed else 0
    hook_dominance_score += 3 if payoff_is_dominant else 0
    return {
        "lead_avg_notes_per_bar": round(sum(bar_counts) / max(1, len(bar_counts)), 2),
        "lead_max_notes_per_bar": max(bar_counts, default=0),
        "lead_long_note_count": len(long_notes),
        "lead_long_note_ratio": duration_report["lead_long_note_ratio"],
        "lead_short_note_removed_count": 0,
        "lead_merged_note_count": 0,
        "lead_avg_note_length": duration_report["lead_avg_note_length"],
        "lead_sustained_note_count": duration_report["lead_sustained_note_count"],
        "lead_sustain_passed": duration_report["lead_long_note_ratio"] >= 0.6 and duration_report["lead_sustained_note_count"] >= 2 and all(length_beats(note_data) >= 0.75 for note_data in all_phrase_notes),
        "lead_payoff_note_length": payoff_length,
        "lead_payoff_note_pitch": payoff_pitch,
        "lead_payoff_is_highest_or_second_highest": payoff_is_highest_or_second,
        "lead_payoff_resolves_to_root_or_third": payoff_resolves,
        "lead_motif_repeat_passed": motif_repeat_passed,
        "lead_motif_rhythm_signature": ",".join(str(item) for item in motif_signature),
        "lead_variation_identity_passed": variation_identity_passed,
        "lead_hook_dominance_score": hook_dominance_score,
        "lead_motif_pitch_changes": motif_pitch_changes,
        "lead_first_half_pitch_spread": first_half_spread,
        "lead_phrase_pitch_spread": phrase_spread,
        "lead_expressive_jump_count": interval_report["lead_expressive_jump_count"],
        "lead_largest_upward_jump": interval_report["lead_largest_upward_jump"],
        "lead_pre_payoff_jump": interval_report["lead_pre_payoff_jump"],
        "lead_controlled_jump_passed": interval_report["lead_controlled_jump_passed"],
        "payoff_is_dominant": payoff_is_dominant,
        "payoff_rank_in_phrase": payoff_rank,
        "payoff_velocity": payoff_velocity,
        "pre_payoff_gap": pre_payoff_gap,
        "payoff_has_long_note_15": payoff_has_long,
        "lift_phrase_lifts": lift_passed,
        "valid": max(bar_counts, default=0) <= 2 and motif_repeat_passed and variation_identity_passed and lift_passed and payoff_is_dominant and interval_report["lead_controlled_jump_passed"] and duration_report["lead_long_note_ratio"] >= 0.6 and duration_report["lead_sustained_note_count"] >= 2 and all(length_beats(note_data) >= 0.75 for note_data in all_phrase_notes) and phrase_spread <= 10,
    }


def repair_hook_dominant_lead_phrase(lead_notes, start_bar, chords):
    repaired = [dict(note_data) for note_data in lead_notes]
    repairs = 0
    for offset in range(8):
        bar_index = start_bar + offset
        chord = chords[bar_index % len(chords)]
        bar_notes = notes_starting_in_bar(repaired, bar_index)
        fixed = []
        for note_data in bar_notes:
            cloned = dict(note_data)
            cloned["pitch"] = safe_lead_tone_for_chord(cloned["pitch"], chord, low=72, high=86)
            cloned["end"] = max(cloned["end"], min(bar_tick(bar_index + 1), cloned["start"] + tick(0.75)))
            fixed.append(cloned)
        if offset >= 6:
            harmonic_state = build_harmonic_state(bar_index, "uplifting", chord)
            payoff = build_long_payoff_note(
                chord,
                harmonic_state,
                start_beat=1.0 if offset == 6 else 0.5,
                length=2.25 if offset == 6 else 2.5,
                register_range=(81, 86) if offset == 6 else (80, 86),
                prefer_third=offset == 7,
            )
            bar_start = bar_tick(bar_index)
            fixed = []
            if offset == 6:
                leap = build_pre_payoff_leap_note(payoff[0][2], start_beat=0.0, length=0.75)
                fixed.append({
                    "start": bar_start + tick(leap[0]),
                    "end": bar_start + tick(leap[0] + leap[1]),
                    "pitch": leap[2],
                    "velocity": 96,
                    "channel": 0,
                })
            fixed.append({
                "start": bar_start + tick(payoff[0][0]),
                "end": bar_start + tick(min(4.0, payoff[0][0] + payoff[0][1])),
                "pitch": payoff[0][2],
                "velocity": 110,
                "channel": 0,
            })
        fixed = simplify_lead_bar_for_hook(fixed)
        if fixed != bar_notes:
            repairs += 1
        repaired = replace_notes_in_bar_range(repaired, bar_index, bar_index + 1, fixed)
    repaired, identity_changed = enforce_single_hook_identity(sorted(repaired, key=lambda item: (item["start"], item["pitch"])), start_bar)
    if identity_changed:
        repairs += 1
    repaired, dominance_result = enforce_payoff_dominance(repaired)
    if dominance_result.get("changed"):
        repairs += 1
    repaired, spread_changed = enforce_hook_pitch_spread(repaired, max_spread=10)
    if spread_changed:
        repairs += 1
    repaired, identity_changed = enforce_single_hook_identity(repaired, start_bar)
    if identity_changed:
        repairs += 1
    repaired, sustain_changed, sustain_report = enforce_lead_sustain_dominance(repaired, start_bar)
    if sustain_changed:
        repairs += 1
    repairs += sustain_report.get("lead_short_note_removed_count", 0)
    repairs += sustain_report.get("lead_merged_note_count", 0)
    repaired, dominance_result = enforce_payoff_dominance(repaired)
    if dominance_result.get("changed"):
        repairs += 1
    return repaired, repairs


def validate_hook_dominant_lead(lead_notes, start_bar, chords):
    return hook_dominance_report(lead_notes, start_bar, chords)


def simplify_phrase_density(lead_notes, start_bar: int, max_bar_density: int = 5):
    simplified = []
    for offset in range(8):
        bar_index = start_bar + offset
        bar_notes = sorted(notes_starting_in_bar(lead_notes, bar_index), key=lambda item: ((item["end"] - item["start"]), item["velocity"]), reverse=True)
        keep = sorted(bar_notes[:max_bar_density], key=lambda item: (item["start"], item["pitch"]))
        simplified.extend(keep)
    return sorted(simplified, key=lambda item: (item["start"], item["pitch"]))


def build_hook_candidate_set(start_bar: int, chords, identity, section_name: str, candidate_count: int = 4):
    candidates = []
    signatures = []
    capped_count = max(3, min(candidate_count, len(HOOK_CANDIDATE_POOL)))
    for candidate_index, (archetype, variant_index) in enumerate(HOOK_CANDIDATE_POOL[:capped_count]):
        notes, drama_profile = generate_hook_phrase_candidate(start_bar, chords, identity, section_name, archetype, variant_index=variant_index)
        signature = candidate_diversity_signature(notes, start_bar, drama_profile)
        if any(too_similar(signature, existing) for existing in signatures):
            continue
        signatures.append(signature)
        candidates.append({
            "candidate_index": candidate_index,
            "archetype": archetype,
            "variant_index": variant_index,
            "drama_profile": drama_profile,
            "notes": notes,
            "signature": signature,
        })
    return candidates


def lead_validation_scores(lead_notes, start_bar: int, root_pc: int, third_pc: int, supersaw_notes=None, chords=None):
    all_densities = [bar_note_density(lead_notes, start_bar + offset) for offset in range(8)]
    all_lengths = []
    breath_gaps = 0
    sustained_pairs = 0
    for pair_start in range(0, 8, 2):
        pair_notes = [note_data for offset in range(pair_start, pair_start + 2) for note_data in notes_starting_in_bar(lead_notes, start_bar + offset)]
        if pair_notes and max((note_data["end"] - note_data["start"]) / TICKS for note_data in pair_notes) > 1.0:
            sustained_pairs += 1
    for offset in range(8):
        bar_notes = notes_starting_in_bar(lead_notes, start_bar + offset)
        all_lengths.extend((note_data["end"] - note_data["start"]) / TICKS for note_data in bar_notes)
        bar_positions = sorted(quantized_bar_positions(lead_notes, start_bar + offset, 0.5))
        if bar_positions:
            gaps = [round(bar_positions[idx + 1] - bar_positions[idx], 2) for idx in range(len(bar_positions) - 1)]
            end_gap = round(4.0 - bar_positions[-1], 2)
            if any(gap >= 0.5 for gap in gaps) or end_gap >= 0.5:
                breath_gaps += 1
    phrase_pipeline = build_hook_phrase_pipeline(lead_notes, start_bar)
    hook_report = validate_hook_dominant_lead(lead_notes, start_bar, chords) if chords else {}
    structure_valid, structure_conditions = validate_motif_phrase_structure(lead_notes, start_bar, root_pc, third_pc)
    motif_validation = validate_motif(phrase_pipeline["bars_1_4"])
    motif_score = motif_validation["motif_score"]
    rhythmic_identity_score = motif_validation["rhythmic_identity_score"]
    pattern_match = motif_validation["pattern_match"]
    phrase_density = phrase_note_density(lead_notes, start_bar, 8)
    rhythm_contrast_ok = enforce_rhythm_contrast(lead_notes)
    peak_moment_ok = enforce_peak_moment(lead_notes)
    motif_interval_identity = score_motif_interval_identity(lead_notes, start_bar)
    motif_interval_identity_score = motif_interval_identity["score"]
    motif_interval_identity_ok = motif_interval_identity["passed"]
    first_four = [tuple(quantized_bar_positions(lead_notes, start_bar + offset, 0.5)) for offset in range(4)]
    phrase_a_notes = [note_data for offset in range(4) for note_data in notes_starting_in_bar(lead_notes, start_bar + offset)]
    phrase_b_notes = [note_data for offset in range(4, 6) for note_data in notes_starting_in_bar(lead_notes, start_bar + offset)]
    payoff_pitch_notes = [note_data for offset in (6, 7) for note_data in notes_starting_in_bar(lead_notes, start_bar + offset)]
    a_avg = sum(note_data["pitch"] for note_data in phrase_a_notes) / len(phrase_a_notes) if phrase_a_notes else 0
    b_avg = sum(note_data["pitch"] for note_data in phrase_b_notes) / len(phrase_b_notes) if phrase_b_notes else 0
    payoff_avg = sum(note_data["pitch"] for note_data in payoff_pitch_notes) / len(payoff_pitch_notes) if payoff_pitch_notes else 0
    register_arc_score = 4 if b_avg >= a_avg + 2 and payoff_avg >= b_avg + 1 else 2 if b_avg > a_avg or payoff_avg > b_avg else 0
    payoff_notes = payoff_pitch_notes
    sustained = any((note_data["end"] - note_data["start"]) / TICKS >= 1.0 for note_data in payoff_notes)
    final_pitch = payoff_notes[-1]["pitch"] % 12 if payoff_notes else None
    resolves = final_pitch in (root_pc, third_pc)
    phrase_b_density = len(phrase_b_notes)
    payoff_density = len(payoff_notes)
    highest_in_phrase = max((note_data["pitch"] for note_data in phrase_a_notes + phrase_b_notes + payoff_notes), default=0)
    peak_in_payoff = max((note_data["pitch"] for note_data in payoff_notes), default=0) >= highest_in_phrase
    payoff_score = (2 if sustained else 0) + (1 if resolves else 0) + (1 if peak_in_payoff else 0)
    if payoff_density >= max(1, phrase_b_density):
        payoff_score = max(0, payoff_score - 1)
    singability_score = 4
    rounded_lengths = [round(length, 2) for length in all_lengths]
    length_counts = {}
    for length in rounded_lengths:
        length_counts[length] = length_counts.get(length, 0) + 1
    dominant_length_ratio = max(length_counts.values(), default=0) / max(1, len(rounded_lengths))
    too_even = len(length_counts) <= 2 or dominant_length_ratio >= 0.7
    if len({fingerprint for fingerprint in first_four if fingerprint}) <= 1:
        singability_score -= 2
    if sum(1 for value in all_densities if value > 6) > 2:
        singability_score -= 2
    if any(value > 10 for value in all_densities):
        singability_score = max(0, singability_score - 2)
    if breath_gaps < 8:
        singability_score = max(0, singability_score - 2)
    if sustained_pairs < 2:
        payoff_score = max(0, payoff_score - 1)
    if all(length <= 0.3 for length in all_lengths):
        motif_score = max(0, motif_score - 2)
    if too_even:
        singability_score = max(0, singability_score - 2)
    motif_repeat_score = 4 if structure_conditions["motif_repeat_ok"] else 0
    motif_variation_score = 4 if structure_conditions["variation_retains_rhythm"] else 0
    answer_phrase_lift = round(max(0.0, average_pitch(phrase_b_notes) - average_pitch(phrase_a_notes)), 2)
    payoff_strength = payoff_score + (2 if structure_conditions["payoff_has_long_note"] else 0) + (1 if structure_conditions["payoff_resolves"] else 0)
    rejection_reasons = motif_validation["rejection_reasons"][:]
    supersaw_contrast_score = 0
    supersaw_cohesion_score = 0
    supersaw_payoff_crown_ok = False
    supersaw_accent_alignment_ok = False
    supersaw_shared_harmonic_ok = False
    drop_safe_tone_ratio = 1.0
    unsafe_peak_note_count = 0
    supersaw_max_pitch = 0
    if supersaw_notes is not None:
        contrast = score_supersaw_contrast(lead_notes, supersaw_notes, start_bar)
        supersaw_contrast_score = contrast["score"]
        rejection_reasons.extend(contrast["rejection_reasons"])
        cohesion = score_lead_supersaw_cohesion(lead_notes, supersaw_notes, start_bar)
        supersaw_cohesion_score = cohesion["score"]
        supersaw_payoff_crown_ok = cohesion["payoff_crown_ok"]
        supersaw_accent_alignment_ok = cohesion["accent_alignment_ok"]
        supersaw_shared_harmonic_ok = cohesion["shared_harmonic_ok"]
        rejection_reasons.extend(cohesion["rejection_reasons"])
        safe_ratios = []
        for offset in range(8):
            bar_index = start_bar + offset
            bar_notes = notes_starting_in_bar(lead_notes, bar_index)
            supersaw_bar = notes_starting_in_bar(supersaw_notes, bar_index)
            if not bar_notes:
                continue
            allowed = {root_pc, third_pc}
            allowed.update(note_data["pitch"] % 12 for note_data in supersaw_bar)
            safe_count = sum(1 for note_data in bar_notes if lead_note_is_drop_safe(note_data["pitch"], allowed))
            safe_ratio = safe_count / max(1, len(bar_notes))
            safe_ratios.append(safe_ratio)
            if len(bar_notes) > 2:
                rejection_reasons.append("lead_too_busy_for_drop")
            if any(length_beats(note_data) < 0.75 for note_data in bar_notes):
                rejection_reasons.append("lead_note_too_short_for_drop")
            peak_pitch = max(note_data["pitch"] for note_data in bar_notes)
            if (peak_pitch % 12) not in allowed:
                unsafe_peak_note_count += 1
                rejection_reasons.append("unsafe_peak_note")
        drop_safe_tone_ratio = sum(safe_ratios) / max(1, len(safe_ratios))
        supersaw_max_pitch = max((note_data["pitch"] for note_data in supersaw_notes), default=0)
        if drop_safe_tone_ratio < 0.8:
            rejection_reasons.append("lead_harmony_drift")
        if supersaw_max_pitch > 84:
            rejection_reasons.append("supersaw_too_high")
    if not rhythm_contrast_ok:
        rejection_reasons.append("uniform_note_lengths")
    if not peak_moment_ok:
        rejection_reasons.append("no_sustained_high_peak")
    rejection_reasons.extend(motif_interval_identity["rejection_reasons"])
    if too_even:
        rejection_reasons.append("too_even")
    if phrase_density > 4:
        rejection_reasons.append("too_dense")
    if not sustained:
        rejection_reasons.append("no_sustained_payoff_note")
    if not resolves:
        rejection_reasons.append("no_clear_resolution")
    if payoff_density >= max(1, phrase_b_density):
        rejection_reasons.append("payoff_not_sparser_than_bars_5_6")
    if not peak_in_payoff:
        rejection_reasons.append("no_emotional_peak_in_payoff")
    if not structure_conditions["motif_repeat_ok"]:
        rejection_reasons.append("bars_1_2_not_identical")
    if not structure_conditions["variation_retains_rhythm"]:
        rejection_reasons.append("bars_3_4_not_pitch_only_variation")
    if not structure_conditions["answer_lifts"]:
        rejection_reasons.append("bars_5_6_do_not_lift")
    if not structure_conditions["payoff_sparser"]:
        rejection_reasons.append("bars_7_8_not_sparse_enough")
    if not structure_conditions["payoff_has_long_note"]:
        rejection_reasons.append("payoff_lacks_long_note")
    if not structure_conditions["payoff_resolves"]:
        rejection_reasons.append("payoff_does_not_resolve")
    if hook_report and not hook_report["valid"]:
        rejection_reasons.append("hook_dominance_validation_failed")
    if breath_gaps < 6:
        rejection_reasons.append("insufficient_breath_gaps")
    anthem_scores = score_anthem_payoff(lead_notes, start_bar, root_pc, third_pc)
    surprise_moment_detected = has_surprise_moment(lead_notes, start_bar)
    crowd_response_score = score_crowd_response({
        "motif_score": motif_score,
        "rhythmic_identity_score": rhythmic_identity_score,
        "anthem_payoff_score": anthem_scores["anthem_payoff_score"],
        "singability_score": max(0, singability_score),
        "supersaw_contrast_score": supersaw_contrast_score,
    })
    if not surprise_moment_detected:
        rejection_reasons.append("no_surprise_moment")
    total_score = (
        motif_score
        + motif_repeat_score
        + motif_variation_score
        + rhythmic_identity_score
        + register_arc_score
        + payoff_score
        + max(0, singability_score)
        + supersaw_contrast_score
        + supersaw_cohesion_score
        + motif_interval_identity_score
        + anthem_scores["anthem_payoff_score"] * 2
        + crowd_response_score * 2
        - (rhythmic_identity_score if too_even else 0)
        - (2 if not rhythm_contrast_ok else 0)
        - (3 if not peak_moment_ok else 0)
        - (2 if phrase_density > 4 else 0)
    )
    return {
        "motif_score": motif_score,
        "motif_repeat_score": motif_repeat_score,
        "motif_variation_score": motif_variation_score,
        "rhythmic_identity_score": rhythmic_identity_score,
        "register_arc_score": register_arc_score,
        "payoff_score": payoff_score,
        "answer_phrase_lift": answer_phrase_lift,
        "payoff_strength": payoff_strength,
        "lead_avg_notes_per_bar": hook_report.get("lead_avg_notes_per_bar", 0),
        "lead_max_notes_per_bar": hook_report.get("lead_max_notes_per_bar", 0),
        "lead_long_note_count": hook_report.get("lead_long_note_count", 0),
        "lead_long_note_ratio": hook_report.get("lead_long_note_ratio", 0),
        "lead_short_note_removed_count": hook_report.get("lead_short_note_removed_count", 0),
        "lead_merged_note_count": hook_report.get("lead_merged_note_count", 0),
        "lead_avg_note_length": hook_report.get("lead_avg_note_length", 0),
        "lead_sustained_note_count": hook_report.get("lead_sustained_note_count", 0),
        "lead_sustain_passed": hook_report.get("lead_sustain_passed", False),
        "lead_payoff_note_length": hook_report.get("lead_payoff_note_length", 0),
        "lead_payoff_note_pitch": hook_report.get("lead_payoff_note_pitch", 0),
        "lead_payoff_is_highest_or_second_highest": hook_report.get("lead_payoff_is_highest_or_second_highest", False),
        "lead_payoff_resolves_to_root_or_third": hook_report.get("lead_payoff_resolves_to_root_or_third", False),
        "lead_motif_repeat_passed": hook_report.get("lead_motif_repeat_passed", False),
        "lead_motif_rhythm_signature": hook_report.get("lead_motif_rhythm_signature", ""),
        "lead_variation_identity_passed": hook_report.get("lead_variation_identity_passed", False),
        "lead_hook_dominance_score": hook_report.get("lead_hook_dominance_score", 0),
        "lead_motif_pitch_changes": hook_report.get("lead_motif_pitch_changes", 0),
        "lead_first_half_pitch_spread": hook_report.get("lead_first_half_pitch_spread", 0),
        "lead_phrase_pitch_spread": hook_report.get("lead_phrase_pitch_spread", 0),
        "lead_expressive_jump_count": hook_report.get("lead_expressive_jump_count", 0),
        "lead_largest_upward_jump": hook_report.get("lead_largest_upward_jump", 0),
        "lead_pre_payoff_jump": hook_report.get("lead_pre_payoff_jump", 0),
        "lead_controlled_jump_passed": hook_report.get("lead_controlled_jump_passed", False),
        "payoff_is_dominant": hook_report.get("payoff_is_dominant", False),
        "payoff_rank_in_phrase": hook_report.get("payoff_rank_in_phrase", 0),
        "payoff_velocity": hook_report.get("payoff_velocity", 0),
        "pre_payoff_gap": hook_report.get("pre_payoff_gap", 0.0),
        "singability_score": max(0, singability_score),
        "supersaw_contrast_score": supersaw_contrast_score,
        "supersaw_cohesion_score": supersaw_cohesion_score,
        "motif_interval_identity_score": motif_interval_identity_score,
        "anthem_payoff_score": anthem_scores["anthem_payoff_score"],
        "release_score": anthem_scores["release_score"],
        "dominance_score": anthem_scores["dominance_score"],
        "crowd_response_score": crowd_response_score,
        "rhythm_contrast_ok": rhythm_contrast_ok,
        "peak_moment_ok": peak_moment_ok,
        "supersaw_payoff_crown_ok": supersaw_payoff_crown_ok,
        "supersaw_accent_alignment_ok": supersaw_accent_alignment_ok,
        "supersaw_shared_harmonic_ok": supersaw_shared_harmonic_ok,
        "lead_safe_tone_ratio": round(drop_safe_tone_ratio, 3),
        "unsafe_peak_note_count": unsafe_peak_note_count,
        "supersaw_max_pitch": supersaw_max_pitch,
        "motif_interval_identity_ok": motif_interval_identity_ok,
        "too_even": too_even,
        "surprise_moment_detected": surprise_moment_detected,
        "motif_structure_valid": structure_valid,
        "motif_structure_conditions": structure_conditions,
        "total": total_score,
        "rejection_reasons": sorted(set(rejection_reasons)),
        "valid": bool(hook_report and hook_report["valid"]) or (
            total_score >= 20
            and payoff_score >= 3
            and anthem_scores["anthem_payoff_score"] >= 6
            and motif_score >= 2
            and motif_repeat_score >= 4
            and motif_variation_score >= 4
            and rhythmic_identity_score >= 2
            and register_arc_score >= 2
            and all(value <= 6 for value in all_densities)
            and phrase_density <= 2
            and structure_valid
            and (not hook_report or hook_report["valid"])
            and (supersaw_notes is None or supersaw_shared_harmonic_ok)
        ),
    }


def select_best_hook_candidate(start_bar: int, chords, identity, section_name: str, supersaw_notes=None, candidate_count: int = 4, recent_winners=None):
    chord = chords[start_bar % len(chords)]
    candidate_notes = build_drop_lead_phrase_from_motif(start_bar, chords, supersaw_notes or [], identity, section_name)
    motif_supersaw_lock_applied = False
    candidate_notes, drop_repair_metrics = enforce_drop_lead_harmony_rules(candidate_notes, start_bar, chords, supersaw_notes)
    candidate_notes, payoff_result = apply_payoff_rules_to_phrase(candidate_notes, start_bar, chord["root"] % 12, chord["third"] % 12)
    candidate_notes, dominance_result = enforce_payoff_dominance(candidate_notes)
    hook_report = validate_hook_dominant_lead(candidate_notes, start_bar, chords)
    hook_repairs = 1 if dominance_result.get("changed") else 0
    if not hook_report["valid"]:
        candidate_notes, repair_count = repair_hook_dominant_lead_phrase(candidate_notes, start_bar, chords)
        hook_repairs += repair_count
        payoff_result = {"rejection_reasons": []}
    score = lead_validation_scores(candidate_notes, start_bar, chord["root"] % 12, chord["third"] % 12, supersaw_notes, chords=chords)
    score["rejection_reasons"] = sorted(set(score.get("rejection_reasons", []) + payoff_result.get("rejection_reasons", [])))
    score["diversity_bonus"] = 0.0
    score["archetype_penalty"] = 0.0
    score["repetition_penalty"] = 0.0
    score["selection_total"] = round(score["total"], 2)
    score["motif_supersaw_lock_applied"] = motif_supersaw_lock_applied
    score.update(drop_repair_metrics)
    score["lead_repairs_applied"] = hook_repairs + score.get("lead_drop_density_repairs", 0)
    scored_candidate = {
        "index": 0,
        "archetype": "motif_engine",
        "variant_index": 0,
        "drama_profile": "motif_driven",
        "notes": candidate_notes,
        "score": score,
    }
    if score["valid"]:
        return scored_candidate, [scored_candidate]
    fallback_notes, fallback_drama = generate_hook_phrase_candidate(
        start_bar,
        chords,
        identity,
        section_name,
        "declarative",
        variant_index=0,
    )
    fallback_notes, fallback_drop_metrics = enforce_drop_lead_harmony_rules(fallback_notes, start_bar, chords, supersaw_notes)
    fallback_notes, fallback_payoff = apply_payoff_rules_to_phrase(fallback_notes, start_bar, chord["root"] % 12, chord["third"] % 12)
    fallback_notes, fallback_dominance = enforce_payoff_dominance(fallback_notes)
    fallback_hook_repairs = 1 if fallback_dominance.get("changed") else 0
    if not validate_hook_dominant_lead(fallback_notes, start_bar, chords)["valid"]:
        fallback_notes, fallback_repair_count = repair_hook_dominant_lead_phrase(fallback_notes, start_bar, chords)
        fallback_hook_repairs += fallback_repair_count
        fallback_payoff = {"rejection_reasons": []}
    fallback_score = lead_validation_scores(fallback_notes, start_bar, chord["root"] % 12, chord["third"] % 12, supersaw_notes, chords=chords)
    fallback_score["rejection_reasons"] = sorted(set(fallback_score.get("rejection_reasons", []) + fallback_payoff.get("rejection_reasons", [])))
    fallback_score["selection_total"] = round(fallback_score["total"], 2)
    fallback_score["motif_supersaw_lock_applied"] = False
    fallback_score.update(fallback_drop_metrics)
    fallback_score["lead_repairs_applied"] = fallback_hook_repairs + fallback_score.get("lead_drop_density_repairs", 0)
    fallback_candidate = {
        "index": 1,
        "archetype": "fallback_declarative",
        "variant_index": 0,
        "drama_profile": fallback_drama,
        "notes": fallback_notes,
        "score": fallback_score,
    }
    winner = scored_candidate if scored_candidate["score"].get("lead_hook_dominance_score", 0) >= fallback_candidate["score"].get("lead_hook_dominance_score", 0) else fallback_candidate
    return winner, [scored_candidate, fallback_candidate]


def forecast_drop_supersaw_window(phrase_start_bar: int, phrase_start_local_bar: int, section_bars: int, kind: str, intensity: float, blueprint, identity, is_second_pass: bool, chords):
    temp_tracks = {stem: [] for stem in STEMS}
    for offset in range(8):
        local_bar = phrase_start_local_bar + offset
        if local_bar >= section_bars:
            break
        global_bar = phrase_start_bar + offset
        chord = chords[global_bar % len(chords)]
        start_tick = bar_tick(global_bar)
        add_harmony(temp_tracks, start_tick, chord, kind, local_bar, section_bars, intensity, blueprint, identity, is_second_pass)
    return events_to_notes(temp_tracks["supersaw_chords"])


def rebuilt_lead_window(start_bar: int, chords, identity, blueprint, section_name: str):
    fallback, _ = generate_hook_phrase_candidate(start_bar, chords, identity, section_name, blueprint.get("lead_archetype", "declarative"))
    fallback, _ = apply_payoff_rules_to_phrase(fallback, start_bar, chords[start_bar % len(chords)]["root"] % 12, chords[start_bar % len(chords)]["third"] % 12)
    return simplify_phrase_density(fallback, start_bar, max_bar_density=5)


def countermelody_scores(counter_notes, lead_notes, start_bar: int):
    counter_window = [note_data for offset in range(8) for note_data in notes_starting_in_bar(counter_notes, start_bar + offset)]
    lead_window = [note_data for offset in range(8) for note_data in notes_starting_in_bar(lead_notes, start_bar + offset)]
    if not counter_window:
        return {"independence_score": 0, "emotional_support_score": 0, "timing_score": 0, "answer_strength": 0, "total": 0, "valid": False}
    counter_avg = sum((note_data["end"] - note_data["start"]) / TICKS for note_data in counter_window) / len(counter_window)
    lead_avg = sum((note_data["end"] - note_data["start"]) / TICKS for note_data in lead_window) / max(1, len(lead_window))
    early_entries = 0
    for note_data in counter_window:
        bar_index = note_data["start"] // BAR_TICKS
        beat = round((note_data["start"] - bar_tick(bar_index)) / TICKS, 2)
        if beat < 1.0:
            early_entries += 1
    delayed_entries = 0
    harmonic_hits = 0
    lead_pitch_classes = {note_data["pitch"] % 12 for note_data in lead_window}
    for note_data in counter_window:
        if any(note_data["start"] > lead_note["start"] and note_data["start"] <= lead_note["start"] + tick(1.0) for lead_note in lead_window):
            delayed_entries += 1
        if (note_data["pitch"] % 12) in lead_pitch_classes:
            harmonic_hits += 1
    independence_score = 4 if counter_avg > lead_avg and len(counter_window) >= 6 else 2 if counter_avg >= lead_avg else 1
    emotional_support_score = 4 if len(counter_window) >= 6 and max((note_data["end"] - note_data["start"]) / TICKS for note_data in counter_window) >= 0.75 else 2 if len(counter_window) >= 4 else 0
    timing_score = 4 if early_entries <= max(1, len(counter_window) // 4) else 1
    answer_strength = 4 if delayed_entries >= max(2, len(counter_window) // 2) and harmonic_hits >= max(2, len(counter_window) // 2) else 2 if delayed_entries >= 1 else 0
    total = independence_score + emotional_support_score + timing_score + answer_strength
    return {"independence_score": independence_score, "emotional_support_score": emotional_support_score, "timing_score": timing_score, "answer_strength": answer_strength, "total": total, "valid": total >= 10}


def build_counter_from_lead_answer(lead_phrase_notes, chord, register_shift=5):
    counter = []
    ordered = sorted(lead_phrase_notes, key=lambda item: (item["start"], item["pitch"]))
    for idx, note_data in enumerate(ordered):
        if idx % 2 == 0:
            counter.append({
                "start": note_data["start"] + tick(0.5),
                "end": note_data["start"] + tick(1.25),
                "pitch": clamp(note_data["pitch"] + register_shift, 60, 98),
                "velocity": min(110, note_data["velocity"] + 6),
                "channel": 0,
            })
    return counter


def rebuilt_counter_window(start_bar: int, lead_notes, identity, chords, section_name: str = ""):
    pipeline = build_hook_phrase_pipeline(lead_notes, start_bar)
    source_notes = pipeline["bars_5_6"]["notes"] + pipeline["bars_7_8"]["notes"]
    rebuilt = []
    if "Drop 2" in section_name:
        rebuilt = build_counter_from_lead_answer(source_notes, chords[(start_bar + 4) % len(chords)], register_shift=5)
        for note_data in rebuilt:
            bar_index = note_data["start"] // BAR_TICKS
            chord = chords[bar_index % len(chords)]
            note_data["pitch"] = clamp(note_data["pitch"], chord["third"], clamp(identity["counter"] + 17, 60, 98))
            note_data["end"] = max(note_data["end"], note_data["start"] + tick(1.0))
    else:
        for note_data in build_counter_from_lead_answer(pipeline["bars_5_6"]["notes"], chords[(start_bar + 4) % len(chords)], register_shift=2):
            note_data["pitch"] = clamp(note_data["pitch"] - 7, 52, 88)
            note_data["velocity"] = clamp(note_data["velocity"] - 10, 0, 104)
            rebuilt.append(note_data)
    return sorted(rebuilt, key=lambda item: (item["start"], item["pitch"]))


def section_note_slice(notes, start_bar: int, end_bar: int):
    start_tick = bar_tick(start_bar)
    end_tick = bar_tick(end_bar)
    return [note_data for note_data in notes if start_tick <= note_data["start"] < end_tick]


def section_profile(section, note_tracks):
    start_bar = section["start_bar"]
    end_bar = section["end_bar"]
    active_roles = sum(1 for lane in STEMS if section_note_slice(note_tracks[lane], start_bar, end_bar))
    top_end_density = sum(len(section_note_slice(note_tracks[lane], start_bar, end_bar)) for lane in ("lead", "arp", "pluck", "vocal_melody", "countermelody", "strings"))
    lead_notes = section_note_slice(note_tracks["lead"], start_bar, end_bar)
    supersaw_notes = section_note_slice(note_tracks["supersaw_chords"], start_bar, end_bar)
    arp_notes = section_note_slice(note_tracks["arp"], start_bar, end_bar)
    pluck_notes = section_note_slice(note_tracks["pluck"], start_bar, end_bar)
    counter_notes = section_note_slice(note_tracks["countermelody"], start_bar, end_bar)
    hat_notes = section_note_slice(note_tracks["hats"], start_bar, end_bar)
    return {
        "active_roles": active_roles,
        "top_end_density": top_end_density,
        "lead_peak_pitch": max((note_data["pitch"] for note_data in lead_notes), default=0),
        "supersaw_density": len(supersaw_notes),
        "supersaw_octave_layers": len({note_data["pitch"] // 12 for note_data in supersaw_notes}),
        "arp_density": len(arp_notes),
        "pluck_density": len(pluck_notes),
        "counter_density": len(counter_notes),
        "hat_density": len(hat_notes),
        "rolling_bass": bool(section_note_slice(note_tracks["rolling_bass"], start_bar, end_bar)),
    }


def section_delta(profile_a, profile_b):
    delta = 0.0
    delta += abs(profile_a["active_roles"] - profile_b["active_roles"])
    delta += abs(profile_a["top_end_density"] - profile_b["top_end_density"]) * 0.02
    delta += abs(profile_a["lead_peak_pitch"] - profile_b["lead_peak_pitch"]) * 0.12
    delta += abs(profile_a["supersaw_density"] - profile_b["supersaw_density"]) * 0.02
    return round(delta, 2)


def validate_section_contrast(section_profiles):
    checks = [("Intro", "Verse", 1.6), ("Build", "Drop 1", 2.3), ("Drop 1", "Drop 2", 1.8), ("Breakdown", "Drop 2", 2.6)]
    failures = []
    total = 0.0
    for first_name, second_name, threshold in checks:
        if first_name in section_profiles and second_name in section_profiles:
            delta = section_delta(section_profiles[first_name], section_profiles[second_name])
            total += delta
            if delta < threshold:
                failures.append((first_name, second_name))
    return failures, round(total, 2)


def score_drop_difference(drop1_stats, drop2_stats):
    score = 0
    if drop2_stats["lead_peak_pitch"] > drop1_stats["lead_peak_pitch"]:
        score += 2
    if drop2_stats["counter_density"] > drop1_stats["counter_density"]:
        score += 2
    if drop2_stats["supersaw_octave_layers"] > drop1_stats["supersaw_octave_layers"]:
        score += 2
    if drop2_stats["hat_density"] > drop1_stats["hat_density"]:
        score += 1
    if drop2_stats["rolling_bass"] and not drop1_stats["rolling_bass"]:
        score += 2
    return score


def validate_song(tracks, blueprint, sections, chords, identity):
    note_tracks = {stem: events_to_notes(events) for stem, events in tracks.items()}
    report = {
        "lead_generation_mode": "hook_dominant",
        "harmony_engine_mode": "unified",
        "lead_hook_score": 0,
        "lead_motif_score": 0,
        "motif_repeat_score": 0,
        "motif_variation_score": 0,
        "answer_phrase_lift": 0,
        "payoff_strength": 0,
        "lead_avg_notes_per_bar": 0,
        "lead_max_notes_per_bar": 0,
        "lead_long_note_count": 0,
        "lead_long_note_ratio": 0,
        "lead_short_note_removed_count": 0,
        "lead_merged_note_count": 0,
        "lead_avg_note_length": 0,
        "lead_sustained_note_count": 0,
        "lead_sustain_passed": False,
        "lead_payoff_note_length": 0,
        "lead_payoff_note_pitch": 0,
        "lead_payoff_is_highest_or_second_highest": False,
        "lead_payoff_resolves_to_root_or_third": False,
        "lead_motif_repeat_passed": False,
        "lead_motif_rhythm_signature": "",
        "lead_variation_identity_passed": False,
        "lead_hook_dominance_score": 0,
        "lead_motif_pitch_changes": 0,
        "lead_first_half_pitch_spread": 0,
        "lead_phrase_pitch_spread": 0,
        "lead_expressive_jump_count": 0,
        "lead_largest_upward_jump": 0,
        "lead_pre_payoff_jump": 0,
        "lead_controlled_jump_passed": False,
        "lead_repairs_applied": 0,
        "payoff_is_dominant": False,
        "payoff_rank_in_phrase": 0,
        "payoff_velocity": 0,
        "pre_payoff_gap": 0.0,
        "lead_rhythmic_identity_score": 0,
        "lead_register_arc_score": 0,
        "lead_payoff_score": 0,
        "lead_supersaw_contrast_score": 0,
        "lead_supersaw_cohesion_score": 0,
        "lead_supersaw_cohesion_passed": False,
        "motif_supersaw_lock_applied": False,
        "lead_motif_interval_identity_score": 0,
        "lead_motif_interval_identity_passed": False,
        "anthem_payoff_score": 0,
        "release_score": 0,
        "dominance_score": 0,
        "crowd_response_score": 0,
        "drama_profile": "",
        "surprise_moment_detected": False,
        "counter_answer_mode": "",
        "lead_candidate_count": 0,
        "lead_selected_candidate_index": 0,
        "lead_best_hook_score": 0,
        "lead_candidate_rejections": 0,
        "lead_candidate_rejection_reasons": "",
        "lead_candidate_windows": [],
        "lead_phrase_regenerations": 0,
        "lead_regenerations": 0,
        "arp_density_rejections": 0,
        "pluck_density_rejections": 0,
        "arp_pluck_overlap_corrections": 0,
        "drop_budget_corrections": 0,
        "support_budget_corrections": 0,
        "countermelody_score": 0,
        "counter_answer_strength": 0,
        "countermelody_strength_applied": 0,
        "drop_harmony_valid": False,
        "drop_harmony_issue_count": 0,
        "lead_safe_tone_ratio": 0.0,
        "unsafe_peak_note_count": 0,
        "supersaw_max_pitch": 0,
        "supersaw_register_repairs": 0,
        "lead_drop_density_repairs": 0,
        "hook_repetition_avoided": 0,
        "lead_rhythm_contrast_passed": False,
        "lead_peak_moment_passed": False,
        "top_end_density_corrections": 0,
        "drop2_upgrade_score": 0,
        "supersaw_drop1_note_count": 0,
        "supersaw_drop2_note_count": 0,
        "supersaw_span_drop1": 0,
        "supersaw_span_drop2": 0,
        "supersaw_avg_length_drop1": 0,
        "supersaw_avg_length_drop2": 0,
        "supersaw_role_drop1": "controlled",
        "supersaw_role_drop2": "expanded",
        "supersaw_drop_energy_repaired": False,
        "supersaw_density_drop2": 0,
        "supersaw_note_count_per_chord": 0,
        "supersaw_sustain_avg": 0,
        "supersaw_weight_score": 0,
        "supersaw_upper_ratio": 0,
        "supersaw_pitch_spread": 0,
        "supersaw_avg_pitch": 0,
        "supersaw_voicing_score": 0,
        "supersaw_variation_count": 0,
        "supersaw_overlap_ratio": 0,
        "supersaw_dynamic_score": 0,
        "section_contrast_score": 0,
        "flatness_corrections": 0,
        "arp_activity_ratio": 0,
        "arp_pattern_name": "",
        "arp_pattern_locked_bars": 0,
        "bar_harmonic_unity_score": 0.0,
        "lead_harmonic_alignment": 0.0,
        "supersaw_harmonic_alignment": 0.0,
        "arp_harmonic_alignment": 0.0,
        "pad_harmonic_alignment": 0.0,
        "strings_harmonic_alignment": 0.0,
        "piano_harmonic_alignment": 0.0,
        "pluck_harmonic_alignment": 0.0,
        "harmony_repairs_applied": 0,
        "breakdown_engine_mode": "emotional_piano_strings",
        "breakdown_piano_motif_score": 0,
        "breakdown_piano_space_score": 0,
        "breakdown_piano_avg_notes_per_bar": 0,
        "breakdown_piano_long_note_count": 0,
        "breakdown_strings_motion_score": 0,
        "breakdown_strings_velocity_curve": "",
        "breakdown_strings_register_span": 0,
        "breakdown_tension_score": 0,
        "breakdown_anchor_note_length": 0,
        "breakdown_anchor_pitch": 0,
        "breakdown_pre_anchor_silence": 0,
        "strings_rise_amount": 0,
        "breakdown_emotion_score": 0,
        "breakdown_simple_mode": True,
        "piano_note_count_avg": 0,
        "piano_long_note_ratio": 0,
        "string_changes_count": 0,
        "emotional_anchor_present": False,
        "breakdown_piano_jump_count": 0,
        "breakdown_repairs_applied": 0,
        "snare_build_detected": False,
        "snare_density_curve": "",
        "snare_velocity_curve": "",
        "snare_final_fill_present": False,
        "snare_velocity_increases": False,
        "drop1_vs_drop2_density_ratio": 0,
        "drop1_avg_note_length": 0,
        "drop1_supersaw_span": 0,
        "drop_balance_score": 0,
        "drop1_impact_score": 0,
        "drop1_first_hit_density": 0,
        "drop1_lead_entry_type": "",
        "drop1_has_gap": False,
        "drop1_hook_note_count": 0,
        "drop1_hook_avg_length": 0,
        "drop1_hook_repeat_score": 0,
        "drop1_hook_strength": 0,
        "hook_note_count": 0,
        "hook_avg_length": 0,
        "hook_repeat_usage": 0,
        "hook_sections_applied": "",
        "hook_strength_score": 0,
        "hook_interval_jump": 0,
        "hook_peak_note": 0,
        "hook_range": 0,
        "hook_emotion_score": 0,
        "hook_peak_length": 0,
        "hook_pre_peak_silence": 0,
        "hook_peak_emphasis_score": 0,
        "hook_dominance_ratio": 0,
        "hook_candidates_generated": 0,
        "hook_selected_score": 0,
        "hook_variation_type": "",
        "global_note_cleanup_removed": 0,
        "global_note_cleanup_extended": 0,
        "global_melodic_avg_note_length": 0,
        "supersaw_energy_curve": "Intro 0.20 > Verse 0.35 > Build 0.55 > Drop 1 0.82 > Breakdown 0.18 > Build 2 0.68 > Drop 2 1.00",
    }
    lead_scores = []
    lead_motif_scores = []
    lead_rhythmic_scores = []
    lead_register_scores = []
    lead_payoff_scores = []
    lead_supersaw_scores = []
    lead_supersaw_cohesion_scores = []
    lead_motif_interval_identity_scores = []
    motif_supersaw_lock_flags = []
    anthem_payoff_scores = []
    release_scores = []
    dominance_scores = []
    crowd_response_scores = []
    lead_rhythm_contrast_flags = []
    lead_peak_moment_flags = []
    counter_scores = []
    motif_repeat_scores = []
    motif_variation_scores = []
    answer_lift_scores = []
    payoff_strength_scores = []
    counter_answer_strength_scores = []
    lead_avg_notes_per_bar_scores = []
    lead_max_notes_per_bar_scores = []
    lead_long_note_counts = []
    lead_long_note_ratios = []
    lead_short_note_removed_counts = []
    lead_merged_note_counts = []
    lead_avg_note_lengths = []
    lead_sustained_note_counts = []
    lead_sustain_flags = []
    lead_payoff_note_lengths = []
    lead_payoff_note_pitches = []
    lead_payoff_high_flags = []
    lead_payoff_resolve_flags = []
    lead_motif_repeat_flags = []
    lead_motif_signatures = []
    lead_variation_identity_flags = []
    lead_hook_dominance_scores = []
    lead_motif_pitch_change_counts = []
    lead_first_half_pitch_spreads = []
    lead_phrase_pitch_spreads = []
    lead_expressive_jump_counts = []
    lead_largest_upward_jumps = []
    lead_pre_payoff_jumps = []
    lead_controlled_jump_flags = []
    payoff_dominant_flags = []
    payoff_ranks = []
    payoff_velocities = []
    pre_payoff_gaps = []
    drop_safe_tone_ratios = []
    unsafe_peak_note_counts = []
    supersaw_max_pitches = []
    best_candidate_snapshot = {"index": 0, "score": 0, "count": len(HOOK_ARCHETYPES)}
    counter_mode_counts = {}
    drop_sections = [section for section in sections if section_kind(section["name"]) == "drop"]
    hook_winners = []

    for section in drop_sections:
        section_start = section["start_bar"]
        for phrase_start in range(section_start, section["end_bar"], 8):
            if phrase_start + 8 > section["end_bar"]:
                continue
            chord = chords[phrase_start % len(chords)]
            supersaw_window = section_note_slice(note_tracks["supersaw_chords"], phrase_start, phrase_start + 8)
            best_candidate, scored_candidates = select_best_hook_candidate(
                phrase_start,
                chords,
                identity,
                section["name"],
                supersaw_window,
                candidate_count=blueprint.get("hook_candidate_count", 4),
                recent_winners=hook_winners,
            )
            chosen_repetition_penalty = best_candidate["score"].get("repetition_penalty", 0.0)
            if chosen_repetition_penalty > 0:
                report["hook_repetition_avoided"] += 1
            hook_winners.append({
                "archetype": best_candidate["archetype"],
                "signature": candidate_window_signature(best_candidate["notes"], phrase_start),
            })
            hook_winners = hook_winners[-4:]
            report["lead_candidate_count"] = len(scored_candidates)
            note_tracks["lead"] = replace_notes_in_bar_range(note_tracks["lead"], phrase_start, phrase_start + 8, best_candidate["notes"])
            report["lead_phrase_regenerations"] += 1
            report["lead_regenerations"] += 1
            report["lead_candidate_rejections"] += max(0, len(scored_candidates) - 1)
            rejected_reasons = []
            for candidate in scored_candidates:
                if candidate["index"] != best_candidate["index"]:
                    rejected_reasons.extend(candidate["score"].get("rejection_reasons", []))
            if best_candidate["score"]["total"] > best_candidate_snapshot["score"]:
                best_candidate_snapshot = {
                    "index": best_candidate["index"],
                    "score": best_candidate["score"]["total"],
                    "count": len(scored_candidates),
                }
                report["drama_profile"] = best_candidate.get("drama_profile", "")
                report["surprise_moment_detected"] = bool(best_candidate["score"].get("surprise_moment_detected", False))
            if rejected_reasons:
                report["lead_candidate_rejection_reasons"] = ",".join(sorted(set(rejected_reasons)))
            report["lead_candidate_windows"].append({
                "section": section["name"],
                "phrase_start_bar": phrase_start + 1,
                "selected_candidate_index": best_candidate["index"],
                "selected_archetype": best_candidate["archetype"],
                "selected_variant_index": best_candidate.get("variant_index", 0),
                "best_hook_score": best_candidate["score"]["total"],
                "candidate_count": len(scored_candidates),
                "candidates": [
                    {
                        "index": candidate["index"],
                        "archetype": candidate["archetype"],
                        "variant_index": candidate.get("variant_index", 0),
                        "total": candidate["score"]["total"],
                        "motif_score": candidate["score"]["motif_score"],
                        "motif_repeat_score": candidate["score"].get("motif_repeat_score", 0),
                        "motif_variation_score": candidate["score"].get("motif_variation_score", 0),
                        "rhythmic_identity_score": candidate["score"]["rhythmic_identity_score"],
                        "register_arc_score": candidate["score"]["register_arc_score"],
                        "payoff_score": candidate["score"]["payoff_score"],
                        "answer_phrase_lift": candidate["score"].get("answer_phrase_lift", 0),
                        "payoff_strength": candidate["score"].get("payoff_strength", 0),
                        "lead_hook_dominance_score": candidate["score"].get("lead_hook_dominance_score", 0),
                        "lead_avg_notes_per_bar": candidate["score"].get("lead_avg_notes_per_bar", 0),
                        "lead_max_notes_per_bar": candidate["score"].get("lead_max_notes_per_bar", 0),
                        "lead_long_note_ratio": candidate["score"].get("lead_long_note_ratio", 0),
                        "lead_avg_note_length": candidate["score"].get("lead_avg_note_length", 0),
                        "lead_merged_note_count": candidate["score"].get("lead_merged_note_count", 0),
                        "lead_payoff_note_length": candidate["score"].get("lead_payoff_note_length", 0),
                        "lead_payoff_note_pitch": candidate["score"].get("lead_payoff_note_pitch", 0),
                        "lead_motif_pitch_changes": candidate["score"].get("lead_motif_pitch_changes", 0),
                        "lead_phrase_pitch_spread": candidate["score"].get("lead_phrase_pitch_spread", 0),
                        "lead_expressive_jump_count": candidate["score"].get("lead_expressive_jump_count", 0),
                        "lead_largest_upward_jump": candidate["score"].get("lead_largest_upward_jump", 0),
                        "lead_pre_payoff_jump": candidate["score"].get("lead_pre_payoff_jump", 0),
                        "lead_controlled_jump_passed": candidate["score"].get("lead_controlled_jump_passed", False),
                        "payoff_is_dominant": candidate["score"].get("payoff_is_dominant", False),
                        "payoff_rank_in_phrase": candidate["score"].get("payoff_rank_in_phrase", 0),
                        "payoff_velocity": candidate["score"].get("payoff_velocity", 0),
                        "pre_payoff_gap": candidate["score"].get("pre_payoff_gap", 0),
                        "singability_score": candidate["score"]["singability_score"],
                        "supersaw_contrast_score": candidate["score"]["supersaw_contrast_score"],
                        "supersaw_cohesion_score": candidate["score"].get("supersaw_cohesion_score", 0),
                        "motif_interval_identity_score": candidate["score"].get("motif_interval_identity_score", 0),
                        "anthem_payoff_score": candidate["score"]["anthem_payoff_score"],
                        "release_score": candidate["score"]["release_score"],
                        "dominance_score": candidate["score"]["dominance_score"],
                        "crowd_response_score": candidate["score"]["crowd_response_score"],
                        "drama_profile": candidate.get("drama_profile", ""),
                        "surprise_moment_detected": candidate["score"].get("surprise_moment_detected", False),
                        "repetition_penalty": candidate["score"].get("repetition_penalty", 0.0),
                        "valid": candidate["score"]["valid"],
                        "rejection_reasons": candidate["score"].get("rejection_reasons", []),
                    }
                    for candidate in scored_candidates
                ],
            })
            score = best_candidate["score"]
            lead_scores.append(score["total"])
            lead_motif_scores.append(score["motif_score"])
            motif_repeat_scores.append(score.get("motif_repeat_score", 0))
            motif_variation_scores.append(score.get("motif_variation_score", 0))
            answer_lift_scores.append(score.get("answer_phrase_lift", 0))
            payoff_strength_scores.append(score.get("payoff_strength", 0))
            lead_avg_notes_per_bar_scores.append(score.get("lead_avg_notes_per_bar", 0))
            lead_max_notes_per_bar_scores.append(score.get("lead_max_notes_per_bar", 0))
            lead_long_note_counts.append(score.get("lead_long_note_count", 0))
            lead_long_note_ratios.append(score.get("lead_long_note_ratio", 0))
            lead_short_note_removed_counts.append(score.get("lead_short_note_removed_count", 0))
            lead_merged_note_counts.append(score.get("lead_merged_note_count", 0))
            lead_avg_note_lengths.append(score.get("lead_avg_note_length", 0))
            lead_sustained_note_counts.append(score.get("lead_sustained_note_count", 0))
            lead_sustain_flags.append(bool(score.get("lead_sustain_passed", False)))
            lead_payoff_note_lengths.append(score.get("lead_payoff_note_length", 0))
            lead_payoff_note_pitches.append(score.get("lead_payoff_note_pitch", 0))
            lead_payoff_high_flags.append(bool(score.get("lead_payoff_is_highest_or_second_highest", False)))
            lead_payoff_resolve_flags.append(bool(score.get("lead_payoff_resolves_to_root_or_third", False)))
            lead_motif_repeat_flags.append(bool(score.get("lead_motif_repeat_passed", False)))
            lead_motif_signatures.append(score.get("lead_motif_rhythm_signature", ""))
            lead_variation_identity_flags.append(bool(score.get("lead_variation_identity_passed", False)))
            lead_hook_dominance_scores.append(score.get("lead_hook_dominance_score", 0))
            lead_motif_pitch_change_counts.append(score.get("lead_motif_pitch_changes", 0))
            lead_first_half_pitch_spreads.append(score.get("lead_first_half_pitch_spread", 0))
            lead_phrase_pitch_spreads.append(score.get("lead_phrase_pitch_spread", 0))
            lead_expressive_jump_counts.append(score.get("lead_expressive_jump_count", 0))
            lead_largest_upward_jumps.append(score.get("lead_largest_upward_jump", 0))
            lead_pre_payoff_jumps.append(score.get("lead_pre_payoff_jump", 0))
            lead_controlled_jump_flags.append(bool(score.get("lead_controlled_jump_passed", False)))
            payoff_dominant_flags.append(bool(score.get("payoff_is_dominant", False)))
            payoff_ranks.append(score.get("payoff_rank_in_phrase", 0))
            payoff_velocities.append(score.get("payoff_velocity", 0))
            pre_payoff_gaps.append(score.get("pre_payoff_gap", 0.0))
            lead_rhythmic_scores.append(score["rhythmic_identity_score"])
            lead_register_scores.append(score["register_arc_score"])
            lead_payoff_scores.append(score["payoff_score"])
            lead_supersaw_scores.append(score["supersaw_contrast_score"])
            lead_supersaw_cohesion_scores.append(score.get("supersaw_cohesion_score", 0))
            lead_motif_interval_identity_scores.append(score.get("motif_interval_identity_score", 0))
            motif_supersaw_lock_flags.append(bool(score.get("motif_supersaw_lock_applied", False)))
            anthem_payoff_scores.append(score["anthem_payoff_score"])
            release_scores.append(score["release_score"])
            dominance_scores.append(score["dominance_score"])
            crowd_response_scores.append(score["crowd_response_score"])
            lead_rhythm_contrast_flags.append(bool(score.get("rhythm_contrast_ok", False)))
            lead_peak_moment_flags.append(bool(score.get("peak_moment_ok", False)))
            drop_safe_tone_ratios.append(score.get("lead_safe_tone_ratio", 0.0))
            unsafe_peak_note_counts.append(score.get("unsafe_peak_note_count", 0))
            supersaw_max_pitches.append(score.get("supersaw_max_pitch", 0))
            report["lead_drop_density_repairs"] += score.get("lead_drop_density_repairs", 0)
            report["lead_repairs_applied"] += score.get("lead_repairs_applied", 0)
            report["lead_short_note_removed_count"] += score.get("lead_short_note_removed_count", 0)
            report["lead_merged_note_count"] += score.get("lead_merged_note_count", 0)
            report["unsafe_peak_note_count"] += score.get("unsafe_peak_note_repairs", 0)

            counter_score = countermelody_scores(note_tracks["countermelody"], note_tracks["lead"], phrase_start)
            if "Drop 2" in section["name"]:
                note_tracks["countermelody"] = replace_notes_in_bar_range(note_tracks["countermelody"], phrase_start, phrase_start + 8, rebuilt_counter_window(phrase_start, note_tracks["lead"], identity, chords, section["name"]))
                report["countermelody_strength_applied"] += 1
                counter_score = countermelody_scores(note_tracks["countermelody"], note_tracks["lead"], phrase_start)
            counter_scores.append(counter_score["total"])
            counter_answer_strength_scores.append(counter_score.get("answer_strength", 0))

        chord_lookup = lambda bar_index, chord_list=chords: chord_list[bar_index % len(chord_list)]
        drop_harmony_report = validate_drop_harmony(
            section_note_slice(note_tracks["lead"], section_start, section["end_bar"]),
            section_note_slice(note_tracks["supersaw_chords"], section_start, section["end_bar"]),
            section_start,
            section["end_bar"],
            chord_lookup,
        )
        if not drop_harmony_report["valid"]:
            repaired_lead, repaired_saw, repair_metrics = repair_drop_harmony(
                note_tracks["lead"],
                note_tracks["supersaw_chords"],
                section_start,
                section["end_bar"],
                chord_lookup,
            )
            note_tracks["lead"] = repaired_lead
            note_tracks["supersaw_chords"] = repaired_saw
            report["supersaw_register_repairs"] += repair_metrics["supersaw_register_repairs"]
            report["lead_drop_density_repairs"] += repair_metrics["lead_drop_density_repairs"]
            report["unsafe_peak_note_count"] += repair_metrics["unsafe_peak_note_repairs"]
            drop_harmony_report = validate_drop_harmony(
                section_note_slice(note_tracks["lead"], section_start, section["end_bar"]),
                section_note_slice(note_tracks["supersaw_chords"], section_start, section["end_bar"]),
                section_start,
                section["end_bar"],
                chord_lookup,
            )
        report["drop_harmony_issue_count"] += len(drop_harmony_report["issues"])
        drop_safe_tone_ratios.append(drop_harmony_report["avg_safe_ratio"])
        unsafe_peak_note_counts.append(drop_harmony_report["unsafe_peak_note_count"])
        supersaw_max_pitches.append(drop_harmony_report["supersaw_max_pitch"])

        for block_start in range(section_start, section["end_bar"], 4):
            if block_start + 4 > section["end_bar"]:
                continue
            active_arp_bars = [bar for bar in range(block_start, block_start + 4) if bar_note_density(note_tracks["arp"], bar) > 0]
            while len(active_arp_bars) > 3:
                target_bar = active_arp_bars[-1]
                note_tracks["arp"] = remove_notes_in_bar_range(note_tracks["arp"], target_bar, target_bar + 1)
                report["arp_density_rejections"] += 1
                active_arp_bars.pop()
            if len(active_arp_bars) == 4:
                target_bar = active_arp_bars[2]
                note_tracks["arp"] = remove_notes_in_bar_range(note_tracks["arp"], target_bar, target_bar + 1)
                report["arp_density_rejections"] += 1
            active_pluck_bars = [bar for bar in range(block_start, block_start + 4) if bar_note_density(note_tracks["pluck"], bar) > 0]
            while len(active_pluck_bars) > 1:
                target_bar = active_pluck_bars[-1]
                note_tracks["pluck"] = remove_notes_in_bar_range(note_tracks["pluck"], target_bar, target_bar + 1)
                report["drop_budget_corrections"] += 1
                report["support_budget_corrections"] += 1
                report["pluck_density_rejections"] += 1
                active_pluck_bars.pop()

        for bar in range(section_start, section["end_bar"]):
            lead_bar = notes_starting_in_bar(note_tracks["lead"], bar)
            counter_bar = notes_starting_in_bar(note_tracks["countermelody"], bar)
            arp_bar = notes_starting_in_bar(note_tracks["arp"], bar)
            pluck_bar = notes_starting_in_bar(note_tracks["pluck"], bar)
            if lead_bar and len(lead_bar) >= 4 and arp_bar:
                note_tracks["arp"] = replace_notes_in_bar_range(note_tracks["arp"], bar, bar + 1, arp_bar[:2])
                report["arp_density_rejections"] += 1
            if lead_bar and len(lead_bar) >= 3 and notes_starting_in_bar(note_tracks["vocal_melody"], bar):
                note_tracks["vocal_melody"] = remove_notes_in_bar_range(note_tracks["vocal_melody"], bar, bar + 1)
                report["drop_budget_corrections"] += 1
            if lead_bar and pluck_bar:
                note_tracks["pluck"] = remove_notes_in_bar_range(note_tracks["pluck"], bar, bar + 1)
                report["drop_budget_corrections"] += 1
                report["support_budget_corrections"] += 1
                report["pluck_density_rejections"] += 1
            if counter_bar and arp_bar:
                offbeat_only = []
                for note_data in arp_bar:
                    beat = round((note_data["start"] - bar_tick(bar)) / TICKS, 2)
                    if is_offbeat_position(beat):
                        offbeat_only.append(note_data)
                note_tracks["arp"] = replace_notes_in_bar_range(note_tracks["arp"], bar, bar + 1, offbeat_only)
                report["arp_density_rejections"] += 1
            if arp_bar and pluck_bar:
                note_tracks["pluck"] = remove_notes_in_bar_range(note_tracks["pluck"], bar, bar + 1)
                report["arp_pluck_overlap_corrections"] += 1
                report["pluck_density_rejections"] += 1

            secondary_order = ["vocal_melody", "arp", "strings", "countermelody"]
            secondary_active = [lane for lane in secondary_order if notes_overlapping_bar(note_tracks[lane], bar)]
            if "countermelody" in secondary_active and "arp" in secondary_active:
                note_tracks["arp"] = remove_notes_in_bar_range(note_tracks["arp"], bar, bar + 1)
                secondary_active.remove("arp")
                report["drop_budget_corrections"] += 1
                report["support_budget_corrections"] += 1
            if "countermelody" in secondary_active and "vocal_melody" in secondary_active:
                note_tracks["vocal_melody"] = remove_notes_in_bar_range(note_tracks["vocal_melody"], bar, bar + 1)
                secondary_active.remove("vocal_melody")
                report["drop_budget_corrections"] += 1
                report["support_budget_corrections"] += 1
            while len(secondary_active) > 2:
                lane = secondary_active[0]
                note_tracks[lane] = remove_notes_in_bar_range(note_tracks[lane], bar, bar + 1)
                secondary_active.pop(0)
                report["drop_budget_corrections"] += 1
                report["support_budget_corrections"] += 1

            tertiary_active = [lane for lane in ("pad", "piano", "pluck") if notes_overlapping_bar(note_tracks[lane], bar)]
            peak_bar = (bar - section_start) % 8 in (6, 7) or "Drop 2" in section["name"]
            if peak_bar:
                for lane in tertiary_active:
                    note_tracks[lane] = remove_notes_in_bar_range(note_tracks[lane], bar, bar + 1)
                    report["drop_budget_corrections"] += 1
                    report["support_budget_corrections"] += 1

            dense_lanes = []
            for lane in ("lead", "arp", "pluck", "vocal_melody", "countermelody", "strings"):
                overlapping = notes_overlapping_bar(note_tracks[lane], bar)
                dense_count = len([note_data for note_data in overlapping if (note_data["end"] - note_data["start"]) / TICKS <= 0.5])
                if dense_count >= 3 or len(overlapping) >= 4:
                    dense_lanes.append(lane)
            if len(dense_lanes) > 3:
                if notes_overlapping_bar(note_tracks["pluck"], bar):
                    note_tracks["pluck"] = remove_notes_in_bar_range(note_tracks["pluck"], bar, bar + 1)
                elif notes_overlapping_bar(note_tracks["arp"], bar):
                    note_tracks["arp"] = remove_notes_in_bar_range(note_tracks["arp"], bar, bar + 1)
                elif notes_overlapping_bar(note_tracks["vocal_melody"], bar):
                    note_tracks["vocal_melody"] = remove_notes_in_bar_range(note_tracks["vocal_melody"], bar, bar + 1)
                elif notes_overlapping_bar(note_tracks["countermelody"], bar):
                    note_tracks["countermelody"] = remove_notes_in_bar_range(note_tracks["countermelody"], bar, bar + 1)
                report["top_end_density_corrections"] += 1

    progression_name = blueprint.get("progression_name", "uplifting")
    progression_family = blueprint.get("progression_family", "")
    chord_lookup = lambda bar_index, chord_list=chords: chord_list[bar_index % len(chord_list)]
    unity_checked_bars = 0
    unity_valid_bars = 0
    for section in sections:
        for bar_index in range(section["start_bar"], section["end_bar"]):
            harmonic_state = build_harmonic_state(bar_index, progression_name, chord_lookup(bar_index), progression_family)
            unity_report = validate_bar_harmonic_unity(bar_index, harmonic_state, note_tracks)
            unity_checked_bars += 1
            if unity_report["valid"]:
                unity_valid_bars += 1
                continue
            for stem_name, _, _ in unity_report["issues"]:
                original_bar_notes = notes_starting_in_bar(note_tracks[stem_name], bar_index)
                low, high = harmonic_note_bounds(stem_name)
                repaired_bar_notes = remap_bar_to_harmonic_targets(original_bar_notes, harmonic_state, low=low, high=high)
                if stem_name == "lead" and section_kind(section["name"]) == "drop" and notes_starting_in_bar(note_tracks["supersaw_chords"], bar_index):
                    repaired_bar_notes = simplify_drop_lead_bar(sorted(repaired_bar_notes, key=lambda item: (item["start"], item["pitch"])))
                    for note_data in repaired_bar_notes:
                        note_data["end"] = max(note_data["end"], min(bar_tick(bar_index + 1), note_data["start"] + tick(0.75)))
                if stem_name == "supersaw_chords":
                    for note_data in repaired_bar_notes:
                        while note_data["pitch"] > 84:
                            note_data["pitch"] -= 12
                if repaired_bar_notes != original_bar_notes:
                    report["harmony_repairs_applied"] += 1
                note_tracks[stem_name] = replace_notes_in_bar_range(note_tracks[stem_name], bar_index, bar_index + 1, repaired_bar_notes)
            if validate_bar_harmonic_unity(bar_index, harmonic_state, note_tracks)["valid"]:
                unity_valid_bars += 1

    section_profiles = {section["name"]: section_profile(section, note_tracks) for section in sections}
    report["drop2_upgrade_score"] = score_drop_difference(section_profiles.get("Drop 1", {}), section_profiles.get("Drop 2", {})) if "Drop 1" in section_profiles and "Drop 2" in section_profiles else 0
    contrast_failures, contrast_total = validate_section_contrast(section_profiles)
    report["section_contrast_score"] = contrast_total
    for first_name, second_name in contrast_failures:
        if first_name == "Build" and second_name == "Drop 1":
            target = next((section for section in sections if section["name"] == "Build"), None)
            if target:
                for lane in ("supersaw_chords", "pad", "strings"):
                    note_tracks[lane] = remove_notes_in_bar_range(note_tracks[lane], target["start_bar"], min(target["end_bar"], target["start_bar"] + 4))
                report["flatness_corrections"] += 1
        elif first_name == "Drop 1" and second_name == "Drop 2":
            drop1 = next((section for section in sections if section["name"] == "Drop 1"), None)
            drop2 = next((section for section in sections if section["name"] == "Drop 2"), None)
            if drop1 and drop2:
                for lane in ("pad", "strings", "arp"):
                    note_tracks[lane] = remove_notes_in_bar_range(note_tracks[lane], drop1["start_bar"], min(drop1["end_bar"], drop1["start_bar"] + 8))
                extra_supersaw = []
                for note_data in section_note_slice(note_tracks["supersaw_chords"], drop2["start_bar"], drop2["end_bar"]):
                    if note_data["pitch"] < 96 and note_data["start"] >= bar_tick(drop2["start_bar"] + 8):
                        extra_supersaw.append({"start": note_data["start"], "end": note_data["end"], "pitch": clamp(note_data["pitch"] + 12, 72, 108), "velocity": max(52, note_data["velocity"] - 8), "channel": note_data["channel"]})
                note_tracks["supersaw_chords"].extend(extra_supersaw[:48])
                report["flatness_corrections"] += 1
        elif first_name == "Breakdown" and second_name == "Drop 2":
            target = next((section for section in sections if section["name"] == "Breakdown"), None)
            if target:
                for lane in ("supersaw_chords", "arp", "strings"):
                    note_tracks[lane] = remove_notes_in_bar_range(note_tracks[lane], target["start_bar"], target["end_bar"])
                report["flatness_corrections"] += 1

    supersaw_energy_repair = repair_supersaw_drop_energy(note_tracks, drop_sections, chords)
    if len(drop_sections) >= 2:
        drop1 = drop_sections[0]
        drop2 = drop_sections[1]
        drop1_lead_balance_repairs = repair_drop1_lead_balance(note_tracks, drop1, chords)
        report["lead_repairs_applied"] += drop1_lead_balance_repairs
        drop1_impact_repairs = apply_drop1_impact_engine(note_tracks, drop_sections, chords)
        report["lead_repairs_applied"] += drop1_impact_repairs["drop1_impact_repairs"]
        drop1_hook_repairs = apply_drop1_hook_engine(note_tracks, drop_sections, chords)
        report["lead_repairs_applied"] += drop1_hook_repairs["drop1_hook_repairs"]
        drop1_saw_notes = section_note_slice(note_tracks["supersaw_chords"], drop1["start_bar"], drop1["end_bar"])
        drop2_saw_notes = section_note_slice(note_tracks["supersaw_chords"], drop2["start_bar"], drop2["end_bar"])
        drop1_lead_notes = section_note_slice(note_tracks["lead"], drop1["start_bar"], drop1["end_bar"])
        drop1_saw_stats = supersaw_drop_stats(drop1_saw_notes)
        drop2_saw_stats = supersaw_drop_stats(drop2_saw_notes)
        report["drop2_upgrade_score"] = score_drop_upgrade(drop1_saw_notes, drop2_saw_notes)
        report["supersaw_drop1_note_count"] = drop1_saw_stats["note_count"]
        report["supersaw_drop2_note_count"] = drop2_saw_stats["note_count"]
        report["supersaw_span_drop1"] = drop1_saw_stats["span"]
        report["supersaw_span_drop2"] = drop2_saw_stats["span"]
        report["supersaw_avg_length_drop1"] = drop1_saw_stats["avg_length"]
        report["supersaw_avg_length_drop2"] = drop2_saw_stats["avg_length"]
        report["supersaw_drop_energy_repaired"] = supersaw_energy_repair["repaired"]
        report["supersaw_density_drop2"] = round(drop2_saw_stats["note_count"] / max(1, drop2["bars"]), 2)
        report["supersaw_note_count_per_chord"] = drop2_saw_stats["min_event_count"]
        report["supersaw_sustain_avg"] = drop2_saw_stats["avg_length"]
        report["supersaw_weight_score"] = score_supersaw_weight(drop1_saw_notes, drop2_saw_notes)
        report["supersaw_upper_ratio"] = drop2_saw_stats["upper_ratio"]
        report["supersaw_pitch_spread"] = drop2_saw_stats["span"]
        report["supersaw_avg_pitch"] = drop2_saw_stats["avg_pitch"]
        report["supersaw_voicing_score"] = score_supersaw_voicing(drop1_saw_notes, drop2_saw_notes)
        report["supersaw_variation_count"] = drop2_saw_stats["variation_count"]
        report["supersaw_overlap_ratio"] = drop2_saw_stats["overlap_ratio"]
        report["supersaw_dynamic_score"] = score_supersaw_dynamic(drop1_saw_notes, drop2_saw_notes)
        report["drop1_vs_drop2_density_ratio"] = round(drop1_saw_stats["note_count"] / max(1, drop2_saw_stats["note_count"]), 3)
        report["drop1_avg_note_length"] = drop1_saw_stats["avg_length"]
        report["drop1_supersaw_span"] = drop1_saw_stats["span"]
        report["drop_balance_score"] = score_drop_balance(drop1_saw_notes, drop2_saw_notes, drop1_lead_notes)
        report.update(drop1_impact_metrics(note_tracks, sections))
        report.update(drop1_hook_metrics(note_tracks, sections))

    breakdown_report = apply_breakdown_emotion_engine(note_tracks, sections, chords, blueprint)
    report.update(breakdown_report)

    total_drop_bars = sum(section["bars"] for section in drop_sections)
    arp_active_bars = sum(1 for section in drop_sections for bar in range(section["start_bar"], section["end_bar"]) if bar_note_density(note_tracks["arp"], bar) > 0)
    report["lead_hook_score"] = round(sum(lead_scores) / max(1, len(lead_scores)), 2)
    report["lead_motif_score"] = round(sum(lead_motif_scores) / max(1, len(lead_motif_scores)), 2)
    report["motif_repeat_score"] = round(sum(motif_repeat_scores) / max(1, len(motif_repeat_scores)), 2)
    report["motif_variation_score"] = round(sum(motif_variation_scores) / max(1, len(motif_variation_scores)), 2)
    report["answer_phrase_lift"] = round(sum(answer_lift_scores) / max(1, len(answer_lift_scores)), 2)
    report["payoff_strength"] = round(sum(payoff_strength_scores) / max(1, len(payoff_strength_scores)), 2)
    report["lead_avg_notes_per_bar"] = round(sum(lead_avg_notes_per_bar_scores) / max(1, len(lead_avg_notes_per_bar_scores)), 2)
    report["lead_max_notes_per_bar"] = max(lead_max_notes_per_bar_scores, default=0)
    report["lead_long_note_count"] = int(sum(lead_long_note_counts))
    report["lead_long_note_ratio"] = round(sum(lead_long_note_ratios) / max(1, len(lead_long_note_ratios)), 3)
    report["lead_merged_note_count"] = int(sum(lead_merged_note_counts))
    report["lead_avg_note_length"] = round(sum(lead_avg_note_lengths) / max(1, len(lead_avg_note_lengths)), 2)
    report["lead_sustained_note_count"] = int(sum(lead_sustained_note_counts))
    report["lead_sustain_passed"] = bool(lead_sustain_flags) and all(lead_sustain_flags)
    report["lead_payoff_note_length"] = round(max(lead_payoff_note_lengths, default=0), 2)
    report["lead_payoff_note_pitch"] = max(lead_payoff_note_pitches, default=0)
    report["lead_payoff_is_highest_or_second_highest"] = bool(lead_payoff_high_flags) and all(lead_payoff_high_flags)
    report["lead_payoff_resolves_to_root_or_third"] = bool(lead_payoff_resolve_flags) and all(lead_payoff_resolve_flags)
    report["lead_motif_repeat_passed"] = bool(lead_motif_repeat_flags) and all(lead_motif_repeat_flags)
    report["lead_motif_rhythm_signature"] = next((signature for signature in lead_motif_signatures if signature), "")
    report["lead_variation_identity_passed"] = bool(lead_variation_identity_flags) and all(lead_variation_identity_flags)
    report["lead_hook_dominance_score"] = round(sum(lead_hook_dominance_scores) / max(1, len(lead_hook_dominance_scores)), 2)
    report["lead_motif_pitch_changes"] = max(lead_motif_pitch_change_counts, default=0)
    report["lead_first_half_pitch_spread"] = max(lead_first_half_pitch_spreads, default=0)
    report["lead_phrase_pitch_spread"] = max(lead_phrase_pitch_spreads, default=0)
    report["lead_expressive_jump_count"] = max(lead_expressive_jump_counts, default=0)
    report["lead_largest_upward_jump"] = max(lead_largest_upward_jumps, default=0)
    report["lead_pre_payoff_jump"] = max(lead_pre_payoff_jumps, default=0)
    report["lead_controlled_jump_passed"] = bool(lead_controlled_jump_flags) and all(lead_controlled_jump_flags)
    report["payoff_is_dominant"] = bool(payoff_dominant_flags) and all(payoff_dominant_flags)
    report["payoff_rank_in_phrase"] = min((rank for rank in payoff_ranks if rank), default=0)
    report["payoff_velocity"] = max(payoff_velocities, default=0)
    report["pre_payoff_gap"] = round(min(pre_payoff_gaps), 2) if pre_payoff_gaps else 0.0
    report["lead_rhythmic_identity_score"] = round(sum(lead_rhythmic_scores) / max(1, len(lead_rhythmic_scores)), 2)
    report["lead_register_arc_score"] = round(sum(lead_register_scores) / max(1, len(lead_register_scores)), 2)
    report["lead_payoff_score"] = round(sum(lead_payoff_scores) / max(1, len(lead_payoff_scores)), 2)
    report["lead_supersaw_contrast_score"] = round(sum(lead_supersaw_scores) / max(1, len(lead_supersaw_scores)), 2)
    report["lead_supersaw_cohesion_score"] = round(sum(lead_supersaw_cohesion_scores) / max(1, len(lead_supersaw_cohesion_scores)), 2)
    report["lead_supersaw_cohesion_passed"] = report["lead_supersaw_cohesion_score"] >= 2.0
    report["motif_supersaw_lock_applied"] = bool(motif_supersaw_lock_flags) and all(motif_supersaw_lock_flags)
    report["lead_motif_interval_identity_score"] = round(sum(lead_motif_interval_identity_scores) / max(1, len(lead_motif_interval_identity_scores)), 2)
    report["lead_motif_interval_identity_passed"] = report["lead_motif_interval_identity_score"] >= 3.0
    report["anthem_payoff_score"] = round(sum(anthem_payoff_scores) / max(1, len(anthem_payoff_scores)), 2)
    report["release_score"] = round(sum(release_scores) / max(1, len(release_scores)), 2)
    report["dominance_score"] = round(sum(dominance_scores) / max(1, len(dominance_scores)), 2)
    report["crowd_response_score"] = round(sum(crowd_response_scores) / max(1, len(crowd_response_scores)), 2)
    report["lead_rhythm_contrast_passed"] = bool(lead_rhythm_contrast_flags) and all(lead_rhythm_contrast_flags)
    report["lead_peak_moment_passed"] = bool(lead_peak_moment_flags) and all(lead_peak_moment_flags)
    report["lead_selected_candidate_index"] = best_candidate_snapshot["index"]
    report["lead_best_hook_score"] = best_candidate_snapshot["score"]
    report["lead_candidate_count"] = best_candidate_snapshot["count"]
    report["counter_answer_mode"] = blueprint.get("_selected_counter_answer_mode", "")
    report["countermelody_score"] = round(sum(counter_scores) / max(1, len(counter_scores)), 2)
    report["counter_answer_strength"] = round(sum(counter_answer_strength_scores) / max(1, len(counter_answer_strength_scores)), 2)
    report["arp_activity_ratio"] = round(arp_active_bars / max(1, total_drop_bars), 2)
    report["drop_harmony_valid"] = report["drop_harmony_issue_count"] == 0
    report["lead_safe_tone_ratio"] = round(sum(drop_safe_tone_ratios) / max(1, len(drop_safe_tone_ratios)), 3)
    report["unsafe_peak_note_count"] = int(report["unsafe_peak_note_count"] + sum(unsafe_peak_note_counts))
    report["supersaw_max_pitch"] = max(supersaw_max_pitches, default=0)
    locked_arp_patterns = blueprint.get("_locked_arp_patterns", {})
    if locked_arp_patterns:
        pattern_counts = {}
        locked_bars = 0
        for item in locked_arp_patterns.values():
            pattern_counts[item["name"]] = pattern_counts.get(item["name"], 0) + 1
            locked_bars = max(locked_bars, item.get("locked_bars", 0))
        report["arp_pattern_name"] = max(pattern_counts, key=pattern_counts.get)
        report["arp_pattern_locked_bars"] = locked_bars
    report["bar_harmonic_unity_score"] = round(unity_valid_bars / max(1, unity_checked_bars), 3)
    total_bars = max((section["end_bar"] for section in sections), default=0)
    report["lead_harmonic_alignment"] = harmonic_alignment_ratio(note_tracks["lead"], 0, total_bars, chord_lookup, progression_name, progression_family)
    report["supersaw_harmonic_alignment"] = harmonic_alignment_ratio(note_tracks["supersaw_chords"], 0, total_bars, chord_lookup, progression_name, progression_family)
    report["arp_harmonic_alignment"] = harmonic_alignment_ratio(note_tracks["arp"], 0, total_bars, chord_lookup, progression_name, progression_family)
    report["pad_harmonic_alignment"] = harmonic_alignment_ratio(note_tracks["pad"], 0, total_bars, chord_lookup, progression_name, progression_family)
    report["strings_harmonic_alignment"] = harmonic_alignment_ratio(note_tracks["strings"], 0, total_bars, chord_lookup, progression_name, progression_family)
    report["piano_harmonic_alignment"] = harmonic_alignment_ratio(note_tracks["piano"], 0, total_bars, chord_lookup, progression_name, progression_family)
    report["pluck_harmonic_alignment"] = harmonic_alignment_ratio(note_tracks["pluck"], 0, total_bars, chord_lookup, progression_name, progression_family)
    report.update(snare_build_metrics(note_tracks["clap_snare"], sections))
    report.update(apply_hook_engine(note_tracks, sections, chords))
    report.update(global_note_cleanup(note_tracks))
    blueprint["validation_report"] = report
    for stem in tracks:
        tracks[stem] = notes_to_events(note_tracks[stem])
    return tracks, blueprint


def section_kind(name: str) -> str:
    lowered = name.lower()
    if "intro" in lowered:
        return "intro"
    if "verse" in lowered:
        return "verse"
    if "build" in lowered:
        return "build"
    if "drop" in lowered:
        return "drop"
    if "breakdown" in lowered:
        return "breakdown"
    if "outro" in lowered:
        return "outro"
    return "other"


def format_story_entry(entry):
    if not entry:
        return ""
    section_name, offset = entry
    return f"{section_name}+{offset}"


def arrangement_story_section_bars(arrangement: str, blueprint=None):
    story_profile = (blueprint or {}).get("arrangement_story_profile", {})
    story_sections = story_profile.get("section_bars", {}).get(arrangement)
    return story_sections or ARRANGEMENTS[arrangement]


def arrange_sections(arrangement: str, blueprint=None):
    sections = []
    current_bar = 0
    for name, bars in arrangement_story_section_bars(arrangement, blueprint):
        sections.append({"name": name, "bars": bars, "start_bar": current_bar, "end_bar": current_bar + bars})
        current_bar += bars
    return sections


def progression_chords(root: str, progression_name: str):
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
    for degree in PROGRESSIONS[progression_name]:
        tones = []
        for scale_degree in triad_map[degree]:
            octave = 4 if scale_degree not in (6, 7) else 3
            tones.append(note(root, scale_degree, octave))
        tones = sorted(tones)
        chords.append({
            "degree": degree,
            "notes": tones,
            "root": tones[0],
            "third": tones[1],
            "fifth": tones[2],
        })
    return chords


def choose_weighted(rng: random.Random, values, user_bias: str):
    if user_bias == "low":
        return values[rng.randrange(0, max(1, len(values) - 1))]
    if user_bias == "high":
        return values[rng.randrange(1, len(values))]
    return rng.choice(values)


def select_track_identity(genre: str, rng: random.Random, user_choice=None):
    global RECENT_TRACK_IDENTITIES
    allowed = GENRE_VARIATIONS.get(genre, list(TRACK_IDENTITY_PROFILES.keys()))
    if user_choice and user_choice != "auto" and user_choice in TRACK_IDENTITY_PROFILES:
        key = user_choice
    else:
        available = [item for item in allowed if item not in RECENT_TRACK_IDENTITIES]
        key = rng.choice(available or allowed)
        RECENT_TRACK_IDENTITIES.append(key)
        RECENT_TRACK_IDENTITIES = RECENT_TRACK_IDENTITIES[-3:]
    profile = copy.deepcopy(TRACK_IDENTITY_PROFILES[key])
    profile["profile_key"] = key
    profile["genre"] = genre
    profile["allowed_variations_for_genre"] = list(allowed)
    return profile


def deep_merge_dict(base, overlay):
    merged = copy.deepcopy(base)
    for key, value in (overlay or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge_dict(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def select_identity_variation(identity_key: str, rng: random.Random, track_identity_choice=None):
    global RECENT_IDENTITY_VARIATIONS
    variations = IDENTITY_VARIATIONS.get(identity_key, [])
    if not variations:
        return "DEFAULT"
    recent = RECENT_IDENTITY_VARIATIONS.get(identity_key, [])
    available = [item for item in variations if item not in recent]
    chosen = rng.choice(available or variations)
    RECENT_IDENTITY_VARIATIONS[identity_key] = (recent + [chosen])[-3:]
    return chosen


def identity_variation_behavior(identity_key: str, variation_type: str):
    return IDENTITY_VARIATION_BEHAVIOR.get(identity_key, {}).get(variation_type, {})


def apply_identity_profile_to_blueprint(blueprint, identity_profile, selected_progression, genre=None):
    overrides = identity_profile.get("blueprint_overrides", {})
    for key, value in overrides.items():
        blueprint[key] = value
    identity_key = identity_profile["profile_key"]
    variation_type = identity_profile.get("identity_variation_type", "DEFAULT")
    variation_behavior = identity_variation_behavior(identity_key, variation_type)
    for key, value in variation_behavior.get("blueprint", {}).items():
        blueprint[key] = value
    story_profile = copy.deepcopy(ARRANGEMENT_STORY_PROFILES.get(identity_key, {}))
    story_profile = deep_merge_dict(story_profile, variation_behavior.get("story", {}))
    blueprint["track_identity_key"] = identity_profile["profile_key"]
    blueprint["track_identity"] = identity_profile["identity_name"]
    blueprint["track_identity_description"] = identity_profile["description"]
    blueprint["variation_type"] = variation_type
    blueprint["variation_behavior_summary"] = variation_behavior.get("summary", "Default identity story behavior.")
    blueprint["emotional_target"] = identity_profile["emotional_target"]
    blueprint["genre"] = genre or selected_progression
    blueprint["variation_identity"] = identity_profile["identity_name"]
    blueprint["allowed_variations_for_genre"] = ",".join(identity_profile.get("allowed_variations_for_genre", []))
    blueprint["selected_chord_progression"] = selected_progression
    blueprint["identity_intro_style"] = identity_profile["intro_behavior"]
    blueprint["identity_bass_style"] = identity_profile["bass_behavior"]
    blueprint["identity_lead_style"] = identity_profile["lead_behavior"]
    blueprint["identity_hook_shape"] = identity_profile["hook_shape"]
    blueprint["identity_supersaw_style"] = identity_profile["supersaw_behavior"]
    blueprint["identity_arp_style"] = identity_profile["arp_behavior"]
    blueprint["identity_pluck_style"] = identity_profile["pluck_behavior"]
    blueprint["identity_breakdown_style"] = identity_profile["breakdown_behavior"]
    blueprint["identity_drum_build_style"] = identity_profile["drum_build_behavior"]
    blueprint["identity_drop_style"] = identity_profile["drop_behavior"]
    blueprint["identity_density_targets"] = identity_profile["density_targets"]
    blueprint["identity_validation_targets"] = identity_profile["validation_targets"]
    blueprint["arrangement_story_profile"] = story_profile
    blueprint["arrangement_story_name"] = story_profile.get("story_name", "default_story")
    blueprint["arrangement_story_description"] = story_profile.get("description", "")
    blueprint["arrangement_intro_instruments"] = ",".join(story_profile.get("intro_instruments", []))
    blueprint["arrangement_breakdown_instruments"] = ",".join(story_profile.get("breakdown_instruments", []))
    blueprint["arrangement_lead_entry"] = format_story_entry(story_profile.get("lead_entry"))
    blueprint["arrangement_arp_entry"] = format_story_entry(story_profile.get("arp_entry"))
    blueprint["arrangement_bass_entry"] = format_story_entry(story_profile.get("bass_entry"))
    return blueprint


def progression_identity(progression: str):
    mapping = {
        "uplifting": {
            "progression_family": "lifted",
            "voicing_profile": "open_air",
            "cadence_profile": "tonic_lift",
            "breakdown_emotion": "skyline_recall",
            "drop_harmony_entry": "emotional_stack",
            "lead_resolution_bias": "fifth_to_tonic",
            "theme_degree": 5,
        },
        "classic": {
            "progression_family": "classic_warmth",
            "voicing_profile": "mid_stack",
            "cadence_profile": "smooth_land",
            "breakdown_emotion": "warm_blend",
            "drop_harmony_entry": "sustain_first",
            "lead_resolution_bias": "third_to_root",
            "theme_degree": 3,
        },
        "festival": {
            "progression_family": "festival_cycle",
            "voicing_profile": "low_fifth_power",
            "cadence_profile": "direct_loop",
            "breakdown_emotion": "rhythmic_support",
            "drop_harmony_entry": "full_stack",
            "lead_resolution_bias": "root_anchor",
            "theme_degree": 1,
        },
        "hopeful": {
            "progression_family": "hopeful_pull",
            "voicing_profile": "wide_emotive",
            "cadence_profile": "delayed_resolve",
            "breakdown_emotion": "suspended_space",
            "drop_harmony_entry": "delayed_bloom",
            "lead_resolution_bias": "suspended_lift",
            "theme_degree": 6,
        },
        "progressive": {
            "progression_family": "progressive_flow",
            "voicing_profile": "wide_emotive",
            "cadence_profile": "delayed_resolve",
            "breakdown_emotion": "suspended_space",
            "drop_harmony_entry": "sustain_first",
            "lead_resolution_bias": "suspended_lift",
            "theme_degree": 5,
        },
    }
    return mapping[progression].copy()


def track_archetype_identity(progression: str):
    mapping = {
        "uplifting": ["emotional_uplifter", "anthemic_classic", "vocal_melodic"],
        "classic": ["anthemic_classic", "vocal_melodic", "progressive_dream"],
        "festival": ["festival_driver", "emotional_uplifter", "anthemic_classic"],
        "hopeful": ["progressive_dream", "vocal_melodic", "emotional_uplifter"],
        "progressive": ["progressive_dream", "vocal_melodic", "anthemic_classic"],
    }
    return mapping[progression]


def counter_identity_bundle(rng: random.Random, archetype: str):
    bundles = {
        "emotional_uplifter": [
            {"presence": "featured", "span": "long", "register": "high_lane", "role": "featured_answer"},
            {"presence": "clear", "span": "medium", "register": "mid_lane", "role": "support"},
            {"presence": "late_focus", "span": "extended", "register": "wide_lane", "role": "transition_push"},
        ],
        "festival_driver": [
            {"presence": "featured", "span": "extended", "register": "high_lane", "role": "transition_push"},
            {"presence": "clear", "span": "long", "register": "wide_lane", "role": "featured_answer"},
            {"presence": "late_focus", "span": "medium", "register": "mid_lane", "role": "late_answer"},
        ],
        "vocal_melodic": [
            {"presence": "whisper", "span": "short", "register": "low_lane", "role": "late_answer"},
            {"presence": "late_focus", "span": "medium", "register": "mid_lane", "role": "support"},
            {"presence": "clear", "span": "medium", "register": "high_lane", "role": "featured_answer"},
        ],
        "progressive_dream": [
            {"presence": "whisper", "span": "short", "register": "low_lane", "role": "support"},
            {"presence": "clear", "span": "medium", "register": "mid_lane", "role": "late_answer"},
            {"presence": "late_focus", "span": "long", "register": "wide_lane", "role": "transition_push"},
        ],
        "anthemic_classic": [
            {"presence": "clear", "span": "medium", "register": "mid_lane", "role": "support"},
            {"presence": "featured", "span": "long", "register": "wide_lane", "role": "featured_answer"},
            {"presence": "late_focus", "span": "extended", "register": "high_lane", "role": "transition_push"},
        ],
    }
    return dict(rng.choice(bundles[archetype]))


def macro_archetype_family(rng: random.Random, progression: str, archetype: str, blueprint, energy_bias: str):
    families = {
        "emotional_uplifter": [
            {
                "family": "late_bloom_emotional",
                "macro_journey_profile": "breakdown_rebirth",
                "section_weight_profile": "late_bloom",
                "drop_pair_profile": "drop1_tight_drop2_emotional",
                "final_lift_profile": "wide_release",
                "breakdown_bias": ("harmonic_lift", "memory_reset"),
            },
            {
                "family": "breakdown_centered_rebirth",
                "macro_journey_profile": "breakdown_rebirth",
                "section_weight_profile": "breakdown_heavy",
                "drop_pair_profile": "drop1_tease_drop2_release",
                "final_lift_profile": "hook_reinforcement",
                "breakdown_bias": ("memory_reset", "tension_hold"),
            },
            {
                "family": "early_complete_anthem",
                "macro_journey_profile": "anthem_arc",
                "section_weight_profile": "balanced",
                "drop_pair_profile": "drop1_statement_drop2_upgrade",
                "final_lift_profile": "anthem_push",
                "breakdown_bias": ("harmonic_lift", "tension_hold"),
            },
        ],
        "anthemic_classic": [
            {
                "family": "early_complete_anthem",
                "macro_journey_profile": "anthem_arc",
                "section_weight_profile": "balanced",
                "drop_pair_profile": "drop1_statement_drop2_upgrade",
                "final_lift_profile": "anthem_push",
                "breakdown_bias": ("memory_reset", "harmonic_lift"),
            },
            {
                "family": "late_bloom_emotional",
                "macro_journey_profile": "anthem_arc",
                "section_weight_profile": "late_bloom",
                "drop_pair_profile": "drop1_full_drop2_wider",
                "final_lift_profile": "wide_release",
                "breakdown_bias": ("harmonic_lift", "tension_hold"),
            },
            {
                "family": "breakdown_centered_rebirth",
                "macro_journey_profile": "breakdown_rebirth",
                "section_weight_profile": "breakdown_heavy",
                "drop_pair_profile": "drop1_tease_drop2_release",
                "final_lift_profile": "hook_reinforcement",
                "breakdown_bias": ("memory_reset", "tension_hold"),
            },
        ],
        "vocal_melodic": [
            {
                "family": "vocal_journey_release",
                "macro_journey_profile": "vocal_journey",
                "section_weight_profile": "breakdown_heavy",
                "drop_pair_profile": "drop1_tease_drop2_release",
                "final_lift_profile": "hook_reinforcement",
                "breakdown_bias": ("vocal_exposure", "harmonic_lift"),
            },
            {
                "family": "late_bloom_emotional",
                "macro_journey_profile": "breakdown_rebirth",
                "section_weight_profile": "late_bloom",
                "drop_pair_profile": "drop1_tight_drop2_emotional",
                "final_lift_profile": "wide_release",
                "breakdown_bias": ("vocal_exposure", "harmonic_lift"),
            },
            {
                "family": "early_complete_anthem",
                "macro_journey_profile": "anthem_arc",
                "section_weight_profile": "balanced",
                "drop_pair_profile": "drop1_statement_drop2_upgrade",
                "final_lift_profile": "anthem_push",
                "breakdown_bias": ("harmonic_lift", "vocal_exposure"),
            },
        ],
        "festival_driver": [
            {
                "family": "early_complete_anthem",
                "macro_journey_profile": "drop_pressure",
                "section_weight_profile": "front_loaded",
                "drop_pair_profile": "drop1_full_drop2_wider",
                "final_lift_profile": "anthem_push",
                "breakdown_bias": ("tension_hold", "memory_reset"),
            },
            {
                "family": "anthemic_cycle",
                "macro_journey_profile": "anthem_arc",
                "section_weight_profile": "balanced",
                "drop_pair_profile": "drop1_statement_drop2_upgrade",
                "final_lift_profile": "anthem_push",
                "breakdown_bias": ("tension_hold", "harmonic_lift"),
            },
        ],
        "progressive_dream": [
            {
                "family": "late_bloom_emotional",
                "macro_journey_profile": "breakdown_rebirth",
                "section_weight_profile": "late_bloom",
                "drop_pair_profile": "drop1_tight_drop2_emotional",
                "final_lift_profile": "subtle_return",
                "breakdown_bias": ("harmonic_lift", "memory_reset"),
            },
            {
                "family": "vocal_journey_release",
                "macro_journey_profile": "vocal_journey",
                "section_weight_profile": "breakdown_heavy",
                "drop_pair_profile": "drop1_tease_drop2_release",
                "final_lift_profile": "wide_release",
                "breakdown_bias": ("harmonic_lift", "vocal_exposure"),
            },
        ],
    }
    candidates = [dict(item) for item in families[archetype]]
    signature_parts = [
        archetype,
        progression,
        blueprint["drum_style"],
        blueprint["bass_style"],
        blueprint["breakdown_style"],
        blueprint["lead_vocal_relationship"],
        blueprint["archetype_support_timing"],
        blueprint["archetype_harmony_emphasis"],
        blueprint["supersaw_identity"],
        energy_bias,
    ]
    signature = sum((idx + 1) * sum(ord(ch) for ch in value) for idx, value in enumerate(signature_parts))
    scores = []
    for idx, family in enumerate(candidates):
        score = 0
        if blueprint["drum_style"] in ("festival", "driving"):
            if family["section_weight_profile"] == "front_loaded":
                score += 5
            if family["final_lift_profile"] == "anthem_push":
                score += 3
        if blueprint["bass_style"] in ("rolling_drive", "syncopated"):
            if family["drop_pair_profile"] in ("drop1_full_drop2_wider", "drop1_statement_drop2_upgrade"):
                score += 4
        if blueprint["breakdown_style"] == "vocal_focus":
            if family["family"] == "vocal_journey_release":
                score += 6
        elif blueprint["breakdown_style"] == "pad_space":
            if family["family"] in ("late_bloom_emotional", "breakdown_centered_rebirth"):
                score += 3
        elif blueprint["breakdown_style"] == "piano_led":
            if family["family"] in ("late_bloom_emotional", "early_complete_anthem"):
                score += 2
        if blueprint["lead_vocal_relationship"] == "lead_carries_drop_vocal_carries_breakdown":
            if family["family"] == "vocal_journey_release":
                score += 5
        elif blueprint["lead_vocal_relationship"] == "shared_hook":
            if family["family"] == "early_complete_anthem":
                score += 3
        if blueprint["archetype_support_timing"] in ("late_bloom", "response_window"):
            if family["section_weight_profile"] in ("late_bloom", "breakdown_heavy"):
                score += 3
        elif blueprint["archetype_support_timing"] == "bed_first":
            if family["section_weight_profile"] in ("balanced", "front_loaded"):
                score += 3
        if blueprint["supersaw_identity"] in ("wall_stack", "pulse_stack"):
            if family["drop_pair_profile"] in ("drop1_full_drop2_wider", "drop1_statement_drop2_upgrade"):
                score += 3
        elif blueprint["supersaw_identity"] in ("bloom_stack", "octave_shine"):
            if family["drop_pair_profile"] == "drop1_tight_drop2_emotional":
                score += 2
        score += (signature + idx * 11) % 4
        scores.append((score, idx, family))
    scores.sort(key=lambda item: (-item[0], item[1]))
    family = dict(scores[signature % max(1, min(3, len(scores)))][2])
    family["family_signature"] = signature
    return family


def macro_journey_bundle(rng: random.Random, progression: str, archetype: str, blueprint, energy_bias: str):
    bundles = {
        "emotional_uplifter": [
            {
                "macro_journey_profile": "anthem_arc",
                "section_weight_profile": "balanced",
                "drop_pair_profile": "drop1_statement_drop2_upgrade",
                "breakdown_function": "harmonic_lift",
                "final_lift_profile": "wide_release",
            },
            {
                "macro_journey_profile": "breakdown_rebirth",
                "section_weight_profile": "late_bloom",
                "drop_pair_profile": "drop1_tight_drop2_emotional",
                "breakdown_function": "memory_reset",
                "final_lift_profile": "hook_reinforcement",
            },
            {
                "macro_journey_profile": "anthem_arc",
                "section_weight_profile": "late_bloom",
                "drop_pair_profile": "drop1_tight_drop2_emotional",
                "breakdown_function": "harmonic_lift",
                "final_lift_profile": "wide_release",
            },
            {
                "macro_journey_profile": "breakdown_rebirth",
                "section_weight_profile": "breakdown_heavy",
                "drop_pair_profile": "drop1_tease_drop2_release",
                "breakdown_function": "memory_reset",
                "final_lift_profile": "hook_reinforcement",
            },
        ],
        "festival_driver": [
            {
                "macro_journey_profile": "drop_pressure",
                "section_weight_profile": "front_loaded",
                "drop_pair_profile": "drop1_full_drop2_wider",
                "breakdown_function": "tension_hold",
                "final_lift_profile": "anthem_push",
            },
            {
                "macro_journey_profile": "anthem_arc",
                "section_weight_profile": "balanced",
                "drop_pair_profile": "drop1_statement_drop2_upgrade",
                "breakdown_function": "memory_reset",
                "final_lift_profile": "anthem_push",
            },
            {
                "macro_journey_profile": "drop_pressure",
                "section_weight_profile": "balanced",
                "drop_pair_profile": "drop1_statement_drop2_upgrade",
                "breakdown_function": "tension_hold",
                "final_lift_profile": "hook_reinforcement",
            },
            {
                "macro_journey_profile": "anthem_arc",
                "section_weight_profile": "late_bloom",
                "drop_pair_profile": "drop1_full_drop2_wider",
                "breakdown_function": "memory_reset",
                "final_lift_profile": "wide_release",
            },
        ],
        "vocal_melodic": [
            {
                "macro_journey_profile": "vocal_journey",
                "section_weight_profile": "breakdown_heavy",
                "drop_pair_profile": "drop1_tease_drop2_release",
                "breakdown_function": "vocal_exposure",
                "final_lift_profile": "hook_reinforcement",
            },
            {
                "macro_journey_profile": "breakdown_rebirth",
                "section_weight_profile": "late_bloom",
                "drop_pair_profile": "drop1_tight_drop2_emotional",
                "breakdown_function": "vocal_exposure",
                "final_lift_profile": "wide_release",
            },
            {
                "macro_journey_profile": "vocal_journey",
                "section_weight_profile": "late_bloom",
                "drop_pair_profile": "drop1_tight_drop2_emotional",
                "breakdown_function": "vocal_exposure",
                "final_lift_profile": "wide_release",
            },
            {
                "macro_journey_profile": "breakdown_rebirth",
                "section_weight_profile": "balanced",
                "drop_pair_profile": "drop1_tease_drop2_release",
                "breakdown_function": "memory_reset",
                "final_lift_profile": "hook_reinforcement",
            },
        ],
        "progressive_dream": [
            {
                "macro_journey_profile": "breakdown_rebirth",
                "section_weight_profile": "late_bloom",
                "drop_pair_profile": "drop1_tight_drop2_emotional",
                "breakdown_function": "harmonic_lift",
                "final_lift_profile": "subtle_return",
            },
            {
                "macro_journey_profile": "vocal_journey",
                "section_weight_profile": "breakdown_heavy",
                "drop_pair_profile": "drop1_tease_drop2_release",
                "breakdown_function": "memory_reset",
                "final_lift_profile": "wide_release",
            },
            {
                "macro_journey_profile": "breakdown_rebirth",
                "section_weight_profile": "balanced",
                "drop_pair_profile": "drop1_tight_drop2_emotional",
                "breakdown_function": "harmonic_lift",
                "final_lift_profile": "subtle_return",
            },
            {
                "macro_journey_profile": "vocal_journey",
                "section_weight_profile": "late_bloom",
                "drop_pair_profile": "drop1_tease_drop2_release",
                "breakdown_function": "harmonic_lift",
                "final_lift_profile": "wide_release",
            },
        ],
        "anthemic_classic": [
            {
                "macro_journey_profile": "anthem_arc",
                "section_weight_profile": "balanced",
                "drop_pair_profile": "drop1_statement_drop2_upgrade",
                "breakdown_function": "memory_reset",
                "final_lift_profile": "anthem_push",
            },
            {
                "macro_journey_profile": "drop_pressure",
                "section_weight_profile": "front_loaded",
                "drop_pair_profile": "drop1_full_drop2_wider",
                "breakdown_function": "harmonic_lift",
                "final_lift_profile": "hook_reinforcement",
            },
            {
                "macro_journey_profile": "anthem_arc",
                "section_weight_profile": "late_bloom",
                "drop_pair_profile": "drop1_tight_drop2_emotional",
                "breakdown_function": "memory_reset",
                "final_lift_profile": "wide_release",
            },
            {
                "macro_journey_profile": "drop_pressure",
                "section_weight_profile": "balanced",
                "drop_pair_profile": "drop1_statement_drop2_upgrade",
                "breakdown_function": "harmonic_lift",
                "final_lift_profile": "anthem_push",
            },
        ],
    }
    progression_preferences = {
        "uplifting": {"macro_journey_profile": {"anthem_arc", "breakdown_rebirth"}},
        "classic": {"macro_journey_profile": {"anthem_arc", "vocal_journey", "drop_pressure"}},
        "festival": {"macro_journey_profile": {"drop_pressure", "anthem_arc"}},
        "hopeful": {"macro_journey_profile": {"breakdown_rebirth", "vocal_journey"}},
        "progressive": {"macro_journey_profile": {"vocal_journey", "breakdown_rebirth", "anthem_arc"}},
    }
    candidates = [
        dict(bundle) for bundle in bundles[archetype]
        if bundle["macro_journey_profile"] in progression_preferences.get(progression, {}).get("macro_journey_profile", {bundle["macro_journey_profile"]})
    ]
    if not candidates:
        candidates = [dict(bundle) for bundle in bundles[archetype]]

    signature_parts = [
        blueprint["archetype_bass_grammar"],
        blueprint["archetype_drum_grammar"],
        blueprint["archetype_breakdown_focus"],
        blueprint["archetype_topline_density"],
        blueprint["archetype_support_timing"],
        blueprint["archetype_harmony_emphasis"],
        blueprint["archetype_supersaw_motion"],
        blueprint["archetype_drum_micro"],
        blueprint["lead_archetype"],
        blueprint["vocal_archetype"],
        blueprint["breakdown_style"],
        blueprint["drum_style"],
        blueprint["bass_style"],
        blueprint["energy_profile"],
        energy_bias,
    ]
    signature = sum((idx + 1) * sum(ord(ch) for ch in value) for idx, value in enumerate(signature_parts))
    all_progression_candidates = []
    for bundle_group in bundles.values():
        for bundle in bundle_group:
            if bundle["macro_journey_profile"] in progression_preferences.get(progression, {}).get("macro_journey_profile", {bundle["macro_journey_profile"]}):
                all_progression_candidates.append(dict(bundle))
    if not all_progression_candidates:
        all_progression_candidates = [dict(bundle) for bundle_group in bundles.values() for bundle in bundle_group]

    macro_preference_scores = {
        "macro_journey_profile": {},
        "section_weight_profile": {},
        "drop_pair_profile": {},
        "final_lift_profile": {},
    }

    def add_macro_score(category: str, value: str, score: int):
        macro_preference_scores[category][value] = macro_preference_scores[category].get(value, 0) + score

    if blueprint["archetype_support_timing"] in ("late_bloom", "response_window"):
        add_macro_score("macro_journey_profile", "breakdown_rebirth", 3)
        add_macro_score("section_weight_profile", "late_bloom", 4)
        add_macro_score("drop_pair_profile", "drop1_tight_drop2_emotional", 2)
        add_macro_score("drop_pair_profile", "drop1_tease_drop2_release", 2)
    elif blueprint["archetype_support_timing"] == "bed_first":
        add_macro_score("macro_journey_profile", "anthem_arc", 2)
        add_macro_score("section_weight_profile", "balanced", 2)
        add_macro_score("section_weight_profile", "front_loaded", 2)
        add_macro_score("drop_pair_profile", "drop1_statement_drop2_upgrade", 2)
    elif blueprint["archetype_support_timing"] == "staggered_frame":
        add_macro_score("macro_journey_profile", "drop_pressure", 2)
        add_macro_score("section_weight_profile", "balanced", 1)
        add_macro_score("section_weight_profile", "breakdown_heavy", 1)
        add_macro_score("drop_pair_profile", "drop1_tease_drop2_release", 2)

    if blueprint["archetype_breakdown_focus"] == "vocal_space":
        add_macro_score("macro_journey_profile", "vocal_journey", 4)
        add_macro_score("section_weight_profile", "breakdown_heavy", 3)
    elif blueprint["archetype_breakdown_focus"] == "pad_horizon":
        add_macro_score("macro_journey_profile", "breakdown_rebirth", 2)
        add_macro_score("section_weight_profile", "late_bloom", 2)
    elif blueprint["archetype_breakdown_focus"] == "piano_memory":
        add_macro_score("macro_journey_profile", "breakdown_rebirth", 2)
        add_macro_score("section_weight_profile", "balanced", 1)
        add_macro_score("final_lift_profile", "hook_reinforcement", 2)
    elif blueprint["archetype_breakdown_focus"] == "arp_glow":
        add_macro_score("macro_journey_profile", "drop_pressure", 2)
        add_macro_score("final_lift_profile", "anthem_push", 1)

    if blueprint["breakdown_style"] == "vocal_focus":
        add_macro_score("macro_journey_profile", "vocal_journey", 4)
        add_macro_score("section_weight_profile", "breakdown_heavy", 2)
        add_macro_score("drop_pair_profile", "drop1_tease_drop2_release", 2)
    elif blueprint["breakdown_style"] == "pad_space":
        add_macro_score("section_weight_profile", "late_bloom", 2)
        add_macro_score("section_weight_profile", "breakdown_heavy", 1)
        add_macro_score("drop_pair_profile", "drop1_tight_drop2_emotional", 1)
    elif blueprint["breakdown_style"] == "piano_led":
        add_macro_score("section_weight_profile", "balanced", 2)
        add_macro_score("drop_pair_profile", "drop1_tight_drop2_emotional", 2)
        add_macro_score("final_lift_profile", "wide_release", 1)
    elif blueprint["breakdown_style"] == "arp_texture":
        add_macro_score("macro_journey_profile", "drop_pressure", 2)
        add_macro_score("drop_pair_profile", "drop1_full_drop2_wider", 2)

    if blueprint["drum_style"] in ("festival", "driving"):
        add_macro_score("macro_journey_profile", "drop_pressure", 2)
        add_macro_score("section_weight_profile", "front_loaded", 2)
        add_macro_score("drop_pair_profile", "drop1_full_drop2_wider", 2)
        add_macro_score("final_lift_profile", "anthem_push", 2)
    elif blueprint["drum_style"] == "minimal":
        add_macro_score("macro_journey_profile", "vocal_journey", 2)
        add_macro_score("section_weight_profile", "breakdown_heavy", 2)
        add_macro_score("final_lift_profile", "subtle_return", 1)
        add_macro_score("final_lift_profile", "hook_reinforcement", 1)

    if blueprint["bass_style"] == "classic_offbeat":
        add_macro_score("section_weight_profile", "late_bloom", 1)
        add_macro_score("drop_pair_profile", "drop1_tight_drop2_emotional", 1)
    elif blueprint["bass_style"] == "rolling_drive":
        add_macro_score("section_weight_profile", "front_loaded", 1)
        add_macro_score("drop_pair_profile", "drop1_full_drop2_wider", 1)
    elif blueprint["bass_style"] == "hybrid":
        add_macro_score("section_weight_profile", "balanced", 2)
        add_macro_score("drop_pair_profile", "drop1_statement_drop2_upgrade", 1)
    elif blueprint["bass_style"] == "syncopated":
        add_macro_score("macro_journey_profile", "drop_pressure", 1)
        add_macro_score("final_lift_profile", "anthem_push", 1)

    if blueprint["lead_vocal_relationship"] == "lead_carries_drop_vocal_carries_breakdown":
        add_macro_score("macro_journey_profile", "vocal_journey", 3)
        add_macro_score("section_weight_profile", "breakdown_heavy", 2)
        add_macro_score("drop_pair_profile", "drop1_tease_drop2_release", 2)
    elif blueprint["lead_vocal_relationship"] == "shared_hook":
        add_macro_score("macro_journey_profile", "anthem_arc", 2)
        add_macro_score("section_weight_profile", "balanced", 2)
        add_macro_score("drop_pair_profile", "drop1_statement_drop2_upgrade", 2)
    elif blueprint["lead_vocal_relationship"] == "alternating_spotlight":
        add_macro_score("macro_journey_profile", "breakdown_rebirth", 2)
        add_macro_score("section_weight_profile", "late_bloom", 1)
        add_macro_score("final_lift_profile", "hook_reinforcement", 1)

    if blueprint["callback_density"] == "strong":
        add_macro_score("final_lift_profile", "hook_reinforcement", 2)
        add_macro_score("section_weight_profile", "breakdown_heavy", 1)
    elif blueprint["callback_density"] == "subtle":
        add_macro_score("final_lift_profile", "subtle_return", 2)
        add_macro_score("section_weight_profile", "balanced", 1)

    if blueprint["supersaw_identity"] in ("wall_stack", "pulse_stack"):
        add_macro_score("final_lift_profile", "anthem_push", 1)
        add_macro_score("drop_pair_profile", "drop1_full_drop2_wider", 1)
    elif blueprint["supersaw_identity"] in ("bloom_stack", "octave_shine"):
        add_macro_score("final_lift_profile", "wide_release", 2)
        add_macro_score("drop_pair_profile", "drop1_tight_drop2_emotional", 1)

    lane_penalty = {
        ("macro_journey_profile", "breakdown_rebirth"): 2,
        ("section_weight_profile", "late_bloom"): 2,
        ("drop_pair_profile", "drop1_tight_drop2_emotional"): 1,
        ("final_lift_profile", "hook_reinforcement"): 1,
    }
    lane_bonus = {
        ("macro_journey_profile", "anthem_arc"): 0,
        ("macro_journey_profile", "drop_pressure"): 3,
        ("macro_journey_profile", "vocal_journey"): 2,
        ("section_weight_profile", "front_loaded"): 4,
        ("section_weight_profile", "breakdown_heavy"): 3,
        ("drop_pair_profile", "drop1_full_drop2_wider"): 3,
        ("drop_pair_profile", "drop1_statement_drop2_upgrade"): 2,
        ("final_lift_profile", "anthem_push"): 3,
        ("final_lift_profile", "subtle_return"): 2,
    }

    if blueprint["drum_style"] in ("festival", "driving") or blueprint["bass_style"] in ("rolling_drive", "syncopated"):
        lane_bonus[("macro_journey_profile", "drop_pressure")] += 1
        lane_bonus[("section_weight_profile", "front_loaded")] += 1
        lane_bonus[("drop_pair_profile", "drop1_full_drop2_wider")] += 1
        lane_bonus[("final_lift_profile", "anthem_push")] += 1
    if blueprint["breakdown_style"] in ("vocal_focus", "pad_space") or blueprint["archetype_breakdown_focus"] in ("vocal_space", "pad_horizon"):
        lane_bonus[("section_weight_profile", "breakdown_heavy")] += 1
    if blueprint["callback_density"] == "subtle":
        lane_bonus[("final_lift_profile", "subtle_return")] += 1
    if blueprint["lead_vocal_relationship"] == "shared_hook":
        lane_bonus[("drop_pair_profile", "drop1_statement_drop2_upgrade")] += 1

    if blueprint["drum_style"] in ("festival", "driving"):
        lane_bonus[("macro_journey_profile", "anthem_arc")] += 1
        lane_bonus[("section_weight_profile", "front_loaded")] += 3
        lane_bonus[("drop_pair_profile", "drop1_full_drop2_wider")] += 2
        lane_bonus[("drop_pair_profile", "drop1_statement_drop2_upgrade")] += 2
        lane_bonus[("final_lift_profile", "anthem_push")] += 3
    if blueprint["bass_style"] in ("rolling_drive", "syncopated"):
        lane_bonus[("section_weight_profile", "front_loaded")] += 2
        lane_bonus[("drop_pair_profile", "drop1_full_drop2_wider")] += 2
        lane_bonus[("final_lift_profile", "anthem_push")] += 2
    if blueprint["drop_arrival_style"] in ("slam", "hook_first"):
        lane_bonus[("macro_journey_profile", "anthem_arc")] += 2
        lane_bonus[("section_weight_profile", "front_loaded")] += 2
        lane_bonus[("drop_pair_profile", "drop1_statement_drop2_upgrade")] += 2
        lane_bonus[("drop_pair_profile", "drop1_full_drop2_wider")] += 2
        lane_bonus[("final_lift_profile", "anthem_push")] += 2
    if blueprint["supersaw_identity"] in ("wall_stack", "pulse_stack"):
        lane_bonus[("section_weight_profile", "front_loaded")] += 1
        lane_bonus[("drop_pair_profile", "drop1_full_drop2_wider")] += 2
        lane_bonus[("drop_pair_profile", "drop1_statement_drop2_upgrade")] += 1
        lane_bonus[("final_lift_profile", "anthem_push")] += 2
    if blueprint["archetype_drum_grammar"] in ("festival_lift", "push_hat"):
        lane_bonus[("section_weight_profile", "front_loaded")] += 1
        lane_bonus[("final_lift_profile", "anthem_push")] += 1
    if blueprint["archetype_supersaw_motion"] in ("full_hold", "pulse_answer"):
        lane_bonus[("drop_pair_profile", "drop1_full_drop2_wider")] += 1
        lane_bonus[("drop_pair_profile", "drop1_statement_drop2_upgrade")] += 1

    if (
        blueprint["drum_style"] in ("festival", "driving")
        and blueprint["bass_style"] in ("rolling_drive", "syncopated")
        and blueprint["drop_arrival_style"] in ("slam", "hook_first")
    ):
        lane_bonus[("macro_journey_profile", "anthem_arc")] += 2
        lane_bonus[("section_weight_profile", "front_loaded")] += 4
        lane_bonus[("drop_pair_profile", "drop1_full_drop2_wider")] += 3
        lane_bonus[("drop_pair_profile", "drop1_statement_drop2_upgrade")] += 2
        lane_bonus[("final_lift_profile", "anthem_push")] += 4

    if (
        blueprint["drum_style"] == "driving"
        and blueprint["bass_style"] == "rolling_drive"
        and blueprint["supersaw_identity"] in ("wall_stack", "pulse_stack")
        and blueprint["drop_arrival_style"] in ("hook_first", "slam", "glide_in")
    ):
        lane_bonus[("macro_journey_profile", "anthem_arc")] += 3
        lane_bonus[("section_weight_profile", "front_loaded")] += 6
        lane_bonus[("drop_pair_profile", "drop1_full_drop2_wider")] += 5
        lane_bonus[("drop_pair_profile", "drop1_statement_drop2_upgrade")] += 2
        lane_bonus[("final_lift_profile", "anthem_push")] += 3

    if (
        blueprint["archetype_drum_grammar"] in ("push_hat", "festival_lift")
        and blueprint["archetype_bass_grammar"] in ("motion", "push")
        and blueprint["archetype_supersaw_motion"] in ("full_hold", "pulse_answer")
    ):
        lane_bonus[("section_weight_profile", "front_loaded")] += 3
        lane_bonus[("drop_pair_profile", "drop1_full_drop2_wider")] += 3

    if blueprint["track_archetype"] in ("festival_driver", "anthemic_classic"):
        lane_bonus[("section_weight_profile", "front_loaded")] += 1
        lane_bonus[("drop_pair_profile", "drop1_full_drop2_wider")] += 1

    if (
        blueprint["drum_style"] == "driving"
        and blueprint["drop_arrival_style"] == "hook_first"
        and blueprint["callback_density"] != "subtle"
    ):
        lane_bonus[("section_weight_profile", "front_loaded")] += 2
        lane_bonus[("drop_pair_profile", "drop1_full_drop2_wider")] += 2
        lane_bonus[("final_lift_profile", "anthem_push")] += 1


    scored_candidates = []
    for idx, candidate in enumerate(all_progression_candidates):
        score = 0
        score += macro_preference_scores["macro_journey_profile"].get(candidate["macro_journey_profile"], 0)
        score += macro_preference_scores["section_weight_profile"].get(candidate["section_weight_profile"], 0)
        score += macro_preference_scores["drop_pair_profile"].get(candidate["drop_pair_profile"], 0)
        score += macro_preference_scores["final_lift_profile"].get(candidate["final_lift_profile"], 0)
        score += lane_bonus.get(("macro_journey_profile", candidate["macro_journey_profile"]), 0)
        score += lane_bonus.get(("section_weight_profile", candidate["section_weight_profile"]), 0)
        score += lane_bonus.get(("drop_pair_profile", candidate["drop_pair_profile"]), 0)
        score += lane_bonus.get(("final_lift_profile", candidate["final_lift_profile"]), 0)
        score -= lane_penalty.get(("macro_journey_profile", candidate["macro_journey_profile"]), 0)
        score -= lane_penalty.get(("section_weight_profile", candidate["section_weight_profile"]), 0)
        score -= lane_penalty.get(("drop_pair_profile", candidate["drop_pair_profile"]), 0)
        score -= lane_penalty.get(("final_lift_profile", candidate["final_lift_profile"]), 0)
        if candidate in candidates:
            score += 2
        diversity_bonus = len({
            candidate["macro_journey_profile"],
            candidate["section_weight_profile"],
            candidate["drop_pair_profile"],
            candidate["final_lift_profile"],
        })
        score += diversity_bonus
        score += ((signature + idx * 17) % 5)
        scored_candidates.append((score, idx, candidate))

    scored_candidates.sort(key=lambda item: (-item[0], item[1]))
    top_slice = scored_candidates[:max(4, min(8, len(scored_candidates)))]
    bundle = dict(top_slice[signature % len(top_slice)][2])

    strongly_vocal_led = (
        blueprint["breakdown_style"] == "vocal_focus"
        or blueprint["archetype_breakdown_focus"] == "vocal_space"
        or blueprint["vocal_archetype"] == "held_emotive"
        or blueprint["lead_vocal_relationship"] == "lead_carries_drop_vocal_carries_breakdown"
        or blueprint["breakdown_narrative"] == "vocal_spotlight"
    )
    semi_vocal_led = (
        blueprint["vocal_archetype"] in ("call_response", "held_emotive")
        or blueprint["archetype_topline_density"] == "vocal_heavy"
        or blueprint["lead_vocal_relationship"] in ("lead_answers_vocal", "vocal_answers_lead")
    )

    breakdown_scores = {
        "memory_reset": 0,
        "harmonic_lift": 0,
        "tension_hold": 0,
        "vocal_exposure": 0,
    }
    breakdown_scores[bundle["breakdown_function"]] += 3

    if strongly_vocal_led:
        breakdown_scores["vocal_exposure"] += 6
    elif semi_vocal_led:
        breakdown_scores["vocal_exposure"] += 1

    if blueprint["breakdown_style"] == "vocal_focus":
        breakdown_scores["vocal_exposure"] += 3
    elif blueprint["breakdown_style"] == "piano_led":
        breakdown_scores["harmonic_lift"] += 3
    elif blueprint["breakdown_style"] == "pad_space":
        breakdown_scores["tension_hold"] += 3
    elif blueprint["breakdown_style"] == "arp_texture":
        breakdown_scores["tension_hold"] += 1
        breakdown_scores["harmonic_lift"] += 1

    if blueprint["archetype_breakdown_focus"] == "vocal_space":
        breakdown_scores["vocal_exposure"] += 3
    elif blueprint["archetype_breakdown_focus"] == "piano_memory":
        breakdown_scores["memory_reset"] += 1
        breakdown_scores["harmonic_lift"] += 3
    elif blueprint["archetype_breakdown_focus"] == "pad_horizon":
        breakdown_scores["tension_hold"] += 4
    elif blueprint["archetype_breakdown_focus"] == "arp_glow":
        breakdown_scores["tension_hold"] += 2

    if blueprint["breakdown_narrative"] == "memory_recall":
        breakdown_scores["memory_reset"] += 3
    elif blueprint["breakdown_narrative"] in ("space_then_lift", "piano_confession"):
        breakdown_scores["harmonic_lift"] += 3
    elif blueprint["breakdown_narrative"] == "vocal_spotlight":
        breakdown_scores["vocal_exposure"] += 3

    if blueprint["archetype_harmony_emphasis"] in ("piano_answer", "string_lift"):
        breakdown_scores["harmonic_lift"] += 3
    if blueprint["archetype_support_timing"] in ("late_bloom", "response_window"):
        breakdown_scores["tension_hold"] += 3
    if blueprint["drum_style"] == "minimal":
        breakdown_scores["tension_hold"] += 1
    if blueprint["hook_recall_style"] in ("direct_echo", "interval_memory"):
        breakdown_scores["memory_reset"] += 1
    if blueprint["callback_density"] == "strong":
        breakdown_scores["memory_reset"] += 1
    elif blueprint["callback_density"] == "subtle":
        breakdown_scores["tension_hold"] += 1
        breakdown_scores["harmonic_lift"] += 1

    if blueprint["breakdown_style"] == "pad_space" and not strongly_vocal_led:
        breakdown_scores["tension_hold"] += 2
    if blueprint["archetype_breakdown_focus"] == "pad_horizon" and blueprint["breakdown_narrative"] != "memory_recall":
        breakdown_scores["tension_hold"] += 1
    if blueprint["breakdown_style"] == "piano_led" and blueprint["breakdown_narrative"] in ("space_then_lift", "piano_confession"):
        breakdown_scores["harmonic_lift"] += 2
    if blueprint["archetype_harmony_emphasis"] == "pad_anchor" and blueprint["archetype_support_timing"] in ("late_bloom", "response_window"):
        breakdown_scores["tension_hold"] += 1

    if (
        blueprint["breakdown_style"] == "pad_space"
        and blueprint["archetype_breakdown_focus"] == "pad_horizon"
    ):
        breakdown_scores["tension_hold"] += 3
    if (
        blueprint["archetype_support_timing"] in ("late_bloom", "response_window")
        and blueprint["archetype_breakdown_focus"] == "pad_horizon"
    ):
        breakdown_scores["tension_hold"] += 2
    if (
        blueprint["breakdown_style"] == "pad_space"
        and blueprint["archetype_support_timing"] in ("late_bloom", "response_window")
    ):
        breakdown_scores["tension_hold"] += 2

    if blueprint["breakdown_narrative"] == "memory_recall":
        breakdown_scores["harmonic_lift"] -= 1
    if (
        blueprint["breakdown_narrative"] == "memory_recall"
        and blueprint["hook_recall_style"] in ("direct_echo", "interval_memory")
    ):
        breakdown_scores["memory_reset"] += 3
    if (
        blueprint["breakdown_narrative"] == "memory_recall"
        and blueprint["callback_density"] in ("balanced", "strong")
    ):
        breakdown_scores["memory_reset"] += 1
    if (
        blueprint["archetype_breakdown_focus"] == "piano_memory"
        and blueprint["breakdown_narrative"] == "memory_recall"
    ):
        breakdown_scores["memory_reset"] += 2
    if (
        blueprint["archetype_breakdown_focus"] == "piano_memory"
        and blueprint["archetype_support_timing"] in ("late_bloom", "response_window")
        and blueprint["breakdown_style"] == "pad_space"
    ):
        breakdown_scores["tension_hold"] += 2
        breakdown_scores["harmonic_lift"] -= 1
    if (
        blueprint["archetype_breakdown_focus"] == "piano_memory"
        and blueprint["breakdown_narrative"] == "space_then_lift"
        and blueprint["archetype_support_timing"] == "bed_first"
    ):
        breakdown_scores["harmonic_lift"] += 1

    if strongly_vocal_led:
        breakdown_scores["memory_reset"] -= 1
        breakdown_scores["harmonic_lift"] -= 1
        breakdown_scores["tension_hold"] -= 1
    elif semi_vocal_led and blueprint["breakdown_style"] != "vocal_focus":
        breakdown_scores["vocal_exposure"] -= 2

    if (
        bundle["breakdown_function"] == "vocal_exposure"
        and not strongly_vocal_led
        and blueprint["archetype_breakdown_focus"] != "vocal_space"
        and blueprint["breakdown_style"] != "vocal_focus"
    ):
        breakdown_scores["vocal_exposure"] -= 2

    if (
        blueprint["lead_vocal_relationship"] == "lead_carries_drop_vocal_carries_breakdown"
        and blueprint["vocal_archetype"] not in ("held_emotive", "call_response")
        and blueprint["archetype_breakdown_focus"] != "vocal_space"
    ):
        breakdown_scores["vocal_exposure"] -= 2

    non_vocal_peak = max(breakdown_scores["memory_reset"], breakdown_scores["harmonic_lift"], breakdown_scores["tension_hold"])
    if not strongly_vocal_led and breakdown_scores["vocal_exposure"] <= non_vocal_peak:
        breakdown_scores["vocal_exposure"] -= 2
    elif not strongly_vocal_led and breakdown_scores["vocal_exposure"] == non_vocal_peak + 1:
        breakdown_scores["vocal_exposure"] -= 1

    best_score = max(breakdown_scores.values())
    top_families = sorted(name for name, score in breakdown_scores.items() if score == best_score)
    bundle["breakdown_function"] = top_families[signature % len(top_families)]

    if blueprint["drum_style"] == "festival" and bundle["macro_journey_profile"] == "vocal_journey":
        bundle["macro_journey_profile"] = "drop_pressure"
    elif blueprint["drum_style"] == "minimal" and bundle["macro_journey_profile"] == "drop_pressure":
        bundle["macro_journey_profile"] = "breakdown_rebirth"

    if blueprint["archetype_support_timing"] == "late_bloom" and bundle["section_weight_profile"] == "front_loaded":
        bundle["section_weight_profile"] = "late_bloom"
    elif blueprint["archetype_support_timing"] == "response_window" and bundle["section_weight_profile"] == "front_loaded":
        bundle["section_weight_profile"] = "breakdown_heavy"

    if blueprint["lead_vocal_relationship"] == "lead_carries_drop_vocal_carries_breakdown":
        bundle["drop_pair_profile"] = "drop1_tease_drop2_release"
    elif blueprint["lead_archetype"] == "driving" and blueprint["drum_style"] in ("festival", "driving"):
        bundle["drop_pair_profile"] = "drop1_full_drop2_wider"

    if blueprint["hook_recall_style"] in ("direct_echo", "interval_memory"):
        bundle["final_lift_profile"] = "hook_reinforcement" if bundle["final_lift_profile"] == "subtle_return" else bundle["final_lift_profile"]
    elif blueprint["callback_density"] == "subtle" and bundle["final_lift_profile"] == "anthem_push":
        bundle["final_lift_profile"] = "subtle_return"

    return bundle


def build_song_blueprint(rng: random.Random, progression: str, variation: str, density: str, energy_bias: str, identity_profile=None):
    profile = progression_identity(progression)
    archetype = choose_weighted(rng, track_archetype_identity(progression), energy_bias)
    chord_options = {
        "uplifting": ["wide_trance", "rhythmic", "block", "syncopated"],
        "classic": ["block", "wide_trance", "rhythmic"],
        "festival": ["rhythmic", "syncopated", "wide_trance"],
        "hopeful": ["broken_chord", "syncopated", "block"],
        "progressive": ["broken_chord", "block", "syncopated"],
    }[progression]
    arp_options = {
        "uplifting": ["uplift_drive", "rolling_16th", "triplet"],
        "classic": ["rolling_16th", "gated_8th", "uplift_drive"],
        "festival": ["triplet", "uplift_drive", "rolling_16th"],
        "hopeful": ["triplet", "gated_8th", "uplift_drive"],
        "progressive": ["gated_8th", "triplet", "uplift_drive"],
    }[progression]
    bass_options = {
        "uplifting": ["classic_offbeat", "rolling_drive", "hybrid"],
        "classic": ["classic_offbeat", "hybrid", "rolling_drive"],
        "festival": ["rolling_drive", "syncopated", "hybrid"],
        "hopeful": ["classic_offbeat", "syncopated", "hybrid"],
        "progressive": ["classic_offbeat", "hybrid", "syncopated"],
    }[progression]
    drum_options = {
        "uplifting": ["driving", "standard", "festival"],
        "classic": ["standard", "minimal", "driving"],
        "festival": ["festival", "driving", "standard"],
        "hopeful": ["minimal", "standard", "driving"],
        "progressive": ["minimal", "standard", "driving"],
    }[progression]
    breakdown_options = {
        "uplifting": ["pad_space", "arp_texture", "piano_led"],
        "classic": ["piano_led", "pad_space", "vocal_focus"],
        "festival": ["arp_texture", "pad_space", "vocal_focus"],
        "hopeful": ["piano_led", "vocal_focus", "pad_space"],
        "progressive": ["pad_space", "piano_led", "vocal_focus"],
    }[progression]
    blueprint = {
        "track_archetype": archetype,
        "archetype_bass_grammar": rng.choice(["anchor", "motion", "breath", "push"]),
        "archetype_drum_grammar": rng.choice(["minimal_frame", "steady_drive", "push_hat", "festival_lift"]),
        "archetype_breakdown_focus": rng.choice(["pad_horizon", "piano_memory", "vocal_space", "arp_glow"]),
        "archetype_topline_density": rng.choice(["lead_heavy", "balanced", "vocal_heavy", "alternating"]),
        "archetype_support_timing": rng.choice(["bed_first", "late_bloom", "response_window", "staggered_frame"]),
        "archetype_harmony_emphasis": rng.choice(["pad_anchor", "piano_answer", "string_lift", "split_layers"]),
        "archetype_counter_grammar": rng.choice(["tail_echo", "mid_answer", "lift_shadow", "transition_spark"]),
        "archetype_supersaw_motion": rng.choice(["full_hold", "pulse_answer", "late_bloom", "split_pulse"]),
        "archetype_drum_micro": rng.choice(["straight_caps", "busy_caps", "late_caps"]),
        "archetype_counter_contour": rng.choice(["flat_reply", "rising_reply", "echo_fall", "spark_jump"]),
        "archetype_arp_grammar": rng.choice(["stream", "breath", "answer", "lift_rush"]),
        "archetype_pluck_grammar": rng.choice(["foreshadow", "pulse", "lift_chain", "drop_gap"]),
        "archetype_counter_presence": rng.choice(["whisper", "clear", "featured", "late_focus"]),
        "archetype_counter_span": rng.choice(["short", "medium", "long", "extended"]),
        "archetype_counter_register": rng.choice(["low_lane", "mid_lane", "high_lane", "wide_lane"]),
        "archetype_counter_role": rng.choice(["support", "late_answer", "featured_answer", "transition_push"]),
        "chord_style": choose_weighted(rng, chord_options, energy_bias),
        "arp_style": choose_weighted(rng, arp_options, energy_bias),
        "bass_style": choose_weighted(rng, bass_options, energy_bias),
        "drum_style": choose_weighted(rng, drum_options, energy_bias),
        "breakdown_style": choose_weighted(rng, breakdown_options, energy_bias),
        "supersaw_identity": rng.choice(["wall_stack", "pulse_stack", "bloom_stack", "octave_shine"]),
        "supersaw_pulse_variant": rng.choice(["straight", "push", "late", "skip"]),
        "supersaw_bloom_variant": rng.choice(["early", "standard", "late", "double"]),
        "supersaw_inversion_variant": rng.choice(["rooted", "wide_top", "fifth_heavy", "mid_open"]),
        "supersaw_response_variant": rng.choice(["full", "tail", "answer", "echo"]),
        "energy_profile": choose_weighted(rng, ["gradual_rise", "early_energy", "late_peak", "double_peak"], energy_bias),
        "lead_archetype": rng.choice(["anthemic", "yearning", "driving", "uplift_hook"]),
        "vocal_archetype": rng.choice(["straight_hook", "call_response", "held_emotive", "stepwise_lift"]),
        "lead_vocal_relationship": rng.choice([
            "lead_answers_vocal",
            "vocal_answers_lead",
            "shared_hook",
            "alternating_spotlight",
            "lead_carries_drop_vocal_carries_breakdown",
        ]),
        "countermelody_style": rng.choice(["late_answer", "constant_support", "drop_tail", "octave_echo"]),
        "bass_motion_profile": rng.choice(["low_anchor", "octave_push", "fifth_drive", "syncopated_lift"]),
        "drop_arrival_style": rng.choice(["slam", "glide_in", "staggered", "hook_first"]),
        "breakdown_narrative": rng.choice(["memory_recall", "space_then_lift", "piano_confession", "vocal_spotlight"]),
        "hook_recall_style": rng.choice(["direct_echo", "interval_memory", "rhythmic_shadow", "emotive_fragment"]),
        "hook_candidate_count": rng.randint(4, 6),
        "theme_anchor_degree": rng.choice([1, 3, 5]),
        "callback_density": choose_weighted(rng, ["subtle", "balanced", "strong"], energy_bias),
        "transition_intent": rng.choice(["tension_riser", "drum_pullback", "harmonic_bloom", "pre_drop_void", "snare_lift"]),
        "arrangement_density_profile": rng.choice(["continuous", "staggered", "breathing", "spotlight"]),
        "groove_variation_profile": rng.choice(["steady", "syncopated", "breathing", "push_pull"]),
        "opening_scene": rng.choice(["pad_seed", "drum_tease", "bass_tease", "hook_tease"]),
        "lead_evolution_profile": rng.choice(["resolved", "climbing", "answering", "wide_payoff"]),
        "countermelody_engine": rng.choice(["answer_arc", "shadow_hook", "octave_lift", "late_bloom"]),
        "drop_layer_budget": rng.choice([4, 5, 6]),
        "variant_lead_gain": rng.choice([0.92, 0.98, 1.0, 1.04, 1.08]),
        "variant_strings_gain": rng.choice([0.9, 0.96, 1.0, 1.04, 1.08]),
        "variant_saw_gain": rng.choice([0.94, 0.98, 1.0, 1.04, 1.08]),
        "variant_arp_gain": rng.choice([0.88, 0.94, 1.0, 1.06, 1.12]),
        "variant_kick_gain": rng.choice([0.94, 0.98, 1.0, 1.04, 1.08]),
        "variant_hat_gain": rng.choice([0.84, 0.92, 1.0, 1.08, 1.16]),
        "variant_clap_gain": rng.choice([0.88, 0.94, 1.0, 1.06, 1.12]),
        "variant_bass_gain": rng.choice([0.9, 0.96, 1.0, 1.04, 1.1]),
        "variant_drop_density": rng.choice([0.88, 0.94, 1.0, 1.06]),
        "variant_drop_tail_bias": rng.choice(["shorter", "balanced", "longer"]),
        "variant_clap_pattern": rng.choice(["backbeat", "late_push", "split_tail", "sparse_answer"]),
        "variant_hat_grid": rng.choice(["steady_8th", "air_16th", "late_8th", "tight_16th"]),
        "variant_kick_phrase": rng.choice(["flat", "front_push", "back_push", "pump"]),
        "variant_verse_drum_entry": rng.choice(["kick_only", "hat_tease", "clap_late", "rolling_open"]),
        "variant_string_entry": rng.choice(["early", "mid", "late", "echo"]),
        "variant_supersaw_ceiling": rng.choice(["restrained", "balanced", "wide"]),
        "variant_arp_restraint": rng.choice(["free", "balanced", "guarded"]),
        "variant_support_spread": rng.choice(["narrow", "balanced", "wide"]),
        "variant_counter_spread": rng.choice(["tight", "balanced", "open"]),
        **profile,
        "variation": variation,
        "density": density,
    }
    blueprint["theme_anchor_degree"] = profile["theme_degree"]
    if blueprint["breakdown_style"] == "piano_led":
        blueprint["breakdown_narrative"] = choose_weighted(rng, ["piano_confession", "memory_recall"], energy_bias)
    elif blueprint["breakdown_style"] == "vocal_focus":
        blueprint["breakdown_narrative"] = choose_weighted(rng, ["vocal_spotlight", "space_then_lift"], energy_bias)
        blueprint["vocal_archetype"] = choose_weighted(rng, ["held_emotive", "call_response"], energy_bias)
    elif blueprint["breakdown_style"] == "arp_texture":
        blueprint["breakdown_narrative"] = choose_weighted(rng, ["space_then_lift", "memory_recall"], energy_bias)

    if blueprint["drum_style"] == "festival":
        blueprint["drop_arrival_style"] = choose_weighted(rng, ["slam", "hook_first"], energy_bias)
    elif blueprint["drum_style"] == "minimal":
        blueprint["drop_arrival_style"] = choose_weighted(rng, ["glide_in", "staggered"], energy_bias)

    if progression == "progressive":
        blueprint["drum_style"] = choose_weighted(rng, ["minimal", "standard"], energy_bias)
        blueprint["bass_style"] = choose_weighted(rng, ["classic_offbeat", "hybrid"], energy_bias)
        blueprint["breakdown_style"] = choose_weighted(rng, ["pad_space", "piano_led"], energy_bias)
        blueprint["drop_arrival_style"] = choose_weighted(rng, ["glide_in", "staggered"], energy_bias)
        blueprint["lead_archetype"] = choose_weighted(rng, ["yearning", "anthemic"], energy_bias)
        blueprint["vocal_archetype"] = choose_weighted(rng, ["held_emotive", "call_response"], energy_bias)
        blueprint["lead_vocal_relationship"] = choose_weighted(rng, ["alternating_spotlight", "vocal_answers_lead"], energy_bias)
        blueprint["archetype_support_timing"] = choose_weighted(rng, ["late_bloom", "response_window", "staggered_frame"], energy_bias)
        blueprint["archetype_harmony_emphasis"] = choose_weighted(rng, ["piano_answer", "pad_anchor", "split_layers"], energy_bias)
        blueprint["variant_hat_grid"] = choose_weighted(rng, ["late_8th", "steady_8th"], energy_bias)
        blueprint["variant_clap_pattern"] = choose_weighted(rng, ["sparse_answer", "late_push"], energy_bias)
        blueprint["variant_kick_phrase"] = choose_weighted(rng, ["flat", "pump"], energy_bias)
        blueprint["variant_verse_drum_entry"] = choose_weighted(rng, ["kick_only", "clap_late"], energy_bias)

    if blueprint["lead_archetype"] == "anthemic":
        blueprint["countermelody_style"] = choose_weighted(rng, ["late_answer", "octave_echo"], energy_bias)
    elif blueprint["lead_archetype"] == "driving":
        blueprint["countermelody_style"] = choose_weighted(rng, ["constant_support", "drop_tail"], energy_bias)
    if blueprint["lead_archetype"] == "driving" and blueprint["vocal_archetype"] == "call_response":
        blueprint["lead_vocal_relationship"] = choose_weighted(rng, ["lead_answers_vocal", "vocal_answers_lead"], energy_bias)
    elif blueprint["lead_archetype"] == "uplift_hook" and blueprint["vocal_archetype"] in ("straight_hook", "stepwise_lift"):
        blueprint["lead_vocal_relationship"] = choose_weighted(rng, ["shared_hook", "alternating_spotlight"], energy_bias)
    elif blueprint["breakdown_style"] in ("vocal_focus", "piano_led"):
        blueprint["lead_vocal_relationship"] = choose_weighted(rng, ["lead_carries_drop_vocal_carries_breakdown", "lead_answers_vocal"], energy_bias)

    if blueprint["bass_style"] == "classic_offbeat":
        blueprint["bass_motion_profile"] = choose_weighted(rng, ["low_anchor", "syncopated_lift"], energy_bias)
    elif blueprint["bass_style"] == "rolling_drive":
        blueprint["bass_motion_profile"] = choose_weighted(rng, ["octave_push", "fifth_drive"], energy_bias)
    if blueprint["hook_recall_style"] == "emotive_fragment":
        blueprint["callback_density"] = choose_weighted(rng, ["balanced", "strong"], energy_bias)
    if blueprint["breakdown_narrative"] == "memory_recall":
        blueprint["hook_recall_style"] = choose_weighted(rng, ["direct_echo", "interval_memory", "emotive_fragment"], energy_bias)
    if blueprint["drum_style"] == "festival":
        blueprint["transition_intent"] = choose_weighted(rng, ["tension_riser", "snare_lift", "pre_drop_void"], energy_bias)
    elif blueprint["drum_style"] == "minimal":
        blueprint["transition_intent"] = choose_weighted(rng, ["drum_pullback", "harmonic_bloom", "pre_drop_void"], energy_bias)
    if progression == "festival":
        blueprint["drop_arrival_style"] = choose_weighted(rng, ["slam", "hook_first", "staggered"], energy_bias)
        blueprint["breakdown_style"] = choose_weighted(rng, ["arp_texture", "pad_space"], energy_bias)
        blueprint["supersaw_identity"] = choose_weighted(rng, ["wall_stack", "pulse_stack"], energy_bias)
        blueprint["supersaw_pulse_variant"] = choose_weighted(rng, ["straight", "push"], energy_bias)
        blueprint["supersaw_response_variant"] = choose_weighted(rng, ["full", "tail"], energy_bias)
    elif progression == "hopeful":
        blueprint["drop_arrival_style"] = choose_weighted(rng, ["glide_in", "staggered"], energy_bias)
        blueprint["transition_intent"] = choose_weighted(rng, ["harmonic_bloom", "pre_drop_void"], energy_bias)
        blueprint["supersaw_identity"] = choose_weighted(rng, ["bloom_stack", "octave_shine"], energy_bias)
        blueprint["supersaw_bloom_variant"] = choose_weighted(rng, ["late", "double"], energy_bias)
        blueprint["supersaw_response_variant"] = choose_weighted(rng, ["echo", "answer"], energy_bias)
    elif progression == "classic":
        blueprint["breakdown_style"] = choose_weighted(rng, ["piano_led", "pad_space"], energy_bias)
        blueprint["bass_style"] = choose_weighted(rng, ["classic_offbeat", "hybrid"], energy_bias)
        blueprint["supersaw_identity"] = choose_weighted(rng, ["pulse_stack", "bloom_stack"], energy_bias)
        blueprint["supersaw_inversion_variant"] = choose_weighted(rng, ["mid_open", "rooted"], energy_bias)
    elif progression == "uplifting":
        blueprint["chord_style"] = choose_weighted(rng, ["wide_trance", "rhythmic", "block"], energy_bias)
        blueprint["drop_arrival_style"] = choose_weighted(rng, ["glide_in", "hook_first", "slam"], energy_bias)
        blueprint["supersaw_identity"] = choose_weighted(rng, ["octave_shine", "wall_stack"], energy_bias)
        blueprint["supersaw_inversion_variant"] = choose_weighted(rng, ["wide_top", "fifth_heavy"], energy_bias)
        blueprint["arrangement_density_profile"] = choose_weighted(rng, ["staggered", "breathing", "spotlight"], energy_bias)
        blueprint["groove_variation_profile"] = choose_weighted(rng, ["syncopated", "breathing", "push_pull"], energy_bias)
        blueprint["opening_scene"] = choose_weighted(rng, ["pad_seed", "drum_tease", "bass_tease", "hook_tease"], energy_bias)
        blueprint["lead_evolution_profile"] = choose_weighted(rng, ["resolved", "climbing", "wide_payoff"], energy_bias)
        blueprint["countermelody_engine"] = choose_weighted(rng, ["answer_arc", "octave_lift", "late_bloom"], energy_bias)
        blueprint["drop_layer_budget"] = choose_weighted(rng, [4, 5], energy_bias)
        if blueprint.get("drop_pair_profile") == "drop1_tease_drop2_release":
            if archetype == "emotional_uplifter" and rng.random() < 0.35:
                blueprint["drop_pair_profile"] = "drop1_tight_drop2_emotional"
            elif archetype == "vocal_melodic" and rng.random() < 0.25:
                blueprint["drop_pair_profile"] = choose_weighted(rng, ["drop1_tight_drop2_emotional", "drop1_statement_drop2_upgrade"], energy_bias)
            elif blueprint["drum_style"] == "standard" and rng.random() < 0.2:
                blueprint["drop_pair_profile"] = "drop1_statement_drop2_upgrade"

    if archetype == "emotional_uplifter":
        blueprint["lead_archetype"] = choose_weighted(rng, ["uplift_hook", "anthemic"], energy_bias)
        blueprint["vocal_archetype"] = choose_weighted(rng, ["straight_hook", "stepwise_lift"], energy_bias)
        blueprint["breakdown_style"] = choose_weighted(rng, ["pad_space", "piano_led"], energy_bias)
        blueprint["drum_style"] = choose_weighted(rng, ["driving", "standard"], energy_bias)
        blueprint["bass_style"] = choose_weighted(rng, ["rolling_drive", "classic_offbeat"], energy_bias)
        blueprint["supersaw_identity"] = choose_weighted(rng, ["octave_shine", "wall_stack"], energy_bias)
        blueprint["drop_arrival_style"] = choose_weighted(rng, ["hook_first", "glide_in"], energy_bias)
        blueprint["callback_density"] = choose_weighted(rng, ["balanced", "strong"], energy_bias)
        blueprint["archetype_bass_grammar"] = choose_weighted(rng, ["motion", "anchor"], energy_bias)
        blueprint["archetype_drum_grammar"] = choose_weighted(rng, ["steady_drive", "push_hat"], energy_bias)
        blueprint["archetype_breakdown_focus"] = choose_weighted(rng, ["pad_horizon", "piano_memory"], energy_bias)
        blueprint["archetype_topline_density"] = choose_weighted(rng, ["lead_heavy", "balanced"], energy_bias)
        blueprint["archetype_support_timing"] = choose_weighted(rng, ["bed_first", "late_bloom"], energy_bias)
        blueprint["archetype_harmony_emphasis"] = choose_weighted(rng, ["pad_anchor", "string_lift"], energy_bias)
        blueprint["archetype_counter_grammar"] = choose_weighted(rng, ["lift_shadow", "tail_echo"], energy_bias)
        blueprint["archetype_supersaw_motion"] = choose_weighted(rng, ["full_hold", "late_bloom"], energy_bias)
        blueprint["archetype_drum_micro"] = choose_weighted(rng, ["straight_caps", "late_caps"], energy_bias)
        blueprint["archetype_counter_contour"] = choose_weighted(rng, ["rising_reply", "echo_fall"], energy_bias)
        blueprint["archetype_arp_grammar"] = choose_weighted(rng, ["stream", "lift_rush"], energy_bias)
        blueprint["archetype_pluck_grammar"] = choose_weighted(rng, ["foreshadow", "lift_chain"], energy_bias)
        blueprint["archetype_counter_presence"] = choose_weighted(rng, ["clear", "featured"], energy_bias)
        blueprint["archetype_counter_span"] = choose_weighted(rng, ["medium", "long"], energy_bias)
        blueprint["archetype_counter_register"] = choose_weighted(rng, ["mid_lane", "high_lane"], energy_bias)
        blueprint["archetype_counter_role"] = choose_weighted(rng, ["support", "featured_answer"], energy_bias)
    elif archetype == "festival_driver":
        blueprint["lead_archetype"] = choose_weighted(rng, ["driving", "anthemic"], energy_bias)
        blueprint["vocal_archetype"] = choose_weighted(rng, ["call_response", "straight_hook"], energy_bias)
        blueprint["breakdown_style"] = choose_weighted(rng, ["arp_texture", "pad_space"], energy_bias)
        blueprint["drum_style"] = choose_weighted(rng, ["festival", "driving"], energy_bias)
        blueprint["bass_style"] = choose_weighted(rng, ["rolling_drive", "syncopated"], energy_bias)
        blueprint["supersaw_identity"] = choose_weighted(rng, ["wall_stack", "pulse_stack"], energy_bias)
        blueprint["drop_arrival_style"] = choose_weighted(rng, ["slam", "hook_first"], energy_bias)
        blueprint["transition_intent"] = choose_weighted(rng, ["tension_riser", "snare_lift"], energy_bias)
        blueprint["archetype_bass_grammar"] = choose_weighted(rng, ["motion", "push"], energy_bias)
        blueprint["archetype_drum_grammar"] = choose_weighted(rng, ["festival_lift", "push_hat"], energy_bias)
        blueprint["archetype_breakdown_focus"] = choose_weighted(rng, ["arp_glow", "pad_horizon"], energy_bias)
        blueprint["archetype_topline_density"] = choose_weighted(rng, ["lead_heavy", "alternating"], energy_bias)
        blueprint["archetype_support_timing"] = choose_weighted(rng, ["staggered_frame", "response_window"], energy_bias)
        blueprint["archetype_harmony_emphasis"] = choose_weighted(rng, ["string_lift", "split_layers"], energy_bias)
        blueprint["archetype_counter_grammar"] = choose_weighted(rng, ["transition_spark", "mid_answer"], energy_bias)
        blueprint["archetype_supersaw_motion"] = choose_weighted(rng, ["split_pulse", "pulse_answer"], energy_bias)
        blueprint["archetype_drum_micro"] = choose_weighted(rng, ["busy_caps", "straight_caps"], energy_bias)
        blueprint["archetype_counter_contour"] = choose_weighted(rng, ["spark_jump", "rising_reply"], energy_bias)
        blueprint["archetype_arp_grammar"] = choose_weighted(rng, ["lift_rush", "answer"], energy_bias)
        blueprint["archetype_pluck_grammar"] = choose_weighted(rng, ["pulse", "lift_chain"], energy_bias)
        blueprint["archetype_counter_presence"] = choose_weighted(rng, ["featured", "late_focus"], energy_bias)
        blueprint["archetype_counter_span"] = choose_weighted(rng, ["medium", "extended"], energy_bias)
        blueprint["archetype_counter_register"] = choose_weighted(rng, ["mid_lane", "high_lane"], energy_bias)
        blueprint["archetype_counter_role"] = choose_weighted(rng, ["featured_answer", "transition_push"], energy_bias)
        blueprint["arrangement_density_profile"] = choose_weighted(rng, ["continuous", "staggered"], energy_bias)
        blueprint["groove_variation_profile"] = choose_weighted(rng, ["push_pull", "syncopated"], energy_bias)
        blueprint["opening_scene"] = choose_weighted(rng, ["drum_tease", "hook_tease"], energy_bias)
        blueprint["lead_evolution_profile"] = choose_weighted(rng, ["climbing", "wide_payoff"], energy_bias)
        blueprint["countermelody_engine"] = choose_weighted(rng, ["octave_lift", "answer_arc"], energy_bias)
        blueprint["drop_layer_budget"] = choose_weighted(rng, [5, 6], energy_bias)
    elif archetype == "vocal_melodic":
        blueprint["lead_archetype"] = choose_weighted(rng, ["yearning", "uplift_hook"], energy_bias)
        blueprint["vocal_archetype"] = choose_weighted(rng, ["held_emotive", "call_response"], energy_bias)
        blueprint["lead_vocal_relationship"] = choose_weighted(rng, ["lead_carries_drop_vocal_carries_breakdown", "lead_answers_vocal"], energy_bias)
        blueprint["breakdown_style"] = choose_weighted(rng, ["vocal_focus", "piano_led"], energy_bias)
        blueprint["drum_style"] = choose_weighted(rng, ["standard", "minimal"], energy_bias)
        blueprint["bass_style"] = choose_weighted(rng, ["classic_offbeat", "hybrid"], energy_bias)
        blueprint["supersaw_identity"] = choose_weighted(rng, ["bloom_stack", "octave_shine"], energy_bias)
        blueprint["drop_arrival_style"] = choose_weighted(rng, ["glide_in", "staggered"], energy_bias)
        blueprint["archetype_bass_grammar"] = choose_weighted(rng, ["breath", "anchor"], energy_bias)
        blueprint["archetype_drum_grammar"] = choose_weighted(rng, ["minimal_frame", "steady_drive"], energy_bias)
        blueprint["archetype_breakdown_focus"] = choose_weighted(rng, ["vocal_space", "piano_memory"], energy_bias)
        blueprint["archetype_topline_density"] = choose_weighted(rng, ["vocal_heavy", "balanced"], energy_bias)
        blueprint["archetype_support_timing"] = choose_weighted(rng, ["response_window", "late_bloom"], energy_bias)
        blueprint["archetype_harmony_emphasis"] = choose_weighted(rng, ["piano_answer", "split_layers"], energy_bias)
        blueprint["archetype_counter_grammar"] = choose_weighted(rng, ["tail_echo", "lift_shadow"], energy_bias)
        blueprint["archetype_supersaw_motion"] = choose_weighted(rng, ["late_bloom", "pulse_answer"], energy_bias)
        blueprint["archetype_drum_micro"] = choose_weighted(rng, ["late_caps", "straight_caps"], energy_bias)
        blueprint["archetype_counter_contour"] = choose_weighted(rng, ["echo_fall", "flat_reply"], energy_bias)
        blueprint["archetype_arp_grammar"] = choose_weighted(rng, ["breath", "answer"], energy_bias)
        blueprint["archetype_pluck_grammar"] = choose_weighted(rng, ["foreshadow", "drop_gap"], energy_bias)
        blueprint["archetype_counter_presence"] = choose_weighted(rng, ["whisper", "late_focus"], energy_bias)
        blueprint["archetype_counter_span"] = choose_weighted(rng, ["short", "medium"], energy_bias)
        blueprint["archetype_counter_register"] = choose_weighted(rng, ["low_lane", "mid_lane"], energy_bias)
        blueprint["archetype_counter_role"] = choose_weighted(rng, ["late_answer", "support"], energy_bias)
        blueprint["arrangement_density_profile"] = choose_weighted(rng, ["breathing", "spotlight", "staggered"], energy_bias)
        blueprint["groove_variation_profile"] = choose_weighted(rng, ["breathing", "steady"], energy_bias)
        blueprint["opening_scene"] = choose_weighted(rng, ["pad_seed", "bass_tease", "hook_tease"], energy_bias)
        blueprint["lead_evolution_profile"] = choose_weighted(rng, ["answering", "resolved"], energy_bias)
        blueprint["countermelody_engine"] = choose_weighted(rng, ["late_bloom", "answer_arc"], energy_bias)
        blueprint["drop_layer_budget"] = choose_weighted(rng, [4, 5], energy_bias)
    elif archetype == "progressive_dream":
        blueprint["lead_archetype"] = choose_weighted(rng, ["yearning", "anthemic"], energy_bias)
        blueprint["vocal_archetype"] = choose_weighted(rng, ["held_emotive", "stepwise_lift"], energy_bias)
        blueprint["breakdown_style"] = choose_weighted(rng, ["pad_space", "piano_led"], energy_bias)
        blueprint["drum_style"] = choose_weighted(rng, ["minimal", "standard"], energy_bias)
        blueprint["bass_style"] = choose_weighted(rng, ["hybrid", "classic_offbeat"], energy_bias)
        blueprint["supersaw_identity"] = choose_weighted(rng, ["bloom_stack", "pulse_stack"], energy_bias)
        blueprint["drop_arrival_style"] = choose_weighted(rng, ["glide_in", "staggered"], energy_bias)
        blueprint["transition_intent"] = choose_weighted(rng, ["harmonic_bloom", "drum_pullback"], energy_bias)
        blueprint["archetype_bass_grammar"] = choose_weighted(rng, ["breath", "motion"], energy_bias)
        blueprint["archetype_drum_grammar"] = choose_weighted(rng, ["minimal_frame", "steady_drive"], energy_bias)
        blueprint["archetype_breakdown_focus"] = choose_weighted(rng, ["pad_horizon", "arp_glow"], energy_bias)
        blueprint["archetype_topline_density"] = choose_weighted(rng, ["balanced", "vocal_heavy"], energy_bias)
        blueprint["archetype_support_timing"] = choose_weighted(rng, ["late_bloom", "response_window"], energy_bias)
        blueprint["archetype_harmony_emphasis"] = choose_weighted(rng, ["pad_anchor", "piano_answer"], energy_bias)
        blueprint["archetype_counter_grammar"] = choose_weighted(rng, ["mid_answer", "tail_echo"], energy_bias)
        blueprint["archetype_supersaw_motion"] = choose_weighted(rng, ["late_bloom", "full_hold"], energy_bias)
        blueprint["archetype_drum_micro"] = choose_weighted(rng, ["late_caps", "straight_caps"], energy_bias)
        blueprint["archetype_counter_contour"] = choose_weighted(rng, ["echo_fall", "rising_reply"], energy_bias)
        blueprint["archetype_arp_grammar"] = choose_weighted(rng, ["breath", "stream"], energy_bias)
        blueprint["archetype_pluck_grammar"] = choose_weighted(rng, ["drop_gap", "foreshadow"], energy_bias)
        blueprint["archetype_counter_presence"] = choose_weighted(rng, ["clear", "late_focus"], energy_bias)
        blueprint["archetype_counter_span"] = choose_weighted(rng, ["short", "medium"], energy_bias)
        blueprint["archetype_counter_register"] = choose_weighted(rng, ["low_lane", "mid_lane"], energy_bias)
        blueprint["archetype_counter_role"] = choose_weighted(rng, ["support", "late_answer"], energy_bias)
        blueprint["arrangement_density_profile"] = choose_weighted(rng, ["staggered", "breathing"], energy_bias)
        blueprint["groove_variation_profile"] = choose_weighted(rng, ["breathing", "steady"], energy_bias)
        blueprint["opening_scene"] = choose_weighted(rng, ["pad_seed", "bass_tease"], energy_bias)
        blueprint["lead_evolution_profile"] = choose_weighted(rng, ["answering", "climbing"], energy_bias)
        blueprint["countermelody_engine"] = choose_weighted(rng, ["shadow_hook", "late_bloom"], energy_bias)
        blueprint["drop_layer_budget"] = choose_weighted(rng, [4, 5], energy_bias)
    elif archetype == "anthemic_classic":
        blueprint["lead_archetype"] = choose_weighted(rng, ["anthemic", "uplift_hook"], energy_bias)
        blueprint["vocal_archetype"] = choose_weighted(rng, ["straight_hook", "call_response"], energy_bias)
        blueprint["breakdown_style"] = choose_weighted(rng, ["piano_led", "pad_space"], energy_bias)
        blueprint["drum_style"] = choose_weighted(rng, ["standard", "driving"], energy_bias)
        blueprint["bass_style"] = choose_weighted(rng, ["classic_offbeat", "rolling_drive"], energy_bias)
        blueprint["supersaw_identity"] = choose_weighted(rng, ["pulse_stack", "wall_stack"], energy_bias)
        blueprint["drop_arrival_style"] = choose_weighted(rng, ["hook_first", "staggered"], energy_bias)
        blueprint["transition_intent"] = choose_weighted(rng, ["harmonic_bloom", "snare_lift"], energy_bias)
        blueprint["archetype_bass_grammar"] = choose_weighted(rng, ["anchor", "motion"], energy_bias)
        blueprint["archetype_drum_grammar"] = choose_weighted(rng, ["steady_drive", "push_hat"], energy_bias)
        blueprint["archetype_breakdown_focus"] = choose_weighted(rng, ["piano_memory", "pad_horizon"], energy_bias)
        blueprint["archetype_topline_density"] = choose_weighted(rng, ["lead_heavy", "alternating"], energy_bias)
        blueprint["archetype_support_timing"] = choose_weighted(rng, ["bed_first", "staggered_frame"], energy_bias)
        blueprint["archetype_harmony_emphasis"] = choose_weighted(rng, ["pad_anchor", "piano_answer"], energy_bias)
        blueprint["archetype_counter_grammar"] = choose_weighted(rng, ["mid_answer", "transition_spark"], energy_bias)
        blueprint["archetype_supersaw_motion"] = choose_weighted(rng, ["full_hold", "split_pulse"], energy_bias)
        blueprint["archetype_drum_micro"] = choose_weighted(rng, ["straight_caps", "busy_caps"], energy_bias)
        blueprint["archetype_counter_contour"] = choose_weighted(rng, ["flat_reply", "spark_jump"], energy_bias)
        blueprint["archetype_arp_grammar"] = choose_weighted(rng, ["stream", "answer"], energy_bias)
        blueprint["archetype_pluck_grammar"] = choose_weighted(rng, ["pulse", "foreshadow"], energy_bias)
        blueprint["archetype_counter_presence"] = choose_weighted(rng, ["clear", "featured"], energy_bias)
        blueprint["archetype_counter_span"] = choose_weighted(rng, ["medium", "long"], energy_bias)
        blueprint["archetype_counter_register"] = choose_weighted(rng, ["mid_lane", "wide_lane"], energy_bias)
        blueprint["archetype_counter_role"] = choose_weighted(rng, ["support", "transition_push"], energy_bias)
        blueprint["arrangement_density_profile"] = choose_weighted(rng, ["continuous", "staggered"], energy_bias)
        blueprint["groove_variation_profile"] = choose_weighted(rng, ["push_pull", "steady"], energy_bias)
        blueprint["opening_scene"] = choose_weighted(rng, ["drum_tease", "pad_seed", "hook_tease"], energy_bias)
        blueprint["lead_evolution_profile"] = choose_weighted(rng, ["resolved", "wide_payoff"], energy_bias)
        blueprint["countermelody_engine"] = choose_weighted(rng, ["answer_arc", "octave_lift"], energy_bias)
        blueprint["drop_layer_budget"] = choose_weighted(rng, [5, 6], energy_bias)

    counter_bundle = counter_identity_bundle(rng, archetype)
    blueprint["archetype_counter_presence"] = counter_bundle["presence"]
    blueprint["archetype_counter_span"] = counter_bundle["span"]
    blueprint["archetype_counter_register"] = counter_bundle["register"]
    blueprint["archetype_counter_role"] = counter_bundle["role"]
    macro_bundle = macro_journey_bundle(rng, progression, archetype, blueprint, energy_bias)
    blueprint["macro_journey_profile"] = macro_bundle["macro_journey_profile"]
    blueprint["section_weight_profile"] = macro_bundle["section_weight_profile"]
    blueprint["drop_pair_profile"] = macro_bundle["drop_pair_profile"]
    blueprint["breakdown_function"] = macro_bundle["breakdown_function"]
    blueprint["final_lift_profile"] = macro_bundle["final_lift_profile"]
    if identity_profile:
        apply_identity_profile_to_blueprint(blueprint, identity_profile, progression, genre=progression)
    return blueprint

def build_identity_blueprint(root: str, rng: random.Random, variation: str, blueprint):
    spread = VARIATION_SPREAD[variation]
    lead_archetype = blueprint["lead_archetype"]
    resolution_bias = blueprint["lead_resolution_bias"]
    if lead_archetype == "anthemic":
        motif_degrees = [5, 3, 1, 7]
    elif lead_archetype == "yearning":
        motif_degrees = [3, 5, 6, 2]
    elif lead_archetype == "driving":
        motif_degrees = [5, 5, 7, 1]
    else:
        motif_degrees = [5, 3, 1, 5]
    if resolution_bias == "root_anchor":
        motif_degrees = [1, 5, 1, 1]
    elif resolution_bias == "third_to_root":
        motif_degrees = [3, 5, 6, 1]
    elif resolution_bias == "suspended_lift":
        motif_degrees = [3, 5, 6, 2]
    elif resolution_bias == "fifth_to_tonic":
        motif_degrees = [5, 3, 1, 1]
    if spread >= 1 and rng.random() > 0.45:
        motif_degrees[2] = rng.choice([1, 2, 6])
    if spread == 2 and rng.random() > 0.45:
        motif_degrees[3] = rng.choice([5, 6, 7])
    theme_anchor = note(root, blueprint["theme_anchor_degree"], 5)
    if blueprint["hook_recall_style"] == "direct_echo":
        theme_rhythm = [(0.0, 0.5), (1.0, 0.45), (2.0, 0.45), (3.0, 0.7)]
    elif blueprint["hook_recall_style"] == "interval_memory":
        theme_rhythm = [(0.0, 0.7), (1.5, 0.45), (3.0, 0.75)]
    elif blueprint["hook_recall_style"] == "rhythmic_shadow":
        theme_rhythm = [(0.0, 0.35), (0.75, 0.25), (1.5, 0.35), (2.75, 0.3), (3.25, 0.45)]
    else:
        theme_rhythm = [(0.0, 0.9), (2.25, 0.8)]
    return {
        "anchor": note(root, motif_degrees[0], 5),
        "support": note(root, motif_degrees[1], 5),
        "lift": note(root, motif_degrees[2], 6),
        "resolve": note(root, motif_degrees[3], 5),
        "counter": note(root, 3, 4),
        "vocal_anchor": note(root, 1, 5),
        "theme_anchor": theme_anchor,
        "theme_degrees": motif_degrees[:],
        "theme_fragment": [note(root, degree, 5 if degree in (1, 3, 5) else 6) for degree in motif_degrees[:4]],
        "theme_rhythm": theme_rhythm,
    }


def add_identity_note(note_tracks, stem, bar_index, beat_pos, beat_len, pitch, velocity):
    note_tracks[stem].append({
        "start": bar_tick(bar_index) + tick(beat_pos),
        "end": bar_tick(bar_index) + tick(beat_pos + beat_len),
        "pitch": int(pitch),
        "velocity": int(clamp(velocity, 1, 124)),
        "channel": 0,
    })


def apply_identity_intro_signature(note_tracks, sections, chords, blueprint):
    intro = next((section for section in sections if section_kind(section["name"]) == "intro"), None)
    if not intro:
        return
    style = blueprint.get("identity_intro_style", "")
    start_bar = intro["start_bar"]
    end_bar = min(intro["end_bar"], start_bar + 8)
    for bar_index in range(start_bar, end_bar):
        chord = chords[bar_index % len(chords)]
        local = bar_index - start_bar
        if style == "pad_supersaw_tease":
            add_identity_note(note_tracks, "pad", bar_index, 0.0, 3.5, chord["root"], 54)
            add_identity_note(note_tracks, "pad", bar_index, 0.0, 3.5, chord["fifth"], 50)
            if local >= 4:
                for pitch in (chord["root"] + 12, chord["third"] + 12, chord["fifth"] + 12):
                    add_identity_note(note_tracks, "supersaw_chords", bar_index, 2.5, 0.9, clamp(pitch, 58, 84), 48)
        elif style == "vocal_or_piano_hint":
            target = chord["third"] + 12 if local % 2 else chord["root"] + 12
            add_identity_note(note_tracks, "piano", bar_index, 0.0, 1.8, clamp(target, 60, 82), 66)
            if local in (1, 5):
                add_identity_note(note_tracks, "vocal_melody", bar_index, 2.5, 1.0, clamp(chord["fifth"] + 12, 60, 84), 58)
        elif style == "groove_pad_atmosphere":
            add_identity_note(note_tracks, "pad", bar_index, 0.0, 3.8, clamp(chord["root"], 45, 70), 48)
            add_identity_note(note_tracks, "rolling_bass", bar_index, 1.5, 0.35, clamp(chord["root"] - 12, 36, 52), 54)
            add_identity_note(note_tracks, "rolling_bass", bar_index, 3.0, 0.35, clamp(chord["fifth"] - 12, 36, 55), 50)
        elif style == "kick_bass_percussion_tension":
            if local % 2 == 0:
                add_identity_note(note_tracks, "kick", bar_index, 0.0, 0.18, 36, 86)
            add_identity_note(note_tracks, "rolling_bass", bar_index, 1.0, 0.25, clamp(chord["root"] - 12, 36, 52), 66)
            add_identity_note(note_tracks, "hats", bar_index, 2.0, 0.08, 42, 44 + local * 2)
        elif style == "piano_strings_teaser":
            add_identity_note(note_tracks, "piano", bar_index, 0.0, 2.0, clamp(chord["root"] + 12, 60, 84), 70)
            if local % 2 == 0:
                for pitch in (chord["root"], chord["third"], chord["fifth"]):
                    add_identity_note(note_tracks, "strings", bar_index, 0.0, 4.0, clamp(pitch, 43, 82), 58 + local)
        elif style == "early_arp_pluck_motif":
            for beat_pos, pitch in ((0.0, chord["root"] + 12), (1.5, chord["third"] + 12), (3.0, chord["fifth"] + 12)):
                add_identity_note(note_tracks, "arp", bar_index, beat_pos, 0.35, clamp(pitch, 60, 78), 58)
            if local % 2 == 1:
                add_identity_note(note_tracks, "pluck", bar_index, 2.0, 0.5, clamp(chord["root"] + 24, 72, 88), 62)
        elif style == "low_pad_dark_motif":
            add_identity_note(note_tracks, "pad", bar_index, 0.0, 4.0, clamp(chord["root"] - 12, 36, 60), 54)
            add_identity_note(note_tracks, "strings", bar_index, 0.0, 3.5, clamp(chord["third"], 43, 72), 48)
            if local in (3, 7):
                add_identity_note(note_tracks, "lead", bar_index, 2.5, 0.8, clamp(chord["third"] + 12, 60, 82), 58)


def scale_identity_section_notes(note_tracks, sections, blueprint):
    key = blueprint.get("track_identity_key", "")
    for section in sections:
        kind = section_kind(section["name"])
        if kind not in ("drop", "breakdown", "build"):
            continue
        start = bar_tick(section["start_bar"])
        end = bar_tick(section["end_bar"])
        if key in ("EMOTIONAL_VOCAL_TRANCE", "PROGRESSIVE_TRANCE"):
            for stem in ("lead", "supersaw_chords"):
                for note_data in note_tracks[stem]:
                    if start <= note_data["start"] < end:
                        note_data["velocity"] = clamp(note_data["velocity"] - (10 if stem == "supersaw_chords" else 8), 1, 124)
        elif key == "TECH_UPLIFT":
            for stem in ("rolling_bass", "arp", "pluck"):
                for note_data in note_tracks[stem]:
                    if start <= note_data["start"] < end:
                        note_data["velocity"] = clamp(note_data["velocity"] + 10, 1, 124)
                        if stem in ("arp", "pluck"):
                            note_data["end"] = min(note_data["end"], note_data["start"] + tick(0.75))
        elif key == "ORCHESTRAL_UPLIFTING":
            for stem in ("strings", "piano"):
                for note_data in note_tracks[stem]:
                    if start <= note_data["start"] < end:
                        note_data["velocity"] = clamp(note_data["velocity"] + 10, 1, 124)
        elif key == "CLASSIC_2000S_TRANCE":
            for stem in ("arp", "pluck"):
                for note_data in note_tracks[stem]:
                    if start <= note_data["start"] < end:
                        note_data["velocity"] = clamp(note_data["velocity"] + 8, 1, 124)
        elif key == "DARK_EUPHORIC":
            for stem in ("supersaw_chords", "lead", "arp"):
                for note_data in note_tracks[stem]:
                    if start <= note_data["start"] < end:
                        note_data["pitch"] = clamp(note_data["pitch"] - 5 if note_data["pitch"] > 72 else note_data["pitch"], 36, 98)
                        note_data["velocity"] = clamp(note_data["velocity"] - (8 if stem == "supersaw_chords" else 2), 1, 124)


def apply_identity_breakdown_signature(note_tracks, sections, chords, blueprint):
    breakdown = next((section for section in sections if section_kind(section["name"]) == "breakdown"), None)
    if not breakdown:
        return
    key = blueprint.get("track_identity_key", "")
    start_bar = breakdown["start_bar"]
    end_bar = min(breakdown["end_bar"], start_bar + 8)
    for bar_index in range(start_bar, end_bar):
        chord = chords[bar_index % len(chords)]
        local = bar_index - start_bar
        if key == "CLASSIC_2000S_TRANCE":
            add_identity_note(note_tracks, "pad", bar_index, 0.0, 3.0, clamp(chord["root"], 48, 72), 48)
            for beat_pos, pitch in ((0.0, chord["root"] + 12), (1.5, chord["third"] + 12), (3.0, chord["fifth"] + 12)):
                add_identity_note(note_tracks, "arp", bar_index, beat_pos, 0.35, clamp(pitch, 60, 80), 54)
        elif key == "EMOTIONAL_VOCAL_TRANCE" and local % 2 == 0:
            add_identity_note(note_tracks, "vocal_melody", bar_index, 2.0, 1.25, clamp(chord["third"] + 12, 60, 84), 56)
        elif key == "DARK_EUPHORIC":
            add_identity_note(note_tracks, "pad", bar_index, 0.0, 3.5, clamp(chord["root"] - 12, 36, 60), 52)
            if local % 2 == 0:
                add_identity_note(note_tracks, "strings", bar_index, 0.0, 3.5, clamp(chord["third"], 43, 72), 50)


def reduce_notes_in_sections(note_tracks, stem, sections, keep_ratio=0.5, min_notes_per_bar=1):
    for section in sections:
        start_bar = section["start_bar"]
        end_bar = section["end_bar"]
        kept = [note for note in note_tracks[stem] if not (bar_tick(start_bar) <= note["start"] < bar_tick(end_bar))]
        for bar_index in range(start_bar, end_bar):
            bar_notes = sorted(notes_starting_in_bar(note_tracks[stem], bar_index), key=lambda item: (item["start"], item["pitch"]))
            keep_count = max(min_notes_per_bar, int(round(len(bar_notes) * keep_ratio))) if bar_notes else 0
            kept.extend(bar_notes[:keep_count])
        note_tracks[stem] = sorted(kept, key=lambda item: (item["start"], item["pitch"]))


def first_bars_window(sections, bars=16):
    total_end = sections[-1]["end_bar"] if sections else bars
    return {"name": f"First {bars}", "start_bar": 0, "end_bar": min(bars, total_end)}


def section_by_name(sections, target_name):
    return next((section for section in sections if section["name"] == target_name), None)


def story_entry_bar(sections, entry, fallback_bar=0):
    if not entry:
        return fallback_bar
    section_name, offset = entry
    section = section_by_name(sections, section_name)
    if not section:
        return fallback_bar
    return min(section["end_bar"], section["start_bar"] + int(offset))


def note_in_section(note_data, section):
    return bar_tick(section["start_bar"]) <= note_data["start"] < bar_tick(section["end_bar"])


def filter_stem_before_bar(note_tracks, stem, entry_bar, allowed_intro=None):
    allowed_intro = allowed_intro or set()
    intro = allowed_intro.get("section") if isinstance(allowed_intro, dict) else None
    allow_intro_stem = isinstance(allowed_intro, dict) and stem in allowed_intro.get("stems", set())
    kept = []
    for note_data in note_tracks[stem]:
        if note_data["start"] >= bar_tick(entry_bar):
            kept.append(note_data)
            continue
        if intro and allow_intro_stem and note_in_section(note_data, intro):
            kept.append(note_data)
    note_tracks[stem] = kept


def apply_arrangement_intro_focus(note_tracks, sections, blueprint):
    intro = section_by_name(sections, "Intro")
    if not intro:
        return
    allowed = set(blueprint.get("arrangement_story_profile", {}).get("intro_instruments", []))
    if not allowed:
        return
    focus_stems = {
        "kick", "offbeat_bass", "rolling_bass", "sub_bass", "clap_snare", "hats",
        "lead", "supersaw_chords", "pad", "arp", "pluck", "strings", "piano", "vocal_melody",
    }
    for stem in focus_stems - allowed:
        note_tracks[stem] = [note for note in note_tracks[stem] if not note_in_section(note, intro)]


def apply_arrangement_breakdown_focus(note_tracks, sections, blueprint):
    breakdown = section_by_name(sections, "Breakdown")
    if not breakdown:
        return
    allowed = set(blueprint.get("arrangement_story_profile", {}).get("breakdown_instruments", []))
    if not allowed:
        return
    focus_stems = {"arp", "pluck", "pad", "strings", "piano", "vocal_melody"}
    for stem in focus_stems - allowed:
        note_tracks[stem] = [note for note in note_tracks[stem] if not note_in_section(note, breakdown)]


def apply_arrangement_entry_gates(note_tracks, sections, blueprint):
    profile = blueprint.get("arrangement_story_profile", {})
    intro = section_by_name(sections, "Intro")
    allowed_intro = {"section": intro, "stems": set(profile.get("intro_instruments", []))}
    lead_bar = story_entry_bar(sections, profile.get("lead_entry"), 0)
    arp_bar = story_entry_bar(sections, profile.get("arp_entry"), 0)
    bass_bar = story_entry_bar(sections, profile.get("bass_entry"), 0)
    filter_stem_before_bar(note_tracks, "lead", lead_bar, allowed_intro)
    for stem in ("arp", "pluck"):
        filter_stem_before_bar(note_tracks, stem, arp_bar, allowed_intro)
    for stem in ("offbeat_bass", "rolling_bass", "sub_bass"):
        filter_stem_before_bar(note_tracks, stem, bass_bar, allowed_intro)


def apply_arrangement_drop2_energy(note_tracks, sections, blueprint):
    profile = blueprint.get("arrangement_story_profile", {})
    boost = float(profile.get("drop2_energy_boost", 1.0) or 1.0)
    drop2 = section_by_name(sections, "Drop 2")
    if not drop2 or boost <= 1.0:
        return
    for stem in ("supersaw_chords", "offbeat_bass", "rolling_bass", "clap_snare", "hats"):
        for note_data in note_tracks[stem]:
            if note_in_section(note_data, drop2):
                note_data["velocity"] = clamp(int(note_data["velocity"] * boost), 1, 124)


def add_intro_arp_motif(note_tracks, bar_index, chord, velocity=76):
    for beat_pos, pitch in (
        (0.0, chord["root"] + 12),
        (1.0, chord["third"] + 12),
        (2.0, chord["fifth"] + 12),
        (3.0, chord["third"] + 12),
    ):
        add_identity_note(note_tracks, "arp", bar_index, beat_pos, 0.35, clamp(pitch, 60, 82), velocity)


def add_intro_pluck_support(note_tracks, bar_index, chord, velocity=70):
    add_identity_note(note_tracks, "pluck", bar_index, 1.5, 0.55, clamp(chord["fifth"] + 12, 67, 86), velocity)
    add_identity_note(note_tracks, "pluck", bar_index, 3.0, 0.55, clamp(chord["root"] + 24, 72, 90), max(1, velocity - 4))


def apply_variation_enforcement(note_tracks, sections, chords, blueprint):
    variation = blueprint.get("variation_type", "DEFAULT")
    first16 = first_bars_window(sections, 16)
    if variation == "ARP_DRIVEN":
        reduce_notes_in_sections(note_tracks, "supersaw_chords", [first16], keep_ratio=0.15, min_notes_per_bar=0)
        for bar_index in range(first16["start_bar"], first16["end_bar"]):
            chord = chords[bar_index % len(chords)]
            if len(notes_starting_in_bar(note_tracks["arp"], bar_index)) < 3:
                add_intro_arp_motif(note_tracks, bar_index, chord, velocity=78)
            if bar_index % 2 == 0 and len(notes_starting_in_bar(note_tracks["pluck"], bar_index)) < 1:
                add_intro_pluck_support(note_tracks, bar_index, chord, velocity=72)
    elif variation == "SUPERSAW_HEAVY":
        reduce_notes_in_sections(note_tracks, "arp", [first16], keep_ratio=0.1, min_notes_per_bar=0)
        reduce_notes_in_sections(note_tracks, "pluck", [first16], keep_ratio=0.1, min_notes_per_bar=0)
        for bar_index in range(first16["start_bar"], first16["end_bar"]):
            chord = chords[bar_index % len(chords)]
            saw_bar = notes_starting_in_bar(note_tracks["supersaw_chords"], bar_index)
            if len(saw_bar) < 3:
                for pitch in (chord["root"], chord["third"], chord["fifth"], chord["root"] + 12):
                    add_identity_note(note_tracks, "supersaw_chords", bar_index, 0.0, 2.0, clamp(pitch, 48, 86), 68)
            else:
                for note_data in saw_bar:
                    note_data["velocity"] = clamp(note_data["velocity"] + 10, 1, 124)
    elif variation == "EARLY_DROP":
        drop1 = section_by_name(sections, "Drop 1")
        if drop1 and drop1["start_bar"] <= 16:
            first_drop_bar = drop1["start_bar"]
            chord = chords[first_drop_bar % len(chords)]
            if not notes_starting_in_bar(note_tracks["lead"], first_drop_bar):
                add_identity_note(note_tracks, "lead", first_drop_bar, 0.0, 1.75, clamp(chord["third"] + 12, 66, 86), 104)
            if not notes_starting_in_bar(note_tracks["supersaw_chords"], first_drop_bar):
                for pitch in (chord["root"], chord["third"], chord["fifth"], chord["root"] + 12):
                    add_identity_note(note_tracks, "supersaw_chords", first_drop_bar, 0.0, 1.75, clamp(pitch, 48, 86), 108)


def add_emotional_breakdown_support(note_tracks, section, chords, include_piano=True, include_strings=True):
    for bar_index in range(section["start_bar"], section["end_bar"]):
        chord = chords[bar_index % len(chords)]
        local = bar_index - section["start_bar"]
        if include_piano and local % 2 == 0 and not notes_starting_in_bar(note_tracks["piano"], bar_index):
            target = chord["root"] + 12 if local < section["bars"] - 2 else chord["third"] + 12
            add_identity_note(note_tracks, "piano", bar_index, 0.0, 2.0, clamp(target, 60, 84), 74)
        if include_strings and local % 2 == 0:
            existing_strings = notes_starting_in_bar(note_tracks["strings"], bar_index)
            if len(existing_strings) < 2:
                for pitch in (chord["root"], chord["fifth"], chord["third"] + 12):
                    add_identity_note(note_tracks, "strings", bar_index, 0.0, 4.0, clamp(pitch, 43, 88), 70)


def enforce_breakdown_identity_focus(note_tracks, sections, chords, blueprint):
    if blueprint.get("track_identity_key") != "ANTHEMIC_UPLIFTING":
        return
    breakdown = section_by_name(sections, "Breakdown")
    if not breakdown:
        return
    variation = blueprint.get("variation_type", "DEFAULT")
    if variation == "SUPERSAW_HEAVY":
        add_emotional_breakdown_support(note_tracks, breakdown, chords, include_piano=False, include_strings=True)
    else:
        add_emotional_breakdown_support(note_tracks, breakdown, chords, include_piano=True, include_strings=True)
    if variation == "ARP_DRIVEN":
        # Keep the arp identity, but do not let the emotional center collapse into pad-only support.
        piano_density = stem_density_in_sections(note_tracks, "piano", [breakdown])
        strings_density = stem_density_in_sections(note_tracks, "strings", [breakdown])
        if piano_density + strings_density < 0.75:
            add_emotional_breakdown_support(note_tracks, breakdown, chords, include_piano=True, include_strings=True)
    if variation == "EARLY_DROP":
        # The fast first drop needs a contrasting, unmistakably emotional reset.
        add_emotional_breakdown_support(note_tracks, breakdown, chords, include_piano=True, include_strings=True)


def apply_arrangement_story_gates(note_tracks, sections, blueprint):
    apply_arrangement_intro_focus(note_tracks, sections, blueprint)
    apply_arrangement_entry_gates(note_tracks, sections, blueprint)
    apply_arrangement_breakdown_focus(note_tracks, sections, blueprint)


def validate_arrangement_story(note_tracks, blueprint, sections):
    profile = blueprint.get("arrangement_story_profile", {})
    intro = section_by_name(sections, "Intro")
    breakdown = section_by_name(sections, "Breakdown")
    drop1 = section_by_name(sections, "Drop 1")
    drop2 = section_by_name(sections, "Drop 2")
    allowed_intro = set(profile.get("intro_instruments", []))
    allowed_breakdown = set(profile.get("breakdown_instruments", []))
    intro_density = {}
    first16_density = {}
    breakdown_density = {}
    score = 0
    failed = []
    if profile:
        score += 15
    else:
        failed.append("missing_story_profile")
    if intro:
        first_window = first_bars_window(sections, 16)
        for stem in ("kick", "offbeat_bass", "rolling_bass", "lead", "supersaw_chords", "pad", "arp", "pluck", "strings", "piano", "vocal_melody"):
            intro_density[stem] = stem_density_in_sections(note_tracks, stem, [intro])
            first16_density[stem] = stem_density_in_sections(note_tracks, stem, [first_window])
        allowed_density = sum(intro_density.get(stem, 0) for stem in allowed_intro)
        disallowed_density = sum(value for stem, value in intro_density.items() if stem not in allowed_intro)
        if allowed_density > 0 and allowed_density >= disallowed_density:
            score += 20
        else:
            failed.append("intro_focus_not_dominant")
    if breakdown:
        for stem in ("arp", "pluck", "pad", "strings", "piano", "vocal_melody"):
            breakdown_density[stem] = stem_density_in_sections(note_tracks, stem, [breakdown])
        allowed_breakdown_density = sum(breakdown_density.get(stem, 0) for stem in allowed_breakdown)
        disallowed_breakdown_density = sum(value for stem, value in breakdown_density.items() if stem not in allowed_breakdown)
        if allowed_breakdown_density >= disallowed_breakdown_density:
            score += 15
        else:
            failed.append("breakdown_focus_not_dominant")
    lead_entry = story_entry_bar(sections, profile.get("lead_entry"), 0)
    arp_entry = story_entry_bar(sections, profile.get("arp_entry"), 0)
    bass_entry = story_entry_bar(sections, profile.get("bass_entry"), 0)
    if not any(note["start"] < bar_tick(lead_entry) for note in note_tracks["lead"] if not (intro and "lead" in allowed_intro and note_in_section(note, intro))):
        score += 10
    else:
        failed.append("lead_enters_too_early")
    if not any(note["start"] < bar_tick(arp_entry) for stem in ("arp", "pluck") for note in note_tracks[stem] if not (intro and stem in allowed_intro and note_in_section(note, intro))):
        score += 10
    else:
        failed.append("arp_or_pluck_enters_too_early")
    if not any(note["start"] < bar_tick(bass_entry) for stem in ("offbeat_bass", "rolling_bass", "sub_bass") for note in note_tracks[stem] if not (intro and stem in allowed_intro and note_in_section(note, intro))):
        score += 10
    else:
        failed.append("bass_enters_too_early")
    if drop1 and drop2 and drop2["bars"] >= drop1["bars"]:
        score += 10
    elif drop1 and drop2:
        failed.append("drop2_not_longer_or_equal")
    if drop1:
        score += 10
    else:
        failed.append("drop1_missing")
    if breakdown and breakdown["bars"] >= 12:
        score += 10
    elif breakdown:
        failed.append("breakdown_too_short")
    section_signature = ",".join(f"{section['name']}:{section['bars']}" for section in sections)
    variation = blueprint.get("variation_type", "DEFAULT")
    first16_arp_density = first16_density.get("arp", 0)
    first16_pluck_density = first16_density.get("pluck", 0)
    first16_supersaw_density = first16_density.get("supersaw_chords", 0)
    breakdown_piano_density = breakdown_density.get("piano", 0)
    breakdown_strings_density = breakdown_density.get("strings", 0)
    breakdown_vocal_density = breakdown_density.get("vocal_melody", 0)
    breakdown_focus_target = ",".join(sorted(allowed_breakdown))
    breakdown_identity_passed = True
    if blueprint.get("track_identity_key") == "ANTHEMIC_UPLIFTING":
        if breakdown_piano_density + breakdown_strings_density <= 0:
            breakdown_identity_passed = False
        if variation == "ARP_DRIVEN" and breakdown_piano_density + breakdown_strings_density < 0.5:
            breakdown_identity_passed = False
        if variation == "SUPERSAW_HEAVY" and breakdown_strings_density <= 0:
            breakdown_identity_passed = False
        if variation == "EARLY_DROP" and breakdown_piano_density + breakdown_strings_density < 1.0:
            breakdown_identity_passed = False
    variation_passed = True
    variation_failures = []
    if variation == "ARP_DRIVEN":
        if first16_arp_density < 2.0:
            variation_passed = False
            variation_failures.append("arp_first16_too_low")
        if first16_pluck_density < 0.5:
            variation_passed = False
            variation_failures.append("pluck_support_missing")
        if first16_supersaw_density > max(2.0, first16_arp_density):
            variation_passed = False
            variation_failures.append("intro_supersaw_masks_arp")
    elif variation == "SUPERSAW_HEAVY":
        if first16_supersaw_density <= first16_arp_density + first16_pluck_density:
            variation_passed = False
            variation_failures.append("supersaw_not_dominant_first16")
        if first16_arp_density + first16_pluck_density > max(2.0, first16_supersaw_density * 0.4):
            variation_passed = False
            variation_failures.append("arp_pluck_not_minimal")
    elif variation == "EARLY_DROP":
        if not drop1 or drop1["start_bar"] > 16:
            variation_passed = False
            variation_failures.append("drop_after_bar_17")
        elif not notes_starting_in_bar(note_tracks["lead"], drop1["start_bar"]) or not notes_starting_in_bar(note_tracks["supersaw_chords"], drop1["start_bar"]):
            variation_passed = False
            variation_failures.append("lead_or_supersaw_missing_at_first_drop")
    return {
        "variation_type": blueprint.get("variation_type", "DEFAULT"),
        "variation_behavior_summary": blueprint.get("variation_behavior_summary", ""),
        "variation_enforcement_passed": variation_passed,
        "variation_enforcement_failed_checks": ",".join(variation_failures) if variation_failures else "none",
        "first16_arp_density": first16_arp_density,
        "first16_pluck_density": first16_pluck_density,
        "first16_supersaw_density": first16_supersaw_density,
        "breakdown_piano_density": breakdown_piano_density,
        "breakdown_strings_density": breakdown_strings_density,
        "breakdown_vocal_density": breakdown_vocal_density,
        "breakdown_focus_target": breakdown_focus_target,
        "breakdown_identity_passed": breakdown_identity_passed,
        "arrangement_story_profile": blueprint.get("arrangement_story_name", ""),
        "arrangement_story_score": min(100, score),
        "arrangement_story_failed_checks": ",".join(failed) if failed else "none",
        "arrangement_section_signature": section_signature,
        "arrangement_intro_instrumentation": ",".join(sorted(allowed_intro)),
        "arrangement_breakdown_instrumentation": ",".join(sorted(allowed_breakdown)),
        "arrangement_lead_entry_bar": lead_entry + 1,
        "arrangement_arp_entry_bar": arp_entry + 1,
        "arrangement_bass_entry_bar": bass_entry + 1,
        "arrangement_drop1_start_bar": (drop1["start_bar"] + 1) if drop1 else 0,
        "arrangement_drop2_start_bar": (drop2["start_bar"] + 1) if drop2 else 0,
        "arrangement_first16_signature": ",".join(f"{stem}={value}" for stem, value in first16_density.items()),
        "arrangement_breakdown_signature": ",".join(f"{stem}={value}" for stem, value in breakdown_density.items()),
    }


def apply_uplifting_subtype_contrast(note_tracks, sections, chords, blueprint):
    if blueprint.get("genre") != "uplifting":
        return
    key = blueprint.get("track_identity_key", "")
    intro = [section for section in sections if section_kind(section["name"]) == "intro"]
    drops = [section for section in sections if section_kind(section["name"]) == "drop"]
    breakdowns = [section for section in sections if section_kind(section["name"]) == "breakdown"]
    builds = [section for section in sections if section_kind(section["name"]) == "build"]
    if key == "ANTHEMIC_UPLIFTING":
        for section in drops:
            for bar_index in range(section["start_bar"], section["end_bar"]):
                chord = chords[bar_index % len(chords)]
                add_identity_note(note_tracks, "offbeat_bass", bar_index, 1.0, 0.45, clamp(chord["root"] - 12, 36, 54), 92)
                add_identity_note(note_tracks, "offbeat_bass", bar_index, 3.0, 0.45, clamp(chord["root"] - 12, 36, 54), 90)
                add_identity_note(note_tracks, "rolling_bass", bar_index, 0.5, 0.25, clamp(chord["fifth"] - 12, 38, 57), 82)
                add_identity_note(note_tracks, "rolling_bass", bar_index, 2.5, 0.25, clamp(chord["root"] - 12, 36, 54), 84)
        for section in intro:
            for bar_index in range(section["start_bar"], min(section["end_bar"], section["start_bar"] + 8)):
                chord = chords[bar_index % len(chords)]
                for pitch in (chord["root"] + 12, chord["third"] + 12, chord["fifth"] + 12):
                    add_identity_note(note_tracks, "supersaw_chords", bar_index, 3.0, 0.75, clamp(pitch, 60, 84), 54)
    elif key == "CLASSIC_2000S_TRANCE":
        for section in intro + builds + breakdowns:
            for bar_index in range(section["start_bar"], section["end_bar"]):
                chord = chords[bar_index % len(chords)]
                for beat_pos, pitch in ((0.0, chord["root"] + 12), (1.0, chord["third"] + 12), (2.0, chord["fifth"] + 12), (3.0, chord["third"] + 12)):
                    add_identity_note(note_tracks, "arp", bar_index, beat_pos, 0.35, clamp(pitch, 60, 82), 70)
                if bar_index % 2 == 0:
                    add_identity_note(note_tracks, "pluck", bar_index, 1.5, 0.5, clamp(chord["fifth"] + 12, 67, 86), 72)
                    add_identity_note(note_tracks, "pluck", bar_index, 3.0, 0.5, clamp(chord["root"] + 24, 72, 90), 70)
        for section in drops:
            for bar_index in range(section["start_bar"], section["end_bar"]):
                chord = chords[bar_index % len(chords)]
                add_identity_note(note_tracks, "arp", bar_index, 0.5, 0.3, clamp(chord["root"] + 12, 60, 82), 64)
                add_identity_note(note_tracks, "arp", bar_index, 2.5, 0.3, clamp(chord["fifth"] + 12, 60, 84), 64)
    elif key == "ORCHESTRAL_UPLIFTING":
        reduce_notes_in_sections(note_tracks, "arp", drops + breakdowns + builds, keep_ratio=0.25, min_notes_per_bar=0)
        reduce_notes_in_sections(note_tracks, "pluck", drops + breakdowns + builds, keep_ratio=0.15, min_notes_per_bar=0)
        for section in intro + breakdowns:
            for bar_index in range(section["start_bar"], section["end_bar"]):
                chord = chords[bar_index % len(chords)]
                add_identity_note(note_tracks, "piano", bar_index, 0.0, 2.0, clamp(chord["root"] + 12, 60, 84), 78)
                if bar_index % 2 == 0:
                    for pitch in (chord["root"], chord["third"], chord["fifth"], chord["root"] + 12):
                        add_identity_note(note_tracks, "strings", bar_index, 0.0, 4.0, clamp(pitch, 43, 88), 74)
        for section in drops:
            for note_data in note_tracks["supersaw_chords"]:
                if bar_tick(section["start_bar"]) <= note_data["start"] < bar_tick(section["end_bar"]):
                    note_data["velocity"] = clamp(note_data["velocity"] - 8, 1, 124)
    elif key == "EMOTIONAL_VOCAL_TRANCE":
        reduce_notes_in_sections(note_tracks, "lead", drops + breakdowns + builds, keep_ratio=0.55, min_notes_per_bar=1)
        reduce_notes_in_sections(note_tracks, "arp", drops + breakdowns + builds, keep_ratio=0.35, min_notes_per_bar=0)
        reduce_notes_in_sections(note_tracks, "pluck", drops + breakdowns + builds, keep_ratio=0.2, min_notes_per_bar=0)
        for section in intro + breakdowns + drops:
            for bar_index in range(section["start_bar"], section["end_bar"]):
                chord = chords[bar_index % len(chords)]
                if bar_index % 2 == 0:
                    add_identity_note(note_tracks, "vocal_melody", bar_index, 1.5, 1.5, clamp(chord["third"] + 12, 60, 84), 72)
                if section_kind(section["name"]) == "drop":
                    for note_data in notes_starting_in_bar(note_tracks["supersaw_chords"], bar_index):
                        note_data["velocity"] = clamp(note_data["velocity"] - 10, 1, 124)


def stem_density_in_sections(note_tracks, stem, sections):
    total_bars = sum(section["end_bar"] - section["start_bar"] for section in sections)
    total_notes = sum(len(section_note_slice(note_tracks[stem], section["start_bar"], section["end_bar"])) for section in sections)
    return round(total_notes / max(1, total_bars), 3)


def add_offbeat_bass_bar(note_tracks, bar_index, chord, velocity=88):
    root = clamp(chord["root"] - 12, 36, 54)
    add_identity_note(note_tracks, "offbeat_bass", bar_index, 1.0, 0.45, root, velocity)
    add_identity_note(note_tracks, "offbeat_bass", bar_index, 3.0, 0.45, root, max(1, velocity - 2))


def add_support_rolling_bass_bar(note_tracks, bar_index, chord, velocity=72):
    add_identity_note(note_tracks, "rolling_bass", bar_index, 0.5, 0.25, clamp(chord["fifth"] - 12, 38, 57), velocity)
    add_identity_note(note_tracks, "rolling_bass", bar_index, 2.5, 0.25, clamp(chord["root"] - 12, 36, 54), max(1, velocity - 2))


def enforce_identity_bass_behavior(note_tracks, sections, chords, blueprint):
    key = blueprint.get("track_identity_key", "")
    target = blueprint.get("identity_bass_style", "")
    drops = [section for section in sections if section_kind(section["name"]) == "drop"]
    builds = [section for section in sections if section_kind(section["name"]) == "build"]
    verses = [section for section in sections if section_kind(section["name"]) == "verse"]
    if target == "offbeat_plus_rolling" or key == "ANTHEMIC_UPLIFTING":
        for section in verses + builds + drops:
            for bar_index in range(section["start_bar"], section["end_bar"]):
                chord = chords[bar_index % len(chords)]
                existing_offbeat = notes_starting_in_bar(note_tracks["offbeat_bass"], bar_index)
                if not existing_offbeat:
                    add_offbeat_bass_bar(note_tracks, bar_index, chord, velocity=82 if section_kind(section["name"]) != "drop" else 94)
                if section_kind(section["name"]) == "drop" and not notes_starting_in_bar(note_tracks["rolling_bass"], bar_index):
                    add_support_rolling_bass_bar(note_tracks, bar_index, chord, velocity=78)
    elif key == "CLASSIC_2000S_TRANCE":
        for section in verses + builds + drops:
            for bar_index in range(section["start_bar"], section["end_bar"]):
                chord = chords[bar_index % len(chords)]
                if not notes_starting_in_bar(note_tracks["offbeat_bass"], bar_index):
                    add_offbeat_bass_bar(note_tracks, bar_index, chord, velocity=88 if section_kind(section["name"]) == "drop" else 78)
        reduce_notes_in_sections(note_tracks, "rolling_bass", drops + builds, keep_ratio=0.35, min_notes_per_bar=1)
    elif key == "ORCHESTRAL_UPLIFTING":
        for section in drops + builds:
            for bar_index in range(section["start_bar"], section["end_bar"]):
                chord = chords[bar_index % len(chords)]
                if section_kind(section["name"]) == "drop" and not notes_starting_in_bar(note_tracks["offbeat_bass"], bar_index):
                    add_offbeat_bass_bar(note_tracks, bar_index, chord, velocity=74)
        reduce_notes_in_sections(note_tracks, "rolling_bass", drops + builds, keep_ratio=0.3, min_notes_per_bar=1)
        for stem in ("offbeat_bass", "rolling_bass"):
            for section in drops + builds:
                for note_data in section_note_slice(note_tracks[stem], section["start_bar"], section["end_bar"]):
                    note_data["velocity"] = clamp(note_data["velocity"] - 8, 1, 124)


def validate_identity_bass_behavior(note_tracks, blueprint, sections):
    drops = [section for section in sections if section_kind(section["name"]) == "drop"]
    verses = [section for section in sections if section_kind(section["name"]) == "verse"]
    builds = [section for section in sections if section_kind(section["name"]) == "build"]
    key = blueprint.get("track_identity_key", "")
    target = blueprint.get("identity_bass_style", "")
    offbeat_count = len(note_tracks["offbeat_bass"])
    rolling_count = len(note_tracks["rolling_bass"])
    drop_offbeat_count = sum(len(section_note_slice(note_tracks["offbeat_bass"], section["start_bar"], section["end_bar"])) for section in drops)
    drop_rolling_count = sum(len(section_note_slice(note_tracks["rolling_bass"], section["start_bar"], section["end_bar"])) for section in drops)
    verse_build_offbeat_count = sum(len(section_note_slice(note_tracks["offbeat_bass"], section["start_bar"], section["end_bar"])) for section in verses + builds)
    passed = True
    failures = []
    if target == "offbeat_plus_rolling" or key == "ANTHEMIC_UPLIFTING":
        if offbeat_count <= 0:
            passed = False
            failures.append("offbeat_bass_empty")
        if drop_offbeat_count <= 0:
            passed = False
            failures.append("drop_offbeat_missing")
        if drop_rolling_count <= 0:
            passed = False
            failures.append("drop_rolling_missing")
        if rolling_count > max(1, offbeat_count) * 12:
            passed = False
            failures.append("rolling_overwhelms_offbeat")
    elif key == "CLASSIC_2000S_TRANCE":
        if offbeat_count <= 0 or drop_offbeat_count <= 0:
            passed = False
            failures.append("classic_offbeat_missing")
        if rolling_count > max(1, offbeat_count) * 6:
            passed = False
            failures.append("classic_rolling_too_dominant")
    elif key == "ORCHESTRAL_UPLIFTING":
        if rolling_count > max(1, offbeat_count + 32) * 8:
            passed = False
            failures.append("orchestral_rolling_too_dominant")
    return {
        "offbeat_bass_note_count": offbeat_count,
        "rolling_bass_note_count": rolling_count,
        "drop_offbeat_bass_note_count": drop_offbeat_count,
        "drop_rolling_bass_note_count": drop_rolling_count,
        "verse_build_offbeat_bass_note_count": verse_build_offbeat_count,
        "bass_behavior_target": target,
        "bass_identity_passed": passed,
        "bass_identity_failed_checks": ",".join(failures) if failures else "none",
    }


def validate_uplifting_subtype_contrast(note_tracks, blueprint, sections):
    if blueprint.get("genre") != "uplifting":
        return {"identity_contrast_score": 0, "identity_contrast_failed_checks": "not_uplifting_genre"}
    key = blueprint.get("track_identity_key", "")
    intro = [section for section in sections if section_kind(section["name"]) == "intro"]
    drops = [section for section in sections if section_kind(section["name"]) == "drop"]
    breakdowns = [section for section in sections if section_kind(section["name"]) == "breakdown"]
    checks = []
    score = 0
    metrics = {
        "intro_piano": stem_density_in_sections(note_tracks, "piano", intro),
        "intro_strings": stem_density_in_sections(note_tracks, "strings", intro),
        "intro_arp": stem_density_in_sections(note_tracks, "arp", intro),
        "intro_pluck": stem_density_in_sections(note_tracks, "pluck", intro),
        "first16_arp": stem_density_in_sections(note_tracks, "arp", [first_bars_window(sections, 16)]),
        "first16_supersaw": stem_density_in_sections(note_tracks, "supersaw_chords", [first_bars_window(sections, 16)]),
        "drop_offbeat": stem_density_in_sections(note_tracks, "offbeat_bass", drops),
        "drop_rolling": stem_density_in_sections(note_tracks, "rolling_bass", drops),
        "drop_lead": stem_density_in_sections(note_tracks, "lead", drops),
        "drop_saw": stem_density_in_sections(note_tracks, "supersaw_chords", drops),
        "breakdown_piano": stem_density_in_sections(note_tracks, "piano", breakdowns),
        "breakdown_strings": stem_density_in_sections(note_tracks, "strings", breakdowns),
        "breakdown_arp": stem_density_in_sections(note_tracks, "arp", breakdowns),
        "breakdown_vocal": stem_density_in_sections(note_tracks, "vocal_melody", breakdowns),
    }
    if key == "ANTHEMIC_UPLIFTING":
        anthemic_arp_intro_ok = (
            blueprint.get("variation_type") == "ARP_DRIVEN"
            and metrics["first16_arp"] >= 3.0
            and metrics["first16_supersaw"] <= 1.0
            and metrics["drop_saw"] >= 4.0
        )
        checks = [
            ("anthemic_offbeat_present", metrics["drop_offbeat"] >= 1.5),
            ("anthemic_rolling_present", metrics["drop_rolling"] >= 1.0),
            ("anthemic_supersaw_strong", metrics["drop_saw"] >= 4.0),
            ("anthemic_not_classic_arp_led", metrics["intro_arp"] < 3.0 or anthemic_arp_intro_ok),
        ]
    elif key == "CLASSIC_2000S_TRANCE":
        checks = [
            ("classic_intro_arp_strong", metrics["intro_arp"] >= 3.0),
            ("classic_pluck_present", metrics["intro_pluck"] >= 0.4 or metrics["breakdown_arp"] >= 3.0),
            ("classic_arp_above_orchestral_level", metrics["breakdown_arp"] >= 2.0),
            ("classic_arp_identity_clearly_present", metrics["intro_arp"] + metrics["breakdown_arp"] >= 8.0),
        ]
    elif key == "ORCHESTRAL_UPLIFTING":
        checks = [
            ("orchestral_intro_piano_strings", metrics["intro_piano"] >= 0.8 and metrics["intro_strings"] >= 1.0),
            ("orchestral_breakdown_piano_strings", metrics["breakdown_piano"] >= 0.8 and metrics["breakdown_strings"] >= 1.0),
            ("orchestral_arp_restrained", metrics["breakdown_arp"] <= 2.5),
            ("orchestral_piano_strings_outweigh_arp", metrics["breakdown_piano"] + metrics["breakdown_strings"] > metrics["breakdown_arp"]),
        ]
    elif key == "EMOTIONAL_VOCAL_TRANCE":
        checks = [
            ("vocal_breakdown_prominent", metrics["breakdown_vocal"] >= 0.4),
            ("vocal_intro_or_breakdown_space", metrics["drop_lead"] <= 2.0),
            ("vocal_arp_restrained", metrics["breakdown_arp"] <= 2.5),
            ("vocal_voice_exceeds_lead_density", metrics["breakdown_vocal"] > metrics["drop_lead"]),
        ]
    else:
        checks = [("non_uplifting_subtype", True)]
    failed = [name for name, ok in checks if not ok]
    score = int(round(100 * (len(checks) - len(failed)) / max(1, len(checks))))
    return {
        "identity_contrast_score": score,
        "identity_contrast_failed_checks": ",".join(failed) if failed else "none",
        "identity_contrast_metrics": ",".join(f"{key}={value}" for key, value in metrics.items()),
    }


def validate_identity_expression(note_tracks, blueprint, sections):
    failed = []
    score = 0
    identity_key = blueprint.get("track_identity_key", "")
    targets = blueprint.get("identity_density_targets", {})
    selected = blueprint.get("selected_chord_progression", "")
    genre = blueprint.get("genre", selected)
    if selected == genre and selected in PROGRESSIONS:
        score += 15
    else:
        failed.append("genre_progression_mismatch")
    intro = next((section for section in sections if section_kind(section["name"]) == "intro"), None)
    intro_notes = []
    if intro:
        for stem in STEMS:
            intro_notes.extend(section_note_slice(note_tracks[stem], intro["start_bar"], min(intro["end_bar"], intro["start_bar"] + 8)))
    intro_stems = {
        stem for stem in STEMS
        if intro and section_note_slice(note_tracks[stem], intro["start_bar"], min(intro["end_bar"], intro["start_bar"] + 8))
    }
    signature = blueprint.get("identity_validation_targets", {}).get("intro_signature", "")
    intro_ok = bool(intro_notes)
    if signature == "piano_strings":
        intro_ok = {"piano", "strings"}.issubset(intro_stems)
    elif signature == "arp_or_pluck":
        intro_ok = bool({"arp", "pluck"} & intro_stems)
    elif signature == "drums_or_bass":
        intro_ok = bool({"kick", "rolling_bass", "offbeat_bass"} & intro_stems)
    elif signature == "vocal_or_piano":
        intro_ok = bool({"vocal_melody", "piano"} & intro_stems)
    elif signature == "low_dark_pad":
        intro_ok = "pad" in intro_stems or "strings" in intro_stems
    elif signature == "pad_or_supersaw":
        intro_ok = "pad" in intro_stems or "supersaw_chords" in intro_stems
    if intro_ok:
        score += 15
    else:
        failed.append("intro_signature_missing")
    total_bars = max((section["end_bar"] for section in sections), default=1)
    lead_density = len(note_tracks["lead"]) / max(1, total_bars)
    arp_density = len(note_tracks["arp"]) / max(1, total_bars)
    saw_density = len(note_tracks["supersaw_chords"]) / max(1, total_bars)
    bass_density = (len(note_tracks["offbeat_bass"]) + len(note_tracks["rolling_bass"])) / max(1, total_bars)
    if lead_density <= targets.get("lead_max", 99):
        score += 10
    else:
        failed.append("lead_density_outside_identity")
    if arp_density <= targets.get("arp_max", 99) and arp_density >= targets.get("arp_min", 0):
        score += 10
    else:
        failed.append("arp_density_outside_identity")
    if saw_density <= targets.get("supersaw_max", 99) and saw_density >= targets.get("supersaw_min", 0):
        score += 10
    else:
        failed.append("supersaw_density_outside_identity")
    if bass_density <= targets.get("bass_max", 99) and bass_density >= targets.get("bass_min", 0):
        score += 10
    else:
        failed.append("bass_density_outside_identity")
    breakdown = next((section for section in sections if section_kind(section["name"]) == "breakdown"), None)
    if breakdown:
        breakdown_stems = {
            stem for stem in ("pad", "strings", "piano", "arp", "vocal_melody")
            if section_note_slice(note_tracks[stem], breakdown["start_bar"], breakdown["end_bar"])
        }
        focus = blueprint.get("identity_validation_targets", {}).get("breakdown_focus", "")
        breakdown_ok = True
        if focus in ("piano_strings", "orchestral"):
            breakdown_ok = {"piano", "strings"}.issubset(breakdown_stems)
        elif focus == "vocal_piano":
            breakdown_ok = "piano" in breakdown_stems and "vocal_melody" in breakdown_stems
        elif focus in ("pad", "dark"):
            breakdown_ok = "pad" in breakdown_stems or "strings" in breakdown_stems
        elif focus == "pad_arp":
            breakdown_ok = "pad" in breakdown_stems and "arp" in breakdown_stems
        if breakdown_ok:
            score += 15
        else:
            failed.append("breakdown_focus_missing")
    else:
        failed.append("breakdown_missing")
    if blueprint.get("identity_drop_style"):
        score += 10
    return {
        "identity_expression_score": min(100, score),
        "identity_failed_checks": ",".join(failed) if failed else "none",
    }


def apply_breakdown_identity_override(identity_report, arrangement_report):
    if not arrangement_report.get("breakdown_identity_passed"):
        return identity_report
    failed_checks = [
        item for item in identity_report.get("identity_failed_checks", "").split(",")
        if item and item != "none"
    ]
    if "breakdown_focus_missing" not in failed_checks:
        return identity_report
    failed_checks = [item for item in failed_checks if item != "breakdown_focus_missing"]
    identity_report["identity_failed_checks"] = ",".join(failed_checks) if failed_checks else "none"
    identity_report["identity_expression_score"] = min(100, identity_report.get("identity_expression_score", 0) + 15)
    return identity_report


def apply_track_identity_postprocess(tracks, sections, chords, blueprint):
    note_tracks = {stem: events_to_notes(events) for stem, events in tracks.items()}
    apply_arrangement_story_gates(note_tracks, sections, blueprint)
    apply_identity_intro_signature(note_tracks, sections, chords, blueprint)
    scale_identity_section_notes(note_tracks, sections, blueprint)
    apply_identity_breakdown_signature(note_tracks, sections, chords, blueprint)
    apply_uplifting_subtype_contrast(note_tracks, sections, chords, blueprint)
    enforce_identity_bass_behavior(note_tracks, sections, chords, blueprint)
    apply_arrangement_story_gates(note_tracks, sections, blueprint)
    apply_variation_enforcement(note_tracks, sections, chords, blueprint)
    enforce_breakdown_identity_focus(note_tracks, sections, chords, blueprint)
    apply_arrangement_drop2_energy(note_tracks, sections, blueprint)
    identity_report = validate_identity_expression(note_tracks, blueprint, sections)
    arrangement_report = validate_arrangement_story(note_tracks, blueprint, sections)
    identity_report = apply_breakdown_identity_override(identity_report, arrangement_report)
    identity_report.update(arrangement_report)
    identity_report.update(validate_uplifting_subtype_contrast(note_tracks, blueprint, sections))
    identity_report.update(validate_identity_bass_behavior(note_tracks, blueprint, sections))
    blueprint.setdefault("validation_report", {}).update(identity_report)
    for stem in tracks:
        tracks[stem] = notes_to_events(sorted(note_tracks[stem], key=lambda item: (item["start"], item["pitch"])))
    return tracks, blueprint


def create_track_story(identity, variation, progression, key):
    identity_key = str(identity.get("track_identity_key", identity.get("track_identity", ""))).upper()
    variation_type = str(identity.get("variation_type", variation or "DEFAULT")).upper()
    if "ORCHESTRAL" in identity_key or variation_type in ("PIANO_INTRO", "PIANO_BREAK", "PIANO_CONFESSION"):
        story_type = "piano_confession"
        main_owner = "piano"
        secondary_owner = "strings"
        arc = ["mystery", "longing", "tension", "release", "reset", "final_lift"]
    elif "VOCAL" in identity_key or "LATE_HOOK" in variation_type:
        story_type = "vocal_longing"
        main_owner = "vocal_melody"
        secondary_owner = "piano"
        arc = ["space", "longing", "answer", "release", "confession", "final_lift"]
    elif "CLASSIC" in identity_key:
        story_type = "classic_arp_memory"
        main_owner = "arp"
        secondary_owner = "lead"
        arc = ["memory", "motion", "tension", "hook", "recall", "final_lift"]
    elif "DARK" in identity_key:
        story_type = "dark_release"
        main_owner = "lead"
        secondary_owner = "strings"
        arc = ["mystery", "pressure", "tension", "release", "shadow", "final_lift"]
    else:
        story_type = "anthemic_lift"
        main_owner = "lead"
        secondary_owner = "piano"
        arc = ["mystery", "longing", "tension", "release", "reset", "final_lift"]
    return {
        "story_type": story_type,
        "emotional_arc": arc,
        "main_motif_owner": main_owner,
        "secondary_motif_owner": secondary_owner,
        "shiver_moment_section": "Build 2",
        "motif_reveal_plan": {
            "Intro": "tease",
            "Verse": "rhythmic_fragment",
            "Build": "tension_fragment",
            "Drop 1": "first_full_hook",
            "Breakdown": "emotional_expansion",
            "Build 2": "rising_variation",
            "Drop 2": "maximum_payoff",
            "Outro": "memory_fragment",
        },
        "progression": progression,
        "key": key,
    }


def create_core_motif(key, progression, identity, story_type):
    phrase_models = {
        "piano_confession": "QUESTION_ANSWER",
        "vocal_longing": "CALL_RESPONSE",
        "classic_arp_memory": "AABB",
        "dark_release": "RISE_AND_RELEASE",
        "anthemic_lift": "AABA",
    }
    contours = {
        "piano_confession": "question_answer",
        "vocal_longing": "arch",
        "classic_arp_memory": "rise",
        "dark_release": "arch",
        "anthemic_lift": "rise",
    }
    rhythm_signatures = {
        "piano_confession": "held_peak",
        "vocal_longing": "long_short_long",
        "classic_arp_memory": "classic_trance",
        "dark_release": "syncopated_answer",
        "anthemic_lift": "long_short_long",
    }
    motif_templates = {
        "piano_confession": [
            (0, 0.0, 3, 1.5, 86), (1, 2.0, 5, 1.0, 82),
            (2, 0.0, 3, 1.5, 86), (3, 2.0, 1, 1.25, 84),
            (4, 0.0, 5, 1.25, 88), (5, 2.0, 6, 1.0, 86),
            (6, 0.0, 5, 1.5, 92), (7, 2.0, 1, 2.0, 96),
        ],
        "vocal_longing": [
            (0, 0.0, 5, 1.25, 86), (1, 2.5, 3, 1.0, 82),
            (2, 0.0, 5, 1.25, 86), (3, 2.0, 1, 1.5, 84),
            (4, 0.0, 3, 1.25, 88), (5, 2.0, 5, 1.25, 88),
            (6, 0.0, 6, 1.0, 90), (7, 1.5, 1, 2.0, 96),
        ],
        "classic_arp_memory": [
            (0, 0.0, 1, 0.75, 82), (0, 1.5, 3, 0.75, 80), (1, 3.0, 5, 1.0, 84),
            (2, 0.0, 1, 0.75, 82), (2, 1.5, 3, 0.75, 80), (3, 3.0, 5, 1.0, 84),
            (4, 0.0, 3, 0.75, 86), (4, 1.5, 5, 0.75, 84), (5, 3.0, 1, 1.0, 88),
            (6, 0.0, 5, 1.25, 90), (7, 2.0, 1, 1.75, 94),
        ],
        "dark_release": [
            (0, 0.0, 1, 1.0, 84), (1, 2.0, 3, 1.0, 82),
            (2, 0.0, 1, 1.0, 84), (3, 2.0, 5, 1.25, 86),
            (4, 0.0, 3, 1.0, 88), (5, 2.0, 6, 1.0, 88),
            (6, 0.0, 5, 1.5, 92), (7, 2.0, 1, 2.0, 96),
        ],
        "anthemic_lift": [
            (0, 0.0, 5, 1.5, 88), (1, 2.5, 3, 0.75, 84),
            (2, 0.0, 5, 1.5, 88), (3, 2.5, 3, 0.75, 84),
            (4, 0.0, 6, 1.0, 90), (5, 2.0, 5, 1.25, 90),
            (6, 0.0, 5, 1.5, 94), (7, 1.5, 1, 2.25, 100),
        ],
    }
    notes = [
        {"bar": bar, "beat": beat, "degree": degree, "duration": duration, "velocity": velocity}
        for bar, beat, degree, duration, velocity in motif_templates.get(story_type, motif_templates["anthemic_lift"])
    ]
    return {
        "motif_id": f"{story_type}_{key}_{progression}",
        "length_bars": 8,
        "notes": notes,
        "contour": contours.get(story_type, "rise"),
        "rhythm_signature": rhythm_signatures.get(story_type, "long_short_long"),
        "phrase_model": phrase_models.get(story_type, "AABA"),
        "resolution_degree": 1,
        "hook_strength_target": 80,
    }


def motif_degree_pitch(chord, degree, register_low=60, register_high=88, octave_shift=12):
    tone_map = {
        1: chord["root"],
        2: chord["third"],
        3: chord["third"],
        4: chord["fifth"],
        5: chord["fifth"],
        6: chord["root"] + 12,
        7: chord["third"] + 12,
    }
    pitch = tone_map.get(int(degree), chord["root"]) + octave_shift
    while pitch < register_low:
        pitch += 12
    while pitch > register_high:
        pitch -= 12
    return clamp(pitch, register_low, register_high)


def develop_motif_for_section(core_motif, section_name, role, energy_level):
    plan = {
        "Intro": {"mode": "tease", "bars": 2, "density": "sparse", "register_shift": -12, "velocity_delta": -20, "duration_scale": 1.2},
        "Verse": {"mode": "rhythmic_fragment", "bars": 4, "density": "medium", "register_shift": -7, "velocity_delta": -14, "duration_scale": 0.9},
        "Build": {"mode": "tension_fragment", "bars": 4, "density": "medium", "register_shift": -2, "velocity_delta": -6, "duration_scale": 0.8},
        "Drop 1": {"mode": "first_full_hook", "bars": 8, "density": "full", "register_shift": 0, "velocity_delta": 2, "duration_scale": 1.0},
        "Breakdown": {"mode": "emotional_expansion", "bars": 8, "density": "sparse", "register_shift": -12, "velocity_delta": -12, "duration_scale": 1.45},
        "Build 2": {"mode": "rising_variation", "bars": 4, "density": "medium", "register_shift": 5, "velocity_delta": 0, "duration_scale": 0.85},
        "Drop 2": {"mode": "maximum_payoff", "bars": 8, "density": "full", "register_shift": 7, "velocity_delta": 10, "duration_scale": 1.08},
        "Outro": {"mode": "memory_fragment", "bars": 2, "density": "sparse", "register_shift": -12, "velocity_delta": -24, "duration_scale": 1.0},
    }.get(section_name, {"mode": "fragment", "bars": 4, "density": "medium", "register_shift": 0, "velocity_delta": -8, "duration_scale": 1.0})
    allowed_bars = plan["bars"]
    notes = []
    for note_data in core_motif["notes"]:
        if note_data["bar"] >= allowed_bars:
            continue
        if plan["density"] == "sparse" and note_data["bar"] % 2 == 1 and note_data["beat"] < 2.0:
            continue
        edited = dict(note_data)
        edited["duration"] = round(max(0.75, edited["duration"] * plan["duration_scale"]), 2)
        edited["velocity"] = clamp(edited["velocity"] + plan["velocity_delta"], 40, 118)
        if plan["mode"] in ("rising_variation", "maximum_payoff") and edited["bar"] >= max(0, allowed_bars - 2):
            edited["degree"] = 6 if edited["degree"] in (3, 5) else edited["degree"]
        notes.append(edited)
    return {**plan, "notes": notes}


def motif_notes_to_stem_notes(motif_version, section, chords, stem, repeat=True):
    notes = []
    if not motif_version["notes"]:
        return notes
    bars_per_cycle = max(1, motif_version["bars"])
    cycles = max(1, section["bars"] // bars_per_cycle) if repeat else 1
    ranges = {
        "lead": (72, 86, 12),
        "piano": (60, 78, 0),
        "arp": (60, 78, 0),
        "pluck": (64, 82, 0),
        "vocal_melody": (65, 84, 0),
        "countermelody": (67, 88, 0),
    }
    low, high, octave_shift = ranges.get(stem, (60, 86, 0))
    for cycle in range(cycles):
        cycle_start = section["start_bar"] + cycle * bars_per_cycle
        for item in motif_version["notes"]:
            target_bar = cycle_start + item["bar"]
            if target_bar >= section["end_bar"]:
                continue
            chord = chords[target_bar % len(chords)]
            pitch = motif_degree_pitch(chord, item["degree"], low, high, octave_shift)
            if motif_version["mode"] == "maximum_payoff" and item["bar"] >= bars_per_cycle - 2 and stem in ("lead", "countermelody"):
                pitch = clamp(pitch + 7, low, high)
            if motif_version["mode"] == "rising_variation" and stem in ("lead", "vocal_melody"):
                pitch = clamp(pitch + 5, low, high)
            start = bar_tick(target_bar) + tick(item["beat"])
            end = min(bar_tick(target_bar + 1), start + tick(item["duration"]))
            notes.append({"start": start, "end": max(start + tick(0.75), end), "pitch": pitch, "velocity": item["velocity"], "channel": 0})
    return sorted(notes, key=lambda data: (data["start"], data["pitch"]))


def assign_motif_to_stems(story, section_name):
    owner = story["main_motif_owner"]
    secondary = story["secondary_motif_owner"]
    if section_name == "Intro":
        return [owner if owner in ("piano", "arp", "vocal_melody") else secondary]
    if section_name == "Verse":
        return ["arp" if owner != "arp" else "pluck"]
    if section_name == "Build":
        return ["lead" if owner != "vocal_melody" else "vocal_melody"]
    if section_name == "Drop 1":
        return ["lead"]
    if section_name == "Breakdown":
        return ["piano", "vocal_melody"] if owner == "vocal_melody" else ["piano"]
    if section_name == "Build 2":
        return ["lead", "countermelody"] if owner != "vocal_melody" else ["vocal_melody", "lead"]
    if section_name == "Drop 2":
        return ["lead", "countermelody"]
    if section_name == "Outro":
        return [secondary if secondary in ("piano", "arp", "pluck") else "piano"]
    return ["lead"]


def create_shiver_moment(story, core_motif, section, chords):
    shiver_bar = max(section["start_bar"], section["end_bar"] - 1)
    return {
        "section": section["name"],
        "bar": shiver_bar + 1,
        "type": "half_bar_silence_then_octave_lead",
        "description": "Motif pauses before returning higher and stronger in Drop 2.",
    }


def apply_shiver_moment(note_tracks, shiver, sections, chords):
    build2 = next((section for section in sections if section["name"] == shiver["section"]), None)
    drop2 = next((section for section in sections if section["name"] == "Drop 2"), None)
    if not build2 or not drop2:
        return
    gap_start = bar_tick(build2["end_bar"]) - tick(0.5)
    gap_end = bar_tick(build2["end_bar"])
    for stem in ("lead", "countermelody", "vocal_melody", "arp", "pluck"):
        note_tracks[stem] = [
            n for n in note_tracks[stem]
            if not (gap_start <= n["start"] < gap_end)
        ]
    chord = chords[drop2["start_bar"] % len(chords)]
    pitch = motif_degree_pitch(chord, 1, 78, 88, 12)
    note_tracks["lead"].append({
        "start": bar_tick(drop2["start_bar"]),
        "end": bar_tick(drop2["start_bar"]) + tick(2.0),
        "pitch": pitch,
        "velocity": 112,
        "channel": 0,
    })


def section_register_limits(section_name, local_bar=0, section_bars=1):
    if section_name == "Intro":
        return {"default": (36, 76), "supersaw_chords": (43, 76), "piano": (48, 72), "strings": (48, 72), "pad": (43, 74)}
    if section_name == "Breakdown":
        return {"default": (43, 80), "lead": (60, 78), "vocal_melody": (58, 78), "piano": (48, 78), "strings": (48, 79), "supersaw_chords": (48, 76)}
    if "Build" in section_name:
        rise = int(6 * (local_bar / max(1, section_bars - 1)))
        return {"default": (43, 78 + rise), "lead": (64, 80 + rise), "supersaw_chords": (48, 78 + rise), "piano": (48, 76 + rise)}
    if section_name == "Drop 1":
        return {"default": (36, 86), "lead": (68, 86), "supersaw_chords": (43, 84), "strings": (48, 82), "piano": (48, 80)}
    if section_name == "Drop 2":
        return {"default": (36, 90), "lead": (70, 88), "supersaw_chords": (43, 88), "strings": (48, 84), "piano": (48, 82)}
    return {"default": (36, 86)}


def clamp_pitch_into_register(pitch, low, high):
    while pitch > high:
        pitch -= 12
    while pitch < low:
        pitch += 12
    return clamp(pitch, low, high)


def chord_tone_pitch_classes(chord):
    return {chord["root"] % 12, chord["third"] % 12, chord["fifth"] % 12}


def scale_pitch_classes_for_key(key):
    root_pc = NOTE[key] % 12
    return {(root_pc + interval) % 12 for interval in SCALE}


def nearest_pitch_from_classes(source_pitch, allowed_classes, low=0, high=127):
    best = clamp(source_pitch, low, high)
    best_dist = 999
    for candidate in range(low, high + 1):
        if candidate % 12 in allowed_classes:
            dist = abs(candidate - source_pitch)
            if dist < best_dist:
                best = candidate
                best_dist = dist
    return best


def nearest_chord_tone(source_pitch, chord, low=0, high=127, prefer_root_fifth=False):
    allowed = {chord["root"] % 12, chord["fifth"] % 12} if prefer_root_fifth else chord_tone_pitch_classes(chord)
    return nearest_pitch_from_classes(source_pitch, allowed, low, high)


def apply_section_register_constraints(note_tracks, sections):
    report = {"intro_avg_pitch": 0, "intro_register_warnings": []}
    constrained_stems = ("lead", "supersaw_chords", "pad", "arp", "pluck", "strings", "piano", "countermelody", "vocal_melody")
    intro_pitches = []
    for section in sections:
        for bar_index in range(section["start_bar"], section["end_bar"]):
            local_bar = bar_index - section["start_bar"]
            limits = section_register_limits(section["name"], local_bar, section["bars"])
            for stem in constrained_stems:
                low, high = limits.get(stem, limits["default"])
                fixed_bar = []
                for note_data in notes_starting_in_bar(note_tracks[stem], bar_index):
                    fixed = dict(note_data)
                    fixed["pitch"] = clamp_pitch_into_register(fixed["pitch"], low, high)
                    fixed_bar.append(fixed)
                    if section["name"] == "Intro":
                        intro_pitches.append(fixed["pitch"])
                note_tracks[stem] = replace_notes_in_bar_range(note_tracks[stem], bar_index, bar_index + 1, fixed_bar)
    report["intro_avg_pitch"] = round(sum(intro_pitches) / max(1, len(intro_pitches)), 2)
    if report["intro_avg_pitch"] > 74:
        report["intro_register_warnings"].append("intro_average_pitch_too_high")
    return report


def enforce_v11_1_lead_lengths(note_tracks, sections, chords):
    report = {"lead_avg_duration": 0, "lead_duration_warnings": [], "lead_length_repairs": 0, "drop2_held_hook_added": False}
    lead_lengths = []
    for section in sections:
        if section["name"] not in ("Drop 1", "Drop 2", "Breakdown", "Build", "Build 2"):
            continue
        for bar_index in range(section["start_bar"], section["end_bar"]):
            for stem in ("lead", "vocal_melody"):
                fixed_bar = []
                min_len = 1.25 if section["name"] == "Breakdown" else 0.9 if "Drop" in section["name"] else 0.75
                for note_data in notes_starting_in_bar(note_tracks[stem], bar_index):
                    fixed = dict(note_data)
                    old_end = fixed["end"]
                    fixed["end"] = max(fixed["end"], fixed["start"] + tick(min_len))
                    fixed["end"] = min(fixed["end"], bar_tick(bar_index + 1))
                    if fixed["end"] != old_end:
                        report["lead_length_repairs"] += 1
                    fixed_bar.append(fixed)
                if "Drop" in section["name"] and stem == "lead" and len(fixed_bar) > 3:
                    fixed_bar = sorted(fixed_bar, key=lambda n: (-(n["end"] - n["start"]), n["start"]))[:3]
                note_tracks[stem] = replace_notes_in_bar_range(note_tracks[stem], bar_index, bar_index + 1, fixed_bar)
    drop2 = next((section for section in sections if section["name"] == "Drop 2"), None)
    if drop2:
        drop2_lead = [n for n in note_tracks["lead"] if bar_tick(drop2["start_bar"]) <= n["start"] < bar_tick(min(drop2["end_bar"], drop2["start_bar"] + 8))]
        if not any(length_beats(n) >= 1.5 for n in drop2_lead):
            chord = chords[drop2["start_bar"] % len(chords)]
            note_tracks["lead"].append({
                "start": bar_tick(drop2["start_bar"] + 1),
                "end": bar_tick(drop2["start_bar"] + 1) + tick(2.0),
                "pitch": motif_degree_pitch(chord, 5, 72, 88, 12),
                "velocity": 108,
                "channel": 0,
            })
            report["drop2_held_hook_added"] = True
    for note_data in note_tracks["lead"]:
        lead_lengths.append(length_beats(note_data))
    report["lead_avg_duration"] = round(sum(lead_lengths) / max(1, len(lead_lengths)), 3)
    if report["lead_avg_duration"] < 0.85:
        report["lead_duration_warnings"].append("lead_average_duration_too_short")
    return report


def lock_strings_to_uplifting_chord_tones(note_tracks, sections, chords):
    report = {"string_non_chord_repairs": 0, "string_density_repairs": 0, "string_warnings": []}
    for section in sections:
        for bar_index in range(section["start_bar"], section["end_bar"]):
            chord = chords[bar_index % len(chords)]
            fixed_bar = []
            for note_data in sorted(notes_starting_in_bar(note_tracks["strings"], bar_index), key=lambda n: (n["start"], n["pitch"])):
                fixed = dict(note_data)
                pitch = nearest_chord_tone(fixed["pitch"], chord, 43, 84)
                if pitch % 12 not in chord_tone_pitch_classes(chord):
                    report["string_non_chord_repairs"] += 1
                if pitch != fixed["pitch"]:
                    report["string_non_chord_repairs"] += 1
                fixed["pitch"] = pitch
                min_len = 2.0 if section["name"] == "Breakdown" else 1.0
                fixed["end"] = max(fixed["end"], fixed["start"] + tick(min_len))
                fixed["end"] = min(fixed["end"], bar_tick(min(section["end_bar"], bar_index + 2)))
                fixed_bar.append(fixed)
            if len(fixed_bar) > 2:
                fixed_bar = sorted(fixed_bar, key=lambda n: (-(n["end"] - n["start"]), n["pitch"]))[:2]
                report["string_density_repairs"] += 1
            note_tracks["strings"] = replace_notes_in_bar_range(note_tracks["strings"], bar_index, bar_index + 1, fixed_bar)
    if report["string_non_chord_repairs"]:
        report["string_warnings"].append("strings_non_chord_tones_corrected")
    return report


def improve_v11_1_breakdown_emotion(note_tracks, sections, chords, blueprint):
    report = {"breakdown_emotion_repairs": 0, "breakdown_allowed_stems": "piano,pad,strings"}
    breakdown = next((section for section in sections if section["name"] == "Breakdown"), None)
    if not breakdown:
        return report
    vocal_required = blueprint.get("v11_motif_story", {}).get("main_motif_owner") == "vocal_melody" or "VOCAL" in blueprint.get("track_identity", "")
    forbidden = ["rolling_bass", "offbeat_bass", "sub_bass", "arp", "pluck", "lead", "countermelody"]
    if not vocal_required:
        forbidden.append("vocal_melody")
    for stem in forbidden:
        before = len(note_tracks[stem])
        note_tracks[stem] = remove_notes_in_bar_range(note_tracks[stem], breakdown["start_bar"], breakdown["end_bar"])
        if len(note_tracks[stem]) != before:
            report["breakdown_emotion_repairs"] += 1
    piano_notes = [n for n in note_tracks["piano"] if bar_tick(breakdown["start_bar"]) <= n["start"] < bar_tick(breakdown["end_bar"])]
    if not piano_notes:
        for bar_index in range(breakdown["start_bar"], breakdown["end_bar"], 2):
            chord = chords[bar_index % len(chords)]
            note_tracks["piano"].append({
                "start": bar_tick(bar_index),
                "end": bar_tick(bar_index) + tick(2.0),
                "pitch": motif_degree_pitch(chord, 3, 60, 78, 0),
                "velocity": 78,
                "channel": 0,
            })
        report["breakdown_emotion_repairs"] += 1
    pad_notes = [n for n in note_tracks["pad"] if bar_tick(breakdown["start_bar"]) <= n["start"] < bar_tick(breakdown["end_bar"])]
    if not pad_notes:
        for bar_index in range(breakdown["start_bar"], breakdown["end_bar"], 2):
            chord = chords[bar_index % len(chords)]
            for pitch in (chord["root"] - 12, chord["fifth"], chord["third"]):
                note_tracks["pad"].append({
                    "start": bar_tick(bar_index),
                    "end": bar_tick(min(breakdown["end_bar"], bar_index + 2)),
                    "pitch": clamp_pitch_into_register(pitch, 43, 76),
                    "velocity": 58,
                    "channel": 0,
                })
        report["breakdown_emotion_repairs"] += 1
    return report


def final_scale_lock_postprocess(note_tracks, sections, chords, key):
    report = {"scale_lock_repairs": 0, "scale_lock_warnings": []}
    scale_classes = scale_pitch_classes_for_key(key)
    bass_stems = ("offbeat_bass", "rolling_bass", "sub_bass")
    chord_priority_stems = ("strings", "supersaw_chords", "piano", "pad")
    melodic_stems = ("lead", "arp", "pluck", "countermelody", "vocal_melody")
    for section in sections:
        for bar_index in range(section["start_bar"], section["end_bar"]):
            chord = chords[bar_index % len(chords)]
            for stem in bass_stems + chord_priority_stems + melodic_stems:
                fixed_bar = []
                for note_data in notes_starting_in_bar(note_tracks[stem], bar_index):
                    fixed = dict(note_data)
                    original = fixed["pitch"]
                    if stem in bass_stems:
                        fixed["pitch"] = nearest_chord_tone(original, chord, 24, 60, prefer_root_fifth=True)
                    elif stem in chord_priority_stems:
                        fixed["pitch"] = nearest_chord_tone(original, chord, 36, 96)
                    elif original % 12 not in scale_classes:
                        fixed["pitch"] = nearest_pitch_from_classes(original, scale_classes, 48, 98)
                    if fixed["pitch"] != original:
                        report["scale_lock_repairs"] += 1
                    fixed_bar.append(fixed)
                note_tracks[stem] = replace_notes_in_bar_range(note_tracks[stem], bar_index, bar_index + 1, fixed_bar)
    if report["scale_lock_repairs"]:
        report["scale_lock_warnings"].append("out_of_key_notes_corrected")
    return report


def apply_v11_1_musical_corrections(note_tracks, sections, chords, blueprint):
    report = {}
    report.update(apply_section_register_constraints(note_tracks, sections))
    report.update(improve_v11_1_breakdown_emotion(note_tracks, sections, chords, blueprint))
    report.update(lock_strings_to_uplifting_chord_tones(note_tracks, sections, chords))
    report.update(enforce_v11_1_lead_lengths(note_tracks, sections, chords))
    report.update(final_scale_lock_postprocess(note_tracks, sections, chords, blueprint.get("selected_key", "C")))
    warnings = []
    warnings.extend(report.get("intro_register_warnings", []))
    warnings.extend(report.get("lead_duration_warnings", []))
    warnings.extend(report.get("string_warnings", []))
    warnings.extend(report.get("scale_lock_warnings", []))
    report["v11_1_warnings"] = sorted(set(warnings)) if warnings else ["none"]
    return report


def apply_phrase_gaps(notes_or_tracks, section):
    note_tracks = notes_or_tracks
    report = {"phrase_gaps_inserted": 0}
    melodic_stems = ("lead", "piano", "arp", "pluck", "countermelody", "vocal_melody")
    for local_bar in range(3, section["bars"], 4):
        gap_bar = section["start_bar"] + local_bar
        gap_start = bar_tick(gap_bar) + tick(3.0 if local_bar % 8 != 7 else 2.0)
        gap_end = bar_tick(gap_bar + 1)
        for stem in melodic_stems:
            before = len(note_tracks[stem])
            note_tracks[stem] = [n for n in note_tracks[stem] if not (gap_start <= n["start"] < gap_end)]
            report["phrase_gaps_inserted"] += max(0, before - len(note_tracks[stem]))
    if section["name"] == "Breakdown":
        for block_start in range(section["start_bar"], section["end_bar"], 2):
            rest_start = bar_tick(block_start + 1) + tick(3.0)
            rest_end = bar_tick(block_start + 2)
            for stem in ("piano", "vocal_melody"):
                before = len(note_tracks[stem])
                note_tracks[stem] = [n for n in note_tracks[stem] if not (rest_start <= n["start"] < rest_end)]
                report["phrase_gaps_inserted"] += max(0, before - len(note_tracks[stem]))
    if section["name"] in ("Build", "Build 2"):
        gap_start = bar_tick(section["end_bar"]) - tick(0.5)
        gap_end = bar_tick(section["end_bar"])
        before = len(note_tracks["lead"])
        note_tracks["lead"] = [n for n in note_tracks["lead"] if not (gap_start <= n["start"] < gap_end)]
        report["phrase_gaps_inserted"] += max(0, before - len(note_tracks["lead"]))
    return report


def apply_anticipation(section_data):
    note_tracks = section_data["note_tracks"]
    section = section_data["section"]
    report = {"anticipation_repairs": 0}
    if section["name"] not in ("Build", "Build 2"):
        return report
    final_bar = section["end_bar"] - 1
    for stem in ("supersaw_chords", "pad", "strings", "arp"):
        bar_notes = sorted(notes_starting_in_bar(note_tracks[stem], final_bar), key=lambda n: (n["start"], n["pitch"]))
        keep = bar_notes[:2] if stem in ("supersaw_chords", "pad", "strings") else bar_notes[:1]
        report["anticipation_repairs"] += max(0, len(bar_notes) - len(keep))
        note_tracks[stem] = replace_notes_in_bar_range(note_tracks[stem], final_bar, final_bar + 1, keep)
    lead_notes = notes_starting_in_bar(note_tracks["lead"], final_bar)
    bass_count = sum(len(notes_starting_in_bar(note_tracks[stem], final_bar)) for stem in ("offbeat_bass", "rolling_bass", "sub_bass"))
    if lead_notes and bass_count:
        before = len(note_tracks["lead"])
        note_tracks["lead"] = remove_notes_in_bar_range(note_tracks["lead"], final_bar, final_bar + 1)
        report["anticipation_repairs"] += before - len(note_tracks["lead"])
    return report


def strongest_two_bar_motif_segment(core_motif):
    best_start = 0
    best_score = -1
    for start_bar in range(0, max(1, core_motif["length_bars"] - 1)):
        segment = [n for n in core_motif["notes"] if start_bar <= n["bar"] < start_bar + 2]
        score = len(segment) * 8 + sum(10 for n in segment if n["duration"] >= 1.0) + sum(4 for n in segment if n["degree"] in (1, 3, 5))
        if score > best_score:
            best_start = start_bar
            best_score = score
    return [dict(n, bar=n["bar"] - best_start) for n in core_motif["notes"] if best_start <= n["bar"] < best_start + 2]


def reinforce_hook(core_motif, section, chords, repetitions=2, register_shift=0, velocity_delta=0):
    segment = strongest_two_bar_motif_segment(core_motif)
    notes = []
    for rep in range(repetitions):
        for item in segment:
            target_bar = section["start_bar"] + rep * 2 + item["bar"]
            if target_bar >= section["end_bar"]:
                continue
            chord = chords[target_bar % len(chords)]
            pitch = motif_degree_pitch(chord, item["degree"], 70, 88, 12)
            pitch = clamp_pitch_into_register(pitch + register_shift, 70, 88)
            start = bar_tick(target_bar) + tick(item["beat"])
            notes.append({
                "start": start,
                "end": min(bar_tick(target_bar + 1), start + tick(max(0.95, item["duration"]))),
                "pitch": pitch,
                "velocity": clamp(item["velocity"] + velocity_delta, 70, 118),
                "channel": 0,
            })
    return sorted(notes, key=lambda n: (n["start"], n["pitch"]))


def apply_drop_contrast(note_tracks, sections, chords, core_motif):
    report = {"hook_repetitions_drop1": 0, "hook_repetitions_drop2": 0, "drop_contrast_score": 0, "drop_contrast_warnings": []}
    drop1 = next((section for section in sections if section["name"] == "Drop 1"), None)
    drop2 = next((section for section in sections if section["name"] == "Drop 2"), None)
    if drop1:
        hook = reinforce_hook(core_motif, drop1, chords, 2, register_shift=0, velocity_delta=0)
        note_tracks["lead"] = replace_notes_in_bar_range(note_tracks["lead"], drop1["start_bar"], min(drop1["end_bar"], drop1["start_bar"] + 4), hook)
        report["hook_repetitions_drop1"] = 2
        for n in note_tracks["lead"]:
            if bar_tick(drop1["start_bar"]) <= n["start"] < bar_tick(drop1["end_bar"]):
                n["velocity"] = min(n["velocity"], 104)
    if drop2:
        hook = reinforce_hook(core_motif, drop2, chords, 3, register_shift=5, velocity_delta=10)
        note_tracks["lead"] = replace_notes_in_bar_range(note_tracks["lead"], drop2["start_bar"], min(drop2["end_bar"], drop2["start_bar"] + 6), hook)
        report["hook_repetitions_drop2"] = 3
        for stem in ("supersaw_chords", "countermelody"):
            for n in note_tracks[stem]:
                if bar_tick(drop2["start_bar"]) <= n["start"] < bar_tick(drop2["end_bar"]):
                    n["velocity"] = clamp(n["velocity"] + 8, 1, 122)
                    if stem == "countermelody":
                        n["pitch"] = clamp_pitch_into_register(n["pitch"] + 7, 60, 92)
    if drop1 and drop2:
        d1 = [n for stem in ("lead", "supersaw_chords", "countermelody") for n in note_tracks[stem] if bar_tick(drop1["start_bar"]) <= n["start"] < bar_tick(drop1["end_bar"])]
        d2 = [n for stem in ("lead", "supersaw_chords", "countermelody") for n in note_tracks[stem] if bar_tick(drop2["start_bar"]) <= n["start"] < bar_tick(drop2["end_bar"])]
        d1_vel = sum(n["velocity"] for n in d1) / max(1, len(d1))
        d2_vel = sum(n["velocity"] for n in d2) / max(1, len(d2))
        report["drop_contrast_score"] = round(70 + max(0, min(30, d2_vel - d1_vel)), 2)
        if report["drop_contrast_score"] < 78:
            report["drop_contrast_warnings"].append("drop contrast too weak")
    return report


def enhance_breakdown_emotion(note_tracks, sections, chords):
    report = {"breakdown_sustained_notes": 0, "breakdown_emotion_warnings": [], "breakdown_emotion_lift_added": False}
    breakdown = next((section for section in sections if section["name"] == "Breakdown"), None)
    if not breakdown:
        return report
    for bar_index in range(breakdown["start_bar"], breakdown["end_bar"]):
        piano_bar = sorted(notes_starting_in_bar(note_tracks["piano"], bar_index), key=lambda n: (n["start"], -(n["end"] - n["start"])))
        piano_bar = piano_bar[:3]
        if (bar_index - breakdown["start_bar"]) % 2 == 0 and not any(length_beats(n) >= 1.5 for n in piano_bar):
            chord = chords[bar_index % len(chords)]
            piano_bar.append({
                "start": bar_tick(bar_index),
                "end": bar_tick(bar_index) + tick(2.0),
                "pitch": motif_degree_pitch(chord, 3, 60, 78, 0),
                "velocity": 80,
                "channel": 0,
            })
        note_tracks["piano"] = replace_notes_in_bar_range(note_tracks["piano"], bar_index, bar_index + 1, piano_bar)
        report["breakdown_sustained_notes"] += sum(1 for n in piano_bar if length_beats(n) >= 1.5)
    for bar_index in range(max(breakdown["start_bar"], breakdown["end_bar"] - 2), breakdown["end_bar"]):
        chord = chords[bar_index % len(chords)]
        string_bar = []
        for degree, lift in ((1, 0), (5, 0), (6, 3)):
            pitch = motif_degree_pitch(chord, degree, 50, 84, 0) + lift
            string_bar.append({
                "start": bar_tick(bar_index),
                "end": bar_tick(bar_index + 1),
                "pitch": nearest_chord_tone(pitch, chord, 48, 84),
                "velocity": 78,
                "channel": 0,
            })
        note_tracks["strings"] = replace_notes_in_bar_range(note_tracks["strings"], bar_index, bar_index + 1, string_bar[:2])
        report["breakdown_emotion_lift_added"] = True
    if report["breakdown_sustained_notes"] < max(1, breakdown["bars"] // 2):
        report["breakdown_emotion_warnings"].append("breakdown lacks sustained notes")
    return report


def apply_humanisation(notes_or_tracks, seed_value=0):
    note_tracks = notes_or_tracks
    rng = random.Random(seed_value)
    report = {"humanised_notes": 0}
    for stem, max_shift in (("lead", 14), ("piano", 12), ("arp", 8)):
        fixed = []
        for n in note_tracks[stem]:
            fixed_note = dict(n)
            if rng.random() < 0.32:
                shift_ms = rng.randint(-max_shift, max_shift)
                shift_ticks = int((shift_ms / 1000.0) * TICKS * 2.3)
                duration = fixed_note["end"] - fixed_note["start"]
                fixed_note["start"] = max(0, fixed_note["start"] + shift_ticks)
                fixed_note["end"] = max(fixed_note["start"] + 1, fixed_note["start"] + duration)
                report["humanised_notes"] += 1
            fixed.append(fixed_note)
        note_tracks[stem] = sorted(fixed, key=lambda data: (data["start"], data["pitch"]))
    return report


def create_shiver_moment_v2(story, core_motif, section):
    if not section:
        return {}
    options = ["half_bar_silence_before_drop", "sustained_high_note_then_silence", "octave_jump_on_drop_entry", "filter_style_repetition"]
    signature = sum(ord(ch) for ch in story.get("story_type", "")) + len(core_motif.get("notes", []))
    chosen = options[signature % len(options)]
    descriptions = {
        "half_bar_silence_before_drop": "A half-bar gap clears the air before the drop returns.",
        "sustained_high_note_then_silence": "A high sustained motif tone hangs briefly, then drops into silence before release.",
        "octave_jump_on_drop_entry": "The first drop-return note jumps an octave to signal the payoff.",
        "filter_style_repetition": "The motif tightens into short repeated notes, simulating a filtered tension loop.",
    }
    return {"section": section["name"], "bar": max(section["start_bar"], section["end_bar"] - 1) + 1, "type": chosen, "description": descriptions[chosen]}


def apply_shiver_moment_v2(note_tracks, shiver, sections, chords):
    build2 = next((section for section in sections if section["name"] == shiver.get("section")), None)
    drop2 = next((section for section in sections if section["name"] == "Drop 2"), None)
    if not build2 or not drop2:
        return
    shiver_type = shiver.get("type")
    if shiver_type == "half_bar_silence_before_drop":
        gap_start = bar_tick(build2["end_bar"]) - tick(0.5)
        for stem in ("lead", "countermelody", "vocal_melody", "arp", "pluck", "supersaw_chords"):
            note_tracks[stem] = [n for n in note_tracks[stem] if not (gap_start <= n["start"] < bar_tick(build2["end_bar"]))]
    elif shiver_type == "sustained_high_note_then_silence":
        chord = chords[(build2["end_bar"] - 1) % len(chords)]
        note_tracks["lead"].append({"start": bar_tick(build2["end_bar"] - 1), "end": bar_tick(build2["end_bar"]) - tick(0.5), "pitch": motif_degree_pitch(chord, 5, 76, 88, 12), "velocity": 96, "channel": 0})
    elif shiver_type == "octave_jump_on_drop_entry":
        first_notes = sorted(notes_starting_in_bar(note_tracks["lead"], drop2["start_bar"]), key=lambda n: n["start"])
        if first_notes:
            first_notes[0]["pitch"] = clamp_pitch_into_register(first_notes[0]["pitch"] + 12, 76, 90)
            note_tracks["lead"] = replace_notes_in_bar_range(note_tracks["lead"], drop2["start_bar"], drop2["start_bar"] + 1, first_notes)
    else:
        final_bar = build2["end_bar"] - 1
        chord = chords[final_bar % len(chords)]
        loop = []
        for idx, beat_pos in enumerate((2.0, 2.5, 3.0, 3.5)):
            loop.append({"start": bar_tick(final_bar) + tick(beat_pos), "end": bar_tick(final_bar) + tick(beat_pos + 0.25), "pitch": motif_degree_pitch(chord, 5 if idx % 2 == 0 else 3, 70, 84, 12), "velocity": 84 + idx * 3, "channel": 0})
        note_tracks["lead"] = replace_notes_in_bar_range(note_tracks["lead"], final_bar, final_bar + 1, loop)


def validate_v11_2_phrase_intent(note_tracks, sections, contrast_report, hook_report, breakdown_report, gap_report):
    warnings = []
    if gap_report.get("phrase_gaps_inserted", 0) <= 0:
        warnings.append("phrase too continuous")
    if hook_report.get("hook_repetitions_drop1", 0) < 2 or hook_report.get("hook_repetitions_drop2", 0) < 3:
        warnings.append("hook repetition too low")
    if contrast_report.get("drop_contrast_score", 0) < 78:
        warnings.append("drop contrast too weak")
    warnings.extend(breakdown_report.get("breakdown_emotion_warnings", []))
    return sorted(set(warnings)) if warnings else ["none"]


def apply_v11_2_phrase_intent_engine(note_tracks, sections, chords, blueprint, story, core_motif):
    gap_report = {"phrase_gaps_inserted": 0}
    anticipation_report = {"anticipation_repairs": 0}
    for section in sections:
        section_gap = apply_phrase_gaps(note_tracks, section)
        gap_report["phrase_gaps_inserted"] += section_gap.get("phrase_gaps_inserted", 0)
        section_anticipation = apply_anticipation({"note_tracks": note_tracks, "section": section})
        anticipation_report["anticipation_repairs"] += section_anticipation.get("anticipation_repairs", 0)
    hook_contrast_report = apply_drop_contrast(note_tracks, sections, chords, core_motif)
    breakdown_report = enhance_breakdown_emotion(note_tracks, sections, chords)
    build2 = next((section for section in sections if section["name"] == "Build 2"), None)
    shiver = create_shiver_moment_v2(story, core_motif, build2)
    if shiver:
        apply_shiver_moment_v2(note_tracks, shiver, sections, chords)
    human_report = apply_humanisation(note_tracks, sum(ord(ch) for ch in str(blueprint.get("selected_key", "")) + str(blueprint.get("variation_type", ""))))
    warnings = validate_v11_2_phrase_intent(note_tracks, sections, hook_contrast_report, hook_contrast_report, breakdown_report, gap_report)
    return {**gap_report, **anticipation_report, **hook_contrast_report, **breakdown_report, **human_report, "shiver_moment_v2": shiver, "v11_2_warnings": warnings}


def intro_pattern_choice(blueprint, core_motif):
    options = ["delayed_kick", "filtered_sparse_kick", "half_time_kick", "full_kick_no_bass"]
    signature = sum(ord(ch) for ch in f"{blueprint.get('track_identity','')}{blueprint.get('variation_type','')}{core_motif.get('motif_id','')}")
    return options[signature % len(options)]


def apply_intro_motif_teaser(note_tracks, intro, chords, core_motif, blueprint):
    report = {"intro_teaser_notes": 0, "intro_teaser_stem": ""}
    if not intro:
        return report
    preferred = "piano" if "PIANO" in blueprint.get("variation_type", "") or "ORCHESTRAL" in blueprint.get("track_identity", "") else "arp" if "ARP" in blueprint.get("variation_type", "") else "pluck"
    report["intro_teaser_stem"] = preferred
    motif_fragment = strongest_two_bar_motif_segment(core_motif)[:3]
    for bar_index in range(intro["start_bar"], min(intro["end_bar"], intro["start_bar"] + 16)):
        local = bar_index - intro["start_bar"]
        chord = chords[bar_index % len(chords)]
        bar_notes = []
        for idx, item in enumerate(motif_fragment[:(1 if local < 4 else 2)]):
            beat_pos = 0.0 if idx == 0 else 2.5
            pitch = motif_degree_pitch(chord, item["degree"], 55 if preferred == "piano" else 60, 76 if preferred == "piano" else 79, 0)
            bar_notes.append({"start": bar_tick(bar_index) + tick(beat_pos), "end": bar_tick(bar_index) + tick(beat_pos + (1.25 if idx == 0 else 0.75)), "pitch": pitch, "velocity": 58 + min(18, local * 2), "channel": 0})
        note_tracks[preferred] = replace_notes_in_bar_range(note_tracks[preferred], bar_index, bar_index + 1, bar_notes)
        report["intro_teaser_notes"] += len(bar_notes)
    return report


def generate_intro_kick_pattern(note_tracks, intro, pattern):
    report = {"intro_kick_pattern": pattern, "intro_kick_hits": 0}
    if not intro:
        return report
    note_tracks["kick"] = remove_notes_in_bar_range(note_tracks["kick"], intro["start_bar"], intro["end_bar"])
    for bar_index in range(intro["start_bar"], intro["end_bar"]):
        local = bar_index - intro["start_bar"]
        if pattern == "delayed_kick":
            beats = [] if local < 4 else [0.0, 1.0, 2.0, 3.0]
        elif pattern == "filtered_sparse_kick":
            beats = [0.0] if local < 4 else [0.0, 2.0] if local < 8 else [0.0, 1.0, 2.0, 3.0]
        elif pattern == "half_time_kick":
            beats = [0.0, 2.0] if local < 4 else [0.0, 1.0, 2.0, 3.0]
        else:
            beats = [0.0, 1.0, 2.0, 3.0]
        velocity = 62 if local < 4 and pattern != "full_kick_no_bass" else 76 if local < 8 else 88
        for beat_pos in beats:
            note_tracks["kick"].append({
                "start": bar_tick(bar_index) + tick(beat_pos),
                "end": bar_tick(bar_index) + tick(beat_pos + 0.12),
                "pitch": 36,
                "velocity": velocity,
                "channel": 0,
            })
            report["intro_kick_hits"] += 1
    return report


def build_intro_percussion_layers(note_tracks, intro):
    report = {"intro_percussion_hits": 0}
    if not intro:
        return report
    for stem in ("clap_snare", "hats"):
        note_tracks[stem] = remove_notes_in_bar_range(note_tracks[stem], intro["start_bar"], intro["end_bar"])
    for bar_index in range(intro["start_bar"], intro["end_bar"]):
        local = bar_index - intro["start_bar"]
        if local < 4:
            hat_beats, clap_beats = ([2.0] if local % 2 == 0 else [1.0, 3.0]), []
        elif local < 8:
            hat_beats, clap_beats = [1.0, 2.0, 3.0], [1.0 if local % 2 else 3.0]
        else:
            hat_beats, clap_beats = [0.5, 1.0, 1.5, 2.5, 3.0, 3.5], [1.0, 3.0]
        for beat_pos in hat_beats:
            note_tracks["hats"].append({
                "start": bar_tick(bar_index) + tick(beat_pos),
                "end": bar_tick(bar_index) + tick(beat_pos + 0.06),
                "pitch": 42,
                "velocity": 48 + min(28, local * 3),
                "channel": 0,
            })
            report["intro_percussion_hits"] += 1
        for beat_pos in clap_beats:
            note_tracks["clap_snare"].append({
                "start": bar_tick(bar_index) + tick(beat_pos),
                "end": bar_tick(bar_index) + tick(beat_pos + 0.08),
                "pitch": 38,
                "velocity": 58 + min(24, local * 2),
                "channel": 0,
            })
            report["intro_percussion_hits"] += 1
    return report


def apply_intro_bass_tease(note_tracks, intro, chords, pattern):
    report = {"intro_bass_tease_notes": 0, "intro_low_end_present": False}
    if not intro:
        return report
    for stem in ("offbeat_bass", "rolling_bass", "sub_bass"):
        note_tracks[stem] = remove_notes_in_bar_range(note_tracks[stem], intro["start_bar"], intro["end_bar"])
    start_offset = 8 if intro["bars"] >= 16 else 4
    if pattern == "full_kick_no_bass":
        start_offset = max(start_offset, 8)
    for bar_index in range(intro["start_bar"] + start_offset, intro["end_bar"], 2):
        chord = chords[bar_index % len(chords)]
        note_tracks["sub_bass"].append({"start": bar_tick(bar_index), "end": bar_tick(min(intro["end_bar"], bar_index + 2)), "pitch": clamp_pitch_into_register(chord["root"] - 24, 30, 45), "velocity": 42, "channel": 0})
        report["intro_bass_tease_notes"] += 1
    report["intro_low_end_present"] = report["intro_bass_tease_notes"] > 0
    return report


def apply_intro_energy_curve(note_tracks, intro):
    report = {"intro_energy_curve": "minimal_to_groove_to_prepare", "intro_velocity_scaled_notes": 0}
    if not intro:
        return report
    for stem in ("kick", "clap_snare", "hats", "pluck", "arp", "piano", "sub_bass"):
        fixed = []
        for n in note_tracks[stem]:
            fixed_note = dict(n)
            if bar_tick(intro["start_bar"]) <= fixed_note["start"] < bar_tick(intro["end_bar"]):
                local = (fixed_note["start"] // BAR_TICKS) - intro["start_bar"]
                factor = 0.62 if local < 4 else 0.78 if local < 8 else 0.92
                fixed_note["velocity"] = clamp(int(fixed_note["velocity"] * factor), 1, 110)
                report["intro_velocity_scaled_notes"] += 1
            fixed.append(fixed_note)
        note_tracks[stem] = sorted(fixed, key=lambda data: (data["start"], data["pitch"]))
    return report


def validate_intro_story(note_tracks, intro, intro_report):
    warnings = []
    if not intro:
        return {"intro_validation_warnings": ["missing_intro_section"], "intro_story_score": 0}
    motif_notes = intro_report.get("intro_teaser_notes", 0)
    rhythm_hits = intro_report.get("intro_kick_hits", 0) + intro_report.get("intro_percussion_hits", 0)
    if motif_notes == 0 or rhythm_hits < 4:
        warnings.append("intro too empty")
    first4_kicks = sum(len(notes_starting_in_bar(note_tracks["kick"], bar)) for bar in range(intro["start_bar"], min(intro["end_bar"], intro["start_bar"] + 4)))
    all_intro_kicks = sum(len(notes_starting_in_bar(note_tracks["kick"], bar)) for bar in range(intro["start_bar"], intro["end_bar"]))
    if first4_kicks >= 16 and all_intro_kicks >= intro["bars"] * 4:
        warnings.append("kick static pattern")
    if intro_report.get("intro_velocity_scaled_notes", 0) <= 0:
        warnings.append("no intro progression")
    if not intro_report.get("intro_low_end_present"):
        warnings.append("no low-end presence")
    return {"intro_validation_warnings": warnings or ["none"], "intro_story_score": max(0, 100 - len(warnings) * 20)}


def apply_v11_3_intro_groove_engine(note_tracks, sections, chords, blueprint, core_motif):
    intro = next((section for section in sections if section["name"] == "Intro"), None)
    report = {}
    if not intro:
        return {"intro_validation_warnings": ["missing_intro_section"], "intro_story_score": 0}
    pattern = intro_pattern_choice(blueprint, core_motif)
    report.update(apply_intro_motif_teaser(note_tracks, intro, chords, core_motif, blueprint))
    report.update(generate_intro_kick_pattern(note_tracks, intro, pattern))
    report.update(build_intro_percussion_layers(note_tracks, intro))
    report.update(apply_intro_bass_tease(note_tracks, intro, chords, pattern))
    report.update(apply_intro_energy_curve(note_tracks, intro))
    report["intro_dj_friendly"] = intro["bars"] % 8 == 0
    report.update(validate_intro_story(note_tracks, intro, report))
    return report


def create_intro_signature_hook(core_motif):
    segment = strongest_two_bar_motif_segment(core_motif)
    signature = []
    for item in segment[:4]:
        if item["bar"] <= 1:
            signature.append({
                "bar": item["bar"],
                "beat": item["beat"],
                "degree": item["degree"],
                "duration": max(0.75, min(1.5, item["duration"])),
                "velocity": item["velocity"],
            })
    if not signature:
        signature = [{"bar": 0, "beat": 0.0, "degree": 5, "duration": 1.25, "velocity": 72}]
    return {
        "length_bars": 2,
        "notes": signature[:4],
        "rhythm_signature": [(item["bar"], item["beat"], item["duration"]) for item in signature[:4]],
    }


def intro_signature_stem(blueprint):
    if "ORCHESTRAL" in blueprint.get("track_identity", "") or "PIANO" in blueprint.get("variation_type", ""):
        return "piano"
    if "ARP" in blueprint.get("variation_type", "") or "CLASSIC" in blueprint.get("track_identity", ""):
        return "arp"
    return "pluck"


def intro_signature_to_notes(signature, intro, chords, stem, repeat_start, velocity_delta=0, pitch_variation=0):
    notes = []
    for idx, item in enumerate(signature["notes"]):
        target_bar = intro["start_bar"] + repeat_start + item["bar"]
        if target_bar >= intro["end_bar"]:
            continue
        chord = chords[target_bar % len(chords)]
        low, high = (55, 76) if stem == "piano" else (60, 79)
        pitch = motif_degree_pitch(chord, item["degree"], low, high, 0)
        if pitch_variation and idx == len(signature["notes"]) - 1:
            pitch = clamp_pitch_into_register(pitch + pitch_variation, low, high)
        start = bar_tick(target_bar) + tick(item["beat"])
        notes.append({
            "start": start,
            "end": min(bar_tick(target_bar + 1), start + tick(item["duration"])),
            "pitch": pitch,
            "velocity": clamp(item["velocity"] + velocity_delta, 48, 98),
            "channel": 0,
        })
    return notes


def apply_intro_call_response(note_tracks, intro, chords, core_motif, blueprint):
    report = {
        "intro_signature_repetitions": 0,
        "intro_signature_stem": "",
        "intro_signature_rhythm": "",
        "intro_call_response_applied": False,
    }
    if not intro:
        return report
    signature = create_intro_signature_hook(core_motif)
    stem = intro_signature_stem(blueprint)
    report["intro_signature_stem"] = stem
    report["intro_signature_rhythm"] = json.dumps(signature["rhythm_signature"])
    for target_stem in ("piano", "arp", "pluck"):
        note_tracks[target_stem] = remove_notes_in_bar_range(note_tracks[target_stem], intro["start_bar"], min(intro["end_bar"], intro["start_bar"] + 8))
    layout = [(0, 0, 0), (2, -10, 0), (4, 2, 0), (6, 8, 3)]
    for repeat_start, velocity_delta, pitch_variation in layout:
        active_signature = {**signature, "notes": signature["notes"][:1]} if repeat_start == 2 else signature
        notes = intro_signature_to_notes(active_signature, intro, chords, stem, repeat_start, velocity_delta, pitch_variation)
        for note_data in notes:
            bar_index = note_data["start"] // BAR_TICKS
            if len(notes_starting_in_bar(note_tracks[stem], bar_index)) < 3:
                note_tracks[stem].append(note_data)
        report["intro_signature_repetitions"] += 1
    report["intro_call_response_applied"] = True
    return report


def create_intro_mini_moment(note_tracks, intro, chords, stem, blueprint):
    report = {"intro_mini_moment": ""}
    if not intro or intro["bars"] < 8:
        return report
    options = ["short_silence_before_bar8", "higher_note_on_last_repeat", "velocity_lift_final_motif", "brief_chord_swell"]
    signature = sum(ord(ch) for ch in f"{blueprint.get('track_identity','')}{blueprint.get('variation_type','')}{blueprint.get('selected_key','')}")
    choice = options[signature % len(options)]
    bar7 = intro["start_bar"] + 6
    bar8 = intro["start_bar"] + 7
    if choice == "short_silence_before_bar8":
        gap_start = bar_tick(bar8) - tick(0.5)
        for target in ("piano", "arp", "pluck", "lead", "vocal_melody"):
            note_tracks[target] = [n for n in note_tracks[target] if not (gap_start <= n["start"] < bar_tick(bar8))]
    elif choice == "higher_note_on_last_repeat":
        final_notes = sorted(notes_starting_in_bar(note_tracks[stem], bar8), key=lambda n: n["start"])
        if final_notes:
            final_notes[-1]["pitch"] = clamp_pitch_into_register(final_notes[-1]["pitch"] + 5, 55, 81)
            note_tracks[stem] = replace_notes_in_bar_range(note_tracks[stem], bar8, bar8 + 1, final_notes)
    elif choice == "velocity_lift_final_motif":
        for bar_index in (bar7, bar8):
            lifted = [{**note_data, "velocity": clamp(note_data["velocity"] + 12, 1, 110)} for note_data in notes_starting_in_bar(note_tracks[stem], bar_index)]
            note_tracks[stem] = replace_notes_in_bar_range(note_tracks[stem], bar_index, bar_index + 1, lifted)
    else:
        chord = chords[bar8 % len(chords)]
        swell = []
        for pitch in (chord["root"], chord["fifth"], chord["third"] + 12):
            swell.append({
                "start": bar_tick(bar8) + tick(2.5),
                "end": bar_tick(bar8 + 1),
                "pitch": clamp_pitch_into_register(pitch, 48, 76),
                "velocity": 62,
                "channel": 0,
            })
        note_tracks["pad"] = replace_notes_in_bar_range(note_tracks["pad"], bar8, bar8 + 1, notes_starting_in_bar(note_tracks["pad"], bar8) + swell)
    report["intro_mini_moment"] = choice
    return report


def validate_intro_identity(note_tracks, intro, report):
    warnings = []
    if not intro:
        return {"intro_identity_score": 0, "intro_identity_warnings": ["missing_intro_section"]}
    if report.get("intro_signature_repetitions", 0) < 3:
        warnings.append("intro lacks repetition")
    if not report.get("intro_signature_rhythm"):
        warnings.append("no recognisable pattern")
    stem = report.get("intro_signature_stem", "pluck")
    too_continuous = any(
        len(notes_starting_in_bar(note_tracks[stem], bar_index)) > 3
        for bar_index in range(intro["start_bar"], min(intro["end_bar"], intro["start_bar"] + 8))
    )
    if too_continuous:
        warnings.append("intro too continuous")
    score = 100 - len(warnings) * 20
    return {"intro_identity_score": max(0, score), "intro_identity_warnings": warnings or ["none"]}


def apply_v11_4_intro_identity_engine(note_tracks, sections, chords, blueprint, core_motif):
    intro = next((section for section in sections if section["name"] == "Intro"), None)
    if not intro:
        return {"intro_identity_score": 0, "intro_identity_warnings": ["missing_intro_section"]}
    report = {}
    report.update(apply_intro_call_response(note_tracks, intro, chords, core_motif, blueprint))
    report.update(create_intro_mini_moment(note_tracks, intro, chords, report.get("intro_signature_stem", "pluck"), blueprint))
    report.update(validate_intro_identity(note_tracks, intro, report))
    return report


def control_lead_entry(note_tracks, sections):
    report = {"lead_entry_repairs": 0, "lead_silent_sections": []}
    intro = next((section for section in sections if section["name"] == "Intro"), None)
    if intro:
        before = len(note_tracks["lead"])
        note_tracks["lead"] = remove_notes_in_bar_range(note_tracks["lead"], intro["start_bar"], intro["end_bar"])
        report["lead_entry_repairs"] += max(0, before - len(note_tracks["lead"]))
        report["lead_silent_sections"].append("Intro")
    build = next((section for section in sections if section["name"] == "Build"), None)
    if build and build["bars"] >= 4:
        before = len(note_tracks["lead"])
        note_tracks["lead"] = remove_notes_in_bar_range(note_tracks["lead"], build["start_bar"], build["start_bar"] + max(1, build["bars"] // 2))
        report["lead_entry_repairs"] += max(0, before - len(note_tracks["lead"]))
    return report


def generate_lead_teaser(note_tracks, sections, chords, core_motif):
    report = {"lead_teaser_notes": 0, "lead_teaser_bars": ""}
    build = next((section for section in sections if section["name"] == "Build"), None)
    if not build:
        return report
    start_bar = max(build["start_bar"], build["end_bar"] - 2)
    motif_note = strongest_two_bar_motif_segment(core_motif)[0]
    teaser = []
    for bar_index in range(start_bar, build["end_bar"]):
        chord = chords[bar_index % len(chords)]
        pitch = motif_degree_pitch(chord, motif_note["degree"], 68, 82, 12)
        for beat_pos in (0.0, 2.0):
            teaser.append({
                "start": bar_tick(bar_index) + tick(beat_pos),
                "end": bar_tick(bar_index) + tick(beat_pos + 0.75),
                "pitch": pitch,
                "velocity": 78 + (bar_index - start_bar) * 4,
                "channel": 0,
            })
    note_tracks["lead"] = replace_notes_in_bar_range(note_tracks["lead"], start_bar, build["end_bar"], teaser)
    report["lead_teaser_notes"] = len(teaser)
    report["lead_teaser_bars"] = f"{start_bar + 1}-{build['end_bar']}"
    return report


def apply_lead_drop_hook(note_tracks, sections, chords, core_motif):
    report = {"drop1_lead_hook_notes": 0, "drop2_lead_payoff_notes": 0, "drop2_lead_payoff_mode": ""}
    drop1 = next((section for section in sections if section["name"] == "Drop 1"), None)
    drop2 = next((section for section in sections if section["name"] == "Drop 2"), None)
    if drop1:
        hook = reinforce_hook(core_motif, drop1, chords, repetitions=2, register_shift=0, velocity_delta=2)
        hook = [{**n, "end": max(n["end"], n["start"] + tick(1.0))} for n in hook]
        note_tracks["lead"] = replace_notes_in_bar_range(note_tracks["lead"], drop1["start_bar"], min(drop1["end_bar"], drop1["start_bar"] + 4), hook)
        report["drop1_lead_hook_notes"] = len(hook)
    if drop2:
        payoff = reinforce_hook(core_motif, drop2, chords, repetitions=3, register_shift=5, velocity_delta=10)
        payoff_fixed = []
        for idx, note_data in enumerate(payoff):
            fixed = dict(note_data)
            if idx == len(payoff) - 1 or idx % 4 == 0:
                fixed["end"] = min(bar_tick((fixed["start"] // BAR_TICKS) + 1), fixed["start"] + tick(1.75))
            payoff_fixed.append(fixed)
        if payoff_fixed:
            payoff_fixed[-1]["pitch"] = clamp_pitch_into_register(payoff_fixed[-1]["pitch"] + 12, 74, 90)
            payoff_fixed[-1]["end"] = min(bar_tick((payoff_fixed[-1]["start"] // BAR_TICKS) + 1), payoff_fixed[-1]["start"] + tick(2.0))
            report["drop2_lead_payoff_mode"] = "octave_lift_plus_longer_note"
        note_tracks["lead"] = replace_notes_in_bar_range(note_tracks["lead"], drop2["start_bar"], min(drop2["end_bar"], drop2["start_bar"] + 6), payoff_fixed)
        report["drop2_lead_payoff_notes"] = len(payoff_fixed)
    return report


def enforce_lead_note_structure(note_tracks, sections, chords):
    report = {"lead_density_repairs": 0, "lead_sustained_repairs": 0, "lead_rest_repairs": 0}
    for section in sections:
        if section["name"] not in ("Drop 1", "Drop 2"):
            continue
        for bar_index in range(section["start_bar"], section["end_bar"]):
            bar_notes = sorted(notes_starting_in_bar(note_tracks["lead"], bar_index), key=lambda n: (n["start"], -(n["end"] - n["start"])))
            if len(bar_notes) > 4:
                report["lead_density_repairs"] += len(bar_notes) - 4
                bar_notes = bar_notes[:4]
            fixed_bar = []
            for note_data in bar_notes:
                fixed = dict(note_data)
                fixed["end"] = min(max(fixed["end"], fixed["start"] + tick(0.9)), bar_tick(bar_index + 1))
                fixed_bar.append(fixed)
            if (bar_index - section["start_bar"]) % 2 == 0:
                block_notes = fixed_bar + notes_starting_in_bar(note_tracks["lead"], bar_index + 1)
                if not any(length_beats(n) >= 1.25 for n in block_notes):
                    chord = chords[bar_index % len(chords)]
                    fixed_bar.append({
                        "start": bar_tick(bar_index),
                        "end": bar_tick(bar_index) + tick(1.5),
                        "pitch": motif_degree_pitch(chord, 5, 70, 86, 12),
                        "velocity": 98,
                        "channel": 0,
                    })
                    report["lead_sustained_repairs"] += 1
            if (bar_index - section["start_bar"]) % 2 == 1:
                before = len(fixed_bar)
                fixed_bar = [n for n in fixed_bar if (n["start"] - bar_tick(bar_index)) / TICKS < 3.0]
                report["lead_rest_repairs"] += before - len(fixed_bar)
            note_tracks["lead"] = replace_notes_in_bar_range(note_tracks["lead"], bar_index, bar_index + 1, fixed_bar)
    return report


def validate_lead_payoff(note_tracks, sections):
    warnings = []
    drop1 = next((section for section in sections if section["name"] == "Drop 1"), None)
    drop2 = next((section for section in sections if section["name"] == "Drop 2"), None)
    all_drop_lead = []
    for section in (drop1, drop2):
        if section:
            all_drop_lead.extend([n for n in note_tracks["lead"] if bar_tick(section["start_bar"]) <= n["start"] < bar_tick(section["end_bar"])])
    avg_len = avg_note_length(all_drop_lead)
    if avg_len < 0.95:
        warnings.append("lead too short")
    if any(len(notes_starting_in_bar(note_tracks["lead"], bar_index)) > 4 for section in (drop1, drop2) if section for bar_index in range(section["start_bar"], section["end_bar"])):
        warnings.append("lead too dense")
    if not any(length_beats(n) >= 1.25 for n in all_drop_lead):
        warnings.append("lead lacks sustained notes")
    if drop1 and drop2:
        d1 = [n for n in note_tracks["lead"] if bar_tick(drop1["start_bar"]) <= n["start"] < bar_tick(min(drop1["end_bar"], drop1["start_bar"] + 8))]
        d2 = [n for n in note_tracks["lead"] if bar_tick(drop2["start_bar"]) <= n["start"] < bar_tick(min(drop2["end_bar"], drop2["start_bar"] + 8))]
        if d1 and d2:
            d1_sig = [(round((n["start"] - bar_tick(n["start"] // BAR_TICKS)) / TICKS, 2), n["pitch"] % 12, round(length_beats(n), 2)) for n in d1[:8]]
            d2_sig = [(round((n["start"] - bar_tick(n["start"] // BAR_TICKS)) / TICKS, 2), n["pitch"] % 12, round(length_beats(n), 2)) for n in d2[:8]]
            if d1_sig == d2_sig or (average_pitch(d2) < average_pitch(d1) + 1 and avg_note_length(d2) <= avg_note_length(d1) + 0.1):
                warnings.append("lead does not change between Drop 1 and Drop 2")
    return {"lead_drop_avg_duration": round(avg_len, 3), "lead_payoff_warnings": warnings or ["none"]}


def apply_v11_5_lead_payoff_engine(note_tracks, sections, chords, core_motif):
    report = {}
    report.update(control_lead_entry(note_tracks, sections))
    report.update(generate_lead_teaser(note_tracks, sections, chords, core_motif))
    report.update(apply_lead_drop_hook(note_tracks, sections, chords, core_motif))
    report.update(enforce_lead_note_structure(note_tracks, sections, chords))
    report.update(validate_lead_payoff(note_tracks, sections))
    return report


def reduce_breakdown_to_story_space(note_tracks, breakdown):
    if not breakdown:
        return
    for stem in ("rolling_bass", "offbeat_bass", "sub_bass"):
        note_tracks[stem] = remove_notes_in_bar_range(note_tracks[stem], breakdown["start_bar"], breakdown["end_bar"])
    for stem in ("lead", "arp", "pluck", "countermelody"):
        note_tracks[stem] = remove_notes_in_bar_range(note_tracks[stem], breakdown["start_bar"], breakdown["end_bar"])
    for bar_index in range(breakdown["start_bar"], breakdown["end_bar"]):
        for stem in ("clap_snare", "hats"):
            bar_notes = sorted(notes_starting_in_bar(note_tracks[stem], bar_index), key=lambda n: (n["start"], n["pitch"]))
            keep = bar_notes[:1] if (bar_index - breakdown["start_bar"]) % 4 == 0 else []
            note_tracks[stem] = replace_notes_in_bar_range(note_tracks[stem], bar_index, bar_index + 1, keep)


def validate_motif_strength(core_motif):
    degrees = [n["degree"] for n in core_motif["notes"]]
    rhythm = [(n["beat"], n["duration"]) for n in core_motif["notes"]]
    repeated_degrees = len(degrees) - len(set(degrees))
    has_long = any(n["duration"] >= 1.5 for n in core_motif["notes"])
    has_rest = len(core_motif["notes"]) <= core_motif["length_bars"] * 2
    stable_resolution = core_motif["notes"][-1]["degree"] in (1, 3, 5)
    score = 45 + min(20, repeated_degrees * 4) + (15 if has_long else 0) + (10 if has_rest else 0) + (10 if stable_resolution else 0)
    return min(100, score), {"repeated_degrees": repeated_degrees, "rhythm_events": rhythm}


def validate_phrase_repetition(core_motif):
    first_half = [(n["beat"], n["degree"]) for n in core_motif["notes"] if n["bar"] < 4]
    second_half = [(n["beat"], n["degree"]) for n in core_motif["notes"] if n["bar"] >= 4]
    first_rhythm = [beat for beat, degree in first_half]
    second_rhythm = [beat for beat, degree in second_half]
    shared_rhythm = len(set(first_rhythm) & set(second_rhythm))
    ratio = shared_rhythm / max(1, len(set(first_rhythm)))
    return min(100, int(65 + ratio * 35))


def validate_story_arc(story, motif_variations):
    required = {"Intro", "Build", "Drop 1", "Breakdown", "Build 2", "Drop 2"}
    present = required & set(motif_variations)
    return min(100, 50 + len(present) * 8 + (10 if story.get("shiver_moment_section") else 0))


def validate_breakdown_quality(note_tracks, sections):
    breakdown = next((section for section in sections if section["name"] == "Breakdown"), None)
    if not breakdown:
        return 0
    piano_count = sum(len(notes_starting_in_bar(note_tracks["piano"], bar)) for bar in range(breakdown["start_bar"], breakdown["end_bar"]))
    strings_count = sum(len(notes_starting_in_bar(note_tracks["strings"], bar)) for bar in range(breakdown["start_bar"], breakdown["end_bar"]))
    rolling_count = sum(len(notes_starting_in_bar(note_tracks["rolling_bass"], bar)) for bar in range(breakdown["start_bar"], breakdown["end_bar"]))
    busy_arp = sum(len(notes_starting_in_bar(note_tracks["arp"], bar)) for bar in range(breakdown["start_bar"], breakdown["end_bar"]))
    score = 45 + (25 if piano_count > 0 else 0) + (15 if strings_count > 0 else 0) + (10 if rolling_count == 0 else -20) + (5 if busy_arp <= 4 else -10)
    return clamp(score, 0, 100)


def validate_drop_payoff(note_tracks, sections):
    drop1 = next((section for section in sections if section["name"] == "Drop 1"), None)
    drop2 = next((section for section in sections if section["name"] == "Drop 2"), None)
    if not drop1 or not drop2:
        return 0
    drop1_notes = [n for n in note_tracks["lead"] if bar_tick(drop1["start_bar"]) <= n["start"] < bar_tick(drop1["end_bar"])]
    drop2_notes = [n for n in note_tracks["lead"] if bar_tick(drop2["start_bar"]) <= n["start"] < bar_tick(drop2["end_bar"])]
    if not drop1_notes or not drop2_notes:
        return 0
    related_density = min(25, int((len(drop2_notes) / max(1, len(drop1_notes))) * 18))
    higher = max(n["pitch"] for n in drop2_notes) >= max(n["pitch"] for n in drop1_notes)
    longer = avg_note_length(drop2_notes) >= avg_note_length(drop1_notes)
    return min(100, 45 + related_density + (15 if higher else 0) + (15 if longer else 0))


def validate_musical_story(story, core_motif, motif_variations, note_tracks, sections, shiver):
    motif_score, motif_detail = validate_motif_strength(core_motif)
    scores = {
        "motif_strength_score": motif_score,
        "phrase_coherence_score": validate_phrase_repetition(core_motif),
        "story_arc_score": validate_story_arc(story, motif_variations),
        "breakdown_quality_score": validate_breakdown_quality(note_tracks, sections),
        "drop_payoff_score": validate_drop_payoff(note_tracks, sections),
        "shiver_moment_score": 85 if shiver else 0,
    }
    critical_failures = []
    if scores["motif_strength_score"] < 75:
        critical_failures.append("weak_core_motif")
    if scores["breakdown_quality_score"] < 75:
        critical_failures.append("breakdown_quality_low")
    if scores["drop_payoff_score"] < 75:
        critical_failures.append("drop_payoff_low")
    if not shiver:
        critical_failures.append("missing_shiver_moment")
    return {
        **scores,
        "motif_validation_detail": motif_detail,
        "motif_story_passed": not critical_failures,
        "motif_story_failed_checks": ",".join(critical_failures) if critical_failures else "none",
    }


def apply_v11_motif_story_engine(tracks, sections, chords, blueprint, identity):
    story = blueprint.get("v11_story") or create_track_story(blueprint, blueprint.get("variation_type", "DEFAULT"), blueprint.get("progression_name", ""), blueprint.get("selected_key", ""))
    core_motif = blueprint.get("v11_core_motif") or create_core_motif(blueprint.get("selected_key", ""), blueprint.get("progression_name", ""), blueprint, story["story_type"])
    note_tracks = {stem: events_to_notes(events) for stem, events in tracks.items()}
    motif_variations = {}
    motif_owners = {}
    for section in sections:
        section_name = section["name"]
        if section_name == "Breakdown":
            reduce_breakdown_to_story_space(note_tracks, section)
        motif_version = develop_motif_for_section(core_motif, section_name, story["motif_reveal_plan"].get(section_name, "fragment"), 1.0)
        owners = assign_motif_to_stems(story, section_name)
        motif_variations[section_name] = {
            "mode": motif_version["mode"],
            "bars": motif_version["bars"],
            "note_count": len(motif_version["notes"]),
            "density": motif_version["density"],
        }
        motif_owners[section_name] = owners
        for stem in owners:
            if stem not in note_tracks:
                continue
            replacement = motif_notes_to_stem_notes(motif_version, section, chords, stem, repeat=section_name not in ("Intro", "Outro"))
            if section_name == "Breakdown" and stem == "piano":
                left_hand = []
                for bar_index in range(section["start_bar"], section["end_bar"], 2):
                    chord = chords[bar_index % len(chords)]
                    left_hand.append({
                        "start": bar_tick(bar_index),
                        "end": bar_tick(bar_index) + tick(2.0),
                        "pitch": clamp(chord["root"] - 12, 36, 56),
                        "velocity": 62,
                        "channel": 0,
                    })
                replacement.extend(left_hand)
            if section_name == "Drop 2" and stem == "countermelody":
                replacement = [
                    {**n, "start": n["start"] + tick(0.5), "end": n["end"] + tick(0.5), "velocity": min(114, n["velocity"] + 4)}
                    for n in replacement
                    if n["start"] + tick(0.5) < bar_tick(section["end_bar"])
                ]
            note_tracks[stem] = replace_notes_in_bar_range(note_tracks[stem], section["start_bar"], section["end_bar"], replacement)
        if section_name == "Breakdown":
            for bar_index in range(section["start_bar"], section["end_bar"], 2):
                chord = chords[bar_index % len(chords)]
                voicing = [clamp(chord["root"], 48, 72), clamp(chord["third"], 52, 76), clamp(chord["fifth"] + 12, 60, 84)]
                for pitch in voicing:
                    note_tracks["strings"].append({
                        "start": bar_tick(bar_index),
                        "end": bar_tick(min(section["end_bar"], bar_index + 2)),
                        "pitch": pitch,
                        "velocity": 64 + min(18, (bar_index - section["start_bar"])),
                        "channel": 0,
                    })
    build2 = next((section for section in sections if section["name"] == "Build 2"), None)
    shiver = create_shiver_moment(story, core_motif, build2, chords) if build2 else {}
    if shiver:
        apply_shiver_moment(note_tracks, shiver, sections, chords)
    musical_correction_report = apply_v11_1_musical_corrections(note_tracks, sections, chords, blueprint)
    phrase_intent_report = apply_v11_2_phrase_intent_engine(note_tracks, sections, chords, blueprint, story, core_motif)
    intro_groove_report = apply_v11_3_intro_groove_engine(note_tracks, sections, chords, blueprint, core_motif)
    intro_identity_report = apply_v11_4_intro_identity_engine(note_tracks, sections, chords, blueprint, core_motif)
    lead_payoff_report = apply_v11_5_lead_payoff_engine(note_tracks, sections, chords, core_motif)
    if phrase_intent_report.get("shiver_moment_v2"):
        shiver = phrase_intent_report["shiver_moment_v2"]
    musical_correction_report.update(phrase_intent_report)
    musical_correction_report.update(intro_groove_report)
    musical_correction_report.update(intro_identity_report)
    musical_correction_report.update(lead_payoff_report)
    musical_correction_report.update(final_scale_lock_postprocess(note_tracks, sections, chords, blueprint.get("selected_key", "C")))
    story_validation = validate_musical_story(story, core_motif, motif_variations, note_tracks, sections, shiver)
    motif_story = {
        **story,
        "core_motif": core_motif,
        "motif_variations_by_section": motif_variations,
        "motif_owner_by_section": motif_owners,
        "shiver_moment": shiver,
        "musical_correction_report": musical_correction_report,
        "validation_scores": {key: value for key, value in story_validation.items() if key.endswith("_score")},
        "validation": story_validation,
        "producer_note": (
            f"The main motif begins as a {story['main_motif_owner']} idea, expands emotionally in the breakdown, "
            f"then returns as a stronger lead/counter hook in Drop 2. The shiver moment occurs in {shiver.get('section', 'Build 2')} "
            f"with a short pause before the motif returns higher."
        ),
    }
    blueprint["v11_motif_story"] = motif_story
    blueprint.setdefault("validation_report", {}).update(story_validation)
    for stem in tracks:
        tracks[stem] = notes_to_events(sorted(note_tracks[stem], key=lambda item: (item["start"], item["pitch"])))
    return tracks, blueprint


def section_intensity(kind: str, is_second_pass: bool, blueprint, section_progress: float) -> float:
    base = {
        "intro": 0.22,
        "verse": 0.42,
        "build": 0.68,
        "drop": 0.92,
        "breakdown": 0.36,
        "outro": 0.25,
        "other": 0.4,
    }[kind]
    profile = blueprint["energy_profile"]
    if profile == "gradual_rise":
        curve = 0.16 * section_progress
    elif profile == "early_energy":
        curve = 0.12 if section_progress < 0.4 else 0.05
    elif profile == "late_peak":
        curve = 0.04 if section_progress < 0.55 else 0.18
    else:
        curve = 0.12 if 0.2 < section_progress < 0.45 or section_progress > 0.75 else 0.06

    weight_profile = blueprint.get("section_weight_profile", "balanced")
    if weight_profile == "front_loaded":
        if section_progress < 0.45 and kind in ("verse", "build", "drop"):
            curve += 0.12
        if section_progress > 0.65 and kind in ("breakdown", "build", "drop"):
            curve -= 0.06
        if is_second_pass and kind in ("build", "drop"):
            curve -= 0.03
    elif weight_profile == "late_bloom":
        if section_progress < 0.4 and kind in ("verse", "build", "drop"):
            curve -= 0.1
        if section_progress < 0.25 and kind in ("intro", "verse"):
            curve -= 0.06
        if section_progress > 0.6 and kind in ("build", "drop"):
            curve += 0.14
        if is_second_pass and kind in ("build", "drop"):
            curve += 0.05
    elif weight_profile == "breakdown_heavy":
        if kind == "breakdown":
            curve += 0.18
        if kind == "drop" and not is_second_pass:
            curve -= 0.08
        if kind == "build" and not is_second_pass:
            curve -= 0.04
    elif weight_profile == "balanced":
        if kind == "breakdown":
            curve += 0.02
        if is_second_pass and kind in ("build", "drop"):
            curve += 0.02

    macro_profile = blueprint.get("macro_journey_profile", "anthem_arc")
    if macro_profile == "breakdown_rebirth":
        if kind == "breakdown":
            curve += 0.12
        elif kind == "build" and is_second_pass:
            curve += 0.06
        elif kind == "drop" and is_second_pass:
            curve += 0.08
    elif macro_profile == "drop_pressure":
        if kind in ("build", "drop"):
            curve += 0.08 if not is_second_pass else 0.12
        elif kind == "breakdown":
            curve -= 0.06
    elif macro_profile == "vocal_journey":
        if kind in ("verse", "breakdown"):
            curve += 0.08
        elif kind == "drop" and not is_second_pass:
            curve -= 0.03
    elif macro_profile == "anthem_arc":
        if kind == "drop":
            curve += 0.04
        if kind in ("build", "drop") and section_progress > 0.55:
            curve += 0.05

    if is_second_pass and kind in ("build", "drop"):
        curve += 0.08
        final_lift = blueprint.get("final_lift_profile", "anthem_push")
        if final_lift == "subtle_return":
            curve -= 0.04
        elif final_lift == "anthem_push":
            curve += 0.08
        elif final_lift == "wide_release":
            curve += 0.06
        elif final_lift == "hook_reinforcement":
            curve += 0.05
    curve += macro_curve_adjustment(kind, blueprint, is_second_pass, section_progress)
    return min(1.28, base + curve)


def phrase_role(local_bar: int, section_bars: int) -> str:
    phrase_bar = local_bar % 8
    has_development = section_bars >= 16 and local_bar >= 8
    if phrase_bar < 2:
        return "establish"
    if phrase_bar < 4:
        return "repeat"
    if phrase_bar < 6:
        return "develop" if has_development else "lift"
    if phrase_bar == 6:
        return "lift"
    return "transition"


def lead_phrase_stage(local_bar: int, section_bars: int, is_second_pass: bool) -> str:
    phrase_bar = local_bar % 8
    if phrase_bar < 2:
        return "phrase_a"
    if phrase_bar < 4:
        return "phrase_a_repeat"
    if phrase_bar < 6:
        return "phrase_b"
    return "payoff"


def evolve_lead_phrase(phrase, stage: str, lead_archetype: str, anchor: int, support_note: int, lift: int, resolve: int, high_anchor: int, root_note: int, third_note: int):
    source = sorted(list(phrase), key=lambda item: item[0])
    motif_a = source[0][2] if source else anchor
    motif_b = source[1][2] if len(source) > 1 else support_note
    motif_c = source[2][2] if len(source) > 2 else lift
    if stage == "phrase_a":
        return [
            (0.0, 0.75, clamp(motif_a, 60, 98)),
            (1.5, 0.5, clamp(motif_b, 60, 98)),
            (3.0, 1.0, clamp(support_note if lead_archetype == "yearning" else motif_a, 60, 98)),
        ]
    if stage == "phrase_a_repeat":
        return [
            (0.0, 0.75, clamp(motif_a, 60, 98)),
            (1.75, 0.45, clamp(motif_b, 60, 98)),
            (2.75, 0.5, clamp(motif_c if lead_archetype != "driving" else motif_b, 60, 98)),
            (3.25, 0.75, clamp(lift if lead_archetype != "yearning" else support_note, 60, 98)),
        ]
    if stage == "phrase_b":
        return [
            (0.0, 0.5, clamp(motif_b, 60, 98)),
            (1.0, 0.45, clamp(motif_c, 60, 98)),
            (2.25, 0.5, clamp(lift if lead_archetype != "yearning" else support_note, 60, 100)),
            (3.0, 1.0, clamp(high_anchor if lead_archetype in ("anthemic", "uplift_hook") else resolve, 60, 100)),
        ]
    return [
        (0.0, 0.7, clamp(motif_a, 60, 98)),
        (1.75, 0.5, clamp(motif_b, 60, 98)),
        (3.0, 1.25, clamp(third_note if lead_archetype == "yearning" else root_note, 60, 98)),
    ]


def countermelody_answer_from_lead(lead_phrase, identity, chord, stage: str, counter_role: str, counter_register: str, progression_family: str):
    if not lead_phrase:
        return []
    answer = []
    answer_shift = {
        "phrase_a": 1.5,
        "phrase_a_repeat": 1.75,
        "phrase_b": 1.25,
        "payoff": 1.0,
    }[stage]
    for idx, (beat, length, pitch) in enumerate(lead_phrase[:3]):
        answer_beat = min(3.75, max(answer_shift, beat + answer_shift))
        answer_pitch = pitch - 7 if progression_family != "hopeful_pull" else pitch - 5
        if counter_role == "featured_answer":
            answer_pitch += 12
        elif counter_role == "late_answer":
            answer_beat = min(3.75, max(2.5, answer_beat + 0.25))
        elif counter_role == "transition_push":
            answer_pitch += 5 if idx == len(lead_phrase[:3]) - 1 else 0
        answer_len = max(0.16, min(0.4, length * (0.7 if stage != "payoff" else 0.9)))
        answer.append((answer_beat, answer_len, answer_pitch))
    if counter_register == "low_lane":
        answer = [(beat, length, clamp(pitch - 12, 48, 78)) for beat, length, pitch in answer]
    elif counter_register == "mid_lane":
        answer = [(beat, length, clamp(pitch, 55, 86)) for beat, length, pitch in answer]
    elif counter_register == "high_lane":
        answer = [(beat, length, clamp(pitch + 12, 67, 96)) for beat, length, pitch in answer]
    elif counter_register == "wide_lane":
        answer = [(beat, length, clamp(pitch + (12 if idx % 2 else 0), 52, 96)) for idx, (beat, length, pitch) in enumerate(answer)]
    return trance_phrase_grid(answer, step=0.25, min_length=0.16, max_events=4)


def build_counter_answer(lead_bar_notes, chord, mode: str):
    if not lead_bar_notes:
        return []
    base = sorted(lead_bar_notes, key=lambda item: item[0])
    if mode == "echo_answer":
        return [(min(3.5, beat + 1.0), max(0.4, length), clamp(pitch - 7, 55, 92)) for beat, length, pitch in base[:2] if beat + 1.0 <= 3.5]
    if mode == "octave_lift_answer":
        return [(min(3.5, max(1.5, beat + 0.5)), max(0.45, length), clamp(pitch + 12, 60, 96)) for beat, length, pitch in base[:2]]
    if mode == "long_note_glow":
        return [(2.0, 0.9, clamp(chord["third"] + 24, 60, 92)), (3.0, 0.9, clamp(chord["fifth"] + 24, 60, 96))]
    if mode == "tail_response":
        tail = base[-2:] if len(base) >= 2 else base
        return [(min(3.5, max(2.25, beat + 0.5)), max(0.5, length * 1.2), clamp(pitch + 5, 55, 94)) for beat, length, pitch in tail]
    return []


def macro_curve_adjustment(kind: str, blueprint, is_second_pass: bool, section_progress: float) -> float:
    curve = 0.0
    weight_profile = blueprint.get("section_weight_profile", "balanced")
    drop_pair_profile = blueprint.get("drop_pair_profile", "drop1_statement_drop2_upgrade")
    final_lift_profile = blueprint.get("final_lift_profile", "anthem_push")
    macro_profile = blueprint.get("macro_journey_profile", "anthem_arc")

    if weight_profile == "front_loaded":
        if not is_second_pass and kind in ("verse", "build", "drop"):
            curve += 0.06
        if is_second_pass and kind in ("build", "drop"):
            curve -= 0.05
        if kind == "breakdown":
            curve -= 0.08
    elif weight_profile == "late_bloom":
        if not is_second_pass and kind in ("intro", "verse", "build", "drop"):
            curve -= 0.06
        if kind == "breakdown":
            curve += 0.06
        if is_second_pass and kind in ("build", "drop"):
            curve += 0.1
    elif weight_profile == "breakdown_heavy":
        if kind == "breakdown":
            curve += 0.12
        if not is_second_pass and kind in ("build", "drop"):
            curve -= 0.06
        if is_second_pass and kind == "build":
            curve += 0.06

    if kind == "drop":
        if drop_pair_profile == "drop1_statement_drop2_upgrade":
            curve += 0.03 if not is_second_pass else 0.08
        elif drop_pair_profile == "drop1_tight_drop2_emotional":
            curve += -0.05 if not is_second_pass else 0.1
        elif drop_pair_profile == "drop1_full_drop2_wider":
            curve += 0.07 if not is_second_pass else 0.1
        elif drop_pair_profile == "drop1_tease_drop2_release":
            curve += -0.08 if not is_second_pass else 0.14
    elif kind == "build":
        if drop_pair_profile == "drop1_tease_drop2_release" and not is_second_pass:
            curve -= 0.04
        elif drop_pair_profile in ("drop1_tight_drop2_emotional", "drop1_tease_drop2_release") and is_second_pass:
            curve += 0.08

    if macro_profile == "breakdown_rebirth":
        if kind == "breakdown":
            curve += 0.08
        elif is_second_pass and kind in ("build", "drop"):
            curve += 0.05
    elif macro_profile == "drop_pressure":
        if kind in ("build", "drop"):
            curve += 0.06
        elif kind == "breakdown":
            curve -= 0.08
    elif macro_profile == "vocal_journey":
        if kind in ("verse", "breakdown"):
            curve += 0.04
        elif kind == "drop" and not is_second_pass:
            curve -= 0.03

    if is_second_pass and kind in ("build", "drop", "outro"):
        if final_lift_profile == "subtle_return":
            curve -= 0.05
        elif final_lift_profile == "anthem_push":
            curve += 0.07
        elif final_lift_profile == "wide_release":
            curve += 0.06
        elif final_lift_profile == "hook_reinforcement":
            curve += 0.04

    if kind == "outro" and section_progress > 0.85:
        curve += 0.03 if final_lift_profile != "subtle_return" else -0.03
    return curve


def macro_contrast_profile(kind: str, role: str, blueprint, is_second_pass: bool):
    profile = {
        "support_bias": 1.0,
        "harmony_bias": 1.0,
        "saw_bias": 1.0,
        "bass_bias": 1.0,
        "drum_bias": 1.0,
        "arp_bias": 1.0,
        "topline_bias": 1.0,
        "breakdown_open": 1.0,
        "build_escalation": 1.0,
        "drop_force": 1.0,
    }
    weight_profile = blueprint.get("section_weight_profile", "balanced")
    drop_pair_profile = blueprint.get("drop_pair_profile", "drop1_statement_drop2_upgrade")
    final_lift_profile = blueprint.get("final_lift_profile", "anthem_push")
    macro_profile = blueprint.get("macro_journey_profile", "anthem_arc")

    if weight_profile == "front_loaded":
        if not is_second_pass and kind in ("verse", "build", "drop"):
            profile["support_bias"] += 0.08
            profile["bass_bias"] += 0.08
            profile["drum_bias"] += 0.08
        if kind == "breakdown":
            profile["breakdown_open"] -= 0.18
            profile["support_bias"] -= 0.06
        if is_second_pass and kind in ("build", "drop"):
            profile["support_bias"] -= 0.05
            profile["drop_force"] -= 0.04
    elif weight_profile == "late_bloom":
        if not is_second_pass and kind in ("intro", "verse", "build", "drop"):
            profile["support_bias"] -= 0.08
            profile["bass_bias"] -= 0.08
            profile["drum_bias"] -= 0.08
        if kind == "breakdown":
            profile["breakdown_open"] += 0.1
        if is_second_pass and kind in ("build", "drop"):
            profile["support_bias"] += 0.1
            profile["harmony_bias"] += 0.08
            profile["saw_bias"] += 0.08
            profile["build_escalation"] += 0.08
            profile["drop_force"] += 0.1
    elif weight_profile == "breakdown_heavy":
        if kind == "breakdown":
            profile["breakdown_open"] += 0.18
            profile["support_bias"] += 0.06
            profile["topline_bias"] += 0.08
        if not is_second_pass and kind in ("build", "drop"):
            profile["drop_force"] -= 0.08
            profile["support_bias"] -= 0.06
        if is_second_pass and kind in ("build", "drop"):
            profile["build_escalation"] += 0.08
            profile["drop_force"] += 0.06

    if kind == "drop":
        if drop_pair_profile == "drop1_statement_drop2_upgrade":
            if is_second_pass:
                profile["support_bias"] += 0.08
                profile["saw_bias"] += 0.08
                profile["drop_force"] += 0.1
            else:
                profile["drop_force"] += 0.04
        elif drop_pair_profile == "drop1_tight_drop2_emotional":
            if is_second_pass:
                profile["harmony_bias"] += 0.12
                profile["support_bias"] += 0.1
                profile["saw_bias"] += 0.08
                profile["drop_force"] += 0.08
            else:
                profile["support_bias"] -= 0.08
                profile["drop_force"] -= 0.08
                profile["bass_bias"] -= 0.04
        elif drop_pair_profile == "drop1_full_drop2_wider":
            if is_second_pass:
                profile["support_bias"] += 0.1
                profile["harmony_bias"] += 0.12
                profile["saw_bias"] += 0.14
                profile["drop_force"] += 0.1
            else:
                profile["support_bias"] += 0.06
                profile["drop_force"] += 0.08
        elif drop_pair_profile == "drop1_tease_drop2_release":
            if is_second_pass:
                profile["support_bias"] += 0.14
                profile["harmony_bias"] += 0.12
                profile["saw_bias"] += 0.14
                profile["bass_bias"] += 0.08
                profile["drum_bias"] += 0.08
                profile["drop_force"] += 0.14
            else:
                profile["support_bias"] -= 0.12
                profile["saw_bias"] -= 0.12
                profile["drop_force"] -= 0.12
                profile["bass_bias"] -= 0.08
    elif kind == "build":
        if drop_pair_profile in ("drop1_tight_drop2_emotional", "drop1_tease_drop2_release"):
            if is_second_pass:
                profile["build_escalation"] += 0.14
                profile["arp_bias"] += 0.08
                profile["topline_bias"] += 0.08
            else:
                profile["build_escalation"] -= 0.06
        elif drop_pair_profile == "drop1_full_drop2_wider" and not is_second_pass:
            profile["build_escalation"] += 0.05

    if macro_profile == "breakdown_rebirth":
        if kind == "breakdown":
            profile["breakdown_open"] += 0.1
        if is_second_pass and kind in ("build", "drop"):
            profile["support_bias"] += 0.06
            profile["drop_force"] += 0.06
    elif macro_profile == "drop_pressure":
        if kind in ("build", "drop"):
            profile["drum_bias"] += 0.06
            profile["bass_bias"] += 0.06
            profile["drop_force"] += 0.06
        if kind == "breakdown":
            profile["breakdown_open"] -= 0.12
    elif macro_profile == "vocal_journey":
        if kind in ("verse", "breakdown"):
            profile["topline_bias"] += 0.08
            profile["support_bias"] -= 0.04
    elif macro_profile == "anthem_arc":
        if kind in ("build", "drop"):
            profile["support_bias"] += 0.03

    if is_second_pass and kind in ("build", "drop", "outro"):
        if final_lift_profile == "subtle_return":
            profile["support_bias"] -= 0.08
            profile["drum_bias"] -= 0.06
            profile["bass_bias"] -= 0.04
            profile["drop_force"] -= 0.06
        elif final_lift_profile == "anthem_push":
            profile["drum_bias"] += 0.1
            profile["bass_bias"] += 0.08
            profile["drop_force"] += 0.08
        elif final_lift_profile == "wide_release":
            profile["support_bias"] += 0.1
            profile["harmony_bias"] += 0.12
            profile["saw_bias"] += 0.1
        elif final_lift_profile == "hook_reinforcement":
            profile["topline_bias"] += 0.1
            profile["support_bias"] += 0.04

    if role in ("lift", "transition") and kind in ("build", "drop"):
        profile["build_escalation"] += 0.04
        profile["drop_force"] += 0.03
    return profile


def callback_multiplier(callback_density: str, kind: str, role: str, is_second_pass: bool) -> float:
    base = {"subtle": 0.65, "balanced": 0.9, "strong": 1.15}[callback_density]
    if kind == "drop":
        base += 0.1
    if kind == "build" and role in ("lift", "transition"):
        base += 0.08
    if kind == "breakdown":
        base += 0.04
    if is_second_pass and kind in ("build", "drop"):
        base += 0.12
    return min(1.35, base)


def theme_fragment_for_role(identity, blueprint, chord, role: str, register_shift: int = 0):
    style = blueprint["hook_recall_style"]
    fragment = identity["theme_fragment"][:]
    if style == "interval_memory":
        fragment = [identity["theme_anchor"], identity["support"], identity["lift"], identity["resolve"]]
    elif style == "rhythmic_shadow":
        fragment = [identity["anchor"], identity["support"], identity["anchor"], identity["lift"], identity["resolve"]]
    elif style == "emotive_fragment":
        fragment = [identity["support"], identity["theme_anchor"], identity["lift"], identity["resolve"]]
    if role == "develop":
        fragment = fragment[1:] + fragment[:1]
    elif role == "lift":
        fragment = fragment[:]
        fragment[-1] = max(fragment[-1], chord["root"] + 12)
    elif role == "transition":
        fragment = fragment[:]
        fragment[-1] = max(identity["resolve"], chord["fifth"] + 12)
    return [clamp(pitch + register_shift, 48, 102) for pitch in fragment]


def theme_phrase_events(identity, blueprint, chord, role: str, register_shift: int = 0, rhythm_scale: float = 1.0):
    fragment = theme_fragment_for_role(identity, blueprint, chord, role, register_shift=register_shift)
    rhythm = [(beat, length * rhythm_scale) for beat, length in identity["theme_rhythm"]]
    count = min(len(fragment), len(rhythm))
    return [(rhythm[idx][0], rhythm[idx][1], fragment[idx]) for idx in range(count)]


def focus_hierarchy(kind: str, role: str, blueprint, is_second_pass: bool):
    focus = {"lead": 1.0, "vocal": 0.95, "harmony": 1.0, "groove": 1.0}
    relation = blueprint.get("lead_vocal_relationship", "shared_hook")
    if kind == "breakdown":
        focus["groove"] = 0.72
        if blueprint["breakdown_style"] == "vocal_focus" or blueprint["breakdown_narrative"] == "vocal_spotlight":
            focus["vocal"] = 1.35
            focus["harmony"] = 0.72
        elif blueprint["breakdown_style"] == "piano_led":
            focus["harmony"] = 1.2
            focus["lead"] = 0.88
        elif blueprint["breakdown_style"] == "arp_texture":
            focus["harmony"] = 0.85
            focus["groove"] = 0.82
    elif kind == "build":
        focus["lead"] = 1.08
        focus["groove"] = 1.08
        if role in ("lift", "transition"):
            focus["lead"] = 1.2
            focus["harmony"] = 0.9
    elif kind == "drop":
        focus["lead"] = 1.18
        focus["groove"] = 1.12
        if role in ("lift", "transition"):
            focus["lead"] = 1.28
            focus["harmony"] = 0.9
        if is_second_pass:
            focus["harmony"] += 0.08
            focus["groove"] += 0.04
    elif kind == "verse":
        focus["vocal"] = 1.1 if blueprint["vocal_archetype"] in ("held_emotive", "call_response") else 1.0
        focus["harmony"] = 0.94
    if relation == "alternating_spotlight":
        if kind in ("breakdown", "verse"):
            focus["vocal"] += 0.18
            focus["lead"] -= 0.14
        elif kind == "drop":
            focus["lead"] += 0.16
            focus["vocal"] -= 0.08
    elif relation == "lead_carries_drop_vocal_carries_breakdown":
        if kind == "breakdown":
            focus["vocal"] += 0.22
            focus["lead"] -= 0.18
        elif kind == "drop":
            focus["lead"] += 0.18
            focus["vocal"] -= 0.08

    support_duck = focus["lead"] >= 1.18 and kind in ("build", "drop")
    vocal_space = focus["vocal"] >= 1.2 and kind == "breakdown"
    return {
        **focus,
        "support_duck": support_duck,
        "vocal_space": vocal_space,
    }


def transition_profile(kind: str, role: str, blueprint, is_second_pass: bool):
    intent = blueprint["transition_intent"]
    active = role == "transition" or (kind == "build" and role == "lift")
    profile = {
        "intent": intent,
        "active": active,
        "harmonic_bloom": active and intent == "harmonic_bloom",
        "drum_pullback": active and intent == "drum_pullback",
        "pre_drop_void": active and intent == "pre_drop_void" and kind == "build",
        "snare_lift": active and intent == "snare_lift",
        "tension_riser": active and intent == "tension_riser",
    }
    if is_second_pass and kind in ("build", "drop"):
        profile["harmonic_bloom"] = profile["harmonic_bloom"] or role == "lift"
    return profile


def lead_vocal_profile(kind: str, role: str, blueprint, is_second_pass: bool):
    relation = blueprint["lead_vocal_relationship"]
    profile = {
        "relation": relation,
        "lead_gain": 1.0,
        "vocal_gain": 1.0,
        "counter_ok": True,
        "shared_hook": False,
        "lead_answers": False,
        "vocal_answers": False,
    }
    if relation == "lead_answers_vocal":
        profile["lead_answers"] = kind in ("build", "drop")
        if kind == "breakdown":
            profile["vocal_gain"] = 1.18
            profile["lead_gain"] = 0.82
        elif kind == "drop":
            profile["lead_gain"] = 1.18
            profile["counter_ok"] = role not in ("lift", "transition")
    elif relation == "vocal_answers_lead":
        profile["vocal_answers"] = kind in ("drop", "verse")
        if kind == "drop":
            profile["lead_gain"] = 1.12
            profile["vocal_gain"] = 0.92 if role in ("establish", "repeat") else 1.02
            profile["counter_ok"] = role not in ("lift", "transition")
    elif relation == "shared_hook":
        profile["shared_hook"] = kind in ("build", "drop", "breakdown")
        profile["lead_gain"] = 1.12 if kind == "drop" else 0.95
        profile["vocal_gain"] = 1.08 if kind in ("breakdown", "build") else 0.96
        profile["counter_ok"] = kind != "drop" or role == "transition"
    elif relation == "alternating_spotlight":
        if kind in ("breakdown", "verse"):
            profile["vocal_gain"] = 1.22
            profile["lead_gain"] = 0.78
            profile["counter_ok"] = False
        elif kind == "drop":
            profile["lead_gain"] = 1.25
            profile["vocal_gain"] = 0.82 if role in ("establish", "repeat") else 0.96
            profile["counter_ok"] = role == "transition"
    else:
        if kind == "breakdown":
            profile["vocal_gain"] = 1.28
            profile["lead_gain"] = 0.72
            profile["counter_ok"] = False
        elif kind == "drop":
            profile["lead_gain"] = 1.24
            profile["vocal_gain"] = 0.8 if role in ("establish", "repeat") else 0.92
            profile["counter_ok"] = role == "transition"
    if is_second_pass and kind == "drop":
        profile["lead_gain"] += 0.06
        if relation in ("shared_hook", "vocal_answers_lead"):
            profile["vocal_gain"] += 0.08
    return profile


def top_line_ownership(kind: str, role: str, relation_profile, is_second_pass: bool):
    relation = relation_profile["relation"]
    ownership = {
        "lead": "full",
        "vocal": "full" if kind in ("verse", "build", "breakdown") else "none",
        "counter": "normal",
    }
    if relation == "lead_answers_vocal":
        if kind == "breakdown":
            ownership["lead"] = "none" if role in ("establish", "repeat") else "late"
            ownership["vocal"] = "full"
            ownership["counter"] = "none"
        elif kind == "build":
            ownership["lead"] = "late"
            ownership["vocal"] = "early"
            ownership["counter"] = "none"
        elif kind == "drop":
            ownership["lead"] = "full"
            ownership["vocal"] = "none"
            ownership["counter"] = "late" if role == "transition" else "none"
    elif relation == "vocal_answers_lead":
        if kind == "verse":
            ownership["lead"] = "early"
            ownership["vocal"] = "late"
            ownership["counter"] = "none"
        elif kind == "drop":
            ownership["lead"] = "early"
            ownership["vocal"] = "late" if is_second_pass or role in ("lift", "transition") else "none"
            ownership["counter"] = "none"
        elif kind == "breakdown":
            ownership["lead"] = "none"
            ownership["vocal"] = "full"
            ownership["counter"] = "none"
    elif relation == "shared_hook":
        if kind == "build":
            ownership["lead"] = "late"
            ownership["vocal"] = "early"
            ownership["counter"] = "none"
        elif kind == "drop":
            ownership["lead"] = "full"
            ownership["vocal"] = "echo" if is_second_pass or role in ("lift", "transition") else "none"
            ownership["counter"] = "none"
        elif kind == "breakdown":
            ownership["lead"] = "none"
            ownership["vocal"] = "full"
            ownership["counter"] = "none"
    elif relation == "alternating_spotlight":
        if kind in ("verse", "breakdown"):
            ownership["lead"] = "none"
            ownership["vocal"] = "full"
            ownership["counter"] = "none"
        elif kind == "drop":
            ownership["lead"] = "full"
            ownership["vocal"] = "none" if role in ("establish", "repeat") else "late"
            ownership["counter"] = "transition_only"
        elif kind == "build":
            ownership["lead"] = "late"
            ownership["vocal"] = "early"
            ownership["counter"] = "none"
    else:
        if kind == "breakdown":
            ownership["lead"] = "none"
            ownership["vocal"] = "full"
            ownership["counter"] = "none"
        elif kind == "drop":
            ownership["lead"] = "full"
            ownership["vocal"] = "echo" if is_second_pass or role in ("lift", "transition") else "none"
            ownership["counter"] = "transition_only"
        elif kind == "build":
            ownership["lead"] = "late"
            ownership["vocal"] = "full" if role in ("establish", "repeat") else "early"
            ownership["counter"] = "none"
    return ownership


def support_state_factor(state: str) -> float:
    return {
        "spotlight": 1.08,
        "support": 1.0,
        "shadow": 0.62,
        "silent": 0.0,
        "response": 0.82,
    }.get(state, 1.0)


def arrangement_support_profile(kind: str, role: str, local_bar: int, blueprint, is_second_pass: bool):
    relation = lead_vocal_profile(kind, role, blueprint, is_second_pass)
    ownership = top_line_ownership(kind, role, relation, is_second_pass)
    primary = "shared"

    if ownership["vocal"] in ("full", "early") and ownership["lead"] in ("none", "late"):
        primary = "vocal"
    elif ownership["lead"] in ("full", "early") and ownership["vocal"] in ("none", "late"):
        primary = "lead"
    elif role == "transition" or ownership["lead"] in ("echo", "late") or ownership["vocal"] in ("echo", "late"):
        primary = "response"

    profile = {
        "primary": primary,
        "ownership": ownership,
        "relation": relation["relation"],
        "supersaw": "support",
        "pad": "support",
        "strings": "support",
        "arp": "support",
        "bass": "support",
        "drums": "support",
        "piano": "support",
        "pluck": "support",
    }

    if primary == "vocal":
        profile.update({
            "supersaw": "silent" if kind == "breakdown" else "shadow",
            "pad": "shadow",
            "strings": "shadow",
            "arp": "silent" if kind in ("breakdown", "drop") else "shadow",
            "bass": "shadow" if kind == "breakdown" else "support",
            "drums": "shadow",
            "piano": "response" if kind == "breakdown" else "shadow",
            "pluck": "shadow",
        })
    elif primary == "lead":
        profile.update({
            "supersaw": "shadow" if kind == "drop" else "support",
            "pad": "support",
            "strings": "shadow",
            "arp": "shadow",
            "bass": "support",
            "drums": "support",
            "piano": "shadow" if kind in ("build", "drop") else "support",
            "pluck": "support" if kind == "build" else "shadow",
        })
    elif primary == "response":
        profile.update({
            "supersaw": "response" if kind in ("build", "drop") else "shadow",
            "pad": "support",
            "strings": "response",
            "arp": "response",
            "bass": "response" if kind in ("build", "drop") else "support",
            "drums": "response",
            "piano": "response",
            "pluck": "response" if kind == "build" else "shadow",
        })
    else:
        profile.update({
            "supersaw": "response" if kind == "drop" else "shadow",
            "pad": "support",
            "strings": "support",
            "arp": "shadow",
            "bass": "support",
            "drums": "support",
            "piano": "support",
            "pluck": "support",
        })

    if kind == "build" and role == "transition":
        profile["supersaw"] = "silent"
        profile["pad"] = "shadow"
        profile["strings"] = "silent"
        profile["arp"] = "silent"
        profile["bass"] = "shadow"
        profile["drums"] = "response"
        profile["pluck"] = "response"
    if kind == "drop" and role in ("establish", "repeat") and primary == "lead":
        profile["supersaw"] = "shadow"
        profile["arp"] = "silent"
        profile["strings"] = "shadow"
    if kind == "breakdown" and primary == "vocal":
        profile["drums"] = "silent"
        profile["bass"] = "shadow"

    progression_family = blueprint["progression_family"]
    cadence_profile = blueprint["cadence_profile"]
    harmony_entry = blueprint["drop_harmony_entry"]
    density_profile = blueprint.get("arrangement_density_profile", "continuous")
    if progression_family == "lifted":
        if kind == "drop":
            profile["supersaw"] = "response" if primary in ("lead", "shared") else profile["supersaw"]
            profile["strings"] = "response" if role in ("lift", "transition") else profile["strings"]
    elif progression_family == "festival_cycle":
        if kind == "drop":
            profile["supersaw"] = "support"
            profile["arp"] = "shadow" if primary == "lead" else profile["arp"]
            profile["bass"] = "support"
    elif progression_family == "hopeful_pull":
        if kind in ("breakdown", "drop"):
            profile["supersaw"] = "silent" if primary == "vocal" or harmony_entry == "delayed_bloom" else "shadow"
            profile["strings"] = "response" if role in ("lift", "transition") else "shadow"
            profile["arp"] = "shadow" if kind == "drop" else profile["arp"]
    elif progression_family == "classic_warmth":
        if kind in ("breakdown", "drop"):
            profile["piano"] = "support"
            profile["strings"] = "shadow" if primary == "lead" else profile["strings"]

    if cadence_profile == "delayed_resolve" and kind == "drop":
        profile["supersaw"] = "response" if profile["supersaw"] != "silent" else "silent"
    elif cadence_profile == "direct_loop" and kind == "drop":
        profile["supersaw"] = "support"
        profile["bass"] = "support"

    second_drop_stage = second_drop_cleanup_stage(kind, local_bar, is_second_pass)
    if second_drop_stage == "entry":
        if profile["primary"] != "vocal":
            profile["primary"] = "lead"
        profile["supersaw"] = "shadow" if profile["supersaw"] != "silent" else "silent"
        profile["pad"] = "shadow" if profile["pad"] != "silent" else "silent"
        profile["strings"] = "silent"
        profile["arp"] = "silent"
        profile["piano"] = "shadow" if profile["piano"] != "silent" else "silent"
        profile["pluck"] = "shadow" if profile["pluck"] != "silent" else "silent"
    elif second_drop_stage == "settle":
        if profile["primary"] == "response":
            profile["primary"] = "lead"
        if profile["supersaw"] == "support":
            profile["supersaw"] = "shadow"
        if profile["strings"] == "support":
            profile["strings"] = "shadow"
        if profile["arp"] == "support":
            profile["arp"] = "shadow"
        if profile["piano"] == "support":
            profile["piano"] = "shadow"

    if density_profile == "staggered":
        if kind == "verse":
            if local_bar < 2:
                profile["supersaw"] = "silent"
                profile["strings"] = "silent" if local_bar == 0 else "shadow"
                profile["piano"] = "shadow" if profile["piano"] != "silent" else "silent"
                profile["pluck"] = "silent"
                profile["arp"] = "silent"
            elif local_bar < 4:
                if profile["strings"] == "support":
                    profile["strings"] = "response"
                if profile["piano"] == "support":
                    profile["piano"] = "response"
        elif kind == "drop" and role in ("establish", "repeat"):
            if profile["pad"] == "support":
                profile["pad"] = "shadow"
            if profile["strings"] == "support":
                profile["strings"] = "shadow"
            if profile["arp"] == "support":
                profile["arp"] = "response"
    elif density_profile == "breathing":
        if kind == "drop":
            if local_bar % 2 == 0:
                if profile["pad"] == "support":
                    profile["pad"] = "shadow"
                if profile["strings"] == "support":
                    profile["strings"] = "response"
            else:
                if profile["arp"] == "support":
                    profile["arp"] = "shadow"
                if profile["piano"] == "support":
                    profile["piano"] = "response"
        elif kind == "build" and role in ("establish", "repeat"):
            profile["strings"] = "silent" if profile["strings"] != "silent" else "silent"
            if profile["pad"] == "support":
                profile["pad"] = "shadow"
    elif density_profile == "spotlight":
        if kind == "verse":
            profile["supersaw"] = "silent"
            if local_bar < 2:
                profile["strings"] = "silent"
                profile["arp"] = "silent"
                profile["pluck"] = "silent"
        elif kind == "drop" and role in ("establish", "repeat"):
            profile["arp"] = "silent"
            if profile["strings"] == "support":
                profile["strings"] = "shadow"
    if kind == "drop":
        budget = int(blueprint.get("drop_layer_budget", 5))
        priorities = {
            "supersaw": 100,
            "strings": 84 if role in ("lift", "transition") else 76,
            "arp": 70 if profile["primary"] != "vocal" else 52,
            "pad": 52 if role in ("lift", "transition") else 42,
            "piano": 44 if progression_family in ("lifted", "classic_warmth") else 36,
            "pluck": 40 if role in ("establish", "repeat") else 32,
        }
        if blueprint.get("countermelody_engine") == "late_bloom":
            priorities["strings"] += 4
            priorities["arp"] -= 6
        elif blueprint.get("countermelody_engine") == "shadow_hook":
            priorities["piano"] += 2
            priorities["pad"] -= 4
        active = [lane for lane in ("supersaw", "pad", "strings", "arp", "piano", "pluck") if profile[lane] != "silent"]
        active_sorted = sorted(active, key=lambda lane: priorities.get(lane, 0), reverse=True)
        keep = set(active_sorted[:budget])
        for lane in active:
            if lane not in keep:
                profile[lane] = "shadow" if lane in ("pad", "strings") else "silent"
        if "supersaw" not in keep and profile["supersaw"] != "silent":
            profile["supersaw"] = "shadow"
        secondary_lanes = [lane for lane in ("arp", "strings") if profile[lane] != "silent"]
        if len(secondary_lanes) > 2:
            secondary_keep = set(sorted(secondary_lanes, key=lambda lane: priorities.get(lane, 0), reverse=True)[:2])
            for lane in secondary_lanes:
                if lane not in secondary_keep:
                    profile[lane] = "shadow" if lane == "strings" else "silent"
        tertiary_lanes = [lane for lane in ("pad", "piano", "pluck") if profile[lane] != "silent"]
        tertiary_limit = 1 if role in ("lift", "transition") else 0
        tertiary_keep = set(sorted(tertiary_lanes, key=lambda lane: priorities.get(lane, 0), reverse=True)[:tertiary_limit])
        for lane in tertiary_lanes:
            if lane not in tertiary_keep:
                profile[lane] = "silent"
    return profile


def progression_voicing(chord, blueprint, kind: str, role: str, is_second_pass: bool, harmonic_state=None):
    profile = blueprint["voicing_profile"]
    if profile == "open_air":
        root_low = chord["root"] - 12
        spread = [root_low, chord["root"], chord["fifth"], chord["third"] + 12, chord["root"] + 24]
        pad_shell = [root_low, chord["third"] - 12]
        bloom = [chord["fifth"] + 12, chord["root"] + 24]
    elif profile == "mid_stack":
        root_low = chord["root"] - 12
        spread = [root_low, chord["root"], chord["third"], chord["fifth"], chord["third"] + 12]
        pad_shell = [root_low, chord["third"] - 12, chord["fifth"] - 12]
        bloom = [chord["third"] + 12, chord["fifth"] + 12]
    elif profile == "low_fifth_power":
        root_low = chord["root"] - 24
        spread = [root_low, chord["fifth"] - 12, chord["root"], chord["fifth"], chord["root"] + 12]
        pad_shell = [root_low, chord["fifth"] - 12]
        bloom = [chord["root"] + 12, chord["fifth"] + 12]
    else:
        root_low = chord["root"] - 12
        spread = [root_low, chord["third"] - 12, chord["root"], chord["fifth"] + 12, chord["root"] + 24]
        pad_shell = [root_low, chord["third"] - 12]
        bloom = [chord["third"] + 12, chord["root"] + 24]
    if harmonic_state is not None:
        base_pad = build_pad_voicing_from_harmonic_state(chord, harmonic_state)
        pad_shell = sorted(dict.fromkeys(base_pad))
        bloom = sorted(dict.fromkeys([p + 12 for p in harmonic_state["primary_pitches"][:2]] + [chord["root"] + 12]))
        spread = sorted(dict.fromkeys([root_low] + build_supersaw_voicing_from_harmonic_state(chord, harmonic_state, max_pitch=84)))
    if kind == "drop" and is_second_pass:
        spread = spread + [chord["root"] + 24]
    if role == "transition":
        bloom = bloom + [chord["root"] + 24]
    return {
        "root_low": root_low,
        "spread": spread,
        "pad_shell": pad_shell,
        "bloom": bloom,
    }


def progression_cadence_events(chord, blueprint, role: str):
    if role not in ("lift", "transition"):
        return []
    profile = blueprint["cadence_profile"]
    if profile == "tonic_lift":
        return [(3.0, 0.75, [chord["root"] + 12, chord["fifth"] + 12])]
    if profile == "smooth_land":
        return [(3.0, 0.75, [chord["third"] + 12, chord["fifth"] + 12])]
    if profile == "direct_loop":
        return [(2.75, 0.85, [chord["root"], chord["fifth"], chord["root"] + 12])]
    return [(3.0, 0.9, [chord["third"] + 12, chord["root"] + 24])]


def supersaw_shape_notes(identity_name: str, spread, chord, root_low: int, inversion_variant: str, harmonic_state=None):
    if harmonic_state is not None:
        notes = build_supersaw_voicing_from_harmonic_state(chord, harmonic_state, max_pitch=84)
        return sorted(dict.fromkeys([root_low] + notes))
    if identity_name == "wall_stack":
        notes = spread[:]
    elif identity_name == "pulse_stack":
        notes = [root_low, chord["root"], chord["fifth"], chord["root"] + 12]
    elif identity_name == "bloom_stack":
        notes = [root_low, chord["third"], chord["fifth"] + 12]
    else:
        notes = [root_low, chord["fifth"] - 12, chord["root"] + 12, chord["fifth"] + 12, chord["root"] + 24]

    if inversion_variant == "wide_top":
        notes = notes + [chord["third"] + 12]
    elif inversion_variant == "fifth_heavy":
        notes = [root_low, chord["fifth"] - 12, chord["fifth"], chord["root"] + 12, chord["fifth"] + 12]
    elif inversion_variant == "mid_open":
        notes = [root_low, chord["root"], chord["third"], chord["fifth"] + 12]
    return sorted(dict.fromkeys(notes))


def chord_hits(style: str, chord, root_low: int, intensity: float, role: str, harmonic_state=None):
    harmonic_chord = build_pad_voicing_from_harmonic_state(chord, harmonic_state) if harmonic_state is not None else chord["notes"]
    if style == "block":
        if role == "transition":
            return [(0.0, 3.0, harmonic_chord + [root_low]), (3.25, 0.5, [harmonic_chord[-1], harmonic_chord[0] + 12])]
        if role == "lift":
            return [(0.0, 2.5, harmonic_chord + [root_low]), (2.5, 1.0, [harmonic_chord[0] + 12, harmonic_chord[-1] + 12])]
        return [(0.0, 4.0, harmonic_chord + [root_low])]
    if style == "rhythmic":
        if role == "develop":
            return [(0.0, 0.72, harmonic_chord), (1.0, 0.62, harmonic_chord), (2.0, 0.72, harmonic_chord), (3.25, 0.45, harmonic_chord)]
        if role == "transition":
            return [(0.0, 0.72, harmonic_chord), (1.5, 0.55, harmonic_chord), (2.5, 0.45, harmonic_chord), (3.25, 0.35, harmonic_chord[:2])]
        return [(beat, 0.82, harmonic_chord) for beat in (0.0, 1.0, 2.0, 3.0)]
    if style == "syncopated":
        if role == "lift":
            return [(0.0, 0.8, chord["notes"]), (1.25, 0.7, chord["notes"]), (2.5, 0.65, chord["notes"]), (3.25, 0.35, [chord["root"] + 12])]
        if role == "transition":
            return [(0.0, 0.75, chord["notes"]), (1.5, 0.55, chord["notes"]), (2.75, 0.4, chord["notes"]), (3.5, 0.2, [chord["fifth"] + 12])]
        return [(0.0, 1.0, chord["notes"]), (1.5, 0.9, chord["notes"]), (2.75, 0.95, chord["notes"])]
    if style == "broken_chord":
        order = [chord["root"], chord["third"], chord["fifth"], chord["third"]]
        if role == "develop":
            order = [chord["third"], chord["fifth"], chord["root"] + 12, chord["fifth"]]
        elif role == "lift":
            order = [chord["root"], chord["third"], chord["fifth"], chord["root"] + 12, chord["fifth"]]
        elif role == "transition":
            order = [chord["root"], chord["third"], chord["fifth"], chord["third"], chord["root"] + 12, chord["fifth"] + 12]
        if intensity > 0.8:
            order += [chord["root"] + 12, chord["fifth"]]
        return [(idx * 0.5, 0.42, pitch) for idx, pitch in enumerate(order)]
    wide = [root_low, chord["fifth"] - 12, chord["third"] + 12, chord["fifth"] + 12]
    if role == "lift":
        wide = [root_low, chord["root"], chord["third"] + 12, chord["fifth"] + 12, chord["root"] + 24]
    elif role == "transition":
        return [(0.0, 3.0, wide), (3.0, 0.75, [chord["third"] + 12, chord["root"] + 24])]
    return [(0.0, 4.0, wide)]


def add_harmony(tracks, start_tick: int, chord, kind: str, local_bar: int, section_bars: int, intensity: float, blueprint, identity, is_second_pass: bool):
    style = blueprint["chord_style"]
    breakdown_style = blueprint["breakdown_style"]
    breakdown_narrative = blueprint["breakdown_narrative"]
    arrival = blueprint["drop_arrival_style"]
    role = phrase_role(local_bar, section_bars)
    section_name = section_display_name(kind, is_second_pass)
    supersaw_energy = get_supersaw_energy(section_name)
    recall_amount = callback_multiplier(blueprint["callback_density"], kind, role, is_second_pass)
    focus = focus_hierarchy(kind, role, blueprint, is_second_pass)
    transition = transition_profile(kind, role, blueprint, is_second_pass)
    support = arrangement_support_profile(kind, role, local_bar, blueprint, is_second_pass)
    breakdown_focus = blueprint["archetype_breakdown_focus"]
    support_timing = blueprint["archetype_support_timing"]
    harmony_emphasis = blueprint["archetype_harmony_emphasis"]
    supersaw_motion = blueprint["archetype_supersaw_motion"]
    pluck_grammar = blueprint["archetype_pluck_grammar"]
    breakdown_function = blueprint.get("breakdown_function", "harmonic_lift")
    weight_profile = blueprint.get("section_weight_profile", "balanced")
    drop_pair_profile = blueprint.get("drop_pair_profile", "drop1_statement_drop2_upgrade")
    final_lift_profile = blueprint.get("final_lift_profile", "anthem_push")
    macro_profile = blueprint.get("macro_journey_profile", "anthem_arc")
    drop_role = drop_section_role(blueprint, is_second_pass)
    finish_factor = finishability_factor(blueprint)
    saw_variant = bounded_variant(blueprint, "variant_saw_gain")
    strings_variant = bounded_variant(blueprint, "variant_strings_gain")
    arp_variant = bounded_variant(blueprint, "variant_arp_gain")
    support_spread = blueprint.get("variant_support_spread", "balanced")
    string_entry = blueprint.get("variant_string_entry", "mid")
    supersaw_ceiling = blueprint.get("variant_supersaw_ceiling", "balanced")
    outro_stage = outro_release_stage(local_bar, section_bars) if kind == "outro" else "full"
    second_drop_stage = second_drop_cleanup_stage(kind, local_bar, is_second_pass)
    build_stage = build_story_stage(kind, local_bar, section_bars, is_second_pass)
    breakdown_stage = breakdown_story_stage(local_bar, section_bars) if kind == "breakdown" else None
    macro = macro_contrast_profile(kind, role, blueprint, is_second_pass)
    bar_index = start_tick // BAR_TICKS
    harmonic_state = build_harmonic_state(
        bar_index,
        blueprint.get("progression_name", identity.get("progression_name", "uplifting")),
        chord,
        blueprint.get("progression_family", ""),
    )
    primary_targets = harmonic_target_pool(harmonic_state, octave_shift=12)["primary"]
    prog_voicing = progression_voicing(chord, blueprint, kind, role, is_second_pass, harmonic_state=harmonic_state)
    root_low = prog_voicing["root_low"]
    hits = chord_hits(style, chord, root_low, intensity, role, harmonic_state=harmonic_state)
    cadence_hits = progression_cadence_events(chord, blueprint, role)
    hits = hits + cadence_hits
    pad_entry_open = early_verse_allows(kind, local_bar, "pad")
    piano_entry_open = early_verse_allows(kind, local_bar, "piano")
    string_entry_open = early_verse_allows(kind, local_bar, "strings")
    verse_harmony_stage = verse_harmonic_stage(kind, local_bar)
    harmony_authority = exposed_harmonic_authority(kind, role, verse_harmony_stage, breakdown_style, breakdown_focus)

    pad_level = clamp(int((48 + intensity * 26) * focus["harmony"] * support_state_factor(support["pad"]) * macro["support_bias"] * macro["harmony_bias"]), 0, 98)
    piano_level = clamp(int((54 + intensity * 24) * max(focus["harmony"], focus["vocal"] if focus["vocal_space"] else 0.95) * support_state_factor(support["piano"]) * macro["harmony_bias"]), 0, 110)
    saw_level = clamp(int((78 + intensity * 30) * focus["harmony"] * support_state_factor(support["supersaw"]) * macro["support_bias"] * macro["saw_bias"]), 0, 124)
    string_level = clamp(int((44 + intensity * 22) * focus["harmony"] * support_state_factor(support["strings"]) * macro["support_bias"] * macro["harmony_bias"]), 0, 102)
    pluck_level = clamp(int((60 + intensity * 24) * focus["harmony"] * support_state_factor(support["pluck"]) * macro["build_escalation"]), 0, 114)
    if kind in ("build", "drop"):
        pad_level = clamp(int(pad_level * finish_factor), 0, 98)
        piano_level = clamp(int(piano_level * finish_factor), 0, 110)
        saw_level = clamp(int(saw_level * finish_factor * saw_variant), 0, 122)
        string_level = clamp(int(string_level * finish_factor * strings_variant), 0, 100)
        pluck_level = clamp(int(pluck_level * finish_factor * arp_variant), 0, 112)
        if support_spread == "narrow":
            pad_level = clamp(pad_level - 4, 0, 96)
            string_level = clamp(string_level - 4, 0, 98)
        elif support_spread == "wide":
            pad_level = clamp(pad_level + 4, 0, 100)
            string_level = clamp(string_level + 4, 0, 102)
    saw_level = clamp(int(saw_level * (0.45 + supersaw_energy * 0.75)), 0, 124)

    if harmony_emphasis == "pad_anchor":
        pad_level = clamp(pad_level + 10, 0, 100)
        piano_level = clamp(piano_level - 8, 0, 102)
        string_level = clamp(string_level + 4, 0, 96)
    elif harmony_emphasis == "piano_answer":
        piano_level = clamp(piano_level + 14, 0, 112)
        pad_level = clamp(pad_level - 10, 0, 92)
        string_level = clamp(string_level - 6, 0, 94)
    elif harmony_emphasis == "string_lift":
        string_level = clamp(string_level + 14, 0, 106)
        pad_level = clamp(pad_level - 6, 0, 92)
    elif harmony_emphasis == "split_layers":
        piano_level = clamp(piano_level + 6, 0, 108)
        string_level = clamp(string_level + 8, 0, 100)
        pad_level = clamp(pad_level - 4, 0, 92)

    if kind in ("intro", "verse", "outro"):
        if pad_level > 0 and pad_entry_open:
            verse_hits = hits
            if support["pad"] == "shadow":
                verse_hits = hits[:max(1, len(hits) // 2)]
            if support_timing == "late_bloom":
                verse_hits = [hit for hit in verse_hits if hit[0] >= 1.0] or verse_hits[-1:]
            elif support_timing == "response_window":
                verse_hits = [hit for hit in verse_hits if hit[0] >= 2.0] or verse_hits[-1:]
            elif support_timing == "staggered_frame" and len(verse_hits) > 1:
                verse_hits = verse_hits[::2]
            if weight_profile == "late_bloom" and kind in ("intro", "verse"):
                verse_hits = [hit for hit in verse_hits if hit[0] >= 1.5] or verse_hits[-1:]
                pad_level = clamp(pad_level - 8, 0, 92)
            elif weight_profile == "front_loaded" and kind in ("intro", "verse"):
                verse_hits = hits
                pad_level = clamp(pad_level + 6, 0, 96)
            if kind == "verse":
                if verse_harmony_stage == "seed":
                    verse_hits = [(3.0, 1.0, prog_voicing["pad_shell"][:2])]
                    pad_level = clamp(pad_level - 18, 0, 88)
                elif verse_harmony_stage == "answer":
                    verse_hits = [(2.0, 1.35, prog_voicing["pad_shell"][:2])]
                    pad_level = clamp(pad_level - 12, 0, 92)
                elif verse_harmony_stage == "lift":
                    verse_hits = [(1.5, 1.6, prog_voicing["pad_shell"][:2]), (3.25, 0.45, build_pad_voicing_from_harmonic_state(chord, harmonic_state)[1:3])]
                    pad_level = clamp(pad_level - 6, 0, 94)
                if blueprint["progression_family"] == "lifted":
                    if local_bar == 0:
                        verse_hits = [
                            (1.5, 1.25, prog_voicing["pad_shell"][:2]),
                            (3.0, 0.85, build_pad_voicing_from_harmonic_state(chord, harmonic_state)[1:3]),
                        ]
                        pad_level = clamp(max(pad_level, 44), 0, 92)
                    elif local_bar == 1:
                        verse_hits = [
                            (1.0, 1.5, prog_voicing["pad_shell"][:2]),
                            (2.75, 0.8, build_pad_voicing_from_harmonic_state(chord, harmonic_state)[1:3]),
                        ]
                        pad_level = clamp(max(pad_level, 48), 0, 94)
                if blueprint["progression_family"] == "progressive_flow" and local_bar == 2:
                    verse_hits = [(1.0, 2.0, prog_voicing["pad_shell"][:2]), (3.0, 0.6, build_pad_voicing_from_harmonic_state(chord, harmonic_state)[1:3])]
                    pad_level = clamp(max(pad_level, 52), 0, 94)
            if kind == "verse" and local_bar >= 2 and len(verse_hits) < len(hits):
                verse_hits = verse_hits + hits[:1]
            if kind == "outro":
                if outro_stage == "thin":
                    verse_hits = verse_hits[:max(1, len(verse_hits) // 2)]
                    pad_level = clamp(pad_level - 8, 0, 90)
                elif outro_stage == "tail":
                    verse_hits = [(2.0, 1.8, prog_voicing["pad_shell"][:2])]
                    pad_level = clamp(pad_level - 12, 0, 86)
                elif outro_stage == "final":
                    verse_hits = [(0.0, 5.5, prog_voicing["pad_shell"][:2])]
                    pad_level = clamp(pad_level - 16, 0, 82)
            for beat_pos, beat_len, pitches in verse_hits:
                max_len = 5.5 if kind == "outro" and outro_stage == "final" else 3.8
                add_events(tracks["pad"], start_tick + tick(beat_pos), pitches, tick(min(beat_len, max_len)), velocity=pad_level)
        if kind == "verse" and piano_entry_open:
            piano_hits = authored_piano_hits(chord, role, verse_harmony_stage, blueprint["progression_family"])
            if support["piano"] == "response":
                piano_hits = [hit for hit in piano_hits if hit[0] >= 2.0] or piano_hits[-1:]
            elif support["piano"] == "shadow":
                piano_hits = piano_hits[:1]
            if harmony_emphasis == "piano_answer" and verse_harmony_stage == "full":
                piano_hits = piano_hits[-2:] if role in ("establish", "repeat") else piano_hits
            if support_timing == "late_bloom":
                piano_hits = [hit for hit in piano_hits if hit[0] >= 1.5] or piano_hits[-1:]
            elif support_timing == "response_window":
                piano_hits = [hit for hit in piano_hits if hit[0] >= 2.0] or piano_hits[-1:]
            piano_velocity = piano_level
            if verse_harmony_stage == "seed":
                piano_velocity = clamp(piano_velocity - 14, 0, 98)
            elif verse_harmony_stage == "answer":
                piano_velocity = clamp(piano_velocity - 8, 0, 102)
            if local_bar == 2:
                entry_start = 2.0
                if blueprint["progression_family"] == "progressive_flow" or support_timing in ("late_bloom", "response_window"):
                    entry_start = 2.5
                piano_hits = ease_in_harmony_hits(piano_hits, entry_start, sustain_scale=0.82)
                piano_velocity = clamp(piano_velocity - 16, 0, 96)
            if piano_level > 0:
                for beat_pos, beat_len, pitches in piano_hits:
                    add_events(tracks["piano"], start_tick + tick(beat_pos), pitches if isinstance(pitches, list) else [pitches], tick(min(beat_len, 1.5)), velocity=piano_velocity)
        if (
            kind == "verse"
            and blueprint["progression_family"] == "progressive_flow"
            and local_bar == 2
            and support["strings"] != "silent"
            and string_level > 0
        ):
            add_events(
                tracks["strings"],
                start_tick + tick(3.0),
                build_strings_from_harmonic_state(chord, harmonic_state),
                tick(0.85),
                velocity=clamp(string_level - 12, 34, 92),
            )
        if (
            kind == "verse"
            and blueprint["progression_family"] == "lifted"
            and local_bar in (0, 1)
            and support["strings"] != "silent"
            and string_level > 0
        ):
            entry_string_start = 3.0 if local_bar == 0 else 2.5
            add_events(
                tracks["strings"],
                start_tick + tick(entry_string_start),
                build_strings_from_harmonic_state(chord, harmonic_state),
                tick(0.9 if local_bar == 0 else 1.15),
                velocity=clamp(string_level - 18 + local_bar * 4, 30, 88),
            )
        if kind == "verse" and string_entry_open and support["strings"] != "silent" and string_level > 0:
            if harmony_authority == "piano_leads":
                string_hits = []
                if verse_harmony_stage == "lift":
                    string_hits = [(2.5, 1.6, build_strings_from_harmonic_state(chord, harmonic_state))]
                elif verse_harmony_stage == "rise":
                    string_hits = [(3.0, 1.4, build_strings_from_harmonic_state(chord, harmonic_state))]
                elif verse_harmony_stage == "full" and role in ("develop", "lift", "transition"):
                    string_hits = [(2.5, 1.75, build_strings_from_harmonic_state(chord, harmonic_state))]
                if support["strings"] == "response":
                    string_hits = [hit for hit in string_hits if hit[0] >= 2.5] or string_hits[-1:]
                elif support["strings"] == "shadow":
                    string_hits = string_hits[:1]
            else:
                string_hits = authored_string_hits(chord, role, verse_harmony_stage, blueprint["progression_family"])
                if support["strings"] == "response":
                    string_hits = [hit for hit in string_hits if hit[0] >= 2.0] or string_hits[-1:]
                elif support["strings"] == "shadow":
                    string_hits = string_hits[:1]
                if support_timing == "late_bloom":
                    string_hits = [hit for hit in string_hits if hit[0] >= 1.5] or string_hits[-1:]
                elif support_timing == "response_window":
                    string_hits = [hit for hit in string_hits if hit[0] >= 2.0] or string_hits[-1:]
            for beat_pos, beat_len, pitches in string_hits:
                vel = clamp(string_level - 6, 0, 104) if harmony_authority == "piano_leads" else clamp(string_level + 4, 0, 110)
                add_events(tracks["strings"], start_tick + tick(beat_pos), pitches, tick(min(beat_len, 2.4)), velocity=vel)
        elif kind == "outro" and piano_level > 0:
            if outro_stage == "full":
                add_events(tracks["piano"], start_tick + tick(2.0), build_piano_hits_from_harmonic_state(harmonic_state, chord)[0][2], tick(1.2), velocity=clamp(piano_level - 12, 0, 96))
            elif outro_stage == "tail":
                add_events(tracks["piano"], start_tick + tick(2.5), build_strings_from_harmonic_state(chord, harmonic_state)[:2], tick(1.6), velocity=clamp(piano_level - 18, 0, 88))
            elif outro_stage == "final":
                add_events(tracks["piano"], start_tick + tick(0.0), [harmonic_target_pool(harmonic_state, octave_shift=12)["primary"][0]], tick(3.2), velocity=clamp(piano_level - 24, 0, 82))
        if kind == "outro" and role in ("lift", "transition") and piano_level > 0:
            add_events(tracks["piano"], start_tick + tick(3.0), build_piano_hits_from_harmonic_state(harmonic_state, chord)[0][2], tick(0.65), velocity=piano_level - 8)
        if blueprint["progression_family"] == "lifted" and support["supersaw"] != "silent":
            teaser_shape = build_supersaw_voicing_from_harmonic_state(chord, harmonic_state, max_pitch=84)
            teaser_velocity = 0
            teaser_start = None
            teaser_len = 0.7
            if kind == "intro" and role in ("lift", "transition"):
                teaser_start = 3.0 if role == "lift" else 2.75
                teaser_velocity = clamp(int((saw_level + string_level) * 0.34), 38, 74)
            elif kind == "verse" and local_bar in (2, 3):
                teaser_start = 3.0 if local_bar == 2 else 2.5
                teaser_velocity = clamp(int((saw_level + pad_level) * 0.3), 36, 70)
            elif kind == "outro" and role == "transition":
                teaser_start = 2.5
                teaser_velocity = clamp(int((saw_level + string_level) * 0.28), 34, 66)
            if teaser_start is not None and teaser_velocity > 0:
                add_events(tracks["supersaw_chords"], start_tick + tick(teaser_start), teaser_shape, tick(teaser_len), velocity=teaser_velocity)
        return

    if kind == "breakdown":
        recall_phrase = theme_phrase_events(identity, blueprint, chord, role, register_shift=-12, rhythm_scale=1.1 if blueprint["hook_recall_style"] == "emotive_fragment" else 1.0)
        breakdown_emotion = blueprint["breakdown_emotion"]
        if breakdown_function == "vocal_exposure":
            support["pad"] = "silent" if role in ("establish", "repeat") else "shadow"
            support["strings"] = "silent"
            support["supersaw"] = "silent"
            support["piano"] = "response"
            pad_level = clamp(pad_level - 30, 0, 88)
            string_level = clamp(string_level - 28, 0, 90)
            piano_level = clamp(piano_level - 14, 0, 96)
        elif breakdown_function == "memory_reset":
            support["pad"] = "shadow"
            support["strings"] = "shadow"
            piano_level = clamp(piano_level + 10, 0, 112)
            string_level = clamp(string_level - 10, 0, 96)
            pad_level = clamp(pad_level - 18, 0, 88)
        elif breakdown_function == "harmonic_lift":
            support["pad"] = "shadow"
            support["strings"] = "support"
            support["piano"] = "support"
            piano_level = clamp(piano_level + 18, 0, 116)
            string_level = clamp(string_level + 24, 0, 112)
            pad_level = clamp(pad_level - 18, 0, 90)
        elif breakdown_function == "tension_hold":
            support["piano"] = "shadow"
            support["strings"] = "silent"
            pad_level = clamp(pad_level + 24, 0, 106)
            piano_level = clamp(piano_level - 30, 0, 88)
            string_level = clamp(string_level - 22, 0, 90)
        if breakdown_stage == "reset":
            support["supersaw"] = "silent"
            support["strings"] = "silent"
            support["arp"] = "silent"
            support["pad"] = "shadow" if breakdown_style != "vocal_focus" else "silent"
            support["piano"] = "support" if breakdown_style == "piano_led" else "shadow"
            pad_level = clamp(pad_level - 20, 0, 86)
            string_level = clamp(string_level - 28, 0, 84)
            piano_level = clamp(piano_level + (10 if breakdown_style == "piano_led" else -8), 0, 112)
            if blueprint["progression_family"] == "lifted" and breakdown_function == "harmonic_lift":
                support["pad"] = "support"
                support["strings"] = "shadow"
                pad_level = clamp(max(pad_level, 56), 0, 98)
                string_level = clamp(max(string_level, 44), 0, 90)
                piano_level = clamp(max(piano_level, 62), 0, 114)
        elif breakdown_stage == "hold":
            support["supersaw"] = "silent"
            support["strings"] = "shadow" if support["strings"] != "silent" else "silent"
            pad_level = clamp(pad_level - 8, 0, 94)
        elif breakdown_stage == "ramp":
            support["strings"] = "response" if support["strings"] != "silent" else "silent"
            support["pad"] = "support" if support["pad"] != "silent" else "shadow"
            piano_level = clamp(piano_level + 12, 0, 116)
            string_level = clamp(string_level + 14, 0, 110)
            pad_level = clamp(pad_level + 10, 0, 102)
        elif breakdown_stage == "launch":
            support["strings"] = "response" if support["strings"] != "silent" else "silent"
            support["pad"] = "support" if support["pad"] != "silent" else "shadow"
            piano_level = clamp(piano_level + 16, 0, 116)
            string_level = clamp(string_level + 18, 0, 112)
            pad_level = clamp(pad_level + 12, 0, 104)
        pad_level = clamp(int(pad_level * macro["breakdown_open"]), 0, 110)
        piano_level = clamp(int(piano_level * (0.92 if macro["breakdown_open"] > 1.05 and breakdown_function == "tension_hold" else max(0.8, macro["breakdown_open"]))), 0, 116)
        string_level = clamp(int(string_level * max(0.8, macro["breakdown_open"])), 0, 112)
        if weight_profile == "breakdown_heavy":
            pad_level = clamp(pad_level + 8, 0, 100)
            piano_level = clamp(piano_level + 6, 0, 112)
            string_level = clamp(string_level + 6, 0, 104)
        elif weight_profile == "late_bloom":
            pad_level = clamp(pad_level - 8, 0, 92)
            string_level = clamp(string_level - 6, 0, 94)
        if breakdown_focus == "vocal_space":
            support["pad"] = "shadow"
            support["strings"] = "shadow"
        elif breakdown_focus == "arp_glow":
            support["strings"] = "response"
        elif breakdown_focus == "piano_memory":
            support["piano"] = "support"
        elif breakdown_focus == "pad_horizon":
            support["pad"] = "support"

        if breakdown_stage == "hold":
            if support["pad"] == "silent":
                support["pad"] = "shadow"
            if support["piano"] == "silent":
                support["piano"] = "shadow"
            pad_level = clamp(max(pad_level, 50), 0, 102)
            piano_level = clamp(max(piano_level, 48), 0, 112)
            if support["strings"] == "silent":
                support["strings"] = "shadow"
            string_level = clamp(max(string_level, 42), 0, 104)
        elif breakdown_stage == "ramp":
            support["pad"] = "support" if support["pad"] != "silent" else "shadow"
            support["piano"] = "support" if support["piano"] != "silent" else "shadow"
            if support["strings"] == "silent":
                support["strings"] = "response"
            pad_level = clamp(max(pad_level, 58), 0, 106)
            piano_level = clamp(max(piano_level, 56), 0, 114)
            string_level = clamp(max(string_level, 50), 0, 108)
        elif breakdown_stage == "launch":
            support["pad"] = "support"
            support["piano"] = "support" if breakdown_style == "piano_led" or harmony_authority == "piano_leads" else "response"
            support["strings"] = "response" if support["strings"] != "silent" else "shadow"
            pad_level = clamp(max(pad_level, 62), 0, 108)
            piano_level = clamp(max(piano_level, 60), 0, 116)
            string_level = clamp(max(string_level, 56), 0, 110)

        # Keep a harmonic bed alive in exposed sections even when the intended vocal
        # is not actually present in the DAW yet.
        if support["pad"] == "silent" and support["piano"] in ("shadow", "response") and support["strings"] == "silent":
            support["pad"] = "shadow"
        harmonic_floor_missing = (
            pad_level < 40
            and piano_level < 42
            and string_level < 40
        )
        if harmonic_floor_missing or (
            support["pad"] == "silent"
            and support["piano"] != "support"
            and support["strings"] in ("silent", "shadow")
        ):
            if harmony_authority == "piano_leads":
                support["piano"] = "support"
                piano_level = clamp(max(piano_level + 14, 54), 0, 114)
                support["pad"] = "shadow" if support["pad"] == "silent" else support["pad"]
                pad_level = clamp(max(pad_level, 46), 0, 98)
                if support["strings"] == "silent":
                    support["strings"] = "shadow"
                string_level = clamp(max(string_level, 38), 0, 98)
            else:
                support["pad"] = "support"
                pad_level = clamp(max(pad_level + 16, 58), 0, 104)
                if support["strings"] == "silent":
                    support["strings"] = "shadow"
                string_level = clamp(max(string_level + 8, 42), 0, 100)
                if support["piano"] == "silent":
                    support["piano"] = "shadow"
                piano_level = clamp(max(piano_level, 38), 0, 108)
        if breakdown_style == "pad_space":
            pad_length = BAR_TICKS if role not in ("lift", "transition") else tick(3.2)
            if breakdown_narrative == "space_then_lift" and role in ("establish", "repeat"):
                pad_length = tick(2.2)
            if breakdown_emotion == "suspended_space":
                pad_length = tick(2.8 if role in ("establish", "repeat") else 3.6)
            if breakdown_function == "tension_hold":
                pad_length = tick(3.8 if role in ("establish", "repeat") else 4.0)
            elif breakdown_function == "vocal_exposure":
                pad_length = tick(1.8 if role in ("establish", "repeat") else 2.6)
            elif breakdown_function == "harmonic_lift":
                pad_length = tick(2.0 if role in ("establish", "repeat") else 2.8)
            if breakdown_focus == "pad_horizon":
                pad_length = tick(3.6 if role in ("establish", "repeat") else 4.0)
            if support_timing == "late_bloom":
                pad_length = tick(2.2 if role in ("establish", "repeat") else 3.0)
            if weight_profile == "breakdown_heavy":
                pad_length = max(pad_length, tick(3.6 if role in ("establish", "repeat") else 4.0))
            elif weight_profile == "late_bloom":
                pad_length = min(pad_length, tick(2.2 if role in ("establish", "repeat") else 3.0))
            if support["pad"] != "silent" and pad_level > 0:
                pad_start = 0.0
                if support_timing == "late_bloom":
                    pad_start = 1.0 if role in ("establish", "repeat") else 0.5
                elif support_timing == "response_window":
                    pad_start = 2.0
                if breakdown_function == "vocal_exposure":
                    pad_start = max(pad_start, 1.5 if role in ("establish", "repeat") else 2.0)
                elif breakdown_function == "tension_hold":
                    pad_start = 0.0
                elif breakdown_function == "harmonic_lift":
                    pad_start = max(0.75, pad_start)
                if weight_profile == "breakdown_heavy":
                    pad_start = min(pad_start, 0.0)
                elif weight_profile == "late_bloom":
                    pad_start = max(pad_start, 1.25 if role in ("establish", "repeat") else 1.75)
                if breakdown_stage == "reset":
                    pad_start = max(pad_start, 1.5)
                    pad_length = min(pad_length, tick(2.4))
                elif breakdown_stage == "hold":
                    pad_start = max(pad_start, 0.75)
                elif breakdown_stage == "ramp":
                    pad_start = min(pad_start, 0.5)
                    pad_length = max(pad_length, tick(3.4))
                elif breakdown_stage == "launch":
                    pad_start = min(pad_start, 0.5)
                    pad_length = max(pad_length, tick(3.8))
                add_events(tracks["pad"], start_tick + tick(pad_start), prog_voicing["pad_shell"], pad_length, velocity=pad_level)
            elif breakdown_stage in ("hold", "ramp", "launch"):
                fallback_pad = prog_voicing["pad_shell"][:2] if breakdown_stage == "hold" else prog_voicing["pad_shell"]
                fallback_start = 1.0 if breakdown_stage == "hold" else 0.5
                fallback_len = tick(2.8 if breakdown_stage == "hold" else 3.4 if breakdown_stage == "ramp" else 3.8)
                add_events(tracks["pad"], start_tick + tick(fallback_start), fallback_pad, fallback_len, velocity=clamp(max(pad_level, 54), 42, 104))
            if role in ("repeat", "lift", "transition") and support["strings"] != "silent" and string_level > 0:
                string_start = 2.0
                if harmony_emphasis == "string_lift":
                    string_start = 1.5
                elif support_timing == "response_window":
                    string_start = 2.5
                if breakdown_function == "harmonic_lift":
                    string_start = max(0.5, string_start - 1.0)
                elif breakdown_function == "vocal_exposure":
                    string_start = max(string_start, 2.75)
                elif breakdown_function == "tension_hold":
                    string_start = max(string_start, 3.0)
                if breakdown_stage == "reset":
                    string_start = max(string_start, 3.0)
                elif breakdown_stage == "ramp":
                    string_start = min(string_start, 1.0)
                elif breakdown_stage == "launch":
                    string_start = min(string_start, 1.5)
                string_shape = [chord["root"], chord["third"], chord["fifth"] + 12]
                if harmony_authority == "strings_lead":
                    string_shape = [chord["root"], chord["third"], chord["fifth"] + 12, chord["root"] + 24]
                string_len = 2.4 if harmony_authority == "strings_lead" else 2
                if breakdown_stage == "ramp":
                    string_len = max(string_len, 2.6)
                elif breakdown_stage == "launch":
                    string_len = max(string_len, 3.0)
                add_events(tracks["strings"], start_tick + tick(string_start), string_shape, tick(string_len), velocity=string_level)
            elif breakdown_stage in ("ramp", "launch"):
                fallback_string_shape = [chord["root"], chord["third"], chord["fifth"] + 12]
                fallback_string_start = 1.5 if breakdown_stage == "ramp" else 1.0
                fallback_string_len = tick(2.4 if breakdown_stage == "ramp" else 3.0)
                add_events(tracks["strings"], start_tick + tick(fallback_string_start), fallback_string_shape, fallback_string_len, velocity=clamp(max(string_level, 50), 40, 108))
            if piano_level > 0 and harmony_authority != "strings_lead" and blueprint["hook_recall_style"] in ("interval_memory", "emotive_fragment") and role in ("develop", "lift", "transition"):
                recall_slice = recall_phrase[:3] if breakdown_function == "memory_reset" else recall_phrase[:2]
                for beat_pos, beat_len, pitch in recall_slice:
                    add_event(tracks["piano"], start_tick + tick(beat_pos), clamp(pitch, 52, 84), tick(beat_len), velocity=clamp(int(piano_level * recall_amount) - 10, 40, 102))
            elif piano_level > 0 and harmony_authority == "strings_lead" and role in ("develop", "lift", "transition"):
                add_events(tracks["piano"], start_tick + tick(2.75), build_strings_from_harmonic_state(chord, harmonic_state), tick(0.9), velocity=clamp(piano_level - 14, 32, 92))
            elif breakdown_stage in ("hold", "ramp", "launch") and piano_level > 0 and harmony_authority != "strings_lead":
                piano_start = 2.25 if breakdown_stage == "hold" else 1.5 if breakdown_stage == "ramp" else 1.0
                piano_shape = build_strings_from_harmonic_state(chord, harmonic_state)
                piano_len = tick(0.85 if breakdown_stage == "hold" else 1.0 if breakdown_stage == "ramp" else 1.2)
                add_events(tracks["piano"], start_tick + tick(piano_start), piano_shape, piano_len, velocity=clamp(max(piano_level - 4, 50), 42, 112))
        elif breakdown_style == "piano_led":
            piano_hits = hits if role in ("develop", "lift", "transition") else hits[:3]
            if breakdown_focus == "piano_memory":
                piano_hits = hits
            if breakdown_function == "vocal_exposure":
                piano_hits = [hit for hit in piano_hits if hit[0] >= 1.5] or piano_hits[-1:]
            elif breakdown_function == "harmonic_lift":
                piano_hits = hits + [(2.5, 0.7, build_strings_from_harmonic_state(chord, harmonic_state))]
            elif breakdown_function == "tension_hold":
                piano_hits = [hit for hit in piano_hits if hit[0] >= 2.5] or piano_hits[-1:]
            if support["piano"] == "response":
                piano_hits = [hit for hit in piano_hits if hit[0] >= 1.5]
            if harmony_emphasis == "piano_answer":
                piano_hits = [hit for hit in piano_hits if hit[0] >= 1.0] or piano_hits
            elif support_timing == "response_window":
                piano_hits = [hit for hit in piano_hits if hit[0] >= 2.0] or piano_hits[-1:]
            if harmony_authority == "piano_leads":
                piano_hits = [(beat_pos, max(0.9, beat_len), pitches if isinstance(pitches, list) else [pitches]) for beat_pos, beat_len, pitches in piano_hits]
            if breakdown_stage == "ramp":
                piano_hits = piano_hits + [(2.75, 0.9, build_strings_from_harmonic_state(chord, harmonic_state))]
            elif breakdown_stage == "launch":
                piano_hits = piano_hits + [(2.5, 0.85, build_strings_from_harmonic_state(chord, harmonic_state)), (3.25, 0.7, build_supersaw_voicing_from_harmonic_state(chord, harmonic_state, max_pitch=84))]
            piano_velocity = piano_level
            if local_bar == 0 or breakdown_stage == "reset":
                entry_start = 1.5
                if blueprint["progression_family"] == "progressive_flow" or support_timing in ("late_bloom", "response_window"):
                    entry_start = 2.0
                piano_hits = ease_in_harmony_hits(piano_hits, entry_start, sustain_scale=0.8)
                piano_velocity = clamp(piano_velocity - 18, 0, 98)
            if piano_level > 0:
                for beat_pos, beat_len, pitches in piano_hits:
                    add_events(tracks["piano"], start_tick + tick(beat_pos), pitches if isinstance(pitches, list) else [pitches], tick(min(beat_len, 1.2)), velocity=piano_velocity)
            if support["pad"] != "silent" and pad_level > 0:
                pad_start = 0.0 if support_timing == "bed_first" else (1.0 if support_timing == "late_bloom" else 2.0 if support_timing == "response_window" else 0.5)
                if breakdown_function == "vocal_exposure":
                    pad_start = max(pad_start, 1.75)
                if weight_profile == "breakdown_heavy":
                    pad_start = min(pad_start, 0.0)
                elif weight_profile == "late_bloom":
                    pad_start = max(pad_start, 1.5)
                if blueprint["progression_family"] == "lifted" and breakdown_stage == "reset":
                    pad_start = min(pad_start, 0.75)
                    pad_level = clamp(max(pad_level, 58), 0, 104)
                if blueprint["progression_family"] == "progressive_flow" and breakdown_stage == "reset":
                    pad_start = min(pad_start, 0.75)
                    pad_level = clamp(max(pad_level, 54), 0, 102)
                if breakdown_stage == "ramp":
                    pad_start = min(pad_start, 0.75)
                elif breakdown_stage == "launch":
                    pad_start = min(pad_start, 0.5)
                add_events(tracks["pad"], start_tick + tick(pad_start), prog_voicing["pad_shell"][:2], tick(3.5 if role == "transition" else 4.0), velocity=max(1, pad_level - 10))
            elif breakdown_stage in ("hold", "ramp", "launch"):
                fallback_len = tick(2.8 if breakdown_stage == "hold" else 3.4 if breakdown_stage == "ramp" else 3.8)
                fallback_start = 1.0 if breakdown_stage == "hold" else 0.5
                add_events(tracks["pad"], start_tick + tick(fallback_start), prog_voicing["pad_shell"][:2], fallback_len, velocity=clamp(max(pad_level, 50), 40, 96))
            if piano_level > 0 and breakdown_narrative == "piano_confession" and role in ("develop", "lift", "transition"):
                add_events(tracks["piano"], start_tick + tick(2.5), build_strings_from_harmonic_state(chord, harmonic_state)[:2], tick(0.9), velocity=piano_level + 6)
            if piano_level > 0 and role in ("repeat", "develop", "lift", "transition") and harmony_authority != "piano_leads":
                recall_slice = recall_phrase[:4] if breakdown_function in ("memory_reset", "harmonic_lift") else recall_phrase[:3]
                for beat_pos, beat_len, pitch in recall_slice:
                    add_event(tracks["piano"], start_tick + tick(beat_pos), clamp(pitch, 56, 86), tick(beat_len * 0.8), velocity=clamp(int((piano_level + 4) * recall_amount), 46, 112))
            if breakdown_function == "harmonic_lift" and string_level > 0 and role in ("develop", "lift", "transition"):
                add_events(tracks["strings"], start_tick + tick(1.5), build_strings_from_harmonic_state(chord, harmonic_state), tick(1.75), velocity=clamp(string_level + 6, 42, 112))
            if blueprint["progression_family"] == "lifted" and breakdown_stage == "reset" and string_level > 0:
                add_events(
                    tracks["strings"],
                    start_tick + tick(1.75),
                    build_strings_from_harmonic_state(chord, harmonic_state),
                    tick(1.35),
                    velocity=clamp(max(string_level - 4, 46), 34, 96),
                )
            if blueprint["progression_family"] == "progressive_flow" and breakdown_stage == "reset" and string_level > 0:
                add_events(
                    tracks["strings"],
                    start_tick + tick(2.5),
                    build_strings_from_harmonic_state(chord, harmonic_state)[-2:],
                    tick(0.9),
                    velocity=clamp(string_level - 10, 34, 88),
                )
            if harmony_authority == "piano_leads" and support["strings"] != "silent" and string_level > 0:
                string_start = 2.25 if role in ("establish", "repeat") else 1.75
                string_shape = build_strings_from_harmonic_state(chord, harmonic_state)
                add_events(tracks["strings"], start_tick + tick(string_start), string_shape, tick(2.2 if role in ("lift", "transition") else 1.7), velocity=clamp(string_level - 8, 34, 96))
            elif breakdown_stage in ("ramp", "launch") and string_level > 0:
                string_start = 1.5 if breakdown_stage == "ramp" else 1.0
                string_shape = build_strings_from_harmonic_state(chord, harmonic_state)
                string_len = tick(2.4 if breakdown_stage == "ramp" else 3.0)
                add_events(tracks["strings"], start_tick + tick(string_start), string_shape, string_len, velocity=clamp(max(string_level - 2, 48), 40, 104))
            if blueprint["progression_family"] == "lifted" and support["supersaw"] != "silent":
                teaser_shape = build_supersaw_voicing_from_harmonic_state(chord, harmonic_state, max_pitch=84)
                teaser_start = None
                teaser_len = 0.8
                teaser_velocity = 0
                if breakdown_stage == "ramp":
                    teaser_start = 2.75
                    teaser_velocity = clamp(int((piano_level + string_level) * 0.36), 42, 82)
                elif breakdown_stage == "launch":
                    teaser_start = 2.0
                    teaser_len = 1.0
                    teaser_velocity = clamp(int((piano_level + string_level) * 0.42), 46, 90)
                elif breakdown_stage == "reset" and role == "transition":
                    teaser_start = 3.25
                    teaser_velocity = clamp(int((piano_level + pad_level) * 0.28), 36, 70)
                if teaser_start is not None and teaser_velocity > 0:
                    add_events(tracks["supersaw_chords"], start_tick + tick(teaser_start), teaser_shape, tick(teaser_len), velocity=teaser_velocity)
        elif breakdown_style == "arp_texture":
            if role != "transition" and support["pad"] != "silent" and pad_level > 0:
                pad_start = 0.0 if support_timing == "bed_first" else 1.0
                if breakdown_function == "vocal_exposure":
                    pad_start = max(pad_start, 1.5)
                elif breakdown_function == "tension_hold":
                    pad_start = 0.0
                if breakdown_stage == "ramp":
                    pad_start = min(pad_start, 0.75)
                elif breakdown_stage == "launch":
                    pad_start = min(pad_start, 0.5)
                add_events(tracks["pad"], start_tick + tick(pad_start), prog_voicing["pad_shell"][:2], tick(2.6), velocity=max(28, pad_level - 16))
            elif breakdown_stage in ("hold", "ramp", "launch"):
                fallback_len = tick(2.6 if breakdown_stage == "hold" else 3.2 if breakdown_stage == "ramp" else 3.6)
                fallback_start = 1.0 if breakdown_stage == "hold" else 0.5
                add_events(tracks["pad"], start_tick + tick(fallback_start), prog_voicing["pad_shell"][:2], fallback_len, velocity=clamp(max(pad_level, 48), 38, 92))
            if support["strings"] != "silent" and string_level > 0:
                string_start = 2 if role != "lift" else 1.5
                if support_timing == "response_window":
                    string_start = max(string_start, 2.5)
                elif harmony_emphasis == "string_lift":
                    string_start = max(1.0, string_start - 0.5)
                if breakdown_function == "harmonic_lift":
                    string_start = max(0.75, string_start - 0.75)
                elif breakdown_function == "vocal_exposure":
                    string_start = max(string_start, 2.75)
                elif breakdown_function == "tension_hold":
                    string_start = max(string_start, 3.0)
                add_events(tracks["strings"], start_tick + tick(string_start), build_strings_from_harmonic_state(chord, harmonic_state)[-2:], tick(1.5), velocity=string_level)
            elif breakdown_stage in ("ramp", "launch"):
                fallback_start = 1.5 if breakdown_stage == "ramp" else 1.0
                fallback_len = tick(2.0 if breakdown_stage == "ramp" else 2.6)
                add_events(tracks["strings"], start_tick + tick(fallback_start), build_strings_from_harmonic_state(chord, harmonic_state)[-2:], fallback_len, velocity=clamp(max(string_level, 46), 38, 98))
            if breakdown_focus == "arp_glow" and string_level > 0:
                glow_start = 0.5 if support_timing != "late_bloom" else 1.25
                add_events(tracks["strings"], start_tick + tick(glow_start), harmonic_target_pool(harmonic_state, octave_shift=12)["primary"][:2], tick(0.9), velocity=max(34, string_level - 6))
            if support["strings"] != "silent" and string_level > 0 and harmony_authority != "strings_lead" and blueprint["hook_recall_style"] in ("rhythmic_shadow", "direct_echo") and role in ("develop", "lift", "transition"):
                shadow_phrase = theme_phrase_events(identity, blueprint, chord, role, register_shift=12, rhythm_scale=0.7)
                for beat_pos, beat_len, pitch in shadow_phrase[:3]:
                    add_event(tracks["strings"], start_tick + tick(beat_pos), clamp(pitch, 72, 94), tick(beat_len), velocity=clamp(int(string_level * recall_amount), 38, 98))
        else:
            if role in ("establish", "repeat") and support["pad"] != "silent" and pad_level > 0:
                add_events(tracks["pad"], start_tick, [prog_voicing["pad_shell"][0]], tick(2.4), velocity=max(1, pad_level - 18))
            if role in ("develop", "transition") and piano_level > 0:
                add_events(tracks["piano"], start_tick + tick(3 if role == "develop" else 2.5), build_piano_hits_from_harmonic_state(harmonic_state, chord)[0][2], tick(0.75), velocity=piano_level - 6)
            if role in ("lift", "transition") and support["strings"] != "silent" and string_level > 0:
                for beat_pos, beat_len, pitch in recall_phrase[:2]:
                    add_event(tracks["strings"], start_tick + tick(beat_pos), clamp(pitch, 60, 88), tick(beat_len), velocity=clamp(int((string_level + 4) * recall_amount), 36, 96))
        return

    if kind == "build":
        build_hits = hits
        pluck_targets = harmonic_target_pool(harmonic_state, octave_shift=12)
        stab_patterns = {
            "establish": [(0.5, 0.55, pluck_targets["primary"]), (2.5, 0.5, pluck_targets["secondary"] + pluck_targets["primary"][:1])],
            "repeat": [(0.5, 0.5, pluck_targets["primary"]), (2.5, 0.5, pluck_targets["secondary"] + pluck_targets["primary"][:1])],
            "develop": [(0.5, 0.45, pluck_targets["secondary"] or pluck_targets["primary"]), (1.75, 0.35, pluck_targets["primary"][:1]), (3.0, 0.4, pluck_targets["secondary"] + pluck_targets["primary"][:1])],
            "lift": [(0.5, 0.42, pluck_targets["secondary"] or pluck_targets["primary"]), (2.0, 0.36, pluck_targets["primary"][:1]), (3.25, 0.3, pluck_targets["primary"])],
            "transition": [(0.5, 0.35, pluck_targets["secondary"] or pluck_targets["primary"]), (2.5, 0.3, pluck_targets["primary"][:1])],
        }
        build_hits = stab_patterns.get(role, build_hits)
        if macro["build_escalation"] < 0.95:
            build_hits = build_hits[:max(1, len(build_hits) - 1)]
        elif macro["build_escalation"] > 1.08 and role in ("develop", "lift", "transition"):
            build_hits = build_hits + [(3.5, 0.18, pluck_targets["primary"])]
        if transition["pre_drop_void"] and role == "transition":
            build_hits = hits[:max(1, len(hits) // 2)]
        if support["pluck"] == "response":
            build_hits = [hit for hit in build_hits if hit[0] >= 1.5]
        elif support["pluck"] == "shadow":
            build_hits = build_hits[:max(1, len(build_hits) // 2)]
        if pluck_grammar == "drop_gap":
            build_hits = [hit for hit in build_hits if hit[0] < 2.75]
        elif pluck_grammar == "pulse":
            build_hits = [(0.5, 0.42, pluck_targets["primary"]), (1.5, 0.34, pluck_targets["secondary"] + pluck_targets["primary"][:1]), (3.0, 0.28, pluck_targets["primary"])]
        elif pluck_grammar == "lift_chain" and role in ("develop", "lift", "transition"):
            build_hits = build_hits + [(3.25, 0.22, pluck_targets["secondary"] + pluck_targets["primary"][:1])]
        if blueprint["arp_style"] in ("rolling_16th", "uplift_drive"):
            pluck_level = clamp(int(pluck_level * 0.6), 0, 108)
            build_hits = build_hits[:max(1, min(2, len(build_hits)))]
        else:
            pluck_level = clamp(int(pluck_level * 0.85), 0, 110)
        if role in ("lift", "transition"):
            pluck_level = clamp(int(pluck_level * 0.8), 0, 108)
        if weight_profile == "late_bloom" and not is_second_pass:
            build_hits = [hit for hit in build_hits if hit[0] >= 1.5] or build_hits[-1:]
            pluck_level = clamp(pluck_level - 10, 0, 108)
            pad_level = clamp(pad_level - 10, 0, 92)
        elif weight_profile == "front_loaded" and not is_second_pass:
            build_hits = hits + [(3.25, 0.25, pluck_targets["secondary"] + pluck_targets["primary"][:1])]
            pluck_level = clamp(pluck_level + 6, 0, 112)
        elif weight_profile == "breakdown_heavy" and not is_second_pass:
            build_hits = build_hits[:max(1, len(build_hits) - 1)]
            pluck_level = clamp(pluck_level - 6, 0, 108)
        if is_second_pass:
            if final_lift_profile == "subtle_return":
                build_hits = build_hits[:max(1, len(build_hits) - 1)]
                pluck_level = clamp(pluck_level - 8, 0, 108)
            elif final_lift_profile == "anthem_push":
                build_hits = build_hits + [(3.5, 0.18, pluck_targets["primary"])]
                pluck_level = clamp(pluck_level + 8, 0, 114)
            elif final_lift_profile == "wide_release":
                pad_level = clamp(pad_level + 8, 0, 96)
                string_level = clamp(string_level + 10, 0, 108)
            elif final_lift_profile == "hook_reinforcement":
                foreshadow_phrase = theme_phrase_events(identity, blueprint, chord, role, register_shift=0, rhythm_scale=0.55)
                for beat_pos, beat_len, pitch in foreshadow_phrase[:3]:
                    if beat_pos < 3.0:
                        add_event(tracks["pluck"], start_tick + tick(beat_pos), clamp(pitch, 64, 96), tick(min(beat_len, 0.28)), velocity=clamp(pluck_level + 4, 40, 118))
        if pluck_level > 0:
            for beat_pos, beat_len, pitches in build_hits:
                if transition["pre_drop_void"] and beat_pos >= 3.0:
                    continue
                add_events(tracks["pluck"], start_tick + tick(beat_pos), pitches if isinstance(pitches, list) else [pitches], tick(min(beat_len, 0.6)), velocity=pluck_level)
        if not transition["pre_drop_void"] and support["pad"] != "silent" and pad_level > 0:
            pad_start = 0.0 if support_timing == "bed_first" else 0.5 if support_timing == "staggered_frame" else 1.0 if support_timing == "late_bloom" else 2.0
            if macro["build_escalation"] > 1.08:
                pad_start = max(0.0, pad_start - 0.5)
            elif macro["build_escalation"] < 0.95:
                pad_start = min(2.0, pad_start + 0.5)
            add_events(tracks["pad"], start_tick + tick(pad_start), prog_voicing["pad_shell"][:2], tick(4.0 if role in ("establish", "repeat") else 2.6), velocity=max(30, pad_level - 12))
        if support["strings"] != "silent" and string_level > 0 and intensity > 0.75 and role in ("develop", "lift", "transition"):
            string_start = 2.0 if not transition["harmonic_bloom"] else 2.5
            if harmony_emphasis == "string_lift":
                string_start = max(1.5, string_start - 0.5)
            elif support_timing == "response_window":
                string_start = max(string_start, 2.75)
            add_events(tracks["strings"], start_tick + tick(string_start), [chord["third"], chord["fifth"], chord["root"] + 12], tick(1.75), velocity=min(118, string_level + 6))
        if pluck_level > 0 and role in ("lift", "transition"):
            foreshadow_phrase = theme_phrase_events(identity, blueprint, chord, role, register_shift=0, rhythm_scale=0.65)
            if pluck_grammar == "foreshadow":
                foreshadow_phrase = foreshadow_phrase[:2]
            elif pluck_grammar == "pulse":
                foreshadow_phrase = foreshadow_phrase[:3] + [(3.5, 0.18, pluck_targets["primary"][0])]
            elif pluck_grammar == "lift_chain":
                foreshadow_phrase = foreshadow_phrase[:3] + [(2.75, 0.2, (pluck_targets["secondary"] or pluck_targets["primary"])[0]), (3.25, 0.18, pluck_targets["primary"][-1])]
            for beat_pos, beat_len, pitch in foreshadow_phrase[:5]:
                if transition["pre_drop_void"] and beat_pos >= 2.75:
                    continue
                add_event(tracks["pluck"], start_tick + tick(beat_pos), clamp(pitch, 64, 96), tick(min(beat_len, 0.24)), velocity=clamp(int((pluck_level + 4) * recall_amount), 44, 108))
        if blueprint["progression_family"] == "lifted" and support["supersaw"] != "silent" and role in ("lift", "transition"):
            teaser_shape = build_supersaw_voicing_from_harmonic_state(chord, harmonic_state, max_pitch=84)
            teaser_start = 3.0 if role == "lift" else 2.75
            teaser_len = 0.85 if role == "lift" else 1.0
            teaser_velocity = clamp(int((pad_level + string_level + pluck_level) * 0.32), 42, 84)
            add_events(tracks["supersaw_chords"], start_tick + tick(teaser_start), teaser_shape, tick(teaser_len), velocity=teaser_velocity)
        return

    if kind == "drop":
        spread = prog_voicing["spread"][:]
        if style == "wide_trance" and blueprint["voicing_profile"] != "low_fifth_power":
            spread = [root_low, chord["fifth"] - 12, chord["third"] + 12, chord["fifth"] + 12]
        bloom_extension = [chord["root"] + 24] if transition["harmonic_bloom"] or is_second_pass else []
        spread = spread + bloom_extension
        if supersaw_energy < 0.4:
            spread = spread[:max(3, min(4, len(spread)))]
        elif supersaw_energy >= 0.75 and chord["root"] + 24 not in spread:
            spread = spread + [chord["root"] + 24]
        elif supersaw_energy >= 0.95:
            spread = spread + [chord["root"] + 24, chord["fifth"] + 24]
        harmony_entry = blueprint["drop_harmony_entry"]
        supersaw_identity = blueprint["supersaw_identity"]
        pulse_variant = blueprint["supersaw_pulse_variant"]
        bloom_variant = blueprint["supersaw_bloom_variant"]
        inversion_variant = blueprint["supersaw_inversion_variant"]
        response_variant = blueprint["supersaw_response_variant"]
        if weight_profile == "late_bloom" and not is_second_pass:
            saw_level = clamp(saw_level - 10, 0, 120)
            pad_level = clamp(pad_level - 12, 0, 92)
            string_level = clamp(string_level - 10, 0, 94)
        elif weight_profile == "front_loaded" and not is_second_pass:
            saw_level = clamp(saw_level + 6, 0, 124)
            pad_level = clamp(pad_level + 6, 0, 96)
        elif weight_profile == "breakdown_heavy" and not is_second_pass:
            saw_level = clamp(saw_level - 8, 0, 120)
            string_level = clamp(string_level - 8, 0, 94)
        if is_second_pass and weight_profile == "late_bloom":
            saw_level = clamp(saw_level + 8, 0, 124)
            pad_level = clamp(pad_level + 10, 0, 98)
            string_level = clamp(string_level + 12, 0, 106)
        elif is_second_pass and weight_profile == "breakdown_heavy":
            saw_level = clamp(saw_level + 4, 0, 124)
            string_level = clamp(string_level + 10, 0, 106)
        saw_level = clamp(int(saw_level * macro["drop_force"]), 0, 124)
        pad_level = clamp(int(pad_level * macro["support_bias"]), 0, 100)
        string_level = clamp(int(string_level * macro["support_bias"]), 0, 110)
        if second_drop_stage == "entry":
            saw_level = clamp(saw_level - 14, 0, 118)
            pad_level = clamp(pad_level - 14, 0, 90)
            string_level = clamp(string_level - 26, 0, 92)
        elif second_drop_stage == "settle":
            saw_level = clamp(saw_level - 8, 0, 120)
            pad_level = clamp(pad_level - 6, 0, 94)
            string_level = clamp(string_level - 12, 0, 98)

        if second_drop_stage == "entry":
            pass
        elif support["pad"] != "silent" and pad_level > 0 and local_bar < 2 and (arrival == "glide_in" or harmony_entry == "sustain_first"):
            add_events(tracks["pad"], start_tick, [root_low, chord["third"] - 12], tick(2.0), velocity=max(28, pad_level - 18))
        elif support["pad"] != "silent" and pad_level > 0 and local_bar < 2 and (arrival == "staggered" or harmony_entry == "delayed_bloom"):
            add_events(tracks["pad"], start_tick + tick(1.0), prog_voicing["pad_shell"][:2], tick(1.6), velocity=max(30, pad_level - 16))
        saw_start = 0.0
        saw_len = 4.0
        progression_family = blueprint["progression_family"]
        cadence_profile = blueprint["cadence_profile"]
        if local_bar < 2 and (arrival == "hook_first" or harmony_entry == "delayed_bloom"):
            saw_start = 0.5
            saw_len = 3.5
        elif local_bar < 2 and (arrival == "staggered" or harmony_entry == "emotional_stack"):
            saw_start = 0.25
            saw_len = 3.75
        elif local_bar < 2 and harmony_entry == "full_stack":
            saw_start = 0.0
            saw_len = 4.0
        if second_drop_stage == "entry":
            saw_start = max(saw_start, 1.25)
            saw_len = min(saw_len, 2.5)
        elif second_drop_stage == "settle":
            saw_start = max(saw_start, 0.5)
            saw_len = min(3.25, saw_len)
        if supersaw_energy <= 0.35:
            saw_len = min(saw_len, 2.2)
            saw_start = max(saw_start, 1.0)
        elif supersaw_energy >= 0.9:
            saw_len = min(4.0, saw_len + 0.35)
            saw_start = max(0.0, saw_start - 0.25)
        if not is_second_pass:
            if drop_pair_profile == "drop1_tease_drop2_release":
                saw_level = clamp(saw_level - 12, 0, 120)
                pad_level = clamp(pad_level - 10, 0, 92)
                string_level = clamp(string_level - 8, 0, 94)
            elif drop_pair_profile == "drop1_tight_drop2_emotional":
                string_level = clamp(string_level - 10, 0, 94)
                saw_len = min(saw_len, 3.4)
        else:
            if drop_pair_profile == "drop1_statement_drop2_upgrade":
                saw_level = clamp(saw_level + 8, 0, 124)
                string_level = clamp(string_level + 8, 0, 104)
            elif drop_pair_profile == "drop1_tease_drop2_release":
                saw_level = clamp(saw_level + 14, 0, 124)
                pad_level = clamp(pad_level + 10, 0, 98)
                string_level = clamp(string_level + 12, 0, 106)
            elif drop_pair_profile == "drop1_full_drop2_wider":
                saw_level = clamp(saw_level + 6, 0, 124)
                spread = spread + [chord["root"] + 24]
            elif drop_pair_profile == "drop1_tight_drop2_emotional":
                pad_level = clamp(pad_level + 12, 0, 98)
                string_level = clamp(string_level + 14, 0, 108)
        if drop_role == "statement":
            saw_start = min(saw_start, 0.25)
            saw_len = min(3.5, saw_len)
            spread = spread[:max(3, len(spread))]
        elif drop_role == "tease":
            saw_start = max(saw_start, 1.25 if local_bar < 2 else 0.75)
            saw_len = max(1.0, min(2.4, 4.0 - saw_start))
            saw_level = clamp(saw_level - 12, 0, 118)
            pad_level = clamp(pad_level - 14, 0, 90)
            string_level = clamp(string_level - 14, 0, 96)
        elif drop_role == "tight":
            saw_start = max(saw_start, 0.5)
            saw_len = min(2.8, saw_len)
            spread = spread[:max(3, len(spread) - 1)]
            string_level = clamp(string_level - 10, 0, 98)
        elif drop_role == "upgrade":
            spread = spread + [chord["root"] + 24]
            saw_level = clamp(saw_level + 8, 0, 124)
            string_level = clamp(string_level + 8, 0, 108)
        elif drop_role == "release":
            saw_start = max(0.0, saw_start - 0.25)
            saw_len = min(4.0, saw_len + 0.5)
            spread = spread + [chord["root"] + 24, chord["fifth"] + 24]
            saw_level = clamp(saw_level + 12, 0, 124)
            pad_level = clamp(pad_level + 10, 0, 100)
            string_level = clamp(string_level + 12, 0, 110)
        elif drop_role == "wider":
            saw_start = min(saw_start, 0.0)
            saw_len = min(4.0, saw_len + 0.35)
            spread = spread + [chord["root"] + 24, chord["third"] + 24]
            string_level = clamp(string_level + 10, 0, 110)
        elif drop_role == "emotional":
            saw_start = max(0.5, saw_start)
            saw_len = min(4.0, saw_len + 0.2)
            spread = spread + [chord["third"] + 24, chord["root"] + 24]
            pad_level = clamp(pad_level + 14, 0, 100)
            string_level = clamp(string_level + 16, 0, 110)
        if blueprint.get("variant_drop_tail_bias") == "shorter":
            saw_len = max(1.5, saw_len - 0.25)
        elif blueprint.get("variant_drop_tail_bias") == "longer":
            saw_len = min(4.0, saw_len + 0.2)
        if is_second_pass:
            if drop_role in ("release", "upgrade", "wider"):
                saw_level = clamp(saw_level - 4, 0, 122)
                string_level = clamp(string_level - 4, 0, 106)
            elif drop_role == "emotional":
                string_level = clamp(string_level - 2, 0, 106)
                pad_level = clamp(pad_level - 2, 0, 98)
        if progression_family == "lifted":
            saw_start = max(saw_start, 0.25 if support["primary"] == "lead" else 0.0)
            if role in ("lift", "transition"):
                saw_len = min(4.0, saw_len + 0.25)
        elif progression_family == "classic_warmth":
            saw_start = max(saw_start, 0.5 if support["primary"] == "vocal" else 0.25)
            saw_len = min(saw_len, 3.5)
        elif progression_family == "festival_cycle":
            saw_start = 0.0
            saw_len = max(saw_len, 3.75)
        elif progression_family == "hopeful_pull":
            saw_start = max(saw_start, 1.0 if support["primary"] in ("lead", "vocal") else 0.75)
            saw_len = min(saw_len, 3.0)
        if role == "transition":
            saw_len = 3.25
        if is_second_pass and final_lift_profile == "subtle_return":
            saw_len = min(saw_len, 3.0)
        elif is_second_pass and final_lift_profile == "wide_release":
            saw_len = min(4.0, saw_len + 0.35)
        elif is_second_pass and final_lift_profile == "hook_reinforcement":
            saw_start = max(0.0, saw_start - 0.25)
        if macro_profile == "vocal_journey" and support["primary"] == "vocal":
            saw_start = max(saw_start, 1.0 if not is_second_pass else 0.5)
        elif macro_profile == "drop_pressure":
            saw_start = min(saw_start, 0.0)
            saw_len = max(saw_len, 3.75)
        if support["supersaw"] == "shadow":
            saw_start = max(saw_start, 1.0 if local_bar < 2 else 0.5)
            saw_len = max(1.5, saw_len - 1.0)
        elif support["supersaw"] == "response":
            saw_start = max(saw_start, 2.0 if role != "transition" else 2.5)
            saw_len = max(0.8, 4.0 - saw_start)
        if is_second_pass and supersaw_energy >= 0.95:
            saw_level = clamp(saw_level + 6, 0, 124)
            string_level = clamp(string_level + 6, 0, 110)
        if second_drop_stage == "entry":
            saw_start = max(saw_start, 1.5)
            saw_len = max(1.0, min(saw_len, 2.25))
        if supersaw_motion == "late_bloom":
            saw_start = max(saw_start, 1.0 if role in ("establish", "repeat") else 1.5)
            saw_len = max(1.0, 4.0 - saw_start)
        elif supersaw_motion == "pulse_answer":
            saw_start = max(saw_start, 1.5)
            saw_len = max(1.0, 4.0 - saw_start)
        elif supersaw_motion == "split_pulse" and role in ("develop", "lift", "transition"):
            saw_len = min(saw_len, 2.0)
        if cadence_profile == "delayed_resolve" and role in ("lift", "transition"):
            saw_start = max(saw_start, 2.25)
            saw_len = max(0.75, 4.0 - saw_start)
        elif cadence_profile == "direct_loop" and role in ("establish", "repeat"):
            saw_start = 0.0
            saw_len = max(saw_len, 4.0)
        if supersaw_ceiling == "restrained":
            saw_cap = 112
        elif supersaw_ceiling == "wide":
            saw_cap = 122
        else:
            saw_cap = 118
        if drop_role in ("statement", "tight"):
            saw_cap -= 2
        elif drop_role == "emotional":
            saw_cap -= 1
        if support["supersaw"] in ("shadow", "response"):
            saw_cap -= 2
        saw_cap = clamp(saw_cap, 104, 122)
        saw_level = min(saw_level, saw_cap)
        supersaw_drop_role_name = get_supersaw_drop_role(is_second_pass)
        if supersaw_drop_role_name == "expanded":
            saw_level = clamp(saw_level + 8, 0, 124)
            saw_start = 0.0
            saw_len = max(saw_len, get_supersaw_length(supersaw_drop_role_name))
            bloom_enabled = True
        else:
            saw_level = clamp(saw_level - 4, 0, 118)
            saw_len = min(saw_len, get_supersaw_length(supersaw_drop_role_name))
        saw_notes = build_supersaw_drop_voicing(chord, supersaw_drop_role_name)
        supersaw_event_cap = 1
        if supersaw_identity == "pulse_stack":
            supersaw_event_cap = 4 if supersaw_ceiling == "wide" else 3 if supersaw_ceiling == "balanced" else 2
            if drop_role in ("tight", "statement"):
                supersaw_event_cap = max(1, supersaw_event_cap - 1)
        bloom_enabled = True
        if supersaw_ceiling == "restrained":
            bloom_enabled = is_second_pass and drop_role not in ("statement", "tight")
        elif drop_role in ("tight", "statement") and not is_second_pass:
            bloom_enabled = False
        if supersaw_identity == "pulse_stack":
            pulse_positions = [(0.0, 1.0), (1.25, 0.8), (2.5, 0.9)] if role in ("establish", "repeat") else [(0.0, 0.8), (1.5, 0.7), (3.0, 0.8)]
            if pulse_variant == "push":
                pulse_positions = [(0.0, 0.8), (1.0, 0.7), (2.0, 0.7), (3.0, 0.7)]
            elif pulse_variant == "late":
                pulse_positions = [(1.0, 0.85), (2.25, 0.75), (3.25, 0.6)]
            elif pulse_variant == "skip":
                pulse_positions = [(0.0, 0.9), (2.0, 0.8), (3.25, 0.45)]
            if supersaw_motion == "pulse_answer":
                pulse_positions = [(2.0, 0.7), (2.75, 0.6), (3.25, 0.5)]
            elif supersaw_motion == "late_bloom":
                pulse_positions = [(1.5, 0.7), (2.5, 0.7), (3.25, 0.5)]
            elif supersaw_motion == "split_pulse":
                pulse_positions = [(0.0, 0.6), (1.0, 0.45), (2.5, 0.55), (3.25, 0.4)]
            if drop_role == "tease":
                pulse_positions = [item for item in pulse_positions if item[0] >= 1.5] or pulse_positions[-1:]
            elif drop_role == "release":
                pulse_positions = pulse_positions + [(3.5, 0.35)]
            elif drop_role == "emotional":
                pulse_positions = [(beat, min(1.15, beat_len + 0.15)) for beat, beat_len in pulse_positions if beat >= 1.0]
            if support["supersaw"] == "response":
                pulse_positions = [(2.0, 0.8), (3.0, 0.75)]
            elif support["supersaw"] == "shadow":
                pulse_positions = pulse_positions[-1:]
            pulse_cap = supersaw_event_cap
            if len(pulse_positions) > pulse_cap:
                pulse_positions = pulse_positions[: pulse_cap - 1] + pulse_positions[-1:]
            if saw_level > 0:
                if supersaw_drop_role_name == "expanded":
                    for beat_pos in get_supersaw_rhythm(supersaw_drop_role_name):
                        add_events(tracks["supersaw_chords"], start_tick + tick(beat_pos), saw_notes, tick(get_supersaw_length(supersaw_drop_role_name)), velocity=saw_level)
                else:
                    for beat_pos in get_supersaw_rhythm(supersaw_drop_role_name):
                        add_events(tracks["supersaw_chords"], start_tick + tick(beat_pos), saw_notes, tick(get_supersaw_length(supersaw_drop_role_name)), velocity=saw_level)
        elif saw_level > 0:
            for beat_pos in get_supersaw_rhythm(supersaw_drop_role_name):
                add_events(
                    tracks["supersaw_chords"],
                    start_tick + tick(beat_pos),
                    saw_notes,
                    tick(get_supersaw_length(supersaw_drop_role_name)),
                    velocity=saw_level,
                )
        if saw_level > 0 and bloom_enabled and support["supersaw"] != "silent" and (role == "transition" or (is_second_pass and role == "lift")):
            bloom = clamp_supersaw_register(prog_voicing["bloom"], max_pitch=84)
            if supersaw_identity == "octave_shine":
                bloom = clamp_supersaw_register(bloom + [chord["root"] + 36], max_pitch=84)
            elif supersaw_identity == "bloom_stack":
                bloom = clamp_supersaw_register(build_strings_from_harmonic_state(chord, harmonic_state), max_pitch=84)
            bloom_start = 3.0 if role == "transition" else 2.75
            if progression_family == "festival_cycle":
                bloom_start = 2.5
            elif progression_family == "hopeful_pull":
                bloom_start = 3.25
            elif progression_family == "classic_warmth":
                bloom_start = max(bloom_start, 3.0)
            if bloom_variant == "early":
                bloom_start = max(2.25, bloom_start - 0.5)
            elif bloom_variant == "late":
                bloom_start = min(3.5, bloom_start + 0.25)
            elif bloom_variant == "double":
                first_start = max(2.25, bloom_start - 0.5)
                add_events(tracks["supersaw_chords"], start_tick + tick(first_start), bloom[:max(2, len(bloom) - 1)], tick(0.45), velocity=min(118, saw_level + 2))
            if is_second_pass and final_lift_profile == "wide_release":
                bloom_start = max(2.25, bloom_start - 0.25)
                bloom = clamp_supersaw_register(bloom + [chord["root"] + 36], max_pitch=84)
            elif is_second_pass and final_lift_profile == "hook_reinforcement":
                bloom = clamp_supersaw_register([clamp(identity["theme_anchor"], 60, 84)] + build_strings_from_harmonic_state(chord, harmonic_state)[1:], max_pitch=84)
            if supersaw_motion == "late_bloom":
                bloom_start = min(3.5, bloom_start + 0.25)
            elif supersaw_motion == "pulse_answer":
                bloom_start = max(2.5, bloom_start)
                bloom = bloom[:max(2, len(bloom) - 1)]
            elif supersaw_motion == "split_pulse":
                first_start = max(2.0, bloom_start - 0.75)
                add_events(tracks["supersaw_chords"], start_tick + tick(first_start), bloom[:2], tick(0.35), velocity=min(112, saw_level))
                bloom_start = min(3.5, bloom_start + 0.1)
            if response_variant == "tail":
                bloom_start = max(bloom_start, 3.25)
            elif response_variant == "answer":
                bloom = clamp_supersaw_register(bloom + [harmonic_target_pool(harmonic_state, octave_shift=24)["secondary"][0] if harmonic_target_pool(harmonic_state, octave_shift=24)["secondary"] else harmonic_target_pool(harmonic_state, octave_shift=24)["primary"][0]], max_pitch=84)
            elif response_variant == "echo":
                bloom = bloom[:max(2, len(bloom) - 1)]
            if supersaw_ceiling == "restrained":
                bloom = bloom[:2]
            elif supersaw_ceiling == "balanced":
                bloom = bloom[:3]
            bloom_velocity = min(saw_cap, saw_level + (2 if supersaw_ceiling == "restrained" else 4 if supersaw_ceiling == "balanced" else 6))
            add_events(tracks["supersaw_chords"], start_tick + tick(bloom_start), bloom, tick(0.75), velocity=bloom_velocity)
        pad_hits = hits[:2] if role in ("establish", "repeat") else hits[-2:]
        if support["pad"] == "response":
            threshold = 2.5 if progression_family in ("lifted", "hopeful_pull") else 2.0
            pad_hits = [hit for hit in pad_hits if hit[0] >= threshold]
        elif support["pad"] == "shadow":
            pad_hits = pad_hits[-1:]
        if support_timing == "late_bloom":
            pad_hits = [hit for hit in pad_hits if hit[0] >= 1.0] or pad_hits[-1:]
        elif support_timing == "response_window":
            pad_hits = [hit for hit in pad_hits if hit[0] >= 2.0] or pad_hits[-1:]
        elif support_timing == "staggered_frame" and len(pad_hits) > 1:
            pad_hits = pad_hits[1:]
        if pad_level > 0:
            for beat_pos, beat_len, pitches in pad_hits:
                if focus["support_duck"] and beat_pos < 1.0 and role in ("lift", "transition"):
                    continue
                add_events(tracks["pad"], start_tick + tick(beat_pos), build_pad_voicing_from_harmonic_state(chord, harmonic_state)[:2], tick(min(beat_len, 1.4)), velocity=max(28, pad_level - 16))
        if drop_role in ("release", "emotional") and support["pad"] != "silent" and pad_level > 0 and role in ("develop", "lift", "transition"):
            bloom_shell = prog_voicing["pad_shell"][:]
            if drop_role == "emotional":
                bloom_shell = build_strings_from_harmonic_state(chord, harmonic_state)
            add_events(tracks["pad"], start_tick + tick(2.5), bloom_shell[:max(2, len(bloom_shell))], tick(1.1), velocity=max(34, pad_level - 6))
        if support["strings"] != "silent" and string_level > 0 and role in ("repeat", "lift", "transition"):
            string_start = 2.0
            string_length = 1.0
            string_shape = build_strings_from_harmonic_state(chord, harmonic_state)
            if progression_family == "festival_cycle":
                string_start = 1.5
            elif progression_family == "hopeful_pull":
                string_start = 2.5
                string_length = 0.9
            if string_entry == "early":
                string_start = max(1.0, string_start - 0.5)
            elif string_entry == "late":
                string_start = min(3.0, string_start + 0.5)
                string_length = min(string_length, 0.8)
            elif string_entry == "echo":
                string_start = max(1.5, string_start)
                string_shape = build_strings_from_harmonic_state(chord, harmonic_state)[-2:]
                string_length = 0.75
            if support_spread == "narrow":
                string_length = min(string_length, 0.85)
            elif support_spread == "wide":
                string_shape = string_shape + [harmonic_target_pool(harmonic_state, octave_shift=24)["primary"][0]]
            if second_drop_stage == "entry":
                string_start = 3.0
                string_length = min(string_length, 0.7)
                string_shape = build_strings_from_harmonic_state(chord, harmonic_state)[-2:]
            elif second_drop_stage == "settle":
                string_start = max(string_start, 2.5)
                string_length = min(string_length, 0.85)
            if is_second_pass:
                string_start = 1.5 if role in ("lift", "transition") else 2.0
                string_length = 1.8 if role == "repeat" else 2.2
                string_shape = build_strings_from_harmonic_state(chord, harmonic_state) + [harmonic_target_pool(harmonic_state, octave_shift=24)["primary"][0]]
                if drop_role in ("release", "wider", "emotional"):
                    string_start = 1.25 if role in ("lift", "transition") else 1.75
                    string_length = 2.6 if role == "repeat" else 3.0
                    upper_secondary = harmonic_target_pool(harmonic_state, octave_shift=24)["secondary"]
                    string_shape = build_strings_from_harmonic_state(chord, harmonic_state) + [upper_secondary[0] if upper_secondary else harmonic_target_pool(harmonic_state, octave_shift=24)["primary"][0]]
                if support_spread == "narrow":
                    string_shape = string_shape[:3]
                elif support_spread == "wide" and harmonic_target_pool(harmonic_state, octave_shift=24)["primary"][-1] not in string_shape:
                    string_shape = string_shape + [harmonic_target_pool(harmonic_state, octave_shift=24)["primary"][-1]]
                if second_drop_stage == "entry":
                    string_start = max(2.5, string_start)
                    string_length = min(string_length, 1.35)
                    string_shape = build_strings_from_harmonic_state(chord, harmonic_state)
                elif second_drop_stage == "settle":
                    string_start = max(2.0, string_start)
                    string_length = min(string_length, 1.9)
            add_events(tracks["strings"], start_tick + tick(string_start), string_shape, tick(string_length), velocity=string_level + 8)
            if string_entry == "echo" and role in ("lift", "transition") and not focus["support_duck"] and not is_second_pass:
                add_events(tracks["strings"], start_tick + tick(min(3.25, string_start + 1.0)), harmonic_target_pool(harmonic_state, octave_shift=12)["primary"][:2], tick(0.55), velocity=max(34, string_level - 8))
        if support["strings"] != "silent" and string_level > 0 and is_second_pass and role in ("develop", "lift", "transition") and second_drop_stage != "entry":
            recall_phrase = theme_phrase_events(identity, blueprint, chord, role, register_shift=12, rhythm_scale=0.85)
            recall_count = 1 if role == "develop" else 2
            if string_entry == "late":
                recall_count = 1
            elif string_entry == "echo":
                recall_count = 2
            if drop_role in ("release", "wider", "emotional"):
                recall_count = 1
            for beat_pos, beat_len, pitch in recall_phrase[:recall_count]:
                if beat_pos < 2.0:
                    beat_pos = 2.0
                add_event(tracks["strings"], start_tick + tick(beat_pos), clamp(pitch, 74, 98), tick(max(0.65, beat_len)), velocity=clamp(int((string_level + 6) * recall_amount), 42, 102))
        if support["piano"] != "silent" and piano_level > 0 and is_second_pass and role in ("repeat", "develop", "lift", "transition"):
            piano_hits = build_piano_hits_from_harmonic_state(harmonic_state, chord)
            if role == "repeat":
                piano_hits = [(2.0, 1.15, build_strings_from_harmonic_state(chord, harmonic_state))]
            elif role == "develop":
                piano_hits = [(1.5, 1.0, build_pad_voicing_from_harmonic_state(chord, harmonic_state)), (3.0, 0.9, build_strings_from_harmonic_state(chord, harmonic_state))]
            elif role == "lift":
                piano_hits = [(1.5, 1.1, build_strings_from_harmonic_state(chord, harmonic_state)), (3.0, 1.0, harmonic_target_pool(harmonic_state, octave_shift=12)["primary"] + harmonic_target_pool(harmonic_state, octave_shift=12)["secondary"][:1])]
            else:
                piano_hits = [(1.0, 1.0, build_strings_from_harmonic_state(chord, harmonic_state)), (2.75, 1.15, harmonic_target_pool(harmonic_state, octave_shift=12)["primary"] + harmonic_target_pool(harmonic_state, octave_shift=12)["secondary"][:1])]
            if drop_role in ("release", "wider", "emotional"):
                piano_hits = [(1.5, 1.25, build_strings_from_harmonic_state(chord, harmonic_state)), (3.0, 1.2, harmonic_target_pool(harmonic_state, octave_shift=12)["primary"] + harmonic_target_pool(harmonic_state, octave_shift=12)["secondary"][:1])]
            if support["piano"] == "response":
                piano_hits = [hit for hit in piano_hits if hit[0] >= 2.0] or piano_hits[-1:]
            elif support["piano"] == "shadow":
                piano_hits = piano_hits[:1]
            if support_timing == "late_bloom":
                piano_hits = [hit for hit in piano_hits if hit[0] >= 2.0] or piano_hits[-1:]
            elif support_timing == "response_window":
                piano_hits = [hit for hit in piano_hits if hit[0] >= 2.5] or piano_hits[-1:]
            if second_drop_stage == "entry":
                piano_hits = [hit for hit in piano_hits if hit[0] >= 2.75] or [(3.0, 0.85, build_strings_from_harmonic_state(chord, harmonic_state))]
            elif second_drop_stage == "settle":
                piano_hits = [hit for hit in piano_hits if hit[0] >= 2.0] or piano_hits[-1:]
            piano_velocity = clamp(piano_level - (10 if support["piano"] == "shadow" else 4), 34, 104)
            for beat_pos, beat_len, pitches in piano_hits:
                add_events(tracks["piano"], start_tick + tick(beat_pos), pitches, tick(min(1.4, beat_len)), velocity=piano_velocity)


def arp_positions(style: str, intensity: float, role: str):
    if style == "rolling_16th":
        if role == "transition":
            return [(0.5, 0.24), (1.5, 0.22), (2.75, 0.18), (3.5, 0.16)]
        if role == "develop":
            return [(0.5, 0.24), (1.25, 0.18), (2.5, 0.24), (3.25, 0.18)]
        return [(0.5, 0.24), (1.5, 0.22), (2.5, 0.24), (3.5, 0.16)]
    if style == "gated_8th":
        if role == "lift":
            return [(0.5, 0.24), (1.5, 0.22), (2.5, 0.24), (3.25, 0.18)]
        if role == "transition":
            return [(0.5, 0.24), (1.5, 0.2), (2.75, 0.18), (3.5, 0.16)]
        return [(step * 0.5, 0.24) for step in range(8)]
    if style == "triplet":
        if role == "transition":
            return [(0.6667, 0.22), (2.0, 0.2), (3.3333, 0.18)]
        return [(0.6667, 0.24), (2.0, 0.22), (3.3333, 0.18)]
    if style == "uplift_drive":
        if intensity < 0.6:
            if role in ("lift", "transition"):
                return [(0.5, 0.2), (1.25, 0.2), (2.0, 0.2), (2.75, 0.18), (3.5, 0.16)]
            return [(0.5, 0.22), (1.5, 0.22), (2.5, 0.22), (3.5, 0.22)]
        if intensity < 0.9:
            if role == "develop":
                return [(0.5, 0.22), (1.5, 0.2), (2.5, 0.22), (3.25, 0.16)]
            return [(step * 0.5, 0.2) for step in range(8)]
        if role == "transition":
            return [(0.5, 0.24), (1.5, 0.2), (2.5, 0.24), (3.5, 0.16)]
        return [(0.5, 0.24), (1.5, 0.22), (2.5, 0.24), (3.5, 0.18)]
    if role == "lift":
        return [(0.5, 0.24), (2.0, 0.22), (3.25, 0.18)]
    if role == "transition":
        return [(0.5, 0.24), (2.75, 0.16)]
    return [(0.5, 0.28), (2.5, 0.28)]


def build_arp_from_pattern(chord, pattern, register_low=60, register_high=78, harmonic_state=None):
    if harmonic_state is not None:
        chord_tones = harmonic_target_pool(harmonic_state, octave_shift=0)["primary"]
        chord_tones = [clamp(pitch, register_low, register_high) for pitch in chord_tones]
    else:
        chord_tones = [
            clamp(chord["root"], register_low, register_high),
            clamp(chord["third"], register_low, register_high),
            clamp(chord["fifth"], register_low, register_high),
        ]
    notes = []
    for idx, beat in enumerate(pattern):
        pitch = chord_tones[idx % len(chord_tones)]
        notes.append((beat, 0.25, pitch))
    return notes


def locked_arp_pattern_for_block(blueprint, section_name: str, local_bar: int):
    store = blueprint.setdefault("_locked_arp_patterns", {})
    block_key = f"{section_name}:{local_bar // 4}"
    if block_key not in store:
        seed_value = sum(ord(ch) for ch in section_name) + (local_bar // 4)
        pattern_index = seed_value % len(ARP_PATTERNS)
        store[block_key] = {
            "name": ARP_PATTERN_NAMES[pattern_index],
            "pattern": ARP_PATTERNS[pattern_index],
            "locked_bars": 4,
        }
    return store[block_key]


def add_arp(tracks, start_tick: int, chord, kind: str, local_bar: int, section_bars: int, intensity: float, blueprint, identity, is_second_pass: bool):
    if kind not in ("build", "drop", "breakdown"):
        return
    role = phrase_role(local_bar, section_bars)
    finish_factor = finishability_factor(blueprint)
    arp_variant = bounded_variant(blueprint, "variant_arp_gain")
    density_variant = bounded_variant(blueprint, "variant_drop_density")
    tail_bias = blueprint.get("variant_drop_tail_bias", "balanced")
    support_spread = blueprint.get("variant_support_spread", "balanced")
    arp_restraint = blueprint.get("variant_arp_restraint", "balanced")
    supersaw_ceiling = blueprint.get("variant_supersaw_ceiling", "balanced")
    macro = macro_contrast_profile(kind, role, blueprint, is_second_pass)
    focus = focus_hierarchy(kind, role, blueprint, is_second_pass)
    transition = transition_profile(kind, role, blueprint, is_second_pass)
    support = arrangement_support_profile(kind, role, local_bar, blueprint, is_second_pass)
    second_drop_stage = second_drop_cleanup_stage(kind, local_bar, is_second_pass)
    arp_grammar = blueprint["archetype_arp_grammar"]
    breakdown_function = blueprint.get("breakdown_function", "harmonic_lift")
    drop_role = drop_section_role(blueprint, is_second_pass)
    lead_stage = lead_phrase_stage(local_bar, section_bars, is_second_pass)
    section_name = section_display_name(kind, is_second_pass)
    harmonic_state = build_harmonic_state(
        start_tick // BAR_TICKS,
        blueprint.get("progression_name", identity.get("progression_name", "uplifting")),
        chord,
        blueprint.get("progression_family", ""),
    )
    if kind in ("build", "drop"):
        pattern_info = locked_arp_pattern_for_block(blueprint, section_name, local_bar)
        pattern = list(pattern_info["pattern"])
        emotion_pattern = HARMONIC_ARP_PATTERNS.get(harmonic_state["emotion"], pattern)
        if kind == "drop" or pattern_info["name"] == "quarter_lock":
            pattern = [beat for beat in emotion_pattern if beat in pattern or pattern_info["name"] == "quarter_lock"]
            if not pattern:
                pattern = list(emotion_pattern)
        register_low = 58 if kind == "build" else 60
        register_high = 76 if kind == "build" else 74
        if kind == "drop" and lead_stage in ("phrase_b", "payoff"):
            pattern = pattern[:2]
        if kind == "drop" and role in ("lift", "transition"):
            pattern = pattern[-2:]
        if kind == "drop" and local_bar % 2 == 1:
            pattern = []
        if support["arp"] == "shadow":
            pattern = pattern[:max(1, len(pattern) // 2)]
        elif support["arp"] == "response":
            pattern = [beat for beat in pattern if beat >= 1.5]
        if kind == "drop":
            pattern = pattern[:4]
        else:
            pattern = pattern[:6]
        if not pattern:
            return
        velocity = clamp(int((42 + intensity * 30) * focus["harmony"] * support_state_factor(support["arp"])), 24, 96)
        for beat_pos, beat_len, pitch in build_arp_from_pattern(
            chord,
            pattern,
            register_low=register_low,
            register_high=register_high,
            harmonic_state=harmonic_state,
        ):
            add_event(tracks["arp"], start_tick + tick(beat_pos), pitch, tick(beat_len), velocity=velocity)
        return
    if kind == "breakdown" and blueprint["breakdown_style"] == "vocal_focus":
        return
    if transition["pre_drop_void"] and kind == "build" and role == "transition":
        return
    if support["arp"] == "silent":
        return
    if kind == "breakdown" and blueprint["breakdown_style"] == "pad_space" and blueprint["arp_style"] != "minimal":
        positions = [(1.5, 0.18), (3.0, 0.18)] if role != "transition" else [(2.5, 0.18)]
    else:
        positions = arp_positions(blueprint["arp_style"], intensity, role)
    if kind == "breakdown":
        if breakdown_function == "vocal_exposure":
            positions = [item for item in positions if item[0] >= 2.0] or positions[-1:]
        elif breakdown_function == "memory_reset":
            positions = positions[:max(1, len(positions) // 3)]
        elif breakdown_function == "harmonic_lift":
            positions = positions + [(2.75, 0.18), (3.25, 0.16)]
        elif breakdown_function == "tension_hold":
            positions = [item for item in positions if item[0] >= 2.5] or positions[-1:]
    if arp_grammar == "breath":
        positions = positions[:max(1, len(positions) // 2)]
    elif arp_grammar == "answer":
        positions = [item for item in positions if item[0] >= 2.0] or positions[-2:]
    elif arp_grammar == "lift_rush":
        if role in ("lift", "transition"):
            positions = positions + [(3.0, 0.14), (3.25, 0.14), (3.5, 0.12)]
        elif role == "develop":
            positions = positions + [(2.75, 0.14), (3.25, 0.12)]
    if focus["vocal_space"] and kind == "breakdown":
        positions = positions[:max(1, len(positions) // 2)]
    elif focus["support_duck"] and kind == "drop" and role in ("lift", "transition"):
        positions = [item for item in positions if item[0] >= 1.5]
    if support["arp"] == "shadow":
        positions = positions[:max(1, len(positions) // 2)]
    elif support["arp"] == "response":
        positions = [item for item in positions if item[0] >= 2.0]
    if kind == "build":
        if macro["build_escalation"] < 0.95:
            positions = positions[:max(1, len(positions) // 2)]
        elif macro["build_escalation"] > 1.08 and role in ("develop", "lift", "transition"):
            positions = positions + [(3.0, 0.14), (3.25, 0.14)]
    elif kind == "drop":
        if macro["drop_force"] < 0.95 and not is_second_pass:
            positions = [item for item in positions if item[0] >= 1.0] or positions[-2:]
        elif macro["drop_force"] > 1.08 and is_second_pass:
            positions = positions + [(2.75, 0.14), (3.5, 0.12)]
        if drop_role == "tease":
            positions = [item for item in positions if item[0] >= 1.5] or positions[-2:]
        elif drop_role == "statement":
            positions = positions[:max(2, len(positions) - 1)]
        elif drop_role == "upgrade":
            positions = positions + [(3.0, 0.16), (3.5, 0.14)]
        elif drop_role == "release":
            positions = [(max(0.0, beat - 0.25), beat_len) for beat, beat_len in positions] + [(3.5, 0.16)]
        elif drop_role == "emotional":
            positions = [(beat, min(0.28, beat_len + 0.06)) for beat, beat_len in positions if beat >= 1.0] or positions[-2:]
        elif drop_role == "wider":
            positions = positions + [(2.5, 0.16), (3.25, 0.16)]
        if density_variant < 1.0 and len(positions) > 8:
            positions = positions[:8]
        elif density_variant > 1.0 and tail_bias == "longer":
            positions = positions + [(3.75, 0.12)]
        if support_spread == "narrow" and len(positions) > 8:
            positions = positions[:8]
        elif support_spread == "wide" and len(positions) > 10:
            positions = positions[:8] + positions[-2:]
        max_positions = 10
        if drop_role in ("release", "upgrade", "wider") and support_spread == "wide" and arp_variant > 1.0:
            max_positions = 12
        if len(positions) > max_positions:
            positions = positions[: max_positions - 2] + positions[-2:]
        if supersaw_ceiling == "wide" and arp_restraint != "free":
            positions = positions[:max(6, min(8, len(positions)))]
        elif arp_restraint == "guarded":
            positions = positions[:max(5, min(7, len(positions)))]
        if drop_role == "emotional" and arp_restraint != "free":
            positions = [item for item in positions if item[0] >= 1.0] or positions[-2:]
        if drop_role == "release":
            positions = [item for item in positions if item[0] >= 1.5] or positions[-3:]
            if arp_restraint != "free":
                positions = positions[:max(4, min(6, len(positions)))]
            if support["arp"] in ("response", "shadow") or support_spread == "wide":
                positions = positions[:max(4, min(5, len(positions)))]
        if second_drop_stage == "entry":
            positions = [item for item in positions if item[0] >= 2.5] or positions[-2:]
        elif second_drop_stage == "settle":
            positions = [item for item in positions if item[0] >= 1.5] or positions[-3:]
    if kind in ("build", "drop") and local_bar % 2 == 1:
        positions = positions + [(1.0, 0.18), (3.0, 0.16)]
    if kind == "drop":
        supportive_patterns = {
            "phrase_a": [(0.5, 0.42), (1.5, 0.38), (2.5, 0.42), (3.5, 0.24)],
            "phrase_a_repeat": [(0.5, 0.4), (1.25, 0.26), (2.5, 0.42), (3.25, 0.22)],
            "phrase_b": [(0.5, 0.38), (1.5, 0.34), (2.75, 0.3), (3.5, 0.2)],
            "payoff": [(0.5, 0.46), (1.5, 0.4), (3.0, 0.28)],
        }
        positions = supportive_patterns.get(lead_stage, positions)
        if local_bar % 4 in (1, 3):
            positions = []
        lead_density_limit = max(2, int(round(len(positions) * 0.6)))
        positions = positions[:lead_density_limit]
        counter_active_hint = is_second_pass and role in ("develop", "lift", "transition")
        if counter_active_hint:
            positions = [item for item in positions if abs(item[0] - round(item[0])) > 1e-6]
        if support["arp"] == "shadow":
            positions = positions[:max(1, len(positions) // 2)]
    positions = sorted({(round(beat, 4), length) for beat, length in positions})
    positions = [(beat, length) for beat, length in positions]
    motif = [
        [chord["root"] + 24, chord["third"] + 24],
        [chord["third"] + 24, chord["fifth"] + 24],
        [chord["fifth"] + 24, chord["root"] + 36],
        [chord["third"] + 24, chord["root"] + 36],
    ]
    if role == "develop":
        motif = [
            [chord["third"] + 24, chord["fifth"] + 24],
            [chord["fifth"] + 24, chord["root"] + 36],
            [chord["root"] + 24, chord["third"] + 24],
            [chord["fifth"] + 24, chord["third"] + 36],
        ]
    elif role == "transition":
        motif = [
            [chord["fifth"] + 24, chord["root"] + 36],
            [chord["third"] + 24, chord["fifth"] + 24],
            [chord["root"] + 24, chord["third"] + 24],
            [chord["fifth"] + 24, chord["third"] + 36],
        ]
    if blueprint["progression_family"] == "lifted":
        motif = [
            [chord["root"] + 12, chord["third"] + 24],
            [chord["third"] + 12, chord["fifth"] + 24],
            [chord["fifth"] + 12, chord["root"] + 24],
            [chord["third"] + 12, chord["root"] + 24],
        ]
        if role == "develop":
            motif = [
                [chord["third"] + 12, chord["fifth"] + 24],
                [chord["fifth"] + 12, chord["root"] + 24],
                [chord["root"] + 12, chord["third"] + 24],
                [chord["third"] + 12, chord["fifth"] + 24],
            ]
        elif role == "transition":
            motif = [
                [chord["fifth"] + 12, chord["root"] + 24],
                [chord["third"] + 12, chord["fifth"] + 24],
                [chord["root"] + 12, chord["third"] + 24],
                [chord["third"] + 12, chord["root"] + 24],
            ]
    arp_density = 1.0
    arp_register = 0
    if kind == "build":
        arp_density *= 0.6
        arp_register -= 6
    if kind != "drop" and blueprint["arp_style"] == "rolling_16th":
        positions = [(0.25, 0.32), (0.75, 0.28), (1.25, 0.32), (1.75, 0.28), (2.25, 0.32), (2.75, 0.28), (3.25, 0.32), (3.75, 0.18)]
    elif kind != "drop" and blueprint["arp_style"] == "uplift_drive":
        positions = [(0.5, 0.42), (1.5, 0.36), (2.5, 0.42), (3.5, 0.24)]
    elif kind != "drop" and blueprint["arp_style"] == "gated_8th":
        positions = [(0.5, 0.45), (1.5, 0.4), (2.5, 0.45), (3.5, 0.24)]
    elif kind != "drop" and blueprint["arp_style"] == "triplet":
        positions = [(0.0, 0.32), (1.3333, 0.28), (2.6667, 0.28), (3.3333, 0.18)]
    if kind != "drop" and blueprint["progression_family"] == "lifted":
        if blueprint["arp_style"] == "triplet":
            groove_positions = {
                "establish": [(0.5, 0.54), (1.5, 0.5), (2.5, 0.54), (3.5, 0.32)],
                "repeat": [(0.5, 0.5), (1.5, 0.46), (2.5, 0.5), (3.25, 0.36)],
                "develop": [(0.5, 0.46), (1.25, 0.38), (2.5, 0.5), (3.25, 0.34)],
                "lift": [(0.5, 0.5), (1.5, 0.46), (2.5, 0.5), (3.25, 0.38), (3.75, 0.26)],
                "transition": [(0.5, 0.46), (1.5, 0.42), (2.75, 0.34), (3.5, 0.24)],
            }
            positions = groove_positions.get(role, positions)
        elif blueprint["arp_style"] == "rolling_16th":
            groove_positions = {
                "establish": [(0.5, 0.44), (1.0, 0.3), (1.5, 0.4), (2.5, 0.44), (3.0, 0.3), (3.5, 0.24)],
                "repeat": [(0.5, 0.4), (1.5, 0.36), (2.5, 0.4), (3.25, 0.28), (3.5, 0.22)],
                "develop": [(0.5, 0.36), (1.25, 0.28), (1.5, 0.34), (2.5, 0.4), (3.25, 0.28)],
                "lift": [(0.5, 0.4), (1.5, 0.36), (2.5, 0.4), (3.25, 0.3), (3.5, 0.22), (3.75, 0.18)],
                "transition": [(0.5, 0.34), (1.5, 0.32), (2.75, 0.26), (3.5, 0.18)],
            }
            positions = groove_positions.get(role, positions)
    if kind in ("build", "drop") and role in ("establish", "repeat", "develop") and arp_grammar != "lift_rush":
        positions = positions[:max(4, min(6, len(positions)))]
    if kind == "drop" and drop_role in ("statement", "tight"):
        positions = positions[:max(4, min(5, len(positions)))]
    elif kind == "drop" and drop_role in ("upgrade", "release", "wider"):
        positions = positions[:max(5, min(7, len(positions)))]
    if kind in ("build", "breakdown") and blueprint["hook_recall_style"] in ("rhythmic_shadow", "interval_memory") and role in ("develop", "lift", "transition"):
        recall_pool = theme_fragment_for_role(identity, blueprint, chord, role, register_shift=12)
        if recall_pool:
            motif = [[clamp(recall_pool[0], 72, 96), chord["fifth"] + 24]] + motif
    if kind == "drop" and is_second_pass and role in ("lift", "transition"):
        recall_pool = theme_fragment_for_role(identity, blueprint, chord, role, register_shift=12)
        if recall_pool:
            motif = [[clamp(recall_pool[0], 72, 98), chord["root"] + 36]] + motif
    if kind == "drop":
        if drop_role == "tease":
            motif = motif[-2:] + motif[:1]
        elif drop_role == "upgrade":
            motif = motif + [[chord["third"] + 36, chord["fifth"] + 36]]
        elif drop_role == "release":
            motif = motif + [[chord["root"] + 36, chord["fifth"] + 36]]
        elif drop_role == "emotional":
            motif = [
                [chord["third"] + 24, chord["fifth"] + 24],
                [chord["fifth"] + 24, chord["root"] + 36],
                [chord["third"] + 24, chord["root"] + 36],
                [chord["fifth"] + 24, chord["third"] + 36],
            ]
        elif drop_role == "wider":
            motif = motif + [[chord["root"] + 36, chord["third"] + 36]]
    if arp_grammar == "answer":
        motif = motif[-2:] + motif[:-2]
    elif arp_grammar == "lift_rush":
        motif = motif + [[chord["root"] + 36, chord["third"] + 36]]
    if blueprint["progression_family"] == "lifted" and arp_grammar == "lift_rush":
        motif = motif[:-1] + [[chord["fifth"] + 24, chord["root"] + 24]]
    velocity = clamp(int((46 + intensity * 38) * focus["harmony"] * support_state_factor(support["arp"]) * macro["arp_bias"] * (macro["build_escalation"] if kind == "build" else macro["support_bias"])), 0, 108) + (4 if role in ("lift", "transition") else 0)
    if arp_grammar == "breath":
        velocity = clamp(velocity - 10, 0, 102)
    elif arp_grammar == "lift_rush":
        velocity = clamp(velocity + 8, 0, 110)
    if kind == "drop":
        velocity = clamp(int(velocity * finish_factor * min(1.04, arp_variant)), 0, 106)
        if supersaw_ceiling == "wide":
            velocity = clamp(velocity - 10, 0, 100)
        elif arp_restraint == "guarded":
            velocity = clamp(velocity - 12, 0, 98)
        if drop_role == "release":
            velocity = clamp(velocity - (10 if arp_restraint != "free" else 6), 0, 96)
        if drop_role == "tease":
            velocity = clamp(velocity - 12, 0, 96)
        elif drop_role == "statement":
            velocity = clamp(velocity - 4, 0, 102)
        elif drop_role == "upgrade":
            velocity = clamp(velocity + 8, 0, 112)
        elif drop_role == "release":
            velocity = clamp(velocity + 10, 0, 112)
        elif drop_role == "emotional":
            velocity = clamp(velocity + 6, 0, 110)
        if second_drop_stage == "entry":
            velocity = clamp(velocity - 18, 0, 92)
        elif second_drop_stage == "settle":
            velocity = clamp(velocity - 8, 0, 98)
    if kind == "build":
        velocity = clamp(int(velocity * 0.8), 0, 96)
    if velocity <= 0:
        return
    length_scale = 1.0
    max_length = 0.56
    if blueprint["progression_family"] == "lifted":
        length_scale = 1.45
        max_length = 0.78
        velocity = clamp(velocity - 6, 0, 104)
    if blueprint["arp_style"] == "triplet":
        length_scale *= 1.12 if blueprint["progression_family"] != "lifted" else 1.18
        max_length = max(max_length, 0.82 if blueprint["progression_family"] == "lifted" else 0.64)
    elif blueprint["arp_style"] == "rolling_16th":
        length_scale *= 1.18 if blueprint["progression_family"] != "lifted" else 1.24
        max_length = max(max_length, 0.68 if blueprint["progression_family"] == "lifted" else 0.52)
    elif blueprint["arp_style"] in ("uplift_drive", "gated_8th"):
        length_scale *= 1.08
        max_length = max(max_length, 0.72 if blueprint["progression_family"] == "lifted" else 0.6)
    if arp_grammar in ("breath", "answer"):
        length_scale *= 1.08
    if kind == "drop" and drop_role in ("release", "emotional"):
        length_scale *= 1.06
        max_length = max(max_length, 0.84 if blueprint["progression_family"] == "lifted" else 0.66)
    if support["arp"] == "shadow":
        length_scale *= 0.94
    elif support["arp"] == "response":
        length_scale *= 1.04
    if kind == "build":
        positions = [(beat, min(length, 0.34)) for beat, length in positions]
    elif kind == "drop":
        positions = [(beat, min(length, 0.3)) for beat, length in positions]
    if kind in ("build", "drop"):
        groove_positions = [(beat, length) for beat, length in positions if is_offbeat_position(beat)]
        positions = groove_positions or [(0.5, 0.32), (1.5, 0.3), (2.5, 0.32), (3.5, 0.18)]
        max_events = 6 if kind == "build" else 4
        if arp_density < 1.0:
            max_events = max(2, int(round(max_events * arp_density)))
        positions = positions[:max_events]
    arp_floor = 60
    arp_ceiling = 72 if kind == "build" else 78
    bar_index = start_tick // BAR_TICKS
    arp_notes = []
    for idx, (beat_pos, beat_len) in enumerate(positions):
        note_group = motif[idx % len(motif)]
        source_pitch = min(note_group)
        if role in ("lift", "transition") and len(note_group) > 1:
            source_pitch = min(note_group[1], max(note_group)) - 12
        if kind == "build":
            source_pitch += arp_register
        elif kind == "drop":
            source_pitch -= 9
        arp_pitch = clamp(source_pitch, arp_floor, arp_ceiling)
        note_len = min(max_length, max(0.24, beat_len * length_scale))
        arp_velocity = clamp(velocity + (8 if idx % 2 == 0 else -6), 0, 112)
        arp_notes.append({
            "start": start_tick + tick(beat_pos),
            "end": start_tick + tick(beat_pos + note_len),
            "pitch": arp_pitch,
            "velocity": arp_velocity,
            "channel": 0,
        })
    if kind in ("build", "drop"):
        arp_notes = enforce_offbeat_groove(arp_notes)
        arp_notes = enforce_arp_pattern(arp_notes, bar_index, max_events=6 if kind == "build" else 4)
    for note_data in arp_notes:
        add_event(tracks["arp"], note_data["start"], note_data["pitch"], note_data["end"] - note_data["start"], velocity=note_data["velocity"])


def add_bass(tracks, start_tick: int, chord, kind: str, local_bar: int, section_bars: int, intensity: float, blueprint, is_second_pass: bool):
    style = blueprint["bass_style"]
    source_style = style
    role = phrase_role(local_bar, section_bars)
    drop_role = drop_section_role(blueprint, is_second_pass)
    finish_factor = finishability_factor(blueprint)
    bass_variant = bounded_variant(blueprint, "variant_bass_gain")
    density_variant = bounded_variant(blueprint, "variant_drop_density")
    tail_bias = blueprint.get("variant_drop_tail_bias", "balanced")
    macro = macro_contrast_profile(kind, role, blueprint, is_second_pass)
    focus = focus_hierarchy(kind, role, blueprint, is_second_pass)
    transition = transition_profile(kind, role, blueprint, is_second_pass)
    support = arrangement_support_profile(kind, role, local_bar, blueprint, is_second_pass)
    weight_profile = blueprint.get("section_weight_profile", "balanced")
    second_drop_stage = second_drop_cleanup_stage(kind, local_bar, is_second_pass)
    build_stage = build_story_stage(kind, local_bar, section_bars, is_second_pass)
    breakdown_stage = breakdown_story_stage(local_bar, section_bars) if kind == "breakdown" else None
    root_note = chord["root"] - 24
    fifth_note = chord["fifth"] - 24
    motion = blueprint["bass_motion_profile"]
    bass_grammar = blueprint["archetype_bass_grammar"]
    groove_profile = blueprint.get("groove_variation_profile", "steady")
    opening_scene = blueprint.get("opening_scene", "pad_seed")
    bass_entry_open = early_verse_allows(kind, local_bar, "bass")
    outro_stage = outro_release_stage(local_bar, section_bars) if kind == "outro" else "full"
    upper_note = root_note + 12
    if motion == "fifth_drive":
        upper_note = fifth_note
    elif motion == "syncopated_lift":
        upper_note = fifth_note + 12
    if style == "hybrid":
        if kind in ("intro", "verse", "breakdown", "outro"):
            style = "classic_offbeat"
        else:
            style = "rolling_drive"
    if kind == "breakdown" and blueprint["breakdown_style"] in ("pad_space", "vocal_focus"):
        style = "classic_offbeat"
    if weight_profile == "late_bloom" and not is_second_pass and kind in ("verse", "build", "drop") and style == "rolling_drive":
        style = "classic_offbeat"
    elif weight_profile == "front_loaded" and not is_second_pass and kind in ("build", "drop") and style == "classic_offbeat":
        style = "rolling_drive"
    if kind == "drop" and macro["drop_force"] < 0.95 and not is_second_pass and style == "rolling_drive":
        style = "classic_offbeat"
    elif kind == "drop" and macro["drop_force"] > 1.08 and is_second_pass and style == "classic_offbeat":
        style = "rolling_drive"
    if second_drop_stage == "entry" and style == "rolling_drive":
        style = "classic_offbeat"

    motion_section = kind in ("build", "drop") and style in ("rolling_drive", "syncopated")
    pulse_support_only = source_style in ("hybrid", "rolling_drive") and kind in ("build", "drop")

    if source_style == "rolling_drive" and style == "classic_offbeat" and kind in ("build", "drop"):
        return
    if source_style == "classic_offbeat" and style in ("rolling_drive", "syncopated") and kind in ("verse", "breakdown", "outro"):
        return

    if style == "classic_offbeat":
        if kind not in ("verse", "build", "drop", "outro", "breakdown"):
            return
        if kind == "verse" and not bass_entry_open:
            return
        if kind == "outro" and outro_stage == "final":
            return
        velocity = clamp(int((72 + intensity * 24) * focus["groove"] * support_state_factor(support["bass"]) * macro["bass_bias"]), 0, 118)
        if velocity <= 0:
            return
        beat_positions = [0.5, 1.5, 2.5, 3.5]
        if role == "lift":
            beat_positions = [0.5, 1.5, 2.5, 3.25, 3.75]
        elif role == "transition":
            beat_positions = [0.5, 1.5, 2.75, 3.5]
        if kind == "verse":
            if local_bar == 1:
                beat_positions = [2.5, 3.5]
                velocity = clamp(velocity - 12, 0, 106)
            elif local_bar == 2:
                beat_positions = [1.5, 2.5, 3.5]
                velocity = clamp(velocity - 6, 0, 110)
            if opening_scene == "bass_tease":
                if local_bar == 1:
                    beat_positions = [2.5, 3.25, 3.5]
                    velocity = clamp(velocity + 4, 0, 112)
                elif local_bar == 2:
                    beat_positions = [1.5, 2.5, 3.25, 3.5]
            elif opening_scene == "hook_tease" and local_bar < 3:
                beat_positions = [beat for beat in beat_positions if beat >= 2.5] or beat_positions[-1:]
        if focus["vocal_space"] and kind == "breakdown":
            beat_positions = [0.5, 2.5]
        if breakdown_stage == "reset":
            beat_positions = [2.5]
            velocity = clamp(velocity - 20, 0, 96)
        elif breakdown_stage == "hold":
            beat_positions = [0.5, 2.5]
            velocity = clamp(velocity - 10, 0, 102)
        elif breakdown_stage == "lift":
            beat_positions = [0.5, 1.5, 2.5, 3.5]
        if focus["support_duck"] and kind == "drop" and role in ("lift", "transition"):
            beat_positions = [beat for beat in beat_positions if beat not in (1.5, 2.5)]
        if transition["pre_drop_void"] and kind == "build" and role == "transition":
            beat_positions = [beat for beat in beat_positions if beat < 3.0]
        if support["bass"] == "shadow":
            beat_positions = beat_positions[:max(1, len(beat_positions) // 2)]
        elif support["bass"] == "response":
            beat_positions = [beat for beat in beat_positions if beat >= 2.0]
        if bass_grammar == "breath":
            beat_positions = [beat for beat in beat_positions if beat not in (1.5, 3.5)]
        elif bass_grammar == "push":
            beat_positions = sorted(set(beat_positions + [3.25]))
        if pulse_support_only:
            beat_positions = [beat for beat in beat_positions if beat in (0.5, 2.5)] or [0.5, 2.5]
            velocity = clamp(velocity - 10, 0, 108)
        if groove_profile == "syncopated" and kind in ("build", "drop"):
            if role in ("repeat", "develop"):
                beat_positions = sorted(set(beat_positions + ([1.25, 3.25] if local_bar % 2 == 0 else [0.75, 2.75])))
            elif role in ("lift", "transition"):
                beat_positions = sorted(set(beat_positions + [3.25]))
        elif groove_profile == "breathing" and kind in ("build", "drop") and local_bar % 2 == 0:
            beat_positions = [beat for beat in beat_positions if beat in (0.5, 2.5, 3.5)] or beat_positions[-2:]
            velocity = clamp(velocity - 8, 0, 112)
        elif groove_profile == "push_pull" and kind in ("build", "drop") and local_bar % 2 == 1:
            beat_positions = sorted(set(beat_positions + [3.25, 3.75]))
            velocity = clamp(velocity + 4, 0, 116)
        if weight_profile == "late_bloom" and not is_second_pass and kind in ("build", "drop"):
            beat_positions = [beat for beat in beat_positions if beat >= 2.0] or beat_positions[-1:]
            velocity = clamp(velocity - 10, 0, 112)
        elif weight_profile == "front_loaded" and not is_second_pass and kind in ("build", "drop"):
            beat_positions = sorted(set(beat_positions + [3.25]))
            velocity = clamp(velocity + 6, 0, 116)
        elif weight_profile == "breakdown_heavy" and not is_second_pass and kind == "drop":
            velocity = clamp(velocity - 8, 0, 112)
        if kind == "drop":
            if drop_role == "statement":
                beat_positions = [beat for beat in beat_positions if beat in (0.5, 1.5, 2.5, 3.5)] or beat_positions
            elif drop_role == "tease":
                beat_positions = [beat for beat in beat_positions if beat >= 2.5] or beat_positions[-2:]
                velocity = clamp(velocity - 12, 0, 106)
            elif drop_role == "tight":
                beat_positions = [beat for beat in beat_positions if beat not in (1.5, 2.5)] or beat_positions[:2]
                velocity = clamp(velocity - 6, 0, 110)
            elif drop_role == "upgrade":
                beat_positions = sorted(set(beat_positions + [0.25, 3.25, 3.75]))
                velocity = clamp(velocity + 6, 0, 118)
            elif drop_role == "release":
                beat_positions = sorted(set(beat_positions + [0.25, 1.25, 2.25, 3.25, 3.75]))
                velocity = clamp(velocity + 10, 0, 118)
            elif drop_role == "wider":
                beat_positions = sorted(set(beat_positions + [1.25, 3.25]))
                velocity = clamp(velocity + 6, 0, 116)
            elif drop_role == "emotional":
                beat_positions = [beat for beat in beat_positions if beat >= 1.5] or beat_positions[-2:]
                velocity = clamp(velocity + 2, 0, 114)
            if pulse_support_only:
                beat_positions = [beat for beat in beat_positions if beat in (0.5, 2.5)] or [0.5, 2.5]
                velocity = clamp(velocity - 8, 0, 104)
        if second_drop_stage == "entry":
            beat_positions = [beat for beat in beat_positions if beat in (0.5, 2.5)] or [0.5, 2.5]
            velocity = clamp(velocity - 8, 0, 106)
        elif second_drop_stage == "settle":
            beat_positions = [beat for beat in beat_positions if beat in (0.5, 1.5, 2.5, 3.5)] or beat_positions
            velocity = clamp(velocity - 4, 0, 110)
        if kind == "drop":
            velocity = clamp(int(velocity * finish_factor * bass_variant), 0, 114)
            if is_second_pass and drop_role in ("release", "upgrade", "wider"):
                beat_positions = beat_positions[:max(4, len(beat_positions) - 1)]
            if density_variant < 1.0 and beat_positions:
                beat_positions = beat_positions[:max(2, len(beat_positions) - 1)]
            elif density_variant > 1.0 and tail_bias == "longer":
                beat_positions = sorted(set(beat_positions + [3.25]))
        elif kind == "outro":
            if outro_stage == "thin":
                beat_positions = [0.5, 2.5]
            elif outro_stage == "tail":
                beat_positions = [0.5]
                velocity = clamp(velocity - 16, 0, 100)
        accent_index = len(beat_positions) - 1
        for idx, beat_pos in enumerate(beat_positions):
            note_to_play = upper_note if motion == "syncopated_lift" and idx == accent_index and role in ("lift", "transition") and not pulse_support_only else root_note
            length = 0.42 if idx < accent_index else 0.28
            if idx == accent_index and role in ("lift", "transition") and not pulse_support_only:
                note_to_play = upper_note if motion != "low_anchor" else root_note + 12
                length = 0.5 if transition["harmonic_bloom"] or role == "transition" else 0.34
            add_event(tracks["offbeat_bass"], start_tick + tick(beat_pos), note_to_play, tick(length), velocity=velocity + (4 if idx == accent_index and role in ("lift", "transition") else 0))
        return

    if style == "rolling_drive":
        if kind == "verse" and local_bar < 4:
            return
        if kind == "outro" and outro_stage in ("tail", "final"):
            return
        velocity = clamp(int((78 + intensity * 26) * focus["groove"] * support_state_factor(support["bass"]) * macro["bass_bias"] * macro["drop_force"]), 0, 122)
        if velocity <= 0:
            return
        pattern_map = {
            "establish": [(0.25, 0.14, root_note), (0.5, 0.12, fifth_note), (0.75, 0.12, root_note), (1.25, 0.14, root_note), (1.5, 0.12, fifth_note), (1.75, 0.12, root_note), (2.25, 0.14, root_note), (2.5, 0.12, fifth_note), (2.75, 0.12, root_note), (3.25, 0.14, root_note), (3.5, 0.12, fifth_note), (3.75, 0.12, root_note)],
            "repeat": [(0.25, 0.14, root_note), (0.5, 0.12, root_note), (0.75, 0.12, fifth_note), (1.25, 0.14, root_note), (1.5, 0.12, root_note), (1.75, 0.12, fifth_note), (2.25, 0.14, root_note), (2.5, 0.12, root_note), (2.75, 0.12, fifth_note), (3.25, 0.14, root_note), (3.5, 0.12, root_note), (3.75, 0.12, upper_note)],
            "develop": [(0.25, 0.14, root_note), (0.5, 0.12, fifth_note), (0.75, 0.12, root_note), (1.25, 0.14, upper_note), (1.5, 0.12, fifth_note), (1.75, 0.12, root_note), (2.25, 0.14, fifth_note), (2.5, 0.12, root_note), (2.75, 0.12, upper_note), (3.25, 0.14, fifth_note), (3.5, 0.12, root_note), (3.75, 0.12, upper_note)],
            "lift": [(0.25, 0.14, root_note), (0.5, 0.12, fifth_note), (0.75, 0.12, root_note), (1.25, 0.14, upper_note), (1.5, 0.12, fifth_note), (1.75, 0.12, root_note), (2.25, 0.14, upper_note), (2.5, 0.12, fifth_note), (2.75, 0.12, root_note), (3.25, 0.14, upper_note), (3.5, 0.12, fifth_note), (3.75, 0.1, upper_note)],
            "transition": [(0.5, 0.12, root_note), (0.75, 0.1, fifth_note), (1.5, 0.12, root_note), (1.75, 0.1, upper_note), (2.5, 0.12, fifth_note), (2.75, 0.1, root_note), (3.25, 0.1, upper_note), (3.75, 0.08, upper_note)],
        }
        pattern = pattern_map[role]
        if motion_section and role == "establish":
            pattern = [(0.25, 0.14, root_note), (0.5, 0.12, fifth_note), (0.75, 0.12, root_note), (1.25, 0.14, root_note), (1.5, 0.12, fifth_note), (1.75, 0.12, root_note), (2.25, 0.14, root_note), (2.5, 0.12, fifth_note), (2.75, 0.12, root_note), (3.25, 0.14, root_note), (3.5, 0.12, fifth_note), (3.75, 0.12, root_note)]
        elif motion_section and role == "repeat":
            pattern = [(0.25, 0.14, root_note), (0.5, 0.12, fifth_note), (0.75, 0.12, root_note), (1.25, 0.14, fifth_note), (1.5, 0.12, root_note), (1.75, 0.12, fifth_note), (2.25, 0.14, root_note), (2.5, 0.12, fifth_note), (2.75, 0.12, root_note), (3.25, 0.14, upper_note), (3.5, 0.12, fifth_note), (3.75, 0.1, root_note)]
        elif motion_section and role == "develop":
            pattern = [(0.25, 0.14, root_note), (0.5, 0.12, fifth_note), (0.75, 0.12, root_note), (1.25, 0.14, fifth_note), (1.5, 0.12, root_note), (1.75, 0.12, upper_note), (2.25, 0.14, root_note), (2.5, 0.12, fifth_note), (2.75, 0.12, root_note), (3.25, 0.14, upper_note), (3.5, 0.12, fifth_note), (3.75, 0.1, upper_note)]
        elif motion_section and role == "lift":
            pattern = [(0.25, 0.14, root_note), (0.5, 0.12, fifth_note), (0.75, 0.12, root_note), (1.25, 0.14, upper_note), (1.5, 0.12, fifth_note), (1.75, 0.12, root_note), (2.25, 0.14, upper_note), (2.5, 0.12, fifth_note), (2.75, 0.12, root_note), (3.25, 0.14, upper_note), (3.5, 0.12, fifth_note), (3.75, 0.08, upper_note)]
        elif motion_section and role == "transition":
            pattern = [(0.25, 0.12, root_note), (0.5, 0.1, fifth_note), (0.75, 0.1, root_note), (1.25, 0.12, fifth_note), (1.5, 0.1, root_note), (1.75, 0.1, upper_note), (2.5, 0.12, fifth_note), (2.75, 0.1, root_note), (3.25, 0.1, upper_note), (3.75, 0.08, upper_note)]
        if bass_grammar == "anchor":
            pattern = [(beat, length, root_note if idx % 3 else pitch) for idx, (beat, length, pitch) in enumerate(pattern)]
        elif bass_grammar == "breath":
            pattern = [entry for idx, entry in enumerate(pattern) if idx % 4 != 2]
        elif bass_grammar == "push":
            pattern = pattern + [(3.5, 0.1, upper_note), (3.75, 0.08, upper_note)]
        if focus["support_duck"] and kind == "drop" and role in ("lift", "transition"):
            pattern = [entry for entry in pattern if entry[0] >= 1.25]
        if support["bass"] == "shadow":
            pattern = [entry for idx, entry in enumerate(pattern) if idx % 2 == 0]
        elif support["bass"] == "response":
            pattern = [entry for entry in pattern if entry[0] >= 2.25]
        if groove_profile == "syncopated" and kind in ("build", "drop"):
            if local_bar % 2 == 0:
                pattern = pattern + [(3.25, 0.1, fifth_note)]
            else:
                pattern = [(beat, length, upper_note if idx in (3, 7) else pitch) for idx, (beat, length, pitch) in enumerate(pattern)]
        elif groove_profile == "breathing" and kind in ("build", "drop") and local_bar % 2 == 0:
            pattern = [entry for idx, entry in enumerate(pattern) if idx % 3 != 1]
            velocity = clamp(velocity - 10, 0, 112)
        elif groove_profile == "push_pull" and kind in ("build", "drop"):
            pattern = pattern + [(3.5, 0.1, upper_note), (3.75, 0.08, upper_note)]
        if weight_profile == "late_bloom" and not is_second_pass:
            pattern = [entry for entry in pattern if entry[0] >= 1.5] or pattern[-2:]
            velocity = clamp(velocity - 10, 0, 118)
        elif weight_profile == "front_loaded" and not is_second_pass:
            velocity = clamp(velocity + 6, 0, 122)
        elif weight_profile == "breakdown_heavy" and not is_second_pass and kind == "drop":
            pattern = [entry for entry in pattern if entry[0] >= 1.0]
        if kind == "drop":
            if drop_role == "statement":
                pattern = pattern[:max(8, len(pattern) - 2)]
            elif drop_role == "tease":
                pattern = [entry for entry in pattern if entry[0] >= 2.25] or pattern[-4:]
                velocity = clamp(velocity - 12, 0, 112)
            elif drop_role == "tight":
                pattern = pattern[:max(8, len(pattern) - 2)]
                pattern = [(beat, min(0.12, length), pitch) for beat, length, pitch in pattern]
            elif drop_role == "upgrade":
                pattern = pattern + [(3.25, 0.12, upper_note), (3.5, 0.1, fifth_note), (3.75, 0.08, upper_note)]
                velocity = clamp(velocity + 6, 0, 122)
            elif drop_role == "release":
                pattern = [(beat, min(0.16, length + 0.02), pitch) for beat, length, pitch in pattern] + [(3.5, 0.1, fifth_note), (3.75, 0.08, upper_note)]
                velocity = clamp(velocity + 10, 0, 122)
            elif drop_role == "wider":
                pattern = pattern + [(3.25, 0.12, fifth_note), (3.5, 0.1, upper_note), (3.75, 0.08, upper_note)]
                velocity = clamp(velocity + 6, 0, 120)
            elif drop_role == "emotional":
                pattern = [(beat, min(0.16, length + 0.02), upper_note if idx in (3, 7, len(pattern) - 1) else pitch) for idx, (beat, length, pitch) in enumerate(pattern) if beat >= 1.25]
                velocity = clamp(velocity + 4, 0, 120)
            if second_drop_stage == "entry":
                pattern = [(beat, min(length, 0.12), root_note if beat < 2.5 else pitch) for beat, length, pitch in pattern if beat >= 1.25]
                velocity = clamp(velocity - 12, 0, 108)
            elif second_drop_stage == "settle":
                pattern = [(beat, min(length, 0.14), pitch) for beat, length, pitch in pattern if beat >= 0.5]
                velocity = clamp(velocity - 6, 0, 114)
            velocity = clamp(int(velocity * finish_factor * bass_variant), 0, 118)
            if is_second_pass and drop_role in ("release", "upgrade", "wider"):
                pattern = pattern[:max(10, len(pattern) - 2)]
            if density_variant < 1.0 and pattern:
                pattern = pattern[:max(8, len(pattern) - 2)]
            elif density_variant > 1.0 and tail_bias == "longer":
                pattern = pattern + [(3.5, 0.1, upper_note), (3.75, 0.08, upper_note)]
        for beat_pos, beat_len, pitch in pattern:
            add_event(tracks["rolling_bass"], start_tick + tick(beat_pos), pitch, tick(beat_len), velocity=velocity - (6 if pitch == upper_note and motion != "fifth_drive" else 0))
        return

    velocity = clamp(int((72 + intensity * 22) * focus["groove"] * support_state_factor(support["bass"]) * macro["bass_bias"]), 0, 118)
    if kind == "verse" and not bass_entry_open:
        return
    if kind == "outro" and outro_stage == "final":
        return
    if velocity <= 0:
        return
    sync_patterns = {
        "establish": [(0.0, 0.35, root_note), (0.75, 0.22, root_note), (1.5, 0.35, fifth_note), (2.5, 0.25, root_note), (3.25, 0.2, upper_note)],
        "repeat": [(0.0, 0.35, root_note), (0.75, 0.22, root_note), (1.5, 0.35, fifth_note), (2.5, 0.25, root_note), (3.25, 0.2, upper_note)],
        "develop": [(0.0, 0.28, root_note), (0.5, 0.2, fifth_note), (1.25, 0.28, root_note), (2.0, 0.22, fifth_note), (2.75, 0.2, root_note), (3.5, 0.18, upper_note)],
        "lift": [(0.0, 0.28, root_note), (0.75, 0.18, root_note), (1.5, 0.28, fifth_note), (2.25, 0.18, upper_note), (2.75, 0.16, root_note), (3.25, 0.14, fifth_note)],
        "transition": [(0.0, 0.25, root_note), (0.75, 0.16, fifth_note), (1.5, 0.22, root_note), (2.5, 0.16, fifth_note), (3.25, 0.12, upper_note), (3.625, 0.08, upper_note)],
    }
    sync_pattern = sync_patterns[role]
    if bass_grammar == "anchor":
        sync_pattern = [(beat, length, root_note if idx % 2 == 0 else pitch) for idx, (beat, length, pitch) in enumerate(sync_pattern)]
    elif bass_grammar == "breath":
        sync_pattern = sync_pattern[:max(2, len(sync_pattern) - 2)]
    elif bass_grammar == "push":
        sync_pattern = sync_pattern + [(3.75, 0.08, upper_note)]
    if focus["support_duck"] and kind == "drop" and role in ("lift", "transition"):
        sync_pattern = [entry for entry in sync_pattern if entry[0] >= 1.0]
    if support["bass"] == "shadow":
        sync_pattern = sync_pattern[:max(1, len(sync_pattern) // 2)]
    elif support["bass"] == "response":
        sync_pattern = [entry for entry in sync_pattern if entry[0] >= 2.0]
    if kind == "build":
        if build_stage == "recover":
            sync_pattern = [entry for entry in sync_pattern if entry[0] >= 2.0] or sync_pattern[-2:]
            velocity = clamp(velocity - 12, 0, 104)
        elif build_stage == "gather":
            sync_pattern = [entry for entry in sync_pattern if entry[0] >= 1.0] or sync_pattern[-3:]
            velocity = clamp(velocity - 4, 0, 110)
        elif build_stage == "launch":
            sync_pattern = sync_pattern + [(3.5, 0.12, upper_note)]
            velocity = clamp(velocity + 6, 0, 118)
    if weight_profile == "late_bloom" and not is_second_pass:
        sync_pattern = [entry for entry in sync_pattern if entry[0] >= 2.0] or sync_pattern[-2:]
        velocity = clamp(velocity - 10, 0, 114)
    elif weight_profile == "front_loaded" and not is_second_pass:
        velocity = clamp(velocity + 6, 0, 118)
    elif weight_profile == "breakdown_heavy" and not is_second_pass and kind == "drop":
        sync_pattern = sync_pattern[:max(2, len(sync_pattern) - 2)]
    if kind == "drop":
        if drop_role == "statement":
            sync_pattern = sync_pattern[:max(4, len(sync_pattern) - 1)]
        elif drop_role == "tease":
            sync_pattern = [entry for entry in sync_pattern if entry[0] >= 2.0] or sync_pattern[-2:]
            velocity = clamp(velocity - 12, 0, 108)
        elif drop_role == "tight":
            sync_pattern = [(beat, min(0.22, length), pitch) for beat, length, pitch in sync_pattern[:max(3, len(sync_pattern) - 1)]]
        elif drop_role == "upgrade":
            sync_pattern = sync_pattern + [(3.25, 0.16, upper_note), (3.625, 0.1, upper_note)]
            velocity = clamp(velocity + 6, 0, 118)
        elif drop_role == "release":
            sync_pattern = [(max(0.0, beat - 0.125), min(0.32, length + 0.04), pitch) for beat, length, pitch in sync_pattern] + [(3.75, 0.1, upper_note)]
            velocity = clamp(velocity + 8, 0, 118)
        elif drop_role == "wider":
            sync_pattern = sync_pattern + [(2.25, 0.18, fifth_note), (3.5, 0.14, upper_note)]
        elif drop_role == "emotional":
            sync_pattern = [(beat, min(0.3, length + 0.04), upper_note if idx == len(sync_pattern) - 1 else pitch) for idx, (beat, length, pitch) in enumerate(sync_pattern) if beat >= 1.0]
            velocity = clamp(velocity + 4, 0, 116)
        if second_drop_stage == "entry":
            sync_pattern = [(beat, min(length, 0.22), root_note if beat < 2.0 else pitch) for beat, length, pitch in sync_pattern if beat >= 1.0]
            velocity = clamp(velocity - 10, 0, 106)
        elif second_drop_stage == "settle":
            sync_pattern = [(beat, min(length, 0.24), pitch) for beat, length, pitch in sync_pattern if beat >= 0.75]
            velocity = clamp(velocity - 5, 0, 110)
        velocity = clamp(int(velocity * finish_factor * bass_variant), 0, 114)
        if is_second_pass and drop_role in ("release", "upgrade", "wider"):
            sync_pattern = sync_pattern[:max(4, len(sync_pattern) - 1)]
        if density_variant < 1.0 and sync_pattern:
            sync_pattern = sync_pattern[:max(3, len(sync_pattern) - 1)]
        elif density_variant > 1.0 and tail_bias == "longer":
            sync_pattern = sync_pattern + [(3.5, 0.12, upper_note)]
    for beat_pos, beat_len, pitch in sync_pattern:
        add_event(tracks["rolling_bass"], start_tick + tick(beat_pos), pitch, tick(beat_len), velocity=velocity)


def add_sub_bass(tracks, start_tick: int, chord, kind: str, local_bar: int, section_bars: int, intensity: float, blueprint, is_second_pass: bool):
    if kind not in ("verse", "build", "drop", "breakdown", "outro"):
        return
    role = phrase_role(local_bar, section_bars)
    support = arrangement_support_profile(kind, role, local_bar, blueprint, is_second_pass)
    focus = focus_hierarchy(kind, role, blueprint, is_second_pass)
    drop_role = drop_section_role(blueprint, is_second_pass)
    outro_stage = outro_release_stage(local_bar, section_bars) if kind == "outro" else "full"
    root_note = chord["root"] - 36
    fifth_note = chord["fifth"] - 36
    velocity = clamp(int((58 + intensity * 20) * focus["groove"] * support_state_factor(support["bass"])), 0, 104)
    if velocity <= 0:
        return
    pattern = []
    if kind == "breakdown":
        pattern = [(0.0, 3.5, root_note)] if support["bass"] != "silent" else []
    elif kind == "verse":
        if not early_verse_allows(kind, local_bar, "bass"):
            return
        pattern = [(0.0, 3.5, root_note)] if local_bar % 2 == 0 else [(0.0, 2.0, root_note), (2.0, 1.5, fifth_note if blueprint["progression_family"] == "festival_cycle" else root_note)]
    elif kind == "build":
        pattern = [(0.0, 2.0, root_note), (2.0, 1.5, root_note)]
        if role in ("lift", "transition"):
            pattern = [(0.0, 1.5, root_note), (2.0, 1.0, root_note), (3.0, 0.75, fifth_note if blueprint["lead_resolution_bias"] == "fifth_to_tonic" else root_note)]
    elif kind == "drop":
        pattern = [(0.0, 1.8, root_note), (2.0, 1.6, root_note)]
        if drop_role in ("release", "upgrade", "wider"):
            pattern = [(0.0, 1.7, root_note), (2.0, 1.1, root_note), (3.25, 0.5, fifth_note if drop_role == "wider" else root_note)]
        elif drop_role == "emotional":
            pattern = [(0.0, 2.2, root_note), (2.5, 1.0, fifth_note)]
        elif drop_role == "tease":
            pattern = [(2.0, 1.2, root_note)]
            velocity = clamp(velocity - 10, 0, 92)
    elif kind == "outro":
        if outro_stage == "full":
            pattern = [(0.0, 3.0, root_note)]
        elif outro_stage == "thin":
            pattern = [(0.0, 2.0, root_note)]
            velocity = clamp(velocity - 10, 0, 92)
        elif outro_stage == "tail":
            pattern = [(0.0, 1.5, root_note)]
            velocity = clamp(velocity - 18, 0, 84)
        else:
            pattern = [(0.0, 5.0, root_note)]
            velocity = clamp(velocity - 26, 0, 76)
    for beat_pos, beat_len, pitch in pattern:
        add_event(tracks["sub_bass"], start_tick + tick(beat_pos), pitch, tick(beat_len), velocity=velocity)


def pre_drop_build_zones(sections, max_bars=8, min_bars=4):
    zones = []
    for idx, section in enumerate(sections):
        if section_kind(section["name"]) != "drop":
            continue
        drop_start = section["start_bar"]
        previous = sections[idx - 1] if idx > 0 else None
        if previous and section_kind(previous["name"]) == "build":
            start_bar = max(previous["start_bar"], drop_start - max_bars)
        else:
            start_bar = max(0, drop_start - max_bars)
        if drop_start - start_bar < min_bars:
            start_bar = max(0, drop_start - min_bars)
        zones.append({"start_bar": start_bar, "end_bar": drop_start, "drop_name": section["name"]})
    return zones


def build_snare_roll(bar_index, total_build_bars):
    progress = bar_index / max(1, total_build_bars)
    if progress < 0.25:
        interval = 2.0
    elif progress < 0.5:
        interval = 1.0
    elif progress < 0.75:
        interval = 0.5
    else:
        interval = 0.25
    hits = []
    beat = 0.0
    while beat < 4.0:
        hits.append(round(beat, 2))
        beat += interval
    return hits


def identity_snare_build_bars(blueprint):
    style = blueprint.get("identity_drum_build_style", "")
    if "4" in style:
        return 4
    if "long" in style or "cinematic" in style or "8" in style:
        return 8
    return 8


def apply_snare_build_engine(tracks, sections, blueprint=None):
    zones = pre_drop_build_zones(sections, max_bars=identity_snare_build_bars(blueprint or {}))
    for zone in zones:
        total_bars = max(1, zone["end_bar"] - zone["start_bar"])
        for bar_index in range(zone["start_bar"], zone["end_bar"]):
            local_index = bar_index - zone["start_bar"]
            progress = local_index / max(1, total_bars - 1)
            bar_start = bar_tick(bar_index)
            roll_positions = build_snare_roll(local_index, total_bars)
            if bar_index == zone["end_bar"] - 1:
                roll_positions = [round(step * 0.25, 2) for step in range(16)]
            velocity = clamp(int(70 + (110 - 70) * progress), 70, 110)
            for idx, beat_pos in enumerate(roll_positions):
                accent = 8 if bar_index == zone["end_bar"] - 1 and idx >= max(0, len(roll_positions) - 6) else 0
                add_event(tracks["clap_snare"], bar_start + tick(beat_pos), 38, tick(0.06), velocity=clamp(velocity + accent, 1, 124))
            if bar_index >= zone["end_bar"] - 2:
                for beat_pos in (1.0, 3.0):
                    add_event(tracks["clap_snare"], bar_start + tick(beat_pos), 39, tick(0.12), velocity=clamp(velocity - 8, 1, 116))
    return bool(zones)


def snare_build_metrics(clap_snare_notes, sections):
    zones = pre_drop_build_zones(sections)
    densities = []
    velocities = []
    final_fill_present = False
    for zone in zones:
        for bar_index in range(zone["start_bar"], zone["end_bar"]):
            snare_bar = [note for note in notes_starting_in_bar(clap_snare_notes, bar_index) if note["pitch"] == 38]
            densities.append(len(snare_bar))
            velocities.extend(note["velocity"] for note in snare_bar)
        final_bar = zone["end_bar"] - 1
        final_notes = sorted([note for note in notes_starting_in_bar(clap_snare_notes, final_bar) if note["pitch"] == 38], key=lambda item: item["start"])
        if len(final_notes) >= 8:
            intervals = [right["start"] - left["start"] for left, right in zip(final_notes, final_notes[1:])]
            if intervals and min(intervals) <= tick(0.25):
                final_fill_present = True
    density_curve = ",".join(str(item) for item in densities)
    velocity_curve = f"{min(velocities, default=0)}-{max(velocities, default=0)}"
    density_increases = bool(densities and max(densities) > min(densities))
    velocity_increases = bool(velocities and max(velocities) > min(velocities))
    return {
        "snare_build_detected": bool(zones and densities and density_increases),
        "snare_density_curve": density_curve,
        "snare_velocity_curve": velocity_curve,
        "snare_final_fill_present": final_fill_present,
        "snare_velocity_increases": velocity_increases,
    }


def add_drums(tracks, start_tick: int, kind: str, local_bar: int, bars_in_section: int, intensity: float, blueprint, is_second_pass: bool):
    style = blueprint["drum_style"]
    progression_family = blueprint["progression_family"]
    drum_grammar = blueprint["archetype_drum_grammar"]
    support_timing = blueprint["archetype_support_timing"]
    drum_micro = blueprint["archetype_drum_micro"]
    weight_profile = blueprint.get("section_weight_profile", "balanced")
    drop_pair_profile = blueprint.get("drop_pair_profile", "drop1_statement_drop2_upgrade")
    final_lift_profile = blueprint.get("final_lift_profile", "anthem_push")
    macro_profile = blueprint.get("macro_journey_profile", "anthem_arc")
    role = phrase_role(local_bar, bars_in_section)
    arrival = blueprint["drop_arrival_style"]
    drop_role = drop_section_role(blueprint, is_second_pass)
    finish_factor = finishability_factor(blueprint)
    kick_variant = bounded_variant(blueprint, "variant_kick_gain")
    hat_variant = bounded_variant(blueprint, "variant_hat_gain")
    clap_variant = bounded_variant(blueprint, "variant_clap_gain")
    density_variant = bounded_variant(blueprint, "variant_drop_density")
    tail_bias = blueprint.get("variant_drop_tail_bias", "balanced")
    clap_pattern = blueprint.get("variant_clap_pattern", "backbeat")
    hat_grid = blueprint.get("variant_hat_grid", "steady_8th")
    kick_phrase = blueprint.get("variant_kick_phrase", "flat")
    verse_entry_variant = blueprint.get("variant_verse_drum_entry", "hat_tease")
    groove_profile = blueprint.get("groove_variation_profile", "steady")
    opening_scene = blueprint.get("opening_scene", "pad_seed")
    macro = macro_contrast_profile(kind, role, blueprint, is_second_pass)
    focus = focus_hierarchy(kind, role, blueprint, is_second_pass)
    transition = transition_profile(kind, role, blueprint, is_second_pass)
    support = arrangement_support_profile(kind, role, local_bar, blueprint, is_second_pass)
    drums_entry_open = early_verse_allows(kind, local_bar, "drums_core")
    outro_stage = outro_release_stage(local_bar, bars_in_section) if kind == "outro" else "full"
    verse_entry_stage = verse_drum_entry_stage(kind, local_bar, verse_entry_variant)
    build_stage = build_story_stage(kind, local_bar, bars_in_section, is_second_pass)
    breakdown_stage = breakdown_story_stage(local_bar, bars_in_section) if kind == "breakdown" else None
    quarter_grid = [0.0, 1.0, 2.0, 3.0]
    half_grid = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
    if kind not in ("verse", "build", "drop", "outro"):
        if kind == "breakdown" and style in ("driving", "festival") and support["drums"] != "silent":
            kick_points = [0.0] if role in ("establish", "repeat") else [0.0, 3.0]
            if drum_grammar == "minimal_frame":
                kick_points = [0.0]
            if support["drums"] == "shadow":
                kick_points = kick_points[:1]
            for beat_pos in kick_points:
                add_event(tracks["kick"], start_tick + tick(beat_pos), 36, tick(0.25), velocity=76)
        return
    if kind == "verse" and not drums_entry_open:
        return

    kick_beats = quarter_grid[:]
    if kind == "verse" and style == "minimal":
        kick_beats = [0.0, 2.0]
    if kind == "verse" and verse_entry_stage in ("kick_only", "hat_tease", "clap_arrives", "settle_in"):
        kick_beats = quarter_grid[:]
    if kind == "verse":
        if opening_scene == "drum_tease":
            if local_bar == 0:
                kick_beats = [0.0, 2.0]
            elif local_bar == 1:
                kick_beats = [0.0, 2.0, 3.0]
        elif opening_scene == "bass_tease":
            if local_bar == 0:
                kick_beats = [0.0]
            elif local_bar == 1:
                kick_beats = [0.0, 2.0]
        elif opening_scene == "hook_tease" and local_bar < 2:
            kick_beats = [2.0, 3.0]
    if kind == "build" and role in ("lift", "transition") and not transition["pre_drop_void"]:
        kick_beats = quarter_grid[:]
    if transition["drum_pullback"] and kind == "build" and role == "transition":
        kick_beats = [0.0, 2.0]
    if transition["pre_drop_void"] and kind == "build" and role == "transition":
        kick_beats = [0.0, 2.0]
    if kind == "build":
        if build_stage == "recover":
            kick_beats = [0.0, 2.0]
        elif build_stage == "gather":
            kick_beats = quarter_grid[:]
        elif build_stage == "launch":
            kick_beats = quarter_grid[:]
    if kind == "drop":
        if drop_role == "tease":
            kick_beats = [2.0, 3.0]
        elif drop_role == "tight":
            kick_beats = [0.0, 1.0, 2.0, 3.0]
        elif drop_role in ("statement", "upgrade", "release", "wider", "emotional"):
            kick_beats = quarter_grid[:]
    if kind == "drop" and local_bar < 2 and arrival == "hook_first":
        kick_beats = [0.0, 1.0, 2.0, 3.0]
    if support_timing == "late_bloom" and kind in ("drop", "build"):
        kick_beats = [beat for beat in kick_beats if beat >= 1.0] or kick_beats[-2:]
    elif support_timing == "response_window" and kind in ("drop", "build"):
        kick_beats = [beat for beat in kick_beats if beat >= 2.0] or kick_beats[-2:]
    if kind == "outro":
        if outro_stage == "thin":
            kick_beats = [0.0, 2.0]
        elif outro_stage == "tail":
            kick_beats = [0.0]
        elif outro_stage == "final":
            kick_beats = []
    if support["drums"] == "shadow":
        kick_beats = kick_beats[:max(2, len(kick_beats) // 2)]
    elif support["drums"] == "response":
        kick_beats = [beat for beat in kick_beats if beat >= 2.0] or kick_beats[-2:]
    if groove_profile == "syncopated" and kind in ("build", "drop"):
        if local_bar % 2 == 1:
            kick_beats = sorted(set(kick_beats + [3.5]))
    elif groove_profile == "breathing" and kind in ("build", "drop") and local_bar % 2 == 0:
        kick_beats = [beat for beat in kick_beats if beat in (0.0, 2.0)] or kick_beats[:2]
    elif groove_profile == "push_pull" and kind in ("build", "drop") and role in ("lift", "transition"):
        kick_beats = sorted(set(kick_beats + [3.5]))
    if weight_profile == "late_bloom" and not is_second_pass and kind in ("build", "drop"):
        kick_beats = [beat for beat in kick_beats if beat >= 2.0] or kick_beats[-2:]
    elif weight_profile == "breakdown_heavy" and not is_second_pass and kind == "drop":
        kick_beats = [beat for beat in kick_beats if beat >= 1.0] or kick_beats[-3:]
    if progression_family == "lifted":
        if kind in ("build", "drop"):
            if not (kind == "build" and transition["pre_drop_void"] and role == "transition"):
                if not (kind == "drop" and drop_role == "tease" and local_bar < 2):
                    kick_beats = quarter_grid[:]
        elif kind == "verse" and local_bar >= 2 and opening_scene != "bass_tease":
            kick_beats = quarter_grid[:]
    kick_beats = filter_beats_to_grid(filter_to_step_grid(kick_beats, 1.0), quarter_grid)

    kick_velocity = clamp(int((88 + intensity * 26) * focus["groove"] * support_state_factor(support["drums"]) * macro["drum_bias"] * (macro["drop_force"] if kind == "drop" else macro["build_escalation"] if kind == "build" else 1.0)), 0, 124)
    if kick_velocity > 0:
        if weight_profile == "late_bloom" and not is_second_pass and kind in ("build", "drop"):
            kick_velocity = clamp(kick_velocity - 12, 0, 122)
        elif weight_profile == "front_loaded" and not is_second_pass and kind in ("build", "drop"):
            kick_velocity = clamp(kick_velocity + 6, 0, 124)
        elif weight_profile == "breakdown_heavy" and not is_second_pass and kind == "drop":
            kick_velocity = clamp(kick_velocity - 8, 0, 122)
        if kind == "drop":
            if drop_role == "tease":
                kick_velocity = clamp(kick_velocity - 12, 0, 118)
            elif drop_role == "tight":
                kick_velocity = clamp(kick_velocity - 6, 0, 120)
            elif drop_role == "upgrade":
                kick_velocity = clamp(kick_velocity + 4, 0, 124)
            elif drop_role == "release":
                kick_velocity = clamp(kick_velocity + 8, 0, 124)
            elif drop_role == "emotional":
                kick_velocity = clamp(kick_velocity + 2, 0, 122)
            kick_velocity = clamp(int(kick_velocity * finish_factor * kick_variant), 0, 122)
            if is_second_pass and drop_role in ("release", "upgrade", "wider"):
                kick_beats = kick_beats[:max(5, len(kick_beats) - 1)]
            if density_variant < 1.0 and kick_beats:
                kick_beats = kick_beats[:max(4, len(kick_beats) - 1)]
            elif density_variant > 1.0 and tail_bias == "longer" and kind == "build":
                kick_beats = sorted(set(kick_beats + [3.5]))
        elif kind == "build":
            if build_stage == "recover":
                kick_velocity = clamp(kick_velocity - 16, 0, 110)
            elif build_stage == "gather":
                kick_velocity = clamp(kick_velocity - 6, 0, 116)
            elif build_stage == "launch":
                kick_velocity = clamp(kick_velocity + 4, 0, 124)
        if progression_family == "lifted" and kind in ("build", "drop", "verse"):
            kick_velocity = clamp(kick_velocity + (4 if kind == "drop" else 2), 0, 124)
        kick_beats = filter_beats_to_grid(filter_to_step_grid(kick_beats, 0.5), half_grid)
        kick_len = 0.24 if progression_family == "lifted" else 0.22
        for idx, beat_pos in enumerate(kick_beats):
            extra = 3 if role in ("lift", "transition") and beat_pos >= 2.0 else 0
            if kind == "drop" and local_bar < 2 and arrival == "slam" and beat_pos == 0.0:
                extra += 5
            if kick_phrase == "front_push":
                extra += 4 if beat_pos in (0.0, 2.0) else -1
            elif kick_phrase == "back_push":
                extra += 4 if beat_pos in (1.0, 3.0) else 0
            elif kick_phrase == "pump":
                extra += 3 if idx % 2 == 0 else -2
            if kind == "verse":
                if verse_entry_stage == "kick_only":
                    extra -= 3 if beat_pos in (1.0, 3.0) else 0
                elif verse_entry_stage == "hat_tease":
                    extra -= 2 if beat_pos in (1.0, 3.0) else 0
                elif verse_entry_stage == "clap_arrives":
                    extra += 2 if beat_pos in (0.0, 2.0) else 0
                elif verse_entry_stage == "settle_in":
                    extra += 3 if beat_pos in (0.0, 2.0) else -1
            if progression_family == "lifted":
                extra += 4 if beat_pos in (0.0, 2.0) else 2
                if kind == "drop":
                    extra += 2
            add_event(tracks["kick"], start_tick + tick(beat_pos), 36, tick(kick_len), velocity=clamp(kick_velocity - idx + extra, 1, 124))

    clap_velocity = clamp(int((82 + intensity * 24) * support_state_factor(support["drums"]) * macro["drum_bias"]), 0, 120)
    if clap_velocity > 0:
        clap_beats = (1.0, 3.0)
        if kind == "verse" and local_bar < 2:
            clap_beats = ()
        if kind == "verse":
            if verse_entry_stage == "kick_only":
                clap_beats = ()
            elif verse_entry_stage == "hat_tease":
                clap_beats = ()
            elif verse_entry_stage == "clap_arrives":
                clap_beats = (3.0,)
            elif verse_entry_stage == "settle_in":
                clap_beats = (3.0,)
            elif local_bar == 3 and verse_entry_variant in ("kick_only", "clap_late"):
                clap_beats = (3.0,) if clap_pattern == "sparse_answer" else (1.0, 3.0)
            if opening_scene == "drum_tease" and local_bar < 2:
                clap_beats = ()
            elif opening_scene == "bass_tease" and local_bar < 3:
                clap_beats = (3.0,) if local_bar == 2 else ()
        if kind == "outro":
            if outro_stage in ("tail", "final"):
                clap_beats = ()
            elif outro_stage == "thin":
                clap_beats = (3.0,)
        if kind == "drop":
            if drop_role == "tease":
                clap_beats = (3.0,)
            else:
                clap_beats = (1.0, 3.0)
        elif clap_pattern == "sparse_answer":
            clap_beats = (3.0,)
        if support["drums"] == "response":
            clap_beats = (3.0,)
        if drum_micro == "late_caps" and kind in ("verse", "drop"):
            clap_beats = tuple(beat for beat in clap_beats if beat >= 3.0) or (3.0,)
        if kind == "drop":
            clap_velocity = clamp(int(clap_velocity * finish_factor * clap_variant), 0, 114)
            if drop_role == "tight":
                clap_velocity = clamp(clap_velocity - 6, 0, 108)
            elif drop_role == "emotional":
                clap_velocity = clamp(clap_velocity + 4, 0, 114)
            if density_variant < 1.0 and len(clap_beats) > 1:
                clap_beats = tuple(clap_beats[-1:])
        if kind in ("verse", "drop", "outro"):
            clap_beats = tuple(filter_beats_to_grid(filter_to_step_grid(clap_beats, 0.5), half_grid))
        for beat_pos in clap_beats:
            add_event(tracks["clap_snare"], start_tick + tick(beat_pos), 39, tick(0.18), velocity=clap_velocity)
        if kind == "verse" and clap_velocity > 0:
            if clap_pattern == "late_push" and verse_entry_stage in ("clap_arrives", "settle_in", "open_up") and local_bar >= 2:
                add_event(tracks["clap_snare"], start_tick + tick(3.5), 38, tick(0.08), velocity=clamp(clap_velocity - 16, 1, 104))
            elif clap_pattern == "split_tail" and verse_entry_stage in ("settle_in", "open_up"):
                add_event(tracks["clap_snare"], start_tick + tick(3.5), 38, tick(0.08), velocity=clamp(clap_velocity - 12, 1, 108))

    hat_steps = 4
    if style in ("driving", "festival"):
        hat_steps = 8
    if style == "festival" and kind == "drop":
        hat_steps = 16
    if style == "minimal" and kind != "drop":
        hat_steps = 2
    if kind == "drop" and macro["drop_force"] > 1.08:
        hat_steps = min(16, hat_steps + 4)
    elif kind == "drop" and macro["drop_force"] < 0.95 and not is_second_pass:
        hat_steps = max(2, hat_steps - 2)
    if role == "lift" and kind in ("build", "drop"):
        hat_steps = max(hat_steps, 8)
    if role == "transition" and kind == "drop":
        hat_steps = max(hat_steps, 16)
    if kind == "verse":
        if opening_scene == "drum_tease":
            if local_bar == 0:
                hat_steps = max(4, min(hat_steps, 4))
            elif local_bar == 1:
                hat_steps = max(4, min(hat_steps, 8))
        elif opening_scene == "bass_tease":
            if local_bar == 0:
                hat_steps = 0
            elif local_bar == 1:
                hat_steps = max(2, min(hat_steps, 4))
        elif opening_scene == "hook_tease" and local_bar < 2:
            hat_steps = max(2, min(hat_steps, 4))
    if transition["drum_pullback"] and kind == "build" and role == "transition":
        hat_steps = min(hat_steps, 4)
    if transition["pre_drop_void"] and kind == "build" and role == "transition":
        hat_steps = 0
    if kind == "drop" and local_bar < 2 and arrival == "hook_first":
        hat_steps = min(hat_steps, 8)
    if drum_grammar == "minimal_frame":
        hat_steps = min(hat_steps, 4 if kind == "drop" else 2)
    elif drum_grammar == "push_hat":
        hat_steps = max(hat_steps, 8)
    elif drum_grammar == "festival_lift":
        hat_steps = max(hat_steps, 16 if kind == "drop" else 8)
    elif drum_grammar == "steady_drive" and kind in ("drop", "build"):
        hat_steps = max(hat_steps, 8)
    if drum_micro == "straight_caps":
        hat_steps = max(4, min(hat_steps, 8 if kind == "drop" else 4))
    elif drum_micro == "busy_caps":
        hat_steps = max(hat_steps, 16 if kind == "drop" else 8)
    elif drum_micro == "late_caps":
        hat_steps = max(4, hat_steps // 2)
    if kind == "drop":
        if drop_role == "statement":
            hat_steps = max(4, min(hat_steps, 8))
        elif drop_role == "tease":
            hat_steps = max(2, hat_steps // 2)
        elif drop_role == "tight":
            hat_steps = max(4, min(hat_steps, 6))
        elif drop_role == "upgrade":
            hat_steps = max(hat_steps, 12 if style != "festival" else 16)
        elif drop_role == "release":
            hat_steps = max(hat_steps, 16)
        elif drop_role == "wider":
            hat_steps = max(hat_steps, 12)
        elif drop_role == "emotional":
            hat_steps = max(6, min(hat_steps, 12))
        if is_second_pass and drop_role in ("release", "upgrade", "wider"):
            hat_steps = min(hat_steps, 12)
        if density_variant < 1.0:
            hat_steps = max(2, hat_steps - 2)
        elif density_variant > 1.0:
            hat_steps = min(16, hat_steps + 2)
    if support_timing == "late_bloom" and kind in ("drop", "build"):
        hat_steps = max(0, hat_steps // 2)
    elif support_timing == "response_window" and kind in ("drop", "build"):
        hat_steps = max(0, hat_steps // 2)
    if support["drums"] == "shadow":
        hat_steps = max(0, hat_steps // 2)
    elif support["drums"] == "response":
        hat_steps = max(0, hat_steps // 2)
    if kind == "build":
        if build_stage == "recover":
            hat_steps = max(0, min(hat_steps, 2))
        elif build_stage == "gather":
            hat_steps = max(4, min(hat_steps, 8))
        elif build_stage == "launch":
            hat_steps = max(hat_steps, 8)
    if weight_profile == "late_bloom" and not is_second_pass and kind in ("build", "drop"):
        hat_steps = max(0, hat_steps // 2)
    elif weight_profile == "front_loaded" and not is_second_pass and kind in ("build", "drop"):
        hat_steps = max(hat_steps, 8 if kind == "build" else 16)
    elif weight_profile == "breakdown_heavy" and not is_second_pass and kind == "drop":
        hat_steps = max(4, hat_steps // 2)
    if kind == "drop" and local_bar < 2 and drop_pair_profile == "drop1_tease_drop2_release":
        hat_steps = min(hat_steps, 8)
    elif kind == "drop" and local_bar < 2 and drop_pair_profile == "drop1_full_drop2_wider":
        hat_steps = max(hat_steps, 16)
    if groove_profile == "syncopated" and kind in ("build", "drop") and local_bar % 2 == 1:
        hat_steps = min(16, hat_steps + 2)
    elif groove_profile == "breathing" and kind in ("build", "drop") and local_bar % 2 == 0:
        hat_steps = max(2, hat_steps // 2)
    elif groove_profile == "push_pull" and kind in ("build", "drop") and role in ("lift", "transition"):
        hat_steps = min(16, max(hat_steps, 8))
    if is_second_pass:
        if final_lift_profile == "subtle_return":
            hat_steps = max(4, hat_steps // 2 if kind == "build" else hat_steps)
        elif final_lift_profile == "anthem_push":
            hat_steps = max(hat_steps, 16 if kind == "drop" else 8)
        elif final_lift_profile == "wide_release":
            hat_steps = max(hat_steps, 12 if kind == "drop" else 8)
        elif final_lift_profile == "hook_reinforcement":
            hat_steps = max(hat_steps, 8)
    if macro_profile == "drop_pressure" and kind in ("build", "drop"):
        hat_steps = max(hat_steps, 8 if kind == "build" else 16)
    elif macro_profile == "vocal_journey" and kind == "breakdown":
        hat_steps = min(hat_steps, 2)
    if kind == "drop":
        hat_cap = 12
        if style == "festival" and drop_role in ("release", "upgrade", "wider") and hat_variant > 1.0:
            hat_cap = 14
        if support["drums"] in ("shadow", "response") or support_timing in ("late_bloom", "response_window"):
            hat_cap = min(hat_cap, 10)
        hat_steps = min(hat_steps, hat_cap)
    elif kind == "build":
        hat_steps = min(hat_steps, 8)
    hat_velocity = clamp(int((44 + intensity * 36) * focus["groove"] * support_state_factor(support["drums"])), 0, 108)
    if hat_steps > 0 and hat_velocity > 0:
        if kind == "drop":
            hat_velocity = clamp(int(hat_velocity * finish_factor * hat_variant), 0, 102)
            if hat_steps >= 12:
                hat_velocity = clamp(hat_velocity - 4, 0, 98)
        hat_positions = [step * (4 / hat_steps) for step in range(hat_steps)]
        if kind == "verse":
            verse_hat_templates = {
                "steady_8th": {
                    "kick_only": [],
                    "hat_tease": [3.5],
                    "clap_arrives": [1.5, 3.5],
                    "settle_in": [0.5, 1.5, 3.5],
                    "open_up": [0.5, 1.5, 2.5, 3.5],
                    "full": [0.5, 1.5, 2.5, 3.5] if local_bar % 2 == 0 else [0.5, 1.0, 1.5, 2.5, 3.0, 3.5],
                },
                "air_16th": {
                    "kick_only": [],
                    "hat_tease": [2.5, 3.0, 3.5],
                    "clap_arrives": [1.0, 1.5, 2.5, 3.0, 3.5],
                    "settle_in": [0.5, 1.5, 2.5, 3.0, 3.5],
                    "open_up": [0.5, 1.0, 1.5, 2.5, 3.0, 3.5],
                    "full": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5] if local_bar % 2 == 0 else [0.5, 1.0, 1.5, 2.5, 3.0, 3.5],
                },
                "late_8th": {
                    "kick_only": [],
                    "hat_tease": [3.5],
                    "clap_arrives": [3.5],
                    "settle_in": [1.5, 3.0, 3.5],
                    "open_up": [1.0, 1.5, 2.5, 3.0, 3.5],
                    "full": [1.0, 1.5, 2.5, 3.0, 3.5] if local_bar % 2 == 0 else [0.5, 1.5, 2.5, 3.5],
                },
                "tight_16th": {
                    "kick_only": [],
                    "hat_tease": [2.5, 3.0, 3.5] if verse_entry_variant == "rolling_open" else [1.5, 3.5],
                    "clap_arrives": [0.5, 1.5, 2.5, 3.0, 3.5],
                    "settle_in": [0.5, 1.5, 2.5, 3.0, 3.5],
                    "open_up": [0.5, 1.0, 1.5, 2.5, 3.0, 3.5],
                    "full": [0.5, 1.0, 1.5, 2.5, 3.0, 3.5] if local_bar % 2 == 0 else [0.5, 1.5, 2.0, 2.5, 3.0, 3.5],
                },
            }
            stage_key = verse_entry_stage or "full"
            hat_positions = verse_hat_templates.get(hat_grid, verse_hat_templates["steady_8th"]).get(stage_key, hat_positions)
        elif kind == "build":
            if build_stage == "recover":
                hat_positions = [3.5]
            elif build_stage == "gather":
                hat_positions = [1.5, 3.5] if local_bar % 2 == 0 else [0.5, 1.5, 2.5, 3.5]
            elif build_stage == "launch":
                hat_positions = [0.5, 1.0, 1.5, 2.5, 3.0, 3.5]
        if kind == "drop":
            hat_templates = {
                "steady_8th": {
                    "statement": [0.5, 1.5, 2.5, 3.5],
                    "tight": [0.5, 1.5, 2.5, 3.5],
                    "upgrade": [0.5, 1.5, 2.0, 2.5, 3.0, 3.5],
                    "release": [0.5, 1.0, 1.5, 2.5, 3.0, 3.5],
                    "wider": [0.5, 1.5, 2.5, 3.5],
                    "emotional": [0.5, 1.5, 2.5, 3.5],
                    "tease": [2.5, 3.5],
                },
                "air_16th": {
                    "statement": [0.5, 1.0, 1.5, 2.5, 3.0, 3.5],
                    "tight": [0.5, 1.5, 2.5, 3.5],
                    "upgrade": [0.5, 0.75, 1.5, 2.5, 2.75, 3.0, 3.5, 3.75],
                    "release": [0.5, 0.75, 1.5, 2.0, 2.5, 2.75, 3.5, 3.75],
                    "wider": [0.5, 1.0, 1.5, 2.5, 3.0, 3.5],
                    "emotional": [0.5, 1.5, 2.5, 3.5],
                    "tease": [2.5, 3.0, 3.5],
                },
                "late_8th": {
                    "statement": [0.5, 1.5, 2.5, 3.5],
                    "tight": [1.5, 3.5],
                    "upgrade": [1.0, 1.5, 2.5, 3.0, 3.5],
                    "release": [1.0, 1.5, 2.5, 3.0, 3.5],
                    "wider": [0.5, 1.5, 2.5, 3.5],
                    "emotional": [1.5, 2.5, 3.5],
                    "tease": [2.5, 3.5],
                },
                "tight_16th": {
                    "statement": [0.5, 1.0, 1.5, 2.5, 3.0, 3.5],
                    "tight": [0.5, 1.5, 2.5, 3.5],
                    "upgrade": [0.5, 1.0, 1.5, 2.5, 3.0, 3.25, 3.5, 3.75],
                    "release": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.25, 3.5],
                    "wider": [0.5, 1.0, 1.5, 2.5, 3.0, 3.5],
                    "emotional": [0.5, 1.5, 2.5, 3.5],
                    "tease": [2.5, 3.0, 3.5],
                },
            }
            hat_positions = hat_templates.get(hat_grid, hat_templates["steady_8th"]).get(drop_role, hat_positions)
            if support["drums"] == "shadow":
                hat_positions = hat_positions[-max(2, len(hat_positions) // 2):]
            elif support["drums"] == "response":
                hat_positions = [beat for beat in hat_positions if beat >= 2.0] or hat_positions[-2:]
            if support_timing == "late_bloom":
                hat_positions = [beat for beat in hat_positions if beat >= 1.0] or hat_positions[-2:]
            elif support_timing == "response_window":
                hat_positions = [beat for beat in hat_positions if beat >= 2.0] or hat_positions[-2:]
            if density_variant < 1.0 and len(hat_positions) > 8:
                hat_positions = hat_positions[:8]
            elif density_variant > 1.0 and tail_bias == "longer" and len(hat_positions) < 12:
                hat_positions = sorted(set(hat_positions + [3.5]))
        if kind in ("verse", "drop", "outro"):
            hat_positions = filter_to_step_grid(hat_positions, 0.25)
        if kind == "outro":
            if outro_stage == "thin":
                hat_positions = [1.5, 3.5]
            elif outro_stage == "tail":
                hat_positions = [3.5]
            elif outro_stage == "final":
                hat_positions = []
        hat_steps = max(1, len(hat_positions))
        for step, beat_pos in enumerate(hat_positions):
            if support_timing == "late_bloom" and beat_pos < 1.0:
                continue
            if support_timing == "response_window" and beat_pos < 2.0:
                continue
            if drum_micro == "late_caps" and beat_pos < 2.0:
                continue
            if kind == "drop":
                if drop_role == "tease" and beat_pos < 2.0:
                    continue
                if drop_role == "tight" and beat_pos in (0.5, 1.5, 2.5):
                    continue
            midi_note = 42 if step % 2 == 0 else 46
            if style == "driving" and step % 4 == 3:
                midi_note = 42
            if drum_micro == "straight_caps":
                midi_note = 42 if step % 2 == 0 else 46
            elif drum_micro == "busy_caps":
                midi_note = 46 if step % 4 in (1, 3) else 42
            accent = 5 if role == "develop" and step in (0, 3, 6) else 0
            accent += 8 if role == "lift" and step >= max(0, hat_steps - 4) else 0
            accent += 10 if role == "transition" and step >= max(0, hat_steps - 3) else 0
            if kind == "drop" and local_bar < 2 and arrival == "slam" and step < max(1, hat_steps // 4):
                accent += 10
            elif kind == "drop" and local_bar < 2 and arrival == "glide_in" and step < max(1, hat_steps // 3):
                accent -= 8
            if drum_micro == "busy_caps":
                accent += 3 if step % 2 == 1 else 0
            elif drum_micro == "straight_caps":
                accent -= 2 if step % 2 == 1 else 0
            if kind == "drop":
                if drop_role == "statement":
                    accent += 2 if beat_pos in (0.0, 2.0, 3.0) else 0
                elif drop_role == "upgrade":
                    accent += 4 if beat_pos >= 2.5 else 0
                elif drop_role == "release":
                    accent += 6 if beat_pos >= 2.0 else 0
                elif drop_role == "emotional":
                    accent += 3 if beat_pos in (2.0, 2.6666666666666665, 3.0, 3.3333333333333335, 3.5, 3.75) else 0
            add_event(tracks["hats"], start_tick + tick(beat_pos), midi_note, tick(0.08), velocity=clamp(hat_velocity - (step % 3) + accent, 1, 124))

    if clap_velocity > 0 and kind == "build" and (role in ("lift", "transition") or local_bar >= bars_in_section - 2):
        if transition["snare_lift"]:
            roll_positions = [2.0, 2.5, 3.0, 3.5]
        elif style == "festival":
            roll_positions = [2.0, 2.5, 3.0, 3.5]
        elif style == "driving":
            roll_positions = [2.5, 3.0, 3.5]
        else:
            roll_positions = [2.0, 2.5, 3.0, 3.5]
        if drum_grammar == "minimal_frame":
            roll_positions = [3.0, 3.5, 3.75]
        elif drum_grammar == "push_hat":
            roll_positions = sorted(set(roll_positions + [2.0]))
        elif drum_grammar == "steady_drive":
            roll_positions = sorted(set(roll_positions + [3.0]))
        if drum_micro == "straight_caps":
            roll_positions = roll_positions[:max(2, len(roll_positions) // 2)]
        elif drum_micro == "busy_caps":
            roll_positions = sorted(set(roll_positions + [2.5, 3.5]))
        elif drum_micro == "late_caps":
            roll_positions = [beat for beat in roll_positions if beat >= 3.0]
        if transition["pre_drop_void"]:
            roll_positions = [2.5, 3.0]
        if weight_profile == "late_bloom" and not is_second_pass:
            roll_positions = [beat for beat in roll_positions if beat >= 3.0]
        elif weight_profile == "front_loaded" and not is_second_pass:
            roll_positions = sorted(set(roll_positions + [2.0]))
        elif weight_profile == "breakdown_heavy" and not is_second_pass:
            roll_positions = [beat for beat in roll_positions if beat >= 3.0]
        if is_second_pass:
            if final_lift_profile == "subtle_return":
                roll_positions = [beat for beat in roll_positions if beat >= 3.0]
            elif final_lift_profile == "anthem_push":
                roll_positions = sorted(set(roll_positions + [2.5, 3.5]))
            elif final_lift_profile == "wide_release":
                roll_positions = sorted(set(roll_positions + [2.5, 3.5]))
            elif final_lift_profile == "hook_reinforcement":
                roll_positions = sorted(set(roll_positions + [3.5]))
        if support_timing == "late_bloom":
            roll_positions = [beat for beat in roll_positions if beat >= 2.5]
        elif support_timing == "response_window":
            roll_positions = [beat for beat in roll_positions if beat >= 3.0]
        if support["drums"] == "shadow":
            roll_positions = roll_positions[:max(1, len(roll_positions) // 2)]
        elif support["drums"] == "response":
            roll_positions = [beat for beat in roll_positions if beat >= 3.0]
        roll_positions = filter_to_step_grid(roll_positions, 0.5)
        for idx, beat_pos in enumerate(roll_positions):
            add_event(tracks["clap_snare"], start_tick + tick(beat_pos), 38, tick(0.08), velocity=clamp(76 + idx * 5, 76, 124))
    elif clap_velocity > 0 and kind == "drop" and role == "transition":
        for idx, beat_pos in enumerate([3.0, 3.5]):
            add_event(tracks["clap_snare"], start_tick + tick(beat_pos), 38, tick(0.06), velocity=clamp(82 + idx * 6, 82, 124))
    elif clap_velocity > 0 and kind == "drop" and local_bar < 2 and arrival == "staggered":
        add_event(tracks["clap_snare"], start_tick + tick(1.5), 38, tick(0.08), velocity=clamp(clap_velocity + 8, 1, 124))


def add_lead_family(tracks, start_tick: int, chord, kind: str, local_bar: int, section_bars: int, intensity: float, identity, blueprint, is_second_pass: bool, chords=None):
    if kind not in ("verse", "build", "drop", "breakdown"):
        return

    role = phrase_role(local_bar, section_bars)
    macro = macro_contrast_profile(kind, role, blueprint, is_second_pass)
    lead_archetype = blueprint["lead_archetype"]
    vocal_archetype = blueprint["vocal_archetype"]
    counter_style = blueprint["countermelody_style"]
    counter_grammar = blueprint["archetype_counter_grammar"]
    counter_contour = blueprint["archetype_counter_contour"]
    counter_presence = blueprint["archetype_counter_presence"]
    counter_span = blueprint["archetype_counter_span"]
    counter_register = blueprint["archetype_counter_register"]
    counter_role = blueprint["archetype_counter_role"]
    arrival = blueprint["drop_arrival_style"]
    breakdown_style = blueprint["breakdown_style"]
    breakdown_narrative = blueprint["breakdown_narrative"]
    breakdown_function = blueprint.get("breakdown_function", "harmonic_lift")
    drop_role = drop_section_role(blueprint, is_second_pass)
    finish_factor = finishability_factor(blueprint)
    lead_variant = bounded_variant(blueprint, "variant_lead_gain")
    counter_variant = bounded_variant(blueprint, "variant_strings_gain")
    counter_spread = blueprint.get("variant_counter_spread", "balanced")
    recall_style = blueprint["hook_recall_style"]
    recall_amount = callback_multiplier(blueprint["callback_density"], kind, role, is_second_pass)
    focus = focus_hierarchy(kind, role, blueprint, is_second_pass)
    transition = transition_profile(kind, role, blueprint, is_second_pass)
    relation = lead_vocal_profile(kind, role, blueprint, is_second_pass)
    ownership = top_line_ownership(kind, role, relation, is_second_pass)
    support_profile = arrangement_support_profile(kind, role, local_bar, blueprint, is_second_pass)
    second_drop_stage = second_drop_cleanup_stage(kind, local_bar, is_second_pass)
    lead_entry_open = early_verse_allows(kind, local_bar, "lead")
    counter_entry_open = early_verse_allows(kind, local_bar, "counter")
    vocal_entry_open = early_verse_allows(kind, local_bar, "vocal")
    build_stage = build_story_stage(kind, local_bar, section_bars, is_second_pass)
    breakdown_stage = breakdown_story_stage(local_bar, section_bars) if kind == "breakdown" else None
    lead_stage = lead_phrase_stage(local_bar, section_bars, is_second_pass)
    topline_density = blueprint["archetype_topline_density"]
    resolution_bias = blueprint["lead_resolution_bias"]
    progression_family = blueprint["progression_family"]
    cadence_profile = blueprint["cadence_profile"]
    drop_harmony_entry = blueprint["drop_harmony_entry"]
    lead_evolution = blueprint.get("lead_evolution_profile", "resolved")
    counter_engine = blueprint.get("countermelody_engine", "answer_arc")
    counter_answer_mode = COUNTER_ANSWER_MODES[(local_bar + (2 if is_second_pass else 0)) % len(COUNTER_ANSWER_MODES)]
    if is_second_pass:
        blueprint["_selected_counter_answer_mode"] = counter_answer_mode
    root_note = chord["root"] + 12
    third_note = chord["third"] + 12
    anchor = identity["anchor"]
    support = max(chord["third"], identity["support"] - 12)
    lift = max(chord["root"] + 12, identity["lift"] - 12)
    resolve = max(chord["fifth"], identity["resolve"] - 12)
    high_anchor = anchor + 12
    if resolution_bias == "root_anchor":
        resolve = max(chord["root"] + 12, identity["resolve"] - 12)
    elif resolution_bias == "third_to_root":
        support = max(chord["third"] + 12, support)
        resolve = max(chord["root"] + 12, identity["resolve"] - 12)
    elif resolution_bias == "suspended_lift":
        lift = max(chord["third"] + 12, lift)
        resolve = max(chord["third"] + 12, chord["fifth"])
    elif resolution_bias == "fifth_to_tonic":
        anchor = max(chord["fifth"] + 12, anchor)
        high_anchor = anchor + 12

    lead_templates = {
        "anthemic": {
            "verse": section_matched_lead_phrase("verse", role, local_bar, "anthemic", progression_family, cadence_profile, drop_harmony_entry, relation, anchor, support, lift, resolve, high_anchor),
            "build": section_matched_lead_phrase("build", role, local_bar, "anthemic", progression_family, cadence_profile, drop_harmony_entry, relation, anchor, support, lift, resolve, high_anchor),
            "drop": section_matched_lead_phrase("drop", role, local_bar, "anthemic", progression_family, cadence_profile, drop_harmony_entry, relation, anchor, support, lift, resolve, high_anchor),
        },
        "yearning": {
            "verse": section_matched_lead_phrase("verse", role, local_bar, "yearning", progression_family, cadence_profile, drop_harmony_entry, relation, anchor, support, lift, resolve, high_anchor),
            "build": section_matched_lead_phrase("build", role, local_bar, "yearning", progression_family, cadence_profile, drop_harmony_entry, relation, anchor, support, lift, resolve, high_anchor),
            "drop": section_matched_lead_phrase("drop", role, local_bar, "yearning", progression_family, cadence_profile, drop_harmony_entry, relation, anchor, support, lift, resolve, high_anchor),
        },
        "driving": {
            "verse": section_matched_lead_phrase("verse", role, local_bar, "driving", progression_family, cadence_profile, drop_harmony_entry, relation, anchor, support, lift, resolve, high_anchor),
            "build": section_matched_lead_phrase("build", role, local_bar, "driving", progression_family, cadence_profile, drop_harmony_entry, relation, anchor, support, lift, resolve, high_anchor),
            "drop": section_matched_lead_phrase("drop", role, local_bar, "driving", progression_family, cadence_profile, drop_harmony_entry, relation, anchor, support, lift, resolve, high_anchor),
        },
        "uplift_hook": {
            "verse": section_matched_lead_phrase("verse", role, local_bar, "uplift_hook", progression_family, cadence_profile, drop_harmony_entry, relation, anchor, support, lift, resolve, high_anchor),
            "build": section_matched_lead_phrase("build", role, local_bar, "uplift_hook", progression_family, cadence_profile, drop_harmony_entry, relation, anchor, support, lift, resolve, high_anchor),
            "drop": section_matched_lead_phrase("drop", role, local_bar, "uplift_hook", progression_family, cadence_profile, drop_harmony_entry, relation, anchor, support, lift, resolve, high_anchor),
        },
    }

    if kind == "breakdown":
        if breakdown_narrative == "memory_recall":
            phrase = theme_phrase_events(identity, blueprint, chord, role, register_shift=-12, rhythm_scale=1.1)
        elif breakdown_narrative == "space_then_lift":
            phrase = [(2.0, 1.1, lift - 12)] if role in ("establish", "repeat") else [(0.0, 0.8, support - 12), (2.5, 0.9, lift - 12)]
        elif breakdown_narrative == "piano_confession":
            phrase = [(0.5, 0.8, anchor - 12), (2.5, 1.0, resolve - 12)]
            if recall_style in ("emotive_fragment", "direct_echo"):
                phrase = theme_phrase_events(identity, blueprint, chord, role, register_shift=-12, rhythm_scale=1.0)[:2] + phrase[-1:]
        else:
            phrase = [(0.0, 0.8, support - 12)]
            if role in ("lift", "transition"):
                phrase.append((2.5, 1.0, lift - 12))
        if relation["shared_hook"] or relation["relation"] == "lead_carries_drop_vocal_carries_breakdown":
            phrase = theme_phrase_events(identity, blueprint, chord, role, register_shift=-12, rhythm_scale=0.95)[:max(1, min(3, len(phrase)))]
        if breakdown_function == "vocal_exposure":
            phrase = [entry for entry in phrase if entry[0] >= 2.0] or phrase[-1:]
            phrase = [(beat, min(1.0, length), clamp(pitch - 12, 48, 84)) for beat, length, pitch in phrase[:2]]
        elif breakdown_function == "memory_reset":
            phrase = theme_phrase_events(identity, blueprint, chord, role, register_shift=-12, rhythm_scale=1.2)[:2]
        elif breakdown_function == "harmonic_lift":
            phrase = phrase + [(2.25, 0.75, lift), (3.25, 0.8, resolve)]
        elif breakdown_function == "tension_hold":
            phrase = [(2.5, 0.9, support - 12), (3.25, 0.55, lift - 12)]
        if breakdown_stage == "reset":
            phrase = [(2.5, 1.0, support - 12)] if breakdown_style != "piano_led" else [(0.5, 1.0, anchor - 12), (2.5, 1.0, resolve - 12)]
        elif breakdown_stage == "hold":
            phrase = phrase[:max(1, min(2, len(phrase)))]
        elif breakdown_stage == "lift":
            phrase = phrase[:max(2, min(3, len(phrase)))] + [(3.0, 0.8, lift - 12)]
    elif kind == "build":
        phrase = lead_templates[lead_archetype]["build"][:]
        if relation["lead_answers"]:
            phrase = phrase[-2:]
        elif relation["shared_hook"]:
            phrase = phrase[:max(2, len(phrase) - 1)] + phrase[-1:]
        if role in ("lift", "transition"):
            phrase = phrase[:3] + [(3.0, 0.75, high_anchor if lead_archetype != "yearning" else resolve)]
        if local_bar % 4 == 3:
            phrase.append((3.5, 0.25, resolve))
        if macro["build_escalation"] < 0.95:
            phrase = phrase[:max(2, len(phrase) - 1)]
        elif macro["build_escalation"] > 1.08 and role in ("develop", "lift", "transition"):
            phrase = phrase + [(3.5, 0.2, high_anchor if lead_archetype != "yearning" else lift)]
        if build_stage == "recover":
            phrase = [entry for entry in phrase if entry[0] >= 2.0] or phrase[-1:]
        elif build_stage == "gather":
            phrase = phrase[:max(2, len(phrase) - 1)]
        elif build_stage == "launch":
            phrase = phrase + [(3.5, 0.2, high_anchor if lead_archetype != "yearning" else resolve)]
        phrase = add_phrase_motion(phrase, lead_archetype, role, kind, local_bar, anchor, support, lift, resolve)
    elif kind == "drop":
        global_bar = start_tick // BAR_TICKS
        phrase_start_bar = global_bar - (local_bar % 8)
        phrase_start_local_bar = local_bar - (local_bar % 8)
        phrase_cache = blueprint.setdefault("_selected_hook_phrases", {})
        cache_key = f"{section_display_name(kind, is_second_pass)}:{phrase_start_bar}"
        if chords is not None and cache_key not in phrase_cache:
            supersaw_forecast = forecast_drop_supersaw_window(
                phrase_start_bar,
                phrase_start_local_bar,
                section_bars,
                kind,
                intensity,
                blueprint,
                identity,
                is_second_pass,
                chords,
            )
            best_candidate, scored_candidates = select_best_hook_candidate(
                phrase_start_bar,
                chords,
                identity,
                section_display_name(kind, is_second_pass),
                supersaw_notes=supersaw_forecast,
                candidate_count=blueprint.get("hook_candidate_count", 4),
                recent_winners=blueprint.setdefault("_hook_selection_memory", []),
            )
            selection_memory = blueprint.setdefault("_hook_selection_memory", [])
            selection_memory.append({
                "archetype": best_candidate["archetype"],
                "signature": candidate_window_signature(best_candidate["notes"], phrase_start_bar),
            })
            blueprint["_hook_selection_memory"] = selection_memory[-4:]
            phrase_cache[cache_key] = {
                "selected_index": best_candidate["index"],
                "archetype": best_candidate["archetype"],
                "notes": best_candidate["notes"],
                "scores": [item["score"] for item in scored_candidates],
            }
        selected_phrase = phrase_cache.get(cache_key, {})
        selected_notes = selected_phrase.get("notes", [])
        phrase = []
        for note_data in selected_notes:
            if bar_tick(global_bar) <= note_data["start"] < bar_tick(global_bar + 1):
                beat_pos = round((note_data["start"] - bar_tick(global_bar)) / TICKS, 4)
                beat_len = round((note_data["end"] - note_data["start"]) / TICKS, 4)
                phrase.append((beat_pos, beat_len, note_data["pitch"]))
        if not phrase:
            phrase = lead_templates[lead_archetype]["drop"][:]
    else:
        phrase = lead_templates[lead_archetype]["verse"][:]
        if role == "develop":
            phrase = phrase[:1] + [(2.5, 0.55, support), (3.0, 0.6, resolve)]
        if relation["lead_answers"]:
            phrase = [(2.0, 0.45, support), (3.0, 0.55, resolve)]

    phrase = evolve_lead_phrase(
        phrase,
        lead_stage,
        lead_archetype,
        anchor,
        support,
        lift,
        resolve,
        high_anchor,
        root_note,
        third_note,
    )
    if lead_evolution == "climbing":
        if lead_stage in ("phrase_b", "payoff"):
            phrase = phrase + [(3.5, 0.22, clamp(high_anchor, 60, 102))]
    elif lead_evolution == "answering":
        if lead_stage == "phrase_a_repeat":
            phrase = [(beat, max(0.35, length), clamp(pitch - (2 if idx == 0 else 0), 60, 98)) for idx, (beat, length, pitch) in enumerate(phrase)]
        elif lead_stage == "payoff" and phrase:
            phrase[-1] = (phrase[-1][0], max(1.0, phrase[-1][1]), clamp(root_note, 60, 98))
    elif lead_evolution == "wide_payoff":
        if lead_stage == "phrase_b":
            phrase = phrase + [(2.75, 0.24, clamp(lift, 60, 100))]
        elif lead_stage == "payoff":
            phrase = phrase + [(3.25, 0.24, clamp(high_anchor, 60, 102)), (3.5, 0.28, clamp(high_anchor + 2, 60, 102))]
    elif lead_evolution == "resolved" and lead_stage == "payoff" and phrase:
        phrase[-1] = (phrase[-1][0], max(1.0, phrase[-1][1]), clamp(root_note if lead_archetype != "yearning" else third_note, 60, 98))

    phrase = trance_phrase_grid(
        phrase,
        step=0.5 if kind in ("build", "drop", "verse") else 0.25,
        min_length=0.3 if kind == "drop" else 0.35,
        max_events=4 if kind == "drop" else 3,
    )

    lead_velocity = clamp(int((68 + intensity * 36) * focus["lead"] * relation["lead_gain"] * macro["topline_bias"] * lead_variant), 46, 124)
    if kind == "drop":
        lead_velocity = clamp(int(lead_velocity * finish_factor), 42, 120)
    lead_active = ownership["lead"] != "none" and not (kind == "breakdown" and relation["lead_gain"] < 0.8 and role in ("establish", "repeat"))
    if kind == "verse" and not lead_entry_open:
        lead_active = False
    if topline_density == "vocal_heavy" and kind in ("verse", "breakdown"):
        lead_active = lead_active and role in ("lift", "transition")
    elif topline_density == "lead_heavy" and kind == "drop":
        lead_velocity = clamp(lead_velocity + 8, 46, 124)
    elif topline_density == "alternating" and kind in ("verse", "breakdown") and local_bar % 2 == 0:
        lead_active = False
    if ownership["lead"] == "early":
        phrase = [entry for entry in phrase if entry[0] < 2.0]
    elif ownership["lead"] == "late":
        phrase = [entry for entry in phrase if entry[0] >= 1.5]
    elif ownership["lead"] == "echo":
        phrase = trance_phrase_grid([(2.0 + beat * 0.25, min(0.35, length), pitch) for beat, length, pitch in phrase[:2]], step=0.5, min_length=0.3, max_events=2)
    if kind == "verse" and lead_active:
        if local_bar == 4:
            phrase = [entry for entry in phrase if entry[0] >= 2.5] or phrase[-1:]
            phrase = [(beat, min(length, 0.5), pitch) for beat, length, pitch in phrase[:1]]
            lead_velocity = clamp(lead_velocity - 18, 40, 110)
        elif local_bar == 5:
            phrase = [entry for entry in phrase if entry[0] >= 2.0] or phrase[-2:]
            phrase = [(beat, min(length, 0.55), pitch) for beat, length, pitch in phrase[:2]]
            lead_velocity = clamp(lead_velocity - 10, 42, 114)
    if lead_active:
        for beat_pos, beat_len, pitch in phrase:
            add_event(tracks["lead"], start_tick + tick(beat_pos), clamp(pitch, 60, 98), tick(beat_len), velocity=lead_velocity)

    if kind == "drop":
        theme_counter = theme_phrase_events(identity, blueprint, chord, role, register_shift=-12, rhythm_scale=0.6)
        progression_family = blueprint["progression_family"]
        counter_families = {
            "late_answer": {
                "lift": [(2.25, 0.35, identity["counter"]), (3.0, 0.4, identity["counter"] + 5)],
                "transition": [(2.0, 0.35, identity["counter"]), (2.75, 0.25, identity["counter"] + 5), (3.5, 0.18, identity["counter"] + 7)],
            },
            "constant_support": {
                "repeat": [(1.5, 0.3, identity["counter"]), (3.0, 0.35, identity["counter"] + 5)],
                "develop": [(1.0, 0.3, identity["counter"]), (2.5, 0.3, identity["counter"] + 5)],
                "lift": [(1.0, 0.25, identity["counter"]), (2.25, 0.25, identity["counter"] + 5), (3.25, 0.2, identity["counter"] + 7)],
            },
            "drop_tail": {
                "lift": [(3.0, 0.35, identity["counter"]), (3.5, 0.2, identity["counter"] + 7)],
                "transition": [(2.75, 0.25, identity["counter"]), (3.25, 0.2, identity["counter"] + 5), (3.75, 0.12, identity["counter"] + 12)],
            },
            "octave_echo": {
                "repeat": [(2.0, 0.3, identity["counter"] + 12), (3.0, 0.3, identity["counter"] + 5)],
                "develop": [(1.75, 0.25, identity["counter"] + 12), (2.75, 0.25, identity["counter"] + 7)],
                "transition": [(2.0, 0.25, identity["counter"]), (3.0, 0.25, identity["counter"] + 12), (3.5, 0.18, identity["counter"] + 7)],
            },
        }
        counter_map = counter_families[counter_style]
        counter_phrase = counter_map.get(role, [])
        if counter_role == "support":
            if role in ("repeat", "develop") and not counter_phrase:
                counter_phrase = [(2.0, 0.24, identity["counter"]), (3.0, 0.24, identity["counter"] + 5)]
        elif counter_role == "late_answer":
            counter_phrase = [entry for entry in counter_phrase if entry[0] >= 2.0]
            if role in ("lift", "transition") and not counter_phrase:
                counter_phrase = [(2.5, 0.24, identity["counter"]), (3.25, 0.2, identity["counter"] + 7)]
        elif counter_role == "featured_answer":
            counter_phrase = counter_phrase + [(beat + 0.125, max(0.18, length), clamp(pitch + 5, 48, 92)) for beat, length, pitch in counter_phrase[:2]]
        elif counter_role == "transition_push":
            if role == "transition":
                counter_phrase = counter_phrase + [(3.0, 0.18, identity["counter"] + 7), (3.5, 0.16, identity["counter"] + 12)]
        if counter_grammar == "tail_echo":
            counter_phrase = [(max(2.0, beat), max(0.18, min(length, 0.32)), clamp(pitch + 12, 48, 90)) for beat, length, pitch in counter_phrase]
        elif counter_grammar == "mid_answer":
            counter_phrase = [(max(1.5, beat - 0.25), max(0.25, length), clamp(pitch, 48, 88)) for beat, length, pitch in counter_phrase]
            if role in ("repeat", "develop") and not counter_phrase:
                counter_phrase = [(2.0, 0.3, clamp(identity["counter"], 48, 88)), (3.0, 0.28, clamp(identity["counter"] + 5, 48, 88))]
        elif counter_grammar == "lift_shadow":
            if role in ("lift", "transition"):
                counter_phrase = [(beat, max(0.2, length * 0.8), clamp(pitch - 12, 48, 84)) for beat, length, pitch in counter_phrase]
            else:
                counter_phrase = []
        elif counter_grammar == "transition_spark":
            counter_phrase = counter_phrase if role in ("lift", "transition") else []
            if role == "transition":
                counter_phrase = counter_phrase + [(3.25, 0.16, clamp(identity["counter"] + 12, 48, 90))]
        if counter_contour == "flat_reply":
            counter_phrase = [(beat, length, clamp(identity["counter"], 48, 84)) for beat, length, _pitch in counter_phrase]
        elif counter_contour == "rising_reply":
            counter_phrase = [(beat, length, clamp(pitch + (idx * 2), 48, 90)) for idx, (beat, length, pitch) in enumerate(counter_phrase)]
        elif counter_contour == "echo_fall":
            counter_phrase = [(beat, max(0.14, length * 0.85), clamp(pitch - (idx * 2), 48, 88)) for idx, (beat, length, pitch) in enumerate(counter_phrase)]
        elif counter_contour == "spark_jump":
            counter_phrase = [(beat, length, clamp(pitch + (12 if idx == len(counter_phrase) - 1 else 0), 48, 92)) for idx, (beat, length, pitch) in enumerate(counter_phrase)]
        if counter_span == "short":
            counter_phrase = counter_phrase[:max(1, min(2, len(counter_phrase)))]
        elif counter_span == "medium":
            counter_phrase = counter_phrase[:max(2, min(3, len(counter_phrase)))]
        elif counter_span == "long":
            if counter_phrase:
                counter_phrase = counter_phrase + [(counter_phrase[-1][0] + 0.375, max(0.16, counter_phrase[-1][1] * 0.8), counter_phrase[-1][2])]
        elif counter_span == "extended":
            if counter_phrase:
                counter_phrase = counter_phrase + [
                    (counter_phrase[-1][0] + 0.25, max(0.16, counter_phrase[-1][1] * 0.8), counter_phrase[-1][2]),
                    (min(3.75, counter_phrase[-1][0] + 0.625), 0.14, clamp(counter_phrase[-1][2] + 5, 48, 92)),
                ]
        if counter_register == "low_lane":
            counter_phrase = [(beat, length, clamp(pitch - 12, 48, 78)) for beat, length, pitch in counter_phrase]
        elif counter_register == "mid_lane":
            counter_phrase = [(beat, length, clamp(pitch, 55, 86)) for beat, length, pitch in counter_phrase]
        elif counter_register == "high_lane":
            counter_phrase = [(beat, length, clamp(pitch + 12, 67, 96)) for beat, length, pitch in counter_phrase]
        elif counter_register == "wide_lane":
            counter_phrase = [(beat, length, clamp(pitch + (12 if idx % 2 else 0), 52, 96)) for idx, (beat, length, pitch) in enumerate(counter_phrase)]
        engine_phrase = countermelody_answer_from_lead(
            phrase,
            identity,
            chord,
            lead_stage,
            counter_role,
            counter_register,
            progression_family,
        )
        mode_phrase = build_counter_answer(phrase, chord, counter_answer_mode)
        if counter_engine == "answer_arc":
            counter_phrase = engine_phrase or counter_phrase
        elif counter_engine == "shadow_hook":
            counter_phrase = (engine_phrase[:2] + counter_phrase[:1]) if engine_phrase else counter_phrase[:2]
            counter_phrase = [entry for entry in counter_phrase if entry[0] >= 2.0]
        elif counter_engine == "octave_lift":
            counter_phrase = engine_phrase or counter_phrase
            if counter_phrase:
                tail = counter_phrase[-1]
                counter_phrase = counter_phrase + [(min(3.75, tail[0] + 0.25), max(0.16, tail[1] * 0.8), clamp(tail[2] + 12, 48, 96))]
        elif counter_engine == "late_bloom":
            engine_phrase = [entry for entry in engine_phrase if entry[0] >= 2.0]
            counter_phrase = engine_phrase if role in ("lift", "transition") else counter_phrase[:1]
        if is_second_pass:
            counter_phrase = counter_phrase + mode_phrase
        if counter_presence == "whisper":
            counter_phrase = counter_phrase[:max(1, len(counter_phrase) // 2)]
        elif counter_presence == "clear":
            counter_phrase = counter_phrase + [(beat + 0.125, max(0.12, length * 0.75), clamp(pitch, 48, 90)) for beat, length, pitch in counter_phrase[:1]]
        elif counter_presence == "featured":
            counter_phrase = counter_phrase + [(beat + 0.125, max(0.14, length * 0.8), clamp(pitch + 12, 48, 92)) for beat, length, pitch in counter_phrase[:2]]
        elif counter_presence == "late_focus":
            counter_phrase = [entry for entry in counter_phrase if entry[0] >= 2.0] or counter_phrase[-1:]
        if is_second_pass:
            emotional_answer = []
            lead_answer_source = engine_phrase or counter_phrase[:2]
            for idx, (beat, length, pitch) in enumerate(lead_answer_source[:3]):
                emotional_answer.append((min(3.5, max(1.25, beat + 0.25)), max(0.45, length), clamp(pitch + (5 if idx == len(lead_answer_source[:3]) - 1 else 0), 55, 92)))
            if role in ("repeat", "develop", "lift", "transition"):
                counter_phrase = counter_phrase + emotional_answer
            if drop_role in ("release", "wider", "upgrade"):
                counter_phrase = counter_phrase + [
                    (1.5, 0.75, clamp(identity["counter"] + 12, 60, 94)),
                    (3.0, 0.75, clamp(identity["counter"] + 17, 64, 96)),
                ]
        if progression_family == "lifted":
            counter_phrase = [(beat + 0.25, length, clamp(pitch + 5, 48, 88)) for beat, length, pitch in counter_phrase]
        elif progression_family == "festival_cycle":
            counter_phrase = [(max(0.0, beat - 0.25), length, clamp(pitch, 48, 88)) for beat, length, pitch in counter_phrase]
            if role in ("develop", "lift"):
                counter_phrase = counter_phrase + [(3.0, 0.22, clamp(identity["counter"] + 7, 48, 88))]
        elif progression_family == "hopeful_pull":
            counter_phrase = [(beat + 0.5, min(0.28, length), clamp(pitch - 5, 48, 88)) for beat, length, pitch in counter_phrase if beat >= 2.0]
        elif progression_family == "classic_warmth":
            counter_phrase = [(beat, max(0.32, length), clamp(pitch, 48, 88)) for beat, length, pitch in counter_phrase]
        if recall_style in ("interval_memory", "emotive_fragment"):
            counter_phrase = counter_phrase + [(beat, length, clamp(pitch - 12, 48, 84)) for beat, length, pitch in theme_counter[:2]]
        if drop_role == "tease":
            counter_phrase = [entry for entry in counter_phrase if entry[0] >= 2.5] or counter_phrase[-1:]
        elif drop_role == "upgrade":
            counter_phrase = counter_phrase + [(3.25, 0.18, clamp(identity["counter"] + 12, 48, 92))]
        elif drop_role == "release":
            counter_phrase = counter_phrase + [(beat + 0.125, max(0.18, length), clamp(pitch + 12, 48, 92)) for beat, length, pitch in counter_phrase[:2]]
        elif drop_role == "emotional":
            counter_phrase = [(beat, max(0.24, length), clamp(pitch + 5, 48, 90)) for beat, length, pitch in counter_phrase if beat >= 1.5]
        if focus["support_duck"] and role in ("lift", "transition"):
            counter_phrase = [entry for entry in counter_phrase if entry[0] >= 2.0]
        if not relation["counter_ok"] or ownership["counter"] == "none":
            counter_phrase = counter_phrase[:1] if role == "transition" else []
        elif ownership["counter"] == "transition_only":
            counter_phrase = counter_phrase if role == "transition" else []
        elif ownership["counter"] == "late":
            counter_phrase = [entry for entry in counter_phrase if entry[0] >= 2.0]
        if support_profile["primary"] == "lead":
            counter_phrase = [entry for entry in counter_phrase if entry[0] >= 2.0]
        elif support_profile["primary"] == "vocal":
            counter_phrase = []
        elif support_profile["primary"] == "response":
            counter_phrase = [entry for entry in counter_phrase if entry[0] >= 2.5]
        if second_drop_stage == "entry":
            counter_phrase = []
        elif second_drop_stage == "settle":
            counter_phrase = [entry for entry in counter_phrase if entry[0] >= (2.0 if is_second_pass else 2.5)]
        if kind == "drop" and is_second_pass:
            # Drop 2 countermelody must clearly answer the lead with longer, audible notes.
            counter_phrase = [(beat, max(0.75, length), pitch) for beat, length, pitch in counter_phrase]
            if len(counter_phrase) < 2:
                counter_phrase = (counter_phrase + [
                    (1.5, 0.9, clamp(identity["counter"] + 5, 52, 92)),
                    (3.0, 1.0, clamp(identity["counter"] + 12, 55, 94)),
                ])[:2]
        if local_bar >= max(0, section_bars - 8) and counter_grammar != "lift_shadow":
            counter_phrase = counter_phrase + [(3.75, 0.12, identity["counter"] + 12)]
        if is_second_pass and role in ("lift", "transition"):
            counter_phrase = counter_phrase + [(beat + 0.125, max(0.1, length * 0.7), clamp(pitch, 48, 88)) for beat, length, pitch in theme_counter[:2]]
        counter_velocity = clamp(int((42 + intensity * 36) * recall_amount * support_state_factor(
            "response" if support_profile["primary"] == "response" else
            "shadow" if support_profile["primary"] == "lead" else
            "silent" if support_profile["primary"] == "vocal" else
            "support"
        )), 0, 104)
        if counter_presence == "whisper":
            counter_velocity = clamp(counter_velocity - 12, 0, 96)
        elif counter_presence == "clear":
            counter_velocity = clamp(counter_velocity + 6, 0, 110)
        elif counter_presence == "featured":
            counter_velocity = clamp(counter_velocity + 14, 0, 116)
        elif counter_presence == "late_focus" and role in ("lift", "transition"):
            counter_velocity = clamp(counter_velocity + 10, 0, 112)
        if counter_role == "featured_answer":
            counter_velocity = clamp(counter_velocity + 8, 0, 118)
        elif counter_role == "support":
            counter_velocity = clamp(counter_velocity - 4, 0, 108)
        if is_second_pass and drop_role in ("release", "wider", "upgrade"):
            counter_velocity = clamp(counter_velocity + 14, 0, 118)
        if kind == "drop" and is_second_pass:
            counter_velocity = clamp(counter_velocity + 10, 0, 118)
        if counter_spread == "tight":
            counter_phrase = counter_phrase[:max(1, len(counter_phrase) - 1)]
        elif counter_spread == "open" and counter_phrase:
            counter_phrase = counter_phrase + [(min(3.75, counter_phrase[-1][0] + 0.25), max(0.14, counter_phrase[-1][1] * 0.8), counter_phrase[-1][2])]
        if kind == "verse" and not counter_entry_open:
            counter_phrase = []
        if counter_velocity > 0:
            if kind == "drop":
                counter_velocity = clamp(int(counter_velocity * finish_factor * counter_variant), 0, 112)
            for beat_pos, beat_len, pitch in counter_phrase:
                add_event(tracks["countermelody"], start_tick + tick(beat_pos), pitch, tick(beat_len), velocity=max(36, counter_velocity))

    if kind in ("verse", "build", "breakdown"):
        vocal_velocity = clamp(int((62 + intensity * 26) * focus["vocal"] * relation["vocal_gain"]), 44, 112)
        if vocal_archetype == "straight_hook":
            vocal_phrase = [(0.0, 0.8, identity["vocal_anchor"]), (1.0, 0.6, support), (2.5, 0.9, resolve)]
        elif vocal_archetype == "call_response":
            vocal_phrase = [(0.0, 0.55, identity["vocal_anchor"]), (1.5, 0.45, support), (2.75, 0.7, identity["vocal_anchor"])]
        elif vocal_archetype == "held_emotive":
            vocal_phrase = [(0.0, 1.15, identity["vocal_anchor"]), (2.25, 1.0, resolve)]
        else:
            vocal_phrase = [(0.0, 0.55, support), (1.0, 0.55, identity["vocal_anchor"]), (2.0, 0.55, lift - 12), (3.0, 0.75, resolve)]
        if breakdown_narrative == "vocal_spotlight" and kind == "breakdown":
            vocal_phrase = [(0.0, 1.1, identity["vocal_anchor"]), (2.25, 1.2, lift - 12)]
        elif breakdown_narrative == "space_then_lift" and kind == "breakdown" and role in ("establish", "repeat"):
            vocal_phrase = [(2.0, 1.15, identity["vocal_anchor"])]
        elif role == "transition":
            vocal_phrase = [(0.0, 0.7, identity["vocal_anchor"]), (1.5, 0.55, support), (3.0, 0.6, resolve)]
        if recall_style in ("rhythmic_shadow", "emotive_fragment"):
            theme_vocal = theme_phrase_events(identity, blueprint, chord, role, register_shift=-12, rhythm_scale=1.0 if recall_style == "emotive_fragment" else 0.75)
            if kind == "breakdown":
                vocal_phrase = theme_vocal[:2] if blueprint["callback_density"] != "subtle" else theme_vocal[:1]
            elif kind == "build" and role in ("lift", "transition"):
                vocal_phrase = theme_vocal[:2] + vocal_phrase[-1:]
        if relation["shared_hook"] and kind in ("build", "breakdown"):
            shared_vocal = theme_phrase_events(identity, blueprint, chord, role, register_shift=-12, rhythm_scale=0.82)
            vocal_phrase = shared_vocal[:2] if kind == "breakdown" else shared_vocal[:1] + vocal_phrase[-1:]
        elif relation["vocal_answers"] and kind == "verse":
            response = theme_phrase_events(identity, blueprint, chord, role, register_shift=-12, rhythm_scale=0.65)
            vocal_phrase = [(2.0 + beat_pos * 0.35, min(0.7, beat_len), clamp(pitch, 58, 90)) for beat_pos, beat_len, pitch in response[:2]]
        if topline_density == "lead_heavy":
            vocal_phrase = vocal_phrase[:max(1, len(vocal_phrase) // 2)]
        elif topline_density == "vocal_heavy":
            vocal_velocity = clamp(vocal_velocity + 8, 44, 112)
        elif topline_density == "alternating" and local_bar % 2 == 1:
            vocal_phrase = []
        if transition["pre_drop_void"] and kind == "build" and role == "transition":
            vocal_phrase = [entry for entry in vocal_phrase if entry[0] < 3.0]
        if ownership["vocal"] == "early":
            vocal_phrase = [entry for entry in vocal_phrase if entry[0] < 2.0]
        elif ownership["vocal"] == "late":
            vocal_phrase = [entry for entry in vocal_phrase if entry[0] >= 1.5]
        elif ownership["vocal"] == "echo":
            vocal_phrase = [(2.0 + beat * 0.3, min(0.45, length), clamp(pitch, 58, 90)) for beat, length, pitch in vocal_phrase[:2]]
        elif ownership["vocal"] == "none":
            vocal_phrase = []
        vocal_active = ownership["vocal"] != "none" and not (kind == "drop")
        if kind == "verse" and not vocal_entry_open:
            vocal_active = False
        if vocal_active:
            for beat_pos, beat_len, pitch in vocal_phrase:
                add_event(tracks["vocal_melody"], start_tick + tick(beat_pos), clamp(pitch, 58, 90), tick(beat_len), velocity=vocal_velocity)

    if kind == "drop" and (relation["vocal_answers"] or ownership["vocal"] in ("late", "echo")):
        drop_vocal = theme_phrase_events(identity, blueprint, chord, role, register_shift=-12, rhythm_scale=0.55 if is_second_pass else 0.45)
        if role in ("lift", "transition") or is_second_pass or ownership["vocal"] == "late":
            drop_take = drop_vocal[:2] if ownership["vocal"] != "echo" else drop_vocal[:1]
            if drop_role == "emotional":
                drop_take = drop_vocal[:3]
            elif drop_role == "tease":
                drop_take = drop_vocal[:1]
            if is_second_pass and drop_role in ("release", "upgrade", "wider"):
                drop_take = drop_take[:2]
            if second_drop_stage == "entry":
                drop_take = []
            elif second_drop_stage == "settle":
                drop_take = drop_take[:1]
            for beat_pos, beat_len, pitch in drop_take:
                start_offset = 2.0 if ownership["vocal"] != "echo" else 2.5
                if drop_role == "emotional":
                    start_offset = 1.5
                elif drop_role == "tease":
                    start_offset = 2.5
                if second_drop_stage == "settle":
                    start_offset = max(start_offset, 2.75)
                add_event(tracks["vocal_melody"], start_tick + tick(start_offset + beat_pos * 0.35), clamp(pitch, 60, 90), tick(min(0.6 if drop_role == "emotional" else 0.45, beat_len)), velocity=clamp(int(((58 + intensity * 18) * relation["vocal_gain"]) * finish_factor) + (6 if drop_role == "emotional" else -4 if drop_role == "tease" else 0), 40, 100))


def render_song(bpm: int, key: str, progression: str, arrangement: str, variation: str, density: str, energy_bias: str, track_identity: str = TRACK_IDENTITY_MODE):
    rng = random.Random(time_ns())
    genre = progression
    identity_profile = select_track_identity(genre, rng, track_identity)
    identity_profile["identity_variation_type"] = select_identity_variation(identity_profile["profile_key"], rng, track_identity)
    blueprint = build_song_blueprint(rng, genre, variation, density, energy_bias, identity_profile=identity_profile)
    identity = build_identity_blueprint(key, rng, variation, blueprint)
    blueprint["selected_key"] = key
    blueprint["progression_name"] = genre
    blueprint["genre"] = genre
    identity["progression_name"] = genre
    identity["progression_family"] = blueprint.get("progression_family", "")
    chords = progression_chords(key, genre)
    sections = arrange_sections(arrangement, blueprint)
    blueprint["v11_story"] = create_track_story(blueprint, blueprint.get("variation_type", "DEFAULT"), genre, key)
    blueprint["v11_core_motif"] = create_core_motif(key, genre, blueprint, blueprint["v11_story"]["story_type"])
    tracks = {stem: [] for stem in STEMS}
    markers = []

    for sec_index, section in enumerate(sections):
        markers.append((bar_tick(section["start_bar"]), section_marker_text(section["name"], blueprint)))
        kind = section_kind(section["name"])
        is_second_pass = "2" in section["name"]
        section_progress = sec_index / max(1, len(sections) - 1)
        for local_bar in range(section["bars"]):
            global_bar = section["start_bar"] + local_bar
            start = bar_tick(global_bar)
            chord = chords[global_bar % len(chords)]
            intensity = section_intensity(kind, is_second_pass, blueprint, section_progress) * LEVEL_FACTOR[density]
            add_harmony(tracks, start, chord, kind, local_bar, section["bars"], intensity, blueprint, identity, is_second_pass)
            add_arp(tracks, start, chord, kind, local_bar, section["bars"], intensity, blueprint, identity, is_second_pass)
            add_bass(tracks, start, chord, kind, local_bar, section["bars"], intensity, blueprint, is_second_pass)
            add_sub_bass(tracks, start, chord, kind, local_bar, section["bars"], intensity, blueprint, is_second_pass)
            add_drums(tracks, start, kind, local_bar, section["bars"], intensity, blueprint, is_second_pass)
            add_lead_family(tracks, start, chord, kind, local_bar, section["bars"], intensity, identity, blueprint, is_second_pass, chords=chords)

    apply_snare_build_engine(tracks, sections, blueprint)
    tracks, blueprint = validate_song(tracks, blueprint, sections, chords, identity)
    tracks, blueprint = apply_track_identity_postprocess(tracks, sections, chords, blueprint)
    tracks, blueprint = apply_v11_motif_story_engine(tracks, sections, chords, blueprint, identity)
    return tracks, blueprint, sections, markers


STEM_ADVISOR_PROFILES = {
    "kick": {
        "role": "drop anchor and sidechain trigger",
        "mix_note": "Keep the transient clear, short, and mono; this stem defines the sidechain feel.",
        "primary_owned": {
            "plugin": "Ableton Drum Rack",
            "category": "Kick / 909 / Dance Kick",
            "internal_search_terms": ["kick", "909", "punch", "trance", "dance"],
            "internet_search_terms": ["uplifting trance kick sample", "ASOT trance kick sample", "punchy 909 trance kick"],
            "build_from_scratch": ["Load a tight 909-style kick", "Tune the fundamental to the key if needed", "Layer a short click only if the transient is soft", "Keep decay short enough to leave bass space"],
            "fx_chain": ["EQ low cut below 25 Hz", "small 55-90 Hz weight boost if needed", "clip or saturate lightly", "route as sidechain trigger"],
            "avoid": ["long boomy tails", "wide stereo lows", "large reverb", "muddy 120-250 Hz buildup"],
        },
        "alternative_owned": {
            "plugin": "Battery 4",
            "category": "Electronic Kick / Dance Kit",
            "internal_search_terms": ["kick", "club", "dance", "909", "hard"],
            "internet_search_terms": ["Battery 4 trance kick kit", "Battery 4 dance kick preset", "Battery 4 909 kick"],
            "build_from_scratch": ["Pick a clean electronic kick cell", "Shorten envelope release", "Tune body layer", "Balance click and body cells"],
            "fx_chain": ["Solid EQ cleanup", "Transient Master for attack", "light saturation", "mono utility"],
            "avoid": ["acoustic room kicks", "distorted hardcore kicks", "wide sub layers", "overcompressed tails"],
        },
        "industry_standard": {
            "plugin": "Sonic Academy KICK 2",
            "category": "Trance / Club Kick Synth",
            "internal_search_terms": ["trance", "club", "punch", "909"],
            "internet_search_terms": ["KICK 2 uplifting trance kick preset", "KICK 2 ASOT kick", "KICK 2 trance kick tutorial"],
            "build_from_scratch": ["Synthesize a sine body around the root", "Add a short click transient", "Shape pitch envelope fast", "Export or freeze as audio before mixing"],
            "fx_chain": ["minimal EQ", "soft clip ceiling", "sidechain send", "mono below 150 Hz"],
            "avoid": ["too much sub sustain", "hardstyle pitch tails", "overly bright click", "phasey layered lows"],
        },
    },
    "offbeat_bass": {
        "role": "classic trance offbeat push",
        "mix_note": "Treat this as mid-bass movement; let 04_sub_bass carry the lowest octave.",
        "primary_owned": {
            "plugin": "Massive X",
            "category": "Bass / Synth Bass / Trance Bass",
            "internal_search_terms": ["bass", "trance", "offbeat", "saw", "pluck"],
            "internet_search_terms": ["Massive X trance offbeat bass preset", "Massive X uplifting trance bass", "Massive X saw bass preset"],
            "build_from_scratch": ["Use a saw or square-saw wavetable", "Short amp decay with medium sustain", "Low-pass until it sits below supersaw", "Add unison lightly, not wide in the low end"],
            "fx_chain": ["HPF below sub lane", "LPF around upper mids", "sidechain from kick", "mono below 120 Hz"],
            "avoid": ["sub-heavy stereo patches", "long releases", "acid resonance", "distorted dubstep bass timbres"],
        },
        "alternative_owned": {
            "plugin": "Vital",
            "category": "Bass / Saw Bass",
            "internal_search_terms": ["bass", "saw", "trance", "offbeat", "pluck"],
            "internet_search_terms": ["Vital trance bass preset", "Vital offbeat bass preset", "Vital uplifting trance bass"],
            "build_from_scratch": ["Osc 1 saw with 2-4 voices", "Filter low-pass with envelope pluck", "Short release", "Add light drive before filter"],
            "fx_chain": ["EQ mud cut 180-300 Hz", "compressor sidechain", "sub control utility", "small saturation"],
            "avoid": ["wide bass below 150 Hz", "growl wavetables", "too much chorus", "over-bright filter opening"],
        },
        "industry_standard": {
            "plugin": "Xfer Serum",
            "category": "Bass / Trance Bass",
            "internal_search_terms": ["trance bass", "offbeat", "saw bass", "club bass"],
            "internet_search_terms": ["Serum uplifting trance bass preset", "Serum offbeat bass preset", "Serum trance bass tutorial"],
            "build_from_scratch": ["Saw oscillator with light unison", "MG Low 12 filter", "envelope to cutoff", "noise click only if needed"],
            "fx_chain": ["EQ low cleanup", "OTT very lightly if needed", "sidechain compression", "mono utility"],
            "avoid": ["OTT overkill", "FM growl movement", "wide unison lows", "busy rhythmic gating"],
        },
    },
    "rolling_bass": {
        "role": "forward rhythmic drive",
        "mix_note": "Keep it locked to the groove and below the hook; it should add urgency without stealing the lead lane.",
        "primary_owned": {
            "plugin": "Massive X",
            "category": "Bass / Sequence Bass / Rolling Bass",
            "internal_search_terms": ["rolling", "sequence", "bass", "trance", "drive"],
            "internet_search_terms": ["Massive X rolling trance bass preset", "Massive X progressive trance bass", "Massive X sequence bass"],
            "build_from_scratch": ["Use saw or pulse source", "Fast attack and short release", "Filter envelope for per-note bite", "Add mild phase or wavetable motion only above low mids"],
            "fx_chain": ["tight amp envelope", "mid saturation", "sidechain from kick", "cut 180-350 Hz mud"],
            "avoid": ["long overlapping releases", "excess resonance", "wide low frequencies", "melodic movement that fights lead"],
        },
        "alternative_owned": {
            "plugin": "Ableton Operator",
            "category": "Bass / FM Bass",
            "internal_search_terms": ["bass", "fm bass", "sequence", "pluck"],
            "internet_search_terms": ["Ableton Operator trance bass", "Operator rolling bass preset", "Ableton rolling bass tutorial"],
            "build_from_scratch": ["Use sine plus light FM harmonic", "Short decay envelope", "Add click with pitch or filter envelope", "Keep patch mono"],
            "fx_chain": ["Saturator for harmonics", "EQ low-mid cleanup", "Compressor sidechain", "Utility mono"],
            "avoid": ["metallic FM clang", "wide chorus", "sub conflict", "slow envelopes"],
        },
        "industry_standard": {
            "plugin": "Reveal Sound Spire",
            "category": "Bass / Trance Bass / Sequence",
            "internal_search_terms": ["bass", "seq", "trance", "rolling"],
            "internet_search_terms": ["Spire rolling trance bass preset", "Spire uplifting bass preset", "Spire trance bass sequence"],
            "build_from_scratch": ["VA saw oscillator", "mono mode", "short envelope", "filter drive for bite"],
            "fx_chain": ["EQ", "sidechain compressor", "light distortion", "mono low utility"],
            "avoid": ["supersaw-like width", "bright lead tone", "long reverb", "too many octave jumps"],
        },
    },
    "sub_bass": {
        "role": "low-end foundation",
        "mix_note": "Let this own the sub lane while the offbeat and rolling bass provide movement.",
        "primary_owned": {
            "plugin": "Ableton Operator",
            "category": "Sub Bass / Sine Bass",
            "internal_search_terms": ["sine", "sub", "bass", "clean"],
            "internet_search_terms": ["Ableton Operator clean sub bass", "Operator sine sub bass", "trance sub bass Ableton"],
            "build_from_scratch": ["Single sine oscillator", "mono legato off unless needed", "short fade attack to avoid clicks", "release short enough for kick sidechain"],
            "fx_chain": ["LPF below 100 Hz", "Utility mono", "sidechain from kick", "spectrum check for fundamental"],
            "avoid": ["reverb", "chorus", "stereo widening", "distortion that clouds the kick"],
        },
        "alternative_owned": {
            "plugin": "Vital",
            "category": "Bass / Sub / Basic Shapes",
            "internal_search_terms": ["sub", "sine", "clean bass", "mono"],
            "internet_search_terms": ["Vital clean sub bass preset", "Vital sine sub bass", "Vital mono sub bass"],
            "build_from_scratch": ["Basic sine oscillator", "disable unison", "low-pass any added harmonic", "keep velocity response modest"],
            "fx_chain": ["EQ LPF", "Utility mono", "sidechain compressor", "gentle saturation only if inaudible"],
            "avoid": ["detune", "wide stereo", "wavetable movement", "clicky transient overlap with kick"],
        },
        "industry_standard": {
            "plugin": "Xfer Serum",
            "category": "Bass / Sub",
            "internal_search_terms": ["sub", "sine", "clean", "mono"],
            "internet_search_terms": ["Serum clean sub bass preset", "Serum sine sub bass", "Serum trance sub bass"],
            "build_from_scratch": ["Use sub oscillator sine", "disable main oscillators if not needed", "mono mode", "short release"],
            "fx_chain": ["no Serum FX unless saturation is tiny", "EQ LPF", "sidechain", "mono utility"],
            "avoid": ["unison", "noise layer", "reverb", "phasey stereo bass"],
        },
    },
    "clap_snare": {
        "role": "backbeat and build tension",
        "mix_note": "Last build bars can be brighter and louder, but keep the drop transient clean.",
        "primary_owned": {
            "plugin": "Ableton Drum Rack",
            "category": "Clap / Snare / Build Roll",
            "internal_search_terms": ["clap", "snare", "roll", "909", "build"],
            "internet_search_terms": ["uplifting trance clap sample", "trance snare roll sample", "Ableton snare build roll"],
            "build_from_scratch": ["Layer one clap with one short snare", "Shorten decay for backbeat", "Use velocity ramp for rolls", "Add a brighter layer in final build bars"],
            "fx_chain": ["HPF below 120 Hz", "short plate reverb send", "transient shaping", "automation for build roll velocity"],
            "avoid": ["huge room wash on every hit", "low-mid boxiness", "flat roll velocity", "snare louder than lead on drop"],
        },
        "alternative_owned": {
            "plugin": "Battery 4",
            "category": "Electronic Snare / Clap Kit",
            "internal_search_terms": ["clap", "snare", "roll", "electronic", "dance"],
            "internet_search_terms": ["Battery 4 trance clap kit", "Battery 4 snare roll", "Battery 4 dance clap"],
            "build_from_scratch": ["Choose tight clap and snare cells", "Map roll velocity layers", "Tune snare slightly up for build tension", "Keep backbeat dry enough for punch"],
            "fx_chain": ["Solid EQ", "Transient Master", "plate reverb send", "limiter only on group if needed"],
            "avoid": ["acoustic rock snares", "long gated reverb", "harsh 4-7 kHz spikes", "overwide mono-incompatible claps"],
        },
        "industry_standard": {
            "plugin": "Vengeance Essential Clubsounds",
            "category": "Trance Clap and Snare Samples",
            "internal_search_terms": ["trance clap", "build snare", "uplifting roll"],
            "internet_search_terms": ["Vengeance trance clap sample", "Freshly Squeezed trance snare roll", "uplifting trance snare fill sample"],
            "build_from_scratch": ["Pick high-quality one-shots", "Program roll density from sparse to fast", "Automate velocity and filter lift", "Layer clap only in last two bars if needed"],
            "fx_chain": ["EQ", "short reverb", "bus compression lightly", "automation on build send"],
            "avoid": ["constant 1/16 rolls too early", "noise riser masking snare", "overcompressed clap bus", "low-end clutter"],
        },
    },
    "hats": {
        "role": "top-end motion",
        "mix_note": "Use width carefully; hats should energize without masking the lead.",
        "primary_owned": {
            "plugin": "Ableton Drum Rack",
            "category": "Closed Hat / Open Hat / Shaker",
            "internal_search_terms": ["hat", "open hat", "closed hat", "shaker", "909"],
            "internet_search_terms": ["uplifting trance hi hat sample", "trance open hat sample", "909 open hat trance"],
            "build_from_scratch": ["Use closed hat for pulse", "Add open hat on offbeats", "Humanize velocity slightly", "Keep decay controlled"],
            "fx_chain": ["HPF below 300 Hz", "tiny room send", "de-ess 8-12 kHz if sharp", "light bus compression"],
            "avoid": ["harsh white-noise hats", "wide phasey hats", "too much swing", "masking vocal or lead air"],
        },
        "alternative_owned": {
            "plugin": "Battery 4",
            "category": "Electronic Hats / Cymbals",
            "internal_search_terms": ["hat", "open", "closed", "shaker", "ride"],
            "internet_search_terms": ["Battery 4 trance hats", "Battery 4 electronic hi hats", "Battery 4 909 hats"],
            "build_from_scratch": ["Select bright but smooth hat cells", "Shorten closed hat decay", "Velocity-layer open hats", "Use shaker only in busier sections"],
            "fx_chain": ["EQ HPF", "transient softening if too clicky", "small ambience send", "stereo utility above 2 kHz"],
            "avoid": ["crashy cymbals in breakdown", "low-frequency hat noise", "flat machine-gun velocity", "excessive reverb"],
        },
        "industry_standard": {
            "plugin": "Vengeance Essential Clubsounds",
            "category": "Trance Hat Loops and One-Shots",
            "internal_search_terms": ["trance hats", "open hat", "closed hat", "top loop"],
            "internet_search_terms": ["Vengeance trance hi hats", "Loopmasters uplifting trance hats", "trance top loop samples"],
            "build_from_scratch": ["Choose one-shots rather than busy loops", "Program offbeat open hat", "Add closed hat pulse gradually", "Layer shaker lightly in high-energy sections"],
            "fx_chain": ["HPF", "de-esser", "tiny room", "level automation by section"],
            "avoid": ["loop clutter", "overly bright rides", "stereo phase smear", "top end louder than supersaw"],
        },
    },
    "lead": {
        "role": "anthem hook and emotional centre",
        "mix_note": "Use a euphoric sustained saw lead: bright, wide, upfront, and not harsh.",
        "primary_owned": {
            "plugin": "Vital",
            "category": "Lead / Uplifting Trance Saw Lead / Anthem Lead",
            "internal_search_terms": ["lead", "saw", "anthem", "euphoric", "trance", "bright", "poly"],
            "internet_search_terms": ["Vital uplifting trance lead preset", "Vital euphoric saw lead preset", "Vital ASOT style lead preset"],
            "build_from_scratch": ["Osc 1 saw with 5-7 voices and medium detune", "Osc 2 saw with 3-5 voices at lower volume", "fairly open low-pass filter", "fast attack and medium release"],
            "fx_chain": ["HPF below 150 Hz", "Replika XT synced 1/8 or dotted 1/8 delay", "Raum or Neoverb 20-30 percent send", "subtle Choral or Phasis width", "light sidechain compression"],
            "avoid": ["dark aggressive bass-led presets", "too much distortion", "shrill 5-8 kHz peaks", "reverb so wet the hook loses front edge"],
        },
        "alternative_owned": {
            "plugin": "Massive X",
            "category": "Lead / Mono Lead / Poly Lead / Trance Lead / Euphoric Lead",
            "internal_search_terms": ["lead", "saw", "anthem", "euphoric", "trance", "bright", "poly"],
            "internet_search_terms": ["Massive X uplifting trance lead preset", "Massive X euphoric saw lead", "Massive X anthem lead preset"],
            "build_from_scratch": ["Use wavetable or virtual-analogue saw source", "enable unison and spread", "bright but controlled low-pass filtering", "fast attack with medium decay/release", "macro opens filter slightly on sustained notes"],
            "fx_chain": ["Solid EQ or Neutron EQ HPF below 150 Hz", "Replika XT 1/8 ping-pong", "Raum or Neoverb send", "Choral or Phasis subtly", "Neutron Compressor light sidechain"],
            "avoid": ["industrial expansions", "distorted bass macros", "overwide mono-incompatible patches", "long amp release that blurs motif gaps"],
        },
        "industry_standard": {
            "plugin": "Reveal Sound Spire",
            "category": "Lead / Trance Lead / Saw Lead",
            "internal_search_terms": ["uplifting lead", "saw lead", "trance lead", "anthem"],
            "internet_search_terms": ["Spire uplifting trance lead preset", "Spire ASOT trance lead preset", "Spire euphoric saw lead"],
            "build_from_scratch": ["Stack saw oscillators with unison", "use bright but not harsh filter position", "center a mono-compatible core", "add delay/reverb-heavy but upfront FX"],
            "fx_chain": ["HPF below 150 Hz", "tempo delay", "large hall send", "sidechain compressor", "gentle exciter"],
            "avoid": ["overly nasal resonance", "supersaw pad presets", "pitch modulation wobble", "lead masking the vocal guide completely"],
        },
    },
    "supersaw_chords": {
        "role": "drop width and emotional chord mass",
        "mix_note": "Drop 2 should feel wider and more sustained than Drop 1 without overpowering the hook melody.",
        "primary_owned": {
            "plugin": "Vital",
            "category": "Pad / Supersaw / Trance Chords",
            "internal_search_terms": ["supersaw", "saw pad", "trance chord", "euphoric", "wide"],
            "internet_search_terms": ["Vital uplifting trance supersaw preset", "Vital euphoric saw chords", "Vital trance chord stack"],
            "build_from_scratch": ["Osc 1 saw 7-9 voices", "Osc 2 saw one octave up at lower volume", "medium detune with controlled stereo", "slow attack only if not masking drop hit", "filter open enough for lift"],
            "fx_chain": ["HPF 120-180 Hz", "sidechain from kick", "tame 3-6 kHz harshness", "reverb send below breakdown pad level", "stereo width above low mids only"],
            "avoid": ["top-heavy octave stacks", "mud below 150 Hz", "too much reverb in drop", "clashing with 07_lead register"],
        },
        "alternative_owned": {
            "plugin": "Massive X",
            "category": "Pad / Poly Synth / Supersaw",
            "internal_search_terms": ["supersaw", "pad", "poly", "trance", "wide"],
            "internet_search_terms": ["Massive X supersaw trance preset", "Massive X euphoric pad", "Massive X trance chord preset"],
            "build_from_scratch": ["Use VA saw source", "enable unison with spread", "layer root and fifth emphasis", "map macro to filter brightness", "keep drop ceiling controlled"],
            "fx_chain": ["Neutron EQ HPF", "sidechain compression", "Raum short hall send", "light chorus if mono stays stable", "dynamic EQ harsh bands"],
            "avoid": ["dark cinematic pads", "slow attacks on first drop hit", "distorted bass presets", "wide low-end unison"],
        },
        "industry_standard": {
            "plugin": "LennarDigital Sylenth1",
            "category": "Trance Supersaw / Chord Stab / Pad",
            "internal_search_terms": ["supersaw", "trance", "chord", "pad", "uplifting"],
            "internet_search_terms": ["Sylenth1 uplifting trance supersaw preset", "Sylenth1 ASOT supersaw", "Sylenth1 euphoric chord preset"],
            "build_from_scratch": ["Use multiple saw oscillators with 6-8 voices", "detune moderately", "double root/third in upper octave", "filter bright but safe", "amp sustain high"],
            "fx_chain": ["HPF", "sidechain", "short hall send", "gentle stereo widen", "dynamic EQ upper mids"],
            "avoid": ["over-detuned seasick chords", "too many notes above MIDI 84", "reverb wash hiding rhythm", "thin high-only voicings"],
        },
    },
    "pad": {
        "role": "harmonic atmosphere",
        "mix_note": "Blend low enough that it supports the chord emotion without clouding the drop.",
        "primary_owned": {
            "plugin": "Massive X",
            "category": "Pad / Warm Pad / Atmospheric Pad",
            "internal_search_terms": ["pad", "warm", "atmosphere", "soft", "wide"],
            "internet_search_terms": ["Massive X warm trance pad preset", "Massive X atmospheric pad", "Massive X emotional pad"],
            "build_from_scratch": ["Soft saw or wavetable source", "slow attack", "long release", "low-pass for warmth", "minimal modulation"],
            "fx_chain": ["HPF 180-250 Hz", "long reverb", "duck under lead and supersaw", "cut low-mid mud", "gentle width"],
            "avoid": ["busy rhythmic gates", "bright supersaw lead tone", "sub content", "constant high resonance", "industrial or distorted bass-heavy Massive X presets"],
        },
        "alternative_owned": {
            "plugin": "Vital",
            "category": "Pad / Ambient / Soft Synth",
            "internal_search_terms": ["pad", "ambient", "warm", "soft", "trance"],
            "internet_search_terms": ["Vital warm trance pad", "Vital emotional pad preset", "Vital atmospheric pad"],
            "build_from_scratch": ["Two saw/triangle sources", "low unison detune", "slow filter envelope", "long amp release", "subtle noise texture"],
            "fx_chain": ["EQ HPF", "Raum or Neoverb hall", "sidechain lightly", "dynamic EQ low mids", "chorus subtle"],
            "avoid": ["sparkly lead presets", "too much stereo low end", "fast pluck envelopes", "melody-like movement"],
        },
        "industry_standard": {
            "plugin": "Spectrasonics Omnisphere",
            "category": "Pad / Warm Synth Pad / Airy Pad",
            "internal_search_terms": ["warm pad", "airy pad", "emotional pad", "synth pad"],
            "internet_search_terms": ["Omnisphere uplifting trance pad", "Omnisphere emotional pad preset", "Omnisphere warm synth pad"],
            "build_from_scratch": ["Choose warm synth waveform", "slow amp attack", "filter dark enough for background", "add gentle motion", "keep chord identity clear"],
            "fx_chain": ["HPF", "long hall", "sidechain", "EQ dip around lead body", "automation by section"],
            "avoid": ["cinematic hits", "choir dominating breakdown", "low drones conflicting with bass", "excess shimmer"],
        },
    },
    "arp": {
        "role": "groove sparkle and harmonic rhythm",
        "mix_note": "Keep it predictable and supportive, not a competing melody.",
        "primary_owned": {
            "plugin": "Vital",
            "category": "Arp / Pluck / Sequence",
            "internal_search_terms": ["arp", "pluck", "sequence", "trance", "bright"],
            "internet_search_terms": ["Vital trance arp preset", "Vital uplifting arp", "Vital pluck sequence preset"],
            "build_from_scratch": ["Saw or square source", "short decay", "low sustain", "filter pluck envelope", "no heavy pitch modulation"],
            "fx_chain": ["HPF 180 Hz", "short synced delay", "sidechain lightly", "thin during dense lead moments", "small reverb send"],
            "avoid": ["random note scatter", "long release tails", "lead-like brightness", "arp louder than hook"],
        },
        "alternative_owned": {
            "plugin": "Massive X",
            "category": "Arp / Sequence / Pluck",
            "internal_search_terms": ["arp", "sequence", "pluck", "trance", "digital"],
            "internet_search_terms": ["Massive X trance arp preset", "Massive X uplifting sequence", "Massive X pluck arp"],
            "build_from_scratch": ["Bright wavetable source", "fast attack", "short decay", "use performer/modulation only subtly", "filter cutoff below lead air"],
            "fx_chain": ["Solid EQ HPF", "Replika XT 1/8 delay", "light sidechain", "short room or plate", "velocity trim"],
            "avoid": ["complex generative sequences", "heavy distortion", "wide low notes", "busy 1/16 chatter in drops"],
        },
        "industry_standard": {
            "plugin": "Reveal Sound Spire",
            "category": "Arp / Trance Pluck / Sequence",
            "internal_search_terms": ["arp", "pluck", "seq", "trance"],
            "internet_search_terms": ["Spire trance arp preset", "Spire uplifting pluck arp", "Spire ASOT arp preset"],
            "build_from_scratch": ["Single or dual saw source", "short envelope", "filter pluck", "tempo delay", "keep harmonic targets simple"],
            "fx_chain": ["HPF", "delay", "sidechain", "small reverb", "EQ high harshness"],
            "avoid": ["acid lines", "main hook melodies", "too many octave jumps", "uncontrolled delay feedback"],
        },
    },
    "pluck": {
        "role": "light punctuation",
        "mix_note": "Use only where it adds space or anticipation; mute it when arp/lead density is high.",
        "primary_owned": {
            "plugin": "Massive X",
            "category": "Pluck / Trance Pluck / Short Synth",
            "internal_search_terms": ["pluck", "trance", "short", "bright", "mallet"],
            "internet_search_terms": ["Massive X trance pluck preset", "Massive X progressive pluck", "Massive X uplifting pluck"],
            "build_from_scratch": ["Saw or bell-like wavetable", "fast attack", "short decay", "low sustain", "filter envelope creates snap"],
            "fx_chain": ["HPF 200 Hz", "short delay send", "small plate", "duck under arp", "EQ click if harsh"],
            "avoid": ["independent melodies", "long sustain", "wide bass notes", "constant presence through drops"],
        },
        "alternative_owned": {
            "plugin": "Vital",
            "category": "Pluck / Bell / Soft Trance Pluck",
            "internal_search_terms": ["pluck", "bell", "trance", "soft", "short"],
            "internet_search_terms": ["Vital trance pluck preset", "Vital progressive pluck", "Vital soft pluck preset"],
            "build_from_scratch": ["Triangle/saw blend", "pluck filter envelope", "short release", "optional quiet noise click", "velocity-sensitive cutoff"],
            "fx_chain": ["EQ HPF", "Replika short delay", "Raum small send", "sidechain lightly", "transient trim"],
            "avoid": ["supersaw lead patches", "bright piercing bells", "reverb wash", "filling every gap"],
        },
        "industry_standard": {
            "plugin": "Xfer Serum",
            "category": "Pluck / Trance Pluck",
            "internal_search_terms": ["pluck", "trance", "progressive", "bell"],
            "internet_search_terms": ["Serum trance pluck preset", "Serum uplifting pluck", "Serum progressive trance pluck"],
            "build_from_scratch": ["Basic shapes saw/triangle", "filter envelope to cutoff", "short amp decay", "delay in FX", "small reverb"],
            "fx_chain": ["HPF", "delay", "short reverb", "sidechain", "EQ highs"],
            "avoid": ["FM harshness", "too much sustain", "deep bass layer", "busy counter-melody behavior"],
        },
    },
    "strings": {
        "role": "breakdown emotion and lift",
        "mix_note": "Keep movement smooth; strings should swell rather than chatter.",
        "primary_owned": {
            "plugin": "Kontakt Factory Library",
            "category": "Strings / Ensemble / Legato / Cinematic Pad",
            "internal_search_terms": ["strings", "ensemble", "sustain", "legato", "cinematic pad", "warm"],
            "internet_search_terms": ["Kontakt warm ensemble strings preset", "Kontakt trance breakdown strings", "Kontakt sustained strings"],
            "build_from_scratch": ["Load sustained ensemble or legato strings", "use as a pad/support layer rather than a melody", "voice simple triads", "automate expression upward in final bars", "keep voicing smooth every 2 bars"],
            "fx_chain": ["HPF 150 Hz", "long hall reverb", "gentle compression", "expression automation", "EQ dip if masking piano"],
            "avoid": ["spiccato or rhythmic strings", "fast per-bar movement", "harsh top-note jumps", "overlapping low cello mud"],
        },
        "alternative_owned": {
            "plugin": "Ableton Orchestral Strings",
            "category": "Sustained Strings / Ensemble",
            "internal_search_terms": ["strings", "sustain", "ensemble", "slow", "warm"],
            "internet_search_terms": ["Ableton orchestral strings trance breakdown", "Ableton sustained strings", "Ableton emotional string pad"],
            "build_from_scratch": ["Choose sustained ensemble", "increase attack slightly", "use mod wheel or velocity for swell", "raise top note only near phrase end", "keep chord changes simple"],
            "fx_chain": ["EQ HPF", "large hall", "sidechain very lightly only outside breakdown", "stereo width moderate", "volume automation"],
            "avoid": ["staccato articulations", "busy rhythmic patterns", "thin solo violin lead", "constant octave movement"],
        },
        "industry_standard": {
            "plugin": "Spitfire Audio LABS",
            "category": "Soft Strings / Long Strings",
            "internal_search_terms": ["soft strings", "long strings", "ensemble", "cinematic"],
            "internet_search_terms": ["Spitfire soft strings trance breakdown", "LABS strings emotional preset", "Albion long strings trance"],
            "build_from_scratch": ["Select soft long strings", "play sparse chord blocks", "automate dynamics", "widen final two bars", "avoid rhythmic ostinato"],
            "fx_chain": ["HPF", "hall reverb", "gentle EQ", "slow volume automation", "subtle saturation only if too thin"],
            "avoid": ["epic trailer brass-like intensity", "short bowing", "huge low drones", "pitchy solo articulations"],
        },
    },
    "piano": {
        "role": "breakdown motif and exposed emotion",
        "mix_note": "Let the long notes breathe; the piano should feel simple and memorable.",
        "primary_owned": {
            "plugin": "Kontakt Piano",
            "category": "Grand Piano / Felt Piano / Emotional Melody Piano",
            "internal_search_terms": ["piano", "grand", "felt", "soft", "emotional"],
            "internet_search_terms": ["Kontakt emotional piano preset", "Kontakt trance breakdown piano", "Kontakt soft grand piano"],
            "build_from_scratch": ["Use a warm grand or felt piano", "use as the exposed breakdown melody voice", "keep velocity moderate", "allow long note tails", "highlight the repeated motif"],
            "fx_chain": ["HPF 80-120 Hz", "gentle compression", "long reverb send", "delay only if motif remains clear", "soft high shelf if dull"],
            "avoid": ["fast arpeggiated piano", "bright honky tone", "too much pedal mud", "quantized robotic velocity"],
        },
        "alternative_owned": {
            "plugin": "Ableton Grand Piano",
            "category": "Piano / Grand Piano",
            "internal_search_terms": ["grand piano", "soft", "warm", "piano"],
            "internet_search_terms": ["Ableton grand piano emotional trance", "Ableton piano breakdown preset", "Ableton warm grand piano"],
            "build_from_scratch": ["Choose grand piano rack", "soften velocity curve", "add release ambience", "play one long note per bar in breakdown", "keep sustain controlled"],
            "fx_chain": ["EQ HPF", "Compressor lightly", "Hybrid Reverb or hall send", "Utility narrow low mids", "automation for anchor note"],
            "avoid": ["hard EDM piano stabs", "dense left-hand lows", "short 0.25 notes", "wash that hides motif rhythm"],
        },
        "industry_standard": {
            "plugin": "Native Instruments Noire",
            "category": "Felt / Cinematic / Emotional Piano",
            "internal_search_terms": ["felt", "emotional", "cinematic", "soft"],
            "internet_search_terms": ["Noire emotional piano trance breakdown", "Noire felt piano preset", "Noire uplifting trance piano"],
            "build_from_scratch": ["Use pure or felt tone", "reduce mechanical noise if distracting", "long release", "simple motif notes", "slight velocity arc into phrase end"],
            "fx_chain": ["HPF", "gentle compression", "hall reverb", "optional filtered delay", "EQ low-mid cleanup"],
            "avoid": ["cinematic noise too loud", "overly dark tone", "fast runs", "wide stereo lows"],
        },
    },
    "countermelody": {
        "role": "answer layer and Drop 2 width",
        "mix_note": "It should answer the lead, not fight for the same emotional lane.",
        "primary_owned": {
            "plugin": "Vital",
            "category": "Lead / Soft Trance Lead / Answer Lead",
            "internal_search_terms": ["lead", "soft", "answer", "trance", "saw"],
            "internet_search_terms": ["Vital soft trance lead preset", "Vital counter melody lead", "Vital euphoric answer lead"],
            "build_from_scratch": ["Use fewer saw voices than main lead", "slightly darker filter", "medium release", "lower volume", "place after lead attacks"],
            "fx_chain": ["HPF below 180 Hz", "less delay than main lead", "duck under lead attacks", "subtle pan or width", "small reverb send"],
            "avoid": ["same preset as main lead", "equal loudness with hook", "bright peak notes above lead", "busy rhythmic fills"],
        },
        "alternative_owned": {
            "plugin": "Massive X",
            "category": "Lead / Poly Lead / Soft Saw",
            "internal_search_terms": ["lead", "soft", "poly", "saw", "trance"],
            "internet_search_terms": ["Massive X soft trance lead", "Massive X counter melody lead", "Massive X euphoric poly lead"],
            "build_from_scratch": ["VA saw source", "light unison", "filter slightly closed", "medium release", "macro for subtle brightness"],
            "fx_chain": ["Solid EQ HPF", "shorter Replika delay", "Raum send lower than main lead", "sidechain from lead bus if needed", "dynamic EQ harshness"],
            "avoid": ["distorted mono leads", "supersaw pad width", "too much delay feedback", "competing with vocal melody"],
        },
        "industry_standard": {
            "plugin": "Reveal Sound Spire",
            "category": "Lead / Soft Trance Lead",
            "internal_search_terms": ["soft lead", "trance lead", "saw lead", "answer"],
            "internet_search_terms": ["Spire soft trance lead preset", "Spire counter melody lead", "Spire uplifting answer lead"],
            "build_from_scratch": ["Use saw lead with reduced unison", "darken cutoff compared with main lead", "medium amp release", "delay lower in mix", "keep centre mono-compatible"],
            "fx_chain": ["HPF", "delay", "small hall", "sidechain", "EQ notch if masking lead"],
            "avoid": ["main-room screech leads", "excessive portamento", "high-note clutter", "same octave lane as payoff"],
        },
    },
    "vocal_melody": {
        "role": "vocal guide melody or topline sketch",
        "mix_note": "Treat this as a writing guide unless replacing it with a real vocal.",
        "primary_owned": {
            "plugin": "Kontakt Factory Library",
            "category": "Vocal Pad / Vocal Lead / Guide Melody",
            "internal_search_terms": ["vocal", "choir", "ahh", "lead", "soft", "pad"],
            "internet_search_terms": ["Kontakt vocal pad preset", "Kontakt vocal lead guide", "trance vocal synth preset"],
            "build_from_scratch": ["Use a simple ahh or vowel patch", "use pad-like vowels for atmosphere or lead-like vowels only as a guide melody", "soft attack", "medium release", "keep lyric space open"],
            "fx_chain": ["HPF 150 Hz", "delay/reverb send", "formant shaping optional", "compress gently", "duck below main hook"],
            "avoid": ["realistic choir too loud", "lyrics implied by clutter", "low vowel mud", "competing with 07_lead"],
        },
        "alternative_owned": {
            "plugin": "Vital",
            "category": "Vocal Synth / Air Lead / Soft Lead",
            "internal_search_terms": ["vocal", "air", "choir", "formant", "soft lead"],
            "internet_search_terms": ["Vital vocal lead preset", "Vital airy vocal synth", "Vital trance vocal chop lead"],
            "build_from_scratch": ["Use formant/vowel wavetable if available", "soft filter", "light unison", "medium release", "keep tone airy"],
            "fx_chain": ["HPF", "filtered delay", "Neoverb send", "chorus subtle", "sidechain under lead"],
            "avoid": ["robotic formant wobble", "harsh nasal peaks", "busy chop behavior", "wide low mids"],
        },
        "industry_standard": {
            "plugin": "Output Exhale",
            "category": "Vocal Engine / Pads / One-Shots / Loops",
            "internal_search_terms": ["vocal pad", "airy", "phrase", "lead", "one shot"],
            "internet_search_terms": ["Output Exhale trance vocal pad", "Exhale vocal lead preset", "uplifting trance vocal chop preset"],
            "build_from_scratch": ["Pick a sustained vowel or airy one-shot", "avoid rhythmic loop mode unless replacing MIDI", "shape attack to match guide", "filter out low body", "use as texture behind hook"],
            "fx_chain": ["HPF", "de-ess", "delay/reverb send", "sidechain", "volume automation"],
            "avoid": ["recognizable loops that clash with MIDI rhythm", "overly breathy noise", "dominant vocal over lead", "muddy layered lows"],
        },
    },
}
def default_sound_design_guide(plugin_name: str, category: str, stem: str, build_steps, fx_chain, avoid):
    role_hint = STEM_CARD_TITLES.get(stem, stem.replace("_", " ").title())
    return {
        "start_patch": [f"{plugin_name} -> start from an Init/blank patch or the cleanest {category} preset.", f"Load the MIDI on {role_hint} first, then shape the sound while the full track loops."],
        "oscillators": list(build_steps[:3]) or ["Choose the simplest source that matches the role.", "Keep low-frequency sources mono and harmonic layers above the bass lane."],
        "filter": ["Use the filter to place the sound before reaching for EQ.", "Close cutoff if it fights lead/supersaw; open only until the part speaks clearly.", "Use low resonance unless the part is intentionally plucky."],
        "envelope": ["Fast attack for rhythmic parts, slower attack for pads/strings.", "Short release for bass/arp, medium release for leads, long release for pads.", "High sustain for held parts; lower sustain for plucks or percussion-like stems."],
        "modulation": ["Map velocity to a small amount of brightness or level.", "Use one slow LFO or macro for movement; avoid competing modulations."],
        "advanced_features": ["Add movement only after the dry patch works in the arrangement.", "Keep stereo width above low mids and check mono compatibility."],
        "built_in_fx": ["Use chorus, delay, or reverb lightly; leave most space decisions for sends.", "Use built-in EQ or drive for tone shaping, not masking fixes."],
        "external_fx": list(fx_chain),
        "listen_for": ["The part should be obvious at its intended section level without masking the hook.", "Mute and unmute it against kick, bass, lead, and supersaw to confirm its job."],
        "common_mistakes": list(avoid),
    }


def vital_sound_design_guide(category: str, stem: str, fx_chain, avoid):
    if stem == "lead":
        return {
            "action": ["Load Vital -> Init Preset", "Search: uplifting trance lead", "Goal: Wide sustained emotional lead above supersaw"],
            "core_build": {
                "oscillators": ["Osc 1 -> Basic Shapes -> Saw.", "Voices: 7.", "Detune: ~0.08.", "Stereo: ~70%.", "Osc 2 -> Saw, 3 voices, lower volume (~40%)."],
                "filter": ["Low-pass 24dB.", "Cutoff ~80%.", "Low resonance."],
                "envelope": ["Fast attack.", "Medium release.", "High sustain."],
                "fx": ["Chorus -> light.", "Delay -> 1/8 ping pong.", "Reverb -> medium hall."],
            },
            "pro_tweaks": {
                "modulation": ["LFO -> slight filter movement.", "Velocity -> filter cutoff.", "Mod wheel -> brightness."],
                "advanced": ["Slight wavetable movement.", "Small pitch drift.", "Control stereo spread."],
                "mix_position": ["HPF below 150 Hz.", "Keep centre clean."],
                "listen_for": ["Smooth sustained tone.", "Emotional lift on long notes."],
                "common_mistakes": ["Too much detune.", "Too much reverb.", "Pluck-style envelope."],
            },
            "start_patch": ["Vital -> Menu -> Init Preset.", "Set polyphony to 6-8 voices so sustained hook notes can overlap cleanly."],
            "oscillators": ["Osc 1: Basic Shapes -> Saw, 6-8 unison voices, medium detune, medium-wide stereo spread.", "Osc 2: Basic Shapes -> Saw, 3-5 voices, volume 35-45%, fine tune slightly for thickness.", "Optional Noise: very low bright air only if the lead feels sterile."],
            "filter": ["Filter 1: Analog 12 dB or Digital Low Pass.", "Cutoff roughly 5-8 kHz for bright but controlled trance tone.", "Resonance 5-12%; drive 5-10% for edge.", "Route Osc 1 and Osc 2 into Filter 1."],
            "envelope": ["Env 1 amp: attack 0-5 ms.", "Decay 0.4-0.8 s, sustain 75-90%, release 250-450 ms.", "Why: the MIDI uses long hook notes, so the patch must sustain instead of pluck."],
            "modulation": ["Env 2 -> Filter 1 cutoff +5 to +12 for held-note bloom.", "Velocity -> Filter cutoff +3 to +8 so stronger notes get brighter.", "Macro 1: Brightness mapped to cutoff and a little drive.", "Macro 2: Width mapped lightly to unison spread."],
            "advanced_features": ["Move wavetable position only slightly if using a non-basic saw.", "Try subtle spectral warp such as Bend or Sync at very low amount.", "Use random phase low-to-medium; fixed phase if attacks feel inconsistent.", "Use one slow LFO at 1/2 or 1 bar to move cutoff by only 1-3%."],
            "built_in_fx": ["Chorus: low mix, wide, slow rate.", "Delay: synced 1/8 or dotted 1/8 if not using Replika.", "Reverb: small amount only; main space comes from Raum/Neoverb send.", "EQ: HPF if needed; gentle high shelf only if not harsh.", "Compressor: light multiband only if the lead feels too soft."],
            "external_fx": fx_chain,
            "listen_for": ["Wide and emotional, not fizzy.", "Payoff notes sustain above supersaw without turning shrill.", "The hook stays clear when delay and reverb are active."],
            "common_mistakes": ["Using a pluck envelope on sustained MIDI.", "Too much detune causing seasick pitch smear.", "Too much reverb pushing the hook backward.", "Filter too closed, making the anthem note small."] + list(avoid[:2]),
        }
    if stem == "supersaw_chords":
        return {
            "action": ["Load Vital -> Init Preset", "Search: trance supersaw", "Goal: Wide euphoric chord stack that supports the lead"],
            "core_build": {
                "oscillators": ["Osc 1 -> Saw (9-11 voices).", "Detune: 0.15.", "Stereo: wide.", "Osc 2 -> Saw (7 voices).", "Blend ~50%."],
                "filter": ["Mostly open low-pass.", "Slight drive."],
                "envelope": ["Fast attack.", "Medium release."],
                "fx": ["Chorus -> strong.", "Reverb -> light."],
            },
            "pro_tweaks": {
                "modulation": ["Subtle pitch movement.", "Macro brightness control."],
                "advanced": ["Add noise layer.", "Slight detune variation per osc."],
                "mix_position": ["Cut 200-400 Hz if muddy.", "Avoid masking lead."],
                "listen_for": ["Wide but controlled.", "Not harsh."],
                "common_mistakes": ["Too much upper-mid bite.", "Too much reverb.", "Masking the lead."],
            },
            "start_patch": ["Vital -> Init Preset.", "Loop Drop 2 chords while setting width and brightness."],
            "oscillators": ["Osc 1: Basic Shapes -> Saw, 7-9 voices, medium detune, medium stereo spread.", "Osc 2: Saw one octave up, 4-6 voices, level 25-40%.", "Optional air/noise layer very low and high-passed."],
            "filter": ["Filter 1: Low Pass 12 dB, cutoff around 4-7 kHz.", "Resonance very low; drive 3-8% for body.", "Open cutoff more in Drop 2, but avoid harsh 3-6 kHz build-up."],
            "envelope": ["Env 1 amp: attack 5-20 ms for drop hits, 40-80 ms for breakdown pads.", "Sustain 85-100%, release 350-700 ms.", "Why: supersaw chords need weight and overlap, not short stabs."],
            "modulation": ["Macro 1: Drop Brightness mapped to cutoff.", "Macro 2: Width mapped lightly to unison spread.", "Velocity -> small level/brightness change.", "Avoid tempo LFO gating unless intentionally making a rhythmic pad."],
            "advanced_features": ["Random phase moderate so stacked chords do not click identically.", "Tiny wavetable-position movement only on upper oscillator.", "Spectral warp subtle; too much sounds digital and sour.", "Check upper octave layers when the lead enters."],
            "built_in_fx": ["Chorus: optional low mix.", "Reverb: short/medium and lower than breakdown pad reverb.", "EQ: HPF around 120-180 Hz.", "Compressor: light glue; sidechain externally from kick."],
            "external_fx": fx_chain,
            "listen_for": ["Huge but not higher than the lead.", "Drop 2 wider than Drop 1.", "Powerful body without muddying bass."],
            "common_mistakes": ["Too many upper-octave voices.", "Detune too wide, making chords blurry.", "Reverb too wet in the drop.", "Low mids fighting bass and piano."] + list(avoid[:2]),
        }
    if stem in ("offbeat_bass", "rolling_bass", "sub_bass"):
        return {
            "action": ["Load Vital -> Init Preset", "Search: trance offbeat bass", "Goal: Tight punchy low end locked to kick"],
            "core_build": {
                "oscillators": ["Saw or square.", "1-2 voices."],
                "filter": ["Low-pass.", "Fairly closed."],
                "envelope": ["Fast attack.", "Short decay.", "Low sustain."],
                "fx": ["Sub: sine layer (low).", "Light distortion.", "EQ clean."],
            },
            "pro_tweaks": {
                "modulation": ["Env -> filter pluck.", "Macro -> drive."],
                "advanced": ["Transient shaping.", "Harmonic layer."],
                "mix_position": ["Mono below 120 Hz.", "Strong sidechain."],
                "listen_for": ["Tight, punchy, clean."],
                "common_mistakes": ["Stereo low end.", "Release too long.", "Filter too open."],
            },
            "start_patch": ["Vital -> Init Preset.", "Loop kick plus this bass stem while designing."],
            "oscillators": ["Offbeat/rolling: Basic Shapes -> Saw or square-saw, 1-3 voices, minimal detune.", "Sub: sine only, no unison, mono.", "Quiet octave-up oscillator only if bass disappears on small speakers."],
            "filter": ["Low Pass 12/24 dB; cutoff low enough to sit under supersaw.", "Use envelope-to-cutoff for bite on offbeat/rolling bass.", "Low resonance; small drive before or inside filter."],
            "envelope": ["Attack 0-5 ms.", "Decay 120-300 ms, sustain 35-70%.", "Release 40-120 ms so notes stop before the next kick/bass hit."],
            "modulation": ["Env 2 -> cutoff for pluck shape.", "Velocity -> level only a little; bass stays even.", "Macro 1: Bite mapped to cutoff envelope amount and drive."],
            "advanced_features": ["Keep phase stable if low end feels inconsistent.", "Avoid wide unison below 150 Hz.", "Use subtle saturation for audibility, not growl."],
            "built_in_fx": ["Distortion/drive: low amount.", "EQ: cut mud if needed.", "Compressor: light only; main pumping comes from external sidechain."],
            "external_fx": fx_chain,
            "listen_for": ["Locks with the kick.", "Offbeat pushes groove without swallowing sub.", "Rolling bass adds urgency, not melody."],
            "common_mistakes": ["Stereo width on low bass.", "Release too long.", "Filter too open.", "Too much distortion."] + list(avoid[:2]),
        }
    if stem in ("arp", "pluck", "countermelody", "vocal_melody"):
        return {
            "start_patch": ["Vital -> Init Preset.", "Loop the section and design at low volume under the lead."],
            "oscillators": ["Basic Shapes -> Saw/triangle blend.", "1-3 voices for pluck, 2-4 for arp/soft answer, light detune.", "Optional noise transient very low if attacks need definition."],
            "filter": ["Low Pass 12 dB with cutoff envelope.", "Cutoff starts moderately closed, opens quickly on each note.", "Resonance 8-18% for sparkle, but stop before whistle."],
            "envelope": ["Attack 0-5 ms.", "Decay 180-450 ms, sustain 20-45%, release 80-220 ms.", "For countermelody/vocal guide, raise sustain and release slightly."],
            "modulation": ["Env 2 -> cutoff +20 to +40 for pluck snap.", "Velocity -> cutoff so accent notes shine.", "Macro 1: Brightness; Macro 2: delay/width."],
            "advanced_features": ["Random phase for slight human attack variation.", "Tiny wavetable motion; MIDI already supplies movement.", "Slow LFO only for gentle stereo/filter movement."],
            "built_in_fx": ["Delay: synced 1/8, low mix.", "Reverb: short, low mix.", "Chorus: optional tiny width.", "EQ: high-pass to stay out of bass."],
            "external_fx": fx_chain,
            "listen_for": ["Audible as groove/support, not chatter.", "Supports lead rhythm without becoming a second hook.", "Delay repeats do not clutter the drop."],
            "common_mistakes": ["Too much delay feedback.", "Sustain too long.", "Bright resonance masking lead.", "Adding rhythmic LFO over rhythmic MIDI."] + list(avoid[:2]),
        }
    return None


def massive_x_sound_design_guide(category: str, stem: str, fx_chain, avoid):
    return {
        "start_patch": [f"Massive X -> Init patch or clean {category} preset family.", "Avoid industrial, distorted, or bass-heavy expansions unless this stem is bass."],
        "oscillators": ["Choose a virtual-analogue saw/pulse or smooth wavetable source.", "Use unison/spread for leads and pads; keep bass patches narrower.", "Blend a second oscillator quietly for body rather than complexity."],
        "filter": ["Use a clean low-pass or state-variable filter.", "Set cutoff by role: brighter for lead, darker for pad/bass.", "Use moderate drive for density; keep resonance controlled."],
        "envelope": ["Amp attack fast for lead/bass/arp, slower for pads.", "Release medium for sustained leads, short for bass/arp, long for pads.", "Use decay/sustain to match MIDI length instead of forcing every part into a pluck."],
        "modulation": ["Use Performer or LFO for slow motion, not busy wobble.", "Macro 1 -> filter brightness.", "Macro 2 -> width or wavetable position.", "Velocity -> slight filter opening on accented notes."],
        "advanced_features": ["Subtle wavetable position movement for expression.", "Use routing feedback/insert FX lightly.", "Keep movement slower than the MIDI rhythm.", "Check mono compatibility after unison/spread."],
        "built_in_fx": ["Dimension/chorus for width at low mix.", "Delay/reverb only if external sends are not doing the space.", "EQ or insert drive for tone shaping.", "Avoid heavy distortion unless designing tech bass."],
        "external_fx": fx_chain,
        "listen_for": ["Modern and controlled, not industrial.", "Macros improve held notes without changing the musical role.", "Patch sits in its lane before big FX."],
        "common_mistakes": ["Aggressive bass presets for melodic stems.", "Too much Performer motion.", "Wide low end.", "Macro movement that changes melody feel."] + list(avoid[:2]),
    }


def kontakt_sound_design_guide(category: str, stem: str, fx_chain, avoid):
    is_strings = stem == "strings"
    return {
        "start_patch": [f"Kontakt/Komplete Kontrol -> search {category}.", "Prefer a clean library/instrument over a processed trailer preset."],
        "oscillators": ["Library direction: Strings / Ensemble / Legato / Cinematic Pad." if is_strings else "Library direction: Grand Piano / Felt Piano / Emotional Piano.", "Articulation: sustain or legato; avoid staccato/spiccato unless replacing MIDI." if is_strings else "Tone: soft grand or felt; avoid hard EDM piano stabs.", "Use ensemble patches for pad support." if is_strings else "Use one main piano; avoid layered left-hand bass unless needed."],
        "filter": ["Use Kontakt/instrument tone controls to remove harsh highs or low mud.", "High-pass externally rather than over-filtering the natural instrument.", "Keep brightness warm enough to blend with pads/supersaw."],
        "envelope": ["Strings: moderate/slow attack, long release, expression swelling into phrase ends." if is_strings else "Piano: natural attack, release/pedal enough for emotion but not mud.", "Use MIDI velocity/dynamics to shape phrase emotion.", "Avoid cutting note tails too short in breakdown."],
        "modulation": ["Map mod wheel/CC1 to dynamics for strings.", "Use expression/CC11 for swells and phrase-level volume.", "For piano, vary velocity rather than adding synthetic LFO movement."],
        "advanced_features": ["Use round robin/humanize if available.", "Choose close/room mics moderately; too much room washes out motif.", "Strings should change dynamics more than notes; piano should preserve repeated motif."],
        "built_in_fx": ["Use built-in room/reverb lightly if the library needs realism.", "Disable huge cinematic reverb if using Raum/Neoverb sends.", "Use built-in EQ/tone controls gently."],
        "external_fx": fx_chain,
        "listen_for": ["Emotional and realistic, not placeholder MIDI.", "Motif or chord swell breathes between phrases.", "Supports the drop emotionally without masking lead."],
        "common_mistakes": ["Wrong articulation on sustained MIDI.", "Too much pedal/room mud.", "Velocity too flat.", "Trailer brightness overpowering trance warmth."] + list(avoid[:2]),
    }


def build_sound_design_guide(data: dict, stem: str = ""):
    plugin_name = data.get("plugin", "")
    category = data.get("category", "")
    build_steps = list(data.get("build_from_scratch", []))
    fx_chain = list(data.get("fx_chain", []))
    avoid = list(data.get("avoid", []))
    if plugin_name == "Vital":
        guide = vital_sound_design_guide(category, stem, fx_chain, avoid)
        if guide:
            return guide
    if plugin_name == "Massive X":
        return massive_x_sound_design_guide(category, stem, fx_chain, avoid)
    if "Kontakt" in plugin_name:
        return kontakt_sound_design_guide(category, stem, fx_chain, avoid)
    return default_sound_design_guide(plugin_name, category, stem, build_steps, fx_chain, avoid)


def determine_arrangement_role(stem, metadata, midi_analysis, mix_context=None):
    identity = str(metadata.get("track_identity", "")).upper()
    variation = str(metadata.get("variation_type", "")).upper()
    genre = str(metadata.get("genre", metadata.get("progression_name", ""))).lower()
    density = midi_analysis.get("notes_per_active_bar", 0) or 0
    avg_length = midi_analysis.get("avg_note_length", 0) or 0
    role = "SUPPORT"
    reason = f"{stem.replace('_', ' ').title()} is treated as a controlled support layer for this {genre or 'trance'} arrangement."
    intensity = "controlled"
    dominance = "medium"

    if stem in ("kick", "offbeat_bass", "rolling_bass", "sub_bass"):
        role = "FOUNDATION"
        reason = "Kick and bass stems define the low-end foundation and must stay clean, tight, and mono-compatible."
        intensity = "clean"
        dominance = "high" if stem == "kick" else "medium"
    elif stem in ("arp", "pluck"):
        role = "RHYTHMIC_MOTION"
        reason = "Arp/pluck stems provide rhythmic motion, so the patch should stay clear rather than overly animated."
        intensity = "clean" if density >= 3 else "moderate"
        dominance = "medium"
    elif stem in ("pad", "strings", "vocal_melody"):
        role = "ATMOSPHERE"
        reason = "Atmospheric stems should widen the emotional space without competing for hook focus."
        intensity = "soft"
        dominance = "low"
    elif stem == "clap_snare":
        role = "TRANSITION_TENSION"
        reason = "Snare/clap material should build tension and support transitions without becoming chaotic early."
        intensity = "evolving"
        dominance = "medium"
    elif stem == "lead":
        role = "MAIN_FOCUS"
        reason = "Lead is the primary hook stem when no contextual identity overrides it."
        intensity = "present"
        dominance = "high"
    elif stem == "supersaw_chords":
        role = "RELEASE_LAYER"
        reason = "Supersaw chords should create emotional release and width around drop moments."
        intensity = "controlled"
        dominance = "medium"

    if identity == "ORCHESTRAL_UPLIFTING" and variation == "PIANO_INTRO":
        if stem == "piano":
            return {
                "arrangement_role": "MAIN_FOCUS",
                "role_reason": "Orchestral Uplifting with PIANO_INTRO: piano carries the exposed emotional motif.",
                "sound_design_intensity": "intimate",
                "dominance_level": "high",
            }
        if stem == "strings":
            return {
                "arrangement_role": "ATMOSPHERE",
                "role_reason": "Orchestral Uplifting with PIANO_INTRO: strings are emotional support around the piano.",
                "sound_design_intensity": "soft",
                "dominance_level": "medium",
            }
        if stem == "lead":
            return {
                "arrangement_role": "SUPPORT",
                "role_reason": "Orchestral Uplifting with PIANO_INTRO: piano/strings carry emotion, so lead should join warmly and become brighter only in the drop.",
                "sound_design_intensity": "warm_controlled",
                "dominance_level": "medium",
            }
        if stem == "supersaw_chords":
            return {
                "arrangement_role": "RELEASE_LAYER",
                "role_reason": "Orchestral Uplifting with PIANO_INTRO: supersaw should lift behind piano/strings and bloom into release.",
                "sound_design_intensity": "controlled",
                "dominance_level": "medium",
            }
        if stem in ("offbeat_bass", "rolling_bass", "sub_bass"):
            return {
                "arrangement_role": "FOUNDATION",
                "role_reason": "Orchestral Uplifting with PIANO_INTRO: bass supports piano/strings early and grows into the drop.",
                "sound_design_intensity": "clean_controlled",
                "dominance_level": "medium",
            }

    if identity == "ANTHEMIC_UPLIFTING" and variation == "SUPERSAW_HEAVY":
        if stem == "supersaw_chords":
            role, reason, intensity, dominance = "MAIN_FOCUS", "Anthemic Uplifting with SUPERSAW_HEAVY: supersaw is the dominant release layer and should feel wide and powerful.", "bold", "high"
        elif stem == "lead":
            role, reason, intensity, dominance = "MAIN_FOCUS", "Anthemic Uplifting with SUPERSAW_HEAVY: lead must cut through the wide supersaw while keeping a dry centre.", "bright_present", "high"
        elif stem in ("offbeat_bass", "rolling_bass", "sub_bass"):
            role, reason, intensity, dominance = "FOUNDATION", "Anthemic Uplifting with SUPERSAW_HEAVY: bass must drive the drop under the large chord wall.", "driving", "high"
    elif identity == "ANTHEMIC_UPLIFTING" and variation == "ARP_DRIVEN":
        if stem == "arp":
            role, reason, intensity, dominance = "RHYTHMIC_MOTION", "Anthemic Uplifting with ARP_DRIVEN: arp is a secondary identity layer and should stay clean and audible early.", "clean", "medium_high"
        elif stem == "supersaw_chords":
            role, reason, intensity, dominance = "SUPPORT", "Anthemic Uplifting with ARP_DRIVEN: supersaw supports until the drop and should not overpower early arp motion.", "controlled", "medium"
        elif stem == "lead":
            role, reason, intensity, dominance = "MAIN_FOCUS", "Anthemic Uplifting with ARP_DRIVEN: lead becomes main focus in the drop while leaving intro/build space for arp.", "present", "high"
    elif identity == "EMOTIONAL_VOCAL_TRANCE" or variation == "LATE_HOOK":
        if stem == "vocal_melody":
            role, reason, intensity, dominance = "MAIN_FOCUS", "Emotional/Vocal context: vocal melody is the emotional placeholder and should feel airy and human.", "airy", "high"
        elif stem in ("lead", "supersaw_chords"):
            role, reason, intensity, dominance = "SUPPORT", "Emotional/Vocal context: lead/supersaw should leave space for vocal emotion and avoid aggressive anthem brightness.", "warm_spacious", "medium"
        elif stem in ("offbeat_bass", "rolling_bass", "sub_bass"):
            role, reason, intensity, dominance = "FOUNDATION", "Emotional/Vocal context: bass should be clean and softer so vocal space remains open.", "clean_soft", "medium"
    elif identity == "CLASSIC_2000S_TRANCE":
        if stem in ("arp", "pluck"):
            role, reason, intensity, dominance = "RHYTHMIC_MOTION", "Classic 2000s Trance: arp/pluck identity is important and should be rhythmic, gated, and delay-friendly.", "classic_clear", "medium_high"
        elif stem == "lead":
            role, reason, intensity, dominance = "MAIN_FOCUS", "Classic 2000s Trance: lead should be simple, repetitive, and can lean into pluck-lead character.", "clear_repetitive", "high"
        elif stem == "supersaw_chords":
            role, reason, intensity, dominance = "SUPPORT", "Classic 2000s Trance: supersaw should be simpler and brighter, less huge than modern festival stacks.", "simple_bright", "medium"

    return {
        "arrangement_role": role,
        "role_reason": reason,
        "sound_design_intensity": intensity,
        "dominance_level": dominance,
    }


def role_label(role):
    return str(role or "SUPPORT").replace("_", " ").title()


def contextual_sound_design_overrides(stem, role_context):
    role = role_context.get("arrangement_role")
    reason = role_context.get("role_reason", "")
    intensity = role_context.get("sound_design_intensity", "")
    if stem == "supersaw_chords" and role == "RELEASE_LAYER" and "Orchestral" in reason:
        return {
            "action": ["Load Vital -> Init Preset -> build a controlled release supersaw", "Search: controlled trance supersaw", "Goal: Supportive emotional lift behind piano/strings, opening into the drop"],
            "core_build": {
                "oscillators": ["Osc 1 Saw: 7-9 voices.", "Detune: 0.10-0.12.", "Osc 2 Saw: 5 voices, lower volume.", "Stereo: controlled wide."],
                "filter": ["Low-pass slightly more closed than festival supersaw.", "Cutoff 75-85%.", "Controlled mids."],
                "envelope": ["Fast attack.", "Medium release.", "Sustain high enough to bloom."],
                "fx": ["Chorus -> medium, not strong.", "Reverb -> moderate for blend.", "Avoid full festival wash early."],
            },
            "pro_tweaks": {
                "modulation": ["Automate filter open into drop.", "Automate width wider in drop.", "Use macro for release intensity."],
                "advanced": ["Keep upper sides wide but mids controlled.", "Use gentle noise/air only if needed."],
                "mix_position": ["Narrow 2-4 kHz mids if lead/piano needs space.", "High-pass below 120-180 Hz.", "Do not mask piano/strings."],
                "listen_for": ["Should lift the emotional section.", "Should not overpower piano/strings.", "Should bloom into release."],
                "common_mistakes": ["Too many voices.", "Too much detune.", "Strong chorus causing wash.", "Masking piano/lead mids."],
            },
            "key_settings": "Voices: 7-9 | Detune: 0.10-0.12 | Stereo: Controlled Wide | Filter: 75-85%",
            "mix_insight": "Supersaw should bloom into the drop. Automate filter and width instead of using full intensity throughout.",
        }
    if stem == "lead" and role == "SUPPORT" and "Orchestral" in reason:
        return {
            "action": ["Load Vital -> Init Preset -> build a warm supportive lead", "Search: warm trance support lead", "Goal: Emotional support lead that joins piano/strings rather than dominating them"],
            "core_build": {
                "oscillators": ["Osc 1 Saw: 5-7 voices.", "Detune: 0.05-0.08.", "Osc 2 Saw/Triangle: low volume for body.", "Keep stereo controlled."],
                "filter": ["Filter more closed than anthem lead.", "Brightness 70-80%.", "Low resonance."],
                "envelope": ["Fast attack.", "Medium-long release.", "High sustain for emotional notes."],
                "fx": ["Delay -> slightly wetter than main anthem lead.", "Reverb -> medium to sit behind piano early.", "Chorus -> light."],
            },
            "pro_tweaks": {
                "modulation": ["Automate brightness into drop.", "Use velocity or macro to open filter on emotional peaks."],
                "advanced": ["Keep dry centre controlled.", "Avoid giant unison spread before the drop."],
                "mix_position": ["Sit behind piano/strings until the drop.", "HPF below 150 Hz.", "Keep 2-5 kHz gentle."],
                "listen_for": ["Warm and emotional.", "Does not overpower piano.", "Becomes more present only in drop."],
                "common_mistakes": ["Using harsh anthem lead too early.", "Too much stereo width.", "Too little release.", "Masking piano transient."],
            },
            "key_settings": "Voices: 5-7 | Detune: 0.05-0.08 | Brightness: Warm | Reverb: Medium",
            "mix_insight": "Lead should sit behind piano/strings until the drop. Use warmer filter and more space, then automate brightness upward.",
        }
    if stem in ("offbeat_bass", "rolling_bass", "sub_bass") and "Orchestral" in reason:
        return {
            "action": ["Load Vital -> Init Preset -> build clean controlled trance bass", "Search: clean trance bass", "Goal: Stable low-end foundation that supports piano/strings and grows into the drop"],
            "core_build": {
                "oscillators": ["Osc 1 Saw/Square, mono.", "Voices: 1-2.", "Optional sine sub layer."],
                "filter": ["Low-pass fairly closed.", "Keep low mids clean.", "Open more in drops if needed."],
                "envelope": ["Fast attack.", "Short decay.", "Low sustain."],
                "fx": ["Very light saturation.", "EQ clean.", "No stereo widening on lows."],
            },
            "pro_tweaks": {
                "modulation": ["Env -> filter pluck.", "Macro -> presence for drop energy."],
                "advanced": ["Keep intro bass lower in level.", "Increase presence in drop.", "Use harmonic layer only if small speakers need it."],
                "mix_position": ["Mono below 120 Hz.", "Stronger sidechain only once kick/drop is active.", "Avoid piano low-mid mud."],
                "listen_for": ["Clean low end.", "No mud with piano.", "Controlled drive."],
                "common_mistakes": ["Too aggressive early bass.", "Stereo low end.", "Heavy distortion.", "Muddy overlap with piano low mids."],
            },
            "key_settings": "Voices: 1-2 | Filter: Closed/Medium | Mono: Yes | Saturation: Light",
            "mix_insight": "Keep bass controlled so piano low mids remain clear. Avoid aggressive saturation before the drop.",
        }
    if stem == "piano" and role == "MAIN_FOCUS" and "Orchestral" in reason:
        return {
            "action": ["Load Kontakt Piano -> warm grand/felt patch", "Search: emotional cinematic piano", "Goal: Intimate breakdown motif that carries the track emotion"],
            "core_build": {
                "oscillators": ["Library: warm grand or felt piano.", "Use one main piano patch.", "Avoid layered bass-heavy lows."],
                "filter": ["Use tone control to soften harsh highs.", "HPF gently below 80-120 Hz.", "Keep low mids clean."],
                "envelope": ["Natural attack.", "Long enough release for emotion.", "Use velocity for phrase shape."],
                "fx": ["Hall reverb send.", "Light compression.", "Optional filtered delay only if motif stays clear."],
            },
            "pro_tweaks": {
                "modulation": ["Use velocity variation instead of synth LFO.", "Automate reverb send on anchor notes."],
                "advanced": ["Keep pedal/release musical but not muddy.", "Let silence before emotional notes breathe."],
                "mix_position": ["Leave centre clear and intimate.", "Keep bass out of piano low mids."],
                "listen_for": ["Simple hummable motif.", "Expressive long note.", "Piano feels like the emotional centre."],
                "common_mistakes": ["Hard EDM piano stabs.", "Too much pedal mud.", "Robotic velocity.", "Masking with bass low mids."],
            },
            "key_settings": "Tone: Warm/Felt | Velocity: Expressive | Release: Natural | Reverb: Hall",
            "mix_insight": "Piano is the emotional centre. Keep it intimate and readable before widening supporting layers around it.",
        }
    if stem == "strings" and role == "ATMOSPHERE" and "Orchestral" in reason:
        return {
            "action": ["Load Kontakt Strings -> sustained ensemble", "Search: warm sustained strings", "Goal: Smooth emotional support around the piano"],
            "core_build": {
                "oscillators": ["Library: ensemble strings.", "Articulation: sustain or legato.", "Avoid rhythmic short articulations."],
                "filter": ["Warm tone.", "Remove harsh top if needed.", "HPF low rumble."],
                "envelope": ["Slow/moderate attack.", "Long release.", "Use expression swells."],
                "fx": ["Large hall reverb.", "Gentle EQ.", "Light compression only if uneven."],
            },
            "pro_tweaks": {
                "modulation": ["Use mod wheel/CC1 for dynamics.", "Expression rises into final bars."],
                "advanced": ["Change dynamics more than notes.", "Widen final bars subtly."],
                "mix_position": ["Sit behind piano.", "Avoid 2-5 kHz build-up.", "Keep low strings controlled."],
                "listen_for": ["Smooth ensemble sustain.", "Emotional lift without weird motion.", "Supports piano, not replaces it."],
                "common_mistakes": ["Spiccato movement.", "Trailer brightness.", "Too much low cello mud.", "Constant note changes."],
            },
            "key_settings": "Articulation: Sustain/Legato | Attack: Soft | Dynamics: Swell | Reverb: Hall",
            "mix_insight": "Strings should widen the emotional space behind the piano. Use dynamics and register, not busy movement.",
        }
    if stem == "supersaw_chords" and role == "MAIN_FOCUS":
        return {
            "key_settings": "Voices: 9-11 | Detune: 0.13-0.17 | Stereo: Wide | Filter: Mostly Open",
            "mix_insight": "Supersaw is a main focus. Keep it wide and dominant, but carve space for the lead in the 2-5 kHz range.",
        }
    if stem == "lead" and role == "MAIN_FOCUS":
        return {
            "key_settings": "Voices: 7-9 | Detune: 0.08-0.11 | Brightness: Open | Dry Centre: Strong",
            "mix_insight": "Lead is a main focus. Keep the dry centre clear, then use delay/reverb sends for size.",
        }
    if stem in ("arp", "pluck") and role == "RHYTHMIC_MOTION":
        return {
            "key_settings": "Patch: Clean | Release: Short | Delay: Low Feedback | Built-in Arp: Off",
            "mix_insight": "Use a simple patch; the MIDI already supplies movement. Reduce delay/reverb if the groove blurs.",
        }
    if stem == "vocal_melody" and role == "MAIN_FOCUS":
        return {
            "key_settings": "Tone: Airy | Attack: Soft | Reverb: Spacious | Brightness: Gentle",
            "mix_insight": "Vocal melody is the emotional placeholder. Keep other melodic layers warm and leave phrase space around it.",
        }
    if stem in ("offbeat_bass", "rolling_bass", "sub_bass"):
        bass_drive = "DRIVE" if intensity in ("driving", "classic_clear") else "SUPPORT"
        return {
            "key_settings": "Filter: Medium | Saturation: Moderate | Sidechain: Strong | Mono: Yes" if bass_drive == "DRIVE" else "Filter: More Closed | Saturation: Light | Sidechain: Moderate | Mono: Yes",
            "mix_insight": "Bass is the foundation. Keep the sub mono, leave space for the kick, and scale aggression to the section energy.",
        }
    return {}


def apply_role_context_to_plugin_record(record: dict, stem: str, role_context: dict):
    overrides = contextual_sound_design_overrides(stem, role_context)
    guide = record.get("sound_design_guide", {})
    if "action" in overrides:
        plugin_name = record.get("plugin", "Plugin")
        guide["action"] = [item.replace("Vital", plugin_name).replace("Kontakt Piano", plugin_name).replace("Kontakt Strings", plugin_name) for item in overrides["action"]]
    if "core_build" in overrides:
        guide["core_build"] = overrides["core_build"]
    if "pro_tweaks" in overrides:
        guide["pro_tweaks"] = overrides["pro_tweaks"]
    record["sound_design_guide"] = guide
    if overrides.get("key_settings"):
        record["contextual_key_settings"] = overrides["key_settings"]
    if overrides.get("mix_insight"):
        record["contextual_mix_insight"] = overrides["mix_insight"]
    record["arrangement_role"] = role_context.get("arrangement_role", "SUPPORT")
    record["role_reason"] = role_context.get("role_reason", "")
    record["sound_design_intensity"] = role_context.get("sound_design_intensity", "controlled")
    record["dominance_level"] = role_context.get("dominance_level", "medium")
    return record


def advisor_plugin_record(data: dict, stem: str = "") -> dict:
    record = {
        "plugin": data["plugin"],
        "category": data["category"],
        "internal_search_terms": list(data["internal_search_terms"]),
        "internet_search_terms": list(data["internet_search_terms"]),
        "build_from_scratch": list(data["build_from_scratch"]),
        "fx_chain": list(data["fx_chain"]),
        "avoid": list(data["avoid"]),
    }
    if record["plugin"] == "Massive X":
        for warning in ("industrial preset families", "distorted bass-heavy patches", "over-aggressive macro movement"):
            if warning not in record["avoid"]:
                record["avoid"].append(warning)
    record["sound_design_guide"] = build_sound_design_guide(record, stem)
    return record


def make_industry_alternative(plugin: str, category: str, internal_terms, internet_terms, build_steps, fx_chain, avoid):
    return {
        "plugin": plugin,
        "category": category,
        "internal_search_terms": list(internal_terms),
        "internet_search_terms": list(internet_terms),
        "build_from_scratch": list(build_steps),
        "fx_chain": list(fx_chain),
        "avoid": list(avoid),
    }


def industry_alternative_plugins(stem: str, profile: dict):
    alternatives = [advisor_plugin_record(profile["industry_standard"], stem=stem)]
    if stem == "lead":
        alternatives.extend([
            make_industry_alternative(
                "Xfer Serum",
                "Lead / Euphoric Saw Lead / Trance Lead",
                ["lead", "saw lead", "trance", "euphoric", "anthem"],
                ["Serum euphoric trance lead preset", "Serum uplifting saw lead preset", "Serum ASOT trance lead"],
                ["Use saw oscillator with 5-7 unison voices", "create one clear mono-compatible centre", "place a single higher peak note without harshness", "use filter cutoff to keep brightness controlled"],
                ["HPF below 150 Hz", "tempo delay", "large hall send", "light sidechain", "gentle exciter"],
                ["OTT overuse", "screechy high resonance", "wide low-frequency unison", "complex wavetable motion that weakens hook identity"],
            ),
            make_industry_alternative(
                "LennarDigital Sylenth1",
                "Lead / Trance Saw / Anthem Lead",
                ["lead", "trance", "saw", "anthem", "uplifting"],
                ["Sylenth1 ASOT trance lead preset", "Sylenth1 uplifting lead preset", "Sylenth1 euphoric saw lead"],
                ["Stack saw oscillators across parts", "moderate detune", "fast attack with medium release", "filter bright but smooth", "keep delay/reverb as sends"],
                ["HPF", "synced delay", "hall reverb", "sidechain", "high-mid smoothing EQ"],
                ["over-detuned lead blur", "supersaw pad presets", "too much portamento", "uncontrolled reverb tails"],
            ),
        ])
    elif stem == "supersaw_chords":
        alternatives.insert(0, make_industry_alternative(
            "Reveal Sound Spire",
            "Supersaw / Trance Chords / Wide Pad",
            ["supersaw", "trance", "chord", "pad", "uplifting"],
            ["Spire uplifting trance supersaw preset", "Spire euphoric saw chords", "Spire ASOT supersaw"],
            ["Use multiple saw oscillators", "moderate unison detune", "emphasize root and fifth", "add upper octave brightness without exceeding safe register", "sustain chords through drop hits"],
            ["HPF 120-180 Hz", "sidechain", "short hall send", "dynamic EQ harsh bands", "stereo width above low mids"],
            ["too much top-octave stacking", "mud below 150 Hz", "washy reverb", "thin high-only voicings"],
        ))
        alternatives.insert(1, make_industry_alternative(
            "Xfer Serum",
            "Supersaw / Chord Stack / Trance Pad",
            ["supersaw", "chord", "trance", "pad", "wide"],
            ["Serum uplifting trance supersaw preset", "Serum euphoric chord stack", "Serum trance saw chords"],
            ["Use saw oscillator with 7-9 unison voices", "duplicate chord tones by octave in MIDI or synth layers", "keep detune musical not seasick", "use filter and sidechain for drop movement"],
            ["HPF", "sidechain", "EQ harshness", "hall send", "mono low utility"],
            ["OTT over-compression", "wide sub frequencies", "top-heavy shrillness", "excess noise layer"],
        ))
    for alternative in alternatives:
        alternative.setdefault("sound_design_guide", build_sound_design_guide(alternative, stem))
    return alternatives


def append_unique(items, additions):
    for item in additions:
        if item not in items:
            items.append(item)


def append_to_plugin(plugin: dict, *, category_suffix: str = "", internal_terms=None, internet_terms=None, build_steps=None, fx_steps=None, avoid_notes=None):
    if category_suffix and category_suffix not in plugin["category"]:
        plugin["category"] = f"{plugin['category']} / {category_suffix}"
    append_unique(plugin["internal_search_terms"], internal_terms or [])
    append_unique(plugin["internet_search_terms"], internet_terms or [])
    append_unique(plugin["build_from_scratch"], build_steps or [])
    append_unique(plugin["fx_chain"], fx_steps or [])
    append_unique(plugin["avoid"], avoid_notes or [])


def apply_length_recommendation(profile: dict, advice_notes, mode: str):
    if mode == "short":
        advice_notes.append("MIDI behaviour: short average notes detected, so choose pluck, gated, or sequence-style patches instead of long sustained leads.")
        for tier in ("primary_owned", "alternative_owned", "industry_standard"):
            append_to_plugin(
                profile[tier],
                category_suffix="Pluck / Gated / Sequence",
                internal_terms=["pluck", "gated", "sequence", "short decay"],
                internet_terms=["trance pluck preset", "gated trance lead preset", "uplifting trance sequence preset"],
                build_steps=["Shorten amp release", "use a pluck envelope on filter cutoff", "keep delay feedback controlled", "avoid slow pad-style attacks"],
                fx_steps=["shorter delay feedback", "less reverb send", "transient control"],
                avoid_notes=["long washy sustained presets", "slow attack leads", "reverb tails that blur short notes"],
            )
    elif mode == "sustained":
        advice_notes.append("MIDI behaviour: sustained notes detected, so choose anthem/sustained trance lead patches with longer release and emotional delay/reverb.")
        for tier in ("primary_owned", "alternative_owned", "industry_standard"):
            append_to_plugin(
                profile[tier],
                category_suffix="Sustained / Anthem / Euphoric",
                internal_terms=["sustained", "anthem", "euphoric", "long lead"],
                internet_terms=["sustained uplifting trance lead preset", "anthem trance lead preset", "euphoric long note lead"],
                build_steps=["Use medium release", "keep a strong mono-compatible centre", "let delay and reverb support long notes", "automate filter slightly open on held notes"],
                fx_steps=["longer tempo delay", "larger hall send", "gentle exciter"],
                avoid_notes=["overly percussive plucks", "gated sequences", "short decay presets that underplay held notes"],
            )


def apply_density_recommendation(profile: dict, advice_notes, density_mode: str, target: str):
    if density_mode == "high":
        advice_notes.append(f"MIDI behaviour: high {target} density detected, so choose cleaner and simpler patches that leave space.")
        for tier in ("primary_owned", "alternative_owned", "industry_standard"):
            append_to_plugin(
                profile[tier],
                category_suffix="Clean / Simple",
                internal_terms=["clean", "simple", "tight", "minimal"],
                internet_terms=[f"clean trance {target} preset", f"simple uplifting {target} preset"],
                build_steps=["Reduce unison or oscillator layers", "use shorter release where appropriate", "prioritize note clarity over motion"],
                fx_steps=["reduce reverb send", "control delay feedback", "use EQ to carve repeated-note buildup"],
                avoid_notes=["complex animated presets", "busy built-in arps", "wide washes that blur dense MIDI"],
            )
    elif density_mode == "low":
        advice_notes.append(f"MIDI behaviour: low {target} density detected, so fuller or more animated patches are safe.")
        for tier in ("primary_owned", "alternative_owned", "industry_standard"):
            append_to_plugin(
                profile[tier],
                category_suffix="Full / Animated",
                internal_terms=["wide", "animated", "rich", "motion"],
                internet_terms=[f"wide trance {target} preset", f"animated uplifting {target} preset"],
                build_steps=["Allow wider unison or richer layers", "add gentle modulation for movement", "use sustain/release to fill the space between notes"],
                fx_steps=["wider reverb send", "tempo delay for motion", "slow filter automation"],
                avoid_notes=["over-thinning sparse MIDI", "dry patches that make gaps feel empty"],
            )


def apply_pitch_span_recommendation(profile: dict, advice_notes, analysis: dict):
    span = analysis.get("pitch_span", 0)
    if span and span <= 7:
        advice_notes.append("MIDI behaviour: narrow pitch range detected, so add expression through filter, velocity, width, or subtle modulation.")
        for tier in ("primary_owned", "alternative_owned", "industry_standard"):
            append_to_plugin(
                profile[tier],
                category_suffix="Expressive Motion",
                internal_terms=["expressive", "motion", "macro", "modulation"],
                internet_terms=["expressive trance preset", "macro motion trance preset"],
                build_steps=["Add subtle filter or wavetable movement", "map velocity to cutoff or brightness", "use modulation to create emotion without changing notes"],
                fx_steps=["automation-friendly filter", "subtle chorus or phaser", "dynamic reverb send"],
                avoid_notes=["static init-style patches", "flat velocity response"],
            )
    elif span >= 18:
        advice_notes.append("MIDI behaviour: wide pitch range detected, so use controlled patches with less modulation to avoid chaos.")
        for tier in ("primary_owned", "alternative_owned", "industry_standard"):
            append_to_plugin(
                profile[tier],
                category_suffix="Controlled / Stable",
                internal_terms=["controlled", "stable", "focused", "mono compatible"],
                internet_terms=["controlled trance preset", "stable uplifting trance preset"],
                build_steps=["Reduce pitch and wavetable modulation", "keep filter movement subtle", "preserve a stable centre image across wide notes"],
                fx_steps=["less chorus depth", "tighter delay feedback", "dynamic EQ on high notes"],
                avoid_notes=["wild pitch modulation", "random arp presets", "overwide high-register FX"],
            )


def build_mix_context(stem_analysis):
    lead = stem_analysis.get("lead", {})
    supersaw = stem_analysis.get("supersaw_chords", {})
    arp = stem_analysis.get("arp", {})
    pad = stem_analysis.get("pad", {})
    kick = stem_analysis.get("kick", {})
    bass_stems = [
        stem_analysis.get("offbeat_bass", {}),
        stem_analysis.get("rolling_bass", {}),
        stem_analysis.get("sub_bass", {}),
    ]
    bass_density = round(sum(item.get("notes_per_active_bar", 0) for item in bass_stems), 2)
    bass_min_pitch = min(
        [item.get("min_pitch") for item in bass_stems if item.get("min_pitch") is not None] or [None],
        default=None,
    )
    bass_max_pitch = max(
        [item.get("max_pitch") for item in bass_stems if item.get("max_pitch") is not None] or [None],
        default=None,
    )
    return {
        "lead_supersaw_dense": lead.get("notes_per_active_bar", 0) >= 1.8 and supersaw.get("notes_per_active_bar", 0) >= 5.0,
        "lead_sparse": lead.get("notes_per_active_bar", 0) <= 1.5,
        "arp_dense": arp.get("notes_per_active_bar", 0) >= 3.5,
        "pad_supersaw_sustained": pad.get("avg_note_length", 0) >= 1.0 and supersaw.get("avg_note_length", 0) >= 1.0,
        "bass_kick_overlap": kick.get("note_count", 0) > 0 and bass_density >= 4.0 and (bass_min_pitch is not None and bass_min_pitch <= 48),
        "bass_density": bass_density,
        "bass_pitch_range": [bass_min_pitch, bass_max_pitch],
        "lead_density": lead.get("notes_per_active_bar", 0),
        "supersaw_density": supersaw.get("notes_per_active_bar", 0),
        "arp_density": arp.get("notes_per_active_bar", 0),
        "pad_avg_note_length": pad.get("avg_note_length", 0),
        "supersaw_avg_note_length": supersaw.get("avg_note_length", 0),
    }


def apply_mix_context_recommendation(stem: str, profile: dict, advice_notes, mix_context: dict):
    mix_notes = []
    if mix_context.get("lead_supersaw_dense") and stem == "lead":
        note = (
            "Mix context: lead and supersaw are both dense, so use a thinner brighter lead and carve the shared 2-5 kHz range."
        )
        mix_notes.append(note)
        for tier in ("primary_owned", "alternative_owned", "industry_standard"):
            append_to_plugin(
                profile[tier],
                category_suffix="Thin Bright / Mask-Safe Lead",
                internal_terms=["thin lead", "bright lead", "focused", "mask safe"],
                internet_terms=["thin bright trance lead preset", "mask safe uplifting lead preset"],
                build_steps=["Reduce oscillator stack thickness", "keep lead bright but narrow in the low mids", "preserve a mono-compatible centre above the supersaw"],
                fx_steps=["EQ carve supersaw or lead around 2-5 kHz", "HPF lead below 180 Hz", "reduce reverb low mids"],
                avoid_notes=["lead and supersaw occupy same 2-5kHz range; reduce one or EQ carve", "thick supersaw-style lead patches", "wide low-mid chorus on the lead"],
            )
    if mix_context.get("lead_supersaw_dense") and stem == "supersaw_chords":
        note = (
            "Mix context: supersaw and lead are both active in the hook range; keep supersaw wide but carve a small 2-5 kHz pocket for 07_lead."
        )
        mix_notes.append(note)
        for tier in ("primary_owned", "alternative_owned", "industry_standard"):
            append_to_plugin(
                profile[tier],
                category_suffix="Wide Background / Lead Pocket",
                internal_terms=["wide", "background", "smooth", "chord bed"],
                internet_terms=["smooth trance supersaw chord preset", "wide background supersaw preset"],
                build_steps=["Keep chord body wide but not piercing", "reduce midrange stack thickness", "leave the lead attack range clear"],
                fx_steps=["dynamic EQ dip around 2-5 kHz keyed by lead", "sidechain from kick", "reduce exciter on chord bus"],
                avoid_notes=["supersaw masking lead attacks in 2-5kHz", "bright lead-like chord presets", "too much upper-mid distortion"],
            )
    if mix_context.get("bass_kick_overlap") and stem in ("kick", "offbeat_bass", "rolling_bass", "sub_bass"):
        note = (
            "Mix context: bass density is high while kick and bass share low-frequency space; use stronger sidechain and EQ separation around the kick fundamental."
        )
        mix_notes.append(note)
        for tier in ("primary_owned", "alternative_owned", "industry_standard"):
            append_to_plugin(
                profile[tier],
                category_suffix="Kick-Separated Low End",
                internal_terms=["tight", "sidechain", "mono", "low control"],
                internet_terms=["trance kick bass sidechain EQ", "uplifting trance low end separation"],
                build_steps=["Shorten low-end release where needed", "leave a gap for the kick transient", "keep bass mono below 120 Hz"],
                fx_steps=["stronger kick sidechain", "EQ notch bass near kick fundamental", "separate kick click from bass body"],
                avoid_notes=["kick and bass overlap below 120Hz; sidechain harder and carve bass around kick body", "long bass release over kick", "stereo sub layers"],
            )
    if mix_context.get("pad_supersaw_sustained") and stem == "pad":
        note = (
            "Mix context: pad and supersaw are both sustained; make the pad darker and wider so it supports instead of stacking brightness."
        )
        mix_notes.append(note)
        for tier in ("primary_owned", "alternative_owned", "industry_standard"):
            append_to_plugin(
                profile[tier],
                category_suffix="Dark Wide Support Pad",
                internal_terms=["dark pad", "wide pad", "support", "warm"],
                internet_terms=["dark wide trance pad preset", "warm support pad preset"],
                build_steps=["Close pad filter slightly", "spread pad width above 300 Hz", "keep attack slow behind supersaw"],
                fx_steps=["low-pass pad brightness", "widen pad sides", "duck pad under supersaw sustain"],
                avoid_notes=["pad and supersaw both sustained; reduce pad brightness above 3kHz", "bright saw pad competing with supersaw", "dense midrange pad voicing"],
            )
    if mix_context.get("pad_supersaw_sustained") and stem == "supersaw_chords":
        note = (
            "Mix context: sustained pad is already filling atmosphere; keep supersaw midrange narrower and let width live in the upper sides."
        )
        mix_notes.append(note)
        for tier in ("primary_owned", "alternative_owned", "industry_standard"):
            append_to_plugin(
                profile[tier],
                category_suffix="Narrower Mid / Wide Top",
                internal_terms=["controlled mid", "wide top", "smooth supersaw"],
                internet_terms=["controlled supersaw chord preset", "smooth wide top supersaw"],
                build_steps=["Keep midrange chord core focused", "put extra width in upper octave layers", "avoid adding pad-like low mids"],
                fx_steps=["mono-compatible mid channel", "side EQ width above 4 kHz", "cut 250-600 Hz if pad is active"],
                avoid_notes=["pad and supersaw both sustained; avoid wide low-mid buildup", "too much chorus on chord body", "bright pad-like supersaw wash"],
            )
    if mix_context.get("arp_dense") and stem == "arp":
        note = "Mix context: arp density is high in the full arrangement; reduce delay and reverb so repeats do not smear the groove."
        mix_notes.append(note)
        for tier in ("primary_owned", "alternative_owned", "industry_standard"):
            append_to_plugin(
                profile[tier],
                category_suffix="Dry Clean Groove",
                internal_terms=["dry", "clean", "simple", "short"],
                internet_terms=["dry clean trance arp preset", "simple clean trance pluck"],
                build_steps=["Use a simple transient pluck", "disable complex built-in sequencers", "keep release short"],
                fx_steps=["short delay feedback", "lower reverb send", "HPF delay return"],
                avoid_notes=["dense arp plus delay feedback creates chatter; reduce delay/reverb", "complex arp presets", "ping-pong feedback masking hats"],
            )
    if mix_context.get("lead_sparse") and stem == "lead":
        note = "Mix context: lead is sparse enough to carry richer space; use wider stereo delay/reverb while keeping the dry note upfront."
        mix_notes.append(note)
        for tier in ("primary_owned", "alternative_owned", "industry_standard"):
            append_to_plugin(
                profile[tier],
                category_suffix="Wide Spacious Hook",
                internal_terms=["wide lead", "spacious", "anthem", "delay"],
                internet_terms=["wide uplifting trance lead preset", "spacious anthem lead preset"],
                build_steps=["Keep dry lead centred", "add width in delay/reverb returns", "let held notes bloom after the attack"],
                fx_steps=["richer ping-pong delay", "larger hall send", "stereo widening on returns only"],
                avoid_notes=["fully wet lead losing centre", "wide dry oscillator phase problems", "delay masking next hook attack"],
            )
    if mix_notes:
        advice_notes.extend(mix_notes)
    return mix_notes


def advisor_profile_for_analysis(stem: str, analysis: dict, mix_context=None):
    profile = copy.deepcopy(STEM_ADVISOR_PROFILES[stem])
    advice_notes = []
    mix_context = mix_context or {}
    avg_len = analysis.get("avg_note_length", 0)
    density = analysis.get("notes_per_active_bar", 0)

    if stem in ("lead", "countermelody", "vocal_melody"):
        if avg_len < 0.6:
            apply_length_recommendation(profile, advice_notes, "short")
        elif avg_len >= 1.0:
            apply_length_recommendation(profile, advice_notes, "sustained")

    if stem == "arp":
        if density >= 3.5:
            apply_density_recommendation(profile, advice_notes, "high", "arp")
            advice_notes.append("Arp-specific decision: warn against complex arp presets because the MIDI already supplies enough activity.")
        elif density <= 2.0:
            apply_density_recommendation(profile, advice_notes, "low", "arp")
            advice_notes.append("Arp-specific decision: more complex sequence presets are acceptable because MIDI density is low.")

    if stem == "supersaw_chords":
        if density >= 5.0:
            apply_density_recommendation(profile, advice_notes, "high", "supersaw chord")
            advice_notes.append("Supersaw-specific decision: use thinner cleaner patches because chord stacking is already dense.")
        elif density <= 3.0:
            apply_density_recommendation(profile, advice_notes, "low", "supersaw chord")
            advice_notes.append("Supersaw-specific decision: use thicker wider patches because the MIDI chord density is restrained.")

    if stem == "piano":
        if density <= 1.5:
            advice_notes.append("MIDI behaviour: sparse piano detected, so use emotional felt piano and long ambience.")
            for tier in ("primary_owned", "alternative_owned", "industry_standard"):
                append_to_plugin(
                    profile[tier],
                    category_suffix="Sparse Felt / Emotional",
                    internal_terms=["felt", "soft", "emotional", "sparse"],
                    internet_terms=["emotional felt piano preset", "sparse trance breakdown piano"],
                    build_steps=["Use softer velocity curve", "let long notes ring", "preserve silence before emotional notes"],
                    fx_steps=["longer hall send", "gentle compression", "soft transient shaping"],
                    avoid_notes=["bright percussive EDM piano", "dense chord stabs", "short slap delay"],
                )
        elif density >= 2.5:
            advice_notes.append("MIDI behaviour: dense piano detected, so use a brighter more percussive piano with controlled ambience.")
            for tier in ("primary_owned", "alternative_owned", "industry_standard"):
                append_to_plugin(
                    profile[tier],
                    category_suffix="Bright / Percussive",
                    internal_terms=["bright", "percussive", "pop grand", "attack"],
                    internet_terms=["bright trance piano preset", "percussive EDM piano preset"],
                    build_steps=["Use clearer hammer attack", "shorten release", "control sustain pedal feel"],
                    fx_steps=["shorter reverb", "transient control", "EQ low-mid cleanup"],
                    avoid_notes=["felt presets too soft for dense MIDI", "long pedal wash", "muddy low chords"],
                )

    apply_pitch_span_recommendation(profile, advice_notes, analysis)
    mix_notes = apply_mix_context_recommendation(stem, profile, advice_notes, mix_context)
    profile["mix_context_advice"] = mix_notes
    profile["dynamic_advice"] = advice_notes or ["MIDI behaviour: balanced note length, density, and pitch range detected, so use the base recommendation without extra correction."]
    return profile


def analyze_exported_midi_stem(stem_name: str, notes):
    if notes and not isinstance(notes[0], dict):
        notes = events_to_notes(notes)
    ordered = sorted(notes, key=lambda item: (item["start"], item.get("pitch", 0), item["end"]))
    export_name = STEM_EXPORT_LABELS.get(stem_name, stem_name)
    if not ordered:
        return {
            "stem": stem_name,
            "file": f"stems/{export_name}.mid",
            "note_count": 0,
            "active_bars": 0,
            "first_bar": None,
            "last_bar": None,
            "avg_note_length": 0,
            "long_note_ratio": 0,
            "avg_velocity": 0,
            "max_velocity": 0,
            "min_pitch": None,
            "max_pitch": None,
            "pitch_span": 0,
            "notes_per_active_bar": 0,
        }

    lengths = [length_beats(note) for note in ordered]
    velocities = [note.get("velocity", 0) for note in ordered]
    pitches = [note.get("pitch", 0) for note in ordered]
    bars = {note["start"] // BAR_TICKS for note in ordered}
    first_bar = min(bars) + 1
    last_bar = max(note["end"] // BAR_TICKS for note in ordered) + 1
    long_count = sum(1 for value in lengths if value >= 1.0)
    return {
        "stem": stem_name,
        "file": f"stems/{export_name}.mid",
        "note_count": len(ordered),
        "active_bars": len(bars),
        "first_bar": first_bar,
        "last_bar": last_bar,
        "avg_note_length": round(sum(lengths) / max(1, len(lengths)), 3),
        "long_note_ratio": round(long_count / max(1, len(lengths)), 3),
        "avg_velocity": round(sum(velocities) / max(1, len(velocities)), 1),
        "max_velocity": max(velocities),
        "min_pitch": min(pitches),
        "max_pitch": max(pitches),
        "pitch_span": max(pitches) - min(pitches),
        "notes_per_active_bar": round(len(ordered) / max(1, len(bars)), 2),
    }


def analyze_exported_midi_stems(tracks):
    return {
        stem: analyze_exported_midi_stem(stem, tracks.get(stem, []))
        for stem in STEMS
    }


def stem_advice_block(stem: str, analysis: dict, mix_context=None) -> str:
    profile = advisor_profile_for_analysis(stem, analysis, mix_context)
    export_name = STEM_EXPORT_LABELS.get(stem, stem)
    def plugin_block(label: str, data: dict) -> str:
        data = advisor_plugin_record(data, stem=stem)
        return (
            f"- {label}_plugin_name: {data['plugin']}\n"
            f"- {label}_category_preset_family: {data['category']}\n"
            f"- {label}_internal_search_terms: {'; '.join(data['internal_search_terms'])}\n"
            f"- {label}_internet_search_terms: {'; '.join(data['internet_search_terms'])}\n"
            f"- {label}_build_from_scratch: {'; '.join(data['build_from_scratch'])}\n"
            f"- {label}_fx_chain: {'; '.join(data['fx_chain'])}\n"
            f"- {label}_avoid_notes: {'; '.join(data['avoid'])}\n"
        )
    def industry_blocks() -> str:
        blocks = []
        for index, data in enumerate(industry_alternative_plugins(stem, profile), start=1):
            blocks.append(plugin_block(f"industry_alternative_{index}", data))
        return "".join(blocks)
    return (
        f"{export_name}.mid\n"
        f"- role: {profile['role']}\n"
        f"- detected_note_count: {analysis['note_count']}\n"
        f"- active_bar_range: {analysis['first_bar'] or 'none'}-{analysis['last_bar'] or 'none'}\n"
        f"- notes_per_active_bar: {analysis['notes_per_active_bar']}\n"
        f"- avg_note_length_beats: {analysis['avg_note_length']}\n"
        f"- long_note_ratio: {analysis['long_note_ratio']}\n"
        f"- velocity_range: avg {analysis['avg_velocity']} / max {analysis['max_velocity']}\n"
        f"- pitch_range: {analysis['min_pitch'] or 'none'}-{analysis['max_pitch'] or 'none'} span {analysis['pitch_span']}\n"
        f"- mix_note: {profile['mix_note']}\n"
        f"- dynamic_midi_advice: {'; '.join(profile['dynamic_advice'])}\n"
        f"- mix_context_advice: {'; '.join(profile['mix_context_advice']) if profile['mix_context_advice'] else 'none'}\n"
        + plugin_block("primary_owned", profile["primary_owned"])
        + plugin_block("alternative_owned", profile["alternative_owned"])
        + industry_blocks()
    )


STEM_CARD_TITLES = {
    "kick": "Kick - Drop Anchor",
    "offbeat_bass": "Offbeat Bass - Trance Push",
    "rolling_bass": "Rolling Bass - Groove Drive",
    "sub_bass": "Sub Bass - Low Foundation",
    "clap_snare": "Clap/Snare - Backbeat and Builds",
    "hats": "Hats - Top-End Motion",
    "lead": "Lead - Main Hook",
    "supersaw_chords": "Supersaw Chords - Drop Width",
    "pad": "Pad - Atmosphere",
    "arp": "Arp - Harmonic Rhythm",
    "pluck": "Pluck - Punctuation",
    "strings": "Strings - Emotional Lift",
    "piano": "Piano - Breakdown Motif",
    "countermelody": "Countermelody - Answer Layer",
    "vocal_melody": "Vocal Melody - Topline Guide",
}


STEM_MIX_LEVELS = {
    "kick": "-8 dB",
    "offbeat_bass": "-12 dB",
    "rolling_bass": "-14 dB",
    "sub_bass": "-14 dB",
    "clap_snare": "-14 dB",
    "hats": "-18 dB",
    "lead": "-14 dB",
    "supersaw_chords": "-16 dB",
    "pad": "-22 dB",
    "arp": "-20 dB",
    "pluck": "-21 dB",
    "strings": "-20 dB",
    "piano": "-18 dB",
    "countermelody": "-18 dB",
    "vocal_melody": "-18 dB",
}


def first_items(items, limit):
    return list(items or [])[:limit]


def numbered_lines(items, limit=4):
    return "\n".join(f"{index + 1}. {item}" for index, item in enumerate(first_items(items, limit)))


def bullet_lines(items, limit=4):
    return "\n".join(f"- {item}" for item in first_items(items, limit))


def behaviour_classification(stem: str, analysis: dict):
    density = analysis.get("notes_per_active_bar", 0)
    avg_len = analysis.get("avg_note_length", 0)
    if stem in ("kick", "clap_snare", "hats"):
        return "rhythmic percussion"
    if avg_len >= 1.25 and density <= 2:
        return "sustained melodic or harmonic part"
    if density >= 3.5:
        return "dense rhythmic pattern"
    if avg_len < 0.75:
        return "short-note groove part"
    return "balanced support part"


def stem_warning(profile, analysis):
    warnings = []
    warnings.extend(profile.get("dynamic_advice", [])[:1])
    warnings.extend(profile.get("mix_context_advice", [])[:1])
    if not warnings:
        warnings = ["No urgent warning; start with the recommended sound and balance by ear."]
    return warnings[0]


def sound_design_guide_text(guide: dict, limit_per_section=3):
    if guide and ("action" in guide or "core_build" in guide or "pro_tweaks" in guide):
        lines = []
        action = guide.get("action", [])
        if action:
            lines.append("- Action:")
            for item in first_items(action, 3):
                lines.append(f"  - {item}")
        core_labels = [
            ("oscillators", "Core Build - Oscillators"),
            ("filter", "Core Build - Filter"),
            ("envelope", "Core Build - Envelope"),
            ("fx", "Core Build - FX"),
        ]
        core = guide.get("core_build", {})
        for key, label in core_labels:
            lines.append(f"- {label}:")
            for item in first_items(core.get(key, []), limit_per_section):
                lines.append(f"  - {item}")
        pro_labels = [
            ("modulation", "Pro Tweaks - Modulation"),
            ("advanced", "Pro Tweaks - Advanced"),
            ("mix_position", "Pro Tweaks - Mix Position"),
            ("listen_for", "Pro Tweaks - Listen For"),
            ("common_mistakes", "Pro Tweaks - Common Mistakes"),
        ]
        pro = guide.get("pro_tweaks", {})
        for key, label in pro_labels:
            lines.append(f"- {label}:")
            for item in first_items(pro.get(key, []), limit_per_section):
                lines.append(f"  - {item}")
        return "\n".join(lines)
    labels = [
        ("start_patch", "Start Patch"),
        ("oscillators", "Oscillators"),
        ("filter", "Filter"),
        ("envelope", "Envelope"),
        ("modulation", "Modulation"),
        ("advanced_features", "Advanced Features"),
        ("built_in_fx", "FX"),
        ("external_fx", "External FX Chain"),
        ("listen_for", "What To Listen For"),
        ("common_mistakes", "Common Mistakes"),
    ]
    lines = []
    for key, label in labels:
        lines.append(f"- {label}:")
        for item in first_items((guide or {}).get(key, []), limit_per_section):
            lines.append(f"  - {item}")
    return "\n".join(lines)


def build_stem_card(stem: str, analysis: dict, mix_context):
    profile = advisor_profile_for_analysis(stem, analysis, mix_context)
    primary = advisor_plugin_record(profile["primary_owned"], stem=stem)
    alternative = advisor_plugin_record(profile["alternative_owned"], stem=stem)
    industry = industry_alternative_plugins(stem, profile)[0]
    export_name = STEM_EXPORT_LABELS.get(stem, stem)
    title = STEM_CARD_TITLES.get(stem, stem.replace("_", " ").title())
    return (
        "--------------------------------------------------\n\n"
        f"[{export_name.upper()} - {title}]\n\n"
        "Role:\n"
        f"- {profile['role']}\n\n"
        "Best Plugin:\n"
        f"- {primary['plugin']}\n\n"
        "Preset Category:\n"
        f"- {primary['category']}\n\n"
        "Search:\n"
        f"{bullet_lines(primary['internal_search_terms'], 4)}\n\n"
        "Build From Scratch:\n"
        f"{sound_design_guide_text(primary.get('sound_design_guide', {}), 3)}\n\n"
        "FX Chain:\n"
        f"{numbered_lines(primary['fx_chain'], 4)}\n\n"
        "Alternative Plugin:\n"
        f"- {alternative['plugin']}\n\n"
        "Alternative Setup:\n"
        f"- Category: {alternative['category']}\n"
        f"- Search: {', '.join(first_items(alternative['internal_search_terms'], 3))}\n"
        f"- Direction: {'; '.join(first_items(alternative['build_from_scratch'], 2))}\n\n"
        "Industry Alternative:\n"
        f"- {industry['plugin']}\n\n"
        "Avoid:\n"
        f"- {stem_warning(profile, analysis)}\n\n"
        "Mix Level:\n"
        f"- Start at {STEM_MIX_LEVELS.get(stem, '-18 dB')}\n\n"
    )


def build_production_advice_text(stem_analysis, blueprint, sections) -> str:
    mix_context = build_mix_context(stem_analysis)
    blocks = "\n".join(build_stem_card(stem, stem_analysis[stem], mix_context) for stem in STEMS)
    return (
        f"Dream Trance Generator {APP_VERSION} / Advisor {ADVISOR_UI_VERSION} - Production Advice\n\n"
        "Use this as the main producer workflow file. Open production_quick_start.txt first if you want the fastest setup.\n\n"
        "STEM CARDS\n\n"
        f"{blocks}"
    )


def build_production_quick_start_text(stem_analysis, blueprint, sections, bpm: int, key: str = ""):
    mix_context = build_mix_context(stem_analysis)
    lead_driver = "lead + supersaw"
    if blueprint.get("track_identity_key") == "ORCHESTRAL_UPLIFTING":
        lead_driver = "piano + strings into supersaw"
    elif blueprint.get("track_identity_key") == "EMOTIONAL_VOCAL_TRANCE":
        lead_driver = "vocal guide + warm lead support"
    elif blueprint.get("track_identity_key") == "CLASSIC_2000S_TRANCE":
        lead_driver = "arp/pluck motif + lead hook"
    warnings = []
    for stem in ("lead", "supersaw_chords", "arp", "offbeat_bass", "rolling_bass", "pad"):
        profile = advisor_profile_for_analysis(stem, stem_analysis[stem], mix_context)
        warnings.extend(profile.get("mix_context_advice", [])[:1])
    if not warnings:
        warnings = ["Balance lead, supersaw, and bass first; then bring in support layers."]
    return (
        f"Dream Trance Generator {APP_VERSION} / Advisor {ADVISOR_UI_VERSION} - Production Quick Start\n\n"
        "TRACK OVERVIEW\n"
        f"- Genre: {blueprint.get('genre', blueprint.get('progression_name', ''))}\n"
        f"- Identity: {blueprint.get('track_identity', '')}\n"
        f"- Variation: {blueprint.get('variation_type', 'DEFAULT')}\n"
        f"- BPM: {bpm}\n"
        f"- Key: {key or blueprint.get('selected_key') or 'selected key'}\n\n"
        "START HERE (STEP-BY-STEP)\n"
        "1. Load Kick: Ableton Drum Rack or Battery 4.\n"
        "2. Load Bass: Massive X or Vital bass for 02/03/04 stems.\n"
        "3. Load Supersaw: Vital pad/lead or Sylenth1 supersaw for 08_supersaw_chords.\n"
        "4. Load Lead: Vital lead for 07_lead.\n"
        "5. Add FX sends: one filtered delay, one hall reverb, one short room.\n\n"
        "PRIORITY ELEMENTS\n"
        f"- What drives this track: {lead_driver}\n"
        f"- Drop profile: {blueprint.get('identity_drop_style', '')}\n"
        f"- Breakdown focus: {blueprint.get('identity_breakdown_style', '')}\n\n"
        "CRITICAL WARNINGS\n"
        f"{bullet_lines(warnings, 5)}\n"
    )


def build_technical_midi_analysis_text(stem_analysis, blueprint, sections):
    mix_context = build_mix_context(stem_analysis)
    context_lines = "\n".join(f"- {key}: {value}" for key, value in mix_context.items())
    stem_blocks = []
    for stem in STEMS:
        analysis = stem_analysis[stem]
        profile = advisor_profile_for_analysis(stem, analysis, mix_context)
        export_name = STEM_EXPORT_LABELS.get(stem, stem)
        stem_blocks.append(
            f"{export_name}.mid\n"
            f"- Notes: {analysis['note_count']}\n"
            f"- Active bars: {analysis['first_bar'] or 'none'}-{analysis['last_bar'] or 'none'} ({analysis['active_bars']})\n"
            f"- Range: {analysis['min_pitch'] or 'none'}-{analysis['max_pitch'] or 'none'}\n"
            f"- Avg length: {analysis['avg_note_length']} beats\n"
            f"- Density: {analysis['notes_per_active_bar']} notes/active bar\n"
            f"- Behaviour: {behaviour_classification(stem, analysis)}\n"
            f"- Warning: {stem_warning(profile, analysis)}\n"
        )
    return (
        f"Dream Trance Generator {APP_VERSION} / Advisor {ADVISOR_UI_VERSION} - Technical MIDI Analysis\n\n"
        "TRACK METADATA\n"
        f"- Genre: {blueprint.get('genre', blueprint.get('progression_name', ''))}\n"
        f"- Identity: {blueprint.get('track_identity', '')}\n"
        f"- Progression: {blueprint.get('progression_name', '')}\n\n"
        "CROSS-STEM MIX CONTEXT\n"
        f"{context_lines}\n\n"
        "STEM MIDI ANALYSIS\n\n"
        + "\n".join(stem_blocks)
    )


def build_ableton_setup_guide(stem_analysis, bpm: int, sections, blueprint=None) -> str:
    blueprint = blueprint or {}
    stem_lines = "\n".join(
        f"- {STEM_EXPORT_LABELS.get(stem, stem)}.mid: import to its own MIDI track, then load the recommended instrument from production_advice.txt"
        for stem in STEMS
    )
    section_lines = "\n".join(
        f"- {section['name']}: bars {section['start_bar'] + 1}-{section['end_bar']}"
        for section in sections
    )
    return (
        f"Ableton Setup Guide - Dream Trance Generator {APP_VERSION} / Advisor {ADVISOR_UI_VERSION}\n\n"
        "Project Setup:\n"
        f"- Set tempo to {bpm} BPM before importing MIDI.\n"
        f"- Track identity: {blueprint.get('track_identity', 'unknown')}\n"
        f"- Production intention: {blueprint.get('track_identity_description', 'unknown')}\n"
        f"- Emotional target: {blueprint.get('emotional_target', 'unknown')}\n"
        f"- Progression: {blueprint.get('progression_name', 'unknown')}\n"
        f"- Progression family: {blueprint.get('progression_family', 'unknown')}\n"
        "- Use 4/4 time.\n"
        "- Drag full_arrangement.mid into the arrangement first if you want a reference overview.\n"
        "- Drag each file from stems/ onto a separate MIDI track for production and sound selection.\n"
        "- Preserve the imported clip start positions so stems stay aligned.\n\n"
        "Recommended Track Groups:\n"
        "- Drums: 01_kick, 05_clap_snare, 06_hats\n"
        "- Bass: 02_offbeat_bass, 03_rolling_bass, 04_sub_bass\n"
        "- Hook: 07_lead, 14_countermelody, 15_vocal_melody\n"
        "- Harmony: 08_supersaw_chords, 09_pad, 10_arp, 11_pluck, 12_strings, 13_piano\n\n"
        "Import Checklist:\n"
        f"{stem_lines}\n\n"
        "Section Markers:\n"
        f"{section_lines}\n\n"
        "Routing and Mix Starts:\n"
        "- Route kick to a sidechain bus and feed lead, supersaw, pad, arp, pluck, and bass compressors lightly.\n"
        "- Keep 04_sub_bass mono and avoid reverb on it.\n"
        "- Put 07_lead upfront with delay/reverb sends rather than heavy insert wash.\n"
        "- Let 08_supersaw_chords dominate Drop 2 width while staying ducked by the kick.\n"
        "- In breakdown sections, feature 13_piano and 12_strings with more space and less sidechain.\n\n"
        "Recommended Return Tracks:\n"
        "- A Delay: synced 1/8 or dotted 1/8 ping-pong, filtered lows below 200 Hz.\n"
        "- B Hall: Raum/Neoverb large hall, 20-30 percent send for lead/piano/strings.\n"
        "- C Short Room: subtle drum and pluck space.\n"
        "- D Width: subtle chorus/phaser for lead or countermelody only when mono compatibility survives.\n"
    )


def build_plugin_recommendations(stem_analysis, blueprint=None, bpm=None):
    blueprint = blueprint or {}
    mix_context = build_mix_context(stem_analysis)
    recommendations = {}
    for stem in STEMS:
        profile = advisor_profile_for_analysis(stem, stem_analysis[stem], mix_context)
        role_context = determine_arrangement_role(stem, blueprint, stem_analysis[stem], mix_context)
        primary_record = apply_role_context_to_plugin_record(advisor_plugin_record(profile["primary_owned"], stem=stem), stem, role_context)
        alternative_record = apply_role_context_to_plugin_record(advisor_plugin_record(profile["alternative_owned"], stem=stem), stem, role_context)
        industry_records = [
            apply_role_context_to_plugin_record(record, stem, role_context)
            for record in industry_alternative_plugins(stem, profile)
        ]
        contextual_mix_insight = (
            primary_record.get("contextual_mix_insight")
            or (profile.get("mix_context_advice") or profile.get("dynamic_advice") or [profile.get("mix_note", "")])[0]
        )
        recommendations[STEM_EXPORT_LABELS.get(stem, stem)] = {
            "midi_file": stem_analysis[stem]["file"],
            "role": profile["role"],
            "arrangement_role": role_context["arrangement_role"],
            "arrangement_role_label": role_label(role_context["arrangement_role"]),
            "role_reason": role_context["role_reason"],
            "sound_design_intensity": role_context["sound_design_intensity"],
            "dominance_level": role_context["dominance_level"],
            "contextual_mix_insight": contextual_mix_insight,
            "analysis": stem_analysis[stem],
            "mix_note": profile["mix_note"],
            "dynamic_midi_advice": profile["dynamic_advice"],
            "mix_context_advice": profile["mix_context_advice"],
            "primary_plugin": primary_record,
            "alternative_owned_plugin": alternative_record,
            "industry_alternative_plugins": industry_records,
        }
    return {
        "build": APP_VERSION,
        "advisor_ui_version": ADVISOR_UI_VERSION,
        "advisor_mode": "auto_production_advisor",
        "advisor_role_context_mode": "context_aware_role_aware",
        "generated_from_exported_stem_analysis": True,
        "track_identity": blueprint.get("track_identity", ""),
        "variation_type": blueprint.get("variation_type", "DEFAULT"),
        "variation_behavior_summary": blueprint.get("variation_behavior_summary", ""),
        "bpm": bpm,
        "key": blueprint.get("selected_key", ""),
        "emotional_target": blueprint.get("emotional_target", ""),
        "selected_chord_progression": blueprint.get("selected_chord_progression", blueprint.get("progression_name", "")),
        "progression_name": blueprint.get("progression_name", ""),
        "progression_family": blueprint.get("progression_family", ""),
        "motif_story_mode": "v11_motif_phrase_story",
        "story_type": blueprint.get("v11_motif_story", {}).get("story_type", ""),
        "main_motif_owner": blueprint.get("v11_motif_story", {}).get("main_motif_owner", ""),
        "shiver_moment": blueprint.get("v11_motif_story", {}).get("shiver_moment", {}),
        "mix_context": mix_context,
        "stem_count": len(STEMS),
        "recommendations": recommendations,
    }


def export_pack(bpm: int, tracks, blueprint, sections, markers, out_path: Path):
    tempo = bpm2tempo(bpm)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    td = EXPORTS_DIR / ("_build_" + uuid4().hex)
    td.mkdir(parents=True, exist_ok=True)
    try:
        combined = MidiFile(type=1, ticks_per_beat=TICKS)
        combined.tracks.append(finalise_track("Markers", tempo, [], markers=markers))

        for stem in STEMS:
            export_name = STEM_EXPORT_LABELS.get(stem, stem)
            stem_midi = MidiFile(type=1, ticks_per_beat=TICKS)
            stem_midi.tracks.append(finalise_track(export_name, tempo, tracks[stem]))
            stem_path = td / f"{export_name}.mid"
            stem_midi.save(stem_path)
            combined.tracks.append(finalise_track(export_name, tempo, tracks[stem]))

        arrangement_path = td / "full_arrangement.mid"
        combined.save(arrangement_path)

        notes_path = td / "production_notes.txt"
        validation = blueprint.get("validation_report", {})
        motif_story = blueprint.get("v11_motif_story", {})
        motif_validation = motif_story.get("validation", {})
        shiver_moment = motif_story.get("shiver_moment", {})
        motif_corrections = motif_story.get("musical_correction_report", {})
        candidate_windows = validation.get("lead_candidate_windows", [])
        candidate_window_lines = []
        for window in candidate_windows:
            candidate_window_lines.append(
                f"- {window['section']} bars {window['phrase_start_bar']}-{window['phrase_start_bar'] + 7}: selected candidate {window['selected_candidate_index']} ({window['selected_archetype']} v{window['selected_variant_index']}) score {window['best_hook_score']}"
            )
            for candidate in window.get("candidates", []):
                reasons = ", ".join(candidate.get("rejection_reasons", []))
                candidate_window_lines.append(
                    f"  - candidate {candidate['index']} {candidate['archetype']} v{candidate['variant_index']}: total={candidate['total']} motif={candidate['motif_score']} rhythm={candidate['rhythmic_identity_score']} register={candidate['register_arc_score']} payoff={candidate['payoff_score']} singability={candidate['singability_score']} contrast={candidate['supersaw_contrast_score']} valid={candidate['valid']} reasons={reasons}"
                )
        notes_path.write_text(
            f"Dream Trance Generator {APP_VERSION}\n\n"
            + "V11 MOTIF / STORY SUMMARY\n"
            + f"- story_type: {motif_story.get('story_type', '')}\n"
            + f"- emotional_arc: {', '.join(motif_story.get('emotional_arc', []))}\n"
            + f"- main_motif_owner: {motif_story.get('main_motif_owner', '')}\n"
            + f"- secondary_motif_owner: {motif_story.get('secondary_motif_owner', '')}\n"
            + f"- core_motif_contour: {motif_story.get('core_motif', {}).get('contour', '')}\n"
            + f"- phrase_model: {motif_story.get('core_motif', {}).get('phrase_model', '')}\n"
            + f"- motif_reveal_plan: {json.dumps(motif_story.get('motif_reveal_plan', {}))}\n"
            + f"- breakdown_treatment: {motif_story.get('motif_variations_by_section', {}).get('Breakdown', {}).get('mode', '')}\n"
            + f"- drop1_motif_treatment: {motif_story.get('motif_variations_by_section', {}).get('Drop 1', {}).get('mode', '')}\n"
            + f"- drop2_motif_treatment: {motif_story.get('motif_variations_by_section', {}).get('Drop 2', {}).get('mode', '')}\n"
            + f"- shiver_moment: {shiver_moment.get('type', '')} at {shiver_moment.get('section', '')} bar {shiver_moment.get('bar', '')}\n"
            + f"- motif_strength_score: {motif_validation.get('motif_strength_score', 0)}\n"
            + f"- phrase_coherence_score: {motif_validation.get('phrase_coherence_score', 0)}\n"
            + f"- story_arc_score: {motif_validation.get('story_arc_score', 0)}\n"
            + f"- breakdown_quality_score: {motif_validation.get('breakdown_quality_score', 0)}\n"
            + f"- drop_payoff_score: {motif_validation.get('drop_payoff_score', 0)}\n"
            + f"- intro_avg_pitch: {motif_corrections.get('intro_avg_pitch', 0)}\n"
            + f"- lead_avg_duration: {motif_corrections.get('lead_avg_duration', 0)}\n"
            + f"- string_non_chord_repairs: {motif_corrections.get('string_non_chord_repairs', 0)}\n"
            + f"- scale_lock_repairs: {motif_corrections.get('scale_lock_repairs', 0)}\n"
            + f"- v11_1_warnings: {', '.join(motif_corrections.get('v11_1_warnings', ['none']))}\n"
            + f"- phrase_gaps_inserted: {motif_corrections.get('phrase_gaps_inserted', 0)}\n"
            + f"- anticipation_repairs: {motif_corrections.get('anticipation_repairs', 0)}\n"
            + f"- hook_repetitions_drop1: {motif_corrections.get('hook_repetitions_drop1', 0)}\n"
            + f"- hook_repetitions_drop2: {motif_corrections.get('hook_repetitions_drop2', 0)}\n"
            + f"- drop_contrast_score: {motif_corrections.get('drop_contrast_score', 0)}\n"
            + f"- breakdown_sustained_notes: {motif_corrections.get('breakdown_sustained_notes', 0)}\n"
            + f"- humanised_notes: {motif_corrections.get('humanised_notes', 0)}\n"
            + f"- v11_2_warnings: {', '.join(motif_corrections.get('v11_2_warnings', ['none']))}\n"
            + f"- intro_teaser_stem: {motif_corrections.get('intro_teaser_stem', '')}\n"
            + f"- intro_teaser_notes: {motif_corrections.get('intro_teaser_notes', 0)}\n"
            + f"- intro_kick_pattern: {motif_corrections.get('intro_kick_pattern', '')}\n"
            + f"- intro_kick_hits: {motif_corrections.get('intro_kick_hits', 0)}\n"
            + f"- intro_percussion_hits: {motif_corrections.get('intro_percussion_hits', 0)}\n"
            + f"- intro_bass_tease_notes: {motif_corrections.get('intro_bass_tease_notes', 0)}\n"
            + f"- intro_story_score: {motif_corrections.get('intro_story_score', 0)}\n"
            + f"- intro_validation_warnings: {', '.join(motif_corrections.get('intro_validation_warnings', ['none']))}\n"
            + f"- intro_signature_stem: {motif_corrections.get('intro_signature_stem', '')}\n"
            + f"- intro_signature_repetitions: {motif_corrections.get('intro_signature_repetitions', 0)}\n"
            + f"- intro_signature_rhythm: {motif_corrections.get('intro_signature_rhythm', '')}\n"
            + f"- intro_call_response_applied: {motif_corrections.get('intro_call_response_applied', False)}\n"
            + f"- intro_mini_moment: {motif_corrections.get('intro_mini_moment', '')}\n"
            + f"- intro_identity_score: {motif_corrections.get('intro_identity_score', 0)}\n"
            + f"- intro_identity_warnings: {', '.join(motif_corrections.get('intro_identity_warnings', ['none']))}\n"
            + f"- lead_silent_sections: {', '.join(motif_corrections.get('lead_silent_sections', []))}\n"
            + f"- lead_teaser_notes: {motif_corrections.get('lead_teaser_notes', 0)}\n"
            + f"- lead_teaser_bars: {motif_corrections.get('lead_teaser_bars', '')}\n"
            + f"- drop1_lead_hook_notes: {motif_corrections.get('drop1_lead_hook_notes', 0)}\n"
            + f"- drop2_lead_payoff_notes: {motif_corrections.get('drop2_lead_payoff_notes', 0)}\n"
            + f"- drop2_lead_payoff_mode: {motif_corrections.get('drop2_lead_payoff_mode', '')}\n"
            + f"- lead_drop_avg_duration: {motif_corrections.get('lead_drop_avg_duration', 0)}\n"
            + f"- lead_payoff_warnings: {', '.join(motif_corrections.get('lead_payoff_warnings', ['none']))}\n"
            + f"- producer_note: {motif_story.get('producer_note', '')}\n\n"
            + "Track Identity Engine:\n"
            + f"- track_archetype: {blueprint['track_archetype']}\n"
            + "- record-level identity now biases the whole blueprint instead of only individual stem families\n"
            + "- drop behavior, breakdown mood, hook authority, and support weighting now lean toward a clearer type of trance record\n\n"
            + "Validation Report:\n"
            + f"- track_identity: {blueprint.get('track_identity', '')}\n"
            + f"- track_identity_description: {blueprint.get('track_identity_description', '')}\n"
            + f"- variation_type: {validation.get('variation_type', blueprint.get('variation_type', 'DEFAULT'))}\n"
            + f"- variation_behavior_summary: {validation.get('variation_behavior_summary', blueprint.get('variation_behavior_summary', ''))}\n"
            + f"- variation_enforcement_passed: {validation.get('variation_enforcement_passed', False)}\n"
            + f"- variation_enforcement_failed_checks: {validation.get('variation_enforcement_failed_checks', '')}\n"
            + f"- first16_arp_density: {validation.get('first16_arp_density', 0)}\n"
            + f"- first16_pluck_density: {validation.get('first16_pluck_density', 0)}\n"
            + f"- first16_supersaw_density: {validation.get('first16_supersaw_density', 0)}\n"
            + f"- breakdown_piano_density: {validation.get('breakdown_piano_density', 0)}\n"
            + f"- breakdown_strings_density: {validation.get('breakdown_strings_density', 0)}\n"
            + f"- breakdown_vocal_density: {validation.get('breakdown_vocal_density', 0)}\n"
            + f"- breakdown_focus_target: {validation.get('breakdown_focus_target', '')}\n"
            + f"- breakdown_identity_passed: {validation.get('breakdown_identity_passed', False)}\n"
            + f"- emotional_target: {blueprint.get('emotional_target', '')}\n"
            + f"- selected_chord_progression: {blueprint.get('selected_chord_progression', blueprint.get('progression_name', ''))}\n"
            + f"- identity_lead_style: {blueprint.get('identity_lead_style', '')}\n"
            + f"- identity_bass_style: {blueprint.get('identity_bass_style', '')}\n"
            + f"- identity_supersaw_style: {blueprint.get('identity_supersaw_style', '')}\n"
            + f"- identity_breakdown_style: {blueprint.get('identity_breakdown_style', '')}\n"
            + f"- identity_intro_style: {blueprint.get('identity_intro_style', '')}\n"
            + f"- identity_expression_score: {validation.get('identity_expression_score', 0)}\n"
            + f"- identity_failed_checks: {validation.get('identity_failed_checks', '')}\n"
            + f"- identity_contrast_score: {validation.get('identity_contrast_score', 0)}\n"
            + f"- identity_contrast_failed_checks: {validation.get('identity_contrast_failed_checks', '')}\n"
            + f"- identity_contrast_metrics: {validation.get('identity_contrast_metrics', '')}\n"
            + f"- arrangement_story_profile: {validation.get('arrangement_story_profile', blueprint.get('arrangement_story_name', ''))}\n"
            + f"- arrangement_story_description: {blueprint.get('arrangement_story_description', '')}\n"
            + f"- arrangement_story_score: {validation.get('arrangement_story_score', 0)}\n"
            + f"- arrangement_story_failed_checks: {validation.get('arrangement_story_failed_checks', '')}\n"
            + f"- arrangement_section_signature: {validation.get('arrangement_section_signature', '')}\n"
            + f"- arrangement_intro_instrumentation: {validation.get('arrangement_intro_instrumentation', '')}\n"
            + f"- arrangement_breakdown_instrumentation: {validation.get('arrangement_breakdown_instrumentation', '')}\n"
            + f"- arrangement_lead_entry_bar: {validation.get('arrangement_lead_entry_bar', 0)}\n"
            + f"- arrangement_arp_entry_bar: {validation.get('arrangement_arp_entry_bar', 0)}\n"
            + f"- arrangement_bass_entry_bar: {validation.get('arrangement_bass_entry_bar', 0)}\n"
            + f"- arrangement_drop1_start_bar: {validation.get('arrangement_drop1_start_bar', 0)}\n"
            + f"- arrangement_drop2_start_bar: {validation.get('arrangement_drop2_start_bar', 0)}\n"
            + f"- arrangement_first16_signature: {validation.get('arrangement_first16_signature', '')}\n"
            + f"- arrangement_breakdown_signature: {validation.get('arrangement_breakdown_signature', '')}\n"
            + f"- offbeat_bass_note_count: {validation.get('offbeat_bass_note_count', 0)}\n"
            + f"- rolling_bass_note_count: {validation.get('rolling_bass_note_count', 0)}\n"
            + f"- drop_offbeat_bass_note_count: {validation.get('drop_offbeat_bass_note_count', 0)}\n"
            + f"- drop_rolling_bass_note_count: {validation.get('drop_rolling_bass_note_count', 0)}\n"
            + f"- verse_build_offbeat_bass_note_count: {validation.get('verse_build_offbeat_bass_note_count', 0)}\n"
            + f"- bass_behavior_target: {validation.get('bass_behavior_target', '')}\n"
            + f"- bass_identity_passed: {validation.get('bass_identity_passed', False)}\n"
            + f"- bass_identity_failed_checks: {validation.get('bass_identity_failed_checks', '')}\n"
            + f"- lead_generation_mode: {validation.get('lead_generation_mode', 'hook_dominant')}\n"
            + f"- harmony_engine_mode: {validation.get('harmony_engine_mode', 'unified')}\n"
            + f"- lead_candidate_count: {validation.get('lead_candidate_count', 0)}\n"
            + f"- lead_selected_candidate_index: {validation.get('lead_selected_candidate_index', 0)}\n"
            + f"- lead_best_hook_score: {validation.get('lead_best_hook_score', 0)}\n"
            + f"- lead_hook_score: {validation.get('lead_hook_score', 0)}\n"
            + f"- lead_motif_score: {validation.get('lead_motif_score', 0)}\n"
            + f"- motif_repeat_score: {validation.get('motif_repeat_score', 0)}\n"
            + f"- motif_variation_score: {validation.get('motif_variation_score', 0)}\n"
            + f"- answer_phrase_lift: {validation.get('answer_phrase_lift', 0)}\n"
            + f"- payoff_strength: {validation.get('payoff_strength', 0)}\n"
            + f"- lead_avg_notes_per_bar: {validation.get('lead_avg_notes_per_bar', 0)}\n"
            + f"- lead_max_notes_per_bar: {validation.get('lead_max_notes_per_bar', 0)}\n"
            + f"- lead_long_note_count: {validation.get('lead_long_note_count', 0)}\n"
            + f"- lead_long_note_ratio: {validation.get('lead_long_note_ratio', 0)}\n"
            + f"- lead_short_note_removed_count: {validation.get('lead_short_note_removed_count', 0)}\n"
            + f"- lead_merged_note_count: {validation.get('lead_merged_note_count', 0)}\n"
            + f"- lead_avg_note_length: {validation.get('lead_avg_note_length', 0)}\n"
            + f"- lead_sustained_note_count: {validation.get('lead_sustained_note_count', 0)}\n"
            + f"- lead_sustain_passed: {validation.get('lead_sustain_passed', False)}\n"
            + f"- lead_payoff_note_length: {validation.get('lead_payoff_note_length', 0)}\n"
            + f"- lead_payoff_note_pitch: {validation.get('lead_payoff_note_pitch', 0)}\n"
            + f"- lead_payoff_is_highest_or_second_highest: {validation.get('lead_payoff_is_highest_or_second_highest', False)}\n"
            + f"- lead_payoff_resolves_to_root_or_third: {validation.get('lead_payoff_resolves_to_root_or_third', False)}\n"
            + f"- lead_motif_repeat_passed: {validation.get('lead_motif_repeat_passed', False)}\n"
            + f"- lead_motif_rhythm_signature: {validation.get('lead_motif_rhythm_signature', '')}\n"
            + f"- lead_variation_identity_passed: {validation.get('lead_variation_identity_passed', False)}\n"
            + f"- lead_hook_dominance_score: {validation.get('lead_hook_dominance_score', 0)}\n"
            + f"- lead_motif_pitch_changes: {validation.get('lead_motif_pitch_changes', 0)}\n"
            + f"- lead_first_half_pitch_spread: {validation.get('lead_first_half_pitch_spread', 0)}\n"
            + f"- lead_phrase_pitch_spread: {validation.get('lead_phrase_pitch_spread', 0)}\n"
            + f"- lead_expressive_jump_count: {validation.get('lead_expressive_jump_count', 0)}\n"
            + f"- lead_largest_upward_jump: {validation.get('lead_largest_upward_jump', 0)}\n"
            + f"- lead_pre_payoff_jump: {validation.get('lead_pre_payoff_jump', 0)}\n"
            + f"- lead_controlled_jump_passed: {validation.get('lead_controlled_jump_passed', False)}\n"
            + f"- lead_repairs_applied: {validation.get('lead_repairs_applied', 0)}\n"
            + f"- payoff_is_dominant: {validation.get('payoff_is_dominant', False)}\n"
            + f"- payoff_rank_in_phrase: {validation.get('payoff_rank_in_phrase', 0)}\n"
            + f"- payoff_velocity: {validation.get('payoff_velocity', 0)}\n"
            + f"- pre_payoff_gap: {validation.get('pre_payoff_gap', 0)}\n"
            + f"- lead_rhythmic_identity_score: {validation.get('lead_rhythmic_identity_score', 0)}\n"
            + f"- lead_register_arc_score: {validation.get('lead_register_arc_score', 0)}\n"
            + f"- lead_payoff_score: {validation.get('lead_payoff_score', 0)}\n"
            + f"- lead_supersaw_contrast_score: {validation.get('lead_supersaw_contrast_score', 0)}\n"
            + f"- lead_supersaw_cohesion_score: {validation.get('lead_supersaw_cohesion_score', 0)}\n"
            + f"- lead_supersaw_cohesion_passed: {validation.get('lead_supersaw_cohesion_passed', False)}\n"
            + f"- motif_supersaw_lock_applied: {validation.get('motif_supersaw_lock_applied', False)}\n"
            + f"- lead_motif_interval_identity_score: {validation.get('lead_motif_interval_identity_score', 0)}\n"
            + f"- lead_motif_interval_identity_passed: {validation.get('lead_motif_interval_identity_passed', False)}\n"
            + f"- anthem_payoff_score: {validation.get('anthem_payoff_score', 0)}\n"
            + f"- release_score: {validation.get('release_score', 0)}\n"
            + f"- dominance_score: {validation.get('dominance_score', 0)}\n"
            + f"- crowd_response_score: {validation.get('crowd_response_score', 0)}\n"
            + f"- lead_rhythm_contrast_passed: {validation.get('lead_rhythm_contrast_passed', False)}\n"
            + f"- lead_peak_moment_passed: {validation.get('lead_peak_moment_passed', False)}\n"
            + f"- drama_profile: {validation.get('drama_profile', '')}\n"
            + f"- surprise_moment_detected: {validation.get('surprise_moment_detected', False)}\n"
            + f"- counter_answer_mode: {validation.get('counter_answer_mode', blueprint.get('_selected_counter_answer_mode', ''))}\n"
            + f"- lead_candidate_rejections: {validation.get('lead_candidate_rejections', 0)}\n"
            + f"- lead_candidate_rejection_reasons: {validation.get('lead_candidate_rejection_reasons', '')}\n"
            + f"- hook_repetition_avoided: {validation.get('hook_repetition_avoided', 0)}\n"
            + f"- lead_phrase_regenerations: {validation.get('lead_phrase_regenerations', 0)}\n"
            + f"- lead_regenerations: {validation.get('lead_regenerations', 0)}\n"
            + f"- supersaw_energy_curve: {validation.get('supersaw_energy_curve', '')}\n"
            + f"- drop2_upgrade_score: {validation.get('drop2_upgrade_score', 0)}\n"
            + f"- supersaw_drop1_note_count: {validation.get('supersaw_drop1_note_count', 0)}\n"
            + f"- supersaw_drop2_note_count: {validation.get('supersaw_drop2_note_count', 0)}\n"
            + f"- supersaw_span_drop1: {validation.get('supersaw_span_drop1', 0)}\n"
            + f"- supersaw_span_drop2: {validation.get('supersaw_span_drop2', 0)}\n"
            + f"- supersaw_avg_length_drop1: {validation.get('supersaw_avg_length_drop1', 0)}\n"
            + f"- supersaw_avg_length_drop2: {validation.get('supersaw_avg_length_drop2', 0)}\n"
            + f"- supersaw_role_drop1: {validation.get('supersaw_role_drop1', 'controlled')}\n"
            + f"- supersaw_role_drop2: {validation.get('supersaw_role_drop2', 'expanded')}\n"
            + f"- supersaw_drop_energy_repaired: {validation.get('supersaw_drop_energy_repaired', False)}\n"
            + f"- supersaw_density_drop2: {validation.get('supersaw_density_drop2', 0)}\n"
            + f"- supersaw_note_count_per_chord: {validation.get('supersaw_note_count_per_chord', 0)}\n"
            + f"- supersaw_sustain_avg: {validation.get('supersaw_sustain_avg', 0)}\n"
            + f"- supersaw_weight_score: {validation.get('supersaw_weight_score', 0)}\n"
            + f"- supersaw_upper_ratio: {validation.get('supersaw_upper_ratio', 0)}\n"
            + f"- supersaw_pitch_spread: {validation.get('supersaw_pitch_spread', 0)}\n"
            + f"- supersaw_avg_pitch: {validation.get('supersaw_avg_pitch', 0)}\n"
            + f"- supersaw_voicing_score: {validation.get('supersaw_voicing_score', 0)}\n"
            + f"- supersaw_variation_count: {validation.get('supersaw_variation_count', 0)}\n"
            + f"- supersaw_overlap_ratio: {validation.get('supersaw_overlap_ratio', 0)}\n"
            + f"- supersaw_dynamic_score: {validation.get('supersaw_dynamic_score', 0)}\n"
            + f"- drop_harmony_valid: {validation.get('drop_harmony_valid', False)}\n"
            + f"- drop_harmony_issue_count: {validation.get('drop_harmony_issue_count', 0)}\n"
            + f"- lead_safe_tone_ratio: {validation.get('lead_safe_tone_ratio', 0)}\n"
            + f"- unsafe_peak_note_count: {validation.get('unsafe_peak_note_count', 0)}\n"
            + f"- supersaw_max_pitch: {validation.get('supersaw_max_pitch', 0)}\n"
            + f"- supersaw_register_repairs: {validation.get('supersaw_register_repairs', 0)}\n"
            + f"- lead_drop_density_repairs: {validation.get('lead_drop_density_repairs', 0)}\n"
            + f"- arp_activity_ratio: {validation.get('arp_activity_ratio', 0)}\n"
            + f"- arp_pattern_name: {validation.get('arp_pattern_name', '')}\n"
            + f"- arp_pattern_locked_bars: {validation.get('arp_pattern_locked_bars', 0)}\n"
            + f"- bar_harmonic_unity_score: {validation.get('bar_harmonic_unity_score', 0)}\n"
            + f"- lead_harmonic_alignment: {validation.get('lead_harmonic_alignment', 0)}\n"
            + f"- supersaw_harmonic_alignment: {validation.get('supersaw_harmonic_alignment', 0)}\n"
            + f"- arp_harmonic_alignment: {validation.get('arp_harmonic_alignment', 0)}\n"
            + f"- pad_harmonic_alignment: {validation.get('pad_harmonic_alignment', 0)}\n"
            + f"- strings_harmonic_alignment: {validation.get('strings_harmonic_alignment', 0)}\n"
            + f"- piano_harmonic_alignment: {validation.get('piano_harmonic_alignment', 0)}\n"
            + f"- pluck_harmonic_alignment: {validation.get('pluck_harmonic_alignment', 0)}\n"
            + f"- breakdown_engine_mode: {validation.get('breakdown_engine_mode', 'emotional_piano_strings')}\n"
            + f"- breakdown_piano_motif_score: {validation.get('breakdown_piano_motif_score', 0)}\n"
            + f"- breakdown_piano_space_score: {validation.get('breakdown_piano_space_score', 0)}\n"
            + f"- breakdown_piano_avg_notes_per_bar: {validation.get('breakdown_piano_avg_notes_per_bar', 0)}\n"
            + f"- breakdown_piano_long_note_count: {validation.get('breakdown_piano_long_note_count', 0)}\n"
            + f"- breakdown_strings_motion_score: {validation.get('breakdown_strings_motion_score', 0)}\n"
            + f"- breakdown_strings_velocity_curve: {validation.get('breakdown_strings_velocity_curve', '')}\n"
            + f"- breakdown_strings_register_span: {validation.get('breakdown_strings_register_span', 0)}\n"
            + f"- breakdown_tension_score: {validation.get('breakdown_tension_score', 0)}\n"
            + f"- breakdown_anchor_note_length: {validation.get('breakdown_anchor_note_length', 0)}\n"
            + f"- breakdown_anchor_pitch: {validation.get('breakdown_anchor_pitch', 0)}\n"
            + f"- breakdown_pre_anchor_silence: {validation.get('breakdown_pre_anchor_silence', 0)}\n"
            + f"- strings_rise_amount: {validation.get('strings_rise_amount', 0)}\n"
            + f"- breakdown_emotion_score: {validation.get('breakdown_emotion_score', 0)}\n"
            + f"- breakdown_simple_mode: {validation.get('breakdown_simple_mode', True)}\n"
            + f"- piano_note_count_avg: {validation.get('piano_note_count_avg', 0)}\n"
            + f"- piano_long_note_ratio: {validation.get('piano_long_note_ratio', 0)}\n"
            + f"- string_changes_count: {validation.get('string_changes_count', 0)}\n"
            + f"- emotional_anchor_present: {validation.get('emotional_anchor_present', False)}\n"
            + f"- breakdown_piano_jump_count: {validation.get('breakdown_piano_jump_count', 0)}\n"
            + f"- breakdown_repairs_applied: {validation.get('breakdown_repairs_applied', 0)}\n"
            + f"- snare_build_detected: {validation.get('snare_build_detected', False)}\n"
            + f"- snare_density_curve: {validation.get('snare_density_curve', '')}\n"
            + f"- snare_velocity_curve: {validation.get('snare_velocity_curve', '')}\n"
            + f"- snare_final_fill_present: {validation.get('snare_final_fill_present', False)}\n"
            + f"- drop1_vs_drop2_density_ratio: {validation.get('drop1_vs_drop2_density_ratio', 0)}\n"
            + f"- drop1_avg_note_length: {validation.get('drop1_avg_note_length', 0)}\n"
            + f"- drop1_supersaw_span: {validation.get('drop1_supersaw_span', 0)}\n"
            + f"- drop_balance_score: {validation.get('drop_balance_score', 0)}\n"
            + f"- drop1_impact_score: {validation.get('drop1_impact_score', 0)}\n"
            + f"- drop1_first_hit_density: {validation.get('drop1_first_hit_density', 0)}\n"
            + f"- drop1_lead_entry_type: {validation.get('drop1_lead_entry_type', '')}\n"
            + f"- drop1_has_gap: {validation.get('drop1_has_gap', False)}\n"
            + f"- drop1_hook_note_count: {validation.get('drop1_hook_note_count', 0)}\n"
            + f"- drop1_hook_avg_length: {validation.get('drop1_hook_avg_length', 0)}\n"
            + f"- drop1_hook_repeat_score: {validation.get('drop1_hook_repeat_score', 0)}\n"
            + f"- drop1_hook_strength: {validation.get('drop1_hook_strength', 0)}\n"
            + f"- hook_note_count: {validation.get('hook_note_count', 0)}\n"
            + f"- hook_avg_length: {validation.get('hook_avg_length', 0)}\n"
            + f"- hook_repeat_usage: {validation.get('hook_repeat_usage', 0)}\n"
            + f"- hook_sections_applied: {validation.get('hook_sections_applied', '')}\n"
            + f"- hook_strength_score: {validation.get('hook_strength_score', 0)}\n"
            + f"- hook_interval_jump: {validation.get('hook_interval_jump', 0)}\n"
            + f"- hook_peak_note: {validation.get('hook_peak_note', 0)}\n"
            + f"- hook_range: {validation.get('hook_range', 0)}\n"
            + f"- hook_emotion_score: {validation.get('hook_emotion_score', 0)}\n"
            + f"- hook_peak_length: {validation.get('hook_peak_length', 0)}\n"
            + f"- hook_pre_peak_silence: {validation.get('hook_pre_peak_silence', 0)}\n"
            + f"- hook_peak_emphasis_score: {validation.get('hook_peak_emphasis_score', 0)}\n"
            + f"- hook_dominance_ratio: {validation.get('hook_dominance_ratio', 0)}\n"
            + f"- hook_candidates_generated: {validation.get('hook_candidates_generated', 0)}\n"
            + f"- hook_selected_score: {validation.get('hook_selected_score', 0)}\n"
            + f"- hook_variation_type: {validation.get('hook_variation_type', '')}\n"
            + f"- global_note_cleanup_removed: {validation.get('global_note_cleanup_removed', 0)}\n"
            + f"- global_note_cleanup_extended: {validation.get('global_note_cleanup_extended', 0)}\n"
            + f"- global_melodic_avg_note_length: {validation.get('global_melodic_avg_note_length', 0)}\n"
            + f"- harmony_repairs_applied: {validation.get('harmony_repairs_applied', 0)}\n"
            + f"- arp_density_rejections: {validation.get('arp_density_rejections', 0)}\n"
            + f"- pluck_density_rejections: {validation.get('pluck_density_rejections', 0)}\n"
            + f"- arp_pluck_overlap_corrections: {validation.get('arp_pluck_overlap_corrections', 0)}\n"
            + f"- drop_budget_corrections: {validation.get('drop_budget_corrections', 0)}\n"
            + f"- support_budget_corrections: {validation.get('support_budget_corrections', 0)}\n"
            + f"- countermelody_score: {validation.get('countermelody_score', 0)}\n"
            + f"- counter_answer_strength: {validation.get('counter_answer_strength', 0)}\n"
            + f"- countermelody_strength_applied: {validation.get('countermelody_strength_applied', 0)}\n"
            + f"- section_contrast_score: {validation.get('section_contrast_score', 0)}\n"
            + f"- flatness_corrections: {validation.get('flatness_corrections', 0)}\n"
            + f"- top_end_density_corrections: {validation.get('top_end_density_corrections', 0)}\n\n"
            + f"{ADVISOR_UI_VERSION} Advisor Dashboard Export:\n"
            + "- web app result page now offers Download ZIP and Open Advisor Dashboard actions\n"
            + "- /advisor renders a context-aware dashboard from the latest plugin_recommendations.json\n"
            + "- stem cards now adapt sound-design advice to genre, identity, variation, MIDI behaviour, and mix context\n"
            + "- role badges classify stems as Main Focus, Support, Release Layer, Foundation, Atmosphere, Rhythmic Motion, or Transition Tension\n"
            + "- Technical Analysis tab exposes arrangement_role, role_reason, dominance_level, and sound_design_intensity\n"
            + "- production_quick_start.txt: 30-second setup path for getting sounds loaded fast\n"
            + "- production_advice.txt: clean producer-facing stem cards\n"
            + "- technical_midi_analysis.txt: dense MIDI metrics and warnings moved out of the main advice file\n"
            + "- plugin_recommendations.json: unchanged machine-readable detailed recommendations\n\n"
            + f"{APP_VERSION} Build Notes:\n"
            + "Composition Identity and Variation Engine:\n"
            + f"- track_identity: {blueprint.get('track_identity', '')}\n"
            + f"- identity_description: {blueprint.get('track_identity_description', '')}\n"
            + f"- emotional_target: {blueprint.get('emotional_target', '')}\n"
            + f"- intro_behavior: {blueprint.get('identity_intro_style', '')}\n"
            + f"- bass_behavior: {blueprint.get('identity_bass_style', '')}\n"
            + f"- lead_behavior: {blueprint.get('identity_lead_style', '')}\n"
            + f"- hook_shape: {blueprint.get('identity_hook_shape', '')}\n"
            + f"- supersaw_behavior: {blueprint.get('identity_supersaw_style', '')}\n"
            + f"- arp_behavior: {blueprint.get('identity_arp_style', '')}\n"
            + f"- pluck_behavior: {blueprint.get('identity_pluck_style', '')}\n"
            + f"- breakdown_behavior: {blueprint.get('identity_breakdown_style', '')}\n"
            + f"- drum_build_behavior: {blueprint.get('identity_drum_build_style', '')}\n"
            + f"- drop_behavior: {blueprint.get('identity_drop_style', '')}\n\n"
            + f"- macro_journey_profile: {blueprint['macro_journey_profile']}\n"
            + f"- section_weight_profile: {blueprint['section_weight_profile']}\n"
            + f"- drop_pair_profile: {blueprint['drop_pair_profile']}\n"
            + f"- drop1_role: {drop_section_role(blueprint, False)}\n"
            + f"- drop2_role: {drop_section_role(blueprint, True)}\n"
            + f"- breakdown_function: {blueprint['breakdown_function']}\n"
            + f"- final_lift_profile: {blueprint['final_lift_profile']}\n"
            + f"- arrangement_density_profile: {blueprint['arrangement_density_profile']}\n"
            + f"- groove_variation_profile: {blueprint['groove_variation_profile']}\n"
            + f"- opening_scene: {blueprint['opening_scene']}\n"
            + f"- lead_evolution_profile: {blueprint['lead_evolution_profile']}\n"
            + f"- countermelody_engine: {blueprint['countermelody_engine']}\n"
            + f"- drop_layer_budget: {blueprint['drop_layer_budget']}\n"
            + "- Track 08 Supersaw Chords now treats Drop 1 as controlled and Drop 2 as expanded\n"
            + "- Drop 2 supersaw voicing doubles chord tones across octaves, adds subtle low-root reinforcement, and enforces a wider register span\n"
            + "- Drop 2 supersaw rhythm uses two chord hits per bar with longer sustain, while Drop 1 stays as one controlled hit per bar\n"
            + "- Track 07 Lead now prioritizes two-note motif bars, exact rhythm repetition, higher lift bars, and one-note payoff bars\n"
            + "- bars 1-4 now commit to A A A A so the hook is obvious, repetitive, and easier to remember\n"
            + "- bars 5-8 now allow one controlled expressive lift jump while keeping the first motif mostly stepwise\n"
            + "- lead durations now remove sub-0.75 drop notes, merge close adjacent notes, and enforce a 60 percent long-note ratio before export\n"
            + "- payoff notes are forced longer, louder, and resolving, with a hard lead ceiling so the hook stays emotional instead of shrill\n"
            + "- one payoff note per 8-bar phrase is now forced to outrank competing pre-payoff notes by pitch rank, length, velocity, and a short setup gap\n"
            + "- lead validation now reports motif repeat, variation identity, payoff pitch, payoff length, and hook dominance from the actual exported phrase\n\n"
            + "Supporting Identity Layers:\n"
            + f"- archetype_bass_grammar: {blueprint['archetype_bass_grammar']}\n"
            + f"- archetype_drum_grammar: {blueprint['archetype_drum_grammar']}\n"
            + f"- archetype_breakdown_focus: {blueprint['archetype_breakdown_focus']}\n"
            + f"- archetype_topline_density: {blueprint['archetype_topline_density']}\n"
            + "- sibling renders should still separate by groove, breakdown framing, and density while sharing the new unified harmonic language\n\n"
            + "Support Separation Layer:\n"
            + f"- archetype_support_timing: {blueprint['archetype_support_timing']}\n"
            + f"- archetype_harmony_emphasis: {blueprint['archetype_harmony_emphasis']}\n"
            + f"- archetype_counter_grammar: {blueprint['archetype_counter_grammar']}\n"
            + "- drums, piano, strings, and counter-response timing still separate supporting behaviors between sibling renders\n\n"
            + "Micro Variation Layer:\n"
            + f"- archetype_supersaw_motion: {blueprint['archetype_supersaw_motion']}\n"
            + f"- archetype_drum_micro: {blueprint['archetype_drum_micro']}\n"
            + f"- archetype_counter_contour: {blueprint['archetype_counter_contour']}\n"
            + "- supersaw motion, drum micro-shape, and counter contour still provide intra-archetype variation around the new unified harmony engine\n\n"
            + "Support Voice Layer:\n"
            + f"- archetype_arp_grammar: {blueprint['archetype_arp_grammar']}\n"
            + f"- archetype_pluck_grammar: {blueprint['archetype_pluck_grammar']}\n"
            + f"- archetype_counter_presence: {blueprint['archetype_counter_presence']}\n"
            + "- arp restraint, pluck role, and counter presence still shape how much spotlight the hook receives\n\n"
            + "Countermelody Focus Layer:\n"
            + f"- archetype_counter_span: {blueprint['archetype_counter_span']}\n"
            + f"- archetype_counter_register: {blueprint['archetype_counter_register']}\n"
            + f"- archetype_counter_role: {blueprint['archetype_counter_role']}\n"
            + "- countermelody still separates by phrase length, register lane, and spotlight behavior, now with a stronger answer-first role in Drop 2\n\n"
            + "Arrangement Identity Engine:\n"
            + f"- chord_style: {blueprint['chord_style']}\n"
            + f"- arp_style: {blueprint['arp_style']}\n"
            + f"- bass_style: {blueprint['bass_style']}\n"
            + "- sub_bass stem: enabled\n"
            + f"- drum_style: {blueprint['drum_style']}\n"
            + f"- variant_kick_phrase: {blueprint['variant_kick_phrase']}\n"
            + f"- variant_verse_drum_entry: {blueprint['variant_verse_drum_entry']}\n"
            + f"- variant_clap_pattern: {blueprint['variant_clap_pattern']}\n"
            + f"- variant_hat_grid: {blueprint['variant_hat_grid']}\n"
            + f"- breakdown_style: {blueprint['breakdown_style']}\n"
            + f"- energy_profile: {blueprint['energy_profile']}\n\n"
            + "Progression Harmonic Profile:\n"
            + f"- progression_name: {blueprint.get('progression_name', '')}\n"
            + f"- progression_family: {blueprint['progression_family']}\n"
            + f"- voicing_profile: {blueprint['voicing_profile']}\n"
            + f"- cadence_profile: {blueprint['cadence_profile']}\n"
            + f"- breakdown_emotion: {blueprint['breakdown_emotion']}\n"
            + f"- drop_harmony_entry: {blueprint['drop_harmony_entry']}\n"
            + f"- lead_resolution_bias: {blueprint['lead_resolution_bias']}\n\n"
            + "Lead-Vocal Interaction Engine:\n"
            + f"- lead_vocal_relationship: {blueprint['lead_vocal_relationship']}\n"
            + "- hook ownership can shift between breakdown, build, and drop\n"
            + "- relationship mode now changes phrase timing and top-line ownership more explicitly\n"
            + "- countermelody yields more aggressively when the main hook needs space\n"
            + "- drop vocal echoes and shared-hook phrasing are structurally stronger\n\n"
            + "Arrangement-Wide Hook Framing Engine:\n"
            + "- support layers now react to hook ownership instead of staying fixed under every moment\n"
            + "- supersaw, pad, strings, arp, bass, and drums can switch between support, shadow, response, and silence\n"
            + "- lead-owned phrases hold more air before chord bloom, while vocal-owned phrases thin the arrangement more decisively\n"
            + "- response windows now let the arrangement answer after the hook instead of masking it during the statement\n\n"
            + "V4.3.1 Targeted Tightening:\n"
            + "- supersaw entry and bloom timing now respond more strongly to progression family and cadence profile\n"
            + "- countermelody branches later, earlier, warmer, or more suspended depending on progression feel\n"
            + "- support-layer response timing now shifts more decisively with progression and hook ownership\n"
            + "- classic, lifted, festival, hopeful, and progressive tracks should now separate more clearly in support behavior\n\n"
            + "V4.3.2 Supersaw Identity Layer:\n"
            + f"- supersaw_identity: {blueprint['supersaw_identity']}\n"
            + "- supersaw now uses authored stack families instead of one mostly shared chord wall\n"
            + "- pulse, bloom, wall, and octave-shine modes change voicing shape as well as onset timing\n"
            + "- drop support should now separate more clearly even when other support layers stay close\n\n"
            + "V4.3.3 Within-Identity Supersaw Variation:\n"
            + f"- supersaw_pulse_variant: {blueprint['supersaw_pulse_variant']}\n"
            + f"- supersaw_bloom_variant: {blueprint['supersaw_bloom_variant']}\n"
            + f"- supersaw_inversion_variant: {blueprint['supersaw_inversion_variant']}\n"
            + f"- supersaw_response_variant: {blueprint['supersaw_response_variant']}\n"
            + "- repeated supersaw identities should now vary internally instead of collapsing into one support shape\n\n"
            + "Song Archetypes:\n"
            + f"- lead_archetype: {blueprint['lead_archetype']}\n"
            + f"- vocal_archetype: {blueprint['vocal_archetype']}\n"
            + f"- countermelody_style: {blueprint['countermelody_style']}\n"
            + f"- bass_motion_profile: {blueprint['bass_motion_profile']}\n"
            + f"- drop_arrival_style: {blueprint['drop_arrival_style']}\n"
            + f"- breakdown_narrative: {blueprint['breakdown_narrative']}\n\n"
            + "Hook Recall Engine:\n"
            + f"- hook_recall_style: {blueprint['hook_recall_style']}\n"
            + f"- theme_anchor_degree: {blueprint['theme_anchor_degree']}\n"
            + f"- callback_density: {blueprint['callback_density']}\n\n"
            + "Production Framing Layer:\n"
            + f"- transition_intent: {blueprint['transition_intent']}\n"
            + "- spotlight hierarchy frames lead, vocal, harmony, and groove importance per phrase\n"
            + "- support layers can thin out before major hook moments and transition bars\n"
            + "- supersaw and offbeat bass now vary more around payoff and release moments\n\n"
            + "Per-Window Hook Candidate Breakdown:\n"
            + ("\n".join(candidate_window_lines) + "\n\n" if candidate_window_lines else "- none\n\n")
            + "Phrase Evolution Layer:\n"
            + "- bars 1-4 establish and repeat\n"
            + "- bars 5-6 develop\n"
            + "- bar 7 lifts\n"
            + "- bar 8 transitions\n\n"
            + "V4.1 Recall Targets:\n"
            + "- breakdown callback or interval memory\n"
            + "- late-build foreshadow before the drop\n"
            + "- Drop 2 thematic deepening through support layers\n"
            + "- countermelody and vocal tied back to the hook fragment\n\n"
            + "Sections:\n"
            + "\n".join(f"- {section['name']}: bars {section['start_bar'] + 1}-{section['end_bar']}" for section in sections)
            + "\n"
        )
        stem_analysis = analyze_exported_midi_stems(tracks)
        production_quick_start_path = td / "production_quick_start.txt"
        production_advice_path = td / "production_advice.txt"
        technical_midi_analysis_path = td / "technical_midi_analysis.txt"
        technical_midi_analysis_json_path = td / "technical_midi_analysis.json"
        ableton_setup_path = td / "ableton_setup_guide.txt"
        plugin_recommendations_path = td / "plugin_recommendations.json"
        motif_story_path = td / "motif_story.json"
        production_quick_start_path.write_text(build_production_quick_start_text(stem_analysis, blueprint, sections, bpm))
        production_advice_path.write_text(build_production_advice_text(stem_analysis, blueprint, sections))
        technical_midi_analysis_path.write_text(build_technical_midi_analysis_text(stem_analysis, blueprint, sections))
        technical_midi_analysis_json_path.write_text(json.dumps({"build": APP_VERSION, "stem_analysis": stem_analysis}, indent=2))
        ableton_setup_path.write_text(build_ableton_setup_guide(stem_analysis, bpm, sections, blueprint))
        plugin_recommendations = build_plugin_recommendations(stem_analysis, blueprint, bpm=bpm)
        plugin_recommendations_path.write_text(json.dumps(plugin_recommendations, indent=2))
        motif_story_path.write_text(json.dumps(blueprint.get("v11_motif_story", {}), indent=2))
        persist_latest_advisor(plugin_recommendations)

        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(arrangement_path, arrangement_path.name)
            archive.write(notes_path, notes_path.name)
            archive.write(production_quick_start_path, production_quick_start_path.name)
            archive.write(production_advice_path, production_advice_path.name)
            archive.write(technical_midi_analysis_path, technical_midi_analysis_path.name)
            archive.write(technical_midi_analysis_json_path, technical_midi_analysis_json_path.name)
            archive.write(ableton_setup_path, ableton_setup_path.name)
            archive.write(plugin_recommendations_path, plugin_recommendations_path.name)
            archive.write(motif_story_path, motif_story_path.name)
            for stem in STEMS:
                export_name = STEM_EXPORT_LABELS.get(stem, stem)
                archive.write(td / f"{export_name}.mid", f"stems/{export_name}.mid")
    finally:
        shutil.rmtree(td, ignore_errors=True)


MELODY_LAB_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>EDM MIDI Idea Lab - Dream Trance Generator __APP_VERSION__</title>
  <style>
    :root {
      --bg: #081018;
      --panel: rgba(14, 22, 32, 0.96);
      --panel-2: rgba(24, 31, 43, 0.94);
      --line: rgba(190, 208, 226, 0.18);
      --text: #f4f7fb;
      --muted: #bbc7d4;
      --accent: #74d6ff;
      --accent-2: #ffd073;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      font-family: Arial, Helvetica, sans-serif;
      background: linear-gradient(150deg, #081018 0%, #14202c 54%, #2a2230 100%);
    }
    .shell { max-width: 1280px; margin: 0 auto; padding: 28px; }
    .top { display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; margin-bottom: 22px; }
    h1 { margin: 0 0 10px; font-size: clamp(28px, 4vw, 54px); line-height: 1; letter-spacing: 0; }
    h2, h3 { margin-top: 0; }
    p { color: var(--muted); line-height: 1.55; }
    a { color: var(--accent); }
    .panel, .type {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 22px;
      box-shadow: 0 16px 36px rgba(0,0,0,0.28);
    }
    .layout { display: grid; grid-template-columns: minmax(0, 1fr) 390px; gap: 18px; }
    .grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
    .field { display: flex; flex-direction: column; gap: 8px; }
    label { font-weight: 700; font-size: 14px; }
    input, select {
      width: 100%;
      border: 1px solid rgba(255,255,255,0.12);
      background: rgba(3, 8, 14, 0.75);
      color: var(--text);
      border-radius: 8px;
      padding: 13px;
      font-size: 15px;
    }
    .actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 18px; }
    button, .button {
      border: 0;
      border-radius: 8px;
      padding: 14px 18px;
      font-weight: 800;
      text-decoration: none;
      cursor: pointer;
    }
    .primary { background: linear-gradient(135deg, var(--accent), var(--accent-2)); color: #071019; }
    .secondary { background: rgba(255,255,255,0.07); color: var(--text); }
    .types { display: grid; gap: 12px; }
    .type { background: var(--panel-2); }
    .type strong { display: block; margin-bottom: 6px; }
    .result { margin-bottom: 18px; border-color: rgba(116, 214, 255, 0.45); }
    .preview-grid { display: grid; gap: 16px; margin-bottom: 20px; }
    .option-card { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 20px; }
    .meta { display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0 14px; }
    .pill { background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.08); border-radius: 999px; padding: 6px 10px; color: var(--muted); font-size: 13px; }
    .section-preview { border-top: 1px solid var(--line); padding-top: 12px; margin-top: 12px; }
    .progression { color: var(--accent-2); font-weight: 800; }
    .notes { color: var(--muted); font-size: 13px; line-height: 1.45; }
    .wide { grid-column: 1 / -1; }
    @media (max-width: 880px) {
      .top, .layout, .grid { grid-template-columns: 1fr; display: grid; }
      .shell { padding: 16px; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <section class="top">
      <div>
        <h1>EDM MIDI Idea Lab</h1>
        <p>Generate three producer-focused trance and melodic EDM MIDI ideas with section-aware chords, hooks, bass roots, and optional arpeggio/pluck tracks.</p>
      </div>
      <a class="button secondary" href="/">Full Pack Generator</a>
    </section>
    __RESULT__
    <section class="layout">
      <form class="panel" method="post" action="/melody-lab/generate">
        <h2>Generator Controls</h2>
        <div class="grid">
          <div class="field">
            <label for="bpm">BPM</label>
            <input id="bpm" name="bpm" type="number" min="120" max="150" value="138">
          </div>
          <div class="field">
            <label for="key">Key</label>
            <select id="key" name="key">__KEYS__</select>
          </div>
          <div class="field">
            <label for="scale">Scale / Mode</label>
            <select id="scale" name="scale">__SCALES__</select>
          </div>
          <div class="field">
            <label for="genre">Trance / EDM Type</label>
            <select id="genre" name="genre">__GENRES__</select>
          </div>
          <div class="field">
            <label for="generation_type">MIDI Generation Type</label>
            <select id="generation_type" name="generation_type">__GENERATION_TYPES__</select>
          </div>
          <div class="field">
            <label for="arrangement_section">Arrangement Section</label>
            <select id="arrangement_section" name="arrangement_section">__SECTIONS__</select>
          </div>
          <div class="field">
            <label for="bars">Length</label>
            <select id="bars" name="bars">
              <option value="4">4 bars</option>
              <option value="8">8 bars</option>
              <option value="16" selected>16 bars</option>
              <option value="32">32 bars</option>
            </select>
          </div>
          <div class="field">
            <label for="length_mode">Length Mode</label>
            <select id="length_mode" name="length_mode">
              <option value="per_section" selected>Bars per section</option>
              <option value="total_arrangement">Total arrangement</option>
            </select>
          </div>
          <div class="field">
            <label for="include_arpeggio_pluck">Arpeggio / Pluck</label>
            <select id="include_arpeggio_pluck" name="include_arpeggio_pluck">
              <option value="true" selected>Enabled</option>
              <option value="false">Disabled</option>
            </select>
          </div>
          <div class="field">
            <label for="complexity">Complexity</label>
            <select id="complexity" name="complexity">__COMPLEXITIES__</select>
          </div>
          <div class="field">
            <label for="energy">Energy Level</label>
            <select id="energy" name="energy">__ENERGIES__</select>
          </div>
          <div class="field wide">
            <label for="creative_risk">Creative Risk</label>
            <select id="creative_risk" name="creative_risk">__RISKS__</select>
          </div>
          <div class="field wide">
            <label for="audition_depth">Hook Audition Depth</label>
            <select id="audition_depth" name="audition_depth">
              <option value="draft">Draft - 3 candidates</option>
              <option value="balanced" selected>Balanced - 8 to 12 candidates</option>
              <option value="deep">Deep search - 20 to 32 candidates</option>
            </select>
          </div>
          <input type="hidden" id="regenerate_mode" name="regenerate_mode" value="full_option">
          <input type="hidden" id="variation_seed" name="variation_seed" value="0">
        </div>
        <div class="actions">
          <button class="primary" type="submit">Generate 3 Options</button>
          <button class="secondary" type="reset">Reset</button>
        </div>
      </form>
      <aside class="types">
        <div class="type"><strong>Option 1: Classic / Reliable</strong><p>Safe trance movement, clear chord tones, strong resolutions, and DAW-ready sections.</p></div>
        <div class="type"><strong>Option 2: Emotional / Cinematic</strong><p>Suspensions, richer voicings, expressive phrase endings, and breakdown-friendly identity.</p></div>
        <div class="type"><strong>Option 3: Experimental / Outside-the-Box</strong><p>Borrowed colour, rhythmic displacement, add9/sus/m9 flavours, and controlled tension.</p></div>
      </aside>
    </section>
  </main>
</body>
</html>
"""


def select_options(values, default_value):
    return "".join(
        f'<option value="{value}"{" selected" if value == default_value else ""}>{label}</option>'
        for value, label in values
    )


def melody_lab_page(result_html: str = "", playback_json: str = "[]") -> str:
    key_options = "".join(
        f'<option value="{key}"{" selected" if key == "F# minor" else ""}>{key}</option>'
        for key in EDM_KEY_OPTIONS
    )
    page_html = (
        MELODY_LAB_HTML
        .replace("__APP_VERSION__", APP_VERSION)
        .replace("__KEYS__", key_options)
        .replace("__SCALES__", select_options(MODE_LABELS.items(), "natural_minor"))
        .replace("__GENRES__", select_options(GENRE_LABELS.items(), "uplifting_trance"))
        .replace("__GENERATION_TYPES__", select_options(GENERATION_LABELS.items(), "full_section_sketch"))
        .replace("__SECTIONS__", select_options(SECTION_LABELS.items(), "full"))
        .replace("__COMPLEXITIES__", select_options(COMPLEXITY_LABELS.items(), "medium"))
        .replace("__ENERGIES__", select_options(ENERGY_LABELS.items(), "emotional"))
        .replace("__RISKS__", select_options(RISK_LABELS.items(), "club_ready"))
        .replace("__RESULT__", result_html)
    )
    audition_script = f"""
<script>
window.ideaLabPlayback = {playback_json};
let ideaAudioContext = null;
let ideaStopHandles = [];
function stopIdeaPlayback() {{
  ideaStopHandles.forEach(handle => clearTimeout(handle));
  ideaStopHandles = [];
  if (ideaAudioContext) {{
    ideaAudioContext.close();
    ideaAudioContext = null;
  }}
}}
function playTone(ctx, pitch, startTime, duration, gainValue) {{
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "sawtooth";
  osc.frequency.value = 440 * Math.pow(2, (pitch - 69) / 12);
  gain.gain.setValueAtTime(0.0001, startTime);
  gain.gain.exponentialRampToValueAtTime(gainValue, startTime + 0.015);
  gain.gain.exponentialRampToValueAtTime(0.0001, startTime + Math.max(0.05, duration));
  osc.connect(gain).connect(ctx.destination);
  osc.start(startTime);
  osc.stop(startTime + Math.max(0.08, duration));
}}
function playIdeaOption(optionIndex, trackName) {{
  stopIdeaPlayback();
  const payload = window.ideaLabPlayback && window.ideaLabPlayback[optionIndex];
  if (!payload) return;
  ideaAudioContext = new (window.AudioContext || window.webkitAudioContext)();
  const ctx = ideaAudioContext;
  const tracks = trackName === "full" ? ["melody", "chords", "bass", "arp"] : [trackName];
  tracks.forEach(track => {{
    (payload[track] || []).forEach(event => {{
      const startTime = ctx.currentTime + 0.05 + event.time;
      const duration = Math.max(0.06, event.duration);
      const notes = Array.isArray(event.notes) ? event.notes : [event.note];
      notes.forEach(note => playTone(ctx, note, startTime, duration, track === "bass" ? 0.08 : track === "chords" ? 0.045 : 0.07));
    }});
  }});
}}
function regenerateIdea(mode) {{
  const modeInput = document.getElementById("regenerate_mode");
  const seedInput = document.getElementById("variation_seed");
  if (modeInput) modeInput.value = mode;
  if (seedInput) seedInput.value = String(Date.now() % 1000000);
  const form = document.querySelector('form[action="/melody-lab/generate"]');
  if (form) form.submit();
}}
</script>
"""
    return page_html.replace("</body>", audition_script + "\n</body>")


def event_seconds(event, bpm):
    beat_seconds = 60.0 / max(1, bpm)
    return round((event["start"] / 480) * beat_seconds, 4), round((event["duration"] / 480) * beat_seconds, 4)


def playback_payload(result):
    payload = []
    for option in result.options:
        option_payload = {"melody": [], "chords": [], "bass": [], "arp": []}
        for section in option.sections:
            for event in section.melody_events:
                start, duration = event_seconds(event, option.bpm)
                option_payload["melody"].append({"time": start, "duration": duration, "note": event["note"]})
            for event in section.chord_events:
                start, duration = event_seconds(event, option.bpm)
                option_payload["chords"].append({"time": start, "duration": min(duration, 2.0), "notes": event["notes"]})
            for event in section.bass_events:
                start, duration = event_seconds(event, option.bpm)
                option_payload["bass"].append({"time": start, "duration": min(duration, 0.5), "note": event["note"]})
            for event in section.arp_events:
                start, duration = event_seconds(event, option.bpm)
                option_payload["arp"].append({"time": start, "duration": duration, "note": event["note"]})
        payload.append(option_payload)
    return payload


def zip_export_summary(file_path: Path):
    with zipfile.ZipFile(file_path) as archive:
        names = archive.namelist()
        manifest = json.loads(archive.read("preview_manifest.json"))
        validation = json.loads(archive.read("validation_report.json"))
        midi_count = sum(1 for name in names if name.endswith(".mid"))
        sections = manifest["options"][0]["sections"] if manifest.get("options") else []
        return {
            "export_schema_version": manifest.get("export_schema_version", "unknown"),
            "backend_build_marker": manifest.get("backend_build_marker", "unknown"),
            "midi_count": midi_count,
            "total_file_count": len(names),
            "validation_passed": bool(validation.get("passed")),
            "arrangement_length_bars": manifest.get("arrangement_length_bars", 0),
            "section_ranges": [(section["name"], section["arrangement_bar_range"]) for section in sections],
        }


def render_export_proof(export_summary):
    if not export_summary:
        return ""
    section_lines = "<br>".join(
        f'{name}: {bar_range}'
        for name, bar_range in export_summary["section_ranges"]
    )
    return (
        '<div class="section-preview">'
        '<h3>Export proof</h3>'
        f'<p class="notes">Export schema: {export_summary["export_schema_version"]}<br>'
        f'Backend marker: {export_summary["backend_build_marker"]}<br>'
        f'MIDI files: {export_summary["midi_count"]}<br>'
        f'Total files: {export_summary["total_file_count"]}<br>'
        f'Validation: {"passed" if export_summary["validation_passed"] else "failed"}<br>'
        f'Arrangement: {export_summary["arrangement_length_bars"]} bars<br>'
        f'{section_lines}</p>'
        '</div>'
    )


def render_option_preview(result, download_href: str, download_filename: str = "edm_trance_idea_pack.zip", export_summary=None):
    cards = []
    for option in result.options:
        preview = option_preview_dict(option)
        section_html = []
        for section in preview["sections"]:
            notes = "<br>".join(section["notes"])
            section_html.append(
                '<div class="section-preview">'
                f'<h3>{section["name"]} <span class="pill">Arrangement bars {section["arrangement_bar_range"]}</span></h3>'
                f'<p class="progression">{" - ".join(section["chords"])}</p>'
                f'<p>Section length: {section["section_length_bars"]} bars | Local bars: {section["local_bar_range"]} | Energy: {section["energy"]}</p>'
                f'<p class="notes">Start tick: {section["start_tick"]} | End tick: {section["end_tick"]} | Arpeggio: {"enabled" if section["arpeggio_enabled"] else "disabled"}</p>'
                f'<p>Roman: {" - ".join(section["roman"])}</p>'
                f'<p>{section["motif_summary"]}</p>'
                f'<p class="notes">{notes}</p>'
                '</div>'
            )
        cards.append(
            '<article class="option-card">'
            f'<h2>{preview["name"]}</h2>'
            f'<p>{option.purpose}</p>'
            '<div class="meta">'
            f'<span class="pill">{preview["key"]}</span>'
            f'<span class="pill">{preview["scale"]}</span>'
            f'<span class="pill">{preview["bpm"]} BPM</span>'
            f'<span class="pill">{preview["genre"]}</span>'
            f'<span class="pill">{preview["generation_type"]}</span>'
            '</div>'
            f'<p>Creative risk: {preview["creative_risk_description"]}. Energy: {preview["energy_description"]}.</p>'
            f'<p><strong>Melody:</strong> {preview["hook_summary"]}</p>'
            f'<p class="notes">Core motif notes: {", ".join(preview["core_motif_notes"])}<br>'
            f'Core rhythm beats: {", ".join(str(beat) for beat in preview["core_motif_rhythm"])}<br>'
            f'Phrase structure: {preview["phrase_structure"]}<br>'
            f'Strongest hook bar: {preview["strongest_hook_bar"]} | Hook Score: {preview["melody_strength_score"]}/100<br>'
            f'Candidates tested: {preview["candidates_generated"]} | Rejected: {preview["candidates_rejected"]} | Threshold: {preview["hook_threshold"]} | Met: {"Yes" if preview["threshold_met"] else "No"}<br>'
            f'{preview["selected_reason"]}<br>'
            f'Motif clarity: {preview["hook_subscores"]["motif_clarity"]}, Rhythm: {preview["hook_subscores"]["rhythmic_identity"]}, '
            f'Singability: {preview["hook_subscores"]["singability"]}, Chord targeting: {preview["hook_subscores"]["chord_tone_targeting"]}, '
            f'Phrase shape: {preview["hook_subscores"]["phrase_shape"]}, Repetition/variation: {preview["hook_subscores"]["repetition_variation"]}, '
            f'EDM suitability: {preview["hook_subscores"]["edm_suitability"]}</p>'
            '<div class="actions">'
            f'<button class="secondary" type="button" onclick="playIdeaOption({len(cards)}, \'full\')">Play Full</button>'
            f'<button class="secondary" type="button" onclick="playIdeaOption({len(cards)}, \'melody\')">Play Melody</button>'
            f'<button class="secondary" type="button" onclick="playIdeaOption({len(cards)}, \'chords\')">Play Chords</button>'
            f'<button class="secondary" type="button" onclick="playIdeaOption({len(cards)}, \'bass\')">Play Bass</button>'
            f'<button class="secondary" type="button" onclick="playIdeaOption({len(cards)}, \'arp\')">Play Arp</button>'
            '<button class="secondary" type="button" onclick="stopIdeaPlayback()">Stop</button>'
            '<button class="secondary" type="button" onclick="regenerateIdea(\'melody_only\')">Regenerate Melody Only</button>'
            '<button class="secondary" type="button" onclick="regenerateIdea(\'chords_only\')">Regenerate Chords Only</button>'
            '<button class="secondary" type="button" onclick="regenerateIdea(\'full_option\')">Regenerate Full Option</button>'
            '</div>'
            + "".join(section_html)
            + '</article>'
        )
    return (
        '<section class="panel result">'
        '<h2>Three creative MIDI options are ready</h2>'
        '<p>The ZIP includes full arrangements, melody-only files, chords-only files, bass/root guides, arpeggio/pluck files, and section MIDI exports for each option.</p>'
        f'{render_export_proof(export_summary)}'
        f'<a class="button primary" href="{download_href}" download="{download_filename}">Download MIDI Idea ZIP</a>'
        '</section>'
        '<section class="preview-grid">'
        + "".join(cards)
        + '</section>'
    )


@app.get("/", response_class=HTMLResponse)
def home():
    return page()


@app.get("/melody-lab", response_class=HTMLResponse)
def melody_lab():
    return melody_lab_page()


@app.post("/melody-lab/generate", response_class=HTMLResponse)
def generate_melody_lab(
    bpm: Annotated[int, Form(..., ge=120, le=150)],
    key: Annotated[str, Form(...)],
    scale: Annotated[str, Form(...)],
    genre: Annotated[str, Form(...)],
    generation_type: Annotated[str, Form(...)],
    arrangement_section: Annotated[str, Form(...)],
    bars: Annotated[int, Form(..., ge=4, le=32)],
    complexity: Annotated[str, Form(...)],
    energy: Annotated[str, Form(...)],
    creative_risk: Annotated[str, Form(...)],
    length_mode: Annotated[str, Form()] = "per_section",
    include_arpeggio_pluck: Annotated[str, Form()] = "true",
    audition_depth: Annotated[str, Form()] = "balanced",
    regenerate_mode: Annotated[str, Form()] = "full_option",
    variation_seed: Annotated[str, Form()] = "0",
):
    result = generate_edm_ideas({
        "bpm": bpm,
        "key": key,
        "scale": scale,
        "genre": genre,
        "generation_type": generation_type,
        "arrangement_section": arrangement_section,
        "bars": bars,
        "length_mode": length_mode,
        "complexity": complexity,
        "energy": energy,
        "creative_risk": creative_risk,
        "include_arpeggio_pluck": include_arpeggio_pluck,
        "audition_depth": audition_depth,
        "regenerate_mode": regenerate_mode,
        "variation_seed": variation_seed,
    })
    file_path = export_idea_pack(result, EXPORTS_DIR, APP_VERSION)
    export_summary = zip_export_summary(file_path)
    filename = f"edm_trance_idea_pack_{export_slug(result.key)}_section_stems_v2.zip"
    zip_bytes = file_path.read_bytes()
    temp_parent = file_path.parent
    try:
        file_path.unlink(missing_ok=True)
    except OSError:
        pass
    if temp_parent.name.startswith("edm_idea_pack_"):
        shutil.rmtree(temp_parent, ignore_errors=True)
    download_href = "data:application/zip;base64," + base64.b64encode(zip_bytes).decode("ascii")
    html = melody_lab_page(render_option_preview(result, download_href, filename, export_summary), json.dumps(playback_payload(result)))
    return HTMLResponse(html, headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})


@app.get("/advisor", response_class=HTMLResponse)
def advisor_dashboard():
    advisor_path = latest_advisor_json_path()
    if not advisor_path.exists():
        return no_advisor_page()
    return advisor_dashboard_page(json.loads(advisor_path.read_text()))


@app.get("/download/{token}")
def download_pack(token: str):
    pack = GENERATED_PACKS.get(token)
    if not pack:
        return HTMLResponse("<h1>Download expired</h1><p>Please generate a new MIDI pack.</p>", status_code=404)
    file_path = Path(pack["path"])
    if not file_path.exists():
        GENERATED_PACKS.pop(token, None)
        return HTMLResponse("<h1>Download expired</h1><p>Please generate a new MIDI pack.</p>", status_code=404)
    return FileResponse(
        path=file_path,
        filename=pack["filename"],
        media_type="application/zip",
        background=BackgroundTask(lambda item_token, path: (GENERATED_PACKS.pop(item_token, None), Path(path).unlink(missing_ok=True)), token, str(file_path)),
    )


@app.post("/generate")
def generate(
    bpm: Annotated[int, Form(..., ge=132, le=142)],
    key: Annotated[KeyType, Form(...)],
    progression: Annotated[ProgressionType, Form(...)],
    arrangement: Annotated[ArrangementType, Form(...)],
    variation: Annotated[VariationType, Form(...)],
    density: Annotated[DensityType, Form(...)],
    energy_profile: Annotated[EnergyBiasType, Form(...)],
    track_identity: Annotated[TrackIdentityType, Form()] = TRACK_IDENTITY_MODE,
):
    tracks, blueprint, sections, markers = render_song(bpm, key, progression, arrangement, variation, density, energy_profile, track_identity)
    progression_slug = export_slug(blueprint.get("progression_name", progression))
    file_path = EXPORTS_DIR / f"dream_trance_{EXPORT_VERSION}_{progression_slug}_{uuid4().hex}.zip"
    export_pack(bpm, tracks, blueprint, sections, markers, file_path)
    token = uuid4().hex
    filename = f"dream_trance_{EXPORT_VERSION}_{progression_slug}_pack.zip"
    GENERATED_PACKS[token] = {"path": str(file_path), "filename": filename}
    return HTMLResponse(result_page(f"/download/{token}", blueprint, bpm, key))
