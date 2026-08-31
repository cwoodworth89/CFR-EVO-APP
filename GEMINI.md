# CFR EVO: Workspace & Architectural Rules

> [!IMPORTANT]
> **This file is a pointer, not the rules.** The canonical, actively maintained rules for CFR EVO live in [`CLAUDE.md`](./CLAUDE.md). Read that file instead of this one — it covers the same ground (offline architecture, sibling import paths, kiosk deployment protocol, address normalization) plus current Claude Code conventions (skills in `.claude/skills/`, sub-agents in `.claude/agents/`).
>
> This file used to contain the full duplicate ruleset for Antigravity/Gemini sessions. It was collapsed to this pointer on 2026-08-20 to eliminate drift between two copies of the same rules — going forward, edit `CLAUDE.md` only. This file is kept solely so Antigravity's `GEMINI.md` auto-load convention still finds something and redirects correctly.

Two sections below remain here because they're specific to Antigravity's own multi-agent orchestration model (model tiers, `invoke_subagent`) and have no Claude Code equivalent — Claude Code's delegation model is described in `CLAUDE.md` §4 instead.

---

## Antigravity-Specific: Sub-Agent Delegation & Model Tier Allocation
To maximize token economy and avoid burning coordinator reasoning credits on mechanical tasks:
1. **Coordinator Role**: The main chat acts exclusively as the **System Architect & Coordinator** (managing roadmap phases, reviewing sub-agent deliverables, making architectural trade-offs, and reporting to the user).
2. **Mandatory Sub-Agent Invocation**: The coordinator MUST delegate implementation tasks to sub-agents via `invoke_subagent` instead of executing bulk file edits, script writing, test runners, or tile downloads in the main coordinator loop.
3. **Model Tier Allocation Matrix**:
   * **`Model: 'flash_lite'`**: Deterministic test runners (`feed_recorded_call.py`, `pytest`), mechanical file renames, dead code/import pruning, log parsing, and linting.
   * **`Model: 'flash'`**: Feature engineering, database migrations, shapefile ingestion scripts, React JSX component decomposition, tile pre-caching scripts, API route development.
   * **`Model: 'pro'`**: Deep mathematical reasoning, DSP STFT/FFT harmonic filter calculations, OSRM Lua routing profile math, LoRA quantization analysis, and complex concurrency deadlock diagnosis.
4. **Autonomous Background Execution**: Once a sub-agent is launched with clear instructions and acceptance criteria, the coordinator MUST provide a concise update to the user and immediately end the turn, letting the sub-agent run in the background.
5. **Skill Lookup**: Check `.claude/skills/` before drafting implementation plans. It is the single canonical location — the Antigravity copy under `.agents/skills/` was archived out of the repository on 2026-08-30 and was 10 days stale when it went.
