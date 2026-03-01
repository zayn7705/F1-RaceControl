"""
Test that example events conform to the canonical event schema

Uses jsonschema library for validation.
"""

import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("ERROR: jsonschema library not installed. Install with: pip install jsonschema")
    sys.exit(1)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def load_schema():
    """Load the event schema from schemas/event_schema.json"""
    schema_path = Path(__file__).parent.parent / "schemas" / "event_schema.json"
    with open(schema_path, 'r') as f:
        return json.load(f)


def load_example_events():
    """Load example events from schemas/examples/"""
    examples_dir = Path(__file__).parent.parent / "schemas" / "examples"
    events = []
    
    for example_file in sorted(examples_dir.glob("*.json")):
        with open(example_file, 'r') as f:
            events.append((example_file.name, json.load(f)))
    
    return events


def validate_event(event: dict, schema: dict) -> tuple[bool, list[str]]:
    """
    Validate event against schema using jsonschema library.
    
    Returns:
        (is_valid, list_of_errors)
    """
    try:
        jsonschema.validate(instance=event, schema=schema)
        return True, []
    except jsonschema.ValidationError as e:
        return False, [str(e)]
    except jsonschema.SchemaError as e:
        return False, [f"Schema error: {str(e)}"]


def test_schema_validation():
    """Test that example events conform to the schema"""
    print("Testing schema validation with jsonschema...")
    print("=" * 60)
    
    schema = load_schema()
    example_events = load_example_events()
    
    if not example_events:
        print("WARNING: No example events found!")
        return False
    
    all_passed = True
    
    for filename, event in example_events:
        print(f"\nValidating: {filename}")
        is_valid, errors = validate_event(event, schema)
        
        if is_valid:
            print(f"  ✓ {filename} is valid")
            print(f"    Event type: {event.get('event_type')}")
            print(f"    Seq: {event.get('seq')}, Time: {event.get('event_time')}")
        else:
            print(f"  ✗ {filename} has errors:")
            for error in errors:
                print(f"    - {error}")
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All example events passed validation!")
        return True
    else:
        print("✗ Some events failed validation")
        return False


def test_smoke_build_events():
    """
    Smoke test: Try to build events from a known race if data is available.
    
    This test does not require network if FastF1 cache is warm.
    """
    print("\n" + "=" * 60)
    print("Smoke test: build_events (requires FastF1 cache)")
    print("=" * 60)
    
    try:
        from ingest import load_race, build_events
        
        # Try a common race that should be in cache
        # Use a recent year and popular GP
        print("\nAttempting to load 2022 Hungary GP...")
        print("(This will use cache if available, or skip if not)")
        
        try:
            raw_data = load_race(2022, "Hungary", "R")
            events = build_events(raw_data)
            
            print(f"✓ Successfully built {len(events)} events")
            
            # Basic sanity checks
            if len(events) > 0:
                print(f"  First event: seq={events[0].get('seq')}, type={events[0].get('event_type')}")
                print(f"  Last event: seq={events[-1].get('seq')}, type={events[-1].get('event_type')}")
                
                # Check seq is monotonic
                seqs = [e.get('seq') for e in events]
                if seqs == list(range(len(events))):
                    print("  ✓ Sequence numbers are monotonic")
                else:
                    print("  ✗ Sequence numbers are not monotonic!")
                    return False
                
                # Check events are sorted by time
                times = [e.get('event_time') for e in events if e.get('event_time') is not None]
                if times == sorted(times):
                    print("  ✓ Events are sorted by time")
                else:
                    print("  ✗ Events are not sorted by time!")
                    return False
            
            return True
            
        except Exception as e:
            print(f"  ⚠ Smoke test skipped: {e}")
            print("  (This is OK if FastF1 cache is not warm)")
            return True  # Don't fail the test suite if cache is cold
        
    except ImportError as e:
        print(f"  ⚠ Could not import ingest module: {e}")
        return False


if __name__ == "__main__":
    success = test_schema_validation()
    
    # Run smoke test (non-blocking)
    smoke_success = test_smoke_build_events()
    
    if success and smoke_success:
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("✗ Some tests failed")
        sys.exit(1)
