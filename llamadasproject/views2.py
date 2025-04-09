from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
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
import random
import subprocess
import pyttsx3
import string
import os
from django.http import HttpResponse
from django.core.files.storage import FileSystemStorage
from django.conf import settings
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
    def realizar_llamada(self, channel, exten,context, priority, callerid,audio_file=None):
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
        action['Data'] = 'mi_audio'#por el momento se trabaja con el audio que se subio al servidor asterisk
        #action['Async']= 'no',  # Sincrónico, espera a que termine la reproducción
        response = self._manager.send_action(action)
        # Verificar respuesta completa (para depuración)
        print(response)
        
        #utilizo la funcion con la cual esucho las teclas que presione en el telefono
        #le paso las credenciales del usuario ami
        #self.obtener_teclas_asterisk("admin", "mi_contrasenia", "192.168.2.18")
        #esta parte estoy realziando pruebas para comprobar que durante la llamada me permita teclear
        #time.sleep(5)  # Pausar 5 segundos después de la reproducción del audio
        # Luego continuar con otras acciones como colgar o continuar la llamada
        #print("Finalizando la llamada...") 
        #action['Action']= 'Hangup',
        #action['Channel']= channel
        #linea agregada para realizar pruebas y que luego se pueda colgar la llamda al escuchar 
        #response = self._manager.send_action(action)
        if audio_file:
            # Aquí usas ffmpeg para enviar el audio en tiempo real
            self.enviar_audio_a_asterisk(audio_file, '192.168.2.18')

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

    import subprocess

    def enviar_audio_a_asterisk(self,audio_file, asterisk_ip, asterisk_port=5060):
        # Ejecutar ffmpeg para convertir y enviar el audio como RTP hacia Asterisk
        cmd = [
            'ffmpeg', 
            '-re',  # Reproduce el audio en tiempo real
            '-i', audio_file,  # Ruta del archivo de audio
            '-vn',  # No video
            '-acodec', 'pcm_alaw',  # Codec de audio compatible con Asterisk
            '-ar', '8000',  # Tasa de muestreo de 8kHz para llamadas VoIP
            '-f', 'rtp',  # Formato RTP
            f'rtp://{asterisk_ip}:{asterisk_port}'  # Dirección de destino RTP (la IP de Asterisk y su puerto RTP)
        ]
        
        # Ejecutar el comando
        subprocess.Popen(cmd)




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

        # Definir el texto que se convertirá en audio
        texto = 'Este es el texto convertido en audio para poder realizar las pruebas en tiempo real.'

        # Verificar si el texto fue proporcionado en la solicitud (opcional)
        texto = request.data.get('texto', texto)

        try:
            # Instanciar el procesador de audio
            procesador = AudioProcessor()

            # Usar la función de texto a voz para generar el audio como binario
            audio_binario = procesador.texto_a_voz(texto)

            if audio_binario is None:
                return JsonResponse({"error": "Hubo un problema al generar el archivo de audio."}, status=500)

            # Guardar el archivo de audio en un archivo temporal en el servidor
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio_file:
                temp_audio_file.write(audio_binario)
                temp_audio_path = temp_audio_file.name  # Ruta temporal del archivo de audio

            # Iniciar la conexión AMI
            ami_core = AMICoreUno()

            # Realizar la llamada y pasar la ruta del archivo de audio generado
            response = ami_core.realizar_llamada(channel, exten, context, priority, callerid, audio_file=temp_audio_path)

            if response.success:
                # Eliminar archivo temporal después de usarlo (opcional, si no lo necesitas para depuración)
                os.remove(temp_audio_path)
                return JsonResponse({'message': 'Llamada realizada correctamente'})
            else:
                return JsonResponse({'message': 'Hubo un error al realizar la llamada'}, status=400)

        except Exception as e:
            return JsonResponse({'message': f'Error al realizar la llamada: {str(e)}'}, status=500)
        # Iniciar la conexión AMI
        '''ami_core = AMICoreUno()

        # Realizar la llamada
        response = ami_core.realizar_llamada(channel, exten, context, priority, callerid)

        if response.success:
            return JsonResponse({'message': 'Llamada realizada correctamente'})
        else:
            return JsonResponse({'message': 'Hubo un error al realizar la llamada'}, status=400)'''



class AudioProcessor():
    def __init__(self):
        # Aquí puedes inicializar cualquier parámetro o configuraciones que necesites.
        pass

    def texto_a_voz(self,texto):
        try:
            # Inicializar pyttsx3
            engine = pyttsx3.init()
            engine.setProperty('rate', 150)
            engine.setProperty('volume', 1)

            # Generar el audio en formato .wav
            temp_audio_path = 'output.wav'
            engine.save_to_file(texto, temp_audio_path)
            engine.runAndWait()

            # Llamar a la función que convierte el audio a las especificaciones que necesitas
            audio_binario = self.convertir_audio(temp_audio_path)
            # Eliminar los archivos temporales
            os.remove(temp_audio_path)
            return audio_binario
        
        except Exception as e:
            print(f"Error al leer el archivo .wav: {e}")
            return None

    def generar_nombre_archivo(self,longitud=8):
        caracteres = string.ascii_letters + string.digits  # Letras (mayúsculas y minúsculas) + dígitos
        nombre = ''.join(random.choice(caracteres) for _ in range(longitud))
        return nombre 
    
    def convertir_audio(self,input_audio):
        try:
            #output_path='C:/Users/mlema/Documents/audios/audio_convertido.wav'
            output_path = input_audio
            # Generamos un nombre aleatorio para el archivo
            nombre_aleatorio = self.generar_nombre_archivo(12)

            # Separamos la ruta y la extensión
            ruta_sin_extension, extension = os.path.splitext(output_path)

            # Combinamos la ruta con el nombre aleatorio
            nueva_ruta = f"{ruta_sin_extension}_{nombre_aleatorio}{extension}"
            print(nueva_ruta);
            # Usamos ffmpeg para convertir el archivo generado a las especificaciones requeridas
            # Comando ffmpeg para convertir a 8000Hz, Mono y 16 bits
            subprocess.run([
                'ffmpeg', '-i', input_audio,  # archivo de entrada
                '-ar', '8000',               # establecer la tasa de muestreo a 8000Hz
                '-ac', '1',                  # convertir a mono (1 canal)
                '-sample_fmt', 's16',        # establecer a 16 bits (sample format s16)
                nueva_ruta                  # archivo de salida
            ], check=True)

            print(f"Archivo de audio convertido y guardado en: {nueva_ruta}")

            # Leer el archivo de audio convertido como binario
            with open(output_path, 'rb') as f:
                audio_binario = f.read()

        except Exception as e:
            print(f"Error al convertir el archivo con ffmpeg: {e}")
            return None

        return audio_binario



import tempfile
class AudioViewget(viewsets.ViewSet):
    @action(detail=False, methods=['get'])
    def convertir_audio2(self,request):
        texto = 'Este es el texto convertido en audio para poder realizar las pruebas en tiempo real             .'

        if not texto:
            return Response({"error": "Debe proporcionar texto."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Instancia el procesador de audio
            procesador = AudioProcessor()

            # Usamos la función de texto a voz para generar el audio como binario
            audio_binario = procesador.texto_a_voz(texto)  # Usamos None ya que no necesitamos ruta de destino aquí
            
            if audio_binario is None:
                return Response({"error": "Hubo un problema al generar el archivo de audio."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Guardar el archivo de audio temporalmente en el servidor
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio_file:
                temp_audio_file.write(audio_binario)
                temp_audio_path = temp_audio_file.name  # Ruta temporal del archivo de audio

            # Devolver el audio generado en la respuesta
            #response = HttpResponse(audio_binario, content_type='audio/wav')
            #response['Content-Disposition'] = 'attachment; filename="audio_generado.wav"'
            
            # Ahora que tenemos el archivo temporal, se puede usar para transmitirlo a Asterisk

            return HttpResponse(f"Audio guardado temporalmente en: {temp_audio_path}", content_type='text/plain')

            #return response
        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


'''
import io

class AudioViewget(viewsets.ViewSet):
    @action(detail=False, methods=['get'])
    def convertir_audio2(self, request):
        texto = 'Este es el texto convertido en audio para poder realizar las pruebas y poder enviar al socket'

        if not texto:
            return Response({"error": "Debe proporcionar texto."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Instancia el procesador de audio
            procesador = AudioProcessor()
            llamada = AMICoreUno()
            # Usamos la función de texto a voz para generar el audio como binario
            audio_binario = procesador.texto_a_voz(texto)  # Usamos None ya que no necesitamos ruta de destino aquí
            
            if audio_binario is None:
                return Response({"error": "Hubo un problema al generar el archivo de audio."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


            # Crear un archivo en memoria para que pueda ser procesado como un archivo
            audio_file = io.BytesIO(audio_binario)

            # Devolver el audio generado como una respuesta HTTP
            response = HttpResponse(audio_file.read(), content_type='audio/wav')
            response['Content-Disposition'] = 'attachment; filename="audio_generado.wav"'
            
            return response
        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
#################################












 texto = 'Estimado cliente Camila Escobar en representacion de Banco del Pacífico, el ESTUDIO JURIDICO ROMERO D Y ASOCIADOS le recuerda que mantiene su credito vencido con un saldo de $1800, para mas informacion presione 1'
'''
