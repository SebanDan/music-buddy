from music21 import converter, stream, note, meter, duration


def main():
# Charger le fichier MusicXML
    score = converter.parse("/output/bass.musicxml")

    # Créer un nouveau stream propre
    clean_score = stream.Score()

    for part in score.parts:
        new_part = stream.Part()
        # Copier les mesures
        for m in part.getElementsByClass(stream.Measure):
            new_measure = stream.Measure(number=m.number)

            for n in m.notes:
                if isinstance(n, note.Note):
                    # Arrondir la durée à la note la plus proche 1/16
                    dur = max(0.0625, round(n.duration.quarterLength * 16)/16)
                    n.duration = duration.Duration(dur)
                    new_measure.append(n)
            new_part.append(new_measure)
        clean_score.append(new_part)

    # Sauvegarder le MusicXML nettoyé
    clean_score.write("musicxml", fp="bass_clean.musicxml")
    print("Fichier nettoyé : bass_clean.musicxml")

if __name__ == "__main__":
    main()