from odoo import models, fields, api, _

class HavanoProfessionalAdmission(models.Model):
    _name = 'havano.professional.admission'
    _description = 'Professional Membership Application'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Application Reference', default='New', readonly=True, copy=False)
    surname = fields.Char(string='Surname', required=True)
    first_name = fields.Char(string='First Name', required=True)
    middle_name = fields.Char(string='Middle Name')
    dob = fields.Date(string='D.O.B')
    title = fields.Selection([
        ('PROF', 'PROF'),
        ('DR', 'DR'),
        ('MR', 'MR'),
        ('MRS', 'MRS'),
        ('MS', 'MS'),
        ('Other', 'Other')
    ], string='Title')
    pmp = fields.Selection([('yes', 'YES'), ('no', 'NO')], string='PMP')
    year = fields.Char(string='Year')
    highest_prof_qualifications = fields.Char(string='Highest Prof. Qualifications')
    company_name_address = fields.Text(string='Company Name & Address')
    present_position = fields.Char(string='Present Position')
    telephone = fields.Char(string='Telephone Number (Cell)')
    id_no = fields.Char(string='I.D No.')
    residential_address = fields.Text(string='Residential Address')
    chapter = fields.Char(string='Chapter')
    email = fields.Char(string='Email Addresses')
    postal_address = fields.Text(string='Preferred Postal Address')
    
    industry_affiliation = fields.Selection([
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

    job_function = fields.Selection([
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

    grading = fields.Selection([
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

    application_fee = fields.Float(string='Application Fee', compute='_compute_application_fee', store=True)

    # Proof of payment upload (optional)
    proof_of_payment = fields.Binary(string='Proof of Payment', attachment=True)
    proof_of_payment_filename = fields.Char(string='Proof of Payment Filename')

    # Payment status and management
    is_paid = fields.Boolean(string='Is Paid', default=False, tracking=True)
    amount_paid = fields.Float(string='Amount Paid')
    journal_id = fields.Many2one('account.journal', string='Account Paid To', domain="[('type', 'in', ('bank', 'cash'))]")
    invoice_id = fields.Many2one('account.move', string='Application Invoice', readonly=True, copy=False)
    payment_id = fields.Many2one('pmz.member.payment', string='Member Payment', readonly=True, copy=False)
    member_id = fields.Many2one('pmz.member', string='Created Member', readonly=True, copy=False)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('waiting_list', 'Waiting List'),
        ('approved', 'Approved'),
        ('rejected', 'Disapproved')
    ], string='Status', default='draft', tracking=True)

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    def _pmz_fee_structure(self):
        self.ensure_one()
        from .pmz_settings import GRADING_TIER
        company = self.company_id or self.env.company
        return company._pmz_fee_assignment(GRADING_TIER.get(self.grading, 'standard'))

    @api.depends('grading', 'company_id')
    def _compute_application_fee(self):
        for rec in self:
            rec.application_fee = rec._pmz_fee_structure().total_amount if rec.grading else 0.0

    @api.onchange('is_paid')
    def _onchange_is_paid(self):
        if self.is_paid:
            if not self.amount_paid:
                self.amount_paid = self.invoice_id.amount_residual or self.application_fee
            if not self.journal_id:
                company = self.company_id or self.env.company
                self.journal_id = company.pmz_payment_journal_id or self.env['account.journal'].search([
                    ('type', 'in', ('bank', 'cash')), ('company_id', '=', company.id)], limit=1)
        else:
            self.amount_paid = 0.0

    def _auto_bill_application(self, partner):
        """Creates and posts the application fee invoice from the Settings fees assignment."""
        self.ensure_one()
        company = self.company_id or self.env.company
        structure = self._pmz_fee_structure()
        lines = company._pmz_invoice_lines(structure, 1.0, _('Application %s') % self.name)
        invoice = company._pmz_create_invoice(partner, lines, _('PMZ Application Fee - %s') % self.name)
        self.invoice_id = invoice.id
        return invoice

    def action_register_auto_payment(self):
        """Registers payment against the application invoice."""
        for rec in self:
            if not rec.is_paid:
                continue
            if not rec.invoice_id:
                partner = self.env['res.partner'].sudo().search([('email', '=ilike', (rec.email or '').strip())], limit=1) \
                    or self.env['res.partner'].sudo().create({
                        'name': f"{rec.first_name} {rec.surname}".strip(),
                        'email': rec.email, 'phone': rec.telephone})
                rec._auto_bill_application(partner)
            (rec.company_id or self.env.company)._pmz_pay_invoice(
                rec.invoice_id, rec.journal_id, rec.amount_paid, _('Payment for %s') % rec.name)


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('havano.professional.admission') or 'New'
        records = super(HavanoProfessionalAdmission, self).create(vals_list)

        for rec in records:
            # Auto-bill immediately upon application creation
            partner_name = f"{rec.first_name} {rec.surname}".strip()
            partner = self.env['res.partner'].sudo().search([('email', '=ilike', (rec.email or '').strip())], limit=1)
            if not partner:
                partner = self.env['res.partner'].sudo().create({
                    'name': partner_name,
                    'email': rec.email,
                    'phone': rec.telephone,
                    'street': rec.residential_address or rec.postal_address,
                    'company_id': rec.company_id.id or self.env.company.id,
                })
            rec._auto_bill_application(partner)

            # If created from backend with is_paid checked, trigger auto payment
            if rec.is_paid:
                rec.action_register_auto_payment()

            # Send email notification with payment amount details
            rec._send_application_email()

        return records

    def write(self, vals):
        res = super(HavanoProfessionalAdmission, self).write(vals)
        for rec in self:
            if vals.get('is_paid') or ('journal_id' in vals and rec.is_paid) or ('amount_paid' in vals and rec.is_paid):
                if rec.is_paid and rec.journal_id and rec.amount_paid > 0:
                    rec.action_register_auto_payment()
        return res

    def _send_application_email(self):
        """Sends email notification informing applicant of registration and fee required."""
        for rec in self:
            if not rec.email:
                continue
            fee = rec.application_fee or (100.0 if rec.grading in ('full', 'professional') else 25.0)
            inv_name = rec.invoice_id.name if rec.invoice_id else 'Pending'
            subject = f"PMZ Membership Application Received - Ref: {rec.name}"
            body_html = f"""
                <p>Dear {rec.first_name} {rec.surname},</p>
                <p>Thank you for submitting your membership application to <strong>Project Management Zimbabwe (PMZ)</strong>.</p>
                <p><strong>Application Reference:</strong> {rec.name}<br/>
                <strong>Membership Grading Selected:</strong> {dict(rec._fields['grading'].selection).get(rec.grading, rec.grading)}<br/>
                <strong>Application Fee Due:</strong> <span style="color: #004080; font-size: 16px; font-weight: bold;">${fee:.2f} USD</span><br/>
                <strong>Invoice Reference:</strong> {inv_name}</p>
                <p>Please note that your application is being processed and you are required to pay the application fee of <strong>${fee:.2f} USD</strong> before tracking or admission confirmation.</p>
                <p>If you have already paid or attached proof of payment, our finance team will verify and confirm your account promptly.</p>
                <br/>
                <p>Best regards,<br/><strong>Project Management Zimbabwe Admissions Office</strong></p>
            """
            try:
                mail_vals = {
                    'subject': subject,
                    'body_html': body_html,
                    'email_to': rec.email,
                    'email_from': self.company_id.email or self.env.company.email or 'admin@pmz.org.zw',
                }
                self.env['mail.mail'].sudo().create(mail_vals).send()
            except Exception:
                pass

    def action_approve(self):
        self.state = 'approved'
        for rec in self:
            member = self.env['pmz.member'].create({
                'first_name': rec.first_name,
                'middle_name': rec.middle_name,
                'last_name': rec.surname,
                'prof_title': rec.title,
                'birth_date': rec.dob,
                'email': rec.email,
                'phone': rec.telephone,
                'prof_telephone': rec.telephone,
                'company_id': rec.company_id.id if rec.company_id else self.env.company.id,
                'prof_grading': rec.grading,
                'prof_industry_affiliation': rec.industry_affiliation,
                'prof_job_function': rec.job_function,
                'prof_highest_prof_qualifications': rec.highest_prof_qualifications,
                'prof_company_name_address': rec.company_name_address,
                'prof_present_position': rec.present_position,
                'prof_id_no': rec.id_no,
                'prof_residential_address': rec.residential_address,
                'prof_chapter': rec.chapter,
                'prof_postal_address': rec.postal_address,
                'prof_pmp': rec.pmp,
                'prof_year': rec.year,
                'session': rec.session or 'first',
                'membership_status': 'active',
            })
            rec.member_id = member.id

    def action_reject(self):
        self.state = 'rejected'

    def action_waitlist(self):
        self.state = 'waiting_list'
