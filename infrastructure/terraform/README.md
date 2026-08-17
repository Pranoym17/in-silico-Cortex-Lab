# Cortex Lab Terraform

Terraform creates isolated AWS runtime resources for `staging` and `production` in `us-east-2`. Cloudflare remains the DNS authority and is intentionally not managed by Terraform.

1. Install Terraform 1.9 or newer and authenticate AWS with an infrastructure-capable non-root identity.
2. Copy `terraform.tfvars.example` to an ignored `staging.tfvars` file and replace every placeholder.
3. Build and push the immutable API/worker image before applying ECS services.
4. Run `terraform init`, `terraform plan -var-file=staging.tfvars`, then `terraform apply -var-file=staging.tfvars`.
5. Terraform outputs ACM validation records. Create them as DNS-only Cloudflare records, wait for validation, and re-run apply.
6. Create the output API CNAME as a DNS-only Cloudflare record, then test `/health`.

Use a separate tfvars file and state key for production. The runtime secret map is sensitive but Terraform state still contains sensitive values; use encrypted remote state before applying real environments.
