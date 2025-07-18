from odoo import _,models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import date
import logging

_logger = logging.getLogger(__name__)

class AssetConditionMonth(models.Model):
    _name = 'x_asset.condition.month'
    _description = 'Kondisi Bulanan Aset'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # RELASI KE LINE
    line_ids = fields.One2many(
        'x_asset.condition.month.line',
        'month_id',
        string='Detail Inspeksi'
    )

    tanggal = fields.Date(string='Tanggal', required=True, default=fields.Date.context_today)
    jumlah = fields.Integer(string='Jumlah', compute='_compute_total_kondisi', store=True)
    kondisi_baik = fields.Integer(string='Kondisi Baik', compute='_compute_total_kondisi', store=True)
    kondisi_rusak = fields.Integer(string='Kondisi Rusak', compute='_compute_total_kondisi', store=True)
    keterangan = fields.Text(string='Keterangan')
    bulan_tahun = fields.Char(string='Bulan - Tahun', compute='_compute_bulan_tahun', store=True)
    inspect_by = fields.Many2one('res.users', string='Inspected By', readonly=True)

    approval_route_ids = fields.Many2many(
        'approval.route.line',
        string='Approval Routes',
        default=lambda self: self.env.ref('module_name.approval_group_route_line_1').ids if self.env.ref('module_name.approval_group_route_line_1', raise_if_not_found=False) else []
    )
    current_approval_index = fields.Integer(string='Current Approval Index', default=0)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('on_approval', 'On Approval'),
        ('approved', 'Approved'),
       ], string='Status', default='draft', tracking=True)

    approver_user_ids = fields.Many2many(
        'res.users',
        'x_asset_condition_month_approver_rel',
        'condition_id',
        'user_id',
        string='Approvers',
        compute='_compute_approvers',
        store=True
    )

    approved_user_ids = fields.Many2many(
        'res.users',
        'x_asset_condition_month_approved_rel',
        'condition_id',
        'user_id',
        string='Approved By'
    )

    show_submit = fields.Boolean(compute='_compute_button_visibility', store=True)
    show_approve = fields.Boolean(compute='_compute_button_visibility', store=True)
    show_reject = fields.Boolean(compute='_compute_button_visibility', store=True)

    # === COMPUTE ===
    @api.depends('state', 'approver_user_ids', 'approved_user_ids')
    def _compute_button_visibility(self):
        current_user = self.env.user
        for rec in self:
            rec.show_submit = rec.state == 'draft'
            rec.show_approve = rec.state == 'on_approval' and current_user in rec.approver_user_ids and current_user not in rec.approved_user_ids
            rec.show_reject = rec.state == 'on_approval' and current_user in rec.approver_user_ids

    @api.depends('tanggal')
    def _compute_bulan_tahun(self):
        for record in self:
            record.bulan_tahun = record.tanggal.strftime('%B %Y') if record.tanggal else ''

    @api.depends('approval_route_ids')
    def _compute_approvers(self):
        for rec in self:
            users = self.env['res.users']
            for line in rec.approval_route_ids:
                group_users = self.env['res.users'].search([('groups_id', '=', line.group_id.id)])
                users |= group_users
            rec.approver_user_ids = [(6, 0, users.ids)]

    @api.depends('line_ids.kondisi_baik', 'line_ids.kondisi_rusak')
    def _compute_total_kondisi(self):
        for rec in self:
            total_baik = sum(line.kondisi_baik or 0 for line in rec.line_ids)
            total_rusak = sum(line.kondisi_rusak or 0 for line in rec.line_ids)
            rec.kondisi_baik = total_baik
            rec.kondisi_rusak = total_rusak
            rec.jumlah = total_baik + total_rusak

        # === CREATE/WRITE ===

    # def write(self, vals):
    #     for rec in self:
    #         print("rec.state:", rec.state)
    #         if rec.state != 'draft':
    #             raise UserError(_("Tidak bisa mengubah data jika bukan dalam status Draft."))
    #     return super().write(vals)

    # === ACTIONS ===

    def action_submit(self):
        for rec in self:
            rec.inspect_by = self.env.user
            # total = (rec.kondisi_baik or 0) + (rec.kondisi_rusak or 0)

        # if rec.total != rec.jumlah:
        #     rec.state = 'on_approval'
        #     rec.current_approval_index = 0
        #     rec.message_post(body="⚠️ Jumlah kondisi tidak sesuai. Diperlukan proses approval.")
        # elif not rec.approver_user_ids:
        #     rec.state = 'approved'
        #     rec.message_post(body="✅ Jumlah kondisi sesuai dan tidak ada approver. Status langsung disetujui.")

        rec.state = 'on_approval'
        rec.current_approval_index = 0
        rec.message_post(body="⏳ Menunggu persetujuan dari approver.")


    @api.onchange('tanggal')
    def _onchange_generate_line_ids(self):
        if not self.line_ids:
            items = self.env['x_asset.item'].search([])
            lines = []
            for item in items:
                if item:
                    lines.append((0, 0, {
                        'item_id': item.id,
                        'jumlah': item.onHandQuantity,
                    }))
            if lines:
                self.line_ids = lines

        
    def action_approve(self):
        for rec in self:
            if rec.state != 'on_approval':
                raise ValidationError(_("Record is not under approval."))

            user = self.env.user

            # ❗ Cek apakah user termasuk dalam approver_user_ids
            if user.id not in rec.approver_user_ids.ids:
                raise UserError(_("Anda tidak memiliki izin untuk menyetujui record ini."))

            if user in rec.approved_user_ids:
                raise UserError(_("Anda sudah menyetujui record ini sebelumnya."))

            rec.approved_user_ids = [(4, user.id)]
            rec.message_post(body=f"✅ {user.name} telah menyetujui.")

            approver_ids = set(rec.approver_user_ids.ids)
            approved_ids = set(rec.approved_user_ids.ids)

            if approver_ids and approver_ids.issubset(approved_ids):
                rec.state = 'approved'
                rec.message_post(body="✅ Semua approver telah menyetujui. Status: Approved.")
            else:
                remaining = approver_ids - approved_ids
                names = ', '.join(self.env['res.users'].browse(list(remaining)).mapped('name'))
                rec.message_post(body=f"⏳ Menunggu persetujuan dari: {names}")




    # @api.model
    # def create(self, vals):
    #     if not vals.get('line_ids'):
    #         items = self.env['x_asset.item'].search([])
    #         lines = []
    #         for item in items:
    #             lines.append((0, 0, {
    #                 'item_id': item.id,
    #                 'jumlah': item.onHandQuantity,
    #             }))
    #         vals['line_ids'] = lines

    #     return super().create(vals)
    

    @api.model
    def create(self, vals):
        if not vals.get('approval_route_ids'):
            default_route = self.env.ref('assetManagement.approval_route_assets_step1', raise_if_not_found=False)
            if default_route:
                vals['approval_route_ids'] = [(6, 0, [default_route.id])]

        # Auto generate line_ids jika belum ada
        if not vals.get('line_ids'):
            items = self.env['x_asset.item'].search([])
            lines = [(0, 0, {'item_id': item.id, 'jumlah': item.onHandQuantity}) for item in items]
            vals['line_ids'] = lines

        return super().create(vals)

    @api.depends('approval_route_ids')
    def _compute_approvers(self):
        for rec in self:
            users = self.env['res.users']
            for line in rec.approval_route_ids:
                group_users = self.env['res.users'].search([('groups_id', '=', line.group_id.id)])
                users |= group_users
            rec.approver_user_ids = [(6, 0, users.ids)]

    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('tanggal')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"Inspection - {rec.tanggal.strftime('%d/%m/%Y')}" if rec.tanggal else "Inspection"

    _rec_name = 'display_name'