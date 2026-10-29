# Step08 — Weather Advisor in the Cloud

## ITMO 444 / ITMO 544 — Cloud Computing

This project implements a complete two-tier cloud application called **Weather Advisor** using Python, AWS, Node.js, PostgreSQL, external weather APIs, Google Gemini, `pytest`, and `moto`.

For the graduate ITMO 544 version of the lab, the cloud infrastructure is created and deleted using **Python and boto3** rather than Bash.

The project demonstrates:

- Python-based infrastructure automation
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
- Unit testing with pytest and moto
- Real AWS integration testing
- Chaos testing
- Automatic EC2 replacement and recovery
- Secure network design
- Automated infrastructure cleanup

---

# 1. Project Overview

The application contains two main services:

1. **Weather Service**
2. **Advisor Service**

The Weather service accepts a US ZIP code and retrieves forecast information.

The Advisor service calls the Weather service and uses the returned weather information to generate clothing recommendations using Google Gemini.

Both services run on EC2 instances behind an AWS Application Load Balancer.

---

# 2. High-Level Architecture

```text
                           Internet
                              |
                              v
                  Application Load Balancer
                              |
               +--------------+--------------+
               |                             |
               |                             |
        Listener Port 8080            Listener Port 8081
               |                             |
               v                             v
        Weather Target Group          Advisor Target Group
               |                             |
               v                             v
        Weather EC2 Instance          Advisor EC2 Instance
               |                             |
       +-------+-------+                     |
       |               |                     |
       v               v                     |
 Zippopotam API     NWS API                  |
       |                                     |
       +----------> Weather Data              |
                     |                        |
                     v                        |
               PostgreSQL RDS                |
                     |                        |
                     +------------------------+
                              |
                              v
                         Advisor Tier
                              |
                              v
                       Google Gemini API
                              |
                              v
                     Clothing Recommendation
```

The public ALB listener ports are:

```text
8080 -> Weather Tier
8081 -> Advisor Tier
```

Both applications run internally on:

```text
Port 3000
```

---

# 3. Application Request Flow

A normal Advisor request follows this path:

```text
User
 |
 v
Application Load Balancer
 |
 v
Advisor Service
 |
 v
Weather Service through ALB port 8080
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

---

# 4. Why Two Application Tiers?

The application is separated into two tiers so each service has a clear responsibility.

## Weather Tier

The Weather Tier handles:

- ZIP-code validation
- ZIP-to-location conversion
- NWS forecast retrieval
- PostgreSQL caching
- Weather lookup history
- Database connectivity
- Graceful behavior when PostgreSQL is unavailable

## Advisor Tier

The Advisor Tier handles:

- Calling the Weather service
- Retrieving the Gemini API key securely
- Sending forecast information to Gemini
- Returning clothing recommendations
- Falling back to rule-based advice if Gemini fails

Separating these responsibilities improves:

- security
- maintainability
- scalability
- testing
- fault isolation
- service independence

---

# 5. Main AWS Resources

The project creates and manages the following AWS resources.

## Networking

- Default VPC
- Subnets in two Availability Zones
- Application Load Balancer Security Group
- Application EC2 Security Group
- PostgreSQL Database Security Group

## Load Balancing

- Application Load Balancer
- Weather Target Group
- Advisor Target Group
- Weather listener on port `8080`
- Advisor listener on port `8081`

## Compute

- Weather Launch Template
- Advisor Launch Template
- Weather Auto Scaling Group
- Advisor Auto Scaling Group
- Weather EC2 instance
- Advisor EC2 instance

## IAM

- Weather IAM Role
- Weather Instance Profile
- Advisor IAM Role
- Advisor Instance Profile
- Least-privilege inline IAM policies

## Database

- PostgreSQL RDS instance
- DB Subnet Group
- DB Security Group
- Secure database password stored in SSM

## Secrets

- PostgreSQL password stored as SecureString
- Gemini API key stored as SecureString

---

# 6. Project Structure

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
|   `-- storage.py
|
|-- tests/
|   |-- conftest.py
|   |-- helpers.py
|   |
|   |-- unit/
|   |   |-- test_config.py
|   |   |-- test_policies.py
|   |   |-- test_stack_with_moto.py
|   |   `-- test_user_data.py
|   |
|   `-- integration/
|       |-- test_application.py
|       |-- test_infrastructure.py
|       `-- test_recovery.py
|
|-- create_database.py
|-- delete_database.py
|-- create_weather_stack.py
|-- delete_weather_stack.py
|-- pytest.ini
|-- requirements.txt
|-- README.md
|-- SUBMISSION_NOTES.md
|-- .gitignore
`-- screenshots/
```

## Proof — Project Layout

![Project Folder Layout](screenshots/01_project_structure.png)

---

# 7. Python Infrastructure Design

The infrastructure is divided into small Python modules.

This makes the code easier to:

- understand
- test
- reuse
- debug
- modify
- validate independently

---

# 8. `stack/config.py`

This module loads and validates configuration from `.env`.

Important base configuration includes:

```text
AWS_REGION
AMI_ID
KEY_NAME
INSTANCE_TYPE
APP_SECURITY_GROUP_ID
AZ_A
AZ_B
```

Weather configuration includes:

```text
WEATHER_ROLE_NAME
WEATHER_PROFILE_NAME
WEATHER_LT_NAME
WEATHER_TG_NAME
WEATHER_ASG_NAME
WEATHER_LISTENER_PORT
```

Advisor configuration includes:

```text
ADVISOR_ROLE_NAME
ADVISOR_PROFILE_NAME
ADVISOR_LT_NAME
ADVISOR_TG_NAME
ADVISOR_ASG_NAME
ADVISOR_LISTENER_PORT
```

Database settings include:

```text
DB_INSTANCE_ID
DB_NAME
DB_USER
DB_SG_NAME
DB_SUBNET_GROUP_NAME
DB_PASSWORD_PARAM
CACHE_SECONDS
```

Gemini settings include:

```text
GEMINI_PARAM_NAME
GEMINI_MODEL
KEY_CACHE_SECONDS
```

The module also validates that required settings are present.

---

# 9. `stack/clients.py`

This module creates all boto3 clients in one central place.

AWS services used include:

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

STS is used to automatically determine the AWS account ID.

---

# 10. `stack/policies.py`

This module defines IAM policy documents.

The trust policy allows:

```text
EC2 service
```

to assume the application roles.

The Weather role receives permission only for:

```text
ssm:GetParameter
```

on:

```text
/itmo-444-544/db-password
```

The Advisor role receives permission only for:

```text
ssm:GetParameter
```

on:

```text
/itmo-444-544/gemini-api-key
```

---

# 11. `stack/storage.py`

This module manages:

- IAM roles
- inline IAM policies
- instance profiles
- role/profile deletion

It creates exact SSM parameter ARNs using:

```text
AWS Region
AWS Account ID
Parameter Name
```

---

# 12. `stack/network.py`

This module manages networking.

It:

- finds the default VPC
- finds subnets in two Availability Zones
- creates the ALB Security Group
- allows ALB ports `8080` and `8081`
- restricts application port `3000`
- permits port `3000` only from the ALB Security Group

---

# 13. `stack/balancer.py`

This module manages:

- Weather Target Group
- Advisor Target Group
- Application Load Balancer
- listeners
- ALB health checks
- ALB deletion
- Target Group deletion

Health-check configuration includes:

```text
Protocol: HTTP
Health Check Path: /
Health Check Port: traffic-port
Health Check Interval: 10 seconds
Health Check Timeout: 5 seconds
Healthy Threshold: 2
Unhealthy Threshold: 2
Expected HTTP Code: 200
```

The code waits for the Application Load Balancer to become available before continuing.

This is important because the Advisor user-data requires the ALB DNS name.

---

# 14. `stack/compute.py`

This module creates:

- EC2 user-data
- Launch Template configuration

Weather user-data includes:

```text
AWS_REGION
PORT
DB_HOST
DB_NAME
DB_USER
DB_PASSWORD_PARAM
CACHE_SECONDS
NWS_USER_AGENT
```

Advisor user-data includes:

```text
AWS_REGION
PORT
WEATHER_URL
GEMINI_KEY_PARAM
GEMINI_MODEL
KEY_CACHE_SECONDS
```

Application files are embedded into user-data using base64 encoding.

---

# 15. EC2 User-Data Size

EC2 user-data has a size limit.

The lab requires user-data to stay below:

```text
16 KB
```

The generated scripts were measured before deployment.

Observed results:

```text
Weather user-data bytes: 13192
Advisor user-data bytes: 11332
16 KB limit: 16384
Weather under limit: True
Advisor under limit: True
```

Therefore both user-data scripts meet the requirement.

---

# 16. `stack/scaling.py`

This module manages:

- Weather Auto Scaling Group
- Advisor Auto Scaling Group
- ASG updates
- ASG cleanup

Each Auto Scaling Group uses:

```text
Minimum Capacity: 1
Maximum Capacity: 1
Desired Capacity: 1
HealthCheckType: ELB
```

Each ASG spans two subnets.

Instance Name tags are:

```text
weather-app
advisor-app
```

---

# 17. `stack/database.py`

This module manages PostgreSQL infrastructure.

It creates:

- Database Security Group
- DB Subnet Group
- Secure password
- SSM SecureString parameter
- PostgreSQL RDS instance

It also implements database cleanup.

The password is generated automatically using Python instead of being manually hardcoded.

---

# 18. `stack/runner.py`

This module controls the creation and deletion order.

Application stack creation follows this sequence:

```text
1. AWS account lookup
2. VPC lookup
3. Subnet lookup
4. Database endpoint lookup
5. Weather IAM role
6. Advisor IAM role
7. Instance profiles
8. ALB Security Group
9. Application Security Group restriction
10. Target Groups
11. Application Load Balancer
12. Wait until ALB is available
13. Listeners
14. Weather Launch Template
15. Advisor Launch Template
16. Weather Auto Scaling Group
17. Advisor Auto Scaling Group
18. Save stack outputs
```

---

# 19. Infrastructure Idempotency

The Python infrastructure is designed to be idempotent.

Idempotency means that rerunning creation code should avoid creating unnecessary duplicate resources.

Examples include:

- reusing existing IAM roles
- reusing existing Security Groups
- reusing existing Target Groups
- publishing a new Launch Template version when necessary
- updating existing Auto Scaling Groups
- safely repeating deletion operations

This makes deployment more reliable.

---

# 20. Weather Service

The Weather service runs using:

```text
Node.js
Express
```

The application listens internally on:

```text
3000
```

Users reach it through:

```text
ALB port 8080
```

---

# 21. Zippopotam API

The Weather service first converts a ZIP code into geographic information.

Example request:

```bash
curl -s https://api.zippopotam.us/us/60616
```

For ZIP:

```text
60616
```

the API returned:

```text
Chicago
Illinois
Latitude: 41.8426
Longitude: -87.6306
```

These coordinates are then used for the National Weather Service API.

---

# 22. National Weather Service API

The Weather service calls:

```text
api.weather.gov/points/{latitude},{longitude}
```

The NWS response provides the forecast URL.

The forecast endpoint provides information such as:

- temperature
- temperature unit
- short forecast
- wind speed
- precipitation chance
- daytime/nighttime status

A descriptive User-Agent containing the course/project and contact information is sent with NWS requests.

## Proof — Weather API

![Weather API Forecast Proof](screenshots/02_weather_api_forecast.png)

---

# 23. Weather Endpoint

The main Weather endpoint is:

```text
GET /weather?zip=ZIPCODE
```

Example:

```bash
curl -i "http://ALB_DNS:8080/weather?zip=60616"
```

Example result:

```json
{
  "zip": "60616",
  "city": "Chicago",
  "state": "IL",
  "latitude": "41.8426",
  "longitude": "-87.6306",
  "forecast": {
    "name": "This Afternoon",
    "temperature": 68,
    "temperatureUnit": "F",
    "shortForecast": "Mostly Cloudy",
    "windSpeed": "10 mph",
    "precipitationChance": 14,
    "isDaytime": true
  },
  "cache": "miss"
}
```

---

# 24. PostgreSQL RDS Database

The Weather Tier uses PostgreSQL running on Amazon RDS.

The database is used for:

- weather lookup history
- weather cache

The database configuration was:

```text
Engine: PostgreSQL
Instance class: db.t4g.micro
Storage: 20 GB gp2
Storage encrypted: Yes
Public access: No
Multi-AZ: No
Automated backups: Disabled
Backup retention: 0 days
```

---

# 25. Creating the Database

The database infrastructure is created using:

```bash
python3 create_database.py
```

The Python script performs:

```text
1. Find default VPC and subnets
2. Create Database Security Group
3. Create DB Subnet Group
4. Generate database password
5. Store password in SSM
6. Create PostgreSQL RDS instance
7. Wait for database availability
8. Save database endpoint information
```

Successful output confirmed that the database was:

```text
Private
Encrypted
Single-AZ
Backups disabled
```

## Proof — Database Created

![Database Created](screenshots/04_database_created.png)

---

# 26. Database Verification

The deployed RDS instance was verified using AWS CLI.

Observed configuration:

```json
{
  "PubliclyAccessible": false,
  "MultiAZ": false,
  "Encrypted": true,
  "BackupRetentionPeriod": 0
}
```

Database snapshots:

```text
[]
```

Automated backups:

```text
[]
```

## Proof — Database Verification

![Database Verification](screenshots/05_database_verified.png)

---

# 27. Database Security Group

The PostgreSQL Database Security Group allows only:

```text
TCP port 5432
```

from:

```text
Application Security Group
```

The verified ingress rule was:

```text
IpProtocol: tcp
FromPort: 5432
ToPort: 5432
Source: Application Security Group
```

The rule contains:

```text
No 0.0.0.0/0 CIDR
No public IPv6 range
```

Therefore PostgreSQL is not exposed directly to the internet.

---

# 28. Database Password Security

The PostgreSQL password is not hardcoded in:

- Python source code
- Node.js source code
- `.env`
- EC2 user-data
- GitHub

Instead, Python generates the password and stores it as:

```text
AWS Systems Manager Parameter Store SecureString
```

Parameter name:

```text
/itmo-444-544/db-password
```

Only the Weather IAM role can read this secret.

---

# 29. Weather Cache

PostgreSQL is also used as a cache.

When Weather receives a request, it first checks PostgreSQL for recent data.

The configured cache duration is:

```text
CACHE_SECONDS=600
```

which equals approximately:

```text
10 minutes
```

First lookup:

```json
"cache": "miss"
```

Second lookup for the same ZIP:

```json
"cache": "hit"
```

This proves database-backed caching is working.

---

# 30. Why Caching Is Useful

Caching reduces:

- calls to external APIs
- response latency
- dependency on external services
- network traffic

It also improves the application's efficiency.

---

# 31. Weather History

The Weather Tier saves lookup history in PostgreSQL.

Endpoint:

```text
GET /history
```

Example:

```bash
curl -i "http://ALB_DNS:8080/history"
```

Observed result:

```json
{
  "count": 1,
  "lookups": [
    {
      "id": "1",
      "zip": "60616",
      "city": "Chicago",
      "state": "IL",
      "short_forecast": "Mostly Cloudy",
      "temperature": "68"
    }
  ]
}
```

This proves PostgreSQL reads and writes are functioning.

---

# 32. Weather Error Handling

The application validates ZIP codes.

## Invalid ZIP Format

Example:

```text
123
```

returns:

```text
HTTP/1.1 400 Bad Request
```

## Unknown ZIP

Example:

```text
00000
```

returns:

```text
HTTP/1.1 404 Not Found
```

Response:

```json
{
  "error": "zip_not_found"
}
```

---

# 33. Advisor Service

The Advisor service also runs using Node.js and Express.

It listens internally on:

```text
3000
```

Users access it through:

```text
ALB port 8081
```

The Advisor does not connect directly to the Weather EC2 instance.

Instead, it calls Weather through:

```text
Application Load Balancer port 8080
```

This preserves load-balanced service communication.

---

# 34. Google Gemini Integration

The Advisor Tier uses Google Gemini.

Configured model:

```text
gemini-3.1-flash-lite
```

The Advisor sends forecast information such as:

- temperature
- forecast
- precipitation chance
- wind
- day/night status

Gemini returns clothing advice.

Example:

```json
{
  "advice": "Wear a light jacket or a long-sleeved shirt to stay comfortable.",
  "source": "gemini",
  "model": "gemini-3.1-flash-lite"
}
```

---

# 35. Gemini API Key Security

The Gemini API key is stored as:

```text
AWS Systems Manager SecureString
```

Parameter:

```text
/itmo-444-544/gemini-api-key
```

The API key is not stored in GitHub or hardcoded in the application.

## Proof — SecureString Parameter

![Gemini SSM SecureString](screenshots/03_gemini_ssm_securestring.png)

---

# 36. Advisor Endpoint

Endpoint:

```text
GET /advice?zip=ZIPCODE
```

Example:

```bash
curl -s "http://ALB_DNS:8081/advice?zip=60616" | python3 -m json.tool
```

Observed response:

```json
{
  "zip": "60616",
  "city": "Chicago",
  "state": "IL",
  "forecast": {
    "temperature": 68,
    "shortForecast": "Mostly Cloudy"
  },
  "cache": "hit",
  "advice": "Wear a light sweater or a long-sleeved shirt to stay comfortable.",
  "source": "gemini",
  "model": "gemini-3.1-flash-lite"
}
```

## Proof — Gemini Advisor Success

![Advisor Gemini Success](screenshots/07_advisor_gemini_success.png)

---

# 37. Gemini API Key Caching

The Advisor temporarily caches the Gemini API key after retrieving it from SSM.

Configured duration:

```text
KEY_CACHE_SECONDS=60
```

This avoids unnecessary repeated SSM API requests.

---

# 38. Gemini Fallback

The Advisor contains built-in fallback logic.

If Gemini fails, the application still provides clothing advice.

Example observed fallback:

```json
{
  "advice": "Wear a light jacket or a sweater over long sleeves.",
  "source": "fallback",
  "model": null
}
```

This improves application availability.

The application does not become completely unusable when Gemini is unavailable.

---

# 39. IAM Least Privilege

The project uses separate IAM roles.

## Weather Role

Allowed:

```text
ssm:GetParameter
```

only for:

```text
/itmo-444-544/db-password
```

It does not have permission to read the Gemini secret.

## Advisor Role

Allowed:

```text
ssm:GetParameter
```

only for:

```text
/itmo-444-544/gemini-api-key
```

It does not have permission to read the database password.

Verified Weather policy:

```text
Effect: Allow
Action: ssm:GetParameter
Resource: parameter/itmo-444-544/db-password
```

Verified Advisor policy:

```text
Effect: Allow
Action: ssm:GetParameter
Resource: parameter/itmo-444-544/gemini-api-key
```

## Proof — IAM Least Privilege

![IAM Least Privilege](screenshots/08_iam_least_privilege.png)

---

# 40. Creating the Weather Advisor Stack

Application infrastructure is created using:

```bash
python3 create_weather_stack.py
```

The script successfully created:

```text
Weather IAM role
Advisor IAM role
Weather instance profile
Advisor instance profile
ALB Security Group
Weather Target Group
Advisor Target Group
Application Load Balancer
Listener 8080
Listener 8081
Weather Launch Template
Advisor Launch Template
Weather Auto Scaling Group
Advisor Auto Scaling Group
```

The ALB DNS address was printed after creation.

## Proof — Weather Stack Created

![Weather Stack Created](screenshots/06_weather_stack_created.png)

---

# 41. Application Load Balancer

The ALB is:

```text
internet-facing
```

and spans two Availability Zones.

Listeners:

```text
8080 -> Weather Target Group
8081 -> Advisor Target Group
```

The ALB forwards requests to application instances on:

```text
Port 3000
```

---

# 42. Target Group Health Checks

Both Target Groups use:

```text
HealthCheckProtocol: HTTP
HealthCheckPort: traffic-port
HealthCheckPath: /
HealthCheckIntervalSeconds: 10
HealthyThresholdCount: 2
UnhealthyThresholdCount: 2
```

Both deployed Target Groups were verified as:

```text
healthy
```

---

# 43. Auto Scaling Groups

There are two Auto Scaling Groups:

```text
Weather ASG
Advisor ASG
```

Configuration:

```text
MinSize: 1
MaxSize: 1
DesiredCapacity: 1
HealthCheckType: ELB
```

The groups span two subnets.

If an application EC2 instance fails, the corresponding ASG automatically creates a replacement instance.

---

# 44. Application Network Security

The EC2 instances received public IP addresses, but the application itself is not publicly accessible on port `3000`.

Direct tests were performed using:

```bash
curl --connect-timeout 5 -i "http://INSTANCE_IP:3000/"
```

Observed result:

```text
curl: (28) Connection timeout
```

This happened for both Weather and Advisor.

Port `3000` is allowed only from:

```text
ALB Security Group
```

This proves the EC2 application endpoints are protected from direct internet access.

---

# 45. Unit Testing

The project uses:

```text
pytest
moto
```

Unit tests validate Python logic without deploying new real AWS resources.

The unit tests validate:

- configuration
- required environment variables
- Weather configuration
- Advisor configuration
- application paths
- tier lookup
- EC2 trust policy
- SSM least-privilege policies
- Weather IAM policy
- Advisor IAM policy
- unknown tier rejection
- IAM role creation
- IAM instance profile creation
- idempotent role creation
- ALB Security Group creation
- ALB Security Group idempotency
- Weather user-data
- Advisor user-data
- embedded application files
- systemd service creation
- Launch Template settings
- user-data size

---

# 46. Configuration Unit Tests

Configuration tests verify:

- AWS Region
- Application Security Group
- Weather listener port
- Advisor listener port
- DB configuration
- cache configuration
- Gemini model
- Gemini key cache
- application directories
- missing required settings
- Weather/Advisor tier lookup

Result:

```text
4 passed
```

---

# 47. IAM Policy Unit Tests

Policy tests verify:

- EC2 trust policy
- SSM GetParameter permission
- Weather DB secret access
- Advisor Gemini secret access
- correct policy selection
- unknown tier rejection

Result:

```text
7 passed
```

---

# 48. Moto Infrastructure Tests

Moto tests verify:

- Weather IAM role creation
- Advisor IAM role creation
- instance profile creation
- idempotent role/profile creation
- Weather SSM resource policy
- Advisor SSM resource policy
- ALB Security Group creation
- ALB Security Group idempotency
- repeated deletion behavior

Result:

```text
6 passed
```

---

# 49. User-Data Unit Tests

User-data tests verify:

- Weather database variables
- AWS Region
- cache settings
- Advisor Weather URL
- Gemini SSM parameter
- Gemini model
- key cache duration
- embedded app.js
- embedded package.json
- Weather systemd service
- Advisor systemd service
- Launch Template data
- 16 KB size limit

Result:

```text
6 passed
```

---

# 50. Final Unit Test Result

Command:

```bash
pytest -q
```

Final result:

```text
23 passed, 20 deselected
```

---

# 51. Integration Testing

Integration tests run against the actual deployed AWS infrastructure.

Command:

```bash
pytest -q -m integration
```

Integration tests validate:

- Weather root endpoint
- valid ZIP weather lookup
- Weather cache
- Weather history
- invalid ZIP `400`
- unknown ZIP `404`
- Advisor root endpoint
- Advisor clothing advice
- Gemini/fallback response
- ALB state
- ALB Availability Zones
- listener routing
- Target Group configuration
- Auto Scaling Group configuration
- application Security Group
- Database Security Group
- private RDS
- encrypted RDS
- backups disabled
- Weather IAM permissions
- Advisor IAM permissions
- healthy targets

Final result:

```text
18 passed, 25 deselected
```

---

# 52. Unit and Integration Test Proof

Final commands:

```bash
pytest -q
pytest -q -m integration
```

Observed results:

```text
23 passed, 20 deselected

18 passed, 25 deselected
```

## Proof — Unit and Integration Tests

![Unit and Integration Tests Passed](screenshots/13_unit_and_integration_tests_passed.png)

---

# 53. What Moto Proves

Moto simulates many AWS APIs locally.

Moto helped prove:

- boto3 methods are called correctly
- configuration can be loaded
- IAM roles can be created
- instance profiles can be created
- IAM policies contain expected resources
- Security Groups can be created
- idempotent code can be tested
- infrastructure functions produce expected structures

---

# 54. What Moto Cannot Prove

Moto does not fully reproduce all real AWS behavior.

Moto cannot fully prove:

- real EC2 boot time
- real ALB health checks
- IAM propagation delay
- actual networking
- public HTTP traffic
- Auto Scaling timing
- RDS connectivity
- Gemini API behavior
- NWS API behavior
- Zippopotam availability
- actual recovery times

Because of this, real AWS integration tests and chaos tests were also performed.

---

# 55. Chaos Testing

Chaos testing intentionally breaks infrastructure to verify failure behavior and recovery.

Two primary chaos experiments were implemented:

1. Database outage
2. Weather EC2 failure

Command:

```bash
pytest -q -m chaos -s
```

---

# 56. Chaos Test 1 — Database Failure

The PostgreSQL Security Group rule was temporarily removed.

This prevented Weather from reaching PostgreSQL.

A Weather request was then made using:

```text
ZIP 10001
```

Observed response:

```text
HTTP 200
```

with:

```json
"cache": "unavailable"
```

Full behavior:

```json
{
  "zip": "10001",
  "city": "New York City",
  "state": "NY",
  "forecast": {
    "temperature": 70,
    "shortForecast": "Sunny"
  },
  "cache": "unavailable"
}
```

The Weather application still returned live forecast data.

This proves database failure does not completely break the Weather service.

---

# 57. Graceful Degradation

The Weather Tier treats PostgreSQL as useful but not mandatory for a live weather request.

If the database becomes unreachable:

```text
Cache lookup fails
        |
        v
Weather service continues
        |
        v
External APIs are called
        |
        v
Forecast is returned
        |
        v
cache = unavailable
```

This behavior is called:

```text
Graceful Degradation
```

The PostgreSQL Security Group rule was restored after the experiment.

---

# 58. Chaos Test 2 — Weather Instance Failure

A running Weather EC2 instance was intentionally terminated.

The termination changed the instance state to:

```text
shutting-down
```

During the Weather outage, the Advisor endpoint was called.

Observed response:

```text
HTTP/1.1 502 Bad Gateway
```

Response body:

```json
{
  "error": "weather_service_unavailable"
}
```

This proves the Advisor correctly detects that its Weather dependency is unavailable.

## Proof — Advisor During Weather Outage

![Advisor Weather Outage 502](screenshots/10_advisor_weather_outage_502.png)

---

# 59. Auto Scaling Replacement

After the Weather instance was terminated, the Weather Auto Scaling Group automatically detected the unhealthy capacity.

It launched a new EC2 instance.

The scaling activity showed that a new instance was launched because:

```text
an unhealthy instance needed to be replaced
```

The replacement progressed to:

```text
LifecycleState: InService
HealthStatus: Healthy
```

---

# 60. Recovery Time

The automated chaos test measured the Weather recovery time.

Observed recovery:

```text
112.50762629508972 seconds
```

Approximately:

```text
112.5 seconds
```

Required recovery limit:

```text
300 seconds
```

Therefore:

```text
112.5 < 300
```

The recovery requirement passed.

---

# 61. Weather Recovery

After the replacement instance became healthy, the Weather endpoint returned:

```text
HTTP/1.1 200 OK
```

again.

The response also showed:

```json
"cache": "hit"
```

This confirmed that:

- the replacement EC2 instance started correctly
- the Node.js application started
- the ALB health check succeeded
- Weather became routable again
- PostgreSQL connectivity returned
- caching continued working

## Proof — Weather Recovery

![Weather Recovery After Outage](screenshots/11_weather_recovered_after_outage.png)

---

# 62. Additional Recovery Proof

An earlier manual replacement test also proved that a terminated Weather EC2 instance was replaced automatically and became healthy.

## Proof

![Weather Chaos Recovery](screenshots/09_weather_chaos_recovery.png)

---

# 63. Automated Chaos Test Result

Command:

```bash
pytest -q -m chaos -s
```

Observed output:

```text
DB outage response: 200
cache: unavailable

Terminated Weather instance

Saw Advisor 502: True

Weather recovery time: 112.50762629508972s

2 passed
```

Final result:

```text
2 passed, 41 deselected
```

## Proof — Automated Chaos Tests

![Chaos Tests Passed](screenshots/12_chaos_tests_passed.png)

---

# 64. Final Test Summary

| Test Category | Result |
|---|---:|
| Unit / Moto Tests | 23 passed |
| Integration Tests | 18 passed |
| Chaos Tests | 2 passed |
| DB Failure Weather Response | 200 OK |
| Advisor During Weather Failure | 502 Bad Gateway |
| Weather Recovery | ~112.5 seconds |
| Required Recovery Limit | <= 300 seconds |

All required automated tests passed.

---

# 65. Why Python Instead of Bash?

The graduate version of the lab requires infrastructure management using Python.

Bash can sometimes be shorter for simple AWS commands.

For example:

```bash
aws ec2 describe-instances
```

is shorter than constructing a boto3 client and parsing Python dictionaries.

However, Python provides important advantages:

- reusable functions
- structured code
- easier unit testing
- exception handling
- AWS-specific error handling
- better configuration validation
- easier idempotency
- modular design
- better maintenance
- easier integration with pytest and moto

For a larger infrastructure project, these advantages are more important than the small amount of extra code.

---

# 66. Python Error Handling vs Bash

A Bash pattern such as:

```bash
2>/dev/null || true
```

can hide every error.

That could accidentally hide serious problems such as:

```text
AccessDenied
InvalidParameter
UnauthorizedOperation
```

The Python code instead ignores only expected errors such as:

```text
EntityAlreadyExists
NoSuchEntity
InvalidPermission.Duplicate
```

Unexpected errors are allowed to fail visibly.

This makes the infrastructure safer and easier to debug.

---

# 67. Secrets Management

The project does not store secrets in Git.

Sensitive values are stored using:

```text
AWS Systems Manager Parameter Store
```

Secret parameters:

```text
/itmo-444-544/db-password
/itmo-444-544/gemini-api-key
```

Both are:

```text
SecureString
```

The applications retrieve them at runtime through IAM roles.

---

# 68. Git Security

Sensitive/generated files are excluded using `.gitignore`.

Ignored files include:

```text
.env
db_outputs.env
stack_outputs.env
stack_outputs.json
.venv/
*.pem
__pycache__/
.pytest_cache/
```

The repository therefore does not intentionally commit:

- AWS credentials
- Gemini API key
- database password
- private key files
- generated stack output files

---

# 69. Main Screenshot Evidence

The following screenshots provide evidence for the major lab requirements.

## 01 — Project Layout

```text
screenshots/01_lab06_layout.png
```

![Project Layout](screenshots/01_lab06_layout.png)

---

## 02 — Public Weather APIs

```text
screenshots/02_weather_api_forecast.png
```

![Weather API Forecast](screenshots/02_weather_api_forecast.png)

---

## 03 — Gemini Secret Stored in SSM

```text
screenshots/03_gemini_ssm_securestring.png
```

![Gemini SSM SecureString](screenshots/03_gemini_ssm_securestring.png)

---

## 04 — PostgreSQL Database Created

```text
screenshots/04_database_created.png
```

![Database Created](screenshots/04_database_created.png)

---

## 05 — RDS Configuration Verified

```text
screenshots/05_database_verified.png
```

![Database Verified](screenshots/05_database_verified.png)

---

## 06 — Full Weather Advisor Stack Created

```text
screenshots/06_weather_stack_created.png
```

![Weather Stack Created](screenshots/06_weather_stack_created.png)

---

## 07 — Advisor Successfully Used Gemini

```text
screenshots/07_advisor_gemini_success.png
```

![Gemini Advisor Success](screenshots/07_advisor_gemini_success.png)

---

## 08 — Least-Privilege IAM

```text
screenshots/08_iam_least_privilege.png
```

![IAM Least Privilege](screenshots/08_iam_least_privilege.png)

---

## 09 — Weather Auto Scaling Recovery

```text
screenshots/09_weather_chaos_recovery.png
```

![Weather Chaos Recovery](screenshots/09_weather_chaos_recovery.png)

---

## 10 — Advisor Returned 502 During Weather Failure

```text
screenshots/10_advisor_weather_outage_502.png
```

![Advisor Weather Outage](screenshots/10_advisor_weather_outage_502.png)

---

## 11 — Weather Recovered After Outage

```text
screenshots/11_weather_recovered_after_outage.png
```

![Weather Recovered](screenshots/11_weather_recovered_after_outage.png)

---

## 12 — Automated Chaos Tests Passed

```text
screenshots/12_chaos_tests_passed.png
```

![Chaos Tests Passed](screenshots/12_chaos_tests_passed.png)

---

## 13 — Unit and Integration Tests Passed

```text
screenshots/13_unit_and_integration_tests_passed.png
```

![Unit and Integration Tests Passed](screenshots/13_unit_and_integration_tests_passed.png)

---

# 70. Cleanup

The application stack is deleted using:

```bash
python3 delete_weather_stack.py
```

The application cleanup removes:

- Weather Auto Scaling Group
- Advisor Auto Scaling Group
- Application Load Balancer
- Target Groups
- ALB Security Group
- Weather Launch Template
- Advisor Launch Template
- Weather IAM role
- Advisor IAM role
- Weather instance profile
- Advisor instance profile
- generated stack output files

---

# 71. Database Cleanup

The database is removed separately using:

```bash
python3 delete_database.py
```

RDS deletion uses:

```text
SkipFinalSnapshot=True
DeleteAutomatedBackups=True
```

This avoids leaving unnecessary billable database resources or backups.

---

# 72. Final Cleanup Verification

After cleanup, the following should no longer exist:

```text
RDS database
RDS manual snapshots
RDS automated backups
DB subnet group
DB Security Group
Application Load Balancer
Weather Target Group
Advisor Target Group
Weather Auto Scaling Group
Advisor Auto Scaling Group
Weather Launch Template
Advisor Launch Template
Weather IAM role
Advisor IAM role
Weather instance profile
Advisor instance profile
DB password SSM parameter
Gemini API-key SSM parameter
```

---

# 73. Technologies Used

- Python 3
- boto3
- pytest
- moto
- AWS EC2
- AWS IAM
- AWS Systems Manager Parameter Store
- AWS Application Load Balancer
- AWS Auto Scaling
- AWS RDS PostgreSQL
- AWS Security Groups
- AWS STS
- Node.js
- Express
- PostgreSQL
- Zippopotam API
- National Weather Service API
- Google Gemini
- Docker
- Git
- GitHub

---

# 74. Final Result

The Weather Advisor application was successfully implemented as a two-tier AWS cloud application.

The project successfully demonstrated:

```text
Weather API integration
ZIP-code location lookup
NWS forecast retrieval
PostgreSQL caching
Weather lookup history
Google Gemini clothing advice
Gemini fallback behavior
Secure SSM secrets
Least-privilege IAM
Private encrypted RDS
ALB-only application access
Two Availability Zones
Target Group health checks
Auto Scaling replacement
Database failure tolerance
Advisor 502 dependency failure behavior
Automatic Weather recovery
Python infrastructure automation
pytest unit testing
moto AWS testing
real AWS integration testing
chaos testing
```

Final automated test results:

```text
Unit / Moto:
23 passed

Integration:
18 passed

Chaos:
2 passed

Weather recovery:
approximately 112.5 seconds

Required recovery limit:
300 seconds
```

The Weather service recovered well within the required 300-second limit, and all final automated tests passed successfully.
