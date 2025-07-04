from odoo import models, fields, api
from odoo.exceptions import ValidationError
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

    tanggal = fields.Date(string='Tanggal', required=True)
    jumlah = fields.Integer(string='Jumlah', readonly=True)
    kondisi_baik = fields.Integer(string='Kondisi Baik')
    kondisi_rusak = fields.Integer(string='Kondisi Rusak')
    keterangan = fields.Text(string='Keterangan')
    bulan_tahun = fields.Char(string='Bulan - Tahun', compute='_compute_bulan_tahun', store=True)
    inspect_by = fields.Many2one('res.users', string='Inspected By', readonly=True)

    approval_route_ids = fields.Many2many('approval.route.line', string='Approval Routes')
    current_approval_index = fields.Integer(string='Current Approval Index', default=0)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('on_approval', 'On Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')], string='Status', default='draft', tracking=True)

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

    @api.depends('state')
    def _compute_button_visibility(self):
        for rec in self:
            rec.show_submit = rec.state == 'draft'
            rec.show_approve = rec.state == 'on_approval'
            rec.show_reject = rec.state == 'on_approval'

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

    # === CREATE/WRITE ===

    def write(self, vals):
        return super().write(vals)

    @api.model
    def create(self, vals):
        # Ambil semua item
        items = self.env['x_asset.item'].search([])

        # Buat line_ids langsung di vals
        line_vals = []
        for item in items:
            line_vals.append((0, 0, {
                'item_id': item.id,
                'jumlah': item.onHandQuantity,
                'kondisi_baik': 0,
                'kondisi_rusak': 0,
            }))
        vals['line_ids'] = line_vals

        return super().create(vals)
    
    @api.model
    def default_get(self, fields):
        defaults = super().default_get(fields)
        items = self.env['x_asset.item'].search([])

        line_vals = []
        for item in items:
            if item:
                line_vals.append((0, 0, {
                    'item_id': item.id,
                    'jumlah': item.onHandQuantity,
                    'kondisi_baik': 0,
                    'kondisi_rusak': 0,
                }))
        if line_vals:
            defaults['line_ids'] = line_vals

        return defaults
    # === ACTIONS ===

    def action_submit(self):
        for rec in self:
            total = (rec.kondisi_baik or 0) + (rec.kondisi_rusak or 0)
            if total == rec.jumlah:
                rec.state = 'approved'
                rec.message_post(body="✅ Jumlah kondisi sesuai. Status langsung disetujui.")
            else:
                rec.state = 'on_approval'
                rec.current_approval_index = 0
                rec.message_post(body="⚠️ Jumlah kondisi tidak sesuai. Diperlukan proses approval.")

    def action_approve(self):
        for rec in self:
            if rec.state != 'on_approval':
                raise ValidationError("Record is not under approval.")

            user = self.env.user
            if user in rec.approved_user_ids:
                raise ValidationError("You have already approved this record.")

            rec.approved_user_ids = [(4, user.id)]
            rec.message_post(body=f"✅ {user.name} telah menyetujui.")

            if set(rec.approver_user_ids.ids).issubset(set(rec.approved_user_ids.ids)):
                rec.state = 'approved'
                rec.message_post(body="✅ Semua approver telah menyetujui. Status: Approved.")
            else:
                remaining = set(rec.approver_user_ids.ids) - set(rec.approved_user_ids.ids)
                remaining_users = self.env['res.users'].browse(list(remaining))
                names = ', '.join(remaining_users.mapped('name'))
                rec.message_post(body=f"⏳ Menunggu persetujuan dari: {names}")

    def action_reject(self):
        for rec in self:
            if rec.state != 'on_approval':
                raise ValidationError("Record is not under approval.")
            rec.state = 'rejected'
            rec.message_post(body=f"❌ Ditolak oleh {self.env.user.name}")
