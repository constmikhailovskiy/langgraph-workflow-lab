---
name: backend-estimation
description: What a backend engineer should weigh when estimating implementation effort.
---

For each story, account for:

- Data model / migration changes, including backfills.
- New or changed API contracts, and any versioning/compat concerns.
- Business logic, validation, and edge cases — not just the happy path.
- Integration with existing services and any needed feature flags.

If a story has no backend surface area, estimate 0 rather than padding.
