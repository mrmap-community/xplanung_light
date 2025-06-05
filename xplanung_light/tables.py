import django_tables2 as tables
from django_tables2 import Column
from django_tables2.utils import A
from .models import BPlan, AdministrativeOrganization
from django.urls import reverse
from django.utils.html import format_html
from django.contrib.gis.gdal import OGRGeometry

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
    planart = tables.Column(verbose_name="Planart")
    zoom = tables.Column(verbose_name="", accessor='geltungsbereich', orderable=False, empty_values=())

    def render_zoom(self, value):
        ogr_geom = OGRGeometry(str(value), srs=4326)
        extent = ogr_geom.extent
        # lat/lon !
        return format_html('<i class="fa fa-search-plus" aria-hidden="true" onclick="mapGlobal.fitBounds([[{}, {}], [{}, {}]]);"></i>', extent[1], extent[0], extent[3], extent[2])
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
        fields = ( "zoom", "last_changed", "name", "gemeinde", "planart", "xplan_gml", "iso_metadata", "edit", "delete")


class AdministrativeOrganizationPublishingTable(tables.Table):
    num_bplan = tables.Column(verbose_name="Zahl BPläne")
    wms = tables.LinkColumn('ows', text='WMS', args=[A('pk')], \
                         orderable=False, empty_values=())
    wfs = tables.LinkColumn('ows', text='WFS', args=[A('pk')], \
                         orderable=False, empty_values=())
    ags = tables.Column(verbose_name="AGS", orderable=False)

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
        fields = ("name", "ags", "num_bplan", "wms", "wfs", )