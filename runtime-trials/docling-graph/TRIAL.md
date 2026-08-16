# Docling Graph — 2-hour runtime trial

Source: https://github.com/docling-project/docling-graph
Source ref: main at trial start
Purpose: runtime qualification of Docling Graph as an execution capability.

Trial contract:
- Load source into the runtime workspace.
- Install its Python package and runtime dependencies.
- Run the repository test suite / smoke validation available in the checkout.
- Keep the trial worker alive for up to 120 minutes after successful validation.
- Capture a receipt with source revision, install result, validation result, start/end timestamps, and failure/recovery state.

Classification target: REAL only after execution receipt and telemetry are observed.
