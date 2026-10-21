# Written Responses

## What moto proved and what it could not prove

Moto proved that my Python stack code could call AWS-style APIs with valid parameters, that the create operations were idempotent, that delete operations could safely be repeated, and that resources ended up with the configuration expected by the unit tests. However, moto could not prove that real AWS would behave exactly the same under IAM propagation delays, service quotas, EC2 boot time, npm installation, networking, or real HTTP traffic. The integration tests filled this gap by testing the actual deployed AWS infrastructure and application behavior, while the chaos tests verified whether the application recovered from EC2 instance failure within the defined recovery SLO.

## ignore_errors() compared with Bash 2>/dev/null || true

`ignore_errors("EntityAlreadyExists")` is safer than Bash `2>/dev/null || true` because it ignores only the specific AWS error that is expected during an idempotent operation. Unexpected errors such as `AccessDenied`, invalid parameters, or configuration mistakes are still raised and remain visible. In comparison, `2>/dev/null || true` hides all error output and forces the command to appear successful, which can hide real problems.

## Challenge 5 — Bash versus Python

One place where Bash was shorter was ignoring an expected failure during cleanup, because `2>/dev/null || true` can be written on one line while Python requires exception handling and checking a specific AWS error code. The additional Python lines make the behavior safer because only expected errors are ignored while unexpected failures remain visible. They also make the behavior easier to unit test and reuse throughout the project.
