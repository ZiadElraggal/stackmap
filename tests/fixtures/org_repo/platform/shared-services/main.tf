resource "aws_sns_topic" "alerts" {
  name = "alerts"
}

resource "aws_sqs_queue" "jobs" {
  name = "jobs"
}
