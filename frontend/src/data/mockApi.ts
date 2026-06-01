import type {
  AgentResponse,
  ChatbotKind,
  ChatTurn,
  Conversation,
  Provider,
  ProviderModel,
  TelemetryEvent,
  UsageSummary
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:3003";

export const providerModels: ProviderModel[] = [
  {
    provider: "openai",
    label: "OpenAI",
    models: ["gpt-4o", "gpt-4o-mini", "gpt-4.1-mini"]
  },
  {
    provider: "gemini",
    label: "Gemini",
    models: ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite"]
  },
  {
    provider: "local",
    label: "Local",
    models: ["Phi-3-mini-4k-instruct-q4", "Llama-3.2-3B-Instruct"]
  }
];

const seedConversations: Conversation[] = [
  {
    id: "conv-1",
    title: "Product search",
    updatedAt: new Date().toISOString()
  }
];

type PersistedChatState = {
  conversations: Conversation[];
  turns: ChatTurn[];
  telemetry: TelemetryEvent[];
  sessions: Record<string, string>;
};

const STORAGE_KEY = "ai-deal-hunter-chat-state";
const initialState = loadPersistedState();

let conversations = initialState.conversations;
let turns: ChatTurn[] = initialState.turns;
let telemetry: TelemetryEvent[] = initialState.telemetry;
const sessionByConversation = new Map(Object.entries(initialState.sessions));

type CompareApiResponse = {
  baseline: AgentResponse;
  react: AgentResponse;
  turn?: ChatTurn;
  session_id?: string;
  telemetry?: TelemetryEvent[];
  usage?: UsageSummary;
};

type CompareUpdate = {
  kind: ChatbotKind;
  response: AgentResponse;
};

export async function listConversations() {
  return conversations;
}

export async function listConversationTurns(conversationId: string) {
  return turns.filter((turn) => turn.conversationId === conversationId);
}

export async function createConversation() {
  const conversation: Conversation = {
    id: `conv-${crypto.randomUUID()}`,
    title: "New product search",
    updatedAt: new Date().toISOString()
  };
  conversations = [conversation, ...conversations];
  persistState();
  return conversation;
}

export async function sendComparisonMessage(
  input: string,
  provider: Provider,
  model: string,
  conversationId: string,
  onUpdate?: (update: CompareUpdate) => void
) {
  const sessionId = sessionByConversation.get(conversationId);
  const streamResponse = await fetch(`${API_BASE_URL}/api/compare/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      message: input,
      provider,
      model,
      session_id: sessionId
    })
  });

  if (streamResponse.ok && streamResponse.body) {
    return readCompareStream(streamResponse, input, conversationId, onUpdate);
  }

  const response = await fetch(`${API_BASE_URL}/api/compare`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      message: input,
      provider,
      model,
      session_id: sessionId
    })
  });

  if (!response.ok) {
    const message = await readError(streamResponse.ok ? response : streamResponse);
    throw new Error(message);
  }

  const data = (await response.json()) as CompareApiResponse;
  if (data.session_id) {
    sessionByConversation.set(conversationId, data.session_id);
    persistState();
  }
  onUpdate?.({ kind: "baseline", response: data.baseline });
  onUpdate?.({ kind: "react", response: data.react });

  const turn = normalizeTurn(data.turn, conversationId, input, data.baseline, data.react);

  turns = [...turns, turn];
  conversations = updateConversationTitle(conversations, conversationId, input);
  persistState();

  if (data.telemetry) {
    telemetry = [...data.telemetry, ...telemetry];
    persistState();
  }

  return { baseline: data.baseline, react: data.react, turn };
}

async function readCompareStream(
  response: Response,
  input: string,
  conversationId: string,
  onUpdate?: (update: CompareUpdate) => void
) {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let baseline: AgentResponse | undefined;
  let react: AgentResponse | undefined;
  let finalPayload: Partial<CompareApiResponse> = {};

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      const event = parseSseEvent(chunk);
      if (!event) {
        continue;
      }

      if (event.event === "session" && event.data.session_id) {
        sessionByConversation.set(conversationId, event.data.session_id);
        persistState();
      }
      if (event.event === "baseline") {
        baseline = event.data as AgentResponse;
        onUpdate?.({ kind: "baseline", response: baseline });
      }
      if (event.event === "react") {
        react = event.data as AgentResponse;
        onUpdate?.({ kind: "react", response: react });
      }
      if (event.event === "done") {
        finalPayload = event.data as Partial<CompareApiResponse>;
      }
      if (event.event === "error") {
        throw new Error(event.data.error ?? "Streaming comparison failed");
      }
    }

    if (done) {
      break;
    }
  }

  if (!baseline || !react) {
    throw new Error("Streaming comparison ended before both responses were received");
  }

  if (finalPayload.session_id) {
    sessionByConversation.set(conversationId, finalPayload.session_id);
    persistState();
  }

  const turn = normalizeTurn(finalPayload.turn, conversationId, input, baseline, react);

  turns = [...turns, turn];
  conversations = updateConversationTitle(conversations, conversationId, input);

  if (finalPayload.telemetry) {
    telemetry = [...finalPayload.telemetry, ...telemetry];
  }
  persistState();

  return { baseline, react, turn };
}

function parseSseEvent(chunk: string) {
  const lines = chunk.split("\n");
  const event = lines.find((line) => line.startsWith("event:"))?.slice(6).trim() ?? "message";
  const data = lines
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");

  if (!data) {
    return null;
  }

  return {
    event,
    data: JSON.parse(data)
  };
}

function updateConversationTitle(source: Conversation[], conversationId: string, input: string) {
  return source.map((conversation) =>
    conversation.id === conversationId
      ? {
          ...conversation,
          title: input.length > 32 ? `${input.slice(0, 32)}...` : input,
          updatedAt: new Date().toISOString()
        }
      : conversation
  );
}

function normalizeTurn(
  turn: ChatTurn | undefined,
  conversationId: string,
  input: string,
  baseline: AgentResponse,
  react: AgentResponse
): ChatTurn {
  return {
    id: turn?.id ?? crypto.randomUUID(),
    conversationId,
    prompt: turn?.prompt ?? input,
    createdAt: turn?.createdAt ?? new Date().toISOString(),
    baseline: turn?.baseline ?? baseline,
    react: turn?.react ?? react
  };
}

function loadPersistedState(): PersistedChatState {
  const fallback = {
    conversations: [...seedConversations],
    turns: [],
    telemetry: [],
    sessions: {}
  };

  if (typeof localStorage === "undefined") {
    return fallback;
  }

  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return fallback;
    }

    const parsed = JSON.parse(raw) as Partial<PersistedChatState>;
    return {
      conversations: parsed.conversations?.length ? parsed.conversations : fallback.conversations,
      turns: Array.isArray(parsed.turns)
        ? parsed.turns.filter((turn) => Boolean(turn.conversationId))
        : fallback.turns,
      telemetry: Array.isArray(parsed.telemetry) ? parsed.telemetry : fallback.telemetry,
      sessions: parsed.sessions ?? fallback.sessions
    };
  } catch {
    return fallback;
  }
}

function persistState() {
  if (typeof localStorage === "undefined") {
    return;
  }

  const payload: PersistedChatState = {
    conversations,
    turns,
    telemetry,
    sessions: Object.fromEntries(sessionByConversation.entries())
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

export async function getTelemetry() {
  const response = await fetch(`${API_BASE_URL}/api/telemetry`);
  if (!response.ok) {
    return telemetry;
  }

  telemetry = (await response.json()) as TelemetryEvent[];
  persistState();
  return telemetry;
}

export async function getUsageSummary(): Promise<UsageSummary> {
  const response = await fetch(`${API_BASE_URL}/api/usage`);
  if (response.ok) {
    return (await response.json()) as UsageSummary;
  }

  const allResponses = turns.flatMap((turn) => [turn.baseline, turn.react]);
  return summarizeResponses(allResponses);
}

function summarizeResponses(responses: AgentResponse[]): UsageSummary {
  if (responses.length === 0) {
    return {
      totalTokens: 0,
      estimatedCost: 0,
      averageLatencyMs: 0
    };
  }

  return {
    totalTokens: responses.reduce((sum, response) => sum + response.totalTokens, 0),
    estimatedCost: responses.reduce((sum, response) => sum + response.costEstimate, 0),
    averageLatencyMs:
      responses.reduce((sum, response) => sum + response.latencyMs, 0) / responses.length
  };
}

async function readError(response: Response) {
  try {
    const payload = await response.json();
    return payload.detail ?? response.statusText;
  } catch {
    return response.statusText;
  }
}
