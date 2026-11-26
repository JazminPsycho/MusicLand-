# Controles y límites

Contraseñas: hash scrypt con salt a través de Werkzeug; nunca texto plano. Sesiones aleatorias de 256 bits, solo hash en SQLite, 24 h, rotación al autenticar, HttpOnly/SameSite Strict y Secure cuando el transporte es HTTPS. Bootstrap restringido a loopback y token del anfitrión; se cierra al existir una cuenta. Escrituras exigen Origin coincidente. No se confía en cabeceras proxy de identidad.

Se exige cuenta activa para catálogo, portada y audio, incluidos rangos; administración para importación y cuentas. Se invalida la sesión al revocar. Cada bloque de audio comprueba acceso de nuevo; buffers ya enviados permanecen en el cliente. Login limita diez intentos por IP/ventana de cinco minutos; el límite es local al proceso y se reinicia al detenerlo.

Carga: rutas internas generadas, firma WAV y parser de imagen, límites, lectura PCM por bloques y conversión por subprocess sin shell, un FFmpeg con timeout y argumentos explícitos. Los fallos dejan el catálogo publicado utilizable. El código sirve solo recursos de `web/` y medios resueltos desde SQLite, nunca una carpeta privada por URL libre.

CSP, no-sniff y no-store; UI usa textContent para texto del catálogo. No hay CDNs ni cargas automáticas a terceros. El enlace al portafolio solo se abre si la usuaria lo sigue.

No se ha realizado auditoría ASVS completa ni análisis contra una base actual de vulnerabilidades. No habilitar internet con esta entrega. Datos de escucha permanecen sin política automática de retención implementada; comunicar esa condición antes de incorporar oyentes reales. Los tests son evidencia limitada a los casos documentados.
