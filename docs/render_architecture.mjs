// Renders docs/architecture.html to architecture.pdf and architecture.jpg with a local Chrome.
// Usage: from any folder where `npm i playwright-core` has been run:  node <repo>/docs/render_architecture.mjs
// CHROME may point at another Chrome/Chromium executable.
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const { chromium } = createRequire(pathToFileURL(join(process.cwd(), '/')))('playwright-core')

const here = dirname(fileURLToPath(import.meta.url))
const executablePath = process.env.CHROME ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const browser = await chromium.launch({ executablePath, headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 1080 }, deviceScaleFactor: 2 })
await page.goto(pathToFileURL(join(here, 'architecture.html')).href)
const overflow = await page.evaluate(() => ({ w: document.documentElement.scrollWidth, h: document.documentElement.scrollHeight }))
if (overflow.w > 1600 || overflow.h > 1080) console.warn('content overflows the 1600x1080 page:', overflow)
await page.pdf({ path: join(here, 'architecture.pdf'), width: '1600px', height: '1080px', printBackground: true, pageRanges: '1' })
await page.screenshot({ path: join(here, 'architecture.jpg'), type: 'jpeg', quality: 92 })
await browser.close()
console.log('wrote docs/architecture.pdf and docs/architecture.jpg')
