import base64

from stack.compute import build_user_data, launch_template_data


def test_user_data_contains_bucket_and_region(fake_settings):
    data = build_user_data(
        fake_settings,
        fake_settings.uploader,
    )

    assert f"BUCKET_NAME={fake_settings.bucket_name}" in data
    assert f"AWS_REGION={fake_settings.region}" in data


def test_user_data_contains_app_files(fake_settings):
    data = build_user_data(
        fake_settings,
        fake_settings.uploader,
    )

    app_js_b64 = base64.b64encode(
        (fake_settings.uploader.app_dir / "app.js").read_bytes()
    ).decode()

    package_b64 = base64.b64encode(
        (
            fake_settings.uploader.app_dir / "package.json"
        ).read_bytes()
    ).decode()

    assert app_js_b64 in data
    assert package_b64 in data


def test_user_data_starts_correct_service(fake_settings):
    data = build_user_data(
        fake_settings,
        fake_settings.viewer,
    )

    assert "systemctl enable viewer.service" in data
    assert "systemctl start viewer.service" in data


def test_launch_template_data_uses_expected_settings(fake_settings):
    data = launch_template_data(
        fake_settings,
        fake_settings.uploader,
    )

    assert data["ImageId"] == fake_settings.ami_id
    assert data["InstanceType"] == fake_settings.instance_type
    assert data["KeyName"] == fake_settings.key_name
    assert data["SecurityGroupIds"] == [
        fake_settings.app_sg_id
    ]
    assert data["IamInstanceProfile"] == {
        "Name": fake_settings.uploader.profile_name
    }
    assert data["UserData"]
