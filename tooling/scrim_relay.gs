/** 🎪 내전 자동매칭 HTTPS 릴레이 (Google Apps Script)
 *
 * 왜 필요한가: squad.gg 는 HTTPS 인데 봇은 http(fi15.bot-hosting.net:27116)라
 * 브라우저가 메인화면에서의 직접 호출을 차단한다(혼합 콘텐츠). 이 스크립트를
 * 웹앱으로 배포하면 HTTPS 주소가 생기고, 서버 사이드에서 봇으로 전달해 준다.
 *
 * 배포(1회, 약 5분 — 사장님 구글 계정):
 *   1. script.google.com → 새 프로젝트 → 이 파일 내용 붙여넣기
 *   2. 배포 → 새 배포 → 유형: 웹 앱
 *      · 실행 계정: 나  · 액세스 권한: 모든 사용자
 *   3. 나온 URL(https://script.google.com/macros/s/…/exec)을 클로드에게 전달
 *      → index.html 의 SCRIM_RELAY 상수에 꽂으면 메인화면 대시보드가 켜진다
 *
 * 봇 노드를 이전하면 아래 BOT 만 바꿔 재배포.
 */
const BOT = "http://fi15.bot-hosting.net:27116";

function doGet(e) {
  try {
    const r = UrlFetchApp.fetch(BOT + "/scrim", { muteHttpExceptions: true });
    return ContentService.createTextOutput(r.getContentText())
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ error: String(err) }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doPost(e) {
  try {
    const req = JSON.parse(e.postData.contents || "{}");
    const path = String(req.path || "");
    if (["/scrim-join", "/scrim-leave", "/scrim-last", "/scrim-kick"].indexOf(path) < 0)
      return ContentService.createTextOutput('{"ok":false,"msg":"unknown path"}')
        .setMimeType(ContentService.MimeType.JSON);
    const r = UrlFetchApp.fetch(BOT + path, {
      method: "post", contentType: "application/json",
      payload: JSON.stringify(req.body || {}), muteHttpExceptions: true,
    });
    return ContentService.createTextOutput(r.getContentText())
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ ok: false, msg: String(err) }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
