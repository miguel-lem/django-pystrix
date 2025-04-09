from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action

# views.py
import time
from django.http import JsonResponse
from rest_framework import viewsets
from pystrix import ami
import socket
import json
from rest_framework.viewsets import ViewSet
import pyttsx3
from django.http import FileResponse, JsonResponse
import os
import subprocess
import uuid
#Creacion de un hilo para ejecucion paralela
import threading

# Aquí deberías agregar tu configuración de conexión
_HOST = '192.168.2.18'
_USERNAME = 'admin'
_PASSWORD = 'mi_contrasenia'

#esta clase es para realziar la llamada a una sola extension, esta parte esta 
#para realziar pruebas de conjugacion entre ami y agi
#la primera es para que se ejecute la llamada y la segunda es para que tome las acciones de teclas
class RealizarLllamada:
    """
    Clase para manejar la lógica de la sesión AMI.
    """
    _manager = None
    _kill_flag = False

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

    def kill(self):
        self._manager.close()

    def is_alive(self):
        return not self._kill_flag

    def realizar_llamada(self, channel, exten,context, priority, callerid,nombre_audio):
        nombre_audio_limpio = nombre_audio.replace('.wav', '')
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
        action['Data'] = nombre_audio_limpio#'mi_audio'#'hello-world'
        response = self._manager.send_action(action)
        # Verificar respuesta completa (para depuración)
        print(response)

        # Ahora, si el audio ha sido reproducido, podemos colgar o continuar con más acciones
        if response.success:
            #creo un objeto de la clase donde escucho eventos
            teclas=EscucharEventos()
            #llamo a la funcion de escucha
            teclas.obtener_teclas_asterisk("admin", "mi_contrasenia", "192.168.2.18")
        return response


class LlamadasView3(viewsets.ViewSet):
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

        
        #llamamos a la funcion de crear el audio y enviarlo a al servidor asteris
        #creo el objeto de crearaudio
        gestor_audio = CrearAudio()
        time.sleep(3)
        #llamo a la funcion que quiero generarle el texto en audio
        nombre_audio_generado = gestor_audio.text_to_speech()
        #llamo a la funcion con la cual elimino de asterisk los audios que tiene mas de 3 minutos alli
        #de esa manera evito utilizar espacion con audios que no son necesarios
        gestor_audio.cleanup_old_audios(minutes=3)
        print("SE A PROCEDIDO A CREAR AUDIO Y ELIMINAR AUDIO")
        #compruebo que me devuelva el nombre del archivo
        print("resultado de nombre: ",nombre_audio_generado)
        #le separo el nombre de la extension para poder pasarle al servidor y que entienda cual es el audio que quier
        #se reproduzca en la llamada
        nombre_data = os.path.splitext(nombre_audio_generado)[0]
        #impresion para corroborar que tiene el nombre sin la extension
        print("nombre sin la extension: ", nombre_data)
        #capturo la variable para enviarle 
        print("---------------------------paso de la extraccion de nombre---------------")
        # Iniciar la conexión AMI
        ami_core = RealizarLllamada()
        # Realizar la llamada
        response = ami_core.realizar_llamada(channel, exten, context, priority, callerid,nombre_data)

        if response.success:
            return JsonResponse({'message': 'La llamada fue exitosa'})
        else:
            return JsonResponse({'message': 'Hubo un error al realizar la llamada'}, status=400)

class EscucharEventos:
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


from paramiko import SSHClient, AutoAddPolicy
import datetime

class CrearAudio(ViewSet):
    def __init__(self):
        # Configuración del servidor Asterisk remoto
        self.asterisk_server = {
            'hostname': '192.168.2.18',  # Cambiar por la IP real
            'port': 22,  # Puerto SSH
            'username': 'pcprueba',
            'password': '12345',
            'remote_path': '/var/lib/asterisk/sounds/'  # Ruta donde se guardarán los audios
        }


    def text_to_speech(self):#,keep_seconds=180):
        texto="Estimado cliente Maribel Escobar, en representacion de Banco del Pacífico, el ESTUDIO JURIDICO ROMERO D Y ASOCIADOS le recuerda que mantiene su credito vencido con un saldo de $1080"
        """Función para convertir texto a audio en formato compatible con Asterisk"""
        if not texto:
            raise ValueError("No se proporcionó texto")

        try:
            # 1. Generar audio inicial con pyttsx3
            output_file = self._generate_tts_audio(texto)
            if not output_file:
                raise RuntimeError("Error al generar el audio")

            # 2. Convertir a formato compatible con Asterisk
            converted_file = self._convert_to_asterisk_format(output_file)
            
            # 3. Limpiar archivo temporal original
            if os.path.exists(output_file):
                os.remove(output_file)

            if not converted_file:
                raise RuntimeError("Error al convertir el audio")

            # 4. Enviar el archivo al servidor Asterisk
            remote_filename = self._send_to_asterisk_server(converted_file)

            # 5. Limpiar archivo local convertido
            if os.path.exists(converted_file):
                os.remove(converted_file)

            # Programar eliminación remota después de cierta cantidad de segundos
            #if keep_seconds > 0:
                #threading.Timer(keep_seconds, self._delete_remote_file, [remote_filename]).start()

            return converted_file

        except Exception as e:
            # Limpieza en caso de error
            if 'output_file' in locals() and os.path.exists(output_file):
                os.remove(output_file)
            if 'converted_file' in locals() and converted_file and os.path.exists(converted_file):
                os.remove(converted_file)
            raise e

    def _send_to_asterisk_server(self, local_file):
        """Envía el archivo al servidor Asterisk remoto via SFTP"""
        ssh = SSHClient()
        ssh.set_missing_host_key_policy(AutoAddPolicy())
        
        try:
            # Conectar al servidor remoto
            ssh.connect(
                hostname=self.asterisk_server['hostname'],
                port=self.asterisk_server['port'],
                username=self.asterisk_server['username'],
                password=self.asterisk_server['password'],
                timeout=10  # Timeout para evitar bloqueos
            )
            
            # 2. Verificar permisos del directorio remoto
            sftp = ssh.open_sftp()

            try:
                sftp.chdir(self.asterisk_server['remote_path'])
            except IOError:
                raise RuntimeError(f"El directorio remoto no existe o no es accesible: {self.asterisk_server['remote_path']}")
                
            # 3. Subir archivo con permisos explícitos
            remote_filename = f"converted_temp_audio_{uuid.uuid4().hex}.wav"
            remote_path = f"{self.asterisk_server['remote_path']}{remote_filename}"
            
            # Subir el archivo
            sftp.put(local_file, remote_path)
            
            # Asegurarse de que los permisos son correctos
            sftp.chmod(remote_path, 0o644)  # -rw-r--r--
            # 4. Verificar que el archivo se creó correctamente
            try:
                if sftp.stat(remote_path).st_size == 0:
                    sftp.remove(remote_path)
                    raise RuntimeError("El archivo remoto se subió vacío")
            except IOError:
                raise RuntimeError("No se pudo verificar el archivo remoto")
            
            return remote_filename  # Retornamos solo el nombre del archivo
            
        except Exception as e:
            # Limpieza en caso de error durante la subida
            if 'remote_path' in locals():
                try:
                    sftp.remove(remote_path)
                except:
                    pass
            raise RuntimeError(f"Error al subir archivo: {str(e)}")
        finally:
            if 'sftp' in locals():
                sftp.close()
            ssh.close()
    
    def cleanup_old_audios(self, minutes=3):
        """Elimina archivos de audio más antiguos que X minutos del servidor Asterisk"""
        ssh = SSHClient()
        ssh.set_missing_host_key_policy(AutoAddPolicy())
        
        try:
            ssh.connect(
                hostname=self.asterisk_server['hostname'],
                port=self.asterisk_server['port'],
                username=self.asterisk_server['username'],
                password=self.asterisk_server['password']
            )
            
            sftp = ssh.open_sftp()
            cutoff_time = datetime.datetime.now() - datetime.timedelta(minutes=minutes)
            
            try:
                for filename in sftp.listdir(self.asterisk_server['remote_path']):
                    if filename.startswith('converted_temp_audio_') and filename.endswith('.wav'):
                        filepath = self.asterisk_server['remote_path'] + filename
                        try:
                            file_attr = sftp.stat(filepath)
                            file_time = datetime.datetime.fromtimestamp(file_attr.st_mtime)
                            
                            if file_time < cutoff_time:
                                sftp.remove(filepath)
                                print(f"Eliminado archivo antiguo: {filename}")
                        except IOError:
                            # Si el archivo ya no existe o hay error al acceder, continuamos
                            continue
            except IOError as e:
                print(f"Error al limpiar archivos: {e}")
                
        except Exception as e:
            print(f"Error en limpieza de audios: {e}")
        finally:
            if 'sftp' in locals():
                sftp.close()
            ssh.close()


    def _delete_file(self, file_path):
        """Elimina un archivo si existe"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Archivo {file_path} eliminado después del tiempo especificado")
        except Exception as e:
            print(f"Error al eliminar archivo {file_path}: {e}")

    # Las funciones _generate_tts_audio y _convert_to_asterisk_format permanecen igual
    def _generate_tts_audio(self, texto):
        """Genera el audio inicial con pyttsx3"""
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 150)
            engine.setProperty('volume', 1.0)

            # Usar nombre de archivo único
            output_file = f"temp_audio_{uuid.uuid4().hex}.wav"
            engine.save_to_file(texto, output_file)
            engine.runAndWait()

            return output_file if os.path.exists(output_file) else None
        except Exception as e:
            print(f"Error en generación TTS: {e}")
            return None

    def _convert_to_asterisk_format(self, input_file):
        """Convierte el audio a formato compatible con Asterisk"""
        try:
            # Nombre para archivo convertido
            converted_file = f"converted_{os.path.basename(input_file)}"
            
            # Comando ffmpeg para convertir a formato Asterisk:
            # - 8000Hz (telefonía estándar)
            # - 1 canal (mono)
            # - 16 bits por muestra
            # - Formato WAV PCM
            subprocess.run([
                'ffmpeg',
                '-i', input_file,
                '-ar', '8000',        # Frecuencia de muestreo 8kHz
                '-ac', '1',            # Audio mono
                '-acodec', 'pcm_s16le', # Códec PCM signed 16-bit little-endian
                '-y',                  # Sobrescribir si existe
                converted_file
            ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            return converted_file if os.path.exists(converted_file) else None
        except subprocess.CalledProcessError as e:
            print(f"Error en ffmpeg: {e.stderr.decode('utf-8')}")
            return None
        except Exception as e:
            print(f"Error en conversión: {e}")
            return None


class subir_audioAsterisk:
    def copy_to_asterisk_temp(audio_file):
        asterisk_temp_dir="/var/lib/asterisk/tmp/"
        """Copia el archivo al directorio temporal de Asterisk"""
        try:
            if not os.path.exists(asterisk_temp_dir):
                os.makedirs(asterisk_temp_dir, exist_ok=True)
            
            filename = f"temp_audio_{uuid.uuid4().hex}.wav"
            dest_path = os.path.join(asterisk_temp_dir, filename)
            
            shutil.copy(audio_file, dest_path)
            
            # Programar eliminación
            threading.Timer(15, lambda: os.remove(dest_path) if os.path.exists(dest_path) else None).start()
            
            return filename
            
        except Exception as e:
            raise RuntimeError(f"Error al copiar a directorio temporal de Asterisk: {e}")