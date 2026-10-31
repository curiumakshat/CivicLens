/**
 * CivicLens Authentication JavaScript
 * Real Google OAuth2 + Real Gmail SMTP OTP Verification
 */

const emailInput = document.querySelector('#email-input');
const sendOtpBtn = document.querySelector('#send-otp-btn');
const otpBoxes = [...document.querySelectorAll('.digit-box')];
const verifySubmitBtn = document.querySelector('#verify-submit-btn');
const flowStatus = document.querySelector('#flow-status');
const resendBtn = document.querySelector('#resend-code-btn');
const demoBanner = document.querySelector('#demo-code-banner');
const demoDisplay = document.querySelector('#demo-code-display');
const autofillBtn = document.querySelector('#autofill-btn');
const otpForm = document.querySelector('#otp-flow-form');

// Google modal elements
const googleQuickBtn = document.querySelector('#google-quick-btn');
const googleModal = document.querySelector('#google-picker-modal');
const closeGoogleModal = document.querySelector('#close-google-modal');
const profileBtns = document.querySelectorAll('.profile-btn');
const customGoogleEmail = document.querySelector('#custom-google-email');
const customGoogleSubmit = document.querySelector('#custom-google-submit');

// Setup toggle
const toggleSetupHelp = document.querySelector('#toggle-setup-help');
const setupInstructions = document.querySelector('#setup-instructions');
const setupChevron = document.querySelector('#setup-chevron');

let resendTimer = null;
let otpDispatched = false;

function setStatus(msg, type = '') {
  if (!flowStatus) return;
  flowStatus.textContent = msg;
  flowStatus.className = `flow-status ${type}`;
}

// ==========================================
// 1. GMAIL OTP FLOW
// ==========================================

async function sendOtp() {
  const email = emailInput?.value?.trim().toLowerCase();
  if (!email || !email.includes('@')) {
    setStatus('Please enter a valid Gmail address.', 'error');
    emailInput?.focus();
    return;
  }

  sendOtpBtn.disabled = true;
  sendOtpBtn.textContent = 'Sending...';
  setStatus('Contacting mail server...', 'info');

  try {
    const res = await fetch('/auth/request-otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to dispatch code.');

    otpDispatched = true;
    sendOtpBtn.textContent = 'Code Sent ✓';
    otpBoxes.forEach((b) => (b.disabled = false));
    verifySubmitBtn.disabled = false;
    startResendTimer(30);

    if (data.real_email_sent) {
      setStatus(`✓ Real code sent to ${email}! Check your Gmail inbox (and spam folder).`, 'info');
      demoBanner?.classList.add('hidden');
    } else {
      setStatus(data.message, 'info');
      if (data.demo_code && demoBanner && demoDisplay) {
        demoDisplay.textContent = data.demo_code;
        demoBanner.classList.remove('hidden');
      }
    }

    otpBoxes[0]?.focus();
  } catch (err) {
    sendOtpBtn.disabled = false;
    sendOtpBtn.textContent = 'Send Code →';
    setStatus(err.message, 'error');
  }
}

sendOtpBtn?.addEventListener('click', sendOtp);

function startResendTimer(seconds = 30) {
  if (!resendBtn) return;
  resendBtn.disabled = true;
  let remaining = seconds;
  resendBtn.textContent = `Resend in ${remaining}s`;

  if (resendTimer) clearInterval(resendTimer);
  resendTimer = setInterval(() => {
    remaining -= 1;
    if (remaining <= 0) {
      clearInterval(resendTimer);
      resendBtn.disabled = false;
      resendBtn.textContent = 'Resend code';
    } else {
      resendBtn.textContent = `Resend in ${remaining}s`;
    }
  }, 1000);
}

resendBtn?.addEventListener('click', () => {
  sendOtp();
});

// Digit box interactions
otpBoxes.forEach((box, idx) => {
  box.addEventListener('input', () => {
    box.value = box.value.replace(/\D/g, '').slice(0, 1);
    if (box.value && otpBoxes[idx + 1]) {
      otpBoxes[idx + 1].focus();
    }
  });

  box.addEventListener('keydown', (e) => {
    if (e.key === 'Backspace' && !box.value && otpBoxes[idx - 1]) {
      otpBoxes[idx - 1].focus();
    }
  });

  box.addEventListener('paste', (e) => {
    e.preventDefault();
    const pasteData = (e.clipboardData || window.clipboardData).getData('text');
    const digits = pasteData.replace(/\D/g, '').slice(0, 6);
    if (digits.length) {
      digits.split('').forEach((d, i) => {
        if (otpBoxes[i]) otpBoxes[i].value = d;
      });
      const next = Math.min(digits.length, otpBoxes.length - 1);
      otpBoxes[next]?.focus();
    }
  });
});

// Autofill demo code button
autofillBtn?.addEventListener('click', () => {
  const code = demoDisplay?.textContent?.trim();
  if (code && code.length === 6 && !code.includes('-')) {
    code.split('').forEach((d, i) => {
      if (otpBoxes[i]) otpBoxes[i].value = d;
    });
    verifySubmitBtn?.focus();
    setStatus('Demo code auto-filled. Click Verify & Sign In.', 'info');
  }
});

// Form submission for OTP verification
otpForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const email = emailInput?.value?.trim().toLowerCase();
  const otp = otpBoxes.map((b) => b.value).join('');

  if (!email) {
    setStatus('Enter your Gmail address first.', 'error');
    emailInput?.focus();
    return;
  }

  if (otp.length !== 6) {
    setStatus('Please enter the full 6-digit verification code.', 'error');
    return;
  }

  verifySubmitBtn.disabled = true;
  verifySubmitBtn.textContent = 'Verifying...';
  setStatus('Validating code...', 'info');

  try {
    const res = await fetch('/auth/verify-otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, otp }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Verification failed.');

    setStatus('✓ Success! Opening dashboard...', 'info');
    setTimeout(() => {
      window.location.href = data.redirect_url || '/dashboard';
    }, 400);
  } catch (err) {
    verifySubmitBtn.disabled = false;
    verifySubmitBtn.textContent = 'Verify & Sign In →';
    setStatus(err.message, 'error');
  }
});

// ==========================================
// 2. GOOGLE AUTHENTICATION
// ==========================================

// Global callback for Google Identity Services (GIS)
window.handleGoogleCredentialResponse = async function (response) {
  if (!response || !response.credential) return;
  setStatus('Authenticating with Google OAuth...', 'info');

  try {
    const res = await fetch('/auth/google', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential: response.credential }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Google sign-in failed.');

    setStatus('✓ Authenticated with Google! Redirecting...', 'info');
    setTimeout(() => {
      window.location.href = data.redirect_url || '/dashboard';
    }, 400);
  } catch (err) {
    setStatus(err.message, 'error');
  }
};

// Open Google Modal
googleQuickBtn?.addEventListener('click', () => {
  googleModal?.classList.remove('hidden');
});

closeGoogleModal?.addEventListener('click', () => {
  googleModal?.classList.add('hidden');
});

googleModal?.addEventListener('click', (e) => {
  if (e.target === googleModal) googleModal.classList.add('hidden');
});

// Profile options in modal
profileBtns.forEach((btn) => {
  btn.addEventListener('click', async () => {
    const email = btn.dataset.email;
    const name = btn.dataset.name;
    if (!email) return;

    btn.style.opacity = '0.6';
    setStatus(`Signing in with Google as ${name}...`, 'info');

    try {
      const res = await fetch('/auth/google', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, name }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Sign in failed.');

      setStatus('✓ Signed in! Redirecting...', 'info');
      setTimeout(() => {
        window.location.href = data.redirect_url || '/dashboard';
      }, 400);
    } catch (err) {
      btn.style.opacity = '1';
      setStatus(err.message, 'error');
    }
  });
});

customGoogleSubmit?.addEventListener('click', async () => {
  const email = customGoogleEmail?.value?.trim().toLowerCase();
  if (!email || !email.includes('@')) {
    alert('Please enter a valid Gmail address.');
    return;
  }

  customGoogleSubmit.disabled = true;
  customGoogleSubmit.textContent = '...';

  try {
    const res = await fetch('/auth/google', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Sign in failed.');

    window.location.href = data.redirect_url || '/dashboard';
  } catch (err) {
    customGoogleSubmit.disabled = false;
    customGoogleSubmit.textContent = 'Sign in';
    alert(err.message);
  }
});

// Setup Toggle
toggleSetupHelp?.addEventListener('click', () => {
  setupInstructions?.classList.toggle('hidden');
  setupChevron.textContent = setupInstructions?.classList.contains('hidden') ? '▾' : '▴';
});
