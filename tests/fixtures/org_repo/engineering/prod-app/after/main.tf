resource "aws_lambda_function" "process_worker" {
  function_name = "process-worker"
  runtime       = "python3.12"
  handler       = "index.handler"
  timeout       = 180
}

resource "aws_s3_bucket" "warehouse_exports" {
  bucket = "acme-static-site"
}
