from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class OrderEnquiry(models.Model):
    _name = 'order.enq'
    _order = 'sequence, date_order, id'

    name = fields.Char(string='Enquiry Number', default=lambda self: _('New'), readonly=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.user.company_id.id, string='Company')
    currency_id = fields.Many2one('res.currency', string="Currency", related='company_id.currency_id', readonly=True)
    user_id = fields.Many2one('res.users', string='Enquiry BY', default=lambda self: self.env.user)
    partner_id = fields.Many2one('res.partner', string='Customer',  required=True, domain=[('type', '!=', 'private')])
    email = fields.Char(string="Email", related='partner_id.email')
    state = fields.Selection([('pending', 'Pending'), ('confirm', 'Confirmed'), ('cancel', 'cancel')], default='pending', string='state')
    order_line_ids = fields.One2many('order.enq.lines', 'enq_id', string='Order Line')
    sale_order_id = fields.Many2one('sale.order', string='Sale Order')
    sale_order_ids = fields.Many2many('sale.order', string="Sale Order's")
    multi_order = fields.Boolean('Multi Orders')
    sale_count = fields.Integer(compute="compute_sale_count", store=True)
    display_type = fields.Selection([
        ('line_section', 'Section'),
        ('line_note', 'Note'),
    ], default=False)
    date_order = fields.Datetime(string="Enquiry Date", required=True, readonly=False, copy=False, help="Enquiry Date", default=fields.Datetime.now)
    sequence = fields.Integer(string="Sequence", default=10)
    amount_untaxed = fields.Monetary(string="Untaxed Amount", store=True, compute='_compute_amounts', tracking=5)
    amount_tax = fields.Monetary(string="Taxes", store=True, compute='_compute_amounts')
    amount_total = fields.Monetary(string="Total", store=True, compute='_compute_amounts', tracking=4)
    tax_totals = fields.Binary(compute='_compute_tax_totals', exportable=False)

    @api.depends('sale_order_ids')
    def compute_sale_count(self):
        if self.sale_order_id:
            self.sale_count = len(self.sale_order_ids)
        else:
            self.sale_count = None

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('order.enq.sequence') or _('New')
        return super(OrderEnquiry, self).create(vals)

    def button_cancel(self):
        if self.state == 'pending':
            self.state = 'cancel'

    def button_multi_orders(self):
        sales_list = [self.sale_order_id.id]
        self.button_confirm(sales_list)

    def button_confirm(self, sales_list=None):
        if len(self.order_line_ids) <= 0:
            raise ValidationError(_("Before Confirm Please Add Product"))

        sale_order = {
            'partner_id': self.partner_id.id,
            'order_enquirey_id': self.id,
            'date_order': self.date_order,
            'order_line': []
        }
        for line in self.order_line_ids:
            product = self.env['product.product'].search([('product_tmpl_id', '=', line.product_id.id)], limit=1)
            order_lines = (0, 0, {
                'sequence': line.sequence,
                'product_id': product.id,
                'display_type': line.display_type,
                'name': line.name,
                'price_unit': line.price_unit,
                'product_uom': line.product_uom.id,
                'product_uom_qty': line.product_uom_qty,
                'tax_id': [(6, 0, line.tax_id.ids)],
            })
            sale_order['order_line'].append(order_lines)
        create_sales = self.env['sale.order'].create(sale_order)
        if create_sales:
            self.sale_order_id = create_sales.id
            self.sale_order_ids = [(4, create_sales.id)]
            self.state = 'confirm'

    def view_sale_order(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sale Order',
            'res_model': 'sale.order',
            'domain': [('id', 'in', self.sale_order_ids.ids)],
            'view_mode': 'tree,form',
            'target': 'current',
        }

    def button_add_line_from_sales(self):
        if not self.partner_id:
            raise ValidationError('Sorry, Please Select The Customer First')
        return {
            'type': 'ir.actions.act_window',
            'name': "Add Product",
            'res_model': 'sale.line.wizard',
            'view_mode': 'form',
            'context': {
              'customer_id': self.partner_id.id,
            },
            'target': 'new'
        }

    @api.depends_context('lang')
    @api.depends('order_line_ids.tax_id', 'order_line_ids.price_unit', 'amount_total', 'amount_untaxed', 'currency_id')
    def _compute_tax_totals(self):
        for order in self:
            order_lines = order.order_line_ids.filtered(lambda x: not x.display_type)
            order.tax_totals = self.env['account.tax']._prepare_tax_totals(
                [x._convert_to_tax_base_line_dict() for x in order_lines],
                order.currency_id or order.company_id.currency_id,
            )

    @api.depends('order_line_ids.price_subtotal', 'order_line_ids.price_tax', 'order_line_ids.price_total')
    def _compute_amounts(self):
        for order in self:
            order_lines = order.order_line_ids.filtered(lambda x: not x.display_type)

            if order.company_id.tax_calculation_rounding_method == 'round_globally':
                tax_results = self.env['account.tax']._compute_taxes([
                    line._convert_to_tax_base_line_dict()
                    for line in order_lines
                ])
                totals = tax_results['totals']
                amount_untaxed = totals.get(order.currency_id, {}).get('amount_untaxed', 0.0)
                amount_tax = totals.get(order.currency_id, {}).get('amount_tax', 0.0)
            else:
                amount_untaxed = sum(order_lines.mapped('price_subtotal'))
                amount_tax = sum(order_lines.mapped('price_tax'))

            order.amount_untaxed = amount_untaxed
            order.amount_tax = amount_tax
            order.amount_total = order.amount_untaxed + order.amount_tax


class OrderEnquiryLines(models.Model):
    _name = 'order.enq.lines'
    _order = 'sequence, id'

    sequence = fields.Integer(string="Sequence", default=10)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.user.company_id.id, string='Company', readonly=True)
    currency_id = fields.Many2one('res.currency', string="Currency", related='company_id.currency_id', readonly=True)
    product_id = fields.Many2one('product.template', string='Product', domain=[('sale_ok', '=', True)])
    price_unit = fields.Float('Unit Price')
    product_uom_qty = fields.Float('Quantity')
    product_uom = fields.Many2one('uom.uom', string='Unit Of Measure')
    tax_id = fields.Many2many(comodel_name='account.tax', string="Taxes", domain=[('type_tax_use', '=', 'sale')])
    name = fields.Char('Description')
    display_type = fields.Selection([
        ('line_section', 'Section'),
        ('line_note', 'Note'),
    ], default=False)
    enq_id = fields.Many2one('order.enq')
    price_subtotal = fields.Monetary(string="Subtotal", compute='_compute_amount', store=True, precompute=True)
    price_tax = fields.Float(string="Total Tax", compute='_compute_amount', store=True, precompute=True)
    price_total = fields.Monetary(string="Total", compute='_compute_amount', store=True, precompute=True)
    sale_order_id = fields.Many2one('sale.order', string='Sale Order ID', related='enq_id.sale_order_id')

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.price_unit = self.product_id.list_price
            self.product_uom = self.product_id.uom_id.id
            self.product_uom_qty = 1.0
            self.name = f"[{self.product_id.default_code}] {self.product_id.name}"
            self.display_type = False
            self.tax_id = self.product_id.taxes_id

    def _convert_to_tax_base_line_dict(self):
        """ Convert the current record to a dictionary in order to use the generic taxes computation method
        defined on account.tax.

        :return: A python dictionary.
        """
        self.ensure_one()
        return self.env['account.tax']._convert_to_tax_base_line_dict(
            self,
            partner=self.enq_id.partner_id,
            currency=self.enq_id.currency_id,
            product=self.product_id,
            taxes=self.tax_id,
            price_unit=self.price_unit,
            quantity=self.product_uom_qty,
            price_subtotal=self.price_subtotal,
        )

    @api.depends('product_uom_qty', 'price_unit', 'tax_id')
    def _compute_amount(self):
        """
        Compute the amounts of the Order Enq line.
        """
        for line in self:
            tax_results = self.env['account.tax'].with_company(line.company_id)._compute_taxes(
                [line._convert_to_tax_base_line_dict()]
            )
            totals = list(tax_results['totals'].values())[0]
            amount_untaxed = totals['amount_untaxed']
            amount_tax = totals['amount_tax']

            line.update({
                'price_subtotal': amount_untaxed,
                'price_tax': amount_tax,
                'price_total': amount_untaxed + amount_tax,
            })


class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    order_enquirey_id = fields.Many2one('order.enq', string='Order Enquiry ID')

    def button_add_line_from_sales(self):
        if not self.partner_id:
            raise ValidationError('Sorry, Please Select The Customer First')
        return {
            'type': 'ir.actions.act_window',
            'name': "Add Product",
            'res_model': 'sale.line.wizard',
            'view_mode': 'form',
            'context': {
              'customer_id': self.partner_id.id,
            },
            'target': 'new'
        }


class ProductTemplateInherit(models.Model):
    _inherit = 'product.template'

    def button_add_sales_line(self):
        return {
            'type': 'ir.actions.act_window',
            'name': "Add Product",
            'res_model': 'product.add.wizard',
            'view_mode': 'form',
            'context': {
                'default_product_id': self.id,
                'default_price_unit': self.list_price,
                'default_product_uom': self.uom_id.id,
            },
            'target': 'new'
        }
