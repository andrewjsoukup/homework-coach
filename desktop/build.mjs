// Build the disk plugin: only React and the public Hermes SDK remain external.
import { createRequire } from 'node:module'
import { resolve } from 'node:path'
const root = resolve(import.meta.dirname, '..')
const require = createRequire(resolve(process.env.REACT_DIR || root, 'package.json'))
const { build } = require('esbuild')
const {existsSync,readFileSync,writeFileSync}=await import('node:fs')
const outfile=resolve(import.meta.dirname,'plugin.js')
const result=await build({absWorkingDir:root,entryPoints:[resolve(import.meta.dirname,'src/plugin.jsx')],outfile,
 bundle:true,write:false,format:'esm',target:'es2022',jsx:'automatic',
 external:['react','react/jsx-runtime','@hermes/plugin-sdk'],legalComments:'none',
 banner:{js:'// Homework Coach native workspace. Generated from desktop/src/plugin.jsx; run node desktop/build.mjs.'}})
const bytes=Buffer.from(result.outputFiles[0].contents)
if(process.argv.includes('--check')){
 if(!existsSync(outfile)||!bytes.equals(readFileSync(outfile))){
  console.error('desktop/plugin.js is missing or stale. Run npm run build and commit it with desktop/src/.')
  process.exitCode=1
 }else console.log('desktop/plugin.js matches its source.')
}else{
 writeFileSync(outfile,bytes)
 console.log('Built desktop/plugin.js')
}
