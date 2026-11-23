const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

function loadWeatherForRubricTests() {
  const filename = path.resolve(__dirname, '..', 'app.js');
  let source = fs.readFileSync(filename, 'utf8');

  source += `
module.exports.__rubric = {
  validDateFormat,
  dateInTimeZone,
  addCalendarDays,
  dateInsideSevenDayWindow,
  getLocalParts,
  hourlyPeriod,
  gridValuesForPeriod,
  gridRatesForPeriod,
  openMeteoValuesForPeriod,
  classifyRain,
  classifySnow,
  buildPeriodFacts,
};
`;

  const mod = new Module(filename, module);
  mod.filename = filename;
  mod.paths = Module._nodeModulePaths(path.dirname(filename));
  mod._compile(source, filename);
  return mod.exports.__rubric;
}

const {
  validDateFormat,
  dateInTimeZone,
  addCalendarDays,
  getLocalParts,
  gridValuesForPeriod,
  openMeteoValuesForPeriod,
  classifyRain,
  classifySnow,
  buildPeriodFacts,
} = loadWeatherForRubricTests();

function fixture(name) {
  return JSON.parse(
    fs.readFileSync(
      path.resolve(__dirname, 'fixtures', name),
      'utf8'
    )
  );
}

test('date parser rejects impossible and malformed dates', () => {
  assert.equal(validDateFormat('2026-11-23'), true);
  assert.equal(validDateFormat('2026-02-29'), false);
  assert.equal(validDateFormat('2026-13-01'), false);
  assert.equal(validDateFormat('11/23/2026'), false);
});

test('local date conversion respects timezone boundaries', () => {
  const instant = new Date('2026-11-23T05:30:00Z');

  assert.equal(
    dateInTimeZone(instant, 'America/Chicago'),
    '2026-11-22'
  );

  assert.equal(
    dateInTimeZone(instant, 'America/New_York'),
    '2026-11-23'
  );
});

test('local parts correctly handle daylight-saving fall-back hours', () => {
  const first = getLocalParts(
    new Date('2026-11-01T06:30:00Z'),
    'America/Chicago'
  );

  const second = getLocalParts(
    new Date('2026-11-01T07:30:00Z'),
    'America/Chicago'
  );

  assert.equal(first.date, '2026-11-01');
  assert.equal(second.date, '2026-11-01');
  assert.equal(first.hour, 1);
  assert.equal(second.hour, 1);
});

test('calendar-day arithmetic stays calendar based across month boundary', () => {
  assert.equal(
    addCalendarDays('2026-11-28', 6),
    '2026-12-04'
  );
});

test('recorded Zippopotam contract has expected place fields', () => {
  const data = fixture('zippopotam_60616.json');

  assert.equal(data['post code'], '60616');
  assert.ok(Array.isArray(data.places));
  assert.ok(data.places.length > 0);

  const place = data.places[0];
  assert.equal(typeof place.latitude, 'string');
  assert.equal(typeof place.longitude, 'string');
  assert.equal(typeof place['place name'], 'string');
  assert.equal(typeof place['state abbreviation'], 'string');
});

test('recorded NWS points contract contains timezone and forecast URLs', () => {
  const data = fixture('nws_points.json');

  assert.equal(
    data.properties.timeZone,
    'America/Chicago'
  );

  assert.match(
    data.properties.forecastHourly,
    /^https:\/\/api\.weather\.gov\//
  );

  assert.match(
    data.properties.forecastGridData,
    /^https:\/\/api\.weather\.gov\//
  );
});

test('recorded NWS hourly contract contains required report fields', () => {
  const data = fixture('nws_hourly.json');
  const periods = data.properties.periods;

  assert.ok(Array.isArray(periods));
  assert.ok(periods.length >= 2);

  for (const period of periods) {
    assert.equal(typeof period.startTime, 'string');
    assert.equal(typeof period.temperature, 'number');
    assert.equal(typeof period.windSpeed, 'string');
    assert.ok(period.relativeHumidity);
    assert.ok(period.probabilityOfPrecipitation);
  }
});

test('recorded Open-Meteo contract supplies aligned visibility and UV arrays', () => {
  const data = fixture('open_meteo.json');

  assert.equal(
    data.hourly.time.length,
    data.hourly.visibility.length
  );

  assert.equal(
    data.hourly.time.length,
    data.hourly.uv_index.length
  );
});

test('Open-Meteo parser selects only requested Morning hours', () => {
  const data = fixture('open_meteo.json');

  const values = openMeteoValuesForPeriod(
    data.hourly,
    'visibility',
    '2026-11-23',
    6,
    11
  );

  assert.deepEqual(values, [
    18800,
    18100,
    17600,
  ]);
});

test('missing Open-Meteo field returns no values, not zero', () => {
  const data = fixture('open_meteo_missing_visibility.json');

  const values = openMeteoValuesForPeriod(
    data.hourly,
    'visibility',
    '2026-11-23',
    6,
    11
  );

  assert.deepEqual(values, []);
});

test('NWS grid missing values are ignored rather than converted to zero', () => {
  const property = {
    values: [
      {
        validTime: '2026-11-23T12:00:00+00:00/PT1H',
        value: null,
      },
    ],
  };

  const values = gridValuesForPeriod(
    property,
    '2026-11-23',
    6,
    11,
    'America/Chicago'
  );

  assert.deepEqual(values, []);
});

test('Rain probability boundary is deterministic', () => {
  assert.equal(classifyRain(0, 19), 'No');
  assert.equal(classifyRain(0, 20), 'Mild');
});

test('Rain missing amount and probability is unavailable', () => {
  assert.equal(
    classifyRain(null, null),
    'Not available'
  );
});

test('Snow missing amount is unavailable', () => {
  assert.equal(
    classifySnow(null),
    'Not available'
  );
});

test('period aggregation calculates ranges, max wind, average humidity and supplemental fields', () => {
  const hourly = fixture('nws_hourly.json');
  const grid = fixture('nws_grid.json').properties;
  const openMeteo = fixture('open_meteo.json');

  const facts = buildPeriodFacts({
    name: 'Morning',
    selectedDate: '2026-11-23',
    startHour: 6,
    endHour: 11,
    hourlyPeriods: hourly.properties.periods,
    grid,
    openMeteo,
    timeZone: 'America/Chicago',
  });

  assert.equal(facts.period, 'Morning');
  assert.equal(facts.temperature.min, 33);
  assert.equal(facts.temperature.max, 39);
  assert.equal(facts.temperature.unit, 'F');
  assert.equal(
    facts.temperature.source,
    'National Weather Service'
  );
  assert.equal(facts.windSpeed.maxMph, 15);
  assert.equal(facts.humidity.averagePercent, 70);
  assert.equal(facts.visibility.miles !== null, true);
  assert.equal(facts.uv.max, 2.45);
});

test('supplemental source outage degrades fields instead of inventing numbers', () => {
  const hourly = fixture('nws_hourly.json');
  const grid = fixture('nws_grid_missing_supplemental.json').properties;

  const facts = buildPeriodFacts({
    name: 'Morning',
    selectedDate: '2026-11-23',
    startHour: 6,
    endHour: 11,
    hourlyPeriods: hourly.properties.periods,
    grid,
    openMeteo: null,
    timeZone: 'America/Chicago',
  });

  assert.equal(facts.visibility.miles, null);
  assert.equal(facts.uv.max, null);
  assert.notEqual(facts.temperature.min, null);
  assert.notEqual(facts.windSpeed.maxMph, null);
});
