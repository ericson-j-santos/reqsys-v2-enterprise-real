#!/usr/bin/env node
import fs from 'node:fs/promises'
import path from 'node:path'
import { chromium } from '@playwright/test'

const target = 'https://www.bcb.gov.br/estabilidadefinanceira/comunicacaodados'
const output = process.argv[2] || 'artifacts/bacen/bcb-live-links.json'

const browser = await chromium.launch({ headless: true })
try {
  const page = await browser.newPage({ locale: 'pt-BR' })
  await page.goto(target, { waitUntil: 'domcontentloaded', timeout: 60_000 })
  await page.waitForTimeout(5_000)

  const links = await page.locator('a').evaluateAll((anchors) => anchors.map((a) => ({
    text: (a.textContent || '').replace(/\s+/g, ' ').trim(),
    href: a.href || '',
  })).filter(({ text, href }) => {
    const value = `${text} ${href}`.toLocaleLowerCase('pt-BR')
    return value.includes('manual') || value.includes('catálogo') || value.includes('catalogo') || value.includes('volume') || value.includes('5.13') || value.includes('9.4')
  }))

  const bodyText = (await page.locator('body').innerText()).replace(/\s+/g, ' ').trim()
  const report = {
    schema_version: '1.0.0',
    target,
    final_url: page.url(),
    title: await page.title(),
    markers: {
      catalog_513: bodyText.toLocaleLowerCase('pt-BR').includes('5.13'),
      manual_redes_94: bodyText.toLocaleLowerCase('pt-BR').includes('9.4'),
      manual_seguranca_600: bodyText.toLocaleLowerCase('pt-BR').includes('6.00'),
    },
    links,
  }
  await fs.mkdir(path.dirname(output), { recursive: true })
  await fs.writeFile(output, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  console.log(JSON.stringify(report, null, 2))
} finally {
  await browser.close()
}
