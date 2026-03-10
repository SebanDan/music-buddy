import os
import subprocess
import pretty_midi
from basic_pitch.inference import predict
from music21 import converter

INPUT_AUDIO = "song.mp3"
OUTPUT_DIR = "output"

STEMS = ["vocals", "drums", "bass", "other"]


def run_demucs(audio_path):
    print("Separating instruments with Demucs...")
    subprocess.run([
        "demucs",
        "--out",
        OUTPUT_DIR,
        audio_path
    ])


def find_stems(audio_path):
    song_name = os.path.splitext(os.path.basename(audio_path))[0]

    stem_dir = os.path.join(
        OUTPUT_DIR,
        "htdemucs",
        song_name
    )

    stems = {}

    for stem in STEMS:
        path = os.path.join(stem_dir, f"{stem}.wav")
        if os.path.exists(path):
            stems[stem] = path

    return stems


def audio_to_midi(stems):

    midi_files = {}

    for stem, path in stems.items():

        print(f"Transcribing {stem} to MIDI...")

        model_output, midi_data, note_events = predict(path)

        midi_path = os.path.join(OUTPUT_DIR, f"{stem}.mid")

        midi_data.write(midi_path)

        midi_files[stem] = midi_path

    return midi_files


def clean_midi(midi_files):

    cleaned = {}

    for stem, path in midi_files.items():

        print(f"Cleaning MIDI {stem}...")

        midi = pretty_midi.PrettyMIDI(path)

        for instrument in midi.instruments:
            cleaned_notes = []

            for note in instrument.notes:

                duration = note.end - note.start

                if duration > 0.05:
                    cleaned_notes.append(note)

            instrument.notes = cleaned_notes

        cleaned_path = os.path.join(
            OUTPUT_DIR,
            f"{stem}_clean.mid"
        )

        midi.write(cleaned_path)

        cleaned[stem] = cleaned_path

    return cleaned


def midi_to_sheet(cleaned_midis):

    sheets = {}

    for stem, path in cleaned_midis.items():

        print(f"Generating sheet for {stem}...")

        score = converter.parse(path)

        xml_path = os.path.join(
            OUTPUT_DIR,
            f"{stem}.musicxml"
        )

        score.write("musicxml", xml_path)

        sheets[stem] = xml_path

    return sheets


def main():

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    run_demucs(INPUT_AUDIO)

    stems = find_stems(INPUT_AUDIO)

    midi_files = audio_to_midi(stems)

    cleaned_midis = clean_midi(midi_files)

    sheets = midi_to_sheet(cleaned_midis)

    print("\nFinished! Generated sheets:")

    for k, v in sheets.items():
        print(k, "->", v)


if __name__ == "__main__":
    main()