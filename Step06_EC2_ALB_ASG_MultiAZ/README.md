# Step 06 - Multi-AZ Resilience with ALB and Auto Scaling Groups

## Overview

This lab extends the previous EC2 and S3 two-tier application by adding an **Application Load Balancer (ALB)**, **Target Groups**, **Auto Scaling Groups (ASGs)**, a **Multi-AZ deployment**, and **recovery-time testing**.

The goal was to improve application resilience. In the previous lab, EC2 instances were launched directly. In this lab, the Auto Scaling Groups maintain the required number of EC2 instances and automatically launch a replacement if an instance is terminated.

The Application Load Balancer provides stable endpoints for the uploader and viewer applications and sends traffic only to healthy EC2 instances.

---

## Architecture

The application contains two tiers:

- Uploader application
- Viewer application

Both applications use Amazon S3 as shared storage.

```text
                         Internet
                            |
                 Application Load Balancer
                            |
              +-------------+-------------+
              |                           |
         Port 8080                     Port 8081
              |                           |
       Uploader Target Group       Viewer Target Group
              |                           |
       Uploader Auto Scaling       Viewer Auto Scaling
              Group                       Group
              |                           |
        EC2 Uploader Instance       EC2 Viewer Instance
              |                           |
              +------------+--------------+
                           |
                        Amazon S3
```

---

## AWS Components Used

### Application Load Balancer

The Application Load Balancer provides a public DNS name for the applications. Instead of connecting directly to an EC2 public IP address, users access the uploader and viewer through the ALB.

The listener ports used were:

- `8080` for the uploader
- `8081` for the viewer

The ALB forwards each request to the correct Target Group.

### Target Groups

Two Target Groups were created:

- `itmo-444-544-uploader-tg`
- `itmo-444-544-viewer-tg`

Both applications run internally on port `3000`.

The Target Groups perform health checks so the ALB can route traffic only to healthy application instances.

### Auto Scaling Groups

Two Auto Scaling Groups were created:

- `itmo-444-544-uploader-asg`
- `itmo-444-544-viewer-asg`

Each Auto Scaling Group uses an existing Launch Template and maintains:

- Minimum capacity: `1`
- Desired capacity: `1`
- Maximum capacity: `1`

If an instance is terminated, the Auto Scaling Group automatically launches a replacement to restore the desired capacity.

### Multi-AZ Deployment

The deployment used two Availability Zones:

- `us-east-2a`
- `us-east-2b`

Using more than one Availability Zone improves availability and makes the infrastructure more resilient.

---

## 1. Stack Creation

The updated `create_app_stack.sh` script creates the ALB security group, Target Groups, Application Load Balancer, listeners, and Auto Scaling Groups.

It also stores runtime information in `stack_outputs.env` and prints the ALB DNS name together with the uploader and viewer URLs.

![Create Stack and ALB URLs](01_create_stack_alb_urls.png)

---

## 2. Target Group Health

After deployment, I checked the health of both Target Groups.

Both the uploader and viewer targets showed:

```text
State: healthy
```

![Healthy Target Groups](02_target_groups_healthy.png)

This confirmed that both applications were ready to receive traffic through the ALB.

---

## 3. Uploader Test

I opened the uploader application through the ALB on port `8080` and uploaded a text file.

The application returned:

```text
Upload successful.
```

![Uploader Success](03_uploader_success.png)

This confirmed that the uploader application was working correctly through the Application Load Balancer.

---

## 4. Viewer Test

I opened the viewer application through the ALB on port `8081`.

The viewer successfully displayed the content stored in Amazon S3.

![Viewer Content](04_viewer_content.png)

This confirmed that both applications continued to work correctly after adding the ALB and Auto Scaling architecture.

---

## Recovery-Time SLO

A **Recovery-Time SLO** defines the maximum acceptable amount of time the application should take to recover after a failure.

The first recovery test used an SLO of:

```text
180 seconds
```

The chaos test terminated the active uploader EC2 instance and measured how long it took for the application to become available again.

---

## Chaos Testing

The recovery-testing files are stored in the `testing` directory:

```text
testing/
├── requirements.txt
├── http_probe.py
├── aws_helpers.py
├── chaos_test.py
├── chaos_test_uploader_1976.csv
└── chaos_test_uploader_2301.csv
```

### `http_probe.py`

This script checks whether the ALB endpoint is responding. It is used to detect when the application goes down and when it becomes available again.

### `aws_helpers.py`

This script finds the currently running instance in the Auto Scaling Group and terminates it without reducing the desired capacity.

Because the desired capacity remains `1`, the Auto Scaling Group must launch a replacement instance.

### `chaos_test.py`

This script performs the complete recovery experiment:

1. Confirms the endpoint is healthy.
2. Finds the running EC2 instance.
3. Terminates the instance through the Auto Scaling Group.
4. Waits for the endpoint to become unavailable.
5. Continues polling the endpoint.
6. Waits for a replacement instance to launch.
7. Detects when the application becomes available again.
8. Calculates the recovery time.
9. Compares the recovery time with the configured SLO.
10. Writes the polling results to a CSV file.
11. Reports PASS or FAIL.

---

## 5. Recovery Test - PASS

The first chaos test used a recovery SLO of:

```text
180 seconds
```

The measured recovery time was:

```text
77.0 seconds
```

Result: **PASS**

![Chaos Test Pass](05_chaos_test_pass.png)

The CSV log for this test is:

```text
testing/chaos_test_uploader_1976.csv
```

The application recovered well within the 180-second SLO.

---

## 6. Recovery Test - FAIL

For the second test, I intentionally tightened the SLO to:

```text
60 seconds
```

The measured recovery time was:

```text
77.8 seconds
```

Result: **FAIL**

![Chaos Test Fail](06_chaos_test_fail.png)

The CSV log for this test is:

```text
testing/chaos_test_uploader_2301.csv
```

The infrastructure still recovered successfully, but the recovery time exceeded the stricter 60-second SLO.

---

## Recovery-Time Analysis

During the first recovery test, the uploader recovered in **77.0 seconds** with a **180-second SLO**, so the test passed.

During the second recovery test, the uploader recovered in **77.8 seconds** with a **60-second SLO**, so the test failed.

The two measured recovery times were very similar. This shows that changing the SLO does not change how quickly the infrastructure actually recovers. The SLO only changes the threshold used to decide whether the recovery time is acceptable.

The recovery window was mainly affected by the time required for the Auto Scaling Group to launch a replacement EC2 instance, complete the boot process, start the application, register the new instance with the Target Group, and pass the health checks before the Application Load Balancer began routing traffic to it again.

The Target Group used a 10-second health-check interval with a healthy threshold of two successful checks. Therefore, part of the total recovery time came from health-check timing, while the remaining time came from EC2 startup and application initialization.

---

## Changes from the Previous Lab

In the previous lab, `create_app_stack.sh` launched the uploader and viewer EC2 instances directly using:

```bash
aws ec2 run-instances
```

In this lab, the direct `run-instances` approach was replaced by **Auto Scaling Groups**.

The Auto Scaling Groups use the existing Launch Templates and maintain a desired capacity of one instance. If an EC2 instance is terminated, the Auto Scaling Group automatically launches a replacement.

The Application Load Balancer also provides a stable DNS endpoint, so users do not need to connect directly to a specific EC2 public IP address.

The updated `delete_app_stack.sh` also removes the new infrastructure resources, including:

- Auto Scaling Groups
- Application Load Balancer
- Target Groups
- ALB security group

before cleaning up the remaining Launch Templates, IAM resources, and S3 resources.

---

## Why Auto Scaling Improves Resilience

Without Auto Scaling, a failed EC2 instance would need to be replaced manually.

With Auto Scaling, recovery is automatic:

```text
EC2 Instance Fails
        |
Auto Scaling Group detects missing capacity
        |
Replacement EC2 instance launches
        |
Application starts
        |
Target becomes healthy
        |
ALB begins routing traffic again
```

This reduces manual intervention and improves application availability.

---

## Recovery Test Summary

| Test | Recovery Time | SLO | Result |
|---|---:|---:|---|
| Normal SLO Test | 77.0 seconds | 180 seconds | PASS |
| Tight SLO Test | 77.8 seconds | 60 seconds | FAIL |

---

## 7. Cleanup

After completing the recovery tests, I ran:

```bash
./delete_app_stack.sh
```

The cleanup script removed:

- Auto Scaling Groups
- Application Load Balancer
- Target Groups
- ALB security group
- Launch Templates
- IAM resources
- S3 bucket and objects

The final output showed:

```text
Cleanup complete.
```

![Stack Cleanup](07_delete_stack_complete.png)

I also verified that both Auto Scaling Groups were fully deleted.

---

## Repository Structure

```text
Step06_EC2_ALB_ASG_MultiAZ/
├── README.md
├── .gitignore
├── create_app_stack.sh
├── delete_app_stack.sh
├── lab03/
│   ├── uploader-app/
│   │   ├── app.js
│   │   └── package.json
│   └── viewer-app/
│       ├── app.js
│       └── package.json
├── testing/
│   ├── requirements.txt
│   ├── http_probe.py
│   ├── aws_helpers.py
│   ├── chaos_test.py
│   ├── chaos_test_uploader_1976.csv
│   └── chaos_test_uploader_2301.csv
├── 01_create_stack_alb_urls.png
├── 02_target_groups_healthy.png
├── 03_uploader_success.png
├── 04_viewer_content.png
├── 05_chaos_test_pass.png
├── 06_chaos_test_fail.png
└── 07_delete_stack_complete.png
```

---

## Final Result

The lab successfully converted the previous direct EC2 deployment into a more resilient architecture using an Application Load Balancer, Target Groups, Auto Scaling Groups, Multi-AZ deployment, health checks, and recovery-time testing.

The uploader and viewer both worked successfully through the ALB.

The Auto Scaling Group automatically replaced the terminated uploader instance during the chaos tests.

The measured results were:

- **77.0 seconds** — PASS against the **180-second SLO**
- **77.8 seconds** — FAIL against the **60-second SLO**

All AWS resources created for the lab were cleaned up successfully.
