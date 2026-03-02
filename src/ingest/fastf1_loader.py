"""
FastF1 data loader for RaceControl

Loads race session data from FastF1 library and returns structured data
for event normalization.
"""

import fastf1
from typing import Dict, Any
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Enable FastF1 caching for offline use after initial download
# Create cache directory if it doesn't exist
cache_dir = Path('cache')
cache_dir.mkdir(exist_ok=True)
fastf1.Cache.enable_cache(str(cache_dir))


def load_race(year: int, gp: str, session_type: str = "R") -> Dict[str, Any]:
    """
    Load race session data from FastF1.
    
    Args:
        year: Race year (2018+)
        gp: Grand Prix name (e.g., "Hungary", "Monaco", "Bahrain")
        session_type: Session type, default "R" for race. Options: "FP1", "FP2", "FP3", "Q", "R", "S"
    
    Returns:
        Dictionary containing:
            - session: FastF1 session object
            - laps: Laps dataframe
            - timing_data: Optional timing/telemetry data if available
    
    Raises:
        ValueError: If session data cannot be loaded or is missing required data
        Exception: For other FastF1 errors (network, cache, etc.)
    """
    if year < 2018:
        raise ValueError(f"Year {year} is before 2018. Only years 2018+ are supported.")
    
    try:
        logger.info(f"Loading session: {year} {gp} {session_type}")
        session = fastf1.get_session(year, gp, session_type)
        
        # Load session data
        logger.info("Loading session data...")
        session.load()
        
        # Get laps dataframe
        laps = session.laps
        
        if laps is None or len(laps) == 0:
            raise ValueError(f"No lap data available for {year} {gp} {session_type}")
        
        logger.info(f"Loaded {len(laps)} lap records")
        
        # Try to get timing data if available
        timing_data = None
        try:
            # FastF1 may provide timing data through session object
            # This is optional and may not be available for all sessions
            if hasattr(session, 'timing_data'):
                timing_data = session.timing_data
        except Exception as e:
            logger.debug(f"Timing data not available: {e}")
        
        return {
            "session": session,
            "laps": laps,
            "timing_data": timing_data
        }
    
    except Exception as e:
        error_msg = f"Failed to load race data for {year} {gp} {session_type}: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg) from e
