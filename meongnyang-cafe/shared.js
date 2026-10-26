/* 멍냥 게임천국 공용 코드 — 이름·기기 식별자·Supabase 연결. 새 미니게임도 이 파일을 불러서 쓴다. */
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
  return {
    SB_URL: SB_URL, SB_KEY: SB_KEY, get: get, set: set, pid: pid,
    nick: function () { return (get('mn-nick') || '').slice(0, 12); },
    setNick: function (n) { set('mn-nick', String(n || '').trim().slice(0, 12)); },
    client: function () { if (!client && window.supabase) client = window.supabase.createClient(SB_URL, SB_KEY); return client; }
  };
})();
