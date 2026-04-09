# Dream Trance MIDI Generator V1.1

Improved section-aware uplifting vocal trance MIDI generator.

## What changed from V1
- Stems do not all begin at bar 1 anymore.
- Drops use a repeating motif rather than random lead notes.
- Vocal melody is phrase-based and cadence-aware.
- Builds include snare ramps and end-of-section fills.
- Drop sections switch to denser hats, rolling bass, and supersaw chord staging.

## Run
```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m uvicorn app:app --reload
```
Then open http://127.0.0.1:8000
