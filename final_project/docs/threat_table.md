# Weather Advisor Threat Table

## 1. Purpose

This document identifies security, privacy, abuse, and reliability threats for the Weather Advisor application and records the controls used to reduce those risks.

The application is public, calls external services, uses an AI model, stores temporary data, and can send email, so it must assume that users and external responses may be untrusted.

---

## 2. Threat Table

| Threat | Example | Risk | Control | Verification |
|---|---|---|---|---|
| Invalid ZIP input | `ABCDE`, `6061`, `M5V 3L9` | Unnecessary API calls, incorrect behavior | Server accepts exactly five digits only | Unit tests for valid and invalid postal codes |
| Unknown but valid-format ZIP | `00000` | Wrong location or failed downstream requests | Separate ZIP-not-found handling before Gemini call | Contract/integration test |
| Invalid date | Past date or date beyond seven-day window | Incorrect report or unsupported API horizon | Server-side date validation | Boundary unit tests |
| Free-text gender input | User enters prompt-like text | Prompt injection and unnecessary personal data | Fixed allowed clothing categories only | Unit tests |
| Prompt injection | User attempts to alter Gemini instructions | Model misuse | No user free text is sent to Gemini | Prompt-building unit tests |
| Gemini invents weather facts | Model returns its own temperature | Incorrect report | Gemini generates advice only; measured values come from APIs | Response validation tests |
| Malformed Gemini JSON | Missing or wrong output fields | Broken page or unsafe output | Strict structured-response validation and fallback | Unit tests with malformed fixtures |
| Hostile Gemini output | HTML/script content | Cross-site scripting | Escape all model output before display | Escaping tests |
| Hostile API response | Unexpected text from outside API | XSS or malformed UI | Validate and escape all external data | Contract tests |
| Missing weather field | Visibility unavailable from NWS | False values if treated as zero | Use fallback source or show `Not available` | Contract tests |
| Weather API outage | NWS timeout/failure | Report unavailable | Timeout, recent cache fallback, honest degraded message | Chaos test |
| Supplemental API outage | Open-Meteo failure | Missing UV/visibility | Show `Not available` for affected fields only | Chaos/contract tests |
| Gemini outage | Quota/error/timeout | Advice unavailable | Deterministic rule-based fallback | Chaos test |
| Gemini daily quota exhaustion | Too many requests | Free-tier abuse and failed requests | DynamoDB atomic daily call counter | Moto and integration tests |
| Repeated identical requests | Same ZIP/date repeatedly submitted | Wasted API and Gemini calls | Cached facts and saved reports with TTL | Cache integration test |
| Public endpoint abuse | Rapid repeated requests | Cost increase / service degradation | Per-visitor rate limit | Unit/integration test |
| Email abuse | User sends repeated messages | Spam or service misuse | Recipient confirmation and per-visitor email limit | Email tests |
| Email sent to wrong person | Shared SNS topic without isolation | Privacy breach | Recipient-specific consent and delivery logic | Two-recipient test |
| Email logged | Email appears in app logs | Privacy leak | Never log email addresses | Log inspection test |
| Gender logged | Gender stored with identity | Privacy risk | Do not log gender or store with email | Log/data inspection |
| Email sent to Gemini | Prompt includes email | Privacy breach | Gemini payload excludes email | Prompt unit test |
| Gemini key in code | Hard-coded secret | Credential exposure | Store encrypted key in SSM Parameter Store | Repository grep and IAM test |
| Gemini key in logs | Error prints secret | Credential exposure | Never log secret value | Log inspection |
| Weather tier reads Gemini key | Excess IAM permission | Larger blast radius | Separate least-privilege IAM roles | IAM simulator/integration test |
| Advisor tier reads unnecessary weather storage | Excess IAM permission | Larger blast radius | Restrict Advisor role to required resources only | IAM simulator test |
| Wildcard IAM actions/resources | `Action: "*"` | Excess privilege | Explicit actions and resource ARNs only | Policy unit tests |
| Direct EC2 application access | Public instance port | Bypasses ALB/security controls | App port accepts traffic only from ALB security group | Integration test |
| Instance failure | EC2 terminated | Temporary outage | Auto Scaling Group replacement and ALB health checks | Chaos test |
| State stored only on instance | Report lost after replacement | User-visible data loss | Store shared temporary state in DynamoDB | Architecture/integration verification |
| Request hangs | External API does not respond | ALB timeout / poor UX | Explicit external-call timeouts shorter than ALB idle timeout | Failure tests |
| Cache becomes stale | Forecast changes | Outdated weather shown | Short TTL and freshness label where needed | Cache tests |
| Missing value becomes zero | Missing visibility interpreted as 0 | Dangerous incorrect data | Explicit `None`/missing handling | Unit tests |
| HTML injection in form | Script-like input | Cross-site scripting | Input validation plus output escaping | Security unit tests |
| Concurrent Gemini counter requests | Race condition | Daily cap bypass | Atomic DynamoDB update | Moto race-condition test |
| Cost overrun | Stack left running | Budget violation | `budget.py`, short sessions, teardown after work | Cost report |
| Forgotten infrastructure | ALB/EC2 left active | Ongoing charges | Idempotent Python delete script and final resource checks | Cleanup evidence |

---

## 3. Trust Boundaries

The application has several trust boundaries.

### Browser to Advisor Tier

User input is untrusted.

The Advisor tier validates:

- date
- ZIP code
- clothing category
- email address

Browser-side validation is not treated as sufficient.

---

### Advisor Tier to Weather Data Tier

The Advisor tier requests normalized weather facts.

The Weather Data tier does not receive:

- email address
- unnecessary personal information

The Weather tier does not call Gemini.

---

### Application to Weather APIs

All weather API responses are external and untrusted.

The application validates:

- expected JSON shape
- numeric values
- timestamps
- units
- missing fields

Missing values are not silently converted to zero.

---

### Advisor Tier to Gemini

Only fixed, validated information reaches Gemini.

The Gemini request contains:

- weather facts
- fixed clothing category

It does not contain:

- email address
- free-text user instructions
- arbitrary user prompts

---

### Advisor Tier to Email Service

Email delivery is allowed only after the recipient consent workflow is satisfied.

The email service is never used as an unrestricted mail relay.

---

## 4. Secret Handling

The Gemini API key is stored as an encrypted SSM Parameter Store value.

It must not appear in:

- application source code
- `.env` committed to Git
- screenshots
- logs
- documentation
- user-data content in plaintext

Only the Advisor IAM role receives permission to read the parameter.

The Weather tier does not receive this permission.

---

## 5. IAM Principle

Each tier has a separate IAM role.

### Weather Role

The Weather role receives only permissions required for:

- weather cache reads/writes
- required application storage
- logging/instance operation as necessary

It does not receive permission to read the Gemini secret or send email.

### Advisor Role

The Advisor role receives only permissions required for:

- reading the Gemini key
- report/counter storage it owns
- SNS email workflow
- application operation

It does not receive unnecessary Weather-tier permissions.

---

## 6. Abuse Controls

The public application includes:

- per-visitor request rate limiting
- daily Gemini call cap
- per-visitor email request limits
- caching of repeated weather queries
- caching/saving of repeated reports where appropriate
- short response limits for Gemini
- external-call timeouts

These controls reduce cost and make it harder for one visitor to exhaust the service.

---

## 7. Privacy Controls

The application follows data-minimization principles.

The email address is used only for report delivery.

The clothing category is used only to tailor dressing advice.

The application does not:

- send email addresses to Gemini
- log email addresses
- log gender/clothing category unnecessarily
- retain personal information longer than required

Temporary records use DynamoDB TTL where appropriate.

---

## 8. Failure Safety

Failure must not result in invented data.

Examples:

```text
NWS unavailable
-> use fresh cached facts if available
-> otherwise report weather data unavailable

Visibility unavailable
-> use documented Open-Meteo fallback
-> otherwise show Not available

Gemini unavailable
-> show measured facts
-> use deterministic fallback advice

Email failure
-> tell user delivery failed
-> never claim sent until accepted
```

---

## 9. Security Testing Plan

Security-related tests will include:

- invalid postal-code tests
- invalid date tests
- fixed clothing-category tests
- prompt-construction tests
- Gemini response validation
- HTML escaping tests
- IAM policy wildcard tests
- IAM allowed/denied checks
- email-recipient isolation
- daily-cap race testing
- external API failure tests
- direct-EC2-access denial
- secret-search checks

---

## 10. Threat Model Conclusion

The main security principle of the project is:

```text
Do not trust input.
Do not trust external APIs.
Do not trust model output.
Do not over-permission AWS roles.
Do not retain personal data unnecessarily.
Do not invent weather facts when dependencies fail.
```

The design keeps measured facts, derived categories, generated advice, secrets, and personal data separated so that failures in one part of the system do not automatically compromise the others.
