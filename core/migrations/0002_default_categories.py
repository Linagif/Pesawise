from django.db import migrations

DEFAULTS = {
    "INCOME": ["Parents or guardians", "Casual jobs", "Freelancing", "Tutoring", "Small business",
               "Scholarship or allowance", "Other"],
    "EXPENSE": ["Food", "Transport", "Rent", "Education and academic materials", "Internet and airtime",
                "Entertainment", "Personal care", "Shopping", "Health", "Miscellaneous"],
    "SAVINGS": ["Savings"],
}


def seed(apps, schema_editor):
    Category = apps.get_model("core", "Category")
    for ctype, names in DEFAULTS.items():
        for name in names:
            Category.objects.get_or_create(user=None, name=name, category_type=ctype)


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
