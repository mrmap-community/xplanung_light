import django_tables2 as tables
from django_tables2.utils import A
from .models import BPlan, AdministrativeOrganization, BPlanSpezExterneReferenz, BPlanBeteiligung, ContactOrganization, Uvp
from .models import FPlan, FPlanBeteiligung, FPlanSpezExterneReferenz
from django.urls import reverse
from django.utils.html import format_html
from django.contrib.gis.gdal import OGRGeometry


class AdministrativeOrganizationTable(tables.Table):
    edit = tables.LinkColumn('organization-update', verbose_name='', text='Bearbeiten', args=[A('pk')], \
                         orderable=False, empty_values=())
    #delete = tables.LinkColumn('contactorganization-delete', text='Löschen', args=[A('pk')], \
    #                  orderable=False, empty_values=())

    def render_ags(self, record):
        if record.ts:
            return format_html(record.ags + ' - ' + record.ts)
        else:
            return format_html(record.ags)
        
    def render_name(self, record):
        if record.name_part:
            return format_html(record.name + ' - ' + record.name_part)
        else:
            return format_html(record.name)
        
    class Meta:
        model = AdministrativeOrganization
        template_name = "django_tables2/bootstrap5.html"
        fields = ['id', 'ags', 'name', 'edit']


class ContactOrganizationTable(tables.Table):
    edit = tables.LinkColumn('contact-update', verbose_name='', text='Bearbeiten', args=[A('pk')], \
                         orderable=False, empty_values=())
    delete = tables.LinkColumn('contact-delete', verbose_name='', text='Löschen', args=[A('pk')], \
                         orderable=False, empty_values=())
    class Meta:
        model = ContactOrganization
        template_name = "django_tables2/bootstrap5.html"
        fields = ['id', 'name', 'gemeinde', 'edit', 'delete']


class BPlanSpezExterneReferenzTable(tables.Table):
    edit = tables.LinkColumn('bplanattachment-update', verbose_name='', text='Bearbeiten', args=[A('bplan.id'), A('pk')], \
                         orderable=False, empty_values=())
    delete = tables.LinkColumn('bplanattachment-delete', verbose_name='', text='Löschen', args=[A('bplan.id'), A('pk')], \
                         orderable=False, empty_values=())
    attachment = tables.Column(verbose_name="Ablage", orderable=False)
    download = tables.LinkColumn('bplanattachment-download', verbose_name='', text='Download', args=[A('pk')], \
                         orderable=False, empty_values=())
    name = tables.Column(verbose_name="Name/Bezeichnung")
    typ = tables.Column(verbose_name="Art des Dokuments")

    class Meta:
        model = BPlanSpezExterneReferenz
        template_name = "django_tables2/bootstrap5.html"
        fields = ( "id", "name", "typ", "aus_archiv", "attachment", "download", "edit", "delete")


class FPlanSpezExterneReferenzTable(tables.Table):
    edit = tables.LinkColumn('fplanattachment-update', verbose_name='', text='Bearbeiten', args=[A('fplan.id'), A('pk')], \
                         orderable=False, empty_values=())
    delete = tables.LinkColumn('fplanattachment-delete', verbose_name='', text='Löschen', args=[A('fplan.id'), A('pk')], \
                         orderable=False, empty_values=())
    attachment = tables.Column(verbose_name="Ablage", orderable=False)
    download = tables.LinkColumn('fplanattachment-download', verbose_name='', text='Download', args=[A('pk')], \
                         orderable=False, empty_values=())
    name = tables.Column(verbose_name="Name/Bezeichnung")
    typ = tables.Column(verbose_name="Art des Dokuments")

    class Meta:
        model = FPlanSpezExterneReferenz
        template_name = "django_tables2/bootstrap5.html"
        fields = ( "id", "name", "typ", "aus_archiv", "attachment", "download", "edit", "delete")


class BPlanBeteiligungTable(tables.Table):

    edit = tables.LinkColumn('bplanbeteiligung-update', verbose_name='', text='Bearbeiten', args=[A('bplan.id'), A('pk')], \
                         orderable=False, empty_values=())
    delete = tables.LinkColumn('bplanbeteiligung-delete', verbose_name='', text='Löschen', args=[A('bplan.id'), A('pk')], \
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

class FPlanBeteiligungTable(tables.Table):

    edit = tables.LinkColumn('fplanbeteiligung-update', verbose_name='', text='Bearbeiten', args=[A('fplan.id'), A('pk')], \
                         orderable=False, empty_values=())
    delete = tables.LinkColumn('fplanbeteiligung-delete', verbose_name='', text='Löschen', args=[A('fplan.id'), A('pk')], \
                         orderable=False, empty_values=())
    #attachment = tables.Column(verbose_name="Ablage", orderable=False)
    #download = tables.LinkColumn('bplanbeteiligung-download', text='Download', args=[A('pk')], \
    #                     orderable=False, empty_values=())
    #name = tables.Column(verbose_name="Name/Bezeichnung")
    typ = tables.Column(verbose_name="Art der Beteiligung")

    class Meta:
        model = FPlanBeteiligung
        template_name = "django_tables2/bootstrap5.html"
        fields = ( "id", "bekanntmachung_datum", "typ", "start_datum", "end_datum", "edit", "delete")


class UvpTable(tables.Table):

    edit = tables.LinkColumn('uvp-update', verbose_name='', text='Bearbeiten', args=[A('bplan.id'), A('pk')], \
                         orderable=False, empty_values=())
    delete = tables.LinkColumn('uvp-delete', verbose_name='', text='Löschen', args=[A('bplan.id'), A('pk')], \
                         orderable=False, empty_values=())
    typ = tables.Column(verbose_name="Kategorie gem. UVPG Anlage 1")

    class Meta:
        model = Uvp
        template_name = "django_tables2/bootstrap5.html"
        fields = ( "id", "uvp_vp", "uvp", "typ", "uvp_beginn_datum", "uvp_ende_datum", "edit", "delete")



class BPlanTable(tables.Table):
    last_changed = tables.Column(verbose_name="Letzte Änderung")
    """
    Aus Tabelle rausgenommen, 
    xplan_gml_export = tables.LinkColumn('bplan-export-xplan-raster-6', verbose_name='XPlan-GML', text='Exportieren', args=[A('pk')], \
                         orderable=False, empty_values=())
    xplan_zip_export = tables.LinkColumn('bplan-export-xplan-raster-6-zip', verbose_name='XPlan-ZIP', text='Exportieren', args=[A('pk')], \
                         orderable=False, empty_values=())
    iso_metadata = tables.LinkColumn('bplan-export-iso19139', verbose_name='Geo-Metadaten', text='Exportieren', args=[A('pk')], \
                         orderable=False, empty_values=())
    """
    edit = tables.LinkColumn('bplan-update', verbose_name="", text='Bearbeiten', args=[A('pk')], \
                         orderable=False, empty_values=())
    delete = tables.LinkColumn('bplan-delete', verbose_name="", text='Löschen', args=[A('pk')], \
                         orderable=False, empty_values=())
    planart = tables.Column(verbose_name="Planart")
    zoom = tables.Column(verbose_name="", accessor='geltungsbereich', orderable=False, empty_values=())
    count_attachments = tables.Column(verbose_name="Anlagen", accessor='count_attachments', orderable=False)
    count_beteiligungen = tables.Column(verbose_name="Beteiligungen", accessor='count_beteiligungen', orderable=False)
    count_uvps = tables.Column(verbose_name="UVPs", accessor='count_uvps', orderable=False)
    detail = tables.LinkColumn('bplan-detail', verbose_name='Details', text='Anzeigen', args=[A('pk')], \
                         orderable=False, empty_values=())
    # manytomany relations are handled automatically!
    #gemeinde = tables.Column(verbose_name="Gemeinde(n)", accessor='gemeinde', orderable=False)
    xplangml = tables.Column(verbose_name="XPlan-GML Hochgeladen", accessor='xplan_gml', empty_values=())

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
    
    def render_count_attachments(self, value, record):
        if value == 0:
            return format_html('<a href="' + reverse('bplanattachment-create', kwargs={'planid': record.id}) + '">' +  str(value) + '</a>')
        else:
            return format_html('<a href="' + reverse('bplanattachment-list', kwargs={'planid': record.id}) + '">' +  str(value) + '</a>')
        
    def render_count_beteiligungen(self, value, record):
        if value == 0:
            return format_html('<a href="' + reverse('bplanbeteiligung-create', kwargs={'planid': record.id}) + '">' +  str(value) + '</a>')
        else:
            return format_html('<a href="' + reverse('bplanbeteiligung-list', kwargs={'planid': record.id}) + '">' +  str(value) + '</a>')
        
    def render_count_uvps(self, value, record):
        if value == 0:
            return format_html('<a href="' + reverse('uvp-create', kwargs={'planid': record.id}) + '">' +  str(value) + '</a>')
        else:
            return format_html('<a href="' + reverse('uvp-list', kwargs={'planid': record.id}) + '">' +  str(value) + '</a>')
        
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
        fields = ( "zoom", "last_changed", "inkrafttretens_datum", "nummer", "name", "gemeinde", "planart", "count_attachments", "count_beteiligungen", "count_uvps", "detail", "xplangml", "edit", "delete")


class FPlanTable(tables.Table):
    last_changed = tables.Column(verbose_name="Letzte Änderung")
    edit = tables.LinkColumn('fplan-update', verbose_name="", text='Bearbeiten', args=[A('pk')], \
                         orderable=False, empty_values=())
    delete = tables.LinkColumn('fplan-delete', verbose_name="", text='Löschen', args=[A('pk')], \
                         orderable=False, empty_values=())
    planart = tables.Column(verbose_name="Planart")
    zoom = tables.Column(verbose_name="", accessor='geltungsbereich', orderable=False, empty_values=())
    count_attachments = tables.Column(verbose_name="Anlagen", accessor='count_attachments', orderable=False)
    count_beteiligungen = tables.Column(verbose_name="Beteiligungen", accessor='count_beteiligungen', orderable=False)
    #count_uvps = tables.Column(verbose_name="UVPs", accessor='count_uvps', orderable=False)
    detail = tables.LinkColumn('fplan-detail', verbose_name='Details', text='Anzeigen', args=[A('pk')], \
                         orderable=False, empty_values=())
    # manytomany relations are handled automatically!
    #gemeinde = tables.Column(verbose_name="Gemeinde(n)", accessor='gemeinde', orderable=False)
    xplangml = tables.Column(verbose_name="XPlan-GML Hochgeladen", accessor='xplan_gml', empty_values=())

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
    
    def render_count_attachments(self, value, record):
        if value == 0:
            return format_html('<a href="' + reverse('fplanattachment-create', kwargs={'planid': record.id}) + '">' +  str(value) + '</a>')
        else:
            return format_html('<a href="' + reverse('fplanattachment-list', kwargs={'planid': record.id}) + '">' +  str(value) + '</a>')
        
    def render_count_beteiligungen(self, value, record):
        if value == 0:
            return format_html('<a href="' + reverse('fplanbeteiligung-create', kwargs={'planid': record.id}) + '">' +  str(value) + '</a>')
        else:
            return format_html('<a href="' + reverse('fplanbeteiligung-list', kwargs={'planid': record.id}) + '">' +  str(value) + '</a>')
    """    
    def render_count_uvps(self, value, record):
        if value == 0:
            return format_html('<a href="' + reverse('uvp-create', kwargs={'planid': record.id}) + '">' +  str(value) + '</a>')
        else:
            return format_html('<a href="' + reverse('uvp-list', kwargs={'planid': record.id}) + '">' +  str(value) + '</a>')
        
    """
    """
    geojson = Column(
        accessor=A('geojson'),
        orderable=False,
        # ...
    )
    """

    class Meta:
        model = FPlan
        template_name = "django_tables2/bootstrap5.html"
        fields = ( "zoom", "last_changed", "aufstellungsbeschluss_datum", "nummer", "name", "gemeinde", "planart", "count_attachments", "count_beteiligungen", "detail", "xplangml", "edit", "delete")



class AdministrativeOrganizationPublishingTable(tables.Table):
    num_bplan = tables.Column(verbose_name="Zahl BPläne")
    wms = tables.LinkColumn('ows', text='WMS', args=[A('pk')], \
                         orderable=False, empty_values=())
    wfs = tables.LinkColumn('ows', text='WFS', args=[A('pk')], \
                         orderable=False, empty_values=())
    ags = tables.Column(verbose_name="AGS", orderable=False)

    def render_ags(self, record):
        if record.ts:
            return format_html(record.ags + ' - ' + record.ts)
        else:
            return format_html(record.ags)
        
    def render_name(self, record):
        if record.name_part:
            return format_html(record.name + ' - ' + record.name_part)
        else:
            return format_html(record.name)

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