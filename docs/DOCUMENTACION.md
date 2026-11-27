# JAPs Música · Desarrollo, operación y entrega

**Estado al 27 de noviembre de 2026.** La versión 0.6.0 está publicada en el repositorio público MusicLand- y su paquete probado está en Drive. La aplicación sirve una colección privada desde un equipo anfitrión, con acceso por cuenta dentro de una red de confianza. La publicación en GitHub corresponde al código y a la release. [Repositorio](https://github.com/JazminPsycho/MusicLand-) · [Release v0.6.0](https://github.com/JazminPsycho/MusicLand-/releases/tag/v0.6.0) · [Carpeta de Drive](https://drive.google.com/drive/folders/1ffBDPf5ZefuuWJLR1bKwnjXI-QCs62ok)

## Evolución del proyecto

| Entrega | Trabajo realizado | Referencia |
| --- | --- | --- |
| 0.1.0 | Implementación desde cero autorizada por Jazmín. Biblioteca, álbumes, importación de WAV, conversión a MP3, reproductor, cuentas y permisos, registro de escucha, respaldo y restauración. Se prepararon un lanzador, dependencias fijadas, muestras originales y una plantilla de servicio. | `ebb18db` |
| 0.1.1 | Borradores persistentes con orden de pistas y revisión, inventario de WAV recibidos, recuperación por pista y reintento de conversión. Se probaron conflictos entre ediciones, reinicios, disco lleno y conservación de archivos previos. | `df993e4` |
| 0.5.0 | Búsqueda sin tildes, estados vacíos, detalle de álbum, pista actual destacada, reproductor adaptable, actualización automática de importaciones y gráfico por hora. Recuperé el bundle y el ZIP de Drive y comparé todos los archivos con el tag antes de usarlo como base. | `318d3f0` |
| 0.6.0 | La búsqueda conserva el filtro al volver del álbum. El reproductor ajusta su espacio a su altura y controla avance con teclado. La importación muestra la duración confirmada y devuelve el foco a la pista reordenada. Se automatizó el recorrido en Chromium y WebKit. | `e4da8af` |
| Publicación | Integré el historial de JAPs Música en `MusicLand-`, conservé su commit inicial y verifiqué que el árbol de publicación del código coincidiera con el tag probado. Publiqué la release con enlaces al ZIP y su suma en Drive. | `103327b` |

El proceso pasó de pruebas HTTP con Flask a pruebas en navegadores reales contra Waitress. Al principio la infraestructura de vista previa falló. Para 0.6.0 usé Playwright en un servidor temporal y resolví las dependencias y el acceso a temporales que WebKit necesitaba para reproducir audio.

## Arquitectura y archivos

| Ubicación | Responsabilidad |
| --- | --- |
| [`server.py`](https://github.com/JazminPsycho/MusicLand-/blob/main/server.py) | Flask y Waitress, arranque, sesiones, autorización, catálogo, importación, audio por rangos HTTP y estadísticas. |
| [`web/`](https://github.com/JazminPsycho/MusicLand-/tree/main/web) | Interfaz HTML, CSS y JavaScript. Biblioteca, búsqueda, álbum, reproductor, importación, cuentas y escuchas. Conserva la paleta morada, crema, lila y dorada del portafolio. |
| [`start.sh`](https://github.com/JazminPsycho/MusicLand-/blob/main/start.sh) | Prepara el entorno virtual, instala requisitos fijados y arranca la aplicación. |
| [`manage.py`](https://github.com/JazminPsycho/MusicLand-/blob/main/manage.py) | Copia consistente de SQLite y medios, manifiesto SHA-256 y restauración en un destino separado. |
| [`tests/`](https://github.com/JazminPsycho/MusicLand-/tree/main/tests) y [`qa/browser.py`](https://github.com/JazminPsycho/MusicLand-/blob/main/qa/browser.py) | Pruebas de integración del servidor y recorrido automatizado en navegador. |
| [`example/`](https://github.com/JazminPsycho/MusicLand-/tree/main/example) | Tres WAV sintetizados originales, regenerador y procedencia. |
| [`deploy/japs-musica.service`](https://github.com/JazminPsycho/MusicLand-/blob/main/deploy/japs-musica.service) | Plantilla systemd para Bastión. Queda por instalar y validar en ese equipo. |

SQLite conserva usuarios, sesiones, álbumes, pistas, trabajos, borradores, intentos y eventos de reproducción. Los datos viven fuera del código, por defecto en `~/.local/share/japs-musica`. Podés configurar otra carpeta mediante `--data` y ajustar los límites con [`settings.example.json`](https://github.com/JazminPsycho/MusicLand-/blob/main/settings.example.json) como referencia.

### Cómo funciona cada recorrido

- **Encontrar y reproducir.** La biblioteca busca por álbum, artista o canción y normaliza mayúsculas y tildes. El detalle conserva la pista actual y el reproductor sigue visible al navegar. Hay pausa, pista anterior y siguiente, avance y paso al terminar la pista. El espacio inferior se calcula con la altura del reproductor.
- **Importar un álbum.** La administradora carga WAV PCM, títulos, artista, orden y una portada JPEG o PNG opcional. El servidor valida los archivos, procesa un trabajo a la vez y usa FFmpeg para generar MP3 estéreo a 192 kb/s. Los álbumes se incorporan al catálogo cuando termina el trabajo. Los duplicados por contenido se detectan antes de crear otro álbum.
- **Recuperar una importación.** En **Importaciones**, elegí **Abrir y continuar**. Los títulos, el orden y las pistas recibidas sobreviven a la recarga. Reenviá los WAV que quedaron pendientes. Si una conversión falló y se conservaron sus WAV, **Reintentar conversión** los reutiliza. Si se cortó la escritura de una pista, esa pista se envía completa. La revisión del borrador detecta ediciones de otra pestaña y el bloqueo por trabajo serializa los cambios.
- **Administrar acceso.** La primera cuenta se crea desde el anfitrión con un token de configuración. Las cuentas oyentes quedan pendientes hasta su aprobación. La revocación invalida sesiones y restringe nuevas solicitudes de audio. El reproductor puede conservar datos ya recibidos por el navegador.
- **Consultar escuchas.** El resumen agrupa por canción, álbum, artista o usuario. Una escucha cuenta a partir del menor valor entre 30 segundos y el 50 % de la pista. Completar exige cobertura única de al menos el 90 % y un final coherente. Adelantar suma cero. Los eventos duplicados se descartan y el resumen usa la zona `America/Argentina/Cordoba`. La depuración periódica de eventos sigue pendiente.

## Instalar y operar

1. Descargá y descomprimí el ZIP verificado en una carpeta propia. Compará su suma con el archivo SHA-256. [ZIP](https://drive.google.com/file/d/1snONDdHNa5DCgbnRGdj4dAui6Jgf-Dqa/view) · [SHA-256](https://drive.google.com/file/d/1drt63l1nL9ZuCwyZZxb17bUnGn25XHBH/view)
2. En Linux, con Python 3.11 o posterior, `venv` y FFmpeg, ejecutá `sh start.sh --desktop`. La primera ejecución instala las dependencias.
3. Abrí `http://127.0.0.1:8765` en el anfitrión. Usá el token que muestra el lanzador para crear la administradora. Elegí una contraseña de al menos 12 caracteres.
4. Importá los WAV de `example/` como un álbum y probá buscar y reproducir una pista. Detené el proceso con **Ctrl+C**.
5. Para escuchar desde otro dispositivo de una LAN de confianza, primero creá la cuenta desde el anfitrión y luego iniciá con `sh start.sh --host 0.0.0.0 --port 8765`. Usá la IP vigente del anfitrión. La versión actual usa HTTP y está destinada a esa red local.

### Copia, restauración y actualización

Detené el servidor. Usá destinos nuevos y separados. La restauración verifica los hashes, revisa la integridad de SQLite e invalida las sesiones restauradas. Conserva catálogo, medios, cuentas y estadísticas. Los WAV temporales de importación se vuelven a seleccionar cuando faltan después de restaurar.

```sh
.venv/bin/python manage.py backup '/ruta/datos' '/ruta/nueva/copia'
.venv/bin/python manage.py restore '/ruta/nueva/copia' '/ruta/nueva/restauracion'
sh start.sh --data '/ruta/nueva/restauracion'
```

Para actualizar, hacé una copia verificada antes de cambiar de versión. Descomprimí la versión nueva en otra carpeta. Para volver atrás, recuperá la copia en un destino nuevo y abrilo con la versión anterior. La plantilla de Bastión está separada del mecanismo de recuperación local.

## Qué se verificó en 0.6.0

| Entorno | Resultado |
| --- | --- |
| Debian 13 x86_64, Python 3.12.14 y FFmpeg 7.1.5 | ZIP descomprimido en una carpeta nueva con espacios. El lanzador preparó un venv nuevo con dependencias fijadas. La suite pasó **19 pruebas en 4,52 s**. |
| Chromium 156.0.8078.79 con Playwright 1.62.0 | Pasaron los recorridos a **360, 390, 768 y 1280 px**. |
| WebKit 26.5 con Playwright 1.62.0 | Pasaron los recorridos a **360, 390, 768 y 1280 px** en Linux. |
| Drive | Los cuatro archivos nuevos se descargaron y coincidieron byte por byte con los originales. El ZIP y el bundle de 0.5.0 siguieron presentes. |
| GitHub | Se verificó `main` en `103327b` antes de esta documentación, el tag `v0.6.0` sobre `e4da8af` y la release publicada. |

La suite de servidor cubrió permisos y revocación, límite de intentos de login, rangos de audio, archivos inválidos, duplicados, fallos de conversión, disco lleno, recuperación de importaciones, eventos de escucha y restauración con verificación de hashes. En cada ancho de navegador se creó una cuenta desechable y se usaron WAV de ejemplo. Se interrumpió la segunda subida, se recargó la página y se comprobó que solo volviera a enviarse esa pista. Después se verificaron búsqueda sin tildes, selección con teclado, audio en reproducción, pausa, adelanto y cambio de pista. También se comprobaron foco, controles principales de al menos 44 × 44 px, ausencia de desborde horizontal y espacio para mostrar el final del contenido por encima del reproductor. [Informe de verificación](https://docs.google.com/document/d/1Gib6xEh44-X-UAAweroyGOirBko-Jar2/edit)

Para reproducir las comprobaciones, ejecutá desde el directorio extraído. Playwright requiere sus motores y las bibliotecas del sistema correspondientes.

```sh
sh start.sh --help
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m pip install playwright==1.62.0
.venv/bin/python -m playwright install chromium webkit
.venv/bin/python qa/browser.py chromium
.venv/bin/python qa/browser.py webkit
```

Podés agregar `--width 360` para repetir un solo ancho. El script arranca Waitress en un puerto local y usa datos temporales.

## Publicaciones y recuperación del código

El ZIP se generó desde el commit `e4da8afc7027c9439dbbc8240b9b96c2a6c81898`. El tag permanece en ese commit. La rama `main` integra el historial inicial de MusicLand- y esta documentación. GitHub devolvió HTTP 401 al cargar archivos adjuntos, por lo que la release publicada enlaza los archivos idénticos de Drive. [Release](https://github.com/JazminPsycho/MusicLand-/releases/tag/v0.6.0)

```text
066f05957e746b6135ae156763abca2b0c1832d3fadb85930a7b318b41141028  JAPs-Musica-v0.6.0.zip
```

- **Drive.** Paquete, suma, informe y bundle recuperables. [Carpeta de JAPs Música](https://drive.google.com/drive/folders/1ffBDPf5ZefuuWJLR1bKwnjXI-QCs62ok)
- **GitHub.** Fuente, historial, tag y release. [MusicLand-](https://github.com/JazminPsycho/MusicLand-)
- **Bundle.** Copia Git de la entrega anterior a la integración con MusicLand-. Para recuperarla, descargá el archivo y clonalo con `git clone --branch avance-v06 JAPs-Musica-v0.6.0-historial.bundle japs-musica`. [Historial Git](https://drive.google.com/file/d/1CouYKNU7YME8WfhWDMwPkaMOcRuCin7_/view)

## Pendientes

- **Validación física.** Safari del iPhone, uso durante el bloqueo de pantalla y calidad de sonido en los equipos de destino.
- **Bastión.** Acceso SSH a una carpeta aislada para medir reposo, importación y dos clientes simultáneos. Quedan por validar rendimiento, reinicio y restauración en el equipo. La versión se mantiene en 0.6.0 hasta contar con esas comprobaciones.
- **Release.** Adjuntar el ZIP y el SHA-256 a GitHub cuando haya acceso de carga de archivos. El ZIP verificado está disponible mediante los enlaces publicados.
- **Portafolio.** Se preparó una propuesta de ficha. Al momento de la comprobación, la galería mostraba solamente la ficha de Steam. [Borrador de ficha](https://github.com/JazminPsycho/MusicLand-/blob/main/docs/portafolio.json)
- **Trabajo posterior.** Retención y consolidación de métricas, integración con respaldos de Bastión, auditoría de seguridad para exposición a internet y revisión completa de accesibilidad. [Controles y límites actuales](https://github.com/JazminPsycho/MusicLand-/blob/main/docs/seguridad.md)
