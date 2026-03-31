resource "aws_lambda_function" "process_worker" {
  function_name = "process-worker"
  runtime       = "python3.11"
  handler       = "index.handler"
}

resource "aws_sns_topic" "shared_alerts" {
  name = "shared-alerts-reference"
}
