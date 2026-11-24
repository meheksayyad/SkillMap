from django.db import migrations

from skillmap.taxonomy import NAME_NOT_MATCHED, TAXONOMY


def load_taxonomy(apps, schema_editor):
    """Insert the starting skills so the app works right after `migrate`."""
    Skill = apps.get_model("skillmap", "Skill")
    created = {}
    for name, category, aliases, _prereqs in TAXONOMY:
        obj, _ = Skill.objects.update_or_create(
            name=name,
            defaults={
                "category": category,
                "aliases": list(aliases),
                "match_name": name not in NAME_NOT_MATCHED,
            },
        )
        created[name] = obj
    for name, _category, _aliases, prereqs in TAXONOMY:
        created[name].prerequisites.set([created[p] for p in prereqs])


class Migration(migrations.Migration):
    dependencies = [
        ("skillmap", "0001_initial"),
    ]

    operations = [
        # Reverse is a no-op: removing skills could delete data you added in the admin.
        migrations.RunPython(load_taxonomy, migrations.RunPython.noop),
    ]
