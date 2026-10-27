# Plan de proyecto: bot de trading de BTC/USDT para Telegram

> **Estado:** propuesta inicial — octubre de 2026  
> **Objetivo:** generar señales y, opcionalmente, ejecutar operaciones sobre BTC/USDT usando Volume Profile y RSI en 15 minutos, 30 minutos y 1 hora.

## 1. Alcance y objetivos

El bot debe:

1. Recibir datos de mercado en tiempo casi real.
2. Construir velas de 15m, 30m, 1h y 4h.
3. Calcular Volume Profile por rangos de precio y RSI por temporalidad.
4. Generar señales explicables (no solamente `BUY`/`SELL`).
5. Enviar alertas, gráficos/resúmenes y estado por Telegram.
6. Registrar señales, órdenes, errores y métricas.
7. Comenzar en **modo simulación/paper trading** y testnet; el trading real debe ser una fase posterior y explícitamente habilitada.

### Fuera del alcance inicial

- Alta frecuencia o ejecución de baja latencia.
- Machine learning.
- Soporte simultáneo de muchos exchanges.
- Gestión de fondos de terceros.

## 2. Estrategia propuesta

### Datos

- Símbolo inicial: `BTCUSDT` en mercado spot; elegir futuros solamente si se define claramente el riesgo de apalancamiento.
- Temporalidades: 15m, 30m, 1h y 4h.
- Historial mínimo: 500–1.000 velas por temporalidad para que los indicadores tengan contexto.
- Para un Volume Profile más fiel, consumir trades/agregados (`price`, `quantity`, `timestamp`) y asignar cada operación a un intervalo de precio. Las velas OHLCV sirven para un MVP, pero su volumen queda distribuido de forma aproximada dentro de la vela.

### Indicadores

- **RSI:** período 14 con Wilder/RMA; detectar divergencia alcista/bajista usando pivotes de 15m y evitar señales con velas incompletas.
- **EMA:** período 15 aplicada al cierre de 1h; la confirmación ocurre únicamente cuando la vela 1h cierra cruzando la EMA.
- **Volume Profile:** 500 filas, área de valor del 70%, actualización/ampliación cada 4 horas y únicamente los 5 HVN con mayor volumen. Se calcula con el precio típico de velas 4h del intervalo seleccionado.
- **Inicio configurable:** `/define HH:MM DD/MM/YY` descarga velas históricas 4h desde el punto indicado hasta la última vela cerrada. Un nuevo `/define` reemplaza el perfil anterior; después el perfil crece con cada nueva vela 4h cerrada.
- Confirmar con la temporalidad superior: por ejemplo, una señal en 15m solo es válida si no contradice el régimen de 1h.

### Ejemplo de regla inicial (para validar, no para asumir rentabilidad)

- Compra: el precio toca un HVN llegando desde arriba (posible soporte) o cruza VAL al alza; después aparece divergencia alcista del RSI y una vela 1h cierra por encima de EMA(15).
- Venta: el precio toca un HVN llegando desde abajo (posible resistencia) o cruza VAH a la baja; después aparece divergencia bajista del RSI y una vela 1h cierra por debajo de EMA(15).
- No operar cuando el spread, la volatilidad o la calidad de los datos excedan límites configurados.

Cada señal debe incluir: precio, temporalidad, POC/VAH/VAL, RSI, razón, stop-loss, take-profit, tamaño calculado y timestamp. Las reglas exactas deben probarse con backtesting y walk-forward; no se debe optimizar solamente para que el histórico “se vea bien”.

## 3. Arquitectura recomendada

### Primera versión: monolito modular

No recomiendo microservicios para el MVP. Un solo proceso Python con módulos bien separados reduce coste y complejidad:

```text
Exchange REST/WebSocket
          |
   Market Data Adapter  --->  Normalizer / Candle Aggregator
                                      |
                         Indicators (RSI / Volume Profile)
                                      |
                             Strategy + Risk Manager
                                /              \
                       Alert Service       Execution Adapter
                              |                    |
                         Telegram Bot       Exchange orders
                                      |
                          SQLite/PostgreSQL + logs
```

Módulos sugeridos:

```text
app/
  bot/              # comandos, permisos y notificaciones Telegram
  market_data/      # REST, WebSocket, reconexión, deduplicación
  candles/          # agregación y cierre de velas
  indicators/       # RSI y Volume Profile puros y testeables
  strategy/         # reglas, estados y señales
  risk/             # tamaño, stops, límites diarios y kill switch
  execution/        # paper, testnet y live; interfaces intercambiables
  persistence/      # modelos, migraciones y repositorios
  monitoring/       # health checks, métricas y alertas
tests/
docs/
```

### Flujo de ejecución

1. Conectar al WebSocket y reintentar con backoff exponencial.
2. Persistir datos crudos o, como mínimo, velas cerradas y última secuencia recibida.
3. Recalcular indicadores únicamente con datos cerrados y detectar duplicados.
4. Evaluar estrategia y pasar toda señal por el gestor de riesgo.
5. Enviar alerta a Telegram; en paper/testnet registrar la orden simulada.
6. En live, usar idempotencia (`client_order_id`), confirmar el fill desde el exchange y reconciliar el estado periódicamente.
7. Si faltan datos, el reloj se desfasa o se pierde la conexión, detener nuevas entradas y avisar.

### Persistencia

- **Desarrollo/MVP:** SQLite con volumen limitado.
- **Producción de un solo bot:** PostgreSQL es preferible para órdenes, auditoría y migraciones, aunque no es imprescindible desde el día uno.
- Guardar credenciales únicamente en variables de entorno/secret manager; nunca en Git ni en mensajes de Telegram.

## 4. ¿Es necesario Docker?

**No es estrictamente necesario**, pero sí lo recomiendo para producción porque fija la versión de Python y dependencias, facilita despliegues y permite levantar el bot con `systemd` o Docker Compose.

### Opción recomendada

- Un VPS Linux pequeño.
- Docker Compose con `bot` y, si se necesita, `postgres`.
- Volúmenes para base de datos y logs.
- Política de reinicio `unless-stopped`.
- Healthcheck y logs rotados.
- Firewall, SSH con claves, actualizaciones automáticas y usuario sin privilegios.

Para una primera prueba basta con un entorno virtual y `systemd`. Kubernetes, balanceadores y microservicios serían sobreingeniería para un bot de un símbolo y pocos usuarios.

### Polling o webhook de Telegram

- **Long polling:** más simple y no exige dominio ni HTTPS; buena opción en un VPS privado.
- **Webhook:** apropiado si ya se dispone de HTTPS y una aplicación web; requiere exponer un endpoint.

Telegram no cobra por la Bot API estándar. Los mensajes masivos por encima de los límites gratuitos pueden tener costes de Telegram Stars; no es relevante para un bot privado pequeño.

## 5. APIs y fuentes de datos

### Recomendación principal: Binance Spot API

- REST para histórico, reglas del símbolo, balances y órdenes.
- WebSocket para trades/aggrTrades, book ticker y velas.
- BTC/USDT tiene gran liquidez, lo que suele ayudar al spread y al llenado.
- Separar endpoints/credenciales de producción y testnet.
- Revisar límites de peso, desconexiones y cambios de API en la documentación oficial.

Enlaces: [Binance Spot API](https://developers.binance.com/docs/binance-spot-api-docs), [WebSocket streams](https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams), [Trading fees](https://www.binance.com/en/fee/trading).

### Alternativas

| Proveedor | Uso recomendado | Observaciones |
|---|---|---|
| Bybit | Spot o derivados y testnet | Buena alternativa si Binance no está disponible en la jurisdicción. Revisar restricciones locales y límites. |
| Coinbase Advanced Trade | Spot y mercado regulado en ciertos países | REST/WebSocket; disponibilidad de pares y tarifas dependen del país. |
| Kraken | Spot, respaldo y comparación de precio | API estable; comprobar granularidad de datos y límites. |
| CoinGecko | Precio de referencia y metadatos | No lo usaría como fuente principal de trades intradía para Volume Profile. |
| CCXT | Adaptador REST común entre exchanges | Útil para prototipo; para WebSocket usar la librería/servicio apropiado y verificar licencia/coste de `ccxt.pro`. |

Para el MVP conviene implementar primero un `BinanceMarketDataAdapter` y una interfaz `ExchangeClient`; luego añadir otro exchange sin reescribir estrategia.

Documentación útil: [Telegram Bot API](https://core.telegram.org/bots/api), [Bybit API](https://bybit-exchange.github.io/docs/), [Coinbase Advanced Trade API](https://docs.cdp.coinbase.com/), [Kraken API](https://docs.kraken.com/api/).

## 6. Seguridad y controles de riesgo

Estos controles son obligatorios antes de live trading:

- API key sin permiso de retiro y restringida por IP cuando el exchange lo permita.
- Allowlist de usuarios/chat IDs de Telegram; comandos administrativos separados.
- `DRY_RUN=true` por defecto y un `LIVE_TRADING=true` explícito.
- Riesgo máximo por operación, pérdida máxima diaria, máximo de posiciones y máximo de órdenes.
- Stop-loss definido antes de crear la entrada; kill switch manual (`/stop`) y automático.
- Protección frente a órdenes duplicadas, fills parciales, slippage y desconexiones.
- Reconciliación de balance y órdenes abiertas al reiniciar.
- Logs sin secretos y auditoría de cada decisión.
- Backups de la base de datos y prueba de restauración.

El bot no garantiza ganancias. El trading de criptoactivos puede producir pérdidas totales y las obligaciones regulatorias/fiscales dependen del país.

## 7. Fases de realización

### Fase 0 — Especificación (1–2 días)

- Definir spot vs. futuros, exchange, zona horaria, reglas de Volume Profile y parámetros de riesgo.
- Definir comandos de Telegram y criterios de éxito.

### Fase 1 — Datos y visualización (3–5 días)

- Cliente REST/WebSocket, almacenamiento de velas/trades y reconexión.
- Gráfico o resumen de POC/VAH/VAL y RSI.
- Tests de normalización y cierre de velas.

### Fase 2 — Indicadores y backtesting (4–7 días)

- Implementar RSI y Volume Profile sin mirar datos futuros.
- Comisiones, spread, slippage y latencia en el simulador.
- Backtest, out-of-sample y walk-forward; reportar drawdown, Sharpe, profit factor, número de operaciones y expectativa.

### Fase 3 — Telegram y paper trading (3–5 días)

- `/start`, `/status`, `/signal`, `/positions`, `/performance`, `/pause`, `/resume` y `/stop`.
- Alertas de señal, fill simulado, error y desconexión.
- Permisos, rate limiting y pruebas de recuperación.

### Fase 4 — Testnet y operación supervisada (5–10 días)

- Órdenes reales del entorno de prueba, reconciliación y pruebas de reinicio.
- Ejecutar al menos varias semanas de observación; no pasar a live por calendario sino por criterios definidos.

### Fase 5 — Live con capital pequeño

- Activación gradual, límites estrictos, revisión diaria y rollback inmediato.

## 8. Coste estimado de mantenerlo 24/7

Los importes son orientativos y deben verificarse en la página de precios del proveedor antes de contratar. No incluyen capital de trading, impuestos, comisiones del exchange, pérdidas, conversión de moneda ni trabajo de desarrollo.

| Concepto | MVP mensual aproximado | Comentario |
|---|---:|---|
| Telegram Bot API | 0 USD | Bot privado y volumen normal. |
| API de mercado del exchange | 0 USD | El acceso API suele ser gratuito; se pagan comisiones al ejecutar operaciones. |
| VPS 1 vCPU / 1 GB | 5–10 USD | Suficiente para un bot, SQLite y logs moderados. Hetzner publica planes Cloud desde aprox. €5.99/mes sin IVA; precios cambian. |
| PostgreSQL gestionado | 0–20+ USD | Evitable inicialmente; depende del proveedor y backups. |
| Dominio/HTTPS | 0–15 USD/año | No necesario si se usa long polling; HTTPS puede obtenerse gratis con Let's Encrypt. |
| Monitorización/backup externo | 0–10 USD | Puede empezar con alertas y backup del VPS. |
| **Total razonable** | **5–30 USD/mes** | Bot pequeño, una instancia, sin alta disponibilidad. |

Alternativas: un servicio gestionado tipo Render puede partir de un worker pequeño alrededor de 7 USD/mes según su plan actual, pero hay que revisar suspensión, almacenamiento persistente y límites. Un VPS suele ser más predecible para un proceso WebSocket 24/7.

### Costes que no deben confundirse con hosting

- **Comisión de trading:** porcentaje por cada compra/venta, variable por exchange, volumen, nivel VIP y uso de token/descuentos.
- **Spread y slippage:** coste real adicional, especialmente en órdenes de mercado.
- **Futuros:** funding, liquidación y riesgo de apalancamiento.
- **Datos premium:** solo si se contrata un proveedor especializado; no son necesarios para el MVP de BTC/USDT.

## 9. Stack Python sugerido

- Python 3.12+.
- `aiogram` o `python-telegram-bot` para Telegram; escoger uno y fijar versión.
- `httpx`/`aiohttp` y WebSocket asíncrono.
- `pandas`/`numpy`; `pandas-ta` o implementación propia testeada para RSI.
- `SQLAlchemy` + Alembic; SQLite al inicio, PostgreSQL en producción si hace falta.
- `pytest`, `pytest-asyncio`, `ruff`, `mypy` y pre-commit.
- `Docker Compose`, GitHub Actions y `systemd`/healthcheck.

La estrategia y los indicadores deben ser funciones deterministas y fáciles de probar; el código de Telegram, exchange y base de datos debe quedar detrás de interfaces.

## 10. Skills y herramientas recomendadas para el desarrollo

### Skills de este entorno

- **`git-commit`:** revisar cambios y crear commits Conventional Commits de forma segura.
- **`opencode`:** consultar y configurar OpenCode, agentes, MCP, modelos, permisos y automatización del entorno.
- **`report`:** preparar un reporte si aparece un bug de OpenCode.
- **`frontend-design`:** solo si posteriormente se construye un dashboard web; no es necesario para el bot de Telegram.

### Competencias técnicas a desarrollar

1. Python asíncrono, WebSockets y manejo de reconexiones.
2. APIs de exchanges, rate limits, firmas HMAC y precisión/tamaño mínimo de órdenes.
3. Análisis cuantitativo, Volume Profile, RSI y sesgo de supervivencia/look-ahead.
4. Backtesting realista con fees, spread, slippage y fills parciales.
5. Gestión monetaria y controles de riesgo.
6. Docker, Linux, systemd, secretos, backups y monitorización.
7. Testing unitario, integración con testnet y pruebas de recuperación.

## 11. Criterios de aceptación del MVP

- Reconecta automáticamente y no duplica velas ni órdenes.
- Produce señales reproducibles usando únicamente velas cerradas.
- Explica cada señal en Telegram con indicadores y niveles.
- Paper trading incluye fees, slippage y equity curve.
- Ninguna clave permite retiros.
- El bot puede detener entradas sin perder la capacidad de cerrar/reconciliar posiciones.
- Un reinicio recupera el estado y deja trazabilidad.
- Se han ejecutado backtest, out-of-sample y testnet antes de considerar live.

## Conclusión

Para este caso, la arquitectura óptima inicial es **Python asíncrono + monolito modular + WebSocket del exchange + SQLite/PostgreSQL + Telegram + Docker Compose en un VPS pequeño**. Docker no es obligatorio, pero reduce riesgos operativos. El coste técnico mínimo realista para mantenerlo 24/7 es aproximadamente **5–30 USD al mes**, mientras que el coste económico del trading depende principalmente de comisiones, spread, slippage y pérdidas; debe presupuestarse por separado.
