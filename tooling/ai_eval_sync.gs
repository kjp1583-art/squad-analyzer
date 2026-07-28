/**
 * 스쿼드 시트 자동 동기화 v3 (기존 스크립트를 이걸로 교체 — 1회)
 *
 * [업그레이드 방법 — 2분]
 * 1. https://script.google.com 접속 → 전에 만든 동기화 프로젝트 열기
 * 2. 기존 코드 전체 지우고 이 파일 전체 붙여넣기 → Ctrl+S 저장
 * 3. 함수 드롭다운 [setup] 선택 → [실행] (권한 창 나오면 승인)
 * 4. 로그에 "설치 완료" 뜨면 끝
 *
 * v2 추가 기능: 클로드가 GitHub에 올리는 시트 수정 지시(sheet_updates.json)를
 * 자동 반영 — LINK_ACCOUNT 별칭 추가 같은 시트 편집을 원격으로 처리.
 * (기존 AI 주간평 동기화는 그대로 유지)
 */
var DOC_ID = '10j2QBdXiyL0_UGKLMDcndieXD7jeMGxVHqH3nj6gJnU';
var RAW_BASE = 'https://raw.githubusercontent.com/kjp1583-art/squad-analyzer/ai-eval-data/';

function setup() {
  ScriptApp.getProjectTriggers().forEach(function(t) {
    if (t.getHandlerFunction() === 'sync') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('sync').timeBased().everyHours(6).create();
  sync();
  Logger.log('설치 완료 — 6시간마다 자동 동기화됩니다.');
}

function sync() {
  syncAiEval();
  applySheetUpdates();
}

function _fetchJson(name) {
  var res = UrlFetchApp.fetch(RAW_BASE + name + '?cb=' + Date.now(), { muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) return null;
  try { return JSON.parse(res.getContentText()); } catch (e) { return null; }
}

// ===== AI 주간평 (기존 기능) =====
function syncAiEval() {
  var data = _fetchJson('ai_eval_latest.json');
  if (!data || !data.evals) return;
  var newDate = String(data['갱신일'] || '');
  if (!newDate) return;
  var props = PropertiesService.getScriptProperties();
  var payloadHash = Utilities.base64Encode(Utilities.computeDigest(Utilities.DigestAlgorithm.MD5, JSON.stringify(data), Utilities.Charset.UTF_8));
  if (props.getProperty('lastHash') === payloadHash) { Logger.log('주간평: 이미 반영됨'); return; }

  var ss = SpreadsheetApp.openById(DOC_ID);
  var sh = ss.getSheetByName('AI_EVAL');
  if (!sh) { sh = ss.insertSheet('AI_EVAL'); sh.appendRow(['닉네임', '평가', '갱신일', '상태', '직전평가일']); }
  var rows = sh.getDataRange().getValues();
  var norm = function(s) { return String(s || '').replace(/\s+/g, '').toLowerCase(); };
  var rowByNick = {};
  for (var i = 1; i < rows.length; i++) rowByNick[norm(rows[i][0])] = i + 1;

  var updated = 0, added = 0, skipped = 0;
  for (var nick in data.evals) {
    var key = norm(nick);
    if (rowByNick[key]) {
      var r = rowByNick[key];
      var cur = sh.getRange(r, 1, 1, 5).getValues()[0];
      var curDate = String(cur[2]).slice(0, 10);
      if (curDate === newDate) {
        if (String(cur[1]) !== String(data.evals[nick])) { sh.getRange(r, 2).setValue(data.evals[nick]); updated++; }
        else skipped++;
        continue;
      }
      sh.getRange(r, 1, 1, 5).setValues([[nick, data.evals[nick], newDate, '평가', curDate]]);
      updated++;
    } else {
      sh.appendRow([nick, data.evals[nick], newDate, '평가', '']);
      added++;
    }
  }
  props.setProperty('lastHash', payloadHash);
  Logger.log('주간평 동기화(' + newDate + '): 갱신 ' + updated + ', 신규 ' + added + ', 유지 ' + skipped);
}

// ===== 시트 수정 지시 (v2 신규) — sheet_updates.json의 append 작업을 순번(seq) 기준 1회 적용 =====
function applySheetUpdates() {
  var data = _fetchJson('sheet_updates.json');
  if (!data || !data.ops) return;
  var props = PropertiesService.getScriptProperties();
  var lastSeq = parseInt(props.getProperty('lastUpdateSeq') || '0', 10);
  var seq = parseInt(data.seq || 0, 10);
  if (seq <= lastSeq) { Logger.log('시트수정: 이미 적용됨 (seq ' + seq + ')'); return; }

  var ss = SpreadsheetApp.openById(DOC_ID);
  var applied = 0;
  for (var i = 0; i < data.ops.length; i++) {
    var op = data.ops[i];
    var sh = ss.getSheetByName(op.tab);
    if (!sh) { Logger.log('시트수정: 탭 없음 — ' + op.tab); continue; }
    var existing = sh.getDataRange().getValues().map(function(r) { return r.join(''); });
    (op.append || []).forEach(function(row) {
      if (existing.indexOf(row.join('')) >= 0) return;   // 중복 행 방지
      sh.appendRow(row); applied++;
    });
    // v3: 행 삭제 — A열(첫 열) 값이 일치하는 행을 아래에서부터 제거(인덱스 밀림 방지). 헤더(1행)는 건드리지 않음.
    var rm = (op.remove || []).map(function(v) { return String(v).replace(/\s+/g, '').toLowerCase(); });
    if (rm.length) {
      var vals = sh.getDataRange().getValues();
      for (var k = vals.length - 1; k >= 1; k--) {
        var key = String(vals[k][0] || '').replace(/\s+/g, '').toLowerCase();
        if (key && rm.indexOf(key) >= 0) { sh.deleteRow(k + 1); applied++; }
      }
    }
  }
  props.setProperty('lastUpdateSeq', String(seq));
  Logger.log('시트수정 적용: seq ' + seq + ', ' + applied + '행 추가');
}
