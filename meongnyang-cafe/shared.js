/* 멍냥 게임천국 공용 코드 — 이름·기기 식별자·Supabase 연결. 새 미니게임도 이 파일을 불러서 쓴다. */
/* ---------- 배경음악: 직접 만든 짧은 반복 곡(C-Am-F-G). 소리 파일 없이 WebAudio 로 연주한다 ---------- */
var bgm = (function () {
  var ctx = null, master = null, timer = null, step = 0, nextT = 0, playing = false;
  var EIGHTH = 60 / 104 / 2;
  var CH = [[48, 52, 55], [45, 48, 52], [41, 45, 48], [43, 47, 50]];
  var MEL = [
    79, 0, 76, 0, 72, 76, 79, 0,   81, 0, 79, 0, 76, 79, 81, 0,   77, 0, 81, 0, 84, 81, 77, 0,   74, 0, 79, 77, 76, 74, 72, 0,
    84, 0, 79, 0, 76, 0, 79, 81,   81, 0, 84, 0, 81, 79, 76, 0,   81, 79, 77, 0, 81, 0, 84, 0,   83, 81, 79, 0, 74, 0, 79, 0
  ];
  function hz(m) { return 440 * Math.pow(2, (m - 69) / 12); }
  function pref() { try { return localStorage.getItem('mn-bgm') !== '0'; } catch (e) { return true; } }
  function note(t, m, dur, type, vol) {
    var o = ctx.createOscillator(), g = ctx.createGain();
    o.type = type; o.frequency.value = hz(m);
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.015); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g); g.connect(master); o.start(t); o.stop(t + dur + 0.05);
  }
  function tick() {
    while (nextT < ctx.currentTime + 0.3) {
      var s = step % 64, bar = (s / 8) | 0, k = s % 8, chord = CH[bar % 4], m = MEL[s];
      if (m) note(nextT, m, EIGHTH * 1.9, 'triangle', 0.075);
      if (k === 0 || k === 4) note(nextT, chord[0], EIGHTH * 2.4, 'sine', 0.13);
      if (k === 2 || k === 6) note(nextT, chord[2], EIGHTH * 1.2, 'sine', 0.07);
      if (k % 2 === 1) note(nextT, chord[(k >> 1) % 3] + 12, EIGHTH * 0.9, 'sine', 0.035);
      step++; nextT += EIGHTH;
    }
  }
  function start() {
    if (playing || !pref()) return;
    try {
      if (!ctx) { ctx = new (window.AudioContext || window.webkitAudioContext)(); master = ctx.createGain(); master.gain.value = 0.0001; master.connect(ctx.destination); }
      if (ctx.state === 'suspended') ctx.resume();
      master.gain.cancelScheduledValues(ctx.currentTime); master.gain.setValueAtTime(master.gain.value, ctx.currentTime); master.gain.linearRampToValueAtTime(0.55, ctx.currentTime + 1.2);
      nextT = ctx.currentTime + 0.1; timer = setInterval(tick, 40); playing = true;
    } catch (e) { playing = false; }
  }
  function stop() {
    if (!playing) return; playing = false; clearInterval(timer);
    try { master.gain.cancelScheduledValues(ctx.currentTime); master.gain.setValueAtTime(master.gain.value, ctx.currentTime); master.gain.linearRampToValueAtTime(0.0001, ctx.currentTime + 0.4); } catch (e) { /* 무시 */ }
  }
  document.addEventListener('visibilitychange', function () {
    if (!ctx) return;
    if (document.hidden) { if (playing) { clearInterval(timer); ctx.suspend(); } } else if (playing) { ctx.resume(); nextT = ctx.currentTime + 0.1; timer = setInterval(tick, 40); }
  });
  function arm() { start(); }
  ['pointerdown', 'keydown'].forEach(function (ev) { document.addEventListener(ev, function once() { arm(); document.removeEventListener(ev, once); }); });
  return {
    isOn: pref, start: start, stop: stop,
    toggle: function () { var on = !pref(); try { localStorage.setItem('mn-bgm', on ? '1' : '0'); } catch (e) { /* 무시 */ } if (on) start(); else stop(); return on; },
    get running() { return playing; }
  };
})();

window.MN = (function () {
  var SB_URL = 'https://ygrxsylktbsrczjtrvfh.supabase.co';
  var SB_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlncnhzeWxrdGJzcmN6anRydmZoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTMwMDI1ODgsImV4cCI6MjEwODU3ODU4OH0.-y-BMIakZ-jEShSaJSNXF0g0ZPpKr3wR7lbv_uMSmJQ'; // 공개용(anon) 키 — 쓰기는 DB 함수(game_submit)로만 가능
  var client = null;
  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* 저장 못 해도 계속 */ } }
  function pid() {
    var p = get('mn-pid');
    if (!p || p.length < 16) {
      var a = new Uint8Array(16); (window.crypto || window.msCrypto).getRandomValues(a);
      p = Array.prototype.map.call(a, function (b) { return ('0' + b.toString(16)).slice(-2); }).join('');
      set('mn-pid', p);
    }
    return p;
  }
  /* 방(실시간 접속) — presence 는 처음 한 번만 올리고, 상태는 broadcast 로 주고받는다 */
  function roomNs(self) {
    var sb = self.client(); if (!sb) return null;
    var myKey = 'p' + pid().slice(0, 8) + Math.random().toString(36).slice(2, 8);
    return {
      join: async function (name) {
        var ch = sb.channel('cafe-' + name, { config: { presence: { key: myKey }, broadcast: { self: false } } });
        var mine = {}, handlers = [], states = new Map();
        var peers = function () {
          var out = [{ peer: myKey, isMe: true, presence: mine }];
          Object.keys(ch.presenceState()).forEach(function (k) { if (k !== myKey) out.push({ peer: k, isMe: false, presence: states.get(k) || {} }); });
          return out;
        };
        var fire = function () { handlers.forEach(function (f) { f({ peers: peers() }); }); };
        var send = function () { ch.send({ type: 'broadcast', event: 'st', payload: { k: myKey, s: mine } }).catch(function () {}); };
        ch.on('broadcast', { event: 'st' }, function (m) {
          var p = m.payload;
          if (p && typeof p.k === 'string' && p.k !== myKey && p.s && typeof p.s === 'object') { states.set(p.k, p.s); fire(); }
        });
        ch.on('presence', { event: 'join' }, function (e) { if (e.key !== myKey) send(); fire(); });
        ch.on('presence', { event: 'leave' }, function (e) { states.delete(e.key); fire(); });
        ch.on('presence', { event: 'sync' }, fire);
        await new Promise(function (res, rej) { var t = setTimeout(function () { rej(new Error('timeout')); }, 10000); ch.subscribe(function (st) { if (st === 'SUBSCRIBED') { clearTimeout(t); res(); } else if (st === 'CHANNEL_ERROR' || st === 'TIMED_OUT') { clearTimeout(t); rej(new Error(st)); } }); });
        await ch.track({ k: myKey });
        return {
          peers: peers, onPeers: function (f) { handlers.push(f); },
          presence: async function (patch) { mine = Object.assign({}, mine, patch); send(); },
          leave: async function () { try { await ch.untrack(); await sb.removeChannel(ch); } catch (e) { /* 무시 */ } }
        };
      }
    };
  }
  return {
    SB_URL: SB_URL, SB_KEY: SB_KEY, get: get, set: set, pid: pid,
    nick: function () { return (get('mn-nick') || '').slice(0, 12); },
    setNick: function (n) { set('mn-nick', String(n || '').trim().slice(0, 12)); },
    bgm: bgm,
    roomNs: function () { return roomNs(this); },
    client: function () { if (!client && window.supabase) client = window.supabase.createClient(SB_URL, SB_KEY); return client; }
  };
})();
