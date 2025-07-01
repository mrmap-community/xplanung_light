import django_tables2 as tables
from django_tables2.utils import A
from .models import BPlan, AdministrativeOrganization, BPlanSpezExterneReferenz, BPlanBeteiligung
from django.urls import reverse
from django.utils.html import format_html
from django.contrib.gis.gdal import OGRGeometry


class BPlanSpezExterneReferenzTable(tables.Table):
    edit = tables.LinkColumn('bplanattachment-update', text='Bearbeiten', args=[A('bplan.id'), A('pk')], \
                         orderable=False, empty_values=())
    delete = tables.LinkColumn('bplanattachment-delete', text='Löschen', args=[A('bplan.id'), A('pk')], \
                         orderable=False, empty_values=())
    attachment = tables.Column(verbose_name="Ablage", orderable=False)
    download = tables.LinkColumn('bplanattachment-download', text='Download', args=[A('pk')], \
                         orderable=False, empty_values=())
    name = tables.Column(verbose_name="Name/Bezeichnung")
    typ = tables.Column(verbose_name="Art des Dokuments")

    class Meta:
        model = BPlanSpezExterneReferenz
        template_name = "django_tables2/bootstrap5.html"
        fields = ( "id", "name", "typ", "aus_archiv", "attachment", "download", "edit", "delete")


class BPlanBeteiligungTable(tables.Table):

    edit = tables.LinkColumn('bplanbeteiligung-update', text='Bearbeiten', args=[A('bplan.id'), A('pk')], \
                         orderable=False, empty_values=())
    delete = tables.LinkColumn('bplanbeteiligung-delete', text='Löschen', args=[A('bplan.id'), A('pk')], \
                         orderable=False, empty_values=())
    #attachment = tables.Column(verbose_name="Ablage", orderable=False)
    #download = tables.LinkColumn('bplanbeteiligung-download', text='Download', args=[A('pk')], \
    #                     orderable=False, empty_values=())
    #name = tables.Column(verbose_name="Name/Bezeichnung")
    typ = tables.Column(verbose_name="Art der Beteiligung")

    class Meta:
        model = BPlanBeteiligung
        template_name = "django_tables2/bootstrap5.html"
        fields = ( "id", "bekanntmachung_datum", "typ", "start_datum", "end_datum", "edit", "delete")


class BPlanTable(tables.Table):
    #download = tables.LinkColumn('gedis-document-pdf', text='Download', args=[A('pk')], \
    #                     orderable=False, empty_values=())

    xplan_gml_export = tables.LinkColumn('bplan-export-xplan-raster-6', verbose_name='XPlan-GML', text='Exportieren', args=[A('pk')], \
                         orderable=False, empty_values=())
    xplan_zip_export = tables.LinkColumn('bplan-export-xplan-raster-6-zip', verbose_name='XPlan-ZIP', text='Exportieren', args=[A('pk')], \
                         orderable=False, empty_values=())
    iso_metadata = tables.LinkColumn('bplan-export-iso19139', verbose_name='Geo-Metadaten', text='Exportieren', args=[A('pk')], \
                         orderable=False, empty_values=())
    edit = tables.LinkColumn('bplan-update', text='Bearbeiten', args=[A('pk')], \
                         orderable=False, empty_values=())
    delete = tables.LinkColumn('bplan-delete', text='Löschen', args=[A('pk')], \
                         orderable=False, empty_values=())
    planart = tables.Column(verbose_name="Planart")
    zoom = tables.Column(verbose_name="", accessor='geltungsbereich', orderable=False, empty_values=())
    attachments = tables.Column(verbose_name="Anlagen", accessor='attachments', orderable=False)
    beteiligungen = tables.Column(verbose_name="Beteiligungen", accessor='beteiligungen', orderable=False)
    # manytomany relations are handled automatically!
    #gemeinde = tables.Column(verbose_name="Gemeinde(n)", accessor='gemeinde', orderable=False)
    xplangml = tables.Column(verbose_name="GML Uploaded", accessor='xplan_gml', empty_values=())

    def render_xplangml(self, value, record):
        if value:
            return format_html('<i class="fa fa-check" aria-hidden="true"></i>')
        else:
            return format_html('<i class="fa-solid fa-xmark" aria-hidden="true"></i>')
    
    def render_zoom(self, value):
        ogr_geom = OGRGeometry(str(value), srs=4326)
        extent = ogr_geom.extent
        # lat/lon !
        return format_html('<i class="fa fa-search-plus" aria-hidden="true" onclick="mapGlobal.fitBounds([[{}, {}], [{}, {}]]);"></i>', extent[1], extent[0], extent[3], extent[2])
    
    def render_attachments(self, value, record):
        #print(record)
        #print(record.attachments.count())
        #print(value)
        number_of_attachments = value.count()
        try:
            bplanid = value.first().bplan.id
        except:
            return format_html('<a href="' + reverse('bplanattachment-create', kwargs={'bplanid': record.pk}) + '">' +  str(number_of_attachments) + '</a>')
        return format_html('<a href="' + reverse('bplanattachment-list', kwargs={'bplanid': bplanid}) + '">' +  str(number_of_attachments) + '</a>')
    
    def render_beteiligungen(self, value, record):
        number_of_beteiligungen = value.count()
        try:
            bplanid = value.first().bplan.id
        except:
            return format_html('<a href="' + reverse('bplanbeteiligung-create', kwargs={'bplanid': record.pk}) + '">' +  str(number_of_beteiligungen) + '</a>')
        return format_html('<a href="' + reverse('bplanbeteiligung-list', kwargs={'bplanid': bplanid}) + '">' +  str(number_of_beteiligungen) + '</a>')

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
        fields = ( "zoom", "last_changed", "name", "gemeinde", "planart", "attachments", "xplangml", "xplan_gml_export", "xplan_zip_export", "iso_metadata", "edit", "delete")


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