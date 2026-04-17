# Step Functions Viewer

StackMap parses Amazon States Language definitions into an `asl_graph` stored on state-machine nodes. The parser is used by Terraform, CloudFormation/SAM, and live AWS scans.

## ASL Graph Contract

State-machine nodes may include:

```json
{
  "properties": {
    "asl_graph": {
      "start_at": "ValidateOrder",
      "states": [],
      "transitions": [],
      "resources": [],
      "warnings": []
    }
  }
}
```

When parsing fails, `asl_graph` is still present as an error object such as `{"error": "unparseable"}`.

## Viewer Behavior

The detail panel renders a State Machine section for `aws_sfn_state_machine`, `AWS::StepFunctions::StateMachine`, and `AWS::Serverless::StateMachine` nodes.

The viewer covers:

- Task integrations, including direct Lambda ARNs, optimized service integrations, AWS SDK integrations, and `.sync:2`
- Choice branches and defaults
- Parallel branches
- classic Map iterators and Distributed Map `ItemProcessor`
- Wait, Pass, Succeed, and Fail states
- Retry and Catch paths
- warnings for unreachable states, orphan `Next` targets, missing terminal states, and Tasks without Catch handlers
- raw ASL graph JSON for debugging
- optional recent execution summaries loaded on demand

Clicking a resolved Task resource selects and pans the main graph to that resource.

## Optional Execution Overlay

Recent execution summaries are off by default to avoid extra AWS API calls. Open the State Machine panel and click **Load recent executions** while serving with an AWS profile:

```bash
stackmap scan-aws --profile dev --serve
```

For an existing JSON output, use:

```bash
stackmap serve --source aws-output.json --aws-profile dev
```

The button calls `states:ListExecutions` for the selected state machine only and stores up to 25 compact summaries in `asl_graph.recent_executions`.

## Manual Review Checklist

- Open a graph with a Step Functions state machine.
- Select the state machine node and expand State Machine in the detail panel.
- Confirm Task, Choice, Parallel, and Map cards render with nested branch/iterator content.
- Toggle Raw graph JSON and confirm the parsed graph is visible.
- Open full screen and confirm the same state-machine view expands without losing state.
- Click a resolved Task resource and confirm the main graph selects/pans to that resource.
- Serve with an AWS profile, click **Load recent executions**, and confirm the summary appears when execution data is available.
