# Weather Advisor Source Map and API Investigation

## 1. Purpose

The Weather Advisor must display ten items for both the Morning and Night periods:

1. Temperature
2. Wind speed
3. Visibility
4. UV
5. Humidity
6. Rain category
7. Snow category
8. Suggested road conditions
9. Suggested dressing
10. Suggested accessories

Measured and forecast values must come from weather data sources.

Gemini is used only for advice and must never invent measured weather values.

---

## 2. API Sources Selected

The project uses the following sources:

| Source | Purpose |
|---|---|
| Zippopotam.us | Convert a five-digit US ZIP code into latitude, longitude, city and state |
| National Weather Service API | Primary weather forecast source |
| Open-Meteo | Supplemental source for UV and visibility when NWS visibility data is unavailable |
| Application code | Deterministic Rain and Snow categories |
| Google Gemini | Road, dressing and accessory advice only |
| Rule-based application logic | Fallback advice when Gemini cannot be used |

The National Weather Service remains the primary weather-data source.

Open-Meteo is used only to fill fields that are not reliably available from the NWS response required for the report.

---

# 3. Real ZIP Lookup Investigation

A real request was performed for:

```text
ZIP: 60616
```

The Zippopotam response returned:

```text
Country: United States
Post code: 60616
Place: Chicago
State: Illinois
Latitude: 41.8426
Longitude: -87.6306
```

These coordinates were then used for the National Weather Service `/points` request.

---

# 4. National Weather Service Point Investigation

The following point was queried:

```text
Latitude: 41.8426
Longitude: -87.6306
```

The NWS `/points` response returned:

```text
Weather Forecast Office: LOT
Grid X: 76
Grid Y: 71
Time zone: America/Chicago
```

The returned forecast endpoints were:

```text
Forecast:
https://api.weather.gov/gridpoints/LOT/76,71/forecast

Hourly forecast:
https://api.weather.gov/gridpoints/LOT/76,71/forecast/hourly

Grid forecast data:
https://api.weather.gov/gridpoints/LOT/76,71
```

This proves the application can follow this flow:

```text
ZIP
 |
 v
Zippopotam
 |
 v
latitude + longitude
 |
 v
NWS /points
 |
 +--> local timezone
 |
 +--> NWS grid location
 |
 +--> hourly forecast
 |
 +--> detailed grid forecast
```

---

# 5. Local Time Handling

For ZIP `60616`, the NWS API returned:

```text
America/Chicago
```

All Morning and Night calculations therefore use the timezone returned for the ZIP location rather than:

- UTC
- the EC2 server timezone
- the user's browser timezone

The project defines:

```text
Morning = 06:00 through 11:59 local time
Night   = 18:00 through 23:59 local time
```

---

# 6. NWS Hourly Forecast Evidence

A real hourly forecast response for Chicago contained the following example.

## Example Hour 1

```text
startTime: 2026-11-15T17:00:00-06:00
temperature: 46 F
probabilityOfPrecipitation: 0 percent
relativeHumidity: 60 percent
windSpeed: 5 mph
windDirection: E
shortForecast: Sunny
```

## Example Hour 2

```text
startTime: 2026-11-15T18:00:00-06:00
temperature: 43 F
probabilityOfPrecipitation: 0 percent
relativeHumidity: 68 percent
windSpeed: 5 mph
windDirection: SE
shortForecast: Mostly Clear
```

The offset:

```text
-06:00
```

is consistent with the returned local timezone for Chicago.

---

# 7. NWS Grid Data Investigation

The NWS detailed grid response contained fields including:

```text
temperature
windSpeed
visibility
relativeHumidity
probabilityOfPrecipitation
quantitativePrecipitation
snowfallAmount
```

Additional fields included:

```text
apparentTemperature
dewpoint
windGust
weather
iceAccumulation
skyCover
snowLevel
pressure
```

The project does not assume every property will always contain values.

---

# 8. Real NWS Grid Values

## Temperature

NWS field:

```text
temperature
```

Unit:

```text
wmoUnit:degC
```

Example values:

```text
2026-11-15T15:00:00+00:00 -> 5.5556 C
2026-11-15T16:00:00+00:00 -> 7.7778 C
2026-11-15T17:00:00+00:00 -> 9.4444 C
```

---

## Wind Speed

NWS field:

```text
windSpeed
```

Unit:

```text
wmoUnit:km_h-1
```

Example values:

```text
2026-11-15T15:00:00+00:00 -> 7.408 km/h
2026-11-15T19:00:00+00:00 -> 5.556 km/h
2026-11-15T23:00:00+00:00 -> 7.408 km/h
```

---

## Relative Humidity

NWS field:

```text
relativeHumidity
```

Unit:

```text
wmoUnit:percent
```

Example values:

```text
2026-11-15T15:00:00+00:00 -> 63 percent
2026-11-15T16:00:00+00:00 -> 51 percent
2026-11-15T17:00:00+00:00 -> 52 percent
```

---

## Probability of Precipitation

NWS field:

```text
probabilityOfPrecipitation
```

Unit:

```text
wmoUnit:percent
```

Example values:

```text
2026-11-15T15:00:00+00:00 -> 0 percent
2026-11-19T12:00:00+00:00 -> 8 percent
2026-11-19T18:00:00+00:00 -> 5 percent
```

---

## Quantitative Precipitation

NWS field:

```text
quantitativePrecipitation
```

Unit:

```text
wmoUnit:mm
```

Example values:

```text
2026-11-15T15:00:00+00:00 -> 0 mm
2026-11-15T18:00:00+00:00 -> 0 mm
2026-11-16T00:00:00+00:00 -> 0 mm
```

This field will be used with precipitation probability when deriving the Rain category.

---

## Snowfall

NWS field:

```text
snowfallAmount
```

Unit:

```text
wmoUnit:mm
```

Example values:

```text
2026-11-15T15:00:00+00:00 -> 0 mm
2026-11-15T18:00:00+00:00 -> 0 mm
2026-11-16T00:00:00+00:00 -> 0 mm
```

This measured value is used by application code to derive the Snow category.

---

# 9. Visibility Gap Found During Investigation

The NWS grid response contained the property:

```text
visibility
```

However, for the real Chicago request used during investigation, the field contained no usable forecast values.

This is treated as missing data.

The application must not interpret an absent value as:

```text
0
```

because:

```text
0 visibility
```

has a completely different meaning from:

```text
visibility data unavailable
```

Therefore a supplemental source is required for this field when NWS does not provide usable visibility values.

---

# 10. Open-Meteo Supplemental Investigation

Open-Meteo was tested using the same coordinates:

```text
Latitude: 41.8426
Longitude: -87.6306
Timezone: America/Chicago
Forecast days: 7
```

The hourly fields investigated were:

```text
visibility
uv_index
```

---

# 11. Open-Meteo Visibility Evidence

Open-Meteo returned visibility in:

```text
meters
```

Real example values included:

```text
2026-11-15T00:00 -> 17500 m
2026-11-15T01:00 -> 19500 m
2026-11-15T02:00 -> 18200 m
2026-11-15T03:00 -> 15800 m
2026-11-15T04:00 -> 17000 m
2026-11-15T05:00 -> 16000 m
2026-11-15T06:00 -> 15600 m
2026-11-15T07:00 -> 15100 m
```

Open-Meteo will therefore act as the visibility fallback when the NWS visibility field has no usable values.

The final displayed unit may be converted into miles for readability, but the original source value is retained as measured data.

---

# 12. Open-Meteo UV Evidence

The hourly Open-Meteo response also returned:

```text
uv_index
```

Example nighttime and early-morning values were:

```text
2026-11-15T00:00 -> 0.0
2026-11-15T01:00 -> 0.0
2026-11-15T02:00 -> 0.0
2026-11-15T03:00 -> 0.0
2026-11-15T04:00 -> 0.0
2026-11-15T05:00 -> 0.0
2026-11-15T06:00 -> 0.0
2026-11-15T07:00 -> 0.0
```

The API also returned seven-day daily maximum UV values during investigation:

```text
2026-11-15 -> 2.90
2026-11-16 -> 2.90
2026-11-17 -> 2.90
2026-11-18 -> 2.85
2026-11-19 -> 2.70
2026-11-20 -> 2.60
2026-11-21 -> 2.65
```

The application will use hourly UV values when calculating Morning and Night report values because the report requires a separate value for each period.

A daily maximum alone would not correctly represent both Morning and Night.

---

# 13. Final Source Map

| Report Output | Primary Source | API Field | Unit / Type | Period Handling | Gap Handling |
|---|---|---|---|---|---|
| Temperature | NWS | `temperature` / hourly `temperature` | °C or °F | Aggregate hours inside Morning or Night | Show `Not available` if absent |
| Wind speed | NWS | `windSpeed` | km/h or mph | Use sustained wind for the selected period | Show `Not available` if absent |
| Visibility | NWS first, Open-Meteo fallback | NWS `visibility`; Open-Meteo `visibility` | meters, converted for display if needed | Use values inside Morning or Night | Use Open-Meteo when NWS contains no usable values |
| UV | Open-Meteo | `uv_index` | UV Index | Peak hourly UV inside each period | Show `Not available` if missing |
| Humidity | NWS | `relativeHumidity` | percent | Average hourly humidity in each period | Show `Not available` if absent |
| Rain | NWS + application code | `quantitativePrecipitation` and `probabilityOfPrecipitation` | mm + percent -> category | Evaluate the selected period | Show unavailable if required source data cannot be obtained |
| Snow | NWS + application code | `snowfallAmount` | mm -> category | Evaluate snowfall during selected period | Show unavailable if required source data cannot be obtained |
| Suggested road conditions | Gemini | Structured advice field | Advice | Generated from validated facts | Rule-based fallback |
| Suggested dressing | Gemini | Structured advice field | Advice | Weather facts + fixed clothing category | Rule-based fallback |
| Suggested accessories | Gemini | Structured advice field | Advice | Generated from validated facts | Rule-based fallback |

---

# 14. Source Classification

## API Facts

The following values come from weather APIs:

```text
temperature
wind speed
visibility
UV
humidity
precipitation
snowfall
```

They must never be generated by Gemini.

---

## Derived Values

Application code calculates:

```text
Rain = Heavy / Mild / No
Snow = Heavy / Mild / No
```

These classifications use fixed documented thresholds.

Gemini does not determine these categories.

---

## Advice

Gemini may generate only:

```text
suggested road conditions
suggested dressing
suggested accessories
```

Gemini receives validated weather facts.

The application does not trust numbers repeated by Gemini.

The report displays the original facts supplied by the Weather Data tier.

---

# 15. Seven-Day Horizon

The application accepts dates from:

```text
today
```

through:

```text
today + 6 days
```

for a total of seven calendar dates.

The application must confirm that required data exists for the selected date.

A source that does not provide the required field far enough into the requested window cannot silently substitute a value.

---

# 16. Missing-Data Policy

Missing data is never treated as zero.

For example:

```text
visibility missing
```

does not mean:

```text
visibility = 0
```

When a field cannot be obtained:

1. try the documented fallback source if one exists;
2. otherwise display `Not available`;
3. provide the reason where useful;
4. keep the rest of the report working;
5. do not let Gemini invent the missing measurement.

---

# 17. ZIP-Code Scope

The service supports only:

```text
exactly five-digit US ZIP codes
```

Examples that must be rejected before any weather or Gemini request include:

```text
M5V 3L9
SW1A 1AA
6061
606160
ABCDE
empty input
```

A well-formed five-digit ZIP that does not exist is handled separately with:

```text
ZIP code not found
```

The application does not call Gemini for an invalid or unknown ZIP.

---

# 18. Final Data Flow

```text
Five-digit US ZIP
        |
        v
Zippopotam
        |
        +--> city/state
        |
        +--> latitude/longitude
                |
                v
            NWS /points
                |
                +--> timezone
                |
                +--> grid coordinates
                         |
                         v
                   NWS forecast data
                    /            \
                   /              \
             available         missing gap
                 |                 |
                 |                 v
                 |           Open-Meteo
                 |           where documented
                 |                 |
                 +--------+--------+
                          |
                          v
                 normalized facts
                          |
                 +--------+---------+
                 |                  |
                 v                  v
           deterministic          Gemini
           Rain/Snow rules        advice only
                 |                  |
                 +--------+---------+
                          |
                          v
                   final report
```

---

# 19. Investigation Conclusion

The API investigation showed that one source should not be assumed to supply every required value.

The National Weather Service provides the majority of the required forecast information and remains the primary weather source.

The real Chicago response demonstrated that a field such as `visibility` may exist in the NWS schema without containing usable forecast values.

Open-Meteo therefore provides a justified supplemental source for:

- hourly visibility when NWS visibility is unavailable
- hourly UV index

The architecture keeps measured values separate from AI-generated advice and explicitly represents missing data rather than inventing or silently replacing it.
