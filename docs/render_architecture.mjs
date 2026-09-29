// Renders docs/architecture.html to architecture.pdf and architecture.jpg with a local Chrome.
// With the argument `overview`, renders docs/architecture-overview.html to architecture-overview.png instead.
// Usage: from any folder where `npm i playwright-core` has been run:  node <repo>/docs/render_architecture.mjs [overview]
// CHROME may point at another Chrome/Chromium executable.
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const { chromium } = createRequire(pathToFileURL(join(process.cwd(), '/')))('playwright-core')

const here = dirname(fileURLToPath(import.meta.url))
const overview = process.argv[2] === 'overview'
const width = 1600
const height = overview ? 790 : 1080
const executablePath = process.env.CHROME ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const browser = await chromium.launch({ executablePath, headless: true })
const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 2 })
await page.goto(pathToFileURL(join(here, overview ? 'architecture-overview.html' : 'architecture.html')).href)
const overflow = await page.evaluate(() => ({ w: document.documentElement.scrollWidth, h: document.documentElement.scrollHeight }))
if (overflow.w > width || overflow.h > height) console.warn(`content overflows the ${width}x${height} page:`, overflow)
if (overview) {
  await page.screenshot({ path: join(here, 'architecture-overview.png'), type: 'png' })
  console.log('wrote docs/architecture-overview.png')
} else {
  await page.pdf({ path: join(here, 'architecture.pdf'), width: `${width}px`, height: `${height}px`, printBackground: true, pageRanges: '1' })
  await page.screenshot({ path: join(here, 'architecture.jpg'), type: 'jpeg', quality: 92 })
  console.log('wrote docs/architecture.pdf and docs/architecture.jpg')
}
await browser.close()
