# Claude Code External Research Notebook

This file is the temporary external-research entrypoint for Claude Code.

It exists because the user explicitly requested:

1. read external/community/video/article explanations first
2. form an initial view
3. then read the local Claude Code source

This file is not the final long-term architecture writeup. The long-term docs live under:

- [../../../reports/analysis/reference/claude_code/README.md](../../../reports/analysis/reference/claude_code/README.md)

## Current Working Thesis

Claude Code is useful to us mainly because it demonstrates a practical agent architecture that:

- treats context as a managed budget, not a giant transcript
- uses prompt-based compaction instead of retrieval-first compaction
- separates planning/execution/coordinator/worker roles
- treats permissions and tool execution as a pipeline, not a boolean flag

For the `shi_analyzer`, this matters because the current analyzer still shows:

- `window-first` selection bias
- `forward` / carrier over-weighting
- insufficient message-level `shi core` analysis

## External Source Set

### Official docs

- Claude Code subagents:
  - <https://code.claude.com/docs/en/sub-agents>
- Claude Code memory:
  - <https://code.claude.com/docs/en/memory>
- Claude Code settings:
  - <https://docs.anthropic.com/en/docs/claude-code/settings>
- Anthropic cookbook, context engineering:
  - <https://platform.claude.com/cookbook/tool-use-context-engineering-context-engineering-tools>

### Community / reverse-engineering analyses

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

## Initial External Conclusions

### 1. Claude Code does not treat “long context” as “just use a bigger model window”

The official cookbook and community reverse-engineering agree on the same design pressure:

- long sessions accumulate:
  - user messages
  - assistant messages
  - tool requests/results
  - file reads
  - compaction summaries
- so context management must be:
  - staged
  - lossy in controlled ways
  - explicit about what survives

This is directly relevant to us because the planned message-first analyzer must not simply ship “all related messages” into the model.

### 2. Claude Code’s compact path is fundamentally prompt-based

The official context-engineering cookbook explicitly describes compaction as:

- summarizing a transcript nearing the window limit
- preserving architectural decisions, unresolved questions, and key facts
- discarding redundant content

This matters because the user explicitly called out that Claude Code does not appear to use RAG as the main compact mechanism.

That is consistent with both:

- the official cookbook framing
- the local source layout under `src/services/compact/*`

### 3. Subagents are a context-isolation mechanism, not just an org-chart feature

The official subagents docs emphasize:

- separate context windows
- distinct tools and permissions
- keeping exploration noise out of the main thread
- fresh-vs-resume distinction:
  - a new subagent starts fresh
  - a resumed subagent keeps its prior history

This is highly relevant to us because the current analyzer overmixes:

- exploration
- `shi` judgment
- relation assembly
- review scheduling

### 4. Memory and CLAUDE.md are distinct

Official docs distinguish:

- CLAUDE.md:
  - stable written instructions/rules
- auto memory:
  - learned notes/patterns
- settings:
  - separate from both
  - configure permissions, environment, tools, plugins, and subagent defaults

This distinction maps well to our future analyzer:

- stable ontology/rubric/group role assumptions
- versus evolving reviewed findings and group-specific observations

### 5. Community writeups are most useful when they expose operational patterns

The more trustworthy community articles do not just say “Claude Code is smart”.
They usually surface concrete patterns like:

- preview-only for huge results
- layered compaction
- different handling for file reads versus generic tool output
- explicit output budget reservation

Those patterns are portable. Surface-level “it uses context well” commentary is not.

## What To Carry Into Local Source Reading

When reading local Claude Code source, focus on these questions:

1. how is the system prompt prefix assembled and cached?
2. what exactly gets stripped before compaction?
3. how does compaction preserve reconstruction value?
4. how are permissions/modes/subagents separated?
5. what should map to our future:
   - `message-first analyzer`
   - relation graph
   - review scheduling
   - cross-window aggregation

## Immediate Relevance To `shi_analyzer`

The future analyzer should borrow these architectural ideas:

- stable prompt/context prefix
- structured compact summary
- explicit token budgeting
- separate worker contexts
- coordinator synthesis
- distinct lanes for:
  - stable rules
  - runtime settings/mode
  - evolving memory

It should not blindly copy:

- Claude Code’s coding-task-specific workflow language
- shell/tool permission logic as-is
- transcript-specific assumptions that do not map to QQ message analysis
