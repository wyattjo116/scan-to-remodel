---
name: record-decision
description: Record a decision in the project's brief/decisions.md and keep brief/brief.md in step. Use when the owner decides or rules something out (a variant, a style, a budget, a limit), when a goal is stated or changed, when a decision is reversed, or when you make a working assumption that later work will build on.
---

# Record a decision

Decisions live in `<project>/brief/decisions.md`, numbered and newest first. The brief (`brief.md`) says what is wanted now; the decision log says how it got that way.

1. Read the top of `decisions.md` for the last number. The next is one higher (`D-0001`, `D-0002`, ...). Never reuse or renumber.
2. Add the entry at the top:

```markdown
## D-0007 - Rear wing, not a full second floor (2026-03-14)

**Decided by:** the owner | Claude, as a working assumption
**Decision:** One or two sentences, in plain words.
**Why:** The reason given, in the owner's words where possible.
**Instead of:** What was considered and not chosen.
**Replaces:** D-0003 (if it reverses or changes an earlier one)
**Affects:** brief lines, variants or files that now need changing.
```

3. In the same turn, change the matching lines in `brief.md`: mark them Stated with the date, and say what they replace.
4. If Claude made the choice (a working assumption), say so in "Decided by", mark the brief line **Working**, and tell the owner so they can confirm or overrule it.
5. A reversed decision stays in the log. Add the new one and point "Replaces" at the old.

Record a decision when alternatives were real and later work depends on the choice. Do not record routine edits.
