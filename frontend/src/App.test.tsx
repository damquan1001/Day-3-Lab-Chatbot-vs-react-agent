import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App } from "./App";

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

describe("AI Deal Hunter UI", () => {
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

    expect(await screen.findByText(/lowest listed price/i)).toBeInTheDocument();
    expect(await screen.findByText(/checked item availability/i)).toBeInTheDocument();
  });

  it("shows telemetry and updates usage summary", async () => {
    const user = userEvent.setup();
    renderApp();

    await user.type(screen.getByPlaceholderText(/ask for the best deal/i), "Find a phone deal");
    await user.click(screen.getByRole("button", { name: /send/i }));
    await waitFor(() => expect(screen.getByText(/tokens:/i)).toHaveTextContent(/tokens: 942/i));

    await user.click(screen.getByRole("tab", { name: /telemetry/i }));

    expect(await screen.findByText("CHATBOT_BASELINE")).toBeInTheDocument();
    expect(screen.getAllByText("LLM_METRIC").length).toBeGreaterThan(0);
  });
});
