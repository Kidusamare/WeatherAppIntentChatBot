/// <reference types="vite/client" />

// Environment variables
interface ImportMetaEnv {
  readonly VITE_API_BASE: string
  // Add other env variables here as needed
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

// Global module declarations for assets
declare module '*.css';
declare module '*.scss';
declare module '*.sass';
declare module '*.less';
declare module '*.png';
declare module '*.jpg';
declare module '*.jpeg';
declare module '*.gif';
declare module '*.svg';
declare module '*.woff';
declare module '*.woff2';
declare module '*.ttf';
declare module '*.eot';
declare module '*.mp4';
declare module '*.webm';
declare module '*.ogg';
declare module '*.mp3';
declare module '*.wav';
