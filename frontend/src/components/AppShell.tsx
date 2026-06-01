import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Activity,
  Bot,
  Database,
  FileSpreadsheet,
  MessageSquarePlus,
  PanelLeft,
  Settings,
  Sparkles
} from "lucide-react";
import * as Tabs from "@radix-ui/react-tabs";
import { useEffect, useMemo, useState } from "react";
import {
  createConversation,
  getTelemetry,
  getUsageSummary,
  listConversationTurns,
  listConversations,
  providerModels,
  sendComparisonMessage
} from "../data/mockApi";
import { formatCurrency, formatLatency } from "../lib/utils";
import { useAppStore } from "../store/useAppStore";
import type { AgentResponse, ChatTurn, Provider } from "../types";
import type { TelemetryEvent } from "../types";
import { MarkdownContent } from "./MarkdownContent";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";

type PendingTurn = Omit<ChatTurn, "baseline" | "react"> & {
  baseline?: AgentResponse;
  react?: AgentResponse;
};

export function AppShell() {
  const {
    activeConversationId,
    addConversation,
    addTurn,
    conversations,
    model,
    provider,
    setConversations,
    setModel,
    setProvider,
    setTelemetry,
    setTurns,
    setUsage,
    telemetry,
    turns,
    usage
  } = useAppStore();
  const [input, setInput] = useState("");
  const [pendingTurn, setPendingTurn] = useState<PendingTurn | null>(null);

  const providerConfig = useMemo(
    () => providerModels.find((item) => item.provider === provider) ?? providerModels[0],
    [provider]
  );

  const conversationsQuery = useQuery({
    queryKey: ["conversations"],
    queryFn: listConversations
  });
  const turnsQuery = useQuery({
    queryKey: ["turns", activeConversationId],
    queryFn: () => listConversationTurns(activeConversationId)
  });
  const telemetryQuery = useQuery({
    queryKey: ["telemetry", activeConversationId],
    queryFn: getTelemetry
  });
  const usageQuery = useQuery({
    queryKey: ["usage", activeConversationId, turns.length],
    queryFn: getUsageSummary
  });

  const createConversationMutation = useMutation({
    mutationFn: createConversation,
    onSuccess: addConversation
  });

  const sendMessageMutation = useMutation({
    mutationFn: (message: string) =>
      sendComparisonMessage(message, provider, model, activeConversationId, ({ kind, response }) => {
        setPendingTurn((turn) =>
          turn
            ? {
                ...turn,
                [kind]: response
              }
            : turn
        );
      }),
    onSuccess: async ({ turn }) => {
      addTurn(turn);
      setPendingTurn(null);
      setInput("");
      const [nextTelemetry, nextUsage] = await Promise.all([getTelemetry(), getUsageSummary()]);
      setTelemetry(nextTelemetry);
      setUsage(nextUsage);
    },
    onError: () => {
      setPendingTurn(null);
    }
  });

  useEffect(() => {
    if (conversationsQuery.data) {
      setConversations(conversationsQuery.data);
    }
  }, [conversationsQuery.data, setConversations]);

  useEffect(() => {
    if (turnsQuery.data) {
      setTurns(turnsQuery.data);
    }
  }, [turnsQuery.data, setTurns]);

  useEffect(() => {
    if (telemetryQuery.data) {
      setTelemetry(telemetryQuery.data);
    }
  }, [telemetryQuery.data, setTelemetry]);

  useEffect(() => {
    if (usageQuery.data) {
      setUsage(usageQuery.data);
    }
  }, [usageQuery.data, setUsage]);

  function handleProviderChange(nextProvider: Provider) {
    const nextConfig = providerModels.find((item) => item.provider === nextProvider);
    if (nextConfig) {
      setProvider(nextProvider, nextConfig.models[0]);
    }
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || sendMessageMutation.isPending) {
      return;
    }

    setPendingTurn({
      id: crypto.randomUUID(),
      conversationId: activeConversationId,
      prompt: trimmed,
      createdAt: new Date().toISOString()
    });
    sendMessageMutation.mutate(trimmed);
  }

  const latestTurn = pendingTurn ?? turns.at(-1);
  const loading = sendMessageMutation.isPending;

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      <aside className="hidden h-screen w-72 shrink-0 border-r border-border bg-card px-4 py-4 lg:flex lg:flex-col">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-sm font-semibold">AI Deal Hunter</h1>
            <p className="text-xs text-muted-foreground">Chatbot vs ReAct lab</p>
          </div>
        </div>

        <Button
          className="mt-5 w-full justify-start"
          variant="outline"
          onClick={() => createConversationMutation.mutate()}
        >
          <MessageSquarePlus className="h-4 w-4" />
          New conversation
        </Button>

        <div className="mt-5 rounded-md border border-border bg-muted/45 p-3">
          <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
            <FileSpreadsheet className="h-4 w-4 text-accent" />
            Simulated database
          </div>
          <p className="mt-2 text-sm font-medium">banggia.xlsx</p>
          <p className="mt-1 text-xs text-muted-foreground">Backend catalog for baseline and tools</p>
        </div>

        <div className="mt-5 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          <PanelLeft className="h-4 w-4" />
          Conversations
        </div>
        <div className="scrollbar-subtle mt-2 flex-1 space-y-1 overflow-y-auto">
          {conversations.map((conversation) => (
            <button
              className={`w-full rounded-md px-3 py-2 text-left text-sm transition-colors ${
                conversation.id === activeConversationId
                  ? "bg-primary text-primary-foreground"
                  : "hover:bg-muted"
              }`}
              key={conversation.id}
              onClick={() => useAppStore.getState().setActiveConversationId(conversation.id)}
              type="button"
            >
              <span className="block truncate font-medium">{conversation.title}</span>
              <span
                className={`mt-0.5 block text-xs ${
                  conversation.id === activeConversationId
                    ? "text-primary-foreground/75"
                    : "text-muted-foreground"
                }`}
              >
                {new Date(conversation.updatedAt).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit"
                })}
              </span>
            </button>
          ))}
        </div>
      </aside>

      <main className="flex h-screen min-w-0 flex-1 flex-col overflow-hidden">
        <header className="flex min-h-16 flex-wrap items-center justify-between gap-3 border-b border-border bg-card px-4 py-3 lg:px-6">
          <div>
            <div className="flex items-center gap-2">
              <Bot className="h-5 w-5 text-primary" />
              <h2 className="text-base font-semibold">Deal comparison arena</h2>
            </div>
            <p className="text-sm text-muted-foreground">
              Baseline chatbot and ReAct agent answer the same deal-hunting prompt.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <label className="sr-only" htmlFor="provider">
              Provider
            </label>
            <select
              className="h-9 rounded-md border border-input bg-card px-3 text-sm"
              id="provider"
              onChange={(event) => handleProviderChange(event.target.value as Provider)}
              value={provider}
            >
              {providerModels.map((item) => (
                <option key={item.provider} value={item.provider}>
                  {item.label}
                </option>
              ))}
            </select>

            <label className="sr-only" htmlFor="model">
              Model
            </label>
            <select
              className="h-9 rounded-md border border-input bg-card px-3 text-sm"
              id="model"
              onChange={(event) => setModel(event.target.value)}
              value={model}
            >
              {providerConfig.models.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>
        </header>

        <Tabs.Root className="flex min-h-0 flex-1 flex-col overflow-hidden" defaultValue="chat">
          <div className="border-b border-border bg-card px-4 lg:px-6">
            <Tabs.List className="flex gap-1">
              <Tabs.Trigger
                className="border-b-2 border-transparent px-3 py-3 text-sm font-medium text-muted-foreground data-[state=active]:border-primary data-[state=active]:text-foreground"
                value="chat"
              >
                Chat
              </Tabs.Trigger>
              <Tabs.Trigger
                className="border-b-2 border-transparent px-3 py-3 text-sm font-medium text-muted-foreground data-[state=active]:border-primary data-[state=active]:text-foreground"
                value="telemetry"
              >
                Telemetry
              </Tabs.Trigger>
              <Tabs.Trigger
                className="border-b-2 border-transparent px-3 py-3 text-sm font-medium text-muted-foreground data-[state=active]:border-primary data-[state=active]:text-foreground"
                value="settings"
              >
                Settings
              </Tabs.Trigger>
            </Tabs.List>
          </div>

          <Tabs.Content className="min-h-0 flex-1 overflow-hidden p-4 lg:p-6" value="chat">
            <div className="grid h-full min-h-0 gap-4 xl:grid-cols-2">
              <ResponsePanel
                accent="border-primary/30"
                loading={loading && !latestTurn?.baseline}
                response={latestTurn?.baseline}
                title="Baseline Chatbot"
              />
              <ResponsePanel
                accent="border-accent/40"
                loading={loading && !latestTurn?.react}
                response={latestTurn?.react}
                title="ReAct Agent"
              />
            </div>
          </Tabs.Content>

          <Tabs.Content className="min-h-0 flex-1 overflow-hidden p-4 lg:p-6" value="telemetry">
            <TelemetryTable events={telemetry} />
          </Tabs.Content>

          <Tabs.Content className="min-h-0 flex-1 overflow-hidden p-4 lg:p-6" value="settings">
            <div className="grid gap-4 xl:grid-cols-3">
              <section className="rounded-md border border-border bg-card p-4 shadow-panel">
                <div className="flex items-center gap-2">
                  <Settings className="h-5 w-5 text-primary" />
                  <h3 className="font-semibold">Runtime preference</h3>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">
                  The UI sends provider and model choices only. API keys, local model loading, and
                  Excel parsing remain backend responsibilities.
                </p>
                <div className="mt-4 grid gap-3">
                  <InfoRow label="Provider" value={providerConfig.label} />
                  <InfoRow label="Model" value={model} />
                  <InfoRow label="Data source" value="deals_inventory.xlsx" />
                </div>
              </section>
              <section className="rounded-md border border-border bg-card p-4 shadow-panel xl:col-span-2">
                <div className="flex items-center gap-2">
                  <Database className="h-5 w-5 text-accent" />
                  <h3 className="font-semibold">Backend adapter contract</h3>
                </div>
                <div className="mt-4 grid gap-2 text-sm text-muted-foreground md:grid-cols-2">
                  {[
                    "POST /api/compare",
                    "GET /api/telemetry",
                    "GET /api/usage",
                    "listConversations()",
                    "createConversation()"
                  ].map((item) => (
                    <code className="rounded-md border border-border bg-muted px-3 py-2" key={item}>
                      {item}
                    </code>
                  ))}
                </div>
              </section>
            </div>
          </Tabs.Content>
        </Tabs.Root>

        <form
          className="border-t border-border bg-card px-4 py-3 lg:px-6"
          onSubmit={handleSubmit}
        >
          <div className="flex gap-2">
            <input
              className="h-11 min-w-0 flex-1 rounded-md border border-input bg-background px-4 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask for the best deal, coupon, stock check, or shipped total..."
              value={input}
            />
            <Button disabled={loading || input.trim().length === 0} type="submit">
              Send
            </Button>
          </div>
        </form>

        <footer className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-border bg-muted px-4 py-2 text-xs text-muted-foreground lg:px-6">
          <span className="flex items-center gap-1.5">
            <Activity className="h-3.5 w-3.5" />
            Tokens: <strong className="text-foreground">{usage.totalTokens}</strong>
          </span>
          <span>
            Cost: <strong className="text-foreground">{formatCurrency(usage.estimatedCost)}</strong>
          </span>
          <span>Cost estimate uses reported total tokens at $0.01 per 1K tokens.</span>
          <span>
            Avg latency:{" "}
            <strong className="text-foreground">{formatLatency(usage.averageLatencyMs)}</strong>
          </span>
          <span>
            Runtime:{" "}
            <strong className="text-foreground">
              {providerConfig.label} / {model}
            </strong>
          </span>
        </footer>
      </main>
    </div>
  );
}

function ResponsePanel({
  accent,
  loading,
  response,
  title
}: {
  accent: string;
  loading: boolean;
  response?: {
    content: string;
    latencyMs: number;
    totalTokens: number;
    costEstimate: number;
    status: "success" | "error";
    steps?: number;
  };
  title: string;
}) {
  return (
    <section className={`flex min-h-0 flex-col rounded-md border bg-card shadow-panel ${accent}`}>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3">
        <div>
          <h3 className="font-semibold">{title}</h3>
          <p className="text-xs text-muted-foreground">
            {title.startsWith("ReAct") ? "Tool-aware reasoning path" : "Direct LLM response"}
          </p>
        </div>
        <Badge className={response?.status === "success" ? "border-accent/40 text-accent" : ""}>
          {loading ? "running" : response?.status ?? "idle"}
        </Badge>
      </div>

      <div className="scrollbar-subtle min-h-0 flex-1 overflow-y-auto p-4">
        {response ? (
          <MarkdownContent content={response.content} />
        ) : loading ? (
          <div className="space-y-3">
            <div className="h-4 w-3/4 animate-pulse rounded bg-muted" />
            <div className="h-4 w-5/6 animate-pulse rounded bg-muted" />
            <div className="h-4 w-2/3 animate-pulse rounded bg-muted" />
          </div>
        ) : (
          <div className="flex h-full min-h-72 items-center justify-center text-center text-sm text-muted-foreground">
            Send a deal-hunting prompt to compare the baseline chatbot against the ReAct agent.
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 border-t border-border p-3 text-xs text-muted-foreground md:grid-cols-4">
        <InfoMetric label="Latency" value={response ? formatLatency(response.latencyMs) : "-"} />
        <InfoMetric label="Tokens" value={response ? String(response.totalTokens) : "-"} />
        <InfoMetric label="Cost" value={response ? formatCurrency(response.costEstimate) : "-"} />
        <InfoMetric label="Steps" value={response?.steps ? String(response.steps) : "-"} />
      </div>
    </section>
  );
}

function TelemetryTable({ events }: { events: TelemetryEvent[] }) {
  return (
    <section className="flex h-full min-h-0 flex-col overflow-hidden rounded-md border border-border bg-card shadow-panel">
      <div className="shrink-0 flex items-center justify-between border-b border-border px-4 py-3">
        <div>
          <h3 className="font-semibold">Structured telemetry</h3>
          <p className="text-xs text-muted-foreground">Events are returned by the backend API.</p>
        </div>
        <Badge>{events.length} events</Badge>
      </div>
      <div className="scrollbar-subtle min-h-0 flex-1 overflow-auto">
        <table className="min-w-[980px] w-full border-collapse text-left text-sm">
          <thead className="bg-muted text-xs uppercase text-muted-foreground">
            <tr>
              {[
                "Timestamp",
                "Event",
                "Provider",
                "Model",
                "Latency",
                "Prompt",
                "Completion",
                "Total",
                "Cost",
                "Steps",
                "Error"
              ].map((header) => (
                <th className="px-3 py-2 font-semibold" key={header}>
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {events.map((event) => (
              <tr className="border-t border-border" key={event.id}>
                <td className="px-3 py-2 text-xs text-muted-foreground">
                  {new Date(event.timestamp).toLocaleTimeString()}
                </td>
                <td className="px-3 py-2 font-medium">{event.event}</td>
                <td className="px-3 py-2">{event.provider}</td>
                <td className="px-3 py-2">{event.model}</td>
                <td className="px-3 py-2">{formatLatency(event.latencyMs)}</td>
                <td className="px-3 py-2">{event.promptTokens}</td>
                <td className="px-3 py-2">{event.completionTokens}</td>
                <td className="px-3 py-2">{event.totalTokens}</td>
                <td className="px-3 py-2">{formatCurrency(event.costEstimate)}</td>
                <td className="px-3 py-2">{event.stepCount}</td>
                <td className="px-3 py-2">{event.errorCode ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function InfoMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-muted/45 px-3 py-2">
      <div className="text-[11px] uppercase text-muted-foreground">{label}</div>
      <div className="mt-1 font-semibold text-foreground">{value}</div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-muted px-3 py-2 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
