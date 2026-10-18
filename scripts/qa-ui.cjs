const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const out = path.join(root, 'docs/qa-2026-10-17');
fs.mkdirSync(out,{recursive:true});
const datasetRoot=process.env.ATMOSIGHT_DATASET_DIR || path.join(root,'Dataset');
const checks = [];
(async () => {
 const browser = await chromium.launch({headless:true, channel:'msedge'});
 const context = await browser.newContext({viewport:{width:1440,height:1000}, acceptDownloads:true});
 const page = await context.newPage();
 page.setDefaultTimeout(60000);
 const errors=[]; page.on('pageerror', e=>errors.push(e.message));
 const check=async(name,fn)=>{const start=Date.now(); await fn(); checks.push({name,seconds:(Date.now()-start)/1000}); console.log('PASS',name); fs.writeFileSync(path.join(out,'ui-results.json'),JSON.stringify({checks,errors},null,2));};
 const nav=name=>page.getByRole('button',{name,exact:true}).click();
 const download=async(button,name)=>{const wait=page.waitForEvent('download');await page.getByRole('button',{name:button,exact:true}).click();const d=await wait;const p=path.join(out,name);await d.saveAs(p);return p;};
 const upload=async(file)=>{await nav('Upload & Analyze');await page.locator('input[type=file]').setInputFiles(path.join(root,file));await page.getByRole('heading',{name:'Confirm your import'}).waitFor();};
 const analyze=async()=>{const wait=page.waitForResponse(r=>r.url().endsWith('/analyze')&&r.request().method()==='POST',{timeout:180000});await page.getByRole('button',{name:'Analyze dataset',exact:true}).click();const r=await wait;assert.equal(r.status(),200,await r.text());const report=await r.json();await page.getByRole('heading',{name:'Row-level results'}).waitFor();return report;};
 try {
 await page.goto(process.env.ATMOSIGHT_UI_URL || 'http://127.0.0.1:5173');
 await check('Dashboard and local engine readiness',async()=>{await page.getByText('Local engine ready',{exact:true}).waitFor();await page.screenshot({path:path.join(out,'dashboard.png')});});
 await check('Manual baseline, PM pair, PM2.5, imputation fallback and SHAP',async()=>{
  await nav('Classify');assert(await page.getByRole('button',{name:'Classify observation',exact:true}).isDisabled());
  for(const [values,model] of [[[42,80,12,20,.8,35],'baseline'],[[42,80],'pm_pair'],[[42],'pm25'],[[null,80],'baseline']]){
   await page.getByRole('button',{name:'Clear',exact:true}).click();
   await page.getByLabel('Observation label').fill('QA '+model);
   for(let i=0;i<values.length;i++)if(values[i]!=null)await page.locator('input[type=number]').nth(i).fill(String(values[i]));
   const wait=page.waitForResponse(r=>r.url().endsWith('/predict')&&r.request().method()==='POST');
   await page.getByRole('button',{name:'Classify observation',exact:true}).click();
   const r=await wait;assert.equal(r.status(),200);const v=await r.json();assert.equal(v.model_id,model);assert(Math.abs(v.explanation_base+v.top_factors.reduce((s,f)=>s+f.impact,0)-v.confidence)<1e-5);
   await page.getByRole('heading',{name:'What influenced this result'}).waitFor();
  }
  await page.screenshot({path:path.join(out,'classification.png'),fullPage:true});
 });
 await check('Negative manual measurement blocked',async()=>{await page.locator('input[type=number]').first().fill('-1');assert.equal(await page.locator('input[type=number]').first().evaluate(el=>el.validity.valid),false);});
 await check('Disconnected inference shows actionable error and recovers',async()=>{
  await page.locator('input[type=number]').first().fill('42');
  await page.route('**/predict',route=>route.abort('connectionrefused'));
  await page.getByRole('button',{name:'Classify observation',exact:true}).click();await page.getByRole('alert').filter({hasText:'Cannot connect'}).waitFor();
  await page.unroute('**/predict');assert(await page.getByRole('button',{name:'Classify observation',exact:true}).isEnabled());
 });
 await check('History search, detail, export and reload persistence',async()=>{
  await nav('History');await page.getByLabel('Search history').fill('QA pm25');await page.getByRole('button',{name:'QA pm25',exact:true}).click();
  const p=await download('Export history','history.json');assert.equal(JSON.parse(fs.readFileSync(p)).length,4);
  await page.reload();await nav('History');assert.equal(await page.locator('tbody tr').count(),4);
 });
 await check('CSV preview, required interval, invalid rows and anomaly flags',async()=>{
  await upload('backend/fixtures/quality-check.csv');assert(await page.getByRole('button',{name:'Analyze dataset',exact:true}).isDisabled());
  await page.getByLabel('Map PM2.5',{exact:true}).selectOption('AQI');assert(await page.getByRole('button',{name:'Analyze dataset',exact:true}).isDisabled());await page.getByLabel('Map PM2.5',{exact:true}).selectOption('PM2.5');
  await page.getByLabel('Measurement interval').selectOption('daily');const report=await analyze();assert.equal(report.summary.total,4);assert.equal(report.summary.valid,3);assert.equal(report.summary.invalid,1);assert(report.summary.unusual>0);
  const p=await download('Export complete report','quality-report.json');assert.deepEqual(JSON.parse(fs.readFileSync(p)),report);
  const csv=await download('Export converted measurements','normalized.csv');assert.equal(fs.readFileSync(csv,'utf8').trim().split('\n').length,5);
  await page.getByRole('button',{name:'Next rows',exact:true}).isDisabled().then(v=>assert(v));
  await page.screenshot({path:path.join(out,'csv-results.png'),fullPage:true});
 });
 await check('CSV row opens canonical measurements for explanation',async()=>{const section=page.locator('section').filter({has:page.getByRole('heading',{name:'Row-level results'})});await section.locator('tbody tr').first().getByRole('button').click();assert.equal(await page.locator('input[type=number]').first().inputValue(),'42');});
 await check('Returning to upload preserves preview without another upload',async()=>{let requests=0;const listener=r=>{if(r.url().endsWith('/inspect'))requests++;};page.on('request',listener);await nav('Upload & Analyze');await page.getByRole('heading',{name:'Confirm your import'}).waitFor();await page.waitForTimeout(300);page.off('request',listener);assert.equal(requests,0);assert.equal(await page.getByLabel('Measurement interval').inputValue(),'daily');});
 await check('Mapping, conversion, duplicate-column and ppm validation',async()=>{
  await upload('backend/fixtures/flexible-import.csv');await page.getByLabel('Analyze quality only').uncheck();
  await page.getByLabel('Map PM2.5',{exact:true}).selectOption('Fine Dust');await page.getByLabel('Map PM10',{exact:true}).selectOption('Fine Dust');assert(await page.getByRole('button',{name:'Analyze dataset',exact:true}).isDisabled());
  await page.getByLabel('Map PM10',{exact:true}).selectOption('Coarse Dust');await page.getByLabel('Map CO',{exact:true}).selectOption('Carbon Monoxide');
  await page.getByLabel('Measurement interval').selectOption('daily');await page.getByLabel('Unit CO',{exact:true}).selectOption('ppm');assert(await page.getByRole('button',{name:'Analyze dataset',exact:true}).isDisabled());
  await page.getByLabel('Unit CO',{exact:true}).selectOption('ug/m3');await page.getByLabel('Unit PM2.5',{exact:true}).selectOption('mg/m3');await page.getByLabel('Reference category column').selectOption('Reference');
  const r=await analyze();assert.equal(r.summary.valid,2);assert.equal(r.summary.invalid,1);assert.equal(r.rows[0].normalized.CO,.8);assert.equal(r.rows[0].normalized['PM2.5'],42);assert.equal(r.rows[0].original['Fine Dust'],'0.042');assert.equal(r.rows[0].result.model_id,'pm_pair');
 });
 await check('Unrelated data quality-only and timestamp diagnostics',async()=>{await upload('backend/fixtures/general-quality.csv');const r=await analyze();assert(r.compatibility.quality_only);assert.equal(r.summary.valid,0);assert.equal(r.quality.duplicate_rows,1);assert.equal(r.quality.temporal.invalid_timestamps,1);assert.equal(r.rows.length,4);});
 await check('Pagination and complete report export',async()=>{await upload('backend/fixtures/pagination-check.csv');await page.getByLabel('Measurement interval').selectOption('daily');const r=await analyze();assert(r.rows.length>100);await page.getByRole('button',{name:'Next rows',exact:true}).click();await page.getByText(/Rows 101/).waitFor();await page.getByRole('button',{name:'Previous rows',exact:true}).click();const p=await download('Export complete report','pagination-report.json');assert.equal(JSON.parse(fs.readFileSync(p)).rows.length,r.rows.length);});
 await check('Oversize city_hour.csv rejected before network upload',async()=>{await page.locator('input[type=file]').setInputFiles(path.join(datasetRoot,'city_hour.csv'));await page.getByRole('alert').filter({hasText:'50 MB'}).waitFor();assert(await page.getByRole('button',{name:'Analyze dataset',exact:true}).isDisabled());});
 await check('Template download',async()=>{const p=await download('Download CSV template','template.csv');assert(fs.readFileSync(p,'utf8').startsWith('PM2.5,PM10,SO2,NO2,CO,O3'));});
 await check('Malformed CSV presents a recoverable import error',async()=>{await page.locator('input[type=file]').setInputFiles({name:'broken.csv',mimeType:'text/csv',buffer:Buffer.from('PM2.5\n"42\n')});await page.getByRole('alert').filter({hasText:'unexpected end of data'}).waitFor();assert(await page.getByRole('button',{name:'Analyze dataset',exact:true}).isDisabled());});
 await check('Model evidence and settings theme persistence',async()=>{await nav('Model Info');await page.getByText('78.1%',{exact:true}).first().waitFor();await page.screenshot({path:path.join(out,'models.png'),fullPage:true});await nav('Settings');await page.getByRole('button',{name:'Dark',exact:true}).click();await page.reload();assert(await page.locator('html').evaluate(el=>el.classList.contains('dark')));await nav('Settings');await page.getByRole('button',{name:'Light',exact:true}).click();});
 await check('Clear isolated QA history',async()=>{page.once('dialog',d=>d.accept());await page.getByRole('button',{name:'Clear local history',exact:true}).click();await nav('History');assert.equal(await page.locator('tbody tr').count(),0);});
 assert.deepEqual(errors,[]);
 }catch(e){await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});fs.writeFileSync(path.join(out,'failure.txt'),e.stack+'\n'+await page.locator('body').innerText());throw e;}
 finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
