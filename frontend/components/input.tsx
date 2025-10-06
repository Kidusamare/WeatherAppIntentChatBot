import type { FC, ChangeEvent, KeyboardEvent } from "react"; 
import { useState } from "react";

export interface InputProps {
  onSend: (text: string) => Promise<void>;
}

const Input: FC<InputProps> = ({ onSend }) => {
  const [text, setText] = useState("");

  const handleSend = async () => {
    if (!text.trim()) return;
    await onSend(text);
    setText("");
  };

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    setText(e.currentTarget.value);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") handleSend();
  };

  return (
    <div className="input-container">
      <input
        type="text"
        value={text}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder="Type a message..."
      />
      <button onClick={handleSend}>Send</button>
    </div>
  );
};

export default Input;
