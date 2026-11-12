// Tests of the template's Claude Code backlog pane.
// Run with: tests/backlog-overlay/run.sh (copies the plugin and this file to a temporary folder).
import { expect, test } from 'claude-code/testing'

const PANE = {
  plugin: 'backlog-overlay',
  component: 'Pane',
  requestId: 'backlog',
  props: {
    title: 'Backlog',
    isFocused: true,
    bodyColumns: 80,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 40 },
    view: {},
  },
} as const

const item = (id: string, status: string, extra: Record<string, unknown> = {}) => ({
  id, title: `Title ${id}`, version: 'v0.1.0', epic: 'EPIC-001', type: 'Task', priority: 'P1', status,
  dependencies: [], acceptance_criteria: ['Criterion'], ...extra,
})

const STORE = {
  versions: [{ id: 'v0.1.0', goal: 'G', state: 'Open' }],
  epics: [{ id: 'EPIC-001', title: 'Base', scope: 'S' }],
  items: [item('TEC-001', 'Todo'), item('TEC-002', 'Todo'), item('TEC-003', 'Done')],
}

/** Answers of `backlog export --json …` by the options after `--json`. */
function cli(answers: Record<string, unknown>) {
  const calls: string[][] = []
  const hook = (_: unknown, e: { argv: readonly string[] }) => {
    calls.push([...e.argv])
    const options = e.argv.slice(4).join(' ')
    const answer = answers[options]
    if (answer === undefined) return { value: { exitCode: 2, stdout: '', stderr: `unexpected ${options}`, isStdoutTruncated: false, isStderrTruncated: false } }
    if (typeof answer === 'string') return { value: { exitCode: 1, stdout: '', stderr: answer, isStdoutTruncated: false, isStderrTruncated: false } }
    return { value: { exitCode: 0, stdout: JSON.stringify(answer), stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  }
  return { hook, calls }
}

const branches = (fetch: string, remotes: string[], items: Record<string, unknown> = {}) => ({ fetch, remotes, items })

function engine(on: any, answers: Record<string, unknown>, opened: unknown[] = []) {
  const { hook, calls } = cli(answers)
  on('command.register', () => ({ value: { command: 'backlog' } }))
  on('ui.open', (_: unknown, e: unknown) => (opened.push(e), { value: { isPlaced: true } }))
  on('ui.close', () => ({ value: undefined }))
  on('session.start', (_: unknown, e: { cwd: string }) => ({ cwd: e.cwd }))
  on('process.run', hook)
  return calls
}

const text = async (ui: any, pattern: RegExp) => (await ui.find({ type: 'Text', text: pattern }))?.text

test('opens on the first Todo item and navigates among matching items', async ($, on) => {
  engine(on, { '': STORE, '--branches --no-fetch': { ...STORE, branches: branches('skipped', []) } })
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    await ui.press({ key: 'reload' })
    expect(await text(ui, /^TEC-001 —/)).toBe('TEC-001 — Title TEC-001')
    expect(await text(ui, /total/)).toContain('1 / 2 (3 total)')
    await ui.press({ key: 'next' })
    expect(await text(ui, /^TEC-002 —/)).toBe('TEC-002 — Title TEC-002')
    await ui.press({ key: 'next' })
    expect(await text(ui, /total/)).toContain('2 / 2 (3 total)')
    await ui.press({ key: 'first' })
    expect(await text(ui, /total/)).toContain('1 / 2')
    await ui.unmount()
  }
})

test('the Status filter cycles and reset restores the defaults', async ($, on) => {
  engine(on, { '': STORE, '--branches --no-fetch': { ...STORE, branches: branches('skipped', []) } })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 'reload' })
  for (const expected of ['In Progress', 'Blocked', 'Done']) {
    await ui.press({ key: 'status' })
    expect(await text(ui, /^Type:/)).toContain(`Status: ${expected}`)
  }
  expect(await text(ui, /^TEC-003 —/)).toBe('TEC-003 — Title TEC-003')
  await ui.press({ key: 'status' })
  await ui.press({ key: 'status' })
  expect(await text(ui, /^Type:/)).toContain('Status: all')
  expect(await text(ui, /total/)).toContain('1 / 3')
  await ui.press({ key: 'reset' })
  expect(await text(ui, /^Type:/)).toContain('Type: all · Priority: all · Status: Todo')
  await ui.unmount()
})

test('states come from item branches, then from the fetch', async ($, on) => {
  const started = item('TEC-001', 'In Progress', { branch: 'task/TEC-001-a' })
  const local = { ...STORE, items: [started, ...STORE.items.slice(1)], branches: branches('skipped', ['origin'], { 'TEC-001': { source: 'task/TEC-001-a', also_in: ['origin/task/TEC-001-b'] } }) }
  const calls = engine(on, { '': STORE, '--branches --no-fetch': local, '--branches': { ...local, branches: { ...local.branches, fetch: 'done' } } })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 'reload' })
  expect(calls.map((argv) => argv.slice(4).join(' '))).toEqual(['', '--branches --no-fetch', '--branches'])
  expect(calls[0]!.slice(0, 4)).toEqual(['python3', '.agents/tools/backlog.py', 'export', '--json'])
  await ui.press({ key: 'status' })
  expect(await text(ui, /^TEC-001 —/)).toBe('TEC-001 — Title TEC-001')
  expect(await text(ui, /^from /)).toBe('from task/TEC-001-a · also in: origin/task/TEC-001-b')
  expect(await text(ui, /fetch/)).toBeUndefined()
  await ui.unmount()
})

test('a failed fetch is shown and keeps the local states', async ($, on) => {
  const local = { ...STORE, branches: branches('skipped', ['origin']) }
  engine(on, { '': STORE, '--branches --no-fetch': local, '--branches': { ...STORE, branches: branches('failed', ['origin']) } })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 'reload' })
  expect(await text(ui, /fetch failed/)).toContain('fetch failed: showing last known state')
  await ui.unmount()
})

test('outside a git repository only the current directory is read', async ($, on) => {
  const calls = engine(on, { '': STORE, '--branches --no-fetch': { ...STORE, branches: branches('none', []) } })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 'reload' })
  expect(calls).toHaveLength(2)
  expect(await text(ui, /total/)).toContain('1 / 2 (3 total)')
  await ui.unmount()
})

test('a CLI error is shown instead of the items', async ($, on) => {
  engine(on, { '': 'error: backlog/ not found' })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 'reload' })
  expect(await text(ui, /Cannot read/)).toContain('error: backlog/ not found')
  await ui.unmount()
})

test('/backlog opens the pane with the keyboard, closed by Escape', async ($, on) => {
  const opened: unknown[] = []
  engine(on, { '': STORE }, opened)
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await $.command.run({ command: 'backlog' })
  expect(opened[0]).toMatchObject({ id: 'backlog', focus: true, closeOnEscape: true })
})
