def includeme(config):
    config.add_route('admin_conf_barcoderoute_edit', '/conf_barcoderoute_edit')
    config.add_route('admin_conf_dynconf', '/conf_dynconf')
    config.add_route('admin_fax2email', '/fax2email')
    config.add_route('admin_logout', '/logout')
    config.add_route('admin_users', '/users')
    config.add_route('admin_conf_covers', '/conf_covers')
    config.add_route('admin_conf_dynconf_edit', '/conf_dynconf_edit')
    config.add_route('admin_fax2email_edit', '/fax2email_edit')
    config.add_route('admin_no-database', '/no-database')
    config.add_route('admin_users_list', '/users_list')
    config.add_route('admin_admin', '/admin')
    config.add_route('admin_conf_covers_edit', '/conf_covers_edit')
    config.add_route('admin_conf_modems', '/conf_modems')
    config.add_route('admin_fax_cat_edit', '/fax_cat_edit')
    config.add_route('admin_pwdexpired', '/pwdexpired')
    config.add_route('admin_check_login', '/check_login')
    config.add_route('admin_conf_didroute', '/conf_didroute')
    config.add_route('admin_conf_modems_edit', '/conf_modems_edit')
    config.add_route('admin_fax_categories', '/fax_categories')
    config.add_route('admin_system_func', '/system_func')
    config.add_route('admin_conf_barcoderoute', '/conf_barcoderoute')
    config.add_route('admin_conf_didroute_edit', '/conf_didroute_edit')
    config.add_route('admin_deluser', '/deluser')
    config.add_route('admin_index', '', inherit_slash=True)
    config.add_route('admin_system_logs', '/system_logs')
