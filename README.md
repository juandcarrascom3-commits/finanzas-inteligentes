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
ETORO_API_KEY=
ETORO_USER_KEY=
ETORO_BASE_URL=https://public-api.etoro.com/api/v1
ETORO_ENVIRONMENT=demo
FINANCE_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173
```

`database/*.local.db`, `database/*.personal.db` y `database/backups/` no deben versionarse. No guarde tokens reales en el repositorio.

El backend carga `.env` automáticamente al arrancar, antes de construir su configuración. La carga usa `override=False`: **las variables ya presentes en el proceso siempre ganan sobre `.env`**, así que un valor exportado en la terminal, fijado por el servicio o inyectado por las pruebas conserva prioridad. Si `.env` no existe, el backend arranca sin error usando los valores por defecto.

`.env` es local y está en `.gitignore`: no se versiona ni se comparte. Use `.env.example` como plantilla, que solo contiene placeholders vacíos.

Este proyecto es local-first: ejecute el backend con `--host 127.0.0.1` (comando en la sección 2) para que solo esta máquina pueda hablar con la API.

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
- `POST /api/market-data/sync`: actualiza precios, históricos, FX y benchmark desde provider externo hacia SQLite local.
- `GET /api/market-data/status`: estado local de provider, stale/missing, benchmark y FX.

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

## Market Data
El provider inicial es `yfinance`: no requiere API key, cubre precios diarios, históricos, benchmarks y pares FX como `USDCOP=X`, y queda detrás de una interfaz local para poder cambiarlo después. No se llama al provider desde renders ni endpoints normales de lectura; use el botón **Actualizar datos de mercado** en Invest/Wealth o `POST /api/market-data/sync`.

Los históricos se guardan en `asset_valuations` y `benchmark_prices` con `source=MARKET_DATA`, `provider`, `retrieved_at` y metadata. FX histórico se guarda en `fx_rates`. La política usa precios ajustados cuando el provider los entrega (`auto_adjust=True`) para evitar falsas caídas por splits/dividendos. Si internet falla, Finance conserva el último dato local, marca `STALE`/`UNAVAILABLE` y permite seguir usando precios manuales.

Fase v0.9 agrega controles operativos:
- `market_symbol_mappings` separa ticker interno de símbolo usado por el provider.
- `price_authority` permite `AUTO` o `MANUAL` por activo sin reescribir historia.
- Benchmark se configura desde Wealth y puede sincronizarse sin imponer un índice único.
- FX manual reutiliza `fx_rates` como fallback local.
- Quick refresh actualiza quotes/FX/benchmark reciente; Full history añade histórico incremental.

## eToro read-only
eToro usa `ETORO_API_KEY`, `ETORO_USER_KEY`, `ETORO_BASE_URL` y `ETORO_ENVIRONMENT=demo|real` en el backend. El flujo es: probar conexion, generar preview, revisar mappings/CFDs/diferencias de ledger y confirmar importacion. Finance no implementa trading, ordenes, depositos, retiros ni copy trading.

La importacion al investment ledger es idempotente por `source + external_id`. Las posiciones leidas desde eToro se usan para reconciliacion contra el ledger, no para sobrescribir holdings efectivos. Instrumentos eToro deben mapearse de forma explicita con `source=ETORO`, `external_type=instrument`, `external_id` o nombre externo y `local_id` igual al ticker interno.

## CSV de transacciones
Columnas soportadas: `date`, `amount`, `category`, `description`, `currency`, `account_id`, `external_id`.

Ejemplo:

```csv
date,amount,category,description,currency,external_id
2026-09-21,2500,Ingresos,Nomina,USD,pay-001
2026-09-22,-45.80,Alimentacion,Supermercado,USD,food-001
```
