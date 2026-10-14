from odoo import models, fields, api

class PmzMember(models.Model):
    _name = 'pmz.member'
    _description = 'PMZ Professional Member'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    first_name = fields.Char(string='First Name', required=True)
    middle_name = fields.Char(string='Middle Name')
    last_name = fields.Char(string='Last Name', required=True)
    image_1920 = fields.Binary(string='Image')

    partner_id = fields.Many2one('res.partner', string='Related Partner', delegate=False, ondelete='restrict')

    prof_title = fields.Selection([
        ('PROF', 'PROF'),
        ('DR', 'DR'),
        ('MR', 'MR'),
        ('MRS', 'MRS'),
        ('MS', 'MS'),
        ('Other', 'Other')
    ], string='Title')
    gender = fields.Selection([
        ('m', 'Male'),
        ('f', 'Female'),
        ('o', 'Other')
    ], string='Gender')
    birth_date = fields.Date(string='Date of Birth')
    prof_id_no = fields.Char(string='I.D No.')
    prof_telephone = fields.Char(string='Telephone Number (Cell)')
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')

    prof_company_name_address = fields.Text(string='Company Name & Address')
    prof_present_position = fields.Char(string='Present Position')
    prof_highest_prof_qualifications = fields.Char(string='Highest Prof. Qualifications')

    prof_grading = fields.Selection([
        ('associate', 'ASSOCIATE MEMBER'),
        ('student', 'STUDENT MEMBER'),
        ('retiree', 'RETIREE'),
        ('fellow', 'FELLOW'),
        ('full', 'FULL MEMBER'),
        ('professional', 'PROFESSIONAL MEMBER')
    ], string='Grading')

    session = fields.Selection([
        ('first', 'First Session'),
        ('second', 'Second Session'),
    ], string='Session', default='first', tracking=True, help='Indicates whether the member is in the first session or second session.')

    prof_industry_affiliation = fields.Selection([
        ('Government', 'Government'),
        ('Finance/Insurance/Banking', 'Finance/Insurance/Banking'),
        ('Engineering/Consultation', 'Engineering/Consultation'),
        ('Architecture/Building', 'Architecture/Building'),
        ('Other', 'Other'),
        ('Business Mgt Services', 'Business Mgt Services'),
        ('Computers/Software/DP', 'Computers/Software/DP'),
        ('Education/Training', 'Education/Training'),
        ('Utility/Service Provider', 'Utility/Service Provider'),
        ('Health/Social', 'Health/Social'),
        ('Property Dvpt', 'Property Dvpt'),
        ('Mining Industry', 'Mining Industry'),
        ('Chemical Industry', 'Chemical Industry'),
        ('Pharmaceutical', 'Pharmaceutical'),
        ('Consulting', 'Consulting'),
        ('Manufacturing', 'Manufacturing'),
        ('Communication', 'Communication')
    ], string='Industry Affiliation')

    prof_job_function = fields.Selection([
        ('Business Development', 'Business Development'),
        ('Comm Mgmt', 'Comm Mgmt'),
        ('Consulting', 'Consulting'),
        ('Contract/Proc Mgmt', 'Contract/Proc Mgmt'),
        ('Legal', 'Legal'),
        ('Cost Mgmt', 'Cost Mgmt'),
        ('Distribution', 'Distribution'),
        ('Marketing/PR/Sales', 'Marketing/PR/Sales'),
        ('Production', 'Production'),
        ('Civil Engineering', 'Civil Engineering'),
        ('Electrical', 'Electrical'),
        ('Electronics', 'Electronics'),
        ('Environmental', 'Environmental'),
        ('Financial Services', 'Financial Services'),
        ('HR Mgmt', 'HR Mgmt'),
        ('Manufacturing', 'Manufacturing'),
        ('Infor Computer Mgmt', 'Infor Computer Mgmt')
    ], string='Job Function')

    prof_residential_address = fields.Text(string='Residential Address')
    prof_postal_address = fields.Text(string='Preferred Postal Address')
    prof_chapter = fields.Char(string='Chapter')
    prof_pmp = fields.Selection([('yes', 'YES'), ('no', 'NO')], string='PMP')
    prof_year = fields.Char(string='Year')

    membership_status = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('expired', 'Expired'),
    ], string='Status', default='active', tracking=True)

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency', related='company_id.currency_id')

    # Financial / Follow-up fields
    outstanding_balance = fields.Monetary(
        string='Balance',
        compute='_compute_outstanding_balance',
        currency_field='currency_id',
        store=False,
    )
    activity_date_deadline = fields.Date(string='Due Date')
    activity_note = fields.Html(string='Activity Log Note')

    @api.depends('first_name', 'middle_name', 'last_name')
    def _compute_name(self):
        for rec in self:
            parts = [rec.first_name, rec.middle_name, rec.last_name]
            rec.name = " ".join([p for p in parts if p])

    def _compute_outstanding_balance(self):
        for rec in self:
            if not rec.partner_id:
                rec.outstanding_balance = 0.0
                continue
            # Query posted invoices in not_paid / partial
            invoices = self.env['account.move'].search([
                ('partner_id', '=', rec.partner_id.id),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ('not_paid', 'partial')),
            ])
            rec.outstanding_balance = sum(invoices.mapped('amount_residual'))

    def _sync_partner(self):
        for rec in self:
            vals = {
                'name': rec.name,
                'email': rec.email,
                'phone': rec.phone or rec.prof_telephone,
                'is_company': False,
                'street': rec.prof_residential_address,
                'company_id': rec.company_id.id,
            }
            if not rec.partner_id:
                partner = self.env['res.partner'].create(vals)
                rec.partner_id = partner.id
            else:
                rec.partner_id.write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.partner_id:
                rec._sync_partner()
            # Auto-bill new member according to grading tier (from Settings)
            if rec.prof_grading and not self.env.context.get('skip_auto_bill'):
                from .pmz_settings import GRADING_TIER
                company = rec.company_id or self.env.company
                structure = company._pmz_fee_assignment(GRADING_TIER.get(rec.prof_grading, 'standard'))
                product_ids = structure.line_ids.mapped('product_id').ids
                existing_inv = self.env['account.move'].sudo().search([
                    ('partner_id', '=', rec.partner_id.id),
                    ('move_type', '=', 'out_invoice'),
                    ('state', '!=', 'cancel'),
                    ('invoice_line_ids.product_id', 'in', product_ids),
                ], limit=1)
                if not existing_inv:
                    lines = company._pmz_invoice_lines(structure, 1.0, rec.name)
                    company._pmz_create_invoice(rec.partner_id, lines, 'PMZ Membership Fee - %s' % rec.name)
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(f in vals for f in ['first_name', 'middle_name', 'last_name', 'email', 'phone', 'prof_telephone', 'prof_residential_address']):
            for rec in self:
                rec._sync_partner()
        return res
