from stack.policies import (
    OBJECT_KEY,
    policy_for,
    trust_policy,
    uploader_policy,
    viewer_policy,
)


def test_trust_policy_allows_only_ec2():
    statement = trust_policy()["Statement"][0]

    assert statement["Effect"] == "Allow"
    assert statement["Principal"] == {
        "Service": "ec2.amazonaws.com"
    }
    assert statement["Action"] == "sts:AssumeRole"


def test_uploader_policy_is_put_only():
    policy = uploader_policy("my-bucket")
    statement = policy["Statement"][0]

    assert statement["Action"] == ["s3:PutObject"]
    assert statement["Resource"] == (
        f"arn:aws:s3:::my-bucket/{OBJECT_KEY}"
    )


def test_viewer_policy_can_read_but_not_write():
    policy = viewer_policy("my-bucket")
    actions = {
        action
        for statement in policy["Statement"]
        for action in statement["Action"]
    }

    assert "s3:GetObject" in actions
    assert "s3:ListBucket" in actions
    assert "s3:PutObject" not in actions


def test_policy_for_returns_correct_policy():
    assert policy_for("uploader", "my-bucket") == uploader_policy(
        "my-bucket"
    )
    assert policy_for("viewer", "my-bucket") == viewer_policy(
        "my-bucket"
    )
