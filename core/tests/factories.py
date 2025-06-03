import factory
from django.contrib.auth import get_user_model
from core import models


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@test.com")
    password = factory.PostGenerationMethodCall("set_password", "pass1234")


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Category

    user = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Category {n}")
    parent = None  # ← opcional, evita erros se `parent` for obrigatório


class TransactionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Transaction

    user = factory.SubFactory(UserFactory)
    amount = 100
    date = factory.Faker("date_this_year")
    type = "income"

    # 👇 Garante que a category tem o mesmo user que a transaction
    @factory.lazy_attribute
    def category(self):
        return CategoryFactory(user=self.user)
