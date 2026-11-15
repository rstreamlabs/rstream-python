# Repository guidance

## Shared conventions

Follow the existing architecture, naming and coding style. Preserve public contracts, authentication, certificate verification and project policy. Keep changes in the component that owns the behavior.

Update user documentation and examples when behavior changes. Run the relevant checks; place regression tests with the owning component. Keep secrets, execution logs, investigation notes and standalone upstream reproductions outside the repository.

## Repository-specific guidance

Follow `CODING_STYLE.md` and `CONTRIBUTING.md`. Keep the SDK framework-neutral and typed, with explicit lifecycle ownership. Preserve Python runtime support, optional dependency boundaries and ASGI/WSGI semantics. Reject unsupported capabilities explicitly; maintain the documented webhook parser limits.
