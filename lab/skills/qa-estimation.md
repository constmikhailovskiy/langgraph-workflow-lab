---
name: qa-estimation
description: What a QA engineer should weigh when estimating test effort.
---

For each story, account for:

- New test cases for the acceptance criteria, including negative and boundary cases.
- Regression risk to existing flows the story touches.
- Whether the story needs new fixtures/test data or environment setup.
- Manual exploratory testing time for anything hard to automate cheaply.

Do not estimate 0 for a user-visible story — some verification is always needed.
