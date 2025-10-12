const sanitizeBase = (base: string) => base.replace(/\/$/, "");
const isDevelopment = import.meta.env.DEV ?? false;

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

export interface QueryResponse {
  intent: string;
  confidence: number;
  entities: Record<string, any>;
  reply: string;
  latency_ms: number;
}

export async function sendQuery(session_id: string, text: string): Promise<QueryResponse> {
  const candidates = getCandidateBases();
  const attempts: string[] = [];

  for (const base of candidates) {
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
      return res.json();
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      attempts.push(`${url} [${reason}]`);
    }
  }

  throw new Error(`Unable to reach weather backend. Tried: ${attempts.join("; ")}`);
}
