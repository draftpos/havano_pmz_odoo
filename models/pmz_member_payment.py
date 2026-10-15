from odoo import models, fields, api, _
from odoo.exceptions import UserError

class PmzMemberPayment(models.Model):
    _name = 'pmz.member.payment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Member Payment'
    _order = 'date desc, id desc'

    name = fields.Char(string='Reference', default=lambda self: _('New'), copy=False, readonly=False)
    member_id = fields.Many2one('pmz.member', string='Member', required=True)
    grading = fields.Selection(related='member_id.prof_grading', string='Grading', store=True)

    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    journal_id = fields.Many2one('account.journal', string='Account Paid To', required=True, domain="[('type', 'in', ('bank', 'cash'))]")
    currency_id = fields.Many2one('res.currency', string='Currency', compute='_compute_currency', store=True, readonly=False)
    exchange_rate = fields.Float(string='Exchange Rate', default=1.0)

    total_balance = fields.Monetary(string='Total Balance', compute='_compute_total_balance', currency_field='currency_id')
    allocated_amount = fields.Monetary(string='Allocated Amount', currency_field='currency_id')

    line_ids = fields.One2many('pmz.member.payment.line', 'payment_id', string='Outstanding Invoices')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', readonly=True, copy=False)

    @api.depends('journal_id', 'company_id')
    def _compute_currency(self):
        for record in self:
            if record.journal_id and record.journal_id.currency_id:
                record.currency_id = record.journal_id.currency_id
            elif record.company_id:
                record.currency_id = record.company_id.currency_id

    @api.onchange('member_id')
    def _onchange_member_id(self):
        self.line_ids = [(5, 0, 0)]
        if not self.member_id or not self.member_id.partner_id:
            return

        domain = [
            ('partner_id', '=', self.member_id.partner_id.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial')),
            ('company_id', '=', self.company_id.id),
        ]
        invoices = self.env['account.move'].search(domain, order='invoice_date asc, id asc')
        lines = []
        for invoice in invoices:
            lines.append((0, 0, {
                'move_id': invoice.id,
                'amount_allocated': 0.0,
            }))
        self.line_ids = lines

    @api.onchange('allocated_amount', 'exchange_rate')
    def _onchange_allocated_amount(self):
        if not self.exchange_rate:
            self.exchange_rate = 1.0

        if self.allocated_amount > 0:
            remaining = self.allocated_amount
            for line in self.line_ids:
                if remaining >= line.amount_residual:
                    line.amount_allocated = line.amount_residual
                    remaining -= line.amount_residual
                elif remaining > 0:
                    line.amount_allocated = remaining
                    remaining = 0
                else:
                    line.amount_allocated = 0
        else:
            for line in self.line_ids:
                line.amount_allocated = 0.0

    @api.depends('line_ids.amount_residual', 'line_ids.amount_allocated')
    def _compute_total_balance(self):
        for record in self:
            record.total_balance = sum(record.line_ids.mapped('amount_residual'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                seq = self.env['ir.sequence'].next_by_code('pmz.member.payment')
                if not seq:
                    seq = self.env['ir.sequence'].sudo().create({
                        'name': 'PMZ Member Payment',
                        'code': 'pmz.member.payment',
                        'prefix': 'PAY/%(year)s/',
                        'padding': 5,
                        'company_id': self.env.company.id,
                    }).next_by_id()
                vals['name'] = seq or _('New')
        return super().create(vals_list)

    def action_post(self):
        for payment in self:
            if payment.state != 'draft':
                continue
            if payment.allocated_amount <= 0:
                raise UserError(_('Allocated amount must be greater than zero.'))

            # Register standard payment or reconcile invoice lines
            partner = payment.member_id.partner_id
            for line in payment.line_ids.filtered(lambda l: l.amount_allocated > 0 and l.move_id):
                invoice = line.move_id
                # Register payment against invoice
                pay_wizard = self.env['account.payment.register'].with_context(
                    active_model='account.move',
                    active_ids=invoice.ids
                ).create({
                    'journal_id': payment.journal_id.id,
                    'amount': line.amount_allocated,
                    'payment_date': payment.date,
                    'communication': payment.name,
                })
                pay_wizard._create_payments()

            payment.write({'state': 'posted'})

    def action_cancel(self):
        for payment in self:
            payment.write({'state': 'cancelled'})


class PmzMemberPaymentLine(models.Model):
    _name = 'pmz.member.payment.line'
    _description = 'Member Payment Line'

    payment_id = fields.Many2one('pmz.member.payment', string='Payment', ondelete='cascade')
    move_id = fields.Many2one('account.move', string='Invoice', domain="[('move_type', '=', 'out_invoice')]")
    company_id = fields.Many2one('res.company', related='payment_id.company_id', store=True)
    currency_id = fields.Many2one('res.currency', related='move_id.currency_id')

    name = fields.Char(string='Invoice Number', related='move_id.name')
    invoice_date = fields.Date(string='Invoice Date', related='move_id.invoice_date')
    amount_residual = fields.Monetary(string='Amount Due', related='move_id.amount_residual', currency_field='currency_id')
    amount_allocated = fields.Monetary(string='Allocated Amount', currency_field='currency_id')
