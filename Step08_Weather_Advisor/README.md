# Step08 — Weather Advisor in the Cloud

## ITMO 544 — Cloud Computing

This project implements a complete two-tier cloud application called **Weather Advisor** using Python, AWS, Node.js, PostgreSQL, external weather APIs, Google Gemini, `pytest`, and `moto`.

For the graduate ITMO 544 version of the lab, all AWS infrastructure resources are created and deleted using **Python and boto3** rather than Bash.

The project demonstrates:

- Python-based AWS infrastructure automation
- Two-tier cloud architecture
- Application Load Balancing
- Auto Scaling
- PostgreSQL on Amazon RDS
- AWS Systems Manager Parameter Store
- Least-privilege IAM
- External REST API integration
- Google Gemini integration
- PostgreSQL-backed caching
- Graceful degradation
- Unit testing with `pytest` and `moto`
- Real AWS integration testing
- Chaos testing
- Automatic EC2 replacement and recovery
- Secure network design
- Idempotent infrastructure creation
- Complete AWS resource cleanup

---

# 1. Project Overview

The application contains two main services:

1. **Weather Service**
2. **Advisor Service**

The Weather service accepts a U.S. ZIP code, finds the location, retrieves weather information from the National Weather Service API, stores lookup history and cached weather data in PostgreSQL, and returns the forecast.

The Advisor service calls the Weather service and uses Google Gemini to generate clothing recommendations based on the current weather.

Both services run on EC2 instances behind an AWS Application Load Balancer.

---

# 2. High-Level Architecture

```text
                             User
                              |
                              v
                 Application Load Balancer
                    /                 \
                   /                   \
          Listener 8080             Listener 8081
               |                         |
               v                         v
       Weather Target Group      Advisor Target Group
               |                         |
               v                         v
          Weather EC2               Advisor EC2
               |                         |
        +------+------+                  |
        |             |                  |
        v             v                  |
   Zippopotam      NWS API               |
        |                                |
        +-------> Weather Data            |
                    |                     |
                    v                     |
             PostgreSQL RDS              |
                    ^                     |
                    |                     |
                    +---------------------+
                                          |
                                          v
                                    Google Gemini
                                          |
                                          v
                              Clothing Recommendation
```

Public ALB listener ports:

```text
8080 -> Weather Tier
8081 -> Advisor Tier
```

Both applications listen internally on:

```text
Port 3000
```

PostgreSQL uses:

```text
Port 5432
```

---

# 3. Application Request Flow

A normal Advisor request follows this flow:

```text
User
 |
 v
Application Load Balancer :8081
 |
 v
Advisor Service
 |
 v
Application Load Balancer :8080
 |
 v
Weather Service
 |
 +--> PostgreSQL Cache
 |
 +--> Zippopotam API
 |
 +--> National Weather Service API
 |
 v
Weather Response
 |
 v
Advisor Service
 |
 v
Google Gemini
 |
 v
Clothing Recommendation
 |
 v
User
```

The Advisor service calls the Weather service through the Application Load Balancer instead of directly connecting to a Weather EC2 instance.

This keeps the services loosely coupled and allows Auto Scaling to replace Weather instances without changing the Advisor configuration.

---

# 4. Project Structure

```text
Step08_Weather_Advisor/
|
|-- advisor-app/
|   |-- app.js
|   `-- package.json
|
|-- weather-app/
|   |-- app.js
|   `-- package.json
|
|-- stack/
|   |-- __init__.py
|   |-- balancer.py
|   |-- clients.py
|   |-- compute.py
|   |-- config.py
|   |-- database.py
|   |-- network.py
|   |-- outputs.py
|   |-- policies.py
|   |-- runner.py
|   |-- scaling.py
|   |-- storage.py
|   `-- util.py
|
|-- tests/
|   |-- conftest.py
|   |-- helpers.py
|   |
|   |-- unit/
|   |   |-- test_config.py
|   |   |-- test_database_with_moto.py
|   |   |-- test_policies.py
|   |   |-- test_stack_with_moto.py
|   |   `-- test_user_data.py
|   |
|   `-- integration/
|       |-- test_application.py
|       |-- test_infrastructure.py
|       `-- test_recovery.py
|
|-- screenshots/
|   |-- 01_project_structure.png
|   |-- 02_nws_weather_api.png
|   |-- 03_gemini_ssm_securestring.png
|   |-- 04_database_created.png
|   |-- 05_database_verified.png
|   |-- 06_weather_stack_created.png
|   |-- 07_advisor_gemini_success.png
|   |-- 08_iam_least_privilege.png
|   |-- 09_weather_healthy_before_chaos.png
|   |-- 10_advisor_weather_outage_502.png
|   |-- 11_weather_recovered_after_outage.png
|   |-- 12_chaos_tests_passed.png
|   |-- 13_unit_and_integration_tests_passed.png
|   `-- 14_final_cleanup_verified.png
|
|-- create_database.py
|-- delete_database.py
|-- create_weather_stack.py
|-- delete_weather_stack.py
|-- pytest.ini
|-- requirements.txt
|-- README.md
|-- SUBMISSION_NOTES.md
`-- .gitignore
```

## Screenshot 01 — Project Structure

![Project Structure](screenshots/01_project_structure.png)

---

# 5. Python Infrastructure

The graduate ITMO 544 version of the lab requires Python-based infrastructure automation.

The main scripts are:

```text
create_database.py
delete_database.py
create_weather_stack.py
delete_weather_stack.py
```

All AWS resource creation and deletion is handled using boto3.

AWS CLI commands are used only to verify deployed or deleted resources.

---

# 6. Configuration

`stack/config.py` loads settings from `.env`.

Important settings include:

```text
AWS_REGION
AMI_ID
KEY_NAME
INSTANCE_TYPE
APP_SECURITY_GROUP_ID

AZ_A
AZ_B

WEATHER_ROLE_NAME
WEATHER_PROFILE_NAME
WEATHER_LT_NAME
WEATHER_TG_NAME
WEATHER_ASG_NAME
WEATHER_LISTENER_PORT

ADVISOR_ROLE_NAME
ADVISOR_PROFILE_NAME
ADVISOR_LT_NAME
ADVISOR_TG_NAME
ADVISOR_ASG_NAME
ADVISOR_LISTENER_PORT

ALB_NAME
ALB_SG_NAME

DB_INSTANCE_ID
DB_NAME
DB_USER
DB_SG_NAME
DB_SUBNET_GROUP_NAME
DB_PASSWORD_PARAM
CACHE_SECONDS

GEMINI_PARAM_NAME
GEMINI_MODEL
KEY_CACHE_SECONDS
CONTACT_EMAIL
```

Secrets are not stored in `.env`.

---

# 7. AWS Clients

`stack/clients.py` creates boto3 clients for:

```text
EC2
IAM
ELBv2
Auto Scaling
RDS
SSM
STS
S3
```

STS is used to determine the AWS account ID when building IAM policy ARNs.

---

# 8. Weather Service

The Weather service is written using:

```text
Node.js
Express
PostgreSQL
AWS SDK for SSM
```

Main endpoints:

```text
GET /
GET /weather?zip=ZIPCODE
GET /history
```

The Weather service handles:

- ZIP-code validation
- ZIP-to-location conversion
- National Weather Service forecast retrieval
- PostgreSQL caching
- lookup history
- database connectivity
- graceful behavior during database failure

---

# 9. Zippopotam API

The Weather service first converts the ZIP code into geographic coordinates.

Example:

```bash
curl -s https://api.zippopotam.us/us/60616
```

ZIP code:

```text
60616
```

returns Chicago location information including latitude and longitude.

The coordinates are then used with the National Weather Service API.

---

# 10. National Weather Service API

The Weather service calls:

```text
https://api.weather.gov/points/{latitude},{longitude}
```

The points endpoint returns the forecast endpoint.

The forecast contains information including:

- temperature
- temperature unit
- short forecast
- wind speed
- precipitation chance
- daytime/nighttime status

A descriptive User-Agent containing contact information is sent with the request.

## Screenshot 02 — NWS Weather API

![NWS Weather API](screenshots/02_nws_weather_api.png)

---

# 11. Weather Endpoint

Main Weather endpoint:

```text
GET /weather?zip=60616
```

Example:

```bash
curl -i "http://ALB_DNS:8080/weather?zip=60616"
```

Example response:

```json
{
  "zip": "60616",
  "city": "Chicago",
  "state": "IL",
  "forecast": {
    "temperature": 68,
    "temperatureUnit": "F",
    "shortForecast": "Mostly Cloudy"
  },
  "cache": "miss"
}
```

A repeated request can return:

```json
{
  "cache": "hit"
}
```

---

# 12. PostgreSQL RDS Database

The Weather Tier uses PostgreSQL on Amazon RDS.

The database stores:

- weather cache
- lookup history

Required configuration:

```text
Engine: PostgreSQL
Instance Class: db.t4g.micro
Storage: 20 GB
Storage Type: gp2
Storage Encrypted: Yes
Publicly Accessible: No
Multi-AZ: No
Backup Retention: 0
Automated Backups: Disabled
```

The database is created using:

```bash
python3 create_database.py
```

---

# 13. Database Creation

The Python script performs:

```text
1. Find default VPC
2. Find subnets in both Availability Zones
3. Create DB Security Group
4. Create DB Subnet Group
5. Generate random database password
6. Store password as an SSM SecureString
7. Create PostgreSQL RDS instance
8. Wait for database availability
9. Save the database endpoint
```

## Screenshot 04 — Database Created

![Database Created](screenshots/04_database_created.png)

---

# 14. Database Verification

The deployed database was verified with the following settings:

```text
DBInstanceClass: db.t4g.micro
BackupRetentionPeriod: 0
MultiAZ: False
PubliclyAccessible: False
StorageEncrypted: True
```

Database snapshots:

```text
[]
```

Automated backups:

```text
[]
```

## Screenshot 05 — Database Verification

![Database Verification](screenshots/05_database_verified.png)

---

# 15. Database Security Group

PostgreSQL uses:

```text
TCP 5432
```

The Database Security Group permits port `5432` only from the application Security Group.

It does not allow:

```text
0.0.0.0/0
```

and does not allow a public IPv6 range.

Therefore PostgreSQL is not directly accessible from the internet.

---

# 16. Database Password Security

The database password is generated using:

```python
secrets.token_hex(16)
```

It is stored in AWS Systems Manager Parameter Store as:

```text
SecureString
```

Parameter name:

```text
/itmo-444-544/db-password
```

The database password is not stored in:

- GitHub
- `.env`
- Node.js source code
- Python source code
- screenshots
- logs
- EC2 user-data

Only the Weather IAM role can read the password.

---

# 17. PostgreSQL Cache

Configured cache time:

```text
CACHE_SECONDS=600
```

This equals approximately:

```text
10 minutes
```

First lookup:

```json
{
  "cache": "miss"
}
```

Repeated lookup:

```json
{
  "cache": "hit"
}
```

Caching reduces external API calls and improves response time.

---

# 18. Lookup History

The Weather service stores completed lookups in PostgreSQL.

Endpoint:

```text
GET /history
```

Example:

```bash
curl "http://ALB_DNS:8080/history"
```

The response includes previously requested ZIP codes and forecast information.

This verifies PostgreSQL read and write operations.

---

# 19. Weather Error Handling

Invalid ZIP:

```text
123
```

returns:

```text
HTTP 400 Bad Request
```

Unknown ZIP:

```text
00000
```

returns:

```text
HTTP 404 Not Found
```

Response:

```json
{
  "error": "zip_not_found"
}
```

---

# 20. Advisor Service

The Advisor service is also written using Node.js and Express.

Endpoint:

```text
GET /advice?zip=60616
```

The Advisor performs:

```text
1. Call Weather through ALB port 8080
2. Receive forecast information
3. Retrieve Gemini API key from SSM
4. Send weather information to Gemini
5. Return clothing advice
```

The Advisor does not connect directly to PostgreSQL.

---

# 21. Google Gemini

Configured model:

```text
gemini-3.1-flash-lite
```

A successful response contains:

```json
{
  "source": "gemini",
  "model": "gemini-3.1-flash-lite"
}
```

The application sends weather information needed to generate clothing advice.

---

# 22. Gemini API Key Security

The Gemini key is stored in AWS Systems Manager as a SecureString.

Parameter:

```text
/itmo-444-544/gemini-api-key
```

The actual key is not committed to GitHub.

## Screenshot 03 — Gemini SecureString

![Gemini SSM SecureString](screenshots/03_gemini_ssm_securestring.png)

---

# 23. Gemini Fallback

If Gemini fails, the Advisor provides rule-based clothing advice instead.

Fallback response:

```json
{
  "source": "fallback",
  "model": null
}
```

This prevents the complete Advisor application from failing when the AI service is unavailable.

---

# 24. IAM Least Privilege

The Weather and Advisor tiers use separate roles.

## Weather Role

Allowed:

```text
ssm:GetParameter
```

only for:

```text
/itmo-444-544/db-password
```

## Advisor Role

Allowed:

```text
ssm:GetParameter
```

only for:

```text
/itmo-444-544/gemini-api-key
```

Neither role can read the other tier's secret.

## Screenshot 08 — IAM Least Privilege

![IAM Least Privilege](screenshots/08_iam_least_privilege.png)

---

# 25. Application Load Balancer

The Application Load Balancer has two listeners:

```text
8080 -> Weather Target Group
8081 -> Advisor Target Group
```

The ALB spans two Availability Zones.

The ALB is created before the launch templates because the Advisor user-data requires its DNS name.

---

# 26. Security Groups

## ALB Security Group

Allows public traffic on:

```text
8080
8081
```

## Application Security Group

Application port:

```text
3000
```

is allowed only from the ALB Security Group.

Direct access to the application instances on port `3000` timed out during testing.

## Database Security Group

PostgreSQL port:

```text
5432
```

is allowed only from the application Security Group.

---

# 27. Launch Templates

The Weather Launch Template receives:

```text
DB_HOST
DB_NAME
DB_USER
DB_PASSWORD_PARAM
CACHE_SECONDS
NWS_USER_AGENT
```

The Advisor Launch Template receives:

```text
WEATHER_URL
GEMINI_KEY_PARAM
GEMINI_MODEL
KEY_CACHE_SECONDS
```

Actual secret values are not placed inside user-data.

---

# 28. User-Data Size

AWS EC2 user-data must remain below 16 KB.

Measured sizes:

```text
Weather user-data: 13192 bytes
Advisor user-data: 11332 bytes
Maximum allowed: 16384 bytes
```

Both are below the required limit.

---

# 29. Auto Scaling

Two Auto Scaling Groups are used:

```text
itmo-444-544-weather-asg
itmo-444-544-advisor-asg
```

Configuration:

```text
Minimum Capacity: 1
Maximum Capacity: 1
Desired Capacity: 1
Health Check Type: ELB
```

Each ASG spans two subnets.

If an instance fails, Auto Scaling creates a replacement instance.

---

# 30. Stack Creation

The application stack is created using:

```bash
python3 create_weather_stack.py
```

Creation order:

```text
1. Determine AWS account ID
2. Find default VPC
3. Find subnets
4. Get RDS endpoint
5. Create Weather role/profile
6. Create Advisor role/profile
7. Wait for IAM propagation
8. Create ALB Security Group
9. Restrict application Security Group
10. Create Target Groups
11. Create Application Load Balancer
12. Wait for ALB availability
13. Create listeners
14. Create Weather Launch Template
15. Create Advisor Launch Template
16. Create Weather Auto Scaling Group
17. Create Advisor Auto Scaling Group
18. Save outputs
```

## Screenshot 06 — Weather Stack Created

![Weather Stack Created](screenshots/06_weather_stack_created.png)

---

# 31. Advisor Gemini Success

A live Advisor request successfully returned Gemini-generated clothing advice.

## Screenshot 07 — Advisor Gemini Success

![Advisor Gemini Success](screenshots/07_advisor_gemini_success.png)

---

# 32. Idempotency

Infrastructure functions are designed to be idempotent.

Running creation code more than once does not create duplicate resources.

Examples include:

- existing Security Groups are reused
- existing DB Subnet Groups are reused
- existing password parameters are reused
- an existing RDS database is reused
- IAM roles can already exist
- create functions can be rerun safely
- delete functions tolerate already-missing resources

Database idempotency is also verified using moto tests.

---

# 33. Unit Tests with Moto

Unit tests use:

```text
pytest
moto
```

They do not use the real AWS account.

Final result:

```text
27 passed
20 deselected
```

Command:

```bash
pytest -q
```

---

# 34. Database Moto Tests

A dedicated file was added:

```text
tests/unit/test_database_with_moto.py
```

It contains four required database tests.

## Test 1 — RDS Configuration

Verifies:

```text
DBInstanceClass = db.t4g.micro
Engine = PostgreSQL
AllocatedStorage = 20
BackupRetentionPeriod = 0
MultiAZ = False
PubliclyAccessible = False
StorageEncrypted = True
```

## Test 2 — DB Security Group

Verifies:

```text
Protocol = TCP
Port = 5432
Source = Application Security Group
No IPv4 CIDR
No IPv6 CIDR
```

## Test 3 — Idempotency

Runs database creation functions twice and verifies there are no duplicate:

- DB Security Groups
- DB Subnet Groups
- password parameters
- RDS databases

## Test 4 — Create/Delete Cleanup

Creates the database resources and then deletes them.

Verifies:

- database instance is removed
- snapshots are empty
- password parameter is removed

Result:

```text
4 passed
```

---

# 35. Integration Tests

Integration tests run against the real AWS stack.

Command:

```bash
pytest -q -m integration
```

Final result:

```text
18 passed
29 deselected
```

Integration testing verified:

- ALB active
- two Availability Zones
- listener 8080 routes to Weather
- listener 8081 routes to Advisor
- Weather Target Group healthy
- Advisor Target Group healthy
- both Auto Scaling Groups configured
- application port 3000 restricted to ALB
- PostgreSQL 5432 restricted to application SG
- RDS private
- RDS encrypted
- Multi-AZ disabled
- automated backups disabled
- Weather endpoint working
- cache miss/hit behavior
- lookup history
- invalid ZIP returns 400
- unknown ZIP returns 404
- Advisor returns advice
- IAM least privilege

## Screenshot 13 — Unit and Integration Tests

![Unit and Integration Tests Passed](screenshots/13_unit_and_integration_tests_passed.png)

---

# 36. Chaos Testing

Two failure scenarios were tested.

## Chaos Test 1 — Database Failure

The PostgreSQL Security Group rule was temporarily removed.

The Weather service could no longer connect to PostgreSQL.

The service still returned:

```text
HTTP 200
```

with:

```json
{
  "cache": "unavailable"
}
```

This proves graceful degradation.

The DB Security Group rule was restored after the test.

---

## Chaos Test 2 — Weather EC2 Failure

A Weather instance was intentionally terminated.

Before failure, the target was healthy.

## Screenshot 09 — Healthy Before Chaos

![Weather Healthy Before Chaos](screenshots/09_weather_healthy_before_chaos.png)

During the Weather outage, Advisor returned:

```text
HTTP/1.1 502 Bad Gateway
```

Response:

```json
{
  "error": "weather_service_unavailable"
}
```

## Screenshot 10 — Advisor 502 During Weather Outage

![Advisor Weather Outage](screenshots/10_advisor_weather_outage_502.png)

The Weather Auto Scaling Group automatically launched a replacement.

Measured recovery:

```text
approximately 112.5 seconds
```

Required recovery:

```text
<= 300 seconds
```

The requirement passed.

## Screenshot 11 — Weather Recovered

![Weather Recovered](screenshots/11_weather_recovered_after_outage.png)

Automated chaos tests returned:

```text
2 passed
41 deselected
```

## Screenshot 12 — Chaos Tests Passed

![Chaos Tests Passed](screenshots/12_chaos_tests_passed.png)

---

# 37. Moto Limitations

Moto was useful for testing AWS resource creation and configuration without using real AWS resources.

Moto successfully tested:

- configuration
- IAM policy generation
- RDS configuration
- DB Security Group rules
- SSM parameters
- database creation/deletion
- idempotency
- user-data content
- user-data size

Moto cannot fully prove:

- actual EC2 boot behavior
- ALB health-check timing
- real networking
- IAM propagation delays
- Auto Scaling replacement time
- real RDS connectivity
- TLS networking
- external API behavior
- real internet routing

Therefore integration and chaos tests were also run against the real AWS stack.

---

# 38. Python vs Bash

Bash is useful for short AWS CLI commands, but Python was better for this project because there are many dependent cloud resources.

Python made it easier to:

- divide infrastructure into modules
- validate configuration
- handle specific AWS errors
- implement idempotency
- test infrastructure using moto
- reuse creation and deletion logic
- control creation order
- create integration and chaos tests

Bash can commonly use:

```bash
2>/dev/null || true
```

but this can hide unexpected errors.

Python can inspect specific AWS error codes and ignore only expected errors while allowing unexpected failures to be reported.

Although Python requires more code, it provides better structure and testability for infrastructure automation.

---

# 39. Stack Deletion

The application stack is deleted using:

```bash
python3 delete_weather_stack.py
```

It removes:

```text
Weather Auto Scaling Group
Advisor Auto Scaling Group
Application Load Balancer
Weather Target Group
Advisor Target Group
ALB Security Group
Weather Launch Template
Advisor Launch Template
Weather IAM Role/Profile
Advisor IAM Role/Profile
Gemini SSM parameter
Stack output files
```

The Gemini parameter removed by Python is:

```text
/itmo-444-544/gemini-api-key
```

The deletion code also tolerates the parameter already being absent.

---

# 40. Database Deletion

The database is deleted separately using:

```bash
python3 delete_database.py
```

The script removes:

- RDS database
- DB Subnet Group
- DB Security Group
- database password parameter
- automated backups
- local database output file

Database deletion uses:

```text
SkipFinalSnapshot=True
DeleteAutomatedBackups=True
```

No final snapshot is retained.

Database password parameter:

```text
/itmo-444-544/db-password
```

is also removed.

---

# 41. Final Cleanup Verification

After all testing was complete, both Python deletion scripts were executed.

The following resources were checked:

```text
Auto Scaling Groups
Application Load Balancers
RDS instances
RDS snapshots
RDS automated backups
DB Subnet Groups
Launch Templates
IAM roles
Target Groups
SSM parameters
```

Verification commands included:

```bash
aws autoscaling describe-auto-scaling-groups \
  --query "AutoScalingGroups[?contains(AutoScalingGroupName, 'itmo-444-544')].[AutoScalingGroupName]" \
  --output table
```

```bash
aws elbv2 describe-load-balancers \
  --query "LoadBalancers[?contains(LoadBalancerName, 'itmo-444-544')].[LoadBalancerName]" \
  --output table
```

```bash
aws rds describe-db-instances \
  --query "DBInstances[?contains(DBInstanceIdentifier, 'itmo-444-544')].[DBInstanceIdentifier]" \
  --output table
```

```bash
aws rds describe-db-snapshots \
  --query "DBSnapshots[?contains(DBInstanceIdentifier, 'itmo-444-544')].[DBSnapshotIdentifier]" \
  --output table
```

```bash
aws rds describe-db-instance-automated-backups \
  --query "DBInstanceAutomatedBackups[?contains(DBInstanceIdentifier, 'itmo-444-544')].[DBInstanceIdentifier]" \
  --output table
```

```bash
aws ssm describe-parameters \
  --query "Parameters[?contains(Name, 'itmo-444-544')].[Name]" \
  --output table
```

```bash
aws rds describe-db-subnet-groups \
  --query "DBSubnetGroups[?contains(DBSubnetGroupName, 'itmo-444-544')].[DBSubnetGroupName]" \
  --output table
```

```bash
aws ec2 describe-launch-templates \
  --query "LaunchTemplates[?contains(LaunchTemplateName, 'itmo-444-544')].[LaunchTemplateName]" \
  --output table
```

```bash
aws iam list-roles \
  --query "Roles[?contains(RoleName, 'itmo-444-544')].[RoleName]" \
  --output table
```

```bash
aws elbv2 describe-target-groups \
  --query "TargetGroups[?contains(TargetGroupName, 'itmo-444-544')].[TargetGroupName]" \
  --output table
```

All final verification checks returned no matching Step08 resources.

## Screenshot 14 — Final Cleanup Verification

![Final Cleanup Verified](screenshots/14_final_cleanup_verified.png)

---

# 42. Screenshot Evidence

| No. | Screenshot | Evidence |
|---|---|---|
| 01 | `01_project_structure.png` | Final project structure |
| 02 | `02_nws_weather_api.png` | National Weather Service API |
| 03 | `03_gemini_ssm_securestring.png` | Gemini key stored as SSM SecureString |
| 04 | `04_database_created.png` | PostgreSQL database creation |
| 05 | `05_database_verified.png` | RDS settings verification |
| 06 | `06_weather_stack_created.png` | Python Weather Advisor stack creation |
| 07 | `07_advisor_gemini_success.png` | Successful Gemini Advisor response |
| 08 | `08_iam_least_privilege.png` | Least-privilege IAM policies |
| 09 | `09_weather_healthy_before_chaos.png` | Healthy Weather target before chaos |
| 10 | `10_advisor_weather_outage_502.png` | Advisor 502 during Weather outage |
| 11 | `11_weather_recovered_after_outage.png` | Weather Auto Scaling recovery |
| 12 | `12_chaos_tests_passed.png` | Automated chaos tests |
| 13 | `13_unit_and_integration_tests_passed.png` | 27 unit/moto + 18 integration tests |
| 14 | `14_final_cleanup_verified.png` | Final AWS cleanup verification |

---

# 43. Final Test Results

```text
Database-specific Moto:
4 passed

Complete Unit / Moto Suite:
27 passed
20 deselected

Integration Tests:
18 passed
29 deselected

Chaos Tests:
2 passed
41 deselected

Weather Recovery:
approximately 112.5 seconds

Required Recovery:
<= 300 seconds
```

All automated tests passed.

---

# 44. Graduate Checklist

## Python Infrastructure

- [x] `create_database.py`
- [x] `delete_database.py`
- [x] `create_weather_stack.py`
- [x] `delete_weather_stack.py`
- [x] Infrastructure implemented with boto3
- [x] Required PostgreSQL database configuration
- [x] Database password generated with `secrets.token_hex(16)`
- [x] Database password stored in SSM
- [x] Gemini key stored in SSM
- [x] Weather role reads only DB secret
- [x] Advisor role reads only Gemini secret
- [x] ALB and both listeners
- [x] Weather and Advisor Target Groups
- [x] Weather and Advisor Launch Templates
- [x] Weather and Advisor Auto Scaling Groups
- [x] ALB created before Advisor Launch Template
- [x] Advisor user-data receives ALB DNS
- [x] Weather user-data receives DB host
- [x] No password in user-data
- [x] Both user-data scripts below 16 KB
- [x] Idempotent creation
- [x] Safe repeated deletion
- [x] No secrets committed to GitHub

## Unit / Moto Tests

- [x] `db.t4g.micro`
- [x] Backup retention 0
- [x] Multi-AZ false
- [x] Publicly accessible false
- [x] Storage encrypted
- [x] DB Security Group allows 5432 only from app SG
- [x] No public DB CIDR
- [x] Database create/delete tested
- [x] Snapshots empty after delete
- [x] Password parameter removed
- [x] IAM least privilege tested
- [x] Advisor user-data contains ALB DNS
- [x] Weather user-data contains DB host
- [x] Password absent from user-data
- [x] User-data under 16 KB
- [x] Idempotency tested

## Integration Tests

- [x] Both target groups healthy
- [x] Weather endpoint successful
- [x] Cache miss and hit verified
- [x] `/history` verified
- [x] Invalid ZIP returns 400
- [x] Unknown ZIP returns 404
- [x] Advisor returns advice
- [x] Application instances accessible only through ALB
- [x] Database not publicly reachable
- [x] RDS settings verified
- [x] IAM least privilege verified

## Chaos Tests

- [x] Database access intentionally removed
- [x] Weather remained available
- [x] Cache reported unavailable
- [x] DB rule restored
- [x] Weather EC2 intentionally terminated
- [x] Advisor returned 502 during outage
- [x] Auto Scaling launched replacement
- [x] Weather recovered within 300 seconds

## Cleanup

- [x] Auto Scaling Groups removed
- [x] Application Load Balancer removed
- [x] Target Groups removed
- [x] Launch Templates removed
- [x] IAM roles/profiles removed
- [x] RDS instance removed
- [x] DB Subnet Group removed
- [x] DB snapshots empty
- [x] Automated backups empty
- [x] DB password parameter removed
- [x] Gemini API-key parameter removed
- [x] Final cleanup verified with AWS CLI

---

# 45. Final Result

The Weather Advisor project successfully demonstrates a complete two-tier cloud application implemented and managed using Python.

The project includes:

```text
Python + boto3 infrastructure automation
Two application tiers
Application Load Balancer
Two Target Groups
Two Auto Scaling Groups
PostgreSQL on Amazon RDS
PostgreSQL caching
Lookup history
Zippopotam API
National Weather Service API
Google Gemini
SSM SecureString secrets
Least-privilege IAM
Secure Security Groups
Graceful degradation
Moto unit testing
Real AWS integration testing
Chaos testing
Automatic EC2 recovery
Idempotent infrastructure
Python-based deletion
Complete final AWS cleanup
```

Final automated test results:

```text
27 unit/moto tests passed
18 integration tests passed
2 chaos tests passed
```

Measured Weather recovery time:

```text
approximately 112.5 seconds
```

Required recovery:

```text
<= 300 seconds
```

The application functionality, AWS infrastructure, security, automated testing, failure recovery, and final resource cleanup were successfully completed.
