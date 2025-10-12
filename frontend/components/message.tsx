import type { FC, ReactNode } from "react";

type MessageProps = {
  text: string;
  isUser?: boolean;
};

type IconDescriptor = {
  test: RegExp;
  icon: ReactNode;
};

const iconLibrary: IconDescriptor[] = [
  {
    test: /\b(storm|thunder|lightning|severe)\b/i,
    icon: (
      <svg viewBox="0 0 40 40" fill="none" aria-hidden="true">
        <path
          d="M15 5c-5.523 0-10 4.477-10 10 0 3.037 1.363 5.745 3.504 7.569A6.5 6.5 0 0015 33h12a8 8 0 001.256-15.905A9.5 9.5 0 0015 5z"
          fill="#cbd5f5"
        />
        <path
          d="M18 22l-4 10 7-5-2 8 7-10h-5l2-5z"
          fill="#facc15"
          stroke="#f59e0b"
          strokeWidth="1.2"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  {
    test: /\b(rain|showers|drizzle|wet)\b/i,
    icon: (
      <svg viewBox="0 0 40 40" fill="none" aria-hidden="true">
        <path
          d="M15 9c-4.418 0-8 3.582-8 8 0 2.82 1.46 5.301 3.682 6.732A6.5 6.5 0 0015 31h10a7 7 0 000-14h-.248A8 8 0 0015 9z"
          fill="#dbeafe"
        />
        <path
          d="M13 30l-2 5M19 30l-2 5M25 30l-2 5"
          stroke="#3b82f6"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
    ),
  },
  {
    test: /\b(snow|flurries|ice|sleet)\b/i,
    icon: (
      <svg viewBox="0 0 40 40" fill="none" aria-hidden="true">
        <path
          d="M14 11a8 8 0 00-1.595 15.845A5.5 5.5 0 0014 30h11a6.5 6.5 0 001.018-12.929A7.5 7.5 0 0014 11z"
          fill="#e0f2fe"
        />
        <path
          d="M20 26v6M17 29l6 0M18 28l4 4M18 32l4-4"
          stroke="#38bdf8"
          strokeWidth="1.7"
          strokeLinecap="round"
        />
      </svg>
    ),
  },
  {
    test: /\b(sun|clear|bright|warm)\b/i,
    icon: (
      <svg viewBox="0 0 40 40" fill="none" aria-hidden="true">
        <circle cx="20" cy="20" r="9" fill="#fde047" stroke="#f59e0b" strokeWidth="1.6" />
        <path
          d="M20 6v4M20 30v4M6 20h4M30 20h4M10.1 10.1l2.9 2.9M27 27l2.9 2.9M29.9 10.1L27 13M13 27l-2.9 2.9"
          stroke="#facc15"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
      </svg>
    ),
  },
];

const defaultIcon = (
  <svg viewBox="0 0 40 40" fill="none" aria-hidden="true">
    <path
      d="M15 10c-4.418 0-8 3.582-8 8 0 2.998 1.615 5.622 4.023 7.067A5.5 5.5 0 0015 30h10a7 7 0 000-14h-.248A8 8 0 0015 10z"
      fill="#e2e8f0"
    />
    <path d="M18 30l-3 6M24 30l-3 6" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

const resolveIcon = (text: string): ReactNode => {
  for (const descriptor of iconLibrary) {
    if (descriptor.test.test(text)) {
      return descriptor.icon;
    }
  }
  return defaultIcon;
};

const Message: FC<MessageProps> = ({ text, isUser = false }) => {
  const icon = !isUser ? resolveIcon(text) : null;

  return (
    <div className={`message ${isUser ? "user" : "bot"}`}>
      {!isUser && <span className="message-icon">{icon}</span>}
      <span>{text}</span>
    </div>
  );
};

export default Message;
