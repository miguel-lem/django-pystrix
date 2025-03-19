
from audioproject.views import AudioViewSet
from rest_framework import routers
from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from audioproject.views import AudioViewget

router = routers.DefaultRouter()
router.register(r'audio',AudioViewSet, basename = 'audiosproject')

# Agrega manualmente la acción personalizada
urlpatterns = [ 
    path('crear_audio_convertido/', AudioViewSet.as_view({'post': 'convertir_audio'}), name='convertir_audio'),
    path('crear_audioget_convertido/', AudioViewget.as_view({'get': 'convertir_audio2'}), name='convertir_audio2'),
]

urlpatterns += router.urls

urlpatterns = format_suffix_patterns(urlpatterns)