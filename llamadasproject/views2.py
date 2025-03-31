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

    #funcion para conectarse a AMI con la libreria pystrix
    def __init__(self):
        self._manager = ami.Manager()

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

    #funcion para realizar la llamada
    def realizar_llamada(self, channel, exten,context, priority, callerid):
        # Crear la acción de origen para realizar una llamada
        action = ami.core._Originate(
            channel=channel,
            timeout=30000,
            callerid=callerid,
            variables={},
        )
        # Establecer el contexto y la extensión 
        action['Context'] = context
        action['Exten'] = exten
        action['Priority'] = priority
        action['Application'] = 'Playback' #utilizo la accion para enviar la aplicacion de audios
        action['Data'] = 'mi_audio'#por el momento se trabaja con el audio que se dubio al servidor asterisk
        action['Async']= 'no',  # Sincrónico, espera a que termine la reproducción
        response = self._manager.send_action(action)
        # Verificar respuesta completa (para depuración)
        print(response)
        
        #utilizo la funcion con la cual esucho las teclas que presione en el telefono
        #le paso las credenciales del usuario ami
        self.obtener_teclas_asterisk("admin", "mi_contrasenia", "192.168.2.18")
        #esta parte estoy realziando pruebas para comprobar que durante la llamada me permita teclear
        time.sleep(5)  # Pausar 5 segundos después de la reproducción del audio
        # Luego continuar con otras acciones como colgar o continuar la llamada
        print("Finalizando la llamada...") 
        action['Action']= 'Hangup',
        action['Channel']= channel
        #linea agregada para realizar pruebas y que luego se pueda colgar la llamda al escuchar 
        response = self._manager.send_action(action)

        return response
    #funcion para conectarse con socket hacia asterisk ami, poder asi escuchar los eventos de teclado
    def obtener_teclas_asterisk(self,usuario_ami, secreto_ami, ip_asterisk):
        try:
            #iniciar socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((ip_asterisk, 5038))

            # Capturo la primera conecciopn donde debe mostrarme algo como "Asterisk Call Manager/7.0.3"
            saludo = s.recv(1024).decode()  
            print(f"Saludo AMI: {saludo}")  # Mostrar saludo inicial

            # Autenticación AMI le capturo y la envio convertido para que asterisk comprenda
            s.send("Action:Login\n".encode())
            comando="Username:"+usuario_ami+"\n"
            s.send(comando.encode())
            comando2="Secret:"+secreto_ami+"\n"
            s.send(comando2.encode())
            s.send("\n".encode())
            respuesta = s.recv(1024).decode()
            print("Valor que extrae el reciv: ",respuesta)
            #comprobacion si no logra autenticarse
            if "Success" not in respuesta:
                return "Error de autenticación AMI"
            

            # Obtener la variable LLAMADA_TECLAS
            # Esperar la respuesta de Asterisk
            respuesta = s.recv(1024).decode()
            print(f"Respuesta de Originate: {respuesta}")
            
            # Mantener la conexión abierta y escuchar eventos
            while True:
                # Escuchar eventos de Asterisk
                respuesta_evento = s.recv(1024).decode()  
                # Salir del ciclo si se recibe un evento de fin de llamada
                if respuesta_evento:
                    #aqui se imprime el evento tal cual llega desde asterisk
                    #print(f"Evento recibido: {respuesta_evento}")
                    
                    #creo una variable para capturar en ella los datos y luego extraer el digito que presione del otro lado
                    event_data = {}
                    for line in respuesta_evento.split('\n'):
                        if ':' in line:
                            #utilizo split para separar los valores
                            key, value = line.split(':', 1)
                            event_data[key.strip()] = value.strip()

                    #imprimo los valores para cargarlos en consola
                    print(f"Datos extraídos: {event_data}")
                    # Si no encuentra la clave, le envio un mensaje porque los eventos que me envie asterisk no siempre
                    #tienen eventos de tecla mientras se desarrolla la ejecucion de la llamada.
                    digit = event_data.get('Digit', 'Digito no encontrado')
                    #impresion de la tecla que se esta capturando
                    print(f"TECLA RECIBIDA -------------->: {digit}")
                    # Si la estructura es válida para un JSON, aqui debe permitir extraerle para cambiarle
                    try:
                        # Conversion el diccionario a un string JSON
                        #esta parte fue agregada por pruebas pero se la mantiene en caso de a futuro necesitar
                        json_data = json.dumps(event_data)  
                        print(f"Datos como JSON------>: {json_data}")
                    except Exception as e:
                        print(f"Error al convertir a JSON: {e}")


                    if "Event: NewState" in respuesta_evento:
                        # Aquí se puede manejar las teclas presionadas si están configuradas en AMI
                        if "State: Ringing" in respuesta_evento or "State: Up" in respuesta_evento:
                            print("La llamada está sonando o contestada")
                    
                    if "Event: Hangup" in respuesta_evento:
                        print("Llamada finalizada. Cerrando conexión.")
                        break  # Detener la escucha si se recibe el evento de cierre de llamada
            
            s.close()

            return "Conexión cerrada con éxito"
            

        except Exception as e:
            return f"Error: {e}"



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

        # Iniciar la conexión AMI
        ami_core = AMICoreUno()

        # Realizar la llamada
        response = ami_core.realizar_llamada(channel, exten, context, priority, callerid)

        if response.success:
            return JsonResponse({'message': 'Llamada realizada correctamente'})
        else:
            return JsonResponse({'message': 'Hubo un error al realizar la llamada'}, status=400)





