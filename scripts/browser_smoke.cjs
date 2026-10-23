// Optional real-browser audit. Dependencies live in an ignored cache, not site assets.
// npm ci && npm run test:browser (or use the ignored cache installed in this session).
const path = require('node:path');
const fs = require('node:fs');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const cachedModules = path.join(root, '.cache/browser-tools/node_modules');
const modules = process.env.GEMS_BROWSER_NODE_MODULES || (fs.existsSync(cachedModules) ? cachedModules : path.join(root, 'node_modules'));
const { chromium: playwright } = require(path.join(modules, 'playwright-core'));
const { pathToFileURL } = require('node:url');
let base = process.env.GEMS_PREVIEW_URL || 'http://127.0.0.1:8000';
let projectBase = process.env.GEMS_PROJECT_URL || null;

(async () => {
  const { default: chromium } = await import(pathToFileURL(path.join(modules, '@sparticuz/chromium/build/index.js')).href);
  // Serverless Chromium bundles the NSS/NSPR libraries missing in this minimal
  // Debian sandbox. Extract those packaged runtime libraries, not an external
  // browser download or a system modification.
  const runtime = path.join(root, '.cache/browser-runtime');
  fs.mkdirSync(runtime, {recursive: true});
  if (!fs.existsSync(path.join(runtime, 'lib/libnspr4.so'))) {
    const archive = path.join(runtime, 'al2023.tar');
    fs.writeFileSync(archive, require('node:zlib').brotliDecompressSync(fs.readFileSync(path.join(modules, '@sparticuz/chromium/bin/al2023.tar.br'))));
    require('node:child_process').execFileSync('tar', ['-xf', archive, '-C', runtime]);
  }
  const browser = await playwright.launch({args: chromium.args.filter(arg => arg !== '--single-process'), executablePath: await chromium.executablePath(), headless: true,
    env: {...process.env, LD_LIBRARY_PATH: path.join(runtime, 'lib') + (process.env.LD_LIBRARY_PATH ? ':' + process.env.LD_LIBRARY_PATH : '')}});
  const pages = ['index.html', 'executive-summary.html', 'science.html', 'validation.html', 'registry.html', 'sources.html', 'verification.html'];
  const errors = [];
  const checks = [];
  const output = path.join(root, '.cache/browser-audit');
  fs.mkdirSync(output, {recursive: true});
  let server;
  if (process.env.GEMS_START_SERVER === '1') {
    const http = require('node:http');
    const docs = path.join(root, 'docs');
    const types = {'.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.tif': 'image/tiff', '.zip': 'application/zip'};
    server = http.createServer((req, res) => {
      try {
        const name = decodeURIComponent(new URL(req.url, 'http://local.test').pathname);
        let file;
        if (name.startsWith('/_project/')) {
          const relative = name.slice('/_project/'.length);
          const roots = new Set(['index.html', 'executive-summary.html', 'research.html', 'sources.html']);
          if (roots.has(relative)) file = path.join(root, relative);
          else if (relative.startsWith('docs/')) {
            const candidate = path.resolve(root, relative);
            if (candidate.startsWith(docs + path.sep)) file = candidate;
          }
        } else {
          const candidate = path.resolve(docs, '.' + (name === '/' ? '/index.html' : name));
          if (candidate.startsWith(docs + path.sep)) file = candidate;
        }
        if (!file || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
          res.writeHead(404); res.end('Not found'); return;
        }
        res.writeHead(200, {'Content-Type': types[path.extname(file)] || 'application/octet-stream'});
        fs.createReadStream(file).on('error', () => res.destroy()).pipe(res);
      } catch { res.writeHead(400); res.end('Bad request'); }
    });
    await new Promise((resolve, reject) => {server.once('error', reject); server.listen(0, '0.0.0.0', resolve);});
    base = `http://127.0.0.1:${server.address().port}`;
    projectBase = `${base}/_project`;
  }
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1100}, acceptDownloads: true});
    const page = await context.newPage();
    page.on('pageerror', e => errors.push(e.message));
    for (const file of pages) {
      const response = await page.goto(`${base}/${file}`, {waitUntil: 'networkidle'});
      assert.equal(response.status(), 200, file);
      const horizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
      assert.equal(horizontalOverflow, false, `desktop horizontal overflow: ${file}`);
      const h1 = await page.locator('main h1').first().innerText();
      assert.ok(h1.trim().length > 0, `heading: ${file}`);
      checks.push({page: file, viewport: 'desktop', status: response.status(), no_horizontal_overflow: true});
    }
    await page.goto(`${base}/index.html`, {waitUntil: 'networkidle'});
    await page.screenshot({path: path.join(output, 'desktop.png'), fullPage: true});
    const card = JSON.parse(fs.readFileSync(path.join(root, 'docs/evidence/run_card.json')));
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.locator('a[download]').first().click()
    ]);
    assert.equal(download.suggestedFilename(), card.submission_file);
    const downloaded = path.join(output, download.suggestedFilename());
    await download.saveAs(downloaded);
    const hash = crypto.createHash('sha256').update(fs.readFileSync(downloaded)).digest('hex');
    assert.equal(hash, card.raster_sha256, 'actual browser download SHA-256');
    checks.push({actual_tiff_download_verified: true, raster_sha256: hash});
    await page.goto(`${base}/registry.html`, {waitUntil: 'networkidle'});
    await page.getByLabel('Find a repository').fill('GEMSDOE32');
    assert.equal(await page.locator('[data-search-row]:visible').count(), 1);
    await page.getByLabel('Find a repository').fill('definitely-not-a-project');
    assert.equal(await page.locator('[data-search-row]:visible').count(), 0);
    checks.push({registry_search_verified: true});
    if (projectBase) {
      for (const [alias, target] of [['index.html', 'index.html'], ['executive-summary.html', 'executive-summary.html'], ['research.html', 'science.html'], ['sources.html', 'sources.html']]) {
        await page.goto(`${projectBase}/${alias}`, {waitUntil: 'networkidle'});
        await page.waitForURL(`**/docs/${target}`, {waitUntil: 'networkidle'});
        assert.equal(await page.locator('main h1').count(), 1);
        checks.push({compatibility_entrypoint: alias, redirects_to_current_page: `docs/${target}`});
      }
    }
    await page.goto(`${base}/executive-summary.html`, {waitUntil: 'networkidle'});
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await page.getByRole('button', {name: 'Copy note', exact: true}).click();
    await page.waitForFunction(() => document.querySelector('#copy-feedback').textContent.startsWith('Copied.'));
    assert.equal(await page.evaluate(() => navigator.clipboard.readText()), card.submission_note);
    await page.evaluate(() => Object.defineProperty(navigator, 'clipboard', {value: undefined, configurable: true}));
    await page.getByRole('button', {name: 'Copy name', exact: true}).click();
    await page.waitForFunction(() => document.querySelector('#copy-feedback').textContent.includes('remains selectable'));
    checks.push({clipboard_copy_and_unavailable_fallback_verified: true});
    for (const width of [320, 390, 768]) {
      await page.setViewportSize({width, height: 844});
      for (const file of pages) {
        await page.goto(`${base}/${file}`, {waitUntil: 'networkidle'});
        const horizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
        if (horizontalOverflow) {
          const diagnostics = await page.evaluate(() => [...document.querySelectorAll('main *')].filter(el => el.scrollWidth > el.clientWidth + 2).slice(0, 35).map(el => ({tag: el.tagName, class: el.className, width: el.clientWidth, scroll: el.scrollWidth, text: el.textContent.slice(0, 80)})));
          console.error(JSON.stringify({file, width, diagnostics}, null, 2));
        }
        assert.equal(horizontalOverflow, false, `${width}px horizontal overflow: ${file}`);
        assert.equal(await page.locator('main h1').count(), 1);
        checks.push({page: file, viewport: `${width}x844`, no_horizontal_overflow: true});
      }
    }
    await page.setViewportSize({width: 390, height: 844});
    await page.goto(`${base}/index.html`, {waitUntil: 'networkidle'});
    await page.screenshot({path: path.join(output, 'mobile.png'), fullPage: true});
    await page.route('**/data/feed.json', route => route.abort('failed'));
    await page.goto(`${base}/sources.html`, {waitUntil: 'networkidle'});
    await page.waitForFunction(() => [...document.querySelectorAll('[data-feed-state]')].every(el => el.textContent.includes('unavailable')));
    checks.push({missing_feed_fails_honestly_to_dated_snapshot: true});
    const nojs = await browser.newContext({javaScriptEnabled: false, viewport: {width: 390, height: 844}});
    const staticPage = await nojs.newPage();
    await staticPage.goto(`${base}/executive-summary.html`);
    assert.greaterThanOrEqual ? assert.greaterThanOrEqual(await staticPage.locator(`a[download][href$="${card.submission_file}"]`).count(), 1) : assert.ok(await staticPage.locator(`a[download][href$="${card.submission_file}"]`).count() >= 1);
    const expectedPhrase = card.safe_to_submit ? 'SAFE TO DOWNLOAD / SUBMIT' : 'DO NOT SUBMIT';
    assert.ok((await staticPage.locator('main').innerText()).includes(expectedPhrase));
    await nojs.close();
    checks.push({download_and_decision_work_without_javascript: true});
    assert.equal(errors.length, 0, errors.join('\n'));
    const result = {passed: true, generated_utc: new Date().toISOString(), browser_version: browser.version(), checks, browser_errors: errors, scope: 'Served Pages, actual browser TIFF download hash, 4 compatibility entry points, 4 viewport widths, clipboard success/failure, source-feed failure, no-JavaScript fallback and registry search; not organizer upload acceptance.'};
    fs.writeFileSync(path.join(root, 'docs/evidence/browser_validation.json'), JSON.stringify(result, null, 2) + '\n');
    console.log(JSON.stringify(result, null, 2));
  } finally {
    await browser.close();
    if (server) await new Promise(resolve => server.close(resolve));
  }
})().catch(e => {
  fs.writeFileSync(path.join(root, 'docs/evidence/browser_validation.json'), JSON.stringify({passed: false, generated_utc: new Date().toISOString(), error: e.message, scope: 'Browser software audit; no scientific experiment or slot.'}, null, 2) + '\n');
  console.error(e); process.exit(1);
});
