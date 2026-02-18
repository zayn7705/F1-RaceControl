# RaceControl Architecture

## Overview

RaceControl is designed as a modular, real-time system with clear separation of concerns across four main components: Ingestion, Replay Engine, State Engine, and Strategy Engine. The architecture supports deterministic replay, fault tolerance, and bounded-latency decision making.

## Core Modules

### 1. Ingestion Module

**Purpose**: Convert raw F1 race data (from FastF1/OpenF1) into normalized, timestamped telemetry events.

**Responsibilities**:
- Load historical race data from external APIs
- Normalize data into a consistent event schema
- Assign precise timestamps to each event
- Validate event structure and required fields

**Output**: Stream of normalized events conforming to `event_schema.json`

### 2. Replay Engine

**Purpose**: Emit events in real-time (or accelerated time) with configurable speed control.

**Responsibilities**:
- Maintain event sequence and ordering
- Control replay speed (1x, 5x, 20x real-time)
- Handle event buffering and delivery timing
- Support pause/resume functionality

**Output**: Timed event stream to State Engine

### 3. Race State Engine

**Purpose**: Maintain a consistent, deterministic view of race state for all drivers.

**Responsibilities**:
- Update driver positions, gaps, tire compounds, tire age, lap times
- Track race control events (safety car, flags)
- Generate periodic state snapshots (checkpoints)
- Ensure deterministic state evolution (same events → same state)
- Support state restoration from checkpoints

**Output**: Current race state snapshot, checkpoint files

### 4. Strategy Decision Engine

**Purpose**: Generate pit strategy recommendations based on current race state.

**Responsibilities**:
- Calculate optimal pit windows
- Evaluate undercut/overcut opportunities relative to competitors
- Trigger safety car strategy adjustments
- Perform bounded-time simulation (Monte Carlo or heuristic search)
- Generate recommendations for all drivers (with focus driver emphasis)

**Output**: Strategy recommendations (pit windows, tire choices, timing)

## Reliability Features

- **Checkpointing**: Periodic state snapshots to disk
- **Crash Recovery**: Restore from checkpoint + replay remaining events
- **Event Reordering**: Buffer to handle out-of-order events
- **Heartbeat Monitoring**: Health checks across modules (if multi-process)

## Data Flow

```
Historical Data → Ingestion → Normalized Events → Replay Engine → 
State Engine → Strategy Engine → Recommendations
```

## Performance Targets

- End-to-end latency: < 100ms (p95) for event → strategy output
- Throughput: > 1000 events/sec
- Recovery time: < 5 seconds from checkpoint
