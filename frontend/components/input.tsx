import type { FC, ChangeEvent, KeyboardEvent } from "react";
import { useEffect, useRef, useState } from "react";

export interface InputProps {
  onSend: (text: string, options?: { viaVoice?: boolean }) => Promise<void>;
}

type InputMode = "voice" | "text";

const Input: FC<InputProps> = ({ onSend }) => {
  const [mode, setMode] = useState<InputMode>("voice");
  const [text, setText] = useState("");
  const [lastVoiceInput, setLastVoiceInput] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [checkedVoiceSupport, setCheckedVoiceSupport] = useState(false);
  const [hasAttemptedAutoStart, setHasAttemptedAutoStart] = useState(false);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  type SpeechRecognitionConstructor = new () => SpeechRecognition;

  const resolveSpeechRecognition = (): SpeechRecognitionConstructor | undefined => {
    if (typeof window === "undefined") return undefined;
    const win = window as Window & {
      webkitSpeechRecognition?: SpeechRecognitionConstructor;
      SpeechRecognition?: SpeechRecognitionConstructor;
    };
    return win.SpeechRecognition || win.webkitSpeechRecognition;
  };

  const initializeRecognition = () => {
    const SpeechRecognitionCtor = resolveSpeechRecognition();
    if (!SpeechRecognitionCtor) return;

    const recognition = new SpeechRecognitionCtor();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const transcript = event.results[0][0]?.transcript ?? "";
      setIsListening(false);
      const cleaned = transcript.trim();
      if (cleaned) {
        setLastVoiceInput(cleaned);
        void sendMessage(cleaned, true);
      }
    };

    recognition.onerror = () => {
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;
  };

  useEffect(() => {
    const SpeechRecognitionCtor = resolveSpeechRecognition();
    if (!SpeechRecognitionCtor) {
      setVoiceSupported(false);
      setCheckedVoiceSupport(true);
      return;
    }

    setVoiceSupported(true);
    initializeRecognition();
    setCheckedVoiceSupport(true);

    return () => {
      recognitionRef.current?.stop();
      recognitionRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (checkedVoiceSupport && !voiceSupported) {
      setMode("text");
    }
  }, [checkedVoiceSupport, voiceSupported]);

  useEffect(() => {
    if (mode === "text" && isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
    }
    if (mode === "voice") {
      setText("");
    }
  }, [mode, isListening]);

  useEffect(() => {
    if (!voiceSupported || hasAttemptedAutoStart || mode !== "voice") return;
    setHasAttemptedAutoStart(true);
    try {
      recognitionRef.current?.start();
      setIsListening(true);
    } catch (error) {
      setIsListening(false);
    }
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
      recognitionRef.current?.stop();
      setIsListening(false);
      return;
    }

    if (!recognitionRef.current) {
      initializeRecognition();
    }

    try {
      recognitionRef.current?.start();
      setIsListening(true);
    } catch (error) {
      setIsListening(false);
    }
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
            <span>{voiceSupported ? "Powered by your browser microphone" : "Voice capture unavailable in this browser"}</span>
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
