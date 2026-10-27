# BTC/USDT Telegram Alerts

Bot de alertas (sin trading) que consume datos públicos de Bitget, detecta divergencias RSI en 15m, confirma con EMA en 1h y calcula el Volume Profile con velas de 4h. Si Bitget no está disponible, se puede seleccionar Binance con `MARKET_PROVIDER=binance`.

## Agente de OpenCode

Este proyecto incluye el agente especializado `trading-alerts` en `.opencode/agents/trading-alerts.md`. Está configurado como agente predeterminado en `opencode.jsonc` y contiene el contexto técnico, las restricciones de seguridad y las reglas de mantenimiento del proyecto.

## Inicio rápido

```bash
cp .env.example .env
# Editar TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_IDS
docker compose up --build
```

## Conectar el bot a Telegram

### 1. Crear el bot

1. Abre Telegram y busca [@BotFather](https://t.me/BotFather).
2. Ejecuta `/newbot`.
3. Define el nombre y el username del bot.
4. Copia el token generado. No lo compartas ni lo guardes en Git.

Ejemplo de token:

```text
123456789:ABCxxxxxxxxxxxxxxxxxxxx
```

### 2. Obtener el `chat_id`

Puedes obtenerlo usando [@userinfobot](https://t.me/userinfobot):

1. Abre el bot.
2. Envía `/start`.
3. Copia el número mostrado como `Id`.

Si se utilizará un grupo, agrega el bot al grupo y configura el ID de ese grupo.

### 3. Configurar `.env`

Desde la raíz del proyecto:

```bash
cp .env.example .env
```

Edita `.env`:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCxxxxxxxxxxxxxxxxxxxx
TELEGRAM_CHAT_IDS=123456789
MARKET_PROVIDER=bitget
SYMBOL=BTCUSDT
RSI_PERIOD=14
EMA_PERIOD=15
VOLUME_PROFILE_ROWS=500
VOLUME_PROFILE_VALUE_AREA=70
VOLUME_PROFILE_HVN_COUNT=5
VOLUME_PROFILE_REFRESH_HOURS=4
```

Para varios chats:

```env
TELEGRAM_CHAT_IDS=123456789,987654321
```

No se necesitan API keys de Bitget ni Binance: el bot consume sus datos públicos.

### 4. Iniciar el programa

Construir e iniciar en primer plano:

```bash
docker compose up --build
```

Ejecutar en segundo plano:

```bash
docker compose up -d --build
```

Ver los logs:

```bash
docker compose logs -f bot
```

### 5. Probar el bot

En Telegram, envía:

```text
/start
/status
/last
```

El bot recibirá datos públicos de Bitget. Si Bitget falla, cambiará automáticamente a Binance. Las alertas se enviarán a los `chat_id` configurados cuando se cumplan las condiciones de RSI y Volume Profile.

### 6. Detener y reiniciar

Detener:

```bash
docker compose down
```

Reiniciar:

```bash
docker compose restart bot
```

Si aparece `TELEGRAM_BOT_TOKEN vacío`, verifica que `.env` exista y que contenga un token válido.

El bot únicamente genera alertas informativas. No ejecuta operaciones de compra o venta.

## Estrategia de alertas

La señal requiere las tres confirmaciones siguientes:

1. El precio toca uno de los cinco HVN con mayor volumen, identificando si llega desde arriba (posible soporte) o desde abajo (posible resistencia), o cruza VAL/VAH en la dirección correspondiente.
2. Se detecta una divergencia alcista o bajista del RSI en 15m.
3. Una vela cerrada de 1h cruza la EMA de 15 períodos.

El Volume Profile utiliza 500 filas, un área de valor del 70% y velas 4h cerradas desde el punto inicial definido. Los HVN se calculan sobre el precio típico de cada vela 4h; el perfil se amplía al cerrar cada nueva vela 4h. No se usan datos privados del exchange.

Al ejecutar `/define`, el bot descarga las velas 4h históricas desde esa fecha hasta la última vela cerrada disponible. El punto anterior se sobrescribe completamente. Después, cada nueva vela 4h cerrada se agrega al perfil y este se recalcula hacia la derecha. La hora se interpreta según `TIMEZONE` (por defecto `America/Lima`, UTC−5).

## Comandos

- `/start`: registra el chat y muestra ayuda.
- `/status`: proveedor, símbolo, último precio, inicio del perfil, 5 HVN, POC, VAL y VAH.
- `/last`: última señal calculada.
- `/define HH:MM DD/MM/YY`: define o reemplaza el inicio del Volume Profile usando velas 4h. Ejemplo: `/define 22:00 26/10/26`.

El bot no solicita ni usa API keys de exchange y no ejecuta órdenes.

## Proveedores

- Bitget público por defecto: WebSocket `wss://ws.bitget.com/v2/ws/public`.
- Binance público: WebSocket `wss://stream.binance.com:9443/ws/btcusdt@kline_1m`.

Si el proveedor se desconecta, el proceso reintenta con backoff. Para cambiar a Binance, usa `MARKET_PROVIDER=binance`.

## Desarrollo local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app
```

Las señales son educativas y no constituyen asesoramiento financiero.
