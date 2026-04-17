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

Click **Open workflow graph** to switch the main canvas into a dedicated Step Functions graph mode. This replaces the older stacked card viewer so state machines have one primary inspection surface.

The workflow graph covers:

- Task integrations, including direct Lambda ARNs, optimized service integrations, AWS SDK integrations, and `.sync:2`
- Choice branches and defaults as labeled edges
- Parallel branches, classic Map iterators, and Distributed Map `ItemProcessor`
- Wait, Pass, Succeed, and Fail states
- Step Functions-specific node icons for Pass, Choice, Task, Map, Parallel, Wait, Succeed, and Fail
- a lane-free workflow layout instead of architecture tiers/layers
- Retry and Catch paths
- warnings for unreachable states, orphan `Next` targets, missing terminal states, and Tasks without Catch handlers as amber state halos
- optional mirrored Task targets via **Show target resources**
- jump-back from mirrored targets to the real architecture node
- optional selected-execution overlays

Clicking a resolved Task resource selects and pans the main graph to that resource.

## Optional Execution Debugging

Recent execution summaries are off by default to avoid extra AWS API calls. Open the workflow graph and click **Load recent executions** while serving with an AWS profile:

```bash
stackmap scan-aws --profile dev --serve
```

For an existing JSON output, use:

```bash
stackmap serve --source aws-output.json --aws-profile dev
```

The recent-executions button calls `states:ListExecutions` for the selected state machine only and stores up to 25 compact summaries in `asl_graph.recent_executions`.

Selecting one execution and clicking **Overlay selected execution** calls `states:GetExecutionHistory` for that one execution only. StackMap normalizes the history into per-state statuses (`running`, `succeeded`, `failed`, `timed_out`, `aborted`) and paints the workflow nodes with success/failure/running badges.

Workflow structure works with the normal scan permissions:

- `states:ListStateMachines`
- `states:DescribeStateMachine`

Execution debugging requires the optional Step Functions debugger policy:

```bash
stackmap aws-policy --addon stepfunctions
```

That add-on includes:

- `states:ListExecutions`
- `states:GetExecutionHistory`

If AWS denies execution access, the UI reports: “Your AWS profile can view the state machine definition, but not execution history. Add `states:ListExecutions` and `states:GetExecutionHistory` to use debugging overlays.”

## Manual Review Checklist

- Open a graph with a Step Functions state machine.
- Select the state machine node and click **Open workflow graph**.
- Confirm Task, Choice, Parallel, and Map render as StackMap graph nodes with labeled paths.
- Confirm warnings render as amber halos/dots on affected states.
- Toggle **Show target resources** and confirm resolved Task targets appear as mirrored architecture nodes.
- Click a mirrored target and confirm the real architecture node is selected.
- Toggle Raw graph JSON and confirm the parsed graph is visible.
- Serve with an AWS profile without the optional debugger policy, click **Load recent executions**, and confirm the permission warning is clear.
- Add the optional debugger policy, click **Load recent executions**, choose one execution, click **Overlay selected execution**, and confirm per-state status appears.
