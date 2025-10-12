import type { FC } from "react";

const Hero: FC = () => {
  return (
    <section className="hero" aria-label="Weather assistant introduction">
      <div className="hero-copy">
        <span className="hero-eyebrow" aria-hidden="true">
          EchoCast
        </span>
        <h1>EchoCast speaks the forecast for you</h1>
        <p>
          Start talking and EchoCast will listen, understand, and respond with a natural voice forecast. Prefer to type? Switch
          to text mode whenever you like.
        </p>
        <div className="hero-badges" aria-hidden="true">
          <span className="hero-badge">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="M12 3v18M3 12h18" stroke="#1d4ed8" strokeWidth="2.2" strokeLinecap="round" />
              <circle cx="12" cy="12" r="4.5" stroke="#3b82f6" strokeWidth="2" />
            </svg>
            Real-time conditions
          </span>
          <span className="hero-badge">
            <svg viewBox="0 0 24 24" fill="none">
              <path
                d="M6 11a6 6 0 1112 0v1.2a2 2 0 01.67 3.88L12 18.5l-6.67-2.42A2 2 0 016 12.2V11z"
                stroke="#2563eb"
                strokeWidth="1.8"
                strokeLinejoin="round"
              />
              <path d="M10 22l2-4 2 4" stroke="#1d4ed8" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
            Voice-ready chat
          </span>
          <span className="hero-badge">
            <svg viewBox="0 0 24 24" fill="none">
              <path
                d="M4 7.5C4 5.567 5.567 4 7.5 4h9A3.5 3.5 0 0120 7.5V16c0 1.933-1.567 3.5-3.5 3.5h-9A3.5 3.5 0 014 16V7.5z"
                stroke="#1d4ed8"
                strokeWidth="1.8"
              />
              <path d="M7 9h10M7 12.5h6" stroke="#2563eb" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
            Travel smart
          </span>
        </div>
      </div>
      <div className="hero-art" role="presentation">
        <svg viewBox="0 0 320 320" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <linearGradient id="sunGradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#fde68a" />
              <stop offset="100%" stopColor="#f59e0b" />
            </linearGradient>
            <linearGradient id="cloudGradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#e2eaff" />
              <stop offset="100%" stopColor="#c1d5ff" />
            </linearGradient>
          </defs>
          <circle cx="110" cy="110" r="60" fill="url(#sunGradient)" opacity="0.9" />
          <g opacity="0.9">
            <ellipse cx="210" cy="160" rx="80" ry="50" fill="url(#cloudGradient)" />
            <ellipse cx="155" cy="162" rx="70" ry="46" fill="url(#cloudGradient)" />
            <ellipse cx="245" cy="180" rx="68" ry="42" fill="url(#cloudGradient)" />
          </g>
          <path
            d="M80 230c22 0 30 24 52 24s30-24 52-24 30 24 52 24"
            stroke="#3b82f6"
            strokeWidth="6"
            strokeLinecap="round"
            fill="none"
            opacity="0.65"
          />
          <path d="M122 214l-16 40" stroke="#93c5fd" strokeWidth="6" strokeLinecap="round" />
          <path d="M192 214l-16 40" stroke="#60a5fa" strokeWidth="6" strokeLinecap="round" />
        </svg>
      </div>
    </section>
  );
};

export default Hero;
