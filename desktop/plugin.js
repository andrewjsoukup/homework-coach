// Homework Coach — Desktop panel (SDK surface only).
// Per-child skill progress, recent packets (save/reveal PDFs), homework photo upload,
// and I/S/N feedback. Talks only to this package's own backend (/api/plugins/homework-coach)
// through ctx.rest; files leave the gateway only through captureGatewayFileDownload.
// Disk plugin: plain ESM, no JSX, imports only @hermes/plugin-sdk / react.
import * as sdk from '@hermes/plugin-sdk'
import { useRef, useState } from 'react'
import { jsx as rawJsx, jsxs as rawJsxs, Fragment } from 'react/jsx-runtime'

// The automatic runtime takes `key` as a separate argument, not a prop; these wrappers
// let the uncompiled calls below write `{ key, ... }` like JSX would.
const keyed = fn => (type, props) => {
  if (!props || props.key === undefined) return fn(type, props)
  const { key, ...rest } = props
  return fn(type, rest, key)
}
const jsx = keyed(rawJsx)
const jsxs = keyed(rawJsxs)

const { host, useQuery, useMutation, useQueryClient, Button, Badge, EmptyState, Loader, Textarea } = sdk

const PLUGIN_ID = 'homework-coach'
const ROUTE = '/homework-coach'
const OVERVIEW_KEY = [PLUGIN_ID, 'overview']
const DIMS = ['scaffold', 'steps', 'representation', 'number_range']
const DIM_LABEL = { scaffold: 'Scaffold', steps: 'Steps', representation: 'Representation', number_range: 'Number range' }
const RATINGS = ['I', 'S', 'N']
const RATING_HELP = { I: 'Independent', S: 'Supported', N: 'Not yet' }
const MAX_UPLOAD = 20 * 1024 * 1024
const IMAGE_ACCEPT = '.jpg,.jpeg,.png,.webp,.gif,.heic,.heif'
const MIME = { jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', webp: 'image/webp', gif: 'image/gif', heic: 'image/heic', heif: 'image/heif' }

const muted = 'text-(--ui-text-tertiary)'
const card = 'rounded-md p-3 shadow-[inset_0_0_0_1px_var(--ui-stroke-secondary)]'

/** Pure helpers — exported for the Node test (tests/desktop/plugin.test.mjs). */
export function errorText(err) {
  if (!err) return ''
  const d = err.detail ?? err.body?.detail ?? err.data?.detail
  if (typeof d === 'string') return d
  if (d && typeof d === 'object') return [d.error, ...(d.details || [])].filter(Boolean).join('; ')
  return String(err.message || err)
}

export function ratingsPayload(items, picks) {
  const out = {}
  for (const it of items || []) {
    const r = picks?.[it.id]
    if (RATINGS.includes(r)) out[it.id] = r
  }
  return out
}

export function levelBar(level) {
  const n = Math.max(1, Math.min(5, Number(level) || 1))
  return '\u25CF'.repeat(n) + '\u25CB'.repeat(5 - n)
}

export function mimeFor(name) {
  const ext = String(name || '').split('.').pop().toLowerCase()
  return MIME[ext] || 'application/octet-stream'
}

// ── data ─────────────────────────────────────────────────────────────────────
function useOverview(ctx) {
  return useQuery({
    queryKey: OVERVIEW_KEY,
    queryFn: async () => {
      // Capture the save door alongside the read so it keeps this read's profile scope.
      const save = typeof sdk.captureGatewayFileDownload === 'function' ? sdk.captureGatewayFileDownload() : null
      const data = await ctx.rest('/overview?packets=7')
      return { ...data, save }
    },
    refetchInterval: 60_000
  })
}

// ── leaf components ──────────────────────────────────────────────────────────
function Section({ title, right, children }) {
  return jsxs('section', {
    className: 'flex flex-col gap-2',
    children: [
      jsxs('div', {
        className: 'flex items-center justify-between',
        children: [jsx('h3', { className: 'text-xs font-semibold uppercase tracking-wide ' + muted, children: title }), right]
      }),
      children
    ]
  })
}

function Tally({ tally }) {
  if (!tally) return null
  return jsxs('span', {
    className: 'flex gap-1',
    children: RATINGS.map(r =>
      jsx(Badge, {
        key: r,
        size: 'xs',
        variant: r === 'I' ? 'success' : r === 'N' ? 'warn' : 'muted',
        title: RATING_HELP[r],
        children: `${r} ${tally[r] || 0}`
      })
    )
  })
}

function SkillRow({ s }) {
  const change = s.last_change
  return jsxs('div', {
    className: 'flex flex-col gap-1 py-1.5',
    children: [
      jsxs('div', {
        className: 'flex items-center justify-between gap-2',
        children: [
          jsx('span', { className: 'truncate text-sm', children: s.skill }),
          jsxs('span', {
            className: 'flex items-center gap-2',
            children: [
              jsx(Tally, { tally: s.recent }),
              jsx('span', { className: 'font-mono text-xs text-(--ui-accent)', title: `Level ${s.level} of 5`, children: levelBar(s.level) })
            ]
          })
        ]
      }),
      jsx('div', {
        className: 'flex flex-wrap gap-x-3 gap-y-0.5 text-[0.6875rem] ' + muted,
        children: DIMS.map(d => jsx('span', { key: d, children: `${DIM_LABEL[d]} ${s.dims?.[d] ?? 1}` }))
      }),
      change && jsx('div', {
        className: 'text-[0.6875rem] ' + muted,
        children: `Last change ${change.date || ''}: ${change.change} ${change.dim ? '(' + (DIM_LABEL[change.dim] || change.dim) + ')' : ''}`
      })
    ]
  })
}

function ChildCard({ child, onUpload }) {
  return jsxs('div', {
    className: card + ' flex flex-col gap-2',
    children: [
      jsxs('div', {
        className: 'flex items-start justify-between gap-2',
        children: [
          jsxs('div', {
            className: 'flex flex-col',
            children: [
              jsx('span', { className: 'text-sm font-semibold', children: child.name }),
              jsx('span', {
                className: 'text-xs ' + muted,
                children: `Grade ${child.grade} \u00B7 ${child.curriculum} \u00B7 ${child.item_budget} items/day`
              })
            ]
          }),
          jsx(Button, { size: 'xs', variant: 'secondary', onClick: () => onUpload(child), children: 'Add homework photo' })
        ]
      }),
      child.anchor
        ? jsx('div', {
            className: 'text-xs',
            children: `Classroom anchor (${child.anchor.date}): ${child.anchor.lesson || (child.anchor.skills || []).join(', ') || '\u2014'}`
          })
        : jsx('div', { className: 'text-xs ' + muted, children: 'No homework analysed yet.' }),
      child.skills?.length
        ? jsx('div', {
            className: 'divide-y divide-(--ui-stroke-secondary)',
            children: child.skills.map(s => jsx(SkillRow, { key: s.skill, s }))
          })
        : jsx('div', { className: 'text-xs ' + muted, children: 'Skill levels appear after the first packet feedback.' }),
      child.last_feedback &&
        jsxs('div', {
          className: 'flex items-center gap-2 text-xs ' + muted,
          children: [`Last feedback ${child.last_feedback.date} (packet ${child.last_feedback.packet_date})`, jsx(Tally, { tally: child.last_feedback.tally })]
        })
    ]
  })
}

function PacketCard({ ctx, packet, childNames, save, onRate }) {
  const fileButton = f => {
    const label = f.kind === 'parent_key' ? 'Parent key' : `${childNames[f.child_id] || f.child_id} practice`
    return jsxs('span', {
      key: f.name,
      className: 'flex items-center gap-1',
      children: [
        jsx(Button, {
          size: 'xs',
          variant: 'outline',
          disabled: !save,
          title: save ? 'Save a copy of this PDF' : 'This Desktop build cannot save gateway files',
          // Explicit user gesture → gateway file-save door (native save dialog, no file:// URLs).
          onClick: () => save && save(f.path, `${packet.date}_${f.name}`),
          children: label
        }),
        jsx(Button, {
          size: 'xs',
          variant: 'ghost',
          title: 'Show in folder (local gateway only)',
          onClick: async () => {
            const ok = await ctx.os?.revealPath?.(f.path)
            if (!ok) host.notify({ kind: 'info', message: 'Folder reveal is only available for a local gateway.' })
          },
          children: '\u2197'
        })
      ]
    })
  }
  const kids = Object.entries(packet.children || {})
  return jsxs('div', {
    className: card + ' flex flex-col gap-2',
    children: [
      jsxs('div', {
        className: 'flex items-center justify-between',
        children: [
          jsx('span', { className: 'text-sm font-semibold', children: packet.date }),
          packet.verified === true
            ? jsx(Badge, { size: 'xs', variant: 'success', children: 'verified' })
            : packet.verified === false
              ? jsx(Badge, { size: 'xs', variant: 'warn', children: 'verification failed' })
              : null
        ]
      }),
      packet.files?.length
        ? jsx('div', { className: 'flex flex-wrap gap-2', children: packet.files.map(fileButton) })
        : jsx('div', { className: 'text-xs ' + muted, children: 'No PDFs in this packet folder.' }),
      kids.length > 0 &&
        jsx('div', {
          className: 'flex flex-wrap gap-2',
          children: kids.map(([cid, c]) =>
            jsx(Button, {
              key: cid,
              size: 'xs',
              variant: c.rated ? 'ghost' : 'secondary',
              disabled: !c.items?.length,
              onClick: () => onRate(packet, cid),
              children: `${c.rated ? 'Re-rate' : 'Rate'} ${childNames[cid] || cid}`
            })
          )
        })
    ]
  })
}

function FeedbackForm({ ctx, packet, childId, childName, onDone }) {
  const qc = useQueryClient()
  const items = packet.children?.[childId]?.items || []
  const [picks, setPicks] = useState({})
  const [note, setNote] = useState('')
  const m = useMutation({
    mutationFn: () =>
      ctx.rest('/feedback', { method: 'POST', body: { child_id: childId, packet_date: packet.date, ratings: ratingsPayload(items, picks), note } }),
    onSuccess: res => {
      if (res && res.ok === false) {
        host.notify({ kind: 'error', message: res.error || 'Feedback was not recorded.' })
        return
      }
      const changes = Object.entries(res?.changes || {})
      host.notify({
        kind: 'success',
        message: `Feedback saved for ${childName}.`,
        detail: changes.length ? changes.map(([s, d]) => `${s}: ${d}`).join(', ') : 'No difficulty change yet.'
      })
      qc.invalidateQueries({ queryKey: OVERVIEW_KEY })
      onDone()
    },
    onError: err => host.notify({ kind: 'error', message: errorText(err) || 'Feedback failed.' })
  })
  const rated = Object.keys(ratingsPayload(items, picks)).length
  return jsxs('div', {
    className: card + ' flex flex-col gap-2',
    children: [
      jsxs('div', {
        className: 'flex items-center justify-between',
        children: [
          jsx('span', { className: 'text-sm font-semibold', children: `${childName} \u00B7 packet ${packet.date}` }),
          jsx(Button, { size: 'xs', variant: 'text', onClick: onDone, children: 'Cancel' })
        ]
      }),
      jsx('div', { className: 'text-xs ' + muted, children: 'I = did it alone \u00B7 S = needed help \u00B7 N = not yet. Skip items that were not attempted.' }),
      ...items.map(it =>
        jsxs('div', {
          key: it.id,
          className: 'flex items-center justify-between gap-2',
          children: [
            jsxs('div', {
              className: 'flex min-w-0 flex-col',
              children: [
                jsx('span', { className: 'truncate text-sm', children: `${it.id}. ${it.prompt || it.format}` }),
                jsx('span', { className: 'text-[0.6875rem] ' + muted, children: `${it.skill} \u00B7 ${it.format}${it.optional ? ' \u00B7 optional' : ''}` })
              ]
            }),
            jsx('div', {
              className: 'flex shrink-0 gap-1',
              children: RATINGS.map(r =>
                jsx(Button, {
                  key: r,
                  size: 'icon-xs',
                  variant: picks[it.id] === r ? 'default' : 'outline',
                  title: RATING_HELP[r],
                  'aria-pressed': picks[it.id] === r,
                  onClick: () => setPicks(p => ({ ...p, [it.id]: p[it.id] === r ? undefined : r })),
                  children: r
                })
              )
            })
          ]
        })
      ),
      jsx(Textarea, { value: note, placeholder: 'Optional note (what helped, what was hard)', rows: 2, maxLength: 1000, onChange: e => setNote(e.target.value) }),
      jsx('div', {
        className: 'flex justify-end',
        children: jsx(Button, { size: 'sm', disabled: !rated || m.isPending, onClick: () => m.mutate(), children: m.isPending ? 'Saving\u2026' : `Save ${rated} rating${rated === 1 ? '' : 's'}` })
      })
    ]
  })
}

function UploadForm({ ctx, child, onDone }) {
  const qc = useQueryClient()
  const input = useRef(null)
  const [file, setFile] = useState(null)
  const [note, setNote] = useState('')
  const [result, setResult] = useState(null)
  const m = useMutation({
    mutationFn: async () => {
      const bytes = await file.arrayBuffer()
      const q = `?child_id=${encodeURIComponent(child.id)}&note=${encodeURIComponent(note.slice(0, 500))}`
      return ctx.rest('/intake' + q, { method: 'POST', upload: { filename: file.name, contentType: mimeFor(file.name), bytes }, timeoutMs: 180_000 })
    },
    onSuccess: res => {
      setResult(res)
      if (res && res.ok === false) host.notify({ kind: 'warning', message: res.error || 'Photo was not analysed.' })
      else host.notify({ kind: 'success', message: `Homework analysed for ${child.name}.` })
      qc.invalidateQueries({ queryKey: OVERVIEW_KEY })
    },
    onError: err => host.notify({ kind: 'error', message: errorText(err) || 'Upload failed.' })
  })
  const pick = e => {
    const f = e.target.files?.[0] || null
    if (f && f.size > MAX_UPLOAD) {
      host.notify({ kind: 'error', message: 'Photo is larger than 20 MB.' })
      return
    }
    setFile(f)
    setResult(null)
  }
  return jsxs('div', {
    className: card + ' flex flex-col gap-2',
    children: [
      jsxs('div', {
        className: 'flex items-center justify-between',
        children: [
          jsx('span', { className: 'text-sm font-semibold', children: `Homework photo for ${child.name}` }),
          jsx(Button, { size: 'xs', variant: 'text', onClick: onDone, children: 'Close' })
        ]
      }),
      jsx('div', {
        className: 'text-xs ' + muted,
        children: 'The photo is sent to your configured model provider for reading. Copies stay in the plugin data folder only.'
      }),
      jsx('input', { ref: input, type: 'file', accept: IMAGE_ACCEPT, className: 'hidden', onChange: pick }),
      jsxs('div', {
        className: 'flex items-center gap-2',
        children: [
          jsx(Button, { size: 'xs', variant: 'secondary', onClick: () => input.current?.click(), children: file ? 'Change photo' : 'Choose photo' }),
          jsx('span', { className: 'truncate text-xs ' + muted, children: file ? `${file.name} (${Math.ceil(file.size / 1024)} KB)` : 'No photo chosen' })
        ]
      }),
      jsx(Textarea, { value: note, placeholder: 'Optional: lesson name, what was assigned', rows: 2, maxLength: 500, onChange: e => setNote(e.target.value) }),
      jsx('div', {
        className: 'flex justify-end',
        children: jsx(Button, { size: 'sm', disabled: !file || m.isPending, onClick: () => m.mutate(), children: m.isPending ? 'Analysing\u2026' : 'Analyse homework' })
      }),
      result && jsx(IntakeResult, { result })
    ]
  })
}

function IntakeResult({ result }) {
  if (result.ok === false) return jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: result.error })
  const lines = []
  if (result.summary) lines.push(result.summary)
  for (const k of ['strengths', 'likely_slips', 'checking_targets']) {
    const v = result[k]
    if (Array.isArray(v) && v.length) lines.push(`${k.replace('_', ' ')}: ${v.join('; ')}`)
  }
  if (!lines.length) lines.push('Observation recorded.')
  return jsx('div', { className: 'flex flex-col gap-1 text-xs', children: lines.map((l, i) => jsx('div', { key: i, children: l })) })
}

// ── page ─────────────────────────────────────────────────────────────────────
function HomeworkPage({ ctx }) {
  const q = useOverview(ctx)
  const [rating, setRating] = useState(null) // { packet, childId }
  const [uploading, setUploading] = useState(null) // child
  const data = q.data

  let body
  if (q.isLoading) body = jsx('div', { className: 'grid place-items-center p-8', children: jsx(Loader, {}) })
  else if (q.isError)
    body = jsx(EmptyState, {
      title: 'Homework Coach backend not reachable',
      description: `${errorText(q.error)} \u2014 enable the homework-coach plugin for this profile and restart the gateway.`
    })
  else if (!data?.configured)
    body = jsx(EmptyState, {
      title: data?.config_errors ? 'Family config has problems' : 'No family config yet',
      description: data?.config_errors ? data.config_errors.join('; ') : `Create ${data?.family_config || 'family.yaml'} (see examples/family.example.yaml), or set the "Family config file" plugin setting.`
    })
  else {
    const childNames = Object.fromEntries(data.children.map(c => [c.id, c.name]))
    body = jsxs(Fragment, {
      children: [
        uploading && jsx(UploadForm, { ctx, child: uploading, onDone: () => setUploading(null) }),
        rating &&
          jsx(FeedbackForm, {
            key: `${rating.packet.date}:${rating.childId}`,
            ctx,
            packet: rating.packet,
            childId: rating.childId,
            childName: childNames[rating.childId] || rating.childId,
            onDone: () => setRating(null)
          }),
        jsx(Section, {
          title: 'Children',
          children: jsx('div', {
            className: 'grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(18rem,1fr))]',
            children: data.children.map(c => jsx(ChildCard, { key: c.id, child: c, onUpload: setUploading }))
          })
        }),
        jsx(Section, {
          title: 'Recent packets',
          children: data.packets.length
            ? jsx('div', {
                className: 'flex flex-col gap-2',
                children: data.packets.map(p =>
                  jsx(PacketCard, { key: p.date, ctx, packet: p, childNames, save: data.save, onRate: (packet, childId) => setRating({ packet, childId }) })
                )
              })
            : jsx('div', { className: 'text-xs ' + muted, children: 'No packets yet. Ask Hermes to "make today\u2019s homework packet", or schedule the Daily homework practice packet blueprint.' })
        })
      ]
    })
  }

  return jsx('div', {
    className: 'h-full overflow-y-auto',
    children: jsxs('div', {
      className: 'mx-auto flex max-w-4xl flex-col gap-5 p-4',
      children: [
        jsxs('header', {
          className: 'flex items-center justify-between',
          children: [
            jsxs('div', {
              className: 'flex flex-col',
              children: [
                jsx('h2', { className: 'text-base font-semibold', children: 'Homework Coach' }),
                data?.configured && jsx('span', { className: 'text-xs ' + muted, children: `Today ${data.today} \u00B7 ${data.timezone}` })
              ]
            }),
            jsx(Button, { size: 'xs', variant: 'ghost', onClick: () => q.refetch(), disabled: q.isFetching, children: q.isFetching ? 'Refreshing\u2026' : 'Refresh' })
          ]
        }),
        body
      ]
    })
  })
}

export default {
  id: PLUGIN_ID,
  name: 'Homework Coach',
  register(ctx) {
    ctx.registerMany([
      { id: 'page', area: sdk.ROUTES_AREA, data: { path: ROUTE }, render: () => jsx(HomeworkPage, { ctx }) },
      { id: 'nav', area: sdk.SIDEBAR_NAV_AREA, data: { path: ROUTE, label: 'Homework', codicon: 'mortar-board' } },
      {
        id: 'open',
        area: sdk.PALETTE_AREA,
        data: { id: 'homework-coach.open', label: 'Homework Coach: Open panel', keywords: ['homework', 'packet', 'kids'], run: () => host.navigate(ROUTE) }
      }
    ])
  }
}
