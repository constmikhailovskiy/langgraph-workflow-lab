---
name: devops-estimation
description: What a DevOps engineer should weigh when estimating infra/deployment effort.
---

For each story, account for:

- New infra, config, secrets, or feature flags required to ship safely.
- Deployment/rollout strategy and rollback plan for risky changes.
- Monitoring, alerting, or dashboards needed to observe the new behavior.
- CI/CD pipeline changes.

If a story is pure application code with no infra/deploy impact, estimate 0.
