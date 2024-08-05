
{
    'name': 'Sale Order Enquiry',
    'version': '1.2',
    'summary': 'Order Enquiry feature that helps manage and track potential sales efficiently. It centralizes all relevant information, automates calculations, and integrates smoothly with existing sales processes. This means your team can handle inquiries more effectively, improve customer service, and streamline the sales process from initial inquiry to final sale.',
    'sequence': 10,
    'depends': ['base', 'base_setup', 'sale',  'product', 'account'],
    'author': "JD DEVS",
    'category': 'Sales/Sales',
    'data': [
        'views/order_enq.xml',
        'wizards/add_lines_sale.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'AGPL-3',
    'images': ['static/description/assets/screenshots/banner.png'],
}
