const { chromium }=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
(async()=>{
  const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  const page=await browser.newPage({acceptDownloads:true,viewport:{width:1450,height:900}});
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  try{
    await page.goto(process.env.STUDIO_URL||'http://127.0.0.1:8765/web/studio.html',{waitUntil:'load'});
    await page.locator('#summary').getByText('3 rooms').waitFor({timeout:12000});
    await fs.mkdir('artifacts/studio',{recursive:true});
    await page.screenshot({path:'artifacts/studio/studio-premium-initial.png',fullPage:true});
    await page.locator('#zoom-in').click();
    assert.match(await page.locator('#zoom-label').innerText(),/115%/);
    await page.locator('#zoom-fit').click();
    assert.match(await page.locator('#zoom-label').innerText(),/100%/);
    await page.locator('[data-mode=wall]').click();
    assert.match(await page.locator('#mode-label').innerText(),/画墙模式/);
    await page.keyboard.press('v');
    await page.locator('#add-room').click();
    assert.match(await page.locator('#summary').innerText(),/4 rooms/);
    // Create a non-hard-coded room connection, then put a window on it.
    page.once('dialog',d=>d.accept('OUTSIDE'));
    await page.locator('#add-wall').click();
    assert.match(await page.locator('#summary').innerText(),/6 walls/);
    await page.locator('#add-window').click();
    assert.match(await page.locator('#mode-label').innerText(),/放置窗户/);
    const clickPoint=await page.evaluate(()=>{
      const layout=window.AirTrajectoryStudio.getLayout();
      const w=layout.walls[layout.walls.length-1];
      const svg=document.querySelector('#plan');
      const p=svg.createSVGPoint();
      p.x=(w.x1+w.x2)/2;p.y=(w.y1+w.y2)/2;
      const client=p.matrixTransform(svg.getScreenCTM());
      return {x:client.x,y:client.y};
    });
    await page.mouse.click(clickPoint.x,clickPoint.y);
    assert.match(await page.locator('#summary').innerText(),/6 openings/);
    assert.match(await page.locator('#report').innerText(),/基本检查通过/);
    await page.screenshot({path:'artifacts/studio/studio-premium-edited.png',fullPage:true});
    const selected=await page.locator('#selected-title').innerText();
    assert.match(selected,/opening/i);
    // Persist current canonical contract and load it in a new browser session.
    const downloadPromise=page.waitForEvent('download');
    await page.locator('#export').click();
    const download=await downloadPromise;
    const file=await download.path();
    const payload=JSON.parse(await fs.readFile(file,'utf8'));
    const dest=path.resolve('artifacts/studio/edited-layout.json');
    await fs.mkdir(path.dirname(dest),{recursive:true});
    await fs.writeFile(dest,JSON.stringify(payload,null,2)+'\n');
    assert.equal(payload.rooms.length,4);
    assert.equal(payload.walls.length,6);
    assert.equal(payload.openings.length,6);
    assert.equal(payload.source_kind,'imported-floorplan');
    const window=payload.openings[payload.openings.length-1];
    assert.ok(payload.walls.some(w=>w.id===window.wall_id));
    const other=await browser.newPage({viewport:{width:1450,height:900}});
    await other.goto(process.env.STUDIO_URL||'http://127.0.0.1:8765/web/studio.html');
    await other.locator('#file').setInputFiles({name:'edited-layout.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(payload))});
    assert.match(await other.locator('#summary').innerText(),/4 rooms · 6 walls · 6 openings/);
    assert.match(await other.locator('#report').innerText(),/基本检查通过/);
    await other.close();
    assert.deepEqual(errors,[]);
    console.log('PASS Studio browser E2E: edit dynamic 4-room topology, add wall/window, export, import, validation');
  }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
