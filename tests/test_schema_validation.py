"""
Test schema validation for RaceControl events
"""

import json
import sys
from pathlib import Path

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
    
    for example_file in examples_dir.glob("*.json"):
        with open(example_file, 'r') as f:
            events.append((example_file.name, json.load(f)))
    
    return events


def validate_event_basic(event: dict, schema: dict) -> tuple[bool, list[str]]:
    """
    Basic validation of event against schema.
    Note: This is a simplified validator. For production, use jsonschema library.
    """
    errors = []
    
    # Check required fields
    required_fields = schema.get("properties", {}).keys()
    for field in schema.get("required", []):
        if field not in event:
            errors.append(f"Missing required field: {field}")
    
    # Check event_type enum
    if "event_type" in event:
        valid_types = schema["properties"]["event_type"]["enum"]
        if event["event_type"] not in valid_types:
            errors.append(f"Invalid event_type: {event['event_type']}. Must be one of {valid_types}")
    
    # Check type constraints (simplified)
    for field, value in event.items():
        if field in schema.get("properties", {}):
            prop_schema = schema["properties"][field]
            expected_type = prop_schema.get("type")
            
            if expected_type == "string" and not isinstance(value, str):
                errors.append(f"Field '{field}' must be a string")
            elif expected_type == "integer" and not isinstance(value, int):
                errors.append(f"Field '{field}' must be an integer")
            elif expected_type == "number" and not isinstance(value, (int, float)):
                errors.append(f"Field '{field}' must be a number")
    
    return len(errors) == 0, errors


def test_schema_validation():
    """Test that example events conform to the schema"""
    print("Testing schema validation...")
    print("=" * 50)
    
    schema = load_schema()
    example_events = load_example_events()
    
    all_passed = True
    
    for filename, event in example_events:
        print(f"\nValidating: {filename}")
        is_valid, errors = validate_event_basic(event, schema)
        
        if is_valid:
            print(f"  ✓ {filename} is valid")
        else:
            print(f"  ✗ {filename} has errors:")
            for error in errors:
                print(f"    - {error}")
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("✓ All example events passed validation!")
        return True
    else:
        print("✗ Some events failed validation")
        return False


if __name__ == "__main__":
    success = test_schema_validation()
    sys.exit(0 if success else 1)
