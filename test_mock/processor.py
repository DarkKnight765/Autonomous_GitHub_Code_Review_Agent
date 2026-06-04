"""
Mock data processing module.
Contains performance issues and error handling bugs.
"""

import json
import os


def process_records(file_path):
    # BUG: no check if file exists before opening
    f = open(file_path, "r")
    data = json.load(f)
    # BUG: file handle never closed (should use context manager)

    results = []
    for i in range(len(data)):   # STYLE: should use enumerate or iterate directly
        record = data[i]
        # PERFORMANCE: string concatenation in a loop (quadratic)
        log = ""
        for key in record:
            log = log + key + "=" + str(record[key]) + ","
        print(log)
        results.append(record)
    return results


def save_results(results, output_path):
    # BUG: silently overwrites existing files without warning
    with open(output_path, "w") as f:
        # BUG: writes Python repr, not valid JSON
        f.write(str(results))


def load_config():
    # SECURITY: reads arbitrary env var and evals it
    config_str = os.environ.get("APP_CONFIG", "{}")
    config = eval(config_str)  # noqa: S307  SECURITY: eval on user input
    return config


def calculate_average(numbers):
    # BUG: ZeroDivisionError when numbers is empty list
    total = sum(numbers)
    return total / len(numbers)


def find_duplicates(items):
    # PERFORMANCE: O(n^2) when set() would be O(n)
    duplicates = []
    for i in range(len(items)):
        for j in range(len(items)):
            if i != j and items[i] == items[j]:
                if items[i] not in duplicates:
                    duplicates.append(items[i])
    return duplicates
