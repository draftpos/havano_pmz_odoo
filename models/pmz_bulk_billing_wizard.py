from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class PmzBulkBillingWizard(models.Model):
    _name = 'pmz.bulk.billing.wizard'
    _description = 'PMZ Billing Wizard'
    _order = 'id desc'

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    name = fields.Char(default="Billing")

    billing_mode = fields.Selection([
        ('fees_structure', 'By Fees Assignment'),
        ('fee_product', 'By Fee Item')
    ], string='Billing Mode', default='fees_structure', required=True)

    selection_type = fields.Selection([
        ('all', 'All Members'),
        ('grading', 'By Grading'),
        ('individual', 'Individual Members'),
    ], string='Billing Type', required=True, default='all')

    grading = fields.Selection([
        ('associate', 'ASSOCIATE MEMBER'),
        ('student', 'STUDENT MEMBER'),
        ('retiree', 'RETIREE'),
        ('fellow', 'FELLOW'),
        ('full', 'FULL MEMBER'),
        ('professional', 'PROFESSIONAL MEMBER')
    ], string='Member Grading')

    member_ids = fields.Many2many(
        'pmz.member',
        string="Selected Members",
    )

    date = fields.Date(
        string='Billing Date',
        default=fields.Date.context_today,
    )

    billing_year = fields.Char(
        string='Year',
        default=lambda self: str(fields.Date.today().year),
    )

    member_count = fields.Integer(
        string='Number of Members',
        compute='_compute_member_count',
    )

    invoice_count = fields.Integer(
        string="Invoice Count",
        compute="_compute_invoice_count"
    )

    is_generated = fields.Boolean(
        string='Is Generated',
        default=False,
    )

    is_processing = fields.Boolean(
        string='Is Processing',
        default=False,
    )

    # Fees Assignment Fields
    fees_structure_id = fields.Many2one(
        'pmz.fees.structure',
        string='Fees Assignment',
        domain="[('active', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )

    fees_structure_line_ids = fields.Many2many(
        'pmz.fees.structure.line',
        string='Fees Items',
        domain="[('structure_id', '=', fees_structure_id)]",
    )

    # Manual Fee Fields
    product_id = fields.Many2one('product.product', string='Item')
    sub_fees_category_id = fields.Many2one('pmz.fees.structure.sub', string='Fees Structure')
    amount = fields.Float(string='Fee Amount', default=0.0)
    description = fields.Text(string='Fee Description')

    @api.onchange('fees_structure_id')
    def _onchange_fees_structure_id(self):
        if self.fees_structure_id:
            self.fees_structure_line_ids = [(6, 0, self.fees_structure_id.line_ids.ids)]
        else:
            self.fees_structure_line_ids = [(5, 0, 0)]

    @api.onchange('selection_type', 'grading')
    def _onchange_members(self):
        domain = [('company_id', '=', self.company_id.id), ('membership_status', '=', 'active')]
        if self.selection_type == 'grading' and self.grading:
            domain.append(('prof_grading', '=', self.grading))
            members = self.env['pmz.member'].search(domain)
            self.member_ids = [(6, 0, members.ids)]
        elif self.selection_type == 'all':
            members = self.env['pmz.member'].search(domain)
            self.member_ids = [(6, 0, members.ids)]
        elif self.selection_type == 'individual':
            pass

    @api.depends('member_ids')
    def _compute_member_count(self):
        for rec in self:
            rec.member_count = len(rec.member_ids)

    @api.depends('is_generated', 'member_ids')
    def _compute_invoice_count(self):
        for wizard in self:
            if not wizard.is_generated:
                wizard.invoice_count = 0
                continue
            partner_ids = wizard.member_ids.mapped('partner_id').ids
            if not partner_ids:
                wizard.invoice_count = 0
                continue
            domain = [
                ('move_type', '=', 'out_invoice'),
                ('partner_id', 'in', partner_ids),
                ('invoice_date', '=', wizard.date),
                ('state', '!=', 'cancel'),
            ]
            wizard.invoice_count = self.env['account.move'].search_count(domain)

    def action_view_invoices(self):
        self.ensure_one()
        partner_ids = self.member_ids.mapped('partner_id').ids
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('partner_id', 'in', partner_ids),
            ('invoice_date', '=', self.date),
            ('state', '!=', 'cancel'),
        ]
        return {
            'name': _('Generated Invoices'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {'create': False},
        }

    def action_generate_invoices(self):
        self.ensure_one()
        members = self.member_ids
        if not members:
            raise UserError(_('No members selected to bill.'))

        # Ensure all members have partner_ids
        for m in members:
            if not m.partner_id:
                m._sync_partner()

        invoices_to_create = []

        if self.billing_mode == 'fees_structure':
            if not self.fees_structure_line_ids:
                raise UserError(_('Please configure lines in the Fees Assignment.'))

            invoice_line_vals_template = []
            for line in self.fees_structure_line_ids:
                invoice_line_vals_template.append({
                    'product_id': line.product_id.id,
                    'name': line.product_id.name or line.description or 'PMZ Membership Fee',
                    'quantity': line.qty,
                    'price_unit': line.rate,
                })

            for member in members:
                inv_vals = {
                    'partner_id': member.partner_id.id,
                    'move_type': 'out_invoice',
                    'invoice_date': self.date,
                    'ref': f"PMZ Billing - {self.fees_structure_id.name} ({self.billing_year})",
                    'invoice_line_ids': [(0, 0, vals.copy()) for vals in invoice_line_vals_template],
                    'company_id': self.company_id.id,
                }
                invoices_to_create.append(inv_vals)

        else:
            if not self.product_id or self.amount <= 0:
                raise UserError(_('Please select an item and valid amount.'))

            for member in members:
                inv_vals = {
                    'partner_id': member.partner_id.id,
                    'move_type': 'out_invoice',
                    'invoice_date': self.date,
                    'ref': f"PMZ Billing - {self.description or self.product_id.name} ({self.billing_year})",
                    'invoice_line_ids': [(0, 0, {
                        'product_id': self.product_id.id,
                        'name': self.description or self.product_id.name or 'PMZ Fee',
                        'quantity': 1.0,
                        'price_unit': self.amount,
                    })],
                    'company_id': self.company_id.id,
                }
                invoices_to_create.append(inv_vals)

        created_invoices = self.env['account.move'].create(invoices_to_create)
        for inv in created_invoices:
            try:
                inv.action_post()
            except Exception as e:
                _logger.warning("Could not auto-post invoice %s: %s", inv.name, e)

        self.write({
            'is_generated': True,
            'is_processing': False,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Billing Complete'),
                'message': _('Successfully generated %s invoices!') % len(created_invoices),
                'sticky': False,
                'type': 'success',
            }
        }

    def action_cancel_billing(self):
        self.ensure_one()
        partner_ids = self.member_ids.mapped('partner_id').ids
        invoices = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('partner_id', 'in', partner_ids),
            ('invoice_date', '=', self.date),
            ('state', '!=', 'cancel'),
        ])
        for inv in invoices:
            inv.button_cancel()
        self.write({'is_generated': False})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Billing Cancelled'),
                'message': _('All invoices for this billing run have been cancelled.'),
                'sticky': False,
                'type': 'warning',
            }
        }
