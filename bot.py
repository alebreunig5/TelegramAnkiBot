# bot.py
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv
from anki_functions import (
    obtener_info_completa_ia, 
    crear_tarjeta_anki, 
    buscar_palabra_en_deck,
    obtener_info_notas,
    formatear_json_para_telegram,
    formatear_notas_existentes,
    convertir_nota_a_datos_anki,
    editar_tarjeta_existente_completa
)

# Cargar variables de entorno
load_dotenv()

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Variables de entorno
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_IDS = [int(user_id) for user_id in os.getenv("ALLOWED_USER_IDS", "").split(",") if user_id]

# Estados de conversación
(
    WAITING_WORD,
    CONFIRM_CREATION,
    CHOOSE_CARD_TYPE,
    CHOOSE_DECK,
    EDITING_CARD,
    EDITING_FIELD
) = range(6)

def is_user_authorized(user_id: int) -> bool:
    """Verifica si el usuario está autorizado"""
    return user_id in ALLOWED_USER_IDS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start"""
    user_id = update.effective_user.id
    
    if not is_user_authorized(user_id):
        await update.message.reply_text("❌ No estás autorizado para usar este bot.")
        return
    
    welcome_text = """
🤖 *¡Bienvenido al Bot de Anki con IA!*

*Comandos disponibles:*
/start - Muestra este mensaje
/help - Muestra la ayuda
/word - Buscar una palabra y crear tarjeta

*¿Cómo usar?*
1. Envía /word o simplemente escribe una palabra en inglés
2. El bot buscará información con IA
3. Podrás crear una tarjeta en Anki

*Requisitos:*
• Anki debe estar abierto
• AnkiConnect instalado

¡Empecemos! 🚀
    """
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /help"""
    user_id = update.effective_user.id
    
    if not is_user_authorized(user_id):
        await update.message.reply_text("❌ No estás autorizado para usar este bot.")
        return
    
    help_text = """
📖 *Ayuda del Bot de Anki*

*Funcionalidades:*
• Buscar palabras en inglés
• Obtener información completa con IA Gemini
• Crear tarjetas en Anki automáticamente
• Verificar si la palabra ya existe en tus mazos

*Flujo de trabajo:*
1. Escribe una palabra en inglés
2. El bot consulta a la IA para obtener información completa
3. Puedes crear la tarjeta en Anki con un click

¡Listo para aprender! 🎓
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def handle_word_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /word"""
    user_id = update.effective_user.id
    
    if not is_user_authorized(user_id):
        await update.message.reply_text("❌ No estás autorizado para usar este bot.")
        return
    
    # Si se proporciona la palabra directamente con el comando
    if context.args:
        palabra = ' '.join(context.args)
        await process_word(update, context, palabra)
    else:
        # Solicitar la palabra
        await update.message.reply_text("✍️ Por favor, escribe la palabra en inglés que quieres buscar:")
        context.user_data['state'] = WAITING_WORD

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja mensajes de texto normales"""
    user_id = update.effective_user.id
    
    if not is_user_authorized(user_id):
        await update.message.reply_text("❌ No estás autorizado para usar este bot.")
        return
    
    text = update.message.text.strip()
    
    # Si estamos esperando una palabra
    if context.user_data.get('state') == WAITING_WORD:
        await process_word(update, context, text)
    
    # Si estamos editando un campo
    elif context.user_data.get('state') == EDITING_FIELD:
        await handle_edit_text(update, context)
    
    else:
        # Si no hay estado específico, asumimos que es una palabra para buscar
        await process_word(update, context, text)

async def process_word(update: Update, context: ContextTypes.DEFAULT_TYPE, palabra: str):
    """Procesa una palabra buscada - VERSIÓN MEJORADA"""
    user_id = update.effective_user.id
    
    await update.message.reply_text(f"🔍 *Buscando información para: {palabra}*", parse_mode='Markdown')
    
    # PRIMERO: Buscar en todos los decks de Anki
    decks = ["0 USA::STEP 1", "0 USA::Self-Learning"]
    todas_notas_ids = []
    
    for deck in decks:
        note_ids = buscar_palabra_en_deck(deck, palabra)
        todas_notas_ids.extend(note_ids)
    
    # SI EXISTE EN ANKI: Mostrar opciones
    if todas_notas_ids:
        notas_existentes = obtener_info_notas(todas_notas_ids)
        mensaje = formatear_notas_existentes(notas_existentes)
        
        keyboard = [
            [
                InlineKeyboardButton("✏️ Editar existente", callback_data=f"edit_existing:{palabra}"),
                InlineKeyboardButton("🆕 Crear nueva", callback_data=f"create_new:{palabra}")
            ],
            [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ *La palabra '{palabra}' ya existe en Anki*\n\n{mensaje}",
            parse_mode='Markdown', 
            reply_markup=reply_markup
        )
        return
    
    # SI NO EXISTE: Proceder con IA como antes
    datos_anki = obtener_info_completa_ia(palabra)
    
    if datos_anki is None:
        await update.message.reply_text("❌ Error al obtener la información de la IA. Intenta nuevamente.")
        return
    
    # Guardar datos en el contexto del usuario
    context.user_data['current_word_data'] = datos_anki
    context.user_data['state'] = CONFIRM_CREATION
    
    # Formatear y mostrar la información
    mensaje_info = formatear_json_para_telegram(datos_anki)
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Crear tarjeta", callback_data="confirm_create"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(mensaje_info, parse_mode='Markdown', reply_markup=reply_markup)

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los botones inline"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if not is_user_authorized(user_id):
        await query.edit_message_text("❌ No estás autorizado para usar este bot.")
        return
    
    if data == "cancel":
        await query.edit_message_text("❌ Operación cancelada.")
        context.user_data.clear()
    
    # Editar tarjeta existente
    elif data.startswith("edit_existing:"):
        palabra = data.split(":")[1]
        await query.edit_message_text(f"✏️ *Editando tarjeta existente para: {palabra}*", parse_mode='Markdown')
        
        # Buscar la tarjeta existente
        decks = ["0 USA::STEP 1", "0 USA::Self-Learning"]
        todas_notas_ids = []
        
        for deck in decks:
            note_ids = buscar_palabra_en_deck(deck, palabra)
            todas_notas_ids.extend(note_ids)
        
        if not todas_notas_ids:
            await query.edit_message_text("❌ No se encontró la tarjeta para editar.")
            return
        
        # Obtener información de la primera tarjeta encontrada
        notas_existentes = obtener_info_notas([todas_notas_ids[0]])
        if not notas_existentes:
            await query.edit_message_text("❌ Error al obtener información de la tarjeta.")
            return
        
        # Convertir la tarjeta existente al formato que usa el sistema de edición
        nota_existente = notas_existentes[0]
        datos_existentes = convertir_nota_a_datos_anki(nota_existente, palabra)
        
        context.user_data['current_word_data'] = datos_existentes
        context.user_data['editing_existing_note'] = True
        context.user_data['existing_note_id'] = nota_existente['noteId']
        
        await edit_card_menu(query, context)
    
    # Crear nueva tarjeta aunque exista
    elif data.startswith("create_new:"):
        palabra = data.split(":")[1]
        await query.edit_message_text(f"🆕 *Creando nueva tarjeta para: {palabra}*", parse_mode='Markdown')
        
        # Proceder con IA como normalmente
        datos_anki = obtener_info_completa_ia(palabra)
        
        if datos_anki is None:
            await query.edit_message_text("❌ Error al obtener la información de la IA. Intenta nuevamente.")
            return
        
        context.user_data['current_word_data'] = datos_anki
        context.user_data['state'] = CONFIRM_CREATION
        
        mensaje_info = formatear_json_para_telegram(datos_anki)
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Crear tarjeta", callback_data="confirm_create"),
                InlineKeyboardButton("❌ Cancelar", callback_data="cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(mensaje_info, parse_mode='Markdown', reply_markup=reply_markup)
    
    elif data.startswith("create_anyway:"):
        palabra = data.split(":")[1]
        await query.edit_message_text(f"🔍 *Buscando información para: {palabra}*", parse_mode='Markdown')
        
        datos_anki = obtener_info_completa_ia(palabra)
        
        if datos_anki is None:
            await query.edit_message_text("❌ Error al obtener la información de la IA. Intenta nuevamente.")
            return
        
        context.user_data['current_word_data'] = datos_anki
        context.user_data['state'] = CONFIRM_CREATION
        
        mensaje_info = formatear_json_para_telegram(datos_anki)
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Crear tarjeta", callback_data="confirm_create"),
                InlineKeyboardButton("❌ Cancelar", callback_data="cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(mensaje_info, parse_mode='Markdown', reply_markup=reply_markup)
    
    elif data == "confirm_create":
        await choose_card_type(query, context)
    
    elif data in ["basic_card", "reversed_card"]:
        context.user_data['card_type'] = "Basic" if data == "basic_card" else "Basic (and reversed card)"
        await choose_deck(query, context)
    
    elif data in ["deck_step1", "deck_self_learning"]:
        context.user_data['chosen_deck'] = data
        await show_card_preview(query, context)
    
    elif data == "confirm_create_final":
        await create_card_final(query, context)
    
    # Manejo de edición
    elif data == "edit_card":
        await edit_card_menu(query, context)
    
    elif data.startswith("edit_field:"):
        field_name = data.split(":")[1]
        await handle_field_edit(query, context, field_name)
    
    elif data == "finish_editing":
        await finish_editing(query, context)

async def choose_card_type(query, context):
    """Permite elegir el tipo de tarjeta"""
    keyboard = [
        [
            InlineKeyboardButton("📝 Básica", callback_data="basic_card"),
            InlineKeyboardButton("🔄 Reversible", callback_data="reversed_card")
        ],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🎴 *Elige el tipo de tarjeta:*",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def choose_deck(query, context):
    """Permite elegir el deck"""
    keyboard = [
        [
            InlineKeyboardButton("📚 STEP 1", callback_data="deck_step1"),
            InlineKeyboardButton("🎓 Self-Learning", callback_data="deck_self_learning")
        ],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📁 *Elige el deck donde agregar la tarjeta:*",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_card_preview(query, context):
    """Muestra una vista previa de la tarjeta antes de crear"""
    datos_anki = context.user_data.get('current_word_data')
    card_type = context.user_data.get('card_type', 'Basic')
    
    if not datos_anki:
        await query.edit_message_text("❌ Error: No hay datos de la palabra.")
        return
    
    # Crear vista previa que coincida con el formato de Anki
    palabra = datos_anki.get('Palabra', '')
    pronunciacion = datos_anki.get('Pronunciacion', 'N/A')
    
    # Formatear significado
    significado_text = ""
    if isinstance(datos_anki.get('Significado'), list):
        for significado in datos_anki.get('Significado'):
            significado_text += f"• {significado}\n"
    else:
        significado_text = f"{datos_anki.get('Significado', '')}\n"
    
    preview_text = f"""
📋 **VISTA PREVIA DE TARJETA**

🎴 **Tipo:** {card_type}
📝 **Front:** {palabra} ({pronunciacion})

📖 **Back:**
{significado_text}
💬 {datos_anki.get('Oracion_Comun', 'N/A')}

🏥 {datos_anki.get('Oracion_medica', 'N/A')}

¿Crear esta tarjeta en Anki?
    """
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Crear tarjeta", callback_data="confirm_create_final"),
            InlineKeyboardButton("✏️ Editar", callback_data="edit_card")
        ],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(preview_text, parse_mode=None, reply_markup=reply_markup)

async def create_card_final(query, context):
    """Crea la tarjeta final en Anki o edita una existente - VERSIÓN CORREGIDA"""
    datos_anki = context.user_data.get('current_word_data')
    card_type = context.user_data.get('card_type', 'Basic')
    deck_name = context.user_data.get('chosen_deck')
    
    # Verificar si estamos editando una tarjeta existente
    editing_existing = context.user_data.get('editing_existing_note', False)
    existing_note_id = context.user_data.get('existing_note_id')
    
    if not datos_anki:
        await query.edit_message_text("❌ Error: No hay datos de la palabra. Intenta nuevamente.")
        return
    
    # Obtener información para el mensaje final
    palabra = datos_anki.get('Palabra', '')
    pronunciacion = datos_anki.get('Pronunciacion', 'N/A')
    
    if editing_existing and existing_note_id:
        await query.edit_message_text("⏳ Actualizando tarjeta en Anki...")
        resultado = editar_tarjeta_existente_completa(existing_note_id, datos_anki, card_type, deck_name)
    else:
        await query.edit_message_text("⏳ Creando tarjeta en Anki...")
        resultado = crear_tarjeta_anki(datos_anki, card_type, deck_name)
    
    # Limpiar datos del usuario PRIMERO
    context.user_data.clear()
    
    # MANEJO DE RESPUESTAS
    if resultado is None:
        mensaje_final = "❌ Error crítico: La función devolvió None.\n\nVerifica la consola para más detalles."
        await query.edit_message_text(mensaje_final)
        return
    
    # Si hay error
    if isinstance(resultado, dict) and 'error' in resultado:
        error_msg = resultado['error']
        action = "actualizar" if editing_existing else "crear"
        mensaje_final = f"❌ Error al {action} la tarjeta:\n{error_msg}"
        await query.edit_message_text(mensaje_final)
        return
    
    # SI ES ÉXITO - Mostrar SOLO la vista previa final limpia
    action = "actualizada" if editing_existing else "creada"
    
    # Formatear significado para vista final (escapar caracteres problemáticos)
    significado_text = ""
    if isinstance(datos_anki.get('Significado'), list):
        for significado in datos_anki.get('Significado'):
            # Escapar caracteres especiales de Markdown
            significado_limpio = significado.replace('*', '\\*').replace('_', '\\_').replace('`', '\\`')
            significado_text += f"• {significado_limpio}\n"
    else:
        significado_limpio = str(datos_anki.get('Significado', '')).replace('*', '\\*').replace('_', '\\_').replace('`', '\\`')
        significado_text = f"{significado_limpio}\n"
    
    # Limpiar otros campos de caracteres problemáticos
    oracion_comun_limpia = str(datos_anki.get('Oracion_Comun', 'N/A')).replace('*', '\\*').replace('_', '\\_').replace('`', '\\`')
    oracion_medica_limpia = str(datos_anki.get('Oracion_medica', 'N/A')).replace('*', '\\*').replace('_', '\\_').replace('`', '\\`')
    palabra_limpia = palabra.replace('*', '\\*').replace('_', '\\_').replace('`', '\\`')
    pronunciacion_limpia = pronunciacion.replace('*', '\\*').replace('_', '\\_').replace('`', '\\`')
    
    # MENSAJE FINAL LIMPIO - Solo palabra y vista previa (CON MARKDOWN ESCAPADO)
    mensaje_final = f"""
🎉 *TARJETA {action.upper()} CON ÉXITO*

📝 *Palabra:* {palabra_limpia}
🔊 *Pronunciación:* {pronunciacion_limpia}
📚 *Deck:* {deck_name}
🎴 *Tipo:* {card_type}

*CONTENIDO FINAL:*
{significado_text}
💬 _{oracion_comun_limpia}_
🏥 _{oracion_medica_limpia}_

¡Lista para estudiar! 🚀
    """
    
    # Usar parse_mode='Markdown' con texto escapado
    try:
        await query.edit_message_text(mensaje_final, parse_mode='Markdown')
    except Exception as e:
        # Si falla Markdown, enviar sin formato
        print(f"Error con Markdown, enviando sin formato: {e}")
        mensaje_sin_formato = f"""
🎉 TARJETA {action.upper()} CON ÉXITO

📝 Palabra: {palabra}
🔊 Pronunciación: {pronunciacion}
📚 Deck: {deck_name}
🎴 Tipo: {card_type}

CONTENIDO FINAL:
{significado_text.replace('• ', '- ')}
💬 {oracion_comun_limpia}
🏥 {oracion_medica_limpia}

¡Lista para estudiar! 🚀
        """
        await query.edit_message_text(mensaje_sin_formato)

async def edit_card_menu(query, context):
    """Menú para seleccionar qué campo editar - VERSIÓN SIMPLIFICADA"""
    datos_anki = context.user_data.get('current_word_data')
    
    if not datos_anki:
        await query.edit_message_text("❌ Error: No hay datos de la palabra para editar.")
        return
    
    # Crear vista previa actualizada SOLO con campos que van a Anki
    palabra = datos_anki.get('Palabra', '')
    pronunciacion = datos_anki.get('Pronunciacion', 'N/A')
    
    # Formatear significado para vista previa
    significado_text = ""
    if isinstance(datos_anki.get('Significado'), list):
        for i, sig in enumerate(datos_anki.get('Significado')[:3]):  # Mostrar solo primeros 3
            significado_text += f"  {i+1}. {sig}\n"
        if len(datos_anki.get('Significado')) > 3:
            significado_text += f"  ... y {len(datos_anki.get('Significado')) - 3} más\n"
    else:
        significado_text = f"{datos_anki.get('Significado', '')}\n"
    
    preview_text = f"""
✏️ **EDITAR TARJETA - VISTA PREVIA**

📝 *Palabra:* {palabra}
🔊 *Pronunciación:* {pronunciacion}

📖 *Significados:*
{significado_text}
💬 *Oración común:* 
{datos_anki.get('Oracion_Comun', 'N/A')}

🏥 *Oración médica:* 
{datos_anki.get('Oracion_medica', 'N/A')}

**Selecciona el campo que quieres modificar:**
(Escribe /skip en cualquier momento para cancelar la edición de un campo)
    """
    
    # TECLADO SIMPLIFICADO - Solo campos que van a Anki
    keyboard = [
        [InlineKeyboardButton("📝 Palabra", callback_data="edit_field:Palabra")],
        [InlineKeyboardButton("🔊 Pronunciación", callback_data="edit_field:Pronunciacion")],
        [InlineKeyboardButton("📖 Significado", callback_data="edit_field:Significado")],
        [InlineKeyboardButton("💬 Oración común", callback_data="edit_field:Oracion_Comun")],
        [InlineKeyboardButton("🏥 Oración médica", callback_data="edit_field:Oracion_medica")],
        [
            InlineKeyboardButton("✅ Finalizar edición", callback_data="finish_editing"),
            InlineKeyboardButton("🚪 Salir sin guardar", callback_data="cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(preview_text, parse_mode='Markdown', reply_markup=reply_markup)

async def handle_field_edit(query, context, field_name):
    """Maneja la edición de un campo específico - VERSIÓN MEJORADA"""
    context.user_data['editing_field'] = field_name
    context.user_data['state'] = EDITING_FIELD
    
    field_descriptions = {
        'Palabra': 'la palabra principal',
        'Pronunciacion': 'la pronunciación', 
        'Significado': 'los significados (uno por línea)',
        'Oracion_Comun': 'la oración común',
        'Oracion_medica': 'la oración médica'
    }
    
    description = field_descriptions.get(field_name, field_name)
    current_value = context.user_data['current_word_data'].get(field_name, '')
    
    if isinstance(current_value, list):
        current_value = '\n'.join([f"• {item}" for item in current_value])
    
    # ENVIAR NUEVO MENSAJE en lugar de editar el anterior
    message = f"""
✍️ **Editando {description}**

📋 **Valor actual:**
{current_value if current_value else "Vacío"}

**Envía el nuevo valor o escribe /skip para mantener el actual.**
    
💡 *El menú de edición permanecerá disponible para seguir editando otros campos.*
    """
    
    # Enviar como nuevo mensaje en lugar de editar
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=message,
        parse_mode='Markdown'
    )
    
    # Mantener el mensaje anterior con los botones visible
    await query.answer(f"Preparado para editar {description}...")

async def handle_edit_text(update, context):
    """Maneja el texto ingresado para editar un campo - VERSIÓN MEJORADA"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if not is_user_authorized(user_id):
        await update.message.reply_text("❌ No estás autorizado.")
        return
    
    field_name = context.user_data.get('editing_field')
    if not field_name:
        await update.message.reply_text("❌ Error: No se está editando ningún campo.")
        return
    
    # SI el usuario envía /skip, no modificar el campo y volver al menú
    if text == "/skip":
        await update.message.reply_text("⏭️ Campo no modificado. Volviendo al menú de edición...")
        # Limpiar el estado de edición
        context.user_data['state'] = EDITING_CARD
        context.user_data.pop('editing_field', None)
        await edit_card_menu_from_update(update, context)
        return
    
    datos_anki = context.user_data.get('current_word_data', {})
    
    # Procesar el campo según su tipo
    if field_name == 'Significado':
        # Convertir texto en lista (separado por líneas)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        # Remover viñetas si existen
        cleaned_lines = [line.replace('- ', '').replace('• ', '') for line in lines]
        datos_anki[field_name] = cleaned_lines
    else:
        datos_anki[field_name] = text
    
    context.user_data['current_word_data'] = datos_anki
    await update.message.reply_text("✅ Campo actualizado correctamente.")
    
    # Limpiar el estado de edición y volver al menú
    context.user_data['state'] = EDITING_CARD
    context.user_data.pop('editing_field', None)
    await edit_card_menu_from_update(update, context)

async def edit_card_menu_from_update(update, context):
    """Versión de edit_card_menu para ser llamada desde update - VERSIÓN SIMPLIFICADA"""
    datos_anki = context.user_data.get('current_word_data')
    
    if not datos_anki:
        await update.message.reply_text("❌ Error: No hay datos de la palabra para editar.")
        return
    
    # Crear la misma vista previa simplificada
    palabra = datos_anki.get('Palabra', '')
    pronunciacion = datos_anki.get('Pronunciacion', 'N/A')
    
    significado_text = ""
    if isinstance(datos_anki.get('Significado'), list):
        for i, sig in enumerate(datos_anki.get('Significado')[:3]):
            significado_text += f"  {i+1}. {sig}\n"
        if len(datos_anki.get('Significado')) > 3:
            significado_text += f"  ... y {len(datos_anki.get('Significado')) - 3} más\n"
    else:
        significado_text = f"{datos_anki.get('Significado', '')}\n"
    
    preview_text = f"""
✏️ **EDITAR TARJETA - VISTA PREVIA**

📝 *Palabra:* {palabra}
🔊 *Pronunciación:* {pronunciacion}

📖 *Significados:*
{significado_text}
💬 *Oración común:* 
{datos_anki.get('Oracion_Comun', 'N/A')}

🏥 *Oración médica:* 
{datos_anki.get('Oracion_medica', 'N/A')}

**Selecciona el campo que quieres modificar:**
(Escribe /skip en cualquier momento para cancelar la edición de un campo)
    """
    
    # TECLADO SIMPLIFICADO - Solo campos que van a Anki
    keyboard = [
        [InlineKeyboardButton("📝 Palabra", callback_data="edit_field:Palabra")],
        [InlineKeyboardButton("🔊 Pronunciación", callback_data="edit_field:Pronunciacion")],
        [InlineKeyboardButton("📖 Significado", callback_data="edit_field:Significado")],
        [InlineKeyboardButton("💬 Oración común", callback_data="edit_field:Oracion_Comun")],
        [InlineKeyboardButton("🏥 Oración médica", callback_data="edit_field:Oracion_medica")],
        [
            InlineKeyboardButton("✅ Finalizar edición", callback_data="finish_editing"),
            InlineKeyboardButton("🚪 Salir sin guardar", callback_data="cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(preview_text, parse_mode='Markdown', reply_markup=reply_markup)

async def finish_editing(query, context):
    """Finaliza la edición y vuelve a la vista previa"""
    await query.edit_message_text("✅ Edición finalizada.")
    await show_card_preview(query, context)

async def handle_skip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /skip durante la edición"""
    user_id = update.effective_user.id
    
    if not is_user_authorized(user_id):
        await update.message.reply_text("❌ No estás autorizado.")
        return
    
    # Verificar si estamos en modo edición
    if context.user_data.get('state') == EDITING_FIELD:
        field_name = context.user_data.get('editing_field')
        await update.message.reply_text(f"⏭️ Campo '{field_name}' no modificado. Volviendo al menú...")
        
        # Limpiar estado de edición y volver al menú
        context.user_data['state'] = EDITING_CARD
        context.user_data.pop('editing_field', None)
        await edit_card_menu_from_update(update, context)
    else:
        await update.message.reply_text("ℹ️ El comando /skip solo funciona cuando estás editando un campo.")
    
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja errores"""
    logger.error(f"Error: {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Ocurrió un error inesperado. Por favor, intenta nuevamente."
        )

def main():
    """Función principal para ejecutar el bot"""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN no está configurado en las variables de entorno")
    
    if not ALLOWED_USER_IDS:
        raise ValueError("❌ ALLOWED_USER_IDS no está configurado en las variables de entorno")
    
    # Crear la aplicación
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Manejar comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("word", handle_word_command))
    application.add_handler(CommandHandler("skip", handle_skip_command))
    
    # Manejar mensajes de texto
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # Manejar botones inline
    application.add_handler(CallbackQueryHandler(handle_button))
    
    # Manejar errores
    application.add_error_handler(error_handler)
    
    # Iniciar el bot
    print("🤖 Bot de Telegram iniciado...")
    print("📚 Conectado a Anki a través de AnkiConnect")
    application.run_polling()

if __name__ == "__main__":
    main()