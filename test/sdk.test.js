import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFileSync } from 'node:fs';
import { DataBuffer } from '../src/buffer.js';
import { Transport } from '../src/transport.js';
import guardrail, { Guardrail } from '../src/index.js';
import { SDK_VERSION } from '../src/constants.js';
const packageJson = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));

async function endpoint(t, respond) {
  const requests = [];
  const server = createServer(async (request, response) => {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    requests.push({ headers: request.headers, body: JSON.parse(Buffer.concat(chunks).toString()) });
    const { status, body } = respond(requests.length);
    response.writeHead(status, { 'Content-Type': 'application/json' });
    response.end(JSON.stringify(body));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  return { url: `http://127.0.0.1:${server.address().port}/v1/ingest`, requests };
}

test('buffer pushes, manually flushes, and flushes at batch size', async () => {
  const sent = [];
  const buffer = new DataBuffer(batch => sent.push(batch), { batchSize: 2, flushIntervalMs: 1000 });
  buffer.push(1);
  assert.deepEqual(buffer.queue, [1]);
  await buffer.flush();
  assert.deepEqual(sent, [[1]]);
  buffer.push(2);
  buffer.push(3);
  await buffer.flush();
  assert.deepEqual(sent, [[1], [2, 3]]);
  await buffer.shutdown();
});

test('buffer flushes on timer and drops oldest on overflow', async () => {
  const sent = [];
  const timerBuffer = new DataBuffer(batch => sent.push(batch), { batchSize: 10, flushIntervalMs: 20 });
  timerBuffer.push('timer');
  await new Promise(resolve => setTimeout(resolve, 60));
  assert.deepEqual(sent, [['timer']]);
  await timerBuffer.shutdown();

  const overflow = new DataBuffer(batch => sent.push(batch), {
    batchSize: 10, flushIntervalMs: 1000, maxQueueLimit: 2
  });
  const originalWarn = console.warn;
  console.warn = () => {};
  try {
    overflow.push(1);
    overflow.push(2);
    overflow.push(3);
  } finally {
    console.warn = originalWarn;
  }
  assert.deepEqual(overflow.queue, [2, 3]);
  await overflow.shutdown();
  assert.deepEqual(sent.at(-1), [2, 3]);
});

test('transport: 401 auth failure makes exactly one attempt and reports auth', async t => {
  const { url, requests } = await endpoint(t, () => ({ status: 401, body: { message: 'Unauthorized' } }));
  const failures = [];
  const transport = new Transport({ apiKey: 'wrong', modelId: 'model-a', endpoint: url,
    onError: (error, context) => failures.push({ status: error.response.status, context }) });
  assert.equal(await transport.sendBatch([{ eventId: 'one' }]), false);
  assert.equal(requests.length, 1);
  assert.equal(requests[0].headers['x-api-key'], 'wrong');
  assert.deepEqual(failures.map(f => [f.status, f.context.type, f.context.modelId]), [[401, 'auth', 'model-a']]);
  assert.equal(failures[0].context.batchId, requests[0].body.batchId);
});

test('transport: 403 auth failure also makes exactly one attempt', async t => {
  const { url, requests } = await endpoint(t, () => ({ status: 403, body: { message: 'Forbidden' } }));
  const failures = [];
  const transport = new Transport({ apiKey: 'wrong', modelId: 'model-a', endpoint: url,
    onError: (_error, context) => failures.push(context.type) });
  assert.equal(await transport.sendBatch([{}]), false);
  assert.equal(requests.length, 1);
  assert.deepEqual(failures, ['auth']);
});

test('transport: 5xx retries after a real 1s delay, then succeeds', async t => {
  const { url, requests } = await endpoint(t, count => count === 1
    ? { status: 503, body: { message: 'unavailable' } }
    : { status: 201, body: { status: 'success' } });
  const failures = [];
  const transport = new Transport({ apiKey: 'key', modelId: 'model-a', endpoint: url,
    onError: (_error, context) => failures.push(context) });
  const started = performance.now();
  assert.equal(await transport.sendBatch([{}]), true);
  const elapsed = performance.now() - started;
  assert.equal(requests.length, 2);
  assert.ok(elapsed >= 950, `expected >=950ms, observed ${elapsed}ms`);
  assert.equal(requests[0].body.batchId, requests[1].body.batchId);
  assert.deepEqual(failures, []);
});

test('transport: 422 validation failure makes one attempt and reports response body', async t => {
  const { url, requests } = await endpoint(t, () => ({ status: 422, body: { detail: 'invalid event' } }));
  const failures = [];
  const messages = [];
  const originalError = console.error;
  console.error = message => messages.push(message);
  try {
    const transport = new Transport({ apiKey: 'key', modelId: 'model-a', endpoint: url,
      onError: (error, context) => failures.push({ status: error.response.status, context }) });
    assert.equal(await transport.sendBatch([{}]), false);
  } finally {
    console.error = originalError;
  }
  assert.equal(requests.length, 1);
  assert.equal(failures[0].status, 422);
  assert.equal(failures[0].context.type, 'validation');
  assert.match(messages[0], /invalid event/);
});

test('transport: exhausted network retries make four attempts with 1s, 2s, 4s backoff', async t => {
  const { url } = await endpoint(t, () => ({ status: 503, body: { message: 'unavailable' } }));
  const failures = [];
  const times = [];
  const transport = new Transport({ apiKey: 'key', modelId: 'model-a', endpoint: url,
    onError: (_error, context) => failures.push(context) });
  transport.api.interceptors.request.use(config => { times.push(performance.now()); return config; });
  assert.equal(await transport.sendBatch([{}]), false);
  assert.equal(times.length, 4);
  const delays = times.slice(1).map((time, i) => Math.round(time - times[i]));
  assert.ok(delays[0] >= 950 && delays[1] >= 1950 && delays[2] >= 3950, `observed delays: ${delays}`);
  assert.deepEqual(failures.map(f => f.type), ['network']);
});

test('Guardrail wrap preserves results, model errors, and event schema', async () => {
  assert.ok(guardrail instanceof Guardrail);
  assert.equal(SDK_VERSION, packageJson.version);
  const sdk = new Guardrail();
  sdk.init({ apiKey: 'key', modelId: 'model-a' });
  sdk.transport.api.post = async () => ({ status: 201 });
  const result = { label: 'approved', confidence: 0.8 };
  const modelError = new Error('model failure');
  const wrapped = sdk.wrap({ predict: async value => {
    if (value === 'error') throw modelError;
    return result;
  } });
  assert.strictEqual(await wrapped.predict({ amount: 2 }), result);
  await assert.rejects(wrapped.predict('error'), error => error === modelError);
  assert.equal(sdk.buffer.queue.length, 1);
  const event = sdk.buffer.queue[0];
  assert.deepEqual(Object.keys(event), [
    'eventId', 'modelId', 'timestamp', 'latencyMs', 'inputFeatures', 'prediction',
    'metadata', 'latency', 'input', 'output'
  ]);
  assert.deepEqual(Object.keys(event.prediction), ['value', 'label', 'confidence', 'type']);
  assert.deepEqual(Object.keys(event.metadata), [
    'method', 'domain', 'prediction_type', 'node_name', 'model_version'
  ]);
  await sdk.shutdown();
});

test('Guardrail reports adapter failures without changing model result', async () => {
  const failures = [];
  const sdk = new Guardrail();
  sdk.init({ apiKey: 'key', modelId: 'model-a',
    inputAdapter: () => { throw new Error('adapter failure'); },
    onError: (error, context) => failures.push({ error, context }) });
  const result = { label: 'approved' };
  assert.strictEqual(await sdk.wrap({ predict: () => result }).predict({}), result);
  assert.equal(failures.length, 1);
  assert.equal(failures[0].error.message, 'adapter failure');
  assert.deepEqual(failures[0].context, { type: 'adapter', modelId: 'model-a' });
  assert.equal(sdk.buffer.queue.length, 0);
  await sdk.shutdown();
});

test('Guardrail init options reach transport and report auth failure', async t => {
  const { url, requests } = await endpoint(t, () => ({ status: 401, body: { message: 'Unauthorized' } }));
  const failures = [];
  const sdk = new Guardrail();
  sdk.init({ apiKey: 'wrong', modelId: 'model-a', endpoint: url,
    batchSize: 1, flushIntervalMs: 123, requestTimeoutMs: 42, maxQueueLimit: 2, maxRetries: 0,
    onError: (_error, context) => failures.push(context) });
  assert.equal(sdk.buffer.maxBatchSize, 1);
  assert.equal(sdk.buffer.flushInterval, 123);
  assert.equal(sdk.buffer.maxQueueLimit, 2);
  assert.equal(sdk.transport.api.defaults.timeout, 42);
  assert.equal(sdk.transport.maxRetries, 0);
  await sdk.wrap({ predict: value => value }).predict(1);
  await sdk.flush();
  assert.equal(requests.length, 1);
  assert.deepEqual(failures.map(f => f.type), ['auth']);
  assert.deepEqual(Object.keys(requests[0].body), [
    'batchId', 'modelId', 'sdkVersion', 'sentAt', 'metadata', 'payload'
  ]);
  await sdk.shutdown();
});

test('Guardrail init validates credentials and warns on unsupported predictionType', async () => {
  const sdk = new Guardrail();
  assert.throws(() => sdk.init({ apiKey: '', modelId: 'model-a' }), /apiKey/);
  assert.throws(() => sdk.init({ apiKey: 'key', modelId: ' ' }), /modelId/);
  const warnings = [];
  const originalWarn = console.warn;
  console.warn = message => warnings.push(message);
  try {
    sdk.init({ apiKey: 'key', modelId: 'model-a', predictionType: 'unknown' });
  } finally {
    console.warn = originalWarn;
  }
  assert.match(warnings[0], /Unsupported predictionType/);
  await sdk.shutdown();
});
