/* Shinobi account widget — replaces the nav-links with a hamburger button
   that opens a side drawer containing page navigation plus account controls
   (Sign up / Log in / Profile / Log out). Talks to /api/signup, /api/login,
   /api/logout, /api/me. */
(function () {
  'use strict';

  if (document.getElementById('auth-modal')) return; // already injected

  var navLinks = document.querySelector('.nav-links');
  var nav = document.querySelector('nav');
  if (!navLinks || !nav) return;

  // ---------------------------------------------------------------------
  // Styles
  // ---------------------------------------------------------------------
  var style = document.createElement('style');
  style.textContent = `
  .auth-nav-btn {
    background: none; border: none; color: var(--muted);
    font-size: 14px; cursor: pointer; font-family: inherit;
    padding: 0; transition: color 0.2s; text-align: left;
  }
  .auth-nav-btn:hover { color: var(--text); }
  .auth-nav-email {
    font-size: 12px; color: var(--muted);
    display: flex; align-items: center; gap: 8px;
    text-decoration: none; margin-right: 14px;
    transition: color 0.2s;
  }
  .auth-nav-email:hover { color: var(--text); }
  nav .auth-nav-email { padding: 0; border-bottom: none; }
  .auth-nav-avatar {
    width: 24px; height: 24px; border-radius: 50%; object-fit: cover;
    border: 1px solid #ffffff; flex-shrink: 0;
  }

  /* Hamburger */
  #nav-menu-btn {
    background: none; border: 1px solid #ffffff; border-radius: 0px;
    color: var(--text); cursor: pointer;
    width: 36px; height: 36px;
    display: flex; align-items: center; justify-content: center;
    padding: 0;
  }
  #nav-menu-btn svg { width: 18px; height: 18px; }

  /* Drawer */
  #nav-drawer-overlay {
    position: fixed; inset: 0; z-index: 2147483500;
    background: rgba(0,0,0,0.5);
    display: none;
  }
  #nav-drawer-overlay.nav-open { display: block; }
  #nav-drawer {
    position: fixed; top: 0; right: 0; bottom: 0; z-index: 2147483501;
    width: 280px; max-width: 80vw;
    background: #14141f;
    border-left: 1px solid #ffffff;
    transform: translateX(100%);
    transition: transform 0.25s ease;
    display: flex; flex-direction: column;
    font-family: 'Molgan', Arial, Helvetica, sans-serif;
    padding: 20px;
    gap: 4px;
  }
  #nav-drawer.nav-open { transform: translateX(0); }
  #nav-drawer-close {
    align-self: flex-end;
    background: none; border: none; color: var(--muted); cursor: pointer;
    font-size: 20px; line-height: 1; padding: 4px; margin-bottom: 10px;
  }
  #nav-drawer-close:hover { color: var(--text); }
  #nav-drawer a, #nav-drawer .auth-nav-btn {
    padding: 12px 4px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    color: var(--text); text-decoration: none; font-size: 14px;
  }
  #nav-drawer a:hover, #nav-drawer .auth-nav-btn:hover { color: var(--purple); }
  #nav-drawer .auth-nav-email {
    padding: 12px 4px 4px;
    border-bottom: none;
  }
  #nav-drawer .nav-cta {
    margin-top: 10px; text-align: center; border-bottom: none;
  }

  #auth-modal {
    position: fixed; inset: 0; z-index: 2147483600;
    display: none;
    align-items: center; justify-content: center;
    background: rgba(0,0,0,0.6);
    font-family: 'Molgan', Arial, Helvetica, sans-serif;
  }
  #auth-modal.auth-open { display: flex; }
  .auth-box {
    background: #14141f;
    border: 1px solid #ffffff;
    border-radius: 0px;
    width: 340px;
    max-width: calc(100vw - 32px);
    padding: 24px;
    position: relative;
  }
  .auth-box h2 { margin: 0 0 4px; font-size: 20px; font-weight: 700; color: #f3f1f7; }
  .auth-box .auth-sub { margin: 0 0 18px; font-size: 13px; color: #9b96a8; }
  .auth-box label { display: block; font-size: 12px; color: #9b96a8; margin-bottom: 4px; margin-top: 12px; }
  .auth-box input {
    width: 100%; box-sizing: border-box;
    background: #0d0d14; border: 1px solid #ffffff; border-radius: 0px;
    color: #f3f1f7; padding: 8px 10px; font-size: 14px; font-family: inherit;
  }
  .auth-box input:focus { outline: none; border-color: #8b5cf6; }
  .auth-submit {
    width: 100%; margin-top: 18px;
    background: linear-gradient(135deg, #8b5cf6, #ff4d5e);
    color: #fff; border: 1px solid transparent; border-radius: 0px;
    padding: 9px 0; font-size: 14px; font-weight: 600; cursor: pointer; font-family: inherit;
  }
  .auth-error {
    margin-top: 10px; font-size: 12.5px; color: #ff4d5e; min-height: 1em;
  }
  .auth-switch { margin-top: 14px; font-size: 12.5px; color: #9b96a8; text-align: center; }
  .auth-switch button {
    background: none; border: none; color: #c4b3ff; cursor: pointer;
    font-size: 12.5px; font-family: inherit; padding: 0;
  }
  .auth-close {
    position: absolute; top: 14px; right: 14px;
    background: none; border: none; color: #9b96a8; cursor: pointer;
    font-size: 18px; line-height: 1; padding: 0;
  }
  .auth-close:hover { color: #fff; }
  `;
  document.head.appendChild(style);

  // ---------------------------------------------------------------------
  // Build the drawer, move existing nav-links into it, add a hamburger
  // ---------------------------------------------------------------------
  var menuBtn = document.createElement('button');
  menuBtn.id = 'nav-menu-btn';
  menuBtn.setAttribute('aria-label', 'Open menu');
  menuBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';

  var overlay = document.createElement('div');
  overlay.id = 'nav-drawer-overlay';

  var drawer = document.createElement('div');
  drawer.id = 'nav-drawer';

  var drawerClose = document.createElement('button');
  drawerClose.id = 'nav-drawer-close';
  drawerClose.setAttribute('aria-label', 'Close menu');
  drawerClose.innerHTML = '&times;';
  drawer.appendChild(drawerClose);

  // Move all existing nav-link children (Home, How it works, Create, CTA, etc.)
  // into the drawer.
  while (navLinks.firstChild) {
    drawer.appendChild(navLinks.firstChild);
  }
  navLinks.style.display = 'none';

  nav.appendChild(menuBtn);
  document.body.appendChild(overlay);
  document.body.appendChild(drawer);

  function openDrawer() {
    overlay.classList.add('nav-open');
    drawer.classList.add('nav-open');
  }
  function closeDrawer() {
    overlay.classList.remove('nav-open');
    drawer.classList.remove('nav-open');
  }
  menuBtn.addEventListener('click', openDrawer);
  drawerClose.addEventListener('click', closeDrawer);
  overlay.addEventListener('click', closeDrawer);

  // ---------------------------------------------------------------------
  // Account controls — appended into the drawer
  // ---------------------------------------------------------------------
  var loginBtn = document.createElement('button');
  loginBtn.className = 'auth-nav-btn';
  loginBtn.textContent = 'Log in';

  var signupBtn = document.createElement('button');
  signupBtn.className = 'auth-nav-btn';
  signupBtn.textContent = 'Sign up';

  var emailLabel = document.createElement('a');
  emailLabel.className = 'auth-nav-email';
  emailLabel.href = '/profile.html';

  var logoutBtn = document.createElement('button');
  logoutBtn.className = 'auth-nav-btn';
  logoutBtn.textContent = 'Log out';

  var trashLink = document.createElement('a');
  trashLink.className = 'auth-nav-btn';
  trashLink.href = '/profile.html#trash';
  trashLink.textContent = 'Trash';

  nav.insertBefore(emailLabel, menuBtn);
  drawer.appendChild(loginBtn);
  drawer.appendChild(signupBtn);
  drawer.appendChild(trashLink);
  drawer.appendChild(logoutBtn);

  // ---------------------------------------------------------------------
  // Modal
  // ---------------------------------------------------------------------
  var wrap = document.createElement('div');
  wrap.innerHTML = `
  <div id="auth-modal">
    <div class="auth-box">
      <button class="auth-close" id="auth-close" aria-label="Close">&times;</button>
      <h2 id="auth-title">Log in</h2>
      <p class="auth-sub" id="auth-subtitle">Welcome back to Shinobi.</p>
      <form id="auth-form">
        <label for="auth-email">Email</label>
        <input type="email" id="auth-email" autocomplete="email" required>
        <label for="auth-password">Password</label>
        <input type="password" id="auth-password" autocomplete="current-password" required minlength="6">
        <div class="auth-error" id="auth-error"></div>
        <button type="submit" class="auth-submit" id="auth-submit">Log in</button>
      </form>
      <div class="auth-switch">
        <span id="auth-switch-text">Don't have an account?</span>
        <button id="auth-switch-btn" type="button">Sign up</button>
      </div>
    </div>
  </div>
  `;
  while (wrap.firstChild) document.body.appendChild(wrap.firstChild);

  var modal = document.getElementById('auth-modal');
  var form = document.getElementById('auth-form');
  var title = document.getElementById('auth-title');
  var subtitle = document.getElementById('auth-subtitle');
  var emailInput = document.getElementById('auth-email');
  var passwordInput = document.getElementById('auth-password');
  var errorEl = document.getElementById('auth-error');
  var submitBtn = document.getElementById('auth-submit');
  var switchText = document.getElementById('auth-switch-text');
  var switchBtn = document.getElementById('auth-switch-btn');
  var closeBtn = document.getElementById('auth-close');

  var mode = 'login';

  function setMode(m) {
    mode = m;
    errorEl.textContent = '';
    if (m === 'login') {
      title.textContent = 'Log in';
      subtitle.textContent = 'Welcome back to Shinobi.';
      submitBtn.textContent = 'Log in';
      switchText.textContent = "Don't have an account?";
      switchBtn.textContent = 'Sign up';
      passwordInput.setAttribute('autocomplete', 'current-password');
    } else {
      title.textContent = 'Sign up';
      subtitle.textContent = 'Create your Shinobi account.';
      submitBtn.textContent = 'Sign up';
      switchText.textContent = 'Already have an account?';
      switchBtn.textContent = 'Log in';
      passwordInput.setAttribute('autocomplete', 'new-password');
    }
  }

  function openModal(m) {
    setMode(m);
    closeDrawer();
    modal.classList.add('auth-open');
    emailInput.focus();
  }

  function closeModal() {
    modal.classList.remove('auth-open');
    form.reset();
    errorEl.textContent = '';
  }

  loginBtn.addEventListener('click', function () { openModal('login'); });
  signupBtn.addEventListener('click', function () { openModal('signup'); });
  closeBtn.addEventListener('click', closeModal);
  modal.addEventListener('click', function (e) { if (e.target === modal) closeModal(); });
  switchBtn.addEventListener('click', function () { setMode(mode === 'login' ? 'signup' : 'login'); });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    errorEl.textContent = '';
    var endpoint = mode === 'login' ? '/api/login' : '/api/signup';

    fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: emailInput.value, password: passwordInput.value })
    })
      .then(function (res) { return res.json(); })
      .then(function (json) {
        if (json.success) {
          closeModal();
          refreshAuthUI();
        } else {
          errorEl.textContent = json.error || 'Something went wrong.';
        }
      })
      .catch(function (err) {
        errorEl.textContent = err.message;
      });
  });

  logoutBtn.addEventListener('click', function () {
    fetch('/api/logout', { method: 'POST' }).then(function () { refreshAuthUI(); closeDrawer(); });
  });

  function refreshAuthUI() {
    fetch('/api/me')
      .then(function (res) { return res.json(); })
      .then(function (json) {
        var loggedIn = json.success && json.data && json.data.logged_in;
        loginBtn.style.display = loggedIn ? 'none' : '';
        signupBtn.style.display = loggedIn ? 'none' : '';
        emailLabel.style.display = loggedIn ? '' : 'none';
        logoutBtn.style.display = loggedIn ? '' : 'none';
        trashLink.style.display = loggedIn ? '' : 'none';
        if (loggedIn) {
          var name = json.data.username || json.data.email;
          var avatarUrl = json.data.avatar_url || '/logo-final.png';
          emailLabel.innerHTML = '';
          var img = document.createElement('img');
          img.className = 'auth-nav-avatar';
          img.src = avatarUrl;
          img.alt = '';
          var span = document.createElement('span');
          span.textContent = name;
          emailLabel.appendChild(img);
          emailLabel.appendChild(span);
        }
      })
      .catch(function () { /* ignore */ });
  }
  window.shinobiRefreshAuthUI = refreshAuthUI;

  emailLabel.style.display = 'none';
  logoutBtn.style.display = 'none';
  trashLink.style.display = 'none';
  refreshAuthUI();
})();
