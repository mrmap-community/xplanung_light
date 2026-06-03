from django.test import TestCase
from django.test import Client
from django.contrib.auth.models import User
from xplanung_light.helper.xplanung import XPlanung
from xplanung_light.models import BPlan
from django.urls import reverse
from django.db.models import Subquery, OuterRef, Q
import io
from django.http import FileResponse, HttpResponse
# https://medium.com/an-engineer-a-reader-a-guy/django-test-fixture-setup-setupclass-and-setuptestdata-72b6d944cdef

class InitialDataIntegrity(TestCase):
    fixtures = ['user.json',
                'administrative_organization.json',
                'bplan.json',
                'fplan.json',
                'admin_orga_user.json',
               ]
    
    @classmethod
    def setUpTestData(cls):
        #print("setUpTestData: Run once to set up non-modified data for all class methods.")
        pass

    def setUp(self):
        #print("setUp: Run once for every test method to set up clean data.")
        pass

    def test_if_superuser_name_is_admin_and_id_is_1(self):
        # Check ob superuser die id 1 hat und ob der Nutzername admin ist
        test = True
        user = User.objects.get(pk=1)
        if not user.username == 'admin':
            test = False
        if not user.is_superuser:
            test = False
        self.assertTrue(test)
    
    def test_if_xplangml_export_and_import_works(self):
        """
        Check ob ein der XPlan-GML Export für einen speziellen Plan (4318) sich wieder als BPlan importieren lässt.
        """
        client = Client()
        response = client.get(reverse('bplan-export-xplan-raster-6', args=[4318]))
        # Versuch das XPlan-Dokument wieder zu importieren
        # Zeitstempel des Plans in der Datenbank
        bplan_first = BPlan.objects.filter(pk=4318).annotate(
                last_changed=Subquery(
                            BPlan.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
                        )
        )
        timestamp_before = bplan_first[0].last_changed
        # Wichtig bei TemplateResponse: Zuerst rendern!
        response.render()
        # Umwandlung in ein file-like object (Bytes)
        file_like_bytes = io.BytesIO(response.content)
        # Content-Type direkt als Attribut anhängen, weil die Importfunktion für Uploads geschrieben ist
        file_like_bytes.content_type = response.headers.get('Content-Type', 'application/gml')
        xplan = XPlanung(file_like_bytes)
        bplan = xplan.import_plan(overwrite=True, plan_typ='bplan')
        if bplan:
            bplan_second = BPlan.objects.filter(pk=4318).annotate(
                last_changed=Subquery(
                            BPlan.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
                        )
            )
            timestamp_after = bplan_second[0].last_changed
        #print(str(timestamp_before) + " - " + str(timestamp_after))
        self.assertFalse(timestamp_before == timestamp_after)
        
    def test_if_wms_capabilities_is_created(self):
        """
        Test ob status = 200 für WMS-Capabilities über mapserver
        """
        client = Client()
        response = client.get(reverse('ows', args=[1531]) + "?REQUEST=GetCapabilities&VERSION=1.3.0&SERVICE=WMS")
        #print(response.content)
        self.assertEqual(response.status_code, 200)

    """
    def test_false_is_false(self):
        print("Method: test_false_is_false.")
        self.assertFalse(False)

    def test_false_is_true(self):
        print("Method: test_false_is_true.")
        self.assertTrue(False)

    def test_one_plus_one_equals_two(self):
        print("Method: test_one_plus_one_equals_two.")
        self.assertEqual(1 + 1, 2)
    """