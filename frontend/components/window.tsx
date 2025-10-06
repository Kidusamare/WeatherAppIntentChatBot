import type { FC } from "react";
import Message from "./message";

type WindowProps = {
  messages: { text: string; fromUser?: boolean }[];
};

const Window: FC<WindowProps> = ({ messages }) => {
  return (
    <div className="chat-window">
      {messages.map((msg, idx) => (
        <Message key={idx} text={msg.text} fromUser={msg.fromUser} />
      ))}
    </div>
  );
};

export default Window;
