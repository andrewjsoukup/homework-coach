// Executable contract tests for the native desktop workspace. No live family files.
import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { test } from 'node:test'
const root = resolve(import.meta.dirname, '../..')
const req = createRequire(join(process.env.REACT_DIR || root, 'package.json'))
const React = req('react')
const {renderToStaticMarkup} = req('react-dom/server')
const scratch = mkdtempSync(join(process.env.TMPDIR || tmpdir(), 'hc-workspace-'))
const url = s => JSON.stringify(pathToFileURL(s).href)
writeFileSync(join(scratch,'sdk.mjs'), `
import * as React from ${url(req.resolve('react'))}
const h=React.createElement
const el=tag=>({children,variant,size,...p})=>h(tag,p,children)
export const Button=el('button'), Badge=el('span'), Input=el('input'), Textarea=el('textarea')
export const Loader=()=>h('span',null,'Loading…')
export const atom = initial => { let value=initial; return {get:()=>value,set:v=>{value=v},subscribe:()=>()=>{}} }
export const useValue=a=>a.get()
export const host={state:{profile:atom('demo'),connectionId:atom('local'),activeSessionId:atom(null)},navigate:()=>{},notify:()=>{},composer:{setDraft:async()=>false}}
export let responses={}
export const setResponses=v=>{responses=v}
export const useQuery=o=>({data:responses[o.queryKey.at(-1)],isLoading:false,refetch:()=>{}})
export const useMutation=o=>({mutate:()=>{},isPending:false})
export const useQueryClient=()=>({invalidateQueries:()=>{}})
export const captureGatewayFileDownload=()=>()=>{}
export const ROUTES_AREA='routes', SIDEBAR_NAV_AREA='sidebar.nav', PALETTE_AREA='palette', TRANSCRIPT_DIRECTIVE_AREA='transcript.directives', TOOL_MEDIA_RENDERER_AREA='transcript.toolMedia', STATUSBAR_AREAS={right:'statusBar.right'}
export const pluginSettingsHref=(id,page)=>'/settings?tab=plugins&plugin='+id+(page?'&ppage='+page:'')
`)
const source = readFileSync(join(root,'desktop/plugin.js'),'utf8')
 .replace(/from ['"]@hermes\/plugin-sdk['"]/g, 'from '+url(join(scratch,'sdk.mjs')))
 .replace(/from ['"]react\/jsx-runtime['"]/g, 'from '+url(req.resolve('react/jsx-runtime')))
 .replace(/from ['"]react['"]/g, 'from '+url(req.resolve('react')))
writeFileSync(join(scratch,'plugin.mjs'),source)
const sdk=await import(pathToFileURL(join(scratch,'sdk.mjs')))
const mod=await import(pathToFileURL(join(scratch,'plugin.mjs')))
const ctx={rest:async()=>({}),os:{},registerMany:()=>{}}
const render=(C,p={})=>renderToStaticMarkup(React.createElement(C,{ctx,...p}))

test('native workspace registers page, status, packet cards and family settings',()=>{
 const rows=[],settings=[]
 mod.default.register({...ctx,registerMany:cs=>rows.push(...cs),register:c=>rows.push(c),registerSettingsPage:s=>settings.push(s)})
 assert.ok(rows.find(c=>c.area==='routes'))
 assert.ok(rows.find(c=>c.area==='statusBar.right'),'pending-rating status is reachable')
 assert.ok(rows.find(c=>c.area==='transcript.directives'),'rich packet directive')
 assert.ok(rows.find(c=>c.area==='transcript.toolMedia'),'tool-owned packet files')
 assert.equal(settings[0]?.title,'Homework Coach')
 assert.ok(settings[0].children.some(c=>c.id==='schedule'))
})

test('class plan exposes the full year, today, teacher changes and research sources',()=>{
 sdk.setResponses({'/children/nova/class-plan':{child:{id:'nova',name:'Nova'},today:'2026-11-08',has_plan:true,curriculum:'enVision Math',school_year:'2026–27',sources:[{title:'Publisher scope and sequence',url:'https://example.org/scope'}],unmatched_materials:[],units:[{index:0,title:'Topic 3: Multiplication',phase:'now',start:'2026-11-02',end:'2026-11-13',start_label:'Mon Nov 2',end_label:'Fri Nov 13',source:'teacher',shifted:true,researched_start:'2026-10-05',researched_end:'2026-10-16',goals:['Use equal groups'],vocabulary:['array'],standards:['3.OA.A.1'],materials:[{index:0,title:'Ms. Rivera’s newsletter',date_label:'Mon Nov 2',has_file:true}],packets:['2026-11-07'],undo:true},{index:1,title:'Topic 4: Division',phase:'next',start:'2026-11-16',end:'2026-12-01',goals:[],materials:[],packets:[]}]}})
 const html=render(mod.ClassPlan,{childId:'nova',open:()=>{}})
 for(const x of ['enVision','TODAY','Topic 3','Topic 4','Teacher update','2026-10-05','2026-11-13','equal groups','array','Publisher scope','Undo','Ms. Rivera'])assert.ok(html.includes(x),x)
})

test('family settings offer editable profiles, archival history and practice schedule',()=>{
 sdk.setResponses({'/family':{family_id:'maple',timezone:'America/Chicago',schedule:{days:['mon','wed'],time:'09:00'},grades:['K','1','2','3'],children:[{id:'nova',name:'Nova',grade:'3',minutes_per_day:15,curriculum:'enVision',subjects:['math']}],archived:[{id:'pip',name:'Pip',grade:'K'}]}})
 const html=render(mod.FamilyPage)
 for(const x of ['Nova','15 minutes','Edit profile','Archive','Pip','Restore','Add child','Practice schedule','09:00'])assert.ok(html.includes(x),x)
 const form=render(mod.ChildForm,{child:{id:'nova',name:'Nova',grade:'3',minutes_per_day:15},grades:['K','3'],onDone:()=>{}})
 for(const x of ['Name','Grade','Minutes per day','School math program','Save profile'])assert.ok(form.includes(x),x)
})

const packet={date:'2026-11-07',label:'Sat Nov 7',child:{id:'nova',name:'Nova',grade:'3'},focus:'Equal groups',steered_by:'homework photo',photo_label:'Fri Nov 6',photo_index:0,verified:true,practice_pdf:'/data/nova.pdf',key_pdf:'/data/key.pdf',progression:[],items:[{id:'1',prompt:'Four groups of six',skill_label:'Multiplication',format_label:'Equal groups',answer:'24',worked:'6 + 6 + 6 + 6 = 24',tip:'Point at one group, then skip-count.',rating:'N',optional:false},{id:'S1',prompt:'Challenge',tip:'Think aloud.',rating:null,optional:true}]}
test('rate desk shows actual sheet preview, source, keyboard help and support tip',()=>{
 sdk.setResponses({'/packet/2026-11-07/nova':packet,'/packet/2026-11-07/nova/preview?page=0&kind=practice':{image:'data:image/png;base64,eA==',page:0,pages:1}})
 const html=render(mod.RateDesk,{date:packet.date,childId:'nova',onDone:()=>{},onSource:()=>{}})
 for(const x of ['Nova','Four groups','On their own','With support','Not yet','skip-count','Parent key','Save sheet','Photo','Optional','Save ratings'])assert.ok(html.includes(x),x)
 assert.ok(html.includes('data:image/png;base64,eA=='),'renders the real PDF preview returned by backend')
 assert.equal(mod.ratingKey({key:'I',target:{tagName:'INPUT'}}),null)
 assert.equal(mod.ratingKey({key:'n',target:{tagName:'BUTTON'}}),'N')
 assert.equal(mod.ratingKey({key:'s',ctrlKey:true,target:{tagName:'BUTTON'}}),null)
})
test('chat packet cards show source and links; malformed directives fail closed',()=>{
 sdk.setResponses({'/packet/2026-11-07/nova':packet})
 const html=render(mod.ChatPacket,{attrs:{child:'nova',date:'2026-11-07'}})
 for(const x of ['Nova','Equal groups','Photo','Open sheet','Save','Parent key','Rate'])assert.ok(html.includes(x),x)
 assert.equal(mod.packetReference({child:'../private',date:'2026-11-07'}),null)
 assert.deepEqual(mod.packetReference({child:'nova',date:'2026-11-07'}),{childId:'nova',date:'2026-11-07'})
})

test('progress shows dated rating evidence, real change reasons, and separates homework',()=>{
 sdk.setResponses({'/children/nova/progress?days=30':{child:{id:'nova',name:'Nova'},rated_problems:6,totals:{I:5,S:0,N:1},enough_data:false,columns:[{date:'2026-11-07',label:'Sat Nov 7',rated:true}],skills:[{skill:'multiplication',label:'Multiplication',level:2,dims:{scaffold:2},cells:[{date:'2026-11-07',marks:[{id:'1',rating:'N',prompt:'4 x 6'}]}],changes:[{label:'Sat Nov 7',plain:'hints brought back',why:'after a “not yet”'}]}],homework:[{label:'Fri Nov 6',lesson:'Lesson 3-2',items:12,slips:2}]}})
 const html=render(mod.ProgressView,{childId:'nova',open:()=>{}})
 for(const x of ['How Nova is doing','problems rated','Multiplication','hints brought back','not yet','Rate two practice sheets','From school homework','Lesson 3-2','2 to check'])assert.ok(html.includes(x),x)
 assert.ok(!/mastery|score/i.test(html))
})
test('history and homework read-back expose sources and corrections',()=>{
 sdk.setResponses({'/children/nova/history':{child:{id:'nova',name:'Nova'},events:[{type:'homework',date:'2026-11-06',label:'Fri Nov 6',index:0,title:'Lesson 3-2',detail:'12 problems read · 2 to check'},{type:'practice',date:'2026-11-07',label:'Sat Nov 7',title:'Equal groups',detail:'Not rated yet',steered_by:'homework photo',rated:false}]},
  '/children/nova/observations/0':{index:0,label:'Fri Nov 6',lesson:'Lesson 3-2',photo:'data:image/jpeg;base64,eA==',items:[{n:0,prompt:'6 x 4',child_answer:'26',expected_answer:'24',status:'slip',confidence:0.95},{n:1,prompt:'3 x 4',child_answer:'?',expected_answer:'12',status:'needs_recheck',confidence:0.4}]}})
 let html=render(mod.HistoryView,{childId:'nova',open:()=>{}})
 for(const x of ['Homework photo','See what was read','Followed a homework photo','Rate'])assert.ok(html.includes(x),x)
 html=render(mod.Readback,{childId:'nova',index:0})
 for(const x of ['Lesson 3-2','26','24','Small slip','Unclear','1 unclear reading','Fix this reading','data:image/jpeg'])assert.ok(html.includes(x),x)
})
test('upload screens explain privacy and teacher changes need review',()=>{
 const child={id:'nova',name:'Nova'}
 assert.ok(render(mod.UploadView,{child,onDone:()=>{}}).includes('model provider'))
 const t=render(mod.UploadView,{child,teacher:true,onDone:()=>{}})
 assert.ok(t.includes('review any plan change'))
})

test('empty readings never claim confidence and source links keep exact provenance',()=>{
 sdk.setResponses({'/children/nova/observations/0':{index:0,label:'Fri Nov 6',lesson:'Unreadable page',photo:null,items:[]}})
 let html=render(mod.Readback,{childId:'nova',index:0})
 assert.ok(html.includes('No problems could be read'))
 assert.ok(!html.includes('Every reading looks confident'))
 assert.deepEqual(mod.navigationView({observation:{childId:'nova',index:2}}),{kind:'observation',childId:'nova',index:2})
 assert.equal(mod.canFollowSource({...packet,photo_index:null,photo_provenance:'missing'}),false)
 assert.equal(mod.canFollowSource(packet),true)
 assert.deepEqual(mod.navigationView({packet:{childId:'pip',date:'2026-11-09'}}),{kind:'packet',childId:'pip',date:'2026-11-09'})
})

test('Today tells a parent the next action and offers all four main tabs',()=>{
 sdk.setResponses({'/today':{today:'2026-11-08',today_label:'Sun Nov 8',to_rate:1,children:[{id:'nova',name:'Nova',grade:'3',minutes:15,status:'needs_rating',action:'rate',packet_date:'2026-11-07',headline:'Rate Sat Nov 7’s sheet',class_unit:'Topic 3: Multiplication',steered_by:'homework photo',has_plan:true}]}})
 const html=render(mod.HomeworkPage)
 for(const x of ['Today','Class plan','Progress','History','Nova','Rate Sat Nov 7','Family','Add homework'])assert.ok(html.includes(x),x)
 assert.ok(!html.includes('mastery score'))
})
