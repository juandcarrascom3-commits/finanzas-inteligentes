-- ====================================================================
-- FINANZAS INTELIGENTES: INITIAL SEED DATA
-- Seed: initial_seed.sql
-- ====================================================================

-- 1. Populate Assets
INSERT INTO assets (ticker, name, asset_type, sector, country, quantity, avg_price, current_price, currency, is_watchlist, logo_url, target_allocation_pct)
VALUES 
('AAPL', 'Apple Inc.', 'Renta Variable', 'Tecnología', 'EE.UU.', 15.0, 175.00, 224.50, 'USD', 0, 'https://logo.clearbit.com/apple.com', 15.0),
('MSFT', 'Microsoft Corporation', 'Renta Variable', 'Tecnología', 'EE.UU.', 10.0, 340.00, 448.20, 'USD', 0, 'https://logo.clearbit.com/microsoft.com', 15.0),
('NVDA', 'NVIDIA Corp.', 'Renta Variable', 'Tecnología', 'EE.UU.', 25.0, 95.00, 125.80, 'USD', 0, 'https://logo.clearbit.com/nvidia.com', 12.0),
('SPY', 'SPDR S&P 500 ETF', 'Renta Variable', 'Índices / ETF', 'EE.UU.', 30.0, 480.00, 545.00, 'USD', 0, 'https://logo.clearbit.com/ssga.com', 20.0),
('ECOPETROL', 'Ecopetrol S.A.', 'Renta Variable', 'Energía', 'Colombia', 2500.0, 0.52, 0.61, 'USD', 0, 'https://logo.clearbit.com/ecopetrol.com.co', 5.0),
('BCOLOMBIA', 'Bancolombia S.A.', 'Renta Variable', 'Financiero', 'Colombia', 300.0, 7.20, 8.90, 'USD', 0, 'https://logo.clearbit.com/grupobancolombia.com', 5.0),
('NU', 'Nu Holdings Ltd.', 'Renta Variable', 'Financiero', 'Global', 400.0, 8.50, 14.10, 'USD', 0, 'https://logo.clearbit.com/nubank.com.br', 8.0),
('USD_CASH', 'Efectivo Dólares (High Yield)', 'Efectivo', 'Liquidez', 'EE.UU.', 12500.0, 1.00, 1.00, 'USD', 0, '', 10.0),
('COP_CASH', 'Efectivo Bancolombia (Pesos)', 'Efectivo', 'Liquidez', 'Colombia', 35000000.0, 0.00025, 0.00025, 'COP', 0, '', 5.0),
('BTC', 'Bitcoin', 'Alternativos', 'Criptoactivos', 'Global', 0.45, 42000.00, 61500.00, 'USD', 0, 'https://assets.coingecko.com/coins/images/1/large/bitcoin.png', 7.0),
('ETH', 'Ethereum', 'Alternativos', 'Criptoactivos', 'Global', 3.20, 2400.00, 3100.00, 'USD', 0, 'https://assets.coingecko.com/coins/images/279/large/ethereum.png', 3.0),
('AMZN', 'Amazon.com Inc.', 'Renta Variable', 'Consumo Cíclico', 'EE.UU.', 0.0, 0.00, 178.50, 'USD', 1, 'https://logo.clearbit.com/amazon.com', 0.0),
('GOOGL', 'Alphabet Inc.', 'Renta Variable', 'Tecnología', 'EE.UU.', 0.0, 0.00, 165.20, 'USD', 1, 'https://logo.clearbit.com/google.com', 0.0);

-- 2. Populate Investment Theses (Filtro Humano)
INSERT INTO investment_theses (id, ticker, thesis_text, valuation_grade, timing_context, safety_margin, checklist_passed, criteria_details)
VALUES
('a1000000-0000-0000-0000-000000000001', 'NVDA', 'Liderazgo indiscutible en aceleración por hardware e infraestructura de IA. Retorno sobre capital invertido (ROIC) superior al 55% y fuerte visibilidad de pedidos Blackwell para los próximos 4 trimestres.', 5, 'Consolidación técnica tras split 10:1, respetando media móvil exponencial de 50 días.', 26.50, 1, '{"knows_business_model":true,"debt_ebitda_healthy":true,"margin_safety_above_20":true,"timing_not_overbought":true,"emotional_bias_checked":true}'),
('a1000000-0000-0000-0000-000000000002', 'AAPL', 'Monopolio de ecosistema con fidelidad de usuarios inigualable. El ciclo de renovación por capacidades de IA en dispositivos locales impulsará el crecimiento de ingresos por servicios.', 4, 'En máximos de 52 semanas; ratio P/E de 33x por encima del promedio histórico.', 18.50, 0, '{"knows_business_model":true,"debt_ebitda_healthy":true,"margin_safety_above_20":false,"timing_not_overbought":false,"emotional_bias_checked":true}'),
('a1000000-0000-0000-0000-000000000003', 'NU', 'Disrupción fintech masiva en América Latina con coste de adquisición mínimo (CAC) y expansión sostenida de margen de intermediación en depósitos.', 4, 'En tendencia alcista primaria con volatilidad moderada post-resultados.', 23.00, 1, '{"knows_business_model":true,"debt_ebitda_healthy":true,"margin_safety_above_20":true,"timing_not_overbought":true,"emotional_bias_checked":true}'),
('a1000000-0000-0000-0000-000000000004', 'AMZN', 'Crecimiento de AWS re-acelerando hacia el 19% interanual y márgenes comerciales en expansión gracias a la optimización de logística regional.', 3, 'Buscando soporte en rango de $175. Se recomienda esperar confirmación de volumen.', 15.00, 0, '{"knows_business_model":true,"debt_ebitda_healthy":true,"margin_safety_above_20":false,"timing_not_overbought":true,"emotional_bias_checked":false}');

-- 3. Populate Geopolitical Risk
INSERT INTO geopolitical_risk (region, active_risk_score, anomaly_alert, headline, last_assessed)
VALUES
('Norteamérica', 24.0, 0, 'Trayectoria de aterrizaje suave en la economía de EE.UU. e inicio de ciclo de recortes de tasas de interés.', CURRENT_TIMESTAMP),
('Latinoamérica', 48.5, 0, 'Riesgo político moderado; presiones fiscales en Colombia compensadas por altas tasas reales y atracción de inversión extranjera.', CURRENT_TIMESTAMP),
('Europa', 58.0, 1, 'Alerta de anomalía: Estancamiento del sector manufacturero alemán y vulnerabilidad en cadenas de suministro del este.', CURRENT_TIMESTAMP),
('Asia-Pacífico', 63.5, 1, 'Alerta de anomalía: Presión deflacionaria en China y tensiones marítimas regionales.', CURRENT_TIMESTAMP);

-- 4. Populate BudgetBakers Mappings
INSERT INTO budgetbakers_mappings (id, bb_category_name, local_category, flow_type, is_active)
VALUES
('b1000000-0000-0000-0000-000000000001', 'Salary / Nómina', 'Ingresos Laborales', 'INCOME', 1),
('b1000000-0000-0000-0000-000000000002', 'Investments / Dividendos', 'Rendimientos Financieros', 'INCOME', 1),
('b1000000-0000-0000-0000-000000000003', 'Food & Dining / Supermercado', 'Alimentación y Hogar', 'EXPENSE', 1),
('b1000000-0000-0000-0000-000000000004', 'Housing / Vivienda', 'Vivienda y Servicios', 'EXPENSE', 1),
('b1000000-0000-0000-0000-000000000005', 'Portfolio DCA / Inversión', 'Inversión DCA', 'TRANSFER', 1),
('b1000000-0000-0000-0000-000000000006', 'Transportation / Movilidad', 'Transporte', 'EXPENSE', 1),
('b1000000-0000-0000-0000-000000000007', 'Leisure / Entretenimiento', 'Ocio y Discrecional', 'EXPENSE', 1);

-- 5. Populate Daily API Quota Initial Record
INSERT INTO api_daily_quota (date_key, request_count, max_quota, updated_at)
VALUES
(strftime('%Y-%m-%d', 'now'), 4, 25, CURRENT_TIMESTAMP);
