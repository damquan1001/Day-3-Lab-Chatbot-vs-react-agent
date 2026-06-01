import ast
import json
import os
import re
from typing import Any, Dict, List, Mapping, Optional, Tuple

from src.agent.guards import (
    SCOPE_SAFETY_PROMPT,
    check_input_guards,
    contains_sensitive_input,
    is_greeting_only,
    requires_catalog_tools,
)
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger


class ReActAgent:
    """
    ReAct-style agent: Thought -> Action -> Observation loops.

    version=1: legacy parser (Action must end the message).
    version=2: flexible parser, parse retry, duplicate guard, catalog tool gate.
    """

    def __init__(
        self,
        llm: LLMProvider,
        tools: List[Dict[str, Any]],
        max_steps: int = 5,
        version: int = 1,
    ):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.version = version
        self.history: List[Dict[str, Any]] = []
        self.last_run_metrics: Dict[str, Any] = self._empty_metrics()
        self._seen_actions: set[str] = set()
        self._successful_tool_calls: int = 0
        self._parse_retry_used: bool = False

    def get_system_prompt(self) -> str:
        tool_descriptions = "\n".join(
            self._format_tool_description(tool) for tool in self.tools
        )
        v2_rules = ""
        if self.version >= 2:
            v2_rules = """
- Do not repeat the same Action with identical arguments.
- For price/search/compare/cart questions, always call a catalog tool first; never Final Answer from memory alone.
"""

        return f"""
You are a ReAct shopping agent for Lab 3.
You specialize in tech/IT products: mice, keyboards, monitors, laptops, headphones, webcams, and similar gear.
This catalog does NOT contain clothing, food, or general household items — never suggest those.
Use tools for lookup, comparison, and math. Do not invent tool outputs or products outside catalog observations.

{SCOPE_SAFETY_PROMPT}

Available tools:
{tool_descriptions}

Use exactly one of these formats each step:
Thought: your reasoning
Action: tool_name({{"arg": "value"}})

Or, when enough observations are available:
Thought: your reasoning
Final Answer: detailed shopping advice for the user

Rules:
- Call tools when the user asks for catalog facts, prices, totals, ratings, or delivery.
- Feed each Observation into the next Thought.
- If a tool fails or returns no data, explain that in the next Thought and try a better query.
- Never output an Action for a tool that is not listed.
- Final Answer must sound like an agent explaining its decision, not a one-line chatbot.
- Final Answer is user-facing: never mention file names, paths, spreadsheets, databases, or tool names.
- Answer in Vietnamese by default for this lab UI, unless the user explicitly asks for another language.
- Final Answer should be very detailed and comprehensive, using at least 8-12 natural sentences or 5-8 detailed bullets.
- You MUST first summarize or list all the available options/products found from your search/filter (the full data).
- Then, include: the chosen product/shop, final or sale price, rating, delivery time, why it beats the other alternatives, any description-based caveat, and a clear buying recommendation.
- Do not answer only "X is a good choice." The user should see the comparison logic.
{v2_rules}
""".strip()

    def _reset_run_state(self) -> None:
        self._seen_actions = set()
        self._successful_tool_calls = 0
        self._parse_retry_used = False
        self.last_run_metrics = self._empty_metrics()

    def run(self, user_input: str) -> str:
        self._reset_run_state()

        guarded = check_input_guards(user_input)
        if guarded:
            if contains_sensitive_input(user_input):
                event = "SAFETY_BLOCKED"
            elif is_greeting_only(user_input):
                event = "GREETING"
            else:
                event = "OUT_OF_SCOPE"
            logger.log_event(
                event,
                {
                    "input_length": len(user_input),
                    "version": self.version,
                },
            )
            logger.log_event("AGENT_END", {"steps": 0, "status": event.lower()})
            return guarded

        logger.log_event(
            "AGENT_START",
            {
                "input": user_input,
                "model": self.llm.model_name,
                "tools": [tool.get("name") for tool in self.tools],
                "version": self.version,
            },
        )

        scratchpad = f"User: {user_input}"

        for step in range(1, self.max_steps + 1):
            response = self.llm.generate(
                scratchpad,
                system_prompt=self.get_system_prompt(),
            )
            content = str(response.get("content", "")).strip()
            self._add_response_metrics(response, step)
            self._track_llm_request(response)

            logger.log_event(
                "AGENT_STEP",
                {
                    "step": step,
                    "llm_preview": content[:500],
                    "usage": response.get("usage", {}),
                    "latency_ms": response.get("latency_ms"),
                    "version": self.version,
                },
            )

            if self.version >= 2:
                outcome, scratchpad, maybe_answer = self._process_step_v2(
                    content, scratchpad, user_input, step
                )
                if outcome == "return":
                    return maybe_answer
                continue

            outcome, scratchpad, maybe_answer = self._process_step_v1(
                content, scratchpad, user_input, step
            )
            if outcome == "return":
                return maybe_answer

        logger.log_event("AGENT_END", {"steps": self.max_steps, "status": "max_steps"})
        return (
            "I could not complete the request within the step limit. "
            "Please ask with a narrower product name or fewer constraints."
        )

    def _process_step_v1(
        self,
        content: str,
        scratchpad: str,
        user_input: str,
        step: int,
    ) -> Tuple[str, str, str]:
        final_answer = self._parse_final_answer(content)
        if final_answer:
            return self._complete_final_answer(
                user_input, scratchpad, content, final_answer, step
            )

        action = self._parse_action_v1(content)
        observation = self._resolve_observation(content, action, step)
        new_scratchpad = (
            f"{scratchpad}\n\nAssistant:\n{content}\n"
            f"Observation: {observation}"
        )
        return "continue", new_scratchpad, ""

    def _process_step_v2(
        self,
        content: str,
        scratchpad: str,
        user_input: str,
        step: int,
    ) -> Tuple[str, str, str]:
        action = self._parse_action_v2(content)
        if action is not None:
            tool_name, raw_args = action
            observation = self._execute_tool(tool_name, raw_args)
            new_scratchpad = (
                f"{scratchpad}\n\nAssistant:\n{content}\n"
                f"Observation: {observation}"
            )
            return "continue", new_scratchpad, ""

        final_answer = self._parse_final_answer(content)
        if final_answer:
            if requires_catalog_tools(user_input) and self._successful_tool_calls == 0:
                logger.log_event(
                    "AGENT_FINAL_BLOCKED_NO_TOOLS",
                    {"step": step, "answer_preview": final_answer[:300]},
                )
                new_scratchpad = (
                    f"{scratchpad}\n\nAssistant:\n{content}\n"
                    "Observation: You must call at least one catalog tool "
                    "(search_products, compare_products, get_product_price, or "
                    "calculate_cart_total) and use its Observation before Final Answer."
                )
                return "continue", new_scratchpad, ""

            return self._complete_final_answer(
                user_input, scratchpad, content, final_answer, step
            )

        observation = self._resolve_observation(content, None, step)
        new_scratchpad = (
            f"{scratchpad}\n\nAssistant:\n{content}\n"
            f"Observation: {observation}"
        )
        return "continue", new_scratchpad, ""

    def _complete_final_answer(
        self,
        user_input: str,
        scratchpad: str,
        content: str,
        final_answer: str,
        step: int,
    ) -> Tuple[str, str, str]:
        if self._final_answer_is_too_thin(final_answer):
            logger.log_event(
                "AGENT_FINAL_TOO_THIN",
                {"step": step, "answer_preview": final_answer[:300]},
            )
            rewritten_answer = self._rewrite_thin_final_answer(
                user_input=user_input,
                scratchpad=scratchpad,
                latest_content=content,
                thin_answer=final_answer,
                step=step,
            )
            if rewritten_answer and not self._final_answer_is_too_thin(rewritten_answer):
                final_answer = rewritten_answer
                status = "rewritten_final"
            elif step >= self.max_steps:
                final_answer = rewritten_answer or final_answer
                status = "final"
            else:
                rewrite_hint = (
                    rewritten_answer
                    if rewritten_answer
                    else "The rewrite was still too short."
                )
                new_scratchpad = (
                    f"{scratchpad}\n\nAssistant:\n{content}\n"
                    f"Observation: Final Answer is too short for this shopping agent. "
                    f"Previous rewrite attempt: {rewrite_hint}\n"
                    "Write a much more detailed Vietnamese Final Answer now."
                )
                return "continue", new_scratchpad, ""
        else:
            status = "final"

        self.history.append(
            {
                "user": user_input,
                "steps": step,
                "final_answer": final_answer,
            }
        )
        logger.log_event("AGENT_END", {"steps": step, "status": status})
        return "return", scratchpad, final_answer

    def _resolve_observation(
        self,
        content: str,
        action: Optional[Tuple[str, str]],
        step: int,
    ) -> str:
        if action is not None:
            tool_name, raw_args = action
            return self._execute_tool(tool_name, raw_args)

        logger.log_event(
            "AGENT_PARSE_ERROR",
            {"step": step, "content_preview": content[:500], "version": self.version},
        )
        if self.version >= 2 and not self._parse_retry_used:
            self._parse_retry_used = True
            logger.log_event("AGENT_PARSE_RETRY", {"step": step})
            return (
                "Parser error: no Action or Final Answer found. "
                'RETRY: Output exactly one line: Action: tool_name({"query": "..."}) '
                "with raw JSON only, no markdown."
            )
        return (
            "Parser error: no Action or Final Answer found. "
            "Use Action: tool_name({\"arg\": \"value\"}) or Final Answer: ..."
        )

    def _execute_tool(self, tool_name: str, args: str) -> str:
        if self.version >= 2:
            fingerprint = self._action_fingerprint(tool_name, args)
            if fingerprint in self._seen_actions:
                logger.log_event(
                    "AGENT_DUPLICATE_BLOCKED",
                    {
                        "tool": tool_name,
                        "args_preview": args[:200],
                    },
                )
                return (
                    "Duplicate action blocked. Use a different tool/query "
                    "or proceed to Final Answer."
                )
            self._seen_actions.add(fingerprint)

        tool = self._find_tool(tool_name)
        if tool is None:
            logger.log_event("AGENT_TOOL_ERROR", {"tool": tool_name, "error": "not_found"})
            return f"Tool {tool_name} not found."

        func = tool.get("func") or tool.get("function") or tool.get("callable")
        if not callable(func):
            logger.log_event(
                "AGENT_TOOL_ERROR",
                {"tool": tool_name, "error": "missing_callable"},
            )
            return f"Tool {tool_name} has no callable func."

        try:
            parsed_args = self._parse_action_args(args)
            if isinstance(parsed_args, Mapping):
                result = func(**dict(parsed_args))
            elif isinstance(parsed_args, (list, tuple)):
                result = func(*parsed_args)
            elif parsed_args in (None, ""):
                result = func()
            else:
                result = func(parsed_args)
        except Exception as exc:
            logger.log_event(
                "AGENT_TOOL_ERROR",
                {"tool": tool_name, "args": args, "error": str(exc)},
            )
            return f"Tool {tool_name} failed: {exc}"

        observation = (
            result
            if isinstance(result, str)
            else json.dumps(result, ensure_ascii=False, default=str)
        )
        logger.log_event(
            "AGENT_TOOL_CALL",
            {
                "tool": tool_name,
                "args": args,
                "observation_preview": observation[:500],
            },
        )
        if self.version >= 2 and self._is_successful_observation(observation):
            self._successful_tool_calls += 1
        return observation

    def _is_successful_observation(self, observation: str) -> bool:
        lowered = observation.lower()
        if lowered.startswith("tool ") and " not found" in lowered:
            return False
        if lowered.startswith("tool ") and " failed:" in lowered:
            return False
        if lowered.startswith("duplicate action blocked"):
            return False
        if lowered.startswith("parser error"):
            return False
        return True

    def _action_fingerprint(self, tool_name: str, raw_args: str) -> str:
        parsed = self._parse_action_args(raw_args)
        if isinstance(parsed, Mapping):
            payload = json.dumps(parsed, sort_keys=True, ensure_ascii=False)
        else:
            payload = str(parsed)
        return f"{tool_name}:{payload}"

    def _find_tool(self, tool_name: str) -> Optional[Dict[str, Any]]:
        for tool in self.tools:
            if tool.get("name") == tool_name:
                return tool
        return None

    def _format_tool_description(self, tool: Mapping[str, Any]) -> str:
        parameters = tool.get("parameters")
        parameter_text = f" Args: {parameters}" if parameters else ""
        return f"- {tool.get('name')}: {tool.get('description')}{parameter_text}"

    def _parse_action_v1(self, content: str) -> Optional[Tuple[str, str]]:
        match = re.search(
            r"Action\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)\s*$",
            content,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return None
        return match.group(1), match.group(2).strip()

    def _parse_action_v2(self, content: str) -> Optional[Tuple[str, str]]:
        cleaned = self._strip_code_fence(content)

        match = re.search(
            r"Action\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match:
            return match.group(1), match.group(2).strip()

        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            action_match = re.match(
                r"Action\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:\((.*))?$",
                line,
                flags=re.IGNORECASE,
            )
            if not action_match:
                continue
            tool_name = action_match.group(1)
            inline_args = (action_match.group(2) or "").strip()
            if inline_args.endswith(")"):
                return tool_name, inline_args[:-1].strip()
            if inline_args:
                return tool_name, inline_args
            if index + 1 < len(lines):
                return tool_name, lines[index + 1]
        return None

    def _parse_final_answer(self, content: str) -> str:
        match = re.search(
            r"Final Answer\s*:\s*(.*)",
            content,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return match.group(1).strip() if match else ""

    def _rewrite_thin_final_answer(
        self,
        user_input: str,
        scratchpad: str,
        latest_content: str,
        thin_answer: str,
        step: int,
    ) -> str:
        rewrite_prompt = f"""
User request:
{user_input}

ReAct scratchpad and tool observations:
{scratchpad}

Latest assistant response:
{latest_content}

Thin final answer that must be improved:
{thin_answer}

Rewrite the final answer in Vietnamese. Output only the final user-facing answer, no "Final Answer:" label.
Requirements:
- Provide a very detailed and comprehensive answer, using at least 8-12 natural sentences or 5-8 detailed bullets.
- First, summarize or list ALL the available options/products found from the filter/search.
- Mention the chosen product/shop, price, rating, delivery time.
- Explain why it beats the other alternatives.
- Mention description-based caveats or say the description has no obvious red flag.
- End with a clear buying recommendation.
""".strip()

        try:
            response = self.llm.generate(
                rewrite_prompt,
                system_prompt=(
                    "You are a Vietnamese ReAct shopping advisor for tech products "
                    "(chuột, bàn phím, màn hình, laptop, tai nghe...). Rewrite short answers "
                    "into detailed, grounded buying advice. Do not invent facts outside "
                    "the provided scratchpad and observations. Never mention file names, "
                    "paths, spreadsheets, databases, or data sources."
                ),
            )
            self._add_response_metrics(response, step + 1)
            self._track_llm_request(response)
            rewritten = str(response.get("content", "")).strip()
            rewritten = self._parse_final_answer(rewritten) or rewritten
            logger.log_event(
                "AGENT_FINAL_REWRITE",
                {
                    "step": step,
                    "rewrite_preview": rewritten[:500],
                    "usage": response.get("usage", {}),
                    "latency_ms": response.get("latency_ms"),
                },
            )
            return rewritten
        except Exception as exc:
            logger.log_event("AGENT_FINAL_REWRITE_FAILED", {"error": str(exc)})
            return ""

    def _final_answer_is_too_thin(self, answer: str) -> bool:
        normalized = re.sub(r"\s+", " ", answer).strip()
        if len(normalized) < 400:
            return True

        sentence_count = len(re.findall(r"[.!?。]|[。！？]", normalized))
        bullet_count = len(re.findall(r"(^|\n)\s*[-*•]", answer))
        return sentence_count < 4 and bullet_count < 4

    def _parse_action_args(self, args: str) -> Any:
        args = args.strip()
        if not args:
            return {}

        cleaned = self._strip_code_fence(args)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        try:
            return ast.literal_eval(cleaned)
        except (SyntaxError, ValueError):
            pass

        keyword_args = self._parse_keyword_args(cleaned)
        if keyword_args is not None:
            return keyword_args

        return cleaned.strip("\"'")

    def _parse_keyword_args(self, args: str) -> Optional[Dict[str, Any]]:
        if "=" not in args:
            return None

        parsed: Dict[str, Any] = {}
        for part in self._split_args(args):
            if "=" not in part:
                return None
            key, value = part.split("=", 1)
            key = key.strip()
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
                return None
            parsed[key] = self._parse_action_args(value.strip())
        return parsed

    def _split_args(self, args: str) -> List[str]:
        parts: List[str] = []
        depth = 0
        quote: Optional[str] = None
        start = 0

        for index, char in enumerate(args):
            if quote:
                if char == quote and args[index - 1 : index] != "\\":
                    quote = None
                continue

            if char in ("'", '"'):
                quote = char
            elif char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
            elif char == "," and depth == 0:
                parts.append(args[start:index].strip())
                start = index + 1

        tail = args[start:].strip()
        if tail:
            parts.append(tail)
        return parts

    def _strip_code_fence(self, value: str) -> str:
        cleaned = value.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json|python)?\s*", "", cleaned, flags=re.I)
            cleaned = re.sub(r"\s*```", "", cleaned)
        return cleaned.strip()

    def _track_llm_request(self, response: Mapping[str, Any]) -> None:
        try:
            from src.telemetry.metrics import tracker

            tracker.track_request(
                provider=str(response.get("provider") or self.llm.__class__.__name__),
                model=self.llm.model_name,
                usage=dict(response.get("usage") or {}),
                latency_ms=int(response.get("latency_ms") or 0),
            )
        except Exception as exc:
            logger.error(f"Failed to track agent LLM metric: {exc}")

    def _empty_metrics(self) -> Dict[str, Any]:
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "latency_ms": 0,
            "steps": 0,
        }

    def _add_response_metrics(self, response: Mapping[str, Any], step: int) -> None:
        usage = dict(response.get("usage") or {})
        self.last_run_metrics["prompt_tokens"] += int(usage.get("prompt_tokens", 0) or 0)
        self.last_run_metrics["completion_tokens"] += int(
            usage.get("completion_tokens", 0) or 0
        )
        self.last_run_metrics["total_tokens"] += int(usage.get("total_tokens", 0) or 0)
        self.last_run_metrics["latency_ms"] += int(response.get("latency_ms", 0) or 0)
        self.last_run_metrics["steps"] = step


def resolve_agent_version(req_version: Optional[int] = None) -> int:
    if req_version is not None:
        return int(req_version)
    return int(os.getenv("AGENT_VERSION", "1"))


def build_catalog_react_agent(
    llm: LLMProvider,
    max_steps: int = 5,
    version: Optional[int] = None,
) -> ReActAgent:
    from src.tools.catalog_tools import build_catalog_tools

    resolved_version = resolve_agent_version(version)
    return ReActAgent(
        llm=llm,
        tools=build_catalog_tools(),
        max_steps=max_steps,
        version=resolved_version,
    )
