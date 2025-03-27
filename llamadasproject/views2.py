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
import socket
import json
# Aquí deberías agregar tu configuración de conexión
_HOST = '192.168.2.18'
_USERNAME = 'admin'
_PASSWORD = 'mi_contrasenia'

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
        print("ESTO ES DENTRO DEL LA FUNCION REGISTER_CALLBACKS----------------------------->")
        # Registra las devoluciones de llamada para manejar eventos
        self._manager.register_callback('FullyBooted', self._handle_event)
        self._manager.register_callback('Shutdown', self._handle_shutdown)
        # Registra el callback para el evento DTMF
        self._manager.register_callback('DTMF', self._handle_dtmf_event) #esta linea a sido agregada para ver teclas presionadas
        print("FIN DE REGISTER_CALLBACK------------------------------------------->")

    def _handle_event(self, event, manager):
        print(f"Evento recibido: {event.name}")

    def _handle_shutdown(self, event, manager):
        self._kill_flag = True

    #-------------------------------
    def _handle_dtmf_event(self, event, manager):
        """
        Maneja los eventos DTMF cuando el usuario presiona una tecla.
        """
        print("SE INICIO LA FUNCION DE DTMF EVENTOS------------------------------>")
        print(f"Evento DTMF completo: {event.result}")  # Imprimir todo el evento para depuración
        #digit = event.result['digit']
        #channel = event.result['channel']
        digit = event.result.get('digit', 'Desconocido')
        channel = event.result.get('channel', 'Desconocido')
        print(f"Tecla presionada: {digit} en el canal: {channel}")

        # Aquí podrías realizar una acción con la tecla presionada
        #self.send_to_django_api(digit, channel)
        print("SE FINALIZO LA FUNCION DE DTMF EVENTOS------------------------------>")

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
        action['Async']= 'no',  # Sincrónico, espera a que termine la reproducción
        #'http://localhost:8000/api/audios/crear_audioget_convertido/'
        response = self._manager.send_action(action)
        # Verificar respuesta completa (para depuración)
        print(response)
        # Esperar 5 segundos
        time.sleep(5)  # Pausar 5 segundos después de la reproducción del audio

        
        self.obtener_teclas_asterisk("admin", "mi_contrasenia", "192.168.2.18")
        # Luego puedes continuar con otras acciones como colgar o continuar la llamada
        action['Action']= 'Hangup',
        action['Channel']= channel
        '''  
        # Ahora, si el audio ha sido reproducido, podemos colgar o continuar con más acciones
        if response.success:
            # Esto asegura que Asterisk espere a que termine la reproducción
            # O simplemente colgar aquí
            action = ami.core._Originate(
                channel=channel,
                timeout=60000,
                callerid=callerid,
                variables={},
            )
            action['Context'] = context
            action['Exten'] = exten
            action['Priority'] = priority + 1  # Cambiar prioridad para ejecutar otro paso
            action['Application'] = 'WaitExten'  # Dejar la llamada en espera para recibir DTMF
            action['Data'] = '30'  # Tiempo en segundos para esperar DTMF
        
            response = self._manager.send_action(action)
            print(response)
            print("---------SE ESTA COMPROBANDO QUE PARO DE LA PRIORIDAD + 1----------")
            if response.success:
                print("---------SE ESTA COMPROBANDO QUE INGRESO DE LA PRIORIDAD + 2----------")
                # Colgar la llamada al finalizar
                action = ami.core._Originate(
                    channel=channel,
                    timeout=30000,
                    callerid=callerid,
                    variables={},
                )
                action['Context'] = context
                action['Exten'] = exten
                action['Priority'] = priority + 2  # Cambiar prioridad para ejecutar otro paso
                action['Application'] = 'Hangup'  # Colgar la llamada al finalizar

                response = self._manager.send_action(action)
                print(response)
        '''  
        return response
    #############################################
    def obtener_teclas_asterisk(self,usuario_ami, secreto_ami, ip_asterisk):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((ip_asterisk, 5038))
            
            saludo = s.recv(1024).decode()  # Esto debería ser "Asterisk Call Manager/7.0.3"
            print(f"Saludo AMI: {saludo}")  # Mostrar saludo inicial

            # Autenticación AMI
            s.send("Action:Login\n".encode())
            comando="Username:"+usuario_ami+"\n"
            s.send(comando.encode())
            comando2="Secret:"+secreto_ami+"\n"
            s.send(comando2.encode())
            s.send("\n".encode())
            respuesta = s.recv(1024).decode()
            print("Valor que extrae el reciv: ",respuesta)
            if "Success" not in respuesta:
                return "Error de autenticación AMI"


            # Enviar el comando para reproducir el archivo de audio
            '''s.send(f"Action: Playback\r\n"
                    f"Channel: {exten}\r\n"  # Canal de la llamada
                    f"Application: Playback\r\n"
                    f"Data: mi_audio\r\n"  # Aquí 'mi_audio' es el nombre del archivo
                    f"\r\n".encode())'''
            

            # Obtener la variable LLAMADA_TECLAS
            # # Esperar la respuesta de Asterisk
            respuesta = s.recv(1024).decode()
            print(f"Respuesta de Originate: {respuesta}")
            
            # Verificar si la llamada fue correctamente originada
            if "Response: Success" in respuesta:
                print("La llamada inicio correctamente.")
            #else:
                #print("Error al intentar realizar la llamada.")
            
            # Mantener la conexión abierta y escuchar eventos
            while True:
                respuesta_evento = s.recv(1024).decode()  # Escuchar eventos de Asterisk
                # Salir del ciclo si se recibe un evento de fin de llamada
                if respuesta_evento:
                    #print(f"Evento recibido: {respuesta_evento}")
                    
                    event_data = {}
                    for line in respuesta_evento.split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            event_data[key.strip()] = value.strip()

                    print(f"Datos extraídos: {event_data}")
                    digit = event_data.get('Digit', 'No digit found')# Si no encuentra la clave, retorna 'No digit found'
                    print(f"TECLA RECIBIDA -------------->: {digit}")
                    # Si la estructura es válida para un JSON, puedes intentar convertirlo
                    try:
                        json_data = json.dumps(event_data)  # Convierte el diccionario a un string JSON
                        print(f"Datos como JSON------>: {json_data}")
                        #print(f"TECLA RECIBIDA -------------->: {json_data['Digit']}")
                    except Exception as e:
                        print(f"Error al convertir a JSON: {e}")


                    if "Event: NewState" in respuesta_evento:
                        # Aquí puedes manejar las teclas presionadas si están configuradas en AMI
                        if "State: Ringing" in respuesta_evento or "State: Up" in respuesta_evento:
                            print("La llamada está sonando o contestada")
                    
                    if "Event: Hangup" in respuesta_evento:
                        print("Llamada finalizada. Cerrando conexión.")
                        break  # Detener la escucha si se recibe el evento de cierre de llamada
            
            s.close()

            return "Conexión cerrada con éxito"
            

        except Exception as e:
            return f"Error: {e}"
    #############################################









class LlamadasView2(viewsets.ViewSet):
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
            return JsonResponse({'message': 'Llamada realizada correctamente'})
        else:
            return JsonResponse({'message': 'Hubo un error al realizar la llamada'}, status=400)
