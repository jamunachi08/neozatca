app_name = "neozatca"
app_title = "NeoZatca"
app_publisher = "Neotec Integrated Solutions"
app_description = "ZATCA e-invoicing (Phase 1 & Phase 2) for ERPNext"
app_email = "support@neotec.ai"
app_license = "mit"

# Apps screen (v15) and desktop app icon (v16+)
add_to_apps_screen = [
	{
		"name": app_name,
		"logo": "/assets/neozatca/images/neozatca-logo.svg",
		"title": app_title,
		"route": "/app/zatca",
		"has_permission": "neozatca.permissions.check_app_permission",
	}
]

# Apps
# ------------------

required_apps = ["erpnext"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "neozatca",
# 		"logo": "/assets/neozatca/logo.png",
# 		"title": "NeoZatca",
# 		"route": "/neozatca",
# 		"has_permission": "neozatca.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "desk_fonts.bundle.css"

# Load modular JS files in dependency order
app_include_js = [
    # Sales Invoice modules (load in dependency order)
    "/assets/neozatca/js/sales_invoice/prepayment.js",      # Must load first (provides constants)
    "/assets/neozatca/js/sales_invoice/pos_payments.js",    # Depends on prepayment constants
    "/assets/neozatca/js/sales_invoice/zatca_buttons.js",   # Independent
    "/assets/neozatca/js/neozatca_onboarding.js",           # One-click ZATCA onboarding UI + portal links
    "/assets/neozatca/js/sales_invoice/zatca_environment.js", # Phase / environment banner on invoices
]

# include js, css files in header of web template
# web_include_css = "/assets/neozatca/css/neozatca.css"
# web_include_js = "/assets/neozatca/js/neozatca.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "neozatca/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views

doctype_js = {
    "Company" : "public/js/company.js",
    "Branch" : "public/js/branch.js",
	"Sales Invoice" : "public/js/sales_invoice.js" ,
	"Sales Order" : "public/js/sales_order.js" ,
    "Quotation" : "public/js/quotation.js" ,
	"Delivery Note" : "public/js/delivery_note.js"
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "neozatca/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
jinja = {
	"methods": [
		"neozatca.money_in_words.custom_money_in_words",
	],
	# "filters": "neozatca.utils.jinja_filters"
}

# Installation
# ------------

# before_install = "neozatca.install.before_install"
after_install = "neozatca.install.after_install"
after_migrate = ["neozatca.install.ensure_site_setup"]

# Uninstallation
# ------------

before_uninstall = "neozatca.uninstall.before_uninstall"
# after_uninstall = "neozatca.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "neozatca.utils.before_app_install"
# after_app_install: reserved for reacting to OTHER apps being installed
# (cross-app integration). Self-setup runs from after_install, not here.
# after_app_install = "neozatca.integrations.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "neozatca.utils.before_app_uninstall"
# after_app_uninstall = "neozatca.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "neozatca.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"Sales Invoice": "neozatca.overrides.sales_invoice.CustomSalesInvoice"
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Company": {
		"validate": "neozatca.zatca.phase.validate_company_phase",
	},
	"Sales Invoice": {
		"before_save": "neozatca.money_in_words.set_custom_money_in_words",
        "validate": "neozatca.events.prepayment.validate_prepayments",
		"before_cancel": "neozatca.events.sales_invoice.sales_invoice_before_cancel",
		"on_trash": "neozatca.events.sales_invoice.sales_invoice_on_trash",
        "on_submit" : "neozatca.events.sales_invoice.sales_invoice_on_submit",
	},
	"Purchase Invoice": {
		"before_save": "neozatca.money_in_words.set_custom_money_in_words",
	},
	"Sales Order": {
		"before_save": "neozatca.money_in_words.set_custom_money_in_words",
	},
	"Purchase Order": {
		"before_save": "neozatca.money_in_words.set_custom_money_in_words",
	},
	"Quotation": {
		"before_save": "neozatca.money_in_words.set_custom_money_in_words",
	},
	"Supplier Quotation": {
		"before_save": "neozatca.money_in_words.set_custom_money_in_words",
	},
	"Delivery Note": {
		"before_save": "neozatca.money_in_words.set_custom_money_in_words",
	},
	"Purchase Receipt": {
		"before_save": "neozatca.money_in_words.set_custom_money_in_words",
	},
	"Payment Entry": {
		"before_save": "neozatca.money_in_words.set_custom_money_in_words",
	},
	"Journal Entry": {
		"before_save": "neozatca.money_in_words.set_custom_money_in_words",
	},
	"Salary Slip": {
		"before_save": "neozatca.money_in_words.set_custom_money_in_words",
	},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"neozatca.zatca.health.check_certificates",
	],
}

# scheduler_events = {
# 	"all": [
# 		"neozatca.tasks.all"
# 	],
# 	"daily": [
# 		"neozatca.tasks.daily"
# 	],
# 	"hourly": [
# 		"neozatca.tasks.hourly"
# 	],
# 	"weekly": [
# 		"neozatca.tasks.weekly"
# 	],
# 	"monthly": [
# 		"neozatca.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "neozatca.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "neozatca.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
override_doctype_dashboards = {
	"Sales Order": "neozatca.overrides.sales_order_dashboard.get_data"
}

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

ignore_links_on_delete = ["NeoZatca Logs"]

# Request Events
# ----------------
# before_request = ["neozatca.utils.before_request"]
# after_request = ["neozatca.utils.after_request"]

# Job Events
# ----------
# before_job = ["neozatca.utils.before_job"]
# after_job = ["neozatca.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"neozatca.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }


website_route_rules = [{'from_route': '/zatca-onboarding/<path:app_path>', 'to_route': 'zatca-onboarding'},]

regional_overrides = {
	'Saudi Arabia': {
		'erpnext.controllers.taxes_and_totals.update_itemised_tax_data': 'neozatca.zatca.itemised_tax.update_itemised_tax_data'
	}
}


# fixtures = []

boot_session = "neozatca.startup.boot.add_neozatca_boot_info"
