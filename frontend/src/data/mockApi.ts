import type {
  AgentResponse,
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
    models: ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"]
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

let conversations = [...seedConversations];
let turns: ChatTurn[] = [];
let telemetry: TelemetryEvent[] = [];
const sessionByConversation = new Map<string, string>();

type CompareApiResponse = {
  baseline: AgentResponse;
  react: AgentResponse;
  turn?: ChatTurn;
  session_id?: string;
  telemetry?: TelemetryEvent[];
  usage?: UsageSummary;
};

export async function listConversations() {
  return conversations;
}

export async function createConversation() {
  const conversation: Conversation = {
    id: `conv-${crypto.randomUUID()}`,
    title: "New product search",
    updatedAt: new Date().toISOString()
  };
  conversations = [conversation, ...conversations];
  return conversation;
}

export async function sendComparisonMessage(
  input: string,
  provider: Provider,
  model: string,
  conversationId: string
) {
  const sessionId = sessionByConversation.get(conversationId);
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
    const message = await readError(response);
    throw new Error(message);
  }

  const data = (await response.json()) as CompareApiResponse;
  if (data.session_id) {
    sessionByConversation.set(conversationId, data.session_id);
  }

  const turn: ChatTurn =
    data.turn ??
    ({
      id: crypto.randomUUID(),
      prompt: input,
      createdAt: new Date().toISOString(),
      baseline: data.baseline,
      react: data.react
    } satisfies ChatTurn);

  turns = [...turns, turn];
  conversations = conversations.map((conversation) =>
    conversation.id === conversationId
      ? {
          ...conversation,
          title: input.length > 32 ? `${input.slice(0, 32)}...` : input,
          updatedAt: new Date().toISOString()
        }
      : conversation
  );

  if (data.telemetry) {
    telemetry = [...data.telemetry, ...telemetry];
  }

  return { baseline: data.baseline, react: data.react, turn };
}

export async function getTelemetry() {
  const response = await fetch(`${API_BASE_URL}/api/telemetry`);
  if (!response.ok) {
    return telemetry;
  }

  telemetry = (await response.json()) as TelemetryEvent[];
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
