import os
import logging
import asyncio
from configparser import ConfigParser
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
import uvicorn
from threading import Thread
import requests
from datetime import datetime

# Configuración de logging mejorada
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_activity.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Carga de configuración segura
def load_config():
    config = ConfigParser()
    config.read('config.ini')
    
    return {
        'TOKEN': config.get('Telegram', 'TOKEN', fallback=os.getenv('TELEGRAM_TOKEN')),
        'ADMIN_ID': config.getint('Telegram', 'ADMIN_ID', fallback=os.getenv('ADMIN_ID', 0)),
        'APP_URL': config.get('Telegram', 'APP_URL', fallback=os.getenv('APP_URL')),
        'ALLOWED_GROUPS': {
            int(id_.strip()): "" for id_ in 
            config.get('Grupos', 'Permitidos', fallback="").split(',') 
            if id_.strip()
        }
    }

config = load_config()

if not config['TOKEN']:
    raise ValueError("Token de Telegram no configurado")

# Mensaje mejorado con gestión de errores
def get_message():
    return """
🌟 *Oferta Especial* 🌟
¡Desarrollamos soluciones a tu medida!

💻 *Servicios*:
- Bots personalizados
- Páginas web
- Aplicaciones móviles

📅 *Promoción válida hasta*: {date}
📞 Contacto: +123456789

*Este mensaje fue enviado automáticamente*
""".format(date=datetime.now().strftime("%d/%m/%Y"))

# Sistema de keep-alive mejorado (sin aiohttp)
def keep_alive():
    try:
        if config['APP_URL']:
            response = requests.get(f"{config['APP_URL']}/ping", timeout=10)
            logger.info(f"Keep-alive status: {response.status_code}")
    except Exception as e:
        logger.error(f"Keep-alive error: {str(e)}")
    finally:
        # Programa el próximo keep-alive
        Thread(target=lambda: (
            asyncio.sleep(600),  # 10 minutos
            keep_alive()
        )).start()

# Gestión de grupos con persistencia
def save_groups():
    try:
        with open('allowed_groups.txt', 'w') as f:
            for chat_id, title in config['ALLOWED_GROUPS'].items():
                f.write(f"{chat_id},{title}\n")
    except Exception as e:
        logger.error(f"Error saving groups: {e}")

def load_groups():
    try:
        with open('allowed_groups.txt') as f:
            for line in f:
                chat_id, title = line.strip().split(',', 1)
                config['ALLOWED_GROUPS'][int(chat_id)] = title
    except FileNotFoundError:
        logger.info("No groups file found, starting fresh")
    except Exception as e:
        logger.error(f"Error loading groups: {e}")

# Handlers de comandos mejorados
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start"""
    user = update.effective_user
    logger.info(f"Start command from {user.id}")
    
    await update.message.reply_text(
        "🤖 *Bot de Mensajes Automáticos*\n\n"
        "Comandos disponibles:\n"
        "/suscribir - Suscribe este grupo\n"
        "/info - Muestra información del bot\n\n"
        "ℹ️ Solo administradores pueden usar comandos",
        parse_mode="Markdown"
    )

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /suscribir"""
    chat = update.effective_chat
    user = update.effective_user
    
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Este comando solo funciona en grupos")
        return
        
    try:
        member = await chat.get_member(user.id)
        if member.status not in ['creator', 'administrator']:
            await update.message.reply_text("❌ Solo administradores pueden suscribir grupos")
            return
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        await update.message.reply_text("⚠️ Error verificando permisos")
        return

    config['ALLOWED_GROUPS'][chat.id] = chat.title
    save_groups()
    
    await update.message.reply_text(
        f"✅ *{chat.title} suscrito correctamente!*\n\n"
        f"Ahora recibirán mensajes automáticos cada hora.",
        parse_mode="Markdown"
    )
    logger.info(f"New group subscribed: {chat.id} - {chat.title}")

async def send_scheduled_message(context: ContextTypes.DEFAULT_TYPE):
    """Envía mensajes programados"""
    logger.info("Starting scheduled message send")
    
    for chat_id, title in config['ALLOWED_GROUPS'].items():
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=get_message(),
                parse_mode="Markdown"
            )
            logger.info(f"Message sent to {title} ({chat_id})")
        except Exception as e:
            logger.error(f"Error sending to {chat_id}: {e}")
            # Opcional: remover grupos inactivos
            # del config['ALLOWED_GROUPS'][chat_id]

# Servidor web para health checks
def run_web_server():
    app = FastAPI()
    
    @app.get("/")
    async def health_check():
        return {
            "status": "running",
            "bot": "active",
            "groups": len(config['ALLOWED_GROUPS'])
        }
    
    @app.get("/ping")
    async def ping():
        return {"response": "pong", "timestamp": datetime.now().isoformat()}
    
    uvicorn.run(app, host="0.0.0.0", port=8000)

async def main():
    """Punto de entrada principal"""
    # Cargar grupos permitidos
    load_groups()
    
    # Iniciar servidor web en segundo plano
    Thread(target=run_web_server, daemon=True).start()
    
    # Iniciar sistema keep-alive
    keep_alive()
    
    # Configurar aplicación de Telegram
    application = Application.builder().token(config['TOKEN']).build()
    
    # Registrar handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("suscribir", subscribe))
    
    # Configurar scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_scheduled_message,
        trigger=IntervalTrigger(hours=1),
        args=[application]
    )
    scheduler.start()
    
    # Iniciar el bot
    await application.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot detenido manualmente")
    except Exception as e:
        logger.critical(f"Error fatal: {e}")
