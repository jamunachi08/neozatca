// NeoZatca desk scripts, built by `bench build` into a content-hashed file
// (/assets/neozatca/dist/js/neozatca.bundle.<hash>.js) so browsers and the CDN pick up every
// deploy immediately. Order matters: prepayment defines constants used by pos_payments.
import "./sales_invoice/prepayment.js";
import "./sales_invoice/pos_payments.js";
import "./sales_invoice/zatca_buttons.js";
import "./neozatca_onboarding.js";
import "./sales_invoice/zatca_environment.js";
