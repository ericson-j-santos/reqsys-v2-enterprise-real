#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const https = require("https");
const crypto = require("crypto");

const FLOW_NAME = "PA-E2E - Change 1842 Outlook Idempotency 20260928";
const EVENT_SUBJECT = "[PA-E2E CHANGE 1842] Revisao pos-aprovacao 20260928";
const IDEMPOTENCY_KEY = "CHANGE-1842-CALENDAR-REVIEW-PA-E2E-20260928-V1";
const EVENT_START = "2026-09-30T14:00:00";
const EVENT_END = "2026-09-30T14:30:00";
const CONNECTION_KEY = "shared_office365";
const API_ID = "/providers/Microsoft.PowerApps/apis/shared_office365";

function arg(name, fallback = "") {
  const i = process.argv.indexOf(name);
  return i >= 0 && i + 1 < process.argv.length ? process.argv[i + 1] : fallback;
}

function requestRaw(url, { method = "GET", headers = {}, body = null } = {}) {
  return new Promise((resolve, reject) => {
    const req = https.request(url, { method, headers }, (res) => {
      const chunks = [];
      res.on("data", chunk => chunks.push(Buffer.from(chunk)));
      res.on("end", () => resolve({
        status: res.statusCode || 0,
        headers: res.headers,
        body: Buffer.concat(chunks).toString("utf8"),
      }));
    });
    req.setTimeout(45000, () => req.destroy(new Error("REQUEST_TIMEOUT")));
    req.on("error", reject);
    if (body) req.write(body);
    req.end();
  });
}

async function requestJson(url, opts = {}) {
  const res = await requestRaw(url, opts);
  if (res.status < 200 || res.status >= 300) {
    const detail = res.body.slice(0, 800).replace(/[\r\n]+/g, " ");
    throw new Error(`HTTP_${res.status} ${detail}`);
  }
  return { ...res, json: res.body ? JSON.parse(res.body) : {} };
}

async function token(tenant, client, secret, envUrl) {
  const body = new URLSearchParams({
    grant_type: "client_credentials",
    client_id: client,
    client_secret: secret,
    scope: envUrl.replace(/\/$/, "") + "/.default",
  }).toString();
  const res = await requestJson(
    `https://login.microsoftonline.com/${encodeURIComponent(tenant)}/oauth2/v2.0/token`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Content-Length": Buffer.byteLength(body),
      },
      body,
    },
  );
  if (!res.json.access_token) throw new Error("ACCESS_TOKEN_MISSING");
  return res.json.access_token;
}

function dvHeaders(accessToken) {
  return {
    Authorization: `Bearer ${accessToken}`,
    Accept: "application/json",
    "Content-Type": "application/json",
    "OData-MaxVersion": "4.0",
    "OData-Version": "4.0",
  };
}

function connectionName(connectionId) {
  const raw = String(connectionId || "").replace(/\/$/, "");
  return raw.split("/").filter(Boolean).pop() || raw;
}

function isOffice365(item) {
  return String(item.connectorid || "").toLowerCase().includes("/shared_office365");
}

function buildClientData(ref) {
  const calendarExpr = "@first(body('Get_calendars_V2')?['value'])?['id']";
  const filter = `subject eq '${EVENT_SUBJECT}'`;

  const outlookInputs = (operationId, parameters) => ({
    host: {
      apiId: API_ID,
      connectionName: CONNECTION_KEY,
      operationId,
    },
    parameters,
    authentication: "@parameters('$authentication')",
  });

  const definition = {
    "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
    contentVersion: "1.0.0.0",
    parameters: {
      "$connections": { defaultValue: {}, type: "Object" },
      "$authentication": { defaultValue: {}, type: "SecureObject" },
    },
    triggers: {
      Recurrence: {
        type: "Recurrence",
        recurrence: { frequency: "Minute", interval: 1 },
      },
    },
    actions: {
      Get_calendars_V2: {
        type: "OpenApiConnection",
        runAfter: {},
        inputs: outlookInputs("CalendarGetTables_V2", {}),
      },
      Init_EventId: {
        type: "InitializeVariable",
        runAfter: { Get_calendars_V2: ["Succeeded"] },
        inputs: { variables: [{ name: "EventId", type: "string", value: "" }] },
      },
      Get_events_pass1: {
        type: "OpenApiConnection",
        runAfter: { Init_EventId: ["Succeeded"] },
        inputs: outlookInputs("V4CalendarGetItems", {
          table: calendarExpr,
          "$filter": filter,
          "$top": 10,
        }),
      },
      Pass1_create_if_missing: {
        type: "If",
        runAfter: { Get_events_pass1: ["Succeeded"] },
        expression: {
          and: [{
            equals: ["@length(body('Get_events_pass1')?['value'])", 0],
          }],
        },
        actions: {
          Create_event_V4: {
            type: "OpenApiConnection",
            runAfter: {},
            inputs: outlookInputs("V4CalendarPostItem", {
              table: calendarExpr,
              subject: EVENT_SUBJECT,
              start: EVENT_START,
              end: EVENT_END,
              timeZone: "UTC",
              body: `Power Automate E2E idempotency practice.<br>IdempotencyKey: ${IDEMPOTENCY_KEY}<br>Pass1Created=true`,
              showAs: "free",
              responseRequested: false,
            }),
          },
          Set_EventId_created: {
            type: "SetVariable",
            runAfter: { Create_event_V4: ["Succeeded"] },
            inputs: {
              name: "EventId",
              value: "@body('Create_event_V4')?['id']",
            },
          },
        },
        else: {
          actions: {
            Set_EventId_existing: {
              type: "SetVariable",
              runAfter: {},
              inputs: {
                name: "EventId",
                value: "@first(body('Get_events_pass1')?['value'])?['id']",
              },
            },
          },
        },
      },
      Get_event_after_pass1: {
        type: "OpenApiConnection",
        runAfter: { Pass1_create_if_missing: ["Succeeded"] },
        inputs: outlookInputs("V3CalendarGetItem", {
          table: calendarExpr,
          id: "@variables('EventId')",
        }),
      },
      Delay_before_pass2: {
        type: "Wait",
        runAfter: { Get_event_after_pass1: ["Succeeded"] },
        inputs: { interval: { count: 5, unit: "Second" } },
      },
      Get_events_pass2: {
        type: "OpenApiConnection",
        runAfter: { Delay_before_pass2: ["Succeeded"] },
        inputs: outlookInputs("V4CalendarGetItems", {
          table: calendarExpr,
          "$filter": filter,
          "$top": 10,
        }),
      },
      Pass2_require_exactly_one: {
        type: "If",
        runAfter: { Get_events_pass2: ["Succeeded"] },
        expression: {
          and: [{
            equals: ["@length(body('Get_events_pass2')?['value'])", 1],
          }],
        },
        actions: {
          Set_EventId_pass2: {
            type: "SetVariable",
            runAfter: {},
            inputs: {
              name: "EventId",
              value: "@first(body('Get_events_pass2')?['value'])?['id']",
            },
          },
          Update_event_pass2_evidence: {
            type: "OpenApiConnection",
            runAfter: { Set_EventId_pass2: ["Succeeded"] },
            inputs: outlookInputs("V4CalendarPatchItem", {
              table: calendarExpr,
              id: "@variables('EventId')",
              subject: EVENT_SUBJECT,
              start: EVENT_START,
              end: EVENT_END,
              timeZone: "UTC",
              body: `Power Automate E2E idempotency practice.<br>IdempotencyKey: ${IDEMPOTENCY_KEY}<br>Pass1CreatedOrReused=true<br>SecondPassValidated=true`,
              showAs: "free",
              responseRequested: false,
            }),
          },
        },
        else: {
          actions: {
            Fail_duplicate_or_missing: {
              type: "Terminate",
              runAfter: {},
              inputs: {
                runStatus: "Failed",
                runError: {
                  code: "IDEMPOTENCY_COUNT_INVALID",
                  message: "Second pass did not find exactly one event.",
                },
              },
            },
          },
        },
      },
      Get_event_after_pass2: {
        type: "OpenApiConnection",
        runAfter: { Pass2_require_exactly_one: ["Succeeded"] },
        inputs: outlookInputs("V3CalendarGetItem", {
          table: calendarExpr,
          id: "@variables('EventId')",
        }),
      },
      E2E_result: {
        type: "Compose",
        runAfter: { Get_event_after_pass2: ["Succeeded"] },
        inputs: {
          eventId: "@variables('EventId')",
          idempotencyKey: IDEMPOTENCY_KEY,
          secondPassValidated: true,
          observedSubject: "@body('Get_event_after_pass2')?['subject']",
        },
      },
    },
    outputs: {},
  };

  return {
    properties: {
      connectionReferences: {
        [CONNECTION_KEY]: {
          impersonation: {},
          runtimeSource: "embedded",
          connection: {
            name: connectionName(ref.connectionid),
            connectionReferenceLogicalName: ref.connectionreferencelogicalname,
          },
          api: { name: CONNECTION_KEY },
        },
      },
      definition,
    },
    schemaVersion: "1.0.0.0",
  };
}

function selfTest() {
  const ref = {
    connectionid: "/providers/Microsoft.PowerApps/apis/shared_office365/connections/shared-office365-test-guid",
    connectionreferencelogicalname: "reqsys_sharedoffice365_test",
  };
  const data = buildClientData(ref);
  if (data.properties.connectionReferences.shared_office365.connection.name !== "shared-office365-test-guid") {
    throw new Error("SELFTEST_CONNECTION_NAME");
  }
  const actions = data.properties.definition.actions;
  if (actions.Get_events_pass1.inputs.host.operationId !== "V4CalendarGetItems") {
    throw new Error("SELFTEST_GET_EVENTS");
  }
  if (actions.Pass2_require_exactly_one.actions.Update_event_pass2_evidence.inputs.host.operationId !== "V4CalendarPatchItem") {
    throw new Error("SELFTEST_UPDATE_EVENT");
  }
  const serialized = JSON.stringify(data);
  if (!serialized.includes(IDEMPOTENCY_KEY) || !serialized.includes("SecondPassValidated=true")) {
    throw new Error("SELFTEST_EVIDENCE_MARKERS");
  }
  console.log("PA_OUTLOOK_E2E_SELFTEST_OK");
}

async function context() {
  const tenant = (process.env.POWERPLATFORM_TENANT_ID || "").trim();
  const client = (process.env.POWERPLATFORM_APP_ID || "").trim();
  const secret = (process.env.POWERPLATFORM_CLIENT_SECRET || "").trim();
  const envUrl = (process.env.DEV_ENVIRONMENT_URL || "").trim().replace(/\/$/, "");
  if (!tenant || !client || !secret || !envUrl) throw new Error("POWERPLATFORM_CONFIGURATION_INCOMPLETE");
  const accessToken = await token(tenant, client, secret, envUrl);
  return { envUrl, accessToken, headers: dvHeaders(accessToken) };
}

async function usableOutlookRef(ctx) {
  const select = encodeURIComponent("connectionreferencelogicalname,connectionid,connectorid,displayname,statecode");
  const res = await requestJson(
    `${ctx.envUrl}/api/data/v9.2/connectionreferences?$select=${select}`,
    { headers: ctx.headers },
  );
  const refs = (res.json.value || []).filter(x => isOffice365(x) && x.connectionid && x.connectionreferencelogicalname);
  if (refs.length !== 1) throw new Error(`OUTLOOK_REFERENCE_AMBIGUOUS count=${refs.length}`);
  return refs[0];
}

async function findFlow(ctx) {
  const filter = encodeURIComponent(`name eq '${FLOW_NAME}' and category eq 5`);
  const select = encodeURIComponent("workflowid,name,statecode,statuscode,modifiedon,clientdata");
  const res = await requestJson(
    `${ctx.envUrl}/api/data/v9.2/workflows?$filter=${filter}&$select=${select}`,
    { headers: ctx.headers },
  );
  const rows = res.json.value || [];
  if (rows.length > 1) throw new Error(`FLOW_NAME_AMBIGUOUS count=${rows.length}`);
  return rows[0] || null;
}

async function readFlow(ctx, workflowId) {
  const select = encodeURIComponent("workflowid,name,statecode,statuscode,modifiedon");
  const res = await requestJson(
    `${ctx.envUrl}/api/data/v9.2/workflows(${workflowId})?$select=${select}`,
    { headers: ctx.headers },
  );
  return res.json;
}

async function createOrUpdateAndActivate(evidenceFile, correlationId) {
  const ctx = await context();
  const ref = await usableOutlookRef(ctx);
  const clientdata = JSON.stringify(buildClientData(ref));
  let flow = await findFlow(ctx);
  let created = false;

  if (!flow) {
    const payload = JSON.stringify({
      category: 5,
      name: FLOW_NAME,
      type: 1,
      description: `Governed DEV E2E practice. correlation_id=${correlationId}`,
      primaryentity: "none",
      clientdata,
    });
    const res = await requestRaw(`${ctx.envUrl}/api/data/v9.2/workflows`, {
      method: "POST",
      headers: { ...ctx.headers, "Content-Length": Buffer.byteLength(payload) },
      body: payload,
    });
    if (res.status < 200 || res.status >= 300) {
      throw new Error(`CREATE_FLOW_HTTP_${res.status} ${res.body.slice(0,600)}`);
    }
    const entity = String(res.headers["odata-entityid"] || res.headers["OData-EntityId"] || "");
    const m = entity.match(/workflows\(([0-9a-f-]{36})\)/i);
    if (!m) throw new Error("CREATE_FLOW_ID_MISSING");
    flow = { workflowid: m[1], statecode: 0 };
    created = true;
  } else {
    if (Number(flow.statecode) === 1) {
      const off = JSON.stringify({ statecode: 0 });
      const offRes = await requestRaw(`${ctx.envUrl}/api/data/v9.2/workflows(${flow.workflowid})`, {
        method: "PATCH",
        headers: { ...ctx.headers, "If-Match": "*", "Content-Length": Buffer.byteLength(off) },
        body: off,
      });
      if (offRes.status < 200 || offRes.status >= 300) throw new Error(`DEACTIVATE_BEFORE_UPDATE_HTTP_${offRes.status}`);
    }
    const patch = JSON.stringify({
      clientdata,
      description: `Governed DEV E2E practice. correlation_id=${correlationId}`,
    });
    const patchRes = await requestRaw(`${ctx.envUrl}/api/data/v9.2/workflows(${flow.workflowid})`, {
      method: "PATCH",
      headers: { ...ctx.headers, "If-Match": "*", "Content-Length": Buffer.byteLength(patch) },
      body: patch,
    });
    if (patchRes.status < 200 || patchRes.status >= 300) {
      throw new Error(`UPDATE_FLOW_HTTP_${patchRes.status} ${patchRes.body.slice(0,600)}`);
    }
  }

  const activate = JSON.stringify({ statecode: 1 });
  const actRes = await requestRaw(`${ctx.envUrl}/api/data/v9.2/workflows(${flow.workflowid})`, {
    method: "PATCH",
    headers: { ...ctx.headers, "If-Match": "*", "Content-Length": Buffer.byteLength(activate) },
    body: activate,
  });
  if (actRes.status < 200 || actRes.status >= 300) {
    throw new Error(`ACTIVATE_FLOW_HTTP_${actRes.status} ${actRes.body.slice(0,600)}`);
  }

  const readback = await readFlow(ctx, flow.workflowid);
  if (Number(readback.statecode) !== 1) throw new Error("ACTIVATION_READBACK_FAILED");

  const evidence = {
    schema: "powerautomate-outlook-idempotency-e2e/v1",
    correlation_id: correlationId,
    environment: "dev",
    flow_name: FLOW_NAME,
    workflow_id: flow.workflowid,
    created,
    activated: true,
    statecode: readback.statecode,
    idempotency_key: IDEMPOTENCY_KEY,
    event_subject: EVENT_SUBJECT,
    event_start: EVENT_START + "Z",
    event_end: EVENT_END + "Z",
    connection_reference_logical_name: ref.connectionreferencelogicalname,
    connection_id_sha256: crypto.createHash("sha256").update(String(ref.connectionid)).digest("hex"),
    secrets_exposed: false,
    production_touched: false,
  };
  fs.mkdirSync(path.dirname(path.resolve(evidenceFile)), { recursive: true });
  fs.writeFileSync(path.resolve(evidenceFile), JSON.stringify(evidence, null, 2) + "\n", "utf8");
  console.log("PA_OUTLOOK_E2E_FLOW_ACTIVE");
  console.log(`workflow_id=${flow.workflowid}`);
  console.log(`created=${created}`);
  console.log("statecode=1");
}

async function deactivate(evidenceFile, correlationId, delaySeconds = 0) {
  if (delaySeconds > 0) {
    console.log(`PA_OUTLOOK_E2E_BOUNDED_WAIT seconds=${delaySeconds}`);
    await new Promise(resolve => setTimeout(resolve, delaySeconds * 1000));
  }
  const ctx = await context();
  const flow = await findFlow(ctx);
  if (!flow) throw new Error("FLOW_NOT_FOUND_FOR_DEACTIVATION");

  const body = JSON.stringify({ statecode: 0 });
  const res = await requestRaw(`${ctx.envUrl}/api/data/v9.2/workflows(${flow.workflowid})`, {
    method: "PATCH",
    headers: { ...ctx.headers, "If-Match": "*", "Content-Length": Buffer.byteLength(body) },
    body,
  });
  if (res.status < 200 || res.status >= 300) throw new Error(`DEACTIVATE_HTTP_${res.status}`);

  const readback = await readFlow(ctx, flow.workflowid);
  if (Number(readback.statecode) !== 0) throw new Error("DEACTIVATION_READBACK_FAILED");

  const evidence = {
    schema: "powerautomate-outlook-idempotency-e2e-deactivate/v1",
    correlation_id: correlationId,
    environment: "dev",
    flow_name: FLOW_NAME,
    workflow_id: flow.workflowid,
    activated: false,
    statecode: readback.statecode,
    production_touched: false,
    secrets_exposed: false,
    bounded_wait_seconds: delaySeconds,
  };
  fs.mkdirSync(path.dirname(path.resolve(evidenceFile)), { recursive: true });
  fs.writeFileSync(path.resolve(evidenceFile), JSON.stringify(evidence, null, 2) + "\n", "utf8");
  console.log("PA_OUTLOOK_E2E_FLOW_DEACTIVATED");
  console.log(`workflow_id=${flow.workflowid}`);
  console.log("statecode=0");
}

async function main() {
  const mode = arg("--mode", "self-test");
  if (mode === "self-test") {
    selfTest();
    return;
  }
  const evidenceFile = arg("--evidence-file");
  const correlationId = arg("--correlation-id");
  if (!evidenceFile || !correlationId) throw new Error("REQUIRED_ARGUMENT_MISSING");
  if (mode === "apply") return createOrUpdateAndActivate(evidenceFile, correlationId);
  if (mode === "deactivate") {
    const delaySeconds = Number(arg("--delay-seconds", "0"));
    if (!Number.isInteger(delaySeconds) || delaySeconds < 0 || delaySeconds > 600) throw new Error("INVALID_DELAY_SECONDS");
    return deactivate(evidenceFile, correlationId, delaySeconds);
  }
  throw new Error(`UNKNOWN_MODE ${mode}`);
}

main().catch(err => {
  console.error(`PA_OUTLOOK_E2E_FAILED ${err.message}`);
  process.exitCode = 1;
});
