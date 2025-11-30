# GitHub Copilot Instructions

Always run Python scripts using uv run. Always.

## Code Modification Guidelines

### 1. Protect Working Code
**Never change existing working code without express permission.**

Before modifying any code that is currently functioning:
- Clearly explain what changes you propose to make
- Explicitly warn that the change could break working code
- Wait for express permission before proceeding
- If debugging, add instrumentation rather than changing logic

### 2. CSV Field Mapping Validation
**When populating or adding columns to a CSV file, always check the field mapping between the Player dataclass and the CSV output from the very beginning.**

Before debugging CSV output issues:
- First verify that dataclass field names match CSV column names
- Check the `to_dict()` method for any field name transformations
- Validate that `output_fields` in `ENTITY_CONFIGS` matches the dataclass structure
- Ensure the CSV writer is using the correct field names

This is a basic data validation step that should be performed before debugging extraction logic or other intermediate steps.

### 3. Check first
**Before adding a new URL format for a team, check first to see if the proposed new format already exists.**


