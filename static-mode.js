/* Static mode: the whole app in the browser. The page's /api calls are answered by the Python engine in a Web Worker.
   Live questions call Nebius Token Factory directly with the visitor's own key. The key stays in this browser
   (localStorage) and is sent only to api.tokenfactory.nebius.com. Without a key, real recorded answers are shown. */
(function () {
  const TF = 'https://api.tokenfactory.nebius.com/v1';
  const KEY = 'ail_key';
  const worker = new Worker('pyworker.js');
  const pending = {};
  let seq = 0, inflight = 0, fatal = null, recorded = null;
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  worker.onmessage = (e) => {
    const m = e.data;
    if (m.ready) { setBanner('ready'); return; }
    if (m.fatal) { fatal = m.fatal; setBanner('fatal'); for (const k in pending) pending[k].reject(new Error(fatal)); return; }
    const p = pending[m.id]; if (!p) return; delete pending[m.id];
    m.error ? p.reject(new Error(m.error)) : p.resolve(m.result);
  };
  const call = (fn, ...args) => new Promise((resolve, reject) => {
    if (fatal) return reject(new Error('The analysis engine did not start: ' + fatal));
    const id = ++seq; pending[id] = { resolve, reject }; worker.postMessage({ id, fn, args });
  });
  window.AIL_CALL = call;

  // ---- banner -------------------------------------------------------------------------------------------------
  let banner;
  function setBanner(state) {
    if (!banner) return;
    const txt = {
      loading: 'Starting the analysis engine in your browser (about 3 seconds the first time)…',
      ready: 'Static demo: the analysis runs in your browser (Python in WebAssembly), so nothing you change leaves this page. Live questions use your own Nebius key, if you add one.',
      fatal: 'The analysis engine could not start in this browser: ' + fatal,
    }[state];
    banner.textContent = txt + ' ';
    if (state !== 'loading') { const a = document.createElement('a'); a.href = 'https://github.com/vishalbanwari26/ai-ledger'; a.textContent = 'Source code'; a.style.color = 'var(--accent)'; banner.appendChild(a); }
  }
  document.addEventListener('DOMContentLoaded', () => {
    banner = document.createElement('div');
    banner.style.cssText = 'background:#161b22;border:1px solid #252c36;border-radius:8px;padding:8px 12px;margin:0 0 12px;font-size:12px;color:#8b95a5';
    const main = document.querySelector('main'); main.insertBefore(banner, main.firstChild); setBanner(fatal ? 'fatal' : (window.__ailReady ? 'ready' : 'loading'));
    installKeyCard();
    document.querySelectorAll('a[href$="/api/sample.csv"]').forEach(a => a.addEventListener('click', ev => { ev.preventDefault(); window.AIL_DOWNLOAD('/api/sample.csv'); }));
  });

  // ---- routing the page's /api calls ---------------------------------------------------------------------------
  async function idle() { while (inflight > 0) await sleep(150); await sleep(250); }   // the slow robustness check waits for the rest

  window.AIL_HOOK = async function (url, opt = {}) {
    const method = (opt.method || 'GET').toUpperCase();
    const path = url.split('?')[0];
    if (path === '/api/ask') return liveOrRecordedAsk(JSON.parse(opt.body).question);
    if (path === '/api/brief') return liveOrRecordedBrief();
    let body = '';
    if (path === '/api/upload' && opt.body instanceof FormData) body = JSON.stringify({ text: await opt.body.get('file').text() });
    else if (opt.body) body = typeof opt.body === 'string' ? opt.body : JSON.stringify(opt.body);
    if (path === '/api/robustness') await idle();
    inflight++;
    let out;
    try { out = JSON.parse(await call('handle', method, url, body)); } finally { inflight--; }
    if (out.status >= 400) throw new Error((out.json && out.json.detail) || 'request failed');
    window.__ailReady = true; if (banner && banner.textContent.startsWith('Starting')) setBanner('ready');
    return out.json !== undefined ? out.json : out.text;
  };

  window.AIL_DOWNLOAD = async function (url) {
    const out = JSON.parse(await call('handle', 'GET', url, ''));
    const name = url.includes('actions') ? 'ai-ledger-actions.csv' : 'ai-ledger-sample.csv';
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([out.text], { type: 'text/csv' })); a.download = name; a.click(); URL.revokeObjectURL(a.href);
  };

  // ---- Token Factory, called straight from the browser ---------------------------------------------------------
  const getKey = () => { try { return localStorage.getItem(KEY) || ''; } catch (e) { return ''; } };
  let modelCache = null;

  async function tf(path, init, key) {
    let r;
    try { r = await fetch(TF + path, { ...init, headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + key } }); }
    catch (e) { throw new Error('Could not reach Token Factory from this browser: ' + e.message); }
    if (r.status === 401 || r.status === 403) throw new Error('Token Factory rejected the key (' + r.status + '). Check it and save it again.');
    if (!r.ok) throw new Error('Token Factory error ' + r.status + ': ' + (await r.text()).slice(0, 200));
    return r.json();
  }
  async function models(key) {
    if (modelCache && modelCache.key === key) return modelCache.m;
    const list = await tf('/models', { method: 'GET' }, key);
    const m = JSON.parse(await call('pick_models_json', JSON.stringify(list.data.map(x => x.id))));
    modelCache = { key, m }; return m;
  }
  const chat = (key, model, messages, tools, temperature) =>
    tf('/chat/completions', { method: 'POST', body: JSON.stringify({ model, messages, temperature, ...(tools ? { tools } : {}) }) }, key);

  async function liveAsk(question, key) {
    const m = await models(key);
    const setup = JSON.parse(await call('ask_setup', question));
    const msgs = [{ role: 'system', content: setup.system }, { role: 'user', content: setup.question }];
    const evidence = []; let answer = 'I ran out of steps before reaching an answer.';
    for (let step = 0; step < 6; step++) {
      const msg = (await chat(key, m.reason, msgs, setup.tools, 0.2)).choices[0].message;
      if (!msg.tool_calls || !msg.tool_calls.length) { answer = await call('strip_think', msg.content || ''); break; }
      msgs.push(msg);
      for (const tc of msg.tool_calls) {
        const args = tc.function.arguments || '{}';
        const res = await call('run_tool_json', tc.function.name, args);
        evidence.push({ tool: tc.function.name, args: JSON.parse(args), result: JSON.parse(res) });
        msgs.push({ role: 'tool', tool_call_id: tc.id, content: res });
      }
    }
    let repaired = false;
    if (await call('blames', answer)) {            // one repair pass, then a fixed group-level summary
      repaired = true;
      const rep = JSON.parse(await call('repair_messages', answer));
      answer = await call('strip_think', (await chat(key, m.reason, rep, null, 0.1)).choices[0].message.content || '');
      if (await call('blames', answer)) answer = await call('safe_summary');
    }
    if (setup.targeted) answer = setup.prefix + answer;
    return { answer, evidence, model: m.reason, reframed: setup.targeted, repaired };
  }

  async function liveBrief(key) {
    const m = await models(key);
    const msgs = JSON.parse(await call('brief_messages_json'));
    const r = await chat(key, m.fast, msgs, null, 0.2);
    return { brief: await call('strip_think', r.choices[0].message.content || ''), model: m.fast };
  }

  // ---- recorded answers (real runs, labelled) ------------------------------------------------------------------
  async function loadRecorded() {
    if (recorded) return recorded;
    try { recorded = await (await fetch('recorded.json')).json(); } catch (e) { recorded = { items: [], brief: null }; }
    return recorded;
  }
  const norm = s => s.toLowerCase().replace(/\s+/g, ' ').trim();
  const stamp = r => 'Recorded answer from ' + r.model + ' on Nebius Token Factory, ' + r.recorded_on + ', on the demo company with default settings.';

  async function liveOrRecordedAsk(question) {
    const key = getKey();
    if (key) return liveAsk(question, key);
    const rec = await loadRecorded();
    const hit = rec.items.find(i => norm(i.question) === norm(question));
    if (!hit) throw new Error('Live questions need your own Nebius Token Factory key: add it in the box above. Without a key you can pick one of the recorded questions below the box.');
    const isDefault = await call('is_default');
    return { ...hit, answer: hit.answer, model: hit.model + '  (' + stamp({ model: hit.model, recorded_on: rec.recorded_on }) + (isDefault ? '' : ' You have changed settings or data since, so this answer describes the default company.') + ')' };
  }
  async function liveOrRecordedBrief() {
    const key = getKey();
    if (key) return liveBrief(key);
    const rec = await loadRecorded();
    if (!rec.brief) throw new Error('Add your Nebius Token Factory key to write the summary live.');
    return { brief: rec.brief.brief, model: rec.brief.model + '  (' + stamp({ model: rec.brief.model, recorded_on: rec.recorded_on }) + ')' };
  }

  // ---- the key box ---------------------------------------------------------------------------------------------
  function installKeyCard() {
    const tab = document.getElementById('tab-ask'); if (!tab) return;
    const card = document.createElement('div'); card.className = 'card'; card.id = 'keycard';
    const h = document.createElement('h2'); h.textContent = 'Live answers with your own key'; card.appendChild(h);
    const p = document.createElement('p'); p.style.margin = '0 0 8px';
    p.textContent = 'This page runs without a server. To ask anything and see Nemotron answer live, paste a Nebius Token Factory key. It is stored only in this browser and sent only to api.tokenfactory.nebius.com. Without a key you can still read real answers recorded from Nemotron 3 Ultra: use the suggested questions below.';
    card.appendChild(p);
    const row = document.createElement('div'); row.className = 'row';
    const inp = document.createElement('input'); inp.type = 'password'; inp.placeholder = 'Token Factory API key'; inp.autocomplete = 'off';
    inp.style.cssText = 'width:320px;max-width:100%;background:var(--bg);color:var(--text);border:1px solid var(--line);border-radius:6px;padding:8px 10px;font:inherit';
    const save = document.createElement('button'); save.textContent = 'Save key';
    const clear = document.createElement('button'); clear.className = 'ghost'; clear.textContent = 'Remove key';
    const status = document.createElement('span'); status.className = 'mute';
    const refresh = () => { status.textContent = getKey() ? 'Live mode: your key is saved in this browser.' : 'No key: recorded answers only.'; inp.value = ''; };
    save.onclick = () => { const v = inp.value.trim(); if (!v) { status.textContent = 'Paste a key first.'; return; } try { localStorage.setItem(KEY, v); } catch (e) { status.textContent = 'This browser blocks saving: use a normal window.'; return; } modelCache = null; refresh(); };
    clear.onclick = () => { try { localStorage.removeItem(KEY); } catch (e) {} modelCache = null; refresh(); };
    [inp, save, clear, status].forEach(x => row.appendChild(x)); card.appendChild(row);
    tab.insertBefore(card, tab.firstChild); refresh();
  }
})();
