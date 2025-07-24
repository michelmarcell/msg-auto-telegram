import os
import logging
from telegram.ext import Application, CommandHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Configura logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.getenv('TELEGRAM_TOKEN')
GRUPOS_PERMITIDOS = {}

async def enviar_mensaje(context):
    mensaje = """🌟 ¡Transformamos tus ideas en soluciones digitales! 🌟
💻 *Soluciones Informáticas Integrales* 💻

En *Tech Solutions* somos especialistas en:
    
🤖 *Desarrollo de Bots Personalizados*:
   - Bots de atención al cliente 24/7
   - Bots para automatizar ventas y reservas
   - Bots educativos con contenido interactivo
   - Bots para gestión de comunidades y grupos
   - Bots de notificaciones y alertas

🌐 *Desarrollo Web Corporativo*:
   - Páginas web profesionales
   - Tiendas online completas
   - Portafolios digitales
   - Sistemas de gestión interna

🔄 *Beneficios para tu negocio*:
   - Ahorro de hasta 70% en costos operativos
   - Atención a clientes sin límites de horario
   - Procesos automatizados sin errores humanos
   - Soluciones a medida de tus necesidades

💡 *¡Este mensaje fue generado automáticamente por nuestro bot!* 
   ¿Quieres uno similar para tu empresa?

📲 *Contáctanos ahora*:
📞 Llamadas: +53 58784497
📱 WhatsApp: https://wa.me/5358784497"""
    
    for chat_id in GRUPOS_PERMITIDOS:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=mensaje,
                parse_mode="Markdown"  # Necesario para formato con *
            )
            logging.info(f"Mensaje enviado a {chat_id}")
        except Exception as e:
            logging.error(f"Error en {chat_id}: {e}")

async def suscribir(update, context):
    chat = update.effective_chat
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Solo funciona en grupos")
        return
        
    GRUPOS_PERMITIDOS[chat.id] = chat.title
    await update.message.reply_text(f"✅ {chat.title} suscrito!")

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("suscribir", suscribir))
    
    # Configura el scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        enviar_mensaje,
        'interval',
        hours=1,
        args=[application]
    )
    scheduler.start()
    
    application.run_polling()

if __name__ == "__main__":
    main()
