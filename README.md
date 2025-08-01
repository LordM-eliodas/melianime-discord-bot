# 🎭 Melianime Discord Bot

Anime takip ve WordPress entegrasyonu için geliştirilmiş gelişmiş Discord botu.

## ✨ Özellikler

### 🤖 Bot Komutları
- `!ping` - Bot durumunu kontrol et
- `!ara <anime adı>` - AniList'te anime ara
- `!anime <AniList ID>` - Anime detaylarını göster
- `!post-oluştur <anime adı>` - WordPress'te anime postu oluştur
- `!bölüm-ekle <ID> <bölüm> [başlık]` - Animeye yeni bölüm ekle
- `!takip <AniList ID>` - Animeyi takip listesine ekle
- `!takip-listesi` - Takip edilen anime listesini göster
- `!durum` - Bot durumunu göster
- `!yardım` - Yardım menüsünü göster

### 🔗 Entegrasyonlar
- **AniList API** - Anime bilgilerini çekme
- **WordPress API** - Otomatik post oluşturma
- **Movifox API** - Web sitesi entegrasyonu
- **Discord Webhooks** - Bildirim sistemi

### 📊 Veritabanı Özellikleri
- Anime takip sistemi
- Bölüm geçmişi
- Kullanıcı tercihleri
- Konfigürasyon yönetimi

## 🚀 Kurulum

### 1. Gereksinimler
```bash
pip install -r requirements.txt
```

### 2. Ortam Değişkenleri
`env.example` dosyasını `.env` olarak kopyalayın ve değerleri doldurun:

```env
# Discord Bot Configuration
DISCORD_BOT_TOKEN=your_discord_bot_token_here

# WordPress Configuration
WORDPRESS_USERNAME=your_wordpress_username
WORDPRESS_APP_PASSWORD=your_wordpress_app_password
WORDPRESS_API_URL=https://your-wordpress-site.com

# Movifox API Configuration
MOVIFOX_API_URL=https://your-movifox-site.com
MOVIFOX_API_KEY=your_movifox_api_key

# Discord Channel IDs
TARGET_CHANNEL_ID=your_target_channel_id
PURGE_CHANNEL_ID=your_purge_channel_id

# Authorized Users (comma-separated Discord user IDs)
AUTHORIZED_USER_IDS=123456789,987654321

# Bot Owner ID
OWNER_ID=your_discord_user_id

# Debug Mode (true/false)
DEBUG_MODE=false
```

### 3. Discord Bot Oluşturma
1. [Discord Developer Portal](https://discord.com/developers/applications)'a gidin
2. "New Application" oluşturun
3. "Bot" sekmesine gidin ve bot oluşturun
4. Token'ı kopyalayın ve `.env` dosyasına ekleyin
5. Gerekli izinleri verin:
   - Send Messages
   - Embed Links
   - Attach Files
   - Manage Messages
   - Read Message History

### 4. WordPress Ayarları
1. WordPress'te Application Passwords oluşturun
2. REST API'yi etkinleştirin
3. Gerekli izinleri verin

### 5. Botu Çalıştırma
```bash
python main.py
```

## 📋 Kullanım

### Anime Arama
```
!ara Naruto
```
AniList'te anime arar ve sonuçları listeler.

### Anime Detayları
```
!anime 20
```
AniList ID ile anime detaylarını gösterir.

### WordPress Post Oluşturma
```
!post-oluştur Attack on Titan
```
AniList'ten anime bilgilerini alır ve WordPress'te post oluşturur.

### Bölüm Ekleme
```
!bölüm-ekle 20 1 "İlk Bölüm"
```
Belirtilen animeye yeni bölüm ekler.

### Anime Takip
```
!takip 20
```
Animeyi takip listesine ekler.

## 🔧 Gelişmiş Özellikler

### Otomatik Bölüm Kontrolü
Bot her 6 saatte bir takip edilen anime'leri kontrol eder ve yeni bölüm varsa bildirim gönderir.

### Veritabanı Yönetimi
- SQLite veritabanı kullanır
- Anime takip geçmişi
- Bölüm geçmişi
- Kullanıcı tercihleri

### API Entegrasyonları
- **AniList GraphQL API** - Anime bilgileri
- **WordPress REST API** - Post yönetimi
- **Movifox API** - Web sitesi entegrasyonu

## 🛠️ Geliştirme

### Proje Yapısı
```
discord_bot/
├── main.py              # Ana bot dosyası
├── requirements.txt      # Python bağımlılıkları
├── env.example          # Örnek ortam değişkenleri
├── README.md           # Bu dosya
└── melianime_bot.db    # SQLite veritabanı (otomatik oluşur)
```

### Kod Yapısı
- **Modüler tasarım** - Her özellik ayrı fonksiyonlarda
- **Async/await** - Asenkron işlemler
- **Error handling** - Kapsamlı hata yönetimi
- **Logging** - Detaylı log sistemi

### Yeni Özellik Ekleme
1. Yeni komut fonksiyonu ekleyin
2. `@bot.command` decorator'ı kullanın
3. Gerekli izinleri kontrol edin
4. Hata yönetimi ekleyin
5. Logging ekleyin

## 🔒 Güvenlik

### Yetkilendirme
- Bot sahibi kontrolü
- Yetkili kullanıcı listesi
- Komut bazında izin kontrolü

### API Güvenliği
- Token tabanlı kimlik doğrulama
- Rate limiting
- Input sanitization

## 📊 İstatistikler

Bot şu bilgileri takip eder:
- Toplam anime sayısı
- Takip edilen anime sayısı
- Oluşturulan post sayısı
- Eklenen bölüm sayısı

## 🤝 Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Commit yapın (`git commit -m 'Add amazing feature'`)
4. Push yapın (`git push origin feature/amazing-feature`)
5. Pull Request oluşturun

## 📝 Lisans

Bu proje MIT lisansı altında lisanslanmıştır.

## 🆘 Destek

Sorunlar için:
1. GitHub Issues kullanın
2. Discord sunucusuna katılın
3. Dokümantasyonu kontrol edin

## 🔄 Güncellemeler

### v2.0 (Güncel)
- Modern Discord.py kullanımı
- Gelişmiş API entegrasyonları
- Veritabanı sistemi
- Otomatik bölüm kontrolü
- Modern UI/UX

### v1.0
- Temel Discord bot
- WordPress entegrasyonu
- AniList API

---

**🎭 Melianime Bot v2.0** - Anime takip sisteminin geleceği! 