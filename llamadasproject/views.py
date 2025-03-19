from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
import pystrix.ami
#from pystrix.ami.core import OriginateAction
# Create your views here.

# views.py
import time
from django.http import JsonResponse
from rest_framework import viewsets
from pystrix import ami
import requests

# Aquí deberías agregar tu configuración de conexión
_HOST = '192.168.2.18'
_USERNAME = 'admin'
_PASSWORD = 'mi_contrasenia'

#clase para efectuar una llamadas entre dos extensiones
class AMICore:
    """
    Clase para manejar la lógica de la sesión AMI.
    """
    _manager = None
    _kill_flag = False

    def __init__(self):
        self._manager = ami.Manager()
        self._register_callbacks()

        try:
            self._manager.connect(_HOST)

            # Solicitar el token de desafío para la autenticación
            challenge_response = self._manager.send_action(ami.core.Challenge())
            if challenge_response and challenge_response.success:
                action = ami.core.Login(_USERNAME, _PASSWORD, challenge=challenge_response.result['Challenge'])
                self._manager.send_action(action)
            else:
                self._kill_flag = True
                raise ConnectionError("Asterisk no proporcionó el token MD5 de desafío")

        except ami.ManagerSocketError as e:
            self._kill_flag = True
            raise ConnectionError(f"No se puede conectar al servidor Asterisk: {str(e)}")
        except ami.core.ManagerAuthError as reason:
            self._kill_flag = True
            raise ConnectionError(f"No se puede autenticar en el servidor Asterisk: {reason}")
        except ami.ManagerError as reason:
            self._kill_flag = True
            raise ConnectionError(f"Ocurrió un error inesperado en Asterisk: {reason}")

        self._manager.monitor_connection()

    def _register_callbacks(self):
        # Registra las devoluciones de llamada para manejar eventos
        self._manager.register_callback('FullyBooted', self._handle_event)
        self._manager.register_callback('Shutdown', self._handle_shutdown)

    def _handle_event(self, event, manager):
        print(f"Evento recibido: {event.name}")

    def _handle_shutdown(self, event, manager):
        self._kill_flag = True

    def kill(self):
        self._manager.close()

    def is_alive(self):
        return not self._kill_flag

    def realizar_llamada(self, channel, exten, context, priority, callerid):
        # Crear la acción de origen para realizar una llamada
        action = ami.core._Originate(
            channel=channel,
            timeout=30000,
            callerid=callerid,
            variables={},
            #async=True
        )
        # Establecer el contexto y la extensión (esto puede necesitar ajustes dependiendo de tu implementación)
        action['Context'] = context
        action['Exten'] = exten
        action['Priority'] = priority
        response = self._manager.send_action(action)
        # Verificar respuesta completa (para depuración)
        print(response)

        return response

#esta clase funciona en concordancia con la anterior
class LlamadasViewset(viewsets.ViewSet):
    """
    Vista para manejar la llamada desde la API.
    """
    def realizar_llamada(self, request):
        # Extraer los parámetros de la solicitud
        channel = request.data.get('channel', '')
        exten = request.data.get('exten', '')
        context = request.data.get('context', '')
        priority = request.data.get('priority', 1)
        callerid = request.data.get('callerid', '')
        #print(dir(ami.core))
        #print("esto es las librerias del ami")
        #print(dir(ami.ami))

        # Iniciar la conexión AMI
        ami_core = AMICore()

        # Realizar la llamada
        response = ami_core.realizar_llamada(channel, exten, context, priority, callerid)

        if response.success:
            return JsonResponse({'message': 'Llamada realizada con correctamente'})
        else:
            return JsonResponse({'message': 'Hubo un error al realizar la llamada'}, status=400)



#esta clase es para realziar la llamada a una sola extension, esta parte esta 
#para realziar pruebas de conjugacion entre ami y agi
#la primera es para que se ejecute la llamada y la segunda es para que tome las acciones de teclas
class AMICoreUno:
    """
    Clase para manejar la lógica de la sesión AMI.
    """
    _manager = None
    _kill_flag = False

    def __init__(self):
        self._manager = ami.Manager()
        self._register_callbacks()

        try:
            self._manager.connect(_HOST)

            # Solicitar el token de desafío para la autenticación
            challenge_response = self._manager.send_action(ami.core.Challenge())
            if challenge_response and challenge_response.success:
                action = ami.core.Login(_USERNAME, _PASSWORD, challenge=challenge_response.result['Challenge'])
                self._manager.send_action(action)
            else:
                self._kill_flag = True
                raise ConnectionError("Asterisk no proporcionó el token MD5 de desafío")

        except ami.ManagerSocketError as e:
            self._kill_flag = True
            raise ConnectionError(f"No se puede conectar al servidor Asterisk: {str(e)}")
        except ami.core.ManagerAuthError as reason:
            self._kill_flag = True
            raise ConnectionError(f"No se puede autenticar en el servidor Asterisk: {reason}")
        except ami.ManagerError as reason:
            self._kill_flag = True
            raise ConnectionError(f"Ocurrió un error inesperado en Asterisk: {reason}")

        self._manager.monitor_connection()

    def _register_callbacks(self):
        # Registra las devoluciones de llamada para manejar eventos
        self._manager.register_callback('FullyBooted', self._handle_event)
        self._manager.register_callback('Shutdown', self._handle_shutdown)
        # Registra el callback para el evento DTMF
        self._manager.register_callback('DTMF', self._handle_dtmf_event) #esta linea a sido agregada para ver teclas presionadas

    def _handle_event(self, event, manager):
        print(f"Evento recibido: {event.name}")

    def _handle_shutdown(self, event, manager):
        self._kill_flag = True

    #-------------------------------
    def _handle_dtmf_event(self, event, manager):
        """
        Maneja los eventos DTMF cuando el usuario presiona una tecla.
        """
        digit = event.result['digit']
        channel = event.result['channel']
        print(f"Tecla presionada: {digit} en el canal: {channel}")

        # Aquí podrías realizar una acción con la tecla presionada
        self.send_to_django_api(digit, channel)

    def send_to_django_api(self, digit, channel):
        """Envía la tecla presionada a la API Django."""
        api_url = 'http://192.168.1.100:8000/guardar_tecla/'  # Cambia la URL a tu API Django
        data = {
            'digit': digit,
            'channel': channel
        }

        try:
            response = requests.post(api_url, data=data)
            if response.status_code == 200:
                print(f"Tecla {digit} enviada correctamente a la API.")
            else:
                print(f"Error al enviar la tecla {digit} a la API: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Error de conexión con la API Django: {e}")



    #------------------------
    def kill(self):
        self._manager.close()

    def is_alive(self):
        return not self._kill_flag

    def realizar_llamada(self, channel, exten,context, priority, callerid):
        # Crear la acción de origen para realizar una llamada
        action = ami.core._Originate(
            channel=channel,
            timeout=30000,
            callerid=callerid,
            variables={},
            #async=True
        )
        # Establecer el contexto y la extensión (esto puede necesitar ajustes dependiendo de tu implementación)
        action['Context'] = context
        action['Exten'] = exten
        action['Priority'] = priority
        action['Application'] = 'Playback'
        action['Data'] = 'mi_audio'#'hello-world'
        #'http://localhost:8000/api/audios/crear_audioget_convertido/'
        response = self._manager.send_action(action)
        # Verificar respuesta completa (para depuración)
        print(response)

         # Ahora, si el audio ha sido reproducido, podemos colgar o continuar con más acciones
        if response.success:
            # Esto asegura que Asterisk espere a que termine la reproducción
            # O simplemente colgar aquí
            action = ami.core._Originate(
                channel=channel,
                timeout=30000,
                callerid=callerid,
                variables={},
            )
            action['Context'] = context
            action['Exten'] = exten
            action['Priority'] = priority + 1  # Cambiar prioridad para ejecutar otro paso
            action['Application'] = 'Hangup'  # Colgar la llamada al finalizar

            response = self._manager.send_action(action)
            print(response)
        return response

class LlamadasView(viewsets.ViewSet):
    """
    Vista para manejar la llamada desde la API.
    """
    def realizar_llamadaunica(self, request):
        # Extraer los parámetros de la solicitud
        channel = request.data.get('channel', '')
        exten = request.data.get('exten', '')
        context = request.data.get('context', '')
        priority = request.data.get('priority', 1)
        callerid = request.data.get('callerid', '')
        #print(dir(ami.core))
        #print("esto es las librerias del ami")
        #print(dir(ami.ami))

        # Iniciar la conexión AMI
        ami_core = AMICoreUno()

        # Realizar la llamada
        response = ami_core.realizar_llamada(channel, exten, context, priority, callerid)

        if response.success:
            return JsonResponse({'message': 'Llamada realizada con correctamente'})
        else:
            return JsonResponse({'message': 'Hubo un error al realizar la llamada'}, status=400)

class llamadasAGI():
    import pystrix

    if __name__ == '__main__':
        agi = pystrix.agi.AGI()

        agi.execute(pystrix.agi.core.Answer()) #Answer the call

        response = agi.execute(pystrix.agi.core.StreamFile('demo-thanks', escape_digits=('1', '2'))) #Play a file; allow DTMF '1' or '2' to interrupt
        if response: #Playback was interrupted; if you don't care, you don't need to catch this
            (dtmf_character, offset) = response #The key pressed by the user and the playback time

        agi.execute(pystrix.agi.core.Hangup()) #Hang up the call

