import { lazy, Suspense, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import {
  Activity,
  ArrowUpRight,
  Bell,
  CircleHelp,
  Database,
  FileSearch,
  LayoutDashboard,
  ListChecks,
  Loader2,
  LogOut,
  Menu,
  Moon,
  Plus,
  Settings2,
  ShieldCheck,
  Sparkles,
  Sun,
} from 'lucide-react'
import { api, ApiError, post, setCsrf } from './lib/api'
import type { System, User } from './lib/types'
import { Brand, ErrorState, Loading } from './components/shared'
import { Button } from './components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from './components/ui/dialog'

const Overview = lazy(() => import('./pages/Overview'))
const Investigations = lazy(() => import('./pages/Investigations'))
const InvestigationView = lazy(() => import('./pages/InvestigationView'))
const Sources = lazy(() => import('./pages/Sources'))
const Actions = lazy(() => import('./pages/Actions'))
const Workspace = lazy(() => import('./pages/Workspace'))
const navigation = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/investigations', label: 'Investigations', icon: FileSearch },
  { to: '/sources', label: 'Data sources', icon: Database },
  { to: '/actions', label: 'Actions & monitoring', icon: ListChecks },
]

function Login({
  onLogin,
  themeControl,
}: {
  onLogin: (user: User) => void
  themeControl: ReactNode
}) {
  const [email, setEmail] = useState('founder@sanketai.local')
  const [password, setPassword] = useState('')
  const mutation = useMutation({
    mutationFn: () => post<User>('/auth/login', { email, password }),
    onSuccess: onLogin,
  })
  function submit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate()
  }
  return (
    <div className="login-layout">
      <section className="login-story">
        <Brand />
        <div>
          <span className="eyebrow text-mint">LESS GUESSWORK. MORE CLARITY.</span>
          <h1>
            Follow the signals.
            <br />
            <span>Find the reason.</span>
          </h1>
          <p>An autonomous investigator for the questions your dashboard can’t answer.</p>
          <div className="login-proof">
            <div>
              <FileSearch size={20} />
              <p>Trace every insight</p>
            </div>
            <div>
              <Activity size={20} />
              <p>Connect the signals</p>
            </div>
            <div>
              <ShieldCheck size={20} />
              <p>Stay in control</p>
            </div>
          </div>
        </div>
        <p className="text-xs text-white/65">Built for businesses moving Nepal forward.</p>
      </section>
      <section className="login-panel relative">
        <div className="absolute right-5 top-5">{themeControl}</div>
        <div className="w-full max-w-sm">
          <h2 className="mt-3 text-3xl font-semibold tracking-tight">Welcome to SanketAI</h2>
          <p className="mb-8 mt-3 text-sm leading-6 text-muted-foreground">
            Sign in to connect the evidence and understand what’s happening in your business.
          </p>
          <form onSubmit={submit} className="space-y-5">
            <div>
              <label htmlFor="email">Email address</label>
              <input
                id="email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div>
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                maxLength={1024}
              />
            </div>
            {mutation.error && <ErrorState error={mutation.error} />}
            <Button type="submit" className="w-full" disabled={mutation.isPending}>
              {mutation.isPending ? <Loader2 className="animate-spin" /> : null}Sign in to workspace
              <ArrowUpRight />
            </Button>
          </form>
          <p className="mt-8 text-xs leading-5 text-muted-foreground">
            Use the administrator email and password configured during setup. Your business data
            stays in your workspace.
          </p>
        </div>
      </section>
    </div>
  )
}

function Shell({ user, themeControl }: { user: User; themeControl: ReactNode }) {
  const client = useQueryClient()
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const system = useQuery({
    queryKey: ['system'],
    queryFn: () => api<System>('/system'),
    refetchInterval: 30000,
  })
  const logout = useMutation({
    mutationFn: () => post('/auth/logout'),
    onSuccess: () => {
      setCsrf('')
      client.clear()
      client.setQueryData(['session'], null)
    },
  })
  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])
  const active =
    navigation.find((item) =>
      item.to === '/' ? location.pathname === '/' : location.pathname.startsWith(item.to),
    )?.label || 'Workspace'
  const sidebar = (
    <>
      <Link to="/" aria-label="SanketAI home" className="px-6 pt-7 pb-7">
        <Brand />
      </Link>
      <div className="mx-4 mb-6 rounded-lg border border-white/10 bg-white/5 px-3 py-3">
        <div className="flex items-center gap-3">
          <span className="flex size-9 items-center justify-center rounded-lg bg-accent text-xs font-bold text-accent-foreground">
            <Database size={17} />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold text-white">My business workspace</p>
            <p className="mt-1 text-[11px] text-white/65">Business intelligence</p>
          </div>
        </div>
      </div>
      <p className="px-6 pb-3 text-[9px] font-semibold tracking-[1.8px] text-white/65">WORKSPACE</p>
      <nav aria-label="Main navigation" className="space-y-1 px-3">
        {navigation.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <item.icon size={17} />
            {item.label}
            {item.to === '/investigations' && (
              <span className="ml-auto text-[9px] tracking-wider opacity-40">AGENT</span>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="mx-3 mt-7 border-t border-white/10 pt-5">
        <NavLink
          to="/workspace"
          className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
        >
          <Settings2 size={17} />
          Workspace & audit
        </NavLink>
        <button className="nav-item w-full" onClick={() => setHelpOpen(true)}>
          <CircleHelp size={17} />
          How SanketAI works
          <ArrowUpRight size={13} className="ml-auto opacity-40" />
        </button>
      </div>
      <div className="mt-auto px-4 pb-4">
        <div className="agent-sidebar">
          <span className="flex size-8 items-center justify-center rounded-lg bg-mint/10 text-mint">
            <Activity size={16} />
          </span>
          <div>
            <p className="text-xs font-medium text-white/90">Investigation engine</p>
            <p className="mt-1 flex items-center gap-1.5 text-[11px] text-white/65">
              <span
                className={`size-1.5 rounded-full ${system.data?.worker_online ? 'bg-mint' : 'bg-warning-bg'}`}
              />
              {system.data?.worker_online ? 'Worker connected' : 'Worker not connected'}
            </p>
          </div>
        </div>
        <div className="mt-4 flex items-center gap-2.5 border-t border-white/10 pt-4">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/10 text-xs">
            {user.email.slice(0, 2).toUpperCase()}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[11px] text-white/80">{user.email}</p>
            <p className="mt-0.5 text-[11px] text-white/65">Workspace administrator</p>
          </div>
          <button
            aria-label="Sign out"
            onClick={() => logout.mutate()}
            disabled={logout.isPending}
            className="rounded-md p-1.5 text-white/65 hover:text-white"
          >
            <LogOut size={15} />
          </button>
        </div>
        {logout.error && (
          <p role="alert" className="mt-2 text-xs text-danger-bg">
            {logout.error.message}
          </p>
        )}
      </div>
    </>
  )
  return (
    <div className="app-layout">
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      <aside className="sidebar hidden lg:flex">{sidebar}</aside>
      <Dialog open={mobileOpen} onOpenChange={setMobileOpen}>
        <DialogContent className="mobile-sidebar">
          <DialogTitle className="sr-only">Workspace navigation</DialogTitle>
          <DialogDescription className="sr-only">
            Navigate your SanketAI workspace.
          </DialogDescription>
          {sidebar}
        </DialogContent>
      </Dialog>
      <div className="main-layout">
        <header className="topbar">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              aria-label="Open navigation"
              onClick={() => setMobileOpen(true)}
            >
              <Menu />
            </Button>
            <span className="hidden text-xs text-muted-foreground sm:inline">Workspace</span>
            <span className="hidden text-muted-foreground sm:inline">/</span>
            <span className="text-xs font-medium">{active}</span>
          </div>
          <div className="flex items-center gap-2 sm:gap-4">
            {themeControl}
            <span className="hidden items-center gap-2 text-[11px] text-muted-foreground sm:flex">
              <span className="size-1.5 rounded-full bg-primary" />
              Private workspace
            </span>
            <Link
              to="/actions"
              aria-label="View pending actions"
              className="rounded-md p-2 text-muted-foreground hover:bg-muted"
            >
              <Bell size={17} />
            </Link>
            <span className="h-5 w-px bg-border" />
            <Link
              to="/investigations?new=1"
              className="flex h-9 items-center gap-2 rounded-lg bg-primary px-3 text-xs font-semibold text-primary-foreground hover:bg-primary-hover"
            >
              <Plus size={15} />
              <span className="hidden sm:inline">New investigation</span>
            </Link>
          </div>
        </header>
        <main id="main-content" className="page-content">
          <Suspense fallback={<Loading />}>
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/investigations" element={<Investigations />} />
              <Route path="/investigations/:id" element={<InvestigationView />} />
              <Route path="/sources" element={<Sources />} />
              <Route path="/actions" element={<Actions />} />
              <Route path="/workspace" element={<Workspace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
          <footer className="page-footer">
            <span>SanketAI · Follow the evidence.</span>
            <span className="flex items-center gap-1.5">
              <ShieldCheck size={12} />
              Human judgment stays in the loop
            </span>
          </footer>
        </main>
      </div>
      <Dialog open={helpOpen} onOpenChange={setHelpOpen}>
        <DialogContent>
          <DialogTitle className="text-xl font-semibold">
            From a signal to a supported explanation
          </DialogTitle>
          <DialogDescription className="text-sm leading-6 text-muted-foreground">
            SanketAI investigates a question or scans your business for unusual changes.
          </DialogDescription>
          <ol className="space-y-5">
            {[
              [
                'Connect evidence',
                'Upload 56+ days of business CSVs or Excel files, or connect a Google Sheet. Add supplier letters, complaint logs and notes as PDF, text or Markdown.',
              ],
              [
                'Let the agent investigate',
                'It compares the latest 28 days with the 28 days before, tests competing hypotheses, and searches your documents by meaning for supporting and contradictory evidence.',
              ],
              [
                'Challenge the conclusion',
                'Run a second pass against the same source snapshot. Confidence describes evidence strength, not a probability.',
              ],
              [
                'Approve and monitor',
                'Approve an internal operations task. Upload a newer outcome period to check the KPI and trigger follow-up if needed.',
              ],
            ].map(([title, description], i) => (
              <li key={title} className="flex gap-3">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                  {i + 1}
                </span>
                <div>
                  <h3 className="text-sm font-semibold">{title}</h3>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">{description}</p>
                </div>
              </li>
            ))}
          </ol>
          <div>
            <h3 className="text-sm font-semibold">What it can explain</h3>
            <ul className="mt-2 space-y-2 text-sm leading-6 text-muted-foreground">
              <li>
                <span className="font-medium text-foreground">Sales drops:</span> supplier delays
                that caused stockouts and lost sales.
              </li>
              <li>
                <span className="font-medium text-foreground">Falling margin:</span> courier or
                supplier price rises, with a chart of where the margin went.
              </li>
              <li>
                <span className="font-medium text-foreground">Other questions:</span> the AI still
                investigates, but no measured explanation is built in, so check the evidence.
              </li>
            </ul>
          </div>
          <p className="rounded-lg bg-muted p-3 text-xs leading-5 text-muted-foreground">
            <Sparkles className="mr-2 inline size-4" />
            AI model reasoning is labeled separately from deterministic analysis. Observational
            evidence cannot prove causality on its own.
          </p>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default function App() {
  const [dark, setDark] = useState(false)
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute('content', dark ? '#08111F' : '#0B1424')
  }, [dark])
  const themeControl = (
    <Button
      variant="ghost"
      size="icon"
      aria-label={dark ? 'Use light theme' : 'Use dark theme'}
      onClick={() => setDark(!dark)}
    >
      {dark ? <Sun /> : <Moon />}
    </Button>
  )
  const client = useQueryClient()
  const session = useQuery({
    queryKey: ['session'],
    queryFn: async () => {
      try {
        const user = await api<User>('/auth/me')
        setCsrf(user.csrf_token)
        return user
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null
        throw error
      }
    },
    retry: false,
    staleTime: 60000,
  })
  useEffect(() => {
    const expired = () => {
      setCsrf('')
      client.clear()
      client.setQueryData(['session'], null)
    }
    window.addEventListener('sanket:session-expired', expired)
    return () => window.removeEventListener('sanket:session-expired', expired)
  }, [client])
  if (session.isPending) return <Loading label="Opening your workspace…" />
  if (session.error)
    return (
      <div className="mx-auto max-w-lg p-8">
        <ErrorState error={session.error} retry={() => session.refetch()} />
      </div>
    )
  if (!session.data)
    return (
      <Login
        themeControl={themeControl}
        onLogin={(user) => {
          setCsrf(user.csrf_token)
          client.setQueryData(['session'], user)
        }}
      />
    )
  return <Shell user={session.data} themeControl={themeControl} />
}
