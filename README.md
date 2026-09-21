# Finanzas Inteligentes

Dashboard local de finanzas personales en fase v0.4. Puede trabajar con datos DEMO/seed para desarrollo o con una base local personal vacia configurada por entorno. Wallet by BudgetBakers puede conectarse en modo real de solo lectura mediante token.

---

## Arquitectura actual

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ HEADER: Finanzas Inteligentes | Switcher USD/COP | Privacidad | Actualizar             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ OVERVIEW: KPIs, allocation, What Changed, Action Center                                 │
│ • Patrimonio Neto Total (USD / COP) • Tasa de Ahorro Mensual (Meta 30%)                │
│ • Rendimiento TWR vs MWR (TIR)      • Métricas de Riesgo (Beta, Sharpe, Max Drawdown)  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PLAN: budgets, recurrentes, forecast y cierre mensual                                  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ INVEST: portfolio y tesis                                                              │
│ DATOS: cuentas, activos, transacciones, CSV, Wallet, reconciliacion y backup           │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Requisitos y Puesta en Marcha

### 1. Entorno de Ejecución
- Python 3.12+
- Node.js LTS y npm

Copie `.env.example` a `.env` para usar datos personales locales:

```powershell
Copy-Item .env.example .env
```

Por defecto recomendado para uso real:

```text
FINANCE_DB_PATH=database/finance.local.db
FINANCE_SEED_DEMO=0
BUDGETBAKERS_API_TOKEN=
BUDGETBAKERS_BASE_URL=https://rest.budgetbakers.com/wallet
```

`database/*.local.db`, `database/*.personal.db` y `database/backups/` no deben versionarse. No guarde tokens reales en el repositorio.

La estrategia de migraciones SQLite es incremental:
- `database/migrations/001_sqlite_local.sql`: baseline local.
- `database/migrations/002_sqlite_operational_hardening.sql`: indices operativos.
- La tabla `schema_migrations` registra version, archivo, checksum y fecha aplicada. No edite migraciones ya aplicadas; agregue una nueva.

### 2. Iniciar Backend (FastAPI + SQLite / Supabase Parity)
```powershell
# Crear y activar entorno virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -r backend\requirements.txt

# Ejecutar servidor FastAPI en puerto 8000
uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```

El backend expone:
- `GET /api/dashboard`: KPIs, Treemap de asignación, curva de evolución temporal y estado de cuota.
- `GET /api/panorama`: Proyecciones a 3, 6, 12 meses y checklist semafórico presupuestal.
- `GET/POST/DELETE /api/accounts`: cuentas personales.
- `GET /api/assets`: Grilla de activos (Portafolio vs Activos en Observación).
- `POST/DELETE /api/assets`: alta, edicion y eliminacion de activos.
- `GET/POST/DELETE /api/transactions`: transacciones personales.
- `POST /api/import/transactions/preview`: preview CSV.
- `POST /api/import/transactions`: importacion CSV.
- `GET /api/backup`: export local de backup con metadata de esquema.
- `POST /api/backup/validate`: valida integridad SQLite y tablas requeridas.
- `POST /api/backup/restore`: restaura un backup validado y crea copia pre-restore.
- `GET /api/budgetbakers/status`: estado de Wallet sin exponer token.
- `POST /api/budgetbakers/test`: prueba de conexion real.
- `POST /api/budgetbakers/preview`: lee cuentas/registros y devuelve preview sin guardar.
- `POST /api/budgetbakers/import`: confirma e importa el preview.
- `POST /api/theses`: Formulario del Filtro Humano con variables cualitativas de Investing Pro.
- `POST /api/simulate-purchase`: **Guardrail de Seguridad**: Bloquea órdenes de compra si no se aprueba el checklist humano.

### 3. Iniciar Frontend Principal (Vite + React)
```powershell
cd frontend
npm install
npm run dev
```
La aplicación web abrirá en `http://localhost:3000`.

### 4. Verificacion
```powershell
# Backend
pytest backend\tests -q

# Frontend
cd frontend
npm run build
```

---

## 🛡️ Filtro Humano: Guardrail de Inversión
La aplicación implementa una barrera estricta que impide que la emoción domine las decisiones de compra:
1. **Comprensión del Negocio (Moat)**
2. **Solvencia (Deuda Neta / EBITDA < 3x)**
3. **Margen de Seguridad (Mínimo 20% cuantitativo)**
4. **Timing Técnico (Fuera de sobrecompra extrema)**
5. **Control de Sesgos (Libre de FOMO)**

Si la tesis no cumple los 5 criterios, el botón de simulación y compra queda **estrictamente bloqueado**.

---

## Ingestion Wallet
Wallet by BudgetBakers usa `BUDGETBAKERS_API_TOKEN` en el backend y no expone el token al navegador. El flujo es: probar conexion, generar preview, revisar conteos y confirmar importacion. La importacion es idempotente por `source + external_id`.

## CSV de transacciones
Columnas soportadas: `date`, `amount`, `category`, `description`, `currency`, `account_id`, `external_id`.

Ejemplo:

```csv
date,amount,category,description,currency,external_id
2026-09-21,2500,Ingresos,Nomina,USD,pay-001
2026-09-22,-45.80,Alimentacion,Supermercado,USD,food-001
```
