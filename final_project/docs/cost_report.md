# Weather Advisor Cost Report

## Cost Objective

The final project was designed to remain below approximately $0.07 per hour while the complete AWS stack is running and below approximately $2.00 for the project testing and demonstration period.

## Deployed Architecture

The cost estimate includes:

- Two Amazon EC2 `t3.micro` Linux instances:
  - Weather Data tier
  - Advisor tier
- One Application Load Balancer with two listeners
- Two small EC2 root EBS volumes
- Two DynamoDB on-demand tables
- One Amazon SNS topic
- One encrypted SSM Parameter Store parameter
- Small amounts of logging and network traffic

Auto Scaling Groups maintain one desired instance for each application tier. Auto Scaling itself does not add a separate hourly instance-management charge.

## Estimated Hourly Cost

| Component | Estimated hourly cost |
|---|---:|
| 2 × EC2 t3.micro | $0.0208 |
| Application Load Balancer base | $0.0225 |
| Low-traffic ALB LCU allowance | $0.0008 |
| Two small gp3 EBS volumes | ~$0.0018 |
| DynamoDB, SNS, logs, and small data-transfer allowance | ~$0.0030 |
| **Estimated total** | **~$0.0489/hour** |

The estimate is intentionally conservative for a small classroom demonstration workload. DynamoDB and SNS use consumption-based pricing, so their actual cost depends on the number of requests and messages.

## Budget Evaluation

Estimated hourly stack cost:

**~$0.049/hour**

Assignment hourly target:

**< $0.07/hour**

Result:

**PASS**

At the estimated hourly rate, a 24-hour accumulated runtime costs approximately:

**$1.17**

The stack can run for approximately 40 hours before reaching $2.00 under this estimate. Therefore, the infrastructure should not remain deployed continuously for the full week before the presentation.

## Cost Controls

The project reduces unnecessary cost by:

1. Maintaining only one EC2 instance per application tier.
2. Using `t3.micro` instances.
3. Using DynamoDB on-demand rather than provisioned capacity.
4. Caching Weather and Advisor reports to reduce repeated external calls.
5. Using TTL on DynamoDB temporary records.
6. Using a single Application Load Balancer for both tiers.
7. Deleting the AWS stack when testing or demonstration is complete.
8. Avoiding an RDS database, NAT Gateway, and other higher-cost infrastructure that the final design does not require.

## Pricing Assumptions

This document is a planning estimate rather than an AWS billing statement. Actual charges can differ because of region, data transfer, ALB LCU consumption, CPU-credit usage, storage size, and AWS account credits.

Reference pricing was taken from AWS public EC2, Elastic Load Balancing, and DynamoDB pricing documentation.
