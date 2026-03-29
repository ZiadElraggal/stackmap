"""SAM template parser.

Currently builds on the CloudFormation parser with SAM-aware mappings and
metadata handled in `cloudformation.py`.
"""

from stackmap.parsers.cloudformation import CloudFormationParser


class SamParser(CloudFormationParser):
    """Parser for AWS SAM templates."""

