"""Phase 4 quality gate: CloudFormation core support."""

from pathlib import Path

from stackmap.parsers.base import EdgeType, ResourceCategory
from stackmap.parsers import cloudformation as cfn
from stackmap.parsers.cloudformation import CloudFormationParser

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _edge_count(ir, source_type: str, target_type: str, edge_type: EdgeType) -> int:
    node_types = {n.id: n.resource_type for n in ir.nodes}
    return sum(
        1
        for e in ir.edges
        if e.edge_type == edge_type
        and node_types.get(e.source) == source_type
        and node_types.get(e.target) == target_type
    )


def test_cloudformation_simple_fixture_parses() -> None:
    ir = CloudFormationParser().parse(str(FIXTURES / "cloudformation-simple.json"))
    assert len(ir.nodes) >= 12
    assert len(ir.edges) >= 10
    assert ir.metadata["source_type"] == "cloudformation"


def test_cloudformation_categories_are_mapped() -> None:
    ir = CloudFormationParser().parse(str(FIXTURES / "cloudformation-simple.json"))
    categories = {n.resource_type: n.category for n in ir.nodes}
    assert categories["AWS::ApiGateway::RestApi"] == ResourceCategory.INTEGRATION
    assert categories["AWS::Lambda::Function"] == ResourceCategory.COMPUTE
    assert categories["AWS::DynamoDB::Table"] == ResourceCategory.DATABASE
    assert categories["AWS::S3::Bucket"] == ResourceCategory.STORAGE


def test_cloudformation_core_relationships() -> None:
    ir = CloudFormationParser().parse(str(FIXTURES / "cloudformation-simple.json"))
    assert _edge_count(ir, "AWS::Lambda::Function", "AWS::IAM::Role", EdgeType.AUTHENTICATES) >= 2
    assert _edge_count(ir, "AWS::ApiGateway::RestApi", "AWS::Lambda::Function", EdgeType.TRIGGERS) >= 2
    assert _edge_count(ir, "AWS::ApiGateway::Stage", "AWS::ApiGateway::Deployment", EdgeType.REFERENCES) >= 1


def test_cloudformation_no_dangling_edges() -> None:
    ir = CloudFormationParser().parse(str(FIXTURES / "cloudformation-simple.json"))
    node_ids = {n.id for n in ir.nodes}
    dangling = [e for e in ir.edges if e.source not in node_ids or e.target not in node_ids]
    assert not dangling


def test_cloudformation_yaml_with_intrinsics_parses(tmp_path: Path) -> None:
    if cfn.yaml is None:
        return

    template = """
AWSTemplateFormatVersion: "2010-09-09"
Resources:
  AppRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: demo-app-role
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
  AppFn:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: demo-fn
      Role: !GetAtt AppRole.Arn
      Runtime: python3.12
      Handler: index.handler
      Code:
        ZipFile: |
          def handler(event, context):
            return {"ok": True}
  Api:
    Type: AWS::ApiGateway::RestApi
    Properties:
      Name: !Sub "${AWS::StackName}-api"
  AllowInvoke:
    Type: AWS::Lambda::Permission
    Properties:
      Action: lambda:InvokeFunction
      FunctionName: !Ref AppFn
      Principal: apigateway.amazonaws.com
      SourceArn: !Sub "arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${Api}/*/*/*"
"""
    yaml_path = tmp_path / "mini.yaml"
    yaml_path.write_text(template)

    ir = CloudFormationParser().parse(str(yaml_path))
    assert len(ir.nodes) == 4
    assert any(n.resource_type == "AWS::Lambda::Function" for n in ir.nodes)
    assert any(e.edge_type == EdgeType.AUTHENTICATES for e in ir.edges)
    assert any(e.edge_type == EdgeType.TRIGGERS for e in ir.edges)


def test_cloudformation_yml_extension_parses(tmp_path: Path) -> None:
    if cfn.yaml is None:
        return

    template = """
AWSTemplateFormatVersion: "2010-09-09"
Resources:
  Bucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: demo-bucket-123
"""
    yml_path = tmp_path / "mini.yml"
    yml_path.write_text(template)

    ir = CloudFormationParser().parse(str(yml_path))
    assert len(ir.nodes) == 1
    assert ir.nodes[0].resource_type == "AWS::S3::Bucket"
