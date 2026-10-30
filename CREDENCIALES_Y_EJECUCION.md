# Turnos IESS — credenciales y ejecución

Guía rápida para ejecutar el prototipo local con datos sintéticos.

## Requisitos

- Python y el entorno virtual del proyecto.
- PowerShell.
- Docker Desktop únicamente si se desea probar PostgreSQL y Valkey mediante `docker-compose.yml`.

## Ejecución local

Desde la carpeta del proyecto:

```powershell
$py = "D:\ESPE\Seguridad\Examen\.venv\Scripts\python.exe"
$env:DEMO_PASSWORD = "DemoPass1234!"

& $py manage.py migrate
& $py manage.py seed_demo
& $py manage.py runserver 127.0.0.1:8000
```

Abrir en el navegador:

```text
http://127.0.0.1:8000/login/
```

## Credenciales de prueba

| Perfil | Cédula | Contraseña | TOTP |
|---|---:|---|---|
| Afiliado | `999999001` | `DemoPass1234!` | No requiere |
| Representante | `999999002` | `DemoPass1234!` | No requiere |
| Atención al usuario | `999999003` | `DemoPass1234!` | Sí |
| Médico | `999999004` | `DemoPass1234!` | Sí |
| Auditor | `999999005` | `DemoPass1234!` | Sí |

Los códigos TOTP del personal se muestran en la consola al ejecutar `seed_demo`. Son temporales para esta demostración. Si no aparecen porque la base ya fue inicializada, se puede reiniciar la base demo:

```powershell
Remove-Item -LiteralPath .\db.sqlite3
& $py manage.py migrate
& $py manage.py seed_demo
```

El comando anterior elimina solamente la base SQLite local del prototipo.

## Flujo mínimo

1. Iniciar sesión como afiliado.
2. Consultar disponibilidad.
3. Reservar un turno.
4. Verificarlo en el panel.
5. Cancelarlo.
6. Iniciar sesión como representante y comprobar la representación del titular.
7. Iniciar sesión como auditor y revisar `/audit/`.

## Validaciones rápidas

```powershell
& $py manage.py check
& $py manage.py test turns
& $py manage.py verify_audit
```

## Docker Compose opcional

El prototipo funciona por defecto con SQLite y caché local. Para levantar los servicios previstos de PostgreSQL y Valkey:

```powershell
docker compose up -d
```

Para detenerlos:

```powershell
docker compose down
```

El uso de estos servicios requiere configurar las variables `POSTGRES_HOST` y `REDIS_URL` descritas en `.env.example`. No es necesario para la demostración local básica.

## Detener el servidor

En la terminal donde está ejecutándose Django, presionar:

```text
Ctrl+C
```
