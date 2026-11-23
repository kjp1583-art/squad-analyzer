#!/usr/bin/env python3
"""📺 클랜 유튜브 채널(@league_squad)의 최신 영상 목록을 RSS 로 받아 youtube_latest.json 으로 쓴다.
웹(index.html 홈 「클랜 영상」 카드)이 ai-eval-data 브랜치의 이 파일을 읽는다 — 브라우저는 유튜브 RSS 를 CORS 로 직접 못 읽는다.
사용: python3 tooling/youtube_latest.py <출력경로>   (실패하면 파일을 만들지 않고 0 으로 끝낸다 → 기존 파일 유지)"""
import json, re, sys, time, urllib.request, xml.etree.ElementTree as ET
CHANNEL = "UC8c9ctPOAfk64bAQs_ArLFA"   # https://www.youtube.com/@league_squad
URL = "https://www.youtube.com/feeds/videos.xml?channel_id=" + CHANNEL
NS = {"a": "http://www.w3.org/2005/Atom", "y": "http://www.youtube.com/xml/schemas/2015"}
def main(out):
    last = None
    for i in range(3):
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (squad-gg clan site; latest video card)"})
            xml = urllib.request.urlopen(req, timeout=30).read()
            root = ET.fromstring(xml); vids = []
            for e in root.findall("a:entry", NS):
                vid = (e.findtext("y:videoId", "", NS) or "").strip()
                if not re.fullmatch(r"[\w-]{11}", vid): continue
                vids.append({"id": vid, "title": (e.findtext("a:title", "", NS) or "").strip(),
                             "published": (e.findtext("a:published", "", NS) or "").strip()})
            vids.sort(key=lambda v: v["published"], reverse=True)
            if not vids: raise RuntimeError("영상 0건")
            json.dump({"channel": "@league_squad", "videos": vids[:6]}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
            print("영상 %d건 · 최신 %s %s" % (len(vids), vids[0]["id"], vids[0]["title"])); return
        except Exception as ex:
            last = ex; print("실패 %d/3: %s" % (i + 1, ex)); time.sleep(10)
    print("받지 못함 — 기존 파일 유지:", last)
if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "youtube_latest.json")
