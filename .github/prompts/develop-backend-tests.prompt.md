---
description: Retrofit tests for existing backend code - coverage gaps, missing edge cases, test quality audit
mode: test-engineer
input:
  - scope
---

# Develop Backend Tests

Write tests for existing untested backend code. Analyze code paths, write comprehensive tests.

## Process

1. Analyze existing code to identify untested paths
2. Write failing tests (RED) — behavior over implementation, fakes over mocks
3. Triangulate — multiple test cases per behavior
4. Report: tests written, coverage impact, testability concerns

## Rules

- NEVER write production code — only test code, fakes, fixtures
- Fakes over mocks — mock only at external boundaries
- Tests must fail first (RED phase)
- AAA pattern: Arrange → Act → Assert
- Naming: `test_<unit>_<behavior>_<condition>`
