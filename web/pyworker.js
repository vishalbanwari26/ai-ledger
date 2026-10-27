/* Runs the Python engine (ailedger/webapi.py) in a Web Worker, so heavy calls never freeze the page.
   Pyodide is Python compiled to WebAssembly. Pinned to one exact release so the site cannot change under us. */
importScripts('https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.js');

let W = null;
const ready = (async () => {
  const py = await loadPyodide();
  const buf = await (await fetch('ailedger.zip')).arrayBuffer();
  py.unpackArchive(buf, 'zip');
  py.runPython('import ailedger.webapi as W');
  W = py.globals.get('W');
  self.postMessage({ ready: true });
})().catch(e => self.postMessage({ fatal: String(e && e.message || e) }));

self.onmessage = async (e) => {
  const { id, fn, args } = e.data;
  try {
    await ready;
    if (!W) throw new Error('The analysis engine did not start.');
    const result = W[fn](...args);  // webapi functions take and return strings or booleans
    self.postMessage({ id, result });
  } catch (err) {
    self.postMessage({ id, error: String(err && err.message || err) });
  }
};
