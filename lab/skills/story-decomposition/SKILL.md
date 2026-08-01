---
name: story-decomposition
description: Rubric for decomposing a brief into implementable, estimable user stories. Use when planning stories from a normalized brief.
---

- Each story should be independently implementable and testable — if two items always ship together, merge them.
- Write acceptance criteria as observable behavior ("user sees X after Y"), not implementation detail.
- Split by user-visible increment, not by engineering layer (don't emit one story per side).
- Prefer 3-7 stories; a single "do everything" story is too coarse to estimate.
