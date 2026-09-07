// Flutter 3.44 Windows test handler compares a Windows path with 'canvaskit/'.
// Serve only the matching local SDK engine assets to an owned test iframe via
// CDP, without editing the Flutter SDK or accessing any normal browser tab.
import {readFile} from 'node:fs/promises';
const port = Number(process.argv[2]);
if (!Number.isInteger(port) || port < 1024 || port > 65535) throw Error('Test port required');
const pages = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const page = pages.find(p => p.url.startsWith('http://localhost:') && p.url.includes('/static/index.html'));
if (!page) throw Error('No owned Flutter test page');
const socket = new WebSocket(page.webSocketDebuggerUrl);
let id = 10;
const send = (method, params) => socket.send(JSON.stringify({id: ++id, method, params}));
const timer = setTimeout(() => socket.close(), 45000);
socket.onclose = () => clearTimeout(timer);
socket.onopen = () => {
  socket.send(JSON.stringify({id: 1, method: 'Fetch.enable', params: {patterns: [{urlPattern: '*localhost*/canvaskit/*'}]}}));
};
socket.onmessage = async event => {
  const message = JSON.parse(event.data);
  if (message.id === 1) {
    send('Runtime.evaluate', {expression: 'document.querySelector("iframe").contentWindow.location.reload()'});
  }
  if (message.method !== 'Fetch.requestPaused') return;
  const {requestId, request} = message.params;
  const relative = new URL(request.url).pathname.replace(/^\/canvaskit\//, '');
  if (!/^(chromium\/)?canvaskit\.(js|wasm)$/.test(relative)) {
    send('Fetch.continueRequest', {requestId}); return;
  }
  try {
    const bytes = await readFile(`C:/src/flutter/bin/cache/flutter_web_sdk/canvaskit/${relative}`);
    send('Fetch.fulfillRequest', {requestId, responseCode: 200,
      responseHeaders: [{name: 'Content-Type', value: relative.endsWith('.wasm') ? 'application/wasm' : 'text/javascript'}],
      body: bytes.toString('base64')});
    console.log(`Served local test engine: ${relative}`);
  } catch {
    send('Fetch.failRequest', {requestId, errorReason: 'Failed'});
  }
};
