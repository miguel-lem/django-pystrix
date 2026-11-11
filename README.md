# Django + Pystrix: llamadas automáticas con Asterisk y texto a voz

API REST hecha con Django y Django REST Framework que:

1. Convierte texto a audio (TTS con `pyttsx3`) y lo transforma con `ffmpeg` a un formato compatible con Asterisk.
2. Sube el audio por SSH/SFTP al servidor Asterisk (`/var/lib/asterisk/sounds/`).
3. Origina una llamada mediante AMI (Asterisk Manager Interface) usando [`pystrix`](https://github.com/marcelom/pystrix) y reproduce el audio al cliente.
4. Escucha eventos AMI para capturar las teclas (DTMF) que el cliente presiona.

## Estructura

```
manage.py
princiaplcrud/     Configuración del proyecto (settings, urls, wsgi/asgi)
llamadasproject/   Llamadas AMI + generación/envío de audio a Asterisk
  views.py, views2.py, views3.py   Versiones sucesivas de la lógica (views3 es la más completa)
  models.py                        Modelo Project (sin uso actual)
audioproject/      Endpoints para generar/convertir audio de forma local
audios/            Audios de ejemplo/temporales (.wav)
```

## Requisitos

- Python 3.10+
- Django 5.1, `djangorestframework`
- `pystrix`, `pyttsx3`, `paramiko`, `psycopg2-binary`
- `ffmpeg` instalado y disponible en el `PATH`
- PostgreSQL
- Un servidor Asterisk con AMI habilitado y acceso SSH a la carpeta de sonidos

> No hay `requirements.txt`. Instalación sugerida:
>
> ```bash
> python -m venv venv
> venv\Scripts\activate          # Windows
> pip install django djangorestframework pystrix pyttsx3 paramiko psycopg2-binary
> ```

## Configuración

Actualmente los valores están escritos directamente en el código (ver "Seguridad"). Debes ajustar:

> **Nota:** los valores del código (IP `192.168.2.18`, usuarios y contraseñas) corresponden a una **máquina virtual de pruebas**. Cada persona debe configurarlos según su propio entorno (su IP, usuarios, contraseñas y base de datos).
>
> Ejemplo de la sección de base de datos en [settings.py](princiaplcrud/settings.py), que debes adaptar a tu equipo:
>
> ```python
> DATABASES = {
>     'default': {
>         'ENGINE': 'django.db.backends.postgresql',
>         'NAME': 'ivruno',            # nombre de tu base de datos
>         'USER': 'postgres',          # tu usuario de PostgreSQL
>         'PASSWORD': 'mi_contrasena', # tu contraseña
>         'HOST': '192.168.2.18',      # IP de TU servidor (o 'localhost')
>         'PORT': '5432'
>     }
> }
> ```

| Qué | Dónde | Valor actual (de la VM de pruebas) |
|-----|-------|--------------|
| Base de datos PostgreSQL | [settings.py](princiaplcrud/settings.py) `DATABASES` | BD `ivruno`, host `192.168.2.18:5432` |
| Host/usuario/clave AMI | [views3.py](llamadasproject/views3.py) `_HOST`, `_USERNAME`, `_PASSWORD` | `192.168.2.18`, `admin` |
| Acceso SSH a Asterisk | [views3.py](llamadasproject/views3.py) `CrearAudio.asterisk_server` | usuario `pcprueba`, puerto 22 |
| Texto a locutar | [views3.py](llamadasproject/views3.py) `CrearAudio.text_to_speech` | texto fijo en el código |

## Ejecución

```bash
python manage.py migrate
python manage.py runserver
```

Ver el aviso sobre `MEDIA_URL` en "Problemas conocidos" antes de arrancar.

## Endpoints

Prefijos: `/api/llamadas/` y `/api/audios/`.

### Llamadas (`llamadasproject`)

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/llamadas/realizar_llamadas/` | Genera el audio, lo envía a Asterisk, limpia audios de más de 3 min y origina la llamada (versión actual, `views3`). |
| POST | `/api/llamadas/realizar_llamada/` | Versión original (`views.py`). |
| POST | `/api/llamadas/realizar_llamadaunica/` | Llamada única (`views.py`). |
| POST | `/api/llamadas/realizar_llamadaunica2/` | Llamada única (`views2.py`). |
| GET | `/api/llamadas/crear_audioget_convertido/` | Genera audio vía GET (`views2.py`). |
| POST | `/api/llamadas/crear_audio/` | Sólo genera el audio y lo envía a Asterisk. |

Cuerpo JSON para originar una llamada:

```json
{
  "channel": "SIP/1001",
  "exten": "1001",
  "context": "from-internal",
  "priority": 1,
  "callerid": "Notificaciones <1000>"
}
```

Respuesta: `{"message": "La llamada fue exitosa"}` (200) o error 400.

### Audio (`audioproject`)

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/audios/crear_audio_convertido/` | Recibe `{"texto": "..."}` y devuelve un `.wav` generado. |
| GET | `/api/audios/crear_audioget_convertido/` | Variante por GET. |

Ejemplo:

```bash
curl -X POST http://127.0.0.1:8000/api/audios/crear_audio_convertido/ \
     -H "Content-Type: application/json" \
     -d '{"texto": "Hola, esto es una prueba"}' --output prueba.wav
```

## Flujo de una llamada

```
POST /realizar_llamadas/
  └─ pyttsx3 → .wav
  └─ ffmpeg  → formato Asterisk
  └─ SFTP    → /var/lib/asterisk/sounds/
  └─ AMI Originate (Playback del audio)
  └─ AMI eventos → teclas DTMF presionadas
```

## Seguridad (importante)

El repositorio contiene datos sensibles en texto plano:

- `SECRET_KEY` de Django y `DEBUG = True` en `settings.py`.
- Contraseñas de PostgreSQL, AMI y SSH, e IP interna, en `settings.py` y `views3.py` / `views.py`.
- `AutoAddPolicy()` en paramiko acepta cualquier clave de host SSH.
- Los audios del cliente (`audios/`) incluyen datos personales; no deberían versionarse.

Recomendado: moverlos a variables de entorno (por ejemplo con `python-decouple` o `django-environ`), rotar las credenciales ya expuestas, agregar `.gitignore` (`audios/`, `__pycache__/`, `.env`) y verificar la clave de host SSH.

## Problemas conocidos

- **`MEDIA_URL`/`MEDIA_ROOT` comentados** al final de `settings.py`, pero `princiaplcrud/urls.py` usa `static(settings.MEDIA_URL, ...)`. Con `MEDIA_URL` vacío Django lanza `ImproperlyConfigured` al arrancar. Descomenta esas líneas en `settings.py`.
- `audioproject` no está en `INSTALLED_APPS` (funciona porque no tiene modelos, pero conviene agregarlo).
- Existen tres versiones de la lógica (`views.py`, `views2.py`, `views3.py`) con código duplicado; conviene consolidar en una.
- El texto del audio está fijo en el código; está previsto obtenerlo desde la base de datos.
- Se crea una conexión AMI nueva por cada petición y se usan `print` en lugar de `logging`.
- Faltan `requirements.txt`, tests y `.gitignore`.
