import django_tables2 as tables
from django_tables2 import Column
from django_tables2.utils import A
from .models import BPlan, AdministrativeOrganization
from django.urls import reverse
from django.utils.html import format_html

class BPlanTable(tables.Table):
    #download = tables.LinkColumn('gedis-document-pdf', text='Download', args=[A('pk')], \
    #                     orderable=False, empty_values=())
    xplan_gml = tables.LinkColumn('bplan-export-xplan-raster-6', text='Exportieren', args=[A('pk')], \
                         orderable=False, empty_values=())
    iso_metadata = tables.LinkColumn('bplan-export-iso19139', text='Exportieren', args=[A('pk')], \
                         orderable=False, empty_values=())
    edit = tables.LinkColumn('bplan-update', text='Bearbeiten', args=[A('pk')], \
                         orderable=False, empty_values=())
    delete = tables.LinkColumn('bplan-delete', text='Löschen', args=[A('pk')], \
                         orderable=False, empty_values=())
    """
    geojson = Column(
        accessor=A('geojson'),
        orderable=False,
        # ...
    )
    """

    class Meta:
        model = BPlan
        template_name = "django_tables2/bootstrap5.html"
        fields = ("name", "gemeinde", "planart", "xplan_gml", "iso_metadata", "edit", "delete")


class AdministrativeOrganizationPublishingTable(tables.Table):
    num_bplan = tables.Column(verbose_name="Zahl BPläne")
    wms = tables.LinkColumn('ows', text='WMS', args=[A('pk')], \
                         orderable=False, empty_values=())
    wfs = tables.LinkColumn('ows', text='WFS', args=[A('pk')], \
                         orderable=False, empty_values=())

    # https://stackoverflow.com/questions/36698387/how-to-add-get-parameters-to-django-tables2-linkcolumn
    def render_wms(self, record):
        url = reverse('ows', kwargs={'pk': record.id})
        return format_html('<a href="{}?REQUEST=GetCapabilities&SERVICE=WMS">{}</a>', url, 'WMS GetCapabilities')
    
    def render_wfs(self, record):
        url = reverse('ows', kwargs={'pk': record.id})
        return format_html('<a href="{}?REQUEST=GetCapabilities&SERVICE=WFS">{}</a>', url, 'WFS GetCapabilities')


    class Meta:
        model = AdministrativeOrganization
        template_name = "django_tables2/bootstrap5.html"
        fields = ("name", "ags_8", "num_bplan", "wms", "wfs", )