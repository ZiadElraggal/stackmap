resource "aws_sns_topic" "alerts" {
  name = "alerts"
}

resource "aws_sqs_queue" "jobs" {
  name = "jobs"
}

resource "aws_kms_key" "shared_events" {
  description = "shared event bus key"
}
