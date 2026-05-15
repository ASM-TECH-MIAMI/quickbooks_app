/**
 * QB CFO Agent — Shared App Shell
 * Injects the iOS-inspired design system + sidebar into every page.
 * Usage: call QB.init({ active: 'chat' | 'dashboard' | 'executive' }) at bottom of <body>.
 */
(function (G) {
  'use strict';

  /* ─── Design System CSS ──────────────────────────────────────────────────── */
  const CSS = `
:root {
  --bg:   #09090B;
  --s1:   #111113;
  --s2:   #18181B;
  --s3:   #27272A;
  --s4:   #3F3F46;
  --blue:       #0A84FF;
  --blue-d:     rgba(10,132,255,0.14);
  --blue-b:     rgba(10,132,255,0.28);
  --green:      #30D158;
  --green-d:    rgba(48,209,88,0.14);
  --red:        #FF453A;
  --red-d:      rgba(255,69,58,0.14);
  --orange:     #FF9F0A;
  --orange-d:   rgba(255,159,10,0.14);
  --purple:     #BF5AF2;
  --purple-d:   rgba(191,90,242,0.14);
  --yellow:     #FFD60A;
  --t1:  #FFFFFF;
  --t2:  rgba(235,235,245,0.60);
  --t3:  rgba(235,235,245,0.30);
  --t4:  rgba(235,235,245,0.14);
  --sep: rgba(84,84,88,0.48);
  --sb-w: 256px;
  --r-s:  8px;
  --r-m:  12px;
  --r-l:  16px;
  --r-xl: 22px;
  --ease: cubic-bezier(0.25,0.46,0.45,0.94);
  --font: -apple-system,BlinkMacSystemFont,"SF Pro Display","Helvetica Neue",system-ui,sans-serif;
}

*, *::before, *::after { box-sizing: border-box; margin:0; padding:0; }

html { height: 100%; }

body {
  background: var(--bg);
  color: var(--t1);
  font-family: var(--font);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  display: flex;
  height: 100dvh;
  overflow: hidden;
}

/* ─── Sidebar ─────────────────────────────────────────────────────────────── */
#qb-sb {
  width: var(--sb-w);
  min-width: var(--sb-w);
  height: 100dvh;
  background: rgba(14,14,16,0.97);
  backdrop-filter: saturate(180%) blur(24px);
  -webkit-backdrop-filter: saturate(180%) blur(24px);
  border-right: 1px solid var(--sep);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex-shrink: 0;
  z-index: 100;
}

.sb-hd {
  display: flex; align-items: center; gap: 10px;
  padding: 18px 14px 16px;
  border-bottom: 1px solid var(--sep);
  flex-shrink: 0;
}

.sb-mark {
  width: 34px; height: 34px;
  background: linear-gradient(145deg, #0A84FF 0%, #5E5CE6 100%);
  border-radius: 9px;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 700; color: #fff;
  flex-shrink: 0;
  box-shadow: 0 2px 12px rgba(10,132,255,0.35);
}

.sb-title { font-size: 15px; font-weight: 600; color: var(--t1); line-height:1.2; }
.sb-sub   { font-size: 11px; color: var(--t3); margin-top: 2px; }

.sb-body  { flex:1; overflow-y:auto; overflow-x:hidden; padding: 8px 0; }
.sb-body::-webkit-scrollbar { width:0; }

.sb-sec   { padding: 14px 10px 2px; }

.sb-lbl {
  font-size: 11px; font-weight: 600;
  color: var(--t3);
  letter-spacing: 0.07em;
  text-transform: uppercase;
  padding: 0 6px 8px;
  display: block;
}

.sb-row {
  display: flex; align-items: center; gap: 9px;
  padding: 8px 8px;
  border-radius: var(--r-m);
  cursor: pointer;
  text-decoration: none;
  color: var(--t2);
  font-size: 14px;
  font-weight: 500;
  transition: background .13s var(--ease), color .13s var(--ease);
  user-select: none;
}
.sb-row:hover  { background: rgba(255,255,255,0.06); color: var(--t1); }
.sb-row.active { background: var(--blue-d); color: var(--blue); }

.sb-ico {
  width: 28px; height: 28px;
  border-radius: 7px;
  display: flex; align-items: center; justify-content: center;
  font-size: 15px; flex-shrink: 0;
}
.sb-row.active .sb-ico { background: var(--blue-d); }

.sb-co {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 8px;
  border-radius: var(--r-m);
  text-decoration: none;
  color: var(--t2);
  font-size: 13px;
  cursor: pointer;
  transition: background .13s var(--ease), color .13s var(--ease);
}
.sb-co:hover  { background: rgba(255,255,255,0.06); color: var(--t1); }
.sb-co.active { background: var(--blue-d); color: var(--blue); }
.sb-dot { width:7px; height:7px; border-radius:50%; flex-shrink:0; }
.sb-co-n { flex:1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.sb-live { width:5px; height:5px; border-radius:50%; background:var(--green); flex-shrink:0; }

.sb-ft {
  padding: 8px 10px 22px;
  border-top: 1px solid var(--sep);
  flex-shrink: 0;
}

/* ─── Main ───────────────────────────────────────────────────────────────── */
#qb-main {
  flex: 1; min-width: 0;
  height: 100dvh;
  display: flex; flex-direction: column;
  overflow-y: auto; overflow-x: hidden;
}
#qb-main.no-scroll { overflow: hidden; }

/* ─── Global iOS components ──────────────────────────────────────────────── */
.ios-card  { background:var(--s2); border-radius:var(--r-l); border:1px solid var(--sep); }
.ios-card2 { background:var(--s3); border-radius:var(--r-l); }
.ios-sep   { border:none; border-top:1px solid var(--sep); width:100%; }

.sec-label {
  font-size:11px; font-weight:700; letter-spacing:.07em;
  text-transform:uppercase; color:var(--t3); padding-bottom:10px;
}

.badge {
  display:inline-flex; align-items:center; gap:3px;
  padding:2px 9px; border-radius:999px; font-size:11px; font-weight:600;
}
.b-blue   { background:var(--blue-d);   color:var(--blue);   }
.b-green  { background:var(--green-d);  color:var(--green);  }
.b-red    { background:var(--red-d);    color:var(--red);    }
.b-orange { background:var(--orange-d); color:var(--orange); }
.b-purple { background:var(--purple-d); color:var(--purple); }
.b-gray   { background:rgba(255,255,255,.09); color:var(--t2); }

.c-green  { color:var(--green);  }
.c-red    { color:var(--red);    }
.c-orange { color:var(--orange); }
.c-blue   { color:var(--blue);   }
.c-dim    { color:var(--t2);     }
.c-dimmer { color:var(--t3);     }

::-webkit-scrollbar { width:4px; height:4px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:var(--s3); border-radius:2px; }
::-webkit-scrollbar-thumb:hover { background:var(--s4); }

/* ─── Mobile ─────────────────────────────────────────────────────────────── */
#qb-hmb {
  display:none; position:fixed; top:12px; left:12px; z-index:200;
  width:36px; height:36px; background:var(--s2); border:1px solid var(--sep);
  border-radius:var(--r-s); border:none; cursor:pointer;
  align-items:center; justify-content:center; color:var(--t1);
}
#qb-ov {
  display:none; position:fixed; inset:0;
  background:rgba(0,0,0,.6); backdrop-filter:blur(4px); z-index:99;
}
@media (max-width:768px) {
  #qb-sb { position:fixed; transform:translateX(-100%); transition:transform .3s var(--ease); }
  #qb-sb.open { transform:translateX(0); }
  #qb-main { width:100%; }
  #qb-hmb { display:flex; }
  #qb-ov.show { display:block; }
}
`;

  const CO_COLORS = ['#0A84FF','#BF5AF2','#30D158','#FF9F0A'];

  const NAV = [
    { href:'/',          ico:'💬', label:'Chat',             match: p => p === '/'           },
    { href:'/dashboard', ico:'📊', label:'CFO Dashboard',    match: p => p.startsWith('/dashboard') },
    { href:'/executive', ico:'📋', label:'Executive Report', match: p => p.startsWith('/executive') },
  ];

  function sidebarHTML() {
    const path = window.location.pathname;
    const nav = NAV.map(n =>
      `<a href="${n.href}" class="sb-row ${n.match(path) ? 'active' : ''}">
         <span class="sb-ico">${n.ico}</span>${n.label}
       </a>`
    ).join('');
    return `
      <div class="sb-hd">
        <div class="sb-mark">QB</div>
        <div>
          <div class="sb-title">CFO Agent</div>
          <div class="sb-sub">AI Financial Intelligence</div>
        </div>
      </div>
      <div class="sb-body">
        <div class="sb-sec">
          <span class="sb-lbl">Main</span>
          ${nav}
        </div>
        <div class="sb-sec">
          <span class="sb-lbl">Companies</span>
          <div id="sb-cos"><div style="padding:6px 8px;font-size:12px;color:var(--t3)">Loading…</div></div>
        </div>
      </div>
      <div class="sb-ft">
        <a href="/auth/connect/3" class="sb-row" style="color:var(--t3);font-size:13px;">
          <span class="sb-ico" style="font-size:19px;font-weight:300;color:var(--t3)">＋</span>Connect Company
        </a>
      </div>`;
  }

  async function loadCompanies(activeCompany) {
    try {
      const { companies = [] } = await fetch('/api/companies').then(r => r.json());
      const el = document.getElementById('sb-cos');
      if (!el) return;
      if (!companies.length) { el.innerHTML = '<div style="padding:6px 8px;font-size:12px;color:var(--t3)">None connected</div>'; return; }
      el.innerHTML = companies.map((c, i) => {
        const col   = CO_COLORS[i % 4];
        const short = c.name.replace(/ (LLC|Inc|Corp)\.?$/, '').replace(/ (Media Group|Tech Media Group|Group)$/, '').trim();
        return `<a href="/?company=${encodeURIComponent(c.name)}" class="sb-co ${c.name === activeCompany ? 'active' : ''}">
          <span class="sb-dot" style="background:${col}"></span>
          <span class="sb-co-n" title="${c.name}">${short}</span>
          <span class="sb-live"></span>
        </a>`;
      }).join('');
    } catch(e) { /* silent */ }
  }

  function init(opts = {}) {
    const { active = '', activeCompany = '', noScroll = false } = opts;

    // Inject CSS
    const s = document.createElement('style');
    s.textContent = CSS;
    document.head.appendChild(s);

    // Wrap existing body in #qb-main
    const kids = Array.from(document.body.childNodes);
    const sb   = document.createElement('nav'); sb.id = 'qb-sb'; sb.innerHTML = sidebarHTML();
    const main = document.createElement('div'); main.id = 'qb-main';
    if (noScroll) main.classList.add('no-scroll');
    kids.forEach(n => main.appendChild(n));

    // Mobile overlay + hamburger
    const ov  = document.createElement('div');  ov.id = 'qb-ov';
    const hmb = document.createElement('button'); hmb.id = 'qb-hmb';
    hmb.innerHTML = `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>`;

    const close = () => { sb.classList.remove('open'); ov.classList.remove('show'); };
    ov.addEventListener('click', close);
    hmb.addEventListener('click', () => { sb.classList.toggle('open'); ov.classList.toggle('show'); });

    document.body.innerHTML = '';
    document.body.appendChild(sb);
    document.body.appendChild(main);
    document.body.appendChild(ov);
    document.body.appendChild(hmb);

    loadCompanies(activeCompany);
  }

  G.QB = G.QB || {};
  G.QB.init    = init;
  G.QB.COLORS  = CO_COLORS;
})(window);
