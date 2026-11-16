# Weather Advisor Report Definition

## 1. Purpose

This document defines exactly how every Morning and Night report value is calculated and displayed.

The report contains the same ten items for both periods:

1. Temperature
2. Wind speed
3. Visibility
4. UV
5. Humidity
6. Rain
7. Snow
8. Suggested road conditions
9. Suggested dressing
10. Suggested accessories

Measured values come from weather APIs.

Rain and Snow categories are calculated deterministically by application code.

Advice comes from Gemini when available and from rule-based fallback logic when Gemini cannot be used.

---

# 2. Supported Date Range

The user may select:

```text
today
```

through:

```text
today + 6 days
```

for a total of seven calendar dates.

The selected date is interpreted in the local timezone of the ZIP-code location.

A date outside this window is rejected on the server.

---

# 3. Local Time Rules

The application uses the timezone returned for the ZIP-code location.

The application does not use:

- UTC for report periods
- the EC2 server timezone
- the browser timezone

For example, ZIP `60616` returned:

```text
America/Chicago
```

---

# 4. Morning Period

Morning is defined as:

```text
06:00 through 11:59 local time
```

All source observations or forecast values whose local timestamps fall inside this window are candidates for Morning aggregation.

---

# 5. Night Period

Night is defined as:

```text
18:00 through 23:59 local time
```

This period does not cross midnight.

All source observations or forecast values whose local timestamps fall inside this window are candidates for Night aggregation.

---

# 6. Temperature

## Source

Primary source:

```text
National Weather Service
```

Relevant field:

```text
temperature
```

## Aggregation

For each period, the application reports a temperature range:

```text
minimum - maximum
```

Example:

```text
42°F - 48°F
```

This is more informative than a single midpoint because the Morning and Night periods cover several hours.

## Advice Input

The application may also use the average temperature internally when generating advice.

## Missing Data

If no temperature values are available:

```text
Not available
```

is shown.

Gemini must not invent a temperature.

---

# 7. Wind Speed

## Source

Primary source:

```text
National Weather Service
```

Relevant field:

```text
windSpeed
```

## Aggregation

The report displays the maximum sustained wind speed during the period.

Example:

```text
12 mph
```

Using the maximum provides a conservative value for road and clothing advice.

If wind gust data is available, it may be preserved internally for road-condition advice, but the report's main Wind Speed row represents sustained wind.

## Missing Data

If no usable wind values exist:

```text
Not available
```

is shown.

---

# 8. Visibility

## Source

Preferred source:

```text
National Weather Service visibility
```

Fallback source:

```text
Open-Meteo hourly visibility
```

The fallback is necessary because the real NWS Chicago response contained the `visibility` property but no usable values.

## Aggregation

For each period, the application displays the lowest visibility value.

This represents the worst expected visibility during that period and is most useful for travel advice.

The source value may be provided in meters and converted into miles for user-friendly display.

Example:

```text
9.4 mi
```

## Missing Data

If both NWS and Open-Meteo fail to provide visibility:

```text
Not available
```

is shown.

The application does not substitute zero.

---

# 9. UV Index

## Source

```text
Open-Meteo hourly uv_index
```

## Aggregation

For each period, the application displays the highest hourly UV Index value.

Example:

```text
UV 3.1
```

The peak is selected because UV safety recommendations depend on the strongest expected exposure during the period.

At night the expected value will normally be:

```text
0
```

when that zero is actually returned by the source.

A real zero must be distinguished from missing data.

## Missing Data

If UV data is unavailable:

```text
Not available
```

is shown.

Advice must not assume a UV value that was not retrieved.

---

# 10. Humidity

## Source

Primary source:

```text
National Weather Service relativeHumidity
```

## Aggregation

The report displays the arithmetic average of available hourly humidity values during the selected period.

Example:

```text
64%
```

The result is rounded to the nearest whole percentage.

## Missing Data

If no humidity values are available:

```text
Not available
```

is shown.

---

# 11. Rain Category

The Rain row is a deterministic category calculated by application code.

Possible values are:

```text
No
Mild
Heavy
```

Gemini does not determine the Rain category.

## Source Inputs

The application uses:

```text
quantitativePrecipitation
probabilityOfPrecipitation
```

from the National Weather Service.

## Initial Threshold Design

The application first calculates the maximum precipitation amount associated with the selected period.

The classification is:

```text
No:
precipitation amount = 0 mm
AND precipitation probability < 20%

Mild:
precipitation amount > 0 mm and < 7.6 mm
OR precipitation probability >= 20% when measurable precipitation is expected

Heavy:
precipitation amount >= 7.6 mm during the relevant period
```

The value:

```text
7.6 mm
```

is approximately:

```text
0.30 inches
```

The final submission will cite the published meteorological reference used to justify the heavy-rain threshold.

## Boundary Tests

Tests must include:

```text
0 mm
just below 7.6 mm
exactly 7.6 mm
just above 7.6 mm
```

Probability boundaries must also be tested.

## Missing Data

If both precipitation amount and probability are unavailable:

```text
Not available
```

is shown.

The application must not treat missing precipitation as zero.

---

# 12. Snow Category

The Snow row is also calculated deterministically by application code.

Possible values are:

```text
No
Mild
Heavy
```

Gemini does not determine this category.

## Source

NWS field:

```text
snowfallAmount
```

## Initial Threshold Design

The classification is:

```text
No:
snowfall amount = 0 mm

Mild:
snowfall amount > 0 mm and < 50.8 mm

Heavy:
snowfall amount >= 50.8 mm
```

The value:

```text
50.8 mm
```

is approximately:

```text
2 inches
```

The final submission will cite a published source for the selected heavy-snow threshold.

## Boundary Tests

Tests must include:

```text
0 mm
just below 50.8 mm
exactly 50.8 mm
just above 50.8 mm
```

## Missing Data

If snowfall information is unavailable:

```text
Not available
```

is shown.

---

# 13. Suggested Road Conditions

## Primary Source

```text
Google Gemini
```

This is advice, not a measured value.

Gemini may use validated facts including:

- Rain category
- Snow category
- temperature
- visibility
- wind speed

A valid answer must be short and practical.

Example:

```text
Roads should remain mostly dry, but reduced visibility may require slower driving.
```

## Fallback

If Gemini cannot be used, deterministic application logic generates a rule-based road recommendation.

Examples include:

```text
Heavy snow + freezing temperature:
Expect potentially icy or snow-covered roads. Reduce speed and allow extra stopping distance.

Low visibility:
Visibility may be reduced. Use headlights and increase following distance.

No significant hazards:
No major weather-related road hazards are expected.
```

---

# 14. Suggested Dressing

## Primary Source

```text
Google Gemini
```

Gemini receives:

- validated weather facts
- fixed clothing category

The application does not send free-text gender input to Gemini.

Example clothing categories are:

```text
menswear
womenswear
neutral
```

The user interface explains that this selection is used only to tailor clothing suggestions.

## Fallback

Rule-based application logic provides recommendations based on:

- temperature
- wind
- humidity
- rain
- snow

Examples:

```text
Cold:
Wear a warm jacket and layered clothing.

Rain:
Use a waterproof outer layer.

Very cold:
Wear an insulated coat, gloves and warm layers.

Warm:
Wear lightweight clothing.
```

---

# 15. Suggested Accessories

## Primary Source

```text
Google Gemini
```

Gemini may recommend items based on validated facts such as:

- rain
- snow
- UV
- temperature
- wind

Examples include:

```text
umbrella
sunglasses
sunscreen
gloves
scarf
```

## Fallback

Rule-based logic selects accessories from fixed conditions.

Examples:

```text
Rain:
Umbrella

High UV:
Sunglasses and sunscreen

Cold:
Gloves and scarf

Snow:
Water-resistant footwear and gloves
```

---

# 16. Structured Gemini Output

Gemini must return structured data rather than arbitrary free-form text.

The intended logical shape is:

```json
{
  "road_conditions": "short practical advice",
  "dressing": "short clothing advice",
  "accessories": "short accessory advice"
}
```

The application validates:

- all required keys exist
- each value is a string
- each string is within the maximum allowed length
- no unexpected nested structures are accepted
- output is escaped before rendering

If validation fails, the response is rejected and rule-based fallback advice is used.

---

# 17. Morning and Night Report Shape

Each report has two columns:

```text
Morning
Night
```

Each column contains:

```text
Temperature
Wind speed
Visibility
UV
Humidity
Rain
Snow
Suggested road conditions
Suggested dressing
Suggested accessories
```

Example structure:

| Item | Morning | Night |
|---|---|---|
| Temperature | 42°F - 48°F | 35°F - 41°F |
| Wind speed | 8 mph | 12 mph |
| Visibility | 9.4 mi | 8.1 mi |
| UV | 2.9 | 0 |
| Humidity | 61% | 72% |
| Rain | No | Mild |
| Snow | No | No |
| Suggested road conditions | Dry roads expected | Wet roads possible |
| Suggested dressing | Light jacket | Warm jacket |
| Suggested accessories | Sunglasses | Umbrella |

---

# 18. Source Attribution

The report must preserve information about where measured facts originated.

Possible labels include:

```text
National Weather Service
Open-Meteo
```

The application does not label Gemini as the source of any measured value.

Gemini is identified only as the source of generated advice when Gemini advice was successfully used.

Fallback advice is clearly identified as rule-based advice.

---

# 19. Missing Fields

A missing field does not cause the whole report to fail.

If one item is unavailable:

```text
Not available
```

is displayed for that item.

The rest of the report continues to work.

Advice must not rely on a missing measurement.

---

# 20. Report Definition Summary

The final report follows these principles:

```text
Facts = weather APIs
Categories = deterministic application code
Advice = Gemini or deterministic fallback
```

The system never:

- asks Gemini to invent measured weather
- converts missing data to zero
- uses server time for Morning or Night
- silently hides missing fields
- trusts unvalidated Gemini output
