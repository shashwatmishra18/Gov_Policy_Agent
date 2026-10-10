import { useEffect, useState, type FormEvent } from 'react'
import Foundation from './App'
import DocumentAdmin from './DocumentAdmin'
import Search from './Search'
import Ask from './Ask'
import Analytics from './Analytics'
import AnswerLibrary from './AnswerLibrary'
import RecordPage from './RecordPage'
import { translate } from './ui'
import { authorized, login, logout, register, restoreSession, subscribe, type User } from './auth'

const publicDemo = import.meta.env.VITE_PUBLIC_DEMO === 'true'

const inputClass = 'mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 focus:outline-teal-700'
const buttonClass = 'rounded-lg bg-teal-900 px-5 py-3 text-sm font-semibold text-white disabled:opacity-50'
const messageOf = (error: unknown) => error instanceof Error ? error.message : 'Request failed. Try again.'

export default function AuthApp() {
  const [user, setUser] = useState<User | null>(null)
  const [restoring, setRestoring] = useState(true)
  const [page, setPage] = useState(location.hash.slice(1) || 'home')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => subscribe(setUser), [])
  useEffect(() => {
    let disposed = false
    restoreSession().catch((failure: unknown) => { if (!disposed) setError(messageOf(failure)) })
      .finally(() => { if (!disposed) setRestoring(false) })
    return () => { disposed = true }
  }, [])
  useEffect(() => {
    const onHash = () => { setPage(location.hash.slice(1) || 'home'); setError('') }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  async function signOut() {
    setBusy(true); setError('')
    try { await logout(); location.hash = 'login' } catch (failure) { setError(`Logout not completed: ${messageOf(failure)}`) }
    finally { setBusy(false) }
  }
  const t=user?translate(user):(en:string,_hi:string)=>en
  const [path,query]=page.split('?')
  const [route,id]=path.split('/')
  const initialPage=Math.max(1,Number(new URLSearchParams(query).get('page'))||1)
  const links=[['ask','Ask','प्रश्न'],['search','Search','खोज'],['history','History','इतिहास'],['saved','Saved','सहेजे उत्तर'],['account','Account','खाता']]
  return <>
    <a className="skip-link" href="#main-content" onClick={e=>{e.preventDefault();document.getElementById('main-content')?.focus()}}>{t('Skip to content','मुख्य भाग पर जाएँ')}</a>
    <header className="border-b bg-white"><div className="mx-auto max-w-5xl px-5 py-4"><a className="font-semibold text-lg no-underline" href="#home">Government Policy Assistant</a><p className="muted text-sm">GOV-CS-028 · {t('Student project · reviewed historical sources','छात्र परियोजना · जाँचे गए ऐतिहासिक स्रोत')}</p>
    <nav aria-label={t('Main navigation','मुख्य नेविगेशन')} className="mt-4 flex flex-wrap items-center gap-3">
      {user? <>{links.map(([key,en,hi])=><a className="nav-link" aria-current={route===key?'page':undefined} key={key} href={`#${key}`}>{t(en,hi)}</a>)}{user.role==='admin'&&!publicDemo&&<><a className="nav-link" aria-current={route==='admin'?'page':undefined} href="#admin">{t('Admin','प्रशासन')}</a><a className="nav-link" aria-current={route==='analytics'?'page':undefined} href="#analytics">{t('Analytics','आँकड़े')}</a></>}<button disabled={busy} onClick={()=>void signOut()}>{t('Logout','लॉग आउट')}</button></>:<><a href="#login">Login</a>{!publicDemo&&<a href="#register">Register</a>}</>}
    </nav></div></header>
    <main id="main-content" tabIndex={-1} className="mx-auto max-w-5xl px-5 py-8">
    {error&&<p role="alert" className="notice mb-4">{error}</p>}
    {restoring?<p role="status">{t('Restoring session…','सत्र खुल रहा है…')}</p>:route==='home'?<section className="space-y-4"><h1>{t('Explore reviewed policy documents','जाँचे गए नीति दस्तावेज़ देखें')}</h1><p>{t('Search exact passages and ask questions about the reviewed historical corpus. Answers include source evidence and the limits of automated checks.','जाँचे गए ऐतिहासिक दस्तावेज़ों में पाठ खोजें और प्रश्न पूछें। उत्तर में स्रोत के साक्ष्य और स्वचालित जाँच की सीमाएँ दिखाई जाती हैं।')}</p><a href={user?'#ask':'#login'}>{t(user?'Ask a question':'Sign in to start','प्रश्न पूछें')}</a></section>
    :publicDemo&&['system','admin','analytics','register'].includes(route)?<p>{t('This page is available only in the private local installation.','यह पृष्ठ सिर्फ निजी स्थानीय स्थापना में उपलब्ध है।')}</p>:route==='system'?<Foundation/>:route==='login'||route==='register'?<AuthForm kind={route} onLogin={()=>{location.hash='ask'}}/>
    :!user?<section><h1>Sign in required</h1><p>This page requires an active session.</p><a href="#login">Login</a></section>
    :route==='ask'?<Ask user={user}/>:route==='search'?<Search user={user}/>
    :route==='history'||route==='saved'?id?<RecordPage key={id} user={user} id={id} library={route} backPage={initialPage}/>:<AnswerLibrary key={route} user={user} saved={route==='saved'} initialPage={initialPage}/>
    :route==='admin'?<AdminPage/>:route==='account'?<AccountPage user={user} onUpdate={setUser}/>:route==='analytics'?<Analytics user={user}/>:<p>{t('Page not found. Choose a page from the navigation.','पृष्ठ नहीं मिला। नेविगेशन से पृष्ठ चुनें।')}</p>}
    </main><footer className="mx-auto max-w-5xl border-t px-5 py-5 muted text-sm"><p>{t('Academic prototype. Historical evidence does not establish present eligibility.','शैक्षणिक परियोजना। ऐतिहासिक साक्ष्य वर्तमान पात्रता साबित नहीं करते।')}</p>{!publicDemo&&<a href="#system">{t('System status','सिस्टम स्थिति')}</a>}</footer>
  </>
}

function AuthForm({ kind, onLogin }: { kind: 'login' | 'register'; onLogin: () => void }) {
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  useEffect(() => { setPassword(''); setError(''); setNotice('') }, [kind])
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('')
    try {
      if (kind === 'register') {
        await register(email, username, password); setPassword('')
        setNotice('Account created. Use the Login page to sign in.')
      } else { await login(email, password); setPassword(''); onLogin() }
    } catch (failure) { setError(messageOf(failure)) }
    finally { setBusy(false) }
  }
  return <section className="rounded-2xl border border-slate-200 bg-white p-7">
    <h1 className="text-3xl font-semibold">{kind === 'register' ? 'Create your account' : 'Welcome back'}</h1>
    <p className="mt-3 text-sm text-slate-600">{kind === 'register' ? 'Public registration creates a normal user account.' : 'Sign in with your registered email and password.'}</p>
    <form onSubmit={(event) => void submit(event)} className="mt-6 space-y-5">
      <label className="block">Email<input className={inputClass} type="email" required maxLength={254} autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
      {kind === 'register' && <label className="block">Username<input className={inputClass} required minLength={3} maxLength={32} pattern="[A-Za-z0-9_]{3,32}" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} /><span className="text-xs text-slate-500">3–32 letters, digits or underscores. Stored in lowercase.</span></label>}
      <label className="block">Password<input className={inputClass} type="password" required minLength={kind === 'register' ? 12 : 1} maxLength={128} autoComplete={kind === 'register' ? 'new-password' : 'current-password'} value={password} onChange={(event) => setPassword(event.target.value)} /><span className="text-xs text-slate-500">{kind === 'register' && '12–128 characters; passwords are never truncated.'}</span></label>
      {error && <p role="alert" className="text-sm text-red-800">{error}</p>}
      {notice && <p role="status" className="text-sm text-teal-800">{notice} <a href="#login" className="underline">Login</a></p>}
      <button className={buttonClass} disabled={busy}>{busy ? 'Please wait…' : kind === 'register' ? 'Register' : 'Login'}</button>
    </form>
  </section>
}

function AccountPage({ user, onUpdate }: { user: User; onUpdate: (user: User) => void }) {
  const t=translate(user)
  const [language, setLanguage] = useState(user.preferred_language)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    let disposed = false
    authorized<User>('/auth/me').then((result) => { if (!disposed) onUpdate(result) })
      .catch((failure: unknown) => { if (!disposed) setError(messageOf(failure)) })
    return () => { disposed = true }
  }, [onUpdate])
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('')
    try { const result = await authorized<User>('/auth/me', { method: 'PATCH', body: JSON.stringify({ preferred_language: language }) }); onUpdate(result); setNotice('Profile saved.') }
    catch (failure) { setError(messageOf(failure)) } finally { setBusy(false) }
  }
  return <section className="rounded-2xl border border-slate-200 bg-white p-7"><h1 className="text-3xl font-semibold">{t('Your account','आपका खाता')}</h1>
    <dl className="mt-6 space-y-3"><div><dt className="text-sm text-slate-500">Username</dt><dd>{user.username}</dd></div><div><dt className="text-sm text-slate-500">Email</dt><dd className="break-all">{user.email}</dd></div><div><dt className="text-sm text-slate-500">Role</dt><dd>{user.role}</dd></div></dl>
    <form className="mt-6 space-y-4" onSubmit={(event) => void save(event)}><label className="block">{t('Preferred language','पसंदीदा भाषा')}<select className={inputClass} value={language} onChange={(event) => setLanguage(event.target.value)}><option value="en">English</option><option value="hi">हिन्दी</option><option value="hinglish">Hinglish</option></select></label><button className={buttonClass} disabled={busy}>{busy ? t('Saving…','सहेज रहा है…') : t('Save preference','पसंद सहेजें')}</button></form>
    {error && <p role="alert" className="mt-4 text-red-800">{error}</p>}{notice && <p role="status" className="mt-4 text-teal-800">{notice}</p>}
  </section>
}

function AdminPage() {
  const [status, setStatus] = useState('Checking server authorization…')
  useEffect(() => {
    let disposed = false
    authorized<{ authorized: boolean; role: string }>('/auth/admin/access')
      .then((result) => { if (!disposed) setStatus(result.authorized ? 'Admin access confirmed by the backend.' : 'Access denied.') })
      .catch((failure: unknown) => { if (!disposed) setStatus(messageOf(failure)) })
    return () => { disposed = true }
  }, [])
  return <section><h1 className="text-3xl font-semibold">Admin access</h1><p role="status" className="mt-5">{status}</p>{status === 'Admin access confirmed by the backend.' && <DocumentAdmin />}</section>
}
