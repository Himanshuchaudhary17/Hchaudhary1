# Weather Advisor Final Project Reflection

## Project Overview

The Weather Advisor project was developed as a two-tier cloud application. The Weather Data tier collects and aggregates forecast information, while the Advisor tier creates user-facing travel, clothing, road-condition, and accessory advice. The design intentionally separates measured weather data from generative AI advice.

The project uses Amazon EC2, Auto Scaling Groups, an Application Load Balancer, DynamoDB, Amazon SNS, AWS Systems Manager Parameter Store, the National Weather Service APIs, Open-Meteo for selected fallback measurements, and Google Gemini for advisory text.

## What Worked Well

One of the strongest parts of the project was separating responsibilities between the Weather and Advisor services. The Weather service does not know the user's email address or clothing identity selection and does not call Gemini. The Advisor service consumes normalized weather facts and uses Gemini only to generate advice.

DynamoDB caching also improved both reliability and performance. Repeated report requests can reuse cached weather and advisory results rather than repeatedly calling external APIs. The application includes stale-cache behavior so recent data can still be returned when a weather source is temporarily unavailable.

The final deployed application also met the performance SLO test. Using a persistent connection through the public Application Load Balancer, the Advisor `/health` endpoint achieved an average response latency below the 120 ms target during the recorded test.

## Challenges

The largest infrastructure challenge was EC2 user-data size. Embedding the application directly in launch-template user data exceeded the EC2 raw user-data limit. I redesigned the bootstrap process to package the application, `package.json`, and systemd service into a compressed archive and decode it during instance startup. This reduced the user-data size enough to deploy successfully.

Another issue occurred during launch-template updates. Updating an Auto Scaling Group does not automatically replace an existing instance immediately. I used instance replacement and Auto Scaling health checks to verify that the updated application version was actually running.

A further challenge was correctly classifying rain and snow. The National Weather Service grid data can associate a precipitation amount with a multi-hour `validTime`. Treating that complete value as if it were a one-hour amount could produce an incorrect category. The final Weather service normalizes precipitation values by their valid-time duration before applying deterministic Rain and Snow thresholds.

## Reliability Testing

The project included both normal integration testing and failure testing.

During the chaos test, the running Weather EC2 instance was intentionally terminated. The Auto Scaling Group detected the missing instance, launched a replacement, and the replacement eventually returned to a healthy target state behind the load balancer. The measured recovery time was approximately 202 seconds.

The application also includes rule-based advice fallback when Gemini cannot provide acceptable output, and recent cached weather can be used when live weather data is temporarily unavailable.

## Security Lessons

The project reinforced the importance of least privilege. The Weather and Advisor EC2 roles use separate IAM policies and access only the AWS resources required by their tiers. The Gemini API key is stored as an encrypted SSM SecureString rather than being placed in source code.

The user's email address is not sent to Gemini and is not included in application logs. SNS email delivery uses recipient-specific filtering and rate limiting.

The project also reinforced that security should be tested rather than assumed. IAM policy tests check that the deployed application policies do not use wildcard resources or wildcard actions.

## Testing Lessons

The final test strategy includes Python infrastructure tests, deployed integration tests, Node application-logic tests, performance testing, and chaos recovery testing.

Boundary tests were especially useful for Rain and Snow classification because they demonstrate deterministic behavior immediately below, at, and above the configured thresholds.

The SLI exercise also showed the importance of clearly defining what a latency measurement represents. Opening a brand-new TCP connection for every sample adds client-to-AWS connection overhead. The final SLI measures repeated application requests over an established HTTP connection while still using the public Application Load Balancer.

## Cost Lessons

The final architecture was kept deliberately small. Two `t3.micro` instances, one Application Load Balancer, DynamoDB on-demand tables, SNS, and a small amount of storage are sufficient for the classroom workload.

The estimated cost is approximately $0.049 per running hour, which is below the project target of $0.07 per hour. The infrastructure should still be deleted when not needed because leaving the complete stack running continuously for several days would exceed the total project budget.

## What I Would Improve

With more time, I would add HTTPS using AWS Certificate Manager and a domain name, add stronger observability through CloudWatch dashboards and alarms, and automate deployment verification after every launch-template update.

For a production deployment, I would also use a more formal continuous delivery pipeline and collect longer-running SLI data instead of relying mainly on presentation-time measurements.

Overall, this project demonstrated how application architecture, cloud infrastructure, security, reliability, testing, performance, and cost management have to work together rather than being treated as separate concerns.
