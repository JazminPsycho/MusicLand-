# Revisión de JAPs Música · 0.5.0

Se recuperaron de Drive el ZIP y el historial de 0.1.1. El SHA-256 del ZIP coincidió con la evidencia y la rama nueva partió de df993e4bcb9f4e97beb85e8a06a7b4b294d44a15. La entrega anterior ya tenía importación recuperable, cuentas, restricciones de acceso, escucha medible y restauración. Su reporte registraba 19 pruebas y una revisión visual pendiente.

La 0.5.0 actualiza la interfaz sin migrar el esquema. Conserva las pruebas y el flujo de importación de 0.1.1.

## Evidencia de esta entrega

- En Chrome del entorno de desarrollo se revisó la pantalla de primera cuenta.
- En una instalación de prueba con un álbum sintético se comprobó buscar “ultima luz”, abrir el resultado y reproducir un MP3.
- Se verificaron cambio de pista, pausa, conservación del artista y persistencia del reproductor al abrir Escuchas. La pantalla mostró tiempo y saltos medidos.
- La cuenta y el catálogo de la sesión visual fueron desechables. El código auxiliar de la prueba queda fuera de la distribución.
- La suite incluida cubre 19 casos, incluida conversión FFmpeg, recuperación de importaciones, rangos de audio, permisos, revocación, métricas y restauración.

## Continuación autónoma

Para 0.6, automatizar el recorrido completo desde la interfaz, con carga de WAV, recuperación, cambio de pista, pausa y seek. Ejecutar los casos en Chromium y WebKit en los anchos 360, 390, 768 y 1280. Agregar validación de foco con teclado y una prueba de carga reproducible con dos clientes. Registrar resultados por motor y equipo. Validar la política de retención de métricas con fixtures antes de activar una limpieza programada.

Para 1.0 local, comprobar el servicio en Bastion con acceso ya autorizado y datos desechables. Medir CPU, RAM, disco y red en reposo, durante la importación y con dos clientes. Probar reinicio y restauración en una carpeta separada. Cuando esté disponible, medir también Safari físico. Verificar acceso a GitHub para publicar y completar la ficha de portafolio con enlaces reales.

Codex puede ejecutar estos pasos por su cuenta donde tenga acceso. Safari físico y métricas de Bastion quedan pendientes de verificación del entorno. WebKit en un entorno de desarrollo permite avanzar sin presentar esa comprobación como resultado de un iPhone real.
