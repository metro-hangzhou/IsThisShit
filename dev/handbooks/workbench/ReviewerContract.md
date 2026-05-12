# Reviewer Contract

Status: `draft_round_001`

Reviewer responsibilities:

- judge old workflow and new draft against explicit categories
- produce blocker-grade findings only
- distinguish structural flaws from optional polish
- use first-principles pressure to challenge needless complexity, wasted waits, and evidence-ignoring behavior
- check whether subagents received enough strategic context rather than only narrow local instructions
- check whether communication is flat enough for direct filesystem-mediated correction across roles

Reviewer must output:

- `question_id`
- `category`
- `claim_under_review`
- `challenge`
- `required_evidence`
- `blocking`
- `resolution_status`

Reviewer may not:

- silently accept missing archive coverage
- treat user approval as implicit
- downgrade severe coupling issues into casual notes
- preserve clearly wasteful waiting layers when evidence already decides the outcome
