import discord
import asyncio
import os
from datetime import datetime

# ============================================================
#   Le token est lu automatiquement depuis Railway
#   Ne colle JAMAIS ton token ici directement !
# ============================================================
TOKEN = os.environ.get("TOKEN")
GUILD_ID = int(os.environ.get("GUILD_ID", "1510712769731624990"))
# ============================================================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
client = discord.Client(intents=intents)

ticket_counter = {}

# ─── HELPERS PERMISSIONS ─────────────────────────────────────────────────────

def hidden():
    return discord.PermissionOverwrite(view_channel=False)

def read_only():
    return discord.PermissionOverwrite(view_channel=True, send_messages=False, add_reactions=False)

def read_write():
    return discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

def staff_perms():
    return discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True, manage_channels=True, read_message_history=True)

def ticket_user():
    return discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True)

# ─── HELPERS CRÉATION ────────────────────────────────────────────────────────

async def get_or_create_role(guild, existing, name, color, hoist=False):
    if name in existing:
        print(f"  ↩️  Rôle existant : {name}")
        return existing[name]
    role = await guild.create_role(name=name, color=color, hoist=hoist, mentionable=True)
    print(f"  ✅ Rôle créé : {name}")
    await asyncio.sleep(0.8)
    return role

async def make_cat(guild, existing, name, ow):
    if name in existing:
        print(f"  ↩️  Catégorie existante : {name}")
        return existing[name]
    cat = await guild.create_category(name, overwrites=ow)
    print(f"  ✅ Catégorie créée : {name}")
    await asyncio.sleep(0.8)
    return cat

async def make_text(guild, existing, name, cat, ow=None):
    if name in existing:
        print(f"    ↩️  Salon existant : {name}")
        return existing[name]
    kwargs = {"category": cat}
    if ow is not None:
        kwargs["overwrites"] = ow
    ch = await guild.create_text_channel(name, **kwargs)
    print(f"    ✅ Texte créé : {name}")
    await asyncio.sleep(0.8)
    return ch

async def make_voice(guild, existing, name, cat, ow=None):
    if name in existing:
        print(f"    ↩️  Salon existant : {name}")
        return existing[name]
    kwargs = {"category": cat}
    if ow is not None:
        kwargs["overwrites"] = ow
    ch = await guild.create_voice_channel(name, **kwargs)
    print(f"    ✅ Vocal créé : {name}")
    await asyncio.sleep(0.8)
    return ch

# ─── FERMETURE DE TICKET ─────────────────────────────────────────────────────

class CloseTicketView(discord.ui.View):
    def __init__(self, owner, staff_roles, log_channel):
        super().__init__(timeout=None)
        self.owner       = owner
        self.staff_roles = staff_roles
        self.log_channel = log_channel

    @discord.ui.button(label="🔒 Fermer le ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        user  = interaction.user
        chan  = interaction.channel
        is_staff = any(r in user.roles for r in self.staff_roles)
        if user.id != self.owner.id and not is_staff:
            await interaction.response.send_message("❌ Tu n'as pas la permission de fermer ce ticket.", ephemeral=True)
            return

        messages = []
        async for msg in chan.history(limit=300, oldest_first=True):
            if not msg.author.bot:
                messages.append(f"[{msg.created_at.strftime('%d/%m %H:%M')}] {msg.author.display_name}: {msg.content}")
        transcript = "\n".join(messages) if messages else "Aucun message."

        if self.log_channel:
            log_embed = discord.Embed(
                title=f"🔒 Ticket fermé : #{chan.name}",
                description=f"Fermé par {user.mention} — Ouvert par {self.owner.mention}",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            preview = transcript[:1800]
            if len(transcript) > 1800:
                preview += "\n... (tronqué)"
            log_embed.add_field(name="Transcript", value=f"```{preview}```", inline=False)
            await self.log_channel.send(embed=log_embed)

        await interaction.response.send_message("🔒 Fermeture du ticket dans 5 secondes...")
        await asyncio.sleep(5)
        await chan.delete()

# ─── HELPER CRÉATION DE TICKET ───────────────────────────────────────────────

async def create_ticket(interaction, label, category, staff_roles, log_channel, description_text, color=discord.Color.blurple()):
    guild = interaction.guild
    user  = interaction.user

    ticket_counter[guild.id] = ticket_counter.get(guild.id, 0) + 1
    num      = str(ticket_counter[guild.id]).zfill(4)
    chan_name = f"ticket-{label}-{num}"

    ow = {guild.default_role: hidden(), user: ticket_user()}
    for r in staff_roles:
        ow[r] = staff_perms()

    ticket_chan = await guild.create_text_channel(
        chan_name,
        category=category,
        overwrites=ow,
        topic=f"Ticket #{num} | {label} | {user.display_name}"
    )

    embed = discord.Embed(
        title=f"🎫 Ticket #{num} — {label.upper()}",
        description=f"Bienvenue {user.mention} !\n\n{description_text}\n\nUn membre du staff va prendre en charge ta demande.",
        color=color,
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text="MCD Seven • Cliquez sur Fermer pour clore le ticket")

    await ticket_chan.send(
        content=f"{user.mention} " + " ".join(r.mention for r in staff_roles),
        embed=embed,
        view=CloseTicketView(user, staff_roles, log_channel)
    )

    if log_channel:
        log_embed = discord.Embed(title="🎫 Nouveau ticket", color=discord.Color.green(), timestamp=datetime.utcnow())
        log_embed.add_field(name="Utilisateur", value=f"{user.mention} ({user})", inline=True)
        log_embed.add_field(name="Type",        value=label,                      inline=True)
        log_embed.add_field(name="Salon",       value=ticket_chan.mention,        inline=True)
        await log_channel.send(embed=log_embed)

    await interaction.response.send_message(f"✅ Ticket créé : {ticket_chan.mention}", ephemeral=True)

# ══════════════════════════════════════════════════════════════════════════════
#  🎫 TICKET GÉNÉRAL
# ══════════════════════════════════════════════════════════════════════════════

class TicketGeneralView(discord.ui.View):
    def __init__(self, staff, cat_tickets, log_chan):
        super().__init__(timeout=None)
        self.staff      = staff
        self.cat        = cat_tickets
        self.log        = log_chan

    @discord.ui.select(
        custom_id="ticket_general_select",
        placeholder="📋 Choisir le type de ticket...",
        options=[
            discord.SelectOption(label="Support général",   value="support",   emoji="❓"),
            discord.SelectOption(label="Signalement",       value="signalement",emoji="🚨"),
            discord.SelectOption(label="Recours / Appel",   value="recours",   emoji="⚖️"),
            discord.SelectOption(label="Autre demande",     value="autre",     emoji="📝"),
        ]
    )
    async def callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        descs = {
            "support":    "Décris ton problème en détail.",
            "signalement":"Indique le pseudo concerné, la date et les faits. Joins des preuves si possible.",
            "recours":    "Indique la sanction, la date, et les raisons de ta contestation.",
            "autre":      "Explique ta demande en détail.",
        }
        colors = {
            "support": discord.Color.blurple(), "signalement": discord.Color.red(),
            "recours": discord.Color.orange(),  "autre": discord.Color.greyple(),
        }
        await create_ticket(interaction, select.values[0], self.cat, self.staff, self.log, descs[select.values[0]], colors[select.values[0]])

# ══════════════════════════════════════════════════════════════════════════════
#  🚓 TICKET GND
# ══════════════════════════════════════════════════════════════════════════════

class TicketGNDView(discord.ui.View):
    def __init__(self, staff, role_gnd, cat_tickets, log_chan):
        super().__init__(timeout=None)
        self.staff    = staff
        self.role_gnd = role_gnd
        self.cat      = cat_tickets
        self.log      = log_chan

    @discord.ui.select(
        custom_id="ticket_gnd_select",
        placeholder="🚓 Type de demande GND...",
        options=[
            discord.SelectOption(label="Candidature GND",        value="cand-gnd",    emoji="📋", description="Postuler à la GND"),
            discord.SelectOption(label="Rapport d'intervention",  value="rapport-gnd", emoji="📊", description="Soumettre un rapport"),
            discord.SelectOption(label="Demande de groupe",       value="groupe-gnd",  emoji="👥", description="Créer ou rejoindre un groupe GND"),
            discord.SelectOption(label="Signalement interne",     value="signal-gnd",  emoji="🚨", description="Signalement au sein de la GND"),
            discord.SelectOption(label="Demande d'équipement",    value="equip-gnd",   emoji="🔧", description="Réclamer ou signaler un équipement"),
            discord.SelectOption(label="Autre demande GND",       value="autre-gnd",   emoji="📝"),
        ]
    )
    async def callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        descs = {
            "cand-gnd":   "Présente-toi et explique pourquoi tu souhaites rejoindre la GND. Indique ton expérience RP.",
            "rapport-gnd":"Remplis ton rapport d'intervention : date, lieu, personnes impliquées, déroulé des faits.",
            "groupe-gnd": "Indique le nom du groupe souhaité, les membres et l'objectif de l'opération.",
            "signal-gnd": "Décris le comportement signalé, la personne concernée et les preuves disponibles.",
            "equip-gnd":  "Décris l'équipement demandé ou le problème rencontré avec ton équipement actuel.",
            "autre-gnd":  "Explique ta demande en détail.",
        }
        colors = {
            "cand-gnd": discord.Color.blue(),   "rapport-gnd": discord.Color.dark_blue(),
            "groupe-gnd": discord.Color.teal(),  "signal-gnd": discord.Color.red(),
            "equip-gnd": discord.Color.green(),  "autre-gnd": discord.Color.greyple(),
        }
        all_staff = self.staff + [self.role_gnd]
        val = select.values[0]
        if val in GROUP_LABELS:
            await create_ticket_with_threads(interaction, val, self.cat, all_staff, self.log, descs[val], colors.get(val, discord.Color.blue()))
        else:
            await create_ticket(interaction, val, self.cat, all_staff, self.log, descs[val], colors.get(val, discord.Color.blue()))

# ══════════════════════════════════════════════════════════════════════════════
#  🔍 TICKET DETECTIVE DIVISION
# ══════════════════════════════════════════════════════════════════════════════

class TicketDDView(discord.ui.View):
    def __init__(self, staff, role_dd, cat_tickets, log_chan):
        super().__init__(timeout=None)
        self.staff   = staff
        self.role_dd = role_dd
        self.cat     = cat_tickets
        self.log     = log_chan

    @discord.ui.select(
        custom_id="ticket_dd_select",
        placeholder="🔍 Type de demande Detective Division...",
        options=[
            discord.SelectOption(label="Candidature DD",          value="cand-dd",    emoji="📋", description="Postuler à la Detective Division"),
            discord.SelectOption(label="Ouverture d'enquête",      value="enquete-dd", emoji="🔎", description="Ouvrir une nouvelle enquête"),
            discord.SelectOption(label="Ajout de preuves",         value="preuve-dd",  emoji="📁", description="Soumettre des preuves à une enquête"),
            discord.SelectOption(label="Demande d'arrestation",    value="arrest-dd",  emoji="🚔", description="Demander un mandat ou une arrestation"),
            discord.SelectOption(label="Rapport de surveillance",   value="surv-dd",    emoji="👁️", description="Rapport de filature ou surveillance"),
            discord.SelectOption(label="Demande de groupe enquête", value="groupe-dd", emoji="👥", description="Créer un groupe pour une enquête"),
            discord.SelectOption(label="Autre demande DD",         value="autre-dd",   emoji="📝"),
        ]
    )
    async def callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        descs = {
            "cand-dd":   "Présente-toi et explique ta motivation pour rejoindre la DD. Indique ton expérience d'investigation.",
            "enquete-dd":"Donne le nom de l'affaire, les suspects potentiels, les faits observés et les preuves initiales.",
            "preuve-dd": "Indique le numéro d'enquête concerné et décris/joins les preuves à ajouter au dossier.",
            "arrest-dd": "Indique le suspect, les charges retenues, les preuves disponibles et le motif d'arrestation.",
            "surv-dd":   "Indique la cible, la durée de la surveillance, les lieux et les observations effectuées.",
            "groupe-dd": "Indique le nom de l'opération, les agents souhaités et l'objectif de l'enquête.",
            "autre-dd":  "Explique ta demande en détail.",
        }
        colors = {
            "cand-dd": discord.Color.red(),      "enquete-dd": discord.Color.dark_red(),
            "preuve-dd": discord.Color.orange(),  "arrest-dd": discord.Color.dark_orange(),
            "surv-dd": discord.Color.purple(),    "groupe-dd": discord.Color.dark_purple(),
            "autre-dd": discord.Color.greyple(),
        }
        all_staff = self.staff + [self.role_dd]
        val = select.values[0]
        if val in GROUP_LABELS:
            await create_ticket_with_threads(interaction, val, self.cat, all_staff, self.log, descs[val], colors.get(val, discord.Color.greyple()))
        else:
            await create_ticket(interaction, val, self.cat, all_staff, self.log, descs[val], colors.get(val, discord.Color.greyple()))

# ══════════════════════════════════════════════════════════════════════════════
#  👥 TICKET GROUPES & ENQUÊTES À VENIR
# ══════════════════════════════════════════════════════════════════════════════

class TicketGroupeView(discord.ui.View):
    def __init__(self, staff, role_gnd, role_dd, cat_tickets, log_chan):
        super().__init__(timeout=None)
        self.staff   = staff
        self.role_gnd = role_gnd
        self.role_dd  = role_dd
        self.cat      = cat_tickets
        self.log      = log_chan

    @discord.ui.select(
        custom_id="ticket_groupe_select",
        placeholder="👥 Type d'opération ou groupe...",
        options=[
            discord.SelectOption(label="Créer un groupe opérationnel", value="creer-groupe",  emoji="🆕", description="Former un nouveau groupe pour une mission"),
            discord.SelectOption(label="Rejoindre un groupe existant", value="join-groupe",   emoji="➕", description="Demander à rejoindre un groupe"),
            discord.SelectOption(label="Planifier une enquête",        value="plan-enquete",  emoji="📅", description="Planifier une enquête à venir"),
            discord.SelectOption(label="Opération conjointe GND + DD", value="op-conjointe",  emoji="🤝", description="Mission impliquant GND et Detective Division"),
            discord.SelectOption(label="Debriefing d'opération",       value="debrief",       emoji="📋", description="Faire le bilan d'une opération terminée"),
            discord.SelectOption(label="Demande de renfort",           value="renfort",       emoji="🆘", description="Demander du renfort pour une mission en cours"),
        ]
    )
    async def callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        descs = {
            "creer-groupe": "Indique le nom du groupe, l'objectif, les membres souhaités et la durée estimée de l'opération.",
            "join-groupe":  "Indique le nom du groupe que tu veux rejoindre et les raisons de ta candidature.",
            "plan-enquete": "Décris l'enquête à planifier : cibles, objectifs, moyens nécessaires et date souhaitée.",
            "op-conjointe": "Décris l'opération : objectif commun, rôles de la GND et de la DD, date et lieu.",
            "debrief":      "Indique le nom de l'opération, ce qui s'est passé, les résultats et les points à améliorer.",
            "renfort":      "Indique ta position, la situation et le nombre de renforts nécessaires.",
        }
        colors = {
            "creer-groupe": discord.Color.teal(),   "join-groupe": discord.Color.green(),
            "plan-enquete": discord.Color.blue(),    "op-conjointe": discord.Color.gold(),
            "debrief": discord.Color.greyple(),      "renfort": discord.Color.red(),
        }
        all_staff = self.staff + [self.role_gnd, self.role_dd]
        await create_ticket_with_threads(interaction, select.values[0], self.cat, all_staff, self.log, descs[select.values[0]], colors[select.values[0]])

# ══════════════════════════════════════════════════════════════════════════════
#  📂 CASIER JUDICIAIRE — AGENT
# ══════════════════════════════════════════════════════════════════════════════

class CasierView(discord.ui.View):
    def __init__(self, staff, role_gnd, role_dd, cat_casier, log_chan):
        super().__init__(timeout=None)
        self.staff    = staff
        self.role_gnd = role_gnd
        self.role_dd  = role_dd
        self.cat      = cat_casier
        self.log      = log_chan

    @discord.ui.select(
        custom_id="casier_select",
        placeholder="📂 Action sur le casier...",
        options=[
            discord.SelectOption(label="Ouvrir un casier agent",     value="ouvrir-casier",  emoji="📂", description="Créer le casier d'un nouvel agent"),
            discord.SelectOption(label="Ajouter une note / sanction",value="ajouter-note",   emoji="📝", description="Ajouter une entrée au casier d'un agent"),
            discord.SelectOption(label="Consulter un casier",        value="consulter",      emoji="🔍", description="Demander l'accès au casier d'un agent"),
            discord.SelectOption(label="Effacer une mention",        value="effacer",        emoji="🧹", description="Demander la suppression d'une mention"),
            discord.SelectOption(label="Rapport disciplinaire",      value="disciplinaire",  emoji="⚖️", description="Ouvrir une procédure disciplinaire"),
            discord.SelectOption(label="Promotion / Changement grade", value="grade",      emoji="🎖️", description="Signaler une promotion ou changement de grade"),
        ]
    )
    async def callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        descs = {
            "ouvrir-casier": (
                "**Formulaire d'ouverture de casier agent**\n\n"
                "Remplis les informations suivantes :\n"
                "• **Nom de l'agent :** \n"
                "• **Grade actuel :** \n"
                "• **Division (GND / DD) :** \n"
                "• **Date d'entrée en service :** \n"
                "• **Matricule :** "
            ),
            "ajouter-note": (
                "**Formulaire d'ajout de note / sanction**\n\n"
                "• **Nom de l'agent concerné :** \n"
                "• **Type d'entrée (avertissement / blâme / suspension / félicitation) :** \n"
                "• **Date des faits :** \n"
                "• **Description détaillée :** \n"
                "• **Pièces jointes / preuves :** "
            ),
            "consulter": (
                "**Demande de consultation de casier**\n\n"
                "• **Nom de l'agent dont tu veux consulter le casier :** \n"
                "• **Raison de la demande :** \n"
                "• **Ton grade et division :** "
            ),
            "effacer": (
                "**Demande d'effacement de mention**\n\n"
                "• **Ton nom d'agent :** \n"
                "• **Mention concernée :** \n"
                "• **Date de la mention :** \n"
                "• **Raisons de ta demande :** "
            ),
            "disciplinaire": (
                "**Ouverture de procédure disciplinaire**\n\n"
                "• **Nom de l'agent mis en cause :** \n"
                "• **Faits reprochés :** \n"
                "• **Date des faits :** \n"
                "• **Témoins éventuels :** \n"
                "• **Preuves disponibles :** "
            ),
            "grade": (
                "**Formulaire de promotion / changement de grade**\n\n"
                "• **Nom de l'agent :** \n"
                "• **Grade actuel :** \n"
                "• **Nouveau grade proposé :** \n"
                "• **Raisons de la promotion :** \n"
                "• **Validé par (supérieur hiérarchique) :** "
            ),
        }
        colors = {
            "ouvrir-casier": discord.Color.green(),   "ajouter-note": discord.Color.orange(),
            "consulter": discord.Color.blue(),         "effacer": discord.Color.greyple(),
            "disciplinaire": discord.Color.dark_red(), "grade": discord.Color.gold(),
        }
        all_staff = self.staff + [self.role_gnd, self.role_dd]
        await create_ticket(interaction, select.values[0], self.cat, all_staff, self.log, descs[select.values[0]], colors.get(select.values[0], discord.Color.greyple()))

# ─── ENVOI D'UN MESSAGE TICKET ───────────────────────────────────────────────

async def send_ticket_message(channel, title, description, view, color=discord.Color.blurple()):
    async for msg in channel.history(limit=20):
        if msg.author == channel.guild.me:
            await msg.delete()
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="MCD Seven • Système de tickets")
    await channel.send(embed=embed, view=view)

# ─── SETUP PRINCIPAL ─────────────────────────────────────────────────────────

async def setup_server(guild):
    print(f"✅ Connecté à : {guild.name}\n")

    existing_roles = {r.name: r for r in guild.roles}
    existing_cats  = {c.name: c for c in guild.categories}
    existing_chans = {c.name: c for c in guild.channels}

    # ── RÔLES ────────────────────────────────────────────────
    print("🔧 Création des rôles...")
    role_fondateur = await get_or_create_role(guild, existing_roles, "👑 Fondateur",          discord.Color.purple(),     hoist=True)
    role_admin     = await get_or_create_role(guild, existing_roles, "⚙️ Administrateur",     discord.Color.gold(),       hoist=True)
    role_modo      = await get_or_create_role(guild, existing_roles, "🛡️ Modérateur",         discord.Color.orange(),     hoist=True)
    role_dd        = await get_or_create_role(guild, existing_roles, "🔍 Detective Division",  discord.Color.red(),        hoist=True)
    role_gnd       = await get_or_create_role(guild, existing_roles, "🚓 GND",                 discord.Color.blue(),       hoist=True)
    role_membre    = await get_or_create_role(guild, existing_roles, "👋 Membre",              discord.Color.green(),      hoist=False)
    role_non_verif = await get_or_create_role(guild, existing_roles, "🔒 Non Vérifié",         discord.Color.light_grey(), hoist=False)

    everyone = guild.default_role
    staff    = [role_fondateur, role_admin, role_modo]

    def s(*extra):
        ow = {everyone: hidden()}
        for r in staff:
            ow[r] = staff_perms()
        for role, perm in extra:
            ow[role] = perm
        return ow

    print("\n🔧 Création des catégories et salons...")

    # ── 📢 GÉNÉRAL ───────────────────────────────────────────
    cat = await make_cat(guild, existing_cats, "📢 Général", s((role_membre, read_write())))
    await make_text(guild, existing_chans, "📜・règlement",     cat, s((role_membre, read_only())))
    await make_text(guild, existing_chans, "📣・annonces",      cat, s((role_membre, read_only())))
    await make_text(guild, existing_chans, "💬・général",       cat, s((role_membre, read_write())))
    await make_text(guild, existing_chans, "🖼️・médias",        cat, s((role_membre, read_write())))
    await make_text(guild, existing_chans, "🤖・commandes-bot", cat, s((role_membre, read_write())))
    await make_voice(guild, existing_chans, "🔊・vocal-général", cat, s((role_membre, read_write())))

    # ── ✅ VÉRIFICATION ──────────────────────────────────────
    cat = await make_cat(guild, existing_cats, "✅ Vérification", s((role_non_verif, read_write()), (role_membre, hidden())))
    await make_text(guild, existing_chans, "✅・vérification", cat)

    # ── 🎭 RÔLES ─────────────────────────────────────────────
    cat = await make_cat(guild, existing_cats, "🎭 Rôles", s((role_membre, read_only())))
    await make_text(guild, existing_chans, "🎭・choisir-son-role", cat)

    # ── 🚓 GND ───────────────────────────────────────────────
    cat = await make_cat(guild, existing_cats, "🚓 GND", s((role_gnd, read_write())))
    await make_text(guild, existing_chans, "📣・annonces-gnd", cat, s((role_gnd, read_only())))
    await make_text(guild, existing_chans, "📋・briefings",    cat, s((role_gnd, read_write())))
    await make_text(guild, existing_chans, "📂・dossiers",     cat, s((role_gnd, read_write())))
    await make_text(guild, existing_chans, "📊・rapports",     cat, s((role_gnd, read_write())))
    await make_voice(guild, existing_chans, "🔊・permanence",  cat, s((role_gnd, read_write())))

    # ── 🔍 DETECTIVE DIVISION ────────────────────────────────
    cat = await make_cat(guild, existing_cats, "🔍 Detective Division", s((role_dd, read_write())))
    await make_text(guild, existing_chans, "📣・annonces-dd",      cat, s((role_dd, read_only())))
    await make_text(guild, existing_chans, "🔍・enquetes-actives", cat, s((role_dd, read_write())))
    await make_text(guild, existing_chans, "📁・preuves",          cat, s((role_dd, read_write())))
    await make_text(guild, existing_chans, "🧠・theories",         cat, s((role_dd, read_write())))
    await make_text(guild, existing_chans, "📋・suspects",         cat, s((role_dd, read_write())))
    await make_voice(guild, existing_chans, "📞・interrogatoires", cat, s((role_dd, read_write())))

    # ── 🔧 ADMINISTRATION ────────────────────────────────────
    cat_admin = await make_cat(guild, existing_cats, "🔧 Administration", s())
    chan_log_general  = await make_text(guild, existing_chans, "📋・logs-messages",  cat_admin)
    await make_text(guild, existing_chans, "👤・logs-membres",   cat_admin)
    await make_text(guild, existing_chans, "🔨・logs-sanctions", cat_admin)
    await make_text(guild, existing_chans, "⚙️・logs-serveur",   cat_admin)
    await make_text(guild, existing_chans, "💬・staff-general",  cat_admin)
    await make_voice(guild, existing_chans, "🔊・reunion-staff", cat_admin)
    chan_log_tickets  = await make_text(guild, existing_chans, "📁・logs-tickets",   cat_admin)

    # ── 🎫 TICKETS — catégorie pour les salons créés ─────────
    cat_tickets = await make_cat(guild, existing_cats, "🎫 Tickets en cours", s())

    # ── 📬 SUPPORT — portail tickets général ─────────────────
    print("\n🎫 Mise en place des portails de tickets...")
    cat_support = await make_cat(guild, existing_cats, "📬 Support", s((role_membre, read_only())))

    chan_general   = await make_text(guild, existing_chans, "🎫・support-général",   cat_support, s((role_membre, read_only())))
    chan_gnd_tick  = await make_text(guild, existing_chans, "🚓・tickets-gnd",       cat_support, s((role_gnd,    read_only()), (role_membre, hidden())))
    chan_dd_tick   = await make_text(guild, existing_chans, "🔍・tickets-dd",        cat_support, s((role_dd,     read_only()), (role_membre, hidden())))
    chan_groupe    = await make_text(guild, existing_chans, "👥・groupes-operations", cat_support, s((role_gnd, read_only()), (role_dd, read_only())))
    chan_casier    = await make_text(guild, existing_chans, "📂・casiers-agents",    cat_support, s((role_gnd, read_only()), (role_dd, read_only())))

    # ── 📂 CASIERS — catégorie dédiée ────────────────────────
    cat_casier = await make_cat(guild, existing_cats, "📂 Casiers Agents", s((role_gnd, read_write()), (role_dd, read_write())))
    await make_text(guild, existing_chans, "📋・index-agents",     cat_casier, s((role_gnd, read_write()), (role_dd, read_write())))
    await make_text(guild, existing_chans, "⚖️・sanctions-actives",cat_casier, s((role_gnd, read_only()),  (role_dd, read_only())))
    await make_text(guild, existing_chans, "🎖️・promotions",       cat_casier, s((role_gnd, read_only()),  (role_dd, read_only())))
    await make_text(guild, existing_chans, "📜・archives-casiers", cat_casier, s())

    # ── ENVOI DES MESSAGES TICKETS ───────────────────────────
    print("📨 Envoi des messages d'interface tickets...")

    await send_ticket_message(
        chan_general,
        "🎫 Support Général — MCD Seven",
        (
            "Besoin d'aide ? Tu as une demande ou un signalement ?\n\n"
            "**Sélectionne le type de ticket dans le menu ci-dessous.**\n\n"
            "❓ Support général\n"
            "🚨 Signalement\n"
            "⚖️ Recours / Appel de sanction\n"
            "📝 Autre demande"
        ),
        TicketGeneralView(staff, cat_tickets, chan_log_tickets),
        discord.Color.blurple()
    )
    print("    ✅ Portail support général envoyé")

    await send_ticket_message(
        chan_gnd_tick,
        "🚓 Tickets GND — MCD Seven",
        (
            "Portail exclusif aux agents de la **GND**.\n\n"
            "**Sélectionne le type de demande dans le menu ci-dessous.**\n\n"
            "📋 Candidature GND\n"
            "📊 Rapport d'intervention\n"
            "👥 Demande de groupe\n"
            "🚨 Signalement interne\n"
            "🔧 Demande d'équipement\n"
            "📝 Autre demande GND"
        ),
        TicketGNDView(staff, role_gnd, cat_tickets, chan_log_tickets),
        discord.Color.blue()
    )
    print("    ✅ Portail GND envoyé")

    await send_ticket_message(
        chan_dd_tick,
        "🔍 Tickets Detective Division — MCD Seven",
        (
            "Portail exclusif aux agents de la **Detective Division**.\n\n"
            "**Sélectionne le type de demande dans le menu ci-dessous.**\n\n"
            "📋 Candidature DD\n"
            "🔎 Ouverture d'enquête\n"
            "📁 Ajout de preuves\n"
            "🚔 Demande d'arrestation\n"
            "👁️ Rapport de surveillance\n"
            "👥 Demande de groupe enquête\n"
            "📝 Autre demande DD"
        ),
        TicketDDView(staff, role_dd, cat_tickets, chan_log_tickets),
        discord.Color.red()
    )
    print("    ✅ Portail Detective Division envoyé")

    await send_ticket_message(
        chan_groupe,
        "👥 Groupes & Opérations — MCD Seven",
        (
            "Portail de gestion des **groupes opérationnels** et **enquêtes à venir**.\n\n"
            "**Sélectionne le type d'opération dans le menu ci-dessous.**\n\n"
            "🆕 Créer un groupe opérationnel\n"
            "➕ Rejoindre un groupe existant\n"
            "📅 Planifier une enquête\n"
            "🤝 Opération conjointe GND + DD\n"
            "📋 Debriefing d'opération\n"
            "🆘 Demande de renfort"
        ),
        TicketGroupeView(staff, role_gnd, role_dd, cat_tickets, chan_log_tickets),
        discord.Color.gold()
    )
    print("    ✅ Portail Groupes & Opérations envoyé")

    await send_ticket_message(
        chan_casier,
        "📂 Casiers Agents — MCD Seven",
        (
            "Portail de gestion des **casiers judiciaires des agents**.\n\n"
            "**Sélectionne l'action souhaitée dans le menu ci-dessous.**\n\n"
            "📂 Ouvrir un casier agent\n"
            "📝 Ajouter une note / sanction\n"
            "🔍 Consulter un casier\n"
            "🧹 Effacer une mention\n"
            "⚖️ Rapport disciplinaire\n"
            "🎖️ Promotion / Changement de grade"
        ),
        CasierView(staff, role_gnd, role_dd, cat_casier, chan_log_tickets),
        discord.Color.dark_gold()
    )
    print("    ✅ Portail Casiers Agents envoyé")

    print("\n" + "="*55)
    print("🎉 Configuration complète terminée avec succès !")
    print("="*55)
    print("📌 Attribue les rôles à tes membres manuellement.")
    print("⚠️  LAISSE CE TERMINAL OUVERT pour que les tickets")
    print("    et boutons fonctionnent en permanence !")
    print("="*55 + "\n")

@client.event
async def on_ready():
    print(f"🤖 Bot connecté : {client.user}\n")
    guild = client.get_guild(GUILD_ID)
    if guild is None:
        print("❌ Serveur introuvable. Vérifie l'ID et que le bot est bien invité.")
        return
    await setup_server(guild)
    print("💤 Bot actif — Ctrl+C pour quitter.\n")

client.run(TOKEN)
