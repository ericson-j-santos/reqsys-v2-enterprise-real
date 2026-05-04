const { spawn } = require('child_process')

const FRONTEND_URL = process.env.E2E_BASE_URL || 'http://localhost:5173'
const BACKEND_HEALTH_URL = process.env.E2E_BACKEND_HEALTH_URL || 'http://localhost:8210/health'
const CHECK_TIMEOUT_MS = Number(process.env.E2E_CHECK_TIMEOUT_MS || 60000)
const CHECK_INTERVAL_MS = Number(process.env.E2E_CHECK_INTERVAL_MS || 1500)

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms))
}

async function isFrontendReady() {
    try {
        const response = await fetch(`${FRONTEND_URL}/login`, { method: 'GET' })
        return response.ok
    } catch {
        return false
    }
}

async function isBackendReady() {
    try {
        const response = await fetch(BACKEND_HEALTH_URL, { method: 'GET' })
        if (!response.ok) return false
        const body = await response.json().catch(() => ({}))
        return body?.data?.status === 'ok' || body?.success === true
    } catch {
        return false
    }
}

async function waitUntil(checkFn, name) {
    const start = Date.now()
    while (Date.now() - start < CHECK_TIMEOUT_MS) {
        if (await checkFn()) {
            console.log(`[ok] ${name} pronto`)
            return
        }
        await sleep(CHECK_INTERVAL_MS)
    }

    throw new Error(`Timeout aguardando ${name}. Verifique o serviço e tente novamente.`)
}

async function main() {
    console.log(`[info] Frontend alvo: ${FRONTEND_URL}`)
    console.log(`[info] Backend health: ${BACKEND_HEALTH_URL}`)

    await waitUntil(isFrontendReady, 'frontend')
    await waitUntil(isBackendReady, 'backend')

    const playwrightCli = require.resolve('@playwright/test/cli')
    const args = [playwrightCli, 'test', ...process.argv.slice(2)]

    const child = spawn(process.execPath, args, {
        stdio: 'inherit',
        env: {
            ...process.env,
            E2E_BASE_URL: FRONTEND_URL,
        },
    })

    child.on('exit', (code) => {
        process.exit(code ?? 1)
    })
}

main().catch((error) => {
    console.error(`[erro] ${error.message}`)
    process.exit(1)
})
