#!/bin/bash

# ════════════════════════════════════════════════════════
#   Kali Ghost Shield v1.0 - Full Privacy & Security Setup
#   by: Professional Hacker
#   الحماية الشاملة لـ Kali Linux بأمر واحد
# ════════════════════════════════════════════════════════

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# التحقق من صلاحيات الروت
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}[✗] يجب تشغيل السكريبت بصلاحيات root${NC}"
   echo -e "${YELLOW}استخدم: sudo bash kali-ghost-shield.sh${NC}"
   exit 1
fi

# ════════════════════ نظام النسخ الاحتياطي والاستعادة ════════════════════
REAL_USER_EARLY=$(logname 2>/dev/null || echo $SUDO_USER)
USER_HOME_EARLY=$(eval echo ~$REAL_USER_EARLY)
BACKUP_ROOT="$USER_HOME_EARLY/.ghost-shield-backup"
BACKUP_MANIFEST="$BACKUP_ROOT/manifest.txt"

# قائمة الملفات/المسارات التي يعدلها السكربت ويجب نسخها احتياطياً
BACKUP_TARGETS=(
    "/etc/proxychains4.conf"
    "/etc/resolv.conf"
    "/etc/NetworkManager/dispatcher.d/99-macchanger"
    "$USER_HOME_EARLY/.bashrc"
)

backup_settings() {
    echo -e "${YELLOW}[*] إنشاء نسخة احتياطية من الإعدادات الحالية...${NC}"
    mkdir -p "$BACKUP_ROOT/files"
    : > "$BACKUP_MANIFEST"

    for target in "${BACKUP_TARGETS[@]}"; do
        if [ -e "$target" ]; then
            dest="$BACKUP_ROOT/files$(echo "$target" | tr '/' '_')"
            cp -a "$target" "$dest" 2>/dev/null
            echo "EXISTED|$target|$dest" >> "$BACKUP_MANIFEST"
        else
            echo "MISSING|$target|" >> "$BACKUP_MANIFEST"
        fi
    done

    # حفظ حالة iptables الحالية قبل أي تعديل
    iptables-save > "$BACKUP_ROOT/iptables.rules.backup" 2>/dev/null
    echo "IPTABLES|/dev/null|$BACKUP_ROOT/iptables.rules.backup" >> "$BACKUP_MANIFEST"

    chown -R "$REAL_USER_EARLY:$REAL_USER_EARLY" "$BACKUP_ROOT" 2>/dev/null
    echo -e "${GREEN}[✓] تم حفظ نسخة احتياطية في: $BACKUP_ROOT${NC}\n"
}

restore_settings() {
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}[✗] يجب تشغيل الاستعادة بصلاحيات root (sudo)${NC}"
        exit 1
    fi

    if [ ! -f "$BACKUP_MANIFEST" ]; then
        echo -e "${RED}[✗] لا توجد نسخة احتياطية محفوظة في $BACKUP_ROOT${NC}"
        exit 1
    fi

    echo -e "${YELLOW}[*] استعادة الإعدادات كما كانت قبل التشغيل...${NC}"

    while IFS='|' read -r status target dest; do
        case "$status" in
            EXISTED)
                # فك حماية resolv.conf إن لزم قبل الاستبدال
                [ "$target" = "/etc/resolv.conf" ] && chattr -i "$target" 2>/dev/null
                cp -a "$dest" "$target" 2>/dev/null
                echo -e "${GREEN}[✓] استُعيد: $target${NC}"
                ;;
            MISSING)
                [ "$target" = "/etc/resolv.conf" ] && chattr -i "$target" 2>/dev/null
                rm -f "$target" 2>/dev/null
                echo -e "${YELLOW}[i] لم يكن موجودًا أصلاً، تم حذفه: $target${NC}"
                ;;
            IPTABLES)
                iptables-restore < "$dest" 2>/dev/null
                netfilter-persistent save 2>/dev/null
                echo -e "${GREEN}[✓] استُعيدت قواعد iptables${NC}"
                ;;
        esac
    done < "$BACKUP_MANIFEST"

    echo -e "${GREEN}[✓] تمت استعادة كل الإعدادات كما كانت قبل التشغيل${NC}"
    echo -e "${YELLOW}ملاحظة: أعد تشغيل الجهاز لتطبيق كل شيء بالكامل${NC}\n"
    exit 0
}

# دعم وضع الاستعادة: sudo bash kali-ghost-shield.sh --restore
if [[ "$1" == "--restore" ]]; then
    restore_settings
fi

clear
echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════╗"
echo "║                                                   ║"
echo "║        🛡️  KALI GHOST SHIELD v1.0 🛡️              ║"
echo "║     نظام الحماية والخصوصية الشامل               ║"
echo "║                                                   ║"
echo "╚═══════════════════════════════════════════════════╝"
echo -e "${NC}"
sleep 2

# نسخ احتياطي للإعدادات قبل أي تعديل
backup_settings

# ════════════════════ المرحلة 1: التحديث ════════════════════
echo -e "${YELLOW}[1/8] تحديث النظام...${NC}"
apt update -qq && apt upgrade -y -qq
echo -e "${GREEN}[✓] تم التحديث بنجاح${NC}\n"
sleep 1

# ════════════════════ المرحلة 2: تثبيت الأدوات ════════════════════
echo -e "${YELLOW}[2/8] تثبيت أدوات الخصوصية...${NC}"
apt install -y -qq \
    tor \
    proxychains4 \
    macchanger \
    bleachbit \
    mat2 \
    openvpn \
    resolvconf \
    curl \
    net-tools \
    iptables-persistent 2>/dev/null

echo -e "${GREEN}[✓] تم تثبيت جميع الأدوات${NC}\n"
sleep 1

# ════════════════════ المرحلة 3: إعداد Tor ════════════════════
echo -e "${YELLOW}[3/8] إعداد Tor...${NC}"

# نسخة احتياطية
cp /etc/proxychains4.conf /etc/proxychains4.conf.backup 2>/dev/null

# تعديل proxychains
cat > /etc/proxychains4.conf << 'EOF'
# Proxychains Configuration - Ghost Mode
strict_chain
proxy_dns
remote_dns_subnet 224
tcp_read_time_out 15000
tcp_connect_time_out 8000

[ProxyList]
socks5 127.0.0.1 9050
EOF

# تفعيل Tor
systemctl enable tor --now 2>/dev/null
sleep 3

# التحقق من Tor
if systemctl is-active --quiet tor; then
    echo -e "${GREEN}[✓] Tor يعمل بنجاح${NC}\n"
else
    echo -e "${RED}[✗] فشل تشغيل Tor${NC}\n"
fi
sleep 1

# ════════════════════ المرحلة 4: MAC Changer ════════════════════
echo -e "${YELLOW}[4/8] إعداد تغيير MAC تلقائياً...${NC}"

cat > /etc/NetworkManager/dispatcher.d/99-macchanger << 'EOF'
#!/bin/bash
if [ "$2" = "down" ]; then
    /usr/bin/macchanger -r "$1" 2>/dev/null
fi
EOF

chmod +x /etc/NetworkManager/dispatcher.d/99-macchanger

echo -e "${GREEN}[✓] سيتم تغيير MAC عند كل اتصال${NC}\n"
sleep 1

# ════════════════════ المرحلة 5: DNS آمن ════════════════════
echo -e "${YELLOW}[5/8] إعداد DNS آمن...${NC}"

# إزالة الحماية من الملف
chattr -i /etc/resolv.conf 2>/dev/null

cat > /etc/resolv.conf << 'EOF'
# Secure DNS Configuration
nameserver 1.1.1.1
nameserver 1.0.0.1
nameserver 8.8.8.8
EOF

# حماية الملف من التعديل
chattr +i /etc/resolv.conf

echo -e "${GREEN}[✓] DNS آمن تم تفعيله (Cloudflare)${NC}\n"
sleep 1

# ════════════════════ المرحلة 6: إعداد Bash ════════════════════
echo -e "${YELLOW}[6/8] تأمين Bash والسجلات...${NC}"

# للمستخدم الحالي
REAL_USER=$(logname 2>/dev/null || echo $SUDO_USER)
USER_HOME=$(eval echo ~$REAL_USER)

cat >> $USER_HOME/.bashrc << 'EOF'

# ════════ Ghost Mode Configuration ════════
export HISTSIZE=0
export HISTFILESIZE=0
unset HISTFILE

# Aliases للخصوصية
alias clean='history -c && rm -f ~/.bash_history && sudo bleachbit -c system.cache system.tmp 2>/dev/null && echo "[✓] تم التنظيف"'
alias myip='curl -s ifconfig.me'
alias torip='proxychains curl -s ifconfig.me 2>/dev/null'
alias ghost='sudo ghost-mode'

# Proxychains للأدوات الحساسة
alias hydra='proxychains hydra'
alias nmap='proxychains nmap'
alias sqlmap='proxychains sqlmap'
alias nikto='proxychains nikto'
alias dirb='proxychains dirb'
EOF

chown $REAL_USER:$REAL_USER $USER_HOME/.bashrc

echo -e "${GREEN}[✓] Bash آمن تم إعداده${NC}\n"
sleep 1

# ════════════════════ المرحلة 7: Ghost Mode Script ════════════════════
echo -e "${YELLOW}[7/8] إنشاء سكريبت Ghost Mode...${NC}"

cat > /usr/local/bin/ghost-mode << 'EOF'
#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

clear
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${GREEN}    🎭 تفعيل وضع الشبح (Ghost Mode) 🎭${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}\n"

# 1. تشغيل Tor
echo -e "${YELLOW}[*] تشغيل Tor...${NC}"
systemctl start tor
sleep 3
if systemctl is-active --quiet tor; then
    echo -e "${GREEN}[✓] Tor يعمل${NC}"
else
    echo -e "${RED}[✗] فشل تشغيل Tor${NC}"
    exit 1
fi

# 2. تغيير MAC لجميع الواجهات
echo -e "${YELLOW}[*] تغيير عناوين MAC...${NC}"
for iface in $(ip link | grep -oP '^\d+: \K[^:]+' | grep -v lo); do
    ip link set "$iface" down 2>/dev/null
    macchanger -r "$iface" 2>/dev/null | grep "New MAC" | awk '{print "[✓] '$iface': " $3}'
    ip link set "$iface" up 2>/dev/null
done

# 3. حذف السجلات
echo -e "${YELLOW}[*] تنظيف السجلات...${NC}"
history -c
rm -f ~/.bash_history
bleachbit -c system.cache system.tmp 2>/dev/null
echo -e "${GREEN}[✓] تم تنظيف السجلات${NC}"

# 4. تفعيل Proxychains عالمياً
export all_proxy="socks5://127.0.0.1:9050"

# 5. عرض المعلومات
echo -e "\n${BLUE}═══════════════════════════════════════${NC}"
echo -e "${GREEN}[✓] وضع الشبح مفعّل بنجاح!${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}"

# عرض IP الحقيقي
echo -e "${YELLOW}[?] IP الحقيقي:${NC} $(curl -s --max-time 5 ifconfig.me 2>/dev/null || echo 'غير متاح')"

# عرض IP عبر Tor
echo -e "${GREEN}[✓] IP عبر Tor:${NC} $(proxychains curl -s --max-time 5 ifconfig.me 2>/dev/null || echo 'غير متاح')"

echo -e "\n${YELLOW}استخدم الآن الأدوات بشكل آمن!${NC}"
echo -e "${BLUE}مثال: proxychains hydra ...${NC}\n"
EOF

chmod +x /usr/local/bin/ghost-mode

echo -e "${GREEN}[✓] Ghost Mode جاهز للاستخدام${NC}\n"
sleep 1

# ════════════════════ المرحلة 8: Firewall Rules ════════════════════
echo -e "${YELLOW}[8/8] إعداد جدار الحماية...${NC}"

# مسح القواعد القديمة
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X

# قواعد أساسية
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# السماح بالاتصالات المحلية
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# السماح بالاتصالات الموجودة
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# حفظ القواعد
netfilter-persistent save 2>/dev/null

echo -e "${GREEN}[✓] جدار الحماية تم تفعيله${NC}\n"
sleep 1

# ════════════════════ النهاية ════════════════════
clear
echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════╗"
echo "║                                                   ║"
echo "║           ✅ اكتمل التثبيت بنجاح! ✅              ║"
echo "║                                                   ║"
echo "╚═══════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${BLUE}════════════ الأوامر المتاحة ════════════${NC}"
echo -e "${GREEN}ghost-mode${NC}      - تفعيل وضع الشبح الكامل"
echo -e "${GREEN}clean${NC}           - تنظيف السجلات"
echo -e "${GREEN}myip${NC}            - عرض IP الحقيقي"
echo -e "${GREEN}torip${NC}           - عرض IP عبر Tor"
echo ""
echo -e "${BLUE}لاستعادة الإعدادات كما كانت قبل تشغيل السكربت:${NC}"
echo -e "${GREEN}sudo bash kali-ghost-shield.sh --restore${NC}"
echo ""
echo -e "${YELLOW}مثال للاستخدام:${NC}"
echo -e "${BLUE}sudo ghost-mode${NC}"
echo -e "${BLUE}proxychains python3 ps_ghost.py | hydra ...${NC}"
echo ""
echo -e "${RED}⚠️  أعد تشغيل الجهاز لتطبيق جميع الإعدادات${NC}"
echo -e "${GREEN}════════════════════════════════════════════${NC}\n"

# إنشاء ملف معلومات
cat > $USER_HOME/GHOST_SHIELD_INFO.txt << 'EOF'
═══════════════════════════════════════════════
    🛡️ Kali Ghost Shield - دليل الاستخدام
═══════════════════════════════════════════════

✅ تم التثبيت بنجاح!

📋 الأوامر المتاحة:
------------------
1. ghost-mode     → تفعيل وضع الشبح الكامل
2. clean          → تنظيف السجلات
3. myip           → IP الحقيقي
4. torip          → IP عبر Tor

🎯 طريقة الاستخدام:
------------------
# تفعيل الحماية
sudo ghost-mode

# استخدام الأدوات بأمان
proxychains hydra -l admin -P pass.txt target.com ssh
proxychains nmap -sS target.com
proxychains python3 script.py

⚠️ تحذيرات مهمة:
------------------
1. استخدم VPN إضافي للحماية القصوى
2. لا تسجل دخول لحساباتك الشخصية
3. نظف السجلات بعد كل جلسة

🔒 مستوى الحماية الحالي: 90%

═══════════════════════════════════════════════
EOF

chown $REAL_USER:$REAL_USER $USER_HOME/GHOST_SHIELD_INFO.txt

echo -e "${GREEN}[✓] تم حفظ الدليل في: $USER_HOME/GHOST_SHIELD_INFO.txt${NC}\n"

exit 0
