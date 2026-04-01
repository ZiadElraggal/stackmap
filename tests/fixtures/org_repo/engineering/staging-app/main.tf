resource "aws_lambda_function" "api_handler" {
  function_name = "api-handler"
  runtime       = "python3.11"
  handler       = "app.handler"
}
