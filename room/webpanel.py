"""Lustro weneckie w przeglądarce: dwa ekrany + guzik Prowadzącego.

Czysty stdlib (http.server + SSE), zero zewnętrznych zależności,
wyłącznie localhost. Implementuje PanelProtocol — broker nie wie,
czy patrzy na niego terminal, czy przeglądarka.
"""

import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VALID_COMMANDS = {"g", "p", "s", "k", "c"}


class WebPanel:
    def __init__(self, host: str = "127.0.0.1", port: int = 8737):
        self._cmd_q: queue.Queue[str] = queue.Queue()
        self._clients: list[queue.Queue] = []
        self._history: list[dict] = []
        self._lock = threading.Lock()

        panel = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # cisza w konsoli
                pass

            def do_GET(self):
                if self.path == "/":
                    body = PAGE.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif self.path == "/events":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    client: queue.Queue = queue.Queue()
                    with panel._lock:
                        backlog = list(panel._history)
                        panel._clients.append(client)
                    try:
                        for event in backlog:
                            self._send_event(event)
                        while True:
                            self._send_event(client.get())
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                    finally:
                        with panel._lock:
                            if client in panel._clients:
                                panel._clients.remove(client)
                else:
                    self.send_response(404)
                    self.end_headers()

            def _send_event(self, event: dict):
                self.wfile.write(f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8"))
                self.wfile.flush()

            def do_POST(self):
                if self.path == "/cmd":
                    length = int(self.headers.get("Content-Length", 0))
                    data = json.loads(self.rfile.read(length) or b"{}")
                    cmd = str(data.get("cmd", "")).lower()
                    if cmd in VALID_COMMANDS | {"y", "n"}:
                        panel._cmd_q.put(cmd)
                        self.send_response(204)
                    else:
                        self.send_response(400)
                    self.end_headers()
                else:
                    self.send_response(404)
                    self.end_headers()

        try:
            self.server = ThreadingHTTPServer((host, port), Handler)
        except OSError:  # port zajęty → weź wolny efemeryczny
            self.server = ThreadingHTTPServer((host, 0), Handler)
        self.url = f"http://{host}:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def _broadcast(self, event: dict) -> None:
        with self._lock:
            self._history.append(event)
            for client in self._clients:
                client.put(event)

    # --- PanelProtocol --------------------------------------------------------
    def show_message(self, author: str, content: str, room_tokens: int) -> None:
        self._broadcast({"type": "message", "author": author,
                         "content": content, "room_tokens": room_tokens})

    def show_event(self, text: str) -> None:
        self._broadcast({"type": "event", "text": text})

    def show_environment(self, content: str) -> None:
        self._broadcast({"type": "environment", "content": content})

    def command(self) -> str:
        self._broadcast({"type": "awaiting"})
        while True:
            cmd = self._cmd_q.get()
            if cmd in VALID_COMMANDS:
                self._broadcast({"type": "pressed", "cmd": cmd})
                return cmd

    def confirm(self, question: str) -> bool:
        self._broadcast({"type": "confirm", "question": question})
        while True:
            cmd = self._cmd_q.get()
            if cmd in ("y", "n"):
                self._broadcast({"type": "pressed", "cmd": cmd})
                return cmd == "y"

    def close(self) -> None:
        self.server.shutdown()


PAGE = """<!doctype html>
<html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pokój AI — lustro weneckie</title>
<style>
  :root { --bg:#0b0e14; --panel:#11151f; --line:#1d2433; --text:#d7dce6;
          --dim:#6b7385; --klaris:#e8a87c; --kord:#7cc4e8; --glow:#39d98a; }
  * { box-sizing:border-box; margin:0; }
  body { background:var(--bg); color:var(--text); height:100vh; display:flex;
         flex-direction:column; font:15px/1.5 "SF Mono", ui-monospace, monospace; }
  header { padding:10px 18px; border-bottom:1px solid var(--line); display:flex;
           justify-content:space-between; align-items:center; }
  header b { letter-spacing:.12em; font-weight:600; }
  #status { color:var(--dim); font-size:13px; }
  main { flex:1; display:grid; grid-template-columns:1fr 1fr; gap:1px;
         background:var(--line); min-height:0; }
  #board-wrap { display:none; justify-content:center; padding:14px 18px 0; }
  #board-wrap.show { display:flex; }
  #board { border:2px solid #8a734a; background:#171310; color:#e6d9b8;
           border-radius:6px; padding:14px 26px; white-space:pre;
           font-size:13px; line-height:1.35; box-shadow:0 4px 24px rgba(0,0,0,.5);
           animation:in .4s ease; }
  .screen { background:var(--panel); display:flex; flex-direction:column; min-height:0; }
  .screen h2 { padding:10px 16px; font-size:12px; letter-spacing:.18em;
               border-bottom:1px solid var(--line); color:var(--dim); }
  .screen[data-who="Klaris"] h2 { color:var(--klaris); }
  .screen[data-who="Kord"]   h2 { color:var(--kord); }
  .feed { flex:1; overflow-y:auto; padding:16px; display:flex;
          flex-direction:column; gap:12px; }
  .msg { border:1px solid var(--line); border-radius:10px; padding:12px 14px;
         background:var(--bg); animation:in .25s ease; white-space:pre-wrap; }
  .msg small { display:block; margin-top:8px; color:var(--dim); font-size:11px; }
  @keyframes in { from { opacity:0; transform:translateY(6px);} }
  footer { border-top:1px solid var(--line); padding:12px 18px; display:flex;
           gap:10px; align-items:center; }
  footer .mirror { color:var(--dim); font-size:12px; margin-right:auto;
                   letter-spacing:.1em; }
  button { background:var(--panel); color:var(--text); border:1px solid var(--line);
           border-radius:8px; padding:10px 18px; font:inherit; cursor:pointer; }
  button:hover { border-color:var(--dim); }
  #go { border-color:var(--glow); color:var(--glow); }
  #stop { border-color:#e05b5b; color:#e05b5b; }
  body.awaiting #go { box-shadow:0 0 14px 1px var(--glow); animation:pulse 1.2s infinite; }
  @keyframes pulse { 50% { box-shadow:0 0 4px 0 var(--glow);} }
  #log { max-height:70px; overflow-y:auto; font-size:12px; color:var(--dim);
         padding:6px 18px; border-top:1px solid var(--line); }
  #overlay { position:fixed; inset:0; background:rgba(4,6,10,.82); display:none;
             align-items:center; justify-content:center; flex-direction:column; gap:18px; }
  #overlay.show { display:flex; }
  #overlay p { max-width:520px; text-align:center; }
</style></head><body>
<header><b>POKÓJ AI · LUSTRO WENECKIE</b><span id="status">łączenie…</span></header>
<div id="board-wrap"><div id="board"></div></div>
<main>
  <section class="screen" data-who="Klaris"><h2>■ EKRAN KLARIS</h2><div class="feed" id="feed-Klaris"></div></section>
  <section class="screen" data-who="Kord"><h2>■ EKRAN KORDA</h2><div class="feed" id="feed-Kord"></div></section>
</main>
<div id="log"></div>
<footer>
  <span class="mirror">JAN — ZA LUSTREM</span>
  <button id="go" onclick="cmd('g')">▶ GO</button>
  <button onclick="cmd('p')">⏸ PAUZA</button>
  <button onclick="cmd('k')">⏭ SKIP</button>
  <button id="stop" onclick="cmd('s')">■ STOP</button>
  <button onclick="cmd('c')">✕ CLOSE</button>
</footer>
<div id="overlay"><p id="question"></p>
  <div><button onclick="cmd('y')">TAK</button> <button onclick="cmd('n')">NIE</button></div>
</div>
<script>
const $ = id => document.getElementById(id);
function cmd(c) {
  fetch('/cmd', {method:'POST', body:JSON.stringify({cmd:c})});
  $('overlay').classList.remove('show');
  document.body.classList.remove('awaiting');
}
function logLine(t) {
  const d = document.createElement('div'); d.textContent = t;
  $('log').prepend(d);
}
const es = new EventSource('/events');
es.onopen  = () => $('status').textContent = 'połączono';
es.onerror = () => $('status').textContent = 'rozłączono';
es.onmessage = e => {
  const ev = JSON.parse(e.data);
  if (ev.type === 'message') {
    const feed = $('feed-' + ev.author) || $('feed-Klaris');
    const div = document.createElement('div');
    div.className = 'msg';
    div.textContent = ev.content;
    const meta = document.createElement('small');
    meta.textContent = ev.room_tokens + ' room_tokens';
    div.appendChild(meta);
    feed.appendChild(div);
    feed.scrollTop = feed.scrollHeight;
  } else if (ev.type === 'environment') {
      $('board').textContent = ev.content;
      $('board-wrap').classList.add('show');
  } else if (ev.type === 'event')   { logLine('· ' + ev.text); }
    else if (ev.type === 'awaiting'){ document.body.classList.add('awaiting');
                                      $('status').textContent = 'czekam na guzik'; }
    else if (ev.type === 'pressed') { document.body.classList.remove('awaiting');
                                      $('status').textContent = 'guzik: ' + ev.cmd; }
    else if (ev.type === 'confirm') { $('question').textContent = ev.question;
                                      $('overlay').classList.add('show'); }
};
</script></body></html>"""
