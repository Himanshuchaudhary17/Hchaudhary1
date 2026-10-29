# Written Responses — Step08 Weather Advisor

## What moto proved and what it could not prove

Moto helped verify that my Python infrastructure code could make valid AWS-style API calls and create resources with the expected configuration without using real AWS resources for every unit test. It was useful for testing IAM roles, instance profiles, security groups, SSM policies, configuration values, repeated resource creation, and other boto3 logic.

Moto could not fully prove real AWS behavior such as IAM propagation delays, EC2 boot time, Application Load Balancer health-check timing, Auto Scaling replacement time, real network connectivity, RDS availability, public API behavior, or actual HTTP traffic.

Because of those limitations, I also used live integration tests against the deployed AWS infrastructure. The integration tests verified the ALB, listeners, Target Groups, Auto Scaling Groups, security groups, RDS configuration, IAM permissions, Weather endpoint, Advisor endpoint, caching, and error handling.

The chaos tests provided additional proof by intentionally making the database unavailable and terminating a Weather EC2 instance. The Weather application continued returning live forecast data when PostgreSQL was unavailable, and the Auto Scaling Group replaced the terminated Weather instance within approximately 112.5 seconds.

---

## How integration tests provided proof beyond moto

The integration tests validated behavior that could not be reliably simulated with moto.

They tested the real AWS deployment and confirmed:

- the ALB was active
- the ALB used two Availability Zones
- port 8080 routed to the Weather Target Group
- port 8081 routed to the Advisor Target Group
- both Target Groups became healthy
- the Weather and Advisor Auto Scaling Groups were configured correctly
- application port 3000 was accessible only from the ALB Security Group
- PostgreSQL port 5432 was accessible only from the application Security Group
- RDS was private
- RDS storage was encrypted
- Multi-AZ was disabled
- automated backups were disabled
- the Weather role could read only the database password parameter
- the Advisor role could read only the Gemini API-key parameter
- Weather returned successful forecast responses
- Weather caching worked
- lookup history worked
- Advisor returned clothing advice from Gemini or its fallback
- invalid ZIP codes returned the expected HTTP errors

The final integration test result was:

```text
18 passed
```

---

## Chaos testing and recovery

Two failure scenarios were tested.

### Database outage

The database Security Group rule was temporarily removed so the Weather service could not connect to PostgreSQL.

The Weather service still returned:

```text
HTTP 200
```

and reported:

```json
"cache": "unavailable"
```

This showed graceful degradation because live weather requests could still succeed even when the cache/database was unavailable.

### Weather EC2 failure

A Weather EC2 instance was intentionally terminated.

During the outage, the Advisor correctly returned:

```text
HTTP 502 Bad Gateway
```

with:

```json
{
  "error": "weather_service_unavailable"
}
```

The Weather Auto Scaling Group automatically launched a replacement instance.

Measured recovery time:

```text
approximately 112.5 seconds
```

Required limit:

```text
300 seconds
```

Therefore the recovery requirement passed.

The automated chaos test result was:

```text
2 passed
```

---

## Python compared with Bash

Bash is shorter for simple AWS CLI commands, but Python was better for this project because the infrastructure had many dependent resources and required more structured error handling.

Python made it easier to divide the infrastructure into reusable modules, validate configuration, handle specific AWS exceptions, implement idempotent resource creation, write automated tests with pytest and moto, and reuse logic between creation and deletion.

For example, Bash can ignore an error using:

```bash
2>/dev/null || true
```

but this hides every error, including unexpected failures.

Python can inspect the specific AWS error code and ignore only expected conditions such as:

```text
EntityAlreadyExists
NoSuchEntity
InvalidPermission.Duplicate
```

while still raising unexpected errors such as:

```text
AccessDenied
InvalidParameter
UnauthorizedOperation
```

Although Python requires more lines of code, it provides safer and more maintainable infrastructure automation for a project of this size.

---

## Final Test Results

```text
Unit / moto tests:
27 passed

Integration tests:
18 passed

Chaos tests:
2 passed

Weather recovery:
approximately 112.5 seconds

Required recovery:
<= 300 seconds
```

All final automated tests passed.
