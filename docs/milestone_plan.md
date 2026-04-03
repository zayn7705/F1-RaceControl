# Checkpoint plan

### Checkpoint 1: Proposal & Repository Setup
- **Status**: Complete
- **Deliverables**:
  - Project proposal document
  - Repository structure with documentation
  - Event schema definition
  - Example event files
  - Basic hello world script

### Checkpoint 2: Ingestion + Replay Engine
- **Status**: Complete
- **Deliverables**:
  - FastF1 data loader
  - Event normalization pipeline
  - Replay engine with speed control
  - CLI runner for replay
- **Success Criteria**: Can replay one historical race with configurable speed

### Checkpoint 3: Race State Engine
- **Status**: Complete
- **Deliverables**:
  - Driver state tracking (position, gaps, tires, lap times)
  - State update logic
  - Snapshot/checkpoint functionality
  - Deterministic replay validation
- **Success Criteria**: Same event log produces identical final state

### Checkpoint 4: Strategy Engine
- **Status**: Complete (replay-integrated engine)
- **Deliverables**:
  - Pit window recommendation logic
  - Undercut/overcut evaluation
  - Safety car strategy triggers
  - Bounded-time simulation
- **Success Criteria**: Strategy recommendations generated during replay

**Exploratory / in progress (Hungary 2022 what-if)**  
We are **exploring** an interactive counterfactual mode on top of the same event data: `src/strategy_mvp/` and `scripts/strategy_mvp_cli.py` (simple time model, benchmark among candidate strategies). This is a **prototype** for learning and iteration—physics, UX, and promises are **not** frozen. See `README.md`. It does not change the deterministic replay contract.

### Checkpoint 5: Reliability + Metrics + Demo
- **Target Date**: Week 15
- **Deliverables**:
  - Checkpointing and crash recovery
  - Fault injection testing
  - Performance instrumentation (latency, throughput)
  - Performance report (p50/p95 metrics)
  - CLI demo with live updates
- **Success Criteria**: Full race demo with recovery and performance results
