import { chromium } from 'playwright';
import fs from 'fs';

async function run() {
  console.log('--- STARTING PLAYWRIGHT REAL BROWSER REFRESH PERSISTENCE TEST ---');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const edgeCsvPath = 'C:\\Users\\BHARGAV709\\Downloads\\03_edge_case_retail.csv';
  if (!fs.existsSync(edgeCsvPath)) {
    throw new Error(`Edge case CSV not found at ${edgeCsvPath}`);
  }

  // Step 1: Start with the real application
  console.log('Step 1: Navigating to http://localhost:5173/#/upload');
  await page.goto('http://localhost:5173/#/upload', { waitUntil: 'networkidle' });

  // Step 2: Upload 03_edge_case_retail.csv
  console.log('Step 2: Uploading 03_edge_case_retail.csv...');
  const fileInput = await page.waitForSelector('input[type="file"]', { state: 'attached' });
  await fileInput.setInputFiles(edgeCsvPath);

  // Step 3: Confirm 625 raw rows and 621 cleaned records
  console.log('Step 3: Waiting for analysis results...');
  await page.waitForSelector('[data-testid="analysis-results"]', { timeout: 30000 });
  
  const rawRowsText = await page.locator('[data-testid="profile-rows-count"]').textContent();
  const cleanedRowsText = await page.locator('[data-testid="cleaned-rows-count"]').textContent();
  console.log(`Reported Raw Rows: ${rawRowsText?.trim()}, Cleaned Records: ${cleanedRowsText?.trim()}`);
  
  if (!rawRowsText?.includes('625')) throw new Error(`Expected 625 raw rows, got: ${rawRowsText}`);
  if (!cleanedRowsText?.includes('621')) throw new Error(`Expected 621 cleaned records, got: ${cleanedRowsText}`);

  // Confirm splits
  const trainRows = await page.locator('[data-testid="split-train-count"]').textContent();
  const valRows = await page.locator('[data-testid="split-val-count"]').textContent();
  const testRows = await page.locator('[data-testid="split-test-count"]').textContent();
  console.log(`Splits: Train: ${trainRows?.trim()}, Val: ${valRows?.trim()}, Test: ${testRows?.trim()}`);

  // Step 4: Navigate to Evaluation & Backtesting
  console.log('Step 4: Navigating to Evaluation & Backtesting...');
  await page.click('button:has-text("Evaluation & Backtesting")');
  await page.waitForTimeout(1000);
  console.log('Current URL:', page.url());
  if (!page.url().includes('#/evaluation')) throw new Error(`Expected URL to contain #/evaluation, got ${page.url()}`);

  // Step 5: Refresh the browser (Ctrl+R / reload)
  console.log('Step 5: Refreshing browser on Evaluation & Backtesting (Ctrl+R equivalent)...');
  await page.reload({ waitUntil: 'networkidle' });

  // Step 6: Confirm that Evaluation & Backtesting remains open
  console.log('Step 6: Verifying route remains Evaluation & Backtesting after refresh...');
  console.log('URL after reload:', page.url());
  if (!page.url().includes('#/evaluation')) throw new Error(`URL did not stay on evaluation after refresh! Got: ${page.url()}`);
  const evalHeader = await page.locator('h1, h2').filter({ hasText: /Evaluation & Backtesting/i }).first();
  await evalHeader.waitFor({ state: 'visible', timeout: 10000 });
  console.log('Evaluation heading is visible.');

  // Step 7: Confirm that 03_edge_case_retail.csv remains the active dataset
  console.log('Step 7: Verifying active dataset card in Sidebar...');
  const sidebarDatasetName = await page.locator('aside').filter({ hasText: '03_edge_case_retail.csv' }).first();
  await sidebarDatasetName.waitFor({ state: 'visible', timeout: 10000 });
  console.log('Active dataset in sidebar confirmed: 03_edge_case_retail.csv');

  // Step 8: Confirm row counts in sidebar match (625 observation rows)
  const sidebarRows = await page.locator('aside').filter({ hasText: '625 observation rows' }).first();
  await sidebarRows.waitFor({ state: 'visible', timeout: 5000 });
  console.log('Sidebar confirmed 625 observation rows.');

  // Step 9: Refresh again on Upload Dataset and confirm that page and dataset persist
  console.log('Step 9: Navigating to Upload Dataset page and refreshing...');
  await page.click('button:has-text("Upload Dataset")');
  await page.waitForTimeout(1000);
  if (!page.url().includes('#/upload')) throw new Error(`Expected URL #/upload, got ${page.url()}`);
  
  // Refresh on Upload Dataset page
  console.log('Triggering page reload on #/upload...');
  await page.reload({ waitUntil: 'networkidle' });
  
  console.log('URL after reload on upload:', page.url());
  if (!page.url().includes('#/upload')) throw new Error(`URL did not stay on #/upload after refresh! Got ${page.url()}`);

  // Confirm analysis results persist on the Upload Dataset page rather than resetting to empty drop zone
  console.log('Checking that analysis-results card is visible (not empty drop-zone)...');
  await page.waitForSelector('[data-testid="analysis-results"]', { timeout: 10000 });
  const restoredRawRows = await page.locator('[data-testid="profile-rows-count"]').textContent();
  const restoredCleaned = await page.locator('[data-testid="cleaned-rows-count"]').textContent();
  console.log(`Restored on Upload Page -> Raw Rows: ${restoredRawRows?.trim()}, Cleaned: ${restoredCleaned?.trim()}`);
  if (!restoredRawRows?.includes('625')) throw new Error(`Expected 625 raw rows restored, got ${restoredRawRows}`);
  if (!restoredCleaned?.includes('621')) throw new Error(`Expected 621 cleaned records restored, got ${restoredCleaned}`);

  console.log('=== REAL BROWSER REFRESH PERSISTENCE TEST PASSED SUCCESSFULLY ===');

  // Step 10: Verify the dataset is still retrievable directly via API from MongoDB
  console.log('Step 10: Verifying backend persistence retrieval via direct API call...');
  const activeDatasetId = await page.evaluate(() => localStorage.getItem('forecastiq_active_dataset_id'));
  console.log('Active Dataset ID retrieved from localStorage:', activeDatasetId);
  if (!activeDatasetId) throw new Error('No active dataset ID in localStorage!');
  
  const apiRes = await fetch(`http://localhost:8000/api/data/${activeDatasetId}/readiness`);
  if (!apiRes.ok) throw new Error(`API readiness check failed with status: ${apiRes.status}`);
  const apiData = await apiRes.json();
  console.log(`Backend API confirmed dataset ${apiData.filename} with ${apiData.profile.rows_count} rows.`);
  if (apiData.profile.rows_count !== 625) throw new Error(`Expected 625 rows from backend API, got ${apiData.profile.rows_count}`);

  // Step 11: Switch to another dataset (e.g. reset to M5 Benchmark) and confirm previous dataset's metrics are cleared
  console.log('Step 11: Testing dataset isolation when switching / resetting...');
  // Click reset / clear in sidebar or click upload reset
  await page.click('[data-testid="upload-another-btn"]');
  await page.waitForTimeout(500);
  const dropZoneVisible = await page.locator('[data-testid="drop-zone"]').isVisible();
  console.log('Drop zone visible after reset:', dropZoneVisible);
  if (!dropZoneVisible) throw new Error('Drop zone should be visible after reset!');

  const sidebarAfterReset = await page.locator('aside').filter({ hasText: 'M5 Forecasting Accuracy' }).first();
  await sidebarAfterReset.waitFor({ state: 'visible', timeout: 5000 });
  console.log('Sidebar correctly reverted to M5 Forecasting Accuracy.');

  console.log('=== ALL 11 VERIFICATION STEPS PASSED WITH 100% SUCCESS ===');
  await browser.close();
}

run().catch((err) => {
  console.error('FAILED REAL BROWSER TEST:', err);
  process.exit(1);
});
