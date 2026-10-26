# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ZatcaMainSettings(Document):
	
	def before_save(self) :

		if self.has_value_changed("phase") :
			from neozatca.zatca.phase import warn_site_phase_change

			warn_site_phase_change(self)
			frappe.clear_cache()
