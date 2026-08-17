# Terraform Bootstrap

This isolated configuration creates the encrypted, versioned S3 state bucket and DynamoDB lock table used by the main staging and production Terraform configuration. Run it once with a globally unique bucket name, then record its two outputs as GitHub repository variables: `TF_STATE_BUCKET` and `TF_LOCK_TABLE`.

```powershell
terraform -chdir=infrastructure/bootstrap init
terraform -chdir=infrastructure/bootstrap apply -var="state_bucket_name=cortex-lab-terraform-665206375111" -var="github_repository=YOUR_GITHUB_OWNER/in-silico-Cortex-Lab"
```

Do not destroy these resources while either environment exists. The `github_deploy_role_arn` output belongs in the GitHub Actions secret `AWS_DEPLOY_ROLE_ARN`.

The role deliberately starts broad so Terraform can create the first runtime. After staging is stable, use CloudTrail access data to replace `AdministratorAccess` with a policy limited to this account's Cortex Lab resources.
