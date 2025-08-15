import pandas as pd
from io import BytesIO
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from core.models import Transaction

import pytest


def make_file(df):
    bio = BytesIO()
    df.to_excel(bio, index=False)
    bio.seek(0)
    return SimpleUploadedFile("test.xlsx", bio.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@pytest.mark.django_db
def test_missing_required_columns(client):
    user = User.objects.create_user("u")
    client.force_login(user)
    df = pd.DataFrame({"Date": ["2024-01-01"], "Type": ["IN"], "Amount": [1], "Category": ["Food"]})
    file = make_file(df)
    resp = client.post(reverse("transaction_import_wizard"), {"file": file}, follow=True)
    assert b"Missing columns" in resp.content


@pytest.mark.django_db
def test_invalid_data_preview(client):
    user = User.objects.create_user("u2")
    client.force_login(user)
    df = pd.DataFrame({
        "Date": ["bad"],
        "Type": ["IN"],
        "Amount": [1],
        "Category": ["Food"],
        "Account": ["Bank"],
    })
    file = make_file(df)
    resp = client.post(reverse("transaction_import_wizard"), {"file": file})
    assert b"Invalid Date" in resp.content


@pytest.mark.django_db
def test_partial_valid_import(monkeypatch, client):
    user = User.objects.create_user("u3")
    client.force_login(user)
    calls = []
    monkeypatch.setattr("core.views.import_wizard.clear_tx_cache", lambda uid, force=True: calls.append(uid))
    df = pd.DataFrame({
        "Date": ["2024-01-01", "2024-01-02"],
        "Type": ["IN", "BAD"],
        "Amount": [1, 2],
        "Category": ["Food", "Food"],
        "Account": ["Bank", "Bank"],
    })
    file = make_file(df)
    client.post(reverse("transaction_import_wizard"), {"file": file})
    client.post(reverse("transaction_import_wizard_commit"))
    assert Transaction.objects.filter(user=user).count() == 1
    assert calls == [user.id]
