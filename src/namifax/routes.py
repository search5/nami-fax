"""NamiFAX URL route declarations."""

from __future__ import annotations


def includeme(config):
    """Add static views and application routes."""
    config.add_static_view("static", "static", cache_max_age=3600)

    # Public routes
    config.add_route("home", "/")
    config.add_route("login", "/login")
    config.add_route("logout", "/logout")
    config.add_route("forgot", "/forgot")
    config.add_route("pwdexpired", "/pwdexpired")
    config.add_route("login_totp", "/login/totp")

    # Authenticated user routes (permission: 'view' or 'send_fax')
    config.add_route("inbox", "/inbox")
    config.add_route("viewfax", "/viewfax")
    config.add_route("fax_download", "/faxes/download/{fid}")
    config.add_route("fax_image", "/faxes/image/{fid}/{page}")
    config.add_route("fax_thumbnail", "/faxes/thumbnail/{fid}")
    config.add_route("fax_rotate", "/faxes/rotate/{fid}")
    config.add_route("sendfax", "/sendfax")
    config.add_route("outbox", "/outbox")
    config.add_route("opensearch", "/search")
    config.add_route("archive", "/archive")
    config.add_route("addressbook", "/addressbook")
    config.add_route("addressbook_edit", "/addressbook/edit")
    config.add_route("distrolist", "/distrolist")
    config.add_route("distrolist_edit", "/distrolist/edit")
    config.add_route("settings", "/settings")
    config.add_route("totp_setup", "/settings/2fa/setup")
    config.add_route("totp_enable", "/settings/2fa/enable")
    config.add_route("totp_disable", "/settings/2fa/disable")
    config.add_route("totp_recovery", "/settings/2fa/recovery")

    # Admin only routes (permission: 'admin')
    config.add_route("admin", "/admin")
    config.add_route("admin_users", "/admin/users")
    config.add_route("admin_user_delete", "/admin/users/delete")
    config.add_route("admin_modems", "/admin/modems")
    config.add_route("admin_routing_did", "/admin/routing/did")
    config.add_route("admin_did", "/admin/did")
    config.add_route("admin_barcodes", "/admin/barcodes")
    config.add_route("admin_covers", "/admin/covers")
    config.add_route("admin_categories", "/admin/categories")
    config.add_route("admin_dynconf", "/admin/dynconf")
    config.add_route("admin_fax2email", "/admin/fax2email")
    config.add_route("admin_system_func", "/admin/system_func")
    config.add_route("admin_sysfunc", "/admin/sysfunc")
    config.add_route("admin_system_logs", "/admin/system_logs")
    config.add_route("admin_syslog", "/admin/syslog")
    config.add_route("admin_smtp", "/admin/smtp")
    config.add_route("admin_printers", "/admin/printers")
    config.add_route("admin_storage", "/admin/storage")
    config.add_route("admin_scheduler", "/admin/scheduler")
    config.add_route("admin_scheduler_state", "/admin/scheduler/state")
    config.add_route("admin_scheduler_jobs", "/admin/scheduler/jobs")
    config.add_route("admin_saml", "/admin/saml")

    # Interaction Modal Dialog routes
    config.add_route("modal_email", "/email")
    config.add_route("modal_assign", "/assign")
    config.add_route("assignx", "/assignx")
    config.add_route("modal_note", "/note")
    config.add_route("modal_delete", "/delete")
    config.add_route("modal_refax", "/refax")
    config.add_route("modal_txreport", "/txreport")

    # Asynchronous AJAX routes
    config.add_route("ajax_modemstatus", "/ajax/modemstatus")
    config.add_route("ajax_inbox", "/ajax/inbox")
    config.add_route("audio", "/audio/{name}")
    config.add_route("ajax_book", "/ajax/book")
    config.add_route("ajax_emailbook", "/ajax/emailbook")
    config.add_route("ajax_prefillto", "/ajax/prefillto")
    config.add_route("ajax_dlist", "/ajax/dlist")
    config.add_route("ajax_archivefax", "/ajax/archivefax")
    config.add_route("ajax_faxalter", "/ajax/faxalter")
    config.add_route("ajax_deletefaxes", "/ajax/deletefaxes")
    config.add_route("ajax_archivebook", "/ajax/archivebook")

    # Additional Legacy Compatible routes
    config.add_route("rotate", "/rotate")
    config.add_route("setcompany", "/setcompany")
    config.add_route("emailbook", "/emailbook")
    config.add_route("emailbook_edit", "/emailbook/edit")

    # Popup helper routes
    config.add_route("popup_distrolist_helper", "/helper/distrolist")
    config.add_route("popup_distro_contacts", "/helper/distrocontacts")
    config.add_route("popup_fax_contacts", "/helper/faxcontacts")
    config.add_route("popup_email_contacts", "/helper/emailcontacts")

    # vCard Contact Upload routes
    config.add_route("upload_contacts", "/upload/contacts")
    config.add_route("upload_faxcontacts", "/upload/faxcontacts")

    # WebAuthn / Passkeys routes
    config.add_route("api_webauthn_register_options", "/api/webauthn/register/options")
    config.add_route("api_webauthn_register_verify", "/api/webauthn/register/verify")
    config.add_route("api_webauthn_auth_options", "/api/webauthn/auth/options")
    config.add_route("api_webauthn_auth_verify", "/api/webauthn/auth/verify")
    config.add_route("api_webauthn_credentials", "/api/webauthn/credentials")
    config.add_route("api_webauthn_credentials_delete", "/api/webauthn/credentials/delete")

    # SAML 2.0 Enterprise SSO routes
    config.add_route("saml_metadata", "/auth/saml/metadata")
    config.add_route("saml_login", "/auth/saml/login")
    config.add_route("saml_acs", "/auth/saml/acs")
    config.add_route("saml_sls", "/auth/saml/sls")
