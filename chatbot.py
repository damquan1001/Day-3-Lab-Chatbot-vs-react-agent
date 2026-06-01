"""
Chatbot baseline: plain LLM chat (no tools, no ReAct).
Provider: local (GGUF) | openai | google — via .env or --provider flag.
"""
import argparse
import os
import sys

from dotenv import load_dotenv

from src.chat.baseline import ChatbotBaseline, get_llm
from src.telemetry.logger import logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lab 3 — Chatbot baseline")
    parser.add_argument(
        "--provider",
        choices=["local", "openai", "google"],
        default=None,
        help="Override DEFAULT_PROVIDER from .env",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Use generate() instead of stream() (logs LLM_METRIC for API providers)",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    provider = args.provider or os.getenv("DEFAULT_PROVIDER", "local")

    logger.log_event("CHATBOT_START", {"provider": provider})

    try:
        llm = get_llm(provider)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    bot = ChatbotBaseline(llm)
    print(f"\nChatbot baseline ready ({provider}). Type 'quit' or 'exit' to leave.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Bye.")
            break

        bot.reply(user_input, stream=not args.no_stream)

    logger.log_event("CHATBOT_END", {"turns": len(bot.history)})


if __name__ == "__main__":
    main()
