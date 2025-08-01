import discord
import os
import re
import requests
import json
import asyncio
import logging
import base64
import sqlite3
import aiohttp
import time
from datetime import datetime, timedelta
from io import BytesIO
from dotenv import load_dotenv
from discord.ext import commands, tasks
from typing import Optional, List, Dict, Any

# --- 0. Loglama Yapılandırması ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("melianime_bot.log"),
        logging.StreamHandler()
    ])
logger = logging.getLogger('MelianimeBot')

# --- 1. Bot İstemcisi ve Gerekli İzinler ---
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.reactions = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# --- 2. Çevre Değişkenleri ve Sabitler ---
PREFIX = "!"
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"

# Global değişkenler
DISCORD_BOT_TOKEN = None
WORDPRESS_USERNAME = None
WORDPRESS_APP_PASSWORD = None
WORDPRESS_API_URL = None
TARGET_CHANNEL_ID = None
PURGE_CHANNEL_ID = None
AUTHORIZED_USER_IDS = []
ANILIST_API_URL = "https://graphql.anilist.co"
MOVIFOX_API_URL = None

# --- 3. Veritabanı Fonksiyonları ---
DATABASE_NAME = 'melianime_bot.db'

def init_db():
    """Veritabanını başlat ve tabloları oluştur"""
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    
    # Ana konfigürasyon tablosu
    c.execute('''
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Anime takip tablosu
    c.execute('''
        CREATE TABLE IF NOT EXISTS anime_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anilist_id INTEGER UNIQUE,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            last_episode INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Bölüm geçmişi tablosu
    c.execute('''
        CREATE TABLE IF NOT EXISTS episode_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anime_id INTEGER,
            episode_number INTEGER,
            episode_title TEXT,
            wordpress_post_id INTEGER,
            discord_message_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (anime_id) REFERENCES anime_tracking (id)
        )
    ''')
    
    # Kullanıcı tercihleri tablosu
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY,
            notification_enabled BOOLEAN DEFAULT 1,
            preferred_language TEXT DEFAULT 'tr',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Veritabanı başlatıldı ve tablolar oluşturuldu")

def save_config(key: str, value: str):
    """Konfigürasyon kaydet"""
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO config (key, value, updated_at) 
        VALUES (?, ?, CURRENT_TIMESTAMP)
    """, (key, str(value)))
    conn.commit()
    conn.close()
    logger.info(f"Konfigürasyon kaydedildi: {key} = {value}")

def get_config(key: str) -> Optional[str]:
    """Konfigürasyon getir"""
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("SELECT value FROM config WHERE key = ?", (key,))
    result = c.fetchone()
    conn.close()
    if result:
        logger.debug(f"Konfigürasyon yüklendi: {key} = {result[0]}")
        return result[0]
    return None

def add_anime_tracking(anilist_id: int, title: str) -> bool:
    """Anime takip listesine ekle"""
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    try:
        c.execute("""
            INSERT OR REPLACE INTO anime_tracking (anilist_id, title, updated_at) 
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (anilist_id, title))
        conn.commit()
        logger.info(f"Anime takip listesine eklendi: {title} (ID: {anilist_id})")
        return True
    except Exception as e:
        logger.error(f"Anime takip listesine eklenirken hata: {e}")
        return False
    finally:
        conn.close()

def get_tracked_anime() -> List[Dict[str, Any]]:
    """Takip edilen anime listesini getir"""
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT anilist_id, title, last_episode, status, updated_at 
        FROM anime_tracking 
        WHERE status = 'active' 
        ORDER BY updated_at DESC
    """)
    results = c.fetchall()
    conn.close()
    
    return [
        {
            'anilist_id': row[0],
            'title': row[1],
            'last_episode': row[2],
            'status': row[3],
            'updated_at': row[4]
        }
        for row in results
    ]

def update_episode_history(anime_id: int, episode_number: int, episode_title: str, 
                          wordpress_post_id: int, discord_message_id: int) -> bool:
    """Bölüm geçmişini güncelle"""
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO episode_history 
            (anime_id, episode_number, episode_title, wordpress_post_id, discord_message_id) 
            VALUES (?, ?, ?, ?, ?)
        """, (anime_id, episode_number, episode_title, wordpress_post_id, discord_message_id))
        
        # Son bölüm numarasını güncelle
        c.execute("""
            UPDATE anime_tracking 
            SET last_episode = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE anilist_id = ?
        """, (episode_number, anime_id))
        
        conn.commit()
        logger.info(f"Bölüm geçmişi güncellendi: Anime ID {anime_id}, Bölüm {episode_number}")
        return True
    except Exception as e:
        logger.error(f"Bölüm geçmişi güncellenirken hata: {e}")
        return False
    finally:
        conn.close()

# --- 4. Ortam Değişkenlerini Yükleme ---
def check_and_load_environment_variables():
    """Ortam değişkenlerini yükle ve kontrol et"""
    global DISCORD_BOT_TOKEN, WORDPRESS_USERNAME, WORDPRESS_APP_PASSWORD
    global WORDPRESS_API_URL, TARGET_CHANNEL_ID, AUTHORIZED_USER_IDS, PURGE_CHANNEL_ID, MOVIFOX_API_URL
    
    init_db()
    load_dotenv()

    DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    WORDPRESS_USERNAME = os.getenv("WORDPRESS_USERNAME")
    WORDPRESS_APP_PASSWORD = os.getenv("WORDPRESS_APP_PASSWORD")
    WORDPRESS_API_URL = os.getenv("WORDPRESS_API_URL")
    MOVIFOX_API_URL = os.getenv("MOVIFOX_API_URL")

    # Kanal ID'lerini veritabanından yükle
    TARGET_CHANNEL_ID = int(get_config('TARGET_CHANNEL_ID')) if get_config('TARGET_CHANNEL_ID') else int(os.getenv("TARGET_CHANNEL_ID")) if os.getenv("TARGET_CHANNEL_ID") else None
    PURGE_CHANNEL_ID = int(get_config('PURGE_CHANNEL_ID')) if get_config('PURGE_CHANNEL_ID') else int(os.getenv("PURGE_CHANNEL_ID")) if os.getenv("PURGE_CHANNEL_ID") else None

    # Yetkili kullanıcı ID'lerini yükle
    auth_users_str = get_config('AUTHORIZED_USER_IDS') if get_config('AUTHORIZED_USER_IDS') else os.getenv("AUTHORIZED_USER_IDS")
    if auth_users_str:
        AUTHORIZED_USER_IDS = [int(uid.strip()) for uid in auth_users_str.split(',') if uid.strip().isdigit()]

    # Gerekli değişkenlerin kontrolü
    required_vars = {
        'DISCORD_BOT_TOKEN': DISCORD_BOT_TOKEN,
        'WORDPRESS_USERNAME': WORDPRESS_USERNAME,
        'WORDPRESS_APP_PASSWORD': WORDPRESS_APP_PASSWORD,
        'WORDPRESS_API_URL': WORDPRESS_API_URL
    }
    
    missing_vars = [key for key, value in required_vars.items() if not value]
    if missing_vars:
        logger.critical(f"Eksik ortam değişkenleri: {', '.join(missing_vars)}")
        return False

    logger.info("Ortam değişkenleri başarıyla yüklendi.")
    return True

# --- 5. WordPress API Fonksiyonları ---
def get_wordpress_auth_headers():
    """WordPress API için kimlik doğrulama başlıkları"""
    credentials = f"{WORDPRESS_USERNAME}:{WORDPRESS_APP_PASSWORD}"
    token = base64.b64encode(credentials.encode()).decode()
    return {'Authorization': f'Basic {token}', 'Content-Type': 'application/json'}

async def get_wordpress_posts(page=1, per_page=100, status='publish'):
    """WordPress'ten gönderileri al"""
    url = f"{WORDPRESS_API_URL}/wp-json/wp/v2/posts?page={page}&per_page={per_page}&status={status}"
    headers = get_wordpress_auth_headers()
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            else:
                logger.error(f"WordPress gönderileri alınırken hata: {response.status}")
                return None

async def create_wordpress_post(title, content, status='publish', categories=None, tags=None, featured_media=None):
    """WordPress'te yeni gönderi oluştur"""
    url = f"{WORDPRESS_API_URL}/wp-json/wp/v2/posts"
    headers = get_wordpress_auth_headers()
    
    data = {
        'title': title,
        'content': content,
        'status': status,
    }
    
    if categories:
        data['categories'] = categories
    if tags:
        data['tags'] = tags
    if featured_media:
        data['featured_media'] = featured_media

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            if response.status == 201:
                return await response.json()
            else:
                error_text = await response.text()
                logger.error(f"WordPress gönderisi oluşturulurken hata: {response.status} - {error_text}")
                return None

async def upload_media_to_wordpress(file_bytes, filename, mime_type):
    """WordPress'e medya yükle"""
    url = f"{WORDPRESS_API_URL}/wp-json/wp/v2/media"
    headers = get_wordpress_auth_headers()
    headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    headers['Content-Type'] = mime_type

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=file_bytes) as response:
            if response.status == 201:
                return await response.json()
            else:
                error_text = await response.text()
                logger.error(f"WordPress medyası yüklenirken hata: {response.status} - {error_text}")
                return None

# --- 6. AniList API Fonksiyonları ---
async def get_anilist_data(query, variables):
    """AniList API'den veri al"""
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    data = {'query': query, 'variables': variables}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(ANILIST_API_URL, headers=headers, json=data) as response:
            if response.status == 200:
                return await response.json()
            else:
                logger.error(f"AniList API çağrılırken hata: {response.status}")
                return None

async def get_anilist_anime_info(anime_id=None, search_query=None):
    """AniList'ten anime bilgilerini al"""
    query = """
    query ($id: Int, $search: String) {
      Media(id: $id, search: $search, type: ANIME) {
        id
        title {
          romaji
          english
          native
        }
        description(asHtml: false)
        episodes
        status
        startDate { year month day }
        endDate { year month day }
        season
        seasonYear
        coverImage {
          extraLarge
          large
          medium
          color
        }
        bannerImage
        genres
        tags {
          name
        }
        relations {
          edges {
            node {
              type
              id
              title {
                romaji
              }
            }
            relationType
          }
        }
        externalLinks {
          site
          url
        }
        characters {
          edges {
            node {
              name {
                full
              }
            }
          }
        }
        staff {
          edges {
            node {
              name {
                full
              }
            }
          }
        }
        studios(isMain: true) {
          nodes {
            name
          }
        }
      }
    }
    """
    
    variables = {}
    if anime_id:
        variables['id'] = anime_id
    elif search_query:
        variables['search'] = search_query
    else:
        return None

    data = await get_anilist_data(query, variables)
    return data['data']['Media'] if data and 'data' in data else None

async def search_anilist_anime(search_query, limit=10):
    """AniList'te anime ara"""
    query = """
    query ($search: String, $limit: Int) {
      Page(page: 1, perPage: $limit) {
        media(search: $search, type: ANIME) {
          id
          title {
            romaji
            english
            native
          }
          episodes
          status
          coverImage {
            medium
          }
          genres
        }
      }
    }
    """
    
    variables = {'search': search_query, 'limit': limit}
    data = await get_anilist_data(query, variables)
    return data['data']['Page']['media'] if data and 'data' in data else []

# --- 7. Yardımcı Fonksiyonlar ---
def sanitize_filename(name):
    """Dosya adını temizle"""
    return re.sub(r'[\\/:*?"<>|]', '', name)

async def download_image(url):
    """Resim indir"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return BytesIO(await response.read())
                else:
                    logger.error(f"Resim indirilirken hata: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Resim indirilirken hata: {e}")
        return None

def create_anime_embed(anime_data, episode_info=None):
    """Anime için Discord embed oluştur"""
    title = anime_data['title']['romaji'] or anime_data['title']['english'] or anime_data['title']['native']
    
    embed = discord.Embed(
        title=f"🎬 {title}",
        description=anime_data.get('description', 'Açıklama yok.')[:200] + "..." if len(anime_data.get('description', '')) > 200 else anime_data.get('description', 'Açıklama yok.'),
        color=discord.Color.blue(),
        url=f"https://anilist.co/anime/{anime_data['id']}"
    )
    
    # Kapak resmi
    if anime_data.get('coverImage', {}).get('large'):
        embed.set_thumbnail(url=anime_data['coverImage']['large'])
    
    # Banner resmi
    if anime_data.get('bannerImage'):
        embed.set_image(url=anime_data['bannerImage'])
    
    # Temel bilgiler
    embed.add_field(name="📊 Durum", value=anime_data.get('status', 'Bilinmiyor'), inline=True)
    embed.add_field(name="🎭 Bölüm Sayısı", value=anime_data.get('episodes', 'Bilinmiyor'), inline=True)
    embed.add_field(name="📅 Yayın Yılı", value=anime_data.get('seasonYear', 'Bilinmiyor'), inline=True)
    
    # Türler
    if anime_data.get('genres'):
        embed.add_field(name="🎭 Türler", value=", ".join(anime_data['genres'][:5]), inline=False)
    
    # Bölüm bilgisi varsa
    if episode_info:
        embed.add_field(name="🎬 Yeni Bölüm", value=f"Bölüm {episode_info.get('episode', '?')}: {episode_info.get('title', 'Bilinmiyor')}", inline=False)
    
    embed.set_footer(text="Melianime Bot | AniList verileri")
    embed.timestamp = datetime.utcnow()
    
    return embed

# --- 8. Discord Bot Komutları ---
@bot.event
async def on_ready():
    """Bot hazır olduğunda çalışır"""
    logger.info(f'{bot.user} Discord\'a giriş yaptı!')
    print(f'🎭 {bot.user} olarak giriş yaptık!')
    print(f'📊 {len(bot.guilds)} sunucuda aktif')
    print(f'👥 {len(bot.users)} kullanıcıya hizmet veriyoruz')
    
    # Durum mesajını ayarla
    await bot.change_presence(activity=discord.Game(name="!yardım | Anime Takip"))
    
    # Periyodik görevleri başlat
    anime_checker.start()

@bot.event
async def on_command_error(ctx, error):
    """Komut hatalarını yakala"""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Komut bulunamadı! `!yardım` yazarak mevcut komutları görebilirsiniz.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Bu komutu kullanmak için yetkiniz yok!")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Eksik parametre! Kullanım: `{ctx.command.usage}`")
    else:
        logger.error(f"Komut hatası: {error}")
        await ctx.send("❌ Bir hata oluştu. Lütfen daha sonra tekrar deneyin.")

@bot.command(name='ping')
async def ping_command(ctx):
    """Bot'un aktif olup olmadığını kontrol et"""
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Bot gecikmesi: **{latency}ms**",
        color=discord.Color.green()
    )
    embed.set_footer(text=f"İstek: {ctx.author.name}")
    await ctx.send(embed=embed)

@bot.command(name='ara')
async def search_anime(ctx, *, search_query):
    """AniList'te anime ara"""
    await ctx.send(f"🔍 '{search_query}' aranıyor...")
    
    results = await search_anilist_anime(search_query, limit=5)
    
    if not results:
        await ctx.send("❌ Arama sonucu bulunamadı.")
        return
    
    embed = discord.Embed(
        title=f"🔍 '{search_query}' Arama Sonuçları",
        color=discord.Color.blue()
    )
    
    for i, anime in enumerate(results[:5], 1):
        title = anime['title']['romaji'] or anime['title']['english']
        episodes = anime.get('episodes', '?')
        status = anime.get('status', 'Bilinmiyor')
        genres = ", ".join(anime.get('genres', [])[:3])
        
        embed.add_field(
            name=f"{i}. {title}",
            value=f"📊 Bölüm: {episodes} | 🎭 Durum: {status}\n🎭 Türler: {genres}",
            inline=False
        )
    
    embed.set_footer(text="Detaylı bilgi için: !anime <AniList ID>")
    await ctx.send(embed=embed)

@bot.command(name='anime')
async def anime_info(ctx, anime_id: int):
    """AniList ID ile anime bilgilerini göster"""
    await ctx.send(f"🔍 Anime bilgileri alınıyor...")
    
    anime_data = await get_anilist_anime_info(anime_id=anime_id)
    
    if not anime_data:
        await ctx.send("❌ Anime bulunamadı.")
        return
    
    embed = create_anime_embed(anime_data)
    await ctx.send(embed=embed)

@bot.command(name='post-oluştur')
@commands.has_permissions(manage_messages=True)
async def create_post(ctx, *, anime_name):
    """Anime için WordPress postu oluştur"""
    await ctx.send(f"🎬 '{anime_name}' için post oluşturuluyor...")
    
    # AniList'ten anime bilgilerini al
    anime_data = await get_anilist_anime_info(search_query=anime_name)
    
    if not anime_data:
        await ctx.send("❌ AniList'te anime bulunamadı.")
        return
    
    title = anime_data['title']['romaji'] or anime_data['title']['english']
    
    # WordPress'te post oluştur
    post_content = f"""
    <h2>🎬 {title}</h2>
    
    <h3>📊 Anime Bilgileri</h3>
    <ul>
        <li><strong>Durum:</strong> {anime_data.get('status', 'Bilinmiyor')}</li>
        <li><strong>Bölüm Sayısı:</strong> {anime_data.get('episodes', 'Bilinmiyor')}</li>
        <li><strong>Yayın Yılı:</strong> {anime_data.get('seasonYear', 'Bilinmiyor')}</li>
        <li><strong>Türler:</strong> {', '.join(anime_data.get('genres', []))}</li>
    </ul>
    
    <h3>📝 Açıklama</h3>
    <p>{anime_data.get('description', 'Açıklama yok.')}</p>
    """
    
    # Kapak resmini yükle
    featured_media_id = None
    if anime_data.get('coverImage', {}).get('large'):
        cover_image = await download_image(anime_data['coverImage']['large'])
        if cover_image:
            uploaded_media = await upload_media_to_wordpress(
                cover_image.getvalue(),
                f"{sanitize_filename(title)}_cover.jpg",
                'image/jpeg'
            )
            if uploaded_media:
                featured_media_id = uploaded_media['id']
    
    # WordPress'te post oluştur
    created_post = await create_wordpress_post(
        title=title,
        content=post_content,
        featured_media=featured_media_id
    )
    
    if created_post:
        embed = discord.Embed(
            title="✅ Post Başarıyla Oluşturuldu!",
            description=f"**{title}** WordPress'te yayınlandı.",
            color=discord.Color.green(),
            url=created_post['link']
        )
        embed.add_field(name="🔗 Link", value=created_post['link'])
        embed.set_footer(text=f"Oluşturan: {ctx.author.name}")
        await ctx.send(embed=embed)
        
        # Anime takip listesine ekle
        add_anime_tracking(anime_data['id'], title)
    else:
        await ctx.send("❌ Post oluşturulurken hata oluştu.")

@bot.command(name='bölüm-ekle')
@commands.has_permissions(manage_messages=True)
async def add_episode(ctx, anime_id: int, episode_number: int, *, episode_title=None):
    """Animeye yeni bölüm ekle"""
    await ctx.send(f"🎬 Bölüm {episode_number} ekleniyor...")
    
    # AniList'ten anime bilgilerini al
    anime_data = await get_anilist_anime_info(anime_id=anime_id)
    
    if not anime_data:
        await ctx.send("❌ Anime bulunamadı.")
        return
    
    title = anime_data['title']['romaji'] or anime_data['title']['english']
    episode_title = episode_title or f"Bölüm {episode_number}"
    
    # WordPress'te bölüm postu oluştur
    post_content = f"""
    <h2>🎬 {title} - {episode_title}</h2>
    
    <h3>📊 Bölüm Bilgileri</h3>
    <ul>
        <li><strong>Bölüm:</strong> {episode_number}</li>
        <li><strong>Başlık:</strong> {episode_title}</li>
        <li><strong>Eklenme Tarihi:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M')}</li>
    </ul>
    
    <h3>📝 Açıklama</h3>
    <p>Bu bölüm hakkında detaylı bilgi yakında eklenecek.</p>
    """
    
    created_post = await create_wordpress_post(
        title=f"{title} - {episode_title}",
        content=post_content
    )
    
    if created_post:
        # Bölüm geçmişini güncelle
        update_episode_history(anime_id, episode_number, episode_title, created_post['id'], ctx.message.id)
        
        embed = discord.Embed(
            title="✅ Bölüm Başarıyla Eklendi!",
            description=f"**{title}** - {episode_title}",
            color=discord.Color.green(),
            url=created_post['link']
        )
        embed.add_field(name="🔗 Link", value=created_post['link'])
        embed.set_footer(text=f"Ekleyen: {ctx.author.name}")
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Bölüm eklenirken hata oluştu.")

@bot.command(name='takip')
@commands.has_permissions(manage_messages=True)
async def track_anime(ctx, anime_id: int):
    """Animeyi takip listesine ekle"""
    anime_data = await get_anilist_anime_info(anime_id=anime_id)
    
    if not anime_data:
        await ctx.send("❌ Anime bulunamadı.")
        return
    
    title = anime_data['title']['romaji'] or anime_data['title']['english']
    
    if add_anime_tracking(anime_id, title):
        embed = discord.Embed(
            title="✅ Anime Takip Listesine Eklendi!",
            description=f"**{title}** artık takip ediliyor.",
            color=discord.Color.green()
        )
        embed.add_field(name="📊 AniList ID", value=anime_id)
        embed.set_footer(text=f"Ekleyen: {ctx.author.name}")
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Anime takip listesine eklenirken hata oluştu.")

@bot.command(name='takip-listesi')
async def show_tracked_anime(ctx):
    """Takip edilen anime listesini göster"""
    tracked_anime = get_tracked_anime()
    
    if not tracked_anime:
        await ctx.send("📝 Takip edilen anime bulunmuyor.")
        return
    
    embed = discord.Embed(
        title="📋 Takip Edilen Anime Listesi",
        color=discord.Color.blue()
    )
    
    for anime in tracked_anime[:10]:  # İlk 10 anime
        embed.add_field(
            name=f"🎬 {anime['title']}",
            value=f"📊 Son Bölüm: {anime['last_episode']}\n🔄 Durum: {anime['status']}\n📅 Güncelleme: {anime['updated_at']}",
            inline=False
        )
    
    embed.set_footer(text=f"Toplam {len(tracked_anime)} anime takip ediliyor")
    await ctx.send(embed=embed)

@bot.command(name='durum')
async def bot_status(ctx):
    """Bot durumunu göster"""
    embed = discord.Embed(
        title="🤖 Melianime Bot Durumu",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="🟢 Bot Durumu", value="Aktif", inline=True)
    embed.add_field(name="📊 Gecikme", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="🌐 Sunucu Sayısı", value=len(bot.guilds), inline=True)
    embed.add_field(name="👥 Kullanıcı Sayısı", value=len(bot.users), inline=True)
    embed.add_field(name="📝 Takip Edilen Anime", value=len(get_tracked_anime()), inline=True)
    embed.add_field(name="🔗 WordPress", value="Bağlı" if WORDPRESS_API_URL else "Bağlantı Yok", inline=True)
    
    embed.set_footer(text=f"Bot ID: {bot.user.id}")
    embed.timestamp = datetime.utcnow()
    
    await ctx.send(embed=embed)

@bot.command(name='yardım')
async def help_command(ctx):
    """Yardım menüsünü göster"""
    embed = discord.Embed(
        title="🎭 Melianime Bot - Yardım Menüsü",
        description="Anime takip ve WordPress entegrasyonu için geliştirilmiş bot.",
        color=discord.Color.purple()
    )
    
    commands_info = [
        ("!ping", "Bot'un aktif olup olmadığını kontrol eder"),
        ("!ara <anime adı>", "AniList'te anime arar"),
        ("!anime <AniList ID>", "Anime detaylarını gösterir"),
        ("!post-oluştur <anime adı>", "WordPress'te anime postu oluşturur"),
        ("!bölüm-ekle <ID> <bölüm> [başlık]", "Animeye yeni bölüm ekler"),
        ("!takip <AniList ID>", "Animeyi takip listesine ekler"),
        ("!takip-listesi", "Takip edilen anime listesini gösterir"),
        ("!durum", "Bot durumunu gösterir"),
        ("!yardım", "Bu yardım menüsünü gösterir")
    ]
    
    for cmd, desc in commands_info:
        embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
    
    embed.set_footer(text="Melianime Bot v2.0 | Gelişmiş Anime Takip Sistemi")
    await ctx.send(embed=embed)

# --- 9. Periyodik Görevler ---
@tasks.loop(hours=6)
async def anime_checker():
    """Takip edilen anime'leri kontrol et"""
    logger.info("Anime kontrol görevi başlatıldı")
    
    tracked_anime = get_tracked_anime()
    if not tracked_anime:
        return
    
    for anime in tracked_anime:
        try:
            # AniList'ten güncel bilgileri al
            anime_data = await get_anilist_anime_info(anime_id=anime['anilist_id'])
            
            if anime_data and anime_data.get('episodes'):
                current_episodes = anime_data['episodes']
                last_episode = anime['last_episode']
                
                # Yeni bölüm varsa bildir
                if current_episodes and current_episodes > last_episode:
                    embed = discord.Embed(
                        title="🎬 Yeni Bölüm Yayınlandı!",
                        description=f"**{anime['title']}** için yeni bölüm bulundu!",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="📊 Yeni Bölüm", value=f"Bölüm {current_episodes}")
                    embed.add_field(name="📅 Önceki Bölüm", value=f"Bölüm {last_episode}")
                    
                    if TARGET_CHANNEL_ID:
                        channel = bot.get_channel(TARGET_CHANNEL_ID)
                        if channel:
                            await channel.send(embed=embed)
                    
                    logger.info(f"Yeni bölüm bildirimi: {anime['title']} Bölüm {current_episodes}")
                    
        except Exception as e:
            logger.error(f"Anime kontrol hatası ({anime['title']}): {e}")

# --- 10. Bot Başlatma ---
if __name__ == "__main__":
    print("🎭 Melianime Bot v2.0 Başlatılıyor...")
    print("=" * 50)
    
    # Çevre değişkenlerini kontrol et
    if not check_and_load_environment_variables():
        print("❌ Çevre değişkenleri yüklenemedi!")
        exit(1)

    print("✅ Çevre değişkenleri başarıyla yüklendi!")
    print("🔗 Discord'a bağlanılıyor...")
    
    try:
        bot.run(DISCORD_BOT_TOKEN)
    except discord.errors.LoginFailure:
        logger.critical("Discord bot token'ı geçersiz!")
        print("❌ Discord token'ı geçersiz!")
        exit(1)
    except Exception as e:
        logger.critical(f"Bot başlatılırken hata: {e}")
        print(f"❌ Bot başlatılırken hata: {e}")
        exit(1)
