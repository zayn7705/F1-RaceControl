"""
Event builder for normalizing FastF1 data into canonical event format

Converts raw FastF1 session data into a sorted, timestamped list of events
with deterministic ordering.
"""

from typing import List, Dict, Any, Optional
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Event type priority for deterministic sorting (lower number = earlier in sort)
EVENT_TYPE_PRIORITY = {
    "track_status": 0,
    "pit_stop": 1,
    "lap_complete": 2
}


def _get_event_type_priority(event_type: str) -> int:
    """Get numeric priority for event type sorting"""
    return EVENT_TYPE_PRIORITY.get(event_type, 999)


def _convert_time_to_race_seconds(time_value, session_start: Optional[pd.Timestamp] = None) -> Optional[float]:
    """
    Convert FastF1 time value to race-relative seconds.
    
    FastF1 can provide times as:
    - pd.Timedelta (relative to session start)
    - pd.Timestamp (absolute time)
    
    Args:
        time_value: Time value from FastF1 (Timedelta, Timestamp, or other)
        session_start: Optional session start timestamp (for Timestamp conversion)
    
    Returns:
        Float seconds since race start, or None if conversion fails
    """
    if pd.isna(time_value):
        return None
    
    # Handle Timedelta (most common case)
    if isinstance(time_value, pd.Timedelta):
        return time_value.total_seconds()
    
    # Handle Timestamp (absolute time)
    if isinstance(time_value, pd.Timestamp):
        if session_start is not None:
            delta = time_value - session_start
            return delta.total_seconds()
        else:
            # If no session start, try to use the timestamp itself
            # This is a fallback - ideally we'd have session_start
            logger.warning("Timestamp conversion without session_start, using as-is")
            return time_value.timestamp()
    
    # Handle numeric (already in seconds)
    if isinstance(time_value, (int, float)):
        return float(time_value)
    
    # Try to convert string or other types
    try:
        if isinstance(time_value, str):
            # Try parsing as timedelta string
            td = pd.Timedelta(time_value)
            return td.total_seconds()
    except:
        pass
    
    logger.warning(f"Could not convert time value: {type(time_value)} = {time_value}")
    return None


def _build_lap_complete_events(laps: pd.DataFrame, session) -> List[Dict[str, Any]]:
    """
    Build lap_complete events from laps dataframe.
    
    Args:
        laps: FastF1 laps dataframe
        session: FastF1 session object (for session start time if needed)
    
    Returns:
        List of lap_complete event dictionaries
    """
    events = []
    
    # Track tire age per driver (laps since stint start)
    driver_stint_laps = {}  # {(driver, stint): lap_count}
    
    for idx, lap in laps.iterrows():
        driver = lap.get('Driver', None)
        lap_num = lap.get('LapNumber', None)
        
        if pd.isna(driver) or pd.isna(lap_num):
            continue
        
        # Get lap completion time (Time column in FastF1)
        event_time = None
        if 'Time' in lap and not pd.isna(lap['Time']):
            # Try to get session start time for proper conversion
            session_start = None
            if session is not None and hasattr(session, 'date'):
                try:
                    session_start = session.date
                except:
                    pass
            event_time = _convert_time_to_race_seconds(lap['Time'], session_start)
        
        if event_time is None:
            # Fallback: estimate from lap number if time not available
            logger.debug(f"No time available for lap {lap_num} driver {driver}, skipping")
            continue
        
        # Get tire compound
        compound = lap.get('Compound', None)
        if pd.notna(compound):
            compound = str(compound).upper()
        else:
            compound = None
        
        # Get stint number
        stint = lap.get('Stint', None)
        if pd.isna(stint):
            stint = None
        else:
            stint = int(stint)
        
        # Calculate tire age (laps in current stint)
        tire_age = None
        if driver and stint is not None:
            key = (driver, stint)
            if key not in driver_stint_laps:
                driver_stint_laps[key] = 0
            driver_stint_laps[key] += 1
            tire_age = driver_stint_laps[key]
        
        # Get lap time
        lap_time = None
        if 'LapTime' in lap and not pd.isna(lap['LapTime']):
            lap_time = lap['LapTime'].total_seconds() if hasattr(lap['LapTime'], 'total_seconds') else float(lap['LapTime'])
        
        # Get position (if available)
        position = lap.get('Position', None)
        if pd.isna(position):
            position = None
        else:
            position = int(position)
        
        event = {
            "event_time": event_time,
            "event_type": "lap_complete",
            "driver": str(driver),
            "lap": int(lap_num),
            "payload": {
                "lap_time_s": lap_time,
                "compound": compound,
                "stint": stint,
                "tire_age_laps": tire_age,
                "position": position
            }
        }
        
        events.append(event)
    
    logger.info(f"Built {len(events)} lap_complete events")
    return events


def _build_pit_stop_events(laps: pd.DataFrame, session) -> List[Dict[str, Any]]:
    """
    Build pit_stop events from laps dataframe.
    
    Uses PitInTime to determine when pit stop occurs.
    
    Args:
        laps: FastF1 laps dataframe
        session: FastF1 session object (for session start time if needed)
    
    Returns:
        List of pit_stop event dictionaries
    """
    events = []
    
    for idx, lap in laps.iterrows():
        driver = lap.get('Driver', None)
        lap_num = lap.get('LapNumber', None)
        
        if pd.isna(driver) or pd.isna(lap_num):
            continue
        
        # Check if this lap has a pit stop (PitInTime present)
        pit_in_time = None
        pit_out_time = None
        
        # Try to get session start time for proper conversion
        session_start = None
        if session is not None and hasattr(session, 'date'):
            try:
                session_start = session.date
            except:
                pass
        
        if 'PitInTime' in lap and not pd.isna(lap['PitInTime']):
            pit_in_time = _convert_time_to_race_seconds(lap['PitInTime'], session_start)
        
        if 'PitOutTime' in lap and not pd.isna(lap['PitOutTime']):
            pit_out_time = _convert_time_to_race_seconds(lap['PitOutTime'], session_start)
        
        # Only create event if we have pit in time (pit entry is the event)
        if pit_in_time is None:
            continue
        
        # Calculate pit duration
        pit_duration = None
        if pit_in_time is not None and pit_out_time is not None:
            pit_duration = pit_out_time - pit_in_time
        
        # Get stint after pit (next stint)
        stint = lap.get('Stint', None)
        if pd.isna(stint):
            stint = None
        else:
            stint = int(stint)
        
        # Get compound after pit stop
        compound_after = lap.get('Compound', None)
        if pd.notna(compound_after):
            compound_after = str(compound_after).upper()
        else:
            compound_after = None
        
        event = {
            "event_time": pit_in_time,  # Use pit in time as event time
            "event_type": "pit_stop",
            "driver": str(driver),
            "lap": int(lap_num),
            "payload": {
                "pit_in_time_s": pit_in_time,
                "pit_out_time_s": pit_out_time,
                "pit_duration_s": pit_duration,
                "stint": stint,
                "compound_after": compound_after
            }
        }
        
        events.append(event)
    
    logger.info(f"Built {len(events)} pit_stop events")
    return events


def _build_track_status_events(session, timing_data: Optional[Any] = None) -> List[Dict[str, Any]]:
    """
    Build track_status events from session data.
    
    NOTE: FastF1's public API for track status/race control messages is limited.
    This function attempts to extract track status if available, but may return
    an empty list if data is not accessible through public APIs.
    
    Args:
        session: FastF1 session object
        timing_data: Optional timing data (may contain race control messages)
    
    Returns:
        List of track_status event dictionaries (may be empty)
    """
    events = []
    
    # FastF1 does not provide easy access to race control messages through
    # the public Session API. The timing_data and telemetry may contain
    # some information, but it's not reliably accessible.
    # 
    # For CP2, we document this as optional and return empty list.
    # In a production system, you might:
    # 1. Use FastF1's internal APIs (not recommended for stability)
    # 2. Scrape F1 official timing data
    # 3. Use a different data source
    
    logger.info("Track status events: Not implemented (FastF1 public API limitation)")
    logger.info("Returning empty list. This is acceptable for CP2.")
    
    # Placeholder: If timing_data becomes available in future FastF1 versions,
    # parse it here to extract track status changes
    
    return events


def build_events(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Build normalized events from raw FastF1 session data.
    
    Args:
        raw: Dictionary from load_race() containing:
            - session: FastF1 session object
            - laps: Laps dataframe
            - timing_data: Optional timing data
    
    Returns:
        Sorted list of normalized event dictionaries with seq assigned
    """
    session = raw.get('session')
    laps = raw.get('laps')
    timing_data = raw.get('timing_data')
    
    if laps is None or len(laps) == 0:
        logger.warning("No laps data available")
        return []
    
    # Build events by type
    all_events = []
    
    # 1. Lap complete events
    all_events.extend(_build_lap_complete_events(laps, session))
    
    # 2. Pit stop events
    all_events.extend(_build_pit_stop_events(laps, session))
    
    # 3. Track status events (optional, may be empty)
    all_events.extend(_build_track_status_events(session, timing_data))
    
    # Sort events deterministically
    # Sort by: event_time, event_type_priority, driver (or ""), lap (or -1)
    def sort_key(event):
        return (
            event.get('event_time', float('inf')),
            _get_event_type_priority(event.get('event_type', '')),
            event.get('driver', '') or '',
            event.get('lap') if event.get('lap') is not None else -1
        )
    
    all_events.sort(key=sort_key)
    
    # Assign sequential seq numbers
    for seq, event in enumerate(all_events):
        event['seq'] = seq
    
    logger.info(f"Built and sorted {len(all_events)} total events")
    
    return all_events
