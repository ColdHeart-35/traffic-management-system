/* Shared helpers for every page: sign-in, API calls, small utilities. */
const TMS = (() => {
  const KEY = "tms_token";
  const listeners = [];
  let user = null;
  let loaded = false;

  const $ = (selector, root = document) => root.querySelector(selector);
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function token() { try { return sessionStorage.getItem(KEY); } catch (e) { return null; } }
  function setToken(value) { try { value ? sessionStorage.setItem(KEY, value) : sessionStorage.removeItem(KEY); } catch (e) { /* storage blocked */ } }

  function message(err) {
    const detail = err && err.data && err.data.detail;
    if (Array.isArray(detail)) return detail.map((d) => (typeof d === "string" ? d : `${d.field}: ${d.message}`)).join("; ");
    return detail || (err && err.message) || "Something went wrong";
  }

  async function api(path, options = {}) {
    const headers = { "Content-Type": "application/json" };
    const t = token();
    if (t) headers.Authorization = "Bearer " + t;
    const res = await fetch(path, { method: options.method || "GET", headers, body: options.body ? JSON.stringify(options.body) : undefined });
    let data = null;
    try { data = await res.json(); } catch (e) { /* empty body */ }
    if (!res.ok) {
      const err = new Error((data && data.error) || res.statusText);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  function toast(text, bad = false) {
    const box = $("#toast");
    if (!box) return;
    const item = document.createElement("div");
    if (bad) item.className = "bad";
    item.textContent = text;
    box.appendChild(item);
    setTimeout(() => item.remove(), 5000);
  }

  function renderHeader() {
    $("#login-form").hidden = !!user;
    $("#whoami").hidden = !user;
    if (user) { $("#who-name").textContent = user.username; $("#who-role").textContent = user.role; }
  }

  async function refreshUser() {
    try { user = await api("/api/v1/auth/me"); } catch (e) { user = null; setToken(null); }
    loaded = true;
    renderHeader();
    listeners.forEach((fn) => fn(user));
  }

  function onUser(fn) { listeners.push(fn); if (loaded) fn(user); }

  document.addEventListener("DOMContentLoaded", () => {
    $("#login-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        const out = await api("/api/v1/auth/login", { method: "POST", body: { username: $("#login-user").value, password: $("#login-pass").value } });
        setToken(out.token);
        $("#login-pass").value = "";
        await refreshUser();
      } catch (err) { toast(message(err), true); }
    });
    $("#logout").addEventListener("click", async () => { setToken(null); await refreshUser(); });
    refreshUser();
  });

  return { api, esc, toast, message, onUser, $, user: () => user };
})();
