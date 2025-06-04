from django.db import models
from django.contrib.auth.models import User
import uuid, os
from simple_history.models import HistoricalRecords
from django.contrib.gis.db import models
import slugify

# generic meta model
class GenericMetadata(models.Model):
    generic_id = models.UUIDField(default = uuid.uuid4)
    #created = models.DateTimeField(null=True)
    #changed = models.DateTimeField(null=True)
    #deleted = models.DateTimeField(null=True)
    #active = models.BooleanField(default=True)
    #owned_by_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)

    class Meta:
        abstract = True

    """def save(self, *args, **kwargs):
        self.owned_by_user= self.request.user
        super().save(*args, **kwargs)"""


# administrative organizations
class AdministrativeOrganization(GenericMetadata):

    COUNTY = "KR"
    COUNTY_FREE_CITY = "KFS"
    COM_ASS = "VG"
    COM_ASS_FREE_COM = "VFG"
    COM = "GE"
    UNKNOWN = "UK"

    ADMIN_CLASS_CHOICES = [
        (COUNTY,  "Landkreis"),
        (COUNTY_FREE_CITY, "Kreisfreie Stadt"),
        (COM_ASS, "Verbandsgemeinde"),
        (COM_ASS_FREE_COM, "Verbandsfreie Gemeinde"),
        (COM, "Gemeinde/Stadt"),
        (UNKNOWN, "unbekannt"),
    ]

    ls = models.CharField(max_length=2, verbose_name='Landesschlüssel', help_text='Eindeutiger zweistelliger Schlüssel für das Bundesland - RLP: 07', default='07')
    ks = models.CharField(max_length=3, verbose_name='Kreisschlüssel', help_text='Eindeutiger dreistelliger Schlüssel für den Landkreis', default='000')
    vs = models.CharField(blank=True, null=True, max_length=2, verbose_name='Gemeindeverbandsschlüssel', help_text='Eindeutiger zweistelliger Schlüssel für den Gemeindeverband', default='00')
    gs = models.CharField(max_length=3, verbose_name='Gemeindeschlüssel', help_text='Eindeutiger dreistelliger Schlüssel für die Gemeinde', default='000')
    name = models.CharField(max_length=1024, verbose_name='Name der Gebietskörperschaft', help_text='Offizieller Name der Gebietskörperschaft - z.B. Rhein-Lahn-Kreis')
    type = models.CharField(max_length=3, choices=ADMIN_CLASS_CHOICES, default='UK', verbose_name='Typ der Gebietskörperschaft', db_index=True)
    address_street = models.CharField(blank=True, null=True, max_length=1024, verbose_name='Straße mit Hausnummer', help_text='Straße und Hausnummer')
    address_postcode = models.CharField(blank=True, null=True, max_length=5, verbose_name='Postleitzahl', help_text='Postleitzahl')
    
    address_city = models.CharField(max_length=256, blank=True, null=True, verbose_name='Stadt')
    address_phone = models.CharField(max_length=256, blank=True, null=True, verbose_name='Telefon')
    address_facsimile = models.CharField(max_length=256, blank=True, null=True, verbose_name='Fax')
    address_email = models.EmailField(max_length=512, blank=True, null=True, verbose_name='EMail')
    address_homepage = models.URLField(blank=True, null=True, verbose_name='Homepage')
    geometry = models.GeometryField(blank=True, null=True, verbose_name='Gebiet')
    history = HistoricalRecords()

    @property
    def ags_10(self):
        return self.ls + self.ks + self.vs + self.gs
    
    @property
    def ags(self):
        return self.ls + self.ks + self.gs

    def __str__(self):
        """Returns a string representation of a administrative unit."""
        return f"{self.name} ({self.get_type_display()})"
    

"""
https://xleitstelle.de/releases/objektartenkatalog_6_0
"""
class XPlan(GenericMetadata):

    # https://gist.github.com/chhantyal/5370749
    # Aktuell nicht verwendet - Dateien werden in DB abgelegt
    def get_upload_path(self, filename):
        name, ext = os.path.splitext(filename)
        return os.path.join('uploads', 'gml' , str(self.generic_id) + "_" + slugify(name)) + ext

    name = models.CharField(null=False, blank=False, max_length=2048, verbose_name='Name des Plans', help_text='Offizieller Name des raumbezogenen Plans')
    #nummer [0..1]
    nummer = models.CharField(max_length=5, verbose_name="Nummer des Plans.")
    #internalId [0..1]
    #beschreibung [0..1]
    #kommentar [0..1]
    #technHerstellDatum [0..1], Date
    #genehmigungsDatum [0..1], Date
    #untergangsDatum [0..1], Date
    #aendertPlan [0..*], XP_VerbundenerPlan
    #wurdeGeaendertVonPlan [0..*], XP_VerbundenerPlan
    #aendertPlanBereich [0..*], Referenz, Testphase
    #wurdeGeaendertVonPlanBereich [0..*], Referenz, Testphase
    #erstellungsMassstab [0..1], Integer
    #bezugshoehe [0..1], Length
    #hoehenbezug [0..1]
    #technischerPlanersteller, [0..1]
    #raeumlicherGeltungsbereich [1], GM_Object
    geltungsbereich = models.GeometryField(null=False, blank=False, verbose_name='Grenze des räumlichen Geltungsbereiches des Plans.')
    #verfahrensMerkmale [0..*], XP_VerfahrensMerkmal
    #hatGenerAttribut [0..*], XP_GenerAttribut
    #externeReferenz, [0..*], XP_SpezExterneReferenz
    #texte [0..*], XP_TextAbschnitt
    #begruendungsTexte [0..*], XP_BegruendungAbschnitt
    history = HistoricalRecords(inherit=True)

    xplan_gml = models.FileField(null = True, blank = True, verbose_name="XPlan GML-Dokument", help_text="")
    xplan_gml_version = models.CharField(null=True, blank=True, max_length=5, verbose_name='XPlan GML-Dokument Version', help_text='')

    class Meta:
        abstract = True


class BPlan(XPlan):

    BPLAN = "1000"
    EINFACHERBPLAN = "10000"
    QUALIFIZIERTERBPLAN = "10001"
    BEBAUUNGSPLANZURWOHNRAUMVERSORGUNG = "10002"
    VORHABENBEZOGENERBPLAN = "3000"
    VORHABENUNDERSCHLIESSUNGSPLAN = "3100"
    INNENBEREICHSSATZUNG = "4000"
    KLARSTELLUNGSSATZUNG = "40000"
    ENTWICKLUNGSSATZUNG = "40001"
    ERGAENZUNGSSATZUNG = "40002"
    AUSSENBEREICHSSATZUNG = "5000"
    OERTLICHEBAUVORSCHRIFT = "7000"
    SONSTIGES = "9999"

    BPLAN_TYPE_CHOICES = [
        (BPLAN,  "BPlan"),
        (EINFACHERBPLAN, "EinfacherBPlan"),
        (QUALIFIZIERTERBPLAN, "QualifizierterBPlan"),
        (BEBAUUNGSPLANZURWOHNRAUMVERSORGUNG, "BebauungsplanZurWohnraumversorgung"),
        (VORHABENBEZOGENERBPLAN, "VorhabenbezogenerBPlan"),
        (VORHABENUNDERSCHLIESSUNGSPLAN, "VorhabenUndErschliessungsplan"),
        (INNENBEREICHSSATZUNG, "InnenbereichsSatzung"),
        (KLARSTELLUNGSSATZUNG, "KlarstellungsSatzung"),
        (ENTWICKLUNGSSATZUNG, "EntwicklungsSatzung"),
        (ERGAENZUNGSSATZUNG, "ErgaenzungsSatzung"),
        (AUSSENBEREICHSSATZUNG, "AussenbereichsSatzung"),
        (OERTLICHEBAUVORSCHRIFT, "OertlicheBauvorschrift"),
        (SONSTIGES, "Sonstiges"),
    ]

    #gemeinde [1..n], XP_Gemeinde
    # Zur Vereinfachung zunächst nur Kardinalität 1 implementieren
    gemeinde = models.ForeignKey(AdministrativeOrganization, null=True, on_delete=models.SET_NULL)
    #planaufstellendeGemeinde [0..*], XP_Gemeinde
    #plangeber [0..*], XP_Plangeber
    #planArt [1..*], BP_PlanArt
    planart = models.CharField(null=False, blank=False, max_length=5, choices=BPLAN_TYPE_CHOICES, default='1000', verbose_name='Typ des vorliegenden Bebauungsplans.', db_index=True)
	#sonstPlanArt [0..1], BP_SonstPlanArt
    #rechtsstand [0..1], BP_Rechtsstand
    #status [0..1], BP_Status
    #aenderungenBisDatum [0..1], Date
    #aufstellungsbeschlussDatum [0..1], Date
    #veraenderungssperre [0..1], BP_VeraenderungssperreDaten
    #auslegungsStartDatum [0..*], Date
    #auslegungsEndDatum [0..*], Date
    #traegerbeteiligungsStartDatum [0..*], Date
    #traegerbeteiligungsEndDatum [0..*], Date
    #satzungsbeschlussDatum [0..1], Date
    #rechtsverordnungsDatum [0..1], Date
    #inkrafttretensDatum [0..1], Date
    #ausfertigungsDatum [0..1], Date
    #staedtebaulicherVertrag [0..1], Boolean
    #erschliessungsVertrag [0..1], Boolean
    #durchfuehrungsVertrag [0..1], Boolean
    #gruenordnungsplan [0..1], Boolean
    #versionBauNVO [0..1], XP_GesetzlicheGrundlage
    #versionBauGB [0..1], XP_GesetzlicheGrundlage
    #versionSonstRechtsgrundlage [0..*], XP_GesetzlicheGrundlage
    #bereich [0..*], BP_Bereich

    def __str__(self):
        """Returns a string representation of a BPlan."""
        return f"{self.name} ({self.get_planart_display()}) - {self.gemeinde}"