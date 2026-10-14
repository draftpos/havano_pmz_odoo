from odoo import models, fields, api

class PmzFeesStructure(models.Model):
    _name = 'pmz.fees.structure'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Fees Assignment'
    _order = 'name'

    category_id = fields.Many2one(
        'pmz.fees.structure.sub',
        string='Fees Assignment Name',
        domain=[('is_main', '=', True)],
        required=True,
    )
    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
    )

    @api.depends('category_id', 'category_id.name')
    def _compute_name(self):
        for rec in self:
            rec.name = rec.category_id.name if rec.category_id else ''

    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)

    is_monthly_billed = fields.Boolean(
        string='Is Monthly Billed?',
        default=False,
        help='If checked, this Fees Assignment can be billed once per month.',
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )

    def action_share_across_companies(self):
        for rec in self:
            rec.company_id = False

    def action_restrict_to_company(self):
        for rec in self:
            rec.company_id = self.env.company.id

    line_ids = fields.One2many(
        'pmz.fees.structure.line',
        'structure_id',
        string='Fees Items',
    )

    item_count = fields.Integer(
        string='Number of Items',
        compute='_compute_item_count',
    )

    total_amount = fields.Float(
        string='Total Amount',
        compute='_compute_total_amount',
        store=True,
    )

    @api.depends('line_ids.total')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped('total'))

    @api.depends('line_ids')
    def _compute_item_count(self):
        for record in self:
            record.item_count = len(record.line_ids)


class PmzFeesStructureLine(models.Model):
    _name = 'pmz.fees.structure.line'
    _description = 'Fees Assignment Line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    structure_id = fields.Many2one(
        'pmz.fees.structure',
        string='Fees Assignment',
        required=True,
        ondelete='cascade',
    )

    sequence = fields.Integer(string='Sequence', default=10)

    sub_fees_category_id = fields.Many2one(
        'pmz.fees.structure.sub',
        string='Fees Structure',
        required=False,
    )

    product_id = fields.Many2one(
        'product.product',
        string='Item',
        required=True,
    )

    item_id = fields.Char(string='Item ID', size=50)
    price_list_name = fields.Char(string='Price List Name', size=100, default='Selling')
    description = fields.Text(string='Description')

    qty = fields.Float(string='Qty', default=1.0)
    rate = fields.Float(string='Unit Price', required=True)
    total = fields.Float(string='Total', compute='_compute_total', store=True)

    @api.depends('qty', 'rate')
    def _compute_total(self):
        for record in self:
            record.total = record.qty * record.rate

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='structure_id.company_id',
        store=True,
    )

    _sql_constraints = [
        ('unique_product_structure',
         'unique(product_id, structure_id)',
         'Item must be unique per Fees Assignment!'),
    ]

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.rate = self.product_id.list_price
            self.item_id = str(self.product_id.id)
            self.price_list_name = 'Selling'
            if not self.sub_fees_category_id and self.structure_id and self.structure_id.category_id:
                self.sub_fees_category_id = self.structure_id.category_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('sub_fees_category_id') and vals.get('structure_id'):
                struct = self.env['pmz.fees.structure'].browse(vals['structure_id'])
                if struct and struct.category_id:
                    vals['sub_fees_category_id'] = struct.category_id.id
        return super().create(vals_list)
