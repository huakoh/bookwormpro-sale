import { Box, Text, useInput, useStdout } from '@bookworm/ink'
import { useEffect, useMemo, useState } from 'react'

import type { GatewayClient } from '../gatewayClient.js'
import type { SessionListItem, SessionListResponse } from '../gatewayTypes.js'
import { asRpcResult, rpcErrorMessage } from '../lib/rpc.js'
import type { Theme } from '../theme.js'

const VISIBLE = 15
const MIN_WIDTH = 60
const MAX_WIDTH = 120

const age = (ts: number) => {
  const d = (Date.now() / 1000 - ts) / 86400

  if (d < 1) {
    return 'today'
  }

  if (d < 2) {
    return 'yesterday'
  }

  return `${Math.floor(d)}d ago`
}

const fmtTokens = (s: SessionListItem) => {
  const total = (s.input_tokens ?? 0) + (s.output_tokens ?? 0)
  if (total === 0) return '—'
  if (total < 1000) return `${total}`
  if (total < 1_000_000) return `${(total / 1000).toFixed(1)}k`
  return `${(total / 1_000_000).toFixed(1)}M`
}

const fmtCost = (s: SessionListItem) => {
  const cost = s.estimated_cost_usd ?? 0
  if (!cost) return '—'
  if (cost < 0.01) return `$${cost.toFixed(4)}`
  return `$${cost.toFixed(2)}`
}

const fuzzyMatch = (query: string, text: string): boolean => {
  const q = query.toLowerCase()
  const t = text.toLowerCase()
  let qi = 0
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) qi++
  }
  return qi === q.length
}

export function SessionPicker({ gw, onCancel, onSelect, t }: SessionPickerProps) {
  const [allItems, setAllItems] = useState<SessionListItem[]>([])
  const [err, setErr] = useState('')
  const [sel, setSel] = useState(0)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')

  const { stdout } = useStdout()
  const width = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, (stdout?.columns ?? 80) - 6))

  const items = useMemo(() => {
    if (!query) return allItems
    return allItems.filter(s => {
      const haystack = `${s.title ?? ''} ${s.preview ?? ''} ${s.id} ${s.source ?? ''}`
      return fuzzyMatch(query, haystack)
    })
  }, [allItems, query])

  useEffect(() => { setSel(0) }, [query])

  useEffect(() => {
    gw.request<SessionListResponse>('session.list', { limit: 30 })
      .then(raw => {
        const r = asRpcResult<SessionListResponse>(raw)

        if (!r) {
          setErr('invalid response: session.list')
          setLoading(false)

          return
        }

        setAllItems(r.sessions ?? [])
        setErr('')
        setLoading(false)
      })
      .catch((e: unknown) => {
        setErr(rpcErrorMessage(e))
        setLoading(false)
      })
  }, [gw])

  useInput((ch, key) => {
    if (key.escape) {
      if (query) { setQuery(''); return }
      return onCancel()
    }

    if (key.upArrow && sel > 0) {
      setSel(s => s - 1)
    }

    if (key.downArrow && sel < items.length - 1) {
      setSel(s => s + 1)
    }

    if (key.return && items[sel]) {
      onSelect(items[sel]!.id)
    }

    if (key.backspace || key.delete) {
      setQuery(q => q.slice(0, -1))
      return
    }

    if (!query && ch >= '1' && ch <= '9') {
      const n = parseInt(ch)
      if (n >= 1 && n <= Math.min(9, items.length)) {
        onSelect(items[n - 1]!.id)
      }
      return
    }

    if (ch && ch.length === 1 && !key.ctrl && !key.meta && ch >= ' ') {
      setQuery(q => q + ch)
    }
  })

  if (loading) {
    return <Text color={t.color.dim}>loading sessions…</Text>
  }

  if (err) {
    return (
      <Box flexDirection="column">
        <Text color={t.color.label}>error: {err}</Text>
        <Text color={t.color.dim}>Esc to cancel</Text>
      </Box>
    )
  }

  if (!allItems.length) {
    return (
      <Box flexDirection="column">
        <Text color={t.color.dim}>no previous sessions</Text>
        <Text color={t.color.dim}>Esc to cancel</Text>
      </Box>
    )
  }

  const off = Math.max(0, Math.min(sel - Math.floor(VISIBLE / 2), items.length - VISIBLE))

  return (
    <Box flexDirection="column" width={width}>
      <Text bold color={t.color.amber}>
        Resume Session
      </Text>

      <Box>
        <Text color={t.color.dim}>search: </Text>
        <Text color={t.color.amber}>{query || ' '}</Text>
        <Text color={t.color.dim}>{query ? '' : '(type to filter)'}</Text>
      </Box>

      {items.length === 0 && query && (
        <Text color={t.color.dim}> no matches for &quot;{query}&quot;</Text>
      )}

      {off > 0 && <Text color={t.color.dim}> ↑ {off} more</Text>}

      {items.slice(off, off + VISIBLE).map((s, vi) => {
        const i = off + vi
        const selected = sel === i
        const clr = selected ? t.color.amber : t.color.dim

        return (
          <Box key={s.id}>
            <Text bold={selected} color={clr} inverse={selected}>
              {selected ? '▸ ' : '  '}
            </Text>

            <Box width={3}>
              <Text bold={selected} color={clr} inverse={selected}>
                {String(i + 1).padStart(2)}.
              </Text>
            </Box>

            <Box width={28}>
              <Text bold={selected} color={clr} inverse={selected} wrap="truncate-end">
                {' '}{s.title || s.preview || '(untitled)'}
              </Text>
            </Box>

            <Box width={8}>
              <Text bold={selected} color={clr} inverse={selected}>
                {fmtTokens(s).padStart(6)}
              </Text>
            </Box>

            <Box width={8}>
              <Text bold={selected} color={clr} inverse={selected}>
                {fmtCost(s).padStart(7)}
              </Text>
            </Box>

            <Box width={5}>
              <Text bold={selected} color={clr} inverse={selected}>
                {String(s.message_count).padStart(3)}m
              </Text>
            </Box>

            <Text bold={selected} color={clr} inverse={selected}>
              {' '}{age(s.started_at)}
            </Text>
          </Box>
        )
      })}

      {off + VISIBLE < items.length && <Text color={t.color.dim}> ↓ {items.length - off - VISIBLE} more</Text>}

      {items[sel] && (items[sel]!.last_preview || items[sel]!.preview) && (
        <Box marginTop={0}>
          <Text color={t.color.dim} wrap="truncate-end">
            {'  last: '}{items[sel]!.last_preview || items[sel]!.preview}
          </Text>
        </Box>
      )}

      <Text color={t.color.dim}>↑/↓ select · Enter resume · type to search · Esc {query ? 'clear' : 'cancel'}</Text>
    </Box>
  )
}

interface SessionPickerProps {
  gw: GatewayClient
  onCancel: () => void
  onSelect: (id: string) => void
  t: Theme
}
