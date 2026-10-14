from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class PmzExamEntry(models.Model):
    _name = 'pmz.exam.entry'
    _description = 'PMZ Examination Entry Form'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Reference',
        default=lambda self: _('New'),
        copy=False,
        readonly=True,
        tracking=True
    )

    exam_type = fields.Selection([
        ('cpm_dpm', 'CPM & DPM (Certificate & Diploma in Project Management)'),
        ('cme', 'CM&E (Certificate in Project Monitoring & Evaluation)'),
        ('pgdpm', 'PGDPM (Post Graduate Diploma in Project Management)'),
    ], string='Exam Qualification', required=True, default='cpm_dpm', tracking=True)

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id'
    )

    member_id = fields.Many2one(
        'pmz.member',
        string='Linked Member',
        tracking=True,
        help='Optionally link to an existing PMZ member profile to auto-fill candidate details.'
    )

    # --- 1. & 2. & 3. Candidate Profile Details ---
    title = fields.Selection([
        ('Mr', 'Mr'),
        ('Mrs', 'Mrs'),
        ('Miss', 'Miss'),
        ('Dr', 'Dr'),
        ('Prof', 'Prof'),
        ('Other', 'Other'),
    ], string='Mr/Mrs/Miss', default='Mr')

    surname = fields.Char(string='1. Surname', required=True, tracking=True)
    forenames = fields.Char(string='2. Forenames', required=True, tracking=True)
    dob = fields.Date(string='Date of Birth')
    id_no = fields.Char(string='3. I.D number', tracking=True)

    # --- 4. Address & Contacts ---
    address = fields.Text(string='4. Address')
    telephone_home = fields.Char(string='Telephone: Home')
    telephone_business = fields.Char(string='Business')
    telephone_mobile = fields.Char(string='Mobile', required=True)
    email = fields.Char(string='Email', required=True)

    # --- 5., 6., 7. Membership, Session & College ---
    student_membership_no = fields.Char(string='5. PMZ Student Membership No:', tracking=True)
    exam_session = fields.Char(string='6. Examination Session:', default='November 2026', tracking=True)
    college_name = fields.Char(string='7. Name of College where you received tuition:', tracking=True)
    college_date_stamp = fields.Char(string='College Date Stamp / Notes')
    college_stamp_date = fields.Date(string='College Stamp Date')
    college_stamp_received = fields.Boolean(string='College Date Stamp Verified', default=False, tracking=True)
    college_stamp_image = fields.Binary(string='College Stamp Image / Scan', attachment=True)

    # --- 8. & 9. CPM Modules (Part 1) ---
    cpm_ipm01 = fields.Boolean(string='[IPM01] Introduction to Project Management')
    cpm_pp02 = fields.Boolean(string='[PP02] Project Planning')
    cpm_pipml03 = fields.Boolean(string='[PIPML03] Project Implementation')
    cpm_pme04 = fields.Boolean(string='[PM&E04] Project Monitoring and Evaluation')
    cpm_module_count = fields.Integer(string='9. Number of CPM modules being attempted:', compute='_compute_module_counts', store=True)

    # --- 10. & 11. DPM Modules (Part 2) ---
    dpm_pims05 = fields.Boolean(string='[PIMS05] Project Management Information Systems')
    dpm_ppcm06 = fields.Boolean(string='[PPCM06] Project Procurement & Contracts Management')
    dpm_prm07 = fields.Boolean(string='[PRM07] Project Risk Management')
    dpm_pcm08 = fields.Boolean(string='[PCM08] Project Cost Management')
    dpm_ptm09 = fields.Boolean(string='[PTM09] Project Time Management')
    dpm_module_count = fields.Integer(string='11. Number of DPM modules being attempted:', compute='_compute_module_counts', store=True)

    # --- CM&E Modules (Part 1) ---
    cme_ipm01 = fields.Boolean(string='[IPM01] Introduction to Project Management')
    cme_pme02 = fields.Boolean(string='[PME02] Principles of Project Monitoring and Evaluation')
    cme_qlet03 = fields.Boolean(string='[QLET03] Qualitative Evaluation Techniques')
    cme_qtet04 = fields.Boolean(string='[QTET04] Quantitative Evaluation Techniques')
    cme_module_count = fields.Integer(string='CM&E Modules Attempted', compute='_compute_module_counts', store=True)

    # --- PGDPM Modules (Semesters 1 & 2) ---
    pgdpm_pdp01 = fields.Boolean(string='[PDP01] Personal Development Planning')
    pgdpm_pppm02 = fields.Boolean(string='[PPPM02] Principles and Practices in Project Management')
    pgdpm_pimpl03 = fields.Boolean(string='[PIMPL03] Project Planning and Implementation')
    pgdpm_pme04 = fields.Boolean(string='[P M&E04] Project Monitoring and Evaluation')
    pgdpm_sem1_count = fields.Integer(string='Semester 1 Modules Attempted', compute='_compute_module_counts', store=True)
    pgdpm_sem1_sitting = fields.Selection([
        ('first', 'First Sitting'),
        ('rewrite', 'Re-write'),
    ], string='Semester 1 Sitting Type', default='first')

    pgdpm_pmis05 = fields.Boolean(string='[PMIS05] Project Management Information Systems')
    pgdpm_plcm06 = fields.Boolean(string='[PLCM06] Project Leadership and Change Management')
    pgdpm_prm07 = fields.Boolean(string='[PRM07] Project Risk Management')
    pgdpm_pvcm08 = fields.Boolean(string='[PVCM08] Project Valuation and Cost Management')
    pgdpm_ptm09 = fields.Boolean(string='[PTM09] Project Time Management')
    pgdpm_sem2_count = fields.Integer(string='Semester 2 Modules Attempted', compute='_compute_module_counts', store=True)
    pgdpm_sem2_sitting = fields.Selection([
        ('first', 'First Sitting'),
        ('rewrite', 'Re-write'),
    ], string='Semester 2 Sitting Type', default='first')

    total_modules_attempted = fields.Integer(
        string='Total Modules Attempted',
        compute='_compute_module_counts',
        store=True
    )

    # --- Fees & Rates (read from Settings > PMZ Fees Assignments) ---
    fee_per_cpm_module = fields.Float(string='Fee per CPM Module', compute='_compute_fee_rates')
    fee_per_dpm_module = fields.Float(string='Fee per DPM Module', compute='_compute_fee_rates')
    rtgs_fee_per_cpm_module = fields.Float(string='Fee per CPM Module (RTGS)', default=250.0)
    rtgs_fee_per_dpm_module = fields.Float(string='Fee per DPM Module (RTGS)', default=300.0)
    fee_per_cme_module = fields.Float(string='Fee per CM&E Module', compute='_compute_fee_rates')
    fee_per_pgdpm_module = fields.Float(string='Fee per PGDPM Module', compute='_compute_fee_rates')

    # --- Billing & Payment ---
    invoice_id = fields.Many2one('account.move', string='Exam Invoice', readonly=True, copy=False)
    is_paid = fields.Boolean(string='Is Paid', tracking=True)
    pay_amount = fields.Float(string='Amount Paid')
    journal_id = fields.Many2one('account.journal', string='Account Paid To', domain="[('type', 'in', ('bank', 'cash'))]")
    proof_of_payment = fields.Binary(string='Proof of Payment', attachment=True)
    proof_of_payment_filename = fields.Char()

    total_exam_fee = fields.Monetary(
        string='Total Exam Fee Due (USD)',
        compute='_compute_total_fee',
        currency_field='currency_id',
        store=True,
        tracking=True
    )
    rtgs_total_exam_fee = fields.Float(
        string='Total Exam Fee Due (RTGS$)',
        compute='_compute_total_fee',
        store=True,
        tracking=True
    )

    # --- Declaration Section ---
    declaration_agreed = fields.Boolean(
        string='Candidate Declaration Agreed',
        default=True,
        help='Candidate declares they have adequately prepared and understood PMZ rules and regulations.'
    )
    declaration_statement = fields.Text(
        string='Declaration Text',
        readonly=True,
        default='I hereby declare that I have adequately prepared for the examination and will not hold the institute liable for any inabilities to sit for the examination caused by myself after registration, I submit that I have read and understood PMZ rules and regulations in the prospectus.'
    )
    candidate_signature = fields.Char(string='Signature (Candidate)', tracking=True)
    declaration_date = fields.Date(string='Date (Declaration)', default=fields.Date.context_today)

    # --- FOR OFFICIAL USE ONLY ---
    amount_received = fields.Monetary(
        string='Amount received:',
        currency_field='currency_id',
        tracking=True
    )
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('cheque', 'Cheque'),
        ('rtgs', 'RTGS'),
        ('ecocash', 'EcoCash'),
        ('swipe', 'Swipe / POS'),
    ], string='Cash/Cheque/RTGS', default='cash', tracking=True)

    receipt_no = fields.Char(string='Receipt No:', tracking=True)
    session_booked = fields.Char(string='Exam Session Booked for:')
    official_name = fields.Char(string='Official Name:', default=lambda self: self.env.user.name)
    official_signature = fields.Char(string='Signature (Official)')
    official_date = fields.Date(string='Date (Official Use)', default=fields.Date.context_today)
    notes = fields.Text(string='Internal Notes')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('verified', 'Fee Verified'),
        ('approved', 'Registered / Approved'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    @api.onchange('member_id')
    def _onchange_member_id(self):
        if self.member_id:
            m = self.member_id
            self.surname = m.last_name or ''
            self.forenames = f"{m.first_name or ''} {m.middle_name or ''}".strip()
            self.id_no = m.prof_id_no or ''
            self.dob = m.birth_date or False
            self.address = m.prof_residential_address or m.prof_postal_address or ''
            self.telephone_mobile = m.phone or m.prof_telephone or ''
            self.telephone_business = m.prof_telephone or ''
            self.email = m.email or ''
            self.student_membership_no = m.prof_id_no or ''
            self.candidate_signature = m.name or ''
            title_map = {'MR': 'Mr', 'MRS': 'Mrs', 'MS': 'Miss', 'DR': 'Dr', 'PROF': 'Prof'}
            self.title = title_map.get(m.prof_title, 'Other') if m.prof_title else self.title

    @api.depends('company_id')
    def _compute_fee_rates(self):
        for rec in self:
            company = rec.company_id or self.env.company
            rec.fee_per_cpm_module = company._pmz_fee_assignment('cpm').total_amount
            rec.fee_per_dpm_module = company._pmz_fee_assignment('dpm').total_amount
            rec.fee_per_cme_module = company._pmz_fee_assignment('cme').total_amount
            rec.fee_per_pgdpm_module = company._pmz_fee_assignment('pgdpm').total_amount

    def _pmz_exam_billing_parts(self):
        """[(fee_key, module_count)] for this exam type."""
        self.ensure_one()
        if self.exam_type == 'cpm_dpm':
            return [('cpm', self.cpm_module_count), ('dpm', self.dpm_module_count)]
        if self.exam_type == 'cme':
            return [('cme', self.cme_module_count)]
        if self.exam_type == 'pgdpm':
            return [('pgdpm', self.pgdpm_sem1_count + self.pgdpm_sem2_count)]
        return []

    def _pmz_partner(self):
        self.ensure_one()
        if self.member_id:
            if not self.member_id.partner_id:
                self.member_id._sync_partner()
            return self.member_id.partner_id
        Partner = self.env['res.partner'].sudo()
        return Partner.search([('email', '=ilike', (self.email or '').strip())], limit=1) or Partner.create({
            'name': f"{self.forenames} {self.surname}".strip(), 'email': self.email, 'phone': self.telephone_mobile})

    def _get_selected_modules(self):
        """Return list of (code, title, fee_key) for every selected module."""
        self.ensure_one()
        selected = []
        # CPM Modules
        cpm_modules = [
            ('cpm_ipm01', 'IPM01', 'Introduction to Project Management', 'cpm'),
            ('cpm_pp02', 'PP02', 'Project Planning', 'cpm'),
            ('cpm_pipml03', 'PIPML03', 'Project Implementation', 'cpm'),
            ('cpm_pme04', 'PM&E04', 'Project Monitoring and Evaluation', 'cpm'),
        ]
        # DPM Modules
        dpm_modules = [
            ('dpm_pims05', 'PIMS05', 'Project Management Information Systems', 'dpm'),
            ('dpm_ppcm06', 'PPCM06', 'Project Procurement & Contracts Management', 'dpm'),
            ('dpm_prm07', 'PRM07', 'Project Risk Management', 'dpm'),
            ('dpm_pcm08', 'PCM08', 'Project Cost Management', 'dpm'),
            ('dpm_ptm09', 'PTM09', 'Project Time Management', 'dpm'),
        ]
        # CM&E Modules
        cme_modules = [
            ('cme_ipm01', 'IPM01', 'Introduction to Project Management', 'cme'),
            ('cme_pme02', 'PME02', 'Principles of Project Monitoring and Evaluation', 'cme'),
            ('cme_qlet03', 'QLET03', 'Qualitative Evaluation Techniques', 'cme'),
            ('cme_qtet04', 'QTET04', 'Quantitative Evaluation Techniques', 'cme'),
        ]
        # PGDPM Modules
        pgdpm_modules = [
            ('pgdpm_pdp01', 'PDP01', 'Personal Development Planning', 'pgdpm'),
            ('pgdpm_pppm02', 'PPPM02', 'Principles and Practices in Project Management', 'pgdpm'),
            ('pgdpm_pimpl03', 'PIMPL03', 'Project Planning and Implementation', 'pgdpm'),
            ('pgdpm_pme04', 'P M&E04', 'Project Monitoring and Evaluation', 'pgdpm'),
            ('pgdpm_pmis05', 'PMIS05', 'Project Management Information Systems', 'pgdpm'),
            ('pgdpm_plcm06', 'PLCM06', 'Project Leadership and Change Management', 'pgdpm'),
            ('pgdpm_prm07', 'PRM07', 'Project Risk Management', 'pgdpm'),
            ('pgdpm_pvcm08', 'PVCM08', 'Project Valuation and Cost Management', 'pgdpm'),
            ('pgdpm_ptm09', 'PTM09', 'Project Time Management', 'pgdpm'),
        ]

        if self.exam_type == 'cpm_dpm':
            for fname, code, title, fee_key in cpm_modules + dpm_modules:
                if getattr(self, fname):
                    selected.append((code, title, fee_key))
        elif self.exam_type == 'cme':
            for fname, code, title, fee_key in cme_modules:
                if getattr(self, fname):
                    selected.append((code, title, fee_key))
        elif self.exam_type == 'pgdpm':
            for fname, code, title, fee_key in pgdpm_modules:
                if getattr(self, fname):
                    selected.append((code, title, fee_key))
        return selected

    def action_bill_exam(self):
        for rec in self:
            if rec.invoice_id and rec.invoice_id.state != 'cancel':
                continue
            company = rec.company_id or self.env.company
            modules = rec._get_selected_modules()
            lines = []
            if modules:
                for code, title, fee_key in modules:
                    struct = company._pmz_fee_assignment(fee_key)
                    # Use the configured fee assignment lines per module
                    for struct_line in struct.line_ids:
                        lines.append((0, 0, {
                            'product_id': struct_line.product_id.id,
                            'name': f"[{code}] {title} ({fee_key.upper()} Exam Fee)",
                            'quantity': struct_line.qty or 1.0,
                            'price_unit': struct_line.rate,
                        }))
            else:
                for key, count in rec._pmz_exam_billing_parts():
                    lines += company._pmz_invoice_lines(company._pmz_fee_assignment(key), count, key.upper())

            inv = company._pmz_create_invoice(rec._pmz_partner(), lines, _('PMZ Exam Entry - %s') % rec.name)
            rec.invoice_id = inv.id

    def action_register_payment(self):
        for rec in self:
            if not rec.is_paid:
                continue
            if not rec.invoice_id:
                rec.action_bill_exam()
            (rec.company_id or self.env.company)._pmz_pay_invoice(
                rec.invoice_id, rec.journal_id, rec.pay_amount, _('Exam payment %s') % rec.name)
            rec.amount_received = rec.pay_amount
            rec.receipt_no = rec.receipt_no or rec.invoice_id.name

    @api.onchange('is_paid')
    def _onchange_is_paid(self):
        if self.is_paid:
            self.pay_amount = self.pay_amount or self.invoice_id.amount_residual or self.total_exam_fee
            company = self.company_id or self.env.company
            self.journal_id = self.journal_id or company.pmz_payment_journal_id or self.env['account.journal'].search(
                [('type', 'in', ('bank', 'cash')), ('company_id', '=', company.id)], limit=1)

    @api.depends(
        'cpm_ipm01', 'cpm_pp02', 'cpm_pipml03', 'cpm_pme04',
        'dpm_pims05', 'dpm_ppcm06', 'dpm_prm07', 'dpm_pcm08', 'dpm_ptm09',
        'cme_ipm01', 'cme_pme02', 'cme_qlet03', 'cme_qtet04',
        'pgdpm_pdp01', 'pgdpm_pppm02', 'pgdpm_pimpl03', 'pgdpm_pme04',
        'pgdpm_pmis05', 'pgdpm_plcm06', 'pgdpm_prm07', 'pgdpm_pvcm08', 'pgdpm_ptm09',
        'exam_type'
    )
    def _compute_module_counts(self):
        for rec in self:
            cpm = sum([1 for m in [rec.cpm_ipm01, rec.cpm_pp02, rec.cpm_pipml03, rec.cpm_pme04] if m])
            dpm = sum([1 for m in [rec.dpm_pims05, rec.dpm_ppcm06, rec.dpm_prm07, rec.dpm_pcm08, rec.dpm_ptm09] if m])
            cme = sum([1 for m in [rec.cme_ipm01, rec.cme_pme02, rec.cme_qlet03, rec.cme_qtet04] if m])
            sem1 = sum([1 for m in [rec.pgdpm_pdp01, rec.pgdpm_pppm02, rec.pgdpm_pimpl03, rec.pgdpm_pme04] if m])
            sem2 = sum([1 for m in [rec.pgdpm_pmis05, rec.pgdpm_plcm06, rec.pgdpm_prm07, rec.pgdpm_pvcm08, rec.pgdpm_ptm09] if m])

            rec.cpm_module_count = cpm
            rec.dpm_module_count = dpm
            rec.cme_module_count = cme
            rec.pgdpm_sem1_count = sem1
            rec.pgdpm_sem2_count = sem2

            if rec.exam_type == 'cpm_dpm':
                rec.total_modules_attempted = cpm + dpm
            elif rec.exam_type == 'cme':
                rec.total_modules_attempted = cme
            elif rec.exam_type == 'pgdpm':
                rec.total_modules_attempted = sem1 + sem2
            else:
                rec.total_modules_attempted = 0

    @api.depends(
        'exam_type', 'cpm_module_count', 'dpm_module_count', 'cme_module_count',
        'pgdpm_sem1_count', 'pgdpm_sem2_count',
        'rtgs_fee_per_cpm_module', 'rtgs_fee_per_dpm_module'
    )
    def _compute_total_fee(self):
        for rec in self:
            company = rec.company_id or self.env.company
            rec.total_exam_fee = sum(company._pmz_fee_assignment(k).total_amount * c
                                     for k, c in rec._pmz_exam_billing_parts())
            if rec.exam_type == 'cpm_dpm':
                rtgs = rec.cpm_module_count * rec.rtgs_fee_per_cpm_module + rec.dpm_module_count * rec.rtgs_fee_per_dpm_module
            else:
                rtgs = rec.total_modules_attempted * rec.rtgs_fee_per_cpm_module
            rec.rtgs_total_exam_fee = rtgs

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                exam_t = vals.get('exam_type', 'cpm_dpm')
                if exam_t == 'pgdpm':
                    prefix = 'EXAM-PGDPM-'
                elif exam_t == 'cme':
                    prefix = 'EXAM-CME-'
                else:
                    prefix = 'EXAM-CPM-'

                seq = self.env['ir.sequence'].next_by_code('pmz.exam.entry')
                if not seq:
                    seq = self.env['ir.sequence'].sudo().create({
                        'name': 'PMZ Exam Entry Sequence',
                        'code': 'pmz.exam.entry',
                        'prefix': prefix + '%(year)s/',
                        'padding': 4,
                        'company_id': False,
                    }).next_by_id()
                vals['name'] = seq or _('New')
        return super().create(vals_list)

    # --- Workflow Buttons ---
    def action_submit(self):
        for rec in self:
            if rec.total_modules_attempted <= 0:
                raise ValidationError(_('Please select at least one examination module to sit for.'))
            rec.write({'state': 'submitted'})
            rec.action_bill_exam()
            if rec.is_paid:
                rec.action_register_payment()

    def action_verify(self):
        for rec in self:
            rec.write({'state': 'verified'})

    def action_approve(self):
        for rec in self:
            rec.write({'state': 'approved'})

    def action_cancel(self):
        for rec in self:
            rec.write({'state': 'cancelled'})

    def action_draft(self):
        for rec in self:
            rec.write({'state': 'draft'})

    def action_print_form(self):
        """Triggers the printable Examination Entry Form report."""
        return self.env.ref('havano_pmz_odoo.action_report_pmz_exam_entry').report_action(self)
