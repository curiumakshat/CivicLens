# CivicLens Authentication Portal

A dedicated, production-grade login service with **Real Google OAuth 2.0** and **Real Gmail SMTP OTP Verification**.

---

## Why Real Google Auth & Real Gmail OTP Need Configuration

Both Google OAuth and Gmail email dispatch are **protected third-party Google services**:

1. **Google OAuth 2.0 (Google Sign-In)**:
   - Google requires every application to be registered in the **Google Cloud Console**.
   - You must have a registered `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.
   - Google verifies that the request originates from an authorized domain (e.g. `http://localhost:8000`).
   - Without these credentials, Google's servers reject the sign-in request with an `origin_mismatch` or `invalid_client` error.

2. **Gmail SMTP OTP Dispatch (Real Email Sending)**:
   - Sending an actual email to someone's Gmail inbox requires communicating with Google's mail server (`smtp.gmail.com:587`).
   - Standard Google account passwords cannot be used directly with SMTP due to 2-Factor Authentication policies.
   - Google requires a dedicated **16-character App Password** (`SMTP_PASSWORD`) generated from your Google Account security settings.

---

## Quick Setup: How to Enable Real Credentials in 2 Minutes

Create a `.env` file in the project root (or edit the existing `.env`):

```env
# 1. REAL GMAIL SMTP (To send real verification emails to inboxes)
SMTP_EMAIL=yourname@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx

# 2. REAL GOOGLE OAUTH2 (For real Google Sign-In button)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
```

### How to get Gmail App Password:
1. Go to [Google Account Security](https://myaccount.google.com/security).
2. Ensure **2-Step Verification** is turned ON.
3. Search or navigate to **App passwords** ([direct link](https://myaccount.google.com/apppasswords)).
4. Create a new app password named "CivicLens" and copy the 16-character code into `SMTP_PASSWORD`.

### How to get Google OAuth Client ID:
1. Go to [Google Cloud Console Credentials](https://console.cloud.google.com/apis/credentials).
2. Click **Create Credentials** &rarr; **OAuth client ID** &rarr; **Web application**.
3. Under **Authorized JavaScript origins**, add: `http://localhost:8000` and `http://127.0.0.1:8000`.
4. Under **Authorized redirect URIs**, add: `http://localhost:8000/auth/google/callback`.
5. Copy the Client ID and Secret into your `.env`.

---

## Features Built

- **Real Google Sign-In**:
  - Official Google Identity Services (GIS) button + One-Tap prompt.
  - Standard OAuth 2.0 redirect flow (`/auth/google/login` & `/auth/google/callback`).
  - Google tokeninfo API verification.
- **Real Gmail OTP Dispatch**:
  - Sends authentic 6-digit codes via `smtp.gmail.com` (TLS on port 587).
  - Clean HTML email template delivered directly to user's inbox.
  - Auto-advance 6-digit boxes with paste & backspace support.
- **Graceful Fallback Mode**:
  - When keys are not yet configured in `.env`, the UI clearly indicates **Demo Mode** via status pills, and provides immediate 1-click test accounts and on-screen demo OTP codes so the app always functions smoothly without crashing.
- **Verified Dashboard**:
  - Displays authenticated user information, profile picture/avatar, verification badge, and sign-out control.

---

## How to Run

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

## Geotagged image reports

`POST /api/reports/upload` accepts only JPEG or PNG uploads that contain valid EXIF GPS latitude and longitude. The server validates the actual image bytes, rejects missing or invalid GPS metadata, extracts coordinates to six decimal places, stores the original file under `uploads/`, and saves the normalized coordinates on the report. The React report form uses this multipart endpoint and requires an image.

Vercel uses its writable temporary directory for uploaded files; production deployments should move images to object storage because temporary serverless storage is not persistent.

## React frontend

The active web interface is now built with React and Vite. Install and build it with:

```powershell
cd frontend
npm install
npm run build
cd ..
python -m uvicorn app.main:app --reload
```

After Google authentication, `/tracker` opens the React dashboard with the Report Issue form and current Issues list visible immediately. FastAPI serves `frontend/dist` when it exists; the older Jinja templates remain only as a local fallback until the React build is created.

## Vercel deployment note

Vercel functions have a read-only deployment filesystem. CivicLens now falls back to `/tmp/civiclens.db` when deployed without a database URL so the app can start, but that database is ephemeral. For persistent users and reports, configure `CIVICLENS_DATABASE_URL` or `DATABASE_URL` in Vercel with a PostgreSQL/Supabase connection string. The `psycopg` driver is included in `requirements.txt`.
