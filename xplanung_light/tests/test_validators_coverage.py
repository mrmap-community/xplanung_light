import zipfile
from io import BytesIO
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from xplanung_light.models import AdministrativeOrganization
from xplanung_light import validators


class ValidatorCoverageTests(TestCase):
    def _gml(self, plan_type="BP_Plan", name="Testplan", ags="07316000", org_name="Testgemeinde",
             include_name=True, include_planart=True, include_gemeinde=True,
             include_geometry=True, geometry="<gml:Polygon><gml:exterior><gml:LinearRing><gml:posList>0 0 1 0 1 1 0 0</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon>"):
        ns = "http://www.xplanung.de/xplangml/6/0"
        parts = [
            f'<xplan:XPlanAuszug xmlns:xplan="{ns}" xmlns:gml="http://www.opengis.net/gml/3.2">',
            '  <gml:featureMember>',
            f'    <xplan:{plan_type}>',
        ]
        if include_name:
            parts.append(f'      <xplan:name>{name}</xplan:name>')
        if include_planart:
            parts.append('      <xplan:planArt>1000</xplan:planArt>')
        if include_gemeinde:
            parts.append(
                '      <xplan:gemeinde><xplan:XP_Gemeinde>'
                f'<xplan:ags>{ags}</xplan:ags>'
                f'<xplan:gemeindeName>{org_name}</xplan:gemeindeName>'
                '</xplan:XP_Gemeinde></xplan:gemeinde>'
            )
        if include_geometry:
            parts.append(f'      <xplan:raeumlicherGeltungsbereich>{geometry}</xplan:raeumlicherGeltungsbereich>')
        parts += [f'    </xplan:{plan_type}>', '  </gml:featureMember>', '</xplan:XPlanAuszug>']
        return ''.join(parts).encode('utf-8')

    def setUp(self):
        AdministrativeOrganization.objects.get_or_create(
            ls='07', ks='316', gs='000', defaults={'name': 'Testgemeinde'}
        )

    # ------------------------------------------------------------------
    # Small helper / namespace
    # ------------------------------------------------------------------
    def test_namespace_returns_namespace_and_empty_string(self):
        import xml.etree.ElementTree as ET
        self.assertEqual(validators.namespace(ET.fromstring('<a:root xmlns:a="urn:test"/>')), '{urn:test}')
        self.assertEqual(validators.namespace(ET.fromstring('<root/>')), '')

    # ------------------------------------------------------------------
    # Upload validators
    # ------------------------------------------------------------------
    def _zip_upload(self, files, content_type='application/zip'):
        data = BytesIO()
        with zipfile.ZipFile(data, 'w') as zf:
            for filename, payload in files:
                zf.writestr(filename, payload)
        return SimpleUploadedFile('plan.zip', data.getvalue(), content_type=content_type)

    @override_settings(XPLANUNG_LIGHT_CONFIG={
        'limits': {
            'max_files_in_zip': 3,
            'max_uncompressed_file_size': 100,
            'max_uncompressed_zip_size': 150,
            'max_gml_size': 10000,
            'upload_file_size_limits': {'tiff': 1000000},
        }
    })
    def test_upload_validators_reject_wrong_archive_mimetype(self):
        upload = SimpleUploadedFile('plan.zip', b'not-a-zip', content_type='text/plain')
        with self.assertRaises(ValidationError):
            validators.bplan_upload_file_validator(upload)
        upload = SimpleUploadedFile('plan.zip', b'not-a-zip', content_type='text/plain')
        with self.assertRaises(ValidationError):
            validators.fplan_upload_file_validator(upload)

    @override_settings(XPLANUNG_LIGHT_CONFIG={'limits': {
        'max_files_in_zip': 1, 'max_uncompressed_file_size': 1000,
        'max_uncompressed_zip_size': 1000, 'max_gml_size': 10000,
        'upload_file_size_limits': {'tiff': 1000000},
    }})
    def test_upload_validators_reject_too_many_files(self):
        upload = self._zip_upload([('a.txt', b'a'), ('b.txt', b'b')])
        with self.assertRaisesRegex(ValidationError, 'höchstens'):
            validators.bplan_upload_file_validator(upload)
        upload = self._zip_upload([('a.txt', b'a'), ('b.txt', b'b')])
        with self.assertRaisesRegex(ValidationError, 'höchstens'):
            validators.fplan_upload_file_validator(upload)

    @override_settings(XPLANUNG_LIGHT_CONFIG={'limits': {
        'max_files_in_zip': 10, 'max_uncompressed_file_size': 3,
        'max_uncompressed_zip_size': 100, 'max_gml_size': 10000,
        'upload_file_size_limits': {'tiff': 1000000},
    }})
    def test_upload_validators_reject_oversized_member(self):
        upload = self._zip_upload([('large.txt', b'1234')])
        with self.assertRaisesRegex(ValidationError, 'zu groß'):
            validators.bplan_upload_file_validator(upload)
        upload = self._zip_upload([('large.txt', b'1234')])
        with self.assertRaisesRegex(ValidationError, 'zu groß'):
            validators.fplan_upload_file_validator(upload)

    @override_settings(XPLANUNG_LIGHT_CONFIG={'limits': {
        'max_files_in_zip': 10, 'max_uncompressed_file_size': 100,
        'max_uncompressed_zip_size': 5, 'max_gml_size': 10000,
        'upload_file_size_limits': {'tiff': 1000000},
    }})
    def test_upload_validators_reject_oversized_total_content(self):
        upload = self._zip_upload([('a.txt', b'123'), ('b.txt', b'456')])
        with self.assertRaisesRegex(ValidationError, 'entpackte Inhalt'):
            validators.bplan_upload_file_validator(upload)
        upload = self._zip_upload([('a.txt', b'123'), ('b.txt', b'456')])
        with self.assertRaisesRegex(ValidationError, 'entpackte Inhalt'):
            validators.fplan_upload_file_validator(upload)

    @override_settings(XPLANUNG_LIGHT_CONFIG={'limits': {
        'max_files_in_zip': 10, 'max_uncompressed_file_size': 100,
        'max_uncompressed_zip_size': 100, 'max_gml_size': 10000,
        'upload_file_size_limits': {'tiff': 1000000},
    }})
    def test_upload_validators_collect_bad_mimetype_and_missing_gml(self):
        upload = self._zip_upload([('note.bin', b'hello')])
        with patch.object(validators.magic, 'from_buffer', return_value='application/x-weird'):
            with self.assertRaises(ValidationError) as cm:
                validators.bplan_upload_file_validator(upload)
        self.assertIn('nicht zugelassenen MimeType', str(cm.exception))
        self.assertIn('keine GML-Datei', str(cm.exception))

        upload = self._zip_upload([('note.bin', b'hello')])
        with patch.object(validators.magic, 'from_buffer', return_value='application/x-weird'):
            with self.assertRaises(ValidationError) as cm:
                validators.fplan_upload_file_validator(upload)
        self.assertIn('nicht zugelassenen MimeType', str(cm.exception))
        self.assertIn('keine GML-Datei', str(cm.exception))

    @override_settings(XPLANUNG_LIGHT_CONFIG={'limits': {
        'max_files_in_zip': 10, 'max_uncompressed_file_size': 100000,
        'max_uncompressed_zip_size': 200000, 'max_gml_size': 10000,
        'upload_file_size_limits': {'tiff': 1000000},
    }})
    def test_bplan_upload_accepts_allowed_files_and_calls_content_validator(self):
        upload = self._zip_upload([('plan.gml', b'<xml/>'), ('doc.pdf', b'%PDF')])
        def mime(_buffer, mime=True):
            return 'application/gml+xml' if mime else None
        with patch.object(validators.magic, 'from_buffer', side_effect=mime), \
             patch.object(validators, 'bplan_content_validator') as content:
            validators.bplan_upload_file_validator(upload)
        content.assert_called_once()

    @override_settings(XPLANUNG_LIGHT_CONFIG={'limits': {
        'max_files_in_zip': 10, 'max_uncompressed_file_size': 100000,
        'max_uncompressed_zip_size': 200000, 'max_gml_size': 10000,
        'upload_file_size_limits': {'tiff': 1000000},
    }})
    def test_fplan_upload_accepts_allowed_files_and_calls_content_validator(self):
        upload = self._zip_upload([('plan.gml', b'<xml/>'), ('data.bin', b'abc')])
        with patch.object(validators.magic, 'from_buffer', return_value='application/octet-stream'), \
             patch.object(validators, 'fplan_content_validator') as content:
            validators.fplan_upload_file_validator(upload)
        content.assert_called_once()

    @override_settings(XPLANUNG_LIGHT_CONFIG={'limits': {
        'max_files_in_zip': 10, 'max_uncompressed_file_size': 100000,
        'max_uncompressed_zip_size': 200000, 'max_gml_size': 10000,
        'upload_file_size_limits': {'tiff': 1000000},
    }})
    def test_upload_validators_reject_multiple_gml_files(self):
        upload = self._zip_upload([('one.gml', b'a'), ('two.gml', b'b')])
        with patch.object(validators.magic, 'from_buffer', return_value='application/gml+xml'), \
             patch.object(validators, 'bplan_content_validator'):
            with self.assertRaisesRegex(ValidationError, 'mehrere GML-Dateien'):
                validators.bplan_upload_file_validator(upload)
        upload = self._zip_upload([('one.gml', b'a'), ('two.gml', b'b')])
        with patch.object(validators.magic, 'from_buffer', return_value='application/gml+xml'), \
             patch.object(validators, 'fplan_content_validator'):
            with self.assertRaisesRegex(ValidationError, 'mehrere GML-Dateien'):
                validators.fplan_upload_file_validator(upload)

    # ------------------------------------------------------------------
    # GML content validators
    # ------------------------------------------------------------------
    @override_settings(XPLANUNG_LIGHT_CONFIG={'limits': {
        'max_gml_size': 1000, 'max_files_in_zip': 10,
        'max_uncompressed_file_size': 1000, 'max_uncompressed_zip_size': 1000,
        'upload_file_size_limits': {'tiff': 1000000},
    }})
    def test_content_validators_reject_wrong_mimetype_and_oversized_file(self):
        bad = SimpleUploadedFile('x.gml', b'<x/>', content_type='text/html')
        with self.assertRaises(ValidationError):
            validators.bplan_content_validator(bad)
        bad = SimpleUploadedFile('x.gml', b'x' * 1001, content_type='text/xml')
        with self.assertRaises(ValidationError):
            validators.fplan_content_validator(bad)

    @override_settings(XPLANUNG_LIGHT_CONFIG={'limits': {
        'max_gml_size': 10000, 'max_files_in_zip': 10,
        'max_uncompressed_file_size': 1000, 'max_uncompressed_zip_size': 1000,
        'upload_file_size_limits': {'tiff': 1000000},
    }})
    def test_content_validators_support_bytesio_and_reject_bad_bytesio_mimetype(self):
        data = self._gml()
        with patch.object(validators.magic, 'from_buffer', return_value='application/gml+xml'):
            validators.bplan_content_validator(BytesIO(data))
        with patch.object(validators.magic, 'from_buffer', return_value='text/html'):
            with self.assertRaises(ValidationError):
                validators.fplan_content_validator(BytesIO(data))

    @override_settings(XPLANUNG_LIGHT_CONFIG={'limits': {
        'max_gml_size': 10000, 'max_files_in_zip': 10,
        'max_uncompressed_file_size': 1000, 'max_uncompressed_zip_size': 1000,
        'upload_file_size_limits': {'tiff': 1000000},
    }})
    def test_content_validators_reject_invalid_utf8_and_invalid_xml(self):
        binary = SimpleUploadedFile('x.gml', b'\xff\xfe', content_type='text/xml')
        with self.assertRaises(ValidationError):
            validators.bplan_content_validator(binary)
        malformed = SimpleUploadedFile('x.gml', b'<broken', content_type='text/xml')
        with self.assertRaises(ValidationError):
            validators.fplan_content_validator(malformed)

    @override_settings(XPLANUNG_LIGHT_CONFIG={'limits': {
        'max_gml_size': 10000, 'max_files_in_zip': 10,
        'max_uncompressed_file_size': 1000, 'max_uncompressed_zip_size': 1000,
        'upload_file_size_limits': {'tiff': 1000000},
    }})
    def test_content_validators_reject_unsupported_root(self):
        xml = b'<foo:XPlanAuszug xmlns:foo="urn:wrong" />'
        with self.assertRaises(ValidationError):
            validators.bplan_content_validator(SimpleUploadedFile('x.gml', xml, content_type='text/xml'))
        with self.assertRaises(ValidationError):
            validators.fplan_content_validator(SimpleUploadedFile('x.gml', xml, content_type='text/xml'))

    @override_settings(XPLANUNG_LIGHT_CONFIG={'limits': {
        'max_gml_size': 10000, 'max_files_in_zip': 10,
        'max_uncompressed_file_size': 1000, 'max_uncompressed_zip_size': 1000,
        'upload_file_size_limits': {'tiff': 1000000},
    }})
    def test_content_validators_reject_missing_mandatory_fields(self):
        xml = self._gml(include_name=False, include_planart=False, include_gemeinde=False, include_geometry=False)
        with self.assertRaises(ValidationError):
            validators.bplan_content_validator(SimpleUploadedFile('x.gml', xml, content_type='text/xml'))
        xml = self._gml(plan_type='FP_Plan', include_name=False, include_planart=False, include_gemeinde=False, include_geometry=False)
        with self.assertRaises(ValidationError):
            validators.fplan_content_validator(SimpleUploadedFile('x.gml', xml, content_type='text/xml'))

    @override_settings(XPLANUNG_LIGHT_CONFIG={'limits': {
        'max_gml_size': 10000, 'max_files_in_zip': 10,
        'max_uncompressed_file_size': 1000, 'max_uncompressed_zip_size': 1000,
        'upload_file_size_limits': {'tiff': 1000000},
    }})
    def test_content_validators_reject_unknown_organization(self):
        xml = self._gml(ags='07999999', org_name='Unbekannt')
        with self.assertRaises(ValidationError) as cm:
            validators.bplan_content_validator(SimpleUploadedFile('x.gml', xml, content_type='text/xml'))
        self.assertIn('kein Eintrag', str(cm.exception))

    @override_settings(XPLANUNG_LIGHT_CONFIG={'limits': {
        'max_gml_size': 10000, 'max_files_in_zip': 10,
        'max_uncompressed_file_size': 1000, 'max_uncompressed_zip_size': 1000,
        'upload_file_size_limits': {'tiff': 1000000},
    }})
    def test_content_validators_reject_organization_name_mismatch(self):
        # Die Fixture aus setUp() liefert eine echte AdministrativeOrganization
        # mit AGS 07316000 und dem Namen "Testgemeinde". Dadurch wird der
        # eigentliche gemeindeName-Vergleich erreicht, ohne den XML-Parser oder
        # das Model zu mocken.
        xml = self._gml(org_name='Anderer Name')
        with self.assertRaises(ValidationError) as cm:
            validators.bplan_content_validator(
                SimpleUploadedFile('x.gml', xml, content_type='text/xml')
            )
        self.assertIn('gemeindeName', str(cm.exception))

    @override_settings(XPLANUNG_LIGHT_CONFIG={'limits': {
        'max_gml_size': 10000, 'max_files_in_zip': 10,
        'max_uncompressed_file_size': 1000, 'max_uncompressed_zip_size': 1000,
        'upload_file_size_limits': {'tiff': 1000000},
    }})
    def test_content_validators_reject_missing_ags(self):
        xml = self._gml().replace(b'<xplan:ags>07316000</xplan:ags>', b'')
        with self.assertRaises(ValidationError):
            validators.bplan_content_validator(SimpleUploadedFile('x.gml', xml, content_type='text/xml'))

    @override_settings(XPLANUNG_LIGHT_CONFIG={'limits': {
        'max_gml_size': 10000, 'max_files_in_zip': 10,
        'max_uncompressed_file_size': 1000, 'max_uncompressed_zip_size': 1000,
        'upload_file_size_limits': {'tiff': 1000000},
    }})
    def test_content_validators_reject_invalid_geometry(self):
        xml = self._gml()
        with patch.object(validators.GEOSGeometry, 'from_gml', side_effect=Exception('invalid geometry')):
            with self.assertRaisesRegex(ValidationError, 'interpretieren'):
                validators.bplan_content_validator(SimpleUploadedFile('x.gml', xml, content_type='text/xml'))
        xml = self._gml(plan_type='FP_Plan')
        with patch.object(validators.GEOSGeometry, 'from_gml', side_effect=Exception('invalid geometry')):
            with self.assertRaisesRegex(ValidationError, 'interpretieren'):
                validators.fplan_content_validator(SimpleUploadedFile('x.gml', xml, content_type='text/xml'))

    def test_geotiff_validator_rejects_wrong_mimetype_without_opening_raster(self):
        upload = SimpleUploadedFile('x.tif', b'abc', content_type='text/plain')
        fake_raster = Mock(info='')
        with patch.object(validators.magic, 'from_buffer', return_value='text/plain'), \
             patch.object(validators, 'GDALRaster', return_value=fake_raster):
            with self.assertRaises(ValidationError) as cm:
                validators.geotiff_raster_validator(upload)
        self.assertIn('image/tiff', str(cm.exception))

    def test_geotiff_validator_collects_missing_overview_and_compression(self):
        upload = SimpleUploadedFile('x.tif', b'abc', content_type='image/tiff')
        fake_raster = Mock(info='SOMETHING')
        fake_raster.srs.srid = 25832
        fake_raster.extent = (0, 0, 1, 1)
        with patch.object(validators.magic, 'from_buffer', return_value='image/tiff'), \
             patch.object(validators, 'GDALRaster', return_value=fake_raster), \
             patch.object(validators.settings, 'XPLANUNG_LIGHT_CONFIG', {'limits': {'upload_file_size_limits': {'tiff': 1000000}}}):
            with self.assertRaises(ValidationError) as cm:
                validators.geotiff_raster_validator(upload)
        self.assertIn('Overviews', str(cm.exception))
        self.assertIn('LZW', str(cm.exception))

    def test_geotiff_validator_handles_raster_open_failure(self):
        upload = SimpleUploadedFile('x.tif', b'abc', content_type='image/tiff')
        with patch.object(validators.magic, 'from_buffer', return_value='image/tiff'), \
             patch.object(validators, 'GDALRaster', side_effect=Exception('bad raster')):
            with self.assertRaises(ValidationError) as cm:
                validators.geotiff_raster_validator(upload)
        self.assertIn('Raster interpretieren', str(cm.exception))

    def test_geotiff_validator_handles_missing_srs_and_extent(self):
        upload = SimpleUploadedFile('x.tif', b'abc', content_type='image/tiff')
        fake_raster = Mock(info='Overviews: 1\nCOMPRESSION=LZW')
        type(fake_raster).srs = property(lambda self: (_ for _ in ()).throw(Exception('no srs')))
        type(fake_raster).extent = property(lambda self: (_ for _ in ()).throw(Exception('no extent')))
        with patch.object(validators.magic, 'from_buffer', return_value='image/tiff'), \
             patch.object(validators, 'GDALRaster', return_value=fake_raster), \
             patch.object(validators.settings, 'XPLANUNG_LIGHT_CONFIG', {'limits': {'upload_file_size_limits': {'tiff': 1000000}}}):
            with self.assertRaises(ValidationError) as cm:
                validators.geotiff_raster_validator(upload)
        self.assertIn('Koordinatenreferenzsystem', str(cm.exception))
        self.assertIn('Ausdehnung', str(cm.exception))

    @override_settings(XPLANUNG_LIGHT_CONFIG={'limits': {
        'max_gml_size': 10000, 'max_files_in_zip': 10,
        'max_uncompressed_file_size': 1000, 'max_uncompressed_zip_size': 1000,
        'upload_file_size_limits': {'tiff': 1000000},
    }})
    def test_content_validators_handles_geometry_transform_failure(self):
        xml = self._gml()
        fake_geometry = Mock()
        fake_geometry.transform.side_effect = Exception('transform failed')
        with patch.object(validators.GEOSGeometry, 'from_gml', return_value=fake_geometry):
            with self.assertRaisesRegex(ValidationError, 'transformieren') as cm:
                validators.bplan_content_validator(SimpleUploadedFile('x.gml', xml, content_type='text/xml'))
        self.assertIn('EPSG:4326', str(cm.exception))

        xml = self._gml(plan_type='FP_Plan')
        fake_geometry = Mock()
        fake_geometry.transform.side_effect = Exception('transform failed')
        with patch.object(validators.GEOSGeometry, 'from_gml', return_value=fake_geometry):
            with self.assertRaisesRegex(ValidationError, 'transformieren') as cm:
                validators.fplan_content_validator(SimpleUploadedFile('x.gml', xml, content_type='text/xml'))
        self.assertIn('EPSG:4326', str(cm.exception))

    def test_bplan_datum_validator_is_noop(self):
        self.assertIsNone(validators.bplan_datum_validator())
