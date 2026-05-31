"use strict";

const LANG = window.SAMA_LANG || "ar";
const AR = LANG === "ar";
const cart = new Map(); // sku -> {name, base, your, qty, min}
let discountPct = 0;
let canOrder = false;

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
const T = (a, e) => (AR ? a : e);

// ---- tab navigation (bottom nav) ----
function switchTab(name) {
  const target = $$(".nav-btn").find((b) => b.dataset.tab === name);
  if (!target || target.hidden) return;
  $$(".nav-btn").forEach((b) => b.classList.remove("active"));
  $$(".panel").forEach((p) => p.classList.remove("active"));
  target.classList.add("active");
  const panel = $("#" + name);
  if (panel) panel.classList.add("active");
  if (name === "orders") { showOrdersList(); loadOrders(); }
  if (name === "team") loadTeam();
  if (name === "dashboard") loadDashboard();
  if (name === "cart") renderCheckout();
}
$$(".nav-btn").forEach((btn) => btn.addEventListener("click", () => switchTab(btn.dataset.tab)));

// ---- me / tier ----
async function loadMe() {
  const { data } = await api("/api/me");
  if (!data.user) { location.href = "/"; return; }
  canOrder = data.user.can_order;
  discountPct = data.user.discount_pct || 0;
  $("#tier-badge").textContent = `${data.user.business} · ${data.user.tier} ${discountPct}% · ${data.user.name}`;
  $("#tier-badge").classList.remove("hidden");
  const navTeam = $("#nav-team");
  if (navTeam) navTeam.hidden = !data.user.can_manage_team;
}

// ---- dashboard ----
async function loadDashboard() {
  const { ok, data } = await api("/api/dashboard");
  if (!ok) return;
  $("#dash-business").textContent = data.business;
  $("#dash-tier").textContent = data.tier || "";
  $("#dash-discount").textContent = `${data.discount_pct}%`;
  $("#dash-annual").textContent = money(data.yearly_spend);
  $("#dash-orders-count").textContent = data.orders_count;
  $("#dash-orders-total").textContent = money(data.orders_total);
  $("#dash-progress-fill").style.width = `${data.progress_pct}%`;
  $("#dash-progress-now").textContent = `${data.discount_pct}%`;
  if (data.next_tier) {
    $("#dash-progress-next").textContent = `${data.next_tier.name} · ${data.next_tier.discount_pct}%`;
    $("#dash-next").textContent = `${money(data.amount_to_next)} ${T("متبقٍ للوصول للفئة التالية", "left to the next tier")}`;
  } else {
    $("#dash-progress-next").textContent = "";
    $("#dash-next").textContent = T("أنت في أعلى فئة 🎉", "You're at the top tier 🎉");
  }
}

// ---- catalog ----
async function loadCatalog() {
  const { data } = await api("/api/catalog");
  discountPct = data.discount_pct || 0;
  const grid = $("#catalog-grid");
  grid.innerHTML = "";
  data.products.forEach((p) => {
    const card = document.createElement("div");
    card.className = "card product";
    const img = p.image_url ? `<img class="product-img" src="${p.image_url}" alt="${p.name}" loading="lazy">` : `<div class="product-img placeholder"></div>`;
    card.innerHTML = `
      ${img}
      <div class="cat">${p.category}</div>
      <h3>${p.name}</h3>
      <div class="size">${p.size}</div>
      <div class="price-row">
        <span class="your-price">${money(p.your_price)}</span>
        ${discountPct > 0 ? `<span class="base-price">${money(p.base_price)}</span>` : ""}
      </div>
      <div class="qty-row">
        <input type="number" min="0" step="${p.min_order}" placeholder="${T("الكمية", "Qty")}">
        <button class="primary add" ${canOrder ? "" : "disabled title='" + T("للاطلاع فقط", "View-only") + "'"}>${T("أضف", "Add")}</button>
      </div>
      <div class="size">${T("أدنى طلب", "Min")}: ${p.min_order} · ${T("متوفر", "Stock")}: ${p.stock}</div>`;
    const input = card.querySelector("input");
    card.querySelector(".add").addEventListener("click", () => {
      const qty = parseInt(input.value, 10) || 0;
      if (qty <= 0) return;
      addToCart(p, qty);
      input.value = "";
      toast(T("تمت الإضافة للسلة", "Added to cart"));
    });
    grid.appendChild(card);
  });
}

// ---- cart state ----
function addToCart(p, qty) {
  const your = p.your_price != null ? p.your_price : p.base_price;
  const existing = cart.get(p.sku);
  const newQty = (existing ? existing.qty : 0) + qty;
  cart.set(p.sku, { name: p.name, base: p.base_price, your, qty: newQty, min: p.min_order });
  updateCartBadge();
}

function updateCartBadge() {
  const badge = $("#cart-badge");
  if (!badge) return;
  const count = Array.from(cart.values()).reduce((s, it) => s + it.qty, 0);
  if (count > 0) {
    badge.textContent = count;
    badge.hidden = false;
    badge.style.display = "";
  } else {
    badge.textContent = "";
    badge.hidden = true;
    badge.style.display = "none";
  }
}

// ---- cart / checkout ----
function renderCheckout() {
  // make sure we're showing the checkout state (not the post-order confirmation)
  $("#cart-state-checkout").hidden = false;
  $("#cart-state-confirmed").hidden = true;
  const lines = $("#cart-lines");
  const empty = $("#cart-empty");
  const options = $("#cart-options");
  const totalsCard = $("#cart-totals");
  lines.innerHTML = "";
  if (cart.size === 0) {
    empty.hidden = false;
    options.hidden = true;
    totalsCard.hidden = true;
    return;
  }
  empty.hidden = true;
  options.hidden = false;
  totalsCard.hidden = false;
  let subtotal = 0;
  cart.forEach((it, sku) => {
    subtotal += it.base * it.qty;
    const row = document.createElement("div");
    row.className = "cart-line";
    row.innerHTML = `
      <div class="cart-line-info">
        <div class="cart-line-name">${it.name}</div>
        <div class="cart-line-sub">${money(it.base)} × <input type="number" min="0" value="${it.qty}" data-sku="${sku}" class="qty-input"></div>
      </div>
      <div class="cart-line-total">${money(it.base * it.qty)} <button class="rm" data-sku="${sku}" title="${T("حذف","Remove")}">✕</button></div>`;
    row.querySelector(".qty-input").addEventListener("input", (e) => {
      const v = parseInt(e.target.value, 10) || 0;
      if (v <= 0) cart.delete(sku); else cart.get(sku).qty = v;
      updateCartBadge();
      renderCheckout();
    });
    row.querySelector(".rm").addEventListener("click", () => {
      cart.delete(sku);
      updateCartBadge();
      renderCheckout();
    });
    lines.appendChild(row);
  });
  const total = subtotal * (1 - discountPct / 100);
  $("#cart-subtotal").textContent = money(subtotal);
  $("#cart-discount").textContent = discountPct + "%";
  $("#cart-total").textContent = money(total);
}

// delivery radio toggles address field
$$('input[name="delivery"]').forEach((r) =>
  r.addEventListener("change", () => {
    $("#delivery-addr-wrap").hidden = $('input[name="delivery"]:checked').value !== "delivery";
  })
);

$("#place-order").addEventListener("click", async () => {
  const msg = $("#order-msg");
  if (!canOrder) {
    msg.className = "form-msg err";
    msg.textContent = T("حسابك للاطلاع فقط ولا يمكنه تقديم الطلبات.", "Your account is view-only and cannot place orders.");
    return;
  }
  if (cart.size === 0) return;
  const items = Array.from(cart.entries()).map(([sku, it]) => ({ sku, qty: it.qty }));
  const delivery_method = $('input[name="delivery"]:checked').value;
  const delivery_address = delivery_method === "delivery" ? $("#delivery-addr").value.trim() : "";
  const payment_method = $('input[name="payment"]:checked').value;
  const note = $("#order-note").value.trim();
  if (delivery_method === "delivery" && !delivery_address) {
    msg.className = "form-msg err";
    msg.textContent = T("يرجى إدخال عنوان التوصيل.", "Please enter a delivery address.");
    return;
  }
  msg.textContent = "";
  const { ok, data } = await api("/api/orders", {
    method: "POST",
    body: JSON.stringify({ items, delivery_method, delivery_address, payment_method, note }),
  });
  if (ok) {
    cart.clear();
    updateCartBadge();
    showConfirmation(data);
  } else {
    msg.className = "form-msg err";
    const errs = {
      delivery_address_required: T("يرجى إدخال عنوان التوصيل.", "Delivery address required."),
      below_min_order: T("بعض الكميات أقل من الحد الأدنى للطلب.", "Some quantities are below the minimum."),
      empty_order: T("السلة فارغة.", "Cart is empty."),
    };
    msg.textContent = errs[data.error] || (data.error || "error");
  }
});

function showConfirmation(o) {
  $("#cart-state-checkout").hidden = true;
  const c = $("#cart-state-confirmed");
  c.hidden = false;
  c.innerHTML = `
    <div class="card confirm-card">
      <div class="confirm-icon">✓</div>
      <h2>${T("تم تأكيد طلبك", "Order confirmed")}</h2>
      <p class="confirm-num">${T("رقم الطلب", "Order number")}: <strong>#${o.order_id}</strong></p>
      <p class="confirm-total">${T("الإجمالي", "Total")}: <strong>${money(o.total)}</strong></p>
      <div class="confirm-actions">
        <button class="primary" id="view-receipt">${T("عرض الفاتورة", "View receipt")}</button>
        <button class="ghost" id="back-catalog">${T("متابعة التسوّق", "Continue shopping")}</button>
      </div>
    </div>`;
  c.querySelector("#view-receipt").addEventListener("click", () => {
    switchTab("orders");
    setTimeout(() => showReceipt(o.order_id), 100);
  });
  c.querySelector("#back-catalog").addEventListener("click", () => switchTab("catalog"));
}

// ---- offers ----
async function loadOffers() {
  const { data } = await api("/api/offers");
  const list = $("#offers-list");
  list.innerHTML = data.offers.length ? "" : `<p>${T("لا توجد عروض حالياً.", "No offers right now.")}</p>`;
  data.offers.forEach((o) => {
    const el = document.createElement("div");
    el.className = "offer";
    el.innerHTML = `<div class="kind">${o.kind}</div><h3>${o.title}</h3><p>${o.body}</p>`;
    list.appendChild(el);
  });
}

// ---- orders + receipt ----
const PAYMENT_LABELS = {
  on_account: T("على الحساب", "On account"),
  cash: T("نقداً عند الاستلام", "Cash on delivery"),
  card: T("بطاقة عند التسليم", "Card on delivery"),
};
const DELIVERY_LABELS = {
  pickup: T("استلام من المستودع", "Pickup from warehouse"),
  delivery: T("توصيل", "Delivery"),
};

function showOrdersList() {
  $("#orders-list").hidden = false;
  $("#orders-receipt").hidden = true;
}

async function loadOrders() {
  const { data } = await api("/api/orders");
  const list = $("#orders-list");
  list.innerHTML = data.orders.length ? "" : `<p>${T("لا توجد طلبات حتى الآن.", "No orders yet.")}</p>`;
  data.orders.forEach((o) => {
    const el = document.createElement("button");
    el.className = "order order-row";
    el.dataset.id = o.id;
    const by = o.placed_by ? ` · ${T("بواسطة","by")} ${o.placed_by}` : "";
    el.innerHTML = `
      <div class="order-row-left">
        <strong>#${o.id}</strong>
        <span class="meta">${o.status}${by}</span>
        <span class="meta">${o.created_at.replace("T", " ").slice(0, 16)}</span>
      </div>
      <div class="order-row-right">
        <span class="order-total">${money(o.total)}</span>
        <span class="meta">${o.items.length} ${T("صنف", "item(s)")}</span>
      </div>`;
    el.addEventListener("click", () => showReceipt(o.id));
    list.appendChild(el);
  });
}

async function showReceipt(orderId) {
  $("#orders-list").hidden = true;
  const box = $("#orders-receipt");
  box.hidden = false;
  box.innerHTML = `<p>${T("جارٍ التحميل...", "Loading...")}</p>`;
  const { ok, data } = await api(`/api/orders/${orderId}`);
  if (!ok) { box.innerHTML = `<p>${T("تعذّر التحميل", "Failed to load")}</p>`; return; }
  const lines = data.items.map((i) => `
    <tr>
      <td>${AR ? i.name_ar : i.name_en}</td>
      <td class="num">${i.qty}</td>
      <td class="num">${money(i.base_price)}</td>
      <td class="num">${money(i.base_price * i.qty)}</td>
    </tr>`).join("");
  const addr = data.delivery_method === "delivery" && data.delivery_address ? `<p>📍 ${data.delivery_address}</p>` : "";
  box.innerHTML = `
    <div class="receipt-actions no-print">
      <button class="ghost" id="back-orders">← ${T("الطلبات", "Orders")}</button>
      <button class="primary" id="print-receipt">🖨 ${T("طباعة", "Print")}</button>
    </div>
    <div class="card receipt">
      <div class="receipt-head">
        <img src="/static/logo.png" class="receipt-logo" alt="Sama">
        <div class="receipt-meta">
          <div><strong>${data.business}</strong></div>
          <div class="meta">${T("رقم الطلب", "Order")}: <strong>#${data.id}</strong></div>
          <div class="meta">${data.created_at.replace("T", " ").slice(0, 16)}</div>
        </div>
      </div>
      <table class="receipt-table">
        <thead><tr>
          <th>${T("الصنف", "Item")}</th><th class="num">${T("الكمية", "Qty")}</th>
          <th class="num">${T("السعر", "Price")}</th><th class="num">${T("المجموع", "Total")}</th>
        </tr></thead>
        <tbody>${lines}</tbody>
      </table>
      <div class="receipt-totals">
        <div><span>${T("الإجمالي قبل الخصم", "Subtotal")}</span><span>${money(data.subtotal)}</span></div>
        <div><span>${T("الخصم", "Discount")}</span><span>${data.discount_pct}%</span></div>
        <div class="grand"><span>${T("الإجمالي", "Total")}</span><span>${money(data.total)}</span></div>
      </div>
      <div class="receipt-meta-bottom">
        <p><strong>${T("طريقة الاستلام", "Delivery")}:</strong> ${DELIVERY_LABELS[data.delivery_method]}</p>
        ${addr}
        <p><strong>${T("طريقة الدفع", "Payment")}:</strong> ${PAYMENT_LABELS[data.payment_method]}</p>
        ${data.note ? `<p><strong>${T("ملاحظات", "Notes")}:</strong> ${data.note}</p>` : ""}
        <p class="meta">${T("الحالة", "Status")}: ${data.status} · ${data.placed_by ? T("بواسطة", "by") + " " + data.placed_by : ""}</p>
      </div>
    </div>`;
  box.querySelector("#back-orders").addEventListener("click", showOrdersList);
  box.querySelector("#print-receipt").addEventListener("click", () => window.print());
}

// ---- team management (owner) ----
async function loadTeam() {
  const { ok, data } = await api("/api/team");
  const box = $("#team-list");
  if (!box) return;
  if (!ok) { box.innerHTML = `<p>${T("للمالك فقط.", "Owner only.")}</p>`; return; }
  const roleLabel = (r) => ({ owner: T("مالك","Owner"), buyer: T("مشترٍ","Buyer"), viewer: T("مشاهد","Viewer") }[r] || r);
  box.innerHTML = "";
  data.team.forEach((u) => {
    const isMe = u.id === data.me;
    const row = document.createElement("div");
    row.className = "order";
    const toggle = u.status === "active" ? T("تعطيل", "Disable") : T("تفعيل", "Enable");
    row.innerHTML = `<strong>${u.name}</strong> · ${u.phone}
      <span class="meta">(${roleLabel(u.role)} · ${u.status})</span>`;
    if (!isMe && u.role !== "owner") {
      const btn = document.createElement("button");
      btn.className = "ghost";
      btn.style.marginInlineStart = "0.5rem";
      btn.textContent = toggle;
      btn.addEventListener("click", async () => {
        await api(`/api/team/${u.id}/update`, { method: "POST", body: JSON.stringify({ status: u.status === "active" ? "disabled" : "active" }) });
        loadTeam();
      });
      row.appendChild(btn);
    }
    box.appendChild(row);
  });
}

const inviteForm = $("#invite-form");
if (inviteForm) {
  inviteForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const msg = $("#invite-msg");
    const { ok, data } = await api("/api/team/invite", {
      method: "POST",
      body: JSON.stringify({ name: fd.get("name"), phone: fd.get("phone"), role: fd.get("role") }),
    });
    if (ok) { msg.className = "form-msg ok"; msg.textContent = T("تمت الإضافة.", "User added."); e.target.reset(); loadTeam(); }
    else { msg.className = "form-msg err"; msg.textContent = data.error === "phone_taken" ? T("الرقم مستخدم مسبقاً.", "Phone already in use.") : (data.error || "error"); }
  });
}

// ---- contact form ----
const contactForm = $("#contact-form");
if (contactForm) {
  contactForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const msg = $("#contact-msg");
    const { ok, data } = await api("/api/contact-message", {
      method: "POST",
      body: JSON.stringify({
        name: fd.get("name"), phone: fd.get("phone"),
        subject: fd.get("subject"), message: fd.get("message"),
      }),
    });
    if (ok) {
      msg.className = "form-msg ok";
      msg.textContent = T("تم إرسال رسالتك. سيتواصل معك فريق سما قريباً.", "Message sent. Sama's team will get back to you.");
      e.target.reset();
    } else {
      msg.className = "form-msg err";
      msg.textContent = data.error || "error";
    }
  });
}

// ---- logout ----
$("#logout-btn")?.addEventListener("click", async () => {
  await api("/api/auth/logout", { method: "POST" });
  location.href = "/";
});

// ---- push notifications ----
function urlB64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

$("#notify-btn")?.addEventListener("click", async () => {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    alert(T("الإشعارات غير مدعومة في هذا المتصفح.", "Push not supported in this browser."));
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
  const btn = $("#notify-btn");
  btn.classList.add("active");
  btn.title = T("الإشعارات مفعّلة", "Notifications on");
});

// ---- toast (brief feedback for cart adds etc.) ----
function toast(msg) {
  let el = $("#toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("show"), 1800);
}

// ---- init ----
loadMe().then(() => { loadCatalog(); loadOffers(); loadDashboard(); });
