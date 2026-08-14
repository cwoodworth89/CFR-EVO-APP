# Challenger 2 (Milestone 1) Dispatch

## Mission
Adversarially challenge and stress-test the `EVORoutingEngine` implementation in `services/gis/src/gis_service/routing_engine.py` with focus on Station 1 tactical corridor accuracy, apparatus unit parsing, and response physics.

## Reading
- `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\ORIGINAL_REQUEST.md`
- `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\PROJECT.md`
- `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\GEMINI.md`
- `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\worker_m1\handoff.md`

## Testing Requirements
1. Write and execute an empirical test script targeting:
   - Coordinate accuracy and polygon bounds for tactical corridors A (Mariner) and B (Gordon Ave).
   - Invariance across all apparatus types (`E1`, `L1`, `R1`, `Q5`, `WT4`, `MEDIC1`, `CHIEF1`, unknown units).
   - Speed/ETA mathematics comparison between Emergency (Code 3) and Routine (Code 1).
   - Memory leaks / recursion issues during high-volume queries.
2. Confirm empirical correctness.
3. Write your findings, empirical results, and verdict (`APPROVE` or `REJECT`) to:
`c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\challenger_m1_2\handoff.md`
