const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

export interface QueryResponse {
  intent: string;
  confidence: number;
  entities: Record<string, any>;
  reply: string;
  latency_ms: number;
}

export async function sendQuery(session_id: string, text: string): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE}/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id, text }),
  });
  if (!res.ok) throw new Error("Failed to fetch from API");
  return res.json();
}
