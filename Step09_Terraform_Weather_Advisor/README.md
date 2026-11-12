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
- Terraform outputs
- Terraform state

The lab demonstrated Terraform concepts such as declarative infrastructure, idempotence, dependency management, state tracking, drift detection, targeted updates, IAM least privilege, graceful failure handling, and complete infrastructure destruction.

---

# Part A — First Terraform Experience

Terraform uses a declarative approach.

Instead of manually specifying each AWS API call, the Terraform configuration describes the desired final infrastructure.

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

A second Terraform run showing:

```text
No changes.
```

demonstrates idempotence.

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

`screenshots/01_troubleshooting_iam_ssm_tag_access_policy.png`

### Screenshot

![IAM SSM tag access troubleshooting](screenshots/01_troubleshooting_iam_ssm_tag_access_policy.png)

### Explanation

This screenshot documents the temporary IAM permission added during troubleshooting.

IAM controls which AWS actions a user or service is allowed to perform.

Terraform itself can only create or modify AWS resources if the AWS identity executing Terraform has permission to perform those operations.

The temporary permission was removed after completing the lab.

---

# Part E — Deployment and Testing

## Manual Weather and Gemini Test

### Screenshot Path

`screenshots/02_manual_weather_cache_and_gemini_test.png`

### Screenshot

![Manual weather cache and Gemini test](screenshots/02_manual_weather_cache_and_gemini_test.png)

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

`screenshots/03_smoke_test_9_of_9_passed.png`

### Screenshot

![Smoke test 9 of 9 passed](screenshots/03_smoke_test_9_of_9_passed.png)

### Explanation

The smoke test completed with:

```text
9 of 9 checks passed
```

A smoke test verifies that the most important application and infrastructure functions work after deployment.

Passing all nine checks confirms that the Terraform-created environment was operational before continuing with further experiments.

---

# Part F — Terraform Experiments

## Step 1 — Compare Infrastructure Effort

### Screenshot Path

`screenshots/04_step1_effort_line_counts.png`

### Screenshot

![Step 1 effort line counts](screenshots/04_step1_effort_line_counts.png)

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

## Step 2 — Terraform Dependency Graph

### Screenshot Path

`screenshots/05_step2_terraform_dependency_graph.png`

### Screenshot

![Terraform dependency graph](screenshots/05_step2_terraform_dependency_graph.png)

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

## Step 3 — Terraform Idempotence

### Screenshot Path

`screenshots/06_step3_no_changes_idempotence.png`

### Screenshot

![Terraform no changes and idempotence](screenshots/06_step3_no_changes_idempotence.png)

### Explanation

Terraform reported:

```text
No changes.
```

This demonstrates idempotence.

Terraform compared the desired configuration against both Terraform state and the actual AWS infrastructure.

Because everything already matched, Terraform did not perform unnecessary changes.

---

## Step 4 — Change CACHE_SECONDS

The Weather cache value was temporarily changed to:

```text
CACHE_SECONDS=60
```

### Terraform Plan Details

#### Screenshot Path

`screenshots/07_step4_cache_seconds_plan_details.png`

#### Screenshot

![CACHE_SECONDS Terraform plan details](screenshots/07_step4_cache_seconds_plan_details.png)

#### Explanation

This screenshot shows which Terraform resources were affected by the cache configuration change.

Terraform identified that the Weather launch configuration needed to change while unrelated infrastructure could remain unchanged.

---

### Terraform Plan Summary

#### Screenshot Path

`screenshots/08_step4_cache_seconds_plan_summary.png`

#### Screenshot

![CACHE_SECONDS plan summary](screenshots/08_step4_cache_seconds_plan_summary.png)

#### Explanation

Terraform showed:

```text
Plan: 0 to add, 2 to change, 0 to destroy.
```

Only two resources required changes.

Terraform did not unnecessarily recreate the entire infrastructure.

---

### Auto Scaling Instance Refresh

#### Screenshot Path

`screenshots/09_step4_instance_refresh_started.png`

#### Screenshot

![Weather instance refresh started](screenshots/09_step4_instance_refresh_started.png)

#### Explanation

Changing the launch-template configuration caused the Weather Auto Scaling Group to refresh its EC2 instance.

An Auto Scaling instance refresh gradually replaces old instances with instances created using the latest launch-template configuration.

---

### Verify CACHE_SECONDS

#### Screenshot Path

`screenshots/10_step4_cache_seconds_60_verified.png`

#### Screenshot

![CACHE_SECONDS 60 verification](screenshots/10_step4_cache_seconds_60_verified.png)

#### Explanation

The replacement EC2 instance showed:

```text
Environment="CACHE_SECONDS=60"
```

This verifies that Terraform successfully propagated the new configuration to the new Weather instance.

---

# Step 5 — Configuration Drift

Configuration drift occurs when the actual cloud infrastructure is changed outside Terraform and no longer matches the Terraform configuration.

## Health Check Drift

### Screenshot Path

`screenshots/11_step5_health_check_drift_plan.png`

### Screenshot

![Weather health-check drift detected](screenshots/11_step5_health_check_drift_plan.png)

### Explanation

The Weather target-group health-check path was manually changed outside Terraform.

Terraform detected that the real AWS configuration differed from the desired configuration.

It then produced a plan to restore the correct value.

---

## Target Group Recovery

### Screenshot Path

`screenshots/12_step5_target_group_recovery.png`

### Screenshot

![Weather target group recovery](screenshots/12_step5_target_group_recovery.png)

### Explanation

After Terraform repaired the health-check configuration, the replacement Weather target became healthy.

Target-group health checks are used by the load balancer to determine whether application instances are ready to receive traffic.

---

## Deleted Advisor Listener

### Screenshot Path

`screenshots/13_step5_deleted_listener_plan_1_add.png`

### Screenshot

![Deleted Advisor listener detected](screenshots/13_step5_deleted_listener_plan_1_add.png)

### Explanation

The Advisor listener was manually deleted from AWS.

Terraform detected that a declared resource was completely missing.

The plan showed:

```text
Plan: 1 to add, 0 to change, 0 to destroy.
```

Terraform then recreated the listener.

---

# Step 6 — IAM Least Privilege

### Screenshot Path

`screenshots/14_step6_iam_policy_simulator.png`

### Screenshot

![IAM least privilege simulator](screenshots/14_step6_iam_policy_simulator.png)

### Explanation

The IAM Policy Simulator was used to verify permissions for the Weather and Advisor roles.

| Role | Action | Result |
|---|---|---|
| Weather | `dynamodb:PutItem` | Allowed |
| Weather | `ssm:GetParameter` | Implicit Deny |
| Advisor | `ssm:GetParameter` | Allowed |
| Advisor | `dynamodb:GetItem` | Implicit Deny |

This demonstrates the principle of least privilege.

The Weather service needs DynamoDB access but does not need the Gemini secret.

The Advisor service needs the Gemini secret but does not need direct access to the Weather DynamoDB table.

---

# Step 7 — Terraform State and External Secrets

### Screenshot Path

`screenshots/15_step7_no_changes_and_state_key_check.png`

### Screenshot

![Terraform state and API key check](screenshots/15_step7_no_changes_and_state_key_check.png)

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

This tells Terraform not to treat external changes to the parameter value as infrastructure drift.

Terraform state should still be protected because providers may store resource values in state.

---

# Step 8 — Gemini Failure and Graceful Fallback

## Fallback Responses

### Screenshot Path

`screenshots/16_step8_fallback_responses.png`

### Screenshot

![Gemini fallback responses](screenshots/16_step8_fallback_responses.png)

### Explanation

The valid Gemini API key was temporarily replaced with:

```text
not-a-real-key
```

After the application cache expired, the Advisor was tested twice.

Both requests returned fallback advice instead of failing completely.

This demonstrates graceful degradation.

---

## Gemini Error Logs

### Screenshot Path

`screenshots/17_step8_gemini_error_logs.png`

### Screenshot

![Gemini error journal logs](screenshots/17_step8_gemini_error_logs.png)

### Explanation

The Advisor journal contained:

```text
"event":"gemini_error"
"status":400
"reason":"gemini_http_error"
```

This proves that Gemini was failing while the application continued serving fallback recommendations.

---

## Gemini Restored

### Screenshot Path

`screenshots/18_step8_gemini_restored.png`

### Screenshot

![Gemini restored successfully](screenshots/18_step8_gemini_restored.png)

### Explanation

After restoring the valid Gemini API key, the Advisor returned to:

```text
gemini - ...
```

This confirmed that normal Gemini functionality was restored.

---

## Advisor Webpage Verification

### Screenshot Path

`screenshots/19_advisor_webpage_gemini.png`

### Screenshot

![Weather Advisor webpage using Gemini](screenshots/19_advisor_webpage_gemini.png)

### Explanation

The final Advisor webpage was tested using ZIP code:

```text
60616
```

The page displayed Chicago weather information and generated a clothing recommendation.

It showed:

```text
Suggestion source: gemini
```

This confirms the complete application flow through the web interface.

---

# Step 9 — EC2 vs Lambda Architecture

The current architecture uses EC2 instances behind an Application Load Balancer.

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

## What Would Become Easier?

Moving from EC2 to Lambda would reduce:

- operating-system management
- launch templates
- Auto Scaling Groups
- systemd services
- EC2 bootstrapping
- instance refreshes
- server patching
- server lifecycle management

AWS Lambda automatically scales functions based on demand.

API Gateway could replace much of the ALB listener and target-group configuration.

## What Would Still Be Required?

The following would still need management:

- IAM permissions
- DynamoDB
- SSM Parameter Store
- Gemini integration
- external API failure handling
- application logic
- logging
- monitoring
- security

Lambda reduces infrastructure administration but does not eliminate application complexity.

---

# Step 10 — Terraform Destroy and Cleanup

## Final Terraform Status and Version

### Screenshot Path

`screenshots/20_final_no_changes_terraform_version_sts.png`

### Screenshot

![Final Terraform version, no changes and masked STS identity](screenshots/20_final_no_changes_terraform_version_sts.png)

### Explanation

Before destruction, Terraform reported that no infrastructure changes were required.

The environment showed:

```text
Terraform v1.17.2
AWS Provider v5.100.0
```

The AWS account identifier was masked.

---

## Destroy Plan

### Screenshot Path

`screenshots/21_step10_destroy_plan_25_resources.png`

### Screenshot

![Terraform destroy plan for 25 resources](screenshots/21_step10_destroy_plan_25_resources.png)

### Explanation

Terraform produced:

```text
Plan: 0 to add, 0 to change, 25 to destroy.
```

The destroy plan allowed the infrastructure deletion to be reviewed before execution.

---

## Destroy Complete

### Screenshot Path

`screenshots/22_step10_destroy_complete_25.png`

### Screenshot

![Terraform destroy complete](screenshots/22_step10_destroy_complete_25.png)

### Explanation

Terraform reported:

```text
Destroy complete! Resources: 25 destroyed.
```

This confirms that all Terraform-managed resources were successfully removed.

---

## Cleanup Verification

### Screenshot Path

`screenshots/23_step10_cleanup_verification.png`

### Screenshot

![Terraform and temporary access cleanup verification](screenshots/23_step10_cleanup_verification.png)

### Explanation

The SSM Gemini parameter returned:

```text
ParameterNotFound
```

The command:

```bash
terraform state list
```

returned no resources.

The temporary Lab07 IAM policies and temporary SSH key files were also removed.

---

## Final AWS Resource Verification

### Screenshot Path

`screenshots/24_step10_final_aws_resource_checks.png`

### Screenshot

![Final AWS Lab07 resource verification](screenshots/24_step10_final_aws_resource_checks.png)

### Explanation

Final AWS checks were performed for:

- EC2
- Load Balancers
- Target Groups
- Auto Scaling Groups
- Launch Templates
- DynamoDB
- SSM
- Security Groups
- IAM roles

No active Lab07 resources remained.

---

# Review Questions

## 1. Why is Terraform declarative?

Terraform is declarative because the configuration describes the desired final infrastructure rather than every API operation needed to create it.

## 2. What is Terraform state?

Terraform state maps Terraform resources to real infrastructure and allows Terraform to determine whether resources need creation, updates, replacement, or destruction.

## 3. What is idempotence?

Idempotence means repeatedly applying the same configuration eventually results in:

```text
No changes.
```

## 4. How does Terraform determine dependencies?

Terraform detects dependencies through references between resources, such as:

```text
aws_lb.main.dns_name
```

## 5. What is configuration drift?

Configuration drift occurs when infrastructure is modified outside Terraform and no longer matches the desired Terraform configuration.

## 6. Why use `terraform plan`?

`terraform plan` allows infrastructure changes to be reviewed before applying them.

## 7. Why protect Terraform state?

Terraform state can contain sensitive resource information and potentially secret values, so it should not be committed publicly.

## 8. Why use `ignore_changes`?

`ignore_changes` lets selected resource attributes be changed externally without Terraform attempting to restore their original values.

## 9. How was Terraform different from Python?

Terraform provides built-in state management, dependency resolution, idempotence, drift detection, and destruction planning that would otherwise require custom code.

## 10. What does Terraform not solve?

Terraform manages infrastructure but does not replace application monitoring.

Application-level failures such as:

```text
gemini_error
```

still require application logs and observability.

---

# Cost and Cleanup

The AWS infrastructure was active only during the lab.

Potentially billable resources included:

- EC2
- Application Load Balancer
- DynamoDB usage

At the end of the lab:

```text
Destroy complete! Resources: 25 destroyed.
```

Final AWS checks confirmed that no Lab07 infrastructure remained active.

---

# Final Result

The Terraform Weather Advisor lab was successfully completed.

The lab demonstrated:

- Terraform deployment
- state management
- idempotence
- dependency management
- targeted configuration changes
- Auto Scaling refresh
- configuration drift detection
- drift repair
- IAM least privilege
- secret management
- graceful Gemini fallback
- application logging
- infrastructure destruction
- final AWS cleanup verification

The complete Weather Advisor infrastructure was successfully created, tested, modified, repaired, and destroyed using Terraform.
