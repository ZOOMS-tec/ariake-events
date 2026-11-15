(function () {
"use strict";
var TZ = "Asia/Tokyo", DOW = "日月火水木金土";
var PERIODS = [["today","今日"],["tomorrow","明日"],["week","今週"],["d30","今後30日"],["all","今後すべて"]];
var st = { data: null, fac: "all", per: "today", q: "", today: "", skipped: 0 };
var $ = function (id) { return document.getElementById(id); };
function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
function nowParts() {
  var o = {};
  new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" })
    .formatToParts(new Date()).forEach(function (p) { o[p.type] = p.value; });
  return o;
}
function utc(s) { var m = s.split("-"); return new Date(Date.UTC(+m[0], m[1] - 1, +m[2])); }
function addDays(s, n) { var d = utc(s); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); }
function md(s) { var d = utc(s); return (d.getUTCMonth() + 1) + "/" + d.getUTCDate() + "（" + DOW[d.getUTCDay()] + "）"; }
function range(per, t) {
  if (per === "today") return [t, t];
  if (per === "tomorrow") { var n = addDays(t, 1); return [n, n]; }
  if (per === "week") return [t, addDays(t, (7 - utc(t).getUTCDay()) % 7)];
  if (per === "d30") return [t, addDays(t, 30)];
  return [t, "9999-12-31"];
}
function isYmd(s) { return typeof s === "string" && /^\d{4}-\d{2}-\d{2}$/.test(s); }
function norm(s) { return String(s == null ? "" : s).normalize("NFKC").toLowerCase(); }
function dateText(e, t) {
  var y = t.slice(0, 4), a = e.start_date, b = e.end_date;
  var yr = function (s) { return s.slice(0, 4) !== y ? s.slice(0, 4) + "年 " : ""; };
  return a === b ? yr(a) + md(a) : yr(a) + md(a) + " 〜 " + yr(b) + md(b);
}
function fmtUpdated(s) {
  if (!s) return "不明";
  var d = new Date(s); if (isNaN(d)) return String(s);
  var o = { timeZone: TZ, year: "numeric", month: "long", day: "numeric" };
  if (String(s).indexOf("T") > -1) { o.hour = "2-digit"; o.minute = "2-digit"; o.hourCycle = "h23"; }
  return new Intl.DateTimeFormat("ja-JP", o).format(d);
}
function safeUrl(u) { return typeof u === "string" && /^https?:\/\//i.test(u) ? u : null; }
function tick() {
  var p = nowParts(), t = p.year + "-" + p.month + "-" + p.day;
  $("date").textContent = p.year + "年" + (+p.month) + "月" + (+p.day) + "日（" + DOW[utc(t).getUTCDay()] + "）";
  $("clock").textContent = p.hour + ":" + p.minute;
  if (t !== st.today) { st.today = t; if (st.data) render(); }
}
function showMsg(text, retry) {
  var m = $("msg"); m.textContent = ""; m.appendChild(el("div", null, text));
  if (retry) { var b = el("button", null, "再読み込み"); b.type = "button"; b.onclick = load; m.appendChild(b); }
  m.hidden = false; $("list").textContent = ""; $("count").textContent = "";
}
function buildControls() {
  var fw = $("facs"); fw.textContent = "";
  var all = el("button", "chip", "すべて"); all.type = "button"; all.dataset.id = "all"; fw.appendChild(all);
  st.data.facilities.forEach(function (f) {
    var b = el("button", "chip"); b.type = "button"; b.dataset.id = f.id;
    if (f.color) b.style.setProperty("--c", f.color);
    b.appendChild(el("i")); b.appendChild(document.createTextNode(f.name)); fw.appendChild(b);
  });
  fw.onclick = function (e) { var b = e.target.closest("button"); if (b) { st.fac = b.dataset.id; render(); } };
  var pw = $("pers"); pw.textContent = "";
  PERIODS.forEach(function (p) { var b = el("button", null, p[1]); b.type = "button"; b.dataset.id = p[0]; pw.appendChild(b); });
  pw.onclick = function (e) { var b = e.target.closest("button"); if (b) { st.per = b.dataset.id; render(); } };
}
function card(e, f, t) {
  var c = el("article", "card"); c.style.setProperty("--c", (f && f.color) || "#64748b");
  var tags = el("div", "tags");
  tags.appendChild(el("span", "tag fac", f ? f.name : "施設不明"));
  tags.appendChild(e.start_date > t ? el("span", "tag soon", "開催予定") : el("span", "tag on", "開催中"));
  if (e.category) tags.appendChild(el("span", "tag", e.category));
  c.appendChild(tags); c.appendChild(el("h3", null, e.title));
  var dl = el("dl", "meta");
  function row(k, v) { if (v) { dl.appendChild(el("dt", null, k)); dl.appendChild(el("dd", null, v)); } }
  row("日程", dateText(e, t));
  row("時間", e.time_text || (e.start_time ? e.start_time + (e.end_time ? " 〜 " + e.end_time : "〜") : null));
  row("会場", e.venue_detail);
  c.appendChild(dl);
  if (e.description) c.appendChild(el("p", "meta", e.description));
  var u = safeUrl(e.official_url), fallback = !u && f ? safeUrl(f.source_url) : null;
  if (u || fallback) {
    var a = el("a", null, u ? "公式サイトで詳しく見る →" : "施設の公式イベント一覧へ →");
    a.href = u || fallback; a.target = "_blank"; a.rel = "noopener noreferrer"; c.appendChild(a);
  }
  return c;
}
function render() {
  var d = st.data, t = st.today, r = range(st.per, t), fmap = {}, order = {};
  d.facilities.forEach(function (f, i) { fmap[f.id] = f; order[f.id] = i; });
  document.querySelectorAll("#facs .chip").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.id === st.fac)); });
  document.querySelectorAll("#pers button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.id === st.per)); });
  var terms = norm(st.q).split(/\s+/).filter(Boolean);
  var items = d.events.filter(function (e) {
    if (st.fac !== "all" && e.facility_id !== st.fac) return false;
    if (e.end_date < r[0] || e.start_date > r[1]) return false;
    if (!terms.length) return true;
    var f = fmap[e.facility_id], hay = norm([e.title, f && f.name, e.category, e.description, e.venue_detail].join(" "));
    return terms.every(function (w) { return hay.indexOf(w) > -1; });
  }).sort(function (a, b) {
    return a.start_date < b.start_date ? -1 : a.start_date > b.start_date ? 1 :
      a.end_date < b.end_date ? -1 : a.end_date > b.end_date ? 1 :
      (order[a.facility_id] || 99) - (order[b.facility_id] || 99) || (a.title < b.title ? -1 : 1);
  });
  var list = $("list"); list.textContent = ""; $("msg").hidden = true;
  var per = PERIODS.filter(function (p) { return p[0] === st.per; })[0][1];
  $("count").textContent = items.length + "件（" + per + "）" + (st.skipped ? "／情報が不足している" + st.skipped + "件は表示していません" : "");
  if (!items.length) { showMsg("条件に合うイベントはありません。期間や施設、キーワードを変えてみてください。"); $("count").textContent = "0件（" + per + "）"; return; }
  items.forEach(function (e) { list.appendChild(card(e, fmap[e.facility_id], t)); });
}
function clean(raw) {
  if (!raw || typeof raw !== "object" || !Array.isArray(raw.events)) throw new Error("format");
  var facs = Array.isArray(raw.facilities) ? raw.facilities.filter(function (f) { return f && f.id && f.name; }) : [];
  var ids = {}; facs.forEach(function (f) { ids[f.id] = 1; });
  var skipped = 0, ev = raw.events.filter(function (e) {
    var ok = e && typeof e.title === "string" && e.title && ids[e.facility_id] && isYmd(e.start_date);
    if (ok) { if (!isYmd(e.end_date)) e.end_date = e.start_date; ok = e.end_date >= e.start_date; }
    if (!ok) skipped++; return ok;
  });
  st.skipped = skipped;
  return { metadata: raw.metadata || {}, facilities: facs, events: ev };
}
function load() {
  fetch("events.json?t=" + Date.now(), { cache: "no-store" })
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (raw) {
      st.data = clean(raw); st.today = st.today || (function () { var p = nowParts(); return p.year + "-" + p.month + "-" + p.day; })();
      $("updated").textContent = fmtUpdated(st.data.metadata.last_updated);
      if (!$("facs").children.length) buildControls();
      render();
    })
    .catch(function () { if (!st.data) showMsg("イベント情報を読み込めませんでした。時間をおいて再読み込みしてください。", true); });
}
$("q").addEventListener("input", function (e) { st.q = e.target.value; if (st.data) render(); });
tick(); setInterval(tick, 15000);
load(); setInterval(load, 600000);
})();
