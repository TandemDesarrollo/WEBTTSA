/* Execute with: node tests/test_contact_frontend.js
 * Runs the actual contact handler against a small DOM and simulated fetch.
 * No HTTP or SMTP connection is made. Also usable in a plain JS runtime.
 */
async function runContactFrontendTests(source) {
  const start = source.indexOf('// Formulario de contacto');
  const end = source.lastIndexOf('})();');
  if (start < 0 || end <= start) throw new Error('No se pudo aislar el manejador de contacto');
  const handlerSource = source.slice(start, end);
  const results = [];
  const initialValues = {
    nombre: '  María Pérez  ', empresa: 'Compañía Ñandú', email: 'maria@example.com',
    telefono: '+54 11 5555 1234', industria: 'Fintech', mensaje: 'Consulta de prueba.\nGracias.'
  };

  function assert(condition, message) {
    if (!condition) throw new Error(message);
  }

  function setup(fetchReply) {
    const calls = [];
    const timers = new Map();
    const attrs = new Map();
    const status = { textContent: '', className: '' };
    const buttonAttrs = new Map();
    const button = {
      disabled: false, textContent: 'Enviar consulta',
      setAttribute: (key, value) => buttonAttrs.set(key, value),
      removeAttribute: key => buttonAttrs.delete(key)
    };
    const fields = Object.entries(initialValues).map(([name, value]) => ({
      name, value, required: ['nombre', 'empresa', 'email'].includes(name),
      attributes: new Map(), invalid: false, disabled: false,
      classList: { toggle() {} },
      setAttribute(key, value) { this.attributes.set(key, value); },
      checkValidity() {
        // All values in this harness are assigned programmatically. Browsers do
        // not set validity.tooLong for these assignments, even above maxlength.
        // Length must therefore be rejected by the handler's explicit guard.
        return !this.invalid
          && (name !== 'email' || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(this.value));
      },
      focus() { this.focused = true; }
    }));
    let submitHandler;
    const form = {
      action: 'https://example.test/api/contact', resetCount: 0,
      querySelector: () => button,
      querySelectorAll(selector) {
        return selector === '[required]' ? fields.filter(field => field.required) : fields;
      },
      addEventListener(event, callback) { if (event === 'submit') submitHandler = callback; },
      setAttribute: (key, value) => attrs.set(key, value),
      removeAttribute: key => attrs.delete(key),
      reset() { this.resetCount += 1; fields.forEach(field => { field.value = ''; }); }
    };
    const document = {
      getElementById(id) {
        if (id === 'contactForm') return form;
        if (id === 'formStatus') return status;
        if (id === 'year') return {};
        throw new Error(`Elemento inesperado: ${id}`);
      }
    };
    class SimulatedFormData {
      constructor() { this.entries = fields.filter(field => !field.disabled).map(field => [field.name, field.value]); }
      [Symbol.iterator]() { return this.entries[Symbol.iterator](); }
    }
    class SimulatedAbortController {
      constructor() {
        const listeners = [];
        this.signal = {
          aborted: false,
          addEventListener(type, callback) { if (type === 'abort') listeners.push(callback); }
        };
        this.abort = () => {
          this.signal.aborted = true;
          listeners.forEach(callback => callback());
        };
      }
    }
    const fetch = (url, options) => {
      calls.push({ url, options });
      return fetchReply(url, options);
    };
    let timerId = 0;
    new Function('document', 'fetch', 'FormData', 'AbortController', 'setTimeout', 'clearTimeout', handlerSource)(
      document, fetch, SimulatedFormData, SimulatedAbortController,
      (callback, delay) => { timers.set(++timerId, { callback, delay }); return timerId; },
      id => timers.delete(id)
    );
    assert(typeof submitHandler === 'function', 'No se registró el submit');
    return {
      form, fields, status, button, buttonAttrs, attrs, calls, timers,
      submit() {
        let prevented = false;
        const pending = submitHandler({ preventDefault() { prevented = true; } });
        assert(prevented, 'El submit debe impedir la navegación nativa');
        return Promise.resolve(pending);
      }
    };
  }

  const response = (data, ok = true) => Promise.resolve({ ok, json: async () => data });
  const values = env => env.fields.map(field => field.value);
  function assertFieldsDisabled(env, expected) {
    const names = Object.keys(initialValues);
    assert(env.fields.length === names.length, 'Debe comprobar todos los campos del formulario');
    names.forEach(name => {
      const field = env.fields.find(candidate => candidate.name === name);
      assert(field, `Falta el campo ${name} en la simulación`);
      assert(field.disabled === expected, `El campo ${name} debe quedar ${expected ? 'bloqueado' : 'habilitado'}`);
    });
  }
  function assertPending(env) {
    assert(env.button.disabled === true, 'Debe deshabilitar el botón mientras espera');
    assertFieldsDisabled(env, true);
    assert(env.attrs.get('aria-busy') === 'true', 'Debe marcar el formulario ocupado');
    assert(env.buttonAttrs.get('aria-busy') === 'true', 'Debe marcar el botón ocupado');
  }
  function assertRestored(env) {
    assert(env.button.disabled === false, 'Debe rehabilitar el botón');
    assert(env.button.textContent === 'Enviar consulta', 'Debe restaurar el texto del botón');
    assertFieldsDisabled(env, false);
    assert(!env.attrs.has('aria-busy'), 'Debe quitar aria-busy del formulario');
    assert(!env.buttonAttrs.has('aria-busy'), 'Debe quitar aria-busy del botón');
    assert(env.timers.size === 0, 'Debe limpiar el temporizador');
  }
  function assertFailure(env, before) {
    assert(env.form.resetCount === 0, 'No debe borrar datos tras un fallo');
    assert(JSON.stringify(values(env)) === JSON.stringify(before), 'Debe conservar lo escrito');
    assert(env.status.className.includes('err'), 'Debe mostrar estado de error');
    assert(env.status.textContent.trim().length > 0, 'Debe explicar el error');
    assertRestored(env);
  }
  async function test(name, action) {
    try { await action(); results.push(name); }
    catch (error) { throw new Error(`${name}: ${error.message}`); }
  }

  await test('awaits confirmation, prevents duplicate requests, then resets on success', async () => {
    let resolve;
    const env = setup(() => new Promise(done => { resolve = done; }));
    const pending = env.submit();
    assertPending(env);
    assert(env.form.resetCount === 0, 'No debe borrar datos antes de confirmar');
    assert(!env.status.className.includes('ok'), 'No debe anunciar éxito antes de confirmar');
    await env.submit();
    assert(env.calls.length === 1, 'El segundo submit no debe duplicar el envío');
    const { url, options } = env.calls[0];
    assert(url === env.form.action || url === '/api/contact', 'Debe usar el endpoint canónico');
    assert(options.method === 'POST', 'Debe usar POST');
    assert(options.headers['Content-Type'] === 'application/json', 'Debe enviar JSON');
    const payload = JSON.parse(options.body);
    Object.entries(initialValues).forEach(([name, value]) => {
      assert(payload[name] === value.trim(), `Debe enviar el campo ${name} completo y sin espacios exteriores`);
    });
    resolve({ ok: true, json: async () => ({ ok: true, message: 'Consulta aceptada.' }) });
    await pending;
    assert(env.form.resetCount === 1, 'Debe borrar datos al confirmar');
    assert(env.status.className.includes('ok'), 'Debe mostrar estado de éxito');
    assert(env.status.textContent === 'Consulta aceptada.', 'Debe mostrar message del servidor');
    assertRestored(env);
  });

  await test('shows message when error is omitted', async () => {
    let resolve;
    const env = setup(() => new Promise(done => { resolve = done; }));
    const before = values(env);
    const pending = env.submit();
    assertPending(env);
    resolve({ ok: false, json: async () => ({ ok: false, message: 'Servicio temporalmente indisponible.' }) });
    await pending;
    assertFailure(env, before);
    assert(env.status.textContent === 'Servicio temporalmente indisponible.', 'Debe mostrar message sin necesitar error');
  });

  await test('shows optional backend error', async () => {
    const env = setup(() => response({ ok: false, message: 'Solicitud rechazada.', error: 'Revisá el email.' }, false));
    const before = values(env);
    await env.submit();
    assertFailure(env, before);
    assert(['Solicitud rechazada.', 'Revisá el email.'].includes(env.status.textContent), 'Debe mostrar el detalle del servidor');
  });

  await test('does not accept ok false even on HTTP 200', async () => {
    const env = setup(() => response({ ok: false, message: 'No se aceptó la consulta.' }));
    const before = values(env);
    await env.submit();
    assertFailure(env, before);
  });

  await test('does not accept an HTTP error even if JSON says ok true', async () => {
    const env = setup(() => response({ ok: true, message: 'Respuesta inconsistente.' }, false));
    const before = values(env);
    await env.submit();
    assertFailure(env, before);
  });

  await test('rejects incomplete or incorrectly typed success responses', async () => {
    for (const data of [null, {}, { message: 'Falta ok.' }, { ok: 'true' }, { ok: 1 }]) {
      const env = setup(() => response(data));
      const before = values(env);
      await env.submit();
      assertFailure(env, before);
    }
  });

  await test('preserves data when JSON cannot be decoded', async () => {
    const env = setup(() => Promise.resolve({ ok: false, json: async () => { throw new SyntaxError('HTML from proxy'); } }));
    const before = values(env);
    await env.submit();
    assertFailure(env, before);
  });

  await test('preserves data after network failure', async () => {
    const env = setup(() => Promise.reject(new TypeError('Simulated network failure')));
    const before = values(env);
    await env.submit();
    assertFailure(env, before);
  });

  await test('invalid required values and email never call fetch', async () => {
    for (const [name, value] of [['nombre', '   '], ['empresa', ''], ['email', 'invalid-email']]) {
      const env = setup(() => { throw new Error('No debe iniciar fetch'); });
      const field = env.fields.find(field => field.name === name);
      field.value = value;
      await env.submit();
      assert(env.calls.length === 0, 'No debe enviar datos inválidos');
      assert(env.form.resetCount === 0, 'No debe borrar datos inválidos');
      assert(field.focused === true, 'Debe enfocar el primer campo inválido');
      assert(env.button.disabled === false, 'No debe bloquear el formulario inválido');
      assert(env.status.className.includes('err'), 'Debe indicar validación fallida');
    }
  });

  await test('rejects programmatically assigned values above maxlength', async () => {
    const limits = { nombre: 120, empresa: 160, email: 254, telefono: 60, mensaje: 5000 };
    for (const [name, limit] of Object.entries(limits)) {
      const env = setup(() => response({ ok: true, message: 'No debe llegar al servidor.' }));
      const field = env.fields.find(candidate => candidate.name === name);
      field.maxLength = limit;
      field.value = name === 'email'
        ? 'a'.repeat(limit + 1 - '@example.com'.length) + '@example.com'
        : 'x'.repeat(limit + 1);
      assert(field.value.length === limit + 1, `El valor de ${name} debe exceder maxlength`);
      assert(field.checkValidity() === true, `La validación nativa no debe rechazar el valor programático de ${name}`);
      const before = values(env);
      await env.submit();
      assert(env.calls.length === 0, `No debe enviar ${name} por encima de maxlength`);
      assert(env.form.resetCount === 0, 'Debe conservar los datos inválidos');
      assert(JSON.stringify(values(env)) === JSON.stringify(before), `Debe conservar el valor de ${name}`);
      assert(field.focused === true, `Debe enfocar ${name}`);
      assert(env.status.className.includes('err'), 'Debe mostrar el fallo de validación');
      assertRestored(env);
    }
  });

  await test('can submit again after a failure', async () => {
    let attempt = 0;
    const env = setup(() => ++attempt === 1
      ? response({ ok: false, message: 'Fallo temporal.' }, false)
      : response({ ok: true, message: 'Consulta aceptada.' }));
    const before = values(env);
    await env.submit();
    assertFailure(env, before);
    await env.submit();
    assert(env.calls.length === 2, 'Debe permitir un nuevo envío tras el fallo');
    assert(env.form.resetCount === 1, 'Solo el envío aceptado debe borrar datos');
    assertRestored(env);
  });

  return { passed: results.length, cases: results };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { runContactFrontendTests };
  if (require.main === module) {
    const fs = require('node:fs');
    const path = require('node:path');
    const source = fs.readFileSync(path.join(__dirname, '..', 'script.js'), 'utf8');
    runContactFrontendTests(source).then(
      result => process.stdout.write(JSON.stringify(result) + '\n'),
      error => { process.stderr.write(error.stack + '\n'); process.exitCode = 1; }
    );
  }
}
