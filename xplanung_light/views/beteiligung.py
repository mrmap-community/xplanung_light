from __future__ import annotations
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
#from reportlab.pdfgen import canvas
from django.http import HttpResponse
from django.http import FileResponse
from xplanung_light.models import BPlanBeteiligung, FPlanBeteiligung, BPlanBeteiligungBeitrag, FPlanBeteiligungBeitrag, BPlan, FPlan
from django.shortcuts import HttpResponse
from django.contrib.auth.decorators import login_required
#from reportlab.platypus import BaseDocTemplate
from io import BytesIO
from django.views.generic import DetailView



# Imports für pydantic und reportlab-Konverter
import uuid
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, BaseDocTemplate, Paragraph, Spacer, HRFlowable, 
    ListFlowable, ListItem, PageBreak
)
from reportlab.lib.units import cm, mm
from reportlab.lib.pagesizes import A4
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Frame, PageTemplate, NextPageTemplate, Paragraph, Table, TableStyle

# TipTap Logikmodell für pydantic
class TipTapMark(BaseModel):
    type: str
    attrs: Optional[Dict[str, Any]] = None


class TipTapNode(BaseModel):
    type: str
    attrs: Optional[Dict[str, Any]] = Field(default_factory=dict)
    content: Optional[List[TipTapNode]] = None
    text: Optional[str] = None
    marks: Optional[List[TipTapMark]] = None

TipTapNode.model_rebuild()


class TipTapToReportLab:
    """
    Klasse um ein TipTap json in ein Reportlab-Objekt zu überführen
    """
    def __init__(self):
        self.styles = getSampleStyleSheet()

    def convert_to_elements(self, doc_node: TipTapNode) -> List[Any]:
        elements = []
        if doc_node.content:
            for child in doc_node.content:
                res = self._process_node(child)
                if res: elements.extend(res if isinstance(res, list) else [res])
        return elements

    def _process_node(self, node: TipTapNode):
        handlers = {"paragraph": self._handle_paragraph, 
                    "heading": self._handle_heading, 
                    "bulletList": self._handle_list, 
                    "horizontalRule": lambda n: [HRFlowable(width="100%"), Spacer(1, 0.4*cm)]}
        handler = handlers.get(node.type)
        return handler(node) if handler else None

    def _get_styled_text(self, nodes: Optional[List[TipTapNode]]) -> str:
        if not nodes: return ""
        result = ""
        for n in nodes:
            if n.type == "text" and n.text:
                t = n.text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                if n.marks:
                    for m in n.marks:
                        if m.type == "bold": t = f"<b>{t}</b>"
                        elif m.type == "italic": t = f"<i>{t}</i>"
                        elif m.type == "link":
                            href = m.attrs.get("href", "#") if m.attrs else "#"
                            t = f'<a href="{href}" color="blue"><u>{t}</u></a>'
                result += t
        return result

    def _handle_heading_old(self, node: TipTapNode):
        level = node.attrs.get("level", 1) if node.attrs else 1
        raw_text = self._get_styled_text(node.content)
        style = self.styles.get(f"Heading{level}", self.styles["Heading1"])
        
        # KEY-GENERIERUNG
        bookmark_key = f"target_{uuid.uuid4().hex[:6]}"
        
        # DER TRICK: Wir betten einen Anker-Tag im Text ein
        anchored_text = f'<a name="{bookmark_key}"/>{raw_text}'
        p = Paragraph(anchored_text, style)
        
        # Metadaten für MyDocTemplate - TODO: wird aktuell nicht genutzt
        p.bookmarkKey = bookmark_key
        p.tocText = raw_text
        p.tocLevel = level - 1
        
        return [p, Spacer(1, 0.3*cm)]

    def _handle_heading(self, node: TipTapNode):
        level = node.attrs.get("level", 1) if node.attrs else 1
        raw_text = self._get_styled_text(node.content)
        
        # Fallback, falls Heading-Level nicht im Stylesheet existiert
        style_name = f"Heading{level}"
        if style_name not in self.styles:
            style_name = "Heading2" # Fallback auf Heading 2
        
        style = self.styles[style_name]
        # TODO: wird aktuell nicht genutzt
        bookmark_key = f"target_{uuid.uuid4().hex[:6]}"
        anchored_text = f'<a name="{bookmark_key}"/>{raw_text}'
        p = Paragraph(anchored_text, style)
        
        p.bookmarkKey = bookmark_key
        p.tocText = raw_text
        p.tocLevel = level - 1
        
        return [p, Spacer(1, 0.3*cm)]

    def _handle_paragraph(self, node: TipTapNode):
        return [Paragraph(self._get_styled_text(node.content), self.styles["Normal"]), Spacer(1, 0.2*cm)]

    def _handle_list(self, node: TipTapNode):
        items = []
        for li in (node.content or []):
            # Alle Flowables eines ListItems sammeln (z.B. Paragraph + Spacer)
            li_elements = []
            if li.content:
                for child in li.content:
                    res = self._process_node(child)
                    if res:
                        # Sicherstellen, dass wir eine flache Liste von Flowables haben
                        li_elements.extend(res if isinstance(res, list) else [res])
            
            # Ein ListItem mit den gesammelten Flowables erstellen
            items.append(ListItem(li_elements))

        # bulletType 'bullet' für BulletList, '1' für OrderedList
        return [ListFlowable(items, bulletType='bullet', leftIndent=20), Spacer(1, 0.2*cm)]
    
    def _handle_list_old(self, node: TipTapNode):
        items = [ListItem([self._process_node(c) for c in (li.content or [])]) for li in (node.content or [])]
        return [ListFlowable(items, bulletType='bullet', leftIndent=20), Spacer(1, 0.2*cm)]


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        width, height = A4
        line_y = 2.0 * cm  # Höhe der Linie
        text_y = 1.5 * cm  # Höhe des Textes darunter
        # 1. Die Linie oberhalb des Footers
        self.setLineWidth(0.5)
        self.line(2*cm, line_y, width - 2*cm, line_y)
        self.setFont("Helvetica", 9)
        self.drawCentredString(A4[0]/2, 1*cm, f"Seite {self._pageNumber} von {page_count}")


class MyDocTemplate(SimpleDocTemplate):
    pass
"""    
    def afterFlowable(self, flowable):
        
        if isinstance(flowable, Paragraph) and hasattr(flowable, 'bookmarkKey'):
            # notify(level, text, page, key)
            self.notify('TOCEntry', (flowable.tocLevel, flowable.tocText, self.page, flowable.bookmarkKey))
            # Sidebar-Bookmark direkt im Canvas setzen
            self.canv.addOutlineEntry(flowable.tocText, flowable.bookmarkKey, level=flowable.tocLevel)
"""


# TODO: Noch nicht benötigt - ggf. wenn wir das Navigationsmenu brauchen - scheint bei der reportlab Version von debian 11 etwas tricky zu sein
TOC_REGISTRY = {}


class FinalCanvas(canvas.Canvas):
    """
    Aktuell nicht verwendet
    """
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)

    def showPage(self):
        # Seitenzahl für Footer
        self.setFont("Helvetica", 9)
        self.drawCentredString(A4[0]/2, 1.5*cm, f"Seite {self._pageNumber}")
        canvas.Canvas.showPage(self)


class HeadingWithAnchor(Paragraph):
    """
    Aktuell nicht verwendet
    """
    def __init__(self, text, style, key):
        super().__init__(f'<a name="{key}"/>{text}', style)
        self.key = key
        self.text_content = text

    def draw(self):
        # WICHTIG: Hier wird die ECHTE Seitenzahl während des Zeichnens erfasst
        curr_page = self.canv.getPageNumber()
        TOC_REGISTRY[self.key] = {
            'page': curr_page,
            'text': self.text_content
        }
        
        # Den Punkt im PDF markieren
        self.canv.bookmarkPage(self.key)
        self.canv.addOutlineEntry(self.text_content, self.key, level=0)
        super().draw()


class PdfBeteiligungBeitraege(MyDocTemplate):
    def __init__(self, filename, beteiligung, plantyp, **kwargs):
        super().__init__(filename, **kwargs)
        self.beteiligung = beteiligung
        self.plantyp = plantyp
        # Dinge die wir für das Layout brauchen
        styles = getSampleStyleSheet()
        self.style = styles
        story = []

        # TOC STYLE (WICHTIG: linkToItem=1)
        toc = TableOfContents()
        ps = ParagraphStyle(name='TOC', fontSize=10, textColor=colors.blue, linkToItem=1)
        toc.levelStyles = [ps, ps, ps]
        # STORY BAUEN
        # A. Rahmen / Header / Footer
        # 1. Allgemeine Informationen zum Beteiligungsverfahren
         # Dummy Content Seite 1
        story.append(Paragraph("Informationen zum Beteiligungsverfahren - ...", styles['Heading1']))
        # Informationen zum Projekt - hier Beteiligung, Plan , ...
        content_info_frame = Frame(125*mm, 192*mm, 75*mm, 55*mm, showBoundary=0)   
        if self.plantyp=='bplan':
            content_info_content = "<font size=10><b>" + self.beteiligung.get_typ_display() + " zum Bebauungsplan</b><br/>"
            content_info_content = content_info_content + "\"" + self.beteiligung.bplan.name + "\"<br/>"
        if self.plantyp=='fplan':
            content_info_content = "<font size=10><b>" + self.beteiligung.get_typ_display() + " zum Flächennutzungsplan</b><br/>"
            content_info_content = content_info_content + "\"" + self.beteiligung.fplan.name + "\"<br/>" 
        # typ
        content_info_content = content_info_content + "<b>Bekanntmachung:</b> " + str(self.beteiligung.bekanntmachung_datum.strftime('%Y-%m-%d')) + "<br/>" 
        content_info_content = content_info_content + "<b>Beginn Beteiligung:</b> " + str(self.beteiligung.start_datum.strftime('%Y-%m-%d')) + "<br/>"
        content_info_content = content_info_content + "<b>Ende Beteiligung:</b> " + str(self.beteiligung.end_datum.strftime('%Y-%m-%d')) + "<br/></font>" 
        #content_info_content = content_info_content + "<b>E-Mail:</b> " + self.invoice.my_party.party_contact_person_email + "<br/>" 
        #content_info_content = content_info_content + "<b>Telefon:</b> " + self.invoice.my_party.party_contact_person_phone + "<br/><br/>"
        #content_info_content = content_info_content + "<b>Projekt-ID:</b> " + self.invoice.project_reference_id + "<br/>" 
        #content_info_content = content_info_content + "<b>Leitweg-ID:</b> " + self.invoice.buyer_reference + "<br/>" 
        #content_info_content = content_info_content + "<b>Bestellreferenz:</b> " + self.invoice.order_reference + "<br/></font>" 
        content_info_paragraph_style = self.style['Normal']
        content_info_flowable = Paragraph(content_info_content, content_info_paragraph_style)
        story.append(content_info_flowable)
        story.append(HRFlowable(color='#ff0066', dash=(10, 5)))
        doc_model = TipTapNode.model_validate(beteiligung.beschreibung)
        elements = TipTapToReportLab().convert_to_elements(doc_model)
        story.extend(elements)
        story.append(PageBreak())
        # 2. Liste mit den abgegebenen Online-Beteiligungen
        story.append(Paragraph("Online-Beteiligungen - ...", styles['Heading1']))
        # 3. Einzelne Beteiligungsbeiträge 
        # 4. Anlagen ... ggf. in pdf einbetten oder in Form einer ZIP-Datei exportieren
        # Tabelle mit den abgegebenen Online-Beteiligungen:
        table_grid = [["Lfd. Nr.", "Datum/Zeit", "Titel", "EMail", "# Anlagen"]]
        # Selektion der Objekte
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
            table_grid.append([beteiligung_beitrag.id, beteiligung_beitrag.last_changed.strftime('%Y-%m-%d %H:%M'), Paragraph(beteiligung_beitrag.titel, description_paragraph_style), beteiligung_beitrag.email, beteiligung_beitrag.count_attachments])
        total_paragraph_style = copy.deepcopy(self.style['Normal'])
        total_paragraph_style.alignment = 2
        total_paragraph_style.fontSize = 8
        story.append(Table(table_grid, repeatRows=1, colWidths=[0.10 * 165 * mm,  0.17 * 165 * mm, 0.20 * 165 * mm, 0.25 * 165 * mm, 0.10 * 165 * mm],#, 0.15 * 165 * self.mm],
                           style=TableStyle([('GRID',(0,1),(-1,-1), 0.25, colors.gray),
                                             ('BOX', (0,0), (-1,-1), 1.0, colors.black),
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
        story.append(PageBreak())
        self.multiBuild(story, canvasmaker=NumberedCanvas)

    def build_story(data_list, mode="final"):
        """
        Nur ein Test - aktuell nicht verwendet!
        """
        styles = getSampleStyleSheet()
        story = []
        
        # --- INHALTSVERZEICHNIS ---
        story.append(Paragraph("Inhaltsverzeichnis", styles['Heading1']))
        story.append(Spacer(1, 10))
        
        if mode == "discovery":
            # Im ersten Lauf wissen wir die Seiten noch nicht -> Platzhalter
            story.append(Spacer(1, 5*cm))
        else:
            # Im zweiten Lauf nutzen wir die gefüllte TOC_REGISTRY
            for key in [item['id'] for item in data_list]:
                if key in TOC_REGISTRY:
                    entry = TOC_REGISTRY[key]
                    link = f'<a href="#{key}" color="blue">{entry["text"]}</a>'
                    # Rechtsbündige Seitenzahl via Tabulator-Simulation (oder Tabelle)
                    story.append(Paragraph(f"{link} .......................... Seite {entry['page']}", styles['Normal']))
        story.append(PageBreak())
         # --- CONTENT ---
        for item in data_list:
            story.append(HeadingWithAnchor(item['title'], styles['Heading1'], item['id']))
            story.append(Paragraph(item['content'], styles['Normal']))
            story.append(PageBreak())
        return story
    

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


