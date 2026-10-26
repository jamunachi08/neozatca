# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt
"""Detect fields left behind by other apps that make Frappe refuse any customization.

When a Link/Table field points to a DocType that no longer exists (typically an app was
uninstalled or a child DocType deleted, but its Custom Field stayed), Frappe re-validates the
whole DocType every time anyone adds a field or property setter to it and aborts with
"Options must be a valid DocType for field ...". NeoZatca's installer works around such
fields, and these helpers report — and, if asked, clean up — the safe cases.

    bench --site SITE execute neozatca.setup.site_health.report
    bench --site SITE execute neozatca.setup.site_health.remove_orphan_table_fields --kwargs "{'confirm': True}"
"""

import frappe
from click import secho

LINK_TYPES = ("Link", "Table", "Table MultiSelect")


def find_broken_link_fields(doctypes=None) -> list[dict]:
	"""Fields whose Link/Table target DocType does not exist, on the given (or all customised) DocTypes."""
	if doctypes is None:
		doctypes = sorted(set(frappe.get_all("Custom Field", pluck="dt")) | set(frappe.get_all("Property Setter", pluck="doc_type")))
	existing = set(frappe.get_all("DocType", pluck="name"))
	broken = []
	for dt in doctypes:
		if dt not in existing:
			continue
		frappe.clear_cache(doctype=dt)
		for df in frappe.get_meta(dt).fields:
			if df.fieldtype not in LINK_TYPES or not df.options or df.options in ("[Select]", dt):
				continue
			if df.options not in existing:
				cf = frappe.db.get_value("Custom Field", {"dt": dt, "fieldname": df.fieldname}, ["name", "module"], as_dict=True)
				broken.append({
					"doctype": dt, "fieldname": df.fieldname, "label": df.label, "fieldtype": df.fieldtype,
					"options": df.options, "custom_field": cf.name if cf else None, "module": cf.module if cf else None,
				})
	return broken


def report(doctypes=None) -> list[dict]:
	broken = find_broken_link_fields(doctypes)
	if not broken:
		secho("No broken Link/Table fields found.", fg="green")
		return broken
	secho(f"{len(broken)} field(s) point to a DocType that does not exist:", fg="yellow")
	for b in broken:
		where = f"Custom Field '{b['custom_field']}'" + (f" (module {b['module']})" if b["module"] else "") if b["custom_field"] else "standard field"
		secho(f"  {b['doctype']}.{b['fieldname']} [{b['fieldtype']} → {b['options']}] label '{b['label']}' — {where}", fg="yellow")
	secho("Fix: reinstall the app that owns them, or remove orphan Table fields with "
		"neozatca.setup.site_health.remove_orphan_table_fields (confirm=True).", fg="cyan")
	return broken


def remove_orphan_table_fields(confirm: bool = False) -> list[str]:
	"""Delete orphan *Table* custom fields only.

	A Table field has no column on the parent; its rows lived in the child table that no longer
	exists, so removing the field loses nothing. Orphan *Link* fields hold values in a real
	column and are only reported, never deleted.
	"""
	targets = [b for b in find_broken_link_fields() if b["custom_field"] and b["fieldtype"] in ("Table", "Table MultiSelect")]
	names = [b["custom_field"] for b in targets]
	if not confirm:
		secho(f"Would delete: {', '.join(names) or 'nothing'}. Re-run with confirm=True.", fg="cyan")
		return names
	for name in names:
		frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)
		secho(f"  deleted Custom Field {name}", fg="green")
	frappe.db.commit()
	return names
