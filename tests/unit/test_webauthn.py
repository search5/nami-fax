from namifax.services.webauthn import WebAuthnService, WebAuthnCredential

def test_webauthn_service_init():
    svc = WebAuthnService(rp_id="fax.example.com", rp_name="NamiFAX Enterprise")
    assert svc.rp_id == "fax.example.com"
    assert svc.rp_name == "NamiFAX Enterprise"

def test_generate_registration_options():
    svc = WebAuthnService(rp_id="fax.example.com", rp_name="NamiFAX Enterprise")
    opts = svc.generate_registration_options(
        user_id=1,
        user_name="admin",
        user_display_name="Administrator",
    )
    assert "challenge" in opts
    assert opts["rp"]["name"] == "NamiFAX Enterprise"
    assert opts["rp"]["id"] == "fax.example.com"
    assert opts["user"]["name"] == "admin"
    assert opts["user"]["displayName"] == "Administrator"
    assert len(opts["pubKeyCredParams"]) > 0

# credential storage (list/save/delete/options) is covered against a real session in test_webauthn_orm.py
