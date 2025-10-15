import io
import os
import wave
from functools import lru_cache
from pathlib import Path
from typing import Dict, Generator, Optional, Tuple

import numpy as np
import torch
from faster_whisper import WhisperModel
from piper import PiperVoice

_VOICE_CACHE: Dict[Tuple[Path, Optional[Path]], PiperVoice] = {}


def _data_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data"


def _voices_dir() -> Path:
    override = os.getenv("PIPER_VOICE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return (_data_dir() / "voices").resolve()


def _resolve_voice_paths(voice_id: Optional[str]) -> Tuple[Path, Optional[Path]]:
    voice_name = voice_id or os.getenv("PIPER_VOICE") or "en_US-amy-medium"
    base_dir = _voices_dir()

    model_path = Path(voice_name)
    if not model_path.suffix:
        model_path = model_path.with_suffix(".onnx")
    if not model_path.is_absolute():
        model_path = (base_dir / model_path).resolve()

    config_path = model_path.with_suffix(".json")
    if not config_path.exists():
        config_path = None

    if not model_path.exists():
        raise FileNotFoundError(
            f"Piper voice model not found at {model_path}. "
            "Set PIPER_VOICE or PIPER_VOICE_DIR to point to a valid .onnx voice file."
        )

    return model_path, config_path


def _load_voice(voice_id: Optional[str]) -> PiperVoice:
    model_path, config_path = _resolve_voice_paths(voice_id)
    cache_key = (model_path, config_path)
    if cache_key not in _VOICE_CACHE:
        _VOICE_CACHE[cache_key] = PiperVoice.load(
            str(model_path),
            config_path=str(config_path) if config_path else None,
        )
    return _VOICE_CACHE[cache_key]


def _detect_device() -> str:
    device = os.getenv("WHISPER_DEVICE")
    if device:
        return device
    return "cuda" if torch.cuda.is_available() else "cpu"


def _detect_compute_type(device: str) -> str:
    env_value = os.getenv("WHISPER_COMPUTE_TYPE")
    if env_value:
        return env_value
    if device == "cuda":
        return "float16"
    return "int8"


@lru_cache(maxsize=1)
def _whisper_model() -> WhisperModel:
    model_id = os.getenv("WHISPER_MODEL", "base")
    device = _detect_device()
    compute_type = _detect_compute_type(device)
    return WhisperModel(model_id, device=device, compute_type=compute_type)


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    if orig_sr == target_sr:
        return audio.astype(np.float32)

    duration = audio.shape[0] / float(orig_sr)
    target_length = max(int(duration * target_sr), 1)

    # Use linear interpolation for resampling to avoid external dependencies.
    source_positions = np.linspace(0.0, duration, num=audio.shape[0], endpoint=False)
    target_positions = np.linspace(0.0, duration, num=target_length, endpoint=False)
    resampled = np.interp(target_positions, source_positions, audio)
    return resampled.astype(np.float32)


def transcribe_wav(audio_bytes: bytes) -> Tuple[str, Optional[str], float]:
    """
    Transcribe PCM WAV audio using faster-whisper.

    Returns a tuple of (transcript text, detected language, transcription duration seconds).
    """
    if not audio_bytes:
        raise ValueError("Audio payload is empty.")

    with wave.open(io.BytesIO(audio_bytes), "rb") as wav_reader:
        sample_width = wav_reader.getsampwidth()
        if sample_width != 2:
            raise ValueError("Expected 16-bit PCM WAV input.")

        sample_rate = wav_reader.getframerate()
        channels = wav_reader.getnchannels()
        frames = wav_reader.readframes(wav_reader.getnframes())

    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
    if channels > 1:
        audio = audio.reshape((-1, channels)).mean(axis=1)

    audio /= 32768.0
    audio = _resample(audio, sample_rate, 16000)

    model = _whisper_model()
    segments, info = model.transcribe(audio, batch_size=8)

    transcript_parts = [segment.text.strip() for segment in segments if segment.text]
    transcript = " ".join(part for part in transcript_parts if part).strip()

    return transcript, getattr(info, "language", None), getattr(info, "duration", 0.0)


def stream_speech(text: str, voice_id: Optional[str] = None) -> Generator[bytes, None, None]:
    """
    Synthesize speech using Piper and stream WAV bytes.
    """
    if not text or not text.strip():
        raise ValueError("Text must be provided for speech synthesis.")

    voice = _load_voice(voice_id)
    buffer = io.BytesIO()

    with wave.open(buffer, "wb") as wav_writer:
        voice.synthesize(text.strip(), wav_writer, sentence_silence=0.2)

    buffer.seek(0)

    chunk_size = 4096
    while True:
        chunk = buffer.read(chunk_size)
        if not chunk:
            break
        yield chunk
