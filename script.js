// Tandem Technology — interacciones del sitio
(() => {
  const nav = document.getElementById('nav');
  const toggle = document.getElementById('navToggle');
  const links = document.getElementById('navLinks');

  // Nav: fondo sólido al hacer scroll
  const onScroll = () => nav.classList.toggle('is-scrolled', window.scrollY > 40);
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

  // Menú móvil
  const setMenu = (open) => {
    nav.classList.toggle('is-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Cerrar menú' : 'Abrir menú');
  };
  toggle.addEventListener('click', () => setMenu(!nav.classList.contains('is-open')));
  links.querySelectorAll('a').forEach(a => a.addEventListener('click', () => setMenu(false)));
  document.addEventListener('keydown', e => { if (e.key === 'Escape') setMenu(false); });

  // Aparición de elementos al entrar en pantalla (escalonado por grupo)
  const reveals = document.querySelectorAll('.reveal');
  const animateCount = (el) => {
    const target = Number(el.dataset.count);
    const prefix = el.dataset.prefix || '';
    const suffix = el.dataset.suffix || '';
    const start = performance.now();
    const dur = 1400;
    const tick = (now) => {
      const p = Math.min((now - start) / dur, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = prefix + Math.round(target * eased) + suffix;
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };

  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        const el = entry.target;
        const siblings = [...el.parentElement.children].filter(c => c.classList.contains('reveal'));
        el.style.transitionDelay = `${Math.min(siblings.indexOf(el), 5) * 90}ms`;
        el.classList.add('is-visible');
        el.querySelectorAll('[data-count]').forEach(animateCount);
        io.unobserve(el);
      });
    }, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });
    reveals.forEach(el => io.observe(el));
  } else {
    reveals.forEach(el => el.classList.add('is-visible'));
    document.querySelectorAll('[data-count]').forEach(el => {
      el.textContent = (el.dataset.prefix || '') + el.dataset.count + (el.dataset.suffix || '');
    });
  }

  // Hero: red animada de conectores (canvas)
  (() => {
    const canvas = document.getElementById('heroNet');
    const ctx = canvas.getContext('2d');
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    // Paletas por tema: el índice 3 es el color "neutro" (mayoría de los nodos)
    const PALETTES = {
      dark:  { nodes: ['232,88,42', '176,104,143', '255,180,151', '255,255,255'], link: '255,190,170', linkA: .38 },
      light: { nodes: ['232,88,42', '176,104,143', '196,66,26', '94,15,12'], link: '139,26,22', linkA: .26 }
    };
    const pal = () => PALETTES[document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark'];
    let W = 0, H = 0, dpr = 1, nodes = [], pulses = [], linkDist = 150, raf = null, running = true;
    const mouse = { x: -9999, y: -9999 };

    const resize = () => {
      const r = canvas.getBoundingClientRect();
      const prevW = W;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = r.width; H = r.height;
      canvas.width = W * dpr; canvas.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      linkDist = W < 760 ? 120 : 175;
      // En celular la barra del navegador cambia el alto al hacer scroll: no regenerar la red por eso
      if (nodes.length && W === prevW) { if (reduce) draw(); return; }
      const count = Math.round(Math.min(180, Math.max(50, (W * H) / 7500)));
      nodes = Array.from({ length: count }, () => ({
        x: Math.random() * W, y: Math.random() * H,
        vx: (Math.random() - .5) * .35, vy: (Math.random() - .5) * .35,
        r: Math.random() * 1.6 + .8,
        ci: Math.random() < .55 ? 3 : Math.floor(Math.random() * 3),
        hub: Math.random() < .08
      }));
      pulses = [];
      if (reduce) draw();
    };

    const spawnPulse = () => {
      const a = nodes[Math.floor(Math.random() * nodes.length)];
      let best = null, bd = linkDist;
      for (const b of nodes) {
        if (b === a) continue;
        const d = Math.hypot(a.x - b.x, a.y - b.y);
        if (d < bd && Math.random() < .5) { best = b; bd = d; }
      }
      if (best) pulses.push({ a, b: best, t: 0, sp: .012 + Math.random() * .015 });
    };

    const draw = () => {
      ctx.clearRect(0, 0, W, H);
      const P = pal();
      // conexiones
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j];
          const dx = a.x - b.x, dy = a.y - b.y;
          const d2 = dx * dx + dy * dy;
          if (d2 < linkDist * linkDist) {
            const o = 1 - Math.sqrt(d2) / linkDist;
            ctx.strokeStyle = `rgba(${P.link},${o * P.linkA})`;
            ctx.lineWidth = .8;
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
          }
        }
        // conexión con el cursor
        const md = Math.hypot(a.x - mouse.x, a.y - mouse.y);
        if (md < linkDist * 1.3) {
          ctx.strokeStyle = `rgba(232,88,42,${(1 - md / (linkDist * 1.3)) * .55})`;
          ctx.lineWidth = 1;
          ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(mouse.x, mouse.y); ctx.stroke();
        }
      }
      // pulsos de datos viajando por las conexiones
      for (const p of pulses) {
        const x = p.a.x + (p.b.x - p.a.x) * p.t, y = p.a.y + (p.b.y - p.a.y) * p.t;
        const g = ctx.createRadialGradient(x, y, 0, x, y, 7);
        g.addColorStop(0, 'rgba(255,170,120,.95)'); g.addColorStop(1, 'rgba(232,88,42,0)');
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, 7, 0, Math.PI * 2); ctx.fill();
      }
      // nodos
      for (const n of nodes) {
        if (n.hub) {
          ctx.fillStyle = `rgba(${P.nodes[n.ci]},.12)`;
          ctx.beginPath(); ctx.arc(n.x, n.y, n.r * 5, 0, Math.PI * 2); ctx.fill();
        }
        ctx.fillStyle = `rgba(${P.nodes[n.ci]},${n.hub ? .95 : .7})`;
        ctx.beginPath(); ctx.arc(n.x, n.y, n.hub ? n.r * 1.8 : n.r, 0, Math.PI * 2); ctx.fill();
      }
    };

    const step = () => {
      for (const n of nodes) {
        n.x += n.vx; n.y += n.vy;
        if (n.x < -20) n.x = W + 20; else if (n.x > W + 20) n.x = -20;
        if (n.y < -20) n.y = H + 20; else if (n.y > H + 20) n.y = -20;
      }
      pulses = pulses.filter(p => (p.t += p.sp) < 1 && Math.hypot(p.a.x - p.b.x, p.a.y - p.b.y) < linkDist * 1.1);
      if (pulses.length < nodes.length / 6 && Math.random() < .15) spawnPulse();
      draw();
      raf = running ? requestAnimationFrame(step) : null;
    };

    const start = () => { if (!reduce && !raf) { running = true; raf = requestAnimationFrame(step); } };
    const stop = () => { running = false; if (raf) cancelAnimationFrame(raf); raf = null; };

    resize();
    window.addEventListener('resize', resize);
    const heroEl = canvas.parentElement;
    heroEl.addEventListener('mousemove', e => { const r = canvas.getBoundingClientRect(); mouse.x = e.clientX - r.left; mouse.y = e.clientY - r.top; });
    heroEl.addEventListener('mouseleave', () => { mouse.x = mouse.y = -9999; });
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(([e]) => (e.isIntersecting ? start() : stop())).observe(canvas);
    } else start();
    document.addEventListener('visibilitychange', () => (document.hidden ? stop() : start()));
    if (reduce) draw();
    window.addEventListener('themechange', () => { if (reduce) draw(); });
  })();

  // Cómo trabajamos: journey del deudor (pasos + celular sincronizados)
  (() => {
    const journey = document.getElementById('journey');
    if (!journey) return;
    const steps = [...journey.querySelectorAll('.jstep')];
    const screens = [...journey.querySelectorAll('.scr')];
    const dni = document.getElementById('msDni');
    const opts = [...journey.querySelectorAll('.opt')];
    const STEP_MS = 4500;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let current = 0, timer = null, typing = null, inView = false, hover = false;
    journey.style.setProperty('--jtime', `${STEP_MS}ms`);

    const typeDni = () => {
      clearInterval(typing);
      const txt = '28.456.412';
      if (reduce) { dni.textContent = txt; return; }
      let i = 0; dni.textContent = '';
      typing = setInterval(() => { dni.textContent = txt.slice(0, ++i); if (i >= txt.length) clearInterval(typing); }, 140);
    };
    const pickOption = () => {
      opts.forEach(o => o.classList.remove('is-sel'));
      setTimeout(() => opts[1] && opts[1].classList.add('is-sel'), reduce ? 0 : 1300);
    };

    const go = (i) => {
      current = (i + steps.length) % steps.length;
      steps.forEach((s, k) => {
        s.classList.toggle('is-active', k === current);
        s.classList.toggle('is-done', k < current);
        s.setAttribute('aria-current', k === current ? 'step' : 'false');
        const bar = s.querySelector('.jstep__bar');
        bar.style.animation = 'none'; void bar.offsetWidth; bar.style.animation = '';
      });
      screens.forEach((sc, k) => sc.classList.toggle('is-active', k === current));
      if (current === 1) typeDni();
      if (current === 2) pickOption();
      schedule();
    };
    const schedule = () => {
      clearTimeout(timer);
      const paused = reduce || !inView || hover;
      journey.classList.toggle('is-paused', paused);
      if (!paused) timer = setTimeout(() => go(current + 1), STEP_MS);
    };

    steps.forEach((s, k) => s.addEventListener('click', () => go(k)));
    journey.addEventListener('mouseenter', () => { hover = true; schedule(); });
    journey.addEventListener('mouseleave', () => { hover = false; go(current); });
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(([e]) => { inView = e.isIntersecting; schedule(); }, { threshold: .35 }).observe(journey);
    } else { inView = true; }
    go(0);
  })();

  // Mapa de operaciones: resaltar país al pasar por la lista o por el mapa
  document.querySelectorAll('.countries').forEach(card => {
    const hl = (code, on) => card.querySelectorAll(`[data-c="${code}"]`).forEach(el => el.classList.toggle('is-hl', on));
    card.querySelectorAll('.countries__list li, .samap__land path.on').forEach(el => {
      el.addEventListener('mouseenter', () => hl(el.dataset.c, true));
      el.addEventListener('mouseleave', () => hl(el.dataset.c, false));
    });
  });

  // Tecnología: la interfaz se endereza y crece a medida que entra en pantalla
  (() => {
    const stage = document.getElementById('techStage');
    if (!stage) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { stage.style.setProperty('--p', 1); return; }
    let ticking = false;
    const update = () => {
      ticking = false;
      const r = stage.getBoundingClientRect(), vh = window.innerHeight;
      // 0 cuando el borde superior entra por abajo; 1 cuando llega al 25% superior de la pantalla
      const p = Math.min(1, Math.max(0, (vh - r.top) / (vh * .75)));
      stage.style.setProperty('--p', p.toFixed(3));
    };
    const onScroll = () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } };
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    update();
  })();

  // Selector de tema claro / oscuro (se recuerda en este navegador)
  (() => {
    const btn = document.getElementById('themeToggle');
    if (!btn) return;
    const root = document.documentElement;
    const current = () => (root.getAttribute('data-theme') === 'light' ? 'light' : 'dark');
    const label = () => btn.setAttribute('aria-label', current() === 'light' ? 'Cambiar a tema oscuro' : 'Cambiar a tema claro');
    label();
    btn.addEventListener('click', () => {
      const next = current() === 'light' ? 'dark' : 'light';
      root.classList.add('theme-anim');
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('tandem-theme', next); } catch (e) {}
      label();
      window.dispatchEvent(new Event('themechange'));
      setTimeout(() => root.classList.remove('theme-anim'), 450);
    });
  })();

  // Formulario de contacto
  const form = document.getElementById('contactForm');
  const status = document.getElementById('formStatus');
  const submitButton = form.querySelector('[type="submit"]');
  let sending = false;
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (sending) return;

    const fields = [...form.querySelectorAll('input, select, textarea')].filter(input => !input.disabled);
    let firstInvalid = null;
    fields.forEach(input => {
      const withinLimit = !(input.maxLength >= 0) || input.value.length <= input.maxLength;
      const ok = (!input.required || input.value.trim() !== '') && withinLimit && input.checkValidity();
      input.classList.toggle('is-invalid', !ok);
      input.setAttribute('aria-invalid', String(!ok));
      if (!ok && !firstInvalid) firstInvalid = input;
    });
    if (firstInvalid) {
      status.textContent = 'Revisá los campos marcados para continuar.';
      status.className = 'form__status err';
      firstInvalid.focus();
      return;
    }

    const payload = Object.fromEntries([...new FormData(form)].map(([key, value]) => [key, value.trim()]));
    const buttonText = submitButton.textContent;
    sending = true;
    fields.forEach(input => { input.disabled = true; });
    submitButton.disabled = true;
    submitButton.setAttribute('aria-busy', 'true');
    submitButton.textContent = 'Enviando…';
    form.setAttribute('aria-busy', 'true');
    status.textContent = 'Estamos enviando tu consulta…';
    status.className = 'form__status';

    try {
      const response = await fetch(form.action, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      const message = data && typeof data.message === 'string' && data.message.trim() ? data.message : '';
      if (!response.ok || !data || data.ok !== true || !message) {
        const errorMessage = message || (data && typeof data.error === 'string' && data.error.trim() ? data.error : '');
        status.textContent = errorMessage || 'No pudimos confirmar el envío de tu consulta. Podés escribirnos a info@tandemtech.com.ar.';
        status.className = 'form__status err';
        return;
      }
      status.textContent = message;
      status.className = 'form__status ok';
      form.reset();
    } catch (error) {
      status.textContent = 'No pudimos confirmar si tu consulta fue enviada. Para evitar duplicarla, consultanos en info@tandemtech.com.ar.';
      status.className = 'form__status err';
    } finally {
      sending = false;
      fields.forEach(input => { input.disabled = false; });
      submitButton.disabled = false;
      submitButton.removeAttribute('aria-busy');
      submitButton.textContent = buttonText;
      form.removeAttribute('aria-busy');
    }
  });

  document.getElementById('year').textContent = new Date().getFullYear();
})();
