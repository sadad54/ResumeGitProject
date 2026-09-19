import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { webcrypto } from 'node:crypto';

function setup() {
  const store = {}, tabs = [], listeners = {};
  const event = name => ({ addListener: fn => { listeners[name] = fn; } });
  const chrome = {
    runtime: { id: 'a'.repeat(32), onInstalled: event('install'), onMessage: event('internal'), onMessageExternal: event('external') },
    contextMenus: { removeAll: fn => fn(), create: () => {}, onClicked: event('click') },
    storage: { session: {
      get: async key => key ? { [key]: store[key] } : { ...store },
      set: async values => Object.assign(store, values),
      remove: async keys => { for (const key of [keys].flat()) delete store[key]; },
    } },
    tabs: { create: async tab => tabs.push(tab), query: async () => [{ url: 'https://example.com/job', title: 'Backend Engineer' }] },
    action: { setBadgeText: async () => {}, setTitle: async () => {} },
  };
  const source = readFileSync(new URL('../background.js', import.meta.url), 'utf8').replace('import { WEB_ORIGIN } from "./config.js";', 'const WEB_ORIGIN = "http://localhost:3000";');
  runInNewContext(source, { chrome, crypto: webcrypto, URL, Date });
  return { store, tabs, listeners };
}
const tick = () => new Promise(resolve => setImmediate(resolve));

test('selection handoff carries text, never places content in URL', async () => {
  const { tabs, store, listeners } = setup();
  listeners.click({ selectionText: 'private job description', pageUrl: 'https://example.com/job' }, { title: 'Role' });
  await tick();
  assert.equal(tabs.length, 1);
  assert.ok(!tabs[0].url.includes('private'));
  assert.equal(Object.values(store)[0].selected_text, 'private job description');
  assert.ok(Object.values(store)[0].expires > Date.now());
});

test('untrusted sites and wrong ports cannot read captures', () => {
  const { listeners } = setup();
  for (const url of ['https://evil.example', 'http://localhost:9000', 'https://localhost:3000']) {
    let called = false;
    const result = listeners.external({ type: 'read-capture', capture_id: webcrypto.randomUUID() }, { url }, () => { called = true; });
    assert.equal(result, undefined); assert.equal(called, false);
  }
});

test('trusted web session can read then consume a handoff', async () => {
  const { listeners, store } = setup();
  const id = webcrypto.randomUUID();
  store[id] = { capture_id: id, selected_text: 'fixture', expires: Date.now() + 10000 };
  const sender = { url: 'http://localhost:3000/capture' };
  const result = await new Promise(resolve => listeners.external({ type: 'read-capture', capture_id: id }, sender, resolve));
  assert.equal(result.payload.selected_text, 'fixture');
  assert.equal(result.payload.expires, undefined);
  await new Promise(resolve => listeners.external({ type: 'finish-capture', capture_id: id }, sender, resolve));
  assert.equal(store[id], undefined);
});

test('expired capture is removed and cannot be read', async () => {
  const { listeners, store } = setup(); const id = webcrypto.randomUUID();
  store[id] = { selected_text: 'private', expires: Date.now() - 1 };
  const result = await new Promise(resolve => listeners.external({ type: 'read-capture', capture_id: id }, { url: 'http://localhost:3000/capture' }, resolve));
  assert.ok(result.error); assert.equal(store[id], undefined);
});

test('manifest remains minimal and has no page-wide injection', () => {
  const manifest = JSON.parse(readFileSync(new URL('../manifest.json', import.meta.url)));
  assert.deepEqual(manifest.permissions.sort(), ['activeTab', 'contextMenus', 'storage']);
  assert.equal(manifest.host_permissions, undefined);
  assert.equal(manifest.content_scripts, undefined);
});

test('popup "capture active page" uses the active tab and only accepts internal senders', async () => {
  const { listeners, store, tabs } = setup();
  const external = await new Promise(resolve => {
    const r = listeners.internal({ type: 'capture-active' }, { id: 'someone-else' }, resolve);
    if (r === undefined) resolve('ignored');
  });
  assert.equal(external, 'ignored');
  assert.equal(tabs.length, 0);

  const reply = await new Promise(resolve => listeners.internal({ type: 'capture-active' }, { id: 'a'.repeat(32) }, resolve));
  assert.equal(reply.ok, true); // cross-realm object, so compare the field
  const [entry] = Object.values(store);
  assert.equal(entry.page_url, 'https://example.com/job');
  assert.equal(entry.title, 'Backend Engineer');
  assert.equal(entry.selected_text, '');
  assert.equal(tabs.length, 1);
});

test('capture bounds text, url and title and rejects non-http page urls', async () => {
  const { listeners, store } = setup();
  listeners.click({ selectionText: 'x'.repeat(70000), pageUrl: 'javascript:alert(1)' }, { title: 't'.repeat(600) });
  await tick();
  const [entry] = Object.values(store);
  assert.equal(entry.selected_text.length, 60000);
  assert.equal(entry.page_url, null);
  assert.equal(entry.title.length, 500);
});

test('a new capture sweeps expired handoffs from session storage', async () => {
  const { listeners, store } = setup();
  store['stale'] = { selected_text: 'old', expires: Date.now() - 1000 };
  store['fresh'] = { selected_text: 'new', expires: Date.now() + 100000 };
  listeners.click({ selectionText: 'now', pageUrl: 'https://example.com/a' }, { title: 'r' });
  await tick();
  assert.equal(store['stale'], undefined);
  assert.ok(store['fresh']);
});

test('malformed capture ids and unknown message types are ignored', () => {
  const { listeners } = setup();
  const sender = { url: 'http://localhost:3000/capture' };
  for (const message of [
    { type: 'read-capture', capture_id: 'not-a-uuid' },
    { type: 'read-capture', capture_id: '../../etc' },
    { type: 'delete-everything', capture_id: webcrypto.randomUUID() },
    null,
  ]) {
    let called = false;
    const result = listeners.external(message, sender, () => { called = true; });
    assert.equal(result, undefined); assert.equal(called, false);
  }
});
