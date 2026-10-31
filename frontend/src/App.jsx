import { useEffect, useMemo, useState } from 'react';
import { supabase } from './supabaseClient';

const seedIssues = [
  { id: 'CVL-8942', title: 'Deep pothole near the school crossing', location: 'Ward 7 - Main Gate', category: 'Roads & potholes', score: 87, priority: 'Critical', status: 'Open', reports: 12 },
  { id: 'CVL-8891', title: 'Uncollected waste at Sector 4 market', location: 'Sector 4 - Market Street', category: 'Garbage & sanitation', score: 72, priority: 'High', status: 'Open', reports: 8 },
  { id: 'CVL-8816', title: 'Water leak along the footpath', location: 'Adarsh Nagar - Lane 3', category: 'Water supply', score: 64, priority: 'High', status: 'In progress', reports: 6 },
  { id: 'CVL-8710', title: 'Streetlight out near bus terminus', location: 'Bus Terminus - Platform 3', category: 'Streetlights', score: 45, priority: 'Medium', status: 'Open', reports: 5 },
];

function GoogleIcon() {
  return <span className="google-icon" aria-hidden="true">G</span>;
}

function Header({ authenticated, activePage = '', isAdmin = false, onLogout }) {
  return (
    <header className="react-header">
      <a className="react-brand" href="/">
        <span className="brand-symbol" aria-hidden="true">⌂</span>
        <span><strong>Civic<span>Lens</span></strong><small>HACKNOVATE PS 9</small></span>
      </a>
      {authenticated ? (
        <nav className="react-nav" aria-label="Resident navigation">
          <a className={activePage === 'report' ? 'active' : ''} href="/report">Report</a>
          <a className={activePage === 'tracker' ? 'active' : ''} href="/tracker">Tracker</a>
          {isAdmin && <a className={activePage === 'admin' ? 'active' : ''} href="/admin">Admin</a>}
          <button className="header-link" onClick={onLogout}>Logout</button>
        </nav>
      ) : (
        <nav className="react-nav" aria-label="Authentication">
          <a className="active" href="/">Login</a>
          <a href="/#register">Register</a>
        </nav>
      )}
    </header>
  );
}

function Login({ error }) {
  const [credentials, setCredentials] = useState({ email: '', password: '' });
  const [authError, setAuthError] = useState('');
  const [signingIn, setSigningIn] = useState(false);

  async function submitEmailPassword(event) {
    event.preventDefault();
    setSigningIn(true);
    setAuthError('');
    try {
      if (!supabase) throw new Error('Supabase is not configured.');
      const { error: loginError } = await supabase.auth.signInWithPassword(credentials);
      if (loginError) throw loginError;
      window.location.reload();
    } catch (loginError) {
      setAuthError(loginError.message);
    } finally {
      setSigningIn(false);
    }
  }

  return (
    <div className="auth-layout">
      <Header />
      <main className="auth-main-react">
        <section className="auth-card-react" id="register">
          <div className="shield">✓</div>
          <p className="kicker">STATE MUNICIPAL CORPORATION</p>
          <h1>Resident Verification Portal</h1>
          <p className="intro">Sign in to report civic issues and follow them through resolution.</p>
          {error && <div className="error-banner" role="alert">{error}</div>}
          <a className="google-button" href="/auth/google/login"><GoogleIcon /> Continue with Google</a>
          <div className="or-divider"><span>OR</span></div>
          <form className="password-form" onSubmit={submitEmailPassword}>
            <label>Email<input type="email" value={credentials.email} onChange={(event) => setCredentials({ ...credentials, email: event.target.value })} autoComplete="email" required /></label>
            <label>Password<input type="password" value={credentials.password} onChange={(event) => setCredentials({ ...credentials, password: event.target.value })} autoComplete="current-password" minLength="8" required /></label>
            {authError && <div className="error-banner" role="alert">{authError}</div>}
            <button className="primary-button" disabled={signingIn}>{signingIn ? 'Signing in...' : 'Sign in'} <span>→</span></button>
          </form>
          <p className="login-note">Email/password is handled securely by Supabase Auth. Google sign-in remains available as an alternative.</p>
        </section>
      </main>
    </div>
  );
}

function ReportForm({ onCreated }) {
  const [form, setForm] = useState({ category: '', title: '', description: '', photo: null });
  const [status, setStatus] = useState('');
  const [saving, setSaving] = useState(false);

  const update = (event) => setForm({ ...form, [event.target.name]: event.target.value });
  const updatePhoto = (event) => setForm({ ...form, photo: event.target.files?.[0] || null });

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setStatus('');
    try {
      if (!form.photo) throw new Error('Choose an image with EXIF GPS metadata.');
      const payload = new FormData();
      payload.append('category', form.category);
      payload.append('title', form.title);
      payload.append('description', form.description);
      payload.append('photo', form.photo);
      const response = await fetch('/api/reports/upload', {
        method: 'POST',
        body: payload,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Unable to save the report.');
      onCreated({ id: `CVL-${data.report_id}`, title: form.title, category: form.category, location: 'Ward 7 - Jaipur', score: 35, priority: 'Medium', status: 'Open', reports: 1 });
      setForm({ category: '', title: '', description: '', photo: null });
      setStatus('Report submitted successfully.');
    } catch (error) {
      setStatus(error.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel-react report-panel">
      <div className="panel-heading"><div><p className="eyebrow-react">HELP YOUR COMMUNITY</p><h2>Report an issue</h2><p>A photo and location help the right team act faster.</p></div><span className="step-chip">01</span></div>
      <form onSubmit={submit} className="report-form-react">
        <label>Issue category<select name="category" value={form.category} onChange={update} required><option value="">Choose a category</option><option>Roads & potholes</option><option>Garbage & sanitation</option><option>Streetlights</option><option>Water supply</option><option>Drainage & flooding</option></select></label>
        <label>Short description<input name="title" value={form.title} onChange={update} maxLength="160" placeholder="e.g. Deep pothole near the school crossing" required /></label>
        <label>More details<textarea name="description" value={form.description} onChange={update} rows="4" placeholder="What happened? Is anyone at immediate risk?" /></label>
        <label>Geotagged image<input name="photo" type="file" accept="image/jpeg,image/png" onChange={updatePhoto} required /><small className="field-help">JPEG or PNG with EXIF GPS latitude and longitude. Images without GPS are rejected.</small></label>
        <div className="location-note"><span>⌖</span><div><strong>Location comes from image EXIF</strong><small>Coordinates are extracted and normalized on the server.</small></div></div>
        <button className="primary-button" disabled={saving}>{saving ? 'Submitting...' : 'Submit report'} <span>→</span></button>
        {status && <p className="form-status" role="status">{status}</p>}
      </form>
    </section>
  );
}

function Issues({ issues }) {
  return (
    <section className="panel-react issues-panel-react">
      <div className="panel-heading"><div><p className="eyebrow-react">TRANSPARENT TRACKING</p><h2>Nearby issues <span className="count-chip">{issues.length}</span></h2><p>See what your community is waiting on.</p></div><span className="map-chip">Map view</span></div>
      <div className="issue-list-react">
        {issues.map((issue) => <article className="issue-row" key={issue.id}><div><strong>{issue.title}</strong><p>{issue.location} <span>·</span> {issue.reports} reports</p></div><div className="issue-meta-react"><span className={`priority ${issue.priority.toLowerCase()}`}>{issue.priority}</span><span className="status">{issue.status}</span><b>{issue.score}</b></div></article>)}
      </div>
      <div className="tracker-callout"><strong>Every report makes a difference.</strong><span>Issues are grouped and ranked so urgent problems get attention first.</span></div>
    </section>
  );
}

function ReportPage({ user, onLogout }) {
  const userName = user?.name || 'Resident';
  return (
    <div className="dashboard-layout">
      <Header authenticated activePage="report" isAdmin={user?.is_admin} onLogout={onLogout} />
      <main className="dashboard-main">
        <div className="welcome-row"><div><p className="eyebrow-react">JAIPUR · WARD 7</p><h1>Welcome, <em>{userName}</em></h1><p>Report a problem and see how your neighbourhood is progressing.</p></div><div className="signed-in">Verified resident</div></div>
        <div className="dashboard-grid single-panel"><ReportForm onCreated={() => {}} /></div>
      </main>
    </div>
  );
}

function reportTitle(description, category) {
  return description?.split(':')[0] || category || 'Civic issue';
}

function statusLabel(status) {
  return status === 'in_progress' ? 'In progress' : status === 'resolved' ? 'Resolved' : 'Pending';
}

function TrackerPage({ user, onLogout }) {
  const [myReports, setMyReports] = useState([]);
  const [localReports, setLocalReports] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch('/api/reports/my-reports').then((response) => response.json()),
      fetch('/api/reports/locality').then((response) => response.json()),
    ]).then(([mine, local]) => {
      setMyReports(mine.reports || []);
      setLocalReports(local.reports || []);
    }).finally(() => setLoading(false));
  }, []);

  return (
    <div className="dashboard-layout">
      <Header authenticated activePage="tracker" isAdmin={user?.is_admin} onLogout={onLogout} />
      <main className="dashboard-main">
        <div className="welcome-row"><div><p className="eyebrow-react">JAIPUR · WARD 7</p><h1>Your civic tracker</h1><p>Follow your submissions and stay informed about issues near you.</p></div><div className="signed-in">{user?.name || 'Verified resident'}</div></div>
        <div className="tracker-grid">
          <section className="panel-react tracker-panel">
            <div className="panel-heading"><div><p className="eyebrow-react">YOUR SUBMISSIONS</p><h2>My complaints <span className="count-chip">{myReports.length}</span></h2><p>Updates on issues you have reported.</p></div><a className="text-link" href="/report">Raise an issue →</a></div>
            <div className="tracker-list">
              {loading && <p className="empty-state">Loading your complaints...</p>}
              {!loading && myReports.length === 0 && <p className="empty-state">You have not submitted a complaint yet.</p>}
              {myReports.map((report) => <article className="tracker-row" key={report.id}><div><strong>{reportTitle(report.description, report.category)}</strong><p>{report.category} <span>·</span> Submitted {new Date(report.created_at).toLocaleDateString()}</p></div><span className={`status status-${report.status}`}>{statusLabel(report.status)}</span></article>)}
            </div>
          </section>
          <section className="panel-react tracker-panel">
            <div className="panel-heading"><div><p className="eyebrow-react">COMMUNITY WATCH</p><h2>Issues in your locality <span className="count-chip">{localReports.length}</span></h2><p>Recent reports raised by residents around Ward 7.</p></div><span className="map-chip">Ward 7</span></div>
            <div className="tracker-list">
              {loading && <p className="empty-state">Loading locality issues...</p>}
              {!loading && localReports.length === 0 && <p className="empty-state">No locality issues have been reported yet.</p>}
              {localReports.map((report) => <article className="tracker-row" key={report.id}><div><strong>{reportTitle(report.description, report.category)}</strong><p>{report.category} <span>·</span> {new Date(report.created_at).toLocaleDateString()}</p></div><span className={`status status-${report.status}`}>{statusLabel(report.status)}</span></article>)}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}

function AdminPage({ user, onLogout }) {
  const [data, setData] = useState({ alerts: [], reports: [] });
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');

  const load = () => fetch('/api/admin/overview').then((response) => {
    if (!response.ok) throw new Error('Admin access denied.');
    return response.json();
  }).then(setData).catch((error) => setMessage(error.message)).finally(() => setLoading(false));

  useEffect(() => { load(); }, []);

  async function updateStatus(reportId, nextStatus) {
    const response = await fetch(`/api/admin/reports/${reportId}/status`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(nextStatus),
    });
    if (!response.ok) { setMessage('Unable to update report status.'); return; }
    setData((current) => ({ ...current, reports: current.reports.map((report) => report.id === reportId ? { ...report, status: nextStatus } : report) }));
    setMessage('Report status updated.');
  }

  return (
    <div className="dashboard-layout">
      <Header authenticated activePage="admin" isAdmin onLogout={onLogout} />
      <main className="dashboard-main">
        <div className="welcome-row"><div><p className="eyebrow-react">ADMINISTRATION · CIVICLENS</p><h1>Operations control room</h1><p>Prioritize alerts using frequency, severity, and ward population.</p></div><div className="signed-in">{user?.email}</div></div>
        {message && <p className="form-status" role="status">{message}</p>}
        <section className="admin-alert-grid">
          <div className="panel-react admin-panel"><div className="panel-heading"><div><p className="eyebrow-react">PRIORITY ENGINE</p><h2>Alert queue <span className="count-chip">{data.alerts.length}</span></h2><p>Explainable ranking for municipal response.</p></div></div><div className="tracker-list">{loading && <p className="empty-state">Loading alerts...</p>}{!loading && !data.alerts.length && <p className="empty-state">No alerts yet.</p>}{data.alerts.map((alert) => <article className="tracker-row" key={`${alert.ward}-${alert.category}`}><div><strong>{alert.category}</strong><p>{alert.ward} · {alert.reports} reports · population {alert.population == null ? 'not verified' : alert.population.toLocaleString()} · severity {alert.severity} ({alert.severity_source})</p><small className="score-breakdown">Frequency {alert.score_breakdown.frequency_score} · Severity {alert.score_breakdown.severity_score} · Population {alert.score_breakdown.population_score ?? 'n/a'} · {alert.window_days}-day window</small></div><div className="admin-alert-meta"><span className={`priority ${alert.level.toLowerCase()}`}>{alert.level}</span><b>{alert.score}</b></div></article>)}</div></div>
          <div className="panel-react admin-panel"><div className="panel-heading"><div><p className="eyebrow-react">MODERATION QUEUE</p><h2>Resident reports <span className="count-chip">{data.reports.length}</span></h2><p>Move each report through the resident-visible lifecycle.</p></div></div><div className="tracker-list">{data.reports.map((report) => <article className="tracker-row admin-report-row" key={report.id}><div><strong>#{report.id} · {report.title}</strong><p>{report.category} · {report.ward}</p></div><div className="admin-controls"><select value={report.status} onChange={(event) => updateStatus(report.id, { status: event.target.value })} aria-label={`Status for report ${report.id}`}><option value="pending">Pending</option><option value="in_progress">In progress</option><option value="resolved">Resolved</option></select><select value={report.severity || ''} onChange={(event) => updateStatus(report.id, { status: report.status, severity: event.target.value ? Number(event.target.value) : null })} aria-label={`Severity for report ${report.id}`}><option value="">Severity</option><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option><option value="5">5</option></select></div></article>)}</div></div>
        </section>
      </main>
    </div>
  );
}

export default function App() {
  const [session, setSession] = useState({ loading: true, authenticated: false, user: null });
  const error = useMemo(() => new URLSearchParams(window.location.search).get('error'), []);

  useEffect(() => {
    async function loadSession() {
      try {
        const supabaseSession = supabase ? (await supabase.auth.getSession()).data.session : null;
        if (supabaseSession?.access_token) {
          const response = await fetch('/auth/supabase/session', { method: 'POST', headers: { Authorization: `Bearer ${supabaseSession.access_token}` } });
          const data = await response.json();
          if (!response.ok) throw new Error(data.detail || 'Unable to establish Supabase session.');
          setSession({ loading: false, authenticated: true, user: { ...data.user, is_admin: data.user.email?.toLowerCase() === 'akshat.raj25@st.niituniversity.in' } });
          return;
        }
        const response = await fetch('/auth/me');
        const data = await response.json();
        setSession({ loading: false, authenticated: data.authenticated, user: data.user });
      } catch {
        setSession({ loading: false, authenticated: false, user: null });
      }
    }
    loadSession();
  }, []);

  const logout = async () => {
    if (supabase) await supabase.auth.signOut();
    window.location.href = '/auth/logout';
  };

  if (session.loading) return <div className="loading-screen">Loading CivicLens...</div>;
  if (session.authenticated) {
    if (window.location.pathname === '/admin' && session.user?.is_admin) return <AdminPage user={session.user} onLogout={logout} />;
    const page = window.location.pathname === '/tracker' ? 'tracker' : 'report';
    return page === 'tracker'
      ? <TrackerPage user={session.user} onLogout={logout} />
      : <ReportPage user={session.user} onLogout={logout} />;
  }
  return <Login error={error} />;
}
