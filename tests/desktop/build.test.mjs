import assert from 'node:assert/strict'
import {cpSync,existsSync,mkdirSync,mkdtempSync,readFileSync,writeFileSync} from 'node:fs'
import {resolve,join} from 'node:path'
import {tmpdir} from 'node:os'
import {spawnSync} from 'node:child_process'
import {test} from 'node:test'
const root=resolve(import.meta.dirname,'../..')
test('bundle check detects missing or stale output without rewriting it',()=>{
 const work=mkdtempSync(join(process.env.TMPDIR||tmpdir(),'hc-build-'))
 mkdirSync(join(work,'desktop'))
 cpSync(join(root,'desktop','src'),join(work,'desktop','src'),{recursive:true})
 cpSync(join(root,'desktop','build.mjs'),join(work,'desktop','build.mjs'))
 const script=join(work,'desktop','build.mjs'),out=join(work,'desktop','plugin.js')
 const env={...process.env,REACT_DIR:process.env.REACT_DIR||root}
 const run=(args)=>spawnSync(process.execPath,[script,...args],{env,cwd:work,encoding:'utf8'})
 assert.equal(run(['--check']).status,1,'missing bundle must fail check')
 assert.equal(existsSync(out),false,'check must not write a missing bundle')
 const built=run([]);assert.equal(built.status,0,built.stderr)
 const before=readFileSync(out)
 const good=run(['--check']);assert.equal(good.status,0,good.stderr)
 const source=join(work,'desktop','src','plugin.jsx')
 writeFileSync(source,readFileSync(source,'utf8')+'\nexport const publicationCheckSentinel=1\n')
 assert.equal(run(['--check']).status,1,'source drift must fail check')
 assert.deepEqual(readFileSync(out),before,'failed check must not overwrite the submitted bundle')
})
