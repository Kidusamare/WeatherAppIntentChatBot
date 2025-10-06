import { useState, useMemo } from "react";
import Input from "../components/input";
import Window from "../components/window";
import { sendQuery } from "./backend";
import "./App.css";

function App() {
  const [messages, setMessages] = useState<{ text: string; isUser: boolean }[]>([]);
  const session_id = useMemo(() => crypto.randomUUID(), []);

  const handleSend = async (text: string) => {
    setMessages((prev) => [...prev, { text, isUser: true }]);
    try {
      const response = await sendQuery(session_id, text);
      setMessages((prev) => [...prev, { text: response.reply, isUser: false }]);
    } catch (err) {
      setMessages((prev) => [...prev, { text: "Error connecting to backend.", isUser: false }]);
    }
  };

  return (
    <div className="app-container">
      <h1>Weather Chatbot</h1>
      <Window messages={messages} />
      <Input onSend={handleSend} />
    </div>
  );
}

export default App;
