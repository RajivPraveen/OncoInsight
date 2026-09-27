output "raw_bucket" {
  value = aws_s3_bucket.raw.bucket
}

output "warehouse_endpoint" {
  value = aws_db_instance.warehouse.address
}

output "warehouse_master_secret_arn" {
  value = aws_db_instance.warehouse.master_user_secret[0].secret_arn
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "ecs_cluster" {
  value = aws_ecs_cluster.this.name
}
