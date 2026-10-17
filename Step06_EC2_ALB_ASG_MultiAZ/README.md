# Step 06 - Multi-AZ Resilience with ALB and Auto Scaling Groups

## Recovery-Time Analysis

In the recovery test, the uploader recovered in 77.0 seconds with a 180-second SLO, so the test passed. When I tightened the SLO to 60 seconds, the second recovery took 77.8 seconds and failed the SLO. The recovery window was mainly affected by the time required for the Auto Scaling Group to launch a replacement EC2 instance, complete the instance boot process, install and start the application, and then pass the target group's health checks before the Application Load Balancer could send traffic to it again. The target group was configured with faster 10-second health checks and a threshold of two successful checks, so the instance startup and application initialization were a significant part of the total recovery time.

## Changes from the Previous Lab

In the previous lab, create_app_stack.sh launched the uploader and viewer EC2 instances directly using aws ec2 run-instances with the existing Launch Templates. In this lab, those direct instance-launch commands were replaced by two Auto Scaling Groups. Each Auto Scaling Group references the existing Launch Template, maintains a desired capacity of one instance, and registers its instance with a target group behind the Application Load Balancer. The updated delete_app_stack.sh also deletes the Auto Scaling Groups, Application Load Balancer, target groups, and ALB security group before cleaning up the existing launch templates, IAM resources, and S3 bucket. This allows the architecture to recover automatically when an instance is terminated instead of requiring a manual replacement.

## Recovery Test Results

- Normal SLO test: 77.0 seconds / 180-second SLO — PASS
- Tightened SLO test: 77.8 seconds / 60-second SLO — FAIL
