# Step07 — Infrastructure as Python with boto3 and pytest

This lab rebuilds the previous AWS CLI/Bash infrastructure using Python, boto3, pytest, and moto.

## Features

- S3, IAM roles and instance profiles
- EC2 Launch Templates
- Application Load Balancer and Target Groups
- Auto Scaling Groups
- Security Group configuration
- Unit tests with moto
- Real AWS integration tests
- Chaos recovery testing

## Test Results

- 19 unit tests passed
- 14 integration tests passed
- 2 chaos tests passed with a 180-second SLO
- 2 chaos tests intentionally failed with a 60-second SLO
- Uploader recovery: about 87 seconds
- Viewer recovery: about 83 seconds

## Commands

Unit tests: `pytest`

Create stack: `python create_stack.py`

Integration tests: `pytest -m integration -v`

Chaos tests: `pytest -m chaos -s`

Delete stack: `python delete_stack.py`

## Security

The S3 bucket blocks public access. The uploader IAM role is limited to uploading the shared object, while the viewer role can read but cannot write. Application port 3000 is reachable only from the ALB security group.

## Written Responses

See `SUBMISSION_NOTES.md` for the moto reflection, error-handling comparison, and Challenge 5 response.

## Cleanup

Final AWS validation confirmed that no lab load balancers, Auto Scaling Groups, or IAM roles remained after cleanup.
