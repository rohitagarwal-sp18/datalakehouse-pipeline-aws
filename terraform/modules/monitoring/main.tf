locals {
  prefix = "${var.project}-${var.env}"
  tags = merge(
    {
      Project     = var.project
      Environment = var.env
      ManagedBy   = "terraform"
    },
    var.tags
  )
}

# ─── SNS TOPIC ───────────────────────────────────────────────────────────────

resource "aws_sns_topic" "alerts" {
  name = "${local.prefix}-pipeline-alerts"
  tags = local.tags
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# Allow EventBridge to publish to SNS
resource "aws_sns_topic_policy" "alerts" {
  arn = aws_sns_topic.alerts.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowEventBridge"
        Effect = "Allow"
        Principal = { Service = "events.amazonaws.com" }
        Action   = "SNS:Publish"
        Resource = aws_sns_topic.alerts.arn
      }
    ]
  })
}

# ─── EVENTBRIDGE: GLUE JOB FAILURES ─────────────────────────────────────────

resource "aws_cloudwatch_event_rule" "glue_failure" {
  name        = "${local.prefix}-glue-job-failure"
  description = "Trigger alert when any Glue job in this project fails or times out"

  event_pattern = jsonencode({
    source      = ["aws.glue"]
    detail-type = ["Glue Job State Change"]
    detail = {
      state     = ["FAILED", "TIMEOUT", "ERROR"]
      jobName   = [{ prefix = "${local.prefix}-" }]
    }
  })

  tags = local.tags
}

resource "aws_cloudwatch_event_target" "glue_failure_sns" {
  rule      = aws_cloudwatch_event_rule.glue_failure.name
  target_id = "GlueFailureAlert"
  arn       = aws_sns_topic.alerts.arn
}

# ─── EVENTBRIDGE: STEP FUNCTIONS FAILURES ────────────────────────────────────

resource "aws_cloudwatch_event_rule" "sfn_failure" {
  name        = "${local.prefix}-sfn-failure"
  description = "Trigger alert when the pipeline Step Functions execution fails"

  event_pattern = jsonencode({
    source      = ["aws.states"]
    detail-type = ["Step Functions Execution Status Change"]
    detail = {
      status          = ["FAILED", "TIMED_OUT", "ABORTED"]
      stateMachineArn = var.state_machine_arn != "" ? [var.state_machine_arn] : [{ prefix = "arn:aws:states:" }]
    }
  })

  tags = local.tags
}

resource "aws_cloudwatch_event_target" "sfn_failure_sns" {
  rule      = aws_cloudwatch_event_rule.sfn_failure.name
  target_id = "SFNFailureAlert"
  arn       = aws_sns_topic.alerts.arn
}

# ─── CLOUDWATCH DASHBOARD ────────────────────────────────────────────────────

resource "aws_cloudwatch_dashboard" "pipeline" {
  dashboard_name = "${local.prefix}-pipeline"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "text"
        x      = 0
        y      = 0
        width  = 24
        height = 1
        properties = {
          markdown = "## ${var.project} — ${var.env} Pipeline Health"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 1
        width  = 12
        height = 6
        properties = {
          title   = "Glue Job Failed Task Count"
          view    = "timeSeries"
          stacked = false
          period  = 300
          metrics = length(var.glue_job_names) > 0 ? [
            for job in var.glue_job_names : [
              "Glue", "glue.driver.aggregate.numFailedTasks",
              "JobName", "${local.prefix}-${job}",
              "Type", "gauge",
              { label = job }
            ]
          ] : [["Glue", "glue.driver.aggregate.numFailedTasks"]]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 1
        width  = 12
        height = 6
        properties = {
          title   = "Glue Job Completed Tasks"
          view    = "timeSeries"
          stacked = false
          period  = 300
          metrics = length(var.glue_job_names) > 0 ? [
            for job in var.glue_job_names : [
              "Glue", "glue.driver.aggregate.numCompletedTasks",
              "JobName", "${local.prefix}-${job}",
              "Type", "gauge",
              { label = job }
            ]
          ] : [["Glue", "glue.driver.aggregate.numCompletedTasks"]]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 7
        width  = 12
        height = 6
        properties = {
          title   = "Athena Data Scanned (bytes)"
          view    = "timeSeries"
          period  = 300
          metrics = [
            ["AWS/Athena", "DataScannedInBytes", "WorkGroup", "${local.prefix}-workgroup"]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 7
        width  = 12
        height = 6
        properties = {
          title   = "Step Functions Executions"
          view    = "timeSeries"
          period  = 300
          metrics = [
            ["AWS/States", "ExecutionsSucceeded", "StateMachineArn", var.state_machine_arn],
            ["AWS/States", "ExecutionsFailed", "StateMachineArn", var.state_machine_arn],
            ["AWS/States", "ExecutionsTimedOut", "StateMachineArn", var.state_machine_arn]
          ]
        }
      }
    ]
  })
}
