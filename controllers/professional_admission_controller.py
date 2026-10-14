from odoo import http, _
from odoo.http import request

class ProfessionalAdmissionController(http.Controller):

    @http.route(['/professional/apply'], type='http', auth="public", website=True)
    def professional_apply_form(self, **kw):
        return request.render('havano_pmz_odoo.professional_admission_form', {})

    @http.route(['/professional/apply/submit'], type='http', auth="public", methods=['POST'], website=True, csrf=True)
    def professional_apply_submit(self, **post):
        grading = post.get('grading')

        vals = {
            'first_name': post.get('first_name'),
            'middle_name': post.get('middle_name'),
            'surname': post.get('surname'),
            'title': post.get('title'),
            'dob': post.get('dob') or False,
            'pmp': post.get('pmp') or False,
            'year': post.get('year'),
            'highest_prof_qualifications': post.get('highest_prof_qualifications'),
            'company_name_address': post.get('company_name_address'),
            'present_position': post.get('present_position'),
            'telephone': post.get('telephone'),
            'id_no': post.get('id_no'),
            'residential_address': post.get('residential_address'),
            'chapter': post.get('chapter'),
            'email': post.get('email'),
            'postal_address': post.get('postal_address'),
            'industry_affiliation': post.get('industry_affiliation'),
            'job_function': post.get('job_function'),
            'grading': grading,
            'state': 'submitted'
        }

        # Optional proof of payment upload
        file = post.get('proof_of_payment')
        if file and hasattr(file, 'read'):
            import base64
            file_content = file.read()
            if file_content:
                vals['proof_of_payment'] = base64.b64encode(file_content)
                vals['proof_of_payment_filename'] = getattr(file, 'filename', 'proof_of_payment')

        admission = request.env['havano.professional.admission'].sudo().create(vals)

        return request.render('havano_pmz_odoo.professional_admission_success', {
            'app_name': admission.name,
            'grading_name': dict(admission._fields['grading'].selection).get(admission.grading, admission.grading),
            'fee_amount': admission.invoice_id.amount_total or admission.application_fee,
            'inv_name': admission.invoice_id.name if admission.invoice_id else '',
        })

    @http.route(['/professional/track'], type='http', auth="public", website=True)
    def professional_track_form(self, **kw):
        return request.render('havano_pmz_odoo.professional_admission_track', {
            'error': kw.get('error'),
            'warning': kw.get('warning')
        })

    @http.route(['/professional/track/submit'], type='http', auth="public", methods=['POST'], website=True, csrf=True)
    def professional_track_submit(self, **post):
        domain = [
            ('first_name', '=ilike', post.get('first_name', '').strip()),
            ('surname', '=ilike', post.get('surname', '').strip()),
            ('email', '=ilike', post.get('email', '').strip()),
            ('telephone', '=', post.get('telephone', '').strip()),
        ]
        
        middle_name = post.get('middle_name', '').strip()
        if middle_name:
            domain.append(('middle_name', '=ilike', middle_name))
            
        application = request.env['havano.professional.admission'].sudo().search(domain, order="id desc", limit=1)
        
        if not application:
            return request.redirect('/professional/track?error=No application found matching those details. Please ensure you entered the exact details used during registration.')

        # Check if the member paid that amount before tracking
        is_application_paid = False
        if application.is_paid:
            is_application_paid = True
        elif application.invoice_id and application.invoice_id.payment_state in ('paid', 'in_payment'):
            is_application_paid = True

        fee_amount = application.invoice_id.amount_residual or application.application_fee

        if not is_application_paid:
            warning_msg = f"Payment Required: Application {application.name} has not yet been paid. You are required to pay the application fee of ${fee_amount:.2f} USD before tracking the application status. If you have already paid or attached proof of payment, please allow our finance team to verify and confirm your payment."
            return request.redirect(f'/professional/track?warning={warning_msg}')
            
        return request.render('havano_pmz_odoo.professional_admission_track_result', {
            'application': application
        })

    @http.route(['/professional/exam/cpm_dpm'], type='http', auth="public", website=True)
    def exam_cpm_dpm_form(self, **kw):
        return request.render('havano_pmz_odoo.exam_form_cpm_dpm', {})

    @http.route(['/professional/exam/cme'], type='http', auth="public", website=True)
    def exam_cme_form(self, **kw):
        return request.render('havano_pmz_odoo.exam_form_cme', {})
