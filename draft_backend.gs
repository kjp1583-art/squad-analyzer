/**
 * SQUAD.GG 토너먼트 드래프트 — 무료 실시간 백엔드 (Google Apps Script)
 *
 * [설치 방법 — 1회, 약 5분]
 * 1. https://script.new 접속 (구글 로그인 상태)
 * 2. 이 파일 내용 전체를 붙여넣기 (기존 내용 지우고)
 * 3. 우상단 [배포] → [새 배포] → 톱니바퀴에서 [웹 앱] 선택
 *    - 설명: draft / 실행 계정: 나 / 액세스 권한: **모든 사용자**
 * 4. [배포] 클릭 → 권한 승인(내 계정 선택 → 고급 → 이동 → 허용)
 * 5. 나오는 "웹 앱 URL"(https://script.google.com/macros/s/..../exec) 복사
 * 6. 그 URL을 draft.html 의 DRAFT_API 에 넣으면 운영 모드 완성
 *
 * 데이터는 기존 스쿼드 스프레드시트의 DRAFT_LOG 탭에 기록됩니다(자동 생성).
 */
const DOC_ID = '10j2QBdXiyL0_UGKLMDcndieXD7jeMGxVHqH3nj6gJnU';
const SHEET_NAME = 'DRAFT_LOG';

function sheet_() {
  const ss = SpreadsheetApp.openById(DOC_ID);
  let sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) { sh = ss.insertSheet(SHEET_NAME); sh.appendRow(['room', 'ts', 'json']); }
  return sh;
}

// 방 이벤트 읽기: GET ?room=xxxxx
function doGet(e) {
  const room = String((e.parameter && e.parameter.room) || '').slice(0, 32);
  const events = [];
  if (room) {
    const rows = sheet_().getDataRange().getValues();
    for (let i = 1; i < rows.length; i++) {
      if (String(rows[i][0]) === room) {
        try { const ev = JSON.parse(rows[i][2]); ev.ts = Number(rows[i][1]); events.push(ev); } catch (err) {}
      }
    }
  }
  return out_({ events: events });
}

// 이벤트 추가: POST {room, ev}  (LockService로 동시 클릭 직렬화)
function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(5000);
  try {
    const body = JSON.parse(e.postData.contents);
    const room = String(body.room || '').slice(0, 32);
    const ev = body.ev || {};
    if (!room || !ev.t) return out_({ ok: false });
    sheet_().appendRow([room, Date.now(), JSON.stringify(ev)]);
    return out_({ ok: true });
  } catch (err) {
    return out_({ ok: false, err: String(err) });
  } finally {
    lock.releaseLock();
  }
}

function out_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
