import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import wave


def main():
    parser = argparse.ArgumentParser(description="Genera el dictado con la voz neuronal local de Piper.")
    parser.add_argument("--piper", default="piper", help="Ruta al ejecutable de Piper")
    parser.add_argument("--model", type=pathlib.Path, required=True, help="Modelo es_ES-sharvard-medium.onnx")
    args = parser.parse_args()
    model = args.model.resolve()
    if not model.is_file() or not pathlib.Path(f"{model}.json").is_file():
        raise RuntimeError("Faltan el modelo de voz o su configuracion .onnx.json.")
    chunks = json.load(sys.stdin)
    if not isinstance(chunks, list) or not chunks or any(
        not isinstance(chunk, dict) or not isinstance(chunk.get("spoken"), str)
        or not chunk["spoken"].strip() for chunk in chunks
    ):
        raise ValueError("Los fragmentos deben contener texto para leer.")

    root = pathlib.Path(__file__).resolve().parent.parent
    target = root / "audio" / "biblioteca"
    with tempfile.TemporaryDirectory(prefix="noe-dictation-") as temporary:
        output = pathlib.Path(temporary)
        lines = "\n".join(json.dumps({
            "text": chunk["spoken"],
            "output_file": str(output / f"{index:02}.wav"),
        }, ensure_ascii=False) for index, chunk in enumerate(chunks, 1))
        subprocess.run([
            args.piper, "--model", str(model), "--speaker", "1",
            "--length_scale", "1", "--sentence_silence", "0.15", "--json-input",
        ], input=lines + "\n", text=True, check=True, timeout=180)
        durations = []
        for index in range(1, len(chunks) + 1):
            source = output / f"{index:02}.wav"
            with wave.open(str(source), "rb") as audio:
                if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getframerate() != 22050:
                    raise RuntimeError(f"Formato de audio incorrecto en el fragmento {index}.")
                duration = audio.getnframes() / audio.getframerate()
                if not 1 < duration < 15 or not any(audio.readframes(audio.getnframes())):
                    raise RuntimeError(f"Audio vacio o incompleto en el fragmento {index}.")
                durations.append(duration)
        target.mkdir(parents=True, exist_ok=True)
        for index, duration in enumerate(durations, 1):
            filename = f"{index:02}.wav"
            shutil.copyfile(output / filename, target / filename)
            print(f"{filename}: {duration:.1f} segundos")


if __name__ == "__main__":
    main()
