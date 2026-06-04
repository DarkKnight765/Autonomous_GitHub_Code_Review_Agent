"""
Unified diff parser.

Parses GitHub's unified diff format into structured chunks that can be
sent to Claude for review. Critically, maps absolute file line numbers
to diff positions — required for posting inline comments via GitHub API.

GitHub's inline comment API uses 'position' (line number within the diff hunk),
NOT the absolute line number in the file. This module handles that mapping.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Matches hunk headers like: @@ -10,6 +12,8 @@ def my_function():
HUNK_HEADER_RE = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$"
)


@dataclass
class DiffLine:
    """A single line in a diff hunk."""

    content: str  # the actual line content (without +/-/ prefix)
    line_type: str  # "add", "remove", "context"
    old_line_number: int | None  # line number in the base version
    new_line_number: int | None  # line number in the head (new) version
    diff_position: int  # position in the diff (for GitHub API comments)


@dataclass
class DiffHunk:
    """A single hunk within a file diff."""

    header: str  # e.g., "@@ -10,6 +12,8 @@ def my_function():"
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    section_header: str  # function/class name from hunk header (if any)
    lines: list[DiffLine] = field(default_factory=list)

    @property
    def added_lines(self) -> list[DiffLine]:
        return [line for line in self.lines if line.line_type == "add"]

    @property
    def removed_lines(self) -> list[DiffLine]:
        return [line for line in self.lines if line.line_type == "remove"]

    @property
    def context_lines(self) -> list[DiffLine]:
        return [line for line in self.lines if line.line_type == "context"]


@dataclass
class FileDiff:
    """Complete diff for a single file, containing one or more hunks."""

    file_path: str
    hunks: list[DiffHunk] = field(default_factory=list)

    @property
    def total_additions(self) -> int:
        return sum(len(h.added_lines) for h in self.hunks)

    @property
    def total_deletions(self) -> int:
        return sum(len(h.removed_lines) for h in self.hunks)

    @property
    def all_lines(self) -> list[DiffLine]:
        """All diff lines across all hunks, in order."""
        result = []
        for hunk in self.hunks:
            result.extend(hunk.lines)
        return result

    def get_position_for_new_line(self, new_line_number: int) -> int | None:
        """
        Find the diff position for a given line number in the new file version.

        This is the critical mapping needed for GitHub's inline comment API.

        Args:
            new_line_number: The line number in the new (head) version of the file.

        Returns:
            The diff position, or None if the line isn't in the diff.
        """
        for hunk in self.hunks:
            for line in hunk.lines:
                if line.new_line_number == new_line_number:
                    return line.diff_position
        return None


class DiffParser:
    """
    Parses unified diff text into structured FileDiff objects.

    Usage:
        parser = DiffParser()
        file_diffs = parser.parse(patch_text)  # from a single file
        # or
        all_diffs = parser.parse_multi(full_diff_text)  # multiple files
    """

    def parse(self, patch: str, file_path: str = "") -> FileDiff:
        """
        Parse a single file's unified diff patch.

        Args:
            patch: The unified diff text (e.g., from PyGithub's file.patch).
            file_path: The file path (for context in the result).

        Returns:
            A FileDiff with parsed hunks and line mappings.
        """
        if not patch:
            return FileDiff(file_path=file_path)

        file_diff = FileDiff(file_path=file_path)
        lines = patch.split("\n")

        current_hunk: DiffHunk | None = None
        # diff_position is 1-indexed and counts every line in the diff
        # (including hunk headers)
        diff_position = 0
        old_line = 0
        new_line = 0

        for raw_line in lines:
            diff_position += 1

            # Check for hunk header
            match = HUNK_HEADER_RE.match(raw_line)
            if match:
                old_start = int(match.group(1))
                old_count = int(match.group(2) or "1")
                new_start = int(match.group(3))
                new_count = int(match.group(4) or "1")
                section_header = match.group(5).strip()

                current_hunk = DiffHunk(
                    header=raw_line,
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                    section_header=section_header,
                )
                file_diff.hunks.append(current_hunk)

                old_line = old_start
                new_line = new_start
                continue

            if current_hunk is None:
                # Lines before first hunk header (e.g., diff --git lines)
                continue

            if raw_line.startswith("+"):
                # Added line
                current_hunk.lines.append(
                    DiffLine(
                        content=raw_line[1:],  # strip the + prefix
                        line_type="add",
                        old_line_number=None,
                        new_line_number=new_line,
                        diff_position=diff_position,
                    )
                )
                new_line += 1

            elif raw_line.startswith("-"):
                # Removed line
                current_hunk.lines.append(
                    DiffLine(
                        content=raw_line[1:],  # strip the - prefix
                        line_type="remove",
                        old_line_number=old_line,
                        new_line_number=None,
                        diff_position=diff_position,
                    )
                )
                old_line += 1

            elif raw_line.startswith(" ") or raw_line == "":
                # Context line
                content = raw_line[1:] if raw_line.startswith(" ") else raw_line
                current_hunk.lines.append(
                    DiffLine(
                        content=content,
                        line_type="context",
                        old_line_number=old_line,
                        new_line_number=new_line,
                        diff_position=diff_position,
                    )
                )
                old_line += 1
                new_line += 1

            elif raw_line.startswith("\\"):
                # "\ No newline at end of file" — skip but count position
                pass

        logger.debug(
            f"Parsed {file_path}: {len(file_diff.hunks)} hunks, "
            f"+{file_diff.total_additions}/-{file_diff.total_deletions}"
        )

        return file_diff

    def parse_pr_files(
        self,
        files: list,  # list of FileChange from github_client
    ) -> list[FileDiff]:
        """
        Parse diffs for all files in a pull request.

        Args:
            files: List of FileChange objects from GitHubReviewClient.get_pr_diff().

        Returns:
            List of FileDiff objects, one per changed file.
        """
        diffs: list[FileDiff] = []
        for f in files:
            if f.patch is None:
                # Binary file or empty change — skip
                logger.debug(f"Skipping {f.filename} (no patch data)")
                continue

            diff = self.parse(f.patch, file_path=f.filename)
            diffs.append(diff)

        logger.info(f"Parsed diffs for {len(diffs)} files")
        return diffs


def format_diff_for_review(file_diff: FileDiff) -> str:
    """
    Format a FileDiff into a clean string for sending to Claude.

    Includes file path, hunk headers, and all diff lines with
    line numbers for context.
    """
    parts: list[str] = []
    parts.append(f"### File: {file_diff.file_path}")
    parts.append(f"Changes: +{file_diff.total_additions}/-{file_diff.total_deletions}")
    parts.append("")

    for hunk in file_diff.hunks:
        parts.append("```diff")
        parts.append(hunk.header)

        for line in hunk.lines:
            if line.line_type == "add":
                parts.append(f"+{line.content}")
            elif line.line_type == "remove":
                parts.append(f"-{line.content}")
            else:
                parts.append(f" {line.content}")

        parts.append("```")
        parts.append("")

    return "\n".join(parts)
