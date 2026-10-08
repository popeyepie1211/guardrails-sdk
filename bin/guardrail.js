#!/usr/bin/env node

import { access, readFile, stat } from 'node:fs/promises';
import { constants as fsConstants } from 'node:fs';
import { Blob } from 'node:buffer';
import { basename, extname, resolve } from 'node:path';

const configName = 'guardrail.config.json';
const stringFields = ['model_id', 'model_name', 'domain', 'prediction_type'];
const arrayFields = [
  'feature_columns',
  'numerical_features',
  'categorical_features',
  'quasi_identifier_columns',
];
const fileFields = {
  model_file: ['.joblib', '.pkl'],
  historical_data_file: ['.csv'],
  preprocessor_file: ['.joblib', '.pkl'],
  shap_background_file: ['.csv'],
};

function inputError(message) {
  const error = new Error(message);
  error.exitCode = 2;
  return error;
}

async function localFile(value, field, required) {
  if (value == null && !required) return null;
  if (typeof value !== 'string' || !value.trim()) {
    throw inputError(`${field} must be a local file path in ${configName}.`);
  }
  const file = resolve(value);
  if (!fileFields[field].includes(extname(file).toLowerCase())) {
    throw inputError(`${field} must have a ${fileFields[field].join(' or ')} extension.`);
  }
  try {
    if (!(await stat(file)).isFile()) throw new Error('not a file');
    await access(file, fsConstants.R_OK);
  } catch {
    throw inputError(`${field} is missing or unreadable: ${value}`);
  }
  return file;
}

function validationDetail(body) {
  const detail = body?.detail;
  const message = typeof detail === 'string'
    ? detail
    : Array.isArray(detail)
      ? detail.map((item) => item?.msg).filter((item) => typeof item === 'string').join('; ')
      : '';
  // Do not echo arbitrary server content if it appears to contain a key.
  return message.includes('gr_') ? '' : message.slice(0, 300);
}

async function register() {
  let config;
  try {
    config = JSON.parse(await readFile(resolve(configName), 'utf8'));
  } catch (error) {
    if (error.code === 'ENOENT') throw inputError(`Create ${configName} in the current directory (see README).`);
    throw inputError(`Cannot read or parse ${configName}.`);
  }
  if (!config || typeof config !== 'object' || Array.isArray(config)) {
    throw inputError(`${configName} must contain a JSON object.`);
  }
  if ('apiKey' in config || 'api_key' in config) {
    throw inputError(`Never put an API key in ${configName}; keep it in a secret store.`);
  }
  for (const field of stringFields) {
    if (typeof config[field] !== 'string' || !config[field].trim()) {
      throw inputError(`${field} is required in ${configName}.`);
    }
  }
  for (const field of arrayFields) {
    if (!Array.isArray(config[field]) || (
      ['feature_columns', 'quasi_identifier_columns'].includes(field) && config[field].length === 0
    )) {
      throw inputError(`${field} must be ${field === 'feature_columns' || field === 'quasi_identifier_columns' ? 'a nonempty' : 'an'} array in ${configName}.`);
    }
  }

  let endpoint;
  try {
    const base = new URL(config.apiBaseUrl);
    if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password || base.search || base.hash) {
      throw new Error('invalid URL');
    }
    endpoint = new URL('api/models/register', base.href.endsWith('/') ? base : `${base.href}/`);
  } catch {
    throw inputError(`apiBaseUrl must be an HTTP(S) server URL in ${configName}.`);
  }

  const files = {};
  for (const field of Object.keys(fileFields)) {
    files[field] = await localFile(config[field], field, field === 'model_file' || field === 'historical_data_file');
  }

  const form = new FormData();
  for (const field of stringFields) form.append(field, config[field]);
  for (const field of arrayFields) form.append(field, JSON.stringify(config[field]));
  for (const field of ['model_version', 'prediction_column']) {
    if (config[field] != null) {
      if (typeof config[field] !== 'string' || !config[field].trim()) {
        throw inputError(`${field} must be a nonempty string in ${configName}.`);
      }
      form.append(field, config[field]);
    }
  }
  if (config.protected_attributes != null) {
    if (typeof config.protected_attributes !== 'object' || Array.isArray(config.protected_attributes)) {
      throw inputError(`protected_attributes must be an object in ${configName}.`);
    }
    form.append('protected_attributes', JSON.stringify(config.protected_attributes));
  }
  for (const [field, file] of Object.entries(files)) {
    if (file) form.append(field, new Blob([await readFile(file)]), basename(file));
  }

  let response;
  try {
    response = await fetch(endpoint, { method: 'POST', body: form });
  } catch {
    throw new Error('Could not reach the registration server. The request may have succeeded; check model status before retrying.');
  }
  if (response.status === 409) throw new Error('Model ID already exists (HTTP 409). Choose a different model_id.');
  if (response.status !== 201 && response.status !== 400 && response.status !== 422) {
    throw new Error(`Registration failed (HTTP ${response.status}). Check the server logs; do not retry blindly.`);
  }
  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error(`Registration server returned an invalid response (HTTP ${response.status}).`);
  }
  if (response.status === 201) {
    if (!body || typeof body.model_id !== 'string' || typeof body.api_key !== 'string' || !body.api_key) {
      throw new Error('Registration server returned an incomplete success response. Check model status before retrying.');
    }
    process.stdout.write(`✓ Model registered successfully\n\nModel ID:\n  ${body.model_id}\n\nAPI Key:\n  ${body.api_key}\n\nThis key is shown only once. Store it in your application's secret environment or secret manager.\n`);
    return;
  }
  const detail = validationDetail(body);
  throw new Error(`Registration rejected (HTTP ${response.status})${detail ? `: ${detail}` : '. Check your config and files.'}`);
}

const args = process.argv.slice(2);
if (args.length === 1 && (args[0] === '--help' || args[0] === '-h') ||
    args.length === 2 && args[0] === 'register' && (args[1] === '--help' || args[1] === '-h')) {
  process.stdout.write(`Usage: guardrail register\n\nRead ${configName} from the current directory and register a model.\nThe API key is printed once and never saved by the CLI.\n`);
} else if (args.length === 1 && args[0] === 'register') {
  register().catch((error) => {
    process.stderr.write(`guardrail: ${error.message}\n`);
    process.exitCode = error.exitCode || 1;
  });
} else {
  process.stderr.write('Usage: guardrail register (or guardrail --help)\n');
  process.exitCode = 2;
}
