# Turnos IESS — prototipo seguro

Prototipo local para demostrar controles de seguridad del ejercicio. No pretende implementar la arquitectura institucional completa: usa SQLite, datos sintéticos y servicios externos simulados. PostgreSQL, Redis/Valkey, Caddy/Nginx, Docker, SMTP real y WebAuthn quedan como decisiones de producción documentadas, no como dependencias necesarias para la demostración.

## Ejecución

```powershell
$env:DEMO_PASSWORD="DemoPass1234!"
\.venv\Scripts\python.exe manage.py migrate
\.venv\Scripts\python.exe manage.py seed_demo
\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Abrir `http://127.0.0.1:8000/login/`.

Credenciales sintéticas (la contraseña es la definida en `DEMO_PASSWORD`; si se omite, el comando genera una aleatoria y la imprime):

- Afiliado: cédula `999999001`, contraseña `DemoPass1234!`.
- Representante: cédula `999999002`, contraseña `DemoPass1234!`.
- Personal: cédulas `999999003` a `999999005`, contraseña `DemoPass1234!` y el TOTP mostrado por `seed_demo`.

## Controles demostrables

- Argon2 para contraseñas y sesión con cookie HttpOnly/SameSite, duración limitada y cierre al salir.
- CSRF, CSP, `nosniff`, `frame-ancestors`, política de referencia y permisos del navegador.
- TOTP para personal interno.
- Limitación temporal de intentos fallidos de acceso.
- Autorización a nivel de objeto: un usuario no puede cancelar el turno de otro cambiando un identificador.
- Representación emitida por el titular, con alcance, fecha de expiración y acciones separadas.
- Restricción de un turno activo por paciente y especialidad y de un paciente por cupo.
- Notificaciones sin diagnóstico ni datos clínicos.
- Auditoría estructurada con hash encadenado, incluyendo resultados DENIED.

## Prueba funcional general

1. Ejecutar `migrate`, `seed_demo` y `runserver`.
2. Iniciar sesión como afiliado (`999999001`) y consultar disponibilidad.
3. Reservar un turno y comprobar que aparece en el panel.
4. Intentar reservar otro turno de la misma especialidad: debe rechazarse.
5. Cancelar el turno y comprobar que se genera la notificación.
6. Autorizar al representante (`999999002`) desde el titular, asignando solo `Consultar` y `Reservar`.
7. Iniciar sesión como representante y comprobar que puede reservar para el titular, pero no cancelar si ese permiso no fue concedido.
8. Probar un usuario de personal con contraseña correcta y TOTP incorrecto: el acceso debe rechazarse.
9. Probar cinco accesos fallidos: debe aparecer el bloqueo temporal.
10. Acceder como auditor y revisar que existan eventos de éxito y denegación.

## Prueba de seguridad con ZAP

Ejecutar el escaneo sobre la versión actual y revisar que la política CSP ya no contenga `unsafe-inline`. Para una prueba autenticada, crear un contexto con la sesión del afiliado o del representante e incluir `/`, `/availability/`, `/slots/*/book/`, `/appointments/*/cancel/` y `/representations/create/`. Usar solamente datos sintéticos.

La ausencia de alertas High no prueba por sí sola la autorización de objetos: los casos IDOR, alcance de representación, duplicidad de turnos y permisos por rol deben validarse también con las pruebas automatizadas y los pasos funcionales anteriores.

## Pruebas

```powershell
\.venv\Scripts\python.exe manage.py check
\.venv\Scripts\python.exe manage.py test turns
```

Herramientas opcionales de revisión:

```powershell
pip install -r requirements-dev.txt
bandit -r . -x .venv,turns/migrations
pip-audit -r requirements.txt
coverage run .venv\Scripts\python.exe manage.py test turns
coverage report
\.venv\Scripts\python.exe manage.py check --deploy
```

## Infraestructura opcional

`docker-compose.yml` levanta PostgreSQL y Valkey para probar la configuración prevista en el diseño. La ejecución rápida sigue funcionando con SQLite y caché local. Para usar la variante de infraestructura, instalar `requirements-infra.txt`, copiar `.env.example` a `.env`, iniciar `docker compose up -d` y ejecutar las migraciones con las variables de entorno cargadas.

La variable `DEMO_AGENDA_MODE` permite demostrar dependencia externa disponible o modo degradado: `healthy`, `unavailable` o `timeout`. La pantalla informa el estado sin exponer datos clínicos.

Para verificar la integridad de auditoría:

```powershell
\.venv\Scripts\python.exe manage.py verify_audit
```

Para ZAP, ejecutar el servidor con datos sintéticos y usar primero un escaneo Baseline. Después autenticar un contexto de prueba y repetir el escaneo con las rutas `/login/`, `/`, `/availability/` y las acciones POST. El criterio del prototipo es cero alertas High y revisar manualmente cada Medium; ZAP no sustituye las pruebas de autorización ni permite afirmar seguridad absoluta.

## Alcance conocido

SQLite permite una demostración reproducible, pero la concurrencia real debe validarse con PostgreSQL. No se conectan APIs del IESS ni se envían notificaciones reales. El prototipo no almacena historia clínica, diagnóstico, recetas ni documentos médicos.
