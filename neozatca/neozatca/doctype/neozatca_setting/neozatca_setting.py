# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt

import frappe
import json
from frappe import _
from frappe.model.document import Document
from neozatca.zatca.classes.validate import validate_tax_id_in_saudia_arabia

class NeoZatcaSetting(Document):

	def validate(self) :
		validate_tax_id_in_saudia_arabia(self.organization_identifier)
		from neozatca.zatca.branches import validate_device_vat

		validate_device_vat(self)

	@property
	def status(self) :
		return "Connected" if self.check_pcsid == 1 else "Not Connected"
