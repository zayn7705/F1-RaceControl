#!/usr/bin/env python3
"""
Export normalized F1 race events to JSONL file

Usage:
    python scripts/export_events.py --year 2022 --gp Hungary --session R --out data/sample_events_hungary_2022.jsonl --max-events 500

Full race export for the interactive strategy MVP (no event cap):
    python scripts/export_events.py --year 2022 --gp Hungary --session R --out data/hungary_2022_r.jsonl
"""

import argparse
import json
import sys
import logging
from pathlib import Path
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ingest import load_race, build_events

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)


def export_events(year: int, gp: str, session: str, output_path: str, max_events: Optional[int] = None):
    """
    Load race data, build events, and export to JSONL file.
    
    Args:
        year: Race year
        gp: Grand Prix name
        session: Session type (default "R")
        output_path: Output JSONL file path
        max_events: Optional limit on number of events to export
    """
    print(f"Loading race: {year} {gp} {session}")
    
    try:
        # Load race data
        raw_data = load_race(year, gp, session)
        
        # Build events
        print("Building normalized events...")
        events = build_events(raw_data)
        
        # Limit events if requested
        if max_events is not None and max_events > 0:
            events = events[:max_events]
            print(f"Limited to first {max_events} events")
        
        # Write to JSONL file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"Writing {len(events)} events to {output_path}...")
        with open(output_file, 'w') as f:
            for event in events:
                f.write(json.dumps(event) + '\n')
        
        # Print summary statistics
        print("\n" + "=" * 60)
        print("EXPORT SUMMARY")
        print("=" * 60)
        print(f"Total events: {len(events)}")
        
        # Count by event type
        type_counts = {}
        for event in events:
            event_type = event.get('event_type', 'unknown')
            type_counts[event_type] = type_counts.get(event_type, 0) + 1
        
        print("\nEvents by type:")
        for event_type, count in sorted(type_counts.items()):
            print(f"  {event_type}: {count}")
        
        # First and last timestamps
        if events:
            first_time = events[0].get('event_time')
            last_time = events[-1].get('event_time')
            print(f"\nFirst event time: {first_time:.3f} s")
            print(f"Last event time: {last_time:.3f} s")
            print(f"Race duration: {last_time - first_time:.3f} s")
        
        print("=" * 60)
        print(f"✓ Successfully exported to {output_path}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Export normalized F1 race events to JSONL file"
    )
    parser.add_argument('--year', type=int, required=True, help='Race year (2018+)')
    parser.add_argument('--gp', type=str, required=True, help='Grand Prix name (e.g., "Hungary", "Monaco")')
    parser.add_argument('--session', type=str, default='R', help='Session type (default: R)')
    parser.add_argument('--out', type=str, required=True, help='Output JSONL file path')
    parser.add_argument('--max-events', type=int, default=None, help='Maximum number of events to export')
    
    args = parser.parse_args()
    
    export_events(
        year=args.year,
        gp=args.gp,
        session=args.session,
        output_path=args.out,
        max_events=args.max_events
    )


if __name__ == "__main__":
    main()
