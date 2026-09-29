#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const https = require("https");
const { URLSearchParams } = require("url");

function isOutlookRef(item) {
  const text = [
    item.connectorid || "",
    item.connectionreferencelogicalname || "",
    item.displayname || "",
  ].join(" ").toLowerCase();
  return text.includes("office365") || text.includes("outlook");
}

function requestJson(url, { method = "GET", headers = {}, body = null } = {}) {
  return new Promise((resolve, reject) => {
    const req = https.request(url, { method, headers }, (res) => {
      let data = "";
      res.setEncoding("utf8");
      res.on("data", (chunk) => { data += chunk; });
      res.on("end", () => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          reject(new Error(`HTTP_${res.statusCode}`));
          return;
        }
        try { resolve(data ? JSON.parse(data) : {}); }
        catch (err) { reject(err); }
      });
    });
    req.setTimeout(30000, () => req.destroy(new Error("REQUEST_TIMEOUT")));
    req.on("error", reject);
    if (body) req.write(body);
    req.end();
  });
}

async function acquireToken(tenant, client, secret, envUrl) {
  const form = new URLSearchParams({
    grant_type: "client_credentials",
    client_id: client,
    client_secret: secret,
    scope: envUrl.replace(/\/$/, "") + "/.default",
  }).toString();
  const payload = await requestJson(
    `https://login.microsoftonline.com/${encodeURIComponent(tenant)}/oauth2/v2.0/token`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Content-Length": Buffer.byteLength(form),
      },
      body: form,
    },
  );
  if (!payload.access_token) throw new Error("ACCESS_TOKEN_MISSING");
  return payload.access_token;
}

function selfTest() {
  if (!isOutlookRef({
    connectorid: "/providers/Microsoft.PowerApps/apis/shared_office365",
    connectionreferencelogicalname: "reqsys_outlook",
    displayname: "Office 365 Outlook",
  })) throw new Error("SELFTEST_OFFICE365_NOT_RECOGNIZED");

  if (isOutlookRef({
    connectorid: "/providers/Microsoft.PowerApps/apis/shared_planner",
    connectionreferencelogicalname: "reqsys_planner",
    displayname: "Planner",
  })) throw new Error("SELFTEST_FALSE_POSITIVE");

  console.log("POWERPLATFORM_OUTLOOK_PROBE_SELFTEST_OK");
}

async function main() {
  if (process.argv.includes("--self-test")) {
    selfTest();
    return;
  }

  const getArg = (name) => {
    const i = process.argv.indexOf(name);
    return i >= 0 ? process.argv[i + 1] : "";
  };
  const evidenceFile = getArg("--evidence-file");
  const correlationId = getArg("--correlation-id");
  if (!evidenceFile || !correlationId) throw new Error("REQUIRED_ARGUMENT_MISSING");

  const tenant = (process.env.POWERPLATFORM_TENANT_ID || "").trim();
  const client = (process.env.POWERPLATFORM_APP_ID || "").trim();
  const secret = (process.env.POWERPLATFORM_CLIENT_SECRET || "").trim();
  const envUrl = (process.env.DEV_ENVIRONMENT_URL || "").trim().replace(/\/$/, "");

  const evidence = {
    schema: "reqsys-powerplatform-outlook-probe/v2",
    correlation_id: correlationId,
    environment: "dev",
    configuration_complete: Boolean(tenant && client && secret && envUrl),
    secret_value_exposed: false,
    production_touched: false,
    read_only: true,
    outlook_connection_reference_count: 0,
    connection_references: [],
    usable_reference_found: false,
  };

  const out = path.resolve(evidenceFile);
  fs.mkdirSync(path.dirname(out), { recursive: true });

  if (!evidence.configuration_complete) {
    fs.writeFileSync(out, JSON.stringify(evidence, null, 2) + "\n", "utf8");
    console.error("POWERPLATFORM_OUTLOOK_PROBE_BLOCKED configuration_complete=false");
    process.exitCode = 2;
    return;
  }

  const bearer = await acquireToken(tenant, client, secret, envUrl);
  const select = encodeURIComponent("connectionreferencelogicalname,connectionid,connectorid,displayname,statecode");
  const payload = await requestJson(
    `${envUrl}/api/data/v9.2/connectionreferences?$select=${select}`,
    { headers: { Authorization: `Bearer ${bearer}`, Accept: "application/json" } },
  );

  const matches = (payload.value || []).filter(isOutlookRef).map((item) => {
    const connectionId = String(item.connectionid || "");
    return {
      logical_name: String(item.connectionreferencelogicalname || ""),
      display_name: String(item.displayname || ""),
      connector_id: String(item.connectorid || ""),
      statecode: item.statecode,
      has_connection_id: Boolean(connectionId),
      connection_id_sha256: connectionId
        ? crypto.createHash("sha256").update(connectionId).digest("hex")
        : null,
    };
  });

  evidence.outlook_connection_reference_count = matches.length;
  evidence.connection_references = matches;
  evidence.usable_reference_found = matches.some((x) => x.has_connection_id && x.logical_name);

  fs.writeFileSync(out, JSON.stringify(evidence, null, 2) + "\n", "utf8");
  console.log("POWERPLATFORM_OUTLOOK_PROBE_OK");
  console.log(`outlook_connection_reference_count=${matches.length}`);
  console.log(`usable_reference_found=${String(evidence.usable_reference_found)}`);
  console.log("secret_value_exposed=false");
}

main().catch((err) => {
  console.error(`POWERPLATFORM_OUTLOOK_PROBE_FAILED ${err.message}`);
  process.exitCode = 1;
});
