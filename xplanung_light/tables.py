import django_tables2 as tables
from .models import BPlan
from django_tables2 import Column
from django_tables2.utils import A

class BPlanTable(tables.Table):
    #download = tables.LinkColumn('gedis-document-pdf', text='Download', args=[A('pk')], \
    #                     orderable=False, empty_values=())
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
        fields = ("name", "gemeinde", "edit", "delete")