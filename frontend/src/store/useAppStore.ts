import { create } from "zustand";
import type { ChatTurn, Conversation, Provider, TelemetryEvent, UsageSummary } from "../types";

type AppState = {
  provider: Provider;
  model: string;
  activeConversationId: string;
  conversations: Conversation[];
  turns: ChatTurn[];
  telemetry: TelemetryEvent[];
  usage: UsageSummary;
  setProvider: (provider: Provider, model: string) => void;
  setModel: (model: string) => void;
  setActiveConversationId: (id: string) => void;
  setConversations: (conversations: Conversation[]) => void;
  addConversation: (conversation: Conversation) => void;
  addTurn: (turn: ChatTurn) => void;
  setTelemetry: (events: TelemetryEvent[]) => void;
  setUsage: (usage: UsageSummary) => void;
};

export const useAppStore = create<AppState>((set) => ({
  provider: "openai",
  model: "gpt-4o",
  activeConversationId: "conv-1",
  conversations: [],
  turns: [],
  telemetry: [],
  usage: {
    totalTokens: 0,
    estimatedCost: 0,
    averageLatencyMs: 0
  },
  setProvider: (provider, model) => set({ provider, model }),
  setModel: (model) => set({ model }),
  setActiveConversationId: (activeConversationId) => set({ activeConversationId }),
  setConversations: (conversations) => set({ conversations }),
  addConversation: (conversation) =>
    set((state) => ({
      conversations: [conversation, ...state.conversations],
      activeConversationId: conversation.id,
      turns: []
    })),
  addTurn: (turn) => set((state) => ({ turns: [...state.turns, turn] })),
  setTelemetry: (telemetry) => set({ telemetry }),
  setUsage: (usage) => set({ usage })
}));
