# Smart Groups

Smart groups turn noisy infrastructure inventories into component-sized slices that are easier to review in the UI.

## What Gets Grouped

Auto detection now looks for these signals:

- account and region roots when a scan spans multiple accounts or regions
- environment tags such as `env`, `environment`, `stage`, and `tier`
- service/workload tags such as `service`, `project`, `app`, `component`, and `workload`
- team ownership tags such as `team`, `owner`, `squad`, and `department`
- Terraform module paths from `source_module`
- CloudFormation/SAM stack names
- shared IAM roles for compute resources
- naming prefixes, VPCs, subnets, and connectivity as lower-confidence fallbacks

Each generated group carries `metadata.reason`, `metadata.confidence`, `metadata.signals`, and, when possible, a `parent` pointer. The UI uses parent groups as filter scopes and primary groups as the component cards.

## Component Landing Behavior

The component landing page shows:

- a View All action for the full graph
- parent-scope filter chips for account, region, and environment roots
- confidence pips on smart component cards
- reason captions explaining why a group exists
- an unlinked bucket for resources that no smart group claimed

This keeps genuinely ungrouped resources visible without presenting weak topology buckets as first-class services.

## Suggested Rules

`suggest_groups()` now proposes env, team, module, tag, prefix, and VPC rules with confidence metadata. Suggested configs are intended as a review aid before committing `.stackmap/groups.yaml` rules.

Example suggestion metadata:

```yaml
metadata:
  confidence: 0.78
  signals:
    - service
    - tag:service
  comment: "confidence: 0.78"
```

## Manual Review Checklist

- Run `stackmap serve --source <graph.json>` on a graph with service/env tags.
- Confirm service cards are nested under the expected environment/account/region filters.
- Use View All and confirm the graph returns to the full resource set.
- Open a grouped resource and confirm the detail panel shows the smart group reason and signal chips.
- Confirm unlinked resources are only resources that no smart group claimed.
