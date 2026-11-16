const express = require('express');
const {
  DynamoDBClient,
} = require('@aws-sdk/client-dynamodb');
const {
  DynamoDBDocumentClient,
  GetCommand,
  PutCommand,
} = require('@aws-sdk/lib-dynamodb');

const app = express();

const PORT = Number(process.env.PORT || 3000);
const AWS_REGION = process.env.AWS_REGION || 'us-east-2';

const ZIP_API =
  process.env.ZIP_API_BASE ||
  'https://api.zippopotam.us';

const NWS_API =
  process.env.NWS_API_BASE ||
  'https://api.weather.gov';

const OPEN_METEO_API =
  process.env.OPEN_METEO_API_BASE ||
  'https://api.open-meteo.com';

const NWS_USER_AGENT =
  process.env.NWS_USER_AGENT ||
  '(Weather Advisor Final Project, student@example.com)';

const WEATHER_TABLE =
  process.env.WEATHER_TABLE ||
  'itmo-544-final-weather-cache';

const CACHE_SECONDS =
  Number(process.env.CACHE_SECONDS || 600);

const STALE_CACHE_SECONDS =
  Number(process.env.STALE_CACHE_SECONDS || 21600);

const RAIN_PROBABILITY_THRESHOLD =
  Number(process.env.RAIN_PROBABILITY_THRESHOLD || 20);

const RAIN_HEAVY_MM_PER_HOUR =
  Number(
    process.env.RAIN_HEAVY_MM_PER_HOUR ||
    7.62
  );

const SNOW_HEAVY_MM_PER_HOUR =
  Number(
    process.env.SNOW_HEAVY_MM_PER_HOUR ||
    8.47
  );

const MORNING_START = 6;
const MORNING_END = 11;

const NIGHT_START = 18;
const NIGHT_END = 23;

const dynamodb = DynamoDBDocumentClient.from(
  new DynamoDBClient({
    region: AWS_REGION,
  })
);

const log = (event, fields = {}) => {
  console.log(
    JSON.stringify({
      ts: new Date().toISOString(),
      event,
      ...fields,
    })
  );
};

class UpstreamError extends Error {
  constructor(stage, status = 0) {
    super(`${stage} failed`);
    this.name = 'UpstreamError';
    this.stage = stage;
    this.status = status;
  }
}

async function fetchJson(
  stage,
  url,
  headers = {},
  timeoutMs = 8000
) {
  let lastStatus = 0;

  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      const response = await fetch(url, {
        headers,
        signal: AbortSignal.timeout(timeoutMs),
      });

      lastStatus = response.status;

      if (response.ok) {
        return await response.json();
      }

      if (response.status === 404) {
        return null;
      }

      if (
        response.status < 500 &&
        response.status !== 429
      ) {
        break;
      }
    } catch (err) {
      lastStatus = 0;
    }

    if (attempt < 2) {
      await new Promise((resolve) =>
        setTimeout(resolve, 400)
      );
    }
  }

  throw new UpstreamError(
    stage,
    lastStatus
  );
}

function validDateFormat(dateString) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateString)) {
    return false;
  }

  const [year, month, day] =
    dateString.split('-').map(Number);

  const date = new Date(
    Date.UTC(year, month - 1, day)
  );

  return (
    date.getUTCFullYear() === year &&
    date.getUTCMonth() === month - 1 &&
    date.getUTCDate() === day
  );
}

function dateInTimeZone(date, timeZone) {
  const parts =
    new Intl.DateTimeFormat('en-CA', {
      timeZone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(date);

  const values = {};

  for (const part of parts) {
    if (part.type !== 'literal') {
      values[part.type] = part.value;
    }
  }

  return (
    `${values.year}-` +
    `${values.month}-` +
    `${values.day}`
  );
}

function addCalendarDays(
  dateString,
  numberOfDays
) {
  const [year, month, day] =
    dateString.split('-').map(Number);

  const date = new Date(
    Date.UTC(year, month - 1, day)
  );

  date.setUTCDate(
    date.getUTCDate() + numberOfDays
  );

  return date
    .toISOString()
    .slice(0, 10);
}

function dateInsideSevenDayWindow(
  selectedDate,
  timeZone
) {
  const today =
    dateInTimeZone(
      new Date(),
      timeZone
    );

  const lastDate =
    addCalendarDays(today, 6);

  return (
    selectedDate >= today &&
    selectedDate <= lastDate
  );
}

function getLocalParts(
  instant,
  timeZone
) {
  const parts =
    new Intl.DateTimeFormat(
      'en-US',
      {
        timeZone,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        hour12: false,
      }
    ).formatToParts(instant);

  const values = {};

  for (const part of parts) {
    if (part.type !== 'literal') {
      values[part.type] = part.value;
    }
  }

  let hour = Number(values.hour);

  if (hour === 24) {
    hour = 0;
  }

  return {
    date:
      `${values.year}-` +
      `${values.month}-` +
      `${values.day}`,
    hour,
  };
}

function hourlyPeriod(
  period,
  selectedDate,
  startHour,
  endHour
) {
  if (!period.startTime) {
    return false;
  }

  const local =
    period.startTime.slice(0, 10);

  const hour =
    Number(
      period.startTime.slice(11, 13)
    );

  return (
    local === selectedDate &&
    hour >= startHour &&
    hour <= endHour
  );
}

function numbersFromWindString(value) {
  if (!value) {
    return [];
  }

  return (
    String(value)
      .match(/\d+(\.\d+)?/g) || []
  ).map(Number);
}

function average(values) {
  if (!values.length) {
    return null;
  }

  return (
    values.reduce(
      (sum, value) => sum + value,
      0
    ) / values.length
  );
}

function minimum(values) {
  return values.length
    ? Math.min(...values)
    : null;
}

function maximum(values) {
  return values.length
    ? Math.max(...values)
    : null;
}

function round1(value) {
  if (
    value === null ||
    value === undefined
  ) {
    return null;
  }

  return Math.round(value * 10) / 10;
}

function parseDurationMs(duration) {
  const match =
    /^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?$/.exec(
      duration || ''
    );

  if (!match) {
    return 60 * 60 * 1000;
  }

  const days =
    Number(match[1] || 0);

  const hours =
    Number(match[2] || 0);

  const minutes =
    Number(match[3] || 0);

  return (
    days * 86400000 +
    hours * 3600000 +
    minutes * 60000
  );
}

function gridValuesForPeriod(
  property,
  selectedDate,
  startHour,
  endHour,
  timeZone
) {
  if (
    !property ||
    !Array.isArray(property.values)
  ) {
    return [];
  }

  const results = [];

  for (const item of property.values) {
    if (
      item.value === null ||
      item.value === undefined ||
      !item.validTime
    ) {
      continue;
    }

    const [
      startString,
      durationString,
    ] = item.validTime.split('/');

    const start =
      new Date(startString);

    const durationMs =
      parseDurationMs(durationString);

    const endTime =
      start.getTime() + durationMs;

    let overlaps = false;

    for (
      let cursor = start.getTime();
      cursor < endTime;
      cursor += 3600000
    ) {
      const local =
        getLocalParts(
          new Date(cursor),
          timeZone
        );

      if (
        local.date === selectedDate &&
        local.hour >= startHour &&
        local.hour <= endHour
      ) {
        overlaps = true;
        break;
      }
    }

    if (overlaps) {
      results.push(
        Number(item.value)
      );
    }
  }

  return results.filter(
    Number.isFinite
  );
}


function gridRatesForPeriod(
  property,
  selectedDate,
  startHour,
  endHour,
  timeZone
) {
  if (
    !property ||
    !Array.isArray(property.values)
  ) {
    return [];
  }

  const rates = [];

  for (const item of property.values) {
    if (
      item.value === null ||
      item.value === undefined ||
      !item.validTime
    ) {
      continue;
    }

    const [
      startString,
      durationString,
    ] = item.validTime.split('/');

    const start =
      new Date(startString);

    const durationMs =
      parseDurationMs(
        durationString
      );

    const durationHours =
      durationMs /
      (60 * 60 * 1000);

    if (
      !Number.isFinite(
        durationHours
      ) ||
      durationHours <= 0
    ) {
      continue;
    }

    const endTime =
      start.getTime() +
      durationMs;

    let overlaps = false;

    for (
      let cursor =
        start.getTime();

      cursor < endTime;

      cursor +=
        60 * 60 * 1000
    ) {
      const local =
        getLocalParts(
          new Date(cursor),
          timeZone
        );

      if (
        local.date ===
          selectedDate &&
        local.hour >=
          startHour &&
        local.hour <=
          endHour
      ) {
        overlaps = true;
        break;
      }
    }

    if (overlaps) {
      rates.push(
        Number(item.value) /
        durationHours
      );
    }
  }

  return rates.filter(
    Number.isFinite
  );
}


function openMeteoValuesForPeriod(
  hourly,
  field,
  selectedDate,
  startHour,
  endHour
) {
  if (
    !hourly ||
    !Array.isArray(hourly.time) ||
    !Array.isArray(hourly[field])
  ) {
    return [];
  }

  const values = [];

  for (
    let i = 0;
    i < hourly.time.length;
    i++
  ) {
    const time =
      hourly.time[i];

    const value =
      hourly[field][i];

    if (
      value === null ||
      value === undefined
    ) {
      continue;
    }

    const date =
      time.slice(0, 10);

    const hour =
      Number(time.slice(11, 13));

    if (
      date === selectedDate &&
      hour >= startHour &&
      hour <= endHour
    ) {
      values.push(Number(value));
    }
  }

  return values.filter(
    Number.isFinite
  );
}

function classifyRain(
  rateMmPerHour,
  probabilityPercent
) {
  if (
    rateMmPerHour === null &&
    probabilityPercent === null
  ) {
    return 'Not available';
  }

  const rate =
    rateMmPerHour ?? 0;

  const probability =
    probabilityPercent ?? 0;

  if (
    rate >
    RAIN_HEAVY_MM_PER_HOUR
  ) {
    return 'Heavy';
  }

  if (
    rate > 0 ||
    probability >=
      RAIN_PROBABILITY_THRESHOLD
  ) {
    return 'Mild';
  }

  return 'No';
}


function classifySnow(
  rateMmPerHour
) {
  if (
    rateMmPerHour === null
  ) {
    return 'Not available';
  }

  if (
    rateMmPerHour >=
    SNOW_HEAVY_MM_PER_HOUR
  ) {
    return 'Heavy';
  }

  if (
    rateMmPerHour > 0
  ) {
    return 'Mild';
  }

  return 'No';
}


function buildPeriodFacts({
  name,
  selectedDate,
  startHour,
  endHour,
  hourlyPeriods,
  grid,
  openMeteo,
  timeZone,
}) {
  const periods =
    hourlyPeriods.filter((period) =>
      hourlyPeriod(
        period,
        selectedDate,
        startHour,
        endHour
      )
    );

  const temperatures =
    periods
      .map((period) =>
        Number(period.temperature)
      )
      .filter(Number.isFinite);

  const windSpeeds = [];

  for (const period of periods) {
    windSpeeds.push(
      ...numbersFromWindString(
        period.windSpeed
      )
    );
  }

  const humidityValues =
    periods
      .map((period) =>
        period.relativeHumidity
          ? Number(
              period.relativeHumidity.value
            )
          : null
      )
      .filter(Number.isFinite);

  const precipProbabilityValues =
    periods
      .map((period) =>
        period.probabilityOfPrecipitation
          ? Number(
              period
                .probabilityOfPrecipitation
                .value
            )
          : null
      )
      .filter(Number.isFinite);

  const precipitationAmounts =
    gridValuesForPeriod(
      grid?.quantitativePrecipitation,
      selectedDate,
      startHour,
      endHour,
      timeZone
    );

  const snowfallAmounts =
    gridValuesForPeriod(
      grid?.snowfallAmount,
      selectedDate,
      startHour,
      endHour,
      timeZone
    );

  const precipitationRates =

    gridRatesForPeriod(

      grid?.quantitativePrecipitation,

      selectedDate,

      startHour,

      endHour,

      timeZone

    );

  const snowfallRates =

    gridRatesForPeriod(

      grid?.snowfallAmount,

      selectedDate,

      startHour,

      endHour,

      timeZone

    );

  const nwsVisibility =
    gridValuesForPeriod(
      grid?.visibility,
      selectedDate,
      startHour,
      endHour,
      timeZone
    );

  const openVisibility =
    openMeteoValuesForPeriod(
      openMeteo?.hourly,
      'visibility',
      selectedDate,
      startHour,
      endHour
    );

  const uvValues =
    openMeteoValuesForPeriod(
      openMeteo?.hourly,
      'uv_index',
      selectedDate,
      startHour,
      endHour
    );

  const precipitationAmount =
    maximum(precipitationAmounts);

  const precipitationProbability =
    maximum(precipProbabilityValues);

  const snowfallAmount =
    maximum(snowfallAmounts);

  const precipitationRate =

    maximum(
      precipitationRates
    );

  const snowfallRate =

    maximum(
      snowfallRates
    );

  let visibilityMeters = null;
  let visibilitySource = null;

  if (nwsVisibility.length) {
    visibilityMeters =
      minimum(nwsVisibility);

    visibilitySource =
      'National Weather Service';
  } else if (openVisibility.length) {
    visibilityMeters =
      minimum(openVisibility);

    visibilitySource =
      'Open-Meteo';
  }

  return {
    period: name,

    temperature: {
      min:
        minimum(temperatures),
      max:
        maximum(temperatures),
      unit:
        periods[0]
          ?.temperatureUnit || 'F',
      source:
        'National Weather Service',
    },

    windSpeed: {
      maxMph:
        maximum(windSpeeds),
      source:
        'National Weather Service',
    },

    visibility: {
      meters:
        visibilityMeters,
      miles:
        visibilityMeters === null
          ? null
          : round1(
              visibilityMeters /
                1609.344
            ),
      source:
        visibilitySource,
    },

    uv: {
      max:
        maximum(uvValues),
      source:
        uvValues.length
          ? 'Open-Meteo'
          : null,
    },

    humidity: {
      averagePercent:
        average(humidityValues) === null
          ? null
          : Math.round(
              average(
                humidityValues
              )
            ),
      source:
        'National Weather Service',
    },

    precipitation: {
      amountMm:
        precipitationAmount,

      rateMmPerHour:
        precipitationRate,
      probabilityPercent:
        precipitationProbability,
      source:
        'National Weather Service',
    },

    snowfall: {
      amountMm:
        snowfallAmount,

      rateMmPerHour:
        snowfallRate,
      source:
        'National Weather Service',
    },

    rain:
      classifyRain(
        precipitationRate,
        precipitationProbability
      ),

    snow:
      classifySnow(
        snowfallRate
      ),
  };
}

function cacheKey(zip, date) {
  return `WEATHER#${zip}#${date}`;
}

async function readCache(
  zip,
  date
) {
  try {
    const response =
      await dynamodb.send(
        new GetCommand({
          TableName: WEATHER_TABLE,
          Key: {
            pk: cacheKey(
              zip,
              date
            ),
          },
        })
      );

    return response.Item || null;
  } catch (err) {
    log('cache_error', {
      stage: 'read',
      message: err.message,
    });

    return null;
  }
}

async function writeCache(
  zip,
  date,
  payload
) {
  const now =
    Math.floor(Date.now() / 1000);

  try {
    await dynamodb.send(
      new PutCommand({
        TableName: WEATHER_TABLE,
        Item: {
          pk: cacheKey(
            zip,
            date
          ),
          zip,
          date,
          payload,
          createdAt: now,
          expiresAt:
            now +
            STALE_CACHE_SECONDS,
        },
      })
    );

    return true;
  } catch (err) {
    log('cache_error', {
      stage: 'write',
      message: err.message,
    });

    return false;
  }
}

function cacheAgeSeconds(item) {
  if (!item?.createdAt) {
    return null;
  }

  return (
    Math.floor(Date.now() / 1000) -
    item.createdAt
  );
}

app.get('/', (req, res) => {
  res.json({
    service:
      'weather-data',
    version: '2.0.0',
    usage:
      '/weather?zip=60616&date=YYYY-MM-DD',
    health: '/health',
  });
});

app.get(
  '/health',
  (req, res) => {
    res.json({
      status: 'ok',
      service: 'weather-data',
    });
  }
);

app.get(
  '/weather',
  async (req, res) => {
    const zip =
      String(
        req.query.zip || ''
      ).trim();

    const selectedDate =
      String(
        req.query.date || ''
      ).trim();

    if (!/^\d{5}$/.test(zip)) {
      log('weather_rejected', {
        reason: 'invalid_zip',
      });

      return res
        .status(400)
        .json({
          error: 'invalid_zip',
          message:
            'This service supports exactly five-digit US ZIP codes.',
        });
    }

    if (
      !validDateFormat(
        selectedDate
      )
    ) {
      log('weather_rejected', {
        reason: 'invalid_date',
      });

      return res
        .status(400)
        .json({
          error: 'invalid_date',
          message:
            'Date must be a real calendar date in YYYY-MM-DD format.',
        });
    }

    const started =
      Date.now();

    const cached =
      await readCache(
        zip,
        selectedDate
      );

    const cachedAge =
      cacheAgeSeconds(
        cached
      );

    if (
      cached &&
      cachedAge !== null &&
      cachedAge <=
        CACHE_SECONDS
    ) {
      log('weather_success', {
        zip,
        date:
          selectedDate,
        cache: 'hit',
        ms:
          Date.now() -
          started,
      });

      return res.json({
        ...cached.payload,
        cache: 'hit',
        cacheAgeSeconds:
          cachedAge,
      });
    }

    try {
      const lookup =
        await fetchJson(
          'zip_lookup',
          `${ZIP_API}/us/${zip}`
        );

      if (
        !lookup ||
        !Array.isArray(
          lookup.places
        ) ||
        lookup.places.length === 0
      ) {
        log('weather_rejected', {
          reason:
            'zip_not_found',
          zip,
        });

        return res
          .status(404)
          .json({
            error:
              'zip_not_found',
            message:
              'ZIP code not found.',
          });
      }

      const place =
        lookup.places[0];

      const latitude =
        Number(
          place.latitude
        );

      const longitude =
        Number(
          place.longitude
        );

      if (
        !Number.isFinite(
          latitude
        ) ||
        !Number.isFinite(
          longitude
        )
      ) {
        throw new Error(
          'invalid_coordinates'
        );
      }

      const headers = {
        'User-Agent':
          NWS_USER_AGENT,
        Accept:
          'application/geo+json',
      };

      const point =
        await fetchJson(
          'nws_points',
          `${NWS_API}/points/${latitude.toFixed(
            4
          )},${longitude.toFixed(
            4
          )}`,
          headers
        );

      if (
        !point?.properties
      ) {
        return res
          .status(404)
          .json({
            error:
              'no_nws_coverage',
          });
      }

      const timeZone =
        point.properties
          .timeZone;

      if (!timeZone) {
        throw new Error(
          'timezone_missing'
        );
      }

      if (
        !dateInsideSevenDayWindow(
          selectedDate,
          timeZone
        )
      ) {
        return res
          .status(400)
          .json({
            error:
              'date_out_of_range',
            message:
              'Choose a date from today through six days from today in the ZIP code local timezone.',
          });
      }

      const hourly =
        await fetchJson(
          'nws_hourly',
          point.properties
            .forecastHourly,
          headers
        );

      if (
        !Array.isArray(
          hourly?.properties
            ?.periods
        )
      ) {
        throw new UpstreamError(
          'nws_hourly',
          0
        );
      }

      let grid = null;

      try {
        const gridResponse =
          await fetchJson(
            'nws_grid',
            point.properties
              .forecastGridData,
            headers
          );

        grid =
          gridResponse
            ?.properties ||
          null;
      } catch (err) {
        log(
          'supplemental_failure',
          {
            stage: 'nws_grid',
            message:
              err.message,
          }
        );
      }

      let openMeteo = null;

      try {
        const openUrl =
          `${OPEN_METEO_API}` +
          `/v1/forecast` +
          `?latitude=${encodeURIComponent(
            latitude
          )}` +
          `&longitude=${encodeURIComponent(
            longitude
          )}` +
          `&hourly=visibility,uv_index` +
          `&timezone=${encodeURIComponent(
            timeZone
          )}` +
          `&forecast_days=7`;

        openMeteo =
          await fetchJson(
            'open_meteo',
            openUrl,
            {},
            8000
          );
      } catch (err) {
        log(
          'supplemental_failure',
          {
            stage:
              'open_meteo',
            message:
              err.message,
          }
        );
      }

      const periods =
        hourly.properties
          .periods;

      const morning =
        buildPeriodFacts({
          name: 'Morning',
          selectedDate,
          startHour:
            MORNING_START,
          endHour:
            MORNING_END,
          hourlyPeriods:
            periods,
          grid,
          openMeteo,
          timeZone,
        });

      const night =
        buildPeriodFacts({
          name: 'Night',
          selectedDate,
          startHour:
            NIGHT_START,
          endHour:
            NIGHT_END,
          hourlyPeriods:
            periods,
          grid,
          openMeteo,
          timeZone,
        });

      const body = {
        zip,
        date:
          selectedDate,

        location: {
          city:
            place[
              'place name'
            ],
          state:
            place[
              'state abbreviation'
            ],
          latitude,
          longitude,
          timeZone,
        },

        periods: {
          morning,
          night,
        },

        sources: {
          zip:
            'Zippopotam.us',
          primaryWeather:
            'National Weather Service',
          supplemental:
            'Open-Meteo',
        },
      };

      const saved =
        await writeCache(
          zip,
          selectedDate,
          body
        );

      log('weather_success', {
        zip,
        date:
          selectedDate,
        cache:
          saved
            ? 'miss'
            : 'unavailable',
        ms:
          Date.now() -
          started,
      });

      return res.json({
        ...body,
        cache:
          saved
            ? 'miss'
            : 'unavailable',
      });
    } catch (err) {
      if (
        cached &&
        cachedAge !== null &&
        cachedAge <=
          STALE_CACHE_SECONDS
      ) {
        log(
          'weather_stale_cache',
          {
            zip,
            date:
              selectedDate,
            ageSeconds:
              cachedAge,
            reason:
              err.message,
          }
        );

        return res.json({
          ...cached.payload,
          cache: 'stale',
          cacheAgeSeconds:
            cachedAge,
          warning:
            'Live weather data is temporarily unavailable. Recent cached forecast data is being shown.',
        });
      }

      if (
        err instanceof
        UpstreamError
      ) {
        log(
          'weather_error',
          {
            zip,
            date:
              selectedDate,
            stage:
              err.stage,
            status:
              err.status,
          }
        );

        return res
          .status(502)
          .json({
            error:
              'weather_data_unavailable',
            stage:
              err.stage,
            message:
              'Weather data is temporarily unavailable.',
          });
      }

      log('weather_error', {
        zip,
        date:
          selectedDate,
        stage: 'internal',
        message:
          err.message,
      });

      return res
        .status(500)
        .json({
          error:
            'internal_error',
        });
    }
  }
);

if (require.main === module) {

  app.listen(PORT, () => {

    log('weather_started', {

      port: PORT,

      table:

        WEATHER_TABLE,

    });

  });

}


module.exports = {

  app,

  classifyRain,

  classifySnow,

  gridRatesForPeriod,

  parseDurationMs,

};
