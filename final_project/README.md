# ITMO 544 Final Project — AWS Weather Advisor

A two-tier cloud application deployed on AWS that combines live weather data, DynamoDB caching, Google Gemini-generated recommendations, deterministic fallback logic, and Amazon SNS email delivery.

## Project Overview

The Weather Advisor is composed of two independent Node.js services:

- **Advisor Service** — public user-facing application that validates input, rate-limits requests, calls the Weather service, generates recommendations with Google Gemini or a rule-based fallback, stores temporary state in DynamoDB, and delivers reports through Amazon SNS.
- **Weather Service** — retrieves and aggregates weather information from external APIs, builds Morning and Night weather summaries, and caches results in DynamoDB.

Both services run on Amazon EC2 instances managed by separate Auto Scaling Groups and are exposed through a single internet-facing Application Load Balancer.

## Architecture

```text
User
  |
  v
Application Load Balancer
  |
  +-- Port 8080 --> Advisor Target Group --> Advisor EC2
  |                                      |
  |                                      +--> Advisor DynamoDB
  |                                      +--> SSM Parameter Store
  |                                      +--> Google Gemini
  |                                      +--> Amazon SNS
  |
  +-- Port 8081 --> Weather Target Group --> Weather EC2
                                         |
                                         +--> Weather DynamoDB
                                         +--> Zippopotam.us
                                         +--> National Weather Service
                                         +--> Open-Meteo
```

The Node.js applications listen internally on `APP_PORT=3000`. The public ALB listeners use port `8080` for Advisor and `8081` for Weather.

## AWS Services Used

- Amazon EC2
- EC2 Launch Templates
- EC2 Auto Scaling Groups
- Application Load Balancer
- Target Groups and health checks
- IAM roles and instance profiles
- Amazon DynamoDB
- AWS Systems Manager Parameter Store
- Amazon SNS

## Repository Structure

```text
final_project/
├── advisor-app/
│   ├── app.js
│   └── package.json
├── weather-app/
│   ├── app.js
│   └── package.json
├── stack/
│   ├── balancer.py
│   ├── clients.py
│   ├── compute.py
│   ├── config.py
│   ├── dynamodb.py
│   ├── messaging.py
│   ├── network.py
│   ├── outputs.py
│   ├── policies.py
│   ├── runner.py
│   ├── scaling.py
│   └── storage.py
├── tests/
│   ├── unit/
│   └── integration/
├── testing/
│   └── app_smoke_test.py
├── screenshots/
├── create_weather_stack.py
├── delete_weather_stack.py
├── budget.py
├── requirements.txt
├── pytest.ini
├── .gitignore
└── README.md
```

## Request Flow

### Advisor

When a user generates a report, the Advisor service:

1. Receives ZIP code, date, clothing category, and email.
2. Validates the input.
3. Creates a visitor identifier and applies request rate limiting.
4. Calls the Weather service.
5. Checks the Advisor report cache.
6. Generates Morning and Night recommendations.
7. Uses Google Gemini when allowed and available.
8. Falls back to deterministic rule-based advice when Gemini cannot be used.
9. Stores temporary email state in DynamoDB.
10. Returns the completed report to the browser.

### Weather

The Weather service:

1. Receives a ZIP code and date.
2. Validates the request.
3. Checks the DynamoDB weather cache.
4. Uses Zippopotam.us to resolve the ZIP code to location and coordinates.
5. Uses the National Weather Service as the primary weather source.
6. Uses Open-Meteo for supplemental values such as visibility and UV.
7. Builds separate Morning and Night weather facts.
8. Stores the result in DynamoDB.
9. Returns the weather JSON to Advisor.

## Caching and Resilience

The Weather tier uses DynamoDB keys in the form:

```text
WEATHER#<ZIP>#<DATE>
```

Default cache behavior:

- Fresh cache: approximately 600 seconds
- Stale-cache fallback window: approximately 21,600 seconds

If a live weather provider fails and a usable stale entry exists, the Weather service can return the recent cached forecast with a warning.

The Advisor tier uses temporary DynamoDB state such as:

```text
RATE#...
GEMINI#YYYY-MM-DD
REPORTCACHE#...
EMAILRATE#...
REPORT#<UUID>
```

These support request-rate limiting, Gemini usage control, report caching, email-rate limiting, and temporary email report storage.

## Gemini Integration

The Advisor service uses Google Gemini to generate:

- `road_conditions`
- `dressing`
- `accessories`

The Gemini API key is stored in AWS Systems Manager Parameter Store as a `SecureString` rather than being hard-coded in source code.

The Advisor validates the Gemini response before accepting it. If Gemini is unavailable, the daily usage limit is reached, or the response is invalid, the application returns deterministic rule-based fallback advice.

This makes the application **AI-enhanced, not AI-dependent**.

## SNS Email Workflow

A generated report is temporarily stored in the Advisor DynamoDB table using a `REPORT#UUID` key.

The email workflow:

1. Generates the report once.
2. Saves the completed report temporarily.
3. User selects **Email This Report**.
4. Amazon SNS creates/checks the email subscription.
5. SNS sends a confirmation request when required.
6. User confirms the subscription.
7. Advisor publishes the already-generated report through SNS.

The report is reused instead of being regenerated, which avoids unnecessary Weather and Gemini calls.

## IAM and Security

The project uses separate IAM roles for the two tiers.

### Weather Role

Limited to the permissions required to read and write the Weather DynamoDB cache.

### Advisor Role

Limited to the required:

- DynamoDB operations for Advisor state
- `ssm:GetParameter` for the Gemini secret
- SNS subscription and publish operations

IAM roles are attached to EC2 through instance profiles referenced by the Launch Templates.

The application uses Security Groups to control network access, with the ALB acting as the public entry point.

## EC2 Bootstrap and Self-Healing

Launch Templates define how each EC2 instance is created, including:

- AMI
- instance type
- key pair
- Security Group
- IAM instance profile
- user-data

The user-data bootstrap installs Node.js, deploys the application under `/opt/app`, installs dependencies, and starts the application through `systemd`.

Recovery occurs at two levels:

```text
Node.js process failure
--> systemd restarts the application

EC2 instance failure
--> Auto Scaling Group launches a replacement instance
```

The ALB routes traffic only to healthy targets.

## Auto Scaling

The project currently uses separate Advisor and Weather Auto Scaling Groups with:

```text
MinSize = 1
DesiredCapacity = 1
MaxSize = 1
```

The primary purpose of the current configuration is self-healing. Capacity can be increased in `stack/scaling.py`.

## Configuration

Infrastructure and application settings are loaded from `.env` by `stack/config.py`.

Important settings include:

```text
AWS_REGION
AMI_ID
KEY_NAME
INSTANCE_TYPE
APP_SECURITY_GROUP_ID
AZ_A
AZ_B
APP_PORT
WEATHER_LISTENER_PORT
ADVISOR_LISTENER_PORT
WEATHER_TABLE_NAME
ADVISOR_TABLE_NAME
SNS_TOPIC_NAME
GEMINI_PARAM_NAME
GEMINI_MODEL
CACHE_SECONDS
STALE_CACHE_SECONDS
GEMINI_DAILY_LIMIT
VISITOR_REQUEST_LIMIT
EMAIL_REQUEST_LIMIT
REPORT_CACHE_SECONDS
```

Do not commit a real `.env` file or API key to GitHub.

## Deployment

Install Python dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Configure AWS credentials and create the required `.env` file.

Create the stack:

```bash
python3 create_weather_stack.py
```

The script creates or configures the project's AWS resources and saves stack output information locally.

## Testing

The project contains multiple levels of testing.

### Python Unit Tests

Unit tests validate configuration, IAM policy generation, DynamoDB helpers, stack behavior, Launch Template data, and EC2 user-data generation.

Final recorded result:

```text
32 passed in 1.71s
```

Evidence: `screenshots/19_unit_tests_passed.png`

### Weather Node.js Tests

The Weather service has Node.js tests for rain/snow classification boundaries, duration parsing, and precipitation normalization.

Final recorded result:

```text
12 passed
0 failed
```

Evidence: `screenshots/24_rain_snow_boundary_tests_passed.png`

### Deployed Integration Tests

Integration tests validate the live AWS deployment, including target-group health, ALB listeners, Auto Scaling Groups, instance configuration, DynamoDB, SSM, SNS, IAM restrictions, application behavior, and caching.

Final recorded result:

```text
16 passed in 3.19s
```

Evidence: `screenshots/25_version3_live_integration_passed.png`

### SLI / SLO

The Advisor `/health` endpoint is measured through the public Application Load Balancer using 20 samples after a warm-up request.

Final measured values:

```text
Minimum: 21.34 ms
Median:  27.93 ms
Average: 32.06 ms
P95:     36.08 ms
Maximum: 116.12 ms

SLO target: 120.00 ms average
SLO RESULT: PASS
```

Evidence: `screenshots/26_sli_120ms_passed.png`

### Chaos / Self-Healing Recovery

A Weather EC2 failure was tested by allowing the Auto Scaling Group to replace the instance and waiting for the replacement target to become healthy.

Recorded recovery:

```text
Recovery time: 202 seconds
Weather health after recovery: OK
```

Evidence: `screenshots/21_chaos_recovery_passed.png`

### Cost Budget

The included budget estimator was run for 24 hours.

Recorded estimate:

```text
Estimated hourly total: $0.0489/hour
Estimated 24-hour project cost: $1.17
Hourly target (< $0.07): PASS
Project target (< $2.00): PASS
```

Evidence: `screenshots/27_cost_budget_passed.png`

## Screenshots / Evidence

> **Note:** Some screenshots contain AWS resource identifiers, account identifiers, live endpoint names, or personal email addresses. Remove or redact those details before publishing the repository publicly if you do not want them exposed.

The `screenshots/` folder contains the complete final project evidence set.

### Application and Report Flow

**Deployed Weather Advisor input form**

![Deployed Weather Advisor input form](screenshots/01_weather_advisor_form.png)

**Generated report — top section**

![Generated report — top section](screenshots/02_weather_report_top.png)

**Generated report — full view**

![Generated report — full view](screenshots/03_weather_report_full.png)

**Deployed report through the ALB**

![Deployed report through the ALB](screenshots/17_deployed_weather_report.png)

**Final deployed report with Gemini advice**

![Final deployed report with Gemini advice](screenshots/18_deployed_weather_report_full.png)

### Caching, Validation, Fallback, and Email

**Advisor report cache hit and response-time improvement**

![Advisor report cache hit and response-time improvement](screenshots/04_report_cache_performance.png)

**SNS subscription confirmation required**

![SNS subscription confirmation required](screenshots/05_sns_confirmation_required.png)

**Amazon SNS confirmation email**

![Amazon SNS confirmation email](screenshots/06_sns_confirmation_email.png)

**Report accepted by SNS for delivery**

![Report accepted by SNS for delivery](screenshots/07_report_submitted_for_delivery.png)

**Delivered Weather Advisor email report**

![Delivered Weather Advisor email report](screenshots/08_received_weather_email.png)

**Email request rate-limit behavior**

![Email request rate-limit behavior](screenshots/09_email_rate_limit.png)

**Browser-side ZIP validation**

![Browser-side ZIP validation](screenshots/10_invalid_zip_browser_validation.png)

**Server-side ZIP-not-found validation**

![Server-side ZIP-not-found validation](screenshots/11_zip_not_found_server_validation.png)

**Rule-based fallback output**

![Rule-based fallback output](screenshots/12_gemini_fallback.png)

**Fallback test input**

![Fallback test input](screenshots/13_gemini_fallback_input.png)

### Infrastructure and Health

**EC2 instance and system status checks**

![EC2 instance and system status checks](screenshots/14_ec2_status_checks_ok.png)

**Healthy ALB target groups and Weather health**

![Healthy ALB target groups and Weather health](screenshots/15_alb_targets_and_weather_health.png)

**Deployed Advisor and Weather health endpoints**

![Deployed Advisor and Weather health endpoints](screenshots/16_deployed_health_endpoints.png)

**Auto Scaling self-healing after instance failure**

![Auto Scaling self-healing after instance failure](screenshots/21_chaos_recovery_passed.png)

**Application healthy after chaos recovery**

![Application healthy after chaos recovery](screenshots/22_application_after_chaos.png)

**Advisor health endpoint in browser**

![Advisor health endpoint in browser](screenshots/23_advisor_health_browser.png)

**ALB listeners: 8080 Advisor and 8081 Weather**

![ALB listeners: 8080 Advisor and 8081 Weather](screenshots/28_alb_listeners.png)

**Advisor Auto Scaling Group**

![Advisor Auto Scaling Group](screenshots/29_advisor_asg.png)

**Weather Auto Scaling Group**

![Weather Auto Scaling Group](screenshots/30_weather_asg.png)

**Weather Launch Template**

![Weather Launch Template](screenshots/31_weather_launch_template.png)

**Advisor Launch Template**

![Advisor Launch Template](screenshots/32_advisor_launch_template.png)

**Weather and Advisor DynamoDB tables**

![Weather and Advisor DynamoDB tables](screenshots/33_dynamodb_tables.png)

**Advisor runtime state in DynamoDB**

![Advisor runtime state in DynamoDB](screenshots/34_dynamodb_advisor_runtime_state.png)

**Advisor IAM role and instance profile**

![Advisor IAM role and instance profile](screenshots/35_advisor_iam_role.png)

**Weather IAM role and instance profile**

![Weather IAM role and instance profile](screenshots/36_weather_iam_role.png)

**Gemini API key stored as SSM SecureString**

![Gemini API key stored as SSM SecureString](screenshots/37_ssm_gemini_securestring.png)

### Testing and Cost Evidence

**Source map and data-provider documentation**

![Source map and data-provider documentation](screenshots/00_source_map_documentation.png)

**32 Python unit tests passed**

![32 Python unit tests passed](screenshots/19_unit_tests_passed.png)

**Initial deployed integration test pass**

![Initial deployed integration test pass](screenshots/20_integration_tests_passed_initial.png)

**12 Weather Node.js tests passed**

![12 Weather Node.js tests passed](screenshots/24_rain_snow_boundary_tests_passed.png)

**Final live integration tests: 16 passed**

![Final live integration tests: 16 passed](screenshots/25_version3_live_integration_passed.png)

**SLI/SLO latency test passed**

![SLI/SLO latency test passed](screenshots/26_sli_120ms_passed.png)

**Cost budget estimate passed**

![Cost budget estimate passed](screenshots/27_cost_budget_passed.png)


## Teardown

Delete the deployed AWS project resources with:

```bash
python3 delete_weather_stack.py
```

The teardown logic removes resources in dependency-aware order, including Auto Scaling Groups, the load balancer, target groups, Launch Templates, IAM resources, SNS, DynamoDB tables, the Gemini SSM parameter, and generated local stack outputs.

## Key Design Decisions

- Two independent application tiers
- Single public ALB with separate listeners
- Separate IAM roles following least privilege
- DynamoDB caching and temporary state
- Secure Gemini key storage through SSM
- Gemini output validation
- Deterministic fallback when AI is unavailable
- SNS confirmation-based email delivery
- systemd process recovery
- ASG instance-level self-healing
- Automated deployment and teardown
- Unit, integration, smoke, and latency testing

## Course

**ITMO 544 — Cloud Computing Technologies**

Final Project: **AWS Weather Advisor**
