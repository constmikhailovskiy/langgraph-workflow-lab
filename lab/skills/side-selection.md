---
name: side-selection
description: Rubric for picking which implementing sides (backend/frontend/qa/devops) a feature brief needs.
---

When choosing sides, err inclusive:

- Backend: any new/changed data, business logic, or API endpoint.
- Frontend: any new/changed UI, user-facing copy, or client-side state.
- QA: include whenever the feature is user-visible or touches shared logic — dedicated test coverage is rarely truly free.
- DevOps: only when the feature needs new infra, config, feature flags, or a deploy/rollout change — skip it for pure application-code changes.

Return only the JSON array requested; do not include a side that clearly does not apply.
