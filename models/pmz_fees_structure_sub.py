from odoo import models, fields, api

class PmzFeesStructureSub(models.Model):
    _name = 'pmz.fees.structure.sub'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Fees Structure'
    _order = 'name'

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    name = fields.Char(string='Name', required=True)
    is_main = fields.Boolean(string='Is Main Fees Assignment?', default=False)
    is_monthly_billed = fields.Boolean(
        string='Is Monthly Billed?',
        default=False,
        help='If checked, this Fees Structure can be billed once per month within the same billing period.',
    )

    def action_share_across_companies(self):
        for rec in self:
            rec.company_id = False

    def action_restrict_to_company(self):
        for rec in self:
            rec.company_id = self.env.company.id

    @api.depends('name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name
