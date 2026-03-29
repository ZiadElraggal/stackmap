"""Parser for already-generated StackMap IR JSON payloads."""

from stackmap.parsers.base import BaseParser, StackMapIR


class StackMapIRParser(BaseParser):
    """Load a precomputed StackMap IR document from JSON."""

    def parse(self, source_path: str) -> StackMapIR:
        return StackMapIR.read_json(source_path)
