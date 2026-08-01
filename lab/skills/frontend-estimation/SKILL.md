---
name: frontend-estimation
description: What a frontend engineer should weigh when estimating implementation effort. Use when estimating the frontend side of a story list.
---

For each story, account for:

- All UI states: loading, empty, error, and success — not just the default render.
- Responsive layout and accessibility (keyboard nav, screen-reader labels).
- Client-side validation and its parity with backend rules.
- Integration with the API contract, including handling partial/failed responses.

If a story has no user-facing surface, estimate 0 rather than padding.
