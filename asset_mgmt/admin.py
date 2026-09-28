from django.contrib import admin
from django.apps import apps

admin.site.site_header = 'Engineering Asset Management Administration'
admin.site.site_title = 'Engineering Asset Admin'
admin.site.index_title = 'Master Data and Controlled Records'

# Register every project model. Workflow records are protected by model PROTECT relations;
# production deployments should grant admin access only to authorised system administrators.
app_config = apps.get_app_config('asset_mgmt')
for model in app_config.get_models():
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass
