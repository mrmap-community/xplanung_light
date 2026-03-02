from django.http import HttpResponseRedirect
from xplanung_light.models import BPlanBeteiligung, FPlanBeteiligung, AdministrativeOrganization
from xplanung_light.tables import BeteiligungenTable, BeteiligungenOrgaTable
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.utils import timezone
from django.db.models import Count, F, Value, OuterRef, Subquery
from django.db.models.functions import Concat
from django_tables2 import SingleTableView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core import serializers
from django.db.models import JSONField, CharField, Func, Aggregate
from datetime import datetime
import json
#from django.db.models.aggregates import Aggregate

# https://stackoverflow.com/questions/74111981/django-aggregate-into-array
# TODO: for sqlite - für Postgres gibt es eigene Aggregatfunktionen!
class JsonGroupArray(Aggregate):
    function = 'JSON_GROUP_ARRAY'
    output_field = JSONField()
    template = '%(function)s(%(distinct)s%(expressions)s)'

"""
Nach KI-Recherche - Abstraktion für postgresql und sqlite
Eigentlich wird JSONAgg vorgeschlagen - ob JSONBAgg klappt müssen wir noch ausprobieren

"""
from django.contrib.postgres.aggregates import JSONBAgg
from django.db.models.functions import JSONObject
from django.db import connection


class SQLiteJSONGroupArray(Aggregate):
    function = "JSON_GROUP_ARRAY"
    output_field = JSONField()


class SQLiteJSONObject(Func):
    function = "json_object"


def sqlite_organization_aggregation(plantyp='bplan'):
    return SQLiteJSONGroupArray(
        SQLiteJSONObject(
            Value("id"), plantyp + "__gemeinde__id",
            Value("name"), plantyp + "__gemeinde__name",
        )
    )   

def postgres_organization_aggregation(plantyp='bplan'):
    return JSONBAgg(
        JSONObject(
            id = plantyp + "__gemeinde__id",
            name = plantyp + "__gemeinde__name",
        )
    )

def organization_json_aggregation(plantyp='bplan'):
    if connection.vendor == "postgresql":

        return postgres_organization_aggregation(plantyp)

    if connection.vendor == "sqlite":
        result = sqlite_organization_aggregation(plantyp)
        return result

    raise NotImplementedError


class BeteiligungenListView(SingleTableView):
    """
    Klasse zur Anzeige der laufenden BPlan- und FPlan-Verfahren einer Gebietskörperschaft.

    """
    template_name = "xplanung_light/beteiligungen.html"
    table_class = BeteiligungenTable

    def get_queryset(self):
        """
        Überschreiben von get_queryset um ein union verschiedener Modelle zu ermöglichen.
        
        :param self: Description
        """
        #if 'pk' in self.kwargs.keys():
        #    print("Got pk: " + str(self.kwargs['pk']))

        # Info: https://forum.djangoproject.com/t/group-concat-in-orm/21149
        # https://stackoverflow.com/questions/73668842/django-with-mysql-subquery-returns-more-than-1-row
        # https://djangosnippets.org/snippets/10860/
        #gemeinden_bplaene = AdministrativeOrganization.objects.filter(bplan__id=OuterRef("bplan__id"))
        #beteiligungen_bplaene_1 = BPlanBeteiligung.objects.filter(end_datum__gte=timezone.now()).filter(bekanntmachung_datum__lte=timezone.now(), bplan__public=True).distinct().annotate(xplan_name=F('bplan__name'), plantyp=Value('BPlan'), gemeinden=serializers.serialize('json', Subquery(gemeinden_bplaene)))
        #beteiligungen_bplaene_1 = BPlanBeteiligung.objects.filter(end_datum__gte=timezone.now()).filter(bekanntmachung_datum__lte=timezone.now(), bplan__public=True).distinct().annotate(xplan_name=F('bplan__name'), plantyp=Value('BPlan'), gemeinden=Subquery(gemeinden_bplaene))

        #beteiligungen_bplaene = BPlanBeteiligung.objects.filter(end_datum__gte=timezone.now()).filter(bekanntmachung_datum__lte=timezone.now(), bplan__public=True).distinct().annotate(xplan_name=F('bplan__name'), plantyp=Value('BPlan'), gemeinden=JsonGroupArray('bplan__gemeinde__name'))
        beteiligungen_bplaene = BPlanBeteiligung.objects.filter(end_datum__gte=timezone.now()).filter(bekanntmachung_datum__lte=timezone.now(), bplan__public=True).distinct().annotate(xplan_name=F('bplan__name'), plantyp=Value('BPlan'), xplan_id=F('bplan__id'), gemeinden=organization_json_aggregation())
        #beteiligungen_fplaene = FPlanBeteiligung.objects.filter(end_datum__gte=timezone.now()).filter(bekanntmachung_datum__lte=timezone.now(), fplan__public=True).distinct().annotate(xplan_name=F('fplan__name'), plantyp=Value('FPlan'), gemeinden=JsonGroupArray('fplan__gemeinde__name'))
        beteiligungen_fplaene = FPlanBeteiligung.objects.filter(end_datum__gte=timezone.now()).filter(bekanntmachung_datum__lte=timezone.now(), fplan__public=True).distinct().annotate(xplan_name=F('fplan__name'), plantyp=Value('FPlan'), xplan_id=F('fplan__id'), gemeinden=organization_json_aggregation(plantyp='fplan'))

        if not self.request.user.is_superuser and not self.request.user.is_anonymous:
            beteiligungen_bplaene = beteiligungen_bplaene.filter(bplan__gemeinde__organization_users__user=self.request.user, bplan__gemeinde__organization_users__is_admin=True)
            beteiligungen_fplaene = beteiligungen_fplaene.filter(fplan__gemeinde__organization_users__user=self.request.user, fplan__gemeinde__organization_users__is_admin=True)
        # Info:
        # union(), intersection(), and difference() return model instances of the type of the first QuerySet even if the arguments are QuerySets of other models. Passing different models works as long as the SELECT list is the same in all QuerySets (at least the types, the names don’t matter as long as the types in the same order).   
        # https://pythonguides.com/union-operation-on-models-django/
        beteiligungen_plaene = beteiligungen_bplaene.union(beteiligungen_fplaene).order_by('end_datum')
        return beteiligungen_plaene  
    

class BeteiligungenOrgaListView(BeteiligungenListView):
    template_name = "xplanung_light/organization_beteiligungen.html"
    table_class = BeteiligungenOrgaTable
    # Dynamic Forms with HTMX
    # https://www.youtube.com/watch?v=XdZoYmLkQ4w

    def get_queryset(self):
        if 'pk' in self.kwargs.keys():
            print("Got pk: " + str(self.kwargs['pk']))
        #self.publisher = get_object_or_404(Publisher, name=self.kwargs["publisher"])
        
        beteiligungen_bplaene = BPlanBeteiligung.objects.filter(
            bplan__gemeinde__id=self.kwargs['pk']
        ).filter(
            end_datum__gte=timezone.now(),
            bekanntmachung_datum__lte=timezone.now()
        ).annotate(
            xplan_name=F('bplan__name'),
            xplan_id=F('bplan__id'),
            plantyp=Value('BPlan')
        )
        #).annotate(
        #    count_comments=Count('comments', distinct=True)
        #)
        beteiligungen_fplaene = FPlanBeteiligung.objects.filter(
            fplan__gemeinde__id=self.kwargs['pk']
        ).filter(
            end_datum__gte=timezone.now(),
            bekanntmachung_datum__lte=timezone.now()
        ).annotate(
            xplan_name=F('fplan__name'),
            xplan_id=F('fplan__id'),
            plantyp=Value('FPlan')
        )
        #).annotate(
        #    count_comments=Count('comments', distinct=True)
        #)    

        # https://pythonguides.com/union-operation-on-models-django/
        beteiligungen_plaene = beteiligungen_bplaene.union(beteiligungen_fplaene).order_by('end_datum')

        for beteiligung in beteiligungen_plaene:
            print(beteiligung.plantyp + " - " + str(beteiligung.bekanntmachung_datum))
            #print(str(beteiligung.bekanntmachung_datum) + " - " + beteiligung.typ)
            #if beteiligung.plantyp == 'BPlan':
            #    print(beteiligung.bplan.gemeinde.all)
            #if beteiligung.plantyp == 'FPlan':
            #    print(beteiligung.fplan.gemeinde.all)    
        return beteiligungen_plaene  
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['gemeinde'] = AdministrativeOrganization.objects.get(pk=self.kwargs['pk'])
        return context
    
import copy, csv
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from django.http import FileResponse
from xplanung_light.models import BPlanBeteiligung, FPlanBeteiligung, BPlanBeteiligungBeitrag, FPlanBeteiligungBeitrag, BPlan, FPlan
from django.shortcuts import HttpResponse
from django.contrib.auth.decorators import login_required
from reportlab.platypus import BaseDocTemplate
from io import BytesIO
from django.views.generic import DetailView

class PdfBeteiligungBeitraege(BaseDocTemplate):
    """
    Klasse für das reportlab-Template zum Exportieren der Beteiligungsbeiträge nach PDF 
    """
    # https://stackoverflow.com/questions/39266415/dynamic-framesize-in-python-reportlab
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import styles 
    from reportlab.lib.units import cm, mm
    from reportlab.lib import colors
    from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, NextPageTemplate, Paragraph, PageBreak, Table, \
        TableStyle


    def __init__(self, filename, beteiligung, plantyp, **kwargs):
        super().__init__(filename, page_size=self.A4, _pageBreakQuick=0, **kwargs)
        self.beteiligung = beteiligung
        self.plantyp = plantyp
        # overwrite margins
        self.topMargin=45.0*self.mm
        self.leftMargin=25*self.mm
        self.rightMargin=20*self.mm
        self.bottomMargin=25*self.mm
        # https://stackoverflow.com/questions/637800/showing-page-count-with-reportlab
        self.final_pages = 1
        self.total_pages = 0
        self.pageinfo = "pageinfo"
        self.style = self.styles.getSampleStyleSheet()

        # Setting up the frames, frames are use for dynamic content not fixed page elements
        first_page_table_frame = self.Frame(self.leftMargin, self.bottomMargin + 10 * self.mm, 165 * self.mm, self.height - 10 * self.cm, id='small_table')
        later_pages_table_frame = self.Frame(self.leftMargin, self.bottomMargin + 10 * self.mm, 165 * self.mm, 217 * self.mm, id='large_table')

        # Creating the page templates
        first_page = self.PageTemplate(id='FirstPage', frames=[first_page_table_frame], onPage=self.on_first_page)
        later_pages = self.PageTemplate(id='LaterPages', frames=[later_pages_table_frame], onPage=self.add_default_info)
        self.addPageTemplates([first_page, later_pages])

        # Tell Reportlab to use the other template on the later pages,
        # by the default the first template that was added is used for the first page.
        story = [self.NextPageTemplate(['*', 'LaterPages'])]
        
        #table_grid = [["Pos.", "Beschreibung", "Menge", "Einheit", "EP(€)", "GP(€)"]]
        table_grid = [["Lfd. Nr.", "Datum/Zeit", "Titel", "EMail", "# Anlagen"]]
        # Add the objects
        if plantyp=='bplan':
            beteiligung_beitraege = BPlanBeteiligungBeitrag.objects.filter(bplan_beteiligung=beteiligung).annotate(
                    last_changed=Subquery(
                        BPlanBeteiligungBeitrag.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
                    ),
                    count_attachments=Count('attachments', distinct=True)
                )
        if plantyp=='fplan':
            beteiligung_beitraege = FPlanBeteiligungBeitrag.objects.filter(fplan_beteiligung=beteiligung).annotate(
                    last_changed=Subquery(
                        FPlanBeteiligungBeitrag.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
                    ),
                    count_attachments=Count('attachments', distinct=True)
                )
        description_paragraph_style = copy.deepcopy(self.style['Normal'])
        description_paragraph_style.alignment = 0
        description_paragraph_style.fontSize = 8
        for beteiligung_beitrag in beteiligung_beitraege:
            table_grid.append([beteiligung_beitrag.id, beteiligung_beitrag.last_changed.strftime('%Y-%m-%d %H:%M'), self.Paragraph(beteiligung_beitrag.titel, description_paragraph_style), beteiligung_beitrag.email, beteiligung_beitrag.count_attachments])
        total_paragraph_style = copy.deepcopy(self.style['Normal'])
        total_paragraph_style.alignment = 2
        total_paragraph_style.fontSize = 8
        story.append(self.Table(table_grid, repeatRows=1, colWidths=[0.10 * 165 * self.mm,  0.17 * 165 * self.mm, 0.20 * 165 * self.mm, 0.25 * 165 * self.mm, 0.10 * 165 * self.mm],#, 0.15 * 165 * self.mm],
                           style=self.TableStyle([('GRID',(0,1),(-1,-1), 0.25, self.colors.gray),
                                             ('BOX', (0,0), (-1,-1), 1.0, self.colors.black),
                                             #('BOX', (0,0), (1,0), 1.0, self.colors.black),
                                             #('BOX', (0,0), (1,0), 1.0, self.colors.black),
                                             ('ALIGN', (0,0), (-1,0), 'CENTER'), # first row - header
                                             ('ALIGN', (0,1), (0,-1), 'CENTER'), # first column from second row
                                             ('ALIGN', (1,1), (1,-1), 'LEFT'), # second column from second row
                                             ('ALIGN', (2,1), (2,-1), 'RIGHT'), 
                                             ('ALIGN', (3,1), (3,-1), 'CENTER'), 
                                             ('ALIGN', (4,1), (4,-1), 'RIGHT'), 
                                             #('ALIGN', (5,1), (5,-1), 'RIGHT'),
                                             #('LINEBELOW', (-1,-1), (-1,-1), 1, self.colors.black),
                                             #('ALIGN', (0,1), (-1,-1), 'RIGHT'), # first column, second row: all rows from second row
                                             ('FONTSIZE', (0,1), (-1,-1), 8),
                                             ])))
        """
        # Ggf. Statistiken unterhalb der Tabelle anzeigen lassen 
        table_sum = []
        table_sum.append(["", "", "",  "Summe:", "", "{:.2f}".format(sum_invoice) + " €"])
        table_sum.append(["", "", "",  "Steuer:", "", "+ " + "{:.2f}".format(sum_tax) + " €"])
        table_sum.append(["", "", "",  "Brutto:", "", "{:.2f}".format(sum_b) + " €"])
        table_sum.append(["", "", "",  "abgerechnet:", "", "- " + "{:.2f}".format(invoice.prepaid_amount) + " €"])
        table_sum.append(["", "", "",  "Rechnungsbetrag:" , "", self.Paragraph("<b>" + "{:.2f}".format(to_pay) + " €</b>", total_paragraph_style)])
        story.append(self.Table(table_sum, repeatRows=0, colWidths=[0.10 * 165 * self.mm,  0.40 * 165 * self.mm, 0.10 * 165 * self.mm, 0.15 * 165 * self.mm, 0.10 * 165 * self.mm, 0.15 * 165 * self.mm],
                           style=self.TableStyle([
                                             ('ALIGN', (0,0), (0,-1), 'CENTER'), # first column from second row
                                             ('ALIGN', (1,0), (1,-1), 'LEFT'), # second column from second row
                                             ('ALIGN', (2,0), (2,-1), 'RIGHT'), 
                                             ('ALIGN', (3,0), (3,-1), 'LEFT'), 
                                             ('ALIGN', (4,0), (4,-1), 'RIGHT'), 
                                             ('ALIGN', (5,0), (5,-1), 'RIGHT'),
                                             ('FONTSIZE', (0,0), (-1,-1), 8),
                                             ])))
        # append sums
        sum_paragraph_style = copy.deepcopy(self.style['Normal'])
        sum_paragraph_style.fontSize = 10
        sum_paragraph = self.Paragraph("<b>Zahlungsfrist:</b> " + str(invoice.due_date) + "<br/><b>Zahlungsbedingungen:</b> " + invoice.payment_terms, sum_paragraph_style)
        sum_paragraph.hAlign = 'RIGHT'
        story.append(sum_paragraph)
        """
        self.build(copy.deepcopy(story))
        self.final_pages = self.total_pages
        self.build(copy.deepcopy(story))

    def on_first_page(self, canvas, doc):
        canvas.saveState()
        # Add the logo and other default stuff
        self.add_default_info(canvas, doc)
        #logo_frame = self.Frame(127*self.mm, 252*self.mm, 63*self.mm, 35*self.mm, showBoundary=1)
        #if self.invoice.my_party.party_logo: 
        #    canvas.drawImage(self.invoice.my_party.party_logo.path, 127*self.mm, 252*self.mm, width=63*self.mm, height=35*self.mm)
            #print("Path of logo image: " + str(self.invoice.my_party.party_logo.path))

        #logo_frame.drawBoundary(canvas)
        # 5 lines small 8pt
        # 6 lines big / normal
        # Adressfeld einer DIN-Rechnung
        """
        address_frame = self.Frame(25*self.mm, 207*self.mm, 85*self.mm, 45*self.mm, showBoundary=0)
        address_content = "<font size=8>" + self.invoice.my_party.party_name + " | "
        address_content = address_content + self.invoice.my_party.party_postal_address.street_name + " | "
        address_content = address_content + "" + self.invoice.my_party.party_postal_address.postal_zone + " "
        address_content = address_content + self.invoice.my_party.party_postal_address.city_name + "<br/>"
        address_content = address_content + "Wenn unzustellbar, bitte mit neuer Anschrift zurück<br/>"
        address_content = address_content + "<br/></font>"
        address_content = address_content + self.invoice.customer_party.party_name + "<br/>" 
        address_content = address_content + self.invoice.customer_party.party_postal_address.street_name + "<br/>"
        address_content = address_content + "<b>" + self.invoice.customer_party.party_postal_address.postal_zone + "</b> " + self.invoice.customer_party.party_postal_address.city_name
        address_paragraph_style = self.style['Normal']
        address_flowable = self.Paragraph(address_content, address_paragraph_style)
        address_story = []
        address_story.append(address_flowable)
        address_frame.addFromList(address_story, canvas)
        """
        # Informationen zum Projekt - hier Beteiligung, Plan , ...
        content_info_frame = self.Frame(125*self.mm, 192*self.mm, 75*self.mm, 55*self.mm, showBoundary=0)   
        if self.plantyp=='bplan':
            content_info_content = "<font size=10><b>" + self.beteiligung.get_typ_display() + " zum Bebauungsplan</b><br/>"
            content_info_content = content_info_content + "\"" + self.beteiligung.bplan.name + "\"<br/>"
        if self.plantyp=='fplan':
            content_info_content = "<font size=10><b>" + self.beteiligung.get_typ_display() + " zum Flächennutzungsplan</b><br/>"
            content_info_content = content_info_content + "\"" + self.beteiligung.fplan.name + "\"<br/>" 
        # typ
        content_info_content = content_info_content + "<b>Bekanntmachung:</b> " + str(self.beteiligung.bekanntmachung_datum.strftime('%Y-%m-%d %H:%M')) + "<br/>" 
        content_info_content = content_info_content + "<b>Beginn Beteiligung:</b> " + str(self.beteiligung.start_datum.strftime('%Y-%m-%d %H:%M')) + "<br/>"
        content_info_content = content_info_content + "<b>Ende Beteiligung:</b> " + str(self.beteiligung.end_datum.strftime('%Y-%m-%d %H:%M')) + "<br/></font>" 
        #content_info_content = content_info_content + "<b>E-Mail:</b> " + self.invoice.my_party.party_contact_person_email + "<br/>" 
        #content_info_content = content_info_content + "<b>Telefon:</b> " + self.invoice.my_party.party_contact_person_phone + "<br/><br/>"
        #content_info_content = content_info_content + "<b>Projekt-ID:</b> " + self.invoice.project_reference_id + "<br/>" 
        #content_info_content = content_info_content + "<b>Leitweg-ID:</b> " + self.invoice.buyer_reference + "<br/>" 
        #content_info_content = content_info_content + "<b>Bestellreferenz:</b> " + self.invoice.order_reference + "<br/></font>" 
        content_info_paragraph_style = self.style['Normal']
        content_info_flowable = self.Paragraph(content_info_content, content_info_paragraph_style)
        content_info_story = []
        content_info_story.append(content_info_flowable)
        content_info_frame.addFromList(content_info_story, canvas)
        """
        content_info_frame = self.Frame(125*self.mm, 192*self.mm, 75*self.mm, 55*self.mm, showBoundary=0)   
        content_info_content = "<font size=10><b>" + self.invoice.my_party.party_name + "</b><br/>"
        content_info_content = content_info_content + "<b>Rechnungsnummer:</b> " + self.invoice.identifier + "<br/>" 
        content_info_content = content_info_content + "<b>Rechnungsdatum:</b> " + str(self.invoice.issue_date) + "<br/><br/>"
        content_info_content = content_info_content + "<b>Ansprechpartner:</b> " + self.invoice.my_party.party_contact_person_name + "<br/>" 
        content_info_content = content_info_content + "<b>E-Mail:</b> " + self.invoice.my_party.party_contact_person_email + "<br/>" 
        content_info_content = content_info_content + "<b>Telefon:</b> " + self.invoice.my_party.party_contact_person_phone + "<br/><br/>"
        content_info_content = content_info_content + "<b>Projekt-ID:</b> " + self.invoice.project_reference_id + "<br/>" 
        content_info_content = content_info_content + "<b>Leitweg-ID:</b> " + self.invoice.buyer_reference + "<br/>" 
        content_info_content = content_info_content + "<b>Bestellreferenz:</b> " + self.invoice.order_reference + "<br/></font>" 
        content_info_paragraph_style = self.style['Normal']
        content_info_flowable = self.Paragraph(content_info_content, content_info_paragraph_style)
        content_info_story = []
        content_info_story.append(content_info_flowable)
        content_info_frame.addFromList(content_info_story, canvas)
        """
        table_header_frame = self.Frame(self.leftMargin, self.height - 47 * self.mm, self.width - (self.leftMargin + self.rightMargin), 10*self.mm, showBoundary=0)  
        table_header_paragraph_style = self.style['Normal']
        table_header_flowable = self.Paragraph("<font size=14><b>Online-Beteiligungsbeiträge</b></font>", table_header_paragraph_style)
        table_header_story = []
        table_header_story.append(table_header_flowable)
        table_header_frame.addFromList(table_header_story, canvas)

        canvas.restoreState()

    def afterPage(self):
        self.total_pages += 1  # Increment page count after each page is built
        super().afterPage()  # Call the superclass method

    def add_default_info(self, canvas, doc):
        canvas.saveState()

        page_number_content = f'Seite {doc.page} von {self.final_pages}'
        # draw pagenumbers as textobject
        # https://www.blog.pythonlibrary.org/2018/02/06/reportlab-101-the-textobject/
        # Create textobject
        textobject = canvas.beginText()
        # Set text location (x, y)
        textobject.setTextOrigin(170*self.mm, 33*self.mm)
        # Set font face and size
        textobject.setFont('Helvetica', 9)
        textobject.textLine(text=page_number_content)
        # Write text to the canvas
        canvas.drawText(textobject)
        canvas.line(25*self.mm, 30*self.mm, 195*self.mm, 30*self.mm)
        """
        footer_frame = self.Frame(25*self.mm, 12*self.mm, 165*self.mm, 17*self.mm, showBoundary=0)
        footer_content = "<font size=8><b>" + self.invoice.my_party.party_name + "</b> | "
        footer_content = footer_content + self.invoice.my_party.party_postal_address.city_name + " | "
        footer_content = footer_content + "<b>E-Mail:</b> " + self.invoice.my_party.party_contact_email + " | "
        footer_content = footer_content + "<b>BIC:</b> " + self.invoice.my_party.party_payment_financial_institution_id + " | "
        footer_content = footer_content + "<b>IBAN:</b> " + self.invoice.my_party.party_payment_financial_account_id + " | "
        footer_content = footer_content + "<b>Kontoinhaber:</b> " + self.invoice.my_party.party_payment_financial_account_name + "</font>"
        footer_paragraph_style = self.style['Normal']
        footer_flowable = self.Paragraph(footer_content, footer_paragraph_style)
        footer_story = []
        footer_story.append(footer_flowable)
        footer_frame.addFromList(footer_story, canvas)
        """
        canvas.restoreState()


class BeteiligungPdfView(DetailView):
    model = None
    planmodel = None
    beteiligung = None
    plantyp = None

    def dispatch(self, request, *args, **kwargs):
        # Hier sind die Parameter aus der re_path verfügbar:
        self.plantyp = kwargs.get('plantyp')
        print(str(self.plantyp))
        if self.plantyp == 'bplan':
            self.model = BPlanBeteiligung
            self.planmodel = BPlan
        if self.plantyp == 'fplan':
            self.model = FPlanBeteiligung
            self.planmodel = FPlan
        self.beteiligung = self.model.objects.get(pk=kwargs['beteiligungid'])
        self.plan = self.planmodel.objects.get(pk=kwargs['planid'])
        print(self.beteiligung)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if self.beteiligung:
            pdf_buffer = BytesIO()
            # Starte Generierung
            PdfBeteiligungBeitraege(pdf_buffer, beteiligung=self.beteiligung, plantyp=self.plantyp)
            pdf_buffer.seek(0)
            response = FileResponse(pdf_buffer, 
                            as_attachment=True, 
                            filename='beteiligung_' + str(self.beteiligung.id) + '.pdf')
            return response
        else:
            return HttpResponse("Object not found", status=404)


