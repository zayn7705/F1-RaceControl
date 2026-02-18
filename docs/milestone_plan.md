# Checkpoint Plan Plan

### Checkpoint 1: Proposal & Repository Setup
- **Status**: Complete
- **Deliverables**:
  - Project proposal document
  - Repository structure with documentation
  - Event schema definition
  - Example event files
  - Basic hello world script

### Checkpoint 2: Ingestion + Replay Engine
- **Target Date**: Week 8
- **Deliverables**:
  - FastF1 data loader
  - Event normalization pipeline
  - Replay engine with speed control
  - CLI runner for replay
- **Success Criteria**: Can replay one historical race with configurable speed

### Checkpoint 3: Race State Engine
- **Target Date**: Week 10
- **Deliverables**:
  - Driver state tracking (position, gaps, tires, lap times)
  - State update logic
  - Snapshot/checkpoint functionality
  - Deterministic replay validation
- **Success Criteria**: Same event log produces identical final state

### Checkpoint 4: Strategy Engine
- **Target Date**: Week 12
- **Deliverables**:
  - Pit window recommendation logic
  - Undercut/overcut evaluation
  - Safety car strategy triggers
  - Bounded-time simulation
- **Success Criteria**: Strategy recommendations generated during replay

### Checkpoint 5: Reliability + Metrics + Demo
- **Target Date**: Week 15
- **Deliverables**:
  - Checkpointing and crash recovery
  - Fault injection testing
  - Performance instrumentation (latency, throughput)
  - Performance report (p50/p95 metrics)
  - CLI demo with live updates
- **Success Criteria**: Full race demo with recovery and performance results
