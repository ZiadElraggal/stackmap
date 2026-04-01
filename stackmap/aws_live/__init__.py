"""Live AWS scanning support."""

from stackmap.aws_live.scanner import AWSLiveScanner, build_policy_document

__all__ = ["AWSLiveScanner", "build_policy_document"]
