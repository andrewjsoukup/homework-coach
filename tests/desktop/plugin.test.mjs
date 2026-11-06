// Smoke test for desktop/plugin.js without the Desktop app.
// Loads the plugin against a stub @hermes/plugin-sdk, checks the contract and the
// registered contributions, then server-renders the page with real React for the
// empty, unconfigured and populated states.
//
// Run:  REACT_DIR=<dir containing node_modules/react> node --test tests/desktop/plugin.test.mjs
// (CI installs react + react-dom@19 next to the repo; locally any Hermes checkout works.)
import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { test } from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..', '..')
const req = createRequire(join(process.env.REACT_DIR || root, 'package.json'))
const reactUrl = pathToFileURL(req.resolve('react')).href
const jsxUrl = pathToFileURL(req.resolve('react/jsx-runtime')).href
const React = req('react')
const { renderToStaticMarkup } = req('react-dom/server')
const { QueryClient, QueryClientProvider } = await tryQuery()

async function tryQuery() {
  try {
    return req('@tanstack/react-query')
  } catch {
    return {}
  }
}

const scratch = mkdtempSync(join(process.env.TMPDIR || tmpdir(), 'hc-desktop-'))

// Minimal SDK stub: the identifiers plugin.js reads, rendered as plain elements.
const sdkSrc = `
import * as React from ${JSON.stringify(reactUrl)}
const h = React.createElement
const el = tag => ({ children, variant, size, ...p }) => h(tag, { 'data-variant': variant, ...p }, children)
export const ROUTES_AREA = 'routes', SIDEBAR_NAV_AREA = 'sidebar.nav', PALETTE_AREA = 'palette'
export const notes = []
export const host = { notify: n => notes.push(n), navigate: p => notes.push({ nav: p }) }
export const Button = el('button'), Badge = el('span')
export const Textarea = p => h('textarea', p)
export const Loader = () => h('i', null, 'loading')
export const EmptyState = ({ title, description }) => h('div', { 'data-empty': '' }, title, ' ', description)
export const Fragment = React.Fragment
export let queryState = { isLoading: false, isError: false, data: undefined }
export const setQuery = s => { queryState = s }
export const useQuery = () => ({ refetch() {}, isFetching: false, ...queryState })
export const useMutation = o => ({ mutate() {}, isPending: false, ...o })
export const useQueryClient = () => ({ invalidateQueries() {} })
export const captureGatewayFileDownload = () => () => {}
`
const sdkPath = join(scratch, 'sdk.mjs')
writeFileSync(sdkPath, sdkSrc)

const pluginSrc = readFileSync(join(root, 'desktop', 'plugin.js'), 'utf8')
  .replace(/from '@hermes\/plugin-sdk'/g, `from ${JSON.stringify(pathToFileURL(sdkPath).href)}`)
  .replace(/from 'react\/jsx-runtime'/g, `from ${JSON.stringify(jsxUrl)}`)
  .replace(/from 'react'/g, `from ${JSON.stringify(reactUrl)}`)
const pluginPath = join(scratch, 'plugin.mjs')
writeFileSync(pluginPath, pluginSrc)

const sdk = await import(pathToFileURL(sdkPath).href)
const mod = await import(pathToFileURL(pluginPath).href)
const plugin = mod.default

function registered() {
  const contribs = []
  plugin.register({ registerMany: cs => contribs.push(...cs), register: c => contribs.push(c), rest: async () => ({}), os: {} })
  return contribs
}

function renderPage(state) {
  sdk.setQuery(state)
  const page = registered().find(c => c.id === 'page')
  const tree = page.render()
  return renderToStaticMarkup(QueryClientProvider ? React.createElement(QueryClientProvider, { client: new QueryClient() }, tree) : tree)
}

test('contract: id, name, three SDK contributions', () => {
  assert.equal(plugin.id, 'homework-coach')
  assert.equal(plugin.name, 'Homework Coach')
  const byId = Object.fromEntries(registered().map(c => [c.id, c]))
  assert.deepEqual(Object.keys(byId).sort(), ['nav', 'open', 'page'])
  assert.equal(byId.page.area, 'routes')
  assert.equal(byId.page.data.path, '/homework-coach')
  assert.equal(byId.nav.data.path, '/homework-coach')
  assert.equal(byId.open.data.id, 'homework-coach.open')
  byId.open.data.run()
  assert.deepEqual(sdk.notes.at(-1), { nav: '/homework-coach' })
})

test('pure helpers', () => {
  assert.deepEqual(mod.ratingsPayload([{ id: '1' }, { id: '2' }, { id: '3' }], { 1: 'I', 2: 'X', 3: 'N', 9: 'S' }), { 1: 'I', 3: 'N' })
  assert.equal(mod.levelBar(3), '\u25CF\u25CF\u25CF\u25CB\u25CB')
  assert.equal(mod.levelBar(99), '\u25CF'.repeat(5))
  assert.equal(mod.mimeFor('A.JPG'), 'image/jpeg')
  assert.equal(mod.mimeFor('x.bin'), 'application/octet-stream')
  assert.equal(mod.errorText({ detail: { error: 'family config invalid', details: ['bad id'] } }), 'family config invalid; bad id')
  assert.equal(mod.errorText(new Error('HTTP 404')), 'HTTP 404')
})

test('renders loading, backend error and unconfigured states', () => {
  assert.match(renderPage({ isLoading: true }), /loading/)
  assert.match(renderPage({ isError: true, error: new Error('HTTP 404') }), /backend not reachable.*HTTP 404/)
  const html = renderPage({ data: { configured: false, family_config: '/data/family.yaml', children: [], packets: [] } })
  assert.match(html, /No family config yet/)
  assert.match(html, /\/data\/family\.yaml/)
})

test('renders children, skill progress and packets', () => {
  const data = {
    configured: true,
    family_id: 'maple',
    timezone: 'America/Chicago',
    today: '2026-11-04',
    children: [
      {
        id: 'nova', name: 'Nova', grade: '3', curriculum: 'District Grade 3 Math', item_budget: 6,
        anchor: { date: '2026-11-02', lesson: 'Arrays 4-2', skills: ['arrays'], formats: [] },
        skills: [{ skill: 'arrays', level: 2, dims: { scaffold: 2, steps: 1, representation: 1, number_range: 1 }, recent: { I: 3, S: 1, N: 0 }, last_change: { date: '2026-11-03', change: 'up', dim: 'scaffold' } }],
        last_feedback: { date: '2026-11-03', packet_date: '2026-11-03', tally: { I: 3, S: 1, N: 0 } }
      },
      { id: 'pip', name: 'Pip', grade: 'K', curriculum: 'K number sense', item_budget: 3, anchor: null, skills: [], last_feedback: null }
    ],
    packets: [
      {
        date: '2026-11-03', verified: true,
        files: [
          { kind: 'practice', child_id: 'nova', name: 'nova_practice.pdf', path: '/p/nova_practice.pdf' },
          { kind: 'parent_key', child_id: null, name: 'parent_key.pdf', path: '/p/parent_key.pdf' }
        ],
        children: { nova: { items: [{ id: '1', skill: 'arrays', format: 'array -> equation', prompt: 'p' }], rated: true }, pip: { items: [], rated: false } }
      }
    ]
  }
  const html = renderPage({ data })
  for (const s of ['Nova', 'Pip', 'Arrays 4-2', 'arrays', 'Scaffold 2', 'Last change 2026-11-03: up (Scaffold)', 'I 3', '2026-11-03', 'verified', 'Nova practice', 'Parent key', 'Re-rate Nova', 'Rate Pip', 'No homework analysed yet.']) {
    assert.ok(html.includes(s), `missing ${s}`)
  }
  assert.ok(html.includes('\u25CF\u25CF\u25CB\u25CB\u25CB'))
})
