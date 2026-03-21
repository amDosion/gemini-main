# Stop Conditions

## Active-Domain Stop Conditions

- reviewer gate is pass
- no failed, blocked, or unresolved pending work remains
- all required validator groups pass
- required consecutive accepted-session streak is reached
- the user explicitly stops the effort
- a hard blocker prevents safe continuation

## Video-Domain Specific Completion Rule

- The domain is not complete until the following are true:
  - backend is the single source for video capability definitions
  - frontend no longer carries business-specific video mode branching that should live in backend contracts
  - reference-image, styling, and extension flows are validated end-to-end for session/history persistence
  - the reference-project borrow list has been either implemented or explicitly rejected with reasons

## Rule

- A clean batch alone is not a stop signal.
- A domain that still mixes frontend business logic with backend policy cannot be treated as converged.
