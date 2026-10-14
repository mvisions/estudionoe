import ctypes
import ctypes.util
import json
import pathlib
import sys
import wave


def main():
    library = ctypes.util.find_library("espeak-ng")
    if not library:
        raise RuntimeError("Instala libespeak-ng para generar el audio del dictado.")
    engine = ctypes.CDLL(library)
    engine.espeak_Initialize.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    engine.espeak_Initialize.restype = ctypes.c_int
    engine.espeak_SetVoiceByName.argtypes = [ctypes.c_char_p]
    engine.espeak_SetParameter.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
    engine.espeak_Synth.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint, ctypes.c_int,
        ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint), ctypes.c_void_p,
    ]
    rate = engine.espeak_Initialize(2, 0, None, 0)
    if rate <= 0:
        raise RuntimeError("No se pudo iniciar el sintetizador.")
    if engine.espeak_SetVoiceByName(b"es") != 0:
        raise RuntimeError("No se pudo cargar la voz espanola.")
    if engine.espeak_SetParameter(1, 160, 0) != 0:
        raise RuntimeError("No se pudo configurar la velocidad.")

    samples = bytearray()
    callback_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_void_p)

    @callback_type
    def receive(buffer, count, _events):
        if buffer and count > 0:
            samples.extend(ctypes.string_at(buffer, count * ctypes.sizeof(ctypes.c_short)))
        return 0

    engine.espeak_SetSynthCallback.argtypes = [callback_type]
    engine.espeak_SetSynthCallback(receive)
    root = pathlib.Path(__file__).resolve().parent.parent
    chunks = json.load(sys.stdin)
    for index, chunk in enumerate(chunks, 1):
        samples.clear()
        text = ctypes.create_string_buffer(chunk["spoken"].encode("utf-8"))
        if engine.espeak_Synth(text, len(text), 0, 1, 0, 1, None, None) != 0:
            raise RuntimeError(f"No se pudo generar el fragmento {index}.")
        if engine.espeak_Synchronize() != 0 or not samples:
            raise RuntimeError(f"Audio vacio o incompleto en el fragmento {index}.")
        target = root / "audio" / "biblioteca" / f"{index:02}.wav"
        target.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(target), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(rate)
            output.writeframes(samples)
        print(f"{target.name}: {len(samples) / (rate * 2):.1f} segundos")
    engine.espeak_Terminate()


if __name__ == "__main__":
    main()
