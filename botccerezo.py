import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import re
from datetime import datetime, timedelta, timezone

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        
    async def setup_hook(self):
        cargar_plantillas_desde_archivo()
        cargar_raid_activa()
        
        # 🚀 Al subirlo a producción, usamos la sincronización global estándar.
        # Render se encargará de propagarlo a todos los servidores de forma limpia.
        await self.tree.sync()
        
        # ⏰ Vigilante persistente que lee el archivo JSON en vivo cada 5 segundos
        self.verificador_persistente.start()
        print("¡Comandos globales sincronizados con éxito en Render!")

    async def on_ready(self):
        print(f"🤖 Bot conectado con éxito en la nube como: {self.user.name}")

    def cog_unload(self):
        self.verificador_persistente.cancel()

# ==========================================
# ⏰ VIGILANTE ULTRA SEGURO (LEE DESDE DISCO)
# ==========================================
    @tasks.loop(seconds=5)
    async def verificador_persistente(self):
        global RAID_ACTIVA_DATOS, RAID_CERRADA
        if not RAID_ACTIVA_DATOS or RAID_ACTIVA_DATOS.get("notificado", True):
            return
            
        ahora_unix = int(datetime.now(timezone.utc).timestamp())
        target_unix = RAID_ACTIVA_DATOS.get("target_unix", 0)
        
        if ahora_unix >= target_unix:
            canal = self.get_channel(RAID_ACTIVA_DATOS.get("canal_id", 0))
            if canal:
                slots = RAID_ACTIVA_DATOS.get("slots", {})
                usuarios_a_notificar = []
                for usuarios in slots.values():
                    for u in usuarios:
                        if u not in usuarios_a_notificar:
                            usuarios_a_notificar.append(u)
                            
                actividad = RAID_ACTIVA_DATOS.get("actividad", "Raid")
                if usuarios_a_notificar:
                    lista_pings = " ".join(usuarios_a_notificar)
                    mensaje = f"🔔 {lista_pings}\n\n⚔️ ¡La actividad **{actividad}** está por comenzar! Júntense en el juego / Discord."
                else:
                    mensaje = f"📢 La actividad **{actividad}** ha alcanzado su hora de inicio, pero no había nadie anotado."
                    
                try:
                    await canal.send(mensaje)
                    RAID_ACTIVA_DATOS["notificado"] = True
                    RAID_CERRADA = True
                    guardar_raid_activa()
                    
                    async for msg in canal.history(limit=5):
                        if msg.author.id == self.user.id and msg.embeds:
                            await msg.edit(content="⚠️ **Actividad Iniciada**", view=None)
                            break
                except Exception as e:
                    print(f"Error en notificación persistente: {e}")

    @verificador_persistente.before_loop
    async def antes_de_verificar(self):
        await self.wait_until_ready()

bot = MyBot()

# ==========================================
# 💾 SISTEMA DE BASE DE DATOS LOCAL (JSON)
# ==========================================
PLANTILLAS_GLOBALES = {}
RAID_ACTIVA_DATOS = {}
# En Render, usamos la carpeta /data para que los archivos no se borren al reiniciar
os.makedirs("data", exist_ok=True)
ARCHIVO_PLANTILLAS = os.path.join("data", "plantillas.json")
ARCHIVO_RAID = os.path.join("data", "raid_activa.json")

def guardar_plantillas_en_archivo():
    try:
        with open(ARCHIVO_PLANTILLAS, "w", encoding="utf-8") as f:
            json.dump(PLANTILLAS_GLOBALES, f, ensure_ascii=False, indent=4)
    except Exception as e: print(f"Error guardando plantillas: {e}")

def cargar_plantillas_desde_archivo():
    global PLANTILLAS_GLOBALES
    if os.path.exists(ARCHIVO_PLANTILLAS):
        try:
            with open(ARCHIVO_PLANTILLAS, "r", encoding="utf-8") as f:
                PLANTILLAS_GLOBALES = json.load(f)
        except Exception: PLANTILLAS_GLOBALES = {}

def guardar_raid_activa():
    try:
        with open(ARCHIVO_RAID, "w", encoding="utf-8") as f:
            json.dump(RAID_ACTIVA_DATOS, f, ensure_ascii=False, indent=4)
    except Exception as e: print(f"Error guardando raid activa: {e}")

def cargar_raid_activa():
    global RAID_ACTIVA_DATOS, ROLES_CONFIG, raid_slots, listas_especiales, CREADOR_ID, ACTIVIDAD_ACTUAL, DESCRIPCION_ACTUAL, TIMESTAMP_DISCORD, IMAGEN_URL_ACTUAL, FECHA_CREACION_PING
    if os.path.exists(ARCHIVO_RAID):
        try:
            with open(ARCHIVO_RAID, "r", encoding="utf-8") as f:
                RAID_ACTIVA_DATOS = json.load(f)
                if RAID_ACTIVA_DATOS:
                    ROLES_CONFIG = RAID_ACTIVA_DATOS.get("config_roles", {})
                    raid_slots = RAID_ACTIVA_DATOS.get("slots", {})
                    listas_especiales = RAID_ACTIVA_DATOS.get("listas_especiales", {})
                    CREADOR_ID = RAID_ACTIVA_DATOS.get("creador_id")
                    ACTIVIDAD_ACTUAL = RAID_ACTIVA_DATOS.get("actividad", "")
                    DESCRIPCION_ACTUAL = RAID_ACTIVA_DATOS.get("descripcion", "")
                    TIMESTAMP_DISCORD = RAID_ACTIVA_DATOS.get("timestamp_text", "")
                    IMAGEN_URL_ACTUAL = RAID_ACTIVA_DATOS.get("imagen", "")
                    FECHA_CREACION_PING = RAID_ACTIVA_DATOS.get("publicado", "")
        except Exception:
            RAID_ACTIVA_DATOS = {}

# Variables de estado en vivo
ROLES_CONFIG = {}
raid_slots = {}
listas_especiales = {"Bench": [], "Late": [], "Tentative": [], "Absence": []}
RAID_CERRADA = False
CREADOR_ID = None
ACTIVIDAD_ACTUAL = ""
DESCRIPCION_ACTUAL = ""
TIMESTAMP_DISCORD = "" 
IMAGEN_URL_ACTUAL = ""
FECHA_CREACION_PING = ""

# ==========================================
# 🧠 PROCESADOR DE EMOJIS INTEGRADOS
# ==========================================
def extraer_emoji_usuario(texto_rol):
    texto_rol = str(texto_rol).strip()
    match_custom = re.search(r'<(a?):([^:]+):([0-9]+)>', texto_rol)
    if match_custom:
        return match_custom.group(0), texto_rol.replace(match_custom.group(0), "").strip()
    match_unicode = re.search(r'[\u2600-\u27BF]|[\u2000-\u3300]|[\ud83c-\udbff][\udc00-\udfff]', texto_rol)
    if match_unicode:
        return match_unicode.group(0), texto_rol.replace(match_unicode.group(0), "").strip()
    return None, texto_rol

def convertir_a_partial_emoji(emoji_texto):
    if not emoji_texto: return None
    match = re.match(r'<(a?):([^:]+):([0-9]+)>', emoji_texto.strip())
    if match: return discord.PartialEmoji(animated=bool(match.group(1)), name=match.group(2), id=int(match.group(3)))
    return emoji_texto.strip()

# ==========================================
# 📊 GENERADOR DEL EMBED DINÁMICO
# ==========================================
def generar_embed_raid():
    embed = discord.Embed(title=ACTIVIDAD_ACTUAL, color=discord.Color.red() if RAID_CERRADA else discord.Color.dark_gray())
    total_anotados = sum(len(users) for users in raid_slots.values())
    max_cupos = sum(cfg.get("limite", 1) for cfg in ROLES_CONFIG.values()) if ROLES_CONFIG else 0
    
    embed.add_field(name="👑 Organizador", value=f"<@{CREADOR_ID}>", inline=True)
    embed.add_field(name="⏳ Empieza", value=TIMESTAMP_DISCORD, inline=False)
    embed.add_field(name="👥 Cupos", value=f"`{total_anotados}/{max_cupos}`", inline=True)
    
    cuerpo = f"{DESCRIPCION_ACTUAL}\n"
    if RAID_CERRADA: cuerpo += "\n⚠️ **¡ESTA ACTIVIDAD ESTÁ CERRADA!**\n"
    cuerpo += "───────────────────\n\n"
    
    for rol, config in ROLES_CONFIG.items():
        anotados = raid_slots.get(rol, [])
        prefix = f"{config.get('emoji', '')} " if config.get('emoji') else ""
        cuerpo += f"{prefix}**{rol} ({len(anotados)}/{config.get('limite', 1)})**\n"
        cuerpo += "\n".join(anotados) + "\n\n" if anotados else "—\n\n"
                
    cuerpo += "───────────────────\n"
    for k, v in listas_especiales.items():
        if v: cuerpo += f"🔹 **{k} ({len(v)}):**\n" + ", ".join(v) + "\n"
            
    embed.description = cuerpo
    embed.set_image(url=IMAGEN_URL_ACTUAL if IMAGEN_URL_ACTUAL else "https://media.discordapp.net/attachments/147139695686000000/147139695686000001/image_599c24.png")
    if FECHA_CREACION_PING: embed.set_footer(text=f"📅 Publicado el: {FECHA_CREACION_PING}")
    return embed

def sincronizar_registro_disco():
    global RAID_ACTIVA_DATOS
    if RAID_ACTIVA_DATOS:
        RAID_ACTIVA_DATOS["slots"] = raid_slots
        RAID_ACTIVA_DATOS["listas_especiales"] = listas_especiales
        guardar_raid_activa()

class RaidRoleSelect(discord.ui.Select):
    def __init__(self):
        opciones = []
        for rol, config in ROLES_CONFIG.items():
            if len(raid_slots.get(rol, [])) >= config.get("limite", 1): continue
            opciones.append(discord.SelectOption(label=rol, emoji=convertir_a_partial_emoji(config.get("emoji")), value=rol))
        if not opciones:
            opciones.append(discord.SelectOption(label="¡Raid llena!", value="FULL"))
        super().__init__(placeholder="Selecciona tu clase / rol...", options=opciones)

    async def callback(self, interaction: discord.Interaction):
        if RAID_CERRADA: return
        if self.values[0] == "FULL": return
        
        limpiar_usuario_completo(interaction.user.mention)
        raid_slots[self.values[0]].append(interaction.user.mention)
        sincronizar_registro_disco()
        
        view = RaidButtonsView()
        view.add_item(RaidRoleSelect())
        await interaction.response.edit_message(embed=generar_embed_raid(), view=view)

class RaidButtonsView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    
    async def refrescar(self, intx):
        sincronizar_registro_disco()
        v = RaidButtonsView()
        v.add_item(RaidRoleSelect())
        await intx.response.edit_message(embed=generar_embed_raid(), view=v)

    @discord.ui.button(label="Bench", style=discord.ButtonStyle.grey, custom_id="b_bh")
    async def b_bh(self, i, b):
        limpiar_usuario_completo(i.user.mention); listas_especiales["Bench"].append(i.user.mention); await self.refrescar(i)
    @discord.ui.button(label="Late", style=discord.ButtonStyle.grey, custom_id="b_lt")
    async def b_lt(self, i, b):
        limpiar_usuario_completo(i.user.mention); listas_especiales["Late"].append(i.user.mention); await self.refrescar(i)
    @discord.ui.button(label="Tentative", style=discord.ButtonStyle.grey, custom_id="b_tt")
    async def b_tt(self, i, b):
        limpiar_usuario_completo(i.user.mention); listas_especiales["Tentative"].append(i.user.mention); await self.refrescar(i)
    @discord.ui.button(label="Absence", style=discord.ButtonStyle.grey, custom_id="b_ab")
    async def b_ab(self, i, b):
        limpiar_usuario_completo(i.user.mention); listas_especiales["Absence"].append(i.user.mention); await self.refrescar(i)
    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red, custom_id="b_lv")
    async def b_lv(self, i, b):
        limpiar_usuario_completo(i.user.mention); await self.refrescar(i)

def limpiar_usuario_completo(mencion):
    for r in raid_slots.values():
        if mencion in r: r.remove(mencion)
    for l in listas_especiales.values():
        if mencion in l: l.remove(mencion)

# ==========================================
# ➕ COMANDOS DE BARRA
# ==========================================
@bot.tree.command(name="raid-template-create", description="Define la estructura base")
async def raid_template_create(interaction: discord.Interaction, template_name: str, roles_y_cupos: str):
    try:
        nueva = {}
        for parte in roles_y_cupos.split(","):
            if ":" not in parte: continue
            r_raw, c_raw = parte.split(":", 1)
            emoji, nombre = extraer_emoji_usuario(r_raw.strip())
            nueva[nombre.upper()] = {"emoji": emoji if emoji else "", "limite": int(c_raw.strip())}
        PLANTILLAS_GLOBALES[template_name] = nueva
        guardar_plantillas_en_archivo()
        await interaction.response.send_message(f"✅ Plantilla **'{template_name}'** guardada.", ephemeral=True)
    except Exception: await interaction.response.send_message("❌ Formato incorrecto.", ephemeral=True)

@bot.tree.command(name="raid-create", description="Lanza la actividad hoy")
async def raid_create(
    interaction: discord.Interaction, template_name: str, nombre_actividad: str, 
    hora_evento_24h: str, informacion_actividad: str, fecha_evento: str = None, 
    imagen_archivo: discord.Attachment = None
):
    global ROLES_CONFIG, raid_slots, listas_especiales, CREADOR_ID, ACTIVIDAD_ACTUAL, DESCRIPCION_ACTUAL, TIMESTAMP_DISCORD, IMAGEN_URL_ACTUAL, FECHA_CREACION_PING, RAID_ACTIVA_DATOS, RAID_CERRADA
    if template_name not in PLANTILLAS_GLOBALES:
        await interaction.response.send_message("❌ No existe la plantilla.", ephemeral=True)
        return
        
    try:
        CREADOR_ID = interaction.user.id
        ACTIVIDAD_ACTUAL = nombre_actividad.strip()
        DESCRIPCION_ACTUAL = informacion_actividad.strip()
        ROLES_CONFIG = PLANTILLAS_GLOBALES[template_name]
        
        ahora_local = datetime.now()
        FECHA_CREACION_PING = ahora_local.strftime("%d/%m/%Y")
        
        hora_str, min_str = hora_evento_24h.replace(" ", "").split(":")
        if fecha_evento:
            d, m = fecha_evento.replace(" ", "").replace("-", "/").split("/")[:2]
            ev_dt = datetime(year=ahora_local.year, month=int(m), day=int(d), hour=int(hora_str), minute=int(min_str))
        else:
            ev_dt = ahora_local.replace(hour=int(hora_str), minute=int(min_str), second=0, microsecond=0)
            if ev_dt < ahora_local: ev_dt += timedelta(days=1)
            
        target_utc_unix = int(ev_dt.astimezone(timezone.utc).timestamp())
        TIMESTAMP_DISCORD = f"<t:{target_utc_unix}:F> (<t:{target_utc_unix}:R>)"
        IMAGEN_URL_ACTUAL = imagen_archivo.url if imagen_archivo else ""
        
        raid_slots = {r: [] for r in ROLES_CONFIG}
        listas_especiales = {"Bench": [], "Late": [], "Tentative": [], "Absence": []}
        RAID_CERRADA = False
        
        RAID_ACTIVA_DATOS = {
            "actividad": ACTIVIDAD_ACTUAL, "descripcion": DESCRIPCION_ACTUAL, "creador_id": CREADOR_ID,
            "target_unix": target_utc_unix, "canal_id": interaction.channel_id, "publicado": FECHA_CREACION_PING,
            "timestamp_text": TIMESTAMP_DISCORD, "imagen": IMAGEN_URL_ACTUAL, "config_roles": ROLES_CONFIG,
            "slots": raid_slots, "listas_especiales": listas_especiales, "notificado": False
        }
        guardar_raid_activa()
        
        view = RaidButtonsView()
        view.add_item(RaidRoleSelect())
        await interaction.response.send_message(embed=generar_embed_raid(), view=view)
    except Exception as e:
        print(e)
        await interaction.response.send_message("❌ Error al configurar la fecha/hora.", ephemeral=True)

@raid_create.autocomplete("template_name")
async def rc_auto(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=n, value=n) for n in PLANTILLAS_GLOBALES.keys() if current.lower() in n.lower()][:25]

# ==========================================
# 🗑️ COMANDO PARA BORRAR PLANTILLAS BASE
# ==========================================
@bot.tree.command(name="raid-template-delete", description="Elimina una plantilla global del bot")
@app_commands.describe(template_name="Selecciona cuál de tus plantillas guardadas deseas borrar permanentemente")
async def raid_template_delete(interaction: discord.Interaction, template_name: str):
    if template_name in PLANTILLAS_GLOBALES:
        del PLANTILLAS_GLOBALES[template_name]
        guardar_plantillas_en_archivo()
        await interaction.response.send_message(f"🗑️ La plantilla **'{template_name}'** ha sido eliminada con éxito.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ No existe ninguna plantilla llamada '{template_name}' en la base de datos.", ephemeral=True)

@raid_template_delete.autocomplete("template_name")
async def rtd_auto(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=n, value=n) for n in PLANTILLAS_GLOBALES.keys() if current.lower() in n.lower()][:25]

# 🔐 LEER TOKEN DESDE ENVIROMENT (OBLIGATORIO EN LA NUBE)
token_seguro = os.environ.get('DISCORD_TOKEN')
if token_seguro:
    bot.run(token_seguro)
else:
    print("❌ ERROR: No se encontró la variable de entorno DISCORD_TOKEN en el servidor.")