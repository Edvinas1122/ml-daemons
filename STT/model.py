import os
import sys
import time

from faster_whisper import WhisperModel


class STTEngine:
    def __init__(self, model_size="base", device="cuda", compute_type="float16", beam_size=5):
        t0 = time.time()
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self.beam_size = beam_size
        print(f"Loaded {model_size} model in {time.time() - t0:.1f}s", flush=True)


def load_engine(model_size="base", device="cuda", compute_type="float16", beam_size=5):
    return STTEngine(model_size, device, compute_type, beam_size)
