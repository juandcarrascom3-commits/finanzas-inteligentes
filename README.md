# Finanzas Inteligentes: Dashboard de Riqueza, Riesgo y Panorama

Plataforma integral de gestión patrimonial, proyección financiera y control de riesgo con arquitectura responsiva de tres niveles, basada en los bocetos estratégicos del usuario (`JERARQUIA`, `DISTRIBUCION`, `ESTILO`, `INFORME`).

---

## 🏛️ Arquitectura del Sistema (3 Niveles)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ HEADER: Finanzas Inteligentes | Switcher USD ($) / COP ($) | Quota Meter 25 req/día    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ TIER 1: TOP KPI ROW (Resumen de Alto Nivel)                                            │
│ • Patrimonio Neto Total (USD / COP) • Tasa de Ahorro Mensual (Meta 30%)                │
│ • Rendimiento TWR vs MWR (TIR)      • Métricas de Riesgo (Beta, Sharpe, Max Drawdown)  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ TIER 2: CENTRAL VISUAL SECTION (Visualizaciones Clave)                                 │
│ • Asset Allocation Treemap: Jerarquía Tipo de Activo -> Sector Económico -> Tickers    │
│ • Evolución Temporal: Curva de Crecimiento vs. S&P 500 (Base 100) y Spread de Alfa     │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ TIER 3: BOTTOM TAB SECTION & GRANULAR CONTROLS (Pestañas Granulares)                   │
│ [ Panorama ]  [ Lista de Activos ]  [ Tesis de Inversión ]  [ Ingestión API ] [ Informe]│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Requisitos y Puesta en Marcha

### 1. Entorno de Ejecución
- **Python 3.12+** (Backend FastAPI, Motor Cuantitativo y SQLite)
- **Node.js LTS (v24+) y npm** (Frontend Vite + React + Tailwind CSS)

### 2. Iniciar Backend (FastAPI + SQLite / Supabase Parity)
```powershell
# Activar entorno virtual de Python
.\.venv\Scripts\Activate.ps1

# Ejecutar servidor FastAPI en puerto 8000
.\.venv\Scripts\uvicorn.exe backend.app:app --host 127.0.0.1 --port 8000 --reload
```

El backend expone:
- `GET /api/dashboard`: KPIs, Treemap de asignación, curva de evolución temporal y estado de cuota.
- `GET /api/panorama`: Proyecciones a 3, 6, 12 meses y checklist semafórico presupuestal.
- `GET /api/assets`: Grilla de activos (Portafolio vs Activos en Observación).
- `POST /api/theses`: Formulario del Filtro Humano con variables cualitativas de Investing Pro.
- `POST /api/simulate-purchase`: **Guardrail de Seguridad**: Bloquea órdenes de compra si no se aprueba el checklist humano.
- `POST /api/budgetbakers/sync`: Ingestor desacoplado con límite estricto de 25 peticiones diarias y caché SHA-256.

### 3. Iniciar Frontend (Vite + React)
```powershell
cd frontend
$env:PATH = "C:\Program Files\nodejs;" + $env:PATH
npm.cmd run dev
```
La aplicación web abrirá en `http://localhost:3000`.

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

## 🔄 Ingestión REST API & Protección de Cuota Gratuita (BudgetBakers)
- **Límite Estricto**: 25 peticiones por día registradas en la tabla `api_daily_quota`.
- **Caché Hashed**: Las llamadas idénticas se resuelven en memoria/SQLite durante 6 horas sin debitar la cuota diaria.
- **Modo Fallback**: En caso de agotamiento de cuota, el sistema entrega la última respuesta en caché con una alerta visual de seguridad.
