# Final Project Architecture

## 1. Architecture Overview

The final project uses a two-tier cloud architecture based on the completed Lab06 Weather Advisor design.

The two application tiers are:

1. Advisor tier
2. Weather Data tier

Both tiers run on EC2 instances inside Auto Scaling Groups and are reached through an Application Load Balancer.

The Advisor tier handles the user-facing workflow, while the Weather Data tier is responsible only for weather facts.

This separation keeps measured weather data independent from Gemini-generated advice.

---

## 2. Architecture Diagram

```text
                              Browser
                                 |
                                 v
                    +-------------------------+
                    | Application Load        |
                    | Balancer                |
                    +-------------------------+
                       |                   |
                  :8080|                   |:8081
                       |                   |
                       v                   v
          +---------------------+   +----------------------+
          | ADVISOR TIER        |   | WEATHER DATA TIER    |
          | EC2 + Auto Scaling  |   | EC2 + Auto Scaling   |
          |                     |   |                      |
          | - form              |   | - ZIP lookup         |
          | - validation        |   | - timezone handling  |
          | - report page       |   | - NWS API calls      |
          | - Gemini advice     |   | - supplemental API   |
          | - email workflow    |   | - aggregation        |
          | - rate limiting     |   | - Rain/Snow rules    |
          +---------------------+   +----------------------+
              |        |   |               |
              |        |   |               |
              |        |   |               +------> NWS API
              |        |   |
              |        |   +-----------------------> DynamoDB
              |        |
              |        +---------------------------> SSM Parameter Store
              |
              +------------------------------------> Google Gemini API
              |
              +------------------------------------> Amazon SNS

                         DynamoDB
                            |
          +--------------------------------------+
          | facts cache                          |
          | saved reports                        |
          | Gemini daily call counter            |
          | rate-limit / temporary state         |
          | TTL on temporary data                |
          +--------------------------------------+
```

---

## 3. Component Responsibilities

| Component | Responsibility | Must Not Do |
|---|---|---|
| Application Load Balancer | Public entry point, health checks, and routing to the two tiers | Expose EC2 application instances directly |
| Advisor tier | Serve the form, validate input, request weather facts, call Gemini for advice, render reports, and handle email requests | Call weather APIs directly or invent measured values |
| Weather Data tier | Convert ZIP/date into normalized Morning and Night weather facts | Call Gemini, send email, or process the user's email address |
| DynamoDB | Store cached facts, temporary saved reports, call counters, and rate-limit state with TTL | Retain personal data longer than necessary |
| SSM Parameter Store | Store the Gemini API key securely | Be readable by the Weather tier |
| Gemini API | Generate road, clothing, and accessory advice from supplied facts | Generate or replace measured weather values |
| Amazon SNS | Handle confirmed email delivery | Send one user's report to another user |
| Python boto3 stack | Create and delete AWS resources idempotently | Depend on bash or manually executed infrastructure steps |

---

## 4. Public Network Flow

The Application Load Balancer is the only public application entry point.

```text
Internet
   |
   v
Application Load Balancer
   |
   +---- listener 8080 ----> Advisor target group
   |
   +---- listener 8081 ----> Weather Data target group
```

The EC2 application instances are not directly exposed on their application port.

The application security group accepts application traffic only from the ALB security group.

---

## 5. Report Request Flow

### Step 1

The user submits:

- date
- five-digit US ZIP code
- gender/clothing category
- email address

to the Advisor tier.

### Step 2

The Advisor tier performs server-side validation.

Invalid data ends the request before unnecessary outside API calls are made.

Examples include:

- invalid date
- non-US postal code
- malformed email
- unsupported gender value

### Step 3

The Advisor tier checks whether a fresh saved report already exists.

If a valid cached report exists, it may be returned immediately.

### Step 4

If weather facts are required, the Advisor tier calls the Weather Data tier.

### Step 5

The Weather Data tier:

1. validates the ZIP again as required
2. converts the ZIP to location coordinates
3. determines the local timezone
4. retrieves weather information
5. selects the Morning and Night periods
6. calculates normalized values
7. derives Rain and Snow categories
8. caches the facts in DynamoDB

### Step 6

The Weather Data tier returns normalized facts to the Advisor tier.

Gemini has not been involved at this point.

### Step 7

The Advisor tier checks the Gemini daily call cap.

If Gemini is available and the cap has not been reached, the Advisor sends only:

- normalized weather facts
- clothing category

to Gemini.

The email address is never sent to Gemini.

### Step 8

Gemini returns structured advice for:

- suggested road conditions
- suggested dressing
- suggested accessories

The Advisor tier validates the response before displaying it.

### Step 9

If Gemini fails, exceeds quota, times out, or returns invalid data, the application uses deterministic rule-based fallback advice.

### Step 10

The final report is shown to the user and may be temporarily saved with a TTL.

---

## 6. Email Request Flow

### Step 1

The user clicks the email button from the report page.

### Step 2

The Advisor tier validates the email address and checks the per-visitor email request limit.

### Step 3

If the recipient has not confirmed consent, the Advisor tier initiates the Amazon SNS subscription confirmation process.

The application tells the user that confirmation is required before the report can be delivered.

### Step 4

After confirmation, the report is sent only to the intended recipient.

### Step 5

The user receives a clear application status such as:

- confirmation required
- sent
- failed

The email address is never sent to Gemini and must not be written to application logs.

---

## 7. Data Classification

### Measured or Forecast Facts

These must come from weather data APIs:

- temperature
- wind speed
- visibility
- UV
- humidity
- precipitation values
- snowfall values

Gemini cannot provide these values.

### Derived Categories

These are calculated by application code using documented thresholds:

- Rain: Heavy / Mild / No
- Snow: Heavy / Mild / No

The same input data must always produce the same category.

### Advice

Gemini may generate:

- suggested road conditions
- suggested dressing
- suggested accessories

The advice is based only on validated weather facts and the fixed clothing category.

---

## 8. Time Period Definitions

All time calculations use the local timezone of the ZIP-code location.

### Morning

```text
06:00 through 11:59 local time
```

### Night

```text
18:00 through 23:59 local time
```

The selected date must fall within the seven-calendar-day project window.

---

## 9. Availability and Failure Behavior

The application is designed to degrade safely.

### Invalid Postal Code

Reject the request before any external weather or Gemini call.

### Valid Format but Unknown ZIP

Return a clear ZIP-not-found response and do not call Gemini.

### Weather API Unavailable

Use recent cached facts if available.

Otherwise, show that weather data is unavailable.

Never invent weather values.

### One Weather Field Unavailable

Show:

```text
Not available
```

for that field while keeping the rest of the report usable.

### Gemini Unavailable

Show the weather facts and use rule-based fallback advice.

### Gemini Daily Cap Reached

Use the same fallback advice and log the cap event.

### Email Service Failure

Tell the user the report was not sent.

Do not claim success until the email service accepts the request.

### EC2 Instance Failure

The Auto Scaling Group replaces the failed instance and the ALB routes traffic to healthy instances.

No user-required state is stored only on an EC2 instance.

---

## 10. Security Design

The system applies the following controls:

- server-side validation on all inputs
- fixed allowed gender/clothing values
- no user free text sent to Gemini
- Gemini API key stored in encrypted SSM Parameter Store
- separate IAM role for each tier
- least-privilege IAM permissions
- EC2 application ports reachable only from the ALB
- rate limits for public API requests
- daily Gemini call cap
- email request limits
- output validation before rendering
- escaping of untrusted API and Gemini output
- TTL on temporary DynamoDB records
- no logging of email addresses or gender
- no email address sent to Gemini

---

## 11. Infrastructure Ownership

All AWS infrastructure is created and deleted using Python and boto3.

The project does not use Terraform or bash for final-project deployment.

Create operations are designed to be idempotent.

Delete operations tolerate resources that are already missing.

---

## 12. Architecture Rationale

The two-tier design is retained because it provides:

- independent scaling
- separate IAM permissions
- smaller security blast radius
- clearer responsibility boundaries
- easier testing
- isolation of measured facts from AI-generated advice

The architecture also reuses the working Lab06 design instead of introducing unnecessary infrastructure changes.

---
