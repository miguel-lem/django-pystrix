from django.shortcuts import render
from rest_framework import viewsets
from django.http import HttpResponse
import string
import pyttsx3
import os
import random
import subprocess
from rest_framework.decorators import action
import paramiko
import uuid
# Create your views here.

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
            output_path='C:/Users/mlema/Documents/audios/audio_convertido.wav'

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
    
    


#esta clase esta en revision para comprobar el funcionamiento de la aplicacion
#en el cual es que se convierta en audio y me responda mediante una ruta  luego de que
#se realice la peticion

from rest_framework.response import Response
from rest_framework import status

class AudioViewSet(viewsets.ViewSet):
    @action(detail=False, methods=['post'])
    def convertir_audio(self, request):
        texto = request.data.get('texto', '')

        if not texto:
            return Response({"error": "Debe proporcionar texto."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Instancia el procesador de audio
            procesador = AudioProcessor()

            # Usamos la función de texto a voz para generar el audio como binario
            audio_binario = procesador.texto_a_voz(texto)  # Usamos None ya que no necesitamos ruta de destino aquí
            
            if audio_binario is None:
                return Response({"error": "Hubo un problema al generar el archivo de audio."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Devolver el audio generado en la respuesta
            response = HttpResponse(audio_binario, content_type='audio/wav')
            response['Content-Disposition'] = 'attachment; filename="audio_generado.wav"'

            return response
        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#clase para generar el audio con una peticion get      
class AudioViewget(viewsets.ViewSet):
    @action(detail=False, methods=['get'])
    def convertir_audio2(self,request):
        texto = 'Estimada Juana la Alpaca le llamamos del Estudio  Juridico Romero D y Asociados, le informamos que tiene una deuda vencida en banco pacifico, dicha deuda se encuentra en nuestro estudio,  para mas informacion presione 1'

        if not texto:
            return Response({"error": "Debe proporcionar texto."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Instancia el procesador de audio
            procesador = AudioProcessor()

            # Usamos la función de texto a voz para generar el audio como binario
            audio_binario = procesador.texto_a_voz(texto)  # Usamos None ya que no necesitamos ruta de destino aquí
            
            if audio_binario is None:
                return Response({"error": "Hubo un problema al generar el archivo de audio."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Devolver el audio generado en la respuesta
            response = HttpResponse(audio_binario, content_type='audio/wav')
            response['Content-Disposition'] = 'attachment; filename="audio_generado.wav"'
 
            return response
        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


'''class AudioProcessor():
    def __init__(self):
        pass

    def texto_a_voz(self, texto, numero_telefono):
        try:
            # Generar un nombre único para el archivo basado en el número celular
            unique_filename = f"{numero_telefono}_{str(uuid.uuid4())}.wav"
            audio_path = f'/var/lib/asterisk/sounds/{unique_filename}'

            # Generar el archivo de audio y guardarlo en el directorio de Asterisk
            engine = pyttsx3.init()
            engine.setProperty('rate', 150)
            engine.setProperty('volume', 1)
            engine.save_to_file(texto, audio_path)
            engine.runAndWait()

            # Convertir el archivo a las especificaciones necesarias, si es necesario
            self.convertir_audio(audio_path)

            return unique_filename  # Devolver el nombre del archivo generado

        except Exception as e:
            print(f"Error al generar audio: {e}")
            return None

    def convertir_audio(self, input_audio):
        try:
            # Si necesitas convertir el archivo a un formato específico
            output_audio = input_audio  # Aquí podrías convertir a otro formato, si es necesario
            return output_audio
        except Exception as e:
            print(f"Error al convertir audio: {e}")
            return None
'''

