resource "aws_cloudfront_distribution" "warehouse_exports" {
  enabled = true
}

resource "aws_s3_bucket" "warehouse_exports" {
  bucket = "acme-static-site"
}

resource "aws_s3_bucket" "ad_hoc_exports" {
  bucket = "acme-static-site-ad-hoc"
}
