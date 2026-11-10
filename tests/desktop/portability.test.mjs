// Behavior tests for client portability helpers and their wiring in desktop/src. No live data.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { test } from 'node:test'
const root = resolve(import.meta.dirname, '../..')
const P = await import(pathToFileURL(resolve(root,'desktop/src/portability.js')).href)
const jsx = readFileSync(resolve(root,'desktop/src/plugin.jsx'),'utf8')
const css = readFileSync(resolve(root,'desktop/src/styles.js'),'utf8')
const b64 = s => Buffer.from(s).toString('base64')
const envFor = () => { const log={clicks:[],blobs:[]}
 class B{constructor(parts,o){this.parts=parts;this.type=o.type;log.blobs.push(this)}}
 const a={style:{},click(){log.clicks.push({href:a.href,download:a.download})},remove(){}}
 return {log,env:{hasBridge:()=>true,atob:s=>Buffer.from(s,'base64').toString('binary'),Blob:B,
  URL:{createObjectURL:()=>'blob:x',revokeObjectURL:()=>{}},document:{createElement:()=>a,body:{appendChild:()=>{}}}}} }
const mk=(o={})=>{const calls=[],notes=[];const e=envFor();let scope='a'
 const saver=P.makeSaver({native:o.native,ctx:{rest:async(p,x)=>{calls.push([p,x]);if(o.onRest)o.onRest(()=>{scope='b'});return o.rest||{name:'s.pdf',content_type:'application/pdf',size:3,data_b64:b64('pdf')}}},scopeNow:()=>scope,scope:'a',notify:n=>notes.push(n),env:{...e.env,...(o.env||{})}})
 return {saver,calls,notes,log:e.log,setScope:v=>{scope=v}}}

test('native success (void, as the SDK resolves) never touches the plugin endpoint',async()=>{
 const t=mk({native:async()=>undefined});assert.equal((await t.saver('/p','n.pdf')).status,'native');assert.equal(t.calls.length,0)})
test('void result after a cancelled/failed host dialog is not treated as failure',async()=>{
 for(const r of [undefined,{saved:false,canceled:true},{saved:false}]){const t=mk({native:async()=>r});assert.equal((await t.saver('/p','n')).status,'native');assert.equal(t.calls.length,0)}})
test('thrown cancellation does not fall back',async()=>{
 const t=mk({native:async()=>{throw Object.assign(new Error('Save cancelled'),{name:'AbortError'})}});assert.equal((await t.saver('/p','n')).status,'cancelled');assert.equal(t.calls.length,0)})
test('absent helper or pre-dialog rejection falls back automatically; wording says started',async()=>{
 for(const t of [mk({native:async()=>{throw new Error('Desktop file download bridge is unavailable')}}),mk({native:undefined})]){
  const r=await t.saver('/srv/x.pdf','x.pdf');assert.equal(r.status,'fallback')
  assert.deepEqual(t.calls[0],['/download',{method:'POST',body:{path:'/srv/x.pdf'},timeoutMs:60000}])
  assert.equal(t.log.clicks[0].download,'s.pdf');assert.equal(t.log.blobs[0].type,'application/pdf')
  assert.match(t.notes[0].message,/Download started/);assert.doesNotMatch(t.notes[0].message,/saved/i)}})
test('explicit direct download works even when native helper exists',async()=>{
 const t=mk({native:async()=>undefined});assert.equal((await t.saver.direct('/p','n.pdf')).status,'fallback');assert.equal(t.calls.length,1)})
test('stale profile is rejected before and after the direct request',async()=>{
 const t=mk({native:undefined});t.setScope('b');await assert.rejects(()=>t.saver('/p','n'),/Profile changed/);assert.equal(t.calls.length,0)
 const u=mk({native:undefined,onRest:flip=>flip()});await assert.rejects(()=>u.saver('/p','n'),/Profile changed/);assert.equal(u.log.clicks.length,0)})
test('endpoint errors surface',async()=>{const t=mk({native:undefined,rest:{ok:false,error:'Not a registered file'}});await assert.rejects(()=>t.saver('/p','n'),/registered/)})
test('packet sheet, key and original material expose a Direct download action',()=>{
 assert.ok((jsx.match(/Direct download/g)||[]).length>=3)})

test('copyText uses ctx.os.writeClipboard, then sdk writer, else reports failure',async()=>{
 let got;assert.equal(await P.copyText({os:{writeClipboard:async t=>{got=t;return true}}},'hi'),true);assert.equal(got,'hi')
 let g2;assert.equal(await P.copyText({os:{writeClipboard:async()=>false}},'yo',{writeClipboardText:async t=>{g2=t}}),true);assert.equal(g2,'yo')
 assert.equal(await P.copyText({os:{}},'x',{}),false)
 assert.ok(!jsx.includes('copyText?.('),'old nonexistent ctx.os.copyText call removed')})

test('runJobScoped fences POST, each poll and the result',async()=>{
 const mkj=(flipAt)=>{let scope='a',n=0;const seq=[];return {seq,run:()=>P.runJobScoped({scopeNow:()=>scope,sleep:async()=>{},path:'/x',body:{},
  request:async(p)=>{seq.push(p);if(++n===flipAt)scope='b';return p==='/x'?{job:'j1'}:n<4?{status:'running'}:{status:'done',result:{ok:true}}}})}}
 assert.deepEqual(await mkj(0).run(),{ok:true})
 const a=mkj(1);await assert.rejects(a.run,/Profile changed/);assert.deepEqual(a.seq,['/x'])
 const b=mkj(2);await assert.rejects(b.run,/Profile changed/);assert.equal(b.seq.length,2)
 await assert.rejects(mkj(4).run,/Profile changed/)
 await assert.rejects(()=>P.runJobScoped({scopeNow:(()=>{let i=0;return()=>i++?'b':'a'})(),path:'/x',request:async()=>{throw new Error('should not post')}}),/Profile changed/)})

test('upload preparation cannot retarget an old child into a newly selected profile',async()=>{
 let posted=false
 await assert.rejects(()=>P.runJobScoped({scopeNow:()=>'new-profile',expectedScope:'original-profile',
  path:'/intake64',body:{child_id:'nova'},request:async()=>{posted=true;return {ok:true}}}),/Profile changed/)
 assert.equal(posted,false)
})

test('clientTimezone reads Intl with UTC fallback; existing family zone wins',()=>{
 const intl=z=>({DateTimeFormat:function(a,o){if(o)return;return {resolvedOptions:()=>({timeZone:z})}}})
 assert.equal(P.clientTimezone(intl('Asia/Tokyo')),'Asia/Tokyo')
 assert.equal(P.clientTimezone({DateTimeFormat(){throw new Error('x')}}),'UTC');assert.equal(P.clientTimezone(null),'UTC')
 assert.equal(P.pickTimezone({hasChildren:false,familyZone:'America/Chicago',client:'Asia/Tokyo'}),'Asia/Tokyo')
 assert.equal(P.pickTimezone({hasChildren:true,familyZone:'America/Chicago',client:'Asia/Tokyo'}),'America/Chicago')
 assert.equal(P.pickTimezone({existing:'Europe/Paris',hasChildren:true,familyZone:'America/Chicago',client:'Asia/Tokyo'}),'Europe/Paris')
 assert.equal(P.validTimezone('America/Chicago'),true);assert.equal(P.validTimezone('Not/AZone'),false);assert.equal(P.validTimezone('bad zone'),false)
 assert.ok(!jsx.includes("timezone:'America/Chicago'"))})

class FakeReader{readAsDataURL(f){this.result='data:;base64,'+Buffer.from(f.bytes||'x').toString('base64');queueMicrotask(()=>this.onload())}}
const file=(name,type,size,bytes='orig')=>({name,type,size,bytes})
const codec=(w,h,sizeFor)=>({decode:async()=>({width:w,height:h,close(){}}),encode:async(b,cw,ch,mime,q)=>({size:sizeFor(cw,ch,mime,q),type:mime,bytes:`enc:${cw}x${ch}:${mime}`})})
const env=c=>({codec:c,FileReader:FakeReader})
test('small image passes through unchanged',async()=>{
 const r=await P.prepareUpload(file('a.jpg','image/jpeg',1000),{env:env(codec(800,600,()=>1))});assert.equal(r.resized,false);assert.equal(r.filename,'a.jpg')})
test('oversized JPEG is downscaled to the edge cap and byte target',async()=>{
 const r=await P.prepareUpload(file('big.JPG','image/jpeg',9e6),{env:env(codec(4000,3000,(w,h,m,q)=>w*h*q*0.3))})
 assert.equal(r.resized,true);assert.ok(Math.max(r.width,r.height)<=P.IMAGE_MAX_EDGE);assert.equal(r.mime,'image/jpeg');assert.match(r.filename,/\.jpg$/)
 assert.match(Buffer.from(r.data_b64,'base64').toString(),/^enc:/)})
test('large PNG that stays too big becomes JPEG with matching name and mime',async()=>{
 const r=await P.prepareUpload(file('scan.png','image/png',8e6),{env:env(codec(3000,3000,(w,h,m)=>m==='image/png'?9e6:1e6))})
 assert.equal(r.mime,'image/jpeg');assert.equal(r.filename,'scan.jpg')})
test('hopelessly large image and undecodable/unsupported input are rejected honestly',async()=>{
 await assert.rejects(()=>P.prepareUpload(file('x.jpg','image/jpeg',9e6),{env:env(codec(4000,4000,()=>9e9))}),/still too large/)
 await assert.rejects(()=>P.prepareUpload(file('x.jpg','image/jpeg',9e6),{env:{FileReader:FakeReader,codec:{decode:async()=>{throw new Error('bad')}}}}),/could not be read/)
 await assert.rejects(()=>P.prepareUpload(file('x.heic','image/heic',9e6),{env:env(codec(1,1,()=>1))}),/HEIC/)
 await assert.rejects(()=>P.prepareUpload(file('x.png','image/gif',9e6),{env:env(codec(1,1,()=>1))}),/JPG, PNG or WEBP/)})
test('documents are untouched; 15 MiB cap preserved',async()=>{
 const r=await P.prepareUpload(file('n.pdf','application/pdf',5e6,'%PDF'),{teacher:true,env:env(null)});assert.equal(r.resized,false);assert.equal(r.filename,'n.pdf')
 await assert.rejects(()=>P.prepareUpload(file('n.pdf','application/pdf',16*1024*1024),{teacher:true,env:env(null)}),/15 MB/)})

const PNG='data:image/png;base64,eA=='
const printEnv=(o={})=>{const log={printed:0,removed:0,appended:[],old:0}
 const win={print(){log.printed++},focus(){},addEventListener(n,f){log.after=f},document:{images:[{decode:async()=>{}}]}}
 const frame={style:{},setAttribute(){},remove(){log.removed++},contentWindow:o.noPrint?{}:win}
 const doc={createElement:()=>frame,getElementById:()=>({remove(){log.old++}}),body:{appendChild(f){log.appended.push(f);queueMicrotask(()=>f.onload())}}}
 return {log,frame,env:{document:doc}}}
test('print loads every page at print width, prints only the sheet frame, and cleans up',async()=>{
 const t=printEnv(),asked=[]
 const r=await P.printPages({load:async n=>{asked.push(n);return {image:PNG,page:n,pages:3}},scopeNow:()=>'a',scope:'a',title:'2026-11-09 <nova>',env:t.env})
 assert.deepEqual(asked,[0,1,2]);assert.deepEqual(r,{status:'printing',pages:3})
 assert.equal(t.log.printed,1);assert.equal(t.log.old,1,'a leftover frame is removed first')
 assert.equal((t.frame.srcdoc.match(/<img /g)||[]).length,3);assert.ok(!t.frame.srcdoc.includes('<nova>'))
 t.log.after();assert.equal(t.log.removed,1)
 assert.ok(P.PRINT_WIDTH>=1500&&jsx.includes('width=${PRINT_WIDTH}'))})
test('print fails closed: no page image, unsafe image, no print door, or a changed profile',async()=>{
 const base={scopeNow:()=>'a',scope:'a'}
 await assert.rejects(P.printPages({...base,load:async()=>({image:null,pages:0,unavailable:true}),env:printEnv().env}),/Save sheet/)
 await assert.rejects(P.printPages({...base,load:async()=>({image:'data:image/png;base64,eA=="><script>x</script>',pages:1}),env:printEnv().env}),/Save sheet/)
 const np=printEnv({noPrint:true});await assert.rejects(P.printPages({...base,load:async()=>({image:PNG,pages:1}),env:np.env}),/Save sheet/);assert.equal(np.log.removed,1)
 let scope='a';const t=printEnv()
 await assert.rejects(P.printPages({load:async()=>{scope='b';return {image:PNG,pages:1}},scopeNow:()=>scope,scope:'a',env:t.env}),/Profile changed/)
 assert.equal(t.log.appended.length,0)})
test('Today, the rate desk, History and chat cards all offer Print',()=>{
 assert.ok((jsx.match(/<PrintButton /g)||[]).length>=4)})

test('touch targets are at least 44px and upload/jobs use the prepared helpers',()=>{
 assert.match(css,/\.hc-rating\{[^}]*min-height:44px/);assert.match(css,/\.hc-rating\{[^}]*min-width:44px/)
 assert.ok(jsx.includes('prepareUpload(file')&&jsx.includes('runJobScoped'))})
