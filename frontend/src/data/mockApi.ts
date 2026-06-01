import type {
  AgentResponse,
  ChatTurn,
  Conversation,
  Provider,
  ProviderModel,
  TelemetryEvent,
  UsageSummary
} from "../types";

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
    title: "Laptop bundle hunt",
    updatedAt: new Date().toISOString()
  },
  {
    id: "conv-2",
    title: "Coupon stack test",
    updatedAt: new Date(Date.now() - 1000 * 60 * 48).toISOString()
  }
];

const seedTelemetry: TelemetryEvent[] = [
  makeEvent("AGENT_START", "openai", "gpt-4o", 0, 0, 0, 0),
  makeEvent("LLM_METRIC", "openai", "gpt-4o", 842, 312, 116, 2),
  makeEvent("TOOL_CALL", "openai", "gpt-4o", 118, 24, 18, 2),
  makeEvent("AGENT_END", "openai", "gpt-4o", 1310, 388, 142, 3)
];

let conversations = [...seedConversations];
let turns: ChatTurn[] = [];
let telemetry = [...seedTelemetry];

export async function listConversations() {
  await wait(120);
  return conversations;
}

export async function createConversation() {
  await wait(120);
  const conversation: Conversation = {
    id: `conv-${crypto.randomUUID()}`,
    title: "New deal hunt",
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
  await wait(650);

  const baseline = makeResponse("baseline", input, 890);
  const react = makeResponse("react", input, 1480);
  const turn: ChatTurn = {
    id: crypto.randomUUID(),
    prompt: input,
    createdAt: new Date().toISOString(),
    baseline,
    react
  };

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

  telemetry = [
    makeEvent("CHATBOT_BASELINE", provider, model, baseline.latencyMs, 268, 96, 1),
    makeEvent("AGENT_START", provider, model, 0, 0, 0, 0),
    makeEvent("TOOL_CALL", provider, model, 124, 38, 14, 1),
    makeEvent("LLM_METRIC", provider, model, react.latencyMs, 402, 176, react.steps ?? 3),
    makeEvent("AGENT_END", provider, model, react.latencyMs, 402, 176, react.steps ?? 3),
    ...telemetry
  ];

  return { baseline, react, turn };
}

export async function getTelemetry() {
  await wait(80);
  return telemetry;
}

export async function getUsageSummary(): Promise<UsageSummary> {
  await wait(80);
  const allResponses = turns.flatMap((turn) => [turn.baseline, turn.react]);
  const fallbackTokens = telemetry.reduce((sum, item) => sum + item.totalTokens, 0);
  const totalTokens =
    allResponses.reduce((sum, response) => sum + response.totalTokens, 0) || fallbackTokens;
  const estimatedCost =
    allResponses.reduce((sum, response) => sum + response.costEstimate, 0) ||
    telemetry.reduce((sum, item) => sum + item.costEstimate, 0);
  const averageLatencyMs =
    allResponses.length > 0
      ? allResponses.reduce((sum, response) => sum + response.latencyMs, 0) / allResponses.length
      : 1010;

  return {
    totalTokens,
    estimatedCost,
    averageLatencyMs
  };
}

function makeResponse(kind: "baseline" | "react", input: string, latencyMs: number): AgentResponse {
  const isReact = kind === "react";
  const promptTokens = isReact ? 402 : 268;
  const completionTokens = isReact ? 176 : 96;
  const totalTokens = promptTokens + completionTokens;

  return {
    kind,
    title: isReact ? "ReAct Agent" : "Baseline Chatbot",
    content: isReact
      ? `I inspected the simulated Excel deal sheet, checked item availability, applied the best eligible coupon, and compared final landed prices. Recommended deal: ${input} with the ReAct path because it can justify each step through observations.`
      : `Based on the prompt, a reasonable deal for "${input}" appears to be the lowest listed price. This baseline answer does not verify stock, coupon eligibility, or shipping constraints.`,
    latencyMs,
    promptTokens,
    completionTokens,
    totalTokens,
    costEstimate: Number(((totalTokens / 1000) * 0.01).toFixed(4)),
    status: "success",
    steps: isReact ? 3 : 1
  };
}

function makeEvent(
  event: string,
  provider: Provider,
  model: string,
  latencyMs: number,
  promptTokens: number,
  completionTokens: number,
  stepCount: number
): TelemetryEvent {
  const totalTokens = promptTokens + completionTokens;

  return {
    id: crypto.randomUUID(),
    timestamp: new Date().toISOString(),
    event,
    provider,
    model,
    latencyMs,
    promptTokens,
    completionTokens,
    totalTokens,
    costEstimate: Number(((totalTokens / 1000) * 0.01).toFixed(4)),
    stepCount
  };
}

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}
