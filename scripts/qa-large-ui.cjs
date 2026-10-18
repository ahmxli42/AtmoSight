const { chromium } = require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),out=path.join(root,'docs/qa-2026-10-17');
fs.mkdirSync(out,{recursive:true});
const datasetRoot=process.env.ATMOSIGHT_DATASET_DIR || path.join(root,'Dataset');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(180000);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto(process.env.ATMOSIGHT_UI_URL || 'http://127.0.0.1:5173');await page.getByText('Local engine ready',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Upload & Analyze',exact:true}).click();
  const start=Date.now();await page.locator('input[type=file]').setInputFiles(path.join(datasetRoot,'station_day.csv'));
  await page.getByRole('heading',{name:'Confirm your import'}).waitFor();const inspectionSeconds=(Date.now()-start)/1000;console.log('Inspection',inspectionSeconds);
  await page.getByLabel('Measurement interval').selectOption('daily');
  const response=page.waitForResponse(r=>r.url().endsWith('/analyze')&&r.request().method()==='POST',{timeout:600000});
  const analysisStart=Date.now();await page.getByRole('button',{name:'Analyze dataset',exact:true}).click();
  const r=await response;assert.equal(r.status(),200);console.log('Response received');
  await page.getByRole('heading',{name:'Row-level results'}).waitFor({timeout:180000});console.log('Results rendered');
  const analysisSeconds=(Date.now()-analysisStart)/1000;
  await page.getByText('Rows 1–100 of 108,035',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Next rows',exact:true}).click();await page.getByText('Rows 101–200 of 108,035',{exact:true}).waitFor();
  await page.getByRole('heading',{name:'Row-level results'}).scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'full-station-results.png')});
  const download=page.waitForEvent('download',{timeout:180000});await page.getByRole('button',{name:'Export complete report',exact:true}).click();
  const d=await download;const p=path.join(out,'full-station-report.json');await d.saveAs(p);
  const report=JSON.parse(fs.readFileSync(p,'utf8'));assert.equal(report.rows.length,108035);assert.equal(report.summary.valid,99569);assert.equal(report.summary.invalid,8466);
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'large-ui-results.json'),JSON.stringify({inspectionSeconds,analysisSeconds,summary:report.summary,exportRows:report.rows.length,exportBytes:fs.statSync(p).size,errors},null,2));
  console.log(fs.readFileSync(path.join(out,'large-ui-results.json'),'utf8'));
 }catch(e){await page.screenshot({path:path.join(out,'large-failure.png')});fs.writeFileSync(path.join(out,'large-failure.txt'),e.stack+'\n'+await page.locator('body').innerText());throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
