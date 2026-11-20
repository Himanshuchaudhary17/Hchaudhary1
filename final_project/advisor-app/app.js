const express = require('express');
const crypto = require('crypto');

const {
  SSMClient,
  GetParameterCommand,
} = require('@aws-sdk/client-ssm');

const {
  SNSClient,
  SubscribeCommand,
  PublishCommand,
  ListSubscriptionsByTopicCommand,
} = require('@aws-sdk/client-sns');

const {
  DynamoDBClient,
} = require('@aws-sdk/client-dynamodb');

const {
  DynamoDBDocumentClient,
  GetCommand,
  PutCommand,
  UpdateCommand,
} = require('@aws-sdk/lib-dynamodb');


const app = express();

app.use(
  express.urlencoded({
    extended: false,
  })
);

app.use(express.json());


const PORT =
  Number(process.env.PORT || 3000);

const AWS_REGION =
  process.env.AWS_REGION || 'us-east-2';

const WEATHER_URL =
  process.env.WEATHER_URL ||
  'http://127.0.0.1:3001';

const ADVISOR_TABLE =
  process.env.ADVISOR_TABLE ||
  'itmo-544-final-advisor-state';

const SNS_TOPIC_ARN =
  process.env.SNS_TOPIC_ARN || '';

const GEMINI_API_BASE =
  process.env.GEMINI_API_BASE ||
  'https://generativelanguage.googleapis.com';

const GEMINI_MODEL =
  process.env.GEMINI_MODEL ||
  'gemini-3.1-flash-lite';

const GEMINI_KEY_PARAM =
  process.env.GEMINI_KEY_PARAM ||
  '/itmo-544/final/gemini-api-key';

const KEY_CACHE_MS =
  Number(
    process.env.KEY_CACHE_SECONDS || 300
  ) * 1000;

const GEMINI_DAILY_LIMIT =
  Number(
    process.env.GEMINI_DAILY_LIMIT || 100
  );

const VISITOR_REQUEST_LIMIT =
  Number(
    process.env.VISITOR_REQUEST_LIMIT || 30
  );

const REQUEST_WINDOW_SECONDS =
  Number(
    process.env.REQUEST_WINDOW_SECONDS || 3600
  );

const EMAIL_REQUEST_LIMIT =
  Number(
    process.env.EMAIL_REQUEST_LIMIT || 5
  );

const REPORT_CACHE_SECONDS =
  Number(
    process.env.REPORT_CACHE_SECONDS || 600
  );


const ssm =
  new SSMClient({
    region: AWS_REGION,
  });

const dynamodb =
  DynamoDBDocumentClient.from(
    new DynamoDBClient({
      region: AWS_REGION,
    })
  );

const sns =
  new SNSClient({
    region: AWS_REGION,
  });


let cachedKey = {
  value: null,
  at: 0,
};


const CLOTHING_OPTIONS = {
  menswear: 'Menswear',
  womenswear: 'Womenswear',
  neutral: 'Gender-neutral',
};


const log = (
  event,
  fields = {}
) => {
  console.log(
    JSON.stringify({
      ts: new Date().toISOString(),
      event,
      ...fields,
    })
  );
};


function escapeHtml(value) {
  return String(
    value === null ||
    value === undefined
      ? ''
      : value
  ).replace(
    /[&<>"']/g,
    (character) =>
      ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      }[character])
  );
}


function validZip(zip) {
  return /^\d{5}$/.test(zip);
}


function validDateFormat(date) {
  if (
    !/^\d{4}-\d{2}-\d{2}$/.test(date)
  ) {
    return false;
  }

  const [
    year,
    month,
    day,
  ] = date.split('-').map(Number);

  const parsed =
    new Date(
      Date.UTC(
        year,
        month - 1,
        day
      )
    );

  return (
    parsed.getUTCFullYear() === year &&
    parsed.getUTCMonth() === month - 1 &&
    parsed.getUTCDate() === day
  );
}


function validClothingCategory(value) {
  return Object.prototype.hasOwnProperty.call(
    CLOTHING_OPTIONS,
    value
  );
}


function validEmail(email) {
  if (
    typeof email !== 'string' ||
    email.length > 254
  ) {
    return false;
  }

  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(
    email
  );
}


function clientId(req) {
  const forwarded =
    String(
      req.headers[
        'x-forwarded-for'
      ] || ''
    )
      .split(',')[0]
      .trim();

  const raw =
    forwarded ||
    req.socket.remoteAddress ||
    'unknown';

  let hash = 2166136261;

  for (
    let i = 0;
    i < raw.length;
    i++
  ) {
    hash ^= raw.charCodeAt(i);

    hash = Math.imul(
      hash,
      16777619
    );
  }

  return (
    hash >>> 0
  ).toString(16);
}


function unixNow() {
  return Math.floor(
    Date.now() / 1000
  );
}


function utcDateString() {
  return new Date()
    .toISOString()
    .slice(0, 10);
}


async function getApiKey() {
  if (
    process.env.GEMINI_API_KEY
  ) {
    return (
      process.env.GEMINI_API_KEY
    );
  }

  if (
    cachedKey.value &&
    Date.now() - cachedKey.at <
      KEY_CACHE_MS
  ) {
    return cachedKey.value;
  }

  const response =
    await ssm.send(
      new GetParameterCommand({
        Name:
          GEMINI_KEY_PARAM,
        WithDecryption: true,
      })
    );

  if (
    !response.Parameter ||
    !response.Parameter.Value
  ) {
    throw new Error(
      'gemini_key_missing'
    );
  }

  cachedKey = {
    value:
      response.Parameter.Value,
    at: Date.now(),
  };

  return cachedKey.value;
}


async function consumeVisitorRequest(
  visitor
) {
  const window =
    Math.floor(
      unixNow() /
      REQUEST_WINDOW_SECONDS
    );

  const pk =
    `RATE#${visitor}#${window}`;

  const expiresAt =
    unixNow() +
    REQUEST_WINDOW_SECONDS +
    300;

  try {
    const response =
      await dynamodb.send(
        new UpdateCommand({
          TableName:
            ADVISOR_TABLE,

          Key: {
            pk,
          },

          UpdateExpression:
            'SET #count = if_not_exists(#count, :zero) + :one, expiresAt = :expires',

          ExpressionAttributeNames: {
            '#count': 'count',
          },

          ExpressionAttributeValues: {
            ':zero': 0,
            ':one': 1,
            ':expires':
              expiresAt,
            ':limit':
              VISITOR_REQUEST_LIMIT,
          },

          ConditionExpression:
            'attribute_not_exists(#count) OR #count < :limit',

          ReturnValues:
            'UPDATED_NEW',
        })
      );

    return {
      allowed: true,
      count:
        response.Attributes
          ?.count || 1,
    };
  } catch (err) {
    if (
      err.name ===
      'ConditionalCheckFailedException'
    ) {
      return {
        allowed: false,
      };
    }

    log(
      'rate_limit_storage_error',
      {
        message:
          err.message,
      }
    );

    return {
      allowed: true,
      degraded: true,
    };
  }
}


async function reserveGeminiCall() {
  const today =
    utcDateString();

  const pk =
    `GEMINI#${today}`;

  const tomorrow =
    unixNow() + 172800;

  try {
    const response =
      await dynamodb.send(
        new UpdateCommand({
          TableName:
            ADVISOR_TABLE,

          Key: {
            pk,
          },

          UpdateExpression:
            'SET #count = if_not_exists(#count, :zero) + :one, expiresAt = :expires',

          ExpressionAttributeNames: {
            '#count': 'count',
          },

          ExpressionAttributeValues: {
            ':zero': 0,
            ':one': 1,
            ':limit':
              GEMINI_DAILY_LIMIT,
            ':expires':
              tomorrow,
          },

          ConditionExpression:
            'attribute_not_exists(#count) OR #count < :limit',

          ReturnValues:
            'UPDATED_NEW',
        })
      );

    return {
      allowed: true,
      count:
        response.Attributes
          ?.count || 1,
      limit:
        GEMINI_DAILY_LIMIT,
    };
  } catch (err) {
    if (
      err.name ===
      'ConditionalCheckFailedException'
    ) {
      return {
        allowed: false,
        limit:
          GEMINI_DAILY_LIMIT,
      };
    }

    log(
      'gemini_counter_error',
      {
        message:
          err.message,
      }
    );

    return {
      allowed: false,
      storageError: true,
    };
  }
}


async function fetchWeather(
  zip,
  date
) {
  const url =
    `${WEATHER_URL}` +
    `/weather` +
    `?zip=${encodeURIComponent(
      zip
    )}` +
    `&date=${encodeURIComponent(
      date
    )}`;

  const response =
    await fetch(
      url,
      {
        signal:
          AbortSignal.timeout(
            20000
          ),
      }
    );

  let body = {};

  try {
    body =
      await response.json();
  } catch (err) {
    throw new Error(
      'weather_invalid_json'
    );
  }

  return {
    status:
      response.status,
    ok:
      response.ok,
    body,
  };
}


function formatTemperature(
  temperature
) {
  if (
    !temperature ||
    temperature.min === null ||
    temperature.max === null
  ) {
    return 'Not available';
  }

  return (
    `${temperature.min}°` +
    `${temperature.unit}` +
    ` - ` +
    `${temperature.max}°` +
    `${temperature.unit}`
  );
}


function formatWind(
  wind
) {
  if (
    !wind ||
    wind.maxMph === null
  ) {
    return 'Not available';
  }

  return (
    `${wind.maxMph} mph`
  );
}


function formatVisibility(
  visibility
) {
  if (
    !visibility ||
    visibility.miles === null
  ) {
    return 'Not available';
  }

  return (
    `${visibility.miles} mi`
  );
}


function formatUv(uv) {
  if (
    !uv ||
    uv.max === null
  ) {
    return 'Not available';
  }

  return String(
    uv.max
  );
}


function formatHumidity(
  humidity
) {
  if (
    !humidity ||
    humidity.averagePercent === null
  ) {
    return 'Not available';
  }

  return (
    `${humidity.averagePercent}%`
  );
}


function normalizedFacts(period) {
  return {
    temperature:
      formatTemperature(
        period.temperature
      ),

    wind:
      formatWind(
        period.windSpeed
      ),

    visibility:
      formatVisibility(
        period.visibility
      ),

    uv:
      formatUv(
        period.uv
      ),

    humidity:
      formatHumidity(
        period.humidity
      ),

    rain:
      period.rain ||
      'Not available',

    snow:
      period.snow ||
      'Not available',
  };
}


function fallbackAdvice(
  period,
  clothingCategory
) {
  const tempMin =
    period.temperature
      ?.min;

  const tempMax =
    period.temperature
      ?.max;

  const visibility =
    period.visibility
      ?.miles;

  const wind =
    period.windSpeed
      ?.maxMph;

  const uv =
    period.uv
      ?.max;

  const rain =
    period.rain;

  const snow =
    period.snow;


  let roadConditions =
    'No major weather-related road hazards are expected.';

  if (
    snow === 'Heavy'
  ) {
    roadConditions =
      'Snow-covered or slippery roads are possible. Reduce speed and allow extra stopping distance.';
  } else if (
    snow === 'Mild'
  ) {
    roadConditions =
      'Light snow may create slick spots. Drive carefully and allow extra stopping distance.';
  } else if (
    rain === 'Heavy'
  ) {
    roadConditions =
      'Heavy rain may reduce traction and visibility. Slow down and increase following distance.';
  } else if (
    rain === 'Mild'
  ) {
    roadConditions =
      'Wet roads are possible. Use normal caution and allow extra braking distance.';
  } else if (
    visibility !== null &&
    visibility !== undefined &&
    visibility < 3
  ) {
    roadConditions =
      'Visibility may be reduced. Use headlights and increase following distance.';
  } else if (
    wind !== null &&
    wind !== undefined &&
    wind >= 30
  ) {
    roadConditions =
      'Strong winds may affect high-profile vehicles. Use extra caution while driving.';
  }


  let dressing =
    'Wear comfortable clothing appropriate for the forecast.';

  if (
    tempMax !== null &&
    tempMax !== undefined
  ) {
    if (
      tempMax <= 32
    ) {
      dressing =
        'Wear an insulated winter coat with warm layers.';
    } else if (
      tempMax <= 50
    ) {
      dressing =
        'Wear a warm jacket with long layers.';
    } else if (
      tempMax <= 68
    ) {
      dressing =
        'Wear a light jacket or sweater with comfortable layers.';
    } else if (
      tempMax <= 80
    ) {
      dressing =
        'Wear lightweight everyday clothing.';
    } else {
      dressing =
        'Wear light, breathable clothing.';
    }
  }

  if (
    clothingCategory ===
    'menswear'
  ) {
    dressing +=
      ' Choose a menswear style if preferred.';
  } else if (
    clothingCategory ===
    'womenswear'
  ) {
    dressing +=
      ' Choose a womenswear style if preferred.';
  } else {
    dressing +=
      ' Choose gender-neutral layers if preferred.';
  }


  const accessories = [];

  if (
    rain === 'Mild' ||
    rain === 'Heavy'
  ) {
    accessories.push(
      'umbrella'
    );
  }

  if (
    snow === 'Mild' ||
    snow === 'Heavy'
  ) {
    accessories.push(
      'water-resistant footwear'
    );
  }

  if (
    tempMin !== null &&
    tempMin !== undefined &&
    tempMin <= 40
  ) {
    accessories.push(
      'gloves'
    );
  }

  if (
    uv !== null &&
    uv !== undefined &&
    uv >= 3
  ) {
    accessories.push(
      'sunglasses',
      'sunscreen'
    );
  }

  if (
    accessories.length === 0
  ) {
    accessories.push(
      'no special accessories'
    );
  }

  return {
    road_conditions:
      roadConditions,

    dressing,

    accessories:
      accessories.join(', '),
  };
}


const SYSTEM_PROMPT = `
You are the advice component of a weather application.

You MUST follow these rules:

1. Use only the weather facts supplied by the application.
2. Do not invent any weather measurement.
3. Do not repeat, quote, restate, or include numeric weather measurements.
4. Do not include temperatures, wind speeds, visibility distances, UV values, humidity percentages, precipitation amounts, or other measured numbers in advice.
5. Describe conditions qualitatively, such as "cool conditions", "breezy conditions", or "reduced visibility".
6. Do not change or reinterpret the supplied Rain or Snow categories.
7. Generate exactly three pieces of advice:
   road_conditions
   dressing
   accessories
8. Keep each value under 220 characters.
9. Output valid JSON only.
10. Do not use markdown.
11. Do not include extra keys.
12. The clothing category is a fixed application category, not free-text user input.
13. If a fact is marked Not available, do not pretend to know it.

Required JSON shape:

{
  "road_conditions": "short practical road advice",
  "dressing": "short practical clothing advice",
  "accessories": "short practical accessory advice"
}
`.trim();


function buildGeminiPrompt(
  weather,
  clothingCategory,
  periodName
) {
  const period =
    weather.periods[
      periodName
    ];

  const facts =
    normalizedFacts(
      period
    );

  return JSON.stringify(
    {
      location: {
        city:
          weather.location.city,
        state:
          weather.location.state,
      },

      date:
        weather.date,

      period:
        period.period,

      clothing_category:
        clothingCategory,

      facts,
    },
    null,
    2
  );
}


function stripCodeFence(text) {
  let value =
    String(text || '')
      .trim();

  if (
    value.startsWith(
      '```'
    )
  ) {
    value =
      value.replace(
        /^```(?:json)?\s*/i,
        ''
      );

    value =
      value.replace(
        /\s*```$/,
        ''
      );
  }

  return value.trim();
}


function containsMeasuredNumber(
  text
) {
  const value =
    String(text || '');

  const patterns = [
    /\b\d+(?:\.\d+)?\s*°?\s*[FC]\b/i,
    /\b\d+(?:\.\d+)?\s*(?:mph|km\/h|kph|m\/s)\b/i,
    /\b\d+(?:\.\d+)?\s*(?:mi|mile|miles|km|kilometer|kilometers|meter|meters)\b/i,
    /\b\d+(?:\.\d+)?\s*%/,
    /\bUV\s*\d+(?:\.\d+)?\b/i,
    /\b\d+(?:\.\d+)?\s*(?:mm|cm|in|inch|inches)\b/i,
  ];

  return patterns.some(
    (pattern) =>
      pattern.test(value)
  );
}


function validateGeminiAdvice(
  raw
) {
  let parsed;

  try {
    parsed =
      JSON.parse(
        stripCodeFence(
          raw
        )
      );
  } catch (err) {
    return null;
  }

  if (
    !parsed ||
    typeof parsed !== 'object' ||
    Array.isArray(parsed)
  ) {
    return null;
  }

  const keys =
    Object.keys(parsed);

  const required = [
    'road_conditions',
    'dressing',
    'accessories',
  ];

  if (
    keys.length !==
    required.length
  ) {
    return null;
  }

  for (
    const key of required
  ) {
    if (
      !Object.prototype
        .hasOwnProperty
        .call(
          parsed,
          key
        )
    ) {
      return null;
    }

    if (
      typeof parsed[key] !==
      'string'
    ) {
      return null;
    }

    const value =
      parsed[key]
        .trim();

    if (
      value.length < 1 ||
      value.length > 220
    ) {
      return null;
    }

    if (
      containsMeasuredNumber(
        value
      )
    ) {
      return null;
    }

    parsed[key] =
      value;
  }

  return parsed;
}


async function askGemini(
  prompt
) {
  const key =
    await getApiKey();

  const response =
    await fetch(
      `${GEMINI_API_BASE}` +
      `/v1beta/models/` +
      `${encodeURIComponent(
        GEMINI_MODEL
      )}` +
      `:generateContent`,
      {
        method: 'POST',

        headers: {
          'Content-Type':
            'application/json',

          'x-goog-api-key':
            key,
        },

        body:
          JSON.stringify({
            systemInstruction: {
              parts: [
                {
                  text:
                    SYSTEM_PROMPT,
                },
              ],
            },

            contents: [
              {
                role: 'user',

                parts: [
                  {
                    text:
                      prompt,
                  },
                ],
              },
            ],

            generationConfig: {
              temperature: 0.2,
              maxOutputTokens: 400,
              responseMimeType:
                'application/json',
            },
          }),

        signal:
          AbortSignal.timeout(
            15000
          ),
      }
    );

  if (!response.ok) {
    const error =
      new Error(
        'gemini_http_error'
      );

    error.status =
      response.status;

    throw error;
  }

  const data =
    await response.json();

  const parts =
    data.candidates?.[0]
      ?.content
      ?.parts || [];

  const text =
    parts
      .map(
        (part) =>
          part.text || ''
      )
      .join('')
      .trim();

  if (!text) {
    throw new Error(
      'gemini_empty_response'
    );
  }

  const validated =
    validateGeminiAdvice(
      text
    );

  if (!validated) {
    throw new Error(
      'gemini_invalid_output'
    );
  }

  return validated;
}


async function adviceForPeriod(
  weather,
  periodName,
  clothingCategory
) {
  const period =
    weather.periods[
      periodName
    ];

  const fallback =
    fallbackAdvice(
      period,
      clothingCategory
    );

  const reservation =
    await reserveGeminiCall();

  if (
    !reservation.allowed
  ) {
    log(
      'gemini_fallback',
      {
        reason:
          reservation.storageError
            ? 'counter_unavailable'
            : 'daily_cap',
        period:
          periodName,
      }
    );

    return {
      ...fallback,
      source:
        'rule-based fallback',
      reason:
        reservation.storageError
          ? 'Gemini counter unavailable'
          : 'Daily Gemini limit reached',
    };
  }

  try {
    const advice =
      await askGemini(
        buildGeminiPrompt(
          weather,
          clothingCategory,
          periodName
        )
      );

    return {
      ...advice,
      source:
        'Google Gemini',
      reason: null,
    };
  } catch (err) {
    log(
      'gemini_fallback',
      {
        reason:
          err.message,
        status:
          err.status || 0,
        period:
          periodName,
      }
    );

    return {
      ...fallback,
      source:
        'rule-based fallback',
      reason:
        'Gemini unavailable or response invalid',
    };
  }
}


function reportCacheKey(
  weather,
  clothingCategory
) {
  return (
    `REPORTCACHE#` +
    `${weather.zip}#` +
    `${weather.date}#` +
    `${clothingCategory}`
  );
}


async function getCachedReport(
  weather,
  clothingCategory
) {
  const pk =
    reportCacheKey(
      weather,
      clothingCategory
    );

  try {
    const response =
      await dynamodb.send(
        new GetCommand({
          TableName:
            ADVISOR_TABLE,

          Key: {
            pk,
          },
        })
      );

    const item =
      response.Item;

    if (
      !item ||
      !item.report ||
      !item.expiresAt
    ) {
      return null;
    }

    if (
      Number(
        item.expiresAt
      ) <= unixNow()
    ) {
      return null;
    }

    return item.report;
  } catch (err) {
    log(
      'report_cache_read_error',
      {
        message:
          err.message,
      }
    );

    return null;
  }
}


async function saveCachedReport(
  weather,
  clothingCategory,
  report
) {
  const pk =
    reportCacheKey(
      weather,
      clothingCategory
    );

  try {
    await dynamodb.send(
      new PutCommand({
        TableName:
          ADVISOR_TABLE,

        Item: {
          pk,

          report,

          createdAt:
            unixNow(),

          expiresAt:
            unixNow() +
            REPORT_CACHE_SECONDS,
        },
      })
    );
  } catch (err) {
    log(
      'report_cache_write_error',
      {
        message:
          err.message,
      }
    );
  }
}


async function buildReport(
  weather,
  clothingCategory
) {
  const cached =
    await getCachedReport(
      weather,
      clothingCategory
    );

  if (cached) {
    log(
      'report_cache_hit',
      {
        zip:
          weather.zip,

        date:
          weather.date,
      }
    );

    return {
      ...cached,

      cache:
        weather.cache,

      warning:
        weather.warning ||
        cached.warning ||
        null,

      adviceCache:
        'hit',
    };
  }

  const [
    morningAdvice,
    nightAdvice,
  ] = await Promise.all([
    adviceForPeriod(
      weather,
      'morning',
      clothingCategory
    ),

    adviceForPeriod(
      weather,
      'night',
      clothingCategory
    ),
  ]);

  const report = {
    zip:
      weather.zip,

    date:
      weather.date,

    location:
      weather.location,

    clothingCategory,

    cache:
      weather.cache,

    adviceCache:
      'miss',

    warning:
      weather.warning || null,

    morning: {
      facts:
        normalizedFacts(
          weather.periods
            .morning
        ),

      raw:
        weather.periods
          .morning,

      advice:
        morningAdvice,
    },

    night: {
      facts:
        normalizedFacts(
          weather.periods
            .night
        ),

      raw:
        weather.periods
          .night,

      advice:
        nightAdvice,
    },
  };

  await saveCachedReport(
    weather,
    clothingCategory,
    report
  );

  return report;
}


function validateInputs(
  {
    zip,
    date,
    clothing,
    email,
  }
) {
  const errors = [];

  if (!validZip(zip)) {
    errors.push(
      'ZIP code must contain exactly five digits and must be a US ZIP code.'
    );
  }

  if (
    !validDateFormat(
      date
    )
  ) {
    errors.push(
      'Date must use YYYY-MM-DD format.'
    );
  }

  if (
    !validClothingCategory(
      clothing
    )
  ) {
    errors.push(
      'Choose one of the provided clothing categories.'
    );
  }

  if (
    !validEmail(
      email
    )
  ) {
    errors.push(
      'Enter a valid email address.'
    );
  }

  return errors;
}



function recipientHash(email) {
  return crypto
    .createHash('sha256')
    .update(
      String(email)
        .trim()
        .toLowerCase()
    )
    .digest('hex');
}


async function consumeEmailRequest(
  visitor
) {
  const window =
    Math.floor(
      unixNow() /
      REQUEST_WINDOW_SECONDS
    );

  const pk =
    `EMAILRATE#${visitor}#${window}`;

  try {
    await dynamodb.send(
      new UpdateCommand({
        TableName:
          ADVISOR_TABLE,

        Key: {
          pk,
        },

        UpdateExpression:
          'SET #count = if_not_exists(#count, :zero) + :one, expiresAt = :expires',

        ExpressionAttributeNames: {
          '#count': 'count',
        },

        ExpressionAttributeValues: {
          ':zero': 0,
          ':one': 1,
          ':limit':
            EMAIL_REQUEST_LIMIT,
          ':expires':
            unixNow() +
            REQUEST_WINDOW_SECONDS +
            300,
        },

        ConditionExpression:
          'attribute_not_exists(#count) OR #count < :limit',
      })
    );

    return true;
  } catch (err) {
    if (
      err.name ===
      'ConditionalCheckFailedException'
    ) {
      return false;
    }

    log(
      'email_rate_storage_error',
      {
        message:
          err.message,
      }
    );

    return false;
  }
}


async function saveReportForEmail(
  report,
  email,
  visitor
) {
  const token =
    crypto.randomUUID();

  await dynamodb.send(
    new PutCommand({
      TableName:
        ADVISOR_TABLE,

      Item: {
        pk:
          `REPORT#${token}`,

        recipientHash:
          recipientHash(
            email
          ),

        visitor,

        report,

        createdAt:
          unixNow(),

        expiresAt:
          unixNow() + 900,
      },
    })
  );

  return token;
}


async function loadReportForEmail(
  token,
  email,
  visitor
) {
  if (
    !/^[0-9a-f-]{36}$/i.test(
      token
    )
  ) {
    return null;
  }

  const response =
    await dynamodb.send(
      new GetCommand({
        TableName:
          ADVISOR_TABLE,

        Key: {
          pk:
            `REPORT#${token}`,
        },
      })
    );

  const item =
    response.Item;

  if (!item) {
    return null;
  }

  if (
    item.expiresAt <
    unixNow()
  ) {
    return null;
  }

  if (
    item.visitor !==
    visitor
  ) {
    return null;
  }

  if (
    item.recipientHash !==
    recipientHash(
      email
    )
  ) {
    return null;
  }

  return item.report;
}


async function subscriptionsForTopic() {
  const subscriptions = [];

  let nextToken;

  do {
    const response =
      await sns.send(
        new ListSubscriptionsByTopicCommand({
          TopicArn:
            SNS_TOPIC_ARN,

          NextToken:
            nextToken,
        })
      );

    subscriptions.push(
      ...(
        response.Subscriptions ||
        []
      )
    );

    nextToken =
      response.NextToken;
  } while (nextToken);

  return subscriptions;
}


async function ensureEmailSubscription(
  email
) {
  if (!SNS_TOPIC_ARN) {
    throw new Error(
      'sns_topic_missing'
    );
  }

  const normalized =
    email
      .trim()
      .toLowerCase();

  const subscriptions =
    await subscriptionsForTopic();

  const existing =
    subscriptions.find(
      (subscription) =>
        subscription.Protocol ===
          'email' &&
        String(
          subscription.Endpoint ||
          ''
        )
          .trim()
          .toLowerCase() ===
          normalized
    );

  if (existing) {
    if (
      String(
        existing.SubscriptionArn
      ).startsWith(
        'arn:aws:sns:'
      )
    ) {
      return {
        state:
          'confirmed',

        subscriptionArn:
          existing.SubscriptionArn,
      };
    }

    return {
      state:
        'waiting',
    };
  }

  await sns.send(
    new SubscribeCommand({
      TopicArn:
        SNS_TOPIC_ARN,

      Protocol:
        'email',

      Endpoint:
        normalized,

      ReturnSubscriptionArn:
        true,

      Attributes: {
        FilterPolicy:
          JSON.stringify({
            recipient: [
              recipientHash(
                normalized
              ),
            ],
          }),

        FilterPolicyScope:
          'MessageAttributes',
      },
    })
  );

  return {
    state:
      'waiting',
  };
}


function reportToPlainText(
  report
) {
  const morning =
    report.morning;

  const night =
    report.night;

  return [
    'Weather Advisor Report',
    '',
    `${report.location.city}, ${report.location.state}`,
    `Date: ${report.date}`,
    `ZIP: ${report.zip}`,
    '',
    'MORNING (06:00-11:59 local)',
    `Temperature: ${morning.facts.temperature}`,
    `Wind: ${morning.facts.wind}`,
    `Visibility: ${morning.facts.visibility}`,
    `UV: ${morning.facts.uv}`,
    `Humidity: ${morning.facts.humidity}`,
    `Rain: ${morning.facts.rain}`,
    `Snow: ${morning.facts.snow}`,
    `Road conditions: ${morning.advice.road_conditions}`,
    `Dressing: ${morning.advice.dressing}`,
    `Accessories: ${morning.advice.accessories}`,
    '',
    'NIGHT (18:00-23:59 local)',
    `Temperature: ${night.facts.temperature}`,
    `Wind: ${night.facts.wind}`,
    `Visibility: ${night.facts.visibility}`,
    `UV: ${night.facts.uv}`,
    `Humidity: ${night.facts.humidity}`,
    `Rain: ${night.facts.rain}`,
    `Snow: ${night.facts.snow}`,
    `Road conditions: ${night.advice.road_conditions}`,
    `Dressing: ${night.advice.dressing}`,
    `Accessories: ${night.advice.accessories}`,
    '',
    `Morning advice source: ${morning.advice.source}`,
    `Night advice source: ${night.advice.source}`,
    '',
    'Weather data: National Weather Service and documented supplemental source.',
  ].join('\n');
}


async function publishReport(
  report,
  email
) {
  const hash =
    recipientHash(
      email
    );

  const response =
    await sns.send(
      new PublishCommand({
        TopicArn:
          SNS_TOPIC_ARN,

        Subject:
          `Weather Advisor Report - ${report.date}`,

        Message:
          reportToPlainText(
            report
          ),

        MessageAttributes: {
          recipient: {
            DataType:
              'String',

            StringValue:
              hash,
          },
        },
      })
    );

  return response.MessageId;
}


function emailStatusPage(
  title,
  message,
  retry = null
) {
  const retryHtml =
    retry &&
    retry.email &&
    retry.reportToken
      ? `
        <form
          method="POST"
          action="/email"
        >
          <input
            type="hidden"
            name="email"
            value="${escapeHtml(
              retry.email
            )}"
          >

          <input
            type="hidden"
            name="report_token"
            value="${escapeHtml(
              retry.reportToken
            )}"
          >

          <button
            type="submit"
          >
            I've Confirmed — Send My Report
          </button>
        </form>

        <p>
          After confirming the Amazon SNS subscription from your inbox,
          return to this page and press the button above.
        </p>
      `
      : '';

  return `
<!doctype html>

<html lang="en">

<head>
  <meta charset="utf-8">

  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >

  <title>
    ${escapeHtml(title)}
  </title>
</head>

<body>

  <main>

    <h1>
      ${escapeHtml(title)}
    </h1>

    <p>
      ${escapeHtml(message)}
    </p>

    ${retryHtml}

    <p>
      <a href="/">
        Start a New Weather Report
      </a>
    </p>

  </main>

</body>

</html>
  `;
}


function formPage(
  {
    errors = [],
    values = {},
    report = null,
  } = {}
) {
  const zip =
    escapeHtml(
      values.zip || ''
    );

  const date =
    escapeHtml(
      values.date || ''
    );

  const email =
    escapeHtml(
      values.email || ''
    );

  const clothing =
    values.clothing ||
    'neutral';

  const errorHtml =
    errors.length
      ? `
        <div class="error">
          <strong>Please correct the following:</strong>
          <ul>
            ${errors
              .map(
                (error) =>
                  `<li>${escapeHtml(
                    error
                  )}</li>`
              )
              .join('')}
          </ul>
        </div>
      `
      : '';

  const reportHtml =
    report
      ? renderReport(
          report,
          email
        )
      : '';

  return `
<!doctype html>

<html lang="en">

<head>
  <meta charset="utf-8">

  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >

  <title>
    Weather Advisor
  </title>

  <style>
    body {
      font-family:
        Arial,
        sans-serif;
      margin: 0;
      background: #f5f7fa;
      color: #172033;
    }

    main {
      width: min(
        1100px,
        92%
      );
      margin: 32px auto;
    }

    h1 {
      margin-bottom: 6px;
    }

    .subtitle {
      color: #566174;
      margin-top: 0;
    }

    .card {
      background: white;
      border-radius: 12px;
      padding: 22px;
      margin-bottom: 22px;
      box-shadow:
        0 2px 8px
        rgba(
          0,
          0,
          0,
          0.08
        );
    }

    .grid {
      display: grid;
      grid-template-columns:
        repeat(
          2,
          minmax(
            0,
            1fr
          )
        );
      gap: 16px;
    }

    label {
      display: block;
      font-weight: bold;
      margin-bottom: 6px;
    }

    input,
    select {
      box-sizing:
        border-box;
      width: 100%;
      padding: 10px;
      border:
        1px solid
        #bbc3ce;
      border-radius: 6px;
      font-size: 16px;
    }

    button {
      margin-top: 18px;
      padding:
        11px 18px;
      border: 0;
      border-radius: 7px;
      background: #183b66;
      color: white;
      font-size: 16px;
      cursor: pointer;
    }

    .error {
      background: #ffe9e9;
      border:
        1px solid
        #d77;
      padding: 14px;
      border-radius: 8px;
      margin-bottom: 18px;
    }

    .warning {
      background: #fff8d8;
      border:
        1px solid
        #ddc463;
      padding: 12px;
      border-radius: 8px;
    }

    table {
      width: 100%;
      border-collapse:
        collapse;
      margin-top: 16px;
    }

    th,
    td {
      border:
        1px solid
        #d3d8df;
      padding: 11px;
      text-align: left;
      vertical-align: top;
    }

    th {
      background: #eef2f7;
    }

    .small {
      font-size: 13px;
      color: #5c6676;
    }

    @media (
      max-width: 700px
    ) {
      .grid {
        grid-template-columns:
          1fr;
      }
    }
  </style>
</head>

<body>

<main>

  <div class="card">

    <h1>
      Weather Advisor
    </h1>

    <p class="subtitle">
      Morning and Night weather facts with practical advice.
    </p>

    <form
      method="POST"
      action="/report"
    >

      ${errorHtml}

      <div class="grid">

        <div>
          <label for="date">
            Date
          </label>

          <input
            id="date"
            name="date"
            type="date"
            value="${date}"
            required
          >
        </div>

        <div>
          <label for="zip">
            US ZIP code
          </label>

          <input
            id="zip"
            name="zip"
            inputmode="numeric"
            pattern="[0-9]{5}"
            maxlength="5"
            value="${zip}"
            required
          >
        </div>

        <div>
          <label for="clothing">
            Clothing preference
          </label>

          <select
            id="clothing"
            name="clothing"
            required
          >
            <option
              value="neutral"
              ${
                clothing ===
                'neutral'
                  ? 'selected'
                  : ''
              }
            >
              Gender-neutral
            </option>

            <option
              value="menswear"
              ${
                clothing ===
                'menswear'
                  ? 'selected'
                  : ''
              }
            >
              Menswear
            </option>

            <option
              value="womenswear"
              ${
                clothing ===
                'womenswear'
                  ? 'selected'
                  : ''
              }
            >
              Womenswear
            </option>
          </select>
        </div>

        <div>
          <label for="email">
            Email address
          </label>

          <input
            id="email"
            name="email"
            type="email"
            value="${email}"
            required
          >
        </div>

      </div>

      <button
        type="submit"
      >
        Generate Report
      </button>

    </form>

    <p class="small">
      Weather measurements come from weather APIs.
      Google Gemini receives weather facts and the selected clothing category only.
      Your email address is not sent to Gemini.
    </p>

  </div>

  ${reportHtml}

</main>

</body>

</html>
  `;
}


function renderReport(
  report,
  email
) {
  const morning =
    report.morning;

  const night =
    report.night;

  const row = (
    title,
    morningValue,
    nightValue
  ) => `
    <tr>
      <th>
        ${escapeHtml(
          title
        )}
      </th>

      <td>
        ${escapeHtml(
          morningValue
        )}
      </td>

      <td>
        ${escapeHtml(
          nightValue
        )}
      </td>
    </tr>
  `;

  return `
<div class="card">

  <h2>
    ${escapeHtml(
      report.location.city
    )},
    ${escapeHtml(
      report.location.state
    )}
    —
    ${escapeHtml(
      report.date
    )}
  </h2>

  ${
    report.warning
      ? `
        <p class="warning">
          ${escapeHtml(
            report.warning
          )}
        </p>
      `
      : ''
  }

  <table>

    <thead>
      <tr>
        <th>
          Item
        </th>

        <th>
          Morning
          <br>
          <span class="small">
            06:00–11:59 local
          </span>
        </th>

        <th>
          Night
          <br>
          <span class="small">
            18:00–23:59 local
          </span>
        </th>
      </tr>
    </thead>

    <tbody>

      ${row(
        'Temperature',
        morning.facts
          .temperature,
        night.facts
          .temperature
      )}

      ${row(
        'Wind speed',
        morning.facts.wind,
        night.facts.wind
      )}

      ${row(
        'Visibility',
        morning.facts
          .visibility,
        night.facts
          .visibility
      )}

      ${row(
        'UV',
        morning.facts.uv,
        night.facts.uv
      )}

      ${row(
        'Humidity',
        morning.facts
          .humidity,
        night.facts
          .humidity
      )}

      ${row(
        'Rain',
        morning.facts.rain,
        night.facts.rain
      )}

      ${row(
        'Snow',
        morning.facts.snow,
        night.facts.snow
      )}

      ${row(
        'Suggested road conditions',
        morning.advice
          .road_conditions,
        night.advice
          .road_conditions
      )}

      ${row(
        'Suggested dressing',
        morning.advice
          .dressing,
        night.advice
          .dressing
      )}

      ${row(
        'Suggested accessories',
        morning.advice
          .accessories,
        night.advice
          .accessories
      )}

    </tbody>

  </table>

  <p class="small">
    Morning advice source:
    ${escapeHtml(
      morning.advice.source
    )}
    <br>

    Night advice source:
    ${escapeHtml(
      night.advice.source
    )}
    <br>

    Weather cache:
    ${escapeHtml(
      report.cache
    )}
  </p>

  <form
    method="POST"
    action="/email"
  >

    <input
      type="hidden"
      name="zip"
      value="${escapeHtml(
        report.zip
      )}"
    >

    <input
      type="hidden"
      name="date"
      value="${escapeHtml(
        report.date
      )}"
    >

    <input
      type="hidden"
      name="clothing"
      value="${escapeHtml(
        report.clothingCategory
      )}"
    >

    <input
      type="hidden"
      name="email"
      value="${escapeHtml(
        email
      )}"
    >

    <input
      type="hidden"
      name="report_token"
      value="${escapeHtml(
        report.reportToken ||
        ''
      )}"
    >

    <button
      type="submit"
    >
      Email This Report
    </button>

  </form>

  <p class="small">
    Email delivery will require recipient confirmation.
  </p>

</div>
  `;
}


app.get(
  '/health',
  (req, res) => {
    res.json({
      status: 'ok',
      service: 'advisor',
      version: '2.0.0',
    });
  }
);


app.get(
  '/',
  (req, res) => {
    res.send(
      formPage()
    );
  }
);


app.post(
  '/report',
  async (
    req,
    res
  ) => {
    const zip =
      String(
        req.body.zip || ''
      ).trim();

    const date =
      String(
        req.body.date || ''
      ).trim();

    const clothing =
      String(
        req.body.clothing || ''
      ).trim();

    const email =
      String(
        req.body.email || ''
      ).trim();

    const values = {
      zip,
      date,
      clothing,
      email,
    };

    const errors =
      validateInputs(
        values
      );

    if (
      errors.length
    ) {
      log(
        'report_rejected',
        {
          reason:
            'validation',
        }
      );

      return res
        .status(400)
        .send(
          formPage({
            errors,
            values,
          })
        );
    }

    const visitor =
      clientId(req);

    const rate =
      await consumeVisitorRequest(
        visitor
      );

    if (!rate.allowed) {
      return res
        .status(429)
        .send(
          formPage({
            errors: [
              'Too many report requests. Please try again later.',
            ],
            values,
          })
        );
    }

    const started =
      Date.now();

    let weatherResponse;

    try {
      weatherResponse =
        await fetchWeather(
          zip,
          date
        );
    } catch (err) {
      log(
        'weather_service_error',
        {
          message:
            err.message,
        }
      );

      return res
        .status(502)
        .send(
          formPage({
            errors: [
              'Weather service is temporarily unavailable.',
            ],
            values,
          })
        );
    }

    if (
      !weatherResponse.ok
    ) {
      const error =
        weatherResponse.body
          ?.message ||
        weatherResponse.body
          ?.error ||
        'Unable to generate weather report.';

      return res
        .status(
          weatherResponse.status
        )
        .send(
          formPage({
            errors: [
              error,
            ],
            values,
          })
        );
    }

    const report =
      await buildReport(
        weatherResponse.body,
        clothing
      );

    let reportToken = null;

    try {
      reportToken =
        await saveReportForEmail(
          report,
          email,
          visitor
        );
    } catch (err) {
      log(
        'report_email_state_error',
        {
          message:
            err.message,
        }
      );
    }

    report.reportToken =
      reportToken;

    log(
      'report_success',
      {
        zip,
        date,
        ms:
          Date.now() -
          started,
      }
    );

    return res.send(
      formPage({
        values,
        report,
      })
    );
  }
);


app.get(
  '/api/report',
  async (
    req,
    res
  ) => {
    const zip =
      String(
        req.query.zip || ''
      ).trim();

    const date =
      String(
        req.query.date || ''
      ).trim();

    const clothing =
      String(
        req.query.clothing ||
        'neutral'
      ).trim();

    if (
      !validZip(zip) ||
      !validDateFormat(
        date
      ) ||
      !validClothingCategory(
        clothing
      )
    ) {
      return res
        .status(400)
        .json({
          error:
            'invalid_input',
        });
    }

    const visitor =
      clientId(req);

    const rate =
      await consumeVisitorRequest(
        visitor
      );

    if (!rate.allowed) {
      return res
        .status(429)
        .json({
          error:
            'rate_limit',
        });
    }

    let weatherResponse;

    try {
      weatherResponse =
        await fetchWeather(
          zip,
          date
        );
    } catch (err) {
      return res
        .status(502)
        .json({
          error:
            'weather_service_unavailable',
        });
    }

    if (
      !weatherResponse.ok
    ) {
      return res
        .status(
          weatherResponse.status
        )
        .json(
          weatherResponse.body
        );
    }

    const report =
      await buildReport(
        weatherResponse.body,
        clothing
      );

    return res.json(
      report
    );
  }
);


app.post(
  '/email',
  async (
    req,
    res
  ) => {
    const email =
      String(
        req.body.email || ''
      ).trim();

    const reportToken =
      String(
        req.body.report_token ||
        ''
      ).trim();

    if (
      !validEmail(
        email
      )
    ) {
      return res
        .status(400)
        .send(
          emailStatusPage(
            'Email Not Sent',
            'Enter a valid email address.'
          )
        );
    }

    const visitor =
      clientId(req);

    const allowed =
      await consumeEmailRequest(
        visitor
      );

    if (!allowed) {
      return res
        .status(429)
        .send(
          emailStatusPage(
            'Email Limit Reached',
            'Too many email requests were made. Please try again later.'
          )
        );
    }

    let report;

    try {
      report =
        await loadReportForEmail(
          reportToken,
          email,
          visitor
        );
    } catch (err) {
      log(
        'email_state_error',
        {
          message:
            err.message,
        }
      );

      return res
        .status(503)
        .send(
          emailStatusPage(
            'Email Not Sent',
            'Temporary report state is unavailable.'
          )
        );
    }

    if (!report) {
      return res
        .status(400)
        .send(
          emailStatusPage(
            'Email Not Sent',
            'This report link is invalid or expired. Generate the report again.'
          )
        );
    }

    let subscription;

    try {
      subscription =
        await ensureEmailSubscription(
          email
        );
    } catch (err) {
      log(
        'email_subscription_error',
        {
          message:
            err.message,
        }
      );

      return res
        .status(503)
        .send(
          emailStatusPage(
            'Email Not Sent',
            'The email subscription service is temporarily unavailable.'
          )
        );
    }

    if (
      subscription.state ===
      'waiting'
    ) {
      return res.send(
        emailStatusPage(
          'Confirmation Required',
          'Amazon SNS sent a subscription confirmation message to your email. Confirm it from your inbox, then return to this page and press the button below. Your generated report is temporarily saved for 15 minutes.',
          {
            email,
            reportToken,
          }
        )
      );
    }

    try {
      const messageId =
        await publishReport(
          report,
          email
        );

      log(
        'email_publish_success',
        {
          messageId,
        }
      );

      return res.send(
        emailStatusPage(
          'Report Submitted for Delivery',
          'Amazon SNS accepted the report for delivery to the confirmed requester.'
        )
      );
    } catch (err) {
      log(
        'email_publish_error',
        {
          message:
            err.message,
        }
      );

      return res
        .status(502)
        .send(
          emailStatusPage(
            'Email Not Sent',
            'Amazon SNS did not accept the report for delivery.'
          )
        );
    }
  }
);


app.listen(
  PORT,
  () => {
    log(
      'advisor_started',
      {
        port:
          PORT,
        model:
          GEMINI_MODEL,
        table:
          ADVISOR_TABLE,
      }
    );
  }
);
