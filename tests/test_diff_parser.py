"""Tests for the diff parser."""

from __future__ import annotations

import pytest

from src.github_client.diff_parser import DiffParser, FileDiff


@pytest.fixture
def parser():
    return DiffParser()


# ── Sample Diffs ────────────────────────────────────────────────

SIMPLE_DIFF = """\
@@ -1,4 +1,5 @@
 import os
+import sys

 def main():
     print("hello")
"""

MULTI_HUNK_DIFF = """\
@@ -1,3 +1,4 @@
 import os
+import sys
 import json
@@ -10,6 +11,7 @@ def process():
     data = load()
+    validate(data)
     result = transform(data)
     return result
"""

REMOVAL_DIFF = """\
@@ -1,5 +1,3 @@
 import os
-import deprecated_module
-import another_old_module
 import json
"""


# ── Tests ───────────────────────────────────────────────────────

def test_parse_simple_diff(parser):
    result = parser.parse(SIMPLE_DIFF, file_path="main.py")

    assert isinstance(result, FileDiff)
    assert result.file_path == "main.py"
    assert len(result.hunks) == 1
    assert result.total_additions == 1
    assert result.total_deletions == 0


def test_parse_added_line_has_correct_position(parser):
    result = parser.parse(SIMPLE_DIFF, file_path="main.py")

    added_lines = result.hunks[0].added_lines
    assert len(added_lines) == 1
    assert added_lines[0].content == "import sys"
    assert added_lines[0].new_line_number == 2
    assert added_lines[0].diff_position > 0


def test_parse_multi_hunk(parser):
    result = parser.parse(MULTI_HUNK_DIFF, file_path="utils.py")

    assert len(result.hunks) == 2
    assert result.total_additions == 2
    assert result.total_deletions == 0


def test_parse_removals(parser):
    result = parser.parse(REMOVAL_DIFF, file_path="old.py")

    assert result.total_additions == 0
    assert result.total_deletions == 2

    removed = result.hunks[0].removed_lines
    assert len(removed) == 2
    assert removed[0].content == "import deprecated_module"


def test_parse_empty_patch(parser):
    result = parser.parse("", file_path="empty.py")
    assert len(result.hunks) == 0
    assert result.total_additions == 0


def test_position_mapping(parser):
    result = parser.parse(SIMPLE_DIFF, file_path="main.py")

    # The added line "import sys" should have a valid position
    position = result.get_position_for_new_line(2)
    assert position is not None
    assert position > 0


def test_position_for_nonexistent_line(parser):
    result = parser.parse(SIMPLE_DIFF, file_path="main.py")

    # Line 999 isn't in the diff
    position = result.get_position_for_new_line(999)
    assert position is None


def test_context_lines_have_both_line_numbers(parser):
    result = parser.parse(SIMPLE_DIFF, file_path="main.py")

    context_lines = result.hunks[0].context_lines
    for line in context_lines:
        assert line.old_line_number is not None
        assert line.new_line_number is not None
