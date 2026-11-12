# ITMO 444/544 — Lab 07: Infrastructure as Code with Terraform

## Weather Advisor Rebuild

**Student:** Himanshu Chaudhary  
**AWS Region:** `us-east-2`  
**Terraform Version:** `v1.17.2`  
**AWS Provider Version:** `v5.100.0`

---

# Overview

In this lab, I rebuilt the Weather Advisor infrastructure using Terraform instead of manually managing AWS resources with Python and AWS CLI scripts.

Terraform was used to define and manage:

- Application Load Balancer
- Weather and Advisor listeners
- Target Groups
- Auto Scaling Groups
- EC2 Launch Templates
- EC2 instances
- DynamoDB
- IAM roles and instance profiles
- Security Groups
- AWS Systems Manager Parameter Store
- User-data configuration
- Terraform outputs and state

The lab demonstrated Terraform concepts such as declarative infrastructure, idempotence, dependency management, state tracking, drift detection, targeted updates, IAM least privilege, graceful failure handling, and infrastructure destruction.

---

# Part A — First Terraform Experience

Terraform uses a declarative approach. Instead of manually specifying each AWS API call, the Terraform configuration describes the desired final infrastructure.

Terraform then compares:

```text
Desired configuration
        vs.
Terraform state
        vs.
Actual AWS infrastructure
```

and determines what actions are required.

Important Terraform plan symbols are:

| Symbol | Meaning |
|---|---|
| `+` | Create a resource |
| `~` | Modify a resource in place |
| `-/+` | Destroy and recreate a resource |
| `No changes` | Infrastructure already matches configuration |

A second Terraform run showing `No changes` demonstrates idempotence.

Idempotence means applying the same configuration repeatedly does not keep changing infrastructure after the desired state has been reached.

---

# Part B — Weather Advisor Application

The project contains two application tiers.

## Weather Application

The Weather service accepts a ZIP code and retrieves weather information.

It also:

- stores weather lookup information in DynamoDB
- uses caching
- exposes health endpoints
- serves requests through the Application Load Balancer

## Advisor Application

The Advisor service calls the Weather service and generates clothing recommendations.

It retrieves the Gemini API key from AWS Systems Manager Parameter Store.

If Gemini fails, the Advisor can return rule-based fallback advice instead of completely failing.

This improves application availability.

---

# Part C — Terraform Configuration

The Terraform configuration was separated into several files:

```text
versions.tf
variables.tf
locals.tf
network.tf
storage.tf
iam.tf
alb.tf
compute.tf
outputs.tf
user-data.sh.tftpl
terraform.tfvars
```

Separating Terraform files by responsibility makes the infrastructure easier to understand and maintain.

Terraform was initialized with:

```bash
terraform init
```

The files were formatted and validated with:

```bash
terraform fmt
terraform validate
```

The initial plan showed:

```text
Plan: 25 to add, 0 to change, 0 to destroy.
```

This means Terraform identified 25 infrastructure resources that needed to be created.

---

# Part D — IAM Troubleshooting

During deployment, additional IAM permissions were temporarily required for SSM tagging operations.

### Screenshot Path

```text
screenshots/01_troubleshooting_iam_ssm_tag_access_policy.png
```

### Explanation

This screenshot documents the temporary IAM permission added during troubleshooting.

IAM controls which AWS actions a user or service is allowed to perform.

Terraform itself can only create or modify AWS resources if the AWS identity executing Terraform has permission to perform those operations.

The temporary permission was removed after completing the lab.

---

# Part E — Deployment and Testing

## Manual Weather and Gemini Test

### Screenshot Path

```text
screenshots/02_manual_weather_cache_and_gemini_test.png
```

### Explanation

This screenshot shows successful manual testing of the deployed Weather and Advisor applications.

The Weather service demonstrated cache behavior, and the Advisor successfully generated a Gemini-based recommendation.

This proves that communication between the major components was working:

```text
Client
  ↓
Application Load Balancer
  ↓
Advisor Service
  ↓
Weather Service
  ↓
Weather API / DynamoDB
```

The Advisor also successfully communicated with Gemini using the API key stored in SSM Parameter Store.

---

## Smoke Test

### Screenshot Path

```text
screenshots/03_smoke_test_9_of_9_passed.png
```

### Explanation

The smoke test completed with:

```text
9 of 9 checks passed
```

A smoke test verifies that the most important application and infrastructure functions work after deployment.

Passing all nine checks confirms that the Terraform-created environment was operational before continuing with further experiments.

---

# Part F — Terraform Experiments

# Step 1 — Compare Infrastructure Effort

### Screenshot Path

```text
screenshots/04_step1_effort_line_counts.png
```

### Explanation

This screenshot compares the previous Python implementation with the Terraform configuration.

Approximate results were:

```text
Previous Python total lines: 214
Previous Python code lines: 152
Terraform total lines: 449
Terraform code lines: 356
Delete-script lines: 60
```

Terraform did not necessarily reduce the number of lines.

However, Terraform reduced infrastructure-management complexity because it automatically handles:

- resource dependencies
- state tracking
- updates
- idempotence
- drift detection
- destruction

The Python approach required custom logic for many of these operations.

Therefore, Terraform's main advantage is not simply fewer lines of code. Its advantage is structured and predictable infrastructure lifecycle management.

---

# Step 2 — Terraform Dependency Graph

### Screenshot Path

```text
screenshots/05_step2_terraform_dependency_graph.png
```

### Explanation

Terraform automatically builds a dependency graph between infrastructure resources.

For example, the Advisor launch template needs the Weather service URL.

That URL depends on the Application Load Balancer DNS name.

Therefore, Terraform understands that the ALB must exist before configuration depending on its DNS name can be completed.

If the reference to:

```text
aws_lb.main.dns_name
```

were removed, Terraform would no longer automatically infer that dependency.

Terraform dependencies help determine the correct order for infrastructure creation and destruction.

---

# Step 3 — Terraform Idempotence

### Screenshot Path

```text
screenshots/06_step3_no_changes_idempotence.png
```

### Explanation

Terraform reported:

```text
No changes.
```

This demonstrates idempotence.

Terraform compared the desired configuration against both Terraform state and the actual AWS infrastructure.

Because everything already matched, Terraform did not perform unnecessary changes.

This is more reliable than manually checking whether a resource merely exists.

A resource may exist but still have incorrect configuration.

Terraform checks the resource configuration instead of only its existence.

---

# Step 4 — Change CACHE_SECONDS

The Weather cache value was temporarily changed to:

```text
CACHE_SECONDS=60
```

## Terraform Plan Details

### Screenshot Path

```text
screenshots/07_step4_cache_seconds_plan_details.png
```

### Explanation

This screenshot shows which Terraform resources were affected by the cache configuration change.

Terraform identified that the Weather launch configuration needed to change while unrelated infrastructure could remain unchanged.

This demonstrates Terraform's ability to calculate targeted changes.

---

## Terraform Plan Summary

### Screenshot Path

```text
screenshots/08_step4_cache_seconds_plan_summary.png
```

### Explanation

Terraform showed:

```text
Plan: 0 to add, 2 to change, 0 to destroy.
```

Only two resources required changes.

Terraform did not unnecessarily recreate the entire infrastructure.

This is one of the major benefits of infrastructure state management.

---

## Auto Scaling Instance Refresh

### Screenshot Path

```text
screenshots/09_step4_instance_refresh_started.png
```

### Explanation

Changing the launch-template configuration caused the Weather Auto Scaling Group to refresh its EC2 instance.

An Auto Scaling instance refresh gradually replaces old instances with instances created using the latest launch-template configuration.

This allows configuration changes to be deployed while minimizing downtime.

---

## Verify CACHE_SECONDS

### Screenshot Path

```text
screenshots/10_step4_cache_seconds_60_verified.png
```

### Explanation

The replacement EC2 instance showed:

```text
Environment="CACHE_SECONDS=60"
```

This verifies that Terraform successfully propagated the new configuration to the new Weather instance.

It also demonstrates that modifying infrastructure configuration can cause controlled replacement of application instances.

---

# Step 5 — Configuration Drift

Configuration drift occurs when the actual cloud infrastructure is changed outside Terraform and no longer matches the Terraform configuration.

## Health Check Drift

### Screenshot Path

```text
screenshots/11_step5_health_check_drift_plan.png
```

### Explanation

The Weather target-group health-check path was manually changed outside Terraform.

Terraform detected that the real AWS configuration differed from the desired configuration.

It then produced a plan to restore the correct value.

This demonstrates Terraform's ability to detect configuration drift.

---

## Target Group Recovery

### Screenshot Path

```text
screenshots/12_step5_target_group_recovery.png
```

### Explanation

After Terraform repaired the health-check configuration, the replacement Weather target became healthy.

Target-group health checks are used by the load balancer to determine whether application instances are ready to receive traffic.

A healthy target means the application successfully responds to the configured health-check request.

---

## Deleted Advisor Listener

### Screenshot Path

```text
screenshots/13_step5_deleted_listener_plan_1_add.png
```

### Explanation

The Advisor listener was manually deleted from AWS.

Terraform detected that a declared resource was completely missing.

The plan showed:

```text
Plan: 1 to add, 0 to change, 0 to destroy.
```

Terraform then recreated the listener.

This demonstrates an important difference between Terraform and simple resource-existence scripts.

Terraform continuously compares the desired infrastructure definition with the actual infrastructure.

---

# Step 6 — IAM Least Privilege

### Screenshot Path

```text
screenshots/14_step6_iam_policy_simulator.png
```

### Explanation

The IAM Policy Simulator was used to verify permissions for the Weather and Advisor roles.

The expected results were:

| Role | Action | Result |
|---|---|---|
| Weather | `dynamodb:PutItem` | Allowed |
| Weather | `ssm:GetParameter` | Implicit Deny |
| Advisor | `ssm:GetParameter` | Allowed |
| Advisor | `dynamodb:GetItem` | Implicit Deny |

This demonstrates the principle of least privilege.

Least privilege means giving a component only the permissions required to perform its job.

The Weather service needs DynamoDB access but does not need the Gemini secret.

The Advisor service needs the Gemini secret but does not need direct access to the Weather DynamoDB table.

Separating permissions reduces the damage that could occur if one application tier is compromised.

---

# Step 7 — Terraform State and External Secrets

### Screenshot Path

```text
screenshots/15_step7_no_changes_and_state_key_check.png
```

### Explanation

Terraform reported no changes after the Gemini secret had been updated outside Terraform.

The state check:

```bash
grep -c "AIza" terraform.tfstate
```

returned:

```text
0
```

The SSM Terraform resource used:

```hcl
lifecycle {
  ignore_changes = [value]
}
```

This tells Terraform not to treat external changes to the parameter's value as infrastructure drift.

This is useful when the secret is managed separately from infrastructure.

However, Terraform state must still be treated as sensitive because provider implementations can store resource values inside state.

Terraform state files should therefore never be committed publicly.

---

# Step 8 — Gemini Failure and Graceful Fallback

## Fallback Responses

### Screenshot Path

```text
screenshots/16_step8_fallback_responses.png
```

### Explanation

The valid Gemini API key was temporarily replaced with:

```text
not-a-real-key
```

After the application's cache expired, the Advisor was tested twice.

Both requests returned:

```text
fallback - ...
```

instead of failing completely.

This demonstrates graceful degradation.

Graceful degradation means an application continues providing reduced functionality when one dependency becomes unavailable.

---

## Gemini Error Logs

### Screenshot Path

```text
screenshots/17_step8_gemini_error_logs.png
```

### Explanation

The Advisor journal contained entries such as:

```text
"event":"gemini_error"
"status":400
"reason":"gemini_http_error"
```

This proves that Gemini was actually failing while the user continued receiving fallback recommendations.

Logging is important because graceful fallback can otherwise hide service failures.

Without logs or monitoring, operators may not realize that the AI integration is broken.

---

## Gemini Restored

### Screenshot Path

```text
screenshots/18_step8_gemini_restored.png
```

### Explanation

After restoring the valid Gemini API key, the Advisor returned to:

```text
gemini - ...
```

This confirmed that the SSM parameter was restored correctly and the Advisor resumed normal Gemini operation.

---

## Advisor Webpage Verification

### Screenshot Path

```text
screenshots/19_advisor_webpage_gemini.png
```

### Explanation

The final Advisor webpage was tested using ZIP code:

```text
60616
```

The page displayed Chicago weather information and generated a clothing recommendation.

The page showed:

```text
Suggestion source: gemini
```

This verifies the complete application flow through the web interface.

---

# Step 9 — EC2 vs Lambda Architecture

The current architecture uses EC2 instances.

A serverless implementation could use AWS Lambda and API Gateway.

| EC2 Architecture | Lambda Architecture |
|---|---|
| Launch Templates | Lambda functions |
| Auto Scaling Groups | Automatic Lambda scaling |
| ALB listeners | API Gateway routes |
| Target Groups | API Gateway integrations |
| EC2 IAM roles | Lambda execution roles |
| systemd services | Lambda handlers |
| User data | Function configuration |
| Instance refresh | Function deployment |
| DynamoDB | DynamoDB can remain |
| SSM | SSM can remain |

Lambda would simplify server management because there would be no EC2 operating systems, launch templates, systemd services, or instance refreshes.

However, Lambda would not remove the need for:

- IAM permissions
- DynamoDB
- SSM
- monitoring
- logging
- Gemini integration
- application debugging
- external API error handling

Serverless architecture reduces infrastructure administration but does not eliminate application complexity.

---

# Step 10 — Terraform Destroy and Cleanup

## Final Terraform Status and Version

### Screenshot Path

```text
screenshots/20_final_no_changes_terraform_version_sts.png
```

### Explanation

Before destruction, Terraform reported that no infrastructure changes were required.

The environment also showed:

```text
Terraform v1.17.2
AWS Provider v5.100.0
```

The AWS account identifier was masked before capturing the screenshot.

This screenshot proves the final Terraform environment and clean infrastructure state before destruction.

---

## Destroy Plan

### Screenshot Path

```text
screenshots/21_step10_destroy_plan_25_resources.png
```

### Explanation

Terraform produced:

```text
Plan: 0 to add, 0 to change, 25 to destroy.
```

The destroy plan allows the operator to review which resources will be removed before executing the actual destruction.

Reviewing the plan reduces the risk of deleting unexpected resources.

---

## Destroy Complete

### Screenshot Path

```text
screenshots/22_step10_destroy_complete_25.png
```

### Explanation

Terraform reported:

```text
Destroy complete! Resources: 25 destroyed.
```

This confirms that all 25 Terraform-managed infrastructure resources were successfully removed.

Terraform manages both infrastructure creation and infrastructure destruction from the same declared configuration and state information.

---

## Cleanup Verification

### Screenshot Path

```text
screenshots/23_step10_cleanup_verification.png
```

### Explanation

This screenshot confirms several cleanup checks.

The SSM Gemini parameter returned:

```text
ParameterNotFound
```

The command:

```bash
terraform state list
```

returned no resources.

The temporary Lab07 IAM policies had also been deleted.

The temporary SSH key files were removed from the local machine.

This confirms that both AWS and local troubleshooting artifacts were cleaned up.

---

## Final AWS Resource Verification

### Screenshot Path

```text
screenshots/24_step10_final_aws_resource_checks.png
```

### Explanation

Final AWS CLI checks were performed for:

- EC2
- Load Balancers
- Target Groups
- Auto Scaling Groups
- Launch Templates
- DynamoDB
- SSM Parameter Store
- Security Groups
- IAM roles

No active Lab07 resources remained.

This confirms that the Terraform infrastructure had been completely removed and that no lab resources were intentionally left running.

---

# Review Questions

## 1. Why is Terraform declarative?

Terraform is declarative because the configuration describes the desired final infrastructure rather than describing every API operation required to create it.

Terraform calculates the required actions automatically.

---

## 2. What is Terraform state?

Terraform state stores Terraform's understanding of the infrastructure it manages.

It allows Terraform to map Terraform resources to actual AWS resources.

Terraform uses state to determine whether resources must be:

- created
- updated
- replaced
- destroyed

---

## 3. What is idempotence?

Idempotence means repeatedly applying the same configuration eventually results in:

```text
No changes.
```

Once the infrastructure matches the desired configuration, Terraform does not keep changing it.

---

## 4. How does Terraform determine dependencies?

Terraform detects dependencies when resources reference attributes from other resources.

For example, using:

```text
aws_lb.main.dns_name
```

creates a dependency on the Application Load Balancer.

Terraform uses its dependency graph to determine creation and destruction order.

---

## 5. What is configuration drift?

Configuration drift occurs when someone changes real infrastructure outside Terraform.

Terraform detects differences between the desired configuration and actual AWS resources.

It can then generate a plan to repair those differences.

---

## 6. Why use `terraform plan`?

`terraform plan` shows what Terraform intends to do before modifying infrastructure.

This allows operators to review:

- creations
- updates
- replacements
- destructions

before applying them.

---

## 7. Why protect Terraform state?

Terraform state may contain sensitive configuration details and possibly secret values.

For this reason:

- state files should not be public
- state should not be committed to GitHub
- production state should use secure remote storage and access controls

---

## 8. Why use `ignore_changes`?

`ignore_changes` allows an attribute to be modified outside Terraform without Terraform constantly trying to restore the original configured value.

This was useful for the Gemini SSM parameter because the real secret was managed outside Terraform.

---

## 9. How was Terraform different from Python?

The previous Python approach required custom logic for:

- creation
- existence checks
- ordering
- updating
- deletion

Terraform provides built-in:

- state management
- dependency resolution
- drift detection
- idempotence
- destruction planning

This makes the infrastructure lifecycle easier to manage consistently.

---

## 10. What does Terraform not solve?

Terraform manages infrastructure, but it does not replace application monitoring.

For example, the Gemini API failed while AWS infrastructure remained operational.

Terraform did not consider this infrastructure drift.

Application logs and monitoring were needed to detect:

```text
gemini_error
```

Therefore, infrastructure management and application observability are separate concerns.

---

# Cost and Cleanup

The AWS infrastructure was active only while completing the lab.

The primary potentially billable resources included:

- EC2 instances
- Application Load Balancer
- DynamoDB usage

At the end of the lab:

```text
Destroy complete! Resources: 25 destroyed.
```

Final AWS checks confirmed that no Lab07 infrastructure remained active.

Therefore, there should be no continuing Lab07 infrastructure charges after cleanup.

---

# Final Result

The Terraform Weather Advisor lab was successfully completed.

The lab demonstrated:

- Terraform deployment
- infrastructure state management
- idempotence
- dependency graphs
- targeted configuration changes
- Auto Scaling instance refresh
- drift detection
- drift repair
- IAM least privilege
- external secret management
- graceful Gemini fallback
- application logging
- infrastructure destruction
- final AWS cleanup verification

The complete Weather Advisor infrastructure was successfully created, tested, modified, repaired, and destroyed using Terraform.
