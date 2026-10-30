# Matriz de validación de seguridad — Turnos IESS

Esta matriz conecta los riesgos y controles definidos en el diseño seguro con evidencias reproducibles del prototipo. Los datos son sintéticos y las pruebas se ejecutan únicamente en entorno local.

## Controles y evidencia

| Área | Riesgo cubierto | Evidencia | Resultado esperado |
|---|---|---|---|
| Autenticación | Credenciales débiles, toma de cuenta | `manage.py test turns`, TOTP manual | Contraseña incorrecta y TOTP inválido rechazan el acceso |
| Sesión | Robo o abuso de sesión | Cookies y expiración manual | HttpOnly, SameSite, sesión de 15 minutos y logout por POST |
| Rate limiting | Fuerza bruta | Cinco logins fallidos | Bloqueo temporal por cuenta/IP |
| Autorización | IDOR y escalamiento horizontal | Tests de representación y cancelación | Solo el titular o permiso explícito puede actuar |
| Lógica de negocio | Doble reserva | Test de especialidad y restricción de cupo | Una reserva activa por paciente/especialidad y por cupo |
| Validación/XSS | Inyección HTML | Test de escape y ZAP | No se ejecutan etiquetas ni scripts enviados por usuario |
| CSRF | Acciones forjadas | Cliente con verificación CSRF | POST sin token devuelve 403 |
| Auditoría | Alteración o ausencia de trazabilidad | `manage.py verify_audit` | La cadena de hashes se verifica o informa corrupción |
| Dependencias | CVE en paquetes | `pip-audit --local` | No hay vulnerabilidades conocidas en el entorno auditado |
| Código | Patrones inseguros | Bandit sobre `config`, `turns` y `manage.py` | Cero hallazgos High/Medium/Low no justificados |
| Dependencias externas | Caída o timeout de agenda | `DEMO_AGENDA_MODE=unavailable/timeout` | Se muestra modo degradado sin exponer información clínica |
| Configuración | Errores de despliegue | `manage.py check --deploy` | Las advertencias se revisan y se clasifican por entorno |

## Ampliaciones opcionales

La ejecución rápida usa SQLite y caché local para facilitar la demostración. PostgreSQL y Valkey están descritos en `docker-compose.yml` y se activan mediante variables de entorno. La comparación debe documentar que SQLite no representa por sí sola la concurrencia de producción.

## Criterios de aceptación

- Ninguna alerta High en ZAP.
- La CSP no contiene `unsafe-inline`.
- Bandit sin hallazgos no justificados.
- `pip-audit --local` sin vulnerabilidades conocidas.
- Todos los tests automatizados pasan.
- Las pruebas manuales de titular, representante y auditor producen los eventos esperados.
- Las fallas de agenda no provocan exposición de datos ni error 500.
