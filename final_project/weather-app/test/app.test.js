const test = require(
  'node:test'
);

const assert = require(
  'node:assert/strict'
);

const {
  classifyRain,
  classifySnow,
  gridRatesForPeriod,
  parseDurationMs,
} = require('../app');


test(
  'rain below heavy boundary is Mild',
  () => {
    assert.equal(
      classifyRain(7.61, 0),
      'Mild'
    );
  }
);


test(
  'rain exactly at 7.62 mm/h is Mild',
  () => {
    assert.equal(
      classifyRain(7.62, 0),
      'Mild'
    );
  }
);


test(
  'rain above 7.62 mm/h is Heavy',
  () => {
    assert.equal(
      classifyRain(7.63, 0),
      'Heavy'
    );
  }
);


test(
  'rain with no amount and no probability is unavailable',
  () => {
    assert.equal(
      classifyRain(null, null),
      'Not available'
    );
  }
);


test(
  'rain with zero amount and zero probability is No',
  () => {
    assert.equal(
      classifyRain(0, 0),
      'No'
    );
  }
);


test(
  'snow below 8.47 mm/h is Mild',
  () => {
    assert.equal(
      classifySnow(8.46),
      'Mild'
    );
  }
);


test(
  'snow exactly at 8.47 mm/h is Heavy',
  () => {
    assert.equal(
      classifySnow(8.47),
      'Heavy'
    );
  }
);


test(
  'snow above 8.47 mm/h is Heavy',
  () => {
    assert.equal(
      classifySnow(8.48),
      'Heavy'
    );
  }
);


test(
  'snow zero is No',
  () => {
    assert.equal(
      classifySnow(0),
      'No'
    );
  }
);


test(
  'snow missing value is unavailable',
  () => {
    assert.equal(
      classifySnow(null),
      'Not available'
    );
  }
);


test(
  'ISO duration parser converts six hours correctly',
  () => {
    assert.equal(
      parseDurationMs('PT6H'),
      6 * 60 * 60 * 1000
    );
  }
);


test(
  'grid precipitation amount is normalized by validTime duration',
  () => {
    const property = {
      values: [
        {
          validTime:
            '2026-11-16T06:00:00-06:00/PT6H',

          value:
            45.72,
        },
      ],
    };

    const rates =
      gridRatesForPeriod(
        property,
        '2026-11-16',
        6,
        11,
        'America/Chicago'
      );

    assert.equal(
      rates.length,
      1
    );

    assert.ok(
      Math.abs(
        rates[0] - 7.62
      ) < 0.0001
    );
  }
);
