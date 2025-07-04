{
    'name': "Asset Management",
    'version': '1.0',
    'summary': 'Aset Bulanan dan Kondisi',
    'author': 'Your Name',
    'category': 'Assets',
    'depends': ['base','mail','stock'],
    'data': [
        'views/asset_condition_month_views.xml',
        'views/asset_condition_month_line_views.xml',
        'views/asset_condition_month_done_views.xml',
        'views/menu.xml',
        'views/asset_item_views.xml',
        'views/user_group_views.xml',
        'views/approval_route_line_menu.xml',
        'views/asset_menu_views.xml',
        'data/module_category.xml',
        'data/approval_group_and_route.xml',
        'data/fix_warehouse.xml',
        'security/asset_model_records.xml',
        'security/ir.model.access.csv',
        'data/override_stock_data.xml',
    ],
    'application': True,
}