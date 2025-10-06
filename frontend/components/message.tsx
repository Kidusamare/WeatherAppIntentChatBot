import type { FC } from "react";

type MessageProps = {
  text: string;
  fromUser?: boolean;
};

const Message: FC<MessageProps> = ({ text, fromUser = false }) => {
  return (
    <div className={`message ${fromUser ? "user" : "bot"}`}>
      {text}
    </div>
  );
};

export default Message;
