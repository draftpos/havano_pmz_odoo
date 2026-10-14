from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

# Default seed values used ONLY the first time a fee assignment is missing.
# After that, everything is read from Settings / Fees Assignments (editable).
PMZ_FEE_DEFAULTS = {
    'standard': ('Membership Application Fee - Associate/Student/Retiree/Fellow', 25.0),
    'professional': ('Membership Application Fee - Full/Professional', 100.0),
    'cpm': ('CPM Exam Fee (per module)', 25.0),
    'dpm': ('DPM Exam Fee (per module)', 30.0),
    'cme': ('CM&E Exam Fee (per module)', 25.0),
    'pgdpm': ('PGDPM Exam Fee (per module)', 40.0),
}

GRADING_TIER = {
    'associate': 'standard',
    'student': 'standard',
    'retiree': 'standard',
    'fellow': 'standard',
    'full': 'professional',
    'professional': 'professional',
}


class ResCompany(models.Model):
    _inherit = 'res.company'

    pmz_fee_standard_id = fields.Many2one('pmz.fees.structure', string='Standard Membership Fees Assignment')
    pmz_fee_professional_id = fields.Many2one('pmz.fees.structure', string='Full/Professional Membership Fees Assignment')
    pmz_fee_cpm_id = fields.Many2one('pmz.fees.structure', string='CPM Exam Fees Assignment (per module)')
    pmz_fee_dpm_id = fields.Many2one('pmz.fees.structure', string='DPM Exam Fees Assignment (per module)')
    pmz_fee_cme_id = fields.Many2one('pmz.fees.structure', string='CM&E Exam Fees Assignment (per module)')
    pmz_fee_pgdpm_id = fields.Many2one('pmz.fees.structure', string='PGDPM Exam Fees Assignment (per module)')
    pmz_payment_journal_id = fields.Many2one(
        'account.journal', string='Default Payment Account',
        domain="[('type', 'in', ('bank', 'cash'))]")

    def _pmz_fee_assignment(self, key):
        """Return the fees assignment configured in Settings for `key`.
        If none is configured yet, auto-create item, fees structure and
        fees assignment from the seed defaults and store it in Settings."""
        self.ensure_one()
        field_name = 'pmz_fee_%s_id' % key
        structure = self.sudo()[field_name]
        if structure:
            return structure

        name, amount = PMZ_FEE_DEFAULTS[key]
        Product = self.env['product.product'].sudo()
        product = Product.search([('name', '=', name)], limit=1) or Product.create({
            'name': name, 'type': 'service', 'list_price': amount,
        })
        Sub = self.env['pmz.fees.structure.sub'].sudo()
        sub = Sub.search([('name', '=', name)], limit=1) or Sub.create({
            'name': name, 'is_main': True, 'company_id': self.id,
        })
        Struct = self.env['pmz.fees.structure'].sudo()
        structure = Struct.search([('category_id', '=', sub.id)], limit=1) or Struct.create({
            'category_id': sub.id,
            'company_id': self.id,
            'description': _('Auto-generated. Add or edit items freely; billing uses all lines.'),
            'line_ids': [(0, 0, {
                'product_id': product.id,
                'sub_fees_category_id': sub.id,
                'qty': 1.0,
                'rate': amount,
                'description': name,
            })],
        })
        self.sudo()[field_name] = structure.id
        return structure

    def _pmz_invoice_lines(self, structure, multiplier=1.0, label=''):
        """Build invoice lines from ALL lines of a fees assignment."""
        lines = []
        if multiplier <= 0:
            return lines
        for line in structure.line_ids:
            lines.append((0, 0, {
                'product_id': line.product_id.id,
                'name': (label + ' - ' if label else '') + (line.description or line.product_id.name or structure.name),
                'quantity': (line.qty or 1.0) * multiplier,
                'price_unit': line.rate,
            }))
        return lines

    def _pmz_create_invoice(self, partner, lines, ref):
        if not lines:
            return self.env['account.move']
        inv = self.env['account.move'].sudo().create({
            'partner_id': partner.id,
            'move_type': 'out_invoice',
            'invoice_date': fields.Date.context_today(self),
            'ref': ref,
            'company_id': self.id,
            'invoice_line_ids': lines,
        })
        inv.action_post()
        return inv

    def _pmz_pay_invoice(self, invoice, journal, amount, memo=''):
        if not invoice or invoice.state != 'posted' or invoice.payment_state not in ('not_paid', 'partial'):
            return
        if not journal:
            raise ValidationError(_("Please select 'Account Paid To'."))
        if amount <= 0:
            raise ValidationError(_("'Amount Paid' must be greater than 0."))
        self.env['account.payment.register'].sudo().with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({
            'journal_id': journal.id,
            'amount': min(amount, invoice.amount_residual),
            'payment_date': fields.Date.context_today(self),
            'communication': memo or invoice.name,
        })._create_payments()


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pmz_fee_standard_id = fields.Many2one(related='company_id.pmz_fee_standard_id', readonly=False)
    pmz_fee_professional_id = fields.Many2one(related='company_id.pmz_fee_professional_id', readonly=False)
    pmz_fee_cpm_id = fields.Many2one(related='company_id.pmz_fee_cpm_id', readonly=False)
    pmz_fee_dpm_id = fields.Many2one(related='company_id.pmz_fee_dpm_id', readonly=False)
    pmz_fee_cme_id = fields.Many2one(related='company_id.pmz_fee_cme_id', readonly=False)
    pmz_fee_pgdpm_id = fields.Many2one(related='company_id.pmz_fee_pgdpm_id', readonly=False)
    pmz_payment_journal_id = fields.Many2one(related='company_id.pmz_payment_journal_id', readonly=False)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        company = self.env.company
        # Ensure default items, fees structures and fee assignments are generated and populated by default
        for key in PMZ_FEE_DEFAULTS:
            struct = company._pmz_fee_assignment(key)
            field_name = 'pmz_fee_%s_id' % key
            if field_name in fields_list or not fields_list:
                res[field_name] = struct.id
        if 'pmz_payment_journal_id' in fields_list or not fields_list:
            if not company.pmz_payment_journal_id:
                journal = self.env['account.journal'].search(
                    [('type', 'in', ('bank', 'cash')), ('company_id', '=', company.id)], limit=1)
                if journal:
                    company.sudo().pmz_payment_journal_id = journal.id
                    res['pmz_payment_journal_id'] = journal.id
        return res

    def action_pmz_generate_default_fees(self):
        company = self.env.company
        for key in PMZ_FEE_DEFAULTS:
            company._pmz_fee_assignment(key)
        return {'type': 'ir.actions.client', 'tag': 'reload'}
