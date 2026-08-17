resource "aws_cloudwatch_metric_alarm" "api_unhealthy" {
  alarm_name          = "${local.name_prefix}-api-unhealthy"
  alarm_description   = "The load balancer has no healthy Cortex Lab API target."
  namespace           = "AWS/ApplicationELB"
  metric_name         = "UnHealthyHostCount"
  dimensions          = { LoadBalancer = aws_lb.api.arn_suffix, TargetGroup = aws_lb_target_group.api.arn_suffix }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  treat_missing_data  = "breaching"
}

resource "aws_cloudwatch_metric_alarm" "database_cpu" {
  alarm_name          = "${local.name_prefix}-database-cpu"
  alarm_description   = "Cortex Lab PostgreSQL CPU is persistently high."
  namespace           = "AWS/RDS"
  metric_name         = "CPUUtilization"
  dimensions          = { DBInstanceIdentifier = aws_db_instance.postgres.identifier }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 3
  comparison_operator = "GreaterThanThreshold"
  threshold           = 80
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_dashboard" "runtime" {
  dashboard_name = "${local.name_prefix}-runtime"
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          title  = "API target health"
          region = var.aws_region
          metrics = [["AWS/ApplicationELB", "HealthyHostCount", "LoadBalancer", aws_lb.api.arn_suffix, "TargetGroup", aws_lb_target_group.api.arn_suffix]]
        }
      },
      {
        type = "metric"
        properties = {
          title  = "Job queue and DLQ"
          region = var.aws_region
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.jobs.name],
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.dead_letter.name],
          ]
        }
      },
      {
        type = "metric"
        properties = {
          title  = "PostgreSQL CPU"
          region = var.aws_region
          metrics = [["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", aws_db_instance.postgres.identifier]]
        }
      },
    ]
  })
}
