# Step08 — Weather Advisor in the Cloud

## ITMO 544 — Cloud Computing

This project implements a two-tier cloud application called **Weather Advisor** using Python, boto3, AWS, Node.js, PostgreSQL, external weather APIs, Google Gemini, `pytest`, and `moto`.

For the graduate ITMO 544 version of the assignment, AWS infrastructure is created and deleted using **Python and boto3** rather than Bash scripts.

The project demonstrates:

- Python-based AWS infrastructure automation
- Two-tier cloud architecture
- Application Load Balancing
- Auto Scaling
- PostgreSQL on Amazon RDS
- AWS Systems Manager Parameter Store
- Least-privilege IAM
- National Weather Service API integration
- Google Gemini integration
- PostgreSQL-backed caching
- Graceful degradation
- Unit testing with `pytest` and `moto`
- Real AWS integration testing
- Chaos testing
- Automatic EC2 replacement and recovery
- Secure networking
- Idempotent infrastructure creation
- Complete AWS resource cleanup

---

# 1. Project Overview

The application contains two services:

1. **Weather Service**
2. **Advisor Service**

The Weather service accepts a U.S. ZIP code, finds its location, retrieves weather information from the National Weather Service API, stores lookup history and cached weather data in PostgreSQL, and returns the current forecast.

The Advisor service calls the Weather service and uses Google Gemini to generate clothing recommendations based on the weather.

Both services run on EC2 instances behind an AWS Application Load Balancer.

---

# 2. Architecture

~~~text
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
        +-------+-------+                 |
        |               |                 |
        v               v                 |
    Zippopotam       NWS API              |
        |                                 |
        +--------> Weather Data            |
                        |                  |
                        v                  |
                 PostgreSQL RDS            |
                        ^                  |
                        |                  |
                        +------------------+
                                           |
                                           v
                                     Google Gemini
                                           |
                                           v
                                Clothing Recommendation
~~~

Public ALB listeners:

~~~text
8080 -> Weather Tier
8081 -> Advisor Tier
~~~

Both Node.js applications listen internally on:

~~~text
Port 3000
~~~

PostgreSQL uses:

~~~text
Port 5432
~~~

---

# 3. Request Flow

A normal Advisor request follows this path:

~~~text
User
 |
 v
ALB :8081
 |
 v
Advisor Service
 |
 v
ALB :8080
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
~~~

The Advisor service communicates with the Weather service through the ALB instead of directly contacting an EC2 instance.

This means Auto Scaling can replace a Weather instance without requiring any change to the Advisor configuration.

---

# 4. Project Structure

~~~text
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
~~~

## Screenshot 01 — Project Structure

Command:

~~~bash
ls -R | head -40
~~~

This screenshot shows the Step08 project directory and its main application, infrastructure, testing, and documentation files.

![Project Structure](screenshots/01_project_structure.png)

---

# 5. Python Infrastructure

The main Python infrastructure scripts are:

~~~text
create_database.py
delete_database.py
create_weather_stack.py
delete_weather_stack.py
~~~

AWS resources are created and deleted using **boto3**.

AWS CLI commands are used only to inspect and verify resources.

---

# 6. Configuration

`stack/config.py` loads deployment settings from `.env`.

Important configuration includes:

~~~text
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
~~~

Actual secret values are not stored in `.env`.

---

# 7. AWS Clients

`stack/clients.py` creates boto3 clients for:

~~~text
EC2
IAM
ELBv2
Auto Scaling
RDS
SSM
STS
S3
~~~

STS is used to determine the AWS account ID when IAM ARNs are created.

---

# 8. Weather Service

The Weather service uses:

~~~text
Node.js
Express
PostgreSQL
AWS SDK for SSM
~~~

Endpoints:

~~~text
GET /
GET /weather?zip=ZIPCODE
GET /history
~~~

The service handles:

- ZIP-code validation
- ZIP-to-coordinate lookup
- NWS weather retrieval
- PostgreSQL caching
- lookup history
- database connectivity
- graceful behavior during database failure

---

# 9. Zippopotam API

The Weather service first converts a ZIP code into geographic coordinates.

Example:

~~~bash
curl -s https://api.zippopotam.us/us/60616
~~~

ZIP code `60616` returns Chicago location information including latitude and longitude.

These coordinates are then used with the National Weather Service API.

---

# 10. National Weather Service API

The Weather service uses:

~~~text
https://api.weather.gov/points/{latitude},{longitude}
~~~

The API provides a forecast endpoint containing information such as:

- temperature
- temperature unit
- short forecast
- wind speed
- precipitation chance
- daytime/nighttime status

A descriptive User-Agent is supplied with the NWS request.

## Screenshot 02 — NWS Weather API

Command used:

~~~bash
curl -s -H "User-Agent: $UA" "$FORECAST_URL" | python3 -m json.tool | head -40
~~~

The returned JSON proves that the external NWS forecast API was reachable and successfully returned weather data.

![NWS Weather API](screenshots/02_nws_weather_api.png)

---

# 11. Weather Endpoint

Main endpoint:

~~~text
GET /weather?zip=60616
~~~

Example:

~~~bash
curl -i "http://$ALB_DNS_NAME:8080/weather?zip=60616"
~~~

Example response:

~~~json
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
~~~

A repeated request can return:

~~~json
{
  "cache": "hit"
}
~~~

---

# 12. PostgreSQL RDS Database

The Weather tier uses PostgreSQL on Amazon RDS.

It stores:

- weather cache data
- lookup history

Required database settings:

~~~text
Engine: PostgreSQL
Instance Class: db.t4g.micro
Storage: 20 GB
Storage Type: gp2
Storage Encrypted: Yes
Publicly Accessible: No
Multi-AZ: No
Backup Retention: 0
Automated Backups: Disabled
~~~

---

# 13. Database Creation

Command:

~~~bash
python3 create_database.py
~~~

The script:

~~~text
1. Finds the default VPC
2. Finds required subnets
3. Creates the DB Security Group
4. Creates the DB Subnet Group
5. Generates a random database password
6. Stores the password in SSM
7. Creates the PostgreSQL RDS instance
8. Waits for the database
9. Saves the endpoint
~~~

## Screenshot 04 — Database Created

The screenshot shows successful RDS creation and confirms that the database is:

~~~text
Private
Encrypted
Single-AZ
Automated backups OFF
~~~

![Database Created](screenshots/04_database_created.png)

---

# 14. Database Verification

Verification command:

~~~bash
aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query "DBInstances[0].{Class:DBInstanceClass,Engine:Engine,MultiAZ:MultiAZ,Public:PubliclyAccessible,Encrypted:StorageEncrypted,BackupRetentionDays:BackupRetentionPeriod}" \
  --output table
~~~

Expected configuration:

~~~text
DBInstanceClass: db.t4g.micro
BackupRetentionPeriod: 0
MultiAZ: False
PubliclyAccessible: False
StorageEncrypted: True
Engine: postgres
~~~

Database snapshots and automated backups were also checked and returned empty results.

## Screenshot 05 — Database Verification

![Database Verification](screenshots/05_database_verified.png)

---

# 15. Database Security

PostgreSQL uses:

~~~text
TCP 5432
~~~

The DB Security Group permits port `5432` only from the application Security Group.

It does not permit:

~~~text
0.0.0.0/0
~~~

Therefore the database is not directly exposed to the internet.

---

# 16. Database Password Security

The password is generated using:

~~~python
secrets.token_hex(16)
~~~

It is stored in SSM Parameter Store as:

~~~text
SecureString
~~~

Parameter:

~~~text
/itmo-444-544/db-password
~~~

The password is not stored in:

~~~text
GitHub
.env
Node.js source code
Python source code
screenshots
EC2 user-data
~~~

Only the Weather IAM role can retrieve this parameter.

---

# 17. PostgreSQL Cache

Cache duration:

~~~text
CACHE_SECONDS=600
~~~

which equals approximately 10 minutes.

First lookup:

~~~json
{
  "cache": "miss"
}
~~~

Repeated lookup:

~~~json
{
  "cache": "hit"
}
~~~

This reduces unnecessary external API requests.

---

# 18. Lookup History

The Weather service stores completed requests in PostgreSQL.

Endpoint:

~~~text
GET /history
~~~

Example:

~~~bash
curl "http://$ALB_DNS_NAME:8080/history"
~~~

This proves database read/write functionality.

---

# 19. Error Handling

Invalid ZIP:

~~~text
123
~~~

returns:

~~~text
HTTP 400 Bad Request
~~~

An unknown ZIP such as:

~~~text
00000
~~~

returns:

~~~text
HTTP 404 Not Found
~~~

with:

~~~json
{
  "error": "zip_not_found"
}
~~~

---

# 20. Advisor Service

Advisor endpoint:

~~~text
GET /advice?zip=60616
~~~

Flow:

~~~text
1. Call Weather through ALB port 8080
2. Receive weather data
3. Retrieve Gemini API key from SSM
4. Send forecast information to Gemini
5. Return clothing advice
~~~

The Advisor does not directly connect to PostgreSQL.

---

# 21. Google Gemini

Configured model:

~~~text
gemini-3.1-flash-lite
~~~

A successful response contains:

~~~json
{
  "source": "gemini",
  "model": "gemini-3.1-flash-lite"
}
~~~

---

# 22. Gemini API-Key Security

The Gemini API key is stored in AWS Systems Manager Parameter Store as:

~~~text
SecureString
~~~

Parameter:

~~~text
/itmo-444-544/gemini-api-key
~~~

## Screenshot 03 — Gemini SecureString

Command:

~~~bash
aws ssm describe-parameters \
  --parameter-filters "Key=Name,Values=$GEMINI_PARAM_NAME" \
  --query "Parameters[].{Name:Name,Type:Type,Tier:Tier}" \
  --output table
~~~

The screenshot verifies:

~~~text
Name: /itmo-444-544/gemini-api-key
Type: SecureString
Tier: Standard
~~~

![Gemini SSM SecureString](screenshots/03_gemini_ssm_securestring.png)

---

# 23. Gemini Fallback

If Gemini becomes unavailable, the Advisor can return rule-based clothing advice.

Fallback response:

~~~json
{
  "source": "fallback",
  "model": null
}
~~~

This prevents an AI-service problem from completely breaking the Advisor application.

---

# 24. IAM Least Privilege

The Weather and Advisor tiers use separate IAM roles.

## Weather Role

Allowed:

~~~text
ssm:GetParameter
~~~

only for:

~~~text
/itmo-444-544/db-password
~~~

## Advisor Role

Allowed:

~~~text
ssm:GetParameter
~~~

only for:

~~~text
/itmo-444-544/gemini-api-key
~~~

Neither application can retrieve the other application's secret.

## Screenshot 08 — IAM Least Privilege

Commands:

~~~bash
aws iam get-role-policy \
  --role-name "$WEATHER_ROLE_NAME" \
  --policy-name "${WEATHER_ROLE_NAME}-policy" \
  --query 'PolicyDocument.Statement'
~~~

~~~bash
aws iam get-role-policy \
  --role-name "$ADVISOR_ROLE_NAME" \
  --policy-name "${ADVISOR_ROLE_NAME}-policy" \
  --query 'PolicyDocument.Statement'
~~~

The output proves that each IAM role has access only to its required SSM parameter.

![IAM Least Privilege](screenshots/08_iam_least_privilege.png)

---

# 25. Application Load Balancer

The ALB has two listeners:

~~~text
8080 -> Weather Target Group
8081 -> Advisor Target Group
~~~

It spans two Availability Zones.

The ALB is created before the Advisor Launch Template because Advisor user-data needs the ALB DNS name.

---

# 26. Security Groups

## ALB Security Group

Allows public traffic on:

~~~text
8080
8081
~~~

## Application Security Group

Application port:

~~~text
3000
~~~

is accessible only from the ALB Security Group.

## Database Security Group

PostgreSQL port:

~~~text
5432
~~~

is accessible only from the application Security Group.

---

# 27. Launch Templates

The Weather Launch Template receives:

~~~text
DB_HOST
DB_NAME
DB_USER
DB_PASSWORD_PARAM
CACHE_SECONDS
NWS_USER_AGENT
~~~

The Advisor Launch Template receives:

~~~text
WEATHER_URL
GEMINI_KEY_PARAM
GEMINI_MODEL
KEY_CACHE_SECONDS
~~~

Actual passwords and API keys are not inserted into EC2 user-data.

---

# 28. User-Data Size

AWS user-data must remain below 16 KB.

Measured sizes:

~~~text
Weather user-data: 13192 bytes
Advisor user-data: 11332 bytes
Maximum allowed: 16384 bytes
~~~

Both are within the AWS limit.

---

# 29. Auto Scaling

Two Auto Scaling Groups are used:

~~~text
itmo-444-544-weather-asg
itmo-444-544-advisor-asg
~~~

Configuration:

~~~text
Minimum Capacity: 1
Maximum Capacity: 1
Desired Capacity: 1
Health Check Type: ELB
~~~

If an instance fails, its Auto Scaling Group creates a replacement.

---

# 30. Stack Creation

Command:

~~~bash
python3 create_weather_stack.py
~~~

The script creates:

~~~text
IAM roles and instance profiles
ALB Security Group
Target Groups
Application Load Balancer
Listeners
Launch Templates
Auto Scaling Groups
~~~

## Screenshot 06 — Weather Stack Created

The screenshot shows successful creation of:

- ALB Security Group
- Weather Target Group
- Advisor Target Group
- Application Load Balancer
- listeners on 8080 and 8081
- Weather Launch Template
- Advisor Launch Template
- Weather Auto Scaling Group
- Advisor Auto Scaling Group

It also displays the final Weather and Advisor URLs.

![Weather Stack Created](screenshots/06_weather_stack_created.png)

---

# 31. Advisor Gemini Success

Command:

~~~bash
curl -s "http://$ALB_DNS_NAME:8081/advice?zip=60616" | python3 -m json.tool
~~~

The response contains:

~~~text
zip
city
state
forecast
latitude
longitude
cache
advice
source
model
~~~

The important fields are:

~~~json
{
  "source": "gemini",
  "model": "gemini-3.1-flash-lite"
}
~~~

This proves that the Advisor service successfully contacted the Weather service and generated an AI clothing recommendation through Gemini.

## Screenshot 07 — Advisor Gemini Success

![Advisor Gemini Success](screenshots/07_advisor_gemini_success.png)

---

# 32. Idempotency

Infrastructure creation functions are designed to be safely rerun.

Examples:

- existing Security Groups are reused
- existing DB Subnet Groups are reused
- existing password parameters are reused
- existing RDS resources are reused when appropriate
- IAM roles may already exist
- delete functions tolerate already-missing resources

Idempotency is also tested using moto.

---

# 33. Unit Tests with Moto

Unit tests use:

~~~text
pytest
moto
~~~

Command:

~~~bash
pytest -q
~~~

Final result:

~~~text
27 passed
20 deselected
~~~

The tests run without creating real AWS resources.

---

# 34. Database Moto Tests

File:

~~~text
tests/unit/test_database_with_moto.py
~~~

The tests verify:

## RDS Configuration

~~~text
DBInstanceClass = db.t4g.micro
Engine = PostgreSQL
AllocatedStorage = 20
BackupRetentionPeriod = 0
MultiAZ = False
PubliclyAccessible = False
StorageEncrypted = True
~~~

## Database Security Group

~~~text
Protocol = TCP
Port = 5432
Source = Application Security Group
No public IPv4 CIDR
No public IPv6 CIDR
~~~

## Idempotency

Database creation functions are run twice to verify that duplicate resources are not created.

## Create/Delete Cleanup

The test confirms that:

~~~text
RDS instance is deleted
snapshots remain empty
password parameter is deleted
~~~

Database-specific result:

~~~text
4 passed
~~~

---

# 35. Integration Tests

Command:

~~~bash
pytest -q -m integration
~~~

Final result:

~~~text
18 passed
29 deselected
~~~

Integration tests verified:

- ALB is active
- ALB spans two Availability Zones
- listener 8080 routes to Weather
- listener 8081 routes to Advisor
- Weather Target Group is healthy
- Advisor Target Group is healthy
- Auto Scaling Groups are configured
- application port 3000 is restricted
- PostgreSQL 5432 is restricted
- RDS is private
- RDS is encrypted
- Multi-AZ is disabled
- automated backups are disabled
- Weather endpoint works
- cache miss/hit works
- lookup history works
- invalid ZIP returns 400
- unknown ZIP returns 404
- Advisor returns advice
- IAM least privilege is enforced

## Screenshot 13 — Unit and Integration Tests

Commands:

~~~bash
pytest -q
pytest -q -m integration
~~~

Result:

~~~text
27 passed, 20 deselected
18 passed, 29 deselected
~~~

![Unit and Integration Tests Passed](screenshots/13_unit_and_integration_tests_passed.png)

---

# 36. Chaos Testing

Two failure scenarios were tested.

## Chaos Test 1 — Database Failure

Database connectivity was intentionally interrupted.

Even without PostgreSQL, the Weather service continued returning:

~~~text
HTTP 200
~~~

with:

~~~json
{
  "cache": "unavailable"
}
~~~

This demonstrates graceful degradation.

The database rule was restored after the test.

---

## Chaos Test 2 — Weather EC2 Failure

Before terminating the Weather EC2 instance, the Weather endpoint and Target Group were verified as healthy.

### Screenshot 09 — Healthy Before Chaos

Commands:

~~~bash
curl -i "http://$ALB_DNS_NAME:8080/weather?zip=60616"
~~~

and:

~~~bash
aws elbv2 describe-target-health \
  --target-group-arn "$WEATHER_TG_ARN" \
  --query 'TargetHealthDescriptions[*].{Instance:Target.Id,State:TargetHealth.State,Reason:TargetHealth.Reason}'
~~~

The screenshot shows:

~~~text
HTTP/1.1 200 OK
State: healthy
~~~

This establishes a healthy baseline before introducing the failure.

![Weather Healthy Before Chaos](screenshots/09_weather_healthy_before_chaos.png)

---

The Weather instance was then intentionally terminated.

### Screenshot 10 — Advisor 502 During Weather Outage

Command:

~~~bash
aws ec2 terminate-instances \
  --instance-ids <WEATHER_INSTANCE_ID>
~~~

Immediately afterward:

~~~bash
curl -i "http://$ALB_DNS_NAME:8081/advice?zip=60616"
~~~

returned:

~~~text
HTTP/1.1 502 Bad Gateway
~~~

This confirms that the Advisor correctly reported the Weather service as unavailable while the Weather tier had no healthy target.

![Advisor Weather Outage](screenshots/10_advisor_weather_outage_502.png)

---

The Weather Auto Scaling Group automatically launched a replacement EC2 instance.

### Screenshot 11 — Weather Recovered

Commands:

~~~bash
aws elbv2 describe-target-health \
  --target-group-arn "$WEATHER_TG_ARN" \
  --query 'TargetHealthDescriptions[*].{Instance:Target.Id,State:TargetHealth.State,Reason:TargetHealth.Reason,Description:TargetHealth.Description}'
~~~

and:

~~~bash
curl -i "http://$ALB_DNS_NAME:8080/weather?zip=60616"
~~~

The replacement target became:

~~~text
State: healthy
~~~

and Weather returned:

~~~text
HTTP/1.1 200 OK
~~~

This proves automatic EC2 recovery through Auto Scaling.

![Weather Recovered](screenshots/11_weather_recovered_after_outage.png)

---

Measured recovery time:

~~~text
approximately 112.5 seconds
~~~

Required recovery objective:

~~~text
<= 300 seconds
~~~

The requirement passed.

### Screenshot 12 — Automated Chaos Tests

Command:

~~~bash
pytest -q -m chaos -s
~~~

Output:

~~~text
DB outage response: 200
Terminated Weather instance
Saw Advisor 502: True
Weather recovery time: approximately 112.5 seconds

2 passed, 41 deselected
~~~

This automated both failure scenarios and confirmed recovery.

![Chaos Tests Passed](screenshots/12_chaos_tests_passed.png)

---

# 37. Moto Limitations

Moto was useful for testing infrastructure logic without creating real AWS resources.

Moto successfully tested:

- configuration
- IAM policy generation
- RDS configuration
- DB Security Group rules
- SSM parameters
- database creation/deletion
- idempotency
- user-data contents
- user-data size

Moto cannot fully prove:

- actual EC2 boot behavior
- ALB health-check timing
- real networking
- IAM propagation delays
- Auto Scaling replacement time
- real RDS connectivity
- external API behavior
- internet routing

For those reasons, integration and chaos tests were also executed against real AWS infrastructure.

---

# 38. Python vs Bash

Bash is useful for short AWS CLI operations, but Python is better suited to this assignment because the infrastructure contains many dependent resources.

Python makes it easier to:

- divide infrastructure into modules
- validate configuration
- handle AWS exceptions
- implement idempotency
- test with moto
- reuse creation/deletion logic
- control resource creation order
- write integration and chaos tests

Python requires more code, but provides better organization, testing, and error handling for infrastructure automation.

---

# 39. Stack Deletion

Command:

~~~bash
python3 delete_weather_stack.py
~~~

It removes:

~~~text
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
~~~

Gemini parameter:

~~~text
/itmo-444-544/gemini-api-key
~~~

---

# 40. Database Deletion

Command:

~~~bash
python3 delete_database.py
~~~

The script removes:

- RDS instance
- DB Subnet Group
- DB Security Group
- database password parameter
- automated backups
- local database output file

Database deletion uses:

~~~text
SkipFinalSnapshot=True
DeleteAutomatedBackups=True
~~~

The password parameter:

~~~text
/itmo-444-544/db-password
~~~

is also deleted.

---

# 41. Final Cleanup Verification

After testing, both deletion scripts were executed.

The following resource types were checked:

~~~text
Auto Scaling Groups
Application Load Balancers
RDS instances
RDS snapshots
RDS automated backups
SSM parameters
DB Subnet Groups
Launch Templates
IAM roles
Target Groups
~~~

Verification commands included:

~~~bash
aws autoscaling describe-auto-scaling-groups \
  --query "AutoScalingGroups[?contains(AutoScalingGroupName, 'itmo-444-544')].[AutoScalingGroupName]" \
  --output table
~~~

~~~bash
aws elbv2 describe-load-balancers \
  --query "LoadBalancers[?contains(LoadBalancerName, 'itmo-444-544')].[LoadBalancerName]" \
  --output table
~~~

~~~bash
aws rds describe-db-instances \
  --query "DBInstances[?contains(DBInstanceIdentifier, 'itmo-444-544')].[DBInstanceIdentifier]" \
  --output table
~~~

~~~bash
aws rds describe-db-snapshots \
  --query "DBSnapshots[?contains(DBInstanceIdentifier, 'itmo-444-544')].[DBSnapshotIdentifier]" \
  --output table
~~~

~~~bash
aws rds describe-db-instance-automated-backups \
  --query "DBInstanceAutomatedBackups[?contains(DBInstanceIdentifier, 'itmo-444-544')].[DBInstanceIdentifier]" \
  --output table
~~~

~~~bash
aws ssm describe-parameters \
  --query "Parameters[?contains(Name, 'itmo-444-544')].[Name]" \
  --output table
~~~

~~~bash
aws rds describe-db-subnet-groups \
  --query "DBSubnetGroups[?contains(DBSubnetGroupName, 'itmo-444-544')].[DBSubnetGroupName]" \
  --output table
~~~

~~~bash
aws ec2 describe-launch-templates \
  --query "LaunchTemplates[?contains(LaunchTemplateName, 'itmo-444-544')].[LaunchTemplateName]" \
  --output table
~~~

~~~bash
aws iam list-roles \
  --query "Roles[?contains(RoleName, 'itmo-444-544')].[RoleName]" \
  --output table
~~~

~~~bash
aws elbv2 describe-target-groups \
  --query "TargetGroups[?contains(TargetGroupName, 'itmo-444-544')].[TargetGroupName]" \
  --output table
~~~

All checks returned no matching Step08 resources.

## Screenshot 14 — Final Cleanup Verification

The screenshot shows selected final AWS CLI cleanup checks returning no matching Step08 resources.

![Final Cleanup Verified](screenshots/14_final_cleanup_verified.png)

---

# 42. Screenshot Evidence

| No. | Screenshot | What It Proves |
|---|---|---|
| 01 | `01_project_structure.png` | Final Weather Advisor project structure |
| 02 | `02_nws_weather_api.png` | NWS API successfully returns forecast data |
| 03 | `03_gemini_ssm_securestring.png` | Gemini API key stored as an SSM SecureString |
| 04 | `04_database_created.png` | PostgreSQL RDS database successfully created |
| 05 | `05_database_verified.png` | Required RDS configuration and disabled backups |
| 06 | `06_weather_stack_created.png` | ALB, target groups, listeners, launch templates and ASGs created |
| 07 | `07_advisor_gemini_success.png` | Advisor successfully generated Gemini clothing advice |
| 08 | `08_iam_least_privilege.png` | Weather and Advisor roles only access their required SSM parameters |
| 09 | `09_weather_healthy_before_chaos.png` | Weather endpoint and target healthy before EC2 failure |
| 10 | `10_advisor_weather_outage_502.png` | Weather EC2 terminated and Advisor returned 502 |
| 11 | `11_weather_recovered_after_outage.png` | Replacement Weather instance became healthy and returned HTTP 200 |
| 12 | `12_chaos_tests_passed.png` | Automated DB and Weather failure tests passed |
| 13 | `13_unit_and_integration_tests_passed.png` | 27 unit/moto and 18 integration tests passed |
| 14 | `14_final_cleanup_verified.png` | Final AWS cleanup verified |

---

# 43. Final Test Results

~~~text
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
~~~

All automated tests passed.

---

# 44. Graduate Checklist

## Python Infrastructure

- [x] `create_database.py`
- [x] `delete_database.py`
- [x] `create_weather_stack.py`
- [x] `delete_weather_stack.py`
- [x] Infrastructure implemented using boto3
- [x] Required PostgreSQL RDS configuration
- [x] Password generated using `secrets.token_hex(16)`
- [x] Database password stored in SSM
- [x] Gemini key stored in SSM
- [x] Weather role reads only DB secret
- [x] Advisor role reads only Gemini secret
- [x] ALB and two listeners
- [x] Weather and Advisor Target Groups
- [x] Weather and Advisor Launch Templates
- [x] Weather and Advisor Auto Scaling Groups
- [x] ALB created before Advisor Launch Template
- [x] Advisor user-data receives ALB DNS
- [x] Weather user-data receives DB host
- [x] Secrets excluded from user-data
- [x] User-data below 16 KB
- [x] Idempotent resource creation
- [x] Safe repeated deletion
- [x] No secrets committed to GitHub

## Unit / Moto Tests

- [x] `db.t4g.micro`
- [x] Backup retention = 0
- [x] Multi-AZ = false
- [x] Publicly accessible = false
- [x] Storage encrypted
- [x] DB Security Group restricts port 5432
- [x] No public DB CIDR
- [x] Database create/delete tested
- [x] Snapshots empty after deletion
- [x] Password parameter removed
- [x] IAM least privilege tested
- [x] Advisor user-data contains ALB DNS
- [x] Weather user-data contains DB host
- [x] Password absent from user-data
- [x] User-data below 16 KB
- [x] Idempotency tested

## Integration Tests

- [x] Target Groups healthy
- [x] Weather endpoint works
- [x] Cache miss and hit verified
- [x] `/history` verified
- [x] Invalid ZIP returns 400
- [x] Unknown ZIP returns 404
- [x] Advisor returns clothing advice
- [x] Instances protected behind ALB
- [x] Database not publicly reachable
- [x] RDS configuration verified
- [x] IAM least privilege verified

## Chaos Tests

- [x] Database access intentionally interrupted
- [x] Weather remained available
- [x] Cache reported unavailable
- [x] Database access restored
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
- [x] RDS snapshots empty
- [x] Automated backups empty
- [x] DB password parameter removed
- [x] Gemini API-key parameter removed
- [x] Final cleanup verified with AWS CLI

---

# 45. Final Result

The Weather Advisor project successfully demonstrates a complete two-tier cloud application implemented and managed using Python and AWS.

The final solution includes:

~~~text
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
Complete AWS cleanup
~~~

Final automated results:

~~~text
27 unit/moto tests passed
18 integration tests passed
2 chaos tests passed
~~~

Measured Weather recovery:

~~~text
approximately 112.5 seconds
~~~

Required recovery:

~~~text
<= 300 seconds
~~~

The application functionality, AWS infrastructure, security configuration, testing, failure recovery, and cleanup were successfully completed.
