# Evidencia técnica · 26/11/2026

Entorno comprobado: contenedor Debian 13 x86_64; Python 3.12.14; FFmpeg 7.1.5; SQLite según módulo de Python; Flask 3.1.3; Waitress 3.0.2; Pillow 13.0.0. Esto no identifica el hardware de Juggernaut ni Bastión.

Comandos ejecutados desde el checkout:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
node --check web/app.js
.venv/bin/python -m py_compile server.py manage.py
```

Resultado: **13 pruebas pasaron** (aproximadamente 3 s en la última ejecución completa previa a empaquetar); dependencias sin incompatibilidades declaradas; sintaxis Python y JavaScript válida. La prueba de importación usa FFmpeg real para convertir PCM a MP3 y verifica deduplicación por contenido. La restauración compara un hash de medios e integridad SQLite; revoca sesiones restauradas y rechaza destino existente o copia alterada.

Cobertura:

- Token inicial, origen y protección de última administradora; dos solicitudes concurrentes de bootstrap producen 200/409.
- Usuarios anónimos, pendientes, oyentes y revocados: autorización de catálogo/audio y administración. Revocación durante un generador activo de audio y rechazo de nuevas solicitudes.
- HEAD, Range 206 y 416, audio ausente; finalización del flujo al revocar.
- Límites de login: diez fallos y respuesta 429 en el siguiente intento.
- WAV corrupto, portada SVG rechazada, WAV válido convertido y duplicado exacto sin segundo álbum.
- Disco lleno simulado; FFmpeg fallido; trabajo interrumpido identificado después de reinicio; catálogo anterior preservado.
- 20 s de 60 s: cero escuchas; 35 s: una escucha. Seek 0→50: cero segundos; final con 10 s: incompleto. Reintento diez veces: mismo total. Cobertura de 54 s seguida de final coherente: completo. Secuencia futura y valores no finitos rechazados.
- Edición de títulos conserva IDs; edición con pistas faltantes se rechaza sin cambios.

El intento de vista previa con `sites-preview start` falló al crear un socket (`PermissionError: Operation not permitted`). No hubo revisión visual de escritorio/móvil ni captura real. No se usó otro servidor para eludir esa limitación. La prueba de instalación limpia usa el cliente WSGI y el lanzador con `--help`; no demuestra apertura real del puerto en este contenedor.

## Pruebas de dispositivo y despliegue pendientes

En Juggernaut: iniciar desde ZIP en carpeta con espacios; probar navegación a 360, 390, 768 y 1280 px; teclado y foco, zoom, lector de pantalla y superposición del reproductor. Importar un álbum con música autorizada. Confirmar sonido y uso cómodo.

En iPhone 13 Pro/Safari: anotar iOS real, escuchar, pausar, avanzar, bloquear pantalla, regresar y revisar estado. Confirmar reproducción con el equipo anfitrión en la LAN. Probar cuenta pendiente/aprobada/revocada desde un segundo navegador.

En Bastión: resolver destino y verificar huella y SO; inspeccionar servicios y respaldos actuales; instalar aisladamente; medir 5 minutos de reposo y 20 minutos con dos clientes. Registrar CPU/RSS, RAM disponible, swap, disco, red y cortes, con importación aparte. Objetivos orientativos: menos de 150 MiB en reposo y 250 MiB en reproducción. No hay mediciones reales de estos recorridos ni promesa de cumplimiento.

Antes de internet: auditoría contra la versión vigente de OWASP ASVS, análisis de avisos de seguridad de dependencias, HTTPS, pruebas de retirada y revocación; resolver hallazgos altos/críticos. El servidor HTTP local no constituye un despliegue público seguro.

## Instalación limpia desde ZIP

Se generó el ZIP con `git archive`, se descomprimió en `/tmp/JAPs instalacion limpia/JAPs-Musica-v0.1.0`, se creó un venv nuevo y se instalaron todas las versiones fijadas desde wheels descargados de PyPI. No se reutilizó el venv de desarrollo. Resultado en esa copia: **13 passed in 2.72s**. `sh start.sh --help` encontró las dependencias y mostró las opciones correctamente. La suite volvió a convertir WAV, verificar deduplicación y restaurar en un destino independiente. La apertura de un puerto HTTP permanece sin verificar por la restricción de sockets descrita arriba.

Comandos equivalentes para la verificación de la copia (con red disponible):

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
sh start.sh --help
```

La búsqueda de patrones de claves privadas, tokens GitHub, claves AWS y credenciales incrustadas en URLs no encontró coincidencias en el fuente preparado. Las contraseñas de fixtures son desechables. Esto es un control de patrones, no una auditoría exhaustiva del historial ni de dependencias.

## Recuperación de importaciones · 0.1.1

`tests/test_import_recovery.py` agrega seis pruebas de integración. Se guarda un álbum de dos pistas, se sube una y se crea una aplicación nueva sobre los mismos datos. El cliente recupera metadatos/revisión y el inventario exacto; subir solo la pista pendiente permite convertir el álbum en el orden original. Otro caso provoca un fallo de FFmpeg, reinicia la aplicación y convierte con los WAV conservados sin nuevas subidas.

También se verifican conflictos de edición y arranque con una revisión anterior (409), rechazo de slots repetidos o inválidos, exclusión mutua entre escritura y conversión, denegación a anónimos/oyentes, conservación del WAV anterior frente a reemplazo corrupto y conservación de portada ante ENOSPC simulado. Resultado de la suite completa: **19 pruebas aprobadas**. Sintaxis Python/JavaScript verificada.

La vista previa volvió a fallar: `relay could not open browser port 4173: timed out waiting for relay readiness`. Se consultó el estado del entorno y se detuvo la vista previa. No se afirma haber probado la UI con navegador. La evidencia de esta versión es integración HTTP/WSGI y revisión del código.
