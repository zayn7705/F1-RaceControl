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
        
        # Get sector times
        sector1_time = None
        if 'Sector1Time' in lap and not pd.isna(lap['Sector1Time']):
            sector1_time = lap['Sector1Time'].total_seconds() if hasattr(lap['Sector1Time'], 'total_seconds') else float(lap['Sector1Time'])
        
        sector2_time = None
        if 'Sector2Time' in lap and not pd.isna(lap['Sector2Time']):
            sector2_time = lap['Sector2Time'].total_seconds() if hasattr(lap['Sector2Time'], 'total_seconds') else float(lap['Sector2Time'])
        
        sector3_time = None
        if 'Sector3Time' in lap and not pd.isna(lap['Sector3Time']):
            sector3_time = lap['Sector3Time'].total_seconds() if hasattr(lap['Sector3Time'], 'total_seconds') else float(lap['Sector3Time'])
        
        # Get TyreLife (official tire life from F1 timing)
        tyre_life = None
        if 'TyreLife' in lap and not pd.isna(lap['TyreLife']):
            tyre_life = float(lap['TyreLife'])
        
        # Use TyreLife if available, otherwise fall back to computed tire_age_laps
        # Keep both for compatibility
        final_tire_age = tyre_life if tyre_life is not None else tire_age
        
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
                "sector1_time_s": sector1_time,
                "sector2_time_s": sector2_time,
                "sector3_time_s": sector3_time,
                "compound": compound,
                "stint": stint,
                "tire_age_laps": tire_age,  # Keep computed for backward compatibility
                "tyre_life": tyre_life,  # Official F1 tire life
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

    # Try to get session start time for proper conversion
    session_start = None
    if session is not None and hasattr(session, 'date'):
        try:
            session_start = session.date
        except:
            pass

    # Pair pit-in and pit-out across rows per driver.
    # FastF1 often records PitInTime on one lap row and PitOutTime on the next.
    for driver, driver_laps in laps.groupby('Driver', sort=False):
        if pd.isna(driver):
            continue

        # Keep original order deterministic by Time then LapNumber.
        ordered = driver_laps.sort_values(by=['Time', 'LapNumber'], na_position='last')
        pending = None

        for _, lap in ordered.iterrows():
            lap_num = lap.get('LapNumber', None)
            if pd.isna(lap_num):
                continue

            raw_in = lap.get('PitInTime', None)
            raw_out = lap.get('PitOutTime', None)

            pit_in_time = None
            pit_out_time = None
            if pd.notna(raw_in):
                pit_in_time = _convert_time_to_race_seconds(raw_in, session_start)
            if pd.notna(raw_out):
                pit_out_time = _convert_time_to_race_seconds(raw_out, session_start)

            # Start a pending pit stop when PitInTime appears.
            if pit_in_time is not None:
                pending = {
                    "driver": str(driver),
                    "lap": int(lap_num),
                    "pit_in_time_s": pit_in_time
                }

                # If both in and out are on same row, finalize immediately.
                if pit_out_time is not None:
                    stint_val = lap.get('Stint', None)
                    stint = None if pd.isna(stint_val) else int(stint_val)

                    compound_val = lap.get('Compound', None)
                    compound_after = str(compound_val).upper() if pd.notna(compound_val) else None

                    events.append({
                        "event_time": pit_in_time,
                        "event_type": "pit_stop",
                        "driver": pending["driver"],
                        "lap": pending["lap"],
                        "payload": {
                            "pit_in_time_s": pit_in_time,
                            "pit_out_time_s": pit_out_time,
                            "pit_duration_s": pit_out_time - pit_in_time,
                            "stint": stint,
                            "compound_after": compound_after
                        }
                    })
                    pending = None

                continue

            # Close pending pit stop when PitOutTime appears on a later row.
            if pending is not None and pit_out_time is not None:
                stint_val = lap.get('Stint', None)
                stint = None if pd.isna(stint_val) else int(stint_val)

                compound_val = lap.get('Compound', None)
                compound_after = str(compound_val).upper() if pd.notna(compound_val) else None

                pit_duration = None
                if pending["pit_in_time_s"] is not None:
                    pit_duration = pit_out_time - pending["pit_in_time_s"]

                events.append({
                    "event_time": pending["pit_in_time_s"],
                    "event_type": "pit_stop",
                    "driver": pending["driver"],
                    "lap": pending["lap"],
                    "payload": {
                        "pit_in_time_s": pending["pit_in_time_s"],
                        "pit_out_time_s": pit_out_time,
                        "pit_duration_s": pit_duration,
                        "stint": stint,
                        "compound_after": compound_after
                    }
                })
                pending = None

        # If we ended with an unmatched pit-in, keep event with unknown out/duration.
        if pending is not None:
            events.append({
                "event_time": pending["pit_in_time_s"],
                "event_type": "pit_stop",
                "driver": pending["driver"],
                "lap": pending["lap"],
                "payload": {
                    "pit_in_time_s": pending["pit_in_time_s"],
                    "pit_out_time_s": None,
                    "pit_duration_s": None,
                    "stint": None,
                    "compound_after": None
                }
            })
    
    logger.info(f"Built {len(events)} pit_stop events")
    return events


def _build_track_status_events(session, timing_data: Optional[Any] = None) -> List[Dict[str, Any]]:
    """
    Build track_status events from session data.
    
    Extracts track status changes from session.track_status DataFrame if available.
    
    Args:
        session: FastF1 session object
        timing_data: Optional timing data (not used, kept for compatibility)
    
    Returns:
        List of track_status event dictionaries
    """
    events = []
    
    # Check if session has track_status DataFrame
    if not hasattr(session, 'track_status') or session.track_status is None:
        logger.debug("No track_status DataFrame available in session")
        return events
    
    try:
        track_status_df = session.track_status
        
        if len(track_status_df) == 0:
            logger.debug("track_status DataFrame is empty")
            return events
        
        # Status code mapping (from FastF1)
        # 1 = AllClear (Green), 2 = Yellow, 6 = VSCDeployed, 7 = SCDeployed, etc.
        status_map = {
            1: "GREEN",
            2: "YELLOW",
            6: "VSC",
            7: "SC",
        }
        
        # Get session start time for conversion
        session_start = None
        if session is not None and hasattr(session, 'date'):
            try:
                session_start = session.date
            except:
                pass
        
        # Process each track status change
        for idx, row in track_status_df.iterrows():
            status_code = row.get('Status')
            time_delta = row.get('Time')
            message = row.get('Message', '')
            
            if pd.isna(status_code) or pd.isna(time_delta):
                continue
            
            # Convert time to race-relative seconds
            event_time = _convert_time_to_race_seconds(time_delta, session_start)
            if event_time is None:
                continue
            
            # Map status code to readable string
            status_str = status_map.get(int(status_code), f"UNKNOWN_{int(status_code)}")
            
            # Use message if available, otherwise use mapped status
            if pd.notna(message) and message:
                status_str = str(message).upper()
            
            event = {
                "event_time": event_time,
                "event_type": "track_status",
                "driver": None,  # Track status is global, not driver-specific
                "lap": None,
                "payload": {
                    "status": status_str,
                    "source": "fastf1_track_status"
                }
            }
            
            events.append(event)
        
        logger.info(f"Built {len(events)} track_status events")
        
    except Exception as e:
        logger.warning(f"Error extracting track status events: {e}")
        # Return empty list on error to maintain robustness
        return []
    
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
