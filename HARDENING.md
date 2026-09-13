# SDK lifecycle, cancellation, and concurrent archives

Tool cancellation and failures are recorded and propagated. Start metadata is reused so mutated arguments cannot rewrite the recorded input identity. Archive instances share a file lock, refuse appends to corrupted chains, preserve strict field types, and correctly verify an explicitly empty event list.

SDK lifecycle hooks can run in separate child tasks. Lineage is keyed by the shared SDK usage object across those callbacks; explicit non-SDK tracker calls retain task-local isolation. Completion releases the run state. Use one JEPMiddleware instance/run_id per Runner run, and choose either run-wide hooks or agent-scoped hooks to avoid recording the same callback twice. Existing agent hooks must be composed explicitly before instrumentation.

A real offline Runner test exercises OpenAI Agents SDK 0.22.2 with a local model and tracing disabled. This archive is an execution-observation envelope, not signed JEP-Core wire events. Cryptographic key trust and live authorization require separate profiles.
