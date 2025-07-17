from django.db import models
from django.contrib.auth.models import User
import uuid, os
from simple_history.models import HistoricalRecords, HistoricForeignKey
from django.contrib.gis.db import models
from django.contrib.gis.db.models.functions import Envelope
from django.contrib.gis.gdal.raster.source import GDALRaster
from django.contrib.gis.gdal import SpatialReference
from django.core.files import File
from django.core.files.base import ContentFile
import slugify
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from io import BytesIO
# django-organizations
# einfache Klasse nutzen, weil slug und weitere Attribute sich in die Quere kommen und auch unnötig sind
from organizations.base import (
    OrganizationBase,
    OrganizationUserBase,
    OrganizationOwnerBase,
    OrganizationInvitationBase,
)

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

"""
TODO: UserProfile - Nutzer hat m2m Relation zu AdministrativeOrganization - dadurch wird geregelt, für welche Organisationen er Pläne erfassen kann

"""



"""
Klasse zur Abbildung einer Liste von standardisierten Lizenzen. Aus der Liste der Lizenzen können die Datenbereitsteller eine passende aussuchen.
Die Lizenzen beziehen sich immer auf alle publizierten Pläne einer Gebietskörperschaft. Hier haben wir derzeit nicht vorgesehen,
dass man einzelne Pläne mit getrennten Lizenzinformationen versehen kann.

Als logischen Anhalt was man für die Angabe einer Lizenz benötigt, kann man das europäische Vokabular aus dem OpenData Context nehmen:

    <skos:Concept rdf:about="http://europeandataportal.eu/ontologies/od-licenses#LPL-1.0" at:deprecated="false">
        <dc:identifier>IPL-1.0</dc:identifier>
        <skos:prefLabel xml:lang="en">IBM Public License Version 1.0 (IPL-1.0)</skos:prefLabel>
        <skos:exactMatch rdf:resource="https://opensource.org/licenses/IPL-1.0"/>
        <osi:isOpen rdf:datatype="http://www.w3.org/2001/XMLSchema#boolean">true</osi:isOpen>
    </skos:Concept>

Wir brauchen aber ggf. noch ein Symbol es den Nutzern einfacher zu machen ;-)

Weitere Informationen
https://www.w3.org/TR/vocab-dcat-3/
https://www.w3.org/TR/vocab-dcat-3/#license-rights

"""

class License(GenericMetadata):

    identifier = models.CharField(blank=False, null=False, max_length=1024, verbose_name='Identifikator / Name', help_text='Offizieller Identifikatir / Name der Lizenz')
    label = models.CharField(blank=False, null=False, max_length=1024, verbose_name='Titel / Bezeichnung der Lizenz', help_text='Offizieller Titel / Bezeichnung der Lizenz un deutscher Sprache')
    url = models.URLField(blank=False, null=False, verbose_name='URL', help_text='Verweis auf eine Seite mit einer genauen Beschreibung der Lizenz')
    is_open = models.BooleanField(blank=False, null=False, default=False, verbose_name='Lizenz ist OpenData kompatibel')
    need_source = models.BooleanField(blank=False, null=False, default=False, verbose_name='Lizenz ist erfordert Quellenangabe')
    symbol = models.ImageField(blank=True, null=True, verbose_name='Symbol für die Anzeige')
    history=HistoricalRecords()

    def __str__(self):
        return f"{self.label} ({self.identifier})"

"""
Basisklassen von django-organizations zur Abbildung der Benutzerverwaltung, ...
"""
class AdminOrgaUser(OrganizationUserBase):
    is_admin = models.BooleanField(blank=False, null=False, verbose_name='Nutzer ist Administrator für Organisation', default=False)

    def __str__(self):
        return f"{self.user} - {self.organization}"

class AdminOrgaOwner(OrganizationOwnerBase):
    pass


class AdminOrgaInvitation(OrganizationInvitationBase):
    pass


# administrative organizations
class AdministrativeOrganization(GenericMetadata, OrganizationBase):

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
    # obs = ... - Ortsbezirksschlüssel ...
    name = models.CharField(max_length=1024, verbose_name='Name der Gebietskörperschaft', help_text='Offizieller Name der Gebietskörperschaft - z.B. Rhein-Lahn-Kreis')
    type = models.CharField(max_length=3, choices=ADMIN_CLASS_CHOICES, default='UK', verbose_name='Typ der Gebietskörperschaft', db_index=True)
    address_street = models.CharField(blank=True, null=True, max_length=1024, verbose_name='Straße mit Hausnummer', help_text='Straße und Hausnummer')
    address_postcode = models.CharField(blank=True, null=True, max_length=5, verbose_name='Postleitzahl', help_text='Postleitzahl')
    
    address_city = models.CharField(max_length=256, blank=True, null=True, verbose_name='Stadt')
    address_phone = models.CharField(max_length=256, blank=True, null=True, verbose_name='Telefon')
    address_facsimile = models.CharField(max_length=256, blank=True, null=True, verbose_name='Fax')
    address_email = models.EmailField(max_length=512, blank=True, null=True, verbose_name='EMail')
    address_homepage = models.URLField(blank=True, null=True, verbose_name='Homepage')
    coat_of_arms_url = models.URLField(blank=True, null=True, verbose_name='Link zum Wappen', help_text='Hier bietet sich an den Link von Wikipedia zu übernehmen.')
    
    geometry = models.GeometryField(blank=True, null=True, verbose_name='Gebiet')

    history = HistoricalRecords()

    # published_data_contact_point - foreign key
    #published_data_contact_point = HistoricForeignKey(ContactOrganization, null=True, blank=True, verbose_name='Kontaktstelle für die publizierten Pläne der Organisation', help_text='Auswahl einer Kontaktstelle für die publizierten Pläne der Organisation', on_delete=models.SET_NULL)
    # https://www.w3.org/TR/vocab-dcat-3/#license-rights
    # dcterm namespace
    # https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#http://purl.org/dc/terms/license
    # https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#http://purl.org/dc/terms/accessrights
    # https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#http://purl.org/dc/terms/rights

    # published_data_license - foreign key
    published_data_license = HistoricForeignKey(License, null=True, blank=True, verbose_name='Standardisierte Lizenz', help_text='Auswahl einer standardisierten Lizenz', on_delete=models.SET_NULL)

    # published_data_license_source_note - if needed
    published_data_license_source_note = models.CharField(blank=True, null=True, max_length=4096, verbose_name='Quellenangabe', help_text='Art der Quellenangabe - falls Lizenz diese erfodert')
    # published_data_accessrights
    published_data_accessrights = models.CharField(blank=True, null=True, max_length=4096, verbose_name='Zugriffsbeschränkungen', help_text='Angaben zu vorhandenen Zugriffsbeschränkungen (ist besipielsweise der Zugriff für jedermann möglich, oder nur für besonders berechtigte Personengruppen)')
    # published_data_rights
    published_data_rights = models.CharField(blank=True, null=True, max_length=4096, verbose_name='Sonstige rechtliche Hinweise', help_text='Sonstige rechtliche Hinweise, die nicht von den Angaben zu Lizenzen oder Zugriffsbeschränkungen abgedeckt sind')

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
Klasse um Kontaktinformationen über eine Relation zu verwalten.
Die Kontaktinformationen können den einzelnen Gebietskörperschaften zugewiesen werden. 
Die Kontaktinformationen in den Gebietsköperschaften selbst, sollen die offizielle Daten beinhalten und
dienen nur als Fallback.
"""

class ContactOrganization(GenericMetadata):

    name = models.CharField(blank=False, null=False, max_length=1024, verbose_name='Name der Kontaktstelle', help_text='Offizieller Name der Kontaktstelle - z.B. Bauamt Pirmasens')
    unit = models.CharField(blank=True, null=True, max_length=1024, verbose_name='Name der Einheit/Referat', help_text='Name der zuständigen Einheit innerhalb der Kontaktstelle - z.B. Auskunftsstelle Bauleitplanung')
    person = models.CharField(blank=True, null=True, max_length=1024, verbose_name='Name einer Kontaktperson', help_text='Name einer Person die direkt kontaktiert werden kann, wenn man Informationen zu den Bauleitplänen benötigt.')
    phone = models.CharField(blank=False, null=False, max_length=256, verbose_name='Telefon')
    facsimile = models.CharField(blank=True, null=True, max_length=256, verbose_name='Fax')
    email = models.EmailField(blank=False, null=False, max_length=512, verbose_name='EMail')
    homepage = models.URLField(blank=True, null=True, verbose_name='Homepage')
    gemeinde = models.ManyToManyField(AdministrativeOrganization, blank=False, verbose_name="Kontakt für Gemeinde(n)", related_name="contacts")
    history = HistoricalRecords(m2m_fields=[gemeinde])

    def __str__(self):
        # Returns a string representation of a contact organization.
        return f"{self.name} ({self.unit})"


"""
https://xleitstelle.de/releases/objektartenkatalog_6_0
Achtung neu: https://xleitstelle.de/releases/objektartenkatalog_6_1
2025-04-01
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
    # https://stackoverflow.com/questions/35312334/how-can-i-store-history-of-manytomanyfield-using-django-simple-history
    #history = HistoricalRecords(inherit=True, m2m_fields=)
    #history = HistoricalRecords(inherit=True)
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

    #gemeinde [1..*], XP_Gemeinde
    # Zur Vereinfachung zunächst nur Kardinalität 1 implementieren
    #gemeinde = models.ForeignKey(AdministrativeOrganization, null=True, on_delete=models.SET_NULL)
    gemeinde = models.ManyToManyField(AdministrativeOrganization, blank=False, verbose_name="Gemeinde(n)")
    history = HistoricalRecords(m2m_fields=[gemeinde])
    #planaufstellendeGemeinde [0..*], XP_Gemeinde
    #plangeber [0..*], XP_Plangeber
    #planArt [1..*], BP_PlanArt
    planart = models.CharField(null=False, blank=False, max_length=5, choices=BPLAN_TYPE_CHOICES, default='1000', verbose_name='Typ des vorliegenden Bebauungsplans.', db_index=True)
	#sonstPlanArt [0..1], BP_SonstPlanArt
    #rechtsstand [0..1], BP_Rechtsstand
    #status [0..1], BP_Status
    #aenderungenBisDatum [0..1], Date
    #aufstellungsbeschlussDatum [0..1], Date
    aufstellungsbeschluss_datum = models.DateField(null=True, blank=True, verbose_name="Datum des Aufstellungsbeschlusses", help_text="Datum des Aufstellungsbeschlusses")
    #veraenderungssperre [0..1], BP_VeraenderungssperreDaten
    #auslegungsStartDatum [0..*], Date
    #auslegungsEndDatum [0..*], Date
    #traegerbeteiligungsStartDatum [0..*], Date
    #traegerbeteiligungsEndDatum [0..*], Date
    #satzungsbeschlussDatum [0..1], Date
    satzungsbeschluss_datum = models.DateField(null=True, blank=True, verbose_name="Datum des Satzungsbeschlusses", help_text="Datum des Satzungsbeschlusses")
    #rechtsverordnungsDatum [0..1], Date
    rechtsverordnungs_datum = models.DateField(null=True, blank=True, verbose_name="Datum der Rechtsverordnung", help_text="Datum der Rechtsverordnung")
    #inkrafttretensDatum [0..1], Date
    inkrafttretens_datum = models.DateField(null=True, blank=True, verbose_name="Datum des Inkrafttretens", help_text="Datum des Inkrafttretens")
    #ausfertigungsDatum [0..1], Date
    ausfertigungs_datum = models.DateField(null=True, blank=True, verbose_name="Datum der Ausfertigung", help_text="Datum der Ausfertigung")
    #staedtebaulicherVertrag [0..1], Boolean
    staedtebaulicher_vertrag = models.BooleanField(null=False, blank=False, default=False, verbose_name="Städtebaulicher Vertrag", help_text="Gibt an, ob es zum Plan einen städtebaulichen Vertrag gibt.")
    #erschliessungsVertrag [0..1], Boolean
    erschliessungs_vertrag = models.BooleanField(null=False, blank=False, default=False, verbose_name="Erschließungsvertrag", help_text="Gibt an, ob es für den Plan einen Erschließungsvertrag gibt.")
    #durchfuehrungsVertrag [0..1], Boolean
    durchfuehrungs_vertrag = models.BooleanField(null=False, blank=False, default=False, verbose_name="Durchführungsvertrag", help_text="Gibt an, ob für das Planungsgebiet einen Durchführungsvertrag (Kombination aus Städtebaulichen Vertrag und Erschließungsvertrag) gibt.")
    #gruenordnungsplan [0..1], Boolean
    gruenordnungsplan = models.BooleanField(null=False, blank=False, default=False, verbose_name="Grünordnungsplan", help_text="Gibt an, ob für den Plan ein zugehöriger Grünordnungsplan existiert.")
    #versionBauNVO [0..1], XP_GesetzlicheGrundlage
    #versionBauGB [0..1], XP_GesetzlicheGrundlage
    #versionSonstRechtsgrundlage [0..*], XP_GesetzlicheGrundlage
    #bereich [0..*], BP_Bereich

    def __str__(self):
        """Returns a string representation of a BPlan."""
        return f"{self.name} ({self.get_planart_display()})"
    
"""
Um die verschieden Beteiligungsverfahren abbilden zu können, macht es Sinn die Verfahren über einen ForeignKey an die 
jeweilige Planung zu hängen. Das erfolgt ähnlich wie bei den Anlagen. In XPlanung gibt es 4 Datumsfelder, die der jeweiligen 
Kardinalität von 0..*. Diese können aus 
"""
class BPlanBeteiligung(GenericMetadata):

    AUSLEGUNG = "1000"
    TOEB = "2000"
    TYPE_CHOICES = [
        (AUSLEGUNG,  "Öffentliche Auslegung"),
        (TOEB, "Träger öffentlicher Belange"),
    ]
    bekanntmachung_datum = models.DateField(null=False, blank=False, verbose_name="Datum der Bekanntmachung", help_text="Datum der Bekanntmachung des Verfahrens")
    start_datum = models.DateField(null=False, blank=False, verbose_name="Beginn", help_text="Datum des Beginns des Beteiligungsverfahrens")
    end_datum = models.DateField(null=False, blank=False, verbose_name="Ende", help_text="Enddatum des Beteiligungsverfahrens")
    typ = models.CharField(null=False, blank=False, max_length=5, choices=TYPE_CHOICES, default='1000', verbose_name='Typ des Beteiligungsverfahrens', help_text="Typ des Beteiligungsverfahrens - aktuell Auslegung oder TÖB", db_index=True)
    publikation_internet = models.URLField(null=True, blank=True, verbose_name="Publikation im Internet", help_text="Link zur Publikation auf der Hompage der jeweiligen Organisation")
    bplan = HistoricForeignKey(BPlan, on_delete=models.CASCADE, verbose_name="BPlan", help_text="BPlan", related_name="beteiligungen")
    history = HistoricalRecords()

    def __str__(self):
            """Returns a string representation of Beteiligung."""
            return f"{self.get_typ_display()} - vom {self.bekanntmachung_datum}"

    
class BPlanSpezExterneReferenz(GenericMetadata):

    # https://gist.github.com/chhantyal/5370749
    def get_upload_path(self, filename):
        name, ext = os.path.splitext(filename)
        return os.path.join('uploads', 'attachments' , str(self.generic_id) + "_" + slugify(name)) + ext

    BESCHREIBUNG = "1000"
    BEGRUENDUNG = "1010"
    LEGENDE = "1020"
    RECHTSPLAN = "1030"
    PLANGRUNDLAGE = "1040"
    UMWELTBERICHT = "1050"
    SATZUNG = "1060"
    VERORDNUNG = "1065"
    KARTE = "1070"
    ERLAEUTERUNG = "1080"
    ZUSAMMENFASSENDEERKLAERUNG = "1090"
    KOORDINATENLISTE = "2000"
    GRUNDSTUECKSVERZEICHNIS = "2100"
    PLANZLISTE = "2200"
    GRUENORDNUNGSPLAN = "2300"
    ERSCHLIESSUNGSVERTRAG = "2400"
    DURCHFUEHRUNGSVERTRAG = "2500"
    STAEDTEBAULICHERVERTRAG  = "2600"
    UMWELTBEZOGENESTELLUNGNAHMEN = "2700"
    BESCHLUSS = "2800"
    VORHABENUNDERSCHLIESSUNGSPLAN = "2900"
    METADATENPLAN = "3000"
    STAEDTEBAULENTWICKLUNGSKONZEPTINNENENTWICKLUNG = "3100"
    GENEHMIGUNG = "4000"
    BEKANNTMACHUNG = "5000"
    SCHUTZGEBIETSVERORDNUNG = "6000"
    RECHTSVERBINDLICH = "9998"
    INFORMELL = "9999"
    # Erweiterung XPlanung-light - Ablage der referenzierten und ausgeschnittenen Scans zur Darstellung als WMS-Layer
    REFSCAN = "99999"

    REF_TYPE_CHOICES = [
        (BESCHREIBUNG,  "Beschreibung"),
        (BEGRUENDUNG, "Begruendung"),
        (LEGENDE, "Legende"),
        (RECHTSPLAN, "Rechtsplan"),
        (PLANGRUNDLAGE, "Plangrundlage"),
        (UMWELTBERICHT, "Umweltbericht"),
        (SATZUNG, "Satzung"),
        (VERORDNUNG, "Verordnung"),
        (KARTE, "Karte"),
        (ERLAEUTERUNG, "Erlaeuterung"),
        (ZUSAMMENFASSENDEERKLAERUNG, "ZusammenfassendeErklaerung"),
        (KOORDINATENLISTE, "Koordinatenliste"),
        (GRUNDSTUECKSVERZEICHNIS, "Grundstuecksverzeichnis"),
        (PLANZLISTE, "Pflanzliste"),
        (GRUENORDNUNGSPLAN, "Gruenordnungsplan"),
        (ERSCHLIESSUNGSVERTRAG, "Erschliessungsvertrag"),
        (DURCHFUEHRUNGSVERTRAG, "Durchfuehrungsvertrag"),
        (STAEDTEBAULICHERVERTRAG, "StaedtebaulicherVertrag"),
        (UMWELTBEZOGENESTELLUNGNAHMEN, "UmweltbezogeneStellungnahmen"),
        (BESCHLUSS, "Beschluss"),
        (VORHABENUNDERSCHLIESSUNGSPLAN, "VorhabenUndErschliessungsplan"),
        (METADATENPLAN, "MetadatenPlan"),
        (STAEDTEBAULENTWICKLUNGSKONZEPTINNENENTWICKLUNG, "StaedtebaulEntwicklungskonzeptInnenentwicklung"),
        (GENEHMIGUNG, "Genehmigung"),
        (BEKANNTMACHUNG, "Bekanntmachung"),
        (SCHUTZGEBIETSVERORDNUNG, "Schutzgebietsverordnung"),
        (RECHTSVERBINDLICH, "Rechtsverbindlich"),
        (INFORMELL, "Informell"),
        (REFSCAN, "GeoreferenzierterScan"),
    ]

    #georefURL [0..1], URI
    #art [0..1], XP_ExterneReferenzArt
    #referenzName [1], CharacterString
    name = models.CharField(null=False, blank=False, default="Unbekannt", max_length=2048, verbose_name='Name des Dokumentes', help_text='Name bzw. Titel des referierten Dokuments. Der Standardname ist "Unbekannt".')
    #referenzURL [1], URI
    #referenzMimeType [0..1], XP_MimeTypes
    #beschreibung [0..1], CharacterString
    #datum [0..1], Date
    #typ [1], XP_ExterneReferenzTyp
    typ = models.CharField(null=False, blank=False, max_length=5, choices=REF_TYPE_CHOICES, default='1000', verbose_name='Typ / Inhalt des referierten Dokuments oder Rasterplans', help_text="Typ / Inhalt des referierten Dokuments oder Rasterplans", db_index=True)
    attachment = models.FileField(null = True, blank = True, upload_to='uploads', verbose_name="Dokument")
    bplan = HistoricForeignKey(BPlan, on_delete=models.CASCADE, verbose_name="BPlan", help_text="BPlan", related_name="attachments")
    #bplan = models.ForeignKey(BPlan, on_delete=models.CASCADE, verbose_name="BPlan", help_text="BPlan", related_name="attachments")
    
    # Anwendungsspezifische Felder
    aus_archiv = models.BooleanField(null=False, blank=False, default=False, verbose_name="Anhang stammt aus hochgeladenem ZIP-Archiv", help_text="Gibt an, ob der Anhang ursprünglich aus einem hochgeladenem ZIP-Archiv stammt.")
    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        # https://stackoverflow.com/questions/7514964/django-how-to-create-a-file-and-save-it-to-a-models-filefield
        # TODO - check if really needed - cause reading files from zip don't allow to have a temporary_file_path for each zipped file!
        if self.typ == '****': # 1070 Karte
            #raster_file = self.attachment.file.read()
            try:
                # https://dev.to/doridoro/what-is-contentfile-in-django-6nm
                raster = GDALRaster(self.attachment.file.temporary_file_path()) 
                target_srs = SpatialReference(25832)
                if raster.srs.srid != 25832:
                    target = raster.transform(target_srs)
                    # Was fehlt: Kompression und Overviews - müssten neu generiert werden!
                    # https://gis.stackexchange.com/questions/457264/save-a-gdal-dataset-to-django-file-field
                    #print(target.srs.srid)
                    #print(target.extent)
                    #print(target.name)
                    #print(target.is_vsi_based)
                    # Save the BytesIO object to the ImageField with the new filename
                    # Change name of attachment
                    new_name = self.attachment.name.lower()[0:-4] + "_transformed.tif"
                    if target.is_vsi_based:
                        #print("vsi_based")
                        # TODO: Problem - von Datei wird nur ein erster Teil geschrieben - ggf. ckunk Problem - Problem war dass das Raster erst geschlossen werden musste :-(
                        temp_raster = BytesIO()
                        temp_raster.write(target.vsi_buffer)
                        temp_raster.seek(0)
                        self.attachment.save(new_name, ContentFile(temp_raster.getvalue()), save=False)
                        temp_raster.close()
                    else:
                        temp_file_name = target.name
                        target = None # extremly needed !
                        # load from file
                        with open(temp_file_name, "rb") as f:
                            # test Dateigröße
                            #f.seek(0,2) # move the cursor to the end of the file
                            #print(f.tell())
                            #binary_file = f.read()
                            self.attachment.save(new_name, File(f), save=False)
                # https://stackoverflow.com/questions/67750359/typeerror-a-bytes-like-object-is-required-not-io-bytesio-django-pillow
            except (IOError, SyntaxError) as e:
                raise ValueError(f"Konnte GeoTIFF nicht nach UTM32 transformieren. -- {e}")
        super().save(*args, **kwargs)

    @property
    def file_name(self):
        return os.path.basename(self.attachment.file.name)

    def __str__(self):
            """Returns a string representation of SpezExterneReferenz."""
            return f"{self.name} ({self.get_typ_display()})"

    """
        Angabe eines referenzierten Scans - aus dem Beispiel von Hamburg / XLeitstelle - ist aber veraltet!

        <xplan:refScan>
            <xplan:XP_ExterneReferenz>
            <xplan:georefURL>BPlan004_6-0.pgw</xplan:georefURL>
            <xplan:referenzName>BPlan004_6-0</xplan:referenzName>
            <xplan:referenzURL>BPlan004_6-0.png</xplan:referenzURL>
            </xplan:XP_ExterneReferenz>
        </xplan:refScan>
    """
