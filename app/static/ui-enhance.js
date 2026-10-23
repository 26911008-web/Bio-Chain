/* Bio-Chain UI enhancer — lapisan presentasi saja (DESIGN_SYSTEM.md §7a, §8).
 *
 * Tidak memanggil API, tidak mengubah STATE, tidak mengganti handler bisnis. Hanya:
 *  1. Tema per peran (field/noir) + tombol ganti tema  → <html data-theme>
 *  2. Aksesibilitas runtime: label↔input, elemen onclick bisa dipakai keyboard, aria-current tab,
 *     label tombol ikon, dialog modal (focus trap + kembalikan fokus)
 *  3. Ornamen 3D: tilt kartu KPI (T1) dan hero WebGL three.js di halaman login (T3, lazy & bersyarat)
 */
(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const mq = q => window.matchMedia && window.matchMedia(q).matches;
  const reducedMotion = () => mq("(prefers-reduced-motion: reduce)");
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch {} },
  };

  // ------------------------------------------------------------------
  // 1. TEMA
  // ------------------------------------------------------------------
  const THEME_BY_ROLE = { login: "noir", petani: "field", pengepul: "field", driver: "field",
                          pabrik: "noir", auditor: "noir", admin: "noir" };
  const THEME_KEY = "biochain_theme";            // pilihan manual pengguna (field|noir); kosong = ikut peran

  function currentRole() {
    const app = $("app-view");
    const loggedIn = app && app.style.display === "flex";
    try { if (loggedIn && typeof STATE !== "undefined" && STATE.user) return STATE.user.role; } catch {}
    return loggedIn ? "petani" : "login";
  }
  function applyTheme() {
    const role = currentRole();
    const manual = role === "login" ? null : store.get(THEME_KEY);
    const theme = manual || THEME_BY_ROLE[role] || "field";
    document.documentElement.dataset.theme = theme;
    if (role === "login") delete document.documentElement.dataset.role;
    else document.documentElement.dataset.role = role;
    renderRoleHero(role);
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = theme === "noir" ? "#111111" : "#f8f8f8";
    const btn = $("btn-theme-toggle");
    if (btn) {
      const next = theme === "noir" ? "terang (lapangan)" : "gelap";
      btn.setAttribute("aria-label", `Ganti ke tema ${next}`);
      btn.title = `Ganti ke tema ${next}`;
      btn.textContent = theme === "noir" ? "☀️" : "🌙";
      btn.setAttribute("aria-pressed", String(theme === "noir"));
    }
    hero.toggle(role === "login");
  }
  function toggleTheme() {
    const now = document.documentElement.dataset.theme;
    const next = now === "noir" ? "field" : "noir";
    // Bila pilihan sama dengan default peran, hapus override agar kembali "ikut peran"
    store.set(THEME_KEY, next === THEME_BY_ROLE[currentRole()] ? null : next);
    applyTheme();
  }

  // ------------------------------------------------------------------
  // 1b. PERSONALISASI PERAN — banner sapaan + emblem 3D di atas Portal Persona.
  //     Teks peran diambil dari data akun demo yang sudah ada (role_label, description);
  //     disisipkan di luar #persona-content sehingga render ulang dashboard tidak menghapusnya.
  // ------------------------------------------------------------------
  const ROLE_META = {
    petani:   { icon: "🌾", label: "Petani / Penggilingan", mode: "☀️ Mode Lapangan · tombol besar, kontras tinggi" },
    pengepul: { icon: "📦", label: "Pengepul / Hub KUD",     mode: "☀️ Mode Lapangan · tombol besar, kontras tinggi" },
    driver:   { icon: "🚛", label: "Driver Armada Truk",     mode: "☀️ Mode Jalan · tombol ekstra besar",
                extra: "📵 Tetap jalan saat offline" },
    pabrik:   { icon: "🏭", label: "Pabrik Pirolisis",       mode: "🖥️ Mode Kontrol · tampilan padat" },
    auditor:  { icon: "🔍", label: "Auditor (Read-only)",    mode: "🖥️ Mode Kontrol · hanya baca" },
    admin:    { icon: "⚙️", label: "System Admin",           mode: "🖥️ Mode Kontrol · tampilan padat" },
  };
  let heroKey = "";
  function renderRoleHero(role) {
    const pane = $("tab-persona");
    if (!pane || role === "login") return;
    let user = null, demo = null;
    try {
      user = STATE.user;
      demo = (STATE.demoAccounts || []).find(a => a.role === role);
    } catch {}
    const meta = ROLE_META[role] || { icon: "👤", label: role, mode: "" };
    const name = (user && (user.full_name || user.username)) || "";
    const key = `${role}|${name}`;
    if (key === heroKey && pane.querySelector(".role-hero")) return;
    heroKey = key;

    const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
    const hero = el("section", "role-hero");
    hero.setAttribute("aria-labelledby", "role-hero-title");
    const body = el("div");
    body.append(el("span", "tagline", `${meta.icon} ${(demo && demo.role_label) || meta.label}`));
    // "Pak Sugeng (Penggilingan Padi Godean)" → sapaan pendek + unit kerja sebagai chip (judul tidak membengkak di HP)
    const split = name.match(/^(.+?)\s*\((.+)\)\s*$/);
    const shortName = split ? split[1] : name;
    const h2 = el("h2", null, shortName ? `Halo, ${shortName}` : `Portal ${meta.label}`);
    h2.id = "role-hero-title";
    body.append(h2);
    if (demo && demo.description) body.append(el("p", null, demo.description));
    if (role !== "petani" && role !== "pengepul") {
      const chips = el("div", "role-chips");
      if (split) chips.append(el("span", "role-chip", `${meta.icon} ${split[2]}`));
      if (meta.mode) chips.append(el("span", "role-chip", meta.mode));
      if (meta.extra) chips.append(el("span", "role-chip", meta.extra));
      const place = user && [user.kecamatan, user.kabupaten].filter(Boolean).join(", ");
      if (place) chips.append(el("span", "role-chip", `📍 ${place}`));
      body.append(chips);
    }

    const emblem = el("div", "role-emblem");
    emblem.setAttribute("aria-hidden", "true");
    const cube = el("div", "role-emblem-cube");
    for (let i = 0; i < 6; i++) cube.append(el("div", "role-emblem-face", meta.icon));
    emblem.append(cube);
    hero.append(body, emblem);

    const old = pane.querySelector(".role-hero") || pane.querySelector(":scope > h2.visually-hidden");
    if (old) old.replaceWith(hero); else pane.prepend(hero);
  }

  // ------------------------------------------------------------------
  // 2. AKSESIBILITAS
  // ------------------------------------------------------------------
  let uid = 0;
  const CONTROL = "input:not([type=hidden]),select,textarea";
  const ICON_LABELS = { "✕": "Tutup", "↺": "Mulai percakapan baru", "👁️": "Tampilkan atau sembunyikan password",
                        "🙈": "Tampilkan atau sembunyikan password" };

  function enhance(root) {
    if (!root || !root.querySelectorAll) return;

    // Label tanpa for → tautkan ke kontrol berikutnya
    root.querySelectorAll("label:not([for])").forEach(label => {
      if (label.querySelector(CONTROL)) return;               // label membungkus kontrol: sudah valid
      let el = label.nextElementSibling, control = null;
      for (let i = 0; el && i < 3 && !control; i++, el = el.nextElementSibling) {
        control = el.matches(CONTROL) ? el : el.querySelector && el.querySelector(CONTROL);
      }
      if (!control || control.labels && control.labels.length) return;
      if (!control.id) control.id = `ui-f-${++uid}`;
      label.htmlFor = control.id;
    });

    // Kontrol tanpa label sama sekali → aria-label dari placeholder/title
    root.querySelectorAll(CONTROL).forEach(c => {
      if (c.getAttribute("aria-label") || (c.labels && c.labels.length)) return;
      const name = c.getAttribute("placeholder") || c.getAttribute("title");
      if (name) c.setAttribute("aria-label", name);
    });

    // Elemen non-tombol dengan onclick → bisa difokus & ditekan dengan Enter/Spasi
    root.querySelectorAll("div[onclick],span[onclick],a[onclick]:not([href]),#gate-admin-link").forEach(el => {
      if (!el.hasAttribute("role")) el.setAttribute("role", "button");
      if (!el.hasAttribute("tabindex")) el.tabIndex = 0;
      el.dataset.uiKey = "1";
    });
    root.querySelectorAll("#role-selector-grid .role-card").forEach(el =>
      el.setAttribute("aria-pressed", String(el.classList.contains("active"))));

    // Tombol ikon tanpa nama aksesibel
    root.querySelectorAll("button:not([aria-label])").forEach(b => {
      const t = (b.textContent || "").trim();
      if (ICON_LABELS[t]) b.setAttribute("aria-label", ICON_LABELS[t]);
      else if (t.length <= 2 && b.title) b.setAttribute("aria-label", b.title);
    });

    enhanceField(root);

    // Tabel lebar: pastikan pembungkus bisa digulir & diberi nama
    root.querySelectorAll("table.data-table").forEach(t => {
      const p = t.parentElement;
      if (p && getComputedStyle(p).overflowX === "visible" && !p.classList.contains("table-scroll")) {
        p.classList.add("table-scroll");
      }
    });
  }

  let pending = false;
  const queue = new Set();
  const domObserver = new MutationObserver(muts => {
    for (const m of muts) m.addedNodes.forEach(n => { if (n.nodeType === 1) queue.add(n); });
    if (pending || !queue.size) return;
    pending = true;
    requestAnimationFrame(() => {
      pending = false;
      const nodes = [...queue]; queue.clear();
      nodes.forEach(n => n.isConnected && enhance(n.parentElement || n));
    });
  });

  document.addEventListener("keydown", e => {
    const t = e.target;
    if (t && t.dataset && t.dataset.uiKey && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      t.click();
    }
  });

  function syncNavCurrent() {
    document.querySelectorAll(".nav-btn").forEach(b => {
      if (b.classList.contains("active")) b.setAttribute("aria-current", "page");
      else b.removeAttribute("aria-current");
    });
    document.querySelectorAll("#role-selector-grid .role-card").forEach(el =>
      el.setAttribute("aria-pressed", String(el.classList.contains("active"))));
  }

  // Modal: dialog semantik, fokus masuk, Tab terkunci di dalam, fokus kembali saat ditutup
  const FOCUSABLE = 'button:not([disabled]),[href],input:not([type=hidden]):not([disabled]),select,textarea,[tabindex]:not([tabindex="-1"])';
  const lastFocus = new WeakMap();
  function onModalChange(overlay) {
    const box = overlay.querySelector(".modal-box");
    if (!box) return;
    if (overlay.classList.contains("open")) {
      if (overlay.dataset.uiOpen === "1") return;
      overlay.dataset.uiOpen = "1";
      box.setAttribute("role", "dialog");
      box.setAttribute("aria-modal", "true");
      const h = box.querySelector("h2,h3");
      if (h) { if (!h.id) h.id = `ui-dlg-${++uid}`; box.setAttribute("aria-labelledby", h.id); }
      lastFocus.set(overlay, document.activeElement);
      const first = [...box.querySelectorAll(FOCUSABLE)].find(el => el.offsetParent !== null);
      setTimeout(() => (first || box).focus && (first || box).focus({ preventScroll: true }), 30);
    } else if (overlay.dataset.uiOpen === "1") {
      overlay.dataset.uiOpen = "";
      const prev = lastFocus.get(overlay);
      if (prev && prev.isConnected && prev.focus) prev.focus({ preventScroll: true });
    }
  }
  document.addEventListener("keydown", e => {
    if (e.key !== "Tab") return;
    const overlay = document.querySelector(".modal-overlay.open");
    if (!overlay) return;
    const items = [...overlay.querySelectorAll(FOCUSABLE)].filter(el => el.offsetParent !== null);
    if (!items.length) return;
    const first = items[0], last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });

  // ------------------------------------------------------------------
  // 3a. ORNAMEN 3D — tilt kartu (T1)
  // ------------------------------------------------------------------
  const TILT_SEL = ".kpi-tile, [data-tilt]";
  const canTilt = () => mq("(hover: hover) and (pointer: fine)") && !reducedMotion();
  let tiltEl = null, tiltFrame = 0, lastEvt = null;
  function tiltMax() {
    const v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--tilt-max"));
    return Number.isFinite(v) ? v : 8;
  }
  function paintTilt() {
    tiltFrame = 0;
    if (!tiltEl || !lastEvt) return;
    const r = tiltEl.getBoundingClientRect();
    const px = Math.min(Math.max((lastEvt.clientX - r.left) / r.width, 0), 1);
    const py = Math.min(Math.max((lastEvt.clientY - r.top) / r.height, 0), 1);
    const max = tiltMax();
    tiltEl.style.setProperty("--ry", `${((px - 0.5) * 2 * max).toFixed(2)}deg`);
    tiltEl.style.setProperty("--rx", `${((0.5 - py) * 2 * max).toFixed(2)}deg`);
    tiltEl.style.setProperty("--glare-x", `${(px * 100).toFixed(1)}%`);
    tiltEl.style.setProperty("--glare-y", `${(py * 100).toFixed(1)}%`);
  }
  function resetTilt(el) {
    el.classList.remove("is-tilting");
    el.style.removeProperty("--rx"); el.style.removeProperty("--ry");
  }
  document.addEventListener("pointermove", e => {
    if (e.pointerType !== "mouse" || !canTilt()) return;
    const el = e.target.closest && e.target.closest(TILT_SEL);
    if (el !== tiltEl) {
      if (tiltEl) resetTilt(tiltEl);
      tiltEl = el;
      if (el) el.classList.add("is-tilting");
    }
    if (!el) return;
    lastEvt = e;
    if (!tiltFrame) tiltFrame = requestAnimationFrame(paintTilt);
  }, { passive: true });
  document.addEventListener("pointerleave", () => { if (tiltEl) resetTilt(tiltEl); tiltEl = null; });

  // ------------------------------------------------------------------
  // 3b. ORNAMEN 3D — hero WebGL di login (T3)
  // ------------------------------------------------------------------
  // three.js + addon dimuat lewat <script type="importmap"> di index.html ("three", "three/addons/").
  // Disusun mengikuti skill: threejs-lighting (hemisphere + key + rim + IBL RoomEnvironment),
  // threejs-materials/shaders (instanceColor, clearcoat + fresnel onBeforeCompile, debu ShaderMaterial),
  // threejs-postprocessing (EffectComposer → RenderPass → UnrealBloom setengah resolusi → OutputPass),
  // threejs-interaction (ray-plane: butiran menyingkir dari kursor; klik = siklus sekam → biochar),
  // threejs-animation (intro berkumpul + kamera dolly), plus penurun kualitas otomatis.
  const hero = {
    state: "idle",            // idle | loading | ready | off
    running: false,
    ctx: null,
    eligible() {
      const conn = navigator.connection || {};
      if (reducedMotion() || conn.saveData) return false;
      if (/(^|-)2g$/.test(conn.effectiveType || "")) return false;
      if (navigator.deviceMemory && navigator.deviceMemory < 4) return false;
      if (!mq("(min-width: 768px)")) return false;
      if (!(HTMLScriptElement.supports && HTMLScriptElement.supports("importmap"))) return false;
      try { return !!document.createElement("canvas").getContext("webgl2"); } catch { return false; }
    },
    toggle(show) {
      if (!show) return this.stop();
      if (this.state === "ready") return this.start();
      if (this.state !== "idle") return;
      if (!this.eligible()) { this.state = "off"; return; }
      this.state = "loading";
      // Tunggu halaman tenang dulu agar tidak berebut jaringan dengan form login
      const go = () => this.load().catch(err => { console.warn("[ornamen3d] fallback CSS:", err); this.state = "off"; });
      ("requestIdleCallback" in window) ? requestIdleCallback(go, { timeout: 2500 }) : setTimeout(go, 1200);
    },
    async load() {
      const host = document.querySelector(".login-hero-ornament");
      if (!host) { this.state = "off"; return; }
      const [THREE, { EffectComposer }, { RenderPass }, { UnrealBloomPass }, { OutputPass }, { RoomEnvironment }] =
        await Promise.all([
          import("three"),
          import("three/addons/postprocessing/EffectComposer.js"),
          import("three/addons/postprocessing/RenderPass.js"),
          import("three/addons/postprocessing/UnrealBloomPass.js"),
          import("three/addons/postprocessing/OutputPass.js"),
          import("three/addons/environments/RoomEnvironment.js"),
        ]);
      const W = () => host.clientWidth || 1, H = () => host.clientHeight || 1;
      const BG = 0x111111;                       // = --surface-0 tema noir; tepi kanvas disamarkan mask CSS
      let dpr = Math.min(window.devicePixelRatio || 1, 1.5);

      const renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: "low-power" });
      renderer.setPixelRatio(dpr);
      renderer.setSize(W(), H(), false);
      renderer.setClearColor(BG, 1);
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.05;
      renderer.domElement.setAttribute("aria-hidden", "true");
      host.appendChild(renderer.domElement);

      const scene = new THREE.Scene();
      scene.background = new THREE.Color(BG);
      scene.fog = new THREE.Fog(BG, 8.5, 15);
      const camera = new THREE.PerspectiveCamera(36, W() / H(), 0.1, 60);
      camera.position.set(0, 0.6, 12.5);        // intro: dolly masuk ke z≈9

      // --- Lighting: IBL lembut + hemisphere hangat + key + rim lime ---
      const pmrem = new THREE.PMREMGenerator(renderer);
      scene.environment = pmrem.fromScene(new RoomEnvironment(renderer), 0.04).texture;
      pmrem.dispose();
      scene.add(new THREE.HemisphereLight(0xfff3d6, 0x1a1f0a, 0.55));
      const key = new THREE.DirectionalLight(0xffffff, 1.3); key.position.set(4, 5, 6); scene.add(key);
      const rim = new THREE.DirectionalLight(0xd6ff4d, 3.2); rim.position.set(-6, 2, -5); scene.add(rim);

      const group = new THREE.Group();
      group.rotation.x = 0.35;
      group.position.x = 0.15;
      group.scale.setScalar(0.8);
      scene.add(group);
      const glow = new THREE.PointLight(0xd6ff4d, 4, 5, 2);   // cahaya dari inti biochar
      group.add(glow);

      // --- Butiran sekam: kapsul pipih, warna emas bervariasi per instance ---
      const HUSKS = 520;
      const huskGeo = new THREE.CapsuleGeometry(0.035, 0.22, 3, 6);
      huskGeo.scale(1, 1, 0.45);
      const huskMat = new THREE.MeshStandardMaterial({ roughness: 0.78, metalness: 0, envMapIntensity: 0.35 });
      const husks = new THREE.InstancedMesh(huskGeo, huskMat, HUSKS);
      husks.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      const col = new THREE.Color();
      const seeds = [];
      for (let i = 0; i < HUSKS; i++) {
        seeds.push({
          a: Math.random() * Math.PI * 2,
          r: 2.4 + (Math.random() - 0.5) * 0.9,
          y: (Math.random() - 0.5) * 0.7,
          s: 0.06 + Math.random() * 0.12,
          sx: Math.random() * 6, sy: Math.random() * 6, sz: Math.random() * 6,
          ds: 0.4 + Math.random(),
          intro: 2.2 + Math.random() * 2.4,       // jarak awal (kelipatan radius) saat intro
        });
        col.setHSL(0.11 + Math.random() * 0.03, 0.42 + Math.random() * 0.15, 0.46 + Math.random() * 0.16);
        husks.setColorAt(i, col);
      }
      group.add(husks);
      const offs = new Float32Array(HUSKS * 3);  // dorongan interaksi per butir (di-lerp halus)

      // --- Inti biochar: pelet clearcoat + tepi fresnel lime (onBeforeCompile) ---
      const pelletGeo = new THREE.CylinderGeometry(0.16, 0.16, 0.5, 20);
      const pelletMat = new THREE.MeshPhysicalMaterial({
        color: 0x161616, roughness: 0.42, metalness: 0.1, clearcoat: 0.7, clearcoatRoughness: 0.25, envMapIntensity: 0.6,
      });
      const rimU = { uRim: { value: new THREE.Color(0xd6ff4d) }, uRimPower: { value: 2.6 }, uRimStrength: { value: 1.4 } };
      pelletMat.onBeforeCompile = shader => {
        Object.assign(shader.uniforms, rimU);
        shader.fragmentShader = "uniform vec3 uRim;\nuniform float uRimPower;\nuniform float uRimStrength;\n" +
          shader.fragmentShader.replace("#include <emissivemap_fragment>", `#include <emissivemap_fragment>
            float rimF = pow(1.0 - saturate(dot(normalize(normal), normalize(vViewPosition))), uRimPower);
            totalEmissiveRadiance += uRim * rimF * uRimStrength;`);
      };
      const PELLETS = 46;
      const pellets = new THREE.InstancedMesh(pelletGeo, pelletMat, PELLETS);
      pellets.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      const core = [];
      for (let i = 0; i < PELLETS; i++) {
        const phi = Math.acos(1 - 2 * (i + 0.5) / PELLETS), th = Math.PI * (1 + Math.sqrt(5)) * i;
        core.push({ p: new THREE.Vector3().setFromSphericalCoords(0.95, phi, th), rx: Math.random() * 3, ry: Math.random() * 3 });
      }
      group.add(pellets);

      // --- Cincin orbit HDR (warna >1 agar tertangkap bloom) ---
      const ring = new THREE.Mesh(new THREE.TorusGeometry(2.4, 0.007, 8, 200),
        new THREE.MeshBasicMaterial({ color: new THREE.Color(0xd6ff4d).multiplyScalar(1.8), transparent: true, opacity: 0.5, fog: false }));
      ring.rotation.x = Math.PI / 2;
      group.add(ring);

      // --- Debu bercahaya: ShaderMaterial Points, ukuran ikut jarak, berkelip ---
      const DUST = 900;
      const dPos = new Float32Array(DUST * 3), dSeed = new Float32Array(DUST), dMix = new Float32Array(DUST);
      for (let i = 0; i < DUST; i++) {
        const r = 3 + Math.random() * 3.5, th = Math.random() * Math.PI * 2, ph = Math.acos(2 * Math.random() - 1);
        dPos.set([r * Math.sin(ph) * Math.cos(th), r * Math.cos(ph) * 0.55, r * Math.sin(ph) * Math.sin(th)], i * 3);
        dSeed[i] = Math.random(); dMix[i] = Math.random() < 0.35 ? 1 : 0;
      }
      const dustGeo = new THREE.BufferGeometry();
      dustGeo.setAttribute("position", new THREE.BufferAttribute(dPos, 3));
      dustGeo.setAttribute("aSeed", new THREE.BufferAttribute(dSeed, 1));
      dustGeo.setAttribute("aMix", new THREE.BufferAttribute(dMix, 1));
      const dustMat = new THREE.ShaderMaterial({
        uniforms: { uTime: { value: 0 }, uPR: { value: dpr }, uSize: { value: 42 },
                    uGold: { value: new THREE.Color(0xe8d7a0) }, uLime: { value: new THREE.Color(0xd6ff4d) } },
        vertexShader: `
          attribute float aSeed; attribute float aMix;
          uniform float uTime; uniform float uPR; uniform float uSize;
          varying float vA; varying float vMix;
          void main() {
            vec3 p = position;
            p.y += sin(uTime * 0.25 + aSeed * 30.0) * 0.12;
            vec4 mv = modelViewMatrix * vec4(p, 1.0);
            vA = 0.35 + 0.65 * (0.5 + 0.5 * sin(uTime * (0.6 + aSeed * 1.4) + aSeed * 40.0));
            vMix = aMix;
            gl_PointSize = uSize * uPR * (0.35 + aSeed) / -mv.z;
            gl_Position = projectionMatrix * mv;
          }`,
        fragmentShader: `
          uniform vec3 uGold; uniform vec3 uLime;
          varying float vA; varying float vMix;
          void main() {
            float d = length(gl_PointCoord - 0.5);
            float a = smoothstep(0.5, 0.0, d);
            gl_FragColor = vec4(mix(uGold, uLime, vMix), a * vA * 0.75);
          }`,
        transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      });
      const dust = new THREE.Points(dustGeo, dustMat);
      group.add(dust);

      // --- Post-processing ---
      const composer = new EffectComposer(renderer);
      composer.setPixelRatio(dpr);
      composer.setSize(W(), H());
      composer.addPass(new RenderPass(scene, camera));
      const bloom = new UnrealBloomPass(new THREE.Vector2(W() / 2, H() / 2), 0.7, 0.5, 0.86);
      composer.addPass(bloom);
      composer.addPass(new OutputPass());

      // --- Interaksi: titik pointer di bidang z=0 → ruang lokal grup ---
      const raycaster = new THREE.Raycaster();
      const ndc = new THREE.Vector2();
      const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
      const hitW = new THREE.Vector3(), hitL = new THREE.Vector3();
      const pointer = { x: 0, y: 0, tx: 0, ty: 0, inside: false, dirty: false, active: 0 };
      const view = host.closest("#login-view");
      view.addEventListener("pointermove", e => {
        pointer.tx = (e.clientX / window.innerWidth - 0.5) * 2;
        pointer.ty = (e.clientY / window.innerHeight - 0.5) * 2;
        const r = renderer.domElement.getBoundingClientRect();
        pointer.inside = e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom;
        if (pointer.inside) {
          ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
          pointer.dirty = true;
        }
      }, { passive: true });
      view.addEventListener("pointerleave", () => { pointer.inside = false; }, { passive: true });
      let pulseAt = -10;                         // klik di area hero → siklus sekam → biochar
      const heroEl = host.closest(".login-hero");
      if (heroEl) heroEl.addEventListener("pointerdown", () => { pulseAt = clock.elapsedTime; }, { passive: true });

      const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), e3 = new THREE.Euler(),
            v = new THREE.Vector3(), sc = new THREE.Vector3();
      const easeOut = x => 1 - Math.pow(1 - x, 3);
      const clock = new THREE.Clock();
      let introT = 0, introStart = -1, perfN = 0, perfSum = 0, degraded = 0;

      const frame = () => {
        if (!this.running) return;
        this.raf = requestAnimationFrame(frame);
        const dt = Math.min(clock.getDelta(), 0.05);
        const t = clock.elapsedTime;
        // Intro memakai waktu nyata → tetap selesai ±2,6 dtk walau FPS perangkat rendah
        if (introStart < 0) introStart = performance.now();
        introT = Math.min((performance.now() - introStart) / 2600, 1);
        const intro = easeOut(introT);

        // Siklus klik: amplop 0→1→0 selama 2,4 dtk
        const pk = (t - pulseAt) / 2.4;
        const pulse = pk >= 0 && pk <= 1 ? Math.sin(Math.PI * pk) : 0;

        pointer.x += (pointer.tx - pointer.x) * 0.04;
        pointer.y += (pointer.ty - pointer.y) * 0.04;
        group.rotation.y = t * 0.08 + pointer.x * 0.25;
        group.rotation.x = 0.35 + pointer.y * 0.12;
        camera.position.z = 9 + (1 - intro) * 3.5;
        group.updateMatrixWorld();

        pointer.active += ((pointer.inside ? 1 : 0) - pointer.active) * 0.08;
        if (pointer.dirty) {
          raycaster.setFromCamera(ndc, camera);
          if (raycaster.ray.intersectPlane(plane, hitW)) hitL.copy(group.worldToLocal(hitW.clone()));
          pointer.dirty = false;
        }

        for (let i = 0; i < HUSKS; i++) {
          const s = seeds[i];
          const cyc = (t * 0.05 * s.ds + i / HUSKS) % 1;
          const pull = Math.max(cyc > 0.82 ? (cyc - 0.82) / 0.18 : 0, pulse * 0.85);
          const a = s.a + t * 0.12 * s.ds;
          const r = s.r * (1 - pull * 0.75) * (1 + (1 - intro) * s.intro);
          v.set(Math.cos(a) * r, s.y * (1 - pull) + Math.sin(t * s.ds + i) * 0.05, Math.sin(a) * r);

          // Menyingkir dari kursor (radius 0,9 di ruang lokal), dihaluskan per butir
          const o = i * 3;
          let px = 0, py = 0, pz = 0;
          if (pointer.active > 0.01) {
            const dx = v.x - hitL.x, dy = v.y - hitL.y, dz = v.z - hitL.z;
            const d = Math.sqrt(dx * dx + dy * dy + dz * dz);
            if (d < 0.9 && d > 1e-4) {
              const f = (1 - d / 0.9) ** 2 * 0.7 * pointer.active / d;
              px = dx * f; py = dy * f; pz = dz * f;
            }
          }
          offs[o] += (px - offs[o]) * 0.12; offs[o + 1] += (py - offs[o + 1]) * 0.12; offs[o + 2] += (pz - offs[o + 2]) * 0.12;
          v.x += offs[o]; v.y += offs[o + 1]; v.z += offs[o + 2];

          e3.set(s.sx + t * s.ds, s.sy + t * 0.6, s.sz);
          q.setFromEuler(e3);
          const k = (1 - pull * 0.9) * (s.s * 6) * intro;
          sc.set(k, k, k);
          husks.setMatrixAt(i, m4.compose(v, q, sc));
        }
        husks.instanceMatrix.needsUpdate = true;

        const pScale = 1 + pulse * 0.25;
        for (let i = 0; i < PELLETS; i++) {
          const c = core[i];
          const breathe = (1 + Math.sin(t * 1.2 + i) * 0.04) * pScale;
          v.copy(c.p).multiplyScalar(breathe * (0.4 + 0.6 * intro));
          e3.set(c.rx + t * 0.3, c.ry + t * 0.2, 0);
          q.setFromEuler(e3);
          sc.setScalar(intro);
          pellets.setMatrixAt(i, m4.compose(v, q, sc));
        }
        pellets.instanceMatrix.needsUpdate = true;

        glow.intensity = (3.5 + Math.sin(t * 1.4) * 0.8) * (1 + pulse * 0.6);
        rimU.uRimStrength.value = 1.4 + pulse * 0.7;
        bloom.strength = 0.7 + pulse * 0.35;
        ring.material.opacity = 0.5 * intro;
        dustMat.uniforms.uTime.value = t;
        composer.render();

        // Penurun kualitas otomatis: rata-rata >29 ms/frame selama 90 frame → matikan bloom, lalu turunkan DPR
        perfSum += dt; perfN++;
        if (perfN >= 90) {
          if (perfSum / perfN > 0.029 && introT >= 1) {
            if (degraded === 0) { bloom.enabled = false; degraded = 1; }
            else if (degraded === 1 && dpr > 1) {
              dpr = 1; renderer.setPixelRatio(1); composer.setPixelRatio(1); dustMat.uniforms.uPR.value = 1; resize(); degraded = 2;
            }
          }
          perfN = 0; perfSum = 0;
        }
      };

      const resize = () => {
        renderer.setSize(W(), H(), false);
        composer.setSize(W(), H());
        camera.aspect = W() / H();
        camera.updateProjectionMatrix();
      };
      new ResizeObserver(resize).observe(host);

      // Jeda saat tab tak terlihat atau kanvas keluar layar
      this.visible = true;
      new IntersectionObserver(([en]) => { this.visible = en.isIntersecting; this.visible ? this.start() : this.pause(); })
        .observe(host);
      document.addEventListener("visibilitychange", () => document.hidden ? this.pause() : this.start());

      this.ctx = { frame, clock };
      this.state = "ready";
      host.classList.add("has-webgl");
      if (currentRole() === "login") this.start();
    },
    start() {
      if (this.state !== "ready" || this.running || document.hidden || this.visible === false) return;
      if (currentRole() !== "login") return;
      this.running = true;
      this.ctx.frame();
    },
    pause() { this.running = false; if (this.raf) cancelAnimationFrame(this.raf); },
    stop() { this.pause(); },
  };

  // ------------------------------------------------------------------
  // 4. ERGONOMI LAPANGAN — stepper kg, foto kamera, tabel tersortir, konfirmasi transaksi, banner sinyal.
  //    Tidak mengubah logika bisnis: tombol stepper menulis nilai + memicu event input/change (pratinjau harga
  //    yang sudah ada ikut jalan); konfirmasi membungkus fungsi global yang ada lalu memanggil aslinya.
  // ------------------------------------------------------------------
  const STEPPER_IDS = { "f-qty": "kg", "v-weight": "kg", "dr-qty": "kg" };
  const STEPS = [-50, 50, 100, 500, 1000];

  function addStepper(input) {
    if (input.dataset.uiStepper) return;
    input.dataset.uiStepper = "1";
    input.setAttribute("inputmode", "numeric");
    const unit = STEPPER_IDS[input.id] || "kg";
    const row = document.createElement("div");
    row.className = "qty-stepper";
    row.setAttribute("role", "group");
    row.setAttribute("aria-label", "Ubah jumlah cepat");
    row.innerHTML = STEPS.map(d => {
      const label = Math.abs(d) >= 1000 ? `${d > 0 ? "+" : "−"}${Math.abs(d) / 1000} ton` : `${d > 0 ? "+" : "−"}${Math.abs(d)}`;
      return `<button type="button" class="btn btn-secondary qty-step" data-d="${d}"
                aria-label="${d > 0 ? "Tambah" : "Kurangi"} ${Math.abs(d)} ${unit}">${label}</button>`;
    }).join("") + (truckKg() ? `<button type="button" class="btn btn-secondary qty-step" data-d="${truckKg()}"
                aria-label="Tambah satu truk (${truckKg()} ${unit})" title="Kapasitas 1 bak truk = volume × densitas biomassa">+1 truk</button>` : "");
    row.addEventListener("click", e => {
      const b = e.target.closest(".qty-step");
      if (!b) return;
      const min = input.min !== "" ? Number(input.min) : 0;
      const max = input.max !== "" ? Number(input.max) : Infinity;
      const next = Math.min(max, Math.max(min, (Number(input.value) || 0) + Number(b.dataset.d)));
      input.value = String(next);
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
    input.insertAdjacentElement("afterend", row);
  }

  // Biomassa dibatasi VOLUME bak: 1 truk = m³ bak × densitas curah (parameter), tidak melebihi muatan berat maksimum
  function truckKg() {
    if (typeof PV !== "function") return 0;
    const kg = Math.min(PV("logistik.vehicle_m3", 30) * PV("logistik.bulk_density_kg_m3", 110), PV("logistik.vehicle_payload_kg", 5000));
    return Math.round(kg / 50) * 50;
  }

  // Foto bukti: kamera → kompres DIJAMIN ≤ 300 KB (turunkan mutu JPEG lalu resolusi bertahap) → unggah → isi URL.
  // Encode ulang lewat canvas membuang metadata EXIF (lokasi rumah, info perangkat); orientasi EXIF diterapkan dulu
  // agar foto HP tidak miring. Hemat kuota untuk sinyal pedesaan.
  const MAX_PHOTO_BYTES = 300 * 1024;
  async function compressImage(file, maxBytes = MAX_PHOTO_BYTES) {
    const bmp = await createImageBitmap(file, { imageOrientation: "from-image" }).catch(() =>
      createImageBitmap(file).catch(() => null));
    if (!bmp) return file;
    const c = document.createElement("canvas");
    let blob = null;
    for (const side of [1600, 1280, 1024, 800, 640]) {
      const scale = Math.min(1, side / Math.max(bmp.width, bmp.height));
      c.width = Math.round(bmp.width * scale); c.height = Math.round(bmp.height * scale);
      c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
      for (const q of [0.75, 0.62, 0.5, 0.4]) {
        blob = await new Promise(r => c.toBlob(r, "image/jpeg", q));
        if (blob && blob.size <= maxBytes) return new File([blob], "bukti.jpg", { type: "image/jpeg" });
      }
    }
    return blob ? new File([blob], "bukti.jpg", { type: "image/jpeg" }) : file;
  }
  window.BiochainImage = { compress: compressImage, MAX_PHOTO_BYTES };   // dipakai uji e2e & modul lain

  function addPhotoPicker(input) {
    if (input.dataset.uiPhoto) return;
    input.dataset.uiPhoto = "1";
    const wrap = document.createElement("div");
    wrap.className = "photo-pick";
    const id = `${input.id}-cam`;
    wrap.innerHTML = `<label class="btn btn-secondary photo-pick-btn" for="${id}">📷 Ambil foto</label>
      <input type="file" id="${id}" accept="image/*" capture="environment" class="visually-hidden">
      <span class="photo-pick-status kpi-lbl" aria-live="polite"></span>`;
    input.insertAdjacentElement("afterend", wrap);
    const file = wrap.querySelector("input[type=file]");
    const status = wrap.querySelector(".photo-pick-status");
    file.addEventListener("change", async () => {
      const f = file.files && file.files[0];
      if (!f) return;
      status.textContent = "⏳ Mengompres & mengunggah…";
      const small = await compressImage(f);
      const saveOffline = async () => {                  // tanpa sinyal: simpan di HP, terkirim bersama laporannya
        const token = await window.BiochainPhotos.queue(small);
        input.value = token;
        input.dispatchEvent(new Event("input", { bubbles: true }));
        status.textContent = `📵 Foto (${Math.round(small.size / 1024)} KB) disimpan di HP — otomatis terkirim bersama laporan saat ada sinyal.`;
      };
      if (navigator.onLine === false && window.BiochainPhotos) {
        try { await saveOffline(); } catch (err) { status.textContent = `⚠️ ${err.message}`; }
        file.value = "";
        return;
      }
      try {
        const fd = new FormData();
        fd.append("file", small, small.name || "bukti.jpg");
        const data = await api("/api/v1/uploads", { method: "POST", body: fd, timeoutMs: 60000 });
        input.value = data.url;
        input.dispatchEvent(new Event("input", { bubbles: true }));
        status.innerHTML = `✅ Terunggah (${Math.round(data.size_bytes / 1024)} KB)${data.duplicate
            ? " · ⚠️ foto ini pernah diunggah sebelumnya — pastikan bukan foto lama" : ""}
          <img src="${esc(data.url)}" alt="Pratinjau foto bukti" class="photo-thumb">`;
      } catch (err) {
        if ((navigator.onLine === false || err.network || err instanceof TypeError) && window.BiochainPhotos) {
          try { await saveOffline(); } catch (e2) { status.textContent = `⚠️ ${e2.message}`; }
        } else {
          status.textContent = `⚠️ Gagal unggah: ${err.message}`;
        }
      } finally { file.value = ""; }
    });
  }

  // Tabel: klik/Enter pada judul kolom untuk mengurutkan (angka format Indonesia dikenali).
  const parseNum = t => {
    const s = (t || "").replace(/[^\d,.-]/g, "").replace(/\./g, "").replace(",", ".");
    return s && /\d/.test(s) ? Number(s) : NaN;
  };
  function makeSortable(table) {
    if (table.dataset.uiSort || !table.tHead) return;
    table.dataset.uiSort = "1";
    const bodyRows = table.tBodies[0] ? [...table.tBodies[0].rows].filter(r => r.cells.length > 1) : [];
    [...table.tHead.rows[0].cells].forEach((th, idx) => {
      if (th.colSpan > 1 || !th.textContent.trim()) return;
      // Kolom aksi (tombol/input) tidak bermakna diurutkan — dan judulnya jangan jadi tombol palsu
      if (/^(aksi|tawar|qr|pilih|status aksi)$/i.test(th.textContent.trim())) return;
      if (bodyRows.some(r => r.cells[idx] && r.cells[idx].querySelector("button, input, select"))) return;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "th-sort";
      btn.innerHTML = `${th.innerHTML}<span class="th-sort-ind" aria-hidden="true"></span>`;
      th.textContent = "";
      th.appendChild(btn);
      th.setAttribute("aria-sort", "none");
      btn.addEventListener("click", () => {
        const body = table.tBodies[0];
        if (!body) return;
        const rows = [...body.rows].filter(r => r.cells.length > 1);
        if (rows.length < 2) return;
        const dir = th.getAttribute("aria-sort") === "ascending" ? -1 : 1;
        const vals = rows.map(r => (r.cells[idx] ? r.cells[idx].textContent.trim() : ""));
        const numeric = vals.filter(v => !Number.isNaN(parseNum(v))).length >= rows.length * 0.6;
        rows.map((r, i) => [r, vals[i]])
          .sort((a, b) => numeric ? ((parseNum(a[1]) || 0) - (parseNum(b[1]) || 0)) * dir
                                  : a[1].localeCompare(b[1], "id") * dir)
          .forEach(([r]) => body.appendChild(r));
        table.tHead.querySelectorAll("th[aria-sort]").forEach(h => h.setAttribute("aria-sort", "none"));
        th.setAttribute("aria-sort", dir === 1 ? "ascending" : "descending");
      });
    });
  }

  function enhanceField(root) {
    Object.keys(STEPPER_IDS).forEach(id => {
      const el = root.querySelector ? (root.id === id ? root : root.querySelector(`#${id}`)) : null;
      if (el && el.tagName === "INPUT") addStepper(el);
    });
    // :not([type=file]) wajib: input kamera buatan addPhotoPicker ber-id "rcv-photo-<n>-cam" juga cocok dengan
    // awalan ini; tanpa pengecualian, pemilih foto membuat pemilih foto lagi tanpa henti (halaman pabrik crash).
    root.querySelectorAll('#v-photo:not([type=file]), input[id^="rcv-photo-"]:not([type=file])').forEach(addPhotoPicker);
    root.querySelectorAll("table.data-table").forEach(makeSortable);
  }

  // Dialog konfirmasi (dialog native: fokus terkunci & Esc bawaan; tombol 48px; cegah klik ganda)
  function uiConfirm({ title, body, ok = "Ya, lanjutkan", danger = false }) {
    if (typeof HTMLDialogElement === "undefined") return Promise.resolve(window.confirm(`${title}\n\n${body}`));
    return new Promise(resolve => {
      const d = document.createElement("dialog");
      d.className = "ui-confirm";
      d.setAttribute("aria-labelledby", "ui-confirm-title");
      d.innerHTML = `<form method="dialog">
          <h3 id="ui-confirm-title">${esc(title)}</h3>
          <p class="ui-confirm-body">${esc(body)}</p>
          <div class="ui-confirm-actions">
            <button value="no" class="btn btn-secondary">Batal</button>
            <button value="yes" class="btn ${danger ? "btn-danger" : "btn-primary"}">${esc(ok)}</button>
          </div></form>`;
      document.body.appendChild(d);
      let answered = false;
      d.addEventListener("close", () => {
        if (!answered) { answered = true; resolve(d.returnValue === "yes"); }
        d.remove();
      });
      d.showModal();
      d.querySelector('button[value="yes"]').focus();
    });
  }
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const val = id => { const el = $(id); return el ? el.value : ""; };
  const selText = id => { const el = $(id); return el && el.selectedOptions && el.selectedOptions[0] ? el.selectedOptions[0].textContent.trim() : ""; };
  const idr = n => "Rp " + Math.round(Number(n) || 0).toLocaleString("id-ID");
  const kg = n => `${(Number(n) || 0).toLocaleString("id-ID")} kg`;

  const drConfirm = (id, action, who) => (/^(accept|reject)$/.test(action) ? {
    title: action === "accept" ? "Setujui Delivery Request?" : "Tolak Delivery Request?",
    ok: action === "accept" ? "Setujui" : "Tolak", danger: action === "reject",
    body: `DR #${id}: ${action === "accept" ? "harga & tanggal disepakati" : "pengajuan ditolak"}. ${who} langsung menerima keputusan ini.` }
    : null);                                                // 'counter' (tawar balik) tidak perlu konfirmasi

  const CONFIRMS = {
    placeBid: (listingId) => {
      const p = Number(val(`bp-${listingId}`)), q = Number(val(`bq-${listingId}`));
      if (!p || !q) return null;                              // validasi bawaan fungsi asli yang menangani
      return { title: "Kirim tawaran lelang?", ok: "Kirim tawaran",
               body: `${kg(q)} · ${selText(`bs-${listingId}`)} · ${idr(p)}/kg = ${idr(p * q)}. ` +
                     "Tawaran mengikat bila diterima petani." };
    },
    acceptBid: (listingId, bidId) => ({ title: "Terima tawaran ini?", ok: "Terima & buat kontrak",
      body: `Menyepakati ${kg(val(`acc-${bidId}`))} untuk listing #${listingId}. Stok listing berkurang dan kontrak QR terbit.` }),
    cancelListing: (listingId) => ({ title: "Batalkan listing?", ok: "Batalkan listing", danger: true,
      body: `Listing #${listingId} ditutup; tawaran yang masih aktif tidak bisa diterima lagi.` }),
    paySettlement: (id) => (val(`str-${id}`).trim().length < 3 ? null : {
      title: "Tandai sudah dibayar?", ok: "Ya, sudah dibayar",
      body: `Settlement #${id} dicatat lunas dengan bukti "${val(`str-${id}`).trim()}". Catatan pembayaran tidak bisa diubah.` }),
    submitQc: (id) => {
      const net = Number(val(`qcgross-${id}`)) - Number(val(`qctare-${id}`));
      return { title: "Simpan hasil QC?", ok: "Simpan QC",
               body: `Lot #${id}: netto ${kg(net)}, kadar air ${val(`qcm-${id}`) || "–"}%. ` +
                     "Keputusan terima/tolak dan tagihan pengepul dibuat otomatis." };
    },
    driverComplete: (routeId) => ({ title: "Selesaikan rute?", ok: "Selesaikan rute",
      body: `Rute #${routeId} ditutup. Pastikan semua titik sudah dijemput atau dilaporkan gagal.` }),
    reportStopFailed: (stopId) => ({ title: "Laporkan penjemputan gagal?", ok: "Laporkan gagal", danger: true,
      body: `Alasan: ${selText(`fail-${stopId}`) || "lainnya"}. Pabrik akan menata ulang rute.` }),
    drRespond: (id, action) => drConfirm(id, action, "Pengepul"),
    myDrRespond: (id, action) => drConfirm(id, action, "Pabrik"),
  };
  function installConfirms() {
    Object.entries(CONFIRMS).forEach(([name, make]) => {
      const orig = window[name];
      if (typeof orig !== "function" || orig.__uiConfirm) return;
      const wrapped = async function (...args) {
        const opts = make(...args);
        if (opts && !(await uiConfirm(opts))) return undefined;
        return orig.apply(this, args);
      };
      wrapped.__uiConfirm = true;
      window[name] = wrapped;
    });
  }

  // Banner sinyal — satu indikator (menggantikan pill status jaringan bawaan): offline, sesi berakhir, antrean.
  function syncBanner() {
    let el = $("signal-banner");
    if (!el) {
      el = document.createElement("div");
      el.id = "signal-banner";
      el.setAttribute("role", "status");
      el.setAttribute("aria-live", "polite");
      document.body.prepend(el);
      el.addEventListener("click", e => {
        if (!e.target.closest("[data-flush]")) return;
        try { flushOutbox(); trackFlush(); } catch {}
      });
    }
    let pending = 0, gps = 0, relogin = false;
    try { pending = STATE.user ? myOutbox().length : 0; } catch {}
    try { gps = TRACK.pending || 0; } catch {}
    try { relogin = !!needsLogin; } catch {}
    const offline = navigator.onLine === false;
    const extra = [pending ? `${pending} data antre` : "", gps ? `${gps} titik GPS` : ""].filter(Boolean).join(" · ");
    let html = "", cls = "";
    if (offline) {
      cls = "banner-pending";
      html = `<span aria-hidden="true">📵</span><span><b>Mode Hemat Sinyal.</b> Data yang Anda simpan aman di HP ini dan
              terkirim otomatis saat sinyal kembali.${extra ? ` <b>${extra}</b>.` : ""}</span>`;
    } else if (relogin) {
      cls = "banner-error";
      html = `<span aria-hidden="true">🔐</span><span><b>Sesi berakhir.</b> Antrean data tetap aman — masuk lagi untuk mengirimnya.</span>`;
    } else if (pending || gps) {
      cls = "banner-info";
      html = `<span aria-hidden="true">📶</span><span>Sinyal tersedia — <b>${extra}</b> menunggu dikirim.</span>
              <button type="button" class="btn btn-secondary btn-sm" data-flush>Kirim sekarang</button>`;
    }
    el.className = html ? `banner signal-banner ${cls}` : "signal-banner is-hidden";
    if (el.dataset.html !== html) { el.innerHTML = html; el.dataset.html = html; }
  }

  // Gerbang masuk: daftar akun uji tidak lagi terbuka — dilipat di "Akun uji coba (mode demo)"; hilang bila
  // server produksi (DEMO_MODE=False → daftar kosong).
  function syncDemoAccounts() {
    const box = $("demo-hint");
    if (!box || box.tagName !== "DETAILS") return;
    const has = !!box.querySelector(".demo-chip");
    box.hidden = !has;
  }

  // ------------------------------------------------------------------
  // BOOT
  // ------------------------------------------------------------------
  function boot() {
    enhance(document.body);
    syncNavCurrent();
    applyTheme();

    const tgl = $("btn-theme-toggle");
    if (tgl) tgl.addEventListener("click", toggleTheme);

    domObserver.observe(document.body, { childList: true, subtree: true });

    // Tema mengikuti peran: tampil/sembunyi view & teks badge peran berubah saat login/ganti persona
    const viewObs = new MutationObserver(applyTheme);
    ["app-view", "login-view"].forEach(id => $(id) && viewObs.observe($(id), { attributes: true, attributeFilter: ["style"] }));
    if ($("u-role-badge")) viewObs.observe($("u-role-badge"), { childList: true, characterData: true, subtree: true });

    const navObs = new MutationObserver(syncNavCurrent);
    if ($("nav-tabs")) navObs.observe($("nav-tabs"), { attributes: true, attributeFilter: ["class"], subtree: true });
    if ($("role-selector-grid")) navObs.observe($("role-selector-grid"), { attributes: true, attributeFilter: ["class"], subtree: true });

    installConfirms();
    syncBanner();
    ["online", "offline"].forEach(ev => window.addEventListener(ev, () => setTimeout(syncBanner, 50)));
    setInterval(syncBanner, 4000);
    syncDemoAccounts();
    if ($("demo-accounts-for-gate")) new MutationObserver(syncDemoAccounts).observe($("demo-accounts-for-gate"), { childList: true });

    const modalObs = new MutationObserver(muts => muts.forEach(m => onModalChange(m.target)));
    document.querySelectorAll(".modal-overlay").forEach(o => modalObs.observe(o, { attributes: true, attributeFilter: ["class"] }));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
