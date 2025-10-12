import type { FC } from "react";
import Message from "./message";

type WindowProps = {
  messages: { text: string; isUser?: boolean; viaVoice?: boolean; speak?: boolean }[];
};

const Window: FC<WindowProps> = ({ messages }) => {
  if (messages.length === 0) {
    return (
      <div className="chat-window" role="log" aria-live="polite">
        <div className="chat-placeholder">
          <h3>Ask out loud to get started</h3>
          <p>Tap the mic and say something like:</p>
          <ul>
            <li>"Will it rain in Seattle tomorrow evening?"</li>
            <li>"What's the temperature right now in Austin?"</li>
            <li>"Do I need a jacket for Paris this weekend?"</li>
          </ul>
          <p>Prefer typing? Switch to Text mode below the chat.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-window" role="log" aria-live="polite">
      {messages.map((msg, idx) => (
        <Message key={idx} text={msg.text} isUser={msg.isUser} />
      ))}
    </div>
  );
};

export default Window;
