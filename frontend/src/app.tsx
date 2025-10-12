import { useEffect, useMemo, useState } from "react";
import Hero from "../components/hero";
import Input from "../components/input";
import Window from "../components/window";
import { sendQuery } from "./backend";
import "./App.css";

type MessageEntry = {
  text: string;
  isUser: boolean;
  viaVoice?: boolean;
  speak?: boolean;
};

function App() {
  const [messages, setMessages] = useState<MessageEntry[]>([]);
  const [voice, setVoice] = useState<SpeechSynthesisVoice | null>(null);
  const session_id = useMemo(() => crypto.randomUUID(), []);

  const handleSend = async (text: string, options: { viaVoice?: boolean } = {}) => {
    const viaVoice = options.viaVoice ?? false;
    setMessages((prev) => [...prev, { text, isUser: true, viaVoice }]);
    try {
      const response = await sendQuery(session_id, text);
      setMessages((prev) => [...prev, { text: response.reply, isUser: false, speak: viaVoice }]);
    } catch (err) {
      const baseMessage = err instanceof Error ? err.message : "Error connecting to backend.";
      const guidance =
        baseMessage.includes("Unable to reach weather backend") || baseMessage.includes("Failed to fetch")
          ? `${baseMessage}. Please confirm the Weather API server is running (default: http://127.0.0.1:8000) or update VITE_API_BASE.`
          : `Error connecting to backend: ${baseMessage}`;
      setMessages((prev) => [...prev, { text: guidance, isUser: false }]);
      if (err instanceof Error) {
        console.error("Weather chat backend error:", err);
      }
    }
  };

  useEffect(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    const synth = window.speechSynthesis;

    const pickVoice = () => {
      const voices = synth.getVoices();
      if (!voices.length) return;

      const preferredPatterns = [
        /jenny/i,
        /samantha/i,
        /aria/i,
        /allison/i,
        /femme/i,
        /female/i,
        /en-us/i,
      ];

      for (const pattern of preferredPatterns) {
        const found = voices.find((v) => pattern.test(v.name) || pattern.test(v.lang));
        if (found) {
          setVoice(found);
          return;
        }
      }

      const fallback = voices.find((v) => v.lang.toLowerCase().startsWith("en")) ?? voices[0];
      setVoice(fallback ?? null);
    };

    if (synth.getVoices().length) {
      pickVoice();
      return;
    }

    const handler = () => {
      pickVoice();
    };

    synth.addEventListener("voiceschanged", handler);
    synth.onvoiceschanged = handler;

    return () => {
      synth.removeEventListener("voiceschanged", handler);
      synth.onvoiceschanged = null;
    };
  }, []);

  useEffect(() => {
    if (!messages.length) return;
    const lastMessage = messages[messages.length - 1];
    if (lastMessage.isUser || !lastMessage.speak) return;
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;

    const utterance = new SpeechSynthesisUtterance(lastMessage.text);
    if (voice) {
      utterance.voice = voice;
    }
    utterance.rate = 1.12;
    utterance.pitch = 1.05;
    utterance.volume = 0.85;

    const speak = () => {
      try {
        window.speechSynthesis.cancel();
        if (typeof window.speechSynthesis.resume === "function") {
          window.speechSynthesis.resume();
        }
        window.speechSynthesis.speak(utterance);
      } catch (error) {
        console.error("Speech synthesis error:", error);
      }
    };

    // Delay slightly so the first response after microphone activation plays reliably.
    const speakTimer = window.setTimeout(speak, 40);

    return () => {
      window.clearTimeout(speakTimer);
    };
  }, [messages, voice]);

  return (
    <div className="app-shell">
      <Hero />
      <section className="chat-card" aria-label="Weather conversation">
        <div className="chat-header">
          <div>
            <h2>Hands-free Forecasts</h2>
            <span>EchoCast defaults to voice mode: just speak your question. Need to type? Toggle to text input anytime.</span>
          </div>
        </div>
        <Window messages={messages} />
        <Input onSend={handleSend} />
      </section>
    </div>
  );
}

export default App;
