# Install troubleshooting

## "Options must be a valid DocType for field X in row N"

Another app left a Link/Table field on that DocType pointing to a DocType that no longer exists.
NeoZatca 1.2.1+ installs around it and prints a warning. To clean the site:

```bash
bench --site SITE execute neozatca.setup.site_health.report
# Table fields hold no data on the parent; removing them is safe:
bench --site SITE execute neozatca.setup.site_health.remove_orphan_table_fields --kwargs "{'confirm': True}"
```

Orphan **Link** fields are only reported (they hold values in a real column): reinstall the app
that owns them, or delete the Custom Field yourself after checking its data.

## Install stopped part-way

Frappe records an app as installed before running its setup, so `bench install-app` cannot simply
be repeated. Either deploy again (Frappe Cloud runs `migrate`, which completes the setup) or run:

```bash
bench --site SITE execute neozatca.install.repair
```
