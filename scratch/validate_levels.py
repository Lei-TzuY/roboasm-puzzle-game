import glob
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from level_schema import LevelValidationError, validate_level_definition

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def main():
    level_files = sorted(glob.glob(os.path.join(ROOT_DIR, 'levels', '*.json')))
    failures = []

    for path in level_files:
        filename = os.path.basename(path)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                definition = json.load(f)
            validate_level_definition(definition, source=filename)
            print(f"PASS {filename}")
        except (OSError, json.JSONDecodeError, LevelValidationError) as exc:
            failures.append((filename, str(exc)))
            print(f"FAIL {filename}: {exc}")

    print(f"\nValidated {len(level_files)} level definitions: "
          f"{len(level_files) - len(failures)} passed, {len(failures)} failed.")
    if failures:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
