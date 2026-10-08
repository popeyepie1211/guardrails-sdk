import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { createServer } from 'node:http';
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

const cli = resolve('bin/guardrail.js');

async function run(cwd, ...args) {
  return new Promise((resolveRun, reject) => {
    const child = spawn(process.execPath, [cli, ...args], { cwd });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => { stdout += chunk; });
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.on('error', reject);
    child.on('close', (code) => resolveRun({ code, stdout, stderr }));
  });
}

async function project(fn) {
  const dir = await mkdtemp(join(tmpdir(), 'guardrail-cli-'));
  try {
    await writeFile(join(dir, 'model.joblib'), 'mock model');
    await writeFile(join(dir, 'history.csv'), 'age,prediction\n21,1\n');
    const config = {
      apiBaseUrl: 'http://127.0.0.1:1',
      model_id: 'test_model',
      model_name: 'Test Model',
      domain: 'standard',
      prediction_type: 'binary',
      feature_columns: ['age'],
      numerical_features: ['age'],
      categorical_features: [],
      quasi_identifier_columns: ['age'],
      model_file: 'model.joblib',
      historical_data_file: 'history.csv',
    };
    const save = () => writeFile(join(dir, 'guardrail.config.json'), JSON.stringify(config));
    return await fn({ dir, config, save });
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}

async function mockServer(reply, fn) {
  let request;
  const server = createServer(async (req, res) => {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    request = { method: req.method, url: req.url, headers: req.headers, body: Buffer.concat(chunks).toString() };
    const result = reply(request);
    res.writeHead(result.status, { 'content-type': 'application/json' });
    res.end(typeof result.body === 'string' ? result.body : JSON.stringify(result.body));
  });
  await new Promise((resolveListen) => server.listen(0, '127.0.0.1', resolveListen));
  try {
    return await fn(`http://127.0.0.1:${server.address().port}`, () => request);
  } finally {
    await new Promise((resolveClose) => server.close(resolveClose));
  }
}

test('help works without a config', async () => {
  await project(async ({ dir }) => {
    const result = await run(dir, '--help');
    assert.equal(result.code, 0);
    assert.match(result.stdout, /guardrail register/);
  });
});

test('required config fields and files fail before any request', async () => {
  await project(async ({ dir, config, save }) => {
    let result = await run(dir, 'register');
    assert.equal(result.code, 2);
    assert.match(result.stderr, /Create guardrail.config.json/);

    delete config.model_id;
    await save();
    result = await run(dir, 'register');
    assert.equal(result.code, 2);
    assert.match(result.stderr, /model_id is required/);

    config.model_id = 'test_model';
    config.model_file = 'missing.joblib';
    await save();
    result = await run(dir, 'register');
    assert.equal(result.code, 2);
    assert.match(result.stderr, /model_file is missing or unreadable/);

    config.model_file = 'model.joblib';
    config.historical_data_file = 'missing.csv';
    await save();
    result = await run(dir, 'register');
    assert.equal(result.code, 2);
    assert.match(result.stderr, /historical_data_file is missing or unreadable/);

    config.historical_data_file = 'history.txt';
    await save();
    result = await run(dir, 'register');
    assert.equal(result.code, 2);
    assert.match(result.stderr, /historical_data_file must have a .csv extension/);

    config.historical_data_file = 'history.csv';
    config.model_file = 'model.txt';
    await save();
    result = await run(dir, 'register');
    assert.equal(result.code, 2);
    assert.match(result.stderr, /model_file must have a .joblib or .pkl extension/);

    config.model_file = 'model.joblib';
    config.apiKey = 'should-not-be-saved';
    await save();
    result = await run(dir, 'register');
    assert.equal(result.code, 2);
    assert.match(result.stderr, /Never put an API key/);
    assert.doesNotMatch(result.stderr, /should-not-be-saved/);
  });
});

test('registration sends backend multipart fields and prints key once without writing it', async () => {
  const apiKey = `gr_${randomBytes(16).toString('hex')}`;
  await mockServer(() => ({ status: 201, body: { model_id: 'test_model', api_key: apiKey } }), async (base, getRequest) => {
    await project(async ({ dir, config, save }) => {
      config.apiBaseUrl = base;
      config.model_version = 'v2';
      config.prediction_column = 'prediction';
      config.protected_attributes = { type: 'categorical', columns: ['group'] };
      config.preprocessor_file = 'preprocessor.pkl';
      config.shap_background_file = 'background.csv';
      await writeFile(join(dir, 'preprocessor.pkl'), 'mock preprocessor');
      await writeFile(join(dir, 'background.csv'), 'age\n21\n');
      await save();
      const before = await readdir(dir);
      const configBefore = await readFile(join(dir, 'guardrail.config.json'), 'utf8');

      const result = await run(dir, 'register');
      assert.equal(result.code, 0, result.stderr);
      assert.match(result.stdout, /Model registered successfully/);
      assert.equal(result.stdout.split(apiKey).length - 1, 1);
      assert.match(result.stdout, /shown only once/);
      assert.equal(result.stderr, '');
      assert.deepEqual(await readdir(dir), before);
      assert.equal(await readFile(join(dir, 'guardrail.config.json'), 'utf8'), configBefore);
      for (const name of before) {
        assert.doesNotMatch(await readFile(join(dir, name), 'utf8'), new RegExp(apiKey));
      }

      const request = getRequest();
      assert.equal(request.method, 'POST');
      assert.equal(request.url, '/api/models/register');
      assert.match(request.headers['content-type'], /^multipart\/form-data; boundary=/);
      for (const field of [
        'model_id', 'model_name', 'domain', 'prediction_type', 'feature_columns',
        'numerical_features', 'categorical_features', 'quasi_identifier_columns',
        'protected_attributes', 'model_version', 'prediction_column', 'model_file',
        'historical_data_file', 'preprocessor_file', 'shap_background_file',
      ]) {
        assert.ok(request.body.includes(`name="${field}"`), `missing ${field}`);
      }
      assert.ok(request.body.includes('["age"]'));
      assert.ok(request.body.includes('filename="model.joblib"'));
      assert.ok(request.body.includes('filename="history.csv"'));
    });
  });
});

for (const [label, status, body, expected] of [
  ['duplicate', 409, { detail: 'duplicate' }, /already exists.*409/],
  ['validation', 422, { detail: 'Invalid domain' }, /Invalid domain/],
  ['server', 500, { detail: 'internal error' }, /HTTP 500/],
  ['malformed success', 201, { model_id: 'test_model' }, /incomplete success response/],
]) {
  test(`${label} response exits unsuccessfully`, async () => {
    await mockServer(() => ({ status, body }), async (base) => {
      await project(async ({ dir, config, save }) => {
        config.apiBaseUrl = base;
        await save();
        const result = await run(dir, 'register');
        assert.equal(result.code, 1);
        assert.match(result.stderr, expected);
        assert.doesNotMatch(result.stdout, /API Key:/);
      });
    });
  });
}

test('connection failure is actionable and does not print a key', async () => {
  await project(async ({ dir, save }) => {
    await save();
    const result = await run(dir, 'register');
    assert.equal(result.code, 1);
    assert.match(result.stderr, /check model status before retrying/);
    assert.doesNotMatch(result.stdout, /API Key:/);
  });
});
