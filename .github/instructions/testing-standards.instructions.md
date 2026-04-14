---
description: TDD methodology, test design patterns, fakes over mocks, triangulation
applyTo: "**/tests/**,**/__tests__/**,**/tests/**/*.py,**/tests/**/*.ts,**/tests/**/*.js,**/__tests__/**/*.ts,**/__tests__/**/*.js,**/*test*.py,**/*test*.ts,**/*test*.js,**/*spec*.ts,**/*spec*.js"
---

# Testing Standards

TDD is **mandatory**. RED → GREEN → REFACTOR. One test at a time. Verify it fails for the right reason.

## Core Rules

- **Behavior over implementation**: Test WHAT code does, not HOW
- **Fakes over mocks**: Mock only at external boundaries (HTTP APIs, time, random, filesystem). Everything else: inject the dependency, write a fake
- **Triangulation** (non-negotiable): Multiple inputs per behavior, zero/empty/null/boundary values, error cases, negative cases
- **AAA Pattern**: Arrange → Act → Assert. Act is usually ONE line
- **Naming**: `test_<unit>_<behavior>_<condition>`
- **Coverage**: With TDD, 100% is natural. Exclude: tests, `__init__.py`, migrations, TYPE_CHECKING, abstractmethod

## Anti-patterns

Testing implementation details · Tests that always pass · Flaky tests (fix or delete) · Over-mocking · Mock setup longer than test · Tests written after code · Single test case per behavior
