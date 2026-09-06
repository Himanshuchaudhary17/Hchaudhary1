# Lab 03 - AWS CLI and GitHub Inside Docker

## Credential Security

AWS credentials and GitHub Personal Access Tokens should never be committed to a Git repository because they provide authentication and access to cloud resources or source code.

If a credential is exposed, another person may be able to access, modify, or delete resources using that credential. Even private repositories should not be used to store secrets because repository permissions may change or the repository could accidentally become public.

Credentials should be stored securely outside the repository. If an AWS access key or GitHub token is exposed, it should be revoked or deleted immediately and replaced with a new credential.
