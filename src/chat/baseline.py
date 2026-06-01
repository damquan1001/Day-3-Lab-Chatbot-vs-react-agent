"""Shared chatbot baseline logic for CLI and HTTP API."""
import csv
import io
import os
import re
import zipfile
from pathlib import Path
from typing import Any, Generator
from xml.etree import ElementTree

from src.core.llm_provider import LLMProvider
from src.core.local_provider import LocalProvider
from src.core.openai_provider import OpenAIProvider
from src.core.gemini_provider import GeminiProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker
from src.agent.guards import (
    SCOPE_SAFETY_PROMPT,
    check_input_guards,
    contains_sensitive_input,
    is_greeting_only,
)

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[1] / "database" / "banggia.xlsx"
_SPREADSHEET_NS = {"xlsx": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_CELL_REF_PATTERN = re.compile(r"([A-Z]+)")

SYSTEM_PROMPT = (
    "You are the baseline chatbot for Lab 3 — a tech shopping assistant "
    "(mice, keyboards, monitors, laptops, headphones, and similar gear). "
    "Answer only from the product data pasted in the user prompt. "
    "You do not have access to tools, APIs, code execution, filtering functions, "
    "or calculators. Never suggest clothing, food, or products not in the data. "
    "Never mention file names, paths, spreadsheets, or where the data comes from "
    "in your reply. If a question needs multi-step lookup/math, do your best from "
    "the pasted table and be explicit about uncertainty.\n\n"
    f"{SCOPE_SAFETY_PROMPT}"
)


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Set {name} in .env")
    return value


def _resolve_local_model_path(model_name: str) -> str:
    local_path = os.getenv("LOCAL_MODEL_PATH", "").strip()
    if local_path:
        return local_path
    return os.path.join("models", f"{model_name}.gguf")

CATALOG_COLUMNS = [
    "category",
    "product_name",
    "shop_name",
    "price",
    "discount_percent",
    "price_after_discount",
    "rating",
    "max_delivery_days",
    "description",
]


def get_llm(
    provider: str,
    *,
    model_name: str | None = None,
    quiet: bool = False,
) -> LLMProvider:
    provider = provider.lower().strip()
    model_name = (model_name or _require_env("DEFAULT_MODEL")).strip()

    if provider == "local":
        model_path = _resolve_local_model_path(model_name)
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Local model not found: {model_path}. "
                "Set LOCAL_MODEL_PATH or DEFAULT_MODEL in .env, then download the GGUF file."
            )
        msg = f"Loading local model: {model_name} ({model_path})"
        if quiet:
            logger.log_event(
                "LLM_LOAD",
                {"provider": "local", "model": model_name, "path": model_path},
            )
        else:
            print(f"[local] {msg} (first run may take a few minutes)")
        return LocalProvider(model_path=model_path, model_name=model_name)

    if provider == "openai":
        api_key = _require_env("OPENAI_API_KEY")
        if api_key.startswith("your_"):
            raise ValueError("Set OPENAI_API_KEY in .env for provider openai")
        if not quiet:
            print(f"[openai] Using model: {model_name}")
        return OpenAIProvider(model_name=model_name, api_key=api_key)

    if provider in ("google", "gemini"):
        api_key = _require_env("GEMINI_API_KEY")
        if api_key.startswith("your_"):
            raise ValueError("Set GEMINI_API_KEY in .env for provider google")
        if not quiet:
            print(f"[google] Using model: {model_name}")
        return GeminiProvider(model_name=model_name, api_key=api_key)

    raise ValueError(f"Unknown provider: {provider}. Use: local | openai | google")


def get_default_provider() -> str:
    return _require_env("DEFAULT_PROVIDER")


def load_catalog_context(catalog_path: str | Path = DEFAULT_CATALOG_PATH) -> str:
    """
    Load the whole XLSX catalog into a compact CSV string for the baseline.

    This is intentionally not a search/filter tool. The baseline receives the
    whole table and leaves all lookup/reasoning to the LLM, which makes the
    chatbot-vs-agent limitation visible in traces and evaluations.
    """
    raw_rows = _read_first_worksheet(Path(catalog_path))
    if not raw_rows:
        return ""

    headers = [str(value or "").strip() for value in raw_rows[0]]
    records: list[dict[str, Any]] = []
    for row in raw_rows[1:]:
        if not any(value not in (None, "") for value in row):
            continue
        records.append(
            {
                header: row[position] if position < len(row) else ""
                for position, header in enumerate(headers)
            }
        )
    return build_catalog_context(records)


def build_catalog_context(rows: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CATALOG_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().strip()


def _read_first_worksheet(file_path: Path) -> list[list[Any]]:
    if not file_path.exists():
        raise FileNotFoundError(f"Catalog file not found: {file_path}")

    with zipfile.ZipFile(file_path) as archive:
        shared_strings = _read_shared_strings(archive)
        worksheet_names = [
            name
            for name in archive.namelist()
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        ]
        if not worksheet_names:
            raise ValueError(f"No worksheet found in catalog file: {file_path}")

        worksheet_names.sort()
        root = ElementTree.fromstring(archive.read(worksheet_names[0]))

    rows: list[list[Any]] = []
    for row_node in root.findall(".//xlsx:sheetData/xlsx:row", _SPREADSHEET_NS):
        row_values: list[Any] = []
        for cell_node in row_node.findall("xlsx:c", _SPREADSHEET_NS):
            column_index = _column_index(cell_node.attrib.get("r", ""))
            while len(row_values) <= column_index:
                row_values.append("")
            row_values[column_index] = _cell_value(cell_node, shared_strings)
        rows.append(row_values)
    return rows


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []

    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall(".//xlsx:si", _SPREADSHEET_NS):
        strings.append(
            "".join(
                text_node.text or ""
                for text_node in item.findall(".//xlsx:t", _SPREADSHEET_NS)
            )
        )
    return strings


def _cell_value(cell_node: ElementTree.Element, shared_strings: list[str]) -> Any:
    cell_type = cell_node.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(
            text_node.text or ""
            for text_node in cell_node.findall(".//xlsx:t", _SPREADSHEET_NS)
        )

    value_node = cell_node.find("xlsx:v", _SPREADSHEET_NS)
    if value_node is None:
        return ""

    raw_value = value_node.text or ""
    if cell_type == "s":
        return shared_strings[int(raw_value)]
    if cell_type == "b":
        return raw_value == "1"
    return raw_value


def _column_index(cell_ref: str) -> int:
    match = _CELL_REF_PATTERN.match(cell_ref)
    if not match:
        return 0

    index = 0
    for char in match.group(1):
        index = index * 26 + ord(char) - ord("A") + 1
    return index - 1


def build_prompt(
    history: list[dict[str, str]],
    user_input: str,
    catalog_context: str = "",
) -> str:
    lines: list[str] = []
    if catalog_context:
        lines.extend(
            [
                "PRODUCT CATALOG (internal — do not mention this label or any file/source to the user):",
                "```csv",
                catalog_context,
                "```",
                "",
                "Important baseline constraint: answer directly from this pasted table only.",
                "",
            ]
        )
    for turn in history:
        lines.append(f"User: {turn['user']}\nAssistant: {turn['assistant']}")
    lines.append(f"User: {user_input}")
    return "\n".join(lines)


class ChatbotBaseline:
    def __init__(
        self,
        llm: LLMProvider,
        catalog_path: str | Path = DEFAULT_CATALOG_PATH,
        catalog_context: str | None = None,
    ):
        self.llm = llm
        self.catalog_path = Path(catalog_path)
        self.catalog_context = (
            catalog_context
            if catalog_context is not None
            else load_catalog_context(self.catalog_path)
        )
        self.history: list[dict[str, str]] = []

    def complete(self, user_input: str) -> dict[str, Any]:
        """Non-streaming reply for API / metrics."""
        guarded = check_input_guards(user_input)
        if guarded:
            event = (
                "SAFETY_BLOCKED"
                if contains_sensitive_input(user_input)
                else "GREETING"
                if is_greeting_only(user_input)
                else "OUT_OF_SCOPE"
            )
            logger.log_event(event, {"input_length": len(user_input)})
            self.history.append({"user": user_input, "assistant": guarded})
            return {
                "reply": guarded,
                "model": self.llm.model_name,
                "provider": None,
                "usage": {},
                "latency_ms": 0,
                "catalog_path": str(self.catalog_path),
            }

        prompt = build_prompt(self.history, user_input, self.catalog_context)
        result = self.llm.generate(prompt, system_prompt=SYSTEM_PROMPT)
        content = result["content"]
        tracker.track_request(
            result.get("provider", "unknown"),
            self.llm.model_name,
            result.get("usage", {}),
            result.get("latency_ms", 0),
        )
        logger.log_event(
            "CHATBOT_TURN",
            {
                "user": user_input,
                "assistant_preview": content[:200],
                "stream": False,
                "model": self.llm.model_name,
                "catalog_path": str(self.catalog_path),
            },
        )
        self.history.append({"user": user_input, "assistant": content})
        return {
            "reply": content,
            "model": self.llm.model_name,
            "provider": result.get("provider"),
            "usage": result.get("usage"),
            "latency_ms": result.get("latency_ms"),
            "catalog_path": str(self.catalog_path),
        }

    def stream_tokens(self, user_input: str) -> Generator[str, None, None]:
        """Token generator for SSE; updates history when done."""
        guarded = check_input_guards(user_input)
        if guarded:
            yield guarded
            self.history.append({"user": user_input, "assistant": guarded})
            return

        prompt = build_prompt(self.history, user_input, self.catalog_context)
        chunks: list[str] = []
        for token in self.llm.stream(prompt, system_prompt=SYSTEM_PROMPT):
            chunks.append(token)
            yield token
        content = "".join(chunks)
        logger.log_event(
            "CHATBOT_TURN",
            {
                "user": user_input,
                "assistant_preview": content[:200],
                "stream": True,
                "model": self.llm.model_name,
                "catalog_path": str(self.catalog_path),
            },
        )
        self.history.append({"user": user_input, "assistant": content})

    def reply(self, user_input: str, stream: bool = True) -> str:
        """CLI: print to terminal."""
        if stream:
            print("Assistant: ", end="", flush=True)
            for token in self.stream_tokens(user_input):
                print(token, end="", flush=True)
            print()
            return self.history[-1]["assistant"]
        data = self.complete(user_input)
        print(f"Assistant: {data['reply']}")
        return data["reply"]
