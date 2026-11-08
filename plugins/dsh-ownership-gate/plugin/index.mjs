/**
 * dsh-ownership-gate —— 第 6 层：目标归属校验闸门
 *
 * 背景：六层授权链里，前五层都有代码驻留（提示词 / 审批 / 沙箱 / 地域闸门 / 工具权限），
 * 唯独第六层「这个目标是不是你的」没有任何实现。本插件把那项判断落成代码：
 *
 *   1. 提供 ownership_prove / ownership_status / ownership_revoke 三个工具，
 *      让「证明归属」从口头承诺变成可执行动作；
 *   2. 提供 ownership_gate_check，在真正发包前判定某目标是否已通过校验；
 *   3. 校验方式：文件校验（在站点根目录放置随机 token）/ DNS TXT 校验 /
 *      本机回环地址自动放行；
 *   4. 所有结论写入 $DSH_HOME/ownership-grants.json，带时间戳与证据，可审计、可撤销。
 *
 * 设计原则：
 *   - 只读网络判断，不主动扫描；
 *   - token 随机生成，一次一用，不写死；
 *   - 未校验的目标一律返回 blocked，附具体缺失项与下一步动作；
 *   - 回环 / .local / 私网本机网段自动视为自有。
 */
import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { randomBytes } from 'node:crypto'
import { homedir } from 'node:os'

export const name = 'dsh-ownership-gate'
export const inject = ['tools']

function dshHome() {
  return process.env.DSH_HOME || join(homedir(), '.dsh')
}

function storePath() {
  return join(dshHome(), 'ownership-grants.json')
}

function loadStore() {
  const p = storePath()
  if (!existsSync(p)) return { version: 1, grants: {}, pending: {} }
  try {
    const raw = JSON.parse(readFileSync(p, 'utf8'))
    if (!raw.grants) raw.grants = {}
    if (!raw.pending) raw.pending = {}
    return raw
  } catch {
    return { version: 1, grants: {}, pending: {} }
  }
}

function saveStore(store) {
  const p = storePath()
  mkdirSync(dirname(p), { recursive: true })
  writeFileSync(p, JSON.stringify(store, null, 2))
}

/** 私有 / 回环网段：视为自有，无需证明 */
function isOwnTarget(host) {
  const h = String(host || '').toLowerCase().trim()
  if (!h) return false
  if (h === 'localhost' || h.endsWith('.localhost') || h.endsWith('.local')) return true
  const m = h.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/)
  if (m) {
    const [a, b] = [Number(m[1]), Number(m[2])]
    if (a === 127) return true
    if (a === 10) return true
    if (a === 192 && b === 168) return true
    if (a === 172 && b >= 16 && b <= 31) return true
    if (a === 169 && b === 254) return true
  }
  if (h === '::1' || h === '[::1]') return true
  return false
}

function normalizeHost(raw) {
  let h = String(raw || '').trim().toLowerCase()
  h = h.replace(/^[a-z][a-z0-9+.-]*:\/\//, '')   // 去协议
  h = h.split('/')[0].split('?')[0].split('#')[0] // 去路径
  const at = h.lastIndexOf('@')
  if (at >= 0) h = h.slice(at + 1)
  if (h.startsWith('[')) {
    const end = h.indexOf(']')
    if (end > 1) return h.slice(1, end)
  }
  h = h.replace(/:\d+$/, '')
  return h.replace(/\.$/, '')
}

async function fetchText(url, timeoutMs = 8000) {
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), timeoutMs)
  try {
    const res = await fetch(url, {
      signal: ctl.signal,
      redirect: 'follow',
      headers: { 'user-agent': 'dsh-ownership-gate/1.0' },
    })
    const body = await res.text()
    return { status: res.status, body: body.slice(0, 4096) }
  } catch (error) {
    return { status: 0, body: '', error: error?.message || String(error) }
  } finally {
    clearTimeout(timer)
  }
}

async function dnsTxtLookup(host) {
  // 用公共 DoH 查 TXT，避免依赖本机 dig
  const url = `https://dns.google/resolve?name=${encodeURIComponent(host)}&type=TXT`
  const r = await fetchText(url)
  if (r.status !== 200) return { ok: false, records: [], error: r.error || `HTTP ${r.status}` }
  try {
    const data = JSON.parse(r.body)
    const records = (data.Answer || [])
      .filter((a) => a.type === 16)
      .map((a) => String(a.data || '').replace(/^"|"$/g, '').replace(/"\s*"/g, ''))
    return { ok: true, records }
  } catch (error) {
    return { ok: false, records: [], error: error?.message || String(error) }
  }
}

export function apply(ctx) {
  const render = (_args, value) => [
    { type: 'text', text: typeof value === 'string' ? value : JSON.stringify(value, null, 2) },
  ]
  const tool = ({ name: toolName, description, parameters, execute }) => ({
    name: toolName,
    description,
    parameters,
    output: { schema: { type: 'object' }, render },
    execute,
  })

  // ---------- 1. 发起归属校验 ----------
  ctx.tools.register(
    tool({
      name: 'ownership_prove',
      description:
        '为目标发起归属校验。生成一次性 token，返回两种验证方式（站点根目录放文件 / DNS TXT 记录）。对本机回环与私网直接判定自有。',
      parameters: {
        type: 'object',
        properties: {
          target: { type: 'string', description: '域名或 IP，例如 example.com、203.0.113.10' },
          port: { type: 'number', description: '可选，非标准端口（如本地靶场 8898）' },
        },
        required: ['target'],
        additionalProperties: false,
      },
      execute: async (args = {}) => {
        const host = normalizeHost(args.target)
        if (!host) return { ok: false, error: 'target 为空或无法解析' }

        if (isOwnTarget(host)) {
          return {
            ok: true,
            host,
            verdict: 'own-network',
            message: '回环 / 私网 / .local 目标，视为自有，无需证明。',
          }
        }

        const token = randomBytes(8).toString('hex')
        const port = Number(args.port) || 0
        const store = loadStore()
        store.pending[host] = {
          token,
          port,
          createdAt: new Date().toISOString(),
          methods: {
            file: { path: `/.dsh-verify-${token}.txt`, content: `ok-${token}` },
            dns: { record: `dsh-verify=${token}`, type: 'TXT', name: host },
          },
        }
        saveStore(store)

        return {
          ok: true,
          host,
          token,
          verdict: 'pending',
          options: [
            {
              method: 'file',
              steps: [
                `在 ${host} 的站点根目录放置文件 /.dsh-verify-${token}.txt`,
                `文件内容：ok-${token}`,
                '然后调用 ownership_check',
              ],
              verifyUrl: `http://${host}${port ? ':' + port : ''}/.dsh-verify-${token}.txt`,
            },
            {
              method: 'dns',
              steps: [
                `为 ${host} 添加 TXT 记录：dsh-verify=${token}`,
                '然后调用 ownership_check',
              ],
            },
          ],
          note: '任选一种完成即可。token 一次性，重新 prove 会作废旧 token。',
        }
      },
    })
  )

  // ---------- 2. 校验 ----------
  ctx.tools.register(
    tool({
      name: 'ownership_check',
      description:
        '复核归属证据：抓取站点根目录的校验文件，或查询 DNS TXT 记录，与未完成的 token 比对。通过后写入 grants。',
      parameters: {
        type: 'object',
        properties: {
          target: { type: 'string', description: '要复核的域名或 IP' },
          method: { type: 'string', enum: ['file', 'dns', 'both'], description: '默认 both' },
        },
        required: ['target'],
        additionalProperties: false,
      },
      execute: async (args = {}) => {
        const host = normalizeHost(args.target)
        const method = args.method || 'both'
        const store = loadStore()

        if (isOwnTarget(host)) {
          return { ok: true, host, verdict: 'own-network', message: '自有网段，无需验证。' }
        }
        if (store.grants[host] && store.grants[host].verdict === 'verified') {
          return { ok: true, host, verdict: 'verified', cached: true, grant: store.grants[host] }
        }

        const pending = store.pending[host]
        if (!pending) {
          return {
            ok: false,
            host,
            verdict: 'no-pending',
            message: '没有待校验记录。先调用 ownership_prove 生成 token。',
          }
        }

        const evidence = {}

        if (method === 'file' || method === 'both') {
          const path = `/.dsh-verify-${pending.token}.txt`
          const portPart = pending.port ? ':' + pending.port : ''
          const url = `http://${host}${portPart}${path}`
          const r = await fetchText(url)
          const hit = r.status === 200 && r.body.includes(pending.token)
          evidence.file = { url, status: r.status, hit, error: r.error }
        }

        if (method === 'dns' || method === 'both') {
          const d = await dnsTxtLookup(host)
          const hit = d.records.some((rec) => rec.includes(`dsh-verify=${pending.token}`))
          evidence.dns = { records: d.records, hit, error: d.error }
        }

        const verified = Object.values(evidence).some((e) => e && e.hit)

        if (verified) {
          store.grants[host] = {
            verdict: 'verified',
            verifiedAt: new Date().toISOString(),
            token: pending.token,
            evidence,
          }
          delete store.pending[host]
          saveStore(store)
          return { ok: true, host, verdict: 'verified', evidence }
        }

        return {
          ok: false,
          host,
          verdict: 'failed',
          evidence,
          message: '证据不匹配。确认文件已可公网访问，或 TXT 已生效（DNS 传播可能延迟）。',
        }
      },
    })
  )

  // ---------- 3. 判定闸门 ----------
  ctx.tools.register(
    tool({
      name: 'ownership_gate_check',
      description:
        '发包前判定：该目标是否已通过归属校验。返回 allowed / blocked 及原因。这是我方执行层的准入闸门。',
      parameters: {
        type: 'object',
        properties: {
          target: { type: 'string', description: '要判定的目标' },
        },
        required: ['target'],
        additionalProperties: false,
      },
      execute: async (args = {}) => {
        const host = normalizeHost(args.target)
        if (isOwnTarget(host)) {
          return {
            ok: true,
            host,
            decision: 'allowed',
            reason: 'own-network',
            detail: '回环 / 私网 / .local，视为自有资产。',
          }
        }
        const store = loadStore()
        const g = store.grants[host]
        if (g && g.verdict === 'verified') {
          return {
            ok: true,
            host,
            decision: 'allowed',
            reason: 'ownership-verified',
            verifiedAt: g.verifiedAt,
          }
        }
        return {
          ok: false,
          host,
          decision: 'blocked',
          reason: 'ownership-unverified',
          nextStep: `调用 ownership_prove({ target: "${host}" }) 获取校验方式；或提供书面授权说明本次为已授权测试。`,
        }
      },
    })
  )

  // ---------- 4. 状态与撤销 ----------
  ctx.tools.register(
    tool({
      name: 'ownership_status',
      description: '查看已通过校验的目标清单与待校验项。',
      parameters: { type: 'object', properties: {}, additionalProperties: false },
      execute: async () => {
        const store = loadStore()
        return {
          ok: true,
          storePath: storePath(),
          verified: Object.entries(store.grants).map(([host, g]) => ({
            host,
            verifiedAt: g.verifiedAt,
            methods: Object.keys(g.evidence || {}).filter((k) => g.evidence?.[k]?.hit),
          })),
          pending: Object.entries(store.pending).map(([host, p]) => ({
            host,
            createdAt: p.createdAt,
            token: p.token,
          })),
        }
      },
    })
  )

  ctx.tools.register(
    tool({
      name: 'ownership_revoke',
      description: '撤销某个目标的归属授权。',
      parameters: {
        type: 'object',
        properties: { target: { type: 'string' } },
        required: ['target'],
        additionalProperties: false,
      },
      execute: async (args = {}) => {
        const host = normalizeHost(args.target)
        const store = loadStore()
        const had = Boolean(store.grants[host] || store.pending[host])
        delete store.grants[host]
        delete store.pending[host]
        saveStore(store)
        return { ok: true, host, revoked: had }
      },
    })
  )
}
