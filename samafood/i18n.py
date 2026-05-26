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
}


def normalize_lang(lang: str | None) -> str:
    return lang if lang in LANGS else DEFAULT_LANG


def t(key: str, lang: str) -> str:
    lang = normalize_lang(lang)
    entry = STRINGS.get(key)
    if not entry:
        return key
    return entry.get(lang) or entry.get(DEFAULT_LANG) or key
