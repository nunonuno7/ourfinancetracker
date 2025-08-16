import pytest
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.contrib.messages import get_messages


@pytest.mark.django_db
def test_import_transactions_xlsx_invalid_extension(client):
    user = User.objects.create_user(username="tester", password="secret")
    client.force_login(user)
    file = SimpleUploadedFile("data.txt", b"dummy", content_type="text/plain")
    response = client.post(reverse("transaction_import_xlsx"), {"file": file}, follow=True)
    msgs = list(get_messages(response.wsgi_request))
    assert any("Invalid file extension" in m.message for m in msgs)


@pytest.mark.django_db
def test_import_transactions_xlsx_invalid_mime(client):
    user = User.objects.create_user(username="tester2", password="secret")
    client.force_login(user)
    file = SimpleUploadedFile("data.xlsx", b"dummy", content_type="text/plain")
    response = client.post(reverse("transaction_import_xlsx"), {"file": file}, follow=True)
    msgs = list(get_messages(response.wsgi_request))
    assert any("Invalid file type" in m.message for m in msgs)


@pytest.mark.django_db
def test_import_transactions_xlsx_too_large(client):
    user = User.objects.create_user(username="tester3", password="secret")
    client.force_login(user)
    big_content = b"0" * (5 * 1024 * 1024 + 1)
    file = SimpleUploadedFile(
        "data.xlsx",
        big_content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response = client.post(reverse("transaction_import_xlsx"), {"file": file}, follow=True)
    msgs = list(get_messages(response.wsgi_request))
    assert any("File too large" in m.message for m in msgs)
