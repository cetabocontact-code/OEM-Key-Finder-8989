"""Minimal Arabic (default) / English string table."""

from __future__ import annotations

LANGS = ("ar", "en")
DEFAULT_LANG = "ar"

STRINGS: dict[str, dict[str, str]] = {
    "app_name": {"ar": "سما لتواصل البائعين", "en": "Sama Vendor Connect"},
    "tagline": {"ar": "اطلب منتجات سما واحصل على عروضك الخاصة", "en": "Order Sama products and get your tailored offers"},
    "login": {"ar": "تسجيل الدخول", "en": "Log in"},
    "logout": {"ar": "تسجيل الخروج", "en": "Log out"},
    "phone": {"ar": "رقم الهاتف", "en": "Phone number"},
    "send_code": {"ar": "إرسال الرمز", "en": "Send code"},
    "enter_code": {"ar": "أدخل رمز التحقق", "en": "Enter verification code"},
    "verify": {"ar": "تحقق", "en": "Verify"},
    "catalog": {"ar": "الكتالوج", "en": "Catalog"},
    "offers": {"ar": "العروض", "en": "Offers"},
    "cart": {"ar": "السلة", "en": "Cart"},
    "orders": {"ar": "طلباتي", "en": "My orders"},
    "your_price": {"ar": "سعرك", "en": "Your price"},
    "base_price": {"ar": "السعر الأساسي", "en": "Base price"},
    "add": {"ar": "أضف", "en": "Add"},
    "place_order": {"ar": "تأكيد الطلب", "en": "Place order"},
    "tier": {"ar": "فئتك", "en": "Your tier"},
    "discount": {"ar": "الخصم", "en": "Discount"},
    "become_vendor": {"ar": "تقدّم كبائع", "en": "Apply as vendor"},
    "business_name": {"ar": "اسم النشاط التجاري", "en": "Business name"},
    "contact_name": {"ar": "اسم المسؤول", "en": "Contact name"},
    "documents": {"ar": "المستندات المطلوبة", "en": "Required documents"},
    "submit": {"ar": "إرسال", "en": "Submit"},
    "enable_notifications": {"ar": "تفعيل الإشعارات", "en": "Enable notifications"},
    "subtotal": {"ar": "المجموع الفرعي", "en": "Subtotal"},
    "total": {"ar": "الإجمالي", "en": "Total"},
    "empty_cart": {"ar": "سلتك فارغة", "en": "Your cart is empty"},
    "order_placed": {"ar": "تم استلام طلبك", "en": "Your order was received"},
    "admin": {"ar": "لوحة الإدارة", "en": "Admin"},
    "team": {"ar": "المستخدمون", "en": "Team"},
    "team_desc": {"ar": "أضف مستخدمين مخوّلين ضمن نشاطك لتقديم الطلبات.", "en": "Add authorized users under your business to place orders."},
    "name": {"ar": "الاسم", "en": "Name"},
    "role": {"ar": "الصلاحية", "en": "Role"},
    "role_owner": {"ar": "مالك", "en": "Owner"},
    "role_buyer": {"ar": "مشترٍ", "en": "Buyer"},
    "role_viewer": {"ar": "مشاهد", "en": "Viewer"},
    "add_user": {"ar": "إضافة مستخدم", "en": "Add user"},
    "disable": {"ar": "تعطيل", "en": "Disable"},
    "enable": {"ar": "تفعيل", "en": "Enable"},
    "status": {"ar": "الحالة", "en": "Status"},
    "help": {"ar": "مساعدة", "en": "Help"},
    "help_title": {"ar": "كيف يعمل التطبيق", "en": "How it works"},
    "contact_us": {"ar": "تواصل معنا", "en": "Contact us"},
    "become_distributor": {"ar": "كن موزّعاً", "en": "Become a distributor"},
    "dashboard": {"ar": "لوحتي", "en": "Dashboard"},
    "your_tier": {"ar": "فئتك الحالية", "en": "Your tier"},
    "annual_purchases": {"ar": "مشترياتك السنوية", "en": "Annual purchases"},
    "your_discount": {"ar": "خصمك", "en": "Your discount"},
    "to_next_tier": {"ar": "للوصول للفئة التالية", "en": "to the next tier"},
    "next_tier_label": {"ar": "الفئة التالية", "en": "Next tier"},
    "top_tier": {"ar": "أنت في أعلى فئة 🎉", "en": "You're at the top tier 🎉"},
    "orders_in_app": {"ar": "طلباتك عبر التطبيق", "en": "Orders via the app"},
    "login_tagline": {"ar": "بوابة الموزّعين المعتمدين لدى سما فود", "en": "Authorized distributor portal for Sama Food Industries"},
    "send_code": {"ar": "أرسل رمز التحقق", "en": "Send code"},
    "otp_code": {"ar": "رمز التحقق", "en": "Verification code"},
    "verify": {"ar": "تحقق ودخول", "en": "Verify and sign in"},
    "trouble_signing_in": {"ar": "تعذّر تسجيل الدخول؟", "en": "Trouble signing in?"},
    "trouble_signing_in_help": {"ar": "إذا لم تكن مسجّلاً، يمكنك التقدّم لتصبح موزّعاً معتمداً. وإذا فقدت الوصول لرقم هاتفك المسجّل، تواصل مع سما مباشرة.", "en": "If you're not yet registered you can apply to become an authorized distributor. If you've lost access to your registered phone, contact Sama directly."},
    "apply_now": {"ar": "تقدّم لتصبح موزّعاً", "en": "Apply to become a distributor"},
    "apply_cta_intro": {"ar": "لست موزّعاً معتمداً بعد؟", "en": "Not yet an authorized distributor?"},
    "back_to_login": {"ar": "العودة لتسجيل الدخول", "en": "Back to sign in"},
    "apply_tagline": {"ar": "أرسل طلبك ليراجعه فريق سما — سيتم التواصل معك للتأكيد.", "en": "Submit your application — Sama's team will review and contact you."},
    "client_type": {"ar": "نوع النشاط", "en": "Business type"},
    "supermarket": {"ar": "سوبرماركت", "en": "Supermarket"},
    "restaurant": {"ar": "مطعم", "en": "Restaurant"},
    "cafe": {"ar": "مقهى", "en": "Café"},
    "horeca": {"ar": "فندق / مرافق ضيافة", "en": "Hotel / HoReCa"},
    "retail": {"ar": "تجارة تجزئة", "en": "Retail"},
    "submit_application": {"ar": "إرسال الطلب", "en": "Submit application"},
    "start_chat": {"ar": "ابدأ محادثة", "en": "Start a chat"},
    "start_chat_help": {"ar": "أرسل تفاصيلك ورسالتك وسيتواصل معك فريق سما.", "en": "Send your details and message — Sama's team will get back to you."},
    "subject": {"ar": "الموضوع", "en": "Subject"},
    "message": {"ar": "الرسالة", "en": "Message"},
    "send_message": {"ar": "إرسال", "en": "Send message"},
    "home": {"ar": "الرئيسية", "en": "Home"},
    "checkout": {"ar": "إتمام الطلب", "en": "Checkout"},
    "review_order": {"ar": "مراجعة الطلب", "en": "Review your order"},
    "delivery_method": {"ar": "طريقة الاستلام", "en": "Delivery method"},
    "pickup": {"ar": "استلام من المستودع", "en": "Pickup from warehouse"},
    "delivery": {"ar": "توصيل إلى العنوان", "en": "Delivery to address"},
    "delivery_address": {"ar": "عنوان التوصيل", "en": "Delivery address"},
    "payment_method": {"ar": "طريقة الدفع", "en": "Payment method"},
    "pay_on_account": {"ar": "على الحساب (الحدّ الائتماني)", "en": "On account (credit line)"},
    "pay_cash": {"ar": "نقداً عند الاستلام", "en": "Cash on delivery"},
    "pay_card": {"ar": "بطاقة ائتمان عند التسليم", "en": "Card on delivery"},
    "order_note": {"ar": "ملاحظات (اختياري)", "en": "Notes (optional)"},
    "order_confirmed": {"ar": "تم تأكيد طلبك", "en": "Order confirmed"},
    "order_number": {"ar": "رقم الطلب", "en": "Order number"},
    "view_receipt": {"ar": "عرض الفاتورة", "en": "View receipt"},
    "receipt": {"ar": "الفاتورة", "en": "Receipt"},
    "print_receipt": {"ar": "طباعة", "en": "Print"},
    "back": {"ar": "رجوع", "en": "Back"},
    "remove": {"ar": "حذف", "en": "Remove"},
    "no_orders": {"ar": "لا توجد طلبات حتى الآن.", "en": "No orders yet."},
    "cart_empty": {"ar": "سلتك فارغة. أضف منتجات من الكتالوج.", "en": "Your cart is empty. Add items from the catalog."},
    "added_to_cart": {"ar": "تمت الإضافة للسلة", "en": "Added to cart"},
    "open_cart": {"ar": "فتح السلة", "en": "Open cart"},
}

FAQ = [
    {
        "q_ar": "كيف أسجّل الدخول؟", "q_en": "How do I log in?",
        "a_ar": "أدخل رقم هاتفك المسجّل وستصلك رسالة برمز تحقق لمرة واحدة.",
        "a_en": "Enter your registered phone number and you'll get a one-time verification code.",
    },
    {
        "q_ar": "كيف أصبح موزّعاً معتمداً؟", "q_en": "How do I become an approved distributor?",
        "a_ar": "عبّئ نموذج «كن موزّعاً» وأرفق مستنداتك، وسيقوم فريق سما بمراجعته.",
        "a_en": "Fill the 'Become a distributor' form and attach your documents; the Sama team will review it.",
    },
    {
        "q_ar": "كيف أحصل على خصم أكبر؟", "q_en": "How do I get a bigger discount?",
        "a_ar": "يعتمد الخصم على إجمالي مشترياتك السنوية. كلما زادت مشترياتك ارتفعت فئتك.",
        "a_en": "Discounts depend on your yearly purchases. The more you buy, the higher your tier.",
    },
    {
        "q_ar": "هل يمكن لأكثر من شخص الطلب باسم نشاطي؟", "q_en": "Can more than one person order for my business?",
        "a_ar": "نعم، يمكن للمالك إضافة مستخدمين مخوّلين من قسم «المستخدمون».",
        "a_en": "Yes — the owner can add authorized users from the 'Team' section.",
    },
]

CONTACT = {
    "address_en": "Salem Village Main Road, Shahab, Amman, Jordan",
    "address_ar": "طريق قرية سالم الرئيسي، شهاب، عمّان، الأردن",
    "phone": "+962 6 405 9090",
    "fax": "+962 6 405 9080",
    "email": "Info@samafood.jo",
    "website": "https://samafood.jo/",
    "hours_en": "Saturday to Thursday · 8 AM – 8 PM",
    "hours_ar": "السبت إلى الخميس · ٨ صباحاً – ٨ مساءً",
}


def normalize_lang(lang: str | None) -> str:
    return lang if lang in LANGS else DEFAULT_LANG


def t(key: str, lang: str) -> str:
    lang = normalize_lang(lang)
    entry = STRINGS.get(key)
    if not entry:
        return key
    return entry.get(lang) or entry.get(DEFAULT_LANG) or key
