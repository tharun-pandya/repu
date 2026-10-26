// UI smoke test: loads the REAL frontend/index.html in jsdom against a LIVE Repu server whose
// "Ollama" is a fake (mocked inference). Not a substitute for a real-browser Playwright run.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { JSDOM } from "jsdom";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const py = process.env.PYTHON || path.join(root, ".venv/bin/python");
let procs = [];

function startServer(args = []) {
  return new Promise((resolve, reject) => {
    const p = spawn(py, ["-m", "backend.tests.live_server", ...args], { cwd: root });
    procs.push(p);
    p.stdout.once("data", async (d) => {
      const url = String(d).trim();
      for (let i = 0; i < 100; i++) { try { if ((await fetch(url + "/api/health")).ok) return resolve(url); } catch {} await new Promise((r) => setTimeout(r, 100)); }
      reject(new Error("server never became ready"));
    });
    p.on("error", reject);
    setTimeout(() => reject(new Error("server start timeout")), 15000);
  });
}
after(() => procs.forEach((p) => p.kill()));

async function load(base) {
  const exported = [];
  const dom = await JSDOM.fromURL(base + "/", {
    runScripts: "dangerously", resources: "usable", pretendToBeVisual: true,
    beforeParse(w) {
      w.fetch = (u, o = {}) => {
        if (o.body && o.body.entries) { const fd = new FormData(); for (const [k, v] of o.body.entries()) fd.append(k, v); o = { ...o, body: fd }; }
        return fetch(new URL(u, base), o);
      };
      w.URL.createObjectURL = (b) => { exported.push(b); return "blob:x"; };
      w.HTMLAnchorElement.prototype.click = function () {};
      w.scrollTo = () => {};
    },
  });
  return { w: dom.window, d: dom.window.document, exported };
}
const until = async (fn, ms = 8000) => { const t = Date.now(); while (Date.now() - t < ms) { const v = fn(); if (v) return v; await new Promise((r) => setTimeout(r, 40)); } throw new Error("timeout waiting for: " + fn); };
const fire = (w, el, type) => el.dispatchEvent(new w.Event(type, { bubbles: true }));

test("full review flow: sample -> preview -> extract -> confirm -> export; keyboard focus kept; clear session", async () => {
  const base = await startServer();
  const { w, d, exported } = await load(base);
  await until(() => d.getElementById("model").textContent.includes("ready"));
  assert.match(d.getElementById("model").textContent, /gemma3:4b · ready/);

  d.getElementById("sample").click();
  await until(() => d.getElementById("paste").value.includes("DBMS lab record"));
  d.getElementById("preview").click();
  await until(() => d.getElementById("previewbox").textContent.includes("Import preview"));
  assert.match(d.getElementById("previewbox").textContent, /1 attachment/);

  [...d.querySelectorAll("#previewbox button")].find((b) => b.textContent.includes("Extract tasks")).click();
  await until(() => d.querySelector("#tasks blockquote"));
  assert.match(d.getElementById("tasks").textContent, /Needs your review/);
  assert.match(d.getElementById("tasks").textContent, /AM or PM/i);  // reason is never hidden
  const exportBtn = () => [...d.querySelectorAll("#tasks button")].find((b) => b.textContent.startsWith("Export"));
  assert.equal(exportBtn().disabled, true);                         // nothing confirmed yet
  assert.match(d.getElementById("tasks").textContent, /Nothing confirmed yet/);

  // keyboard: toggling a checkbox must not lose focus
  const cb = d.getElementById("cb-task-t0001");
  cb.focus(); cb.checked = true; fire(w, cb, "change");
  assert.equal(d.activeElement.id, "cb-task-t0001");

  // ambiguous time must be chosen by the user before the task counts as confirmed
  for (const k of ["owner", "deadline", "approve"]) { const c = d.getElementById(`cb-${k}-t0001`); c.checked = true; fire(w, c, "change"); }
  assert.equal(exportBtn().disabled, true, "still blocked: AM/PM unresolved");
  assert.equal(d.getElementById("all-t0001").disabled, true, "quick-confirm needs AM/PM chosen first");
  const am = d.getElementById("tm-t0001-10:00"), pm = d.getElementById("tm-t0001-22:00");
  assert.ok(am && pm && am.getAttribute("role") === "radio");
  assert.equal(am.textContent, "10:00 AM"); assert.equal(pm.textContent, "10:00 PM");
  assert.equal(am.getAttribute("aria-checked"), "false");        // nothing pre-selected: the user must choose
  am.click();
  await until(() => d.getElementById("tab-confirmed").textContent.includes("1"));   // card moved to Confirmed
  assert.equal(exportBtn().disabled, false);
  assert.match(exportBtn().textContent, /Export 1 confirmed/);

  exportBtn().click();
  await until(() => exported.length === 1);
  const ics = await exported[0].text();
  assert.match(ics, /BEGIN:VCALENDAR/); assert.match(ics, /DTSTART:20261027T100000/);
  assert.equal((ics.match(/BEGIN:VEVENT/g) || []).length, 1);          // only the one confirmed task
  await until(() => d.getElementById("status").textContent.includes("Exported 1"));

  // morning brief + timeline (brief lines are labelled as unverified AI text)
  assert.match(d.getElementById("brief").textContent, /candidate task/);
  assert.match(d.getElementById("brief").textContent, /Lab record due tomorrow/);
  assert.match(d.getElementById("brief").textContent, /AI summary · unverified/);
  assert.match(d.getElementById("timeline").textContent, /Submit DBMS lab record/);
  assert.match(d.getElementById("timeline").textContent, /confirmed/);
  const before = d.documentElement.dataset.theme; d.getElementById("theme").click();
  assert.notEqual(d.documentElement.dataset.theme, before);

  // dismiss + restore (dismissed items live in their own tab)
  const dis = [...d.querySelectorAll("#tasks button")].find((b) => b.id.startsWith("dis-"));
  dis.click();
  await until(() => d.getElementById("tab-dismissed"));
  d.getElementById("tab-dismissed").click();
  await until(() => d.querySelector("[id^=res-]"));
  d.querySelector("[id^=res-]").click();
  await until(() => !d.querySelector("[id^=res-]"));
  assert.equal(d.getElementById("tab-review").getAttribute("aria-selected") === "true" || d.getElementById("tab-confirmed").getAttribute("aria-selected") === "true", true);

  // clear session
  [...d.querySelectorAll("#previewbox button")].find((b) => b.textContent === "Clear session").click();
  await until(() => d.getElementById("tasks").children.length === 0);
  assert.equal(d.getElementById("paste").value, "");
  assert.match(d.getElementById("status").textContent, /released|No such session/);
  w.close();
});

test("hosted-demo mode shows a banner, disables upload, and blocks private text", async () => {
  const base = await startServer(["--demo"]);
  const { w, d } = await load(base);
  await until(() => d.getElementById("demo"));
  assert.match(d.getElementById("demo").textContent, /fictional sample data only/);
  assert.equal(d.getElementById("file").disabled, true);
  d.getElementById("paste").value = "26/10/2026, 8:05 pm - A: my private chat";
  d.getElementById("preview").click();
  await until(() => d.getElementById("status").textContent.includes("only accepts"));
  assert.equal(d.getElementById("status").getAttribute("role"), "alert");
  w.close();
});
