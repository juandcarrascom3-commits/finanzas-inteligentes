import puppeteer from 'puppeteer-core';
import path from 'path';
import fs from 'fs';

const ARTIFACT_DIR = 'C:/Users/juand/.gemini/antigravity/brain/d06431b5-0c18-4a09-913c-c11fd4b9e935';
const EDGE_PATH = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';

async function run() {
  if (!fs.existsSync(ARTIFACT_DIR)) {
    fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  }

  console.log('Launching Edge headless browser...');
  const browser = await puppeteer.launch({
    executablePath: EDGE_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1200, deviceScaleFactor: 2 });
  await page.goto('http://127.0.0.1:3000/', { waitUntil: 'networkidle0' });
  await new Promise(r => setTimeout(r, 1500));

  // 1. Full Page Desktop
  const fullDesktopPath = path.join(ARTIFACT_DIR, 'dashboard_full_desktop.png');
  await page.screenshot({ path: fullDesktopPath, fullPage: true });
  console.log('Saved full desktop screenshot:', fullDesktopPath);

  // Helper to click tab by text
  const clickTab = async (label) => {
    const buttons = await page.$$('button');
    for (const btn of buttons) {
      const text = await page.evaluate(el => el.textContent, btn);
      if (text && text.includes(label)) {
        await btn.click();
        await new Promise(r => setTimeout(r, 800));
        return;
      }
    }
  };

  // Helper to capture focused bottom section
  const captureBottom = async (filename) => {
    // Scroll down to the bottom section
    await page.evaluate(() => {
      window.scrollTo(0, 650);
    });
    await new Promise(r => setTimeout(r, 600));
    const dest = path.join(ARTIFACT_DIR, filename);
    await page.screenshot({ path: dest, fullPage: false });
    console.log('Saved:', filename);
  };

  // 2. Panorama Tab
  await clickTab('Panorama');
  await captureBottom('focus_tab_panorama.png');

  // 3. Lista de Activos Tab
  await clickTab('Lista de Activos');
  await captureBottom('focus_tab_assets.png');

  // 4. Tesis de Inversión (NVDA - Unlocked)
  await clickTab('Tesis de Inversión');
  await captureBottom('focus_tab_thesis.png');

  // Switch ticker to AAPL to show BLOCKED Guardrail
  await page.evaluate(() => {
    const selects = document.querySelectorAll('select');
    for (const sel of selects) {
      if (sel.value && (sel.value === 'NVDA' || sel.value.includes('NVDA'))) {
        sel.value = 'AAPL';
        sel.dispatchEvent(new Event('change', { bubbles: true }));
        break;
      }
    }
  });
  await new Promise(r => setTimeout(r, 1000));
  await captureBottom('focus_tab_thesis_blocked.png');

  // 5. REST API Ingestion Tab
  await clickTab('REST API Ingestión');
  await captureBottom('focus_tab_ingestion.png');

  // 6. Informe Estratégico Tab
  await clickTab('Informe Estratégico');
  await captureBottom('focus_tab_report.png');

  await browser.close();
  console.log('All detailed screenshots captured!');
}

run().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
