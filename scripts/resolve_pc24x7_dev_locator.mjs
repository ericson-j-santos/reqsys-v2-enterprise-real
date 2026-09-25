#!/usr/bin/env node
/**
 * Resolve o Quick Tunnel DEV vigente a partir do locator público assinado.
 *
 * Sem segredo: tópico e chave pública são, por contrato, material público.
 * Falha fechado para assinatura inválida, payload expirado, ambiente divergente
 * ou URL fora de https://*.trycloudflare.com.
 */
import { appendFileSync, writeFileSync } from "node:fs";
import {
  createPublicKey,
  generateKeyPairSync,
  sign,
  verify,
} from "node:crypto";

export const TOPIC = "reqsys-dev-locator-2b0950c3bf37ac05b46bdb70ab793ca4c85b220b";
export const PUBLIC_KEY_B64 = "xMQwHfokBxBOkP1bvDCxBDdzmnXlVxApGQbwQ9h8kr8=";
export const TITLE = "reqsys-dev-locator";
export const ENDPOINT = `https://ntfy.sh/${TOPIC}/json?poll=1&since=1h`;
const ED25519_SPKI_PREFIX = Buffer.from("302a300506032b6570032100", "hex");

function b64(value) {
  return Buffer.from(value, "base64");
}

function rawPublicKey(publicKeyB64) {
  const raw = b64(publicKeyB64);
  if (raw.length !== 32) {
    throw new Error("locator_public_key_invalid_length");
  }
  return createPublicKey({
    key: Buffer.concat([ED25519_SPKI_PREFIX, raw]),
    format: "der",
    type: "spki",
  });
}

export function allowedRuntimeUrl(value) {
  try {
    const parsed = new URL(value);
    return (
      parsed.protocol === "https:" &&
      parsed.hostname.endsWith(".trycloudflare.com") &&
      parsed.username === "" &&
      parsed.password === "" &&
      parsed.port === ""
    );
  } catch {
    return false;
  }
}

export function verifyEnvelope(
  rawMessage,
  { publicKeyB64 = PUBLIC_KEY_B64, nowEpoch = Math.floor(Date.now() / 1000) } = {},
) {
  let envelope;
  try {
    envelope = JSON.parse(rawMessage);
  } catch {
    return null;
  }
  if (
    envelope?.v !== 1 ||
    typeof envelope.payload_b64 !== "string" ||
    typeof envelope.signature_b64 !== "string"
  ) {
    return null;
  }

  let verified = false;
  try {
    verified = verify(
      null,
      Buffer.from(envelope.payload_b64, "ascii"),
      rawPublicKey(publicKeyB64),
      b64(envelope.signature_b64),
    );
  } catch {
    return null;
  }
  if (!verified) return null;

  let payload;
  try {
    payload = JSON.parse(b64(envelope.payload_b64).toString("utf8"));
  } catch {
    return null;
  }

  if (
    payload?.environment !== "dev" ||
    !Number.isInteger(payload.issued_at) ||
    !Number.isInteger(payload.expires_at) ||
    payload.expires_at <= nowEpoch ||
    payload.issued_at > nowEpoch + 60 ||
    payload.expires_at - payload.issued_at > 900 ||
    !Array.isArray(payload.urls) ||
    payload.urls.length === 0 ||
    !payload.urls.includes(payload.selected_url) ||
    payload?.runtime_contract?.version !== "2.0.0" ||
    payload?.runtime_contract?.static_frontend_required !== true ||
    payload?.runtime_contract?.vite_hmr_forbidden !== true ||
    !Array.isArray(payload?.runtime_contract?.required_endpoints) ||
    !["/api/health", "/api/runtime/health", "/api/runtime/readiness", "/api/runtime/build-info"].every(
      (endpoint) => payload.runtime_contract.required_endpoints.includes(endpoint),
    ) ||
    !allowedRuntimeUrl(payload.selected_url) ||
    !payload.urls.every(allowedRuntimeUrl)
  ) {
    return null;
  }

  return {
    environment: "dev",
    issued_at: payload.issued_at,
    expires_at: payload.expires_at,
    selected_url: payload.selected_url.replace(/\/$/, ""),
    urls: [...new Set(payload.urls.map((item) => item.replace(/\/$/, "")))],
    runtime_contract: {
      version: payload.runtime_contract.version,
      required_endpoints: [...payload.runtime_contract.required_endpoints],
      static_frontend_required: true,
      vite_hmr_forbidden: true,
    },
  };
}

export function resolveRows(text, options = {}) {
  const messages = [];
  for (const line of text.split(/\r?\n/).filter(Boolean)) {
    try {
      const item = JSON.parse(line);
      if (item?.event === "message" && item?.title === TITLE && typeof item.message === "string") {
        messages.push(item);
      }
    } catch {
      // Linha inválida não pode invalidar uma mensagem posterior assinada.
    }
  }

  for (const item of messages.reverse()) {
    const payload = verifyEnvelope(item.message, options);
    if (payload) return payload;
  }
  throw new Error("no_valid_fresh_signed_locator");
}

export async function resolveRemote(options = {}) {
  const response = await fetch(options.endpoint || ENDPOINT, {
    cache: "no-store",
    headers: { Accept: "application/x-ndjson,text/plain" },
  });
  if (!response.ok) {
    throw new Error(`locator_http_${response.status}`);
  }
  return resolveRows(await response.text(), options);
}

function envelopeForTest(payload, privateKey) {
  const payloadB64 = Buffer.from(
    JSON.stringify(payload, Object.keys(payload).sort()),
    "utf8",
  ).toString("base64");
  return JSON.stringify({
    v: 1,
    payload_b64: payloadB64,
    signature_b64: sign(null, Buffer.from(payloadB64, "ascii"), privateKey).toString("base64"),
  });
}

function selfTest() {
  const { publicKey, privateKey } = generateKeyPairSync("ed25519");
  const der = publicKey.export({ type: "spki", format: "der" });
  const publicKeyB64 = der.subarray(-32).toString("base64");
  const now = 2_000_000_000;
  const validPayload = {
    environment: "dev",
    issued_at: now - 10,
    expires_at: now + 300,
    selected_url: "https://valid-example.trycloudflare.com",
    urls: ["https://valid-example.trycloudflare.com"],
    runtime_contract: {
      version: "2.0.0",
      required_endpoints: ["/api/health", "/api/runtime/health", "/api/runtime/readiness", "/api/runtime/build-info"],
      static_frontend_required: true,
      vite_hmr_forbidden: true,
    },
  };

  const good = verifyEnvelope(envelopeForTest(validPayload, privateKey), {
    publicKeyB64,
    nowEpoch: now,
  });
  if (!good || good.selected_url !== validPayload.selected_url) {
    throw new Error("self_test_valid_signature_failed");
  }

  const expired = { ...validPayload, expires_at: now - 1 };
  if (verifyEnvelope(envelopeForTest(expired, privateKey), { publicKeyB64, nowEpoch: now })) {
    throw new Error("self_test_expired_locator_accepted");
  }

  const legacyContract = { ...validPayload };
  delete legacyContract.runtime_contract;
  if (verifyEnvelope(envelopeForTest(legacyContract, privateKey), { publicKeyB64, nowEpoch: now })) {
    throw new Error("self_test_legacy_locator_accepted");
  }

  const wrongHost = {
    ...validPayload,
    selected_url: "https://example.invalid",
    urls: ["https://example.invalid"],
  };
  if (verifyEnvelope(envelopeForTest(wrongHost, privateKey), { publicKeyB64, nowEpoch: now })) {
    throw new Error("self_test_wrong_host_accepted");
  }

  const tampered = JSON.parse(envelopeForTest(validPayload, privateKey));
  tampered.payload_b64 = Buffer.from('{"environment":"dev"}').toString("base64");
  if (verifyEnvelope(JSON.stringify(tampered), { publicKeyB64, nowEpoch: now })) {
    throw new Error("self_test_invalid_signature_accepted");
  }

  process.stdout.write(JSON.stringify({ self_test: true }) + "\n");
}

function args(argv) {
  const parsed = { output: "" };
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index];
    if (item === "--self-test") parsed.selfTest = true;
    else if (item === "--output") parsed.output = argv[++index] || "";
    else throw new Error(`unknown_argument:${item}`);
  }
  return parsed;
}

async function main() {
  const input = args(process.argv.slice(2));
  if (input.selfTest) {
    selfTest();
    return;
  }
  const result = await resolveRemote();
  const evidence = {
    schema_version: "1.0.0",
    contract: "reqsys-pc24x7-dev-signed-locator-resolution",
    ...result,
    locator_transport: "ntfy_signed_ed25519",
    signature_verified: true,
    rdc_required: false,
    production_touched: false,
    secrets_read: false,
  };
  const raw = JSON.stringify(evidence, null, 2) + "\n";
  if (input.output) writeFileSync(input.output, raw, "utf8");
  process.stdout.write(raw);
  if (process.env.GITHUB_OUTPUT) {
    appendFileSync(process.env.GITHUB_OUTPUT, `base_url=${result.selected_url}\n`);
    appendFileSync(process.env.GITHUB_OUTPUT, `frontend_url=${result.selected_url}\n`);
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((error) => {
    process.stderr.write(`SIGNED_LOCATOR_BLOCKED: ${error.message}\n`);
    process.exitCode = 2;
  });
}
