# Coding Style

Python code in this repository must stay small, typed, and explicit.

Use `asyncio` APIs for runtime work. Do not hide network I/O behind blocking
helpers, and do not add background work that can change tunnel latency without
tests covering the shutdown and error path.

Type safety is strict:

- no broad `Any`;
- no untyped JSON passed across public boundaries;
- no silent coercions for config, protocol fields, or webhook payloads;
- exported APIs must have precise annotations.

Errors must be explicit and actionable. Use SDK error types for user-facing
failures, preserve the original exception with `from error` when context
matters, and reject unsupported config instead of ignoring it.

Dependencies must stay small and conventional. Runtime dependencies are limited
to protocol/config essentials. Optional integrations live behind extras.

Tests must cover behavior, not only happy paths. Runtime protocol changes need
unit tests, fake-engine integration tests, and an opt-in real-engine e2e path
when the behavior reaches the engine.

Code comments are acceptable when they explain non-obvious runtime or protocol
choices. Avoid comments that only restate the code.
