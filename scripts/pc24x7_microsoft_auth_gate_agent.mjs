#!/usr/bin/env node
import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const DEFAULT_REPO = 'ericson-j-santos/reqsys-v2-enterprise-real'
const DEFAULT_BRANCH = 'fix/planner-teams-connection-refs-dev-20260916'
const DEFAULT_WORKFLOW = 'Planner Teams DEV Connection Reference Repair'
const DEFAULT_ARTIFACT_PREFIX = 'planner-teams-connection-reference-device-login-'

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function env(name, fallback = '') {
  return String(process.env[name] || fallback).trim()
}

function envNumber(name, fallback) {
  const parsed = Number(process.env[name])
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

function envBoolean(name, fallback = false) {
  const raw = env(name)
  if (!raw) return fallback
  return ['1', 'true', 'yes', 'on'].includes(raw.toLowerCase())
}

export function validateVerificationUri(raw) {
  const value = String(raw || '').trim()
  if (!value) throw new Error('verification_uri_ausente')
  const url = new URL(value)
  if (url.protocol !== 'https:') throw new Error('verification_uri_protocolo_invalido')
  const host = url.hostname.toLowerCase()
  const allowed =
    host === 'microsoft.com' ||
    host === 'www.microsoft.com' ||
    host.endsWith('.microsoft.com') ||
    host === 'login.microsoftonline.com'
  if (!allowed) throw new Error(`verification_uri_host_nao_permitido:${host}`)
  return url.toString()
}

export function validateUserCode(raw) {
  const value = String(raw || '').trim().toUpperCase()
  if (!/^[A-Z0-9-]{6,16}$/.test(value)) throw new Error('user_code_formato_invalido')
  return value
}

export function buildDeviceLoginUrl(verificationUri, userCode) {
  const url = new URL(validateVerificationUri(verificationUri))
  url.searchParams.set('otc', validateUserCode(userCode))
  return url.toString()
}

export function selectGateArtifact(artifacts, prefix = DEFAULT_ARTIFACT_PREFIX) {
  const matches = (Array.isArray(artifacts) ? artifacts : [])
    .filter((item) => String(item?.name || '').startsWith(prefix) && !item?.expired)
    .sort((a, b) => Date.parse(b?.created_at || 0) - Date.parse(a?.created_at || 0))
  return matches[0] || null
}

export function shouldRerun(run, gate, rerunsUsed, maxReruns) {
  return Boolean(
    run?.status === 'completed' &&
      run?.conclusion === 'failure' &&
      gate?.required === true &&
      rerunsUsed < maxReruns,
  )
}

export function sanitizedGateSummary(gate, runId, artifactName) {
  return {
    run_id: Number(runId),
    artifact: String(artifactName || ''),
    required: gate?.required === true,
    status: String(gate?.status || ''),
    verification_host: gate?.verification_uri
      ? new URL(validateVerificationUri(gate.verification_uri)).hostname
      : null,
    user_code_present: Boolean(gate?.user_code),
    generated_at: gate?.generated_at || null,
    expires_in_seconds: Number(gate?.expires_in_seconds || 0) || null,
  }
}

function spawnCapture(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: options.cwd,
      env: options.env || process.env,
      shell: false,
      windowsHide: true,
    })
    let stdout = ''
    let stderr = ''
    child.stdout?.on('data', (chunk) => { stdout += chunk.toString() })
    child.stderr?.on('data', (chunk) => { stderr += chunk.toString() })
    child.on('error', reject)
    child.on('close', (code) => resolve({ code: Number(code || 0), stdout, stderr }))
  })
}

async function ghJson(args) {
  const gh = env('AUTH_GATE_GH_PATH', 'gh')
  const result = await spawnCapture(gh, args)
  if (result.code !== 0) throw new Error(`gh_falhou:${result.code}:${result.stderr.slice(0, 300)}`)
  try {
    return JSON.parse(result.stdout)
  } catch {
    throw new Error('gh_json_invalido')
  }
}

async function latestRun(repo, branch, workflowName) {
  const payload = await ghJson([
    'api',
    `repos/${repo}/actions/runs?branch=${encodeURIComponent(branch)}&per_page=30`,
  ])
  return (payload.workflow_runs || [])
    .filter((run) => run?.name === workflowName)
    .sort((a, b) => Date.parse(b?.created_at || 0) - Date.parse(a?.created_at || 0))[0] || null
}

async function listArtifacts(repo, runId) {
  const payload = await ghJson(['api', `repos/${repo}/actions/runs/${runId}/artifacts`])
  return payload.artifacts || []
}

async function downloadGate(repo, runId, artifactName, rootDir) {
  const target = path.join(rootDir, `${runId}-${artifactName}`)
  await fs.rm(target, { recursive: true, force: true })
  await fs.mkdir(target, { recursive: true })
  const gh = env('AUTH_GATE_GH_PATH', 'gh')
  const result = await spawnCapture(gh, [
    'run', 'download', String(runId), '--repo', repo,
    '--name', artifactName, '--dir', target,
  ])
  if (result.code !== 0) {
    throw new Error(`gh_download_falhou:${result.code}:${result.stderr.slice(0, 300)}`)
  }
  const entries = await fs.readdir(target, { withFileTypes: true })
  const jsonFiles = entries.filter((entry) => entry.isFile() && entry.name.endsWith('.json'))
  if (jsonFiles.length !== 1) throw new Error(`gate_json_quantidade_invalida:${jsonFiles.length}`)
  return JSON.parse(await fs.readFile(path.join(target, jsonFiles[0].name), 'utf8'))
}

async function openDeviceLogin(verificationUri, userCode) {
  if (process.platform !== 'win32') throw new Error('device_login_requer_windows')
  const completeUrl = buildDeviceLoginUrl(verificationUri, userCode)
  const result = await spawnCapture('rundll32.exe', [
    'url.dll,FileProtocolHandler',
    completeUrl,
  ])
  if (result.code !== 0) {
    throw new Error(`device_login_browser_falhou:${result.code}`)
  }
}

async function readState(statePath) {
  try {
    const value = JSON.parse(await fs.readFile(statePath, 'utf8'))
    return value && typeof value === 'object' ? value : {}
  } catch {
    return {}
  }
}

async function writeState(statePath, state) {
  await fs.mkdir(path.dirname(statePath), { recursive: true })
  await fs.writeFile(statePath, `${JSON.stringify(state, null, 2)}\n`, {
    encoding: 'utf8',
    mode: 0o600,
  })
}

async function rerunFailed(repo, runId) {
  const gh = env('AUTH_GATE_GH_PATH', 'gh')
  const result = await spawnCapture(gh, [
    'run', 'rerun', String(runId), '--repo', repo, '--failed',
  ])
  if (result.code !== 0) throw new Error(`gh_rerun_falhou:${result.code}:${result.stderr.slice(0, 300)}`)
}

async function main() {
  if (process.platform !== 'win32') throw new Error('pc24x7_auth_gate_requer_windows')
  const repo = env('AUTH_GATE_REPO', DEFAULT_REPO)
  const branch = env('AUTH_GATE_BRANCH', DEFAULT_BRANCH)
  const workflow = env('AUTH_GATE_WORKFLOW', DEFAULT_WORKFLOW)
  const artifactPrefix = env('AUTH_GATE_ARTIFACT_PREFIX', DEFAULT_ARTIFACT_PREFIX)
  const pollSeconds = envNumber('AUTH_GATE_POLL_SECONDS', 8)
  const timeoutSeconds = envNumber('AUTH_GATE_TIMEOUT_SECONDS', 1800)
  const maxReruns = envNumber('AUTH_GATE_MAX_RERUNS', 1)
  const autoRerun = envBoolean('AUTH_GATE_AUTO_RERUN_FAILED', true)
  const base = env('LOCALAPPDATA', path.join(os.homedir(), 'AppData', 'Local'))
  const root = env('AUTH_GATE_HOME', path.join(base, 'ReqSys', 'MicrosoftAuthGate'))
  const statePath = path.join(root, 'state.json')
  const artifactsDir = path.join(root, 'artifacts')
  const deadline = Date.now() + timeoutSeconds * 1000
  const state = await readState(statePath)
  state.handled_artifacts ||= {}
  state.reruns ||= {}

  while (Date.now() < deadline) {
    const run = await latestRun(repo, branch, workflow)
    if (!run) {
      await sleep(pollSeconds * 1000)
      continue
    }

    const artifacts = await listArtifacts(repo, run.id)
    const artifact = selectGateArtifact(artifacts, artifactPrefix)
    let gate = null
    if (artifact) {
      gate = await downloadGate(repo, run.id, artifact.name, artifactsDir)
      const key = `${run.id}:${artifact.id}`
      if (gate?.required === true && !state.handled_artifacts[key]) {
        console.log(JSON.stringify({
          event: 'auth_gate_detected',
          ...sanitizedGateSummary(gate, run.id, artifact.name),
        }))
        await openDeviceLogin(gate.verification_uri, gate.user_code)
        state.handled_artifacts[key] = {
          handled_at: new Date().toISOString(),
          run_attempt: run.run_attempt,
        }
        await writeState(statePath, state)
        console.log(JSON.stringify({
          event: 'device_code_opened',
          run_id: run.id,
          human_action: 'somente_se_microsoft_exigir_conta_mfa_ou_consentimento',
        }))
      }
    }

    if (run.status === 'completed') {
      if (run.conclusion === 'success') {
        console.log(JSON.stringify({
          event: 'auth_gate_resolved',
          run_id: run.id,
          conclusion: run.conclusion,
        }))
        return
      }
      const used = Number(state.reruns[run.id] || 0)
      if (autoRerun && shouldRerun(run, gate, used, maxReruns)) {
        await rerunFailed(repo, run.id)
        state.reruns[run.id] = used + 1
        await writeState(statePath, state)
        console.log(JSON.stringify({
          event: 'workflow_rerun_requested',
          run_id: run.id,
          rerun_number: used + 1,
        }))
        await sleep(5000)
        continue
      }
      throw new Error(`workflow_terminal_sem_sucesso:${run.conclusion || 'unknown'}`)
    }

    await sleep(pollSeconds * 1000)
  }
  throw new Error('auth_gate_timeout')
}

const __filename = fileURLToPath(import.meta.url)
if (process.argv[1] && path.resolve(process.argv[1]) === __filename) {
  main().catch((error) => {
    console.error(JSON.stringify({
      event: 'auth_gate_failed',
      error: String(error?.message || error).slice(0, 500),
    }))
    process.exitCode = 1
  })
}
