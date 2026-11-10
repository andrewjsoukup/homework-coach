// Portability helpers: no SDK or React imports, so Node tests exercise them directly.
export const MAX_DOC_BYTES = 15 * 1024 * 1024
export const IMAGE_TARGET_BYTES = 2 * 1024 * 1024
export const IMAGE_MAX_EDGE = 2048
export const IMAGE_MIN_EDGE = 900
const IMAGE_MIMES = {jpg:'image/jpeg',jpeg:'image/jpeg',png:'image/png',webp:'image/webp'}
const EXT_FOR = {'image/jpeg':'jpg','image/png':'png','image/webp':'webp'}

export class ScopeChanged extends Error{constructor(msg){super(msg||'Profile changed. Try again in the new profile.');this.name='ScopeChanged'}}
export function guardScope(scopeNow,scope,msg){if(scopeNow()!==scope)throw new ScopeChanged(msg)}

export function clientTimezone(intl=globalThis.Intl){try{const z=intl?.DateTimeFormat?.().resolvedOptions?.().timeZone;return validTimezone(z,intl)?z:'UTC'}catch{return'UTC'}}
export function validTimezone(z,intl=globalThis.Intl){if(typeof z!=='string'||!z.trim()||/\s/.test(z))return false;try{new intl.DateTimeFormat('en-US',{timeZone:z});return true}catch{return false}}
// Keep a family's saved zone; only a family with no children yet adopts this browser's zone.
export function pickTimezone({existing,familyZone,hasChildren,client}){if(existing)return existing;if(hasChildren&&familyZone)return familyZone;return client||clientTimezone()}

export async function copyText(ctx,text,sdk={}){
 const doors=[ctx?.os?.writeClipboard&&(t=>ctx.os.writeClipboard(t)),sdk.writeClipboardText&&(async t=>{await sdk.writeClipboardText(t);return true})].filter(Boolean)
 for(const door of doors){try{if(await door(text))return true}catch{}}
 return false
}

function cancelled(x){return x?.canceled===true||x?.cancelled===true||/cancel|abort/i.test(String(x?.name||''))||/cancel|abort/i.test(String(x?.message||''))}
export function bytesFromB64(b64,atobFn=globalThis.atob){const bin=atobFn(b64);const a=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)a[i]=bin.charCodeAt(i);return a}
export function browserDownload(file,env={}){
 const doc=env.document||globalThis.document,URLo=env.URL||globalThis.URL,Blobo=env.Blob||globalThis.Blob
 if(!doc?.createElement||!URLo?.createObjectURL||!Blobo)throw new Error('This browser cannot download files here.')
 const blob=new Blobo([bytesFromB64(file.data_b64||'',env.atob)],{type:file.content_type||'application/octet-stream'})
 const url=URLo.createObjectURL(blob),a=doc.createElement('a')
 a.href=url;a.download=file.name||'download';a.rel='noopener';a.style.display='none'
 doc.body.appendChild(a);a.click();a.remove?.()
 setTimeout(()=>URLo.revokeObjectURL(url),30000)
}
// Native captured download is the default. The SDK helper resolves void and never rejects for normal
// failure or cancel (the host shows its own toast), so a resolved call is NEVER treated as failure.
// Plugin endpoint + browser Blob download runs only (a) automatically when the helper is absent or
// rejects before any dialog, or (b) when the user explicitly picks "Direct download" (save.direct).
export function makeSaver({native,ctx,scopeNow,scope,notify,env={}}){
 const stale='Profile changed. Reopen this file in the new profile.'
 async function direct(path,name){
  guardScope(scopeNow,scope,stale)
  const r=await ctx.rest('/download',{method:'POST',body:{path},timeoutMs:60000})
  if(r?.ok===false)throw new Error(r.error||'The file could not be downloaded.')
  guardScope(scopeNow,scope,stale)
  if(!r?.data_b64)throw new Error('The file could not be downloaded.')
  browserDownload({...r,name:r.name||name},env)
  notify?.({kind:'info',message:`Download started: ${r.name||name}. Check your browser's downloads.`})
  return {status:'fallback'}
 }
 async function save(path,name){
  if(typeof native==='function'){
   try{await native(path,name);return {status:'native'}}
   catch(err){if(cancelled(err))return {status:'cancelled'}}
  }
  return direct(path,name)
 }
 save.direct=direct
 save.hasNative=typeof native==='function'
 return save
}

// Poll a background job without letting a profile/connection switch leak into the new view.
export async function runJobScoped({request,scopeNow,expectedScope,path,body,onTick,sleep=ms=>new Promise(r=>setTimeout(r,ms)),maxPolls=180}){
 const scope=expectedScope??scopeNow(),fence=()=>guardScope(scopeNow,scope,'Profile changed while working. Reopen the previous profile to see the result.')
 fence()
 const start=await request(path,{method:'POST',body,timeoutMs:60000});fence()
 if(!start.job)return start
 for(let n=0;n<maxPolls;n++){
  await sleep(n<5?1000:2000);fence();onTick?.(n)
  const j=await request(`/jobs/${encodeURIComponent(start.job)}`);fence()
  if(j.status==='done'){if(j.result?.ok===false)throw new Error(j.result.error||'That did not work.');return j.result}
  if(j.status==='error')throw new Error(j.error||'That did not work.')
 }
 throw new Error('Still working after 6 minutes. Check History shortly.')
}

function extOf(name){return String(name||'').split('.').pop().toLowerCase()}
function swapExt(name,mime){const base=String(name||'upload').replace(/\.[^./\\]+$/,'');return `${base}.${EXT_FOR[mime]}`}
function readB64(file,env={}){return new Promise((res,rej)=>{const R=env.FileReader||globalThis.FileReader,r=new R();r.onload=()=>res(String(r.result).split(',',2)[1]||'');r.onerror=()=>rej(new Error('Could not read that file.'));r.readAsDataURL(file)})}
function browserCodec(env){
 const w=globalThis
 return {
  async decode(file){if(!w.createImageBitmap)throw new Error('unsupported');return w.createImageBitmap(file)},
  async encode(bmp,width,height,mime,quality){
   const canvas=w.OffscreenCanvas?new w.OffscreenCanvas(width,height):Object.assign(w.document.createElement('canvas'),{width,height})
   const g=canvas.getContext('2d');if(mime==='image/jpeg'){g.fillStyle='#fff';g.fillRect(0,0,width,height)}
   g.drawImage(bmp,0,0,width,height)
   if(canvas.convertToBlob)return canvas.convertToBlob({type:mime,quality})
   return new Promise((ok,no)=>canvas.toBlob(b=>b?ok(b):no(new Error('encode failed')),mime,quality))
  }
 }
}
// Image-only: shrink JPG/PNG/WEBP photos so base64 bodies fit through proxies. Documents pass through.
export async function prepareUpload(file,{teacher=false,env={}}={}){
 const ext=extOf(file?.name),declared=IMAGE_MIMES[ext]
 const isImage=Boolean(declared)||/^image\//.test(file?.type||'')
 if(!isImage){
  if(file.size>MAX_DOC_BYTES)throw new Error('That file is larger than 15 MB. Choose a smaller PDF or text file.')
  return {filename:file.name,mime:file.type||'application/octet-stream',data_b64:await readB64(file,env),resized:false}
 }
 if(!declared||(file.type&&!Object.values(IMAGE_MIMES).includes(file.type)))throw new Error('Use a JPG, PNG or WEBP image. Other image types such as HEIC are not supported here; export as JPG first.')
 const codec=env.codec||browserCodec(env),target=env.targetBytes??IMAGE_TARGET_BYTES,maxEdge=env.maxEdge??IMAGE_MAX_EDGE
 let bmp
 try{bmp=await codec.decode(file)}catch{throw new Error('That image could not be read. Choose a different JPG, PNG or WEBP file.')}
 try{
  const {width,height}=bmp
  if(!(width>0&&height>0))throw new Error('That image could not be read. Choose a different JPG, PNG or WEBP file.')
  if(file.size<=target&&Math.max(width,height)<=maxEdge)return {filename:file.name,mime:declared,data_b64:await readB64(file,env),resized:false}
  const attempts=[]
  let edge=Math.min(maxEdge,Math.max(width,height))
  const minEdge=Math.min(IMAGE_MIN_EDGE,edge)
  while(true){
   const s=edge/Math.max(width,height),w=Math.max(1,Math.round(width*s)),h=Math.max(1,Math.round(height*s))
   // PNG photos rarely shrink enough: keep PNG for the first pass, then switch to JPEG with a matching name.
   const mimes=declared==='image/png'?['image/png','image/jpeg']:[declared]
   for(const mime of mimes){
    for(const q of (mime==='image/png'?[undefined]:[0.85,0.7,0.55])){
     const blob=await codec.encode(bmp,w,h,mime,q)
     attempts.push(blob.size)
     if(blob.size<=target)return {filename:swapExt(file.name,blob.type||mime),mime:blob.type||mime,data_b64:await readB64(blob,env),resized:true,width:w,height:h}
    }
   }
   if(edge<=minEdge)break
   edge=Math.max(minEdge,Math.round(edge*0.75))
  }
  throw new Error('That image is still too large after shrinking. Retake it closer or at lower quality.')
 }finally{bmp.close?.()}
}
