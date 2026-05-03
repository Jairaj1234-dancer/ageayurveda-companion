const getApiUrl = (): string => {
  return (window as any).AgeAyurvedaConfig?.apiUrl || "http://localhost:8000";
};

interface ChatRequest {
  message: string;
  session_id: string;
  language?: string;
  conversation_id?: string;
  sources?: string[];
}

interface StreamCallback {
  onToken: (token: string) => void;
  onDone: (data: any) => void;
  onError: (error: string) => void;
}

export interface GroundedStreamCallback extends StreamCallback {
  onToolUse?: (data: { name: string; products: any[] }) => void;
}

export async function sendMessage(request: ChatRequest): Promise<any> {
  const response = await fetch(`${getApiUrl()}/api/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

export async function sendMessageStream(
  request: ChatRequest,
  callbacks: StreamCallback
): Promise<void> {
  const response = await fetch(`${getApiUrl()}/api/v1/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    callbacks.onError(`HTTP ${response.status}`);
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    callbacks.onError("No response body");
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const data = JSON.parse(line.slice(6));
          if (data.type === "token") {
            callbacks.onToken(data.content);
          } else if (data.type === "done") {
            callbacks.onDone(data);
          } else if (data.type === "error") {
            callbacks.onError(data.content);
          }
        } catch {
          // Skip malformed SSE lines
        }
      }
    }
  }
}

export async function sendGroundedMessageStream(
  request: ChatRequest,
  callbacks: GroundedStreamCallback,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${getApiUrl()}/api/v1/chat/grounded/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      signal,
    });
  } catch (e: any) {
    // AbortError isn't a real failure — caller initiated it.
    if (e?.name === "AbortError") {
      callbacks.onDone({ aborted: true });
      return;
    }
    callbacks.onError(e?.message || "Network error");
    return;
  }

  if (!response.ok) {
    if (response.status === 429) {
      callbacks.onError("Too many requests — please wait a moment and try again.");
    } else if (response.status === 503) {
      callbacks.onError("The grounded chat is temporarily unavailable.");
    } else {
      callbacks.onError(`HTTP ${response.status}`);
    }
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    callbacks.onError("No response body");
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const data = JSON.parse(line.slice(6));
          switch (data.type) {
            case "token":
              callbacks.onToken(data.content);
              break;
            case "tool_use":
              callbacks.onToolUse?.({ name: data.name, products: data.products || [] });
              break;
            case "done":
              callbacks.onDone(data);
              break;
            case "error":
              callbacks.onError(data.content);
              break;
          }
        } catch {
          // Skip malformed SSE lines
        }
      }
    }
  } catch (e: any) {
    if (e?.name === "AbortError") {
      callbacks.onDone({ aborted: true });
      return;
    }
    callbacks.onError(e?.message || "Stream error");
  }
}

export async function getWidgetConfig(): Promise<any> {
  const response = await fetch(`${getApiUrl()}/api/v1/widget/config`);
  return response.json();
}

export async function getPrakritiQuestions(): Promise<any[]> {
  const response = await fetch(`${getApiUrl()}/api/v1/prakriti/questions`);
  return response.json();
}

export async function submitPrakriti(
  session_id: string,
  answers: Record<string, string>,
  language: string = "en"
): Promise<any> {
  const response = await fetch(`${getApiUrl()}/api/v1/prakriti/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id, answers, language }),
  });
  return response.json();
}

export async function captureLead(
  session_id: string,
  email: string,
  name?: string,
  source: string = "chat_widget"
): Promise<any> {
  const response = await fetch(`${getApiUrl()}/api/v1/leads/capture`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id, email, name, source }),
  });
  return response.json();
}

export async function getChatHistory(session_id: string): Promise<any[]> {
  const response = await fetch(
    `${getApiUrl()}/api/v1/chat/history?session_id=${encodeURIComponent(session_id)}`
  );
  return response.json();
}
