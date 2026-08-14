# Challenger 1 (Milestone 1) Dispatch

## Mission
Adversarially challenge and stress-test the `EVORoutingEngine` implementation in `services/gis/src/gis_service/routing_engine.py`.

## Reading
- `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\ORIGINAL_REQUEST.md`
- `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\PROJECT.md`
- `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\GEMINI.md`
- `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\worker_m1\handoff.md`

## Testing Requirements
1. Write and execute an adversarial stress test script targeting:
   - High-throughput route calculation (e.g. 1000 simulated calls).
   - Extreme coordinates (boundary of Coquitlam, opposite corners of BC, poles, null coordinates).
   - Simulated OSRM socket drops, connection timeouts, corrupt responses, 502/503 errors.
   - Verification that `continue_straight=true` is present across all query URLs.
2. Confirm performance, latency, and failure resiliency.
3. Write your findings, empirical results, and verdict (`APPROVE` or `REJECT`) to:
`c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\challenger_m1_1\handoff.md`
