const sanitizeBase = (base: string) => base.replace(/\/$/, "");
const isDevelopment = import.meta.env.DEV ?? false;

let resolvedBase: string | null = null;
let resolvingBase: Promise<string> | null = null;

const getCandidateBases = (): string[] => {
  const envBase = import.meta.env.VITE_API_BASE?.trim();
  const origin = typeof window !== "undefined" && window.location.origin ? window.location.origin : undefined;
  const localDefaults = ["http://127.0.0.1:8000", "http://localhost:8000"];
  const ordered: string[] = [];

  if (envBase) ordered.push(envBase);

  if (isDevelopment) {
    ordered.push(...localDefaults);
    if (origin) ordered.push(`${origin}/api`);
  } else {
    if (origin) ordered.push(`${origin}/api`);
    ordered.push("/api");
    ordered.push(...localDefaults);
  }

  return Array.from(new Set(ordered.map((candidate) => sanitizeBase(candidate))));
};

const orderedCandidates = (): string[] => {
  const candidates = getCandidateBases();
  if (!resolvedBase) return candidates;
  return [resolvedBase, ...candidates.filter((candidate) => candidate !== resolvedBase)];
};

const noteSuccessfulBase = (base: string) => {
  resolvedBase = base;
};

const ensureBase = async (): Promise<string> => {
  if (resolvedBase) return resolvedBase;
  if (resolvingBase) return resolvingBase;

  const candidates = getCandidateBases();
  const attempts: string[] = [];

  resolvingBase = (async () => {
    for (const candidate of candidates) {
      const url = `${candidate}/health`;
      try {
        const res = await fetch(url);
        if (res.ok) {
          noteSuccessfulBase(candidate);
          return candidate;
        }
        attempts.push(`${url} [${res.status}]`);
      } catch (error) {
        const reason = error instanceof Error ? error.message : String(error);
        attempts.push(`${url} [${reason}]`);
      }
    }
    throw new Error(`Unable to reach weather backend. Tried: ${attempts.join("; ")}`);
  })();

  try {
    return await resolvingBase;
  } finally {
    resolvingBase = null;
  }
};

export interface QueryResponse {
  intent: string;
  confidence: number;
  entities: Record<string, any>;
  reply: string;
  latency_ms: number;
}

export async function sendQuery(session_id: string, text: string): Promise<QueryResponse> {
  const attempts: string[] = [];

  for (const base of orderedCandidates()) {
    const url = `${base}/predict`;
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id, text }),
      });
      if (!res.ok) {
        attempts.push(`${url} [${res.status}]`);
        continue;
      }
      noteSuccessfulBase(base);
      return res.json();
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      attempts.push(`${url} [${reason}]`);
    }
  }

  throw new Error(`Unable to reach weather backend. Tried: ${attempts.join("; ")}`);
}

export interface TranscriptionResponse {
  text: string;
  language?: string | null;
  audio_seconds?: number;
}

export async function transcribeAudio(audio: Blob): Promise<TranscriptionResponse> {
  const attempts: string[] = [];

  const buildFormData = () => {
    const form = new FormData();
    form.append("audio", audio, "voice-input.wav");
    return form;
  };

  for (const base of orderedCandidates()) {
    const url = `${base}/speech/transcribe`;
    try {
      const res = await fetch(url, {
        method: "POST",
        body: buildFormData(),
      });
      if (!res.ok) {
        attempts.push(`${url} [${res.status}]`);
        continue;
      }
      noteSuccessfulBase(base);
      return res.json();
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      attempts.push(`${url} [${reason}]`);
    }
  }

  // If no base is cached yet, attempt to resolve once before failing.
  try {
    const base = await ensureBase();
    const url = `${base}/speech/transcribe`;
    const res = await fetch(url, {
      method: "POST",
      body: buildFormData(),
    });
    if (!res.ok) {
      attempts.push(`${url} [${res.status}]`);
    } else {
      noteSuccessfulBase(base);
      return res.json();
    }
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    attempts.push(reason);
  }

  throw new Error(`Unable to transcribe audio. Tried: ${attempts.join("; ")}`);
}

export async function getSpeechStreamUrl(text: string, options: { voice?: string } = {}): Promise<string> {
  const base = resolvedBase ?? (await ensureBase());
  const params = new URLSearchParams({ text });
  if (options.voice) {
    params.set("voice", options.voice);
  }
  params.set("_", Date.now().toString());
  return `${base}/speech/synthesize?${params.toString()}`;
}
