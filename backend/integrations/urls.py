from django.urls import path

from integrations.views import POSConnectionDetailView

urlpatterns = [
    path(
        "restaurants/<slug:slug>/pos/connection/",
        POSConnectionDetailView.as_view(),
        name="pos-connection-detail",
    ),
]
