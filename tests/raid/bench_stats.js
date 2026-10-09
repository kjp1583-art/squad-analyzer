/* 레이드 0단계 — 부하 시험 통계 도우미 (2026-10-08)
   퍼센타일은 표본을 전부 모아 정렬한 뒤 「가장 가까운 순위(nearest-rank)」로 구한다 — 히스토그램 근사가 아니라 정확한 값.
   nearest-rank: n 개 표본을 오름차순으로 놓고 p 퍼센타일 = sorted[ceil(p/100 × n) − 1]. */
'use strict';

function pct(sorted, p) {
  const n = sorted.length;
  if (!n) return null;
  if (p <= 0) return sorted[0];
  const i = Math.min(n - 1, Math.max(0, Math.ceil((p * n) / 100 - 1e-9) - 1));   // (부동소수 오차로 99.9%×1000 이 1000 이 되는 것을 막는 -1e-9)
  return sorted[i];
}

const r3 = v => (v == null ? null : Math.round(v * 1000) / 1000);

/* arr(Float64Array 또는 배열, 앞 n 개만)로 {mean,p50,p95,p99,p999,max} (ms, 소수 3자리) */
function summarize(arr, n) {
  n = n == null ? arr.length : n;
  if (!n) return { n: 0, mean: null, p50: null, p95: null, p99: null, p999: null, max: null };
  const s = Float64Array.from(arr.subarray ? arr.subarray(0, n) : arr.slice(0, n));
  s.sort();
  let sum = 0; for (let i = 0; i < n; i++) sum += s[i];
  return { n, mean: r3(sum / n), p50: r3(pct(s, 50)), p95: r3(pct(s, 95)), p99: r3(pct(s, 99)), p999: r3(pct(s, 99.9)), max: r3(s[n - 1]) };
}

module.exports = { pct, summarize, r3 };
