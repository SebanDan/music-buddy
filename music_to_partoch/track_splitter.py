import subprocess


def run_demucs(audio_path):
    print("Separating instruments with Demucs...")
    subprocess.run(["demucs", "--out", OUTPUT_DIR, audio_path])
