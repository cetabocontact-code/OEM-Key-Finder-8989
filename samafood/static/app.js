"use strict";

const LANG = window.SAMA_LANG || "ar";
const AR = LANG === "ar";
const cart = new Map(); // sku -> {name, base, your, qty, min}
let discountPct = 0;
let loggedIn = false;

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: opts.body && !(opts.body instanceof FormData) ? { "Content-Type": "application/json" } : {},
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}

const money = (n) => (n == null ? "-" : Number(n).toFixed(2) + (AR ? " د.أ" : " JOD"));

// ---- tabs ----
$$(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".tab").forEach((b) => b.classList.remove("active"));
    $$(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $("#" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "orders") loadOrders();
  });
});

// ---- me / tier ----
async function loadMe() {
  const { data } = await api("/api/me");
  const badge = $("#tier-badge");
  if (data.client) {
    loggedIn = true;
    discountPct = data.client.discount_pct || 0;
    badge.textContent = `${data.client.tier} · ${AR ? "خصم" : "discount"} ${discountPct}%`;
    badge.classList.remove("hidden");
  } else {
    loggedIn = false;
    badge.classList.add("hidden");
  }
}

// ---- catalog ----
async function loadCatalog() {
  const { data } = await api("/api/catalog");
  discountPct = data.discount_pct || 0;
  const grid = $("#catalog-grid");
  grid.innerHTML = "";
  data.products.forEach((p) => {
    const showYour = p.your_price != null;
    const card = document.createElement("div");
    card.className = "card product";
    card.innerHTML = `
      <div class="cat">${p.category}</div>
      <h3>${p.name}</h3>
      <div class="size">${p.size}</div>
      <div class="price-row">
        <span class="your-price">${money(showYour ? p.your_price : p.base_price)}</span>
        ${showYour && discountPct > 0 ? `<span class="base-price">${money(p.base_price)}</span>` : ""}
      </div>
      <div class="qty-row">
        <input type="number" min="0" step="${p.min_order}" placeholder="${AR ? "الكمية" : "Qty"}" data-min="${p.min_order}">
        <button class="primary add" ${showYour ? "" : "disabled title='login'"}>${AR ? "أضف" : "Add"}</button>
      </div>
      <div class="size">${AR ? "أدنى طلب" : "Min"}: ${p.min_order} · ${AR ? "متوفر" : "Stock"}: ${p.stock}</div>`;
    const input = card.querySelector("input");
    card.querySelector(".add").addEventListener("click", () => {
      const qty = parseInt(input.value, 10) || 0;
      if (qty <= 0) return;
      addToCart(p, qty);
    });
    grid.appendChild(card);
  });
  if (!data.logged_in) {
    grid.insertAdjacentHTML("afterbegin", `<p class="size">${AR ? "سجّل الدخول لرؤية أسعارك الخاصة." : "Log in to see your tier prices."}</p>`);
  }
}

function addToCart(p, qty) {
  const your = p.your_price != null ? p.your_price : p.base_price;
  cart.set(p.sku, { name: p.name, base: p.base_price, your, qty, min: p.min_order });
  renderCart();
}

function renderCart() {
  const box = $("#cart");
  const items = $("#cart-items");
  if (cart.size === 0) {
    box.classList.add("hidden");
    return;
  }
  box.classList.remove("hidden");
  items.innerHTML = "";
  let subtotal = 0;
  cart.forEach((it, sku) => {
    subtotal += it.base * it.qty;
    const line = document.createElement("div");
    line.className = "cart-line";
    line.innerHTML = `<span>${it.name} ×${it.qty}</span><span>${money(it.base * it.qty)} <a href="#" data-sku="${sku}" class="rm">✕</a></span>`;
    line.querySelector(".rm").addEventListener("click", (e) => {
      e.preventDefault();
      cart.delete(sku);
      renderCart();
    });
    items.appendChild(line);
  });
  const total = subtotal * (1 - discountPct / 100);
  $("#cart-subtotal").textContent = money(subtotal);
  $("#cart-discount").textContent = discountPct + "%";
  $("#cart-total").textContent = money(total);
}

$("#place-order").addEventListener("click", async () => {
  const msg = $("#order-msg");
  if (!loggedIn) {
    msg.textContent = AR ? "يرجى تسجيل الدخول أولاً." : "Please log in first.";
    msg.className = "form-msg err";
    openLogin();
    return;
  }
  const items = Array.from(cart.entries()).map(([sku, it]) => ({ sku, qty: it.qty }));
  const { ok, data } = await api("/api/orders", { method: "POST", body: JSON.stringify({ items }) });
  if (ok) {
    msg.textContent = `${AR ? "تم استلام طلبك" : "Order received"} #${data.order_id} · ${money(data.total)}`;
    msg.className = "form-msg ok";
    cart.clear();
    renderCart();
  } else {
    msg.textContent = (AR ? "تعذّر إرسال الطلب: " : "Order failed: ") + (data.error || "");
    msg.className = "form-msg err";
  }
});

// ---- offers ----
async function loadOffers() {
  const { data } = await api("/api/offers");
  const list = $("#offers-list");
  list.innerHTML = data.offers.length ? "" : `<p>${AR ? "لا توجد عروض حالياً." : "No offers right now."}</p>`;
  data.offers.forEach((o) => {
    const el = document.createElement("div");
    el.className = "offer";
    el.innerHTML = `<div class="kind">${o.kind}</div><h3>${o.title}</h3><p>${o.body}</p>`;
    list.appendChild(el);
  });
}

// ---- orders ----
async function loadOrders() {
  if (!loggedIn) {
    $("#orders-list").innerHTML = `<p>${AR ? "سجّل الدخول لعرض طلباتك." : "Log in to view your orders."}</p>`;
    return;
  }
  const { data } = await api("/api/orders");
  const list = $("#orders-list");
  list.innerHTML = data.orders.length ? "" : `<p>${AR ? "لا توجد طلبات بعد." : "No orders yet."}</p>`;
  data.orders.forEach((o) => {
    const lines = o.items.map((i) => `${AR ? i.name_ar : i.name_en} ×${i.qty}`).join("، ");
    const el = document.createElement("div");
    el.className = "order";
    el.innerHTML = `<strong>#${o.id}</strong> — ${money(o.total)} <span class="meta">(${o.status})</span><div class="meta">${o.created_at}</div><div>${lines}</div>`;
    list.appendChild(el);
  });
}

// ---- login (phone + OTP) ----
function openLogin() { $("#login-modal").classList.remove("hidden"); }
function closeLogin() { $("#login-modal").classList.add("hidden"); }
$("#login-btn")?.addEventListener("click", openLogin);
$("#close-login").addEventListener("click", closeLogin);
$("#logout-btn")?.addEventListener("click", async () => {
  await api("/api/auth/logout", { method: "POST" });
  location.reload();
});

$("#send-code").addEventListener("click", async () => {
  const phone = $("#login-phone").value.trim();
  const msg = $("#login-msg");
  const { ok, data } = await api("/api/auth/request-otp", { method: "POST", body: JSON.stringify({ phone }) });
  if (ok) {
    $("#login-step-phone").classList.add("hidden");
    $("#login-step-code").classList.remove("hidden");
    msg.className = "form-msg ok";
    msg.textContent = data.dev_code
      ? `${AR ? "رمز تجريبي" : "Dev code"}: ${data.dev_code}`
      : AR ? "تم إرسال الرمز." : "Code sent.";
  } else {
    msg.className = "form-msg err";
    msg.textContent = data.error === "not_registered"
      ? (AR ? "رقم غير مسجّل. يمكنك التقدّم كبائع." : "Not registered. You can apply as a vendor.")
      : (data.error || "error");
  }
});

$("#verify-code").addEventListener("click", async () => {
  const phone = $("#login-phone").value.trim();
  const code = $("#login-code").value.trim();
  const msg = $("#login-msg");
  const { ok, data } = await api("/api/auth/verify-otp", { method: "POST", body: JSON.stringify({ phone, code }) });
  if (ok) {
    location.reload();
  } else {
    msg.className = "form-msg err";
    msg.textContent = data.error || "error";
  }
});

// ---- vendor application ----
$("#vendor-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = $("#vendor-msg");
  const { ok, data } = await fetch("/api/vendor-application", { method: "POST", body: new FormData(e.target) }).then(async (r) => ({ ok: r.ok, data: await r.json() }));
  if (ok) {
    msg.className = "form-msg ok";
    msg.textContent = AR ? "تم استلام طلبك، ستتم مراجعته." : "Application received, pending review.";
    e.target.reset();
  } else {
    msg.className = "form-msg err";
    msg.textContent = (AR ? "خطأ: " : "Error: ") + (data.error || "");
  }
});

// ---- push notifications ----
function urlB64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

$("#notify-btn").addEventListener("click", async () => {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    alert(AR ? "الإشعارات غير مدعومة في هذا المتصفح." : "Push not supported in this browser.");
    return;
  }
  const perm = await Notification.requestPermission();
  if (perm !== "granted") return;
  const reg = await navigator.serviceWorker.register("/static/sw.js");
  const vapid = document.body.dataset.vapid;
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlB64ToUint8Array(vapid),
  });
  await api("/api/push/subscribe", { method: "POST", body: JSON.stringify(sub) });
  $("#notify-btn").textContent = AR ? "الإشعارات مفعّلة" : "Notifications on";
});

// ---- init ----
loadMe().then(loadCatalog);
loadOffers();
