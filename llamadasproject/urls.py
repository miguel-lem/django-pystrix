from rest_framework import routers
from django.urls import path
from llamadasproject.views import LlamadasViewset
from llamadasproject.views import LlamadasView
from llamadasproject.views2 import LlamadasView2
from llamadasproject.views2 import AudioViewget
from llamadasproject.views3 import LlamadasView3,CrearAudio
from rest_framework.urlpatterns import format_suffix_patterns

router = routers.DefaultRouter()

#ruta para la navegacion
router.register(r'llamada',LlamadasViewset, basename = 'llamadasproject')

# Agrega manualmente la acción personalizada
urlpatterns = [
    path('realizar_llamada/', LlamadasViewset.as_view({'post': 'realizar_llamada'})),
    path('realizar_llamadaunica/', LlamadasView.as_view({'post': 'realizar_llamadaunica'})),
    path('realizar_llamadaunica2/', LlamadasView2.as_view({'post': 'realizar_llamadaunica'})),
    path('crear_audioget_convertido/', AudioViewget.as_view({'get': 'convertir_audio2'}), name='convertir_audio2'),
    path('realizar_llamadas/', LlamadasView3.as_view({'post': 'realizar_llamadaunica'}), name='realizar_llamadaunica'),
    path('crear_audio/', CrearAudio.as_view({'post': 'text_to_speech'}), name='text_to_speech'),
]

urlpatterns += router.urls

# Si necesitas soporte para los sufijos de formato (json, xml, etc.)
urlpatterns = format_suffix_patterns(urlpatterns)


