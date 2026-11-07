from conftest import PASSWORD, login, make_client, make_user

from app.models import AuditLog, User, db
from app.utils import gstin_check_digit, inr, password_problem, valid_gstin, valid_pan


def test_login_success_and_audit(client):
    make_user("alice", "admin")
    response = login(client, "alice")
    assert response.status_code == 302
    assert AuditLog.query.filter_by(action="login").count() == 1


def test_wrong_password_is_generic(client):
    make_user("alice", "admin")
    response = client.post("/auth/login", data={"username": "alice", "password": "nope"}, follow_redirects=True)
    assert b"Invalid username or password" in response.data


def test_lockout_after_five_failures(client):
    make_user("alice", "admin")
    for _ in range(5):
        client.post("/auth/login", data={"username": "alice", "password": "wrong"})
    assert User.query.filter_by(username="alice").one().locked_until is not None
    response = client.post("/auth/login", data={"username": "alice", "password": PASSWORD}, follow_redirects=True)
    assert b"locked" in response.data.lower()


def test_forced_password_change(client):
    user = make_user("bob", "accountant")
    user.must_change_password = True
    db.session.commit()
    login(client, "bob")
    response = client.get("/clients")
    assert response.status_code == 302 and "/auth/change-password" in response.headers["Location"]
    response = client.post("/auth/change-password", data={"current_password": PASSWORD, "new_password": "Newpass456", "confirm_password": "Newpass456"})
    assert response.status_code == 302
    assert client.get("/clients").status_code == 200


def test_password_policy():
    assert password_problem("short1")
    assert password_problem("nodigitshere")
    assert password_problem("12345678")
    assert password_problem("Goodpass1") is None


def test_open_redirect_blocked(client):
    make_user("alice", "admin")
    response = client.post("/auth/login?next=https://evil.example.com/", data={"username": "alice", "password": PASSWORD})
    assert "evil.example.com" not in response.headers["Location"]


def test_login_required_and_api_401(client):
    assert client.get("/clients").status_code == 302
    assert client.get("/api/clients/1/vendors").status_code == 401
    assert client.get("/api/health").json["status"] == "ok"


def test_role_restrictions(client):
    make_client()
    make_user("field", "field_staff")
    login(client, "field")
    assert client.get("/admin/users").status_code == 403
    assert client.get("/clients").status_code == 403


def test_accountant_only_sees_assigned_client(client):
    mine = make_client("Mine", "C0001")
    other = make_client("Other", "C0002")
    make_user("acc", "accountant", clients=[mine])
    login(client, "acc")
    assert client.get(f"/clients/{mine.id}").status_code == 200
    assert client.get(f"/clients/{other.id}").status_code == 403


def test_logout_needs_post(client):
    make_user("alice", "admin")
    login(client, "alice")
    assert client.get("/auth/logout").status_code == 405
    assert client.post("/auth/logout").status_code == 302


def test_pan_and_gstin_validation():
    assert valid_pan("AAPFU0939F")
    assert not valid_pan("AAPFU0939")
    assert valid_gstin("27AAPFU0939F1ZV")
    assert not valid_gstin("27AAPFU0939F1ZX")
    assert gstin_check_digit("27AAPFU0939F1Z") == "V"


def test_indian_number_format():
    assert inr(1234567.5) == "₹12,34,567.50"
    assert inr(999) == "₹999.00"
    assert inr(100000, decimals=0) == "₹1,00,000"
    assert inr(-50000) == "-₹50,000.00"
    assert inr(None) == "-"
