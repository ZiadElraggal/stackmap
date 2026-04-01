resource "aws_lambda_function" "api_handler" {
  function_name = "api-handler"
  runtime       = "python3.12"
  handler       = "app.handler"
}

resource "aws_sqs_queue" "new_ingest_queue" {
  name = "new-ingest-queue"
}
