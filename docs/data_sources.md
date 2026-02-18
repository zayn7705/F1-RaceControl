# Data Sources

## Primary Data Source: FastF1

**FastF1** is a Python library that provides access to Formula 1 timing data, telemetry, and session information. It serves as our primary data source for historical race replays.

### Key Features
- Access to historical race data (2018-present)
- Lap timing data
- Telemetry data (speed, throttle, brake, gear, etc.)
- Pit stop information
- Track status (safety car, flags, etc.)
- Driver positions and gaps

### Installation
```bash
pip install fastf1
```

### Usage Example
```python
import fastf1

# Load a race session
session = fastf1.get_session(2023, 'Monaco', 'R')
session.load()

# Access lap data
laps = session.laps
```

## Alternative: OpenF1 API

**OpenF1** is a REST API that provides real-time and historical F1 data. It can serve as an alternative or complementary data source.

### Features
- RESTful API interface
- Real-time data during live sessions
- Historical race data
- No authentication required

### API Endpoints
- Base URL: `https://api.openf1.org/v1/`
- Endpoints: `/laps`, `/pit`, `/position`, `/session`, etc.

## Data Normalization

All data from external sources will be normalized into our standard event schema (see `schemas/event_schema.json`) to ensure consistency across the system.

### Event Types
- `lap_complete`: Lap timing and metrics
- `pit_stop`: Pit stop events with tire changes
- `track_status`: Safety car, flags, race control events
- `position_update`: Driver position changes
- `gap_update`: Time gaps between drivers

## Data Storage

Historical race data will be cached locally in the `data/` directory to:
- Reduce API calls
- Enable offline development
- Support deterministic replay
