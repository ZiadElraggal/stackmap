"""Org-scan role setup helpers: CloudFormation template generation and deployment."""

from __future__ import annotations

import json
from typing import Any

from stackmap.aws_live.scanner import POLICY_ACTIONS_BROAD, POLICY_ACTIONS_CORE


def build_stackmap_role_template(
    *,
    role_name: str = "StackMapReadOnly",
    management_account_id: str,
    service_set: str = "broad",
    external_id: str | None = None,
    session_duration: int = 3600,
) -> dict[str, Any]:
    """Generate a CloudFormation template that creates the StackMap read-only role.

    Designed to be deployed as a StackSet across an AWS Organization so every
    member account gets the same minimal-privilege role.
    """
    actions = POLICY_ACTIONS_CORE if service_set == "core" else POLICY_ACTIONS_BROAD

    trust_policy: dict[str, Any] = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowStackMapAssume",
                "Effect": "Allow",
                "Principal": {"AWS": f"arn:aws:iam::{management_account_id}:root"},
                "Action": "sts:AssumeRole",
                "Condition": {},
            }
        ],
    }
    if external_id:
        trust_policy["Statement"][0]["Condition"]["StringEquals"] = {
            "sts:ExternalId": external_id,
        }
    else:
        # Remove empty Condition block
        del trust_policy["Statement"][0]["Condition"]

    template: dict[str, Any] = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": (
            f"StackMap read-only role ({role_name}). "
            "Grants minimal read permissions for infrastructure visualization. "
            "No write, delete, or modify permissions are included. "
            "Deploy via CloudFormation StackSets for org-wide scanning."
        ),
        "Parameters": {
            "RoleName": {
                "Type": "String",
                "Default": role_name,
                "Description": "Name for the StackMap read-only IAM role",
            },
            "ManagementAccountId": {
                "Type": "String",
                "Default": management_account_id,
                "Description": "AWS account ID allowed to assume this role (your management account)",
            },
        },
        "Resources": {
            "StackMapReadOnlyRole": {
                "Type": "AWS::IAM::Role",
                "Properties": {
                    "RoleName": {"Ref": "RoleName"},
                    "MaxSessionDuration": session_duration,
                    "AssumeRolePolicyDocument": trust_policy,
                    "Policies": [
                        {
                            "PolicyName": "StackMapReadOnlyAccess",
                            "PolicyDocument": {
                                "Version": "2012-10-17",
                                "Statement": [
                                    {
                                        "Sid": "StackMapReadOnly",
                                        "Effect": "Allow",
                                        "Action": sorted(actions),
                                        "Resource": "*",
                                    }
                                ],
                            },
                        }
                    ],
                    "Tags": [
                        {"Key": "ManagedBy", "Value": "StackMap"},
                        {"Key": "Purpose", "Value": "ReadOnlyInfraVisualization"},
                    ],
                },
            }
        },
        "Outputs": {
            "RoleArn": {
                "Description": "ARN of the StackMap read-only role",
                "Value": {"Fn::GetAtt": ["StackMapReadOnlyRole", "Arn"]},
            }
        },
    }
    return template


def build_stackmap_role_template_yaml(
    *,
    role_name: str = "StackMapReadOnly",
    management_account_id: str,
    service_set: str = "broad",
    external_id: str | None = None,
) -> str:
    """Return the CloudFormation template as formatted JSON (works as CF input)."""
    template = build_stackmap_role_template(
        role_name=role_name,
        management_account_id=management_account_id,
        service_set=service_set,
        external_id=external_id,
    )
    return json.dumps(template, indent=2)


def print_setup_instructions(
    *,
    management_account_id: str,
    role_name: str = "StackMapReadOnly",
    template_path: str = "stackmap-role.cfn.json",
) -> str:
    """Return human-readable setup instructions."""
    return f"""
StackMap Org-Scan Setup
=======================

1. REVIEW the CloudFormation template at: {template_path}
   - Creates a single IAM role: {role_name}
   - Read-only permissions only (Describe*, List*, Get*)
   - Trusts only your management account ({management_account_id})
   - No write, delete, or modify permissions

2. DEPLOY via StackSets (recommended for org-wide):

   aws cloudformation create-stack-set \\
     --stack-set-name StackMapReadOnlyRole \\
     --template-body file://{template_path} \\
     --capabilities CAPABILITY_NAMED_IAM \\
     --permission-model SERVICE_MANAGED \\
     --auto-deployment Enabled=true,RetainStacksOnAccountRemoval=false

   aws cloudformation create-stack-instances \\
     --stack-set-name StackMapReadOnlyRole \\
     --deployment-targets OrganizationalUnitIds=<your-root-ou-id> \\
     --regions us-east-1

   OR deploy to a single account for testing:

   aws cloudformation deploy \\
     --template-file {template_path} \\
     --stack-name StackMapReadOnlyRole \\
     --capabilities CAPABILITY_NAMED_IAM

3. SCAN with StackMap:

   stackmap scan-aws --org-scan --org-file org.json
   stackmap scan-aws --org-scan  # auto-discovers org structure

Security notes:
- The role is STRICTLY read-only. Run 'stackmap aws-policy' to inspect the exact permissions.
- The trust policy limits assumption to your management account only.
- No credentials are stored by StackMap - only the standard AWS SDK credential chain is used.
- You can add an --external-id flag for additional security.
- The full source code is open: review scanner.py to verify every API call.
"""
