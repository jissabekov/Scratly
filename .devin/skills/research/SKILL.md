---
name: research
description: Run parallel web + GitHub-ecosystem research subagents and synthesize actionable recommendations for Scratly
argument-hint: "<topic>"
allowed-tools:
  - read
---

Launch background subagents (`run_subagent`, profile `subagent_explore`, `is_background=true`) in parallel — never sequentially — to keep the main context clean:

1. **Web-research agent**: state of the art (2024–2026) for the requested topic (e.g., conversation continuity/memory, relevancy/adaptive questioning, decision-point orchestration, multi-turn evals, latency). Deliverable: findings with source URLs, a ranked actionable-pattern list mapped to Scratly's known problems (A2 target repetition, A14 duplicate replies, A18 adaptive options never presented, web-research failures, ~12s p95 latency), and relevant open-source repos with approximate stars.
2. GitHub-ecosystem agent: highest-star agent repos (openai/codex, anthropics/claude-code, OpenHands, block/goose, aider…), the AGENTS.md convention (agents.md spec: precedence, recommended sections), Agent Skills format (SKILL.md frontmatter: name/description, progressive disclosure), and MCP servers relevant to this repo (github-mcp-server, crystaldba/postgres-mcp restricted mode, memory, sequential-thinking).

Then synthesize both reports into: (a) findings with sources, (b) top-N actionable patterns each mapped to a concrete Scratly change in the deterministic-policy + LLM-proposal architecture, (c) an adoption plan for agent instructions (AGENTS.md / skills / MCP config). Distill — do not paste raw subagent output.
