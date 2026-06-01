# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Trần Hoàng Nam
- **Student ID**: 2A202600870
- **Date**: 2026-06-01

---

## I. Technical Contribution (15 Points)

*Describe your specific contribution to the codebase (e.g., implemented a specific tool, fixed the parser, etc.).*

- **Roles & Responsibilities**: Code Merging, System Integration, and contributing to Part 3 (Personal Insights).
- **Code Highlights**: 
  - **Code Merging & Integration**: Responsible for merging code from different team members, resolving merge conflicts, and connecting various modules to ensure the entire system works cohesively.
  - **System Assembly**: Integrated the tools, agent logic, and API server components, ensuring smooth data flow between different parts of the project.
  - **Refinement**: Assisted in refining the codebase structure and standardizing the integration points across the project.

---

## II. Debugging Case Study (10 Points)

*Analyze a specific failure event you encountered during the lab using the logging system.*

- **Problem Description**: The ReAct Agent returned overly brief results in English ("The AKKO 3098B Plus at PhongVu is a good wireless keyboard option...") without comparing it to other products, completely ignoring the request to answer in Vietnamese.
- **Log Source**: `logs/2026-06-01.log` or trace printed from `api_server.py`.
- **Diagnosis**: 
  1. The Tool returned too little data (defaulting to only 5 results).
  2. The Agent model was "lazy" in generating answers, and the `_final_answer_is_too_thin()` function checking for `< 220` characters was not strict enough to block a 157-character English response. When the rewrite function failed, it slipped right through to the final result.
- **Solution**: Upgraded `_final_answer_is_too_thin()` to check for `len < 400` and enforced `sentence_count < 4`. This was accompanied by expanding the observation size from Tools so the LLM wouldn't lack data.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

*Reflect on the reasoning capability difference.*

1.  **Reasoning**: The `Thought` block allows the Agent to think step-by-step, call search tools, and analyze the returned data before reaching a conclusion. Unlike a standard Chatbot that is overwhelmed by a mountain of raw CSV data, the Agent can proactively filter and extract information itself using query tools.
2.  **Reliability**: For questions that require scanning the entire inventory to find unique products without knowing the exact keyword, the Agent might perform worse than a Chatbot because the Search Tool is limited by keywords and result count (if keywords don't match, the Tool returns nothing). Meanwhile, the Chatbot has the full CSV, so it manually "searches" using the LLM's context window.
3.  **Observation**: Observation is the lifeblood of ReAct. If the observation is truncated or empty, the Agent will be confused, hallucinate data, or return an abrupt error. Expanding the data returned for the Observation dictated 90% of the Final Answer's quality.

---

## IV. Future Improvements (5 Points)

*How would you scale this for a production-level AI agent system?*

- **Scalability**: Instead of writing a basic Python tool to read Excel files manually, the system should be integrated with a Vector Database or Elasticsearch for Semantic Search capabilities rather than relying on Exact Match.
- **Safety**: Build a parallel Guardrail Agent specifically to moderate the ReAct Agent's Final Answer, preventing it from being lazy or answering in English before sending it to the End-User.
- **Performance**: Implement async processing when calling multiple tools in parallel instead of sequentially to reduce latency (currently it takes nearly 10s for 2-3 steps).
