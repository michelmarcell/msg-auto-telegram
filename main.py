import os
import logging
import asyncio
import aiohttp
from configparser import ConfigParser
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
import uvicorn
from threading import Thread

# Configuración inicial
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Cargar configuración
config = ConfigParser()
config.read('config.ini')

TOKEN = config.get('Telegram', 'TOKEN', fallback=os.getenv('TELEGRAM_TOKEN'))
ADMIN_ID = config.getint('Telegram', 'ADMIN_ID', fallback=os.getenv('ADMIN_ID'))
APP_URL = config.get('Telegram', 'APP_URL', fallback=os.getenv('APP_URL'))

if not TOKEN:
    raise ValueError("No se configuró el token de Telegram")

# Grupos permitidos (cargar desde configuración)
GRUPOS_PERMITIDOS = {
    int(id_.strip()): "" for id_ in 
    config.get('Grupos', 'Permitidos', fallback="").split(',') 
    if id_.strip()
}

# Mensaje predefinido (puedes moverlo a un archivo aparte)
MENSAJE_PREDEFINIDO = """
🌟 ¡Transformamos tus ideas en soluciones digitales! 🌟
💻 *Soluciones Informáticas Integrales* 💻

... (tu mensaje completo aquí) ...
"""

async def verificar_acceso(update: Update) -> bool:
    """Verifica si el usuario tiene acceso a comandos administrativos"""
    user = update.effective_user
    chat = update.effective_chat
    
    # Verificar administrador global
    if user.id == ADMIN_ID:
        return True
    
    # Verificar grupo permitido y administrador
    if chat.id in GRUPOS_PERMITIDOS:
        try:
            member = await chat.get_member(user.id)
            return member.status in ['creator', 'administrator']
        except Exception as e:
            logger.error(f"Error verificando miembro: {e}")
    
    return False

async def keep_alive():
    """Mantiene activo el servicio en Render"""
    if not APP_URL:
        return
        
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{APP_URL}/ping") as resp:
                logger.info(f"Keep-alive: {resp.status}")
    except Exception as e:
        logger.error(f"Error en keep-alive: {e}")

async def enviar_mensaje(context: ContextTypes.DEFAULT_TYPE):
    """Envía el mensaje a los grupos permitidos"""
    for chat_id in GRUPOS_PERMITIDOS:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=MENSAJE_PREDEFINIDO,
                parse_mode="Markdown"
            )
            logger.info(f"Mensaje enviado a {chat_id}")
        except Exception as e:
            logger.error(f"Error enviando a {chat_id}: {e}")

async def suscribir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /suscribir"""
    if not await verificar_acceso(update):
        await update.message.reply_text("❌ Acceso denegado")
        return
        
    chat = update.effective_chat
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Solo funciona en grupos")
        return
        
    GRUPOS_PERMITIDOS[chat.id] = chat.title
    await update.message.reply_text(f"✅ {chat.title} suscrito!")
    logger.info(f"Nuevo grupo suscrito: {chat.id} - {chat.title}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start"""
    await update.message.reply_text(
        "🤖 Bot de mensajes automáticos\n\n"
        "Comandos disponibles:\n"
        "/suscribir - Suscribe este grupo (solo admins)\n"
        "/info - Muestra información del bot"
    )

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /info"""
    if not await verificar_acceso(update):
        return
        
    await update.message.reply_text(
        f"🔒 Bot protegido\n\n"
        f"📊 Grupos suscritos: {len(GRUPOS_PERMITIDOS)}\n"
        f"🔄 Próximo mensaje automático: cada 1 hora\n"
        f"🛡️ Admin: {ADMIN_ID}"
    )

def iniciar_servidor_web():
    """Inicia un servidor FastAPI para health checks"""
    app = FastAPI()
    
    @app.get("/")
    async def root():
        return {"status": "ok", "bot": "active"}
    
    @app.get("/ping")
    async def ping():
        return {"response": "pong"}
    
    uvicorn.run(app, host="0.0.0.0", port=8000)

async def main():
    """Función principal"""
    # Iniciar servidor web en segundo plano
    Thread(target=iniciar_servidor_web, daemon=True).start()
    
    # Configurar el bot
    application = Application.builder().token(TOKEN).build()
    
    # Manejadores de comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("suscribir", suscribir))
    application.add_handler(CommandHandler("info", info))
    
    # Programar tareas automáticas
    scheduler = AsyncIOScheduler()
    
    # Mensaje automático cada hora
    scheduler.add_job(
        enviar_mensaje,
        trigger=IntervalTrigger(hours=1),
        args=[application]
    )
    
    # Keep-alive cada 10 minutos
    scheduler.add_job(
        keep_alive,
        trigger=IntervalTrigger(minutes=10)
    )
    
    scheduler.start()
    
    # Iniciar el bot
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
