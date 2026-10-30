# Step08 — Weather Advisor in the Cloud

## ITMO 544 — Cloud Computing

This project implements a two-tier cloud application called **Weather Advisor** using Python, boto3, AWS, Node.js, PostgreSQL, external weather APIs, Google Gemini, `pytest`, and `moto`.

For the graduate ITMO 544 version of the assignment, AWS infrastructure is created and deleted using **Python and boto3** rather than Bash infrastructure scripts.

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
- Lookup-history persistence
- Graceful degradation
- Unit testing with `pytest` and `moto`
- Real AWS integration testing
- Chaos testing
- Automatic EC2 replacement and recovery
- Secure networking
- Idempotent infrastructure creation
- Configuration-driven resource settings
- Secure secret handling with SSM
- Secure Gemini API key prompting with `getpass`
- Complete AWS resource cleanup

---

# 1. Project Overview

The application contains two services:

1. **Weather Service**
2. **Advisor Service**

The Weather Service accepts a U.S. ZIP code, determines its location, retrieves forecast information from the National Weather Service API, stores lookup history and cached weather data in PostgreSQL, and returns weather information.

The Advisor Service calls the Weather Service and uses Google Gemini to create a clothing recommendation based on the returned weather.

Both services run on EC2 instances behind an AWS Application Load Balancer.

---

# 2. Architecture

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
        +-------+-------+                 |
        |               |                 |
        v               v                 |
    Zippopotam       NWS API              |
        |                                 |
        +--------> Weather Data            |
                        |                  |
                        v                  |
                 PostgreSQL RDS            |
                                           |
                                           v
                                     Google Gemini
                                           |
                                           v
                                Clothing Recommendation
```

Public ALB listeners:

```text
8080 -> Weather Tier
8081 -> Advisor Tier
```

Both Node.js applications listen internally on:

```text
APP_PORT=3000
```

PostgreSQL uses:

```text
DB_PORT=5432
```

---

# 3. Request Flow

A normal Advisor request follows this path:

```text
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
```

The Advisor communicates with the Weather tier through the ALB rather than contacting a specific Weather EC2 instance.

This keeps the application compatible with Auto Scaling because a failed Weather instance can be replaced without changing the Advisor configuration.

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
|-- testing/
|   `-- app_smoke_test.py
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
|       |-- test_recovery.py
|       `-- test_smoke.py
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
|   |-- 15_smoke_test_9_of_9.png
|   |-- 16_weather_journal.png
|   |-- 17_psql_history.png
|   |-- 18_direct_vs_alb.png
|   |-- 19_gemini_fallback_error.png
|   |-- 20_gemini_restored_success.png
|   |-- 21_iam_policy_simulator.png
|   |-- 22_history_endpoint.png
|   |-- 23_advisor_web_page.png
|   |-- 24_cache_timing.png
|   |-- 25_db_failure_log.png
|   |-- 26_db_recovery.png
|   `-- 27_final_cleanup_verified.png
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

Command:

```bash
ls -R | head -40
```

The screenshot shows the main application, infrastructure, test, and documentation files used in the project.

![Project Structure](screenshots/01_project_structure.png)

---

# 5. Python Infrastructure

The main infrastructure scripts are:

```text
create_database.py
delete_database.py
create_weather_stack.py
delete_weather_stack.py
```

All AWS resource creation and deletion for the graduate version is implemented using **Python and boto3**.

AWS CLI commands are used mainly for inspection, experiments, and verification.

The Python implementation is divided into reusable modules under `stack/` rather than placing all infrastructure logic in one large script.

---

# 6. Configuration

`stack/config.py` loads deployment configuration from `.env`.

Important configuration includes:

```text
AWS_REGION
AMI_ID
KEY_NAME
INSTANCE_TYPE
APP_SECURITY_GROUP_ID

AZ_A
AZ_B

APP_PORT
DB_PORT

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
DB_INSTANCE_CLASS
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

Examples:

```text
APP_PORT=3000
DB_PORT=5432
DB_INSTANCE_CLASS=db.t4g.micro
CACHE_SECONDS=600
```

Names, ports, the RDS instance class, and cache duration are loaded from configuration rather than being hardcoded in infrastructure logic.

Secret values are not stored directly in `.env`.

---

# 7. AWS Clients

`stack/clients.py` creates boto3 clients for services including:

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

STS is used to determine the AWS account ID when IAM resource ARNs are constructed.

---

# 8. Weather Service

The Weather Service uses:

```text
Node.js
Express
PostgreSQL
AWS SDK for SSM
```

Endpoints:

```text
GET /
GET /weather?zip=ZIPCODE
GET /history
```

The service handles:

- ZIP validation
- ZIP-to-coordinate lookup
- NWS weather retrieval
- PostgreSQL caching
- lookup history
- database connectivity
- structured logging
- graceful degradation when PostgreSQL is unavailable

---

# 9. ZIP Lookup and National Weather Service APIs

The Weather Service first converts a ZIP code into geographic coordinates using the Zippopotam API.

Example:

```bash
curl -s https://api.zippopotam.us/us/60616
```

ZIP `60616` returns Chicago location information including latitude and longitude.

The Weather Service then contacts:

```text
https://api.weather.gov/points/{latitude},{longitude}
```

The `/points` response provides another URL for the actual forecast endpoint.

Therefore, two NWS-related upstream operations are required:

1. Request the NWS `/points/{lat},{lon}` endpoint to discover the correct forecast URL.
2. Request the returned forecast URL to retrieve the actual forecast-period data.

The forecast includes fields such as:

- temperature
- temperature unit
- short forecast
- wind speed
- precipitation chance
- daytime/nighttime status

A descriptive User-Agent is included in NWS requests.

## Screenshot 02 — NWS Weather API

Command:

```bash
curl -s -H "User-Agent: $UA" "$FORECAST_URL" | python3 -m json.tool | head -40
```

The returned JSON proves that the NWS forecast endpoint successfully returned weather data.

![NWS Weather API](screenshots/02_nws_weather_api.png)

---

# 10. Weather Endpoint

Main endpoint:

```text
GET /weather?zip=60616
```

Example:

```bash
curl -i "http://$ALB_DNS_NAME:8080/weather?zip=60616"
```

Example response:

```json
{
  "zip": "60616",
  "city": "Chicago",
  "state": "IL",
  "forecast": {
    "temperature": 50,
    "temperatureUnit": "F",
    "shortForecast": "Mostly Clear"
  },
  "cache": "miss"
}
```

A later request can return:

```json
{
  "cache": "hit"
}
```

---

# 11. PostgreSQL RDS Database

The Weather tier uses PostgreSQL on Amazon RDS.

The database stores:

- cached weather responses
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

The instance class is configuration-driven:

```text
DB_INSTANCE_CLASS=db.t4g.micro
```

---

# 12. Database Creation

Command:

```bash
python3 create_database.py
```

The script:

```text
1. Finds the default VPC and required subnets
2. Creates or reuses the database Security Group
3. Creates or reuses the DB subnet group
4. Generates a random database password
5. Stores the password in SSM Parameter Store
6. Creates the PostgreSQL RDS instance
7. Waits for the instance to become available
8. Saves the database endpoint for the application stack
```

## Screenshot 04 — Database Created

The creation output confirms:

```text
Database is private
Database is encrypted
Database is single-AZ
Automated backups are OFF
```

![Database Created](screenshots/04_database_created.png)

---

# 13. Database Verification

Verification command:

```bash
aws rds describe-db-instances \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --query "DBInstances[0].{Class:DBInstanceClass,Engine:Engine,MultiAZ:MultiAZ,Public:PubliclyAccessible,Encrypted:StorageEncrypted,BackupRetentionDays:BackupRetentionPeriod}" \
  --output table
```

Expected configuration:

```text
DBInstanceClass: db.t4g.micro
Engine: postgres
MultiAZ: False
PubliclyAccessible: False
StorageEncrypted: True
BackupRetentionPeriod: 0
```

Database snapshots and automated backups were also checked.

## Screenshot 05 — Database Verification

![Database Verification](screenshots/05_database_verified.png)

---

# 14. Database Security

PostgreSQL listens on the configured database port:

```text
DB_PORT=5432
```

The DB Security Group permits TCP port `5432` only from the application Security Group.

It does not expose PostgreSQL to:

```text
0.0.0.0/0
```

The live integration test also attempts to connect to the RDS host and port directly from the client machine.

The connection must fail, proving that the private RDS database cannot be reached directly from the computer running the tests.

---

# 15. Secret Storage with SSM Parameter Store

The database password is generated in Python using:

```python
secrets.token_hex(16)
```

It is stored as an SSM:

```text
SecureString
```

Parameter:

```text
/itmo-444-544/db-password
```

The Gemini API key is also stored as a SecureString:

```text
/itmo-444-544/gemini-api-key
```

Secrets are not stored in:

```text
GitHub
application source code
screenshots
EC2 user-data
plain-text environment configuration
```

## Secure Gemini Key Prompting

`create_weather_stack.py` first checks whether the configured Gemini SSM parameter already exists.

If it does not exist, the script securely prompts for the Gemini API key using:

```python
getpass.getpass("Gemini API key: ")
```

The key is then stored directly in SSM as:

```text
Type = SecureString
```

The API key is not echoed to the terminal and is not written into `.env`.

Expected missing-parameter handling is specific:

```text
ParameterNotFound
```

Unexpected AWS errors are raised rather than silently ignored.

Using SSM Parameter Store is safer because secrets are encrypted at rest, retrieved only at runtime, and protected using IAM permissions.

## Screenshot 03 — Gemini SecureString

Command:

```bash
aws ssm describe-parameters \
  --parameter-filters "Key=Name,Values=$GEMINI_PARAM_NAME" \
  --query "Parameters[].{Name:Name,Type:Type,Tier:Tier}" \
  --output table
```

Expected result:

```text
Name: /itmo-444-544/gemini-api-key
Type: SecureString
Tier: Standard
```

![Gemini SSM SecureString](screenshots/03_gemini_ssm_securestring.png)

---

# 16. PostgreSQL Cache

Configured cache duration:

```text
CACHE_SECONDS=600
```

This is approximately 10 minutes.

A first lookup can return:

```json
{
  "cache": "miss"
}
```

A repeated request can return:

```json
{
  "cache": "hit"
}
```

Caching improves response speed and reduces unnecessary upstream API calls.

The cache should not be excessively long because weather changes over time. A very long TTL could cause users to receive stale forecast information.

---

# 17. Lookup History

Successful weather requests are stored in PostgreSQL.

Endpoint:

```text
GET /history
```

Example:

```bash
curl -s "http://$ALB_DNS_NAME:8080/history" | python3 -m json.tool
```

This allows the application to display previously stored weather lookups.

---

# 18. Input and Error Handling

Invalid ZIP:

```text
123
```

returns:

```text
HTTP 400
```

Unknown ZIP:

```text
00000
```

returns:

```text
HTTP 404
```

The application does not treat invalid or unknown ZIP values as successful weather requests.

---

# 19. Advisor Service

Advisor endpoint:

```text
GET /advice?zip=60616
```

Request flow:

```text
1. Advisor calls Weather through ALB port 8080
2. Weather returns forecast information
3. Advisor retrieves the Gemini key from SSM
4. Advisor sends selected forecast information to Gemini
5. Gemini creates clothing advice
6. Advisor returns the result to the user
```

The Advisor tier does not directly access PostgreSQL.

---

# 20. Google Gemini Integration

Configured model:

```text
gemini-3.1-flash-lite
```

A successful Advisor response includes:

```json
{
  "source": "gemini",
  "model": "gemini-3.1-flash-lite"
}
```

The Advisor sends weather-related data needed to create the recommendation, such as ZIP/location and public forecast information.

No database password, AWS credential, or other AWS secret needs to be sent to Gemini.

Because the project uses a third-party AI service and a free-tier API, only the minimum data necessary for the task should be sent.

Sensitive personal or institutional information should not be included in prompts.

---

# 21. Gemini Fallback

If Gemini fails, the Advisor can still return rule-based clothing advice.

Example fallback response:

```json
{
  "source": "fallback",
  "model": null
}
```

This prevents a third-party AI failure from completely breaking the application.

A completely silent fallback would have an important weakness: operators might not realize that Gemini had stopped working.

For this reason:

```text
source = fallback
```

is returned and Gemini failures are recorded using:

```text
gemini_error
```

---

# 22. IAM Least Privilege

The Weather and Advisor tiers use separate IAM roles.

## Weather Role

Allowed to retrieve:

```text
/itmo-444-544/db-password
```

Not allowed to retrieve:

```text
/itmo-444-544/gemini-api-key
```

## Advisor Role

Allowed to retrieve:

```text
/itmo-444-544/gemini-api-key
```

Not allowed to retrieve:

```text
/itmo-444-544/db-password
```

This applies the principle of least privilege.

If the Advisor tier were compromised, the Advisor role could potentially expose its Gemini parameter, but it would not give the attacker permission to retrieve the PostgreSQL password.

---

# 23. Application Load Balancer

The ALB has two listeners:

```text
8080 -> Weather Target Group
8081 -> Advisor Target Group
```

The load balancer spans two Availability Zones.

The ALB is created before the Advisor Launch Template because Advisor user-data needs the ALB DNS name to contact the Weather Service.

---

# 24. Security Groups

## ALB Security Group

Allows public application traffic on:

```text
8080
8081
```

## Application Security Group

The configured application port:

```text
APP_PORT=3000
```

is accessible only from the ALB Security Group.

## Database Security Group

The configured PostgreSQL port:

```text
DB_PORT=5432
```

is accessible only from the application Security Group.

Using a Security Group as the source instead of a fixed IP address is important because Auto Scaling instances can be terminated and replaced with different IP addresses while remaining members of the same Security Group.

---

# 25. Launch Templates

The Weather Launch Template receives non-secret configuration such as:

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

The actual database password and Gemini API key are not inserted into EC2 user-data.

---

# 26. User-Data Size

AWS EC2 user-data must remain below the AWS size limit.

Measured sizes:

```text
Weather user-data: 13192 bytes
Advisor user-data: 11332 bytes
Maximum allowed: 16384 bytes
```

Both application Launch Templates remain below the limit.

---

# 27. Auto Scaling

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

If an application EC2 instance fails, its Auto Scaling Group can create a replacement.

Persistent lookup data is stored in RDS rather than only on EC2.

This allows the application servers to remain replaceable and mostly stateless.

---

# 28. Stack Creation

Command:

```bash
python3 create_weather_stack.py
```

If the Gemini SSM parameter does not exist, the script securely prompts:

```text
Gemini API key:
```

The typed key is hidden because Python `getpass` is used.

The Python stack then creates:

```text
IAM roles and instance profiles
ALB Security Group
Target Groups
Application Load Balancer
Listeners
Launch Templates
Auto Scaling Groups
```

## Screenshot 06 — Weather Stack Created

The screenshot shows successful creation of the main application infrastructure and the Weather and Advisor URLs.

![Weather Stack Created](screenshots/06_weather_stack_created.png)

---

# 29. Advisor Gemini Success

Command:

```bash
curl -s "http://$ALB_DNS_NAME:8081/advice?zip=60616" | python3 -m json.tool
```

Important response fields include:

```json
{
  "source": "gemini",
  "model": "gemini-3.1-flash-lite"
}
```

This proves that the Advisor successfully contacted the Weather tier and Gemini.

## Screenshot 07 — Advisor Gemini Success

![Advisor Gemini Success](screenshots/07_advisor_gemini_success.png)

---

# 30. Initial IAM Policy Verification

The IAM policies were inspected directly.

## Screenshot 08 — IAM Least Privilege

![IAM Least Privilege](screenshots/08_iam_least_privilege.png)

A later IAM Policy Simulator test provides stronger runtime policy evidence and is shown in Screenshot 21.

---

# 31. Idempotency

Infrastructure creation functions are designed so they can safely be rerun.

Examples include:

- existing Security Groups can be reused
- existing DB subnet groups can be reused
- existing SSM parameters can be reused where appropriate
- existing RDS resources can be detected
- existing IAM roles can be detected
- creation does not blindly duplicate resources
- deletion tolerates resources that are already gone

Idempotency is also tested with `moto`.

This is important because infrastructure code should move AWS toward the requested state rather than blindly creating another copy of every resource each time the script runs.

---

# 32. Unit Tests with Pytest and Moto

Unit tests use:

```text
pytest
moto
```

The non-live test command is:

```bash
pytest -q -m "not integration and not chaos"
```

Latest result after the configuration and secure-Gemini changes:

```text
27 passed, 23 deselected
```

These tests validate infrastructure behavior without requiring the live AWS stack.

---

# 33. Database Moto Tests

File:

```text
tests/unit/test_database_with_moto.py
```

The tests verify required RDS configuration including:

```text
DBInstanceClass = db.t4g.micro
Engine = PostgreSQL
AllocatedStorage = 20
BackupRetentionPeriod = 0
MultiAZ = False
PubliclyAccessible = False
StorageEncrypted = True
```

Database Security Group tests verify:

```text
Protocol = TCP
Port = configured DB_PORT
Source = Application Security Group
No public IPv4 CIDR
No public IPv6 CIDR
```

Create/delete tests also verify that database resources and the database-password parameter can be removed.

Idempotency tests verify repeated creation does not create duplicate infrastructure.

---

# 34. Integration Tests

Command used while the live stack was deployed:

```bash
pytest -q -m integration
```

The live integration tests verify behavior such as:

- ALB is active
- ALB is internet-facing
- ALB spans two Availability Zones
- listener 8080 routes to Weather
- listener 8081 routes to Advisor
- Target Groups use the configured application port
- Weather Target Group becomes healthy
- Advisor Target Group becomes healthy
- Auto Scaling Groups use ELB health checks
- Auto Scaling Groups use both configured subnets
- application port is reachable only from ALB Security Group
- PostgreSQL port is restricted to application Security Group
- RDS is private
- RDS is encrypted
- Multi-AZ is disabled
- backup retention is zero
- correct RDS instance class is used
- private RDS port cannot be reached directly from the client computer
- Weather IAM role can read only the DB secret
- Advisor IAM role can read only the Gemini secret
- IAM Policy Simulator confirms least privilege
- Weather API works
- cache behavior works
- `/history` works
- invalid ZIP returns 400
- unknown ZIP returns 404
- Advisor returns clothing advice

## Screenshot 13 — Unit and Integration Tests

![Unit and Integration Tests Passed](screenshots/13_unit_and_integration_tests_passed.png)

The screenshot records the live integration-testing evidence collected before final AWS cleanup.

---

# 35. Chaos Testing

Two important failure scenarios were tested against real AWS infrastructure.

---

## 35.1 Database Failure

For the automated chaos test:

1. PostgreSQL Security Group ingress is revoked.
2. The Weather EC2 instance is rebooted.
3. The test waits 30 seconds.
4. A new Weather request is sent.
5. Weather must still return HTTP 200.
6. The response must report:

```json
{
  "cache": "unavailable"
}
```

Restarting Weather after revoking the DB rule ensures the test does not accidentally succeed because of an already-open PostgreSQL connection.

The database rule is restored in the cleanup section of the test.

---

## 35.2 Weather EC2 Failure

Before terminating the Weather EC2 instance, the application and Target Group were verified as healthy.

### Screenshot 09 — Healthy Before Chaos

The Weather endpoint returned:

```text
HTTP 200
```

and the Target Group showed:

```text
healthy
```

![Weather Healthy Before Chaos](screenshots/09_weather_healthy_before_chaos.png)

The Weather EC2 instance was then intentionally terminated.

### Screenshot 10 — Advisor During Weather Outage

During the period when no healthy Weather target was available, the Advisor returned:

```text
HTTP 502 Bad Gateway
```

![Advisor Weather Outage](screenshots/10_advisor_weather_outage_502.png)

The Weather Auto Scaling Group launched a replacement instance.

### Screenshot 11 — Weather Recovered

The replacement instance became:

```text
healthy
```

and Weather returned:

```text
HTTP 200
```

![Weather Recovered](screenshots/11_weather_recovered_after_outage.png)

Measured recovery time:

```text
approximately 112.5 seconds
```

Required recovery objective:

```text
<= 300 seconds
```

Therefore the recovery requirement passed.

Lookup history survived because persistent application state lives in PostgreSQL RDS rather than only on the disposable EC2 instance.

---

## 35.3 Automated Chaos Test

Command:

```bash
pytest -q -m chaos -s
```

Observed evidence included:

```text
DB outage response: 200
Weather instance terminated
Advisor 502 observed: True
Weather recovery time: approximately 112.5 seconds
```

## Screenshot 12 — Chaos Tests Passed

![Chaos Tests Passed](screenshots/12_chaos_tests_passed.png)

---

# 36. Required Application Smoke Test

The required application smoke test was run from the `testing` directory.

Command:

```bash
cd testing
python3 app_smoke_test.py
```

Results included:

```text
PASS weather tier returns a forecast
PASS repeat call is answered from the database
PASS history lists the saved lookups
PASS weather tier rejects a bad zip
PASS weather tier returns 404 for an unknown zip
PASS advisor tier returns clothing advice
PASS advice came from Gemini
PASS advisor tier rejects a bad zip
PASS advisor home page loads

9 of 9 checks passed
```

A pytest integration wrapper is also present at:

```text
tests/integration/test_smoke.py
```

It runs the same standalone smoke test from pytest and fails the integration suite if the smoke script returns a non-zero status.

## Screenshot 15 — Application Smoke Test

![Application Smoke Test - 9 of 9 Passed](screenshots/15_smoke_test_9_of_9.png)

---

# 37. Weather Journal and Structured Logging

The Weather Service journal was inspected from the running Weather EC2 instance.

Example command:

```bash
ssh -i /Hchaudhary1/Step04_AWS_CLI_EC2/ITMO-444-544-lab-keypair.pem \
  ec2-user@"$WEATHER_IP" \
  "sudo journalctl -u weather -n 20 --no-pager"
```

The logs contain structured events such as:

```text
weather_request
weather_success
weather_rejected
db_error
```

A `weather_success` event contains information including:

- ZIP code
- cache status
- request time in milliseconds

Example observations:

```text
ZIP 10001 -> cache miss -> approximately 283 ms
ZIP 90210 -> cache miss -> approximately 121 ms
ZIP 60616 -> cache hit  -> approximately 1 ms
```

A `weather_success` event means the Weather Service successfully processed the ZIP request and returned forecast data.

The cache field also shows whether the result came from PostgreSQL cache or required upstream API work.

## Screenshot 16 — Weather Journal

![Weather Journal](screenshots/16_weather_journal.png)

---

# 38. Direct PostgreSQL Verification

The `lookups` table was queried directly using `psql` from the Weather EC2 instance.

The password was retrieved securely from SSM and was not printed.

Example query:

```sql
SELECT id, zip, created_at
FROM lookups
ORDER BY id DESC
LIMIT 5;

SELECT count(*) AS saved_lookups
FROM lookups;
```

The query showed saved records including:

```text
60616
10001
90210
```

This confirmed that lookup data was actually stored in PostgreSQL.

## Screenshot 17 — PostgreSQL History

![PostgreSQL Lookup History](screenshots/17_psql_history.png)

---

# 39. Direct Instance Access vs ALB

A direct request to the Weather EC2 instance on application port `3000` was tested:

```bash
curl -m 5 -s -o /dev/null -w "direct: %{http_code}\n" \
  "http://${WEATHER_IP}:3000/"
```

Result:

```text
direct: 000
direct: no answer (good)
```

The same service through the ALB returned:

```text
through ALB: 200
```

This proves application traffic must pass through the ALB instead of reaching the EC2 application directly.

Using a Security Group reference rather than a fixed IP rule is important because Auto Scaling replacement instances may receive different IP addresses.

## Screenshot 18 — Direct vs ALB

![Direct Access vs ALB](screenshots/18_direct_vs_alb.png)

---

# 40. Gemini Failure Experiment

The Gemini credential was intentionally made invalid for the experiment.

Advisor requests returned rule-based fallback advice.

Example:

```text
fallback - Wear a warm jacket and long pants.
```

The Advisor logs recorded:

```text
event: gemini_error
status: 400
reason: gemini_http_error
```

This proves that the application detected the external AI failure while still returning useful fallback advice.

A weakness of a completely silent fallback would be that operators might not realize Gemini had stopped working.

Returning a `source` value and recording `gemini_error` makes the failure visible.

## Screenshot 19 — Gemini Failure and Fallback

![Gemini Failure and Fallback](screenshots/19_gemini_fallback_error.png)

---

# 41. Gemini Recovery

After the real Gemini API key was restored, the Advisor returned:

```json
{
  "source": "gemini",
  "model": "gemini-3.1-flash-lite"
}
```

This confirmed recovery of the AI integration.

## Screenshot 20 — Gemini Restored

![Gemini Service Restored](screenshots/20_gemini_restored_success.png)

---

# 42. IAM Policy Simulator Verification

The AWS IAM Policy Simulator was used to verify both roles against both secrets.

Results:

```text
===== itmo-444-544-weather-role =====
DB password access : allowed
Gemini key access  : implicitDeny

===== itmo-444-544-advisor-role =====
DB password access : implicitDeny
Gemini key access  : allowed
```

This gives stronger evidence of least privilege than only inspecting IAM policy documents.

The automated live integration test performs the same logical verification with:

```python
iam.simulate_principal_policy(...)
```

The test verifies:

```text
Weather role + DB password      -> allowed
Weather role + Gemini key       -> not allowed
Advisor role + Gemini key       -> allowed
Advisor role + DB password      -> not allowed
```

## Screenshot 21 — IAM Policy Simulator

![IAM Policy Simulator](screenshots/21_iam_policy_simulator.png)

---

# 43. `/history` Endpoint Verification

Command:

```bash
curl -s "http://${ALB_DNS_NAME}:8080/history" | python3 -m json.tool
```

The endpoint returned saved lookup records including examples such as:

```text
60616 -> Chicago, IL
90210 -> Beverly Hills, CA
10001 -> New York City, NY
```

This proves that the Weather Service can read previously stored lookup records from PostgreSQL.

## Screenshot 22 — History Endpoint

![Weather History Endpoint](screenshots/22_history_endpoint.png)

---

# 44. Advisor Web Interface

The Advisor browser page was tested using ZIP code:

```text
60616
```

The page displayed:

```text
Chicago, IL 60616
Weather information
Gemini clothing recommendation
Suggestion source: gemini
```

This verifies the user-facing application in addition to the JSON `/advice` API.

## Screenshot 23 — Advisor Web Page

![Weather Advisor Web Page](screenshots/23_advisor_web_page.png)

---

# 45. Cache Timing Experiment

Two consecutive Weather requests were made for ZIP:

```text
94105
```

Results:

```text
request 1: HTTP 200, time 0.609200s
request 2: HTTP 200, time 0.075543s
cache = hit
```

The first request was slower because the Weather Service needed to perform upstream API work and store the response.

The second request was much faster because the result was available from PostgreSQL cache.

A short cache reduces repeated upstream requests and improves response time.

A very long cache TTL would risk serving stale weather information.

## Screenshot 24 — Cache Timing

![Cache Timing Comparison](screenshots/24_cache_timing.png)

---

# 46. Database-Outage Experiment

Database access was intentionally interrupted by removing PostgreSQL Security Group ingress.

The Weather Service was restarted so it could not continue using an already-established database connection.

A request for ZIP `30301` returned:

```text
city = Atlanta
cache = unavailable
```

This shows that the Weather Service could still obtain fresh upstream weather information even though PostgreSQL was unavailable.

The `/history` endpoint returned:

```text
HTTP 503
```

because history requires PostgreSQL.

The Weather journal recorded:

```text
event: db_error
stage: read
message: Connection terminated due to connection timeout
```

The application temporarily pauses repeated database attempts after detecting a connection problem.

This prevents each incoming request during the outage from repeatedly waiting for the same database timeout.

## Screenshot 25 — Database Failure

![PostgreSQL Failure and Graceful Degradation](screenshots/25_db_failure_log.png)

---

# 47. Database Recovery

The PostgreSQL Security Group rule was restored.

After recovery, a repeated request returned:

```text
cache = hit
```

This confirmed PostgreSQL connectivity and caching recovered successfully.

Persistent lookup data remains in RDS instead of on a particular EC2 instance.

## Screenshot 26 — Database Recovery

![PostgreSQL Recovery](screenshots/26_db_recovery.png)

---

# 48. Why the 30-Second Database Pause Helps

Without temporary database-failure suppression, every incoming request during a PostgreSQL outage could try to open another database connection and wait for a timeout.

That could cause:

- unnecessary latency
- repeated failing connections
- wasted resources
- poor user experience

After detecting database failure, the Weather Service temporarily avoids repeatedly attempting PostgreSQL access.

This allows requests to continue using fresh upstream weather data.

After the pause expires, PostgreSQL can be tried again.

The automated chaos test also includes a 30-second wait after revoking database access and rebooting Weather so the application is fully restarted under the failed database condition before the degraded-response assertion is made.

---

# 49. Backup-Retention Tradeoff

For this lab, RDS uses:

```text
BackupRetentionPeriod = 0
```

Deletion uses:

```text
SkipFinalSnapshot = True
DeleteAutomatedBackups = True
```

This reduces storage usage and simplifies cleanup for a temporary lab.

The tradeoff is that there is:

- no automated restore point
- no point-in-time recovery
- no final database snapshot

This is appropriate for disposable classroom data.

It would generally be inappropriate for an important production database because accidental deletion or corruption could permanently destroy valuable data.

---

# 50. Data Sent to Gemini and Privacy Considerations

The Advisor sends only weather-related information needed to generate clothing advice.

Examples include:

```text
ZIP/location
city/state
temperature
forecast
wind
precipitation-related information
```

The application does not need to send:

```text
database password
AWS credentials
Gemini API key
private RDS information
unrelated personal information
```

Because Gemini is an external AI provider, the safest design is to send only the minimum information required.

Free or consumer AI tiers can have different data-retention and product-improvement policies than private enterprise services.

For a production or institutional system, privacy, retention, training, regional-processing, and contractual policies should be reviewed before sending sensitive data.

---

# 51. Security Review Questions

## 51.1 Why store secrets in SSM instead of source code or `.env`?

SSM Parameter Store allows secrets to be encrypted as `SecureString` values and protected using IAM.

If credentials were committed to GitHub or stored directly in source code, repository history could preserve them even after the current file was changed.

The Gemini API key is entered through `getpass`, so it is not displayed in the terminal or stored in `.env`.

Runtime secret retrieval reduces unnecessary exposure.

---

## 51.2 What would change if the IAM role had `ssm:*` permissions?

Giving a role:

```text
ssm:*
```

would violate least privilege.

A compromised service could potentially list, read, modify, or delete unrelated SSM parameters.

The correct approach is to allow only:

```text
ssm:GetParameter
```

for the specific parameter ARN required by that tier.

---

## 51.3 Why is the ALB public but the application instances are not?

The ALB is the controlled public entry point.

Application instances accept port `3000` traffic only from the ALB Security Group.

This prevents clients from bypassing the load balancer.

---

## 51.4 Why is the database not public?

Only the Weather tier needs PostgreSQL access.

The RDS database therefore uses:

```text
PubliclyAccessible = False
```

and PostgreSQL access is restricted to the application Security Group.

The live integration test also verifies that the RDS port is not reachable directly from the client computer.

---

## 51.5 What is the weakness of using one application Security Group for both services?

If Weather and Advisor share the same application Security Group, a database rule trusting the entire application Security Group technically allows network-level database connectivity from both types of instance.

IAM still prevents Advisor from retrieving the DB password, but stronger production isolation would use:

```text
ALB SG
Weather SG
Advisor SG
Database SG
```

and permit PostgreSQL only from the Weather SG.

---

## 51.6 Should the application use the RDS master database user?

A stronger production design would create a dedicated application database user with only the required permissions instead of using a highly privileged database account.

For example:

```text
SELECT
INSERT
UPDATE
```

on only the required tables.

---

## 51.7 Why use `sslmode=verify-full`?

`verify-full` verifies both encryption and server identity.

Encryption without server certificate and hostname validation can still leave a connection vulnerable to certain man-in-the-middle attacks.

---

## 51.8 Why use SQL parameters/placeholders?

Parameterized SQL separates user-supplied data from SQL commands.

This helps prevent SQL injection.

---

## 51.9 What is the risk of backup retention being zero?

A retention period of zero means there is no automated point-in-time recovery.

This is acceptable for temporary lab data but not a good production default.

---

## 51.10 Who should control the lifecycle of stored weather lookup data?

The organization operating the application should define data retention according to business need, privacy requirements, and storage policy.

---

## 51.11 Can AI output create an XSS risk?

Yes.

AI-generated output should be treated as untrusted external content.

Model-generated text should be escaped or safely rendered rather than directly inserted as raw HTML.

---

## 51.12 What changes if Gemini is used through a paid school or enterprise account?

The architecture could remain similar, but privacy, retention, governance, and contractual terms could differ.

Those terms should be checked rather than assumed.

---

## 51.13 How could the public application be protected against abuse?

Possible protections include:

- rate limiting
- AWS WAF
- authentication
- API quotas
- request-size limits
- monitoring
- alarms
- abuse detection

---

## 51.14 Why label fallback and cache-unavailable states?

Graceful degradation is useful, but hidden degradation is difficult to monitor.

Values such as:

```text
source = fallback
cache = unavailable
```

make degraded behavior visible to users, logs, automated tests, and monitoring.

---

# 52. Moto Limitations and Real AWS Test Coverage

Moto is useful because it allows Python AWS infrastructure logic to be tested without creating live AWS resources.

Moto is used to verify things such as:

- configuration parsing
- required configuration values
- IAM policy construction
- RDS creation parameters
- RDS instance class
- Security Group rules
- SSM parameter behavior
- database creation/deletion
- idempotency
- user-data contents
- user-data secret exclusion
- user-data size

However, Moto is an AWS API emulator. It cannot prove many behaviors that depend on the real AWS control plane, actual networking, operating-system startup, or external services.

The gaps are covered by live integration and chaos tests as follows:

| Moto cannot fully prove | Real test/evidence that covers the gap |
|---|---|
| Actual ALB creation and AWS state | `test_load_balancer_is_public_and_spans_two_azs` |
| Real listener forwarding | `test_listeners_forward_to_correct_target_groups` |
| Real Target Group configuration and health | `test_target_groups_use_expected_health_checks` and `test_every_target_becomes_healthy` |
| Real EC2 application startup from user-data | Healthy Target Groups plus live application endpoint tests |
| Real Auto Scaling configuration | `test_asgs_use_elb_health_and_two_subnets` |
| Real application network isolation | `test_app_port_is_reachable_only_from_alb` and Screenshot 18 |
| Real RDS configuration | `test_database_is_private_encrypted_single_az_no_backups` |
| Real PostgreSQL network isolation | `test_database_port_not_reachable_from_client` |
| Real IAM policy evaluation | `test_iam_policy_simulator_enforces_least_privilege` |
| Real Weather API behavior | `test_weather_valid_zip_returns_forecast` |
| Real PostgreSQL cache behavior | `test_weather_second_lookup_can_use_cache` |
| Real lookup-history behavior | `test_weather_history_returns_rows` and direct `psql` evidence |
| Real Advisor behavior | `test_advisor_returns_advice` |
| External Gemini availability | Advisor response evidence and Gemini failure/recovery experiment |
| Database outage behavior | `test_weather_survives_database_outage` |
| Real Auto Scaling replacement | `test_weather_instance_failure_causes_502_then_recovers` |
| Real AWS recovery time | Same EC2 chaos test measures recovery and enforces `<= 300` seconds |
| Full application workflow | `testing/app_smoke_test.py` and `tests/integration/test_smoke.py` |

Therefore, Moto is used for fast infrastructure logic testing, while live integration and chaos tests prove the behaviors Moto cannot emulate.

---

# 53. Python vs Bash for the Same Infrastructure Task

One direct comparison is **creating an RDS database**.

With Bash and AWS CLI, creation would require commands such as:

```bash
aws rds create-db-instance ...
```

along with separate commands to:

- find the VPC
- find subnets
- create the Security Group
- authorize PostgreSQL ingress
- create the DB subnet group
- generate/store the password
- wait for RDS
- inspect error codes
- detect already-existing resources

This works for a small manual procedure, but handling all of the dependencies and repeated-run cases in Bash becomes difficult.

In this project, the same operation is implemented using Python and boto3.

Python makes it easier to:

- split each resource operation into a reusable function
- parse boto3 response dictionaries directly
- catch specific `ClientError` codes
- validate configuration before creating resources
- implement idempotent behavior
- generate a password using `secrets.token_hex`
- store the secret directly in SSM
- write automated Moto tests
- reuse the same Settings object across the stack
- perform cleanup using corresponding Python functions

For example, an already-missing Security Group can be handled by checking the AWS error code rather than ignoring every error.

Similarly, `ParameterNotFound` can be handled as an expected condition while unrelated SSM failures are still raised.

Bash remains useful for short verification commands such as:

```bash
aws rds describe-db-instances
```

but Python is more suitable for the full graduate infrastructure implementation because it provides stronger structure, testing, configuration handling, and error management.

---

# 54. Python Error Handling and Documentation

Infrastructure functions use focused AWS error handling.

Expected missing/existing-resource cases are handled using specific AWS error codes where appropriate.

Examples include:

```text
ParameterNotFound
DBSubnetGroupNotFoundFault
InvalidGroup.NotFound
InvalidPermission.Duplicate
```

Unexpected AWS errors should still be raised so actual infrastructure failures are visible.

This is safer than using:

```python
except ClientError:
    pass
```

because a broad exception handler could accidentally hide permissions errors, invalid configuration, API failures, or other problems.

Functions are kept focused and include docstrings so creation and deletion behavior can be independently understood and tested.

---

# 55. Stack Deletion

Command:

```bash
python3 delete_weather_stack.py
```

Application-stack cleanup removes resources such as:

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
related application resources
```

The final cleanup also removes the Gemini SSM parameter:

```text
/itmo-444-544/gemini-api-key
```

---

# 56. Database Deletion

Command:

```bash
python3 delete_database.py
```

Database cleanup removes:

- RDS database instance
- DB subnet group
- DB Security Group
- database-password SSM parameter
- automated backups
- local database output information

Database deletion uses:

```text
SkipFinalSnapshot=True
DeleteAutomatedBackups=True
```

The DB password parameter:

```text
/itmo-444-544/db-password
```

is also removed during final cleanup.

---

# 57. Final Cleanup Verification

After all testing was complete, the application and database resources were deleted.

Verification commands included:

```bash
aws rds describe-db-instances \
  --query "DBInstances[].DBInstanceIdentifier"

aws rds describe-db-snapshots \
  --query "DBSnapshots[].DBSnapshotIdentifier"

aws rds describe-db-instance-automated-backups \
  --query "DBInstanceAutomatedBackups[].DBInstanceIdentifier"

aws elbv2 describe-load-balancers \
  --query "LoadBalancers[].LoadBalancerName"

aws iam list-roles \
  --query "Roles[?starts_with(RoleName, 'itmo-444-544')].RoleName"
```

Expected final result:

```text
[]
[]
[]
[]
[]
```

This proves that no assignment RDS instance, RDS snapshot, automated backup, load balancer, or ITMO lab IAM role remained.

## Screenshot 27 — Final Cleanup Verification

![Final Cleanup Verified](screenshots/27_final_cleanup_verified.png)

---

# 58. Screenshot Evidence

| No. | Screenshot | What It Proves |
|---|---|---|
| 01 | `01_project_structure.png` | Final Weather Advisor project structure |
| 02 | `02_nws_weather_api.png` | NWS API successfully returns forecast information |
| 03 | `03_gemini_ssm_securestring.png` | Gemini key stored as an SSM SecureString |
| 04 | `04_database_created.png` | PostgreSQL RDS database successfully created |
| 05 | `05_database_verified.png` | Required RDS configuration |
| 06 | `06_weather_stack_created.png` | ALB, Target Groups, listeners, Launch Templates, and ASGs created |
| 07 | `07_advisor_gemini_success.png` | Advisor successfully generated Gemini advice |
| 08 | `08_iam_least_privilege.png` | Initial IAM policy configuration |
| 09 | `09_weather_healthy_before_chaos.png` | Weather healthy before EC2 failure |
| 10 | `10_advisor_weather_outage_502.png` | Advisor returned 502 during Weather outage |
| 11 | `11_weather_recovered_after_outage.png` | Replacement Weather instance became healthy |
| 12 | `12_chaos_tests_passed.png` | Automated chaos tests passed |
| 13 | `13_unit_and_integration_tests_passed.png` | Unit/Moto and integration testing evidence |
| 15 | `15_smoke_test_9_of_9.png` | Required application smoke test passed 9/9 |
| 16 | `16_weather_journal.png` | Structured Weather logs and cache hit/miss timing |
| 17 | `17_psql_history.png` | Lookup records stored directly in PostgreSQL |
| 18 | `18_direct_vs_alb.png` | Direct instance application access blocked while ALB works |
| 19 | `19_gemini_fallback_error.png` | Invalid Gemini credential triggers fallback and `gemini_error` |
| 20 | `20_gemini_restored_success.png` | Gemini restored successfully |
| 21 | `21_iam_policy_simulator.png` | Both roles tested against both secrets |
| 22 | `22_history_endpoint.png` | `/history` successfully reads PostgreSQL records |
| 23 | `23_advisor_web_page.png` | User-facing Advisor page displays recommendation |
| 24 | `24_cache_timing.png` | Cache-hit request is faster than initial request |
| 25 | `25_db_failure_log.png` | DB outage causes `cache=unavailable`, `/history` 503, and `db_error` |
| 26 | `26_db_recovery.png` | PostgreSQL recovered and cache returned `hit` |
| 27 | `27_final_cleanup_verified.png` | Final AWS cleanup verification |

---

# 59. Test Results and Current Status

## Latest Local Non-Live Test Run

After the configuration and secure Gemini-key changes:

```bash
pytest -q -m "not integration and not chaos"
```

Result:

```text
27 passed, 23 deselected
```

This confirms the current Python code still passes the non-live test suite.

## Live Evidence Collected Before Cleanup

The AWS stack was previously deployed and tested using:

- integration tests
- chaos experiments
- smoke testing
- manual API verification
- IAM Policy Simulator
- direct PostgreSQL verification
- journal inspection

Application smoke test:

```text
9 of 9 checks passed
```

Measured Weather recovery:

```text
approximately 112.5 seconds
```

Required recovery objective:

```text
<= 300 seconds
```

The AWS stack was then deleted and final cleanup was verified.

Because the stack has been removed, live integration and chaos tests are not rerun after code-only documentation/configuration improvements unless the infrastructure is recreated.

---

# 60. Graduate ITMO 544 Checklist

## Python Infrastructure

- [x] `create_database.py`
- [x] `delete_database.py`
- [x] `create_weather_stack.py`
- [x] `delete_weather_stack.py`
- [x] Infrastructure implemented using Python and boto3
- [x] Python code split into reusable modules
- [x] Required PostgreSQL RDS configuration
- [x] RDS instance class loaded from configuration
- [x] Application port loaded from configuration
- [x] Database port loaded from configuration
- [x] Cache duration loaded from configuration
- [x] Password generated with `secrets.token_hex(16)`
- [x] DB password stored in SSM SecureString
- [x] Gemini key stored in SSM SecureString
- [x] Gemini key securely prompted with `getpass`
- [x] Gemini key not echoed to terminal
- [x] Gemini key not stored in `.env`
- [x] Weather role restricted to DB secret
- [x] Advisor role restricted to Gemini secret
- [x] IAM Policy Simulator verification
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
- [x] Safe repeated deletion behavior
- [x] No secrets committed to GitHub
- [x] Specific AWS error handling used for expected conditions

## Application Verification

- [x] NWS API response verified
- [x] Two-step NWS request flow explained
- [x] Weather endpoint verified
- [x] Advisor JSON verified
- [x] Advisor browser page verified
- [x] Application smoke test passed 9/9
- [x] Smoke test also wrapped in pytest integration test
- [x] Invalid ZIP returns 400
- [x] Unknown ZIP returns 404
- [x] Weather journal inspected
- [x] `weather_success` explained
- [x] `/history` endpoint verified
- [x] PostgreSQL verified directly with `psql`
- [x] Cache miss/hit timing tested
- [x] Cache TTL tradeoff explained

## Security

- [x] RDS is private
- [x] RDS is encrypted
- [x] Multi-AZ disabled as required
- [x] Automated backup retention set to zero as required
- [x] PostgreSQL port limited to application SG
- [x] Application port limited to ALB SG
- [x] Direct EC2 application access blocked
- [x] Direct RDS port access from client tested and blocked
- [x] Security Group source behavior explained
- [x] IAM least privilege verified for both roles and both secrets
- [x] SSM secret-storage advantages explained
- [x] Backup-retention tradeoff explained
- [x] Third-party AI privacy considerations discussed

## Failure Experiments

- [x] Gemini credential intentionally invalidated
- [x] Fallback response verified
- [x] `gemini_error` logs verified
- [x] Silent-fallback weakness explained
- [x] Gemini restored successfully
- [x] Database connectivity intentionally interrupted
- [x] Weather restarted during DB chaos test
- [x] Weather remained available
- [x] `cache = unavailable` verified
- [x] `/history` returned 503 during DB outage
- [x] `db_error` journal entry verified
- [x] 30-second DB-outage pause explained
- [x] Database access restored
- [x] Cache recovery verified
- [x] Weather EC2 intentionally terminated
- [x] Advisor returned 502 during Weather outage
- [x] Auto Scaling launched replacement
- [x] Weather recovered within 300 seconds
- [x] Persistent state location explained

## Unit / Moto Tests

- [x] `db.t4g.micro`
- [x] Backup retention = 0
- [x] Multi-AZ = false
- [x] Publicly accessible = false
- [x] Storage encrypted = true
- [x] DB Security Group restricts configured database port
- [x] No public DB CIDR
- [x] Database create/delete tested
- [x] Password parameter behavior tested
- [x] IAM policy behavior tested
- [x] Advisor user-data contains ALB DNS
- [x] Weather user-data contains DB host
- [x] Secrets absent from user-data
- [x] User-data size tested
- [x] Idempotency tested
- [x] Moto limitations explained
- [x] Each major Moto limitation mapped to live integration/chaos coverage

## Integration Tests

- [x] ALB state and two AZs checked
- [x] Listener forwarding checked
- [x] Target Group health configuration checked
- [x] Target Groups become healthy
- [x] Auto Scaling Groups checked
- [x] Weather endpoint works
- [x] Cache hit behavior verified
- [x] `/history` verified
- [x] Invalid ZIP returns 400
- [x] Unknown ZIP returns 404
- [x] Advisor returns clothing advice
- [x] Application instances protected behind ALB
- [x] Database not publicly reachable
- [x] RDS configuration verified
- [x] IAM policy documents verified
- [x] IAM Policy Simulator verifies least privilege
- [x] Application smoke test integrated with pytest

## Cleanup

- [x] Auto Scaling Groups removed
- [x] Application Load Balancer removed
- [x] Target Groups removed
- [x] Launch Templates removed
- [x] IAM roles/profiles removed
- [x] RDS instance removed
- [x] DB subnet group removed
- [x] RDS snapshots verified empty
- [x] Automated backups verified empty
- [x] DB password parameter removed
- [x] Gemini API-key parameter removed during final cleanup
- [x] Final cleanup verified using AWS CLI

---

# 61. Final Result

The Weather Advisor project demonstrates a complete cloud application including infrastructure, application logic, security, testing, observability, failure recovery, and cleanup.

The solution includes:

```text
Python + boto3 infrastructure automation
Configuration-driven resource settings
Two application tiers
Application Load Balancer
Two listeners
Two Target Groups
Two Auto Scaling Groups
PostgreSQL on Amazon RDS
PostgreSQL-backed caching
Persistent lookup history
Zippopotam API
National Weather Service API
Google Gemini
SSM SecureString secrets
Secure getpass Gemini-key input
Least-privilege IAM
IAM Policy Simulator verification
Secure Security Groups
Private RDS network verification
Structured application logs
Graceful database degradation
Gemini fallback behavior
Moto unit testing
Real AWS integration testing
Application smoke testing
Chaos testing
Automatic EC2 recovery
Idempotent infrastructure
Specific AWS ClientError handling
Python-based deletion
Final AWS cleanup verification
```

Latest non-live test result:

```text
27 passed, 23 deselected
```

Application smoke-test evidence:

```text
9 of 9 checks passed
```

Measured Weather recovery:

```text
approximately 112.5 seconds
```

Required recovery objective:

```text
<= 300 seconds
```

The project demonstrates that the Weather and Advisor tiers operate correctly during normal conditions, degrade safely during database and AI-provider failures, recover from EC2 failure through Auto Scaling, protect secrets using SSM and IAM, and can be completely removed from AWS after the assignment.
