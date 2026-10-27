import frappe
from click import secho
from neozatca.zatca.setup import saving_commercial_register
from neozatca.zatca.utils import extract_details_from_certificate , make_auth_header_for_request


def execute() :
    """ Handle Old Customer """
    print("Patches Runing")
    all_companies = get_all_companies()

    for company in all_companies :

        if not frappe.get_meta("Company").has_field("api_endpoints") :
            return 

        try :
            if company.api_endpoints != "production"  :
                return 

            commercial_register = create_commercial_register(company)
            create_neozatca_settings(company , commercial_register)
            handle_neozatca_logs(company , commercial_register)

            secho("Settings Created for Company => {} and commercial Register => {}".format(company.name , commercial_register) , fg="green")
        
        except Exception as e:
            secho("Error in Company => {}".format(company.name) , fg="red")
            print(e)



def get_all_companies() -> list[frappe._dict] :
    company = frappe.db.get_all("Company" , fields=["*"])
    return company


def create_commercial_register(company: frappe._dict) :
    
    commercial_register = saving_commercial_register( 
        company.name , company.registered_address ,
        commercial_register_name = company.organization_unit,
        commercial_register_number = company.get("commercial_register") or company.get("custom_commercial_register")
    )

    return commercial_register


def create_neozatca_settings(company , commercial_register):
    company_settings = {}
    neozatca_setting = frappe.new_doc("NeoZatca Setting")

    neozatca_setting.company = company.name
    neozatca_setting.commercial_register = commercial_register
    neozatca_setting.address = company.registered_address
    neozatca_setting.phases = 'Phase 2'

    neozatca_setting.organization_identifier = company.tax_id
    neozatca_setting.organization_unit_name = company.organization_unit
    neozatca_setting.organization_name = company.custom_organization_name
    neozatca_setting.common_name = company.common_name
    neozatca_setting.egs_serial_number = company.sn
    neozatca_setting.registration_type = "CRN"
    neozatca_setting.country_name = "SA"
    neozatca_setting.industry = company.business_category
    neozatca_setting.invoice_type = company.title

    neozatca_setting.otp = company.otp
    neozatca_setting.api_endpoints = company.api_endpoints
    neozatca_setting.check_csr = 1
    neozatca_setting.check_csid = 1
    neozatca_setting.check_pcsid = 1
    neozatca_setting.invoice_one = 1
    neozatca_setting.invoice_two = 1
    neozatca_setting.invoice_three = 1
    neozatca_setting.invoice_four = 1
    neozatca_setting.invoice_five = 1
    neozatca_setting.invoice_six = 1
    neozatca_setting.private_key = company.pk 
    neozatca_setting.csr = company.csr
    neozatca_setting.request_id = company.csid 
    neozatca_setting.binary_security_token = company.binary_security_token
    neozatca_setting.certificate = company.certificate
    neozatca_setting.token_type = company.token_type
    neozatca_setting.secret = company.secret
    neozatca_setting.authorization = make_auth_header_for_request(company.binary_security_token , company.secret) 

    extract_details_from_certificate(company.certificate , company_settings)
    neozatca_setting.update(company_settings)

    neozatca_setting.save(ignore_permissions=True)


def handle_neozatca_logs(company ,commercial_register):

    zatca_logs = frappe.get_all("Zatca Logs", {"company" : company}, fields=["*"], order_by="creation desc") 

    for log in zatca_logs :
        neozatca_logs = frappe.new_doc("NeoZatca Logs")
        neozatca_logs.commercial_register = commercial_register
        neozatca_logs.environment = "production"
        neozatca_logs.api_endpoint = "complainace_checks" if log.endpoint == "complainace_checks" else "clearance"
        neozatca_logs.qr_code_generated = log.qr_code
        neozatca_logs.update(log)
        neozatca_logs.insert(ignore_permissions=True)

    frappe.db.commit()