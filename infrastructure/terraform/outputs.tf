output "ecr_repository_url" { value = aws_ecr_repository.backend.repository_url }
output "media_bucket_name" { value = aws_s3_bucket.media.id }
output "api_load_balancer_dns_name" { value = aws_lb.api.dns_name }
output "api_cloudflare_cname" {
  value       = aws_lb.api.dns_name
  description = "Create a DNS-only CNAME for api_domain_name in Cloudflare pointing here."
}
output "acm_cloudflare_validation_records" {
  value = [for record in aws_acm_certificate.api.domain_validation_options : {
    name  = record.resource_record_name
    type  = record.resource_record_type
    value = record.resource_record_value
  }]
  description = "Create these DNS-only records in Cloudflare, then re-run Terraform."
}
output "runtime_secret_arn" { value = aws_secretsmanager_secret.runtime.arn }
output "sqs_queue_url" { value = aws_sqs_queue.jobs.url }
output "sqs_dead_letter_queue_url" { value = aws_sqs_queue.dead_letter.url }
output "migration_task_definition_arn" { value = aws_ecs_task_definition.migration.arn }
