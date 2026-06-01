export type Provider = "openai" | "gemini" | "local";

export type ChatbotKind = "baseline" | "react";

export type Conversation = {
  id: string;
  title: string;
  updatedAt: string;
};

export type ChatTurn = {
  id: string;
  prompt: string;
  createdAt: string;
  baseline: AgentResponse;
  react: AgentResponse;
};

export type AgentResponse = {
  kind: ChatbotKind;
  title: string;
  content: string;
  latencyMs: number;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  costEstimate: number;
  status: "success" | "error";
  errorCode?: string;
  steps?: number;
};

export type TelemetryEvent = {
  id: string;
  timestamp: string;
  event: string;
  provider: Provider;
  model: string;
  latencyMs: number;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  costEstimate: number;
  stepCount: number;
  errorCode?: string;
};

export type UsageSummary = {
  totalTokens: number;
  estimatedCost: number;
  averageLatencyMs: number;
};

export type ProviderModel = {
  provider: Provider;
  label: string;
  models: string[];
};
