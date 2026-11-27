# JAPs Música · 0.6.0

Tu colección. Tu espacio musical. Aplicación web local en español, creada desde cero a partir del plan de Jazmín Schürrer, con asistencia de IA. Esta entrega es un prototipo funcional: consultar las limitaciones y la evidencia antes de usar datos únicos.

## Inicio rápido

Requisitos: Linux x86_64, Python 3.11 o posterior con `venv`, FFmpeg con `libmp3lame`, navegador moderno y conexión para instalar dependencias la primera vez. Verificado en el contenedor Debian 13 con Python 3.12.14 y FFmpeg 7.1.5; no implica validación en Juggernaut o Bastión.

1. Descomprimí `JAPs-Musica-v0.6.0.zip` en una carpeta propia.
2. Abrí una terminal allí y ejecutá `sh start.sh --desktop`. La primera vez crea un entorno Python e instala las dependencias fijadas. Si faltan requisitos: Debian `sudo apt install python3-venv ffmpeg`; EndeavourOS `sudo pacman -S python ffmpeg`.
3. Abrí `http://127.0.0.1:8765`. Copiá el token local mostrado por el lanzador y creá tu administradora con una contraseña de al menos 12 caracteres. El token sirve solo desde el anfitrión y deja de servir al existir una cuenta. No hay contraseña predeterminada.
4. En **Importar**, elegí artista, álbum, WAV PCM y portada JPEG/PNG opcional. Revisá títulos y orden. Los MP3 estéreo de 192 kb/s se preparan una sola vez. **Actualizar estado** muestra el resultado. El borrador se guarda en el servidor. Después de una recarga, en Importaciones usá **Abrir y continuar**: solo necesitás seleccionar los WAV pendientes. Las pistas ya recibidas no se suben otra vez. **Reintentar conversión** reutiliza los archivos de un trabajo fallido; si falta alguno, el mensaje indica que abras el borrador.
5. Abrí el álbum y una canción. El reproductor permanece al navegar por Biblioteca, Resumen y Cuentas. Para detener el servidor usá **Ctrl+C** en la terminal. **Salir** cierra la sesión y limpia el reproductor.

Los datos quedan en `~/.local/share/japs-musica`, fuera del código. Para elegir otra carpeta: `sh start.sh --data '/ruta con espacios/mis datos'`. La misma carpeta no puede abrirse con dos servidores. Una segunda ejecución no borra cuentas ni catálogo. No incluyas esa carpeta en un repositorio público.

## Red doméstica

Primero creá la administradora desde el equipo anfitrión. Luego iniciá `sh start.sh --host 0.0.0.0 --port 8765`. Desde el iPhone conectado a la misma red, abrí `http://IP-ACTUAL-DEL-EQUIPO:8765`. Determiná esa IP en el equipo; ninguna IP del plan se toma como vigente. No abras puertos del router. HTTP transmite credenciales sin cifrar: esta configuración es exclusivamente para una LAN de confianza. El piloto de internet requiere HTTPS y la auditoría pendiente.

Los oyentes solicitan acceso desde la pantalla inicial. En **Cuentas**, la administradora aprueba o revoca. Se protege la última administradora activa. La revocación invalida sesiones y detiene el generador de audio al comprobar cada bloque de 16 KiB; bytes ya enviados, buffers del servidor y audio descargado en el cliente no pueden retirarse.

## Ejemplo autorizado

`example/` contiene tres pistas sintetizadas originales de 12 segundos: no son grabaciones comerciales. `python3 example/make_wavs.py` las regenera. Importalas juntas bajo el artista **JAPs · Muestras** y el álbum **Encuentros**. Su procedencia y permisos están en `example/PROCEDENCIA.md`.

## Tecnologías y pruebas

Python, Flask, Waitress (servidor WSGI), SQLite, FFmpeg, Pillow y HTML/CSS/JavaScript sin compilación. No usa CDN, fuentes remotas ni servicios de música. Las versiones exactas comprobadas están en `requirements.txt`; las herramientas de prueba, en `requirements-dev.txt`.

```sh
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

Ver `docs/pruebas.md` para resultados, pruebas pendientes y comandos. El resumen administrativo usa UTC en almacenamiento y America/Argentina/Cordoba para fechas y horas. Una escucha exige `min(30 s, 50 %)` de tiempo aceptado; finalizar exige cobertura única del 90 % y final coherente. Seek suma cero. Se conservan intervalos repetidos como tiempo efectivo, pero no como nueva cobertura. La telemetría del navegador no certifica atención y puede perder hasta el intervalo entre señales (normalmente 5 segundos) o más durante una desconexión. Las señales fuera de secuencia se rechazan; los duplicados no se suman. Cada pestaña nueva inicia sus intentos; al recargar se recupera el intento de esa pestaña si sigue abierto.

## Copia y restauración

Detené el servidor antes de la copia. Los comandos rechazan trabajo concurrente y destinos existentes.

```sh
.venv/bin/python manage.py backup '/ruta/datos' '/ruta/nueva/copia'
.venv/bin/python manage.py restore '/ruta/nueva/copia' '/ruta/nueva/restauracion'
sh start.sh --data '/ruta/nueva/restauracion'
```

Se usa la API de backup de SQLite, un manifiesto SHA-256 y copia de medios. La restauración verifica hashes e integridad, invalida las sesiones y conserva cuentas y estadísticas. No copia WAV temporales: los metadatos de borradores quedan en SQLite y, después de restaurar, hay que seleccionar los archivos faltantes. La configuración settings.json se incluye si existe. Las opciones de arranque deben conservarse junto con la copia; `config.example.env` documenta los parámetros sin secretos. No subas copias privadas a releases públicas.

Actualización: detener, crear y verificar una copia, descomprimir la nueva versión aparte, iniciar con la carpeta de datos compatible y repetir acceso/reproducción. Para volver atrás: detener, restaurar la copia en otra carpeta e iniciar la versión anterior con esa carpeta. El esquema de esta versión es 1; se rechazan esquemas desconocidos. No hay migraciones de versiones anteriores porque esta app se creó desde cero.

## Bastión y publicación

`deploy/japs-musica.service` es una plantilla sin instalar. Crear un usuario `japs-musica`, preparar `/opt/japs-musica` y `/var/lib/japs-musica`, instalar dependencias antes de activar la unidad y verificar puerto, permisos y cortafuegos en el anfitrión. Configurar la primera cuenta por loopback (o túnel SSH local) antes de ofrecer la LAN. La conversión de un álbum usa un único FFmpeg. La integración con Drive está pendiente: el respaldo actual de Bastión tiene un límite de 256 MiB, insuficiente para asumir una colección completa. No se modificaron sus remotos, discos ni servicios.

La release 0.6.0 está publicada en MusicLand-. El ZIP probado y su SHA-256 se descargan desde los enlaces a Drive de la release. El acceso SSH a Bastión sigue pendiente. La procedencia y los permisos de las muestras se documentan por separado. [Release](https://github.com/JazminPsycho/MusicLand-/releases/tag/v0.6.0) · [Documentación de desarrollo, operación y entrega](docs/DOCUMENTACION.md)

## Limitaciones actuales

Pendientes del plan maestro: Safari en iPhone físico y sonido en los equipos de destino; prueba de carga de 5/20 minutos en Bastión; revisión completa de accesibilidad; consolidación y depuración 90 días/12 meses; códigos de error detallados; instalación en Bastión y adaptación de Drive; adjuntos de la release y ficha real en el portafolio. Los datos de eventos se conservan sin depuración automática en esta versión. La interfaz muestra progreso por pista mientras convierte, pero no porcentaje de bytes enviados. Una pista cuya subida se interrumpió se vuelve a enviar completa; no hay reanudación por byte. La cola rechaza un segundo trabajo mientras hay otro activo, en vez de mantener una lista de espera. Para cambiar límites, copiá `settings.example.json` a `settings.json` dentro de la carpeta de datos y reiniciá. El resumen permite agrupar por canción, álbum, artista o usuario. La edición permite cambiar portada conservando la anterior si falla la validación. Las portadas se normalizan a JPEG cuadrado de 800 px.

La auditoría OWASP ASVS vigente y la revisión de dependencias con avisos de seguridad se requieren antes de una exposición a internet. Los controles actuales y pruebas de autorización no reemplazan esa auditoría. CD, extracción, metadatos automáticos y piloto remoto permanecen en backlog.

## Cambios de 0.1.1

Borradores persistentes con títulos y orden, inventario de pistas recibidas, continuación de subidas parciales por archivo y reintento de conversión sin reenvío. Los cambios simultáneos se controlan con una revisión del borrador y un bloqueo por trabajo. La portada anterior se conserva si falla su reemplazo por falta de espacio. Se recuperan también los títulos locales de la versión 0.1.0. Actualización compatible con los datos existentes: se agrega una tabla de borradores sin renombrar cuentas, álbumes ni pistas.

## Cambios de 0.5.0

- Biblioteca con búsqueda sin tildes y estados vacíos diferenciados.
- Detalle de álbum, reproducción del álbum completo y pista actual destacada.
- Reproductor adaptable, con artista conservado al pasar de pista.
- Importaciones con actualización automática y acceso directo al álbum preparado.
- Escuchas por hora con barras y valores legibles.

Esta entrega conserva el esquema de datos de 0.1.1. Para volver a esa versión, detené el proceso y arrancá el paquete anterior con el mismo directorio de datos. Conservá un respaldo previo si trabajás con tu colección real.

## Cambios de 0.6.0

La búsqueda conserva el filtro al volver del álbum. El reproductor reserva espacio según su altura, ajusta los controles en anchos chicos y mantiene visible el foco. Pausar responde de inmediato y el control de posición acepta teclado.

Importar conserva los WAV recibidos tras una interrupción. Al volver al borrador, se muestran las duraciones confirmadas y se pueden seleccionar solo las pistas pendientes. Al reordenar, el foco sigue a la pista movida.

Para repetir la prueba de navegador, instalá Playwright 1.62.0 en el Python que ejecute el script, los motores y sus dependencias de sistema. La app necesita su entorno `.venv` con las dependencias de `requirements.txt`. FFmpeg debe estar disponible. Cada recorrido inicia Waitress con datos temporales y usa los WAV sintetizados de `example/`.

```sh
python3 -m playwright install chromium webkit
python3 qa/browser.py chromium
python3 qa/browser.py webkit
```

Podés usar `--width 360` para repetir un ancho o `--screenshots /ruta` para guardar capturas. La prueba usa un puerto local libre.
