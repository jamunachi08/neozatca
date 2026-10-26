# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt
"""Official ZATCA destinations, in one place, so every screen links to the same URLs."""

import frappe

ENVIRONMENTS = {
	"production": {"label": "Production (Live)", "label_ar": "الإنتاج (مباشر)", "color": "green", "legal": True},
	"simulation": {"label": "Simulation (Pre-production)", "label_ar": "المحاكاة", "color": "orange", "legal": False},
	"sandbox": {"label": "Sandbox (Developer)", "label_ar": "بيئة المطورين", "color": "red", "legal": False},
}

ZATCA_LINKS = [
	{
		"key": "fatoora", "group": "portal", "env": "production",
		"label": "Fatoora Portal (Production / Live)", "label_ar": "بوابة فاتورة",
		"url": "https://fatoora.zatca.gov.sa/",
		"otp_hint": "Log in with your ERAD credentials → Onboard New Solution Unit/Device → enter the number of devices → copy the OTP. Valid for 1 hour.",
	},
	{
		"key": "simulation", "group": "portal", "env": "simulation",
		"label": "Fatoora Simulation Portal", "label_ar": "بوابة فاتورة - المحاكاة",
		"url": "https://fatoora.zatca.gov.sa/",
		"otp_hint": "Log in to Fatoora → switch to “FATOORA Portal Simulation” (top right) → Onboard New Solution Unit/Device → copy the OTP. Valid for 1 hour.",
	},
	{
		"key": "developer", "group": "portal", "env": "sandbox",
		"label": "Developer Portal (Sandbox)", "label_ar": "بوابة المطورين",
		"url": "https://sandbox.zatca.gov.sa/",
		"otp_hint": "The developer sandbox needs no portal OTP — use the test OTP 123345.",
	},
	{
		"key": "specs", "group": "reference",
		"label": "E-Invoice Specifications", "label_ar": "مواصفات الفاتورة الإلكترونية",
		"url": "https://zatca.gov.sa/en/E-Invoicing/SystemsDevelopers/Pages/E-Invoice-specifications.aspx",
	},
	{
		"key": "manual", "group": "reference",
		"label": "Fatoora Portal User Manual (PDF)", "label_ar": "دليل مستخدم بوابة فاتورة",
		"url": "https://zatca.gov.sa/en/E-Invoicing/Introduction/Guidelines/Documents/Fatoora_Portal_User_Manual_English.pdf",
	},
	{
		"key": "community", "group": "reference",
		"label": "ZATCA Developer Community", "label_ar": "مجتمع مطوري هيئة الزكاة",
		"url": "https://zatca1.discourse.group/",
	},
	{
		"key": "support", "group": "reference",
		"label": "ZATCA Solution-Provider Support (email)", "label_ar": "دعم مزودي الحلول",
		"url": "mailto:sp_support@zatca.gov.sa",
	},
]


def portal_for(environment: str | None) -> dict:
	env = environment or "production"
	return next((l for l in ZATCA_LINKS if l.get("env") == env), ZATCA_LINKS[0])


@frappe.whitelist()
def get_zatca_links() -> dict:
	return {"links": ZATCA_LINKS, "environments": ENVIRONMENTS}
