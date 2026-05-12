# Claude Code External Research

## Scope

This document summarizes the external material reviewed before reading the local `claude-code/` source snapshot.

It is intentionally split into:

- official docs / cookbook
- community or reverse-engineered analyses
- migration value for our own agent work

## Source Set

### Official

- Claude Code subagents:
  - <https://code.claude.com/docs/en/sub-agents>
- Claude Code memory:
  - <https://code.claude.com/docs/en/memory>
- Claude Code settings:
  - <https://docs.anthropic.com/en/docs/claude-code/settings>
- Anthropic cookbook, context engineering:
  - <https://platform.claude.com/cookbook/tool-use-context-engineering-context-engineering-tools>

### Community / reverse-engineering

- Shen Han, 阶段 5：上下文与内存管理深度解剖:
  - <https://shenhan.cc/projects/claude-code/05_module_context>
- 潘智祥, 拆解 Claude Code：它是怎么在 200K 上下文里“永远不会聊爆”:
  - <https://panzhixiang.cn/2026/claude-code-context-compression/>
- ClaudeWorld, Context Compaction:
  - <https://claude-world.com/tutorials/s06-context-compaction/>
- Decode Claude, Inside Claude Code's Compaction System:
  - <https://decodeclaude.com/claude-code-compaction/>
- Claude Code Guides, Passing Context Between Claude Code Subagents:
  - <https://claudecodeguides.com/passing-context-between-claude-code-subagents-guide/>

## Official Findings

### 1. Subagents are framed as context-isolated specialists

The official subagent docs emphasize that each subagent has:

- its own context window
- a custom system prompt
- its own tool/permission boundary
- a fresh instance by default
- an explicit resume path when you want to continue the same subagent instead of starting over

The official docs present this less as “multi-agent hype” and more as a practical way to:

- avoid flooding the main thread
- keep expensive local exploration away from the main conversation
- specialize behavior per task type

This is a strong signal that context isolation is an intended product feature, not an implementation accident.

### 2. Memory is a two-system model

Official memory docs distinguish:

- `CLAUDE.md`
  - explicit instructions, rules, project conventions
- auto memory
  - learned patterns and notes written by Claude itself
- settings
  - JSON configuration for permissions, environment variables, plugins, subagent defaults, and other runtime behavior

This split matters because it prevents one memory channel from trying to do both:

- stable normative guidance
- evolving operational observations

It also means Claude Code does not collapse:

- instructions
- learned memory
- runtime configuration

into one undifferentiated context blob.

### 3. The official cookbook frames compaction as context engineering, not retrieval

The Anthropic cookbook describes compaction as:

- summarizing a near-full conversation
- preserving key decisions, unresolved issues, and facts
- discarding redundant content

This confirms that prompt-based structured compact is an intended design pattern in the Anthropic ecosystem, not just a private implementation quirk.

## Community Findings

### 1. The strongest community analyses converge on “layered compaction”

The most useful reverse-engineering articles converge on the same shape:

- cheap early reductions first
- then larger transcript compaction later
- plus post-compact rehydration or continuation state

Even when naming differs, the community consensus is that Claude Code does not rely on a single “one-shot summarize” step.

### 2. File reads and giant tool results are treated differently from generic transcript text

Several community analyses highlight patterns like:

- preview-only for very large tool outputs
- file-read special handling
- truncation/rehydration sequences

This is relevant to us because analyzer context growth is also uneven:

- direct message evidence
- relation graph evidence
- asset-shell metadata
- weak nearby chatter

should not all be compacted the same way.

### 3. Community analyses are strongest when they expose operational mechanisms

The reverse-engineering writeups are most useful when they surface things like:

- output budgets
- preview-size thresholds
- separate memory channels
- mode gating

They are less useful when they only make general claims like:

- “Claude Code is great at long context”

## First-Principles Interpretation

Claude Code’s external literature strongly suggests a design philosophy:

- the context window is a scarce execution substrate
- different classes of information have different continuation value
- agent behavior should change by mode
- subagents are partly a context-budget instrument

This maps directly to the user’s request for the `shi_analyzer`:

- do not pass giant QQ windows blindly
- do not let message form dominate `shi` judgment
- separate stable guidance from evolving findings

## Relevance To Our Planned Redesign

The external research most directly supports these redesign directions:

1. prompt-based structured compact instead of RAG-first compact
2. message-packet assembly instead of raw window dumping
3. separate:
   - coordinator synthesis
   - worker analysis
   - review scheduling
4. explicit token budgeting by information class
5. stable memory lanes:
   - ontology/rules
   - reviewed learnings
   - cross-window group profile summaries
6. explicit fresh-vs-resume semantics for worker analyzers rather than silently assuming every sub-analysis starts from zero

## What External Research Cannot Settle

External materials alone cannot tell us:

- exactly how the local source snapshot behaves now
- which community claims are stale or inaccurate
- how much of Claude Code’s design is portable to QQ `shi` analysis

That is why the next layer is local source decomposition, not blind copying.
