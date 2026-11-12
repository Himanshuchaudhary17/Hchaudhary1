# Lab07 Screenshot Manifest

All screenshots are stored in `screenshots/` in chronological/submission order.

1. `01_troubleshooting_iam_ssm_tag_access_policy.png` — temporary IAM/SSM tag permission used during troubleshooting.
2. `02_manual_weather_cache_and_gemini_test.png` — healthy target plus weather cache miss/hit and Gemini advisor response.
3. `03_smoke_test_9_of_9_passed.png` — Lab07 smoke test: 9 of 9 checks passed.
4. `04_step1_effort_line_counts.png` — Step 1 Python/Terraform/delete-script line counts.
5. `05_step2_terraform_dependency_graph.png` — Step 2 Terraform dependency graph evidence.
6. `06_step3_no_changes_idempotence.png` — Step 3 `terraform plan` shows No changes.
7. `07_step4_cache_seconds_plan_details.png` — Step 4 CACHE_SECONDS change plan details.
8. `08_step4_cache_seconds_plan_summary.png` — Step 4 plan summary: 0 add, 2 change, 0 destroy.
9. `09_step4_instance_refresh_started.png` — Step 4 rolling instance refresh started.
10. `10_step4_cache_seconds_60_verified.png` — Step 4 EC2 Instance Connect success and `CACHE_SECONDS=60` verification.
11. `11_step5_health_check_drift_plan.png` — Step 5 Terraform detects health-check drift and plans repair.
12. `12_step5_target_group_recovery.png` — Step 5 target group recovery/rolling replacement evidence.
13. `13_step5_deleted_listener_plan_1_add.png` — Step 5 deleted listener detected: 1 resource to add.
14. `14_step6_iam_policy_simulator.png` — Step 6 least-privilege IAM simulator results.
15. `15_step7_no_changes_and_state_key_check.png` — Step 7 No changes and `AIza` count 0.
16. `16_step8_fallback_responses.png` — Step 8 two successful fallback responses with broken Gemini key.
17. `17_step8_gemini_error_logs.png` — Step 8 advisor journal `gemini_error` entries.
18. `18_step8_gemini_restored.png` — Step 8 real Gemini key restored and source returns `gemini`.
19. `19_advisor_webpage_gemini.png` — Weather Advisor browser page for ZIP 60616 with Gemini source.
20. `20_final_no_changes_terraform_version_sts.png` — final No changes, Terraform/provider versions, and masked STS identity.
21. `21_step10_destroy_plan_25_resources.png` — Step 10 destroy plan: 25 resources to destroy.
22. `22_step10_destroy_complete_25.png` — Step 10 destroy complete: 25 resources destroyed.
23. `23_step10_cleanup_verification.png` — empty state, SSM `ParameterNotFound`, temporary IAM policies/SSH keys removed.
24. `24_step10_final_aws_resource_checks.png` — final AWS checks show no Lab07 EC2/ALB/TG/ASG/LT/DynamoDB/SSM/SG/IAM resources.
