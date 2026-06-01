import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, vi } from "vitest";
import { App } from "./App";

const baselineResponse = {
  kind: "baseline",
  title: "Baseline Chatbot",
  content: "Baseline API reply from full XLSX prompt.",
  latencyMs: 800,
  promptTokens: 260,
  completionTokens: 90,
  totalTokens: 350,
  costEstimate: 0.0035,
  status: "success",
  steps: 1
};

const reactResponse = {
  kind: "react",
  title: "ReAct Agent",
  content: "ReAct API reply from catalog tools.",
  latencyMs: 1200,
  promptTokens: 410,
  completionTokens: 182,
  totalTokens: 592,
  costEstimate: 0.0059,
  status: "success",
  steps: 3
};

const telemetryPayload = [
  {
    id: "event-1",
    timestamp: new Date().toISOString(),
    event: "CHATBOT_BASELINE",
    provider: "openai",
    model: "gpt-4o",
    latencyMs: 800,
    promptTokens: 260,
    completionTokens: 90,
    totalTokens: 350,
    costEstimate: 0.0035,
    stepCount: 1
  },
  {
    id: "event-2",
    timestamp: new Date().toISOString(),
    event: "AGENT_END",
    provider: "openai",
    model: "gpt-4o",
    latencyMs: 1200,
    promptTokens: 410,
    completionTokens: 182,
    totalTokens: 592,
    costEstimate: 0.0059,
    stepCount: 3
  }
];

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  );
}

function jsonResponse(payload: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" }
    })
  );
}

describe("AI Deal Hunter UI", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/api/compare")) {
          const body = JSON.parse(String(init?.body ?? "{}"));
          return jsonResponse({
            baseline: baselineResponse,
            react: reactResponse,
            session_id: "session-1",
            telemetry: telemetryPayload,
            usage: {
              totalTokens: 942,
              estimatedCost: 0.0094,
              averageLatencyMs: 1000
            },
            turn: {
              id: "turn-1",
              prompt: body.message,
              createdAt: new Date().toISOString(),
              baseline: baselineResponse,
              react: reactResponse
            }
          });
        }
        if (url.endsWith("/api/telemetry")) {
          return jsonResponse(telemetryPayload);
        }
        if (url.endsWith("/api/usage")) {
          return jsonResponse({
            totalTokens: 942,
            estimatedCost: 0.0094,
            averageLatencyMs: 1000
          });
        }
        return jsonResponse({ detail: "Not found" }, 404);
      })
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("changes model options when provider changes", async () => {
    const user = userEvent.setup();
    renderApp();

    await user.selectOptions(screen.getByLabelText("Provider"), "gemini");

    expect(screen.getByLabelText("Model")).toHaveValue("gemini-1.5-flash");
  });

  it("renders both chatbot responses after sending a prompt", async () => {
    const user = userEvent.setup();
    renderApp();

    await user.type(
      screen.getByPlaceholderText(/ask for the best deal/i),
      "Find the cheapest laptop with coupon SAVE10"
    );
    await user.click(screen.getByRole("button", { name: /send/i }));

    expect(await screen.findByText(/Baseline API reply/i)).toBeInTheDocument();
    expect(await screen.findByText(/ReAct API reply/i)).toBeInTheDocument();
  });

  it("shows telemetry and updates usage summary", async () => {
    const user = userEvent.setup();
    renderApp();

    await user.type(screen.getByPlaceholderText(/ask for the best deal/i), "Find a phone deal");
    await user.click(screen.getByRole("button", { name: /send/i }));
    await waitFor(() => expect(screen.getByText(/tokens:/i)).toHaveTextContent(/tokens: 942/i));

    await user.click(screen.getByRole("tab", { name: /telemetry/i }));

    expect(await screen.findByText("CHATBOT_BASELINE")).toBeInTheDocument();
    expect(screen.getAllByText("AGENT_END").length).toBeGreaterThan(0);
  });
});
