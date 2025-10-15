import { useEffect, useMemo, useRef, useState } from "react";
import Hero from "../components/hero";
import Input from "../components/input";
import Window from "../components/window";
import { getSpeechStreamUrl, sendQuery } from "./backend";
import "./App.css";

type MessageEntry = {
  text: string;
  isUser: boolean;
  viaVoice?: boolean;
  speak?: boolean;
};

function App() {
  const [messages, setMessages] = useState<MessageEntry[]>([]);
  const session_id = useMemo(() => crypto.randomUUID(), []);
  const audioRef = useRef<HTMLAudioElement | null>(null);

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
    if (!messages.length) return;
    const lastMessage = messages[messages.length - 1];
    if (lastMessage.isUser || !lastMessage.speak) return;
    let cancelled = false;

    const play = async () => {
      try {
        const url = await getSpeechStreamUrl(lastMessage.text);
        if (cancelled) return;

        const audio = new Audio(url);
        audioRef.current?.pause();
        audioRef.current = audio;

        audio.addEventListener(
          "ended",
          () => {
            if (audioRef.current === audio) {
              audioRef.current = null;
            }
          },
          { once: true },
        );

        await audio.play();
      } catch (error) {
        console.error("Speech playback error:", error);
      }
    };

    void play();

    return () => {
      cancelled = true;
    };
  }, [messages]);

  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = "";
        audioRef.current = null;
      }
    };
  }, []);

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
