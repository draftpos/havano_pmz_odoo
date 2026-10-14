from odoo import models, fields, api, _
import datetime

class PmzDashboard(models.TransientModel):
    _name = 'pmz.dashboard'
    _description = 'PMZ Cockpit Dashboard'

    name = fields.Char(string='Name', default='PMZ Cockpit Dashboard')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency', related='company_id.currency_id')

    # --- Financial & Payments KPIs ---
    total_payments_amount = fields.Monetary(string='Total Payments', compute='_compute_stats', currency_field='currency_id')
    total_payments_count = fields.Integer(string='Payment Count', compute='_compute_stats')
    monthly_payments_amount = fields.Monetary(string="This Month's Collections", compute='_compute_stats', currency_field='currency_id')
    total_invoiced_amount = fields.Monetary(string='Total Invoiced', compute='_compute_stats', currency_field='currency_id')
    total_invoiced_count = fields.Integer(string='Invoice Count', compute='_compute_stats')
    total_outstanding_amount = fields.Monetary(string='Total Receivables', compute='_compute_stats', currency_field='currency_id')
    total_debtors_count = fields.Integer(string='Debtors Count', compute='_compute_stats')

    # --- Membership & Applications KPIs ---
    total_members = fields.Integer(string='Total Members', compute='_compute_stats')
    active_members = fields.Integer(string='Active Members', compute='_compute_stats')
    inactive_members = fields.Integer(string='Inactive Members', compute='_compute_stats')
    total_applications = fields.Integer(string='Applications', compute='_compute_stats')
    pending_applications = fields.Integer(string='Pending Applications', compute='_compute_stats')
    approved_applications = fields.Integer(string='Approved Applications', compute='_compute_stats')
    waiting_applications = fields.Integer(string='Waiting List', compute='_compute_stats')
    rejected_applications = fields.Integer(string='Disapproved Applications', compute='_compute_stats')

    # --- Operations & Catalog KPIs ---
    total_billing_items = fields.Integer(string='Billing Items', compute='_compute_stats')
    total_billing_runs = fields.Integer(string='Billing Runs', compute='_compute_stats')
    total_fees_assignments = fields.Integer(string='Fees Assignments', compute='_compute_stats')
    total_exam_entries = fields.Integer(string='Exam Entries', compute='_compute_stats')

    # --- Interactive Charts & Visuals (HTML/SVG) ---
    revenue_chart_html = fields.Html(string='Revenue Trend Chart', compute='_compute_stats', sanitize=False)
    grading_chart_html = fields.Html(string='Grading Distribution Chart', compute='_compute_stats', sanitize=False)
    admissions_pipeline_html = fields.Html(string='Admissions Pipeline', compute='_compute_stats', sanitize=False)
    recent_payments_html = fields.Html(string='Recent Payments', compute='_compute_stats', sanitize=False)
    recent_applications_html = fields.Html(string='Recent Applications', compute='_compute_stats', sanitize=False)

    def _compute_stats(self):
        today = fields.Date.context_today(self)
        first_day_month = today.replace(day=1)

        for rec in self:
            company = rec.company_id or self.env.company
            symbol = company.currency_id.symbol or '$'

            # 1. Payments Data
            all_payments = self.env['pmz.member.payment'].search([('company_id', '=', company.id)])
            posted_payments = all_payments.filtered(lambda p: p.state == 'posted')
            rec.total_payments_amount = sum(posted_payments.mapped('allocated_amount'))
            rec.total_payments_count = len(posted_payments)

            month_payments = posted_payments.filtered(lambda p: p.date and p.date >= first_day_month)
            rec.monthly_payments_amount = sum(month_payments.mapped('allocated_amount'))

            # 2. Invoices & Receivables
            all_invoices = self.env['account.move'].search([
                ('company_id', '=', company.id),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
            ])
            rec.total_invoiced_amount = sum(all_invoices.mapped('amount_total'))
            rec.total_invoiced_count = len(all_invoices)

            unpaid_invoices = all_invoices.filtered(lambda m: m.payment_state in ('not_paid', 'partial'))
            rec.total_outstanding_amount = sum(unpaid_invoices.mapped('amount_residual'))

            # 3. Members Data
            all_members = self.env['pmz.member'].search([('company_id', '=', company.id)])
            rec.total_members = len(all_members)
            rec.active_members = len(all_members.filtered(lambda m: m.membership_status == 'active'))
            rec.inactive_members = len(all_members.filtered(lambda m: m.membership_status != 'active'))
            rec.total_debtors_count = len(all_members.filtered(lambda m: m.outstanding_balance > 0))

            # 4. Applications Data
            all_apps = self.env['havano.professional.admission'].search([])
            rec.total_applications = len(all_apps)
            rec.pending_applications = len(all_apps.filtered(lambda a: a.state == 'submitted'))
            rec.approved_applications = len(all_apps.filtered(lambda a: a.state == 'approved'))
            rec.waiting_applications = len(all_apps.filtered(lambda a: a.state == 'waiting_list'))
            rec.rejected_applications = len(all_apps.filtered(lambda a: a.state == 'rejected'))

            # 5. Catalog & Billing Operations
            rec.total_billing_items = self.env['product.template'].search_count([])
            rec.total_billing_runs = self.env['pmz.bulk.billing.wizard'].search_count([('company_id', '=', company.id)])
            rec.total_fees_assignments = self.env['pmz.fees.structure'].search_count(['|', ('company_id', '=', False), ('company_id', '=', company.id)])
            rec.total_exam_entries = self.env['pmz.exam.entry'].search_count([('company_id', '=', company.id)])

            # 6. Generate Charts & Visual HTML
            rec.revenue_chart_html = rec._build_revenue_chart(all_invoices, posted_payments, today, symbol)
            rec.grading_chart_html = rec._build_grading_chart(all_members)
            rec.admissions_pipeline_html = rec._build_admissions_pipeline(all_apps)
            rec.recent_payments_html = rec._build_recent_payments_table(posted_payments, symbol)
            rec.recent_applications_html = rec._build_recent_applications_table(all_apps)

    def _build_revenue_chart(self, invoices, payments, today, symbol):
        """Generates a responsive SVG bar chart comparing Invoiced vs Collections over 6 months."""
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        months = []
        for i in range(5, -1, -1):
            m = today.month - i
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            months.append((y, m))

        chart_data = []
        max_val = 100.0

        for y, m in months:
            m_label = f"{month_names[m - 1]} {str(y)[-2:]}"
            inv_sum = sum(
                inv.amount_total for inv in invoices
                if inv.invoice_date and inv.invoice_date.year == y and inv.invoice_date.month == m
            )
            pay_sum = sum(
                pay.allocated_amount for pay in payments
                if pay.date and pay.date.year == y and pay.date.month == m
            )
            if inv_sum > max_val:
                max_val = inv_sum
            if pay_sum > max_val:
                max_val = pay_sum
            chart_data.append((m_label, inv_sum, pay_sum))

        # SVG layout parameters
        svg_w = 640
        svg_h = 240
        chart_top = 35
        chart_bottom = 195
        avail_h = chart_bottom - chart_top
        group_w = 88
        bar_w = 26
        x_start = 55

        # Format max value for Y-axis
        grid_lines = []
        for level in [1.0, 0.66, 0.33, 0.0]:
            y_pos = int(chart_bottom - (level * avail_h))
            val = int(max_val * level)
            label = f"{symbol}{val:,.0f}" if val < 10000 else f"{symbol}{val / 1000:,.1f}k"
            grid_lines.append(
                f'<line x1="{x_start}" y1="{y_pos}" x2="{svg_w - 20}" y2="{y_pos}" stroke="#f1f5f9" stroke-width="1.5" stroke-dasharray="3,3"/>'
                f'<text x="{x_start - 8}" y="{y_pos + 4}" font-size="10" fill="#94a3b8" text-anchor="end" font-family="sans-serif">{label}</text>'
            )

        bars_svg = []
        for idx, (m_label, inv_val, pay_val) in enumerate(chart_data):
            gx = x_start + (idx * group_w) + 12
            h_inv = max(int((inv_val / max_val) * avail_h), 4) if inv_val > 0 else 3
            h_pay = max(int((pay_val / max_val) * avail_h), 4) if pay_val > 0 else 3
            y_inv = chart_bottom - h_inv
            y_pay = chart_bottom - h_pay

            inv_fill = "url(#barGradInv)" if inv_val > 0 else "#e2e8f0"
            pay_fill = "url(#barGradPay)" if pay_val > 0 else "#cbd5e1"

            bars_svg.append(f'''
                <g class="chart-group">
                    <rect x="{gx}" y="{y_inv}" width="{bar_w}" height="{h_inv}" rx="5" fill="{inv_fill}">
                        <title>Invoiced: {symbol}{inv_val:,.2f}</title>
                    </rect>
                    <rect x="{gx + bar_w + 5}" y="{y_pay}" width="{bar_w}" height="{h_pay}" rx="5" fill="{pay_fill}">
                        <title>Collected: {symbol}{pay_val:,.2f}</title>
                    </rect>
                    <text x="{gx + bar_w + 2}" y="{chart_bottom + 20}" font-size="11" font-weight="600" fill="#64748b" text-anchor="middle" font-family="sans-serif">{m_label}</text>
                </g>
            ''')

        svg = f'''
        <div style="width: 100%; overflow-x: auto;">
            <svg viewBox="0 0 {svg_w} {svg_h}" style="width: 100%; min-width: 520px; height: auto; display: block;" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="barGradInv" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="#6366f1"/>
                        <stop offset="100%" stop-color="#4f46e5"/>
                    </linearGradient>
                    <linearGradient id="barGradPay" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="#10b981"/>
                        <stop offset="100%" stop-color="#059669"/>
                    </linearGradient>
                </defs>
                {''.join(grid_lines)}
                {''.join(bars_svg)}
            </svg>
        </div>
        '''
        return svg

    def _build_grading_chart(self, members):
        """Generates an SVG Donut chart displaying member distribution across professional grades."""
        grades = [
            ('full', 'Full Member', '#3b82f6'),
            ('associate', 'Associate Member', '#10b981'),
            ('fellow', 'Fellow', '#8b5cf6'),
            ('professional', 'Professional', '#f59e0b'),
            ('student', 'Student Member', '#06b6d4'),
            ('retiree', 'Retiree', '#64748b'),
        ]

        total = len(members)
        counts = []
        for code, label, color in grades:
            c = len(members.filtered(lambda m: m.prof_grading == code))
            pct = (c / total * 100) if total > 0 else 0
            counts.append((label, c, pct, color))

        # Donut dimensions: radius 60, circumference 376.99
        radius = 60
        circ = 376.99
        donut_segments = []
        accum_pct = 0.0

        if total > 0:
            for label, count, pct, color in counts:
                if count == 0:
                    continue
                dash_len = (pct / 100.0) * circ
                offset = (accum_pct / 100.0) * circ
                donut_segments.append(
                    f'<circle cx="85" cy="85" r="{radius}" fill="none" stroke="{color}" stroke-width="22" '
                    f'stroke-dasharray="{dash_len:0.2f} {circ:0.2f}" stroke-dashoffset="-{offset:0.2f}" '
                    f'transform="rotate(-90 85 85)">'
                    f'<title>{label}: {count} ({pct:0.1f}%)</title>'
                    f'</circle>'
                )
                accum_pct += pct
        else:
            donut_segments.append(
                f'<circle cx="85" cy="85" r="{radius}" fill="none" stroke="#e2e8f0" stroke-width="22"/>'
            )

        legend_rows = []
        for label, count, pct, color in counts:
            legend_rows.append(f'''
                <div class="d-flex align-items-center justify-content-between py-1 border-bottom" style="font-size: 12px;">
                    <div class="d-flex align-items-center text-truncate pe-2">
                        <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:{color}; margin-right:8px; flex-shrink:0;"></span>
                        <span class="text-secondary fw-semibold text-truncate">{label}</span>
                    </div>
                    <div class="d-flex align-items-center gap-2">
                        <span class="fw-bold text-dark">{count}</span>
                        <span class="badge bg-light text-muted border" style="font-size:10px; min-width:38px;">{pct:0.0f}%</span>
                    </div>
                </div>
            ''')

        html = f'''
        <div class="d-flex flex-column flex-md-row align-items-center gap-3">
            <div style="flex-shrink: 0; position: relative; width: 170px; height: 170px;">
                <svg viewBox="0 0 170 170" style="width: 170px; height: 170px; display: block;" xmlns="http://www.w3.org/2000/svg">
                    {''.join(donut_segments)}
                </svg>
                <div style="position: absolute; top:0; left:0; width:100%; height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center; pointer-events:none;">
                    <span style="font-size: 24px; font-weight: 800; color: #0f172a; line-height: 1;">{total}</span>
                    <span style="font-size: 10px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px;">Members</span>
                </div>
            </div>
            <div class="flex-grow-1 w-100">
                {''.join(legend_rows)}
            </div>
        </div>
        '''
        return html

    def _build_admissions_pipeline(self, all_apps):
        """Generates a visual admissions status progress funnel."""
        total = len(all_apps)
        sub_cnt = len(all_apps.filtered(lambda a: a.state == 'submitted'))
        app_cnt = len(all_apps.filtered(lambda a: a.state == 'approved'))
        wt_cnt = len(all_apps.filtered(lambda a: a.state == 'waiting_list'))
        rej_cnt = len(all_apps.filtered(lambda a: a.state == 'rejected'))

        sub_pct = (sub_cnt / total * 100) if total > 0 else 0
        app_pct = (app_cnt / total * 100) if total > 0 else 0
        wt_pct = (wt_cnt / total * 100) if total > 0 else 0
        rej_pct = (rej_cnt / total * 100) if total > 0 else 0

        html = f'''
        <div>
            <div class="progress mb-3" style="height: 14px; border-radius: 8px; background: #e2e8f0; overflow: hidden;">
                <div class="progress-bar bg-warning" role="progressbar" style="width: {sub_pct}%;" title="Submitted: {sub_cnt}"></div>
                <div class="progress-bar bg-success" role="progressbar" style="width: {app_pct}%;" title="Approved: {app_cnt}"></div>
                <div class="progress-bar bg-info" role="progressbar" style="width: {wt_pct}%;" title="Waiting List: {wt_cnt}"></div>
                <div class="progress-bar bg-danger" role="progressbar" style="width: {rej_pct}%;" title="Disapproved: {rej_cnt}"></div>
            </div>
            <div class="row g-2 text-center" style="font-size: 12px;">
                <div class="col-6 col-md-3">
                    <div class="p-2 rounded bg-light border">
                        <span class="d-block text-warning fw-bold fs-5">{sub_cnt}</span>
                        <span class="text-muted fw-semibold">Pending Review</span>
                    </div>
                </div>
                <div class="col-6 col-md-3">
                    <div class="p-2 rounded bg-light border">
                        <span class="d-block text-success fw-bold fs-5">{app_cnt}</span>
                        <span class="text-muted fw-semibold">Approved</span>
                    </div>
                </div>
                <div class="col-6 col-md-3">
                    <div class="p-2 rounded bg-light border">
                        <span class="d-block text-info fw-bold fs-5">{wt_cnt}</span>
                        <span class="text-muted fw-semibold">Waiting List</span>
                    </div>
                </div>
                <div class="col-6 col-md-3">
                    <div class="p-2 rounded bg-light border">
                        <span class="d-block text-danger fw-bold fs-5">{rej_cnt}</span>
                        <span class="text-muted fw-semibold">Disapproved</span>
                    </div>
                </div>
            </div>
        </div>
        '''
        return html

    def _build_recent_payments_table(self, payments, symbol):
        """Generates an HTML table of recent member payments."""
        recent = payments.sorted(key=lambda p: (p.date or datetime.date.min, p.id), reverse=True)[:5]
        if not recent:
            return '''
            <div class="text-center py-4 text-muted">
                <i class="fa fa-credit-card fa-2x mb-2 opacity-50 d-block"></i>
                <span class="small">No posted member payments recorded yet.</span>
            </div>
            '''

        rows = []
        for p in recent:
            mem_name = p.member_id.name if p.member_id else 'Unknown'
            p_date = p.date.strftime('%Y-%m-%d') if p.date else '-'
            journal_name = p.journal_id.name if p.journal_id else '-'
            rows.append(f'''
                <tr>
                    <td class="fw-bold text-dark py-2">{p.name}</td>
                    <td class="text-secondary py-2">{mem_name}</td>
                    <td class="text-muted py-2">{p_date}</td>
                    <td class="text-muted py-2"><span class="badge bg-light text-dark border">{journal_name}</span></td>
                    <td class="text-end fw-bold text-success py-2">{symbol} {p.allocated_amount:,.2f}</td>
                </tr>
            ''')

        return f'''
        <div class="table-responsive">
            <table class="table table-hover align-middle mb-0" style="font-size: 13px;">
                <thead class="table-light text-muted text-uppercase" style="font-size: 11px; letter-spacing: 0.5px;">
                    <tr>
                        <th>Receipt #</th>
                        <th>Member</th>
                        <th>Date</th>
                        <th>Journal</th>
                        <th class="text-end">Amount Paid</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
        '''

    def _build_recent_applications_table(self, all_apps):
        """Generates an HTML table of recent applications awaiting review."""
        pending = all_apps.filtered(lambda a: a.state == 'submitted').sorted(key=lambda a: a.id, reverse=True)[:5]
        if not pending:
            return '''
            <div class="text-center py-4 text-muted">
                <i class="fa fa-id-card-o fa-2x mb-2 opacity-50 d-block"></i>
                <span class="small">No pending membership applications awaiting review.</span>
            </div>
            '''

        rows = []
        for a in pending:
            full_name = f"{a.first_name or ''} {a.surname or ''}".strip() or a.name
            grading = a.grading or '-'
            email = a.email or a.telephone or '-'
            rows.append(f'''
                <tr>
                    <td class="fw-bold text-primary py-2">{a.name}</td>
                    <td class="text-dark fw-semibold py-2">{full_name}</td>
                    <td class="text-secondary py-2"><span class="badge bg-light text-primary border">{grading}</span></td>
                    <td class="text-muted py-2">{email}</td>
                    <td class="text-end py-2">
                        <span class="badge bg-warning text-dark">Under Review</span>
                    </td>
                </tr>
            ''')

        return f'''
        <div class="table-responsive">
            <table class="table table-hover align-middle mb-0" style="font-size: 13px;">
                <thead class="table-light text-muted text-uppercase" style="font-size: 11px; letter-spacing: 0.5px;">
                    <tr>
                        <th>App #</th>
                        <th>Applicant</th>
                        <th>Grade</th>
                        <th>Contact</th>
                        <th class="text-end">Status</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
        '''

    # --- Interactive Button Actions ---
    def action_view_members(self):
        return {
            'name': _('Members Directory'),
            'type': 'ir.actions.act_window',
            'res_model': 'pmz.member',
            'view_mode': 'list,form',
            'target': 'current',
        }

    def action_view_active_members(self):
        return {
            'name': _('Active Members'),
            'type': 'ir.actions.act_window',
            'res_model': 'pmz.member',
            'view_mode': 'list,form',
            'domain': [('membership_status', '=', 'active')],
            'target': 'current',
        }

    def action_view_applications(self):
        return {
            'name': _('Membership Applications'),
            'type': 'ir.actions.act_window',
            'res_model': 'havano.professional.admission',
            'view_mode': 'list,form',
            'target': 'current',
        }

    def action_view_pending_applications(self):
        return {
            'name': _('Pending Applications'),
            'type': 'ir.actions.act_window',
            'res_model': 'havano.professional.admission',
            'view_mode': 'list,form',
            'domain': [('state', '=', 'submitted')],
            'target': 'current',
        }

    def action_view_payments(self):
        return {
            'name': _('Member Payments'),
            'type': 'ir.actions.act_window',
            'res_model': 'pmz.member.payment',
            'view_mode': 'list,form',
            'target': 'current',
        }

    def action_view_invoices(self):
        return {
            'name': _('Member Invoices'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('move_type', '=', 'out_invoice')],
            'context': {'default_move_type': 'out_invoice'},
            'target': 'current',
        }

    def action_view_debtors(self):
        action = self.env.ref('havano_pmz_odoo.action_pmz_debtors_follow_up', raise_if_not_found=False)
        if action:
            return action.read()[0]
        return {
            'name': _('Debtors Follow Up'),
            'type': 'ir.actions.act_window',
            'res_model': 'pmz.member',
            'view_mode': 'list,form',
            'domain': [('outstanding_balance', '>', 0)],
            'target': 'current',
        }

    def action_view_billing_items(self):
        return {
            'name': _('Billing Items Catalog'),
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'view_mode': 'list,kanban,form',
            'target': 'current',
        }

    def action_view_billing_runs(self):
        return {
            'name': _('Bulk Billing Runs'),
            'type': 'ir.actions.act_window',
            'res_model': 'pmz.bulk.billing.wizard',
            'view_mode': 'list,form',
            'target': 'current',
        }

    def action_view_fees_assignments(self):
        return {
            'name': _('Fees Assignments'),
            'type': 'ir.actions.act_window',
            'res_model': 'pmz.fees.structure',
            'view_mode': 'list,form',
            'target': 'current',
        }

    def action_view_exam_forms(self):
        return {
            'name': _('Examination Entries'),
            'type': 'ir.actions.act_window',
            'res_model': 'pmz.exam.entry',
            'view_mode': 'list,form',
            'target': 'current',
        }
