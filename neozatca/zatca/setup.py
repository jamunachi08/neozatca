import binascii
import frappe
import json
import base64
from neozatca.zatca.utils import make_auth_header_for_request



# ====================================================================================================
# DEVICE ONBOARDING
# CSR + keys, compliance CSID, sample invoices, production CSID — in that order. Every stage after
# the first is gated by its own check_* flag on the setting, which is what makes a re-run resume
# rather than start over.


@frappe.whitelist()
def add_company_to_zatca(name):
    """Kept for the onboarding wizard; delegates to the one-click engine (background, resumable)."""
    from neozatca.zatca.onboarding import start_onboarding

    if frappe.db.get_value("NeoZatca Setting", name, "check_pcsid"):
        return {"queued": False, "connected": True}
    return start_onboarding(name)


# ====================================================================================================
# CERTIFICATE RENEWAL
# Re-issues the production CSID for a device that is already onboarded. Needs a fresh OTP, but skips
# CSR generation and the sample invoices.


@frappe.whitelist()
def renew_production_certificate(setting, otp, authorization=None, csr=None):
    """Kept for old clients; secrets are now read server-side."""
    from neozatca.zatca.onboarding import renew_production

    renew_production(setting, otp)


# ====================================================================================================
# REGISTRATION FROM THE ONBOARDING WIZARD
# Entered from the React wizard through zatca/api.py. saving_register_data provisions a company's
# whole device fleet — one Address, Commercial Register and NeoZatca Setting per branch — and
# onboards each one as it goes. get_registered_companies reads the fleet back to prefill the wizard.


def saving_register_data(**kwargs) :

    saving_company_data(**kwargs)
    saving_branches_data(**kwargs)
    saving_main_settings(**kwargs)


def saving_company_data(**kwargs) :

    frappe.db.set_value("Company" , kwargs.get("company") , {
        "company_name_in_arabic" : kwargs.get("company_name_in_arabic") ,
        "tax_id" : kwargs.get("tax_id")
    } , update_modified=True )


def saving_branches_data(**kwargs) :
    company = kwargs.get("company")
    tax_id = kwargs.get("tax_id")
    legal_name = kwargs.get("company_name_in_arabic")
    
    list_of_branches = json.loads(kwargs.get("commercial_register")) if isinstance(kwargs.get("commercial_register") , str) else kwargs.get("commercial_register")

    for branch in list_of_branches:
        company_address = saving_address_data(company , **branch)
        commercial_register = saving_commercial_register(company , company_address , **branch)
        neozatca_settings = saving_neozatca_payment_setting(company ,tax_id, legal_name , commercial_register , company_address , **branch)
        add_company_to_zatca(neozatca_settings)


def saving_address_data(company , **kwargs) :

    address = frappe.get_doc({
        "doctype" : "Address" ,
        "address_title" : company + " " + kwargs.get("commercial_register_name") ,
        "address_type" : "Billing" ,
        "short_address" : kwargs.get("short_address"),
        "building_no" :kwargs.get("building_no"),
        "address_line1" : kwargs.get("address_line1"),
        "address_line2": kwargs.get("address_line2") ,
        "city" : kwargs.get("city"),
        "pincode" : kwargs.get("pincode"),
        "district" : kwargs.get("district") ,

    }).insert(ignore_permissions=True , ignore_mandatory=True)

    return address.name


def saving_commercial_register(company , address , **kwargs) :

    commercial_register = frappe.get_doc({
        "doctype" : "Commercial Register" ,
        "company" : company ,
        "commercial_register_name" : kwargs.get("commercial_register_name") ,
        "commercial_register" : kwargs.get("commercial_register_number"),
        "address" : address
    }).insert(ignore_if_duplicate=True , ignore_permissions=True)

    return commercial_register.name


def saving_neozatca_payment_setting(company ,tax_id, legal_name ,commercial_register ,company_address , **kwargs) :
    
    settings = frappe.get_doc({
        "doctype" : "NeoZatca Setting" ,
        "company" : company ,
        "commercial_register" : commercial_register ,
        "organization_identifier" : tax_id,
        "organization_unit_name" : kwargs.get("commercial_register_name") ,
        "location" : kwargs.get("short_address") ,
        "organization_name" : legal_name ,
        "registration_type" : "CRN",
        "country_name" : "SA",
        "industry" : "Commercial" ,
        "address" : company_address ,
        "invoice_type" : "1100" ,
        "otp" : kwargs.get("otp"),
        "api_endpoints" : "production"
    }).insert(ignore_if_duplicate=True , ignore_permissions=True)

    return settings.name


def saving_main_settings(**kwargs) :
    frappe.db.set_single_value("Zatca Main Settings" , "phase" , kwargs.get("phase") , update_modified=True)


def get_registered_companies() :

    phase = frappe.db.get_single_value("Zatca Main Settings" , "phase")

    return frappe.db.sql(""" 
        SELECT   
            ozs.company , 
            ozs.organization_name as company_name_in_arabic, 
            ozs.organization_identifier as tax_id,
            cr.commercial_register as commercial_register_number ,
            cr.commercial_register_name ,
            ad.short_address ,
            ad.building_no,
            ad.address_line1,
            ad.address_line2,
            ad.city,
            ad.pincode, 
            ad.district ,
            ozs.otp,
            IF(1=0 , "Not Registered" , %(phase)s ) as phase
        FROM `tabNeoZatca Setting` ozs
        LEFT JOIN `tabCommercial Register` cr 
            ON cr.name = ozs.commercial_register
        LEFT JOIN `tabAddress` ad
            ON ad.name = cr.address
        
    """,{"phase" : phase},as_dict=True)


# ====================================================================================================
# PERSISTENCE AND PROGRESS REPORTING
# Every stage reports to the same "zatca" realtime event the onboarding SPA listens on; the
# percentage is what drives its progress bar.


def saving_data_to_company( 
    name:str ,
    company_details
) -> None :
    
    frappe.db.set_value("NeoZatca Setting" , name , company_details , update_modified=True )
    frappe.db.commit()
    
    frappe.publish_realtime("zatca" , {"message" :"Data Saved Successfully", "indicator" : "green" })


def notify_completion_status(settings, company_details):
    status = {
        "message": "ZATCA Setup Completed" if company_details.get("check_pcsid") else "ZATCA Setup Partially Completed",
        "commercial_register_name": settings.commercial_register,
        "indicator": "green" if company_details.get("check_pcsid") else "red",
        "complete": True,
        "percentage": 100 if company_details.get("check_pcsid") else 50
    }
    frappe.publish_realtime("zatca", status)


def handle_zatca_error(settings, error):
    error_status = {
        "message": f"ZATCA Setup Failed: {str(error)}",
        "commercial_register_name": settings.commercial_register,
        "indicator": "red",
        "complete": True,
        "percentage": 0
    }
    frappe.publish_realtime("zatca", error_status)


def _publish_status(settings: frappe._dict, message: str, indicator: str, percentage: int) -> None:
    """Publish realtime status updates"""
    frappe.publish_realtime("zatca", {
        "message": message,
        "commercial_register_name": settings.commercial_register,
        "indicator": indicator,
        "percentage": percentage,
        "complete": percentage == 100
    })


def _handle_cert_error(settings: frappe._dict, error: Exception, stage: str) -> None:
    """Handle certificate generation errors"""
    error_msg = frappe._("Failed during {0}: {1}").format(stage, str(error))
    frappe.log_error(title="ZATCA Certificate Error", message=error_msg)
    _publish_status(settings, error_msg, "red", 0)


# ====================================================================================================
# CERTIFICATE PAYLOAD DECODING
# Both CSID responses arrive as a base64 binary security token: the certificate is its decoded body,
# and the same token pairs with the secret to form the Basic auth header for later calls.


def _decode_certificate(b64_string: str) -> str:
    """Decode base64 encoded certificate string"""
    try:
        return base64.b64decode(b64_string).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as e:
        frappe.throw(frappe._("Invalid certificate format: {0}").format(str(e)))


def _create_auth_header(token: str, secret: str) -> str:
    """Generate authorization header for ZATCA API"""
    return make_auth_header_for_request(token, secret)
