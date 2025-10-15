import type { FC, ChangeEvent, KeyboardEvent } from "react";
import { useEffect, useRef, useState } from "react";
import { transcribeAudio } from "../src/backend";

export interface InputProps {
  onSend: (text: string, options?: { viaVoice?: boolean }) => Promise<void>;
}

type InputMode = "voice" | "text";

const encodeWav = (audioBuffer: AudioBuffer): ArrayBuffer => {
  const channelCount = audioBuffer.numberOfChannels;
  const sampleRate = audioBuffer.sampleRate;
  const sampleLength = audioBuffer.length;

  const monoData = new Float32Array(sampleLength);
  for (let channel = 0; channel < channelCount; channel += 1) {
    const channelData = audioBuffer.getChannelData(channel);
    for (let i = 0; i < sampleLength; i += 1) {
      monoData[i] += channelData[i];
    }
  }
  for (let i = 0; i < sampleLength; i += 1) {
    monoData[i] /= channelCount;
  }

  const bytesPerSample = 2;
  const dataSize = sampleLength * bytesPerSample;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  let offset = 0;
  const writeString = (value: string) => {
    for (let i = 0; i < value.length; i += 1) {
      view.setUint8(offset + i, value.charCodeAt(i));
    }
    offset += value.length;
  };

  writeString("RIFF");
  view.setUint32(offset, 36 + dataSize, true);
  offset += 4;
  writeString("WAVE");
  writeString("fmt ");
  view.setUint32(offset, 16, true);
  offset += 4;
  view.setUint16(offset, 1, true);
  offset += 2;
  view.setUint16(offset, 1, true);
  offset += 2;
  view.setUint32(offset, sampleRate, true);
  offset += 4;
  view.setUint32(offset, sampleRate * bytesPerSample, true);
  offset += 4;
  view.setUint16(offset, bytesPerSample, true);
  offset += 2;
  view.setUint16(offset, 8 * bytesPerSample, true);
  offset += 2;
  writeString("data");
  view.setUint32(offset, dataSize, true);
  offset += 4;

  for (let i = 0; i < sampleLength; i += 1) {
    const sample = Math.max(-1, Math.min(1, monoData[i]));
    const intSample = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    view.setInt16(offset, intSample, true);
    offset += 2;
  }

  return buffer;
};

const Input: FC<InputProps> = ({ onSend }) => {
  const [mode, setMode] = useState<InputMode>("voice");
  const [text, setText] = useState("");
  const [lastVoiceInput, setLastVoiceInput] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [checkedVoiceSupport, setCheckedVoiceSupport] = useState(false);
  const [hasAttemptedAutoStart, setHasAttemptedAutoStart] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);

  const mediaStreamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const discardNextRecordingRef = useRef(false);

  const cleanupStream = () => {
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    recorderRef.current = null;
    chunksRef.current = [];
  };

  const ensureAudioContext = () => {
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContext();
    }
    return audioContextRef.current;
  };

  const convertBlobToWav = async (blob: Blob): Promise<Blob> => {
    const arrayBuffer = await blob.arrayBuffer();
    const audioContext = ensureAudioContext();
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer.slice(0));
    const wavBuffer = encodeWav(audioBuffer);
    return new Blob([wavBuffer], { type: "audio/wav" });
  };

  const startRecording = async () => {
    if (!voiceSupported) return;
    setVoiceError(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;

      const options: MediaRecorderOptions = {};
      if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported("audio/webm")) {
        options.mimeType = "audio/webm";
      }

      const recorder = new MediaRecorder(stream, options);
      chunksRef.current = [];
      discardNextRecordingRef.current = false;

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data && event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onerror = (event) => {
        setVoiceError(event.error?.message ?? "Microphone error encountered.");
      };

      recorder.onstop = async () => {
        const shouldDiscard = discardNextRecordingRef.current;
        discardNextRecordingRef.current = false;

        try {
          if (shouldDiscard || chunksRef.current.length === 0) {
            return;
          }

          const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
          chunksRef.current = [];

          const wavBlob = await convertBlobToWav(blob);
          const transcription = await transcribeAudio(wavBlob);
          const transcript = transcription.text?.trim();

          if (transcript) {
            setLastVoiceInput(transcript);
            await onSend(transcript, { viaVoice: true });
          } else {
            setVoiceError("Could not understand audio. Please try again.");
          }
        } catch (error) {
          const reason = error instanceof Error ? error.message : "Unable to transcribe audio.";
          setVoiceError(reason);
        } finally {
          cleanupStream();
          setIsListening(false);
        }
      };

      recorderRef.current = recorder;
      recorder.start();
      setIsListening(true);
    } catch (error) {
      const reason = error instanceof Error ? error.message : "Unable to access microphone.";
      setVoiceError(reason);
      cleanupStream();
      setIsListening(false);
    }
  };

  const stopRecording = (discard = false) => {
    discardNextRecordingRef.current = discard;
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    } else {
      cleanupStream();
      setIsListening(false);
    }
  };

  useEffect(() => {
    const supported =
      typeof navigator !== "undefined" &&
      !!navigator.mediaDevices?.getUserMedia &&
      typeof MediaRecorder !== "undefined";
    setVoiceSupported(supported);
    setCheckedVoiceSupport(true);

    return () => {
      discardNextRecordingRef.current = true;
      if (recorderRef.current && recorderRef.current.state !== "inactive") {
        recorderRef.current.stop();
      }
      cleanupStream();
      if (audioContextRef.current) {
        audioContextRef.current.close().catch(() => undefined);
        audioContextRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (checkedVoiceSupport && !voiceSupported) {
      setMode("text");
    }
  }, [checkedVoiceSupport, voiceSupported]);

  useEffect(() => {
    if (mode === "text" && isListening) {
      stopRecording(true);
    }
    if (mode === "voice") {
      setText("");
    }
  }, [mode, isListening]);

  useEffect(() => {
    if (!voiceSupported || hasAttemptedAutoStart || mode !== "voice") return;
    setHasAttemptedAutoStart(true);
    void startRecording();
  }, [mode, voiceSupported, hasAttemptedAutoStart]);

  const sendMessage = async (value?: string, viaVoice = false) => {
    const toSend = (value ?? text).trim();
    if (!toSend) return;
    setText("");
    if (viaVoice) {
      setLastVoiceInput(toSend);
    }
    await onSend(toSend, { viaVoice });
  };

  const handleSend = async () => {
    await sendMessage(undefined, false);
  };

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    setText(e.currentTarget.value);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") handleSend();
  };

  const toggleListening = () => {
    if (!voiceSupported) {
      setMode("text");
      return;
    }

    if (isListening) {
      stopRecording();
      return;
    }

    void startRecording();
  };

  return (
    <div className={`input-container ${mode}`}>
      <div className="input-mode-switch" role="tablist" aria-label="Choose input method">
        <button
          type="button"
          role="tab"
          aria-selected={mode === "voice"}
          className={mode === "voice" ? "active" : ""}
          onClick={() => setMode("voice")}
          disabled={!voiceSupported}
        >
          Voice
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "text"}
          className={mode === "text" ? "active" : ""}
          onClick={() => setMode("text")}
        >
          Text
        </button>
      </div>

      {mode === "voice" ? (
        <div className="voice-panel" aria-live="polite">
          <div className={`voice-indicator ${isListening ? "active" : ""}`}>
            <span className="indicator-dot" />
            {isListening ? "Listening..." : "Tap the mic to ask about the weather"}
          </div>
          <button
            type="button"
            onClick={toggleListening}
            aria-pressed={isListening}
            className={`voice-mic-button ${isListening ? "listening" : ""}`}
          >
            <span>{isListening ? "Stop Listening" : "Tap to Speak"}</span>
          </button>
          <div className="voice-status">
            <span>
              {voiceSupported
                ? "Voice capture via faster-whisper backend"
                : "Voice capture unavailable in this browser"}
            </span>
            {voiceError && <div className="voice-error">{voiceError}</div>}
            {lastVoiceInput && <div className="voice-last-input">Last question: "{lastVoiceInput}"</div>}
          </div>
        </div>
      ) : (
        <div className="text-panel">
          <input
            type="text"
            value={text}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder="Type your weather question..."
          />
          <button type="button" onClick={handleSend}>
            Send
          </button>
        </div>
      )}
    </div>
  );
};

export default Input;
